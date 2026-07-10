"""OpenAlex works search client.

Enabled only when an ``OPENALEX_API_KEY`` is supplied (the hub reports the
provider as *disabled*, not failed, without one). The key travels only as a
query parameter and is redacted from every exception, trace, and log line
this module produces.
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
    redact,
)

PROVIDER_NAME = "openalex"
SEARCH_URL = "https://api.openalex.org/works"

Fetcher = Callable[[str, dict[str, str]], Awaitable[FetchResponse]]

_OPENALEX_ID_PREFIX = "https://openalex.org/"


def parse_work(result: dict, rank: int) -> ProviderRecord:
    """Normalize one OpenAlex work; records without a DOI are kept
    (OpenAlex covers preprints/whitepapers) but carry doi=None."""
    raw_id = str(result.get("id", "") or "")
    short_id = raw_id.removeprefix(_OPENALEX_ID_PREFIX) or raw_id
    doi = canonicalize_doi(result.get("doi"))
    authors = []
    for authorship in result.get("authorships") or []:
        name = ((authorship.get("author") or {}).get("display_name") or "").strip()
        if name:
            authors.append(name)
    year = result.get("publication_year")
    venue = (
        ((result.get("primary_location") or {}).get("source") or {}).get(
            "display_name"
        )
        or ""
    )
    score = result.get("relevance_score")
    identifiers = {
        key: str(value)
        for key, value in (result.get("ids") or {}).items()
        if isinstance(value, (str, int))
    }
    return ProviderRecord(
        provider=PROVIDER_NAME,
        provider_id=f"openalex:{short_id}" if short_id else f"openalex:rank-{rank}",
        rank=rank,
        title=str(result.get("display_name", "") or ""),
        authors=authors,
        year=int(year) if isinstance(year, int) else None,
        venue=str(venue),
        doi=doi,
        url=result.get("doi") or raw_id or None,
        work_type=str(result.get("type", "") or ""),
        raw_score=float(score) if isinstance(score, (int, float)) else None,
        identifiers=identifiers,
    )


class OpenAlexClient:
    """Relevance search over api.openalex.org/works (API key required)."""

    name = PROVIDER_NAME

    def __init__(
        self,
        *,
        fetcher: Fetcher,
        cache: TTLCache,
        limiter: AsyncRateLimiter,
        api_key: str,
    ):
        if not api_key:
            raise ValueError("OpenAlexClient requires a non-empty api_key")
        self._fetcher = fetcher
        self._cache = cache
        self._limiter = limiter
        self._api_key = api_key

    def _redact(self, text: str) -> str:
        return redact(text, self._api_key)

    async def search(self, query: str, *, rows: int = MAX_RECORDS_PER_QUERY) -> list[ProviderRecord]:
        rows = max(1, min(rows, MAX_RECORDS_PER_QUERY))
        # Cache key must never embed the secret.
        cache_key = (PROVIDER_NAME, "search", query, rows)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return list(cached)

        params = urllib.parse.urlencode({
            "search": query,
            "per-page": str(rows),
            "api_key": self._api_key,
        })
        url = f"{SEARCH_URL}?{params}"
        headers = {"Accept": "application/json"}

        async def _fetch() -> FetchResponse:
            return await self._fetcher(url, headers)

        try:
            response = await fetch_with_retries(
                _fetch, provider=PROVIDER_NAME, limiter=self._limiter
            )
        except ProviderError as exc:
            # Any transport error may echo the request URL: re-raise with the
            # key blanked so no caller can leak it into traces or logs.
            exc.detail = self._redact(exc.detail)
            exc.args = (self._redact(str(exc.args[0])),) if exc.args else exc.args
            raise
        try:
            data = json.loads(response.text)
            results = data.get("results", []) or []
        except (json.JSONDecodeError, AttributeError) as exc:
            raise ProviderError(
                PROVIDER_NAME,
                self._redact(f"unparseable search response: {exc}"),
            ) from exc

        records = [parse_work(result, rank=i) for i, result in enumerate(results)]
        self._cache.put(cache_key, list(records), SEARCH_TTL_SECONDS)
        return records
