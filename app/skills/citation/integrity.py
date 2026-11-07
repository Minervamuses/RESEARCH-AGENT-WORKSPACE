"""Integrity report for one document against the project bibliography.

The report covers only the text it is given (the editor's current text,
unsaved edits included). It never raises for a bad bibliography: library
errors are reported in ``bibliography.status``/``error``.

An entry is ``verified`` when its DOI, arXiv ID, or official NeurIPS
proceedings URL (``venue:neurips:<year>:<hash>``) has a valid citation bundle
in the citation output directory (the same validation ``storage`` applies
before reusing a bundle); hand-written entries are ``unverified``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from skills.citation import library as lib
from skills.citation.citekeys import Format, find_citations
from skills.citation.storage import (
    HASH_LENGTHS,
    StorageError,
    identity_hash,
    validate_identity_bundle,
)
from skills.citation.types import CanonicalIdentity

BundleCheck = Callable[[dict], bool]


def bundle_checker(output_dir: Path | None) -> BundleCheck:
    """Return ``item -> bool``: does a valid bundle exist for this entry?"""
    by_suffix: dict[str, list[Path]] = {}
    if output_dir is not None:
        try:
            for entry in Path(output_dir).iterdir():
                if entry.is_dir() and not entry.name.startswith("."):
                    by_suffix.setdefault(entry.name.rpartition("--")[2], []).append(entry)
        except OSError:
            by_suffix = {}

    def check(item: dict) -> bool:
        identities = []
        doi = lib.item_doi(item)
        if doi:
            identities.append(CanonicalIdentity("doi", doi))
        arxiv = lib.item_arxiv(item)
        if arxiv:
            identities.append(CanonicalIdentity("arxiv", arxiv))
        neurips = lib.item_neurips(item)
        if neurips:
            identities.append(CanonicalIdentity("venue", neurips))
        for identity in identities:
            for length in HASH_LENGTHS:
                for candidate in by_suffix.get(identity_hash(identity, length=length), ()):
                    try:
                        validate_identity_bundle(candidate, identity)
                        return True
                    except StorageError:
                        continue
        return False

    return check


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


def entry_summary(item: dict, verified: bool) -> dict:
    title = item.get("title")
    return {
        "key": item["id"],
        "authors": _authors(item),
        "year": _year(item),
        "title": title if isinstance(title, str) else "",
        "doi": lib.item_doi(item),
        "type": item.get("type") if isinstance(item.get("type"), str) else "",
        "verification": "verified" if verified else "unverified",
    }


def inspect(
    text: str,
    fmt: Format,
    library_path: Path,
    bundle_check: BundleCheck | None = None,
) -> dict:
    """Build the integrity report for ``text``."""
    check = bundle_check or (lambda _item: False)
    uses = find_citations(text, fmt)
    bibliography = {"path": str(library_path), "status": "ok", "error": None}
    items: list[dict] = []
    try:
        loaded = lib.load(library_path)
        items = loaded.items
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
        summary = entry_summary(item, check(item))
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
