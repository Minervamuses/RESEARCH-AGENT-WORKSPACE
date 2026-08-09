"""Result models shared by normal and extended-thinking turns."""

from __future__ import annotations

from dataclasses import dataclass, field

from agent.thinking.schemas import FusionCandidateTrace


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


@dataclass(frozen=True)
class GraphTurnResult:
    """Normalized output collected from one graph execution."""

    answer: str
    new_messages: list
    tool_calls: list[dict]
    trace_events: list[dict]
    recovery_reason: str | None = None
    fusion: dict | None = None
    candidate_traces: list[FusionCandidateTrace] = field(default_factory=list)
