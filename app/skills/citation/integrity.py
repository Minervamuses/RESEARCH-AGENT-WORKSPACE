"""Integrity report for one document against the project bibliography.

The report covers only the text it is given (the editor's current text,
unsaved edits included). It never raises for a bad bibliography: library
errors are reported in ``bibliography.status``/``error``.

Entries carry no verification status: ``/citation`` verifies a work against
an authority when it saves it, and hand-written entries are the user's own.
"""

from __future__ import annotations

from pathlib import Path

from skills.citation import library as lib
from skills.citation.citekeys import Format, find_citations


def _authors(item: dict) -> list[str]:
    names = item.get("author") or item.get("editor") or []
    out = []
    for name in names if isinstance(names, list) else []:
        if isinstance(name, dict):
            text = name.get("family") or name.get("literal") or ""
            if isinstance(text, str) and text:
                out.append(text)
    return out


def _year(item: dict) -> int | None:
    token = lib._year_token(item)
    return int(token) if token.isdigit() else None


def entry_summary(item: dict) -> dict:
    title = item.get("title")
    return {
        "key": item["id"],
        "authors": _authors(item),
        "year": _year(item),
        "title": title if isinstance(title, str) else "",
        "doi": lib.item_doi(item),
        "type": item.get("type") if isinstance(item.get("type"), str) else "",
    }


def inspect(
    text: str,
    fmt: Format,
    library_path: Path,
) -> dict:
    """Build the integrity report for ``text``."""
    uses = find_citations(text, fmt)
    bibliography = {"path": str(library_path), "status": "ok", "error": None, "fingerprint": None}
    items: list[dict] = []
    try:
        loaded = lib.load(library_path)
        items = loaded.items
        bibliography["fingerprint"] = loaded.fingerprint
        if not loaded.exists:
            bibliography["status"] = "missing"
    except lib.LibraryError as exc:
        bibliography["status"] = "error"
        bibliography["error"] = {"code": exc.code, "message": str(exc)}
    library_ok = bibliography["status"] != "error"
    known = {item["id"] for item in items}

    order: list[str] = []
    counts: dict[str, int] = {}
    for use in uses:
        if use.key not in counts:
            order.append(use.key)
        counts[use.key] = counts.get(use.key, 0) + 1

    entries = []
    for item in items:
        summary = entry_summary(item)
        summary["citedCount"] = counts.get(item["id"], 0)
        summary["firstUse"] = order.index(item["id"]) if item["id"] in counts else None
        entries.append(summary)

    missing = []
    if library_ok:
        for key in order:
            if key not in known:
                missing.append({
                    "key": key,
                    "uses": [
                        {"start": u.start, "end": u.end, "line": u.line}
                        for u in uses if u.key == key
                    ],
                })

    by_doi: dict[str, list[str]] = {}
    for item in items:
        doi = lib.item_doi(item)
        if doi:
            by_doi.setdefault(doi, []).append(item["id"])

    return {
        "format": fmt,
        "bibliography": bibliography,
        "entries": entries,
        "uses": [
            {**use.to_dict(), "known": (use.key in known) if library_ok else None}
            for use in uses
        ],
        "order": order,
        "missing": missing,
        "uncited": [item["id"] for item in items if item["id"] not in counts],
        "duplicateDois": [
            {"doi": doi, "keys": keys} for doi, keys in by_doi.items() if len(keys) > 1
        ],
    }
