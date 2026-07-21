"""Crossref client contracts against local fixtures (no network)."""

import asyncio
import json
import urllib.parse

import pytest

from skills.citation.providers.base import BibliographicQuery
from skills.citation.providers.crossref import (
    CrossrefClient,
    build_work_query_plan,
    parse_work_item,
)
from skills.citation.providers.net import (
    AsyncRateLimiter,
    FetchResponse,
    ProviderError,
    ProviderHTTPError,
    TTLCache,
)

FIXTURE_ITEMS = [
    {
        "DOI": "10.1038/S41586-021-03819-2",
        "title": ["Highly accurate protein structure prediction with AlphaFold"],
        "author": [
            {"given": "John", "family": "Jumper"},
            {"name": "AlphaFold Team"},
        ],
        "issued": {"date-parts": [[2021, 7]]},
        "container-title": ["Nature"],
        "type": "journal-article",
        "score": 55.2,
        "URL": "https://doi.org/10.1038/s41586-021-03819-2",
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
    records = asyncio.run(client.search_text("protein structure prediction"))

    assert [r.provider_id for r in records] == [
        "crossref:10.1038/s41586-021-03819-2",
        "crossref:10.5555/3295222.3295349",
    ]
    first = records[0]
    assert first.doi == "10.1038/s41586-021-03819-2"  # canonical ASCII-folded
    assert first.rank == 0 and records[1].rank == 1
    assert first.authors == ["John Jumper", "AlphaFold Team"]
    assert first.year == 2021
    assert first.venue == "Nature"
    assert first.version_kind == "published"
    assert first.raw_score == pytest.approx(55.2)
    # polite-pool mailto goes out in the UA header
    url, headers = calls[0]
    assert "query.bibliographic=protein+structure+prediction" in url
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


def test_search_wrapper_delegates_to_search_text_cache():
    client, calls = _client([_search_body(FIXTURE_ITEMS[:1])])
    expected = asyncio.run(client.search_text("protein structure"))
    actual = asyncio.run(client.search("protein structure"))

    assert [record.provider_id for record in actual] == [
        record.provider_id for record in expected
    ]
    assert len(calls) == 1


def test_build_work_query_plan_uses_crossref_native_clauses():
    query = BibliographicQuery(
        title="Attention Is All You Need",
        authors=("Vaswani, Ashish", "Noam Shazeer"),
        year=2017,
        venue="NeurIPS",
    )

    strict, fallback = build_work_query_plan(query, rows=500)

    assert strict.name == "strict"
    assert strict.as_params() == {
        "query.title": "Attention Is All You Need",
        "query.author": "Vaswani",
        "rows": "20",
        "filter": "from-pub-date:2016-01-01,until-pub-date:2018-12-31",
    }
    assert fallback.name == "fallback"
    assert fallback.as_params() == {
        "query.bibliographic": (
            "Attention Is All You Need Vaswani, Ashish 2017 NeurIPS"
        ),
        "rows": "20",
    }


def test_search_work_stops_after_plausible_strict_hit_and_requests_full_items():
    client, calls = _client([_search_body(FIXTURE_ITEMS[2:])])
    query = BibliographicQuery(
        title="Attention Is All You Need",
        authors=("Ashish Vaswani",),
        year=2017,
    )

    records = asyncio.run(client.search_work(query))

    assert [record.doi for record in records] == ["10.5555/3295222.3295349"]
    assert len(calls) == 1
    params = urllib.parse.parse_qs(urllib.parse.urlsplit(calls[0][0]).query)
    assert params["query.title"] == ["Attention Is All You Need"]
    assert params["query.author"] == ["Vaswani"]
    assert params["filter"] == [
        "from-pub-date:2016-01-01,until-pub-date:2018-12-31"
    ]
    assert "select" not in params


def test_search_work_falls_back_only_after_miss_and_deduplicates_dois():
    strict_miss = {
        "DOI": "10.1000/DUPLICATE",
        "title": ["A Completely Unrelated Work"],
        "author": [{"given": "Ada", "family": "Lovelace"}],
        "issued": {"date-parts": [[1843]]},
    }
    fallback_hit = {
        **FIXTURE_ITEMS[2],
        "author": [{"given": "Ashish", "family": "Vaswani"}],
    }
    client, calls = _client(
        [
            _search_body([strict_miss]),
            _search_body([{**strict_miss, "DOI": "10.1000/duplicate"}, fallback_hit]),
        ]
    )
    query = BibliographicQuery(
        title="Attention Is All You Need",
        authors=("Ashish Vaswani",),
        year=2017,
        venue="NeurIPS",
    )

    records = asyncio.run(client.search_work(query))

    assert len(calls) == 2
    assert [record.doi for record in records] == [
        "10.1000/duplicate",
        "10.5555/3295222.3295349",
    ]
    assert [record.rank for record in records] == [0, 1]
    fallback_params = urllib.parse.parse_qs(
        urllib.parse.urlsplit(calls[1][0]).query
    )
    assert "query.bibliographic" in fallback_params
    assert "filter" not in fallback_params
    assert "select" not in fallback_params


def test_search_work_success_is_cached_and_errors_are_not():
    query = BibliographicQuery(title="Attention Is All You Need")
    cache = TTLCache()
    client, calls = _client(
        [FetchResponse(status=500), _search_body(FIXTURE_ITEMS[2:])],
        cache=cache,
    )

    with pytest.raises(ProviderHTTPError):
        asyncio.run(client.search_work(query))
    assert len(cache) == 0

    records = asyncio.run(client.search_work(query))
    again = asyncio.run(client.search_work(query))
    assert [record.doi for record in again] == [record.doi for record in records]
    assert len(calls) == 2
    assert len(cache) == 1


def test_parse_work_item_preserves_aliases_relations_and_updates():
    record = parse_work_item(
        {
            "DOI": "10.1000/PUBLISHED",
            "title": ["Published Version"],
            "type": "journal-article",
            "aliases": [
                "10.1000/ALIAS",
                "https://doi.org/10.1000/alias",
                "10.1000/PUBLISHED",
                "not-a-doi",
            ],
            "relation": {
                "has-preprint": [
                    {
                        "id-type": "doi",
                        "id": "10.48550/ARXIV.1706.03762",
                        "asserted-by": "subject",
                    }
                ],
                "is-supplemented-by": [
                    {"id-type": "uri", "id": "https://example.org/supplement"}
                ],
            },
            "update-to": [
                {"DOI": "10.1000/UPDATED", "type": "correction"}
            ],
            "updated-by": [
                {
                    "DOI": "10.1000/CORRECTION",
                    "type": "correction",
                    "label": "publisher correction",
                }
            ],
        },
        rank=0,
    )

    assert record is not None
    assert record.aliases == ("10.1000/alias",)
    assert record.relations == {
        "has-preprint": ["10.48550/arxiv.1706.03762"],
        "is-supplemented-by": ["https://example.org/supplement"],
        "update-to": ["10.1000/updated"],
        "updated-by": ["10.1000/correction"],
    }
    assert {
        (edge.relation_type, edge.identifier, edge.resource_type, edge.detail)
        for edge in record.relation_edges
    } == {
        ("has-preprint", "10.48550/arxiv.1706.03762", "", "subject"),
        ("is-supplemented-by", "https://example.org/supplement", "", ""),
        ("update-to", "10.1000/updated", "correction", ""),
        (
            "updated-by",
            "10.1000/correction",
            "correction",
            "publisher correction",
        ),
    }
    assert record.version_kind == "published"


def test_parse_work_item_identifies_preprint_version():
    record = parse_work_item(
        {
            "DOI": "10.1000/PREPRINT",
            "title": ["Preprint Version"],
            "type": "posted-content",
            "relation": {
                "is-preprint-of": [
                    {"id-type": "doi", "id": "10.1000/PUBLISHED"}
                ]
            },
        },
        rank=0,
    )

    assert record is not None
    assert record.version_kind == "preprint"
    assert record.relations["is-preprint-of"] == ["10.1000/published"]
