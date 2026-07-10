"""Canonical BibTeX validation and re-serialization via pybtex.

Only the *re-serialized* canonical form is ever persisted — the raw provider
response is validated, mined for fields, and discarded. pybtex's parser is
the single BibTeX lexer in this project (no home-grown tokenizer): comments,
@string macros, and junk surrounding the entry are consumed or expanded by
the parse and simply do not survive canonical serialization.

Hard requirements enforced here:
  * payload no larger than :data:`MAX_BIBTEX_BYTES` (1 MiB);
  * exactly one bibliographic entry;
  * empty ``@preamble``.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field, replace

import pybtex.errors
from pybtex.database import parse_string

from citation.normalize import strip_latex

MAX_BIBTEX_BYTES = 1 * 1024 * 1024


class BibtexValidationError(ValueError):
    """Raised when a BibTeX payload fails canonical validation.

    ``code`` is machine-readable: ``payload_too_large`` / ``parse_failed`` /
    ``not_exactly_one_entry`` / ``nonempty_preamble``.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CanonicalBibtex:
    """One validated entry plus the canonical serialization to persist."""

    text: str
    entry_key: str
    entry_type: str
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    venue: str = ""


@contextlib.contextmanager
def _strict_pybtex():
    previous = pybtex.errors.strict
    pybtex.errors.set_strict_mode(True)
    try:
        yield
    finally:
        pybtex.errors.set_strict_mode(previous)


def _extract_year(raw: str | None) -> int | None:
    if not raw:
        return None
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < 4:
        return None
    try:
        return int(digits[:4])
    except ValueError:
        return None


def parse_canonical_bibtex(payload: str | None) -> CanonicalBibtex:
    """Validate ``payload`` and return the canonical entry.

    Raises :class:`BibtexValidationError` on any violation; never returns a
    partially-validated record.
    """
    if not payload or not payload.strip():
        raise BibtexValidationError("parse_failed", "empty BibTeX payload")
    if len(payload.encode("utf-8")) > MAX_BIBTEX_BYTES:
        raise BibtexValidationError(
            "payload_too_large",
            f"BibTeX payload exceeds {MAX_BIBTEX_BYTES} bytes",
        )

    try:
        with _strict_pybtex():
            data = parse_string(payload, "bibtex")
    except Exception as exc:  # noqa: BLE001 - every pybtex failure is one outcome
        raise BibtexValidationError(
            "parse_failed", f"pybtex could not parse payload: {exc}"
        ) from exc

    if len(data.entries) != 1:
        raise BibtexValidationError(
            "not_exactly_one_entry",
            f"expected exactly 1 bibliographic entry, got {len(data.entries)}",
        )
    if (data.preamble or "").strip():
        raise BibtexValidationError(
            "nonempty_preamble", "BibTeX payload carries a non-empty @preamble"
        )

    key = next(iter(data.entries))
    entry = data.entries[key]
    fields = {name.lower(): value for name, value in entry.fields.items()}
    authors = [
        str(person) for person in entry.persons.get("author", [])
    ]

    try:
        canonical_text = data.to_string("bibtex")
    except Exception as exc:  # noqa: BLE001 - serialization failure is a parse failure
        raise BibtexValidationError(
            "parse_failed", f"pybtex could not re-serialize payload: {exc}"
        ) from exc
    if not canonical_text.endswith("\n"):
        canonical_text += "\n"

    return CanonicalBibtex(
        text=canonical_text,
        entry_key=key,
        entry_type=entry.type,
        title=strip_latex(fields.get("title", "")).strip(),
        authors=authors,
        year=_extract_year(fields.get("year")),
        doi=(fields.get("doi") or "").strip() or None,
        venue=strip_latex(
            fields.get("journal") or fields.get("booktitle") or ""
        ).strip(),
    )


def inject_doi(canonical: CanonicalBibtex, doi: str) -> CanonicalBibtex:
    """Return a new canonical entry with ``doi`` added.

    Only for the ``doi_injected_from_verified_lookup`` path: the caller must
    have verified ``doi`` against the structured record, and the entry must
    not already carry a (different) DOI.
    """
    if canonical.doi is not None:
        raise BibtexValidationError(
            "parse_failed",
            "refusing to inject a DOI into an entry that already has one",
        )
    with _strict_pybtex():
        data = parse_string(canonical.text, "bibtex")
    entry = data.entries[canonical.entry_key]
    entry.fields["doi"] = doi
    text = data.to_string("bibtex")
    if not text.endswith("\n"):
        text += "\n"
    return replace(canonical, text=text, doi=doi)
