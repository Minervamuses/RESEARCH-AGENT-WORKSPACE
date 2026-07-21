"""OpenAlex query planning, location expansion, caching, and secret safety."""

import asyncio
import json
import urllib.parse

import pytest

from skills.citation.providers.base import BibliographicQuery
from skills.citation.providers.net import (
    AsyncRateLimiter,
    FetchResponse,
    ProviderError,
    ProviderHTTPError,
    TTLCache,
)
from skills.citation.providers.openalex import (
    OpenAlexClient,
    build_work_query_plan,
    parse_work,
)
from skills.citation.types import PublishedDateFilter

KEY = "sk-openalex-secret"

# Synthetic on purpose: never pair a real OpenAlex ID with invented metadata.
NORMAL_WORK = {
    "id": "https://openalex.org/W1234567890",
    "doi": "https://doi.org/10.1234/example",
    "display_name": "A Structured Work",
    "publication_year": 2020,
    "type": "article",
    "relevance_score": 987.6,
    "authorships": [
        {"author": {"display_name": "Ada Author"}, "raw_author_name": "A. Author"},
        {"author": {"display_name": "Bert Writer"}},
    ],
    "primary_location": {
        "id": "doi:10.1234/example",
        "landing_page_url": "https://doi.org/10.1234/example",
        "source": {"display_name": "Journal A"},
        "version": "publishedVersion",
        "is_accepted": True,
        "is_published": True,
    },
    "locations": [
        {
            "id": "doi:10.1234/example",
            "landing_page_url": "https://doi.org/10.1234/example",
            "source": {"display_name": "Journal A"},
            "version": "publishedVersion",
            "is_accepted": True,
            "is_published": True,
        }
    ],
    "ids": {
        "openalex": "https://openalex.org/W1234567890",
        "doi": "https://doi.org/10.1234/example",
    },
}

# Compact regression shaped after the OpenAlex W2626778328 response observed
# on 2026-07-21: top-level year/DOI can represent a later manifestation while
# the requested arXiv DOI survives only in ``locations``.
MIXED_LOCATION_WORK = {
    "id": "https://openalex.org/W2626778328",
    "doi": "https://doi.org/10.65215/2q58a426",
    "display_name": "Attention Is All You Need",
    "publication_year": 2025,
    "type": "preprint",
    "relevance_score": 4511.514,
    "authorships": [
        {"author": {"display_name": "Ashish Vaswani"}},
        {"author": {"display_name": "Noam Shazeer"}},
    ],
    "primary_location": {
        "id": "doi:10.65215/2q58a426",
        "landing_page_url": "https://doi.org/10.65215/2q58a426",
        "source": None,
        "version": "acceptedVersion",
        "is_accepted": True,
        "is_published": False,
        "raw_type": "posted-content",
    },
    "locations": [
        {
            "id": "doi:10.65215/2q58a426",
            "landing_page_url": "https://doi.org/10.65215/2q58a426",
            "source": None,
            "version": "acceptedVersion",
            "is_accepted": True,
            "is_published": False,
        },
        {
            "id": "doi:10.65215/r5bs2d54",
            "landing_page_url": "https://doi.org/10.65215/r5bs2d54",
            "source": None,
            "version": "acceptedVersion",
            "is_accepted": True,
            "is_published": False,
        },
        {
            "id": "doi:10.48550/arxiv.1706.03762",
            "landing_page_url": "https://doi.org/10.48550/arxiv.1706.03762",
            "source": {
                "display_name": "arXiv (Cornell University)",
                "type": "repository",
            },
            "version": "submittedVersion",
            "is_accepted": False,
            "is_published": False,
        },
    ],
    "ids": {
        "openalex": "https://openalex.org/W2626778328",
        "doi": "https://doi.org/10.65215/2q58a426",
    },
}

DOILESS_WORK = {
    "id": "https://openalex.org/W9999999999",
    "display_name": "Unregistered preprint",
    "publication_year": None,
    "type": "preprint",
    "authorships": [{"author": {"display_name": "No DOI"}}],
}


def _body(results):
    return FetchResponse(status=200, body=json.dumps({"results": results}).encode())


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


def _params(url):
    return urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)


def test_requires_api_key():
    with pytest.raises(ValueError):
        OpenAlexClient(
            fetcher=None,
            cache=TTLCache(),
            limiter=AsyncRateLimiter(),
            api_key="",
        )


def test_parser_normalizes_work_and_preserves_primary_location():
    record = parse_work(NORMAL_WORK, rank=0)
    assert record.provider_id == "openalex:W1234567890"
    assert record.doi == "10.1234/example"
    assert record.title == "A Structured Work"
    assert record.authors == ["Ada Author", "Bert Writer"]
    assert record.venue == "Journal A"
    assert record.raw_score == pytest.approx(987.6)
    assert record.version_kind == "published"
    assert len(record.manifestations) == 1
    assert record.manifestations[0].is_primary is True
    assert record.manifestations[0].is_published is True


def test_parser_tolerates_missing_everything():
    record = parse_work({}, rank=3)
    assert record.provider_id == "openalex:rank-3"
    assert record.doi is None
    assert record.title == ""
    assert record.authors == []
    assert record.manifestations == ()


def test_work_query_plan_uses_supported_fields_and_bounded_rows():
    query = BibliographicQuery(
        'Use "AND" in C:\\Research',
        authors=('Vaswani, "Ashish"',),
        year=2017,
    )
    plan = build_work_query_plan(query, rows=100)

    assert [item.name for item in plan] == [
        "exact_with_year",
        "exact_without_year",
        "stemmed_phrase",
    ]
    strict, relaxed, stemmed = [item.as_params() for item in plan]
    assert strict["search.exact"] == '"Use \\"AND\\" in C:\\\\Research"'
    assert 'raw_author_name.search:"Vaswani \\"Ashish\\""' in strict["filter"]
    assert "from_publication_date:2016-01-01" in strict["filter"]
    assert "to_publication_date:2018-12-31" in strict["filter"]
    assert "publication_date" not in relaxed.get("filter", "")
    assert "raw_author_name.search" in relaxed["filter"]
    assert stemmed["search"] == strict["search.exact"]
    assert "filter" not in stemmed
    for item in plan:
        params = item.as_params()
        assert params["per_page"] == "20"
        assert "locations" in params["select"]
        assert "title.search" not in params


def test_work_query_plan_without_year_skips_duplicate_date_relaxation():
    plan = build_work_query_plan(
        BibliographicQuery("A Structured Work", authors=("Ada Author",))
    )
    assert [item.name for item in plan] == [
        "exact_without_year",
        "stemmed_phrase",
    ]


def test_generic_search_uses_search_text_official_per_page_and_native_dates():
    client, calls = _client([_body([NORMAL_WORK])])
    date_filter = PublishedDateFilter.from_year_range(2020, 2021)
    records = asyncio.run(
        client.search("structured work", rows=100, date_filter=date_filter)
    )

    assert records[0].doi == "10.1234/example"
    assert len(calls) == 1
    params = _params(calls[0][0])
    assert params["search"] == ["structured work"]
    assert params["per_page"] == ["20"]
    assert "per-page" not in params
    assert params["filter"] == [
        "from_publication_date:2020-01-01,to_publication_date:2021-12-31"
    ]
    assert params["api_key"] == [KEY]
    assert all(KEY not in str(value) for value in calls[0][1].values())


def test_search_work_stops_after_first_plausible_pass_and_caches():
    cache = TTLCache()
    client, calls = _client([_body([NORMAL_WORK])], cache=cache)
    query = BibliographicQuery(
        "A Structured Work", authors=("Ada Author",), year=2020
    )

    first = asyncio.run(client.search_work(query, rows=100))
    second = asyncio.run(client.search_work(query, rows=100))

    assert len(first) == len(second) == 1
    assert first[0].doi == "10.1234/example"
    assert len(calls) == 1
    assert _params(calls[0][0])["per_page"] == ["20"]
    for key in cache._items:  # noqa: SLF001 - deliberate secret audit
        assert KEY not in repr(key)


def test_search_work_relaxes_date_conditionally_then_stops():
    unrelated_doi = "10.1234/different"
    unrelated = {
        **NORMAL_WORK,
        "id": "https://openalex.org/W1111111111",
        "doi": f"https://doi.org/{unrelated_doi}",
        "display_name": "A Different Paper",
        "primary_location": {
            **NORMAL_WORK["primary_location"],
            "id": f"doi:{unrelated_doi}",
            "landing_page_url": f"https://doi.org/{unrelated_doi}",
        },
        "locations": [
            {
                **NORMAL_WORK["locations"][0],
                "id": f"doi:{unrelated_doi}",
                "landing_page_url": f"https://doi.org/{unrelated_doi}",
            }
        ],
        "ids": {
            "openalex": "https://openalex.org/W1111111111",
            "doi": f"https://doi.org/{unrelated_doi}",
        },
    }
    client, calls = _client([_body([unrelated]), _body([NORMAL_WORK])])
    query = BibliographicQuery(
        "A Structured Work", authors=("Ada Author",), year=2020
    )

    records = asyncio.run(client.search_work(query))

    assert len(calls) == 2
    assert "from_publication_date" in _params(calls[0][0])["filter"][0]
    assert "from_publication_date" not in _params(calls[1][0])["filter"][0]
    assert {record.title for record in records} == {
        "A Different Paper",
        "A Structured Work",
    }


def test_search_work_never_exceeds_three_conditional_passes():
    unrelated = {**NORMAL_WORK, "display_name": "No Match"}
    client, calls = _client([_body([unrelated])])
    query = BibliographicQuery(
        "A Structured Work", authors=("Ada Author",), year=2020
    )

    records = asyncio.run(client.search_work(query))

    assert len(calls) == 3
    assert records and all(record.title == "No Match" for record in records)


def test_mixed_location_year_drift_expands_each_doi_without_swallowing():
    client, calls = _client(
        [_body([]), _body([MIXED_LOCATION_WORK]), _body([])]
    )
    query = BibliographicQuery(
        "Attention Is All You Need",
        authors=("Ashish Vaswani",),
        year=2017,
    )

    records = asyncio.run(client.search_work(query))

    assert len(calls) == 3  # relaxed result still has a top-level 2025 year
    assert {record.doi for record in records} == {
        "10.65215/2q58a426",
        "10.65215/r5bs2d54",
        "10.48550/arxiv.1706.03762",
    }
    by_doi = {record.doi: record for record in records}
    assert by_doi["10.65215/2q58a426"].version_kind == "repository"
    assert by_doi["10.48550/arxiv.1706.03762"].version_kind == "preprint"
    assert all(len(record.manifestations) == 3 for record in records)
    assert len({record.provider_id for record in records}) == 3


def test_doi_less_plausible_work_is_retained():
    client, calls = _client([_body([DOILESS_WORK])])
    query = BibliographicQuery(
        "Unregistered preprint", authors=("No DOI",)
    )

    records = asyncio.run(client.search_work(query))

    assert len(calls) == 1
    assert len(records) == 1
    assert records[0].doi is None
    assert records[0].provider_id == "openalex:W9999999999"


def test_http_and_unparseable_errors_redact_key_and_are_not_cached():
    cache = TTLCache()
    denied, _ = _client([FetchResponse(status=403)], cache=cache)
    with pytest.raises(ProviderHTTPError) as exc:
        asyncio.run(denied.search_text("q"))
    assert KEY not in str(exc.value) and KEY not in exc.value.detail
    assert len(cache) == 0

    invalid, _ = _client(
        [FetchResponse(status=200, body=f"boom {KEY} boom".encode())],
        cache=cache,
    )
    with pytest.raises(ProviderError) as exc:
        asyncio.run(invalid.search_text("q"))
    assert KEY not in str(exc.value)
    assert len(cache) == 0


def test_query_escaping_survives_url_encoding_without_changing_filter_shape():
    client, calls = _client([_body([])])
    query = BibliographicQuery(
        'Use "AND" in C:\\Research',
        authors=('Vaswani, "Ashish"',),
        year=2017,
    )

    asyncio.run(client.search_work(query))

    assert len(calls) == 3
    strict = _params(calls[0][0])
    assert strict["search.exact"] == ['"Use \\"AND\\" in C:\\\\Research"']
    assert strict["filter"][0].count(",") == 2
    assert 'raw_author_name.search:"Vaswani \\"Ashish\\""' in strict["filter"][0]
    assert KEY not in repr(
        [key for key in client._cache._items]  # noqa: SLF001 - secret audit
    )
