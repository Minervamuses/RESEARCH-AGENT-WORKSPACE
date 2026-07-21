"""Provider-neutral query and record contracts for citation discovery."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from skills.citation.normalize import normalize_title

# Per-provider, per-query hard cap on returned records (plan: 每provider/query最多20筆).
MAX_RECORDS_PER_QUERY = 20


def _query_text(value: str) -> str:
    """Normalize human bibliographic text without adding provider syntax."""
    if not isinstance(value, str):
        raise ValueError("bibliographic fields must be strings")
    text = unicodedata.normalize("NFKC", value).strip()
    if any(ord(char) < 0x20 for char in text):
        raise ValueError("bibliographic fields contain control characters")
    return text


@dataclass(frozen=True)
class BibliographicQuery:
    """Structured identity hints shared by provider-specific query planners.

    Exact identifiers and user-policy constraints deliberately do not live in
    this DTO.  The resolver handles exact identifiers before discovery and
    evaluates hard constraints after providers return candidate records.
    """

    title: str
    authors: tuple[str, ...] = ()
    year: int | None = None
    venue: str = ""
    work_type: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", _query_text(self.title))
        object.__setattr__(
            self,
            "authors",
            tuple(_query_text(author) for author in self.authors if author.strip()),
        )
        object.__setattr__(self, "venue", _query_text(self.venue))
        object.__setattr__(self, "work_type", _query_text(self.work_type))
        if self.year is not None and not 1000 <= self.year <= 2999:
            raise ValueError("bibliographic year is out of range")

    @property
    def first_author(self) -> str:
        return self.authors[0] if self.authors else ""

    @property
    def fingerprint(self) -> tuple:
        """Stable, secret-free cache key component."""
        return (self.title, self.authors, self.year, self.venue, self.work_type)


@dataclass(frozen=True)
class QueryPass:
    """One deterministic provider-native search pass."""

    name: str
    params: tuple[tuple[str, str], ...]

    @classmethod
    def build(cls, name: str, params: dict[str, str]) -> "QueryPass":
        return cls(name=name, params=tuple(params.items()))

    def as_params(self) -> dict[str, str]:
        return dict(self.params)


@dataclass
class ProviderRecord:
    """One provider hit, normalized just enough for fusion and display.

    ``provider_id`` is namespaced (``crossref:10...``, ``openalex:W...``,
    ``web:<url>``) so IDs never collide across providers. ``rank`` is the
    provider's own 0-based result order — the only cross-provider comparable
    signal; ``raw_score`` is kept as evidence but never compared across
    providers.
    """

    provider: str
    provider_id: str
    rank: int
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str = ""
    doi: str | None = None
    url: str | None = None
    work_type: str = ""
    snippet: str = ""
    raw_score: float | None = None
    identifiers: dict[str, str] = field(default_factory=dict)
    publisher: str = ""
    resource_type: str = ""
    version_kind: str = "unknown"
    landing_url: str | None = None
    relations: dict[str, list[str]] = field(default_factory=dict)
    field_provenance: dict[str, str] = field(default_factory=dict)


def plausible_identity_hit(query: BibliographicQuery, record: ProviderRecord) -> bool:
    """Return a loose recall check used only to decide whether to fall back.

    This never authorizes a DOI.  The stricter resolver policy still evaluates
    every returned record and may reject or mark it ambiguous.
    """
    wanted = normalize_title(query.title)
    actual = normalize_title(record.title)
    if wanted:
        if not actual:
            return False
        wanted_tokens = set(wanted.split())
        actual_tokens = set(actual.split())
        overlap = (
            len(wanted_tokens & actual_tokens) / len(wanted_tokens | actual_tokens)
            if wanted_tokens | actual_tokens
            else 0.0
        )
        similarity = max(SequenceMatcher(None, wanted, actual).ratio(), overlap)
        if similarity < 0.75:
            return False
    if query.authors and record.authors:
        expected = {
            token
            for author in query.authors
            for token in normalize_title(author).split()
        }
        observed = {
            token
            for author in record.authors
            for token in normalize_title(author).split()
        }
        if expected and observed and not expected & observed:
            return False
    if query.year is not None and record.year is not None:
        if abs(query.year - record.year) > 1:
            return False
    return bool(wanted or query.authors)
