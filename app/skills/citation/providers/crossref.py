"""Crossref works search client.

Crossref is a *discovery* provider here: it proposes candidates and ranks
them, but confirm-time verification always re-fetches the structured record
via doi.org content negotiation (RA-independent), so Crossref is never the
sole verification authority for a DOI.

Uses the process-level cache/limiter from the hub; search results are cached
for :data:`~citation.providers.net.SEARCH_TTL_SECONDS`, errors never.
"""

from __future__ import annotations

import json
import urllib.parse
from collections.abc import Iterable
from typing import Awaitable, Callable

from skills.citation.doi import canonicalize_doi
from skills.citation.providers.base import (
    MAX_RECORDS_PER_QUERY,
    BibliographicQuery,
    ProviderRecord,
    QueryPass,
    RelationEdge,
    plausible_identity_hit,
)
from skills.citation.providers.net import (
    SEARCH_TTL_SECONDS,
    AsyncRateLimiter,
    FetchResponse,
    ProviderError,
    TTLCache,
    fetch_with_retries,
)
from skills.citation.types import PublishedDateFilter

PROVIDER_NAME = "crossref"
SEARCH_URL = "https://api.crossref.org/works"

# Async transport: (url, headers) -> FetchResponse. Injected by the hub.
Fetcher = Callable[[str, dict[str, str]], Awaitable[FetchResponse]]


def _user_agent(mailto: str | None) -> str:
    base = "research-agent-citation/1.0"
    return f"{base} (mailto:{mailto})" if mailto else base


def _first_author_family_name(name: str) -> str:
    """Return the family-name hint Crossref expects in ``query.author``."""
    normalized = " ".join(name.split())
    if not normalized:
        return ""
    if "," in normalized:
        return normalized.split(",", 1)[0].strip()
    return normalized.rsplit(" ", 1)[-1]


def build_work_query_plan(
    query: BibliographicQuery,
    *,
    rows: int = MAX_RECORDS_PER_QUERY,
) -> tuple[QueryPass, ...]:
    """Build Crossref-native strict and recall passes without doing I/O."""
    rows = max(1, min(rows, MAX_RECORDS_PER_QUERY))
    passes: list[QueryPass] = []

    if query.title:
        strict: dict[str, str] = {
            "query.title": query.title,
            "rows": str(rows),
        }
        family_name = _first_author_family_name(query.first_author)
        if family_name:
            strict["query.author"] = family_name
        if query.year is not None:
            strict["filter"] = (
                f"from-pub-date:{query.year - 1}-01-01,"
                f"until-pub-date:{query.year + 1}-12-31"
            )
        passes.append(QueryPass.build("strict", strict))

    bibliographic = " ".join(
        part
        for part in (
            query.title,
            query.first_author,
            str(query.year) if query.year is not None else "",
            query.venue,
        )
        if part
    )
    if bibliographic:
        passes.append(
            QueryPass.build(
                "fallback",
                {
                    "query.bibliographic": bibliographic,
                    "rows": str(rows),
                },
            )
        )
    return tuple(passes)


def _iter_relation_values(value: object) -> Iterable[object]:
    if isinstance(value, (list, tuple)):
        return value
    if value is None:
        return ()
    return (value,)


def _relation_identifier(value: object, identifier_type: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    canonical = canonicalize_doi(text)
    if identifier_type.casefold() == "doi" or canonical:
        return canonical or text
    return text


def _parse_relations(
    item: dict,
) -> tuple[dict[str, list[str]], tuple[RelationEdge, ...]]:
    relations: dict[str, list[str]] = {}
    edges: list[RelationEdge] = []
    edge_keys: set[tuple[str, str, str, str, str]] = set()

    def add(
        relation_type: object,
        identifier: object,
        *,
        identifier_type: object = "",
        resource_type: object = "",
        detail: object = "",
    ) -> None:
        rel = str(relation_type or "").strip().casefold()
        id_type = str(identifier_type or "").strip().casefold()
        normalized_id = _relation_identifier(identifier, id_type)
        if not rel or not normalized_id:
            return
        values = relations.setdefault(rel, [])
        if normalized_id not in values:
            values.append(normalized_id)
        edge = RelationEdge(
            relation_type=rel,
            identifier=normalized_id,
            identifier_type=id_type,
            resource_type=str(resource_type or "").strip(),
            detail=str(detail or "").strip(),
        )
        key = (
            edge.relation_type,
            edge.identifier,
            edge.identifier_type,
            edge.resource_type,
            edge.detail,
        )
        if key not in edge_keys:
            edge_keys.add(key)
            edges.append(edge)

    raw_relation = item.get("relation") or {}
    if isinstance(raw_relation, dict):
        for relation_type, values in raw_relation.items():
            for value in _iter_relation_values(values):
                if isinstance(value, dict):
                    add(
                        relation_type,
                        value.get("id") or value.get("DOI") or value.get("doi"),
                        identifier_type=value.get("id-type", ""),
                        resource_type=value.get("type", ""),
                        detail=value.get("asserted-by", ""),
                    )
                else:
                    add(relation_type, value)

    for relation_type in ("update-to", "updated-by"):
        for value in _iter_relation_values(item.get(relation_type)):
            if isinstance(value, dict):
                add(
                    relation_type,
                    value.get("DOI") or value.get("doi") or value.get("id"),
                    identifier_type=value.get("id-type", "doi"),
                    resource_type=value.get("type", ""),
                    detail=value.get("label", ""),
                )
            else:
                add(relation_type, value, identifier_type="doi")

    return relations, tuple(edges)


def _parse_aliases(item: dict, doi: str) -> tuple[str, ...]:
    raw_aliases = item.get("aliases") or ()
    if isinstance(raw_aliases, str):
        raw_aliases = (raw_aliases,)
    aliases: list[str] = []
    for value in raw_aliases:
        alias = canonicalize_doi(value if isinstance(value, str) else None)
        if alias and alias != doi and alias not in aliases:
            aliases.append(alias)
    return tuple(aliases)


_PUBLISHED_WORK_TYPES = {
    "book",
    "book-chapter",
    "book-part",
    "book-section",
    "book-series",
    "book-set",
    "book-track",
    "dissertation",
    "edited-book",
    "journal-article",
    "monograph",
    "peer-review",
    "proceedings",
    "proceedings-article",
    "proceedings-series",
    "reference-book",
    "reference-entry",
    "report",
    "standard",
}


def _version_kind(item: dict, relations: dict[str, list[str]]) -> str:
    work_type = str(item.get("type", "") or "").strip().casefold()
    subtype = str(item.get("subtype", "") or "").strip().casefold()
    if "is-preprint-of" in relations or subtype == "preprint":
        return "preprint"
    if "has-preprint" in relations or work_type in _PUBLISHED_WORK_TYPES:
        return "published"
    return "unknown"


def parse_work_item(item: dict, rank: int) -> ProviderRecord | None:
    """Normalize one Crossref ``works`` item; None when it has no DOI."""
    doi = canonicalize_doi(item.get("DOI"))
    if not doi:
        return None
    titles = item.get("title") or []
    authors = []
    for author in item.get("author") or []:
        name = " ".join(
            part for part in (author.get("given"), author.get("family")) if part
        ).strip() or author.get("name", "")
        if name:
            authors.append(name)
    year = None
    parts = (item.get("issued") or {}).get("date-parts") or []
    if parts and parts[0]:
        try:
            year = int(parts[0][0])
        except (TypeError, ValueError):
            year = None
    containers = item.get("container-title") or []
    score = item.get("score")
    relations, relation_edges = _parse_relations(item)
    return ProviderRecord(
        provider=PROVIDER_NAME,
        provider_id=f"crossref:{doi}",
        rank=rank,
        title=str(titles[0]) if titles else "",
        authors=authors,
        year=year,
        venue=str(containers[0]) if containers else "",
        doi=doi,
        url=item.get("URL"),
        work_type=str(item.get("type", "") or ""),
        raw_score=float(score) if isinstance(score, (int, float)) else None,
        identifiers={"doi": doi},
        publisher=str(item.get("publisher", "") or ""),
        resource_type=str(item.get("subtype", "") or ""),
        version_kind=_version_kind(item, relations),
        landing_url=item.get("URL"),
        relations=relations,
        aliases=_parse_aliases(item, doi),
        relation_edges=relation_edges,
        version=str(item.get("version", "") or ""),
    )


class CrossrefClient:
    """Bibliographic search over api.crossref.org/works."""

    name = PROVIDER_NAME

    def __init__(
        self,
        *,
        fetcher: Fetcher,
        cache: TTLCache,
        limiter: AsyncRateLimiter,
        mailto: str | None = None,
    ):
        self._fetcher = fetcher
        self._cache = cache
        self._limiter = limiter
        self._mailto = mailto

    async def _fetch_records(
        self,
        query_params: dict[str, str],
    ) -> list[ProviderRecord]:
        params = urllib.parse.urlencode(query_params)
        url = f"{SEARCH_URL}?{params}"
        headers = {
            "Accept": "application/json",
            "User-Agent": _user_agent(self._mailto),
        }

        async def _fetch() -> FetchResponse:
            return await self._fetcher(url, headers)

        response = await fetch_with_retries(
            _fetch, provider=PROVIDER_NAME, limiter=self._limiter
        )
        try:
            data = json.loads(response.text)
            items = data.get("message", {}).get("items", []) or []
        except (json.JSONDecodeError, AttributeError) as exc:
            raise ProviderError(
                PROVIDER_NAME, f"unparseable search response: {exc}"
            ) from exc

        records: list[ProviderRecord] = []
        for item in items:
            record = parse_work_item(item, rank=len(records))
            if record is not None:
                records.append(record)
        return records

    async def search_text(
        self,
        query: str,
        *,
        rows: int = MAX_RECORDS_PER_QUERY,
        date_filter: PublishedDateFilter | None = None,
    ) -> list[ProviderRecord]:
        rows = max(1, min(rows, MAX_RECORDS_PER_QUERY))
        date_key = (
            (date_filter.date_from, date_filter.date_to) if date_filter else None
        )
        cache_key = (PROVIDER_NAME, "search", query, rows, date_key)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return list(cached)

        query_params: dict[str, str] = {
            "query.bibliographic": query,
            "rows": str(rows),
            "select": "DOI,title,author,issued,score,container-title,type,URL",
        }
        native_filters = []
        if date_filter is not None and date_filter.date_from:
            native_filters.append(f"from-pub-date:{date_filter.date_from}")
        if date_filter is not None and date_filter.date_to:
            native_filters.append(f"until-pub-date:{date_filter.date_to}")
        if native_filters:
            query_params["filter"] = ",".join(native_filters)
        records = await self._fetch_records(query_params)
        self._cache.put(cache_key, list(records), SEARCH_TTL_SECONDS)
        return records

    async def search(
        self,
        query: str,
        *,
        rows: int = MAX_RECORDS_PER_QUERY,
        date_filter: PublishedDateFilter | None = None,
    ) -> list[ProviderRecord]:
        """Compatibility wrapper for callers still using generic search."""
        return await self.search_text(query, rows=rows, date_filter=date_filter)

    async def search_work(
        self,
        query: BibliographicQuery,
        *,
        rows: int = MAX_RECORDS_PER_QUERY,
    ) -> list[ProviderRecord]:
        """Search Crossref using provider-native strict/fallback passes."""
        rows = max(1, min(rows, MAX_RECORDS_PER_QUERY))
        cache_key = (PROVIDER_NAME, "search_work", query.fingerprint, rows)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return list(cached)

        records_by_doi: dict[str, ProviderRecord] = {}
        for query_pass in build_work_query_plan(query, rows=rows):
            pass_records = await self._fetch_records(query_pass.as_params())
            for record in pass_records:
                if record.doi not in records_by_doi:
                    record.rank = len(records_by_doi)
                    records_by_doi[record.doi] = record
            if any(plausible_identity_hit(query, record) for record in pass_records):
                break

        records = list(records_by_doi.values())
        self._cache.put(cache_key, list(records), SEARCH_TTL_SECONDS)
        return records
