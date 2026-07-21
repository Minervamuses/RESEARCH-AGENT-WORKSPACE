"""RA-independent DOI lookups via doi.org content negotiation.

This is the *verification* provider: the save path re-fetches the
structured CSL JSON record for the selected DOI here (never trusting the
discovery provider's copy), then fetches BibTeX for the same canonical DOI.
A plain DOI-shaped search query also resolves through this singleton
without starting any LLM or web search.

DOI lookups are cached 24 h; errors never.
"""

from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from skills.citation.doi import canonicalize_doi
from skills.citation.providers.net import (
    DOI_TTL_SECONDS,
    AsyncRateLimiter,
    FetchResponse,
    ProviderError,
    ProviderHTTPError,
    TTLCache,
    fetch_with_retries,
)

PROVIDER_NAME = "doi.org"
NEGOTIATE_URL = "https://doi.org/{doi}"
RA_URL = "https://doi.org/ra/{doi}"

CSL_ACCEPT = "application/vnd.citationstyles.csl+json"
BIBTEX_ACCEPT = "application/x-bibtex"

Fetcher = Callable[[str, dict[str, str]], Awaitable[FetchResponse]]


class DoiNotFound(ProviderError):
    """The DOI does not resolve (HTTP 404 from doi.org)."""


@dataclass
class StructuredRecord:
    """CSL JSON bibliographic record for one canonical DOI."""

    doi: str
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str = ""
    work_type: str = ""
    url: str | None = None
    registration_agency: str = ""


def _authors_from_csl(raw: list | None) -> list[str]:
    authors: list[str] = []
    for person in raw or []:
        if not isinstance(person, dict):
            continue
        name = " ".join(
            part for part in (person.get("given"), person.get("family")) if part
        ).strip() or str(person.get("name", "") or person.get("literal", "") or "")
        if name:
            authors.append(name)
    return authors


def parse_csl(doi: str, payload: dict) -> StructuredRecord:
    """Normalize a CSL JSON body into a StructuredRecord."""
    year = None
    parts = (payload.get("issued") or {}).get("date-parts") or []
    if parts and parts[0]:
        try:
            year = int(parts[0][0])
        except (TypeError, ValueError):
            year = None
    record_doi = canonicalize_doi(payload.get("DOI")) or doi
    return StructuredRecord(
        doi=record_doi,
        title=str(payload.get("title", "") or ""),
        authors=_authors_from_csl(payload.get("author")),
        year=year,
        venue=str(payload.get("container-title", "") or ""),
        work_type=str(payload.get("type", "") or ""),
        url=payload.get("URL") or None,
    )


class DoiOrgClient:
    """Content-negotiation lookups against doi.org (CSL JSON / BibTeX / RA)."""

    name = PROVIDER_NAME

    def __init__(
        self,
        *,
        fetcher: Fetcher,
        cache: TTLCache,
        limiter: AsyncRateLimiter,
    ):
        self._fetcher = fetcher
        self._cache = cache
        self._limiter = limiter

    def _encoded(self, doi: str) -> str:
        canonical = canonicalize_doi(doi)
        if canonical is None:
            raise ProviderError(PROVIDER_NAME, f"not a DOI: {doi!r}")
        return canonical, urllib.parse.quote(canonical, safe="/")

    async def _get(self, url: str, accept: str) -> FetchResponse:
        async def _fetch() -> FetchResponse:
            return await self._fetcher(url, {"Accept": accept})

        try:
            return await fetch_with_retries(
                _fetch, provider=PROVIDER_NAME, limiter=self._limiter
            )
        except ProviderHTTPError as exc:
            if exc.status == 404:
                raise DoiNotFound(PROVIDER_NAME, f"DOI does not resolve: {url}") from exc
            raise

    async def fetch_structured(self, doi: str) -> StructuredRecord:
        """Fetch the CSL JSON record for ``doi`` (24 h cache)."""
        canonical, encoded = self._encoded(doi)
        cache_key = (PROVIDER_NAME, "csl", canonical)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        response = await self._get(NEGOTIATE_URL.format(doi=encoded), CSL_ACCEPT)
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError as exc:
            raise ProviderError(
                PROVIDER_NAME, f"CSL response for {canonical} is not JSON"
            ) from exc
        record = parse_csl(canonical, payload)
        self._cache.put(cache_key, record, DOI_TTL_SECONDS)
        return record

    async def fetch_bibtex(self, doi: str) -> str:
        """Fetch raw BibTeX text for ``doi`` (24 h cache). Validation is the
        caller's job (citation.bibtex_canonical)."""
        canonical, encoded = self._encoded(doi)
        cache_key = (PROVIDER_NAME, "bibtex", canonical)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        response = await self._get(NEGOTIATE_URL.format(doi=encoded), BIBTEX_ACCEPT)
        text = response.text
        self._cache.put(cache_key, text, DOI_TTL_SECONDS)
        return text

    async def fetch_registration_agency(self, doi: str) -> str:
        """Return the RA name for ``doi`` ('' when the RA API is unhelpful)."""
        canonical, encoded = self._encoded(doi)
        cache_key = (PROVIDER_NAME, "ra", canonical)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        response = await self._get(RA_URL.format(doi=encoded), "application/json")
        try:
            payload = json.loads(response.text)
            agency = str((payload[0] or {}).get("RA", "") or "")
        except (json.JSONDecodeError, IndexError, KeyError, TypeError):
            agency = ""
        if agency:
            self._cache.put(cache_key, agency, DOI_TTL_SECONDS)
        return agency
