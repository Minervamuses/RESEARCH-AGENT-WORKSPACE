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
from typing import Awaitable, Callable

from citation.doi import canonicalize_doi
from citation.providers.base import MAX_RECORDS_PER_QUERY, ProviderRecord
from citation.providers.net import (
    SEARCH_TTL_SECONDS,
    AsyncRateLimiter,
    FetchResponse,
    ProviderError,
    TTLCache,
    fetch_with_retries,
)

PROVIDER_NAME = "crossref"
SEARCH_URL = "https://api.crossref.org/works"

# Async transport: (url, headers) -> FetchResponse. Injected by the hub.
Fetcher = Callable[[str, dict[str, str]], Awaitable[FetchResponse]]


def _user_agent(mailto: str | None) -> str:
    base = "research-agent-citation/1.0"
    return f"{base} (mailto:{mailto})" if mailto else base


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

    async def search(self, query: str, *, rows: int = MAX_RECORDS_PER_QUERY) -> list[ProviderRecord]:
        rows = max(1, min(rows, MAX_RECORDS_PER_QUERY))
        cache_key = (PROVIDER_NAME, "search", query, rows)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return list(cached)

        params = urllib.parse.urlencode({
            "query.bibliographic": query,
            "rows": str(rows),
            "select": "DOI,title,author,issued,score,container-title,type,URL",
        })
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
        self._cache.put(cache_key, list(records), SEARCH_TTL_SECONDS)
        return records
