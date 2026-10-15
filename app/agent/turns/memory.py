"""Canonical completed-turn prompt views."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CanonicalTurnView:
    """Non-authoritative completed-turn view rebuilt from canonical JSON."""

    user_input: str
    assistant_output: str
    turn_id: int
    logical_turn_id: str
    timestamp: str
    tool_activities: tuple = ()
