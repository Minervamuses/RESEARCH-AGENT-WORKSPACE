"""Process-level networking primitives shared by all citation providers.

One TTL cache and one rate limiter per provider live on the process-scoped
:class:`skills.citation.hub.CitationProviderHub`; every session-scoped
CitationService shares them. Policy constants:

  * search results cached 15 minutes, DOI lookups 24 hours;
  * errors are never cached;
  * HTTP 429 honors ``Retry-After`` with jitter, at most two retries;
  * transient failures (HTTP 502/503/504, retryable transport errors, and
    timeouts) share a separate budget of two retries with exponential
    backoff plus jitter; a timeout is retried at most once because each
    attempt may already have waited the full client timeout;
  * every retry re-enters the provider's rate limiter;
  * Crossref concurrency/spacing adjusts to its rate-limit response headers.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping

SEARCH_TTL_SECONDS = 15 * 60
DOI_TTL_SECONDS = 24 * 60 * 60

MAX_RATE_LIMIT_RETRIES = 2
MAX_TRANSIENT_RETRIES = 2
MAX_TIMEOUT_RETRIES = 1
RETRYABLE_HTTP_STATUSES = frozenset({502, 503, 504})
_DEFAULT_RETRY_AFTER_SECONDS = 2.0
_MAX_RETRY_AFTER_SECONDS = 30.0
_BACKOFF_BASE_SECONDS = 1.0
_MAX_BACKOFF_SECONDS = 8.0

logger = logging.getLogger(__name__)


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


class ProviderNetworkError(ProviderError):
    """The request failed below HTTP: connect, reset, or protocol breakage."""

    def __init__(
        self,
        provider: str,
        detail: str,
        *,
        exc_type: str = "",
        retryable: bool = True,
    ):
        super().__init__(provider, detail)
        self.exc_type = exc_type
        self.retryable = retryable


class TransportFailure(Exception):
    """Provider-neutral transport failure raised by an injected fetcher.

    Fetchers are shared across providers, so they cannot name the provider;
    :func:`fetch_with_retries` maps this to :class:`ProviderNetworkError`.
    ``retryable`` marks transient breakage (connection refused/reset, server
    disconnect) as opposed to deterministic failures such as redirect loops.
    """

    def __init__(self, exc_type: str, detail: str, *, retryable: bool):
        super().__init__(f"{exc_type}: {detail}")
        self.exc_type = exc_type
        self.detail = detail
        self.retryable = retryable


TRANSIENT_FAILURE_KINDS = frozenset({
    "rate_limited", "timeout", "network_error", "server_error",
})


def failure_kind(exc: ProviderError) -> str:
    """Return a stable, free-text-free category for a provider failure.

    ``rate_limited``, ``timeout``, ``network_error`` (retryable transport),
    and ``server_error`` (HTTP 5xx) are transient: retries were already
    exhausted, but the same request may succeed later. ``http_error`` (4xx),
    ``transport_error`` (non-retryable transport), ``disabled``, and
    ``error`` (unparseable or invalid responses) are not.
    """
    if isinstance(exc, ProviderRateLimited):
        return "rate_limited"
    if isinstance(exc, ProviderTimeout):
        return "timeout"
    if isinstance(exc, ProviderNetworkError):
        return "network_error" if exc.retryable else "transport_error"
    if isinstance(exc, ProviderDisabled):
        return "disabled"
    if isinstance(exc, ProviderHTTPError):
        return "server_error" if exc.status >= 500 else "http_error"
    return "error"


def describe_failure(exc: ProviderError) -> str:
    """``failure_kind`` plus the HTTP status or exception type, for diagnostics."""
    kind = failure_kind(exc)
    if isinstance(exc, ProviderHTTPError):
        return f"{kind}({exc.status})"
    if isinstance(exc, ProviderNetworkError) and exc.exc_type:
        return f"{kind}({exc.exc_type})"
    return kind


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
        """Adapt concurrency and spacing to Crossref-style headers."""
        lowered = {k.lower(): v for k, v in headers.items()}
        raw_concurrency = lowered.get("x-concurrency-limit", "").strip()
        if raw_concurrency.isdigit() and int(raw_concurrency) > 0:
            self.update(max_concurrency=int(raw_concurrency))
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


# Module-level so offline tests can skip real backoff without patching asyncio.
_retry_sleep: Callable[[float], Awaitable[None]] = asyncio.sleep


def _backoff_seconds(retry: int) -> float:
    return min(_BACKOFF_BASE_SECONDS * 2 ** (retry - 1), _MAX_BACKOFF_SECONDS)


async def _attempt(
    fetch: Callable[[], Awaitable[FetchResponse]],
    *,
    provider: str,
    limiter: AsyncRateLimiter,
) -> FetchResponse:
    async with limiter.slot():
        try:
            return await fetch()
        except (asyncio.TimeoutError, TimeoutError) as exc:
            raise ProviderTimeout(provider, f"request timed out: {exc}") from exc
        except TransportFailure as exc:
            raise ProviderNetworkError(
                provider,
                exc.detail,
                exc_type=exc.exc_type,
                retryable=exc.retryable,
            ) from exc


async def fetch_with_retries(
    fetch: Callable[[], Awaitable[FetchResponse]],
    *,
    provider: str,
    limiter: AsyncRateLimiter,
    max_retries: int = MAX_RATE_LIMIT_RETRIES,
    max_transient_retries: int = MAX_TRANSIENT_RETRIES,
    sleep: Callable[[float], Awaitable[None]] | None = None,
    rng: random.Random | None = None,
) -> FetchResponse:
    """Run ``fetch`` under the limiter with bounded, classified retries.

    HTTP 429 is retried at most ``max_retries`` times, honoring Retry-After.
    HTTP 502/503/504, retryable transport failures, and timeouts share a
    budget of ``max_transient_retries`` (timeouts at most once), using
    Retry-After when present and exponential backoff otherwise; every delay
    adds jitter. Exhausted or non-retryable failures raise
    :class:`ProviderRateLimited`, :class:`ProviderHTTPError`,
    :class:`ProviderTimeout`, or :class:`ProviderNetworkError`. Callers
    cache only successful results.
    """
    rng = rng or random.Random()
    sleep = sleep if sleep is not None else _retry_sleep
    rate_limit_retries = 0
    transient_retries = 0
    timeout_retries = 0

    async def back_off(kind: str, delay: float) -> None:
        delay += rng.uniform(0.0, 1.0)
        logger.info(
            "citation provider %s %s; retry %d in %.1fs",
            provider,
            kind,
            rate_limit_retries + transient_retries,
            delay,
        )
        await sleep(delay)

    while True:
        try:
            response = await _attempt(fetch, provider=provider, limiter=limiter)
        except ProviderTimeout:
            if (
                timeout_retries >= MAX_TIMEOUT_RETRIES
                or transient_retries >= max_transient_retries
            ):
                raise
            timeout_retries += 1
            transient_retries += 1
            await back_off("timed out", _backoff_seconds(transient_retries))
            continue
        except ProviderNetworkError as exc:
            if not exc.retryable or transient_retries >= max_transient_retries:
                raise
            transient_retries += 1
            await back_off(
                f"transport failure {exc.exc_type}",
                _backoff_seconds(transient_retries),
            )
            continue
        limiter.update_from_headers(response.headers)
        if response.status == 429:
            retry_after = _parse_retry_after(response.headers)
            if rate_limit_retries >= max_retries:
                raise ProviderRateLimited(
                    provider,
                    f"HTTP 429 after {rate_limit_retries + 1} attempts",
                    retry_after=retry_after,
                )
            rate_limit_retries += 1
            await back_off(
                "rate limited (HTTP 429)",
                retry_after if retry_after is not None else _DEFAULT_RETRY_AFTER_SECONDS,
            )
            continue
        if (
            response.status in RETRYABLE_HTTP_STATUSES
            and transient_retries < max_transient_retries
        ):
            transient_retries += 1
            retry_after = _parse_retry_after(response.headers)
            await back_off(
                f"returned HTTP {response.status}",
                retry_after
                if retry_after is not None
                else _backoff_seconds(transient_retries),
            )
            continue
        if response.status >= 400:
            attempts = rate_limit_retries + transient_retries + 1
            raise ProviderHTTPError(
                provider,
                response.status,
                f"HTTP {response.status}"
                + (f" after {attempts} attempts" if attempts > 1 else ""),
            )
        return response
