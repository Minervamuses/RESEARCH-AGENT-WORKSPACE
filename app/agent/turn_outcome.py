"""The unified result of one finalized chat turn."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TurnOutcome:
    """What one user-visible turn actually produced.

    ``text`` is the rendered (or gate-blocked safe) message;
    ``validation_errors`` are the citation-gate findings when the draft was
    blocked (empty on a clean turn); ``tool_calls`` is the normalized tool
    trace for the whole turn.
    """

    text: str
    validation_errors: list[str] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
