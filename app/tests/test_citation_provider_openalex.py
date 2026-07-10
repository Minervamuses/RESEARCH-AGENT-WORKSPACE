"""OpenAlex client contracts: parsing, caching, and key redaction."""

import asyncio
import json

import pytest

from skills.citation.providers.net import (
    AsyncRateLimiter,
    FetchResponse,
    ProviderError,
    ProviderHTTPError,
    TTLCache,
)
from skills.citation.providers.openalex import OpenAlexClient, parse_work

FIXTURE_RESULTS = [
    {
        "id": "https://openalex.org/W2741809807",
        "doi": "https://doi.org/10.48550/arXiv.1706.03762",
        "display_name": "Attention Is All You Need",
        "publication_year": 2017,
        "type": "article",
        "relevance_score": 987.6,
        "authorships": [
            {"author": {"display_name": "Ashish Vaswani"}},
            {"author": {"display_name": "Noam Shazeer"}},
        ],
        "primary_location": {"source": {"display_name": "arXiv"}},
        "ids": {
            "openalex": "https://openalex.org/W2741809807",
            "doi": "https://doi.org/10.48550/arXiv.1706.03762",
        },
    },
    {   # DOI-less preprint stays, with doi=None
        "id": "https://openalex.org/W999",
        "display_name": "Unregistered preprint",
        "publication_year": None,
    },
]

KEY = "sk-openalex-secret"


def _client(responses, cache=None):
    calls = []

    async def fetcher(url, headers):
        calls.append((url, headers))
        item = responses[min(len(calls) - 1, len(responses) - 1)]
        if isinstance(item, Exception):
            raise item
        return item

    client = OpenAlexClient(
        fetcher=fetcher,
        cache=cache if cache is not None else TTLCache(),
        limiter=AsyncRateLimiter(max_concurrency=1),
        api_key=KEY,
    )
    return client, calls


def _body(results):
    return FetchResponse(status=200, body=json.dumps({"results": results}).encode())


def test_requires_api_key():
    with pytest.raises(ValueError):
        OpenAlexClient(
            fetcher=None, cache=TTLCache(),
            limiter=AsyncRateLimiter(), api_key="",
        )


def test_search_normalizes_records_and_keeps_doi_less_hits():
    client, calls = _client([_body(FIXTURE_RESULTS)])
    records = asyncio.run(client.search("attention"))

    assert records[0].provider_id == "openalex:W2741809807"
    assert records[0].doi == "10.48550/arxiv.1706.03762"
    assert records[0].authors == ["Ashish Vaswani", "Noam Shazeer"]
    assert records[0].venue == "arXiv"
    assert records[0].raw_score == pytest.approx(987.6)
    assert records[1].doi is None
    assert records[1].provider_id == "openalex:W999"
    # key travels as a query parameter only
    url, headers = calls[0]
    assert f"api_key={KEY}" in url
    assert all(KEY not in str(v) for v in headers.values())


def test_search_caps_rows_and_caches_success():
    cache = TTLCache()
    client, calls = _client([_body([])], cache=cache)
    asyncio.run(client.search("q", rows=100))
    assert "per-page=20" in calls[0][0]
    asyncio.run(client.search("q", rows=100))
    assert len(calls) == 1  # cache hit
    assert len(cache) == 1


def test_http_error_is_raised_with_key_redacted():
    client, _ = _client([FetchResponse(status=403)])
    with pytest.raises(ProviderHTTPError) as exc:
        asyncio.run(client.search("q"))
    assert KEY not in str(exc.value)
    assert KEY not in exc.value.detail


def test_unparseable_body_error_redacts_key():
    client, _ = _client([
        FetchResponse(status=200, body=f"boom {KEY} boom".encode())
    ])
    with pytest.raises(ProviderError) as exc:
        asyncio.run(client.search("q"))
    assert KEY not in str(exc.value)


def test_cache_key_never_embeds_the_secret():
    cache = TTLCache()
    client, _ = _client([_body([])], cache=cache)
    asyncio.run(client.search("q"))
    for key in cache._items:  # noqa: SLF001 - deliberate secret audit
        assert KEY not in repr(key)


def test_parse_work_tolerates_missing_everything():
    record = parse_work({}, rank=3)
    assert record.provider_id == "openalex:rank-3"
    assert record.doi is None
    assert record.title == ""
    assert record.authors == []
