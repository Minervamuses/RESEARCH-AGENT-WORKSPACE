"""DataCite REST discovery client with a bounded response contract."""

from __future__ import annotations

import json
import urllib.parse
from typing import Awaitable, Callable

from skills.citation.doi import canonicalize_doi
from skills.citation.providers.base import MAX_RECORDS_PER_QUERY, ProviderRecord
from skills.citation.providers.net import (
    SEARCH_TTL_SECONDS,
    AsyncRateLimiter,
    FetchResponse,
    ProviderError,
    TTLCache,
    fetch_with_retries,
)
from skills.citation.types import PublishedDateFilter

PROVIDER_NAME = "datacite"
SEARCH_URL = "https://api.datacite.org/dois"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024

Fetcher = Callable[[str, dict[str, str]], Awaitable[FetchResponse]]


def _year(attributes: dict) -> int | None:
    for key in ("publicationYear", "published", "created", "registered"):
        value = attributes.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and len(value) >= 4 and value[:4].isdigit():
            return int(value[:4])
    return None


def parse_doi_item(item: dict, rank: int) -> ProviderRecord | None:
    attributes = item.get("attributes") or {}
    doi = canonicalize_doi(attributes.get("doi") or item.get("id"))
    if not doi:
        return None
    titles = attributes.get("titles") or []
    title = next(
        (str(entry.get("title", "")) for entry in titles if entry.get("title")), ""
    )
    authors: list[str] = []
    for creator in attributes.get("creators") or []:
        name = str(creator.get("name", "") or "").strip()
        if not name:
            name = " ".join(
                str(creator.get(key, "") or "").strip()
                for key in ("givenName", "familyName")
            ).strip()
        if name:
            authors.append(name)
    types = attributes.get("types") or {}
    resource_type = str(
        types.get("resourceTypeGeneral") or types.get("resourceType") or ""
    )
    container = attributes.get("container") or {}
    venue = str(container.get("title", "") or "")
    url = attributes.get("url")
    related: dict[str, list[str]] = {}
    for relation in attributes.get("relatedIdentifiers") or []:
        relation_type = str(relation.get("relationType", "") or "")
        value = str(relation.get("relatedIdentifier", "") or "")
        if relation_type and value:
            related.setdefault(relation_type, []).append(value)
    identifiers = {"doi": doi}
    for alternate in attributes.get("alternateIdentifiers") or []:
        kind = str(alternate.get("alternateIdentifierType", "") or "").casefold()
        value = str(alternate.get("alternateIdentifier", "") or "")
        if kind and value:
            identifiers[kind] = value
    text = f"{resource_type} {url or ''}".casefold()
    version_kind = "preprint" if "preprint" in text or "arxiv" in text else "published"
    provenance = {field: PROVIDER_NAME for field in (
        "title", "authors", "year", "venue", "doi", "work_type", "publisher", "url"
    )}
    return ProviderRecord(
        provider=PROVIDER_NAME,
        provider_id=f"datacite:{doi}",
        rank=rank,
        title=title,
        authors=authors,
        year=_year(attributes),
        venue=venue,
        doi=doi,
        url=str(url) if url else None,
        landing_url=str(url) if url else None,
        work_type=resource_type,
        resource_type=resource_type,
        publisher=str(attributes.get("publisher", "") or ""),
        identifiers=identifiers,
        relations=related,
        version_kind=version_kind,
        field_provenance=provenance,
    )


class DataCiteClient:
    name = PROVIDER_NAME

    def __init__(self, *, fetcher: Fetcher, cache: TTLCache, limiter: AsyncRateLimiter):
        self._fetcher = fetcher
        self._cache = cache
        self._limiter = limiter

    async def search(
        self,
        query: str,
        *,
        rows: int = MAX_RECORDS_PER_QUERY,
        date_filter: PublishedDateFilter | None = None,
    ) -> list[ProviderRecord]:
        rows = max(1, min(rows, MAX_RECORDS_PER_QUERY))
        date_key = (date_filter.year_from, date_filter.year_to) if date_filter else None
        cache_key = (PROVIDER_NAME, "search", query, rows, date_key)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return list(cached)
        params: dict[str, str] = {"query": query, "page[size]": str(rows)}
        if date_filter and date_filter.year_from is not None:
            params["query"] += f" AND publicationYear:[{date_filter.year_from} TO *]"
        if date_filter and date_filter.year_to is not None:
            params["query"] += f" AND publicationYear:[* TO {date_filter.year_to}]"
        url = f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"
        headers = {"Accept": "application/vnd.api+json", "User-Agent": "research-agent-citation/1.0"}

        async def _fetch() -> FetchResponse:
            return await self._fetcher(url, headers)

        response = await fetch_with_retries(
            _fetch, provider=PROVIDER_NAME, limiter=self._limiter
        )
        length = response.headers.get("content-length") or response.headers.get("Content-Length")
        if length and length.isdigit() and int(length) > MAX_RESPONSE_BYTES:
            raise ProviderError(PROVIDER_NAME, "response payload exceeds limit")
        if len(response.body) > MAX_RESPONSE_BYTES:
            raise ProviderError(PROVIDER_NAME, "response payload exceeds limit")
        try:
            data = json.loads(response.text)
            items = data.get("data", []) or []
        except (json.JSONDecodeError, AttributeError) as exc:
            raise ProviderError(PROVIDER_NAME, "unparseable search response") from exc
        records: list[ProviderRecord] = []
        for item in items[:rows]:
            record = parse_doi_item(item, len(records))
            if record is not None:
                records.append(record)
        self._cache.put(cache_key, list(records), SEARCH_TTL_SECONDS)
        return records
