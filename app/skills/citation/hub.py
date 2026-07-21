"""Process-scoped provider hub for citation workflows.

One hub per process owns the shared TTL cache, per-provider rate limiters,
the HTTP transport, and the provider clients. Every session-scoped
Coordinator talks to the same hub, so Crossref/OpenAlex rate limits and
caches are respected process-wide.

OpenAlex is *disabled* (a distinct state, not a failure) when
``OPENALEX_API_KEY`` is absent; the key is only ever sent as a query
parameter and redacted from errors by the client itself.
"""

from __future__ import annotations

import asyncio
import os
import threading

from skills.citation.providers.crossref import CrossrefClient
from skills.citation.providers.datacite import DataCiteClient, MAX_RESPONSE_BYTES
from skills.citation.providers.doi_org import DoiOrgClient
from skills.citation.providers.net import AsyncRateLimiter, FetchResponse, TTLCache
from skills.citation.providers.openalex import OpenAlexClient

_HTTP_TIMEOUT_SECONDS = 25.0


class CitationProviderHub:
    """Shared clients + cache + limiters for every citation Coordinator."""

    def __init__(
        self,
        *,
        env: dict[str, str] | None = None,
        fetcher=None,
        cache: TTLCache | None = None,
    ):
        env = dict(os.environ) if env is None else env
        self.cache = cache if cache is not None else TTLCache()
        self._injected_fetcher = fetcher
        self._http_client = None

        crossref_mailto = env.get("CROSSREF_MAILTO", "").strip() or None
        datacite_mailto = env.get("DATACITE_MAILTO", "").strip() or None

        # Current public/polite pool limits are safe before the first response
        # header arrives; Crossref headers can tighten or relax them at runtime.
        self.crossref_limiter = AsyncRateLimiter(
            max_concurrency=3 if crossref_mailto else 1,
            min_interval=(1.0 / 3.0) if crossref_mailto else 1.0,
        )
        self.openalex_limiter = AsyncRateLimiter(max_concurrency=2, min_interval=0.1)
        self.datacite_limiter = AsyncRateLimiter(
            max_concurrency=2,
            min_interval=0.3 if datacite_mailto else 0.6,
        )
        self.doi_org_limiter = AsyncRateLimiter(max_concurrency=4, min_interval=0.0)

        self.crossref = CrossrefClient(
            fetcher=self._fetch,
            cache=self.cache,
            limiter=self.crossref_limiter,
            mailto=crossref_mailto,
        )
        self.datacite = DataCiteClient(
            fetcher=self._fetch_datacite,
            cache=self.cache,
            limiter=self.datacite_limiter,
            mailto=datacite_mailto,
        )
        api_key = env.get("OPENALEX_API_KEY", "").strip()
        self.openalex = (
            OpenAlexClient(
                fetcher=self._fetch,
                cache=self.cache,
                limiter=self.openalex_limiter,
                api_key=api_key,
            )
            if api_key
            else None
        )
        self.doi_org = DoiOrgClient(
            fetcher=self._fetch,
            cache=self.cache,
            limiter=self.doi_org_limiter,
        )

    @property
    def openalex_enabled(self) -> bool:
        return self.openalex is not None

    async def _fetch(self, url: str, headers: dict[str, str]) -> FetchResponse:
        if self._injected_fetcher is not None:
            return await self._injected_fetcher(url, headers)
        return await self._httpx_fetch(url, headers)

    async def _fetch_datacite(self, url: str, headers: dict[str, str]) -> FetchResponse:
        if self._injected_fetcher is not None:
            response = await self._injected_fetcher(url, headers)
            if len(response.body) > MAX_RESPONSE_BYTES:
                from skills.citation.providers.net import ProviderError
                raise ProviderError("datacite", "response payload exceeds limit")
            return response
        return await self._httpx_fetch_bounded(url, headers, MAX_RESPONSE_BYTES)

    def _get_http_client(self):
        if self._http_client is None:
            import httpx

            self._http_client = httpx.AsyncClient(
                follow_redirects=True,
                timeout=_HTTP_TIMEOUT_SECONDS,
            )
        return self._http_client

    async def _httpx_fetch(self, url: str, headers: dict[str, str]) -> FetchResponse:
        import httpx

        client = self._get_http_client()
        try:
            response = await client.get(url, headers=headers)
        except httpx.TimeoutException as exc:
            # Normalized so fetch_with_retries maps it to ProviderTimeout.
            raise asyncio.TimeoutError(str(exc)) from exc
        return FetchResponse(
            status=response.status_code,
            headers=dict(response.headers),
            body=response.content,
        )

    async def _httpx_fetch_bounded(
        self, url: str, headers: dict[str, str], max_bytes: int
    ) -> FetchResponse:
        """Stream into a bounded buffer; never materialize an oversized body."""
        import httpx

        client = self._get_http_client()
        try:
            async with client.stream("GET", url, headers=headers) as response:
                raw_length = response.headers.get("content-length", "")
                if raw_length.isdigit() and int(raw_length) > max_bytes:
                    from skills.citation.providers.net import ProviderError
                    raise ProviderError("datacite", "response payload exceeds limit")
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        from skills.citation.providers.net import ProviderError
                        raise ProviderError("datacite", "response payload exceeds limit")
                    chunks.append(chunk)
                return FetchResponse(
                    status=response.status_code,
                    headers=dict(response.headers),
                    body=b"".join(chunks),
                )
        except httpx.TimeoutException as exc:
            raise asyncio.TimeoutError(str(exc)) from exc

    async def aclose(self) -> None:
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None


_hub_lock = threading.Lock()
_hub: CitationProviderHub | None = None


def get_provider_hub() -> CitationProviderHub:
    """Process-wide singleton hub (env read once at first use)."""
    global _hub
    with _hub_lock:
        if _hub is None:
            _hub = CitationProviderHub()
        return _hub


def reset_provider_hub() -> None:
    """Testing hook: drop the singleton so the next call rebuilds it."""
    global _hub
    with _hub_lock:
        _hub = None
