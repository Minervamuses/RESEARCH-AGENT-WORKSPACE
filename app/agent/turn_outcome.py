"""The unified result of one finalized chat turn."""

from __future__ import annotations

from dataclasses import dataclass, field

from skills.citation.types import SourceRef


@dataclass
class TurnOutcome:
    """What one user-visible turn actually produced.

    ``text`` is the rendered (or gate-blocked safe) message; ``sources`` are
    the SourceRefs actually cited in it, in numbering order;
    ``validation_errors`` are the citation-gate findings when the draft was
    blocked (empty on a clean turn); ``tool_calls`` is the normalized tool
    trace for the whole turn.
    """

    text: str
    sources: list[SourceRef] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
