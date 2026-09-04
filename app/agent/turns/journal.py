"""Process-local turn diagnostics and legacy recent-turn state."""

from __future__ import annotations

from agent.config import AgentConfig
from agent.observability import CitationSaveMetrics
from agent.turns.memory import TurnRecord
from agent.turns.store import TurnStore
from agent.turns.trace import format_tool_counts


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
    """Own observable turn logs and legacy recent-turn storage state."""

    def __init__(
        self,
        *,
        config: AgentConfig,
        session_id: str,
        history_store,
        restored_turns: list[TurnRecord] | None = None,
    ) -> None:
        restored = merge_restored_turns(list(restored_turns or []))
        window = config.agent_recent_turns_window
        self.recent_turns: list[TurnRecord] = (
            restored[-window:] if window > 0 else []
        )
        self.turn_logs: list[dict] = []
        self.last_tool_calls: list[dict] = []
        self._turn_counter = restored[-1].turn_id if restored else 0
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
