"""Process-local diagnostics for completed canonical turns."""

from __future__ import annotations

from agent.observability import CitationSaveMetrics
from agent.turns.trace import format_tool_counts


class TurnJournal:
    """Own process-local observable turn logs."""

    def __init__(self) -> None:
        self.turn_logs: list[dict] = []
        self.last_tool_calls: list[dict] = []

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
