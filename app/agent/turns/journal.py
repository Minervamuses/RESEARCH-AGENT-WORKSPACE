"""Mutable turn journal state and persistence ordering."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from agent.config import AgentConfig
from agent.observability import CitationSaveMetrics
from agent.turns.memory import TurnRecord
from agent.turns.plan_log import PlanLog
from agent.turns.store import TurnStore
from agent.turns.trace import format_tool_counts

if TYPE_CHECKING:
    from agent.thinking.schemas import FusionCandidateTrace

logger = logging.getLogger(__name__)

AppendBlock = Callable[[str, str], None]


class TurnRestoreError(RuntimeError):
    """Persisted turn sources cannot form one unambiguous conversation."""


def merge_restored_turns(*sources: list[TurnRecord]) -> list[TurnRecord]:
    """Merge persisted sources into one contiguous, non-persisting turn list."""
    by_id: dict[int, TurnRecord] = {}
    for source in sources:
        for turn in source:
            if type(turn.turn_id) is not int or turn.turn_id < 1:
                raise TurnRestoreError("restored turn_id must be a positive integer")
            if turn.turn_id in by_id:
                raise TurnRestoreError(
                    f"restored turn_id appears more than once: {turn.turn_id}"
                )
            if not isinstance(turn.user_input, str) or not turn.user_input:
                raise TurnRestoreError("restored user input must not be empty")
            if not isinstance(turn.assistant_output, str) or not turn.assistant_output:
                raise TurnRestoreError("restored assistant output must not be empty")
            if not isinstance(turn.timestamp, str) or not turn.timestamp:
                raise TurnRestoreError("restored timestamp must not be empty")
            by_id[turn.turn_id] = TurnRecord(
                user_input=turn.user_input,
                assistant_output=turn.assistant_output,
                turn_id=turn.turn_id,
                timestamp=turn.timestamp,
                persist_target="none",
                tool_activities=tuple(turn.tool_activities),
            )
    ordered_ids = sorted(by_id)
    if ordered_ids and ordered_ids != list(range(1, ordered_ids[-1] + 1)):
        raise TurnRestoreError("restored turn_ids must be contiguous from 1")
    return [by_id[turn_id] for turn_id in ordered_ids]


class TurnJournal:
    """Own recent-turn, plan-mode, and observable turn-log state."""

    def __init__(
        self,
        *,
        config: AgentConfig,
        session_id: str,
        history_store,
        app_root_resolver: Callable[[], Path],
        restored_turns: list[TurnRecord] | None = None,
    ) -> None:
        restored = merge_restored_turns(list(restored_turns or []))
        window = config.agent_recent_turns_window
        self.recent_turns: list[TurnRecord] = (
            restored[-window:] if window > 0 else []
        )
        self.turn_logs: list[dict] = []
        self.last_tool_calls: list[dict] = []
        self.plan_mode = False
        self.plan_log_path: Path | None = None
        self._turn_counter = restored[-1].turn_id if restored else 0

        self._plan_log = PlanLog(
            config,
            session_id=session_id,
            app_root_resolver=app_root_resolver,
        )
        self._turn_store = TurnStore(
            history_store,
            config=config,
            session_id=session_id,
            recent_turns=self.recent_turns,
        )

    @property
    def turn_count(self) -> int:
        return self._turn_counter

    @property
    def turn_store(self) -> TurnStore:
        return self._turn_store

    def enter_plan_mode(self) -> None:
        """Enable the temporary plan prompt behavior without a durable side path."""
        self.plan_mode = True
        self.plan_log_path = None

    def resume_plan_mode(self, _log_path: str | Path) -> None:
        """Restore only the temporary plan control; legacy logs stay read-only."""
        self.plan_mode = True
        self.plan_log_path = None

    def exit_plan_mode(self) -> None:
        """Disable plan persistence without changing recent context."""
        self.plan_mode = False
        self.plan_log_path = None

    def append_block(self, log_path: str, block: str) -> None:
        self._plan_log.append_block(log_path, block)

    async def flush(self) -> None:
        """Compatibility no-op: canonical turns are write-through already."""

    def observe_turn(
        self,
        *,
        user_input: str,
        tool_calls: list[dict],
        trace_events: list[dict],
        citation_save_metrics: CitationSaveMetrics,
        fusion: dict | None = None,
        validation_errors: list[str] | None = None,
        recovery_reason: str | None = None,
    ) -> None:
        """Record process-local diagnostics after canonical completion."""
        self.last_tool_calls = list(tool_calls)
        self.turn_logs.append({
            "user_input": user_input,
            "tool_calls": list(tool_calls),
            "trace_events": list(trace_events),
            "tool_counts": format_tool_counts(tool_calls),
            "fusion": fusion,
            "validation_errors": list(validation_errors or []),
            "recovery": recovery_reason,
            **citation_save_metrics.to_record(),
        })

    async def record_turn(
        self,
        *,
        user_input: str,
        answer: str,
        new_messages: list,
        tool_calls: list[dict],
        trace_events: list[dict],
        citation_save_metrics: CitationSaveMetrics,
        append_block: AppendBlock,
        fusion: dict | None = None,
        candidate_traces: list[FusionCandidateTrace] | None = None,
        validation_errors: list[str] | None = None,
        recovery_reason: str | None = None,
        citation_scope: bool = False,
    ) -> None:
        """Record one finalized turn, preserving plan-write atomicity."""
        turn_id = self._turn_counter + 1
        timestamp = datetime.now(timezone.utc).isoformat()
        tool_activities = ()
        if self.plan_mode:
            if self.plan_log_path is None:
                raise RuntimeError("plan mode is enabled without a log path")
            target = "plan_log"
            log_path = str(self.plan_log_path)
            scope = (
                "fusion"
                if fusion is not None or candidate_traces
                else "citation"
                if citation_scope
                else "normal"
            )
            if scope != "fusion":
                tool_activities = self._plan_log.build_tool_activities(
                    new_messages=new_messages,
                    tool_calls=tool_calls,
                    scope=scope,
                )
            try:
                block = self._plan_log.render_block(
                    turn_id=turn_id,
                    timestamp=timestamp,
                    user_input=user_input,
                    answer=answer,
                    new_messages=new_messages,
                    tool_calls=tool_calls,
                    candidate_traces=candidate_traces,
                    scope=scope,
                    tool_activities=tool_activities,
                )
                await asyncio.to_thread(append_block, log_path, block)
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
                tool_activities=tool_activities,
            )
        )
        self.last_tool_calls = tool_calls
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
