"""Multi-turn conversational session for the agent."""

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from skills.citation import SKILL_NAME as CITATION_SKILL_NAME
from skills.citation.gate import build_safe_message, check_citations
from skills.citation.render import render_citations
from skills.citation.tool import create_citation_workflow_tool
from skills.citation.types import (
    SaveBatchOutcome,
    SaveItemOutcome,
    SaveReceipt,
    is_citable_source,
)
from skills.citation.resolution import HostIntentClaim
from skills.citation.service import CitationTurnContext, MutationGuard
from agent.turn_outcome import TurnOutcome
from agent.turn_safety import (
    build_recovery_message,
    content_text,
    final_response_problem,
    has_tool_results,
)

from agent.config import AgentConfig
from agent.fusion import FusionOrchestrator, GraphTurnResult
from agent.graph import build_graph
from agent.history import (
    extract_tool_calls,
    format_tool_counts,
)
from agent.history_rag import ChatHistoryStore, get_chat_history_store
from agent.llm.thinking import (
    get_chat_model_for_role,
    get_fusion_aggregator_model,
)
from agent.observability import (
    CitationSaveMetrics,
    completed_citation_calls,
    log_citation_save_metrics,
)
from agent.skills import (
    SkillMetadata,
    SkillRuntime,
    discover_skills,
    load_skill_runtime,
)
from agent.skills.runtime import render_tool_availability_block
from agent.state import skill_runtime_to_agent_state
from agent.tool_access import ToolAccessResolution, resolve_tool_access
from agent.tools import inventory as tool_inventory
from agent.thinking import FusionCandidateTrace
from agent.memory import (
    TurnRecord,
    assemble_prompt_history,
)
from agent.paths import find_app_root
from agent.plan_log import PlanLog
from agent.turn_store import TurnStore

logger = logging.getLogger(__name__)

# The base tool inventory, its selection policy, and the base workflow are
# owned by agent.tools.inventory (single source of truth). Only the optional
# MCP families, skill activation, and language policy live here.
SYSTEM_PROMPT = f"""You are a research assistant with access to several tool families.

{tool_inventory.render_base_tool_prompt()}

Web Search MCP tools (global once loaded):
- When the Web Search MCP server is configured AND loaded successfully, its tools are available in normal mode and under every skill.
- Being configured does not guarantee availability: trust only the tools actually bound for this session and the [Tool availability] block. If no web tools are bound, treat Web Search as unavailable and fall back to what you have.
- Use for current external information, general web discovery, or topics unlikely to exist in the local KB.

GitHub MCP tools (skill-scoped):
- Available only while an active skill explicitly requests the github MCP family and the server is loaded; never in normal mode.
- Use for remote GitHub state: repository content not in the local KB, pull requests, issues, Actions runs, code search across GitHub.
- Do NOT use GitHub MCP as a substitute for local git shell operations (clone, pull, rebase, commit). Those belong to the user's terminal, not to you.

Local skills (user-activated):
- Skill bundles live under `skills/<name>/`. The user activates one via the `/skill` slash command; you cannot self-activate.
- When a skill is active, its instructions and tool availability arrive as an ephemeral system message — follow them.
- If the user asks what skills are available, discover the bundle names by listing `skills/` via `bash`.

Language policy:
- Respond in the same language the user is writing in.
- When the user writes in Chinese, ALWAYS use Traditional Chinese (繁體中文). Never produce Simplified Chinese characters even if the user's input contains some.
- For other languages, match the user's input language without conversion."""

DEFAULT_RECURSION_LIMIT = 32


@dataclass(frozen=True)
class _ToolRef:
    name: str


class ChatSession:
    """Multi-turn conversational retrieval session backed by LangGraph."""

    def __init__(
        self,
        config: AgentConfig,
        recursion_limit: int = DEFAULT_RECURSION_LIMIT,
        system_prompt: str = SYSTEM_PROMPT,
        extra_tools: list | None = None,
        history_store: ChatHistoryStore | None = None,
        progress_cb=None,
        web_search_tool_names: set[str] | frozenset[str] | None = None,
        mcp_families: dict[str, str] | None = None,
        global_mcp_families: set[str] | frozenset[str] | None = None,
        loaded_skills: list[SkillMetadata] | None = None,
        running_extension_revision: int = 0,
        extension_startup_diagnostics: tuple[str, ...] = (),
    ):
        self.config = config
        self.recursion_limit = recursion_limit
        self.plan_mode = False
        self.thinking_mode = "normal"
        self.plan_log_path: Path | None = None
        self.active_skill_runtime: SkillRuntime | None = None
        self.extra_tools = list(extra_tools or [])
        self.mcp_families = dict(mcp_families or {})
        self.global_mcp_families = frozenset(
            global_mcp_families
            if global_mcp_families is not None
            else {"web_search"}
        )
        self.web_search_tool_names = frozenset(web_search_tool_names or ())

        self.loaded_skills = (
            list(loaded_skills)
            if loaded_skills is not None
            else discover_skills(config)
        )
        self.running_extension_revision = running_extension_revision
        self.extension_startup_diagnostics = tuple(
            extension_startup_diagnostics
        )
        self.system_prompt_message = SystemMessage(content=system_prompt)
        self.recent_turns: list[TurnRecord] = []

        self.session_id = uuid.uuid4().hex
        self._turn_counter = 0
        self.history_store = history_store or get_chat_history_store(config)
        # find_app_root resolves here (not at import), so a monkeypatch of
        # agent.session.find_app_root before construction stays effective.
        self._plan_log = PlanLog(
            config,
            session_id=self.session_id,
            app_root_resolver=lambda: find_app_root(),
        )
        # Shares the recent_turns list by reference: prompt assembly reads it
        # on the facade while TurnStore owns spilling it into the store.
        self._turn_store = TurnStore(
            self.history_store,
            config=config,
            session_id=self.session_id,
            recent_turns=self.recent_turns,
        )
        # Skill-scoped tool: bound into the graph universe but callable only
        # while the citation skill's manifest requests it. Creation is cheap —
        # the session-scoped service behind it is built lazily on first use.
        self.citation_workflow_tool = create_citation_workflow_tool(
            service_getter=lambda: self.citation_service,
            context_getter=lambda: self._citation_turn_context,
        )
        self.graph = build_graph(
            config,
            extra_tools=extra_tools,
            history_store=self.history_store,
            skill_runtime_getter=lambda: self.active_skill_runtime,
            skill_tools=[self.citation_workflow_tool],
            mcp_families=self.mcp_families,
            global_mcp_families=self.global_mcp_families,
        )
        # The graph builder and model getters resolve here (not at import), so
        # monkeypatches of the agent.session module attributes before
        # construction stay effective inside the orchestrator.
        self._fusion = FusionOrchestrator(
            self,
            graph_builder=build_graph,
            role_model_getter=get_chat_model_for_role,
            aggregator_model_getter=get_fusion_aggregator_model,
        )
        self._prompt_master_skill_text_cache: str | None = None

        self.turn_logs: list[dict] = []
        self.last_tool_calls: list[dict] = []
        self.last_trace_events: list[dict] = []

        self._progress_cb = progress_cb
        self._citation_service = None
        self._turn_execution_lock = asyncio.Lock()
        self._citation_turn_context: CitationTurnContext | None = None

    @property
    def citation_service(self):
        """Session-scoped CitationService over the process provider hub.

        Built lazily on first use. Its mutating methods are reachable only
        through the skill-only citation_workflow tool.
        """
        if self._citation_service is None:
            from skills.citation.service import CitationService
            from skills.citation.hub import get_provider_hub
            self._citation_service = CitationService(get_provider_hub(), config=self.config)
        return self._citation_service

    def _prompt_history(self) -> list:
        base = assemble_prompt_history(
            self.system_prompt_message,
            self.recent_turns,
        )
        hints = [
            hint
            for hint in (
                self._build_active_skill_hint(),
                self._build_tool_availability_hint(),
                self._build_plan_mode_hint(),
                self._build_sources_hint(),
            )
            if hint is not None
        ]
        if not hints:
            return base
        return [base[0], *hints, *base[1:]]

    def _build_active_skill_hint(self) -> SystemMessage | None:
        if self.active_skill_runtime is None:
            return None
        return SystemMessage(content=self.active_skill_runtime.context_block())

    def _active_skill_context_block(self) -> str:
        if self.active_skill_runtime is None:
            return ""
        return self.active_skill_runtime.context_block()

    def tool_access_resolution(self) -> ToolAccessResolution:
        """The shared tool access resolution for the current mode.

        The active skill's resolution when one is active; otherwise the
        normal-mode resolution over the session tool universe.
        """
        runtime = self.active_skill_runtime
        if runtime is not None:
            return runtime.tool_access
        return resolve_tool_access(
            None,
            self._tool_universe_refs(),
            mcp_families=self.mcp_families,
            global_mcp_families=self.global_mcp_families,
        )

    def _tool_availability_block(self) -> str:
        runtime = self.active_skill_runtime
        return render_tool_availability_block(
            resolution=self.tool_access_resolution(),
            active_skill=runtime.name if runtime is not None else None,
            task_mode=runtime.task_mode if runtime is not None else None,
            all_tool_names=[tool.name for tool in self._tool_universe_refs()],
            mcp_families=self.mcp_families,
        )

    def _build_tool_availability_hint(self) -> SystemMessage | None:
        if self.active_skill_runtime is None:
            return None
        return SystemMessage(content=self._tool_availability_block())

    def _build_plan_mode_hint(self) -> SystemMessage | None:
        """Tell the LLM that some visible turns are plan-mode (md only),
        so it does not call recall_history looking for them in ChromaDB.
        """
        has_plan_turn = any(
            getattr(turn, "persist_target", "chroma") == "plan_log"
            for turn in self.recent_turns
        )
        if not has_plan_turn:
            return None
        return SystemMessage(content=(
            "[Mode hint] Some turns in the recent context were recorded under "
            "plan mode (stored only in plan_logs/, NOT in ChromaDB). They ARE "
            "visible to you in this prompt - do NOT call recall_history to "
            "look for them."
        ))

    def _citation_registry(self):
        """The session source registry, or None before first citation use."""
        service = self._citation_service
        return service.registry if service is not None else None

    def _build_sources_hint(self) -> SystemMessage | None:
        """Inject the visible/recently-activated sources (at most 20).

        Citation-mode only: outside the citation skill there are no citable
        sources, so no hint is rendered and no registry is consulted.
        """
        if not self.citation_skill_active:
            return None
        registry = self._citation_registry()
        if registry is None:
            return None
        sources = registry.prompt_sources()
        sources = [ref for ref in sources if is_citable_source(ref)]
        if not sources:
            return None
        lines = [
            "[Citable sources] Cite ONLY via these markers; never write raw "
            "DOIs, [1]-style numbers, author-year citations, or a References "
            "section yourself — the renderer numbers sources. Use "
            "[[citation-needed]] when a claim lacks a source.",
        ]
        for ref in sources:
            label = ref.title or ref.doi or ref.url or "(unknown)"
            lines.append(f"- [[cite:{ref.source_id}]] {label}")
        return SystemMessage(content="\n".join(lines))

    @staticmethod
    def _markdown_code_span(value: object) -> str:
        """Render arbitrary one-line trusted data as a Markdown code span."""
        text = str(value).replace("\n", " ")
        longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
        fence = "`" * (longest + 1)
        if text.startswith(("`", " ")) or text.endswith(("`", " ")):
            text = f" {text} "
        return f"{fence}{text}{fence}"

    def _trusted_save_outcomes(
        self, new_messages: list
    ) -> tuple[SaveBatchOutcome | None, tuple[SaveBatchOutcome, ...]]:
        registry = self._citation_registry() if self.citation_skill_active else None
        if registry is None:
            return None, ()
        attempted: list[SaveBatchOutcome] = []
        rejected: list[SaveBatchOutcome] = []
        for message in new_messages:
            if not isinstance(message, ToolMessage) or getattr(message, "name", None) != "citation_workflow":
                continue
            if getattr(message, "status", "success") != "success":
                continue
            artifact = getattr(message, "artifact", None)
            if not isinstance(artifact, dict) or artifact.get("kind") != "citation_save_batch":
                continue
            try:
                batch = SaveBatchOutcome.from_artifact(artifact)
            except ValueError as exc:
                logger.warning("ignored invalid citation save batch: %s", exc)
                continue
            if batch.batch_status == "rejected":
                rejected.append(batch)
                continue
            checked: list[SaveItemOutcome] = []
            for item in batch.items:
                receipt = item.receipt
                if receipt is None:
                    checked.append(item)
                    continue
                ref = registry.get(receipt.source_id)
                if (
                    ref is None
                    or not registry.receipt_is_trusted(receipt)
                    or not is_citable_source(ref)
                ):
                    logger.warning("save receipt/registry mismatch")
                    checked.append(SaveItemOutcome(
                        item.request_index, item.requested_label,
                        "verification_failed", "registry_mismatch",
                        alternatives=item.alternatives,
                    ))
                else:
                    checked.append(item)
            attempted.append(replace(batch, items=tuple(checked)))
        if len(attempted) > 1:
            logger.error("citation invariant breach: multiple attempted save batches")
            first = attempted[0]
            failed = tuple(
                SaveItemOutcome(item.request_index, item.requested_label, "verification_failed", "multiple_attempted_batches")
                for item in first.items
            )
            return replace(first, items=failed), tuple(rejected)
        return (attempted[0] if attempted else None), tuple(rejected)

    @staticmethod
    def _citation_save_metrics(
        attempted: SaveBatchOutcome | None,
        rejected: tuple[SaveBatchOutcome, ...],
    ) -> CitationSaveMetrics:
        if attempted is None:
            return CitationSaveMetrics(
                batch_status="rejected" if rejected else None,
            )
        return CitationSaveMetrics(
            batch_status="attempted",
            new_saved_count=sum(item.status == "saved" for item in attempted.items),
            reused_count=sum(item.status == "reused" for item in attempted.items),
            failed_count=sum(
                item.status not in {"saved", "reused"}
                for item in attempted.items
            ),
        )

    def _render_save_outcome(
        self,
        attempted: SaveBatchOutcome | None,
        rejected: tuple[SaveBatchOutcome, ...],
        *,
        validation_errors: list[str],
    ) -> str:
        reason_messages = {
            "insufficient_identity_anchor": "資訊不足，需補充可辨識的作品資料",
            "intent_binding_ambiguous": "條件無法唯一綁定到批次中的作品",
            "negative_target": "目前語意並未授權保存此作品",
            "identifier_mismatch": "指定識別碼與查得作品不符",
            "multiple_exact_identifiers": "提供了互相衝突的精確識別碼",
            "title_mismatch": "查得標題與指定作品不符",
            "author_mismatch": "查得作者與指定作品不符",
            "hard_year_mismatch": "查得年份違反使用者指定條件",
            "hard_venue_mismatch": "查得 venue 違反使用者指定條件",
            "hard_version_mismatch": "查得版本違反使用者指定條件",
            "version_clarification_required": "版本不明，請分辨要保存的版本",
            "multiple_plausible_records": "找到多筆同樣合理的作品，請補充條件",
            "earliest_manifestation_unknown": "無法判定最早版本",
            "multiple_earliest_manifestations": "找到多筆可能的最早版本，請補充條件",
            "not_original_research": "結果不是所要求的 original research",
            "no_provider_records": "找不到足夠強的書目結果",
            "exact_doi_not_found": "指定 DOI 查無正式書目記錄",
            "exact_arxiv_requires_authority": "指定 arXiv 記錄尚無可保存的權威身分",
            "unsupported_no_doi": "目前版本尚不能保存此無 DOI 來源",
            "all_providers_failed": "書目供應者本次皆失敗",
            "doi_refetch_rate_limited": "DOI 權威查詢遭限流，請稍後重試",
            "doi_refetch_timeout": "DOI 權威查詢逾時，請稍後重試",
            "doi_refetch_failed": "DOI 權威查詢失敗，請稍後重試",
            "refetch_identity_conflict": "DOI 權威資料與指定作品衝突",
            "bibtex_lookup_failed": "無法從 doi.org 取得 BibTeX",
            "bibtex_doi_mismatch": "BibTeX DOI 與查證結果不一致",
            "parse_failed": "BibTeX 無法安全解析",
            "payload_too_large": "BibTeX 資料超過安全大小限制",
            "not_exactly_one_entry": "BibTeX 並非恰好一筆書目",
            "nonempty_preamble": "BibTeX 含不允許的 preamble",
            "bundle_conflict": "既有 bundle 驗證衝突，未覆寫",
            "source_id_collision": "source ID 與既有來源衝突，未覆寫",
            "write_failed": "bundle 寫入失敗",
            "registry_conflict": "來源無法安全登錄至 live registry",
            "registry_mismatch": "保存收據未通過 live registry 驗證",
            "multiple_attempted_batches": "偵測到同輪多個 attempted batch，已 fail closed",
        }
        lines = ["（引用保存結果。）"]
        if attempted is not None:
            for item in sorted(attempted.items, key=lambda value: value.request_index):
                label = self._markdown_code_span(item.requested_label[:160])
                if item.receipt is not None:
                    receipt = item.receipt
                    state = "已保存" if item.status == "saved" else "已重用"
                    lines.extend([
                        f"- {label}：{state}",
                        f"  - source ID：{self._markdown_code_span(receipt.source_id)}",
                        f"  - title：{self._markdown_code_span(receipt.title[:512])}",
                        f"  - year：{self._markdown_code_span(receipt.year or 'unknown')}",
                        f"  - type：{self._markdown_code_span(receipt.work_type[:256])}",
                        f"  - bundle：{self._markdown_code_span(receipt.bundle_path)}",
                        f"  - 引用標記：{self._markdown_code_span(receipt.cite_marker)}",
                    ])
                else:
                    message = reason_messages.get(item.reason_code, item.status.replace("_", " "))
                    lines.append(f"- {label}：{message} ({self._markdown_code_span(item.reason_code)})")
                    for alt in item.alternatives[:5]:
                        facts = " / ".join(str(value) for value in (alt.title[:512], alt.year or "year unknown", alt.venue[:256], alt.version_kind) if value)
                        lines.append(f"  - 可分辨項：{self._markdown_code_span(facts)}")
        if rejected:
            for batch in rejected:
                message = "workflow 正忙，保存嘗試已拒絕" if batch.batch_reason_code == "workflow_busy" else "本輪已嘗試過保存，後續嘗試已拒絕"
                lines.append(f"- {message} ({self._markdown_code_span(batch.batch_reason_code)})")
        if validation_errors:
            lines.append("- 被攔截草稿的檢查結果：")
            lines.extend(f"  - {self._markdown_code_span(error)}" for error in validation_errors)
        return "\n".join(lines)

    def _finalize_answer(
        self, answer: str, *, user_input: str
    ) -> tuple[str, list[str]]:
        """Apply the mode's citation policy, then render when applicable.

        Citation skill active: markers are checked against the registry's
        identity-verified IDs and the renderer numbers them and appends the
        bibliography. Inactive: verified IDs are empty, every citation form
        blocks, and the renderer never runs. Returns ``(final_text,
        validation_errors)``; a violating draft is replaced by the safe
        message and never returned.
        """
        citation_active = self.citation_skill_active
        registry = self._citation_registry() if citation_active else None
        verified_ids = frozenset(
            ref.source_id
            for ref in (registry.list() if registry is not None else [])
            if is_citable_source(ref)
        )
        violations = check_citations(
            answer,
            verified_source_ids=verified_ids,
            citation_active=citation_active,
            user_input=user_input,
        )
        if violations:
            errors = [f"{v.code}: {v.detail}" for v in violations]
            logger.warning(
                "citation gate blocked a draft: %s", [v.code for v in violations]
            )
            safe = build_safe_message(violations, citation_active=citation_active)
            return safe, errors
        if not citation_active:
            return answer, []
        resolve = registry.get if registry is not None else (lambda _sid: None)
        return render_citations(answer, resolve=resolve).text, []

    async def finalize_and_record(
        self,
        *,
        user_input: str,
        answer: str,
        new_messages: list,
        tool_calls: list[dict],
        trace_events: list[dict],
        recovery_reason: str | None = None,
        fusion: dict | None = None,
        candidate_traces=None,
    ) -> TurnOutcome:
        """Single finalization chokepoint for every turn branch.

        Gate + render happen here, strictly *before* the plan log, recent
        turns, and Chroma history see any text — a blocked draft never
        reaches persistence in any form.
        """
        safety_issue = final_response_problem(
            str(answer),
            tool_names=(ref.name for ref in self._tool_universe_refs()),
        )
        if safety_issue is not None:
            answer = build_recovery_message(
                user_input=user_input,
                had_tool_results=has_tool_results(new_messages),
            )
            recovery_reason = recovery_reason or f"finalizer:{safety_issue}"
        save_attempted, save_rejected = self._trusted_save_outcomes(new_messages)
        save_metrics = self._citation_save_metrics(save_attempted, save_rejected)
        save_call_observed = any(
            action == "save"
            for action, _status in completed_citation_calls(new_messages)
        )
        final_text, errors = self._finalize_answer(str(answer), user_input=user_input)
        # A trusted save artifact outranks model prose or a generic fallback.
        if save_attempted is not None or save_rejected:
            final_text = self._render_save_outcome(
                save_attempted, save_rejected, validation_errors=errors
            )
        log_citation_save_metrics(
            save_metrics,
            save_call_observed=save_call_observed,
        )
        await self._record_turn(
            user_input=user_input,
            answer=final_text,
            new_messages=new_messages,
            tool_calls=tool_calls,
            trace_events=trace_events,
            fusion=fusion,
            candidate_traces=candidate_traces,
            validation_errors=errors,
            recovery_reason=recovery_reason,
            citation_save_metrics=save_metrics,
        )
        return TurnOutcome(
            text=final_text,
            validation_errors=errors,
            tool_calls=tool_calls,
        )

    async def _store_turn(self, turn: TurnRecord) -> None:
        await self._turn_store.store_turn(turn)

    async def enter_plan_mode(self) -> Path:
        """Enable plan mode for newly created turns."""
        if self.plan_mode:
            if self.plan_log_path is None:
                self.plan_log_path = self._plan_log.new_log_file()
            return self.plan_log_path
        self.plan_log_path = self._plan_log.new_log_file()
        self.plan_mode = True
        return self.plan_log_path

    async def exit_plan_mode(self) -> None:
        """Disable plan mode without mutating prompt-visible turns."""
        self.plan_mode = False
        self.plan_log_path = None

    def set_thinking_mode(self, mode: str) -> None:
        """Set the per-session thinking workflow mode."""
        normalized = mode.strip().lower()
        if normalized not in {"normal", "extended"}:
            raise ValueError(f"unknown thinking mode: {mode}")
        if normalized == "extended" and self.citation_skill_active:
            raise ValueError(
                "extended thinking is unavailable while the citation skill "
                "is active; deactivate it first (/citation off)"
            )
        self.thinking_mode = normalized

    @property
    def citation_skill_active(self) -> bool:
        """Whether the built-in citation skill is the active skill."""
        runtime = self.active_skill_runtime
        return runtime is not None and runtime.name == CITATION_SKILL_NAME

    def _teardown_citation_session_state(self) -> None:
        """Drop the in-memory workflow and source registry on deactivation.

        The service and its registered SourceRefs are discarded; bundles
        already written to disk are untouched. The next activation lazily
        builds a fresh service.
        """
        self._citation_service = None

    def activate_skill(self, name: str, task_mode: str | None = None) -> SkillRuntime:
        """Activate a local skill for subsequent turns.

        Activating the citation skill forces normal thinking (its session
        registry must never be shared by parallel fusion candidates).
        Leaving the citation skill — for another skill or none — tears down
        its session state. A failed load leaves the previous skill active.
        """
        runtime = load_skill_runtime(
            name,
            config=self.config,
            all_tools=self._tool_universe_refs(),
            mcp_families=self.mcp_families,
            global_mcp_families=self.global_mcp_families,
            task_mode=task_mode,
            catalog=self.loaded_skills,
        )
        previous = self.active_skill_runtime
        self.active_skill_runtime = runtime
        if runtime.name == CITATION_SKILL_NAME:
            self.thinking_mode = "normal"
        elif previous is not None and previous.name == CITATION_SKILL_NAME:
            self._teardown_citation_session_state()
        return runtime

    def deactivate_skill(self) -> None:
        """Deactivate the current local skill, if any."""
        was_citation = self.citation_skill_active
        self.active_skill_runtime = None
        if was_citation:
            self._teardown_citation_session_state()

    def _all_tool_refs(self) -> list[_ToolRef]:
        return [
            _ToolRef(name)
            for name in tool_inventory.base_tool_names(extra_tools=self.extra_tools)
        ]

    def _tool_universe_refs(self) -> list[_ToolRef]:
        """Every tool that actually exists in this session, global or skill.

        This is the universe ``resolve_tool_access`` narrows into effective
        tools: local base tools, loaded MCP tools, and the skill-scoped tools
        (e.g. ``citation_workflow``) that only an active skill manifest can
        surface.
        """
        return [
            *self._all_tool_refs(),
            _ToolRef(self.citation_workflow_tool.name),
        ]

    def _append_block_to_md(self, log_path: str, block: str) -> None:
        # Kept as a facade method: the turn flow (and tests patching this on
        # the instance) must see every plan-log write pass through here.
        self._plan_log.append_block(log_path, block)

    def _visible_context_text(self) -> str:
        lines: list[str] = []
        for turn in self.recent_turns[-self.config.agent_recent_turns_window:]:
            lines.extend([
                f"User turn {turn.turn_id}:",
                turn.user_input,
                f"Assistant turn {turn.turn_id}:",
                turn.assistant_output,
                "",
            ])
        return "\n".join(lines).strip()

    def _prompt_master_skill_text(self) -> str:
        if self._prompt_master_skill_text_cache is None:
            path = find_app_root() / "skills" / "_prompt-master" / "SKILL.md"
            self._prompt_master_skill_text_cache = path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        return self._prompt_master_skill_text_cache

    async def flush_recent_turns(self) -> None:
        """Persist all prompt-visible turns before the session is discarded."""
        await self._turn_store.flush()

    async def _execute_graph(
        self,
        *,
        graph,
        user_input: str,
        prompt_history: list,
        skill_state: dict,
        recursion_limit: int,
        extra_system_messages: list[SystemMessage] | None = None,
        trace_label: str = "writer",
        candidate_id: str | None = None,
    ) -> GraphTurnResult:
        """Internal graph runner shared by the session and fusion proposers.

        ``prompt_history`` and ``skill_state`` are supplied by the caller so a
        proposer can run a cloned graph with directly-injected read-only state,
        while the session default keeps its own active-skill semantics. When
        ``candidate_id`` is set, each emitted tool call and trace event carries
        the candidate id so candidate-scoped rendering never has to guess.
        """
        del trace_label  # reserved for future structured tracing; documents intent
        input_messages = [
            *prompt_history,
            *(extra_system_messages or []),
            HumanMessage(content=user_input),
        ]
        messages: list = list(input_messages)
        initial_state = {
            "messages": input_messages,
            **skill_state,
        }
        async for update in graph.astream(
            initial_state,
            config={"recursion_limit": recursion_limit},
            stream_mode="updates",
        ):
            for node_name, delta in update.items():
                new_msgs = delta.get("messages", []) if isinstance(delta, dict) else []
                messages.extend(new_msgs)
                if self._progress_cb is not None:
                    self._progress_cb(node_name, new_msgs)
        new_messages = messages[len(input_messages):]
        tool_calls = extract_tool_calls(new_messages)
        if candidate_id is not None:
            tool_calls = [{**call, "candidate_id": candidate_id} for call in tool_calls]
        trace_events = [
            {
                "type": "tool",
                "name": call["name"],
                "args": call["args"],
                "id": call.get("id"),
                **({"candidate_id": candidate_id} if candidate_id is not None else {}),
            }
            for call in tool_calls
        ]
        answer = content_text(messages[-1].content) if messages else ""
        last_ai = next(
            (
                message
                for message in reversed(new_messages)
                if isinstance(message, AIMessage)
            ),
            None,
        )
        recovery_reason = None
        if last_ai is not None:
            recovery_reason = (last_ai.response_metadata or {}).get("turn_recovery")

        return GraphTurnResult(
            answer=answer,
            new_messages=new_messages,
            tool_calls=tool_calls,
            trace_events=trace_events,
            recovery_reason=recovery_reason,
        )

    async def _run_graph_turn(
        self,
        user_input: str,
        *,
        extra_system_messages: list[SystemMessage] | None = None,
    ) -> GraphTurnResult:
        """Run the session graph once with session policy (no candidate scope)."""
        return await self._execute_graph(
            graph=self.graph,
            user_input=user_input,
            prompt_history=self._prompt_history(),
            skill_state=skill_runtime_to_agent_state(self.active_skill_runtime),
            recursion_limit=self.recursion_limit,
            extra_system_messages=extra_system_messages,
            trace_label="writer",
            candidate_id=None,
        )

    async def _record_turn(
        self,
        *,
        user_input: str,
        answer: str,
        new_messages: list,
        tool_calls: list[dict],
        trace_events: list[dict],
        fusion: dict | None = None,
        candidate_traces: list[FusionCandidateTrace] | None = None,
        validation_errors: list[str] | None = None,
        recovery_reason: str | None = None,
        citation_save_metrics: CitationSaveMetrics,
    ) -> None:
        """Persist/log the final answer for one user-visible turn.

        Only ever called through :meth:`finalize_and_record`, so ``answer``
        is already gated/rendered. ``fusion``/``candidate_traces`` are only
        supplied by the fusion extended turn; normal turns, reviser, and
        final validation omit them. Compact fusion metadata reaches
        ``turn_logs[-1]["fusion"]`` only through this ``fusion`` argument,
        never reverse-engineered from rendered text.
        """
        turn_id = self._turn_counter + 1
        timestamp = datetime.now(timezone.utc).isoformat()
        if self.plan_mode:
            if self.plan_log_path is None:
                raise RuntimeError("plan mode is enabled without a log path")
            target = "plan_log"
            log_path = str(self.plan_log_path)
            try:
                block = self._plan_log.render_block(
                    turn_id=turn_id,
                    timestamp=timestamp,
                    user_input=user_input,
                    answer=answer,
                    new_messages=new_messages,
                    tool_calls=tool_calls,
                    candidate_traces=candidate_traces,
                )
                await asyncio.to_thread(self._append_block_to_md, log_path, block)
            except Exception as exc:
                logger.error("plan md write failed for turn %s: %s", turn_id, exc)
                raise
        else:
            target = "chroma"
            log_path = None

        self._turn_counter = turn_id
        self.recent_turns.append(
            TurnRecord(
                user_input=user_input,
                assistant_output=answer,
                turn_id=turn_id,
                timestamp=timestamp,
                persist_target=target,
                log_path=log_path,
            )
        )
        self.last_tool_calls = tool_calls
        self.last_trace_events = trace_events
        self.turn_logs.append({
            "user_input": user_input,
            "tool_calls": tool_calls,
            "trace_events": trace_events,
            "tool_counts": format_tool_counts(tool_calls),
            "fusion": fusion,
            "validation_errors": list(validation_errors or []),
            "recovery": recovery_reason,
            **citation_save_metrics.to_record(),
        })
        await self._turn_store.evict_overflow()

    async def _run_normal_turn(self, user_input: str) -> TurnOutcome:
        result = await self._run_graph_turn(user_input)
        return await self.finalize_and_record(
            user_input=user_input,
            answer=result.answer,
            new_messages=result.new_messages,
            tool_calls=result.tool_calls,
            trace_events=result.trace_events,
            recovery_reason=result.recovery_reason,
        )

    async def _run_extended_turn(self, user_input: str) -> TurnOutcome:
        return await self._fusion.run_extended_turn(user_input)

    async def _run_turn(self, user_input: str) -> TurnOutcome:
        """Process one turn through the single finalization chokepoint."""
        if self.thinking_mode == "extended":
            return await self._run_extended_turn(user_input)
        return await self._run_normal_turn(user_input)

    async def turn_outcome(self, user_input: str) -> TurnOutcome:
        """Core entry point: one finalized turn with text, errors, and trace."""
        async with self._turn_execution_lock:
            context = CitationTurnContext(
                uuid.uuid4().hex,
                tuple(self._extract_citation_claims(user_input)),
                MutationGuard(),
            )
            self._citation_turn_context = context
            try:
                return await self._run_turn(user_input)
            finally:
                if self._citation_turn_context is context:
                    self._citation_turn_context = None

    @staticmethod
    def _extract_citation_claims(text: str) -> list[HostIntentClaim]:
        """Extract only explicit current-turn anchors; never infer a version."""
        from skills.citation.doi import extract_doi_candidates

        claims = [HostIntentClaim("doi", doi) for doi in extract_doi_candidates(text)]
        for match in re.finditer(r"(?:arxiv\s*[:：]?\s*)?(\d{4}\.\d{4,5})(?:v\d+)?", text, re.I):
            claims.append(HostIntentClaim("arxiv", match.group(1), span=match.span()))
        lowered = text.casefold()
        if re.search(r"(?:original research|原創研究|原始研究)", lowered):
            claims.append(HostIntentClaim("work_kind", "original_research"))
        elif re.search(r"(?:\boriginal\b|原始|原版)", lowered):
            claims.append(HostIntentClaim("original", "original"))
        if re.search(r"(?:正式版|出版版|published|version of record|\bvor\b)", lowered):
            claims.append(HostIntentClaim("version_kind", "published"))
        if re.search(r"(?:預印本|preprint|arxiv\s*版)", lowered):
            claims.append(HostIntentClaim("version_kind", "preprint"))
        if re.search(
            r"(?:\brepository\b|"
            r"accepted\s+manuscript|institutional\s+repository\s+version|"
            r"接受稿|作者接受稿|機構典藏版|典藏版本)",
            lowered,
        ):
            claims.append(HostIntentClaim("version_kind", "repository"))
        if re.search(
            r"(?:\brepost(?:ed)?\b|reposted\s+version|轉載版|重貼版|再發布版)",
            lowered,
        ):
            claims.append(HostIntentClaim("version_kind", "repost"))
        if re.search(r"(?:最早版本|earliest manifestation|first manifestation)", lowered):
            claims.append(HostIntentClaim("version_kind", "earliest"))
        years = re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", text)
        if len(set(years)) == 1:
            claims.append(HostIntentClaim("year", years[0]))
        return claims

    async def turn(self, user_input: str) -> str:
        """Process one conversation turn. Returns the final text response."""
        outcome = await self.turn_outcome(user_input)
        return outcome.text

    def status_snapshot(self) -> dict[str, str | int]:
        """Expose lightweight session state for local CLI commands."""
        return {
            "session_id": self.session_id,
            "turn_count": self._turn_counter,
            "recent_turn_count": len(self.recent_turns),
            "recursion_limit": self.recursion_limit,
            "last_tool_counts": format_tool_counts(self.last_tool_calls) or "none",
            "plan_mode": self.plan_mode,
            "plan_log_path": str(self.plan_log_path) if self.plan_log_path else "",
            "thinking_mode": self.thinking_mode,
            "mcp_families": (
                ", ".join(sorted(set(self.mcp_families.values()))) or "none"
            ),
            "extension_revision": self.running_extension_revision,
            "extension_diagnostics": "; ".join(
                self.extension_startup_diagnostics
            ),
            "active_skill": (
                self.active_skill_runtime.name
                if self.active_skill_runtime is not None
                else ""
            ),
            "task_mode": (
                self.active_skill_runtime.task_mode
                if self.active_skill_runtime is not None and self.active_skill_runtime.task_mode
                else ""
            ),
        }

    async def turn_with_trace(self, user_input: str) -> tuple[str, list[dict]]:
        """Compatibility wrapper over :meth:`turn_outcome`."""
        outcome = await self.turn_outcome(user_input)
        return outcome.text, outcome.tool_calls

    @classmethod
    async def create(
        cls,
        config: AgentConfig,
        recursion_limit: int = DEFAULT_RECURSION_LIMIT,
        system_prompt: str = SYSTEM_PROMPT,
        history_store: ChatHistoryStore | None = None,
        load_mcp: bool = True,
        progress_cb=None,
    ) -> "ChatSession":
        """Async factory that loads MCP tools (if enabled) before graph construction.

        MCP tool loading is async; turn processing stays asynchronous via
        graph.astream once the session is built.
        """
        builtin_skills = discover_skills(config)
        from agent.extensions.startup import load_extension_startup

        extension_startup = load_extension_startup(
            config,
            builtin_skills=builtin_skills,
        )
        loaded_skills = [*builtin_skills, *extension_startup.skills]
        runtime_diagnostics = list(extension_startup.diagnostics)
        extra_tools: list = []
        if load_mcp:
            from agent.mcp import (
                load_mcp_tools_with_families,
                resolve_mcp_specs,
            )

            try:
                if extension_startup.mcp_specs:
                    specs = [
                        *resolve_mcp_specs(),
                        *extension_startup.mcp_specs,
                    ]
                    extra_tools, families = await load_mcp_tools_with_families(
                        specs=specs,
                        diagnostics=runtime_diagnostics,
                    )
                else:
                    extra_tools, families = await load_mcp_tools_with_families()
            except Exception as exc:
                extra_tools = []
                families = {}
                runtime_diagnostics.append(
                    "MCP loader unavailable: " + type(exc).__name__
                )
        else:
            families = {}
        web_search_tool_names = frozenset(
            name for name, family in families.items() if family == "web_search"
        )
        global_mcp_families = frozenset(
            {"web_search", *extension_startup.global_mcp_families}
        )
        return cls(
            config,
            recursion_limit=recursion_limit,
            system_prompt=system_prompt,
            extra_tools=extra_tools,
            history_store=history_store,
            progress_cb=progress_cb,
            web_search_tool_names=web_search_tool_names,
            mcp_families=families,
            global_mcp_families=global_mcp_families,
            loaded_skills=loaded_skills,
            running_extension_revision=extension_startup.revision,
            extension_startup_diagnostics=tuple(runtime_diagnostics),
        )
