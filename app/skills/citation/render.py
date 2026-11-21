"""Render citation markers into numbered references plus a bibliography.

Runs only after the citation gate has passed. Verified ``[[cite:<id>]]``
markers become ``[1]``, ``[2]``, ... in order of first appearance (the same
source always keeps its number). ``[[citation-needed]]`` renders as a plain
placeholder and never enters the bibliography. Ordinary web links pass
through untouched and unnumbered.

The bibliography format is neutral and fixed: up to six authors then
``et al.``, year, full title, venue, DOI, verification level — any missing
field is simply omitted, never guessed.
"""

from __future__ import annotations

import re
from typing import Callable

from skills.citation.gate import (
    CITATION_NEEDED,
    CITE_MARKER_RE,
    MARKER_RE,
    mask_unscanned_regions,
)
from skills.citation.types import SourceRef

_MAX_BIB_AUTHORS = 6


def _bibliography_entry(ref: SourceRef) -> str:
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
) -> str:
    """Replace markers with per-response numbering and append a bibliography."""
    text = text or ""
    # The same code regions the gate leaves unscanned (masked to spaces).
    scanned = mask_unscanned_regions(text)

    def _in_code(position: int) -> bool:
        return scanned[position] != text[position]

    cited_order: list[SourceRef] = []
    cited_numbers: dict[str, int] = {}

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
        return match.group(0)

    rendered = MARKER_RE.sub(_replace, text)

    if cited_order:
        lines = ["", "Sources:"]
        for i, ref in enumerate(cited_order, start=1):
            lines.append(f"[{i}] {_bibliography_entry(ref)}")
        rendered = rendered.rstrip() + "\n" + "\n".join(lines) + "\n"

    return rendered
