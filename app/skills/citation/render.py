"""Render citation markers into numbered references plus a bibliography.

Runs only after the citation gate has passed. Verified ``[[cite:<id>]]``
markers become ``[1]``, ``[2]``, ... in order of first appearance (the same
source always keeps its number); user-supplied ``[[user-cite:<id>]]``
markers use a separate ``[U1]`` sequence so the two can never collide.
``[[citation-needed]]`` renders as a plain placeholder and never enters the
bibliography. Ordinary web links pass through untouched and unnumbered.

The bibliography format is neutral and fixed: up to six authors then
``et al.``, year, full title, venue, DOI, verification level — any missing
field is simply omitted, never guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from skills.citation.gate import (
    CITATION_NEEDED,
    CITE_MARKER_RE,
    MARKER_RE,
    USER_CITE_MARKER_RE,
)
from skills.citation.types import SourceRef

_MAX_BIB_AUTHORS = 6
_FENCE_OR_CODE_RE = re.compile(r"```.*?(?:```|\Z)|`[^`\n]*`", re.DOTALL)


@dataclass
class RenderedTurn:
    """Final text plus the sources actually cited, in numbering order."""

    text: str
    cited_sources: list[SourceRef] = field(default_factory=list)
    user_sources: list[SourceRef] = field(default_factory=list)


def format_bibliography_entry(ref: SourceRef) -> str:
    """Neutral entry: authors<=6+et al., year, title, venue, DOI, level."""
    parts: list[str] = []
    if ref.authors:
        heads = ref.authors[:_MAX_BIB_AUTHORS]
        authors = ", ".join(heads)
        if len(ref.authors) > _MAX_BIB_AUTHORS:
            authors += " et al."
        parts.append(authors)
    if ref.year is not None:
        parts.append(str(ref.year))
    if ref.title:
        parts.append(ref.title)
    if ref.venue:
        parts.append(ref.venue)
    if ref.doi:
        parts.append(f"DOI: {ref.doi}")
    elif ref.url:
        parts.append(ref.url)
    parts.append(f"[{ref.verification_level}]")
    return ". ".join(parts[:-1]) + f". {parts[-1]}" if len(parts) > 1 else parts[0]


def render_citations(
    text: str,
    *,
    resolve: Callable[[str], SourceRef | None],
) -> RenderedTurn:
    """Replace markers with per-response numbering and append a bibliography."""
    text = text or ""
    code_spans = [m.span() for m in _FENCE_OR_CODE_RE.finditer(text)]

    def _in_code(position: int) -> bool:
        return any(start <= position < end for start, end in code_spans)

    cited_order: list[SourceRef] = []
    cited_numbers: dict[str, int] = {}
    user_order: list[SourceRef] = []
    user_numbers: dict[str, int] = {}

    def _replace(match: re.Match) -> str:
        if _in_code(match.start()):
            return match.group(0)  # markers inside code stay verbatim
        body = match.group(1).strip()
        if body == CITATION_NEEDED:
            return "[citation needed]"
        cite = CITE_MARKER_RE.match(body)
        if cite:
            source_id = cite.group(1)
            ref = resolve(source_id)
            if ref is None:
                return match.group(0)  # gate guarantees this cannot happen
            number = cited_numbers.get(source_id)
            if number is None:
                cited_order.append(ref)
                number = cited_numbers[source_id] = len(cited_order)
            return f"[{number}]"
        user_cite = USER_CITE_MARKER_RE.match(body)
        if user_cite:
            source_id = user_cite.group(1)
            ref = resolve(source_id)
            if ref is None:
                return match.group(0)
            number = user_numbers.get(source_id)
            if number is None:
                user_order.append(ref)
                number = user_numbers[source_id] = len(user_order)
            return f"[U{number}]"
        return match.group(0)

    rendered = MARKER_RE.sub(_replace, text)

    if cited_order or user_order:
        lines = ["", "Sources:"]
        for i, ref in enumerate(cited_order, start=1):
            lines.append(f"[{i}] {format_bibliography_entry(ref)}")
        for i, ref in enumerate(user_order, start=1):
            lines.append(f"[U{i}] {format_bibliography_entry(ref)}")
        rendered = rendered.rstrip() + "\n" + "\n".join(lines) + "\n"

    return RenderedTurn(
        text=rendered,
        cited_sources=cited_order,
        user_sources=user_order,
    )
