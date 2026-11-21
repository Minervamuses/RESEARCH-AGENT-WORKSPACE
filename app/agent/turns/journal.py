"""Process-local diagnostics for completed canonical turns."""

from __future__ import annotations


class TurnJournal:
    """Own process-local last-turn tool-call summary."""

    def __init__(self) -> None:
        self.last_tool_calls: list[dict] = []

    def observe_turn(
        self,
        *,
        tool_calls: list[dict],
    ) -> None:
        """Record the latest completed turn's tool calls."""
        self.last_tool_calls = list(tool_calls)
