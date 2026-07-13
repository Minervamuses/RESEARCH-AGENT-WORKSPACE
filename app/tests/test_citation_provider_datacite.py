import json
import asyncio
from pathlib import Path

import pytest

from skills.citation.providers.datacite import DataCiteClient, MAX_RESPONSE_BYTES, parse_doi_item
from skills.citation.providers.net import AsyncRateLimiter, FetchResponse, ProviderError, TTLCache


def fixture():
    return json.loads((Path(__file__).parent / "fixtures/datacite_arxiv.json").read_text())


def test_parser_normalizes_datacite_fields_and_relations():
    item = fixture()["data"][0]
    item["attributes"]["relatedIdentifiers"] = [{"relationType": "IsPreprintOf", "relatedIdentifier": "https://example.test/published"}]
    record = parse_doi_item(item, 0)
    assert record.doi == "10.48550/arxiv.1706.03762"
    assert record.title == "Attention Is All You Need"
    assert record.year == 2017
    assert record.version_kind == "preprint"
    assert record.relations == {"IsPreprintOf": ["https://example.test/published"]}
    assert record.identifiers["arxiv"] == "1706.03762"


def test_search_encodes_query_caps_rows_and_caches_success():
    calls = []
    body = json.dumps(fixture()).encode()
    async def fetch(url, headers):
        calls.append((url, headers))
        return FetchResponse(200, {}, body)
    client = DataCiteClient(fetcher=fetch, cache=TTLCache(), limiter=AsyncRateLimiter())
    first = asyncio.run(client.search("attention & transformers", rows=100))
    second = asyncio.run(client.search("attention & transformers", rows=100))
    assert len(first) == len(second) == 2
    assert len(calls) == 1
    assert "attention+%26+transformers" in calls[0][0]
    assert "page%5Bsize%5D=20" in calls[0][0]


@pytest.mark.parametrize("headers,oversized", [
    ({"content-length": str(MAX_RESPONSE_BYTES + 1)}, False),
    ({"content-length": "1"}, True),
    ({}, True),
])
def test_oversized_response_is_rejected_and_not_cached(headers, oversized):
    calls = 0
    async def fetch(url, request_headers):
        nonlocal calls
        calls += 1
        return FetchResponse(200, headers, b"x" * (MAX_RESPONSE_BYTES + 1) if oversized else b"{}")
    cache = TTLCache()
    client = DataCiteClient(fetcher=fetch, cache=cache, limiter=AsyncRateLimiter())
    with pytest.raises(ProviderError, match="exceeds"):
        asyncio.run(client.search("x"))
    assert len(cache) == 0
    assert calls == 1


def test_invalid_json_and_empty_are_distinct():
    async def invalid(url, headers):
        return FetchResponse(200, {}, b"not json")
    with pytest.raises(ProviderError, match="unparseable"):
        asyncio.run(DataCiteClient(fetcher=invalid, cache=TTLCache(), limiter=AsyncRateLimiter()).search("x"))
    async def empty(url, headers):
        return FetchResponse(200, {}, b'{"data": []}')
    assert asyncio.run(DataCiteClient(fetcher=empty, cache=TTLCache(), limiter=AsyncRateLimiter()).search("x")) == []
