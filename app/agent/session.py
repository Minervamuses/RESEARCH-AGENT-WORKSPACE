"""Multi-turn conversational session for the agent."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from skills.citation import SKILL_NAME as CITATION_SKILL_NAME
from agent.turns.results import GraphTurnResult, TurnOutcome
from agent.turns.safety import (
    build_recovery_message,
    final_response_problem,
    has_tool_results,
)

from agent.config import AgentConfig
from agent.conversations import (
    MAX_IDENTIFIER_BYTES,
    MAX_TOOL_ACTIVITIES,
    ConversationConflictError,
    ConversationError,
    ConversationRepository,
    ConversationSnapshot,
    ConversationValidationError,
    FailureInfo,
    ToolActivitySummary,
    is_canonical_uuid4_hex,
)
from agent.conversations.models import validate_project_id
from agent.thinking.orchestrator import FusionOrchestrator
from agent.graph import build_graph
from agent.turns.execution import execute_graph
from agent.turns.trace import format_tool_counts
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
from agent.skills.citation.session_policy import CitationSessionPolicy
from agent.skills.runtime import render_tool_availability_block
from agent.state import skill_runtime_to_agent_state
from agent.tools.access import ToolAccessResolution, resolve_tool_access
from agent.tools import inventory as tool_inventory
from agent.thinking import FusionCandidateTrace
from agent.turns.journal import TurnJournal
from agent.turns.memory import CanonicalTurnView, TurnRecord
from agent.paths import find_app_root

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

Local skills (user-selected, one turn at a time):
- Skill bundles live under `skills/<name>/`. The user selects one with `/<skill-name> <prompt>`; the slash wrapper is removed before the prompt reaches you, and you cannot self-select a skill.
- For that one turn, the selected skill's instructions and tool availability arrive as ephemeral system messages — follow them. They do not persist into the next ordinary turn.
- Citation is the sole persistent exception and is controlled by the dedicated `/citation` command.
- If the user asks what skills are available, discover the bundle names by listing `skills/` via `bash`.

Language policy:
- Respond in the same language the user is writing in.
- When the user writes in Chinese, ALWAYS use Traditional Chinese (繁體中文). Never produce Simplified Chinese characters even if the user's input contains some.
- For other languages, match the user's input language without conversion."""

class ChatSession:
    """Multi-turn conversational retrieval session backed by LangGraph."""

    def __init__(
        self,
        config: AgentConfig,
        system_prompt: str = SYSTEM_PROMPT,
        extra_tools: list | None = None,
        history_store: ChatHistoryStore | None = None,
        progress_cb=None,
        mcp_families: dict[str, str] | None = None,
        global_mcp_families: set[str] | frozenset[str] | None = None,
        loaded_skills: list[SkillMetadata] | None = None,
        running_extension_revision: int = 0,
        extension_startup_diagnostics: tuple[str, ...] = (),
        session_id: str | None = None,
        restored_turns: list[TurnRecord] | None = None,
        conversation_repository: ConversationRepository | None = None,
        project_id: str | None = None,
        bash_approval_handler=None,
        bash_command_runner=None,
    ):
        self.config = config
        self.thinking_mode = "normal"
        self.active_skill_runtime: SkillRuntime | None = None
        self.extra_tools = list(extra_tools or [])
        self.mcp_families = dict(mcp_families or {})
        self.global_mcp_families = frozenset(
            global_mcp_families
            if global_mcp_families is not None
            else {"web_search"}
        )
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
        if restored_turns:
            raise ValueError("legacy restored_turns are not accepted by canonical sessions")
        self.session_id = session_id or uuid.uuid4().hex
        if not is_canonical_uuid4_hex(self.session_id):
            raise ValueError("session_id must be canonical UUIDv4 hex")
        self.project_id = validate_project_id(project_id)
        self.conversation_repository = (
            conversation_repository or ConversationRepository(config.persist_dir)
        )
        self._conversation_snapshot = self.conversation_repository.load_optional(
            self.session_id
        )
        if (
            self._conversation_snapshot is not None
            and self._conversation_snapshot.document.project_id != self.project_id
        ):
            raise ConversationConflictError(
                "conversation belongs to a different project"
            )
        self._recover_interrupted_turn()
        self._active_turn_snapshot: ConversationSnapshot | None = None
        self._active_turn_id: str | None = None
        self.history_store = history_store or get_chat_history_store(config)
        self._turn_journal = TurnJournal(
            config=config,
            session_id=self.session_id,
            history_store=self.history_store,
            app_root_resolver=lambda: find_app_root(),
            restored_turns=restored_turns,
        )
        self._citation_policy = CitationSessionPolicy(config)
        self.citation_workflow_tool = self._citation_policy.workflow_tool
        bash_tool_options = {}
        if bash_approval_handler is not None:
            bash_tool_options["bash_approval_handler"] = bash_approval_handler
        if bash_command_runner is not None:
            bash_tool_options["bash_command_runner"] = bash_command_runner
        self.graph = build_graph(
            config,
            extra_tools=extra_tools,
            history_store=self.history_store,
            skill_runtime_getter=lambda: self.active_skill_runtime,
            skill_tools=[self.citation_workflow_tool],
            mcp_families=self.mcp_families,
            global_mcp_families=self.global_mcp_families,
            **bash_tool_options,
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

        self._progress_cb = progress_cb
        self._turn_execution_lock = asyncio.Lock()
        self._final_text_validator: Callable[[str, list[str]], None] | None = None

    @staticmethod
    def _now_timestamp() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _validate_snapshot_project(
        self,
        snapshot: ConversationSnapshot | None,
    ) -> ConversationSnapshot | None:
        if snapshot is not None and snapshot.document.project_id != self.project_id:
            raise ConversationConflictError(
                "conversation belongs to a different project"
            )
        return snapshot

    def _recover_interrupted_turn(self) -> None:
        snapshot = self._validate_snapshot_project(self._conversation_snapshot)
        if snapshot is None:
            return
        pending = next(
            (turn for turn in snapshot.document.turns if turn.state == "pending"),
            None,
        )
        if pending is None:
            return
        self._conversation_snapshot = self.conversation_repository.fail_turn(
            snapshot,
            turn_id=pending.turn_id,
            state="interrupted",
            failure=FailureInfo(
                code="interrupted",
                message="The previous turn was interrupted before completion.",
                retryable=True,
            ),
            finished_at=self._now_timestamp(),
        )

    def _reload_and_recover(self) -> ConversationSnapshot | None:
        self._conversation_snapshot = self.conversation_repository.load_optional(
            self.session_id
        )
        self._recover_interrupted_turn()
        return self._conversation_snapshot

    @staticmethod
    def _turn_from_snapshot(
        snapshot: ConversationSnapshot,
        turn_id: str,
    ):
        return next(
            (turn for turn in snapshot.document.turns if turn.turn_id == turn_id),
            None,
        )

    async def _begin_persisted_turn(
        self,
        *,
        kind: str,
        display_input: str,
        semantic_input: str | None,
        context_eligible: bool,
        thinking_mode: str | None,
        turn_id: str,
        retry: bool,
    ):
        if not is_canonical_uuid4_hex(turn_id):
            raise ConversationValidationError(
                "turnId must be a canonical lowercase UUIDv4 hex string"
            )
        snapshot = await asyncio.to_thread(self._reload_and_recover)
        values = {
            "turn_id": turn_id,
            "kind": kind,
            "display_input": display_input,
            "semantic_input": semantic_input,
            "context_eligible": context_eligible,
            "thinking_mode": thinking_mode,
        }
        submitted_at = self._now_timestamp()
        if snapshot is None:
            snapshot = await asyncio.to_thread(
                self.conversation_repository.create,
                conversation_id=self.session_id,
                project_id=self.project_id,
                submitted_at=submitted_at,
                **values,
            )
            return snapshot, snapshot.document.turns[-1], False

        existing = self._turn_from_snapshot(snapshot, turn_id)
        if existing is not None:
            snapshot = await asyncio.to_thread(
                self.conversation_repository.append_pending,
                snapshot,
                submitted_at=submitted_at,
                **values,
            )
            existing = self._turn_from_snapshot(snapshot, turn_id)
            assert existing is not None
            if existing.state == "completed":
                return snapshot, existing, True
            if existing.state == "pending":
                raise ConversationConflictError(
                    "turn is already pending and will not be replayed automatically"
                )
            if not retry:
                raise ConversationConflictError(
                    f"turn is {existing.state}; explicit retry is required"
                )
            snapshot = await asyncio.to_thread(
                self.conversation_repository.retry_turn,
                snapshot,
                retry_at=submitted_at,
                **values,
            )
            retried = self._turn_from_snapshot(snapshot, turn_id)
            assert retried is not None
            return snapshot, retried, False

        snapshot = await asyncio.to_thread(
            self.conversation_repository.append_pending,
            snapshot,
            submitted_at=submitted_at,
            **values,
        )
        return snapshot, snapshot.document.turns[-1], False

    async def _begin_turn(
        self,
        *,
        semantic_input: str,
        display_input: str,
        turn_id: str,
        retry: bool,
    ):
        return await self._begin_persisted_turn(
            kind="conversational",
            display_input=display_input,
            semantic_input=semantic_input,
            context_eligible=True,
            thinking_mode=self.thinking_mode,
            turn_id=turn_id,
            retry=retry,
        )

    async def _fail_active_turn(
        self,
        *,
        state: str = "failed",
        code: str = "execution_failed",
        message: str = "The turn could not be completed.",
    ) -> None:
        snapshot = self._active_turn_snapshot
        turn_id = self._active_turn_id
        if snapshot is None or turn_id is None:
            return
        try:
            self._conversation_snapshot = await asyncio.to_thread(
                self.conversation_repository.fail_turn,
                snapshot,
                turn_id=turn_id,
                state=state,
                failure=FailureInfo(
                    code=code,
                    message=message,
                    retryable=True,
                ),
                finished_at=self._now_timestamp(),
            )
            self._active_turn_snapshot = self._conversation_snapshot
        except Exception:
            # Preserve the original execution/finalization failure. A leftover
            # pending turn is deterministically recovered on the next load.
            return

    @staticmethod
    def _tool_activity_summaries(
        tool_calls: list[dict],
        new_messages: list,
    ) -> tuple[ToolActivitySummary, ...]:
        results = {
            str(getattr(message, "tool_call_id", "")): message
            for message in new_messages
            if isinstance(message, ToolMessage)
            and getattr(message, "tool_call_id", None)
        }
        summaries: list[ToolActivitySummary] = []
        for call in tool_calls[:MAX_TOOL_ACTIVITIES]:
            name = call.get("name")
            if not isinstance(name, str):
                continue
            raw_call_id = call.get("id")
            call_id = raw_call_id if isinstance(raw_call_id, str) else None
            if call_id is not None and len(call_id.encode("utf-8")) > MAX_IDENTIFIER_BYTES:
                call_id = None
            result = results.get(call_id or "")
            status = "failed" if getattr(result, "status", None) == "error" else "ok"
            try:
                summaries.append(ToolActivitySummary(
                    call_id=call_id,
                    name=name,
                    status=status,
                    summary=(
                        "Tool execution failed."
                        if status == "failed"
                        else "Tool execution completed."
                    ),
                ))
            except ConversationValidationError:
                continue
        return tuple(summaries)

    def _set_final_text_validator(
        self,
        validator: Callable[[str, list[str]], None],
    ) -> None:
        """Install a desktop-only pre-persistence final-text boundary."""
        self._final_text_validator = validator

    @property
    def recent_turns(self) -> list:
        snapshot = self._conversation_snapshot
        if snapshot is None:
            return []
        completed = [
            turn for turn in snapshot.document.turns if turn.state == "completed"
        ]
        window = self.config.agent_recent_turns_window
        visible = completed[-window:] if window > 0 else []
        return [
            CanonicalTurnView(
                user_input=(turn.semantic_input or turn.display_input),
                assistant_output=turn.assistant_output or "",
                turn_id=turn.turn_number,
                logical_turn_id=turn.turn_id,
                timestamp=turn.finished_at or turn.submitted_at,
                tool_activities=turn.tool_activities,
            )
            for turn in visible
        ]

    @property
    def turn_logs(self) -> list[dict]:
        return self._turn_journal.turn_logs

    @property
    def last_tool_calls(self) -> list[dict]:
        return self._turn_journal.last_tool_calls

    @property
    def plan_mode(self) -> bool:
        return self._turn_journal.plan_mode

    @property
    def plan_log_path(self) -> Path | None:
        return self._turn_journal.plan_log_path

    @property
    def _turn_counter(self) -> int:
        if self._conversation_snapshot is None:
            return 0
        return len(self._conversation_snapshot.document.turns)

    @property
    def _turn_store(self):
        return self._turn_journal.turn_store

    @property
    def _citation_service(self):
        """Return the loaded citation service without constructing it."""
        return self._citation_policy.loaded_service

    @_citation_service.setter
    def _citation_service(self, service) -> None:
        self._citation_policy.set_loaded_service(service)

    @property
    def citation_service(self):
        """Session-scoped CitationService over the process provider hub.

        Built lazily on first use. Its mutating methods are reachable only
        through the skill-only citation_workflow tool.
        """
        return self._citation_policy.service

    def _base_prompt_history(self) -> list:
        snapshot = self._conversation_snapshot
        context = (
            self.conversation_repository.latest_context(snapshot)
            if snapshot is not None
            else ()
        )
        messages = [self.system_prompt_message]
        for turn in context:
            messages.extend([
                HumanMessage(content=turn.user_input),
                AIMessage(content=turn.assistant_output),
            ])
        return messages

    def _prompt_history(self) -> list:
        base = self._base_prompt_history()
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
            all_tool_names=self._tool_universe_refs(),
            mcp_families=self.mcp_families,
        )

    def _build_tool_availability_hint(self) -> SystemMessage | None:
        if self.active_skill_runtime is None:
            return None
        return SystemMessage(content=self._tool_availability_block())

    def _build_plan_mode_hint(self) -> SystemMessage | None:
        """Describe the temporary plan prompt behavior without a storage route."""
        if not self.plan_mode:
            return None
        return SystemMessage(content=(
            "[Mode hint] Plan mode is active for this turn. Focus on analysis "
            "and an actionable plan; conversation durability is unchanged."
        ))

    def _citation_registry(self):
        """The session source registry, or None before first citation use."""
        return self._citation_policy.registry

    def _build_sources_hint(self) -> SystemMessage | None:
        """Inject the visible/recently-activated sources (at most 20).

        Citation-mode only: outside the citation skill there are no citable
        sources, so no hint is rendered and no registry is consulted.
        """
        return self._citation_policy.build_sources_hint(
            citation_active=self.citation_skill_active,
        )

    def _citation_save_metrics(self, new_messages: list) -> CitationSaveMetrics:
        """Aggregate trustworthy item counts across every attempted save batch.

        Save results are returned directly to the model by the tool.  This
        parser exists only for redaction-safe telemetry; it never rewrites the
        model's answer.  Successful receipts are still checked against the
        live registry before they contribute to success counts.
        """
        return self._citation_policy.save_metrics(
            new_messages,
            citation_active=self.citation_skill_active,
        )

    def _finalize_answer(
        self, answer: str, *, user_input: str
    ) -> tuple[str, list[str]]:
        """Apply the mode's citation policy, then render when applicable.

        Citation skill active: markers are checked against the registry's
        identity-verified IDs and the renderer numbers them and appends the
        bibliography. Inactive: registry-backed marker syntax is unavailable
        and the renderer never runs; ordinary citation prose remains allowed.
        Returns ``(final_text,
        validation_errors)``; a violating draft is replaced by the safe
        message and never returned.
        """
        return self._citation_policy.finalize_answer(
            answer,
            user_input=user_input,
            citation_active=self.citation_skill_active,
        )

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
        """Finalize, durably complete, then expose one terminal result."""
        snapshot = self._active_turn_snapshot
        turn_id = self._active_turn_id
        if snapshot is None or turn_id is None:
            raise RuntimeError("finalization requires an active pending turn")
        safety_issue = final_response_problem(
            str(answer),
            tool_names=self._tool_universe_refs(),
        )
        if safety_issue is not None:
            answer = build_recovery_message(
                user_input=user_input,
                had_tool_results=has_tool_results(new_messages),
            )
            recovery_reason = recovery_reason or f"finalizer:{safety_issue}"
        save_metrics = self._citation_save_metrics(new_messages)
        save_call_observed = any(
            action == "save"
            for action, _status in completed_citation_calls(new_messages)
        )
        final_text, errors = self._finalize_answer(str(answer), user_input=user_input)
        if self._final_text_validator is not None:
            self._final_text_validator(final_text, errors)
        log_citation_save_metrics(
            save_metrics,
            save_call_observed=save_call_observed,
        )
        tool_activities = self._tool_activity_summaries(tool_calls, new_messages)
        completed = await asyncio.to_thread(
            self.conversation_repository.complete_turn,
            snapshot,
            turn_id=turn_id,
            assistant_output=final_text,
            finished_at=self._now_timestamp(),
            tool_activities=tool_activities,
        )
        self._conversation_snapshot = completed
        self._active_turn_snapshot = completed
        completed_turn = self._turn_from_snapshot(completed, turn_id)
        assert completed_turn is not None
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
            turn_id=turn_id,
            turn_number=completed_turn.turn_number,
            state="completed",
            accepted=True,
            persisted=True,
        )

    async def enter_plan_mode(self) -> None:
        """Enable temporary plan prompt behavior without a Plan-log writer."""
        return self._turn_journal.enter_plan_mode()

    async def resume_plan_mode(self, log_path: str | Path) -> None:
        """Restore temporary plan control without resuming legacy writes."""
        return self._turn_journal.resume_plan_mode(log_path)

    async def exit_plan_mode(self) -> None:
        """Disable plan mode without mutating prompt-visible turns."""
        self._turn_journal.exit_plan_mode()

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
        self._citation_policy.reset()

    def _load_skill_runtime(self, name: str) -> SkillRuntime:
        """Load one runtime from this session's immutable startup catalog."""
        return load_skill_runtime(
            name,
            config=self.config,
            all_tools=self._tool_universe_refs(),
            mcp_families=self.mcp_families,
            global_mcp_families=self.global_mcp_families,
            catalog=self.loaded_skills,
        )

    def activate_citation_skill(self) -> SkillRuntime:
        """Activate the sole persistent Skill and force normal thinking."""
        runtime = self._load_skill_runtime(CITATION_SKILL_NAME)
        self.active_skill_runtime = runtime
        self.thinking_mode = "normal"
        return runtime

    def deactivate_citation_skill(self) -> None:
        """Deactivate Citation without touching an unrelated transient Skill."""
        if not self.citation_skill_active:
            return
        self.active_skill_runtime = None
        self._teardown_citation_session_state()

    async def _run_one_shot_skill_turn(
        self,
        user_input: str,
        skill_name: str,
    ) -> TurnOutcome:
        """Load, run, and clear one non-Citation Skill under the turn lock."""
        if not user_input.strip():
            raise ValueError("skill prompt cannot be empty")
        if skill_name.casefold() == CITATION_SKILL_NAME.casefold():
            raise ValueError("citation must be controlled with /citation")

        # Loading and validation happen before any active session state changes.
        runtime = self._load_skill_runtime(skill_name)
        previous = self.active_skill_runtime
        self.active_skill_runtime = runtime
        try:
            if previous is not None and previous.name == CITATION_SKILL_NAME:
                self._teardown_citation_session_state()
            return await self._run_turn(user_input)
        finally:
            if self.active_skill_runtime is runtime:
                self.active_skill_runtime = None

    def _tool_universe_refs(self) -> list[str]:
        """Every tool that actually exists in this session, global or skill.

        This is the universe ``resolve_tool_access`` narrows into effective
        tools: local base tools, loaded MCP tools, and the skill-scoped tools
        (e.g. ``citation_workflow``) that only an active skill manifest can
        surface.
        """
        return [
            *tool_inventory.base_tool_names(extra_tools=self.extra_tools),
            self.citation_workflow_tool.name,
        ]

    def _append_block_to_md(self, log_path: str, block: str) -> None:
        # Kept as a facade method: the turn flow (and tests patching this on
        # the instance) must see every plan-log write pass through here.
        self._turn_journal.append_block(log_path, block)

    def _visible_context_text(self) -> str:
        lines: list[str] = []
        snapshot = self._conversation_snapshot
        context = (
            self.conversation_repository.latest_context(snapshot)
            if snapshot is not None
            else ()
        )
        for turn in context:
            lines.extend([
                f"User turn {turn.turn_number}:",
                turn.user_input,
                f"Assistant turn {turn.turn_number}:",
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
        """Compatibility no-op: every canonical state change is write-through."""

    async def _execute_graph(
        self,
        *,
        graph,
        user_input: str,
        prompt_history: list,
        skill_state: dict,
        extra_system_messages: list[SystemMessage] | None = None,
        candidate_id: str | None = None,
    ) -> GraphTurnResult:
        """Internal graph runner shared by the session and fusion proposers.

        ``prompt_history`` and ``skill_state`` are supplied by the caller so a
        proposer can run a cloned graph with directly-injected read-only state,
        while the session default keeps its own active-skill semantics. When
        ``candidate_id`` is set, each emitted tool call and trace event carries
        the candidate id so candidate-scoped rendering never has to guess.
        """
        return await execute_graph(
            graph=graph,
            user_input=user_input,
            prompt_history=prompt_history,
            skill_state=skill_state,
            extra_system_messages=extra_system_messages,
            candidate_id=candidate_id,
            progress_cb=self._progress_cb,
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
            extra_system_messages=extra_system_messages,
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
        """Record non-authoritative diagnostics after durable completion."""
        self._turn_journal.observe_turn(
            user_input=user_input,
            tool_calls=tool_calls,
            trace_events=trace_events,
            fusion=fusion,
            validation_errors=validation_errors,
            recovery_reason=recovery_reason,
            citation_save_metrics=citation_save_metrics,
        )

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

    async def _run_turn(self, user_input: str) -> TurnOutcome:
        """Process one turn through the single finalization chokepoint."""
        if self.thinking_mode == "extended":
            return await self._fusion.run_extended_turn(user_input)
        return await self._run_normal_turn(user_input)

    async def run_display_only_turn(
        self,
        display_input: str,
        action: Callable[[], Awaitable[object]],
        render_result: Callable[[object], str],
        *,
        turn_id: str,
        retry: bool = False,
    ) -> tuple[object | None, TurnOutcome]:
        """Run one local command inside the canonical durable turn lifecycle."""
        async with self._turn_execution_lock:
            snapshot, turn, duplicate = await self._begin_persisted_turn(
                kind="display-only",
                display_input=display_input,
                semantic_input=None,
                context_eligible=False,
                thinking_mode=None,
                turn_id=turn_id,
                retry=retry,
            )
            self._conversation_snapshot = snapshot
            if duplicate:
                assert turn.assistant_output is not None
                return None, TurnOutcome(
                    text=turn.assistant_output,
                    turn_id=turn.turn_id,
                    turn_number=turn.turn_number,
                    state="completed",
                    accepted=True,
                    persisted=True,
                )

            self._active_turn_snapshot = snapshot
            self._active_turn_id = turn_id
            try:
                raw_result = await action()
                final_text = render_result(raw_result)
                if not isinstance(final_text, str) or not final_text.strip():
                    raise ConversationValidationError(
                        "display-only result must be nonblank text"
                    )
                if self._final_text_validator is not None:
                    self._final_text_validator(final_text, [])
                completed = await asyncio.to_thread(
                    self.conversation_repository.complete_turn,
                    snapshot,
                    turn_id=turn_id,
                    assistant_output=final_text,
                    finished_at=self._now_timestamp(),
                )
                self._conversation_snapshot = completed
                self._active_turn_snapshot = completed
                completed_turn = self._turn_from_snapshot(completed, turn_id)
                assert completed_turn is not None
                return raw_result, TurnOutcome(
                    text=final_text,
                    turn_id=turn_id,
                    turn_number=completed_turn.turn_number,
                    state="completed",
                    accepted=True,
                    persisted=True,
                )
            except asyncio.CancelledError:
                await self._fail_active_turn(
                    state="interrupted",
                    code="cancelled",
                    message="The command was cancelled before completion.",
                )
                raise
            except ConversationError:
                await self._fail_active_turn(
                    code="persistence_failed",
                    message="The command result could not be saved.",
                )
                raise
            except Exception:
                await self._fail_active_turn(
                    message="The local command could not be completed.",
                )
                raise
            finally:
                self._active_turn_snapshot = None
                self._active_turn_id = None

    async def turn_outcome(
        self,
        user_input: str,
        *,
        display_input: str | None = None,
        turn_id: str | None = None,
        skill_name: str | None = None,
        retry: bool = False,
    ) -> TurnOutcome:
        """Core entry point: one finalized turn with text, errors, and trace."""
        async with self._turn_execution_lock:
            logical_turn_id = turn_id or uuid.uuid4().hex
            snapshot, turn, duplicate = await self._begin_turn(
                semantic_input=user_input,
                display_input=display_input if display_input is not None else user_input,
                turn_id=logical_turn_id,
                retry=retry,
            )
            self._conversation_snapshot = snapshot
            if duplicate:
                assert turn.assistant_output is not None
                return TurnOutcome(
                    text=turn.assistant_output,
                    turn_id=turn.turn_id,
                    turn_number=turn.turn_number,
                    state="completed",
                    accepted=True,
                    persisted=True,
                )
            self._active_turn_snapshot = snapshot
            self._active_turn_id = logical_turn_id
            try:
                if skill_name is not None:
                    return await self._run_one_shot_skill_turn(
                        user_input,
                        skill_name,
                    )
                return await self._run_turn(user_input)
            except asyncio.CancelledError:
                await self._fail_active_turn(
                    state="interrupted",
                    code="cancelled",
                    message="The turn was cancelled before completion.",
                )
                raise
            except ConversationError:
                await self._fail_active_turn(
                    code="persistence_failed",
                    message="The final response could not be saved.",
                )
                raise
            except Exception:
                await self._fail_active_turn()
                raise
            finally:
                self._active_turn_snapshot = None
                self._active_turn_id = None

    async def turn(
        self,
        user_input: str,
        *,
        display_input: str | None = None,
        turn_id: str | None = None,
        skill_name: str | None = None,
        retry: bool = False,
    ) -> str:
        """Process one conversation turn. Returns the final text response."""
        outcome = await self.turn_outcome(
            user_input,
            display_input=display_input,
            turn_id=turn_id,
            skill_name=skill_name,
            retry=retry,
        )
        return outcome.text

    def status_snapshot(self) -> dict[str, str | int]:
        """Expose lightweight session state for local CLI commands."""
        return {
            "session_id": self.session_id,
            "turn_count": self._turn_counter,
            "recent_turn_count": len(self.recent_turns),
            "graph_recursion_limit": self.config.graph_recursion_limit,
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
        }

    @classmethod
    async def create(
        cls,
        config: AgentConfig,
        system_prompt: str = SYSTEM_PROMPT,
        history_store: ChatHistoryStore | None = None,
        load_mcp: bool = True,
        progress_cb=None,
        session_id: str | None = None,
        restored_turns: list[TurnRecord] | None = None,
        conversation_repository: ConversationRepository | None = None,
        project_id: str | None = None,
        bash_approval_handler=None,
        bash_command_runner=None,
    ) -> "ChatSession":
        """Async factory that loads MCP tools (if enabled) before graph construction.

        MCP tool loading is async; turn processing stays asynchronous via
        graph.astream once the session is built.
        """
        from agent.startup import load_session_startup

        startup = await load_session_startup(config, load_mcp=load_mcp)
        return cls(
            config,
            system_prompt=system_prompt,
            extra_tools=list(startup.extra_tools),
            history_store=history_store,
            progress_cb=progress_cb,
            mcp_families=dict(startup.mcp_families),
            global_mcp_families=startup.global_mcp_families,
            loaded_skills=list(startup.loaded_skills),
            running_extension_revision=startup.running_extension_revision,
            extension_startup_diagnostics=(
                startup.extension_startup_diagnostics
            ),
            session_id=session_id,
            restored_turns=restored_turns,
            conversation_repository=conversation_repository,
            project_id=project_id,
            bash_approval_handler=bash_approval_handler,
            bash_command_runner=bash_command_runner,
        )

    @classmethod
    async def restore(
        cls,
        config: AgentConfig,
        *,
        session_id: str,
        system_prompt: str = SYSTEM_PROMPT,
        history_store: ChatHistoryStore | None = None,
        conversation_repository: ConversationRepository | None = None,
        project_id: str | None = None,
        load_mcp: bool = True,
        progress_cb=None,
    ) -> "ChatSession":
        """Restore one canonical conversation and interrupt a leftover pending turn."""
        if not is_canonical_uuid4_hex(session_id):
            raise ValueError("session_id must be canonical UUIDv4 hex")
        return await cls.create(
            config,
            system_prompt=system_prompt,
            history_store=history_store,
            conversation_repository=conversation_repository,
            project_id=project_id,
            load_mcp=load_mcp,
            progress_cb=progress_cb,
            session_id=session_id,
        )
