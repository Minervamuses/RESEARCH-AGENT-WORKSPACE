"""Crossref client contracts against local fixtures (no network)."""

import asyncio
import json

import pytest

from skills.citation.providers.crossref import CrossrefClient, parse_work_item
from skills.citation.providers.net import (
    AsyncRateLimiter,
    FetchResponse,
    ProviderError,
    ProviderHTTPError,
    TTLCache,
)

FIXTURE_ITEMS = [
    {
        "DOI": "10.48550/ARXIV.1706.03762",
        "title": ["Attention Is All You Need"],
        "author": [
            {"given": "Ashish", "family": "Vaswani"},
            {"name": "Google Brain Team"},
        ],
        "issued": {"date-parts": [[2017, 6]]},
        "container-title": ["arXiv"],
        "type": "posted-content",
        "score": 55.2,
        "URL": "https://doi.org/10.48550/arXiv.1706.03762",
    },
    {   # no DOI -> dropped
        "title": ["Some webpage"],
        "score": 3.0,
    },
    {
        "DOI": "10.5555/3295222.3295349",
        "title": ["Attention is all you need"],
        "issued": {"date-parts": [[2017]]},
        "score": 41.0,
    },
]


def _client(responses, cache=None):
    calls = []

    async def fetcher(url, headers):
        calls.append((url, headers))
        item = responses[min(len(calls) - 1, len(responses) - 1)]
        if isinstance(item, Exception):
            raise item
        return item

    client = CrossrefClient(
        fetcher=fetcher,
        cache=cache if cache is not None else TTLCache(),
        limiter=AsyncRateLimiter(max_concurrency=1),
        mailto="dev@example.org",
    )
    return client, calls


def _search_body(items):
    return FetchResponse(
        status=200,
        body=json.dumps({"message": {"items": items}}).encode(),
    )


def test_search_normalizes_records_and_drops_doi_less_items():
    client, calls = _client([_search_body(FIXTURE_ITEMS)])
    records = asyncio.run(client.search("attention is all you need"))

    assert [r.provider_id for r in records] == [
        "crossref:10.48550/arxiv.1706.03762",
        "crossref:10.5555/3295222.3295349",
    ]
    first = records[0]
    assert first.doi == "10.48550/arxiv.1706.03762"  # canonical ASCII-folded
    assert first.rank == 0 and records[1].rank == 1
    assert first.authors == ["Ashish Vaswani", "Google Brain Team"]
    assert first.year == 2017
    assert first.venue == "arXiv"
    assert first.raw_score == pytest.approx(55.2)
    # polite-pool mailto goes out in the UA header
    url, headers = calls[0]
    assert "query.bibliographic=attention" in url
    assert "mailto:dev@example.org" in headers["User-Agent"]


def test_search_caps_rows_at_20():
    client, calls = _client([_search_body([])])
    asyncio.run(client.search("q", rows=500))
    assert "rows=20" in calls[0][0]


def test_search_results_are_cached_but_errors_are_not():
    cache = TTLCache()
    client, calls = _client(
        [FetchResponse(status=500), _search_body(FIXTURE_ITEMS[:1])],
        cache=cache,
    )
    with pytest.raises(ProviderHTTPError):
        asyncio.run(client.search("q"))
    assert len(cache) == 0  # error not cached

    records = asyncio.run(client.search("q"))
    assert len(records) == 1
    again = asyncio.run(client.search("q"))
    assert [r.provider_id for r in again] == [r.provider_id for r in records]
    assert len(calls) == 2  # second success served from cache


def test_empty_result_is_a_success_distinct_from_failure():
    client, _ = _client([_search_body([])])
    assert asyncio.run(client.search("no hits")) == []


def test_unparseable_body_raises_provider_error():
    client, _ = _client([FetchResponse(status=200, body=b"<html>oops</html>")])
    with pytest.raises(ProviderError):
        asyncio.run(client.search("q"))


def test_parse_work_item_tolerates_format_drift():
    # Provider drift: issued missing, title as empty list, score as string.
    record = parse_work_item(
        {"DOI": "10.1234/x", "title": [], "score": "not-a-number"}, rank=0
    )
    assert record.title == ""
    assert record.year is None
    assert record.raw_score is None


def test_search_date_filter_adds_native_filter_and_cache_key():
    import asyncio as _asyncio

    from skills.citation.types import PublishedDateFilter

    cache = TTLCache()
    client, calls = _client(
        [_search_body([]), _search_body([])], cache=cache
    )
    filt = PublishedDateFilter.from_year_range(2021, 2026)
    _asyncio.run(client.search("q", date_filter=filt))
    assert "filter=from-pub-date%3A2021-01-01%2Cuntil-pub-date%3A2026-12-31" in calls[0][0]
    # A different window is a different cache entry.
    _asyncio.run(client.search("q"))
    assert len(calls) == 2 and "filter=" not in calls[1][0]
    _asyncio.run(client.search("q", date_filter=filt))
    assert len(calls) == 2  # filtered result served from cache
