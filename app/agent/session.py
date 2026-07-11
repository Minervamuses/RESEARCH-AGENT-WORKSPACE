"""Multi-turn conversational session for the agent."""

import asyncio
import logging
import re
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from skills.citation import SKILL_NAME as CITATION_SKILL_NAME
from skills.citation.confirmation import classify_confirmation
from skills.citation.gate import build_safe_message, check_citations
from skills.citation.render import render_citations
from skills.citation.tool import create_citation_workflow_tool
from skills.citation.types import ConfirmReceipt
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
from agent.skills import (
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
    ):
        self.config = config
        self.recursion_limit = recursion_limit
        self.plan_mode = False
        self.thinking_mode = "normal"
        self.plan_log_path: Path | None = None
        self.active_skill_runtime: SkillRuntime | None = None
        self.extra_tools = list(extra_tools or [])
        self.mcp_families = dict(mcp_families or {})
        self.web_search_tool_names = frozenset(web_search_tool_names or ())

        self.loaded_skills = discover_skills(config)
        self.system_prompt_message = SystemMessage(content=system_prompt)
        self.recent_turns: list[TurnRecord] = []

        self.session_id = uuid.uuid4().hex
        self._turn_counter = 0
        self._current_user_input: ContextVar[str] = ContextVar(
            f"citation_user_input_{self.session_id}", default=""
        )
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
        # the Coordinator behind it is built lazily on first use.
        self.citation_workflow_tool = create_citation_workflow_tool(
            coordinator_getter=lambda: self.citation_coordinator,
            turn_getter=lambda: self._turn_counter,
            user_input_getter=self._current_user_input.get,
        )
        self.graph = build_graph(
            config,
            extra_tools=extra_tools,
            history_store=self.history_store,
            skill_runtime_getter=lambda: self.active_skill_runtime,
            skill_tools=[self.citation_workflow_tool],
            mcp_families=self.mcp_families,
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
        self._citation_coordinator = None

    @property
    def citation_coordinator(self):
        """Session-scoped citation Coordinator over the process provider hub.

        Built lazily on first use: reuses the session's already loaded web
        MCP tool handles (never restarts MCP) and a lazy chat model factory
        for query expansion (no startup probe). Its mutating methods are
        reachable only through the skill-only citation_workflow tool.
        """
        if self._citation_coordinator is None:
            from skills.citation.coordinator import CitationCoordinator
            from skills.citation.hub import get_provider_hub

            web_tools = {
                tool.name: tool
                for tool in self.extra_tools
                if getattr(tool, "name", None) in self.web_search_tool_names
            }

            def _llm_factory(config=self.config):
                from agent.llm import get_chat_model

                return get_chat_model(config)

            self._citation_coordinator = CitationCoordinator(
                get_provider_hub(),
                web_tools=web_tools,
                llm_factory=_llm_factory,
                config=self.config,
            )
        return self._citation_coordinator

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
        coordinator = self._citation_coordinator
        return coordinator.registry if coordinator is not None else None

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

    def _build_citation_confirmation_hint(
        self, user_input: str
    ) -> SystemMessage | None:
        """Map conservative approval language to an ephemeral model hint."""
        if not self.citation_skill_active or self._citation_coordinator is None:
            return None
        matches = self._citation_coordinator.pending_matches()
        if not matches:
            return None
        decision = classify_confirmation(user_input, matches)
        if decision.approved:
            return SystemMessage(content=(
                "[Citation confirmation intent]\n"
                "The current user message is an explicit, unambiguous approval "
                f"of match {decision.match_id}. Call citation_workflow now with "
                f"action=confirm and identifier={decision.match_id}. Do not expose "
                "or paraphrase a DOI; the finalizer will produce the receipt."
            ))
        if decision.status in {"ambiguous", "rejected"}:
            live_ids = ", ".join(match.match_id for match in matches)
            return SystemMessage(content=(
                "[Citation confirmation intent]\n"
                "Do NOT call confirm: the current message is ambiguous, negative, "
                f"or does not safely identify one live match ({live_ids}). Ask the "
                "user to provide an unambiguous approval and, when needed, one mX id."
            ))
        return None

    def _trusted_confirm_receipts(self, new_messages: list) -> list[ConfirmReceipt]:
        """Validate receipt artifacts against the live session registry."""
        registry = self._citation_registry() if self.citation_skill_active else None
        if registry is None:
            return []
        receipts: list[ConfirmReceipt] = []
        seen: set[str] = set()
        for message in new_messages:
            if not isinstance(message, ToolMessage):
                continue
            if getattr(message, "name", None) != "citation_workflow":
                continue
            if getattr(message, "status", "success") != "success":
                continue
            artifact = getattr(message, "artifact", None)
            if artifact is None:
                continue
            try:
                receipt = ConfirmReceipt.from_artifact(artifact)
            except ValueError as exc:
                logger.warning("ignored invalid citation confirm receipt: %s", exc)
                continue
            ref = registry.get(receipt.source_id)
            if (
                ref is None
                or ref.verification_level != receipt.verification_level
                or ref.doi != receipt.accepted_doi
                or ref.bundle_path != receipt.bundle_path
            ):
                logger.warning(
                    "ignored citation confirm receipt that does not match registry: %s",
                    receipt.source_id,
                )
                continue
            if receipt.source_id not in seen:
                receipts.append(receipt)
                seen.add(receipt.source_id)
        return receipts

    @staticmethod
    def _markdown_code_span(value: object) -> str:
        """Render arbitrary one-line trusted data as a Markdown code span."""
        text = str(value).replace("\n", " ")
        longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
        fence = "`" * (longest + 1)
        if text.startswith(("`", " ")) or text.endswith(("`", " ")):
            text = f" {text} "
        return f"{fence}{text}{fence}"

    def _render_confirm_receipts(
        self,
        receipts: list[ConfirmReceipt],
        *,
        validation_errors: list[str],
    ) -> str:
        blocked = bool(validation_errors)
        lines = [
            (
                "（本輪模型草稿未通過 citation 檢查，但 confirm 已成功完成。）"
                if blocked
                else "（引用已確認並保存。）"
            )
        ]
        for receipt in receipts:
            if len(receipts) > 1:
                lines.append(f"- 收據：{self._markdown_code_span(receipt.source_id)}")
                prefix = "  "
            else:
                prefix = "- "
            lines.extend([
                f"{prefix}source ID：{self._markdown_code_span(receipt.source_id)}",
                f"{prefix}DOI：{self._markdown_code_span(receipt.accepted_doi)}",
                f"{prefix}bundle：{self._markdown_code_span(receipt.bundle_path)}",
                f"{prefix}引用標記：{self._markdown_code_span(receipt.cite_marker)}",
                f"{prefix}驗證等級：{self._markdown_code_span(receipt.verification_level)}",
            ])
            for warning in receipt.warnings:
                lines.append(
                    f"{prefix}驗證警告：{self._markdown_code_span(warning)}"
                )
        if blocked:
            lines.append("- 被攔截草稿的檢查結果：")
            lines.extend(
                f"  - {self._markdown_code_span(error)}"
                for error in validation_errors
            )
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
            if ref.verification_level == "identity_verified"
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
        receipts = self._trusted_confirm_receipts(new_messages)
        final_text, errors = self._finalize_answer(str(answer), user_input=user_input)
        if receipts:
            final_text = self._render_confirm_receipts(
                receipts,
                validation_errors=errors,
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

        The Coordinator (and any half-finished workflow, resolved matches,
        and registered SourceRefs) is discarded; bundles already written to
        disk are untouched. The next activation lazily builds a fresh one.
        """
        self._citation_coordinator = None

    def activate_skill(self, name: str, task_mode: str | None = None) -> SkillRuntime:
        """Activate a local skill for subsequent turns.

        Activating the citation skill forces normal thinking (its stateful
        Coordinator must never be shared by parallel fusion candidates).
        Leaving the citation skill — for another skill or none — tears down
        its session state. A failed load leaves the previous skill active.
        """
        runtime = load_skill_runtime(
            name,
            config=self.config,
            all_tools=self._tool_universe_refs(),
            mcp_families=self.mcp_families,
            task_mode=task_mode,
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
        confirmation_hint = self._build_citation_confirmation_hint(user_input)
        merged_system_messages = [
            *([confirmation_hint] if confirmation_hint is not None else []),
            *(extra_system_messages or []),
        ]
        return await self._execute_graph(
            graph=self.graph,
            user_input=user_input,
            prompt_history=self._prompt_history(),
            skill_state=skill_runtime_to_agent_state(self.active_skill_runtime),
            recursion_limit=self.recursion_limit,
            extra_system_messages=merged_system_messages,
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
        token = self._current_user_input.set(user_input)
        try:
            if self.thinking_mode == "extended":
                return await self._run_extended_turn(user_input)
            return await self._run_normal_turn(user_input)
        finally:
            self._current_user_input.reset(token)

    async def turn_outcome(self, user_input: str) -> TurnOutcome:
        """Core entry point: one finalized turn with text, errors, and trace."""
        return await self._run_turn(user_input)

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
        extra_tools: list = []
        if load_mcp:
            from agent.mcp import load_mcp_tools_with_families

            try:
                extra_tools, families = await load_mcp_tools_with_families()
            except Exception:
                extra_tools = []
                families = {}
        else:
            families = {}
        web_search_tool_names = frozenset(
            name for name, family in families.items() if family == "web_search"
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
        )
