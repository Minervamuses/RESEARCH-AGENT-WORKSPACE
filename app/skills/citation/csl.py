"""Sanitized CSL-JSON items for the project bibliography.

doi.org content negotiation already returns CSL-JSON for every verified DOI.
This module keeps a cleaned copy of it: only CSL 1.0.2 bibliographic
variables survive, names keep only name parts, non-standard types map to
CSL 1.0.2 types through a fixed table, and abstracts, reference lists,
licenses, funders, ORCIDs and affiliations are always dropped.

The result never carries an ``id``; the project library assigns the key.
Nothing here is written into a citation bundle.
"""

from __future__ import annotations

import html
import re
from typing import Any

from skills.citation.doi import canonicalize_doi

CSL_TYPES = frozenset({
    "article", "article-journal", "article-magazine", "article-newspaper",
    "bill", "book", "broadcast", "chapter", "classic", "collection",
    "dataset", "document", "entry", "entry-dictionary", "entry-encyclopedia",
    "event", "figure", "graphic", "hearing", "interview", "legal_case",
    "legislation", "manuscript", "map", "motion_picture", "musical_score",
    "pamphlet", "paper-conference", "patent", "performance", "periodical",
    "personal_communication", "post", "post-weblog", "regulation", "report",
    "review", "review-book", "software", "song", "speech", "standard",
    "thesis", "treaty", "webpage",
})

# Crossref / DataCite / registry types that are not CSL 1.0.2 types.
TYPE_MAP = {
    "journal-article": "article-journal",
    "proceedings-article": "paper-conference",
    "posted-content": "article",
    "preprint": "article",
    "book-chapter": "chapter",
    "book-section": "chapter",
    "book-part": "chapter",
    "book-track": "chapter",
    "monograph": "book",
    "edited-book": "book",
    "reference-book": "book",
    "book-set": "book",
    "book-series": "book",
    "proceedings": "book",
    "proceedings-series": "book",
    "reference-entry": "entry",
    "dissertation": "thesis",
    "journal": "periodical",
    "journal-issue": "periodical",
    "journal-volume": "periodical",
    "report-component": "report",
    "report-series": "report",
    "peer-review": "review",
    "database": "dataset",
    "component": "document",
    "grant": "document",
    "text": "document",
    "other": "document",
}
FALLBACK_TYPE = "document"

TEXT_VARIABLES = (
    "title", "title-short", "container-title", "container-title-short",
    "collection-title", "event-title", "event-place", "publisher",
    "publisher-place", "genre", "medium", "language", "status", "version",
    "archive", "archive-place",
)
NUMBER_VARIABLES = (
    "volume", "issue", "page", "page-first", "number", "number-of-pages",
    "edition", "collection-number", "chapter-number",
)
IDENTIFIER_VARIABLES = ("DOI", "URL", "ISSN", "ISBN", "PMID", "PMCID")
NAME_VARIABLES = (
    "author", "editor", "translator", "collection-editor", "container-author",
)
DATE_VARIABLES = ("issued", "original-date", "event-date")
NAME_PARTS = (
    "family", "given", "literal", "suffix",
    "non-dropping-particle", "dropping-particle",
)
# Text variables that may carry inline markup in Crossref records.
RICH_TEXT_VARIABLES = frozenset({
    "title", "title-short", "container-title", "collection-title", "event-title",
})
_KEPT_TAGS = {"i", "b", "sup", "sub"}
_TAG = re.compile(r"<\s*(/?)\s*([A-Za-z][\w:.-]*)[^>]*>")


def normalize_type(raw: object) -> str:
    """Map a provider type onto a CSL 1.0.2 type."""
    value = raw.strip().casefold() if isinstance(raw, str) else ""
    if value in CSL_TYPES:
        return value
    return TYPE_MAP.get(value, FALLBACK_TYPE)


def _first_text(value: object) -> str:
    if isinstance(value, list):
        value = next((item for item in value if isinstance(item, str) and item.strip()), "")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = str(value)
    return value.strip() if isinstance(value, str) else ""


def clean_rich_text(value: str) -> str:
    """Keep CSL's simple inline tags (i, b, sup, sub); drop all other markup."""

    def keep(match: re.Match) -> str:
        closing, name = match.group(1), match.group(2).casefold()
        return f"<{closing}{name}>" if name in _KEPT_TAGS else ""

    text = html.unescape(_TAG.sub(keep, value))
    return " ".join(text.split())


def _clean_name(raw: object) -> dict | None:
    if not isinstance(raw, dict):
        return None
    name = {
        part: " ".join(raw[part].split())
        for part in NAME_PARTS
        if isinstance(raw.get(part), str) and raw[part].strip()
    }
    if "family" not in name and "literal" not in name:
        fallback = raw.get("name")
        if isinstance(fallback, str) and fallback.strip():
            name = {"literal": " ".join(fallback.split())}
    if "family" not in name and "literal" not in name:
        return None
    return name


def _clean_date(raw: object) -> dict | None:
    if not isinstance(raw, dict):
        return None
    out: dict = {}
    parts = raw.get("date-parts")
    if isinstance(parts, list):
        cleaned = []
        for row in parts[:2]:
            if not isinstance(row, list):
                continue
            values = []
            for item in row[:3]:
                try:
                    values.append(int(item))
                except (TypeError, ValueError):
                    break
            if values:
                cleaned.append(values)
        if cleaned:
            out["date-parts"] = cleaned
    literal = raw.get("literal")
    if isinstance(literal, str) and literal.strip() and "date-parts" not in out:
        out["literal"] = literal.strip()
    return out or None


def sanitize_csl(payload: dict) -> dict:
    """Return a whitelisted CSL-JSON item (no ``id``) for ``payload``."""
    item: dict[str, Any] = {"type": normalize_type(payload.get("type"))}
    for variable in TEXT_VARIABLES:
        value = _first_text(payload.get(variable))
        if value and variable in RICH_TEXT_VARIABLES:
            value = clean_rich_text(value)
        if value:
            item[variable] = value
    if "event-title" not in item:
        event = payload.get("event")
        if isinstance(event, dict):
            event = event.get("name")
        event = _first_text(event)
        if event:
            item["event-title"] = clean_rich_text(event)
    for variable in NAME_VARIABLES:
        raw = payload.get(variable)
        if isinstance(raw, list):
            names = [name for name in map(_clean_name, raw) if name]
            if names:
                item[variable] = names
    for variable in DATE_VARIABLES:
        date = _clean_date(payload.get(variable))
        if date:
            item[variable] = date
    for variable in NUMBER_VARIABLES:
        value = _first_text(payload.get(variable))
        if value:
            item[variable] = value
    for variable in IDENTIFIER_VARIABLES:
        value = _first_text(payload.get(variable))
        if value:
            item[variable] = value
    if "DOI" in item:
        doi = canonicalize_doi(item["DOI"])
        if doi:
            item["DOI"] = doi
        else:
            del item["DOI"]
    return item


def person_from_display_name(name: str) -> dict:
    """Split a display name ("Given Middle Family") into CSL name parts."""
    parts = name.split()
    if len(parts) < 2:
        return {"literal": name.strip()}
    return {"family": parts[-1], "given": " ".join(parts[:-1])}


def minimal_csl(
    *,
    title: str,
    authors: list[str] | tuple[str, ...],
    year: int | None,
    venue: str = "",
    work_type: str = "",
    doi: str | None = None,
    url: str | None = None,
) -> dict:
    """Build a CSL item from already-verified display fields only."""
    item: dict[str, Any] = {"type": normalize_type(work_type)}
    if title:
        item["title"] = title
    if authors:
        item["author"] = [person_from_display_name(name) for name in authors if name.strip()]
    if year:
        item["issued"] = {"date-parts": [[int(year)]]}
    if venue:
        item["container-title"] = venue
    if doi:
        item["DOI"] = doi
    if url:
        item["URL"] = url
    return item


def csl_from_authority(record) -> dict:
    """CSL item for an ``authority.AuthorityRecord`` (arXiv or venue)."""
    item: dict[str, Any] = {
        "type": "article" if record.provider == "arxiv" else "paper-conference",
        "title": record.title,
        "author": [person_from_display_name(name) for name in record.authors],
        "issued": {"date-parts": [[int(record.year)]]},
        "URL": record.url,
    }
    if record.provider == "arxiv":
        # Same convention as hand-written thesis entries: "arXiv:<id>" in number.
        item["number"] = f"arXiv:{record.identity.value}"
    elif record.venue:
        item["container-title"] = record.venue
    return item
