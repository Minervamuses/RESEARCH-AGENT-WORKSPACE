"""Process-level networking primitives shared by all citation providers.

One TTL cache and one rate limiter per provider live on the process-scoped
:class:`citation.hub.CitationProviderHub`; every session-scoped Coordinator
shares them. Policy constants (per plan):

  * search results cached 15 minutes, DOI lookups 24 hours;
  * errors are never cached;
  * HTTP 429 honors ``Retry-After`` with jitter, at most two retries;
  * Crossref concurrency/spacing adjusts to its rate-limit response headers.
"""

from __future__ import annotations

import asyncio
import contextlib
import random
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping

SEARCH_TTL_SECONDS = 15 * 60
DOI_TTL_SECONDS = 24 * 60 * 60

MAX_RATE_LIMIT_RETRIES = 2
_DEFAULT_RETRY_AFTER_SECONDS = 2.0
_MAX_RETRY_AFTER_SECONDS = 30.0


class ProviderError(RuntimeError):
    """Base class: one provider call failed (never cached)."""

    def __init__(self, provider: str, detail: str):
        super().__init__(f"{provider}: {detail}")
        self.provider = provider
        self.detail = detail


class ProviderTimeout(ProviderError):
    pass


class ProviderRateLimited(ProviderError):
    def __init__(self, provider: str, detail: str, retry_after: float | None = None):
        super().__init__(provider, detail)
        self.retry_after = retry_after


class ProviderHTTPError(ProviderError):
    def __init__(self, provider: str, status: int, detail: str = ""):
        super().__init__(provider, detail or f"HTTP {status}")
        self.status = status


class ProviderDisabled(ProviderError):
    pass


def redact(text: str, *secrets: str | None) -> str:
    """Blank out every secret occurrence in ``text`` (for traces/logs)."""
    out = text
    for secret in secrets:
        if secret:
            out = out.replace(secret, "[redacted]")
    return out


class TTLCache:
    """Thread-safe TTL cache; successful values only — callers never cache errors."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._items: dict[Any, tuple[float, Any]] = {}

    def get(self, key: Any) -> Any | None:
        now = self._clock()
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            expires, value = item
            if now >= expires:
                del self._items[key]
                return None
            return value

    def put(self, key: Any, value: Any, ttl_seconds: float) -> None:
        with self._lock:
            self._items[key] = (self._clock() + ttl_seconds, value)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)


class AsyncRateLimiter:
    """Concurrency + request-spacing limiter, adjustable at runtime.

    ``max_concurrency`` bounds in-flight calls; ``min_interval`` spaces call
    *starts*. ``update_from_headers`` adapts to Crossref's
    ``x-rate-limit-limit`` / ``x-rate-limit-interval`` headers so polite/public
    pool changes take effect without restarts.
    """

    def __init__(
        self,
        *,
        max_concurrency: int = 2,
        min_interval: float = 0.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._max_concurrency = max(1, int(max_concurrency))
        self._min_interval = max(0.0, float(min_interval))
        self._clock = clock
        self._sleep = sleep
        self._active = 0
        self._next_start = 0.0
        self._cond: asyncio.Condition | None = None

    def _condition(self) -> asyncio.Condition:
        # Created lazily so the limiter can be built outside an event loop.
        if self._cond is None:
            self._cond = asyncio.Condition()
        return self._cond

    @property
    def max_concurrency(self) -> int:
        return self._max_concurrency

    @property
    def min_interval(self) -> float:
        return self._min_interval

    def update(
        self,
        *,
        max_concurrency: int | None = None,
        min_interval: float | None = None,
    ) -> None:
        if max_concurrency is not None:
            self._max_concurrency = max(1, int(max_concurrency))
        if min_interval is not None:
            self._min_interval = max(0.0, float(min_interval))

    def update_from_headers(self, headers: Mapping[str, str]) -> None:
        """Adapt spacing to Crossref-style rate-limit headers, if present."""
        lowered = {k.lower(): v for k, v in headers.items()}
        raw_limit = lowered.get("x-rate-limit-limit", "")
        raw_interval = lowered.get("x-rate-limit-interval", "")
        match = re.fullmatch(r"(\d+)\s*s?", raw_interval.strip())
        if not raw_limit.isdigit() or not match:
            return
        limit = int(raw_limit)
        interval = int(match.group(1))
        if limit <= 0 or interval <= 0:
            return
        self.update(min_interval=interval / limit)

    @contextlib.asynccontextmanager
    async def slot(self):
        cond = self._condition()
        async with cond:
            while self._active >= self._max_concurrency:
                await cond.wait()
            self._active += 1
            now = self._clock()
            wait = self._next_start - now
            self._next_start = max(self._next_start, now) + self._min_interval
        try:
            if wait > 0:
                await self._sleep(wait)
            yield
        finally:
            async with cond:
                self._active -= 1
                cond.notify_all()


@dataclass
class FetchResponse:
    """Transport-agnostic HTTP response used by provider clients and tests."""

    status: int
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


def _parse_retry_after(headers: Mapping[str, str]) -> float | None:
    lowered = {k.lower(): v for k, v in headers.items()}
    raw = lowered.get("retry-after", "").strip()
    if not raw:
        return None
    try:
        return max(0.0, min(float(raw), _MAX_RETRY_AFTER_SECONDS))
    except ValueError:
        return None  # HTTP-date form: fall back to default backoff


async def fetch_with_retries(
    fetch: Callable[[], Awaitable[FetchResponse]],
    *,
    provider: str,
    limiter: AsyncRateLimiter,
    max_retries: int = MAX_RATE_LIMIT_RETRIES,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    rng: random.Random | None = None,
) -> FetchResponse:
    """Run ``fetch`` under the limiter, honoring Retry-After on 429.

    Retries at most ``max_retries`` times with jitter; any other non-2xx
    status raises :class:`ProviderHTTPError`, timeouts raise
    :class:`ProviderTimeout`. Callers cache only successful results.
    """
    rng = rng or random.Random()
    attempt = 0
    while True:
        async with limiter.slot():
            try:
                response = await fetch()
            except (asyncio.TimeoutError, TimeoutError) as exc:
                raise ProviderTimeout(provider, f"request timed out: {exc}") from exc
        limiter.update_from_headers(response.headers)
        if response.status == 429:
            retry_after = _parse_retry_after(response.headers)
            if attempt >= max_retries:
                raise ProviderRateLimited(
                    provider,
                    f"HTTP 429 after {attempt + 1} attempts",
                    retry_after=retry_after,
                )
            delay = (
                retry_after if retry_after is not None else _DEFAULT_RETRY_AFTER_SECONDS
            )
            await sleep(delay + rng.uniform(0.0, 1.0))
            attempt += 1
            continue
        if response.status >= 400:
            raise ProviderHTTPError(provider, response.status)
        return response
