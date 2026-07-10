"""Process-level cache, limiter, and Retry-After contracts."""

import asyncio
import random

import pytest

from citation.providers.net import (
    AsyncRateLimiter,
    FetchResponse,
    ProviderHTTPError,
    ProviderRateLimited,
    ProviderTimeout,
    TTLCache,
    fetch_with_retries,
    redact,
)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_ttl_cache_expires_by_clock_and_never_returns_stale():
    clock = FakeClock()
    cache = TTLCache(clock=clock)
    cache.put("k", {"v": 1}, ttl_seconds=900)
    assert cache.get("k") == {"v": 1}
    clock.now = 899.9
    assert cache.get("k") == {"v": 1}
    clock.now = 900.0
    assert cache.get("k") is None
    assert len(cache) == 0


def test_ttl_cache_miss_returns_none():
    assert TTLCache().get("absent") is None


def _run(coro):
    return asyncio.run(coro)


def test_limiter_spaces_request_starts():
    clock = FakeClock()
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.now += seconds

    limiter = AsyncRateLimiter(
        max_concurrency=1, min_interval=0.5, clock=clock, sleep=fake_sleep
    )

    async def scenario():
        async with limiter.slot():
            pass
        async with limiter.slot():
            pass
        async with limiter.slot():
            pass

    _run(scenario())
    # First call is immediate; subsequent starts are spaced by min_interval.
    assert sleeps == [0.5, 0.5]


def test_limiter_update_from_crossref_headers():
    limiter = AsyncRateLimiter(max_concurrency=2, min_interval=0.0)
    limiter.update_from_headers(
        {"X-Rate-Limit-Limit": "50", "X-Rate-Limit-Interval": "1s"}
    )
    assert limiter.min_interval == pytest.approx(0.02)
    # Garbage headers leave settings untouched.
    limiter.update_from_headers({"X-Rate-Limit-Limit": "bogus"})
    assert limiter.min_interval == pytest.approx(0.02)


def test_limiter_bounds_concurrency():
    limiter = AsyncRateLimiter(max_concurrency=2)
    peak = 0
    active = 0

    async def worker():
        nonlocal peak, active
        async with limiter.slot():
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0)
            active -= 1

    async def scenario():
        await asyncio.wait_for(
            asyncio.gather(*[worker() for _ in range(6)]), timeout=5
        )

    _run(scenario())
    assert peak <= 2


def _limiter():
    async def no_sleep(_s):
        return None

    return AsyncRateLimiter(max_concurrency=1, sleep=no_sleep)


def test_retry_after_is_honored_with_jitter_max_two_retries():
    responses = [
        FetchResponse(status=429, headers={"Retry-After": "3"}),
        FetchResponse(status=429, headers={"Retry-After": "5"}),
        FetchResponse(status=200, body=b"ok"),
    ]
    slept: list[float] = []

    async def fetch():
        return responses.pop(0)

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    result = _run(fetch_with_retries(
        fetch,
        provider="crossref",
        limiter=_limiter(),
        sleep=sleep,
        rng=random.Random(42),
    ))
    assert result.status == 200
    assert len(slept) == 2
    assert 3.0 <= slept[0] <= 4.0  # Retry-After + jitter in [0, 1)
    assert 5.0 <= slept[1] <= 6.0


def test_rate_limit_exhaustion_raises_after_two_retries():
    calls = 0

    async def fetch():
        nonlocal calls
        calls += 1
        return FetchResponse(status=429, headers={"Retry-After": "1"})

    async def sleep(_seconds: float) -> None:
        return None

    with pytest.raises(ProviderRateLimited) as exc:
        _run(fetch_with_retries(
            fetch, provider="openalex", limiter=_limiter(), sleep=sleep
        ))
    assert calls == 3  # initial + two retries
    assert exc.value.retry_after == 1.0


def test_http_error_and_timeout_are_distinct():
    async def fetch_403():
        return FetchResponse(status=403)

    with pytest.raises(ProviderHTTPError) as exc:
        _run(fetch_with_retries(fetch_403, provider="crossref", limiter=_limiter()))
    assert exc.value.status == 403

    async def fetch_timeout():
        raise asyncio.TimeoutError("deadline")

    with pytest.raises(ProviderTimeout):
        _run(fetch_with_retries(fetch_timeout, provider="crossref", limiter=_limiter()))


def test_success_headers_feed_limiter_adaptation():
    limiter = _limiter()

    async def fetch():
        return FetchResponse(
            status=200,
            headers={"x-rate-limit-limit": "10", "x-rate-limit-interval": "1s"},
        )

    _run(fetch_with_retries(fetch, provider="crossref", limiter=limiter))
    assert limiter.min_interval == pytest.approx(0.1)


def test_redact_blanks_every_secret_occurrence():
    text = "GET https://api.openalex.org/works?api_key=sk-123&q=x sk-123"
    assert redact(text, "sk-123", None, "") == (
        "GET https://api.openalex.org/works?api_key=[redacted]&q=x [redacted]"
    )
