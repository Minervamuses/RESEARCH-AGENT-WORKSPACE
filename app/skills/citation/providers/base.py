"""Shared record shape returned by every discovery provider."""

from __future__ import annotations

from dataclasses import dataclass, field

# Per-provider, per-query hard cap on returned records (plan: 每provider/query最多20筆).
MAX_RECORDS_PER_QUERY = 20


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
