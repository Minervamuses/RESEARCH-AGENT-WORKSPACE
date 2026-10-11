"""Process-level cache, limiter, and Retry-After contracts."""

import asyncio
import random

import pytest

from skills.citation.providers.net import (
    AsyncRateLimiter,
    FetchResponse,
    ProviderHTTPError,
    ProviderNetworkError,
    ProviderRateLimited,
    ProviderTimeout,
    TransportFailure,
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
        {
            "X-Rate-Limit-Limit": "50",
            "X-Rate-Limit-Interval": "1s",
            "X-Concurrency-Limit": "3",
        }
    )
    assert limiter.min_interval == pytest.approx(0.02)
    assert limiter.max_concurrency == 3
    # Garbage headers leave settings untouched.
    limiter.update_from_headers({
        "X-Rate-Limit-Limit": "bogus",
        "X-Concurrency-Limit": "bogus",
    })
    assert limiter.min_interval == pytest.approx(0.02)
    assert limiter.max_concurrency == 3


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

    async def no_sleep(_seconds: float) -> None:
        return None

    with pytest.raises(ProviderTimeout):
        _run(fetch_with_retries(
            fetch_timeout, provider="crossref", limiter=_limiter(), sleep=no_sleep,
        ))


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


def _scripted(outcomes):
    """Return a fetch callable replaying responses/exceptions, plus call log."""
    calls: list[int] = []

    async def fetch():
        calls.append(len(calls))
        outcome = outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    return fetch, calls


def _recording_sleep():
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    return sleep, slept


@pytest.mark.parametrize("status", [502, 503, 504])
def test_transient_server_status_is_retried_with_backoff_and_jitter(status):
    fetch, calls = _scripted([
        FetchResponse(status=status),
        FetchResponse(status=200, body=b"ok"),
    ])
    sleep, slept = _recording_sleep()

    result = _run(fetch_with_retries(
        fetch, provider="crossref", limiter=_limiter(), sleep=sleep,
        rng=random.Random(7),
    ))

    assert result.status == 200
    assert len(calls) == 2
    assert len(slept) == 1 and 1.0 <= slept[0] < 2.0


def test_transient_status_exhaustion_reports_attempts():
    fetch, calls = _scripted([
        FetchResponse(status=503),
        FetchResponse(status=502),
        FetchResponse(status=504),
    ])
    sleep, slept = _recording_sleep()

    with pytest.raises(ProviderHTTPError) as exc:
        _run(fetch_with_retries(
            fetch, provider="datacite", limiter=_limiter(), sleep=sleep,
            rng=random.Random(7),
        ))

    assert exc.value.status == 504
    assert "after 3 attempts" in str(exc.value)
    assert len(calls) == 3
    assert 1.0 <= slept[0] < 2.0 and 2.0 <= slept[1] < 3.0  # exponential


def test_transient_status_honors_retry_after():
    fetch, _calls = _scripted([
        FetchResponse(status=503, headers={"Retry-After": "4"}),
        FetchResponse(status=200),
    ])
    sleep, slept = _recording_sleep()

    _run(fetch_with_retries(
        fetch, provider="crossref", limiter=_limiter(), sleep=sleep,
    ))

    assert 4.0 <= slept[0] < 5.0


@pytest.mark.parametrize("status", [400, 404, 500])
def test_deterministic_http_errors_are_not_retried(status):
    fetch, calls = _scripted([FetchResponse(status=status)])
    sleep, slept = _recording_sleep()

    with pytest.raises(ProviderHTTPError) as exc:
        _run(fetch_with_retries(
            fetch, provider="crossref", limiter=_limiter(), sleep=sleep,
        ))

    assert exc.value.status == status
    assert str(exc.value) == f"crossref: HTTP {status}"
    assert len(calls) == 1 and slept == []


def test_retryable_transport_failure_recovers_within_budget():
    fetch, calls = _scripted([
        TransportFailure("ConnectError", "connection refused", retryable=True),
        TransportFailure("RemoteProtocolError", "server disconnected", retryable=True),
        FetchResponse(status=200),
    ])
    sleep, slept = _recording_sleep()

    result = _run(fetch_with_retries(
        fetch, provider="doi.org", limiter=_limiter(), sleep=sleep,
    ))

    assert result.status == 200
    assert len(calls) == 3 and len(slept) == 2


def test_retryable_transport_failure_exhaustion_raises_network_error():
    fetch, calls = _scripted([
        TransportFailure("ConnectError", "refused", retryable=True)
        for _ in range(3)
    ])
    sleep, _slept = _recording_sleep()

    with pytest.raises(ProviderNetworkError) as exc:
        _run(fetch_with_retries(
            fetch, provider="doi.org", limiter=_limiter(), sleep=sleep,
        ))

    assert exc.value.exc_type == "ConnectError"
    assert len(calls) == 3


def test_non_retryable_transport_failure_fails_immediately():
    fetch, calls = _scripted([
        TransportFailure("TooManyRedirects", "redirect loop", retryable=False),
    ])
    sleep, slept = _recording_sleep()

    with pytest.raises(ProviderNetworkError) as exc:
        _run(fetch_with_retries(
            fetch, provider="doi.org", limiter=_limiter(), sleep=sleep,
        ))

    assert exc.value.retryable is False
    assert len(calls) == 1 and slept == []


def test_timeout_is_retried_once():
    fetch, calls = _scripted([
        asyncio.TimeoutError("deadline"),
        asyncio.TimeoutError("deadline"),
        FetchResponse(status=200),
    ])
    sleep, slept = _recording_sleep()

    with pytest.raises(ProviderTimeout):
        _run(fetch_with_retries(
            fetch, provider="openalex", limiter=_limiter(), sleep=sleep,
        ))

    assert len(calls) == 2 and len(slept) == 1


def test_rate_limit_and_transient_budgets_are_independent():
    fetch, calls = _scripted([
        FetchResponse(status=429, headers={"Retry-After": "0"}),
        FetchResponse(status=503),
        FetchResponse(status=429, headers={"Retry-After": "0"}),
        TransportFailure("ReadError", "reset", retryable=True),
        FetchResponse(status=200),
    ])
    sleep, _slept = _recording_sleep()

    result = _run(fetch_with_retries(
        fetch, provider="crossref", limiter=_limiter(), sleep=sleep,
    ))

    assert result.status == 200
    assert len(calls) == 5


def test_every_retry_reenters_the_rate_limiter():
    clock = FakeClock()
    limiter_sleeps: list[float] = []

    async def limiter_sleep(seconds: float) -> None:
        limiter_sleeps.append(seconds)
        clock.now += seconds

    limiter = AsyncRateLimiter(
        max_concurrency=1, min_interval=5.0, clock=clock, sleep=limiter_sleep,
    )
    fetch, calls = _scripted([
        FetchResponse(status=503),
        TransportFailure("ConnectError", "refused", retryable=True),
        FetchResponse(status=200),
    ])

    async def backoff_sleep(_seconds: float) -> None:
        return None  # backoff does not advance the fake clock

    _run(fetch_with_retries(
        fetch, provider="crossref", limiter=limiter, sleep=backoff_sleep,
    ))

    assert len(calls) == 3
    assert limiter_sleeps == [5.0, 5.0]  # second and third starts are spaced


def test_default_backoff_sleep_is_a_patchable_module_seam(monkeypatch):
    from skills.citation.providers import net

    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(net, "_retry_sleep", fake_sleep)
    fetch, _calls = _scripted([FetchResponse(status=503), FetchResponse(status=200)])

    _run(fetch_with_retries(fetch, provider="crossref", limiter=_limiter()))

    assert len(slept) == 1
