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


class TurnJournal:
    """Own recent-turn, plan-mode, and observable turn-log state."""

    def __init__(
        self,
        *,
        config: AgentConfig,
        session_id: str,
        history_store,
        app_root_resolver: Callable[[], Path],
    ) -> None:
        self.recent_turns: list[TurnRecord] = []
        self.turn_logs: list[dict] = []
        self.last_tool_calls: list[dict] = []
        self.plan_mode = False
        self.plan_log_path: Path | None = None
        self._turn_counter = 0

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

    def enter_plan_mode(self) -> Path:
        """Enable plan persistence for newly recorded turns."""
        if self.plan_mode:
            if self.plan_log_path is None:
                self.plan_log_path = self._plan_log.new_log_file()
            return self.plan_log_path
        self.plan_log_path = self._plan_log.new_log_file()
        self.plan_mode = True
        return self.plan_log_path

    def exit_plan_mode(self) -> None:
        """Disable plan persistence without changing recent context."""
        self.plan_mode = False
        self.plan_log_path = None

    def append_block(self, log_path: str, block: str) -> None:
        self._plan_log.append_block(log_path, block)

    async def flush(self) -> None:
        await self._turn_store.flush()

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
    ) -> None:
        """Record one finalized turn, preserving plan-write atomicity."""
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
