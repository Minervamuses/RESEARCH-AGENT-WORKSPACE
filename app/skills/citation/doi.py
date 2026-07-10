"""DOI canonicalization and candidate extraction.

Canonicalization contract (per plan):
  * Strip ``doi:`` labels and doi.org / dx.doi.org URL prefixes by context.
  * HTML-unescape and percent-decode exactly once each — never in a loop, so
    a DOI that legitimately contains ``%25`` or ``&amp;`` survives one decode.
  * ASCII-only case folding. DOIs are case-insensitive per the DOI handbook,
    but Unicode NFKC is never applied — it can change identity of non-ASCII
    suffix characters.
  * No blind trailing-punctuation stripping: ``)`` or ``.`` can be a legal
    part of a DOI suffix. Extraction from prose returns both the raw match
    and a punctuation-trimmed variant as separate candidates; existence is
    decided by the resolver / structured lookup, never by regex.
"""

from __future__ import annotations

import html
import re
import urllib.parse

# Candidate shape only. Existence must be confirmed by a resolver lookup.
_DOI_CANDIDATE_RE = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)
_DOI_SHAPE_RE = re.compile(r"^10\.\d{4,9}/\S+$")

# Prefixes removed by context (label or resolver URL), longest first.
_URL_PREFIX_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:dx\.)?doi\.org/+", re.IGNORECASE
)
_LABEL_PREFIX_RE = re.compile(r"^doi\s*:\s*", re.IGNORECASE)

# Sentence punctuation that often trails a DOI quoted in prose. Only used to
# offer an *additional* trimmed candidate — never to rewrite the raw match.
_TRAILING_PROSE_PUNCT = ".,;:'\"”’)]}>"


def ascii_casefold(text: str) -> str:
    """Fold only ASCII A-Z to a-z; leave all other characters untouched."""
    return "".join(
        chr(ord(ch) + 32) if "A" <= ch <= "Z" else ch for ch in text
    )


def canonicalize_doi(raw: str | None) -> str | None:
    """Return the canonical form of ``raw`` or None when it is not DOI-shaped.

    Applies prefix stripping, exactly one HTML unescape, exactly one
    percent-decode, and ASCII case folding. Does not verify existence.
    """
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    text = html.unescape(text)
    text = _URL_PREFIX_RE.sub("", text)
    text = _LABEL_PREFIX_RE.sub("", text)
    text = urllib.parse.unquote(text)
    text = text.strip()
    if not _DOI_SHAPE_RE.match(text):
        return None
    return ascii_casefold(text)


def doi_equal(a: str | None, b: str | None) -> bool:
    """True when both values canonicalize to the same non-empty DOI."""
    ca = canonicalize_doi(a)
    cb = canonicalize_doi(b)
    return ca is not None and ca == cb


def extract_doi_candidates(*texts: str | None) -> list[str]:
    """Extract canonical DOI *candidates* from free text, in order, deduped.

    For each regex match the raw canonical form is returned, and — when the
    match ends in common prose punctuation — a trimmed variant as a second
    candidate. Both may be real; only a resolver lookup can decide, so
    neither is dropped here.
    """
    out: list[str] = []
    seen: set[str] = set()

    def _push(value: str | None) -> None:
        canonical = canonicalize_doi(value)
        if canonical and canonical not in seen:
            seen.add(canonical)
            out.append(canonical)

    for text in texts:
        if not text:
            continue
        for match in _DOI_CANDIDATE_RE.finditer(text):
            raw = match.group(0)
            _push(raw)
            trimmed = raw.rstrip(_TRAILING_PROSE_PUNCT)
            if trimmed != raw:
                _push(trimmed)
    return out
