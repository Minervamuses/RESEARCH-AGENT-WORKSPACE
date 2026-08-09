"""Multi-turn conversational session for the agent."""

import asyncio
import uuid
from pathlib import Path

from langchain_core.messages import SystemMessage

from skills.citation import SKILL_NAME as CITATION_SKILL_NAME
from agent.turns.results import GraphTurnResult, TurnOutcome
from agent.turns.safety import (
    build_recovery_message,
    final_response_problem,
    has_tool_results,
)

from agent.config import AgentConfig
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
from agent.turns.memory import assemble_prompt_history
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

Local skills (user-activated):
- Skill bundles live under `skills/<name>/`. The user activates one via the `/skill` slash command; you cannot self-activate.
- When a skill is active, its instructions and tool availability arrive as an ephemeral system message — follow them.
- If the user asks what skills are available, discover the bundle names by listing `skills/` via `bash`.

Language policy:
- Respond in the same language the user is writing in.
- When the user writes in Chinese, ALWAYS use Traditional Chinese (繁體中文). Never produce Simplified Chinese characters even if the user's input contains some.
- For other languages, match the user's input language without conversion."""

DEFAULT_RECURSION_LIMIT = 32


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
        mcp_families: dict[str, str] | None = None,
        global_mcp_families: set[str] | frozenset[str] | None = None,
        loaded_skills: list[SkillMetadata] | None = None,
        running_extension_revision: int = 0,
        extension_startup_diagnostics: tuple[str, ...] = (),
    ):
        self.config = config
        self.recursion_limit = recursion_limit
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
        self.session_id = uuid.uuid4().hex
        self.history_store = history_store or get_chat_history_store(config)
        self._turn_journal = TurnJournal(
            config=config,
            session_id=self.session_id,
            history_store=self.history_store,
            app_root_resolver=lambda: find_app_root(),
        )
        self._citation_policy = CitationSessionPolicy(config)
        self.citation_workflow_tool = self._citation_policy.workflow_tool
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

        self._progress_cb = progress_cb
        self._turn_execution_lock = asyncio.Lock()

    @property
    def recent_turns(self) -> list:
        return self._turn_journal.recent_turns

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
        return self._turn_journal.turn_count

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
            all_tool_names=self._tool_universe_refs(),
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
        """Single finalization chokepoint for every turn branch.

        Gate + render happen here, strictly *before* the plan log, recent
        turns, and Chroma history see any text — a blocked draft never
        reaches persistence in any form.
        """
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

    async def enter_plan_mode(self) -> Path:
        """Enable plan mode for newly created turns."""
        return self._turn_journal.enter_plan_mode()

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
        await self._turn_journal.flush()

    async def _execute_graph(
        self,
        *,
        graph,
        user_input: str,
        prompt_history: list,
        skill_state: dict,
        recursion_limit: int,
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
            recursion_limit=recursion_limit,
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
            recursion_limit=self.recursion_limit,
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
        """Persist/log the final answer for one user-visible turn.

        Only ever called through :meth:`finalize_and_record`, so ``answer``
        is already gated/rendered. ``fusion``/``candidate_traces`` are only
        supplied by the fusion extended turn; normal turns, reviser, and
        final validation omit them. Compact fusion metadata reaches
        ``turn_logs[-1]["fusion"]`` only through this ``fusion`` argument,
        never reverse-engineered from rendered text.
        """
        await self._turn_journal.record_turn(
            user_input=user_input,
            answer=answer,
            new_messages=new_messages,
            tool_calls=tool_calls,
            trace_events=trace_events,
            fusion=fusion,
            candidate_traces=candidate_traces,
            validation_errors=validation_errors,
            recovery_reason=recovery_reason,
            citation_save_metrics=citation_save_metrics,
            append_block=self._append_block_to_md,
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

    async def turn_outcome(self, user_input: str) -> TurnOutcome:
        """Core entry point: one finalized turn with text, errors, and trace."""
        async with self._turn_execution_lock:
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
            mcp_families=families,
            global_mcp_families=global_mcp_families,
            loaded_skills=loaded_skills,
            running_extension_revision=extension_startup.revision,
            extension_startup_diagnostics=tuple(runtime_diagnostics),
        )
