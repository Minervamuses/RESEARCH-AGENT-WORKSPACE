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

        # Crossref starts conservatively; response headers adapt it at runtime.
        self.crossref_limiter = AsyncRateLimiter(max_concurrency=2, min_interval=0.05)
        self.openalex_limiter = AsyncRateLimiter(max_concurrency=2, min_interval=0.1)
        self.doi_org_limiter = AsyncRateLimiter(max_concurrency=4, min_interval=0.0)

        self.crossref = CrossrefClient(
            fetcher=self._fetch,
            cache=self.cache,
            limiter=self.crossref_limiter,
            mailto=env.get("CROSSREF_MAILTO", "").strip() or None,
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
