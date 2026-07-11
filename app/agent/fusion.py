"""Extended-thinking fusion pipeline (proposer panel + aggregate + review loop).

FusionOrchestrator is a ChatSession collaborator holding a back-reference to
the facade: shared turn plumbing (_execute_graph, _run_graph_turn,
_record_turn, prompt/context helpers) stays on the session, while everything
fusion-specific lives here. The graph builder
and thinking-model getters are injected at construction so monkeypatches of
the corresponding agent.session module attributes keep working.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from langchain_core.messages import SystemMessage

from agent.llm.thinking import (
    ExtendedModeNotConfigured,
    ThinkingRole,
    require_thinking_models,
    resolve_fusion_aggregator_model,
    resolve_fusion_proposer_models,
)
from agent.skills.runtime import render_tool_availability_block
from agent.thinking import (
    Clarify,
    FusionAggregateResult,
    FusionCandidate,
    FusionCandidateTrace,
    FusionTurnMetadata,
    ThinkingOutputError,
    aggregate_candidates,
    append_tool_trace,
    build_fusion_evidence_summary,
    parse_reviser_output,
    render_route_message,
    review_draft,
    route_review_report,
    rewrite_prompt,
    summarize_tool_trace,
    trim_head,
    trim_tail,
)
from agent.tool_access import ToolAccessResolution
from agent.tools import inventory as tool_inventory
from agent.memory import assemble_prompt_history

if TYPE_CHECKING:
    from agent.session import ChatSession

logger = logging.getLogger(__name__)

# Read-only tool allowlist for fusion proposers. Only these local base tools
# may be bound; bash, extra tools, and MCP tools are excluded regardless of
# the active skill.
FUSION_READ_ONLY_ALLOWLIST = (
    "rag_explore",
    "rag_search",
    "rag_get_context",
    "recall_history",
    "read_file",
)

_REVISER_INSTRUCTION = """你可以對每一個 reviewer finding 做以下其中之一：
(a) 修改 draft 以處理該 finding；
(b) 駁斥該 finding 並在 REBUTTAL 段說明你不同意的理由。

硬性禁令：
- 不要新增無法佐證的 citation / DOI / 數據 / 樣本數 / 方法細節 / 研究發現。
- 不要新增原始 user input 與可見 context 未提供的事實。

回應格式必須嚴格使用兩個區段標記：

DRAFT:
<新版 draft 全文。這段會被回給使用者，所以保持乾淨、不要包含內部審稿討論。>

REBUTTAL:
<對 reviewer findings 的反對說明；若無，寫 (none)。這段只給下輪 Reviewer 看，不會回給使用者。>"""


@dataclass(frozen=True)
class GraphTurnResult:
    answer: str
    new_messages: list
    tool_calls: list[dict]
    trace_events: list[dict]
    recovery_reason: str | None = None
    fusion: dict | None = None
    candidate_traces: list[FusionCandidateTrace] = field(default_factory=list)


class FusionOrchestrator:
    """Runs the extended-thinking fusion turn on behalf of a ChatSession."""

    def __init__(
        self,
        session: "ChatSession",
        *,
        graph_builder,
        role_model_getter,
        aggregator_model_getter,
    ):
        self._session = session
        self._graph_builder = graph_builder
        self._role_model_getter = role_model_getter
        self._aggregator_model_getter = aggregator_model_getter
        self._thinking_role_models: dict[str, object] = {}
        self._fusion_aggregator_model: object | None = None
        self._proposer_graphs: dict[str, object] = {}

    # --- Model resolution ---------------------------------------------------

    def _get_thinking_role_model(self, role: ThinkingRole):
        if role not in self._thinking_role_models:
            self._thinking_role_models[role] = self._role_model_getter(
                self._session.config,
                role=role,
            )
        return self._thinking_role_models[role]

    def _get_fusion_aggregator_model(self):
        if self._fusion_aggregator_model is None:
            self._fusion_aggregator_model = self._aggregator_model_getter(
                self._session.config
            )
        return self._fusion_aggregator_model

    # --- Fusion proposer tool policy ---------------------------------------

    def _proposer_read_only_names(self) -> list[str]:
        """Read-only allowlist intersected with the session's effective tools.

        Proposers never fall back to the session's full tool set: the fixed
        read-only allowlist is intersected with the shared tool access
        resolution (the active skill's, or normal mode's), so bash, extra
        tools, and MCP tools are excluded regardless of the active skill.
        """
        effective = set(self._session.tool_access_resolution().effective_tools)
        return [name for name in FUSION_READ_ONLY_ALLOWLIST if name in effective]

    def _proposer_resolution(self) -> ToolAccessResolution:
        names = tuple(self._proposer_read_only_names())
        return ToolAccessResolution(
            global_tools=names,
            skill_tools=(),
            effective_tools=names,
            missing_required=(),
            missing_optional=(),
        )

    def _read_only_tool_availability_block(self) -> str:
        runtime = self._session.active_skill_runtime
        return render_tool_availability_block(
            resolution=self._proposer_resolution(),
            active_skill=getattr(runtime, "name", None) if runtime else None,
            task_mode=getattr(runtime, "task_mode", None) if runtime else None,
            all_tool_names=tool_inventory.base_tool_names(
                extra_tools=self._session.extra_tools
            ),
            mcp_families=None,
        )

    def _proposer_tool_availability_block(self) -> str:
        """Availability the proposers actually see (matches their bound tools)."""
        return self._read_only_tool_availability_block()

    def _reviewer_tool_availability_block(self) -> str:
        """Reviewer / reviser use the session availability."""
        return self._session._tool_availability_block()

    def _proposer_read_only_state(self) -> dict:
        """Full read-only skill state injected directly into a proposer graph.

        The state is complete enough that ``skill_loader_node`` (which the
        proposer graph builds with ``skill_runtime_getter=None``) has nothing to
        add and cannot overwrite this policy with the session's full tool set.
        """
        runtime = self._session.active_skill_runtime
        return {
            "active_skill": runtime.name if runtime else None,
            "skill_root": str(runtime.root) if runtime else None,
            # No active skill: skill_instructions are intentionally not injected.
            "skill_instructions": runtime.instructions if runtime else None,
            "loaded_references": dict(runtime.pinned_references) if runtime else {},
            "task_mode": runtime.task_mode if runtime else None,
            "effective_tools": self._proposer_read_only_names(),
        }

    def _proposer_prompt_history(self, availability_block: str) -> list:
        """Prompt history for a read-only proposer: session context + active skill
        context (if any) + the proposer-specific availability block."""
        session = self._session
        base = assemble_prompt_history(
            session.system_prompt_message, session.recent_turns
        )
        hints: list[SystemMessage] = []
        if session.active_skill_runtime is not None:
            hints.append(
                SystemMessage(content=session.active_skill_runtime.context_block())
            )
        hints.append(SystemMessage(content=availability_block))
        plan_hint = session._build_plan_mode_hint()
        if plan_hint is not None:
            hints.append(plan_hint)
        return [base[0], *hints, *base[1:]]

    def _proposer_recursion_limit(self) -> int:
        cap = max(int(self._session.config.thinking_fusion_proposer_tool_interactions), 0)
        return max(8, 2 * (cap + 1) + 6)

    def _proposer_graph(self, model_id: str):
        cached = self._proposer_graphs.get(model_id)
        if cached is not None:
            return cached
        cloned = dataclasses.replace(
            self._session.config,
            llm_model=model_id,
            agent_max_tool_interactions=(
                self._session.config.thinking_fusion_proposer_tool_interactions
            ),
        )
        graph = self._graph_builder(
            cloned,
            extra_tools=None,
            history_store=self._session.history_store,
            skill_runtime_getter=None,
        )
        self._proposer_graphs[model_id] = graph
        return graph

    async def _run_proposer_candidate(
        self,
        candidate_id: str,
        model_id: str,
        *,
        rewritten_prompt: str,
        rewrite_hints: list[SystemMessage],
    ) -> tuple[FusionCandidate, FusionCandidateTrace]:
        """Run one proposer graph and return its candidate + segmented trace.

        The candidate id is known here, so the trace is built directly rather
        than reconstructed later from a flat list by tool_call_id or order.
        """
        config = self._session.config
        graph = self._proposer_graph(model_id)
        prompt_history = self._proposer_prompt_history(
            self._read_only_tool_availability_block()
        )
        skill_state = self._proposer_read_only_state()
        start = time.monotonic()
        try:
            result = await asyncio.wait_for(
                self._session._execute_graph(
                    graph=graph,
                    user_input=rewritten_prompt,
                    prompt_history=prompt_history,
                    skill_state=skill_state,
                    recursion_limit=self._proposer_recursion_limit(),
                    extra_system_messages=rewrite_hints,
                    trace_label="proposer",
                    candidate_id=candidate_id,
                ),
                timeout=config.thinking_fusion_candidate_timeout_seconds,
            )
        except asyncio.TimeoutError:
            elapsed = time.monotonic() - start
            return (
                FusionCandidate(
                    candidate_id=candidate_id,
                    model_id=model_id,
                    status="timeout",
                    answer="",
                    tool_trace_summary="Tool calls: none",
                    error="candidate timed out",
                    elapsed_seconds=elapsed,
                ),
                FusionCandidateTrace(
                    candidate_id=candidate_id,
                    model_id=model_id,
                    status="timeout",
                ),
            )
        except Exception as exc:  # noqa: BLE001 - one bad proposer must not abort the panel
            elapsed = time.monotonic() - start
            logger.warning("fusion candidate %s (%s) failed: %s", candidate_id, model_id, exc)
            return (
                FusionCandidate(
                    candidate_id=candidate_id,
                    model_id=model_id,
                    status="failed",
                    answer="",
                    tool_trace_summary="Tool calls: none",
                    error=f"{type(exc).__name__}: {exc}",
                    elapsed_seconds=elapsed,
                ),
                FusionCandidateTrace(
                    candidate_id=candidate_id,
                    model_id=model_id,
                    status="failed",
                ),
            )
        elapsed = time.monotonic() - start
        answer = result.answer
        status = "success" if answer.strip() else "empty"
        tool_summary = summarize_tool_trace(
            result.tool_calls,
            result.new_messages,
            source_label=f"[{candidate_id} {model_id}]",
            per_result_chars=config.thinking_tool_trace_chars,
        )
        candidate = FusionCandidate(
            candidate_id=candidate_id,
            model_id=model_id,
            status=status,
            answer=answer,
            tool_trace_summary=tool_summary,
            error="",
            elapsed_seconds=elapsed,
        )
        trace = FusionCandidateTrace(
            candidate_id=candidate_id,
            model_id=model_id,
            status=status,
            new_messages=result.new_messages,
            tool_calls=result.tool_calls,
            trace_events=result.trace_events,
            tool_trace_summary=tool_summary,
            answer_excerpt=trim_head(answer, config.thinking_tool_trace_chars),
        )
        return candidate, trace

    async def _run_fusion_candidates(
        self,
        proposer_models: list[str],
        *,
        rewritten_prompt: str,
        rewrite_hints: list[SystemMessage],
    ) -> tuple[list[FusionCandidate], list[FusionCandidateTrace]]:
        """Run all proposer candidates in parallel (read-only tools only)."""
        numbered = list(enumerate(proposer_models, start=1))
        results = await asyncio.gather(*[
            self._run_proposer_candidate(
                f"candidate-{index}",
                model_id,
                rewritten_prompt=rewritten_prompt,
                rewrite_hints=rewrite_hints,
            )
            for index, model_id in numbered
        ])
        candidates = [candidate for candidate, _trace in results]
        traces = [trace for _candidate, trace in results]
        return candidates, traces

    # --- Hints & rendering ---------------------------------------------------

    def _rewrite_hints(
        self,
        *,
        raw_user_input: str,
        rewritten_prompt: str,
    ) -> list[SystemMessage]:
        return [
            SystemMessage(content=f"[Original user input]\n{raw_user_input}"),
            SystemMessage(content=f"[Rewritten by prompt-master]\n{rewritten_prompt}"),
        ]

    def _reviser_hints(
        self,
        *,
        raw_user_input: str,
        rewritten_prompt: str,
        draft: str,
        report,
    ) -> list[SystemMessage]:
        return [
            *self._rewrite_hints(
                raw_user_input=raw_user_input,
                rewritten_prompt=rewritten_prompt,
            ),
            SystemMessage(content=f"[Previous draft]\n{draft}"),
            SystemMessage(content=(
                "[Reviewer feedback]\n"
                f"{report.model_dump_json(indent=2)}"
            )),
            SystemMessage(content=f"[Reviser instruction]\n{_REVISER_INSTRUCTION}"),
        ]

    def _extended_error_message(self, exc: Exception) -> str:
        return (
            "Extended mode 無法安全完成本 turn，已停止以避免不安全改寫。\n"
            f"- {exc}"
        )

    # --- Aggregate & metadata -------------------------------------------------

    async def _aggregate_fusion_panel(
        self,
        candidates: list[FusionCandidate],
        *,
        user_input: str,
        rewritten_prompt: str,
        rewrite_hints: list[SystemMessage],
        skill_context: str,
        proposer_availability: str,
    ) -> tuple[str | None, FusionAggregateResult, GraphTurnResult | None]:
        """Pick or synthesize a draft from the candidate panel.

        Returns ``(draft_or_none, aggregate_result, base_fallback_result)``. The
        session — not the aggregator — owns the reliability tier. A None draft
        means no draft could be produced at all.
        """
        successful = [c for c in candidates if c.status == "success"]
        quorum = max(int(self._session.config.thinking_fusion_quorum), 1)

        if not successful:
            base = None
            try:
                base = await self._session._run_graph_turn(
                    rewritten_prompt, extra_system_messages=rewrite_hints
                )
            except Exception as exc:  # noqa: BLE001 - base fallback must stay best-effort
                logger.warning("fusion base fallback graph raised: %s", exc)
            if base is not None and base.answer.strip():
                return (
                    base.answer,
                    FusionAggregateResult(
                        draft=base.answer,
                        reliability_tier="fallback",
                        aggregator_error="no_successful_candidates_base_fallback",
                    ),
                    base,
                )
            return (
                None,
                FusionAggregateResult(
                    draft="",
                    reliability_tier="fallback",
                    aggregator_error="no_successful_candidates",
                ),
                base,
            )

        if len(successful) == 1:
            chosen = successful[0]
            return (
                chosen.answer,
                FusionAggregateResult(
                    draft=chosen.answer,
                    selected_candidate_ids=[chosen.candidate_id],
                    reliability_tier="single_candidate",
                ),
                None,
            )

        if len(successful) >= quorum:
            try:
                aggregate = aggregate_candidates(
                    self._get_fusion_aggregator_model(),
                    raw_user_input=user_input,
                    rewritten_prompt=rewritten_prompt,
                    successful_candidates=successful,
                    skill_context=skill_context,
                    tool_availability=proposer_availability,
                )
            except ThinkingOutputError as exc:
                chosen = successful[0]
                return (
                    chosen.answer,
                    FusionAggregateResult(
                        draft=chosen.answer,
                        selected_candidate_ids=[chosen.candidate_id],
                        reliability_tier="fallback",
                        aggregator_error=f"aggregator_failure: {exc}",
                    ),
                    None,
                )
            aggregate.reliability_tier = (
                "full_panel" if len(successful) == len(candidates) else "partial_panel"
            )
            return aggregate.draft, aggregate, None

        # More than one success but below quorum: deterministic fallback.
        chosen = successful[0]
        return (
            chosen.answer,
            FusionAggregateResult(
                draft=chosen.answer,
                selected_candidate_ids=[chosen.candidate_id],
                reliability_tier="fallback",
                aggregator_error="quorum_not_met",
            ),
            None,
        )

    def _build_fusion_metadata(
        self,
        candidates: list[FusionCandidate],
        aggregate: FusionAggregateResult,
        *,
        proposer_models: list[str],
        aggregator_model: str,
    ) -> FusionTurnMetadata:
        successful_ids = [c.candidate_id for c in candidates if c.status == "success"]
        selected = list(aggregate.selected_candidate_ids)
        dropped = list(aggregate.dropped_candidate_ids)
        covered = set(selected) | set(dropped)
        omitted = [cid for cid in successful_ids if cid not in covered]
        return FusionTurnMetadata(
            candidate_statuses={c.candidate_id: c.status for c in candidates},
            model_ids={c.candidate_id: c.model_id for c in candidates},
            selected_ids=selected,
            dropped_ids=dropped,
            omitted_successful_ids=omitted,
            reliability_tier=aggregate.reliability_tier or "",
            aggregator_error=aggregate.aggregator_error or "",
            quorum=int(self._session.config.thinking_fusion_quorum),
            resolved_proposer_models=list(proposer_models),
            resolved_aggregator_model=aggregator_model,
        )

    # --- Extended turn ---------------------------------------------------------

    async def run_extended_turn(self, user_input: str):
        session = self._session
        config = session.config
        try:
            require_thinking_models(config)
            rewrite_model = self._get_thinking_role_model("rewrite")
            reviewer_model = self._get_thinking_role_model("reviewer")
            repair_model = self._get_thinking_role_model("repair")
            prompt_master_skill = session._prompt_master_skill_text()
            proposer_models = resolve_fusion_proposer_models(config)
            aggregator_model = resolve_fusion_aggregator_model(config)
        except (ExtendedModeNotConfigured, RuntimeError, OSError) as exc:
            return await session.finalize_and_record(
                user_input=user_input,
                answer=self._extended_error_message(exc),
                new_messages=[],
                tool_calls=[],
                trace_events=[],
            )

        skill_context = session._active_skill_context_block()
        proposer_availability = self._proposer_tool_availability_block()
        reviewer_availability = self._reviewer_tool_availability_block()
        try:
            rewrite_result = rewrite_prompt(
                rewrite_model,
                skill_text=prompt_master_skill,
                user_input=user_input,
                visible_context=trim_tail(
                    session._visible_context_text(),
                    config.thinking_rewrite_visible_chars,
                ),
                skill_context=trim_head(
                    skill_context,
                    config.thinking_rewrite_skill_chars,
                ),
                tool_availability=proposer_availability,
            )
        except Exception as exc:
            return await session.finalize_and_record(
                user_input=user_input,
                answer=self._extended_error_message(exc),
                new_messages=[],
                tool_calls=[],
                trace_events=[],
            )

        if isinstance(rewrite_result, Clarify):
            return await session.finalize_and_record(
                user_input=user_input,
                answer=rewrite_result.text or "需要補充資訊才能安全完成這個任務。",
                new_messages=[],
                tool_calls=[],
                trace_events=[],
            )

        rewritten_prompt = rewrite_result.prompt
        rewrite_hints = self._rewrite_hints(
            raw_user_input=user_input,
            rewritten_prompt=rewritten_prompt,
        )
        candidates, candidate_traces = await self._run_fusion_candidates(
            proposer_models,
            rewritten_prompt=rewritten_prompt,
            rewrite_hints=rewrite_hints,
        )
        draft, aggregate_result, base_fallback = await self._aggregate_fusion_panel(
            candidates,
            user_input=user_input,
            rewritten_prompt=rewritten_prompt,
            rewrite_hints=rewrite_hints,
            skill_context=skill_context,
            proposer_availability=proposer_availability,
        )
        metadata = self._build_fusion_metadata(
            candidates,
            aggregate_result,
            proposer_models=proposer_models,
            aggregator_model=aggregator_model,
        )
        fusion_dict = metadata.to_dict()

        # Flat real tool calls: every candidate's calls (carrying candidate_id),
        # plus any base-fallback / reviser calls (no id).
        flat_tool_calls = [
            call for trace in candidate_traces for call in trace.tool_calls
        ]
        flat_trace_events: list[dict] = [{"type": "fusion", **fusion_dict}]
        for trace in candidate_traces:
            flat_trace_events.extend(trace.trace_events)
        # Non-candidate graph messages (base fallback / reviser) stay out of
        # the candidate segments so plan rendering never cross-pairs colliding
        # tool_call_ids.
        non_candidate_messages: list = []

        if draft is None:
            answer = self._extended_error_message(
                RuntimeError("fusion produced no usable draft")
            )
            if base_fallback is not None:
                non_candidate_messages.extend(base_fallback.new_messages)
                flat_tool_calls.extend(base_fallback.tool_calls)
                flat_trace_events.extend(base_fallback.trace_events)
            return await session.finalize_and_record(
                user_input=user_input,
                answer=answer,
                new_messages=non_candidate_messages,
                tool_calls=flat_tool_calls,
                trace_events=flat_trace_events,
                fusion=fusion_dict,
                candidate_traces=candidate_traces,
            )

        evidence_trace_summary = build_fusion_evidence_summary(
            candidates=candidates,
            candidate_traces=candidate_traces,
            aggregate_result=aggregate_result,
            metadata=metadata,
            per_result_chars=config.thinking_tool_trace_chars,
        )
        if base_fallback is not None:
            non_candidate_messages.extend(base_fallback.new_messages)
            flat_tool_calls.extend(base_fallback.tool_calls)
            flat_trace_events.extend(base_fallback.trace_events)
            evidence_trace_summary = append_tool_trace(
                evidence_trace_summary,
                base_fallback.tool_calls,
                base_fallback.new_messages,
                source_label="[Base fallback writer]",
                per_result_chars=config.thinking_tool_trace_chars,
                total_chars_cap=config.thinking_tool_trace_total_chars,
            )

        rebuttal_history: list[str] = []
        format_warning = ""
        attempts = 0
        final_route = None

        while True:
            try:
                report = review_draft(
                    reviewer_model,
                    raw_user_input=user_input,
                    rewritten_prompt=rewritten_prompt,
                    draft=draft,
                    skill_context=skill_context,
                    evidence_trace_summary=evidence_trace_summary,
                    previous_rebuttal=rebuttal_history[-1] if rebuttal_history else "",
                    tool_availability=reviewer_availability,
                )
            except ThinkingOutputError as exc:
                answer = self._extended_error_message(exc)
                final_route = None
                break

            review_route = route_review_report(report, attempts=attempts)
            if review_route in {"pass", "ask_user", "stop"}:
                final_route = review_route
                answer = render_route_message(
                    review_route,
                    draft,
                    report,
                    format_warning=format_warning,
                )
                break

            reviser_result = await session._run_graph_turn(
                rewritten_prompt,
                extra_system_messages=self._reviser_hints(
                    raw_user_input=user_input,
                    rewritten_prompt=rewritten_prompt,
                    draft=draft,
                    report=report,
                ),
            )
            parsed = parse_reviser_output(
                reviser_result.answer,
                repair_model=repair_model,
            )
            draft = parsed.draft
            format_warning = format_warning or parsed.format_warning
            evidence_trace_summary = append_tool_trace(
                evidence_trace_summary,
                reviser_result.tool_calls,
                reviser_result.new_messages,
                source_label=f"[Reviser round {attempts + 1}]",
                per_result_chars=config.thinking_tool_trace_chars,
                total_chars_cap=config.thinking_tool_trace_total_chars,
            )
            rebuttal_history.append(parsed.rebuttal)
            attempts += 1
            non_candidate_messages.extend(reviser_result.new_messages)
            flat_tool_calls.extend(reviser_result.tool_calls)
            flat_trace_events.extend(reviser_result.trace_events)

        current = GraphTurnResult(
            answer=answer,
            new_messages=non_candidate_messages,
            tool_calls=flat_tool_calls,
            trace_events=flat_trace_events,
        )
        return await session.finalize_and_record(
            user_input=user_input,
            answer=current.answer,
            new_messages=current.new_messages,
            tool_calls=current.tool_calls,
            trace_events=current.trace_events,
            fusion=fusion_dict,
            candidate_traces=candidate_traces,
        )
