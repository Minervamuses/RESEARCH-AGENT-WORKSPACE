"""DataCite client contracts against local fixtures (no network)."""

import asyncio
import json
from pathlib import Path
import urllib.parse

import pytest

from skills.citation.providers.base import BibliographicQuery, RelationEdge
from skills.citation.providers.datacite import (
    MAX_RESPONSE_BYTES,
    DataCiteClient,
    build_work_query_plan,
    parse_doi_item,
)
from skills.citation.providers.net import (
    AsyncRateLimiter,
    FetchResponse,
    ProviderError,
    ProviderHTTPError,
    TTLCache,
)
from skills.citation.types import PublishedDateFilter


def _fixture() -> dict:
    path = Path(__file__).parent / "fixtures/datacite_arxiv.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _body(items: list[dict] | None = None) -> FetchResponse:
    payload = {"data": _fixture()["data"] if items is None else items}
    return FetchResponse(status=200, body=json.dumps(payload).encode())


def _doi_item(
    doi: str,
    title: str,
    *,
    authors: tuple[str, ...] = (),
    year: int | None = None,
) -> dict:
    attributes = {
        "doi": doi,
        "titles": [{"title": title}],
        "creators": [{"name": author} for author in authors],
        "publisher": {"name": "Fixture Repository"},
        "types": {"resourceTypeGeneral": "Text"},
    }
    if year is not None:
        attributes["publicationYear"] = year
    return {"id": doi, "type": "dois", "attributes": attributes}


def _client(responses, *, cache=None, mailto="dev@example.org"):
    calls = []

    async def fetcher(url, headers):
        item = responses[min(len(calls), len(responses) - 1)]
        calls.append((url, headers))
        if isinstance(item, Exception):
            raise item
        return item

    client = DataCiteClient(
        fetcher=fetcher,
        cache=cache if cache is not None else TTLCache(),
        limiter=AsyncRateLimiter(max_concurrency=1),
        mailto=mailto,
    )
    return client, calls


def _params(url: str) -> dict[str, list[str]]:
    return urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)


def test_parser_normalizes_current_datacite_47_shape_and_relation_edges():
    record = parse_doi_item(_fixture()["data"][0], rank=0)

    assert record is not None
    assert record.provider_id == "datacite:10.48550/arxiv.1706.03762"
    assert record.doi == "10.48550/arxiv.1706.03762"
    assert record.title == "Attention Is All You Need"
    assert record.authors == ["Vaswani, Ashish"]
    assert record.year == 2017
    assert record.publisher == "arXiv"
    assert record.work_type == "Preprint"
    assert record.resource_type == "Article"
    assert record.version_kind == "preprint"
    assert record.identifiers["arxiv"] == "1706.03762"
    assert record.relations == {
        "IsVersionOf": ["10.5555/3295222.3295349"]
    }
    assert record.relation_edges == (
        RelationEdge(
            relation_type="IsVersionOf",
            identifier="10.5555/3295222.3295349",
            identifier_type="DOI",
            resource_type="JournalArticle",
            detail="version of record",
        ),
    )
    assert record.version == "1"
    assert record.record_state == "findable"


def test_parser_accepts_legacy_publisher_and_alternate_identifier_shape():
    record = parse_doi_item(_fixture()["data"][1], rank=1)

    assert record is not None
    assert record.publisher == "arXiv"
    assert record.identifiers["arxiv"] == "1312.6114"
    assert record.version_kind == "preprint"


def test_parser_never_uses_created_or_registered_as_publication_year():
    item = _doi_item("10.1000/dataset", "A Dataset")
    attributes = item["attributes"]
    attributes.update(
        {
            "created": "2025-12-31T23:59:59Z",
            "registered": "2026-01-01T00:00:00Z",
            "types": {"resourceTypeGeneral": "Dataset"},
            "identifiers": [
                {"identifierType": "DOI", "identifier": "10.1000/alias"},
            ],
            "alternateIdentifiers": [
                {
                    "alternateIdentifierType": "Handle",
                    "alternateIdentifier": "12345/example",
                }
            ],
        }
    )

    record = parse_doi_item(item, rank=0)

    assert record is not None
    assert record.year is None
    assert record.version_kind == "unknown"
    assert record.aliases == ("10.1000/alias",)
    assert record.identifiers["handle"] == "12345/example"

    attributes["published"] = "2020-06-30"
    assert parse_doi_item(item, rank=0).year == 2020


def test_build_work_query_plan_uses_datacite_native_fielded_passes():
    query = BibliographicQuery(
        title="Attention Is All You Need",
        authors=("Vaswani, Ashish", "Noam Shazeer"),
        year=2017,
        venue="NeurIPS",
    )

    strict, widened, no_year = build_work_query_plan(query, rows=500)
    base = (
        'titles.title:"Attention Is All You Need" AND '
        '(creators.familyName:"Vaswani" OR '
        'creators.name:"Vaswani, Ashish")'
    )

    assert [strict.name, widened.name, no_year.name] == [
        "strict",
        "year_widened",
        "no_year",
    ]
    assert strict.as_params()["query"] == (
        f"{base} AND publicationYear:2017"
    )
    assert widened.as_params()["query"] == (
        f"{base} AND publicationYear:(2016 OR 2017 OR 2018)"
    )
    assert no_year.as_params()["query"] == base
    for query_pass in (strict, widened, no_year):
        params = query_pass.as_params()
        assert params["sort"] == "relevance"
        assert params["page[size]"] == "20"
        assert params["disable-facets"] == "true"
        assert "doi" in params["fields[dois]"].split(",")
        assert "NeurIPS" not in params["query"]


def test_query_plan_escapes_open_search_phrases_without_empty_clauses():
    title = 'A "quoted" \\ path: (x) AND y?*'
    author = 'Ada "A" Lovelace'
    query = BibliographicQuery(title=title, authors=(author,), year=1843)

    strict = build_work_query_plan(query)[0].as_params()["query"]

    escaped_title = 'A \\"quoted\\" \\\\ path\\: \\(x\\) AND y\\?\\*'
    escaped_author = 'Ada \\"A\\" Lovelace'
    assert f'titles.title:"{escaped_title}"' in strict
    assert 'creators.familyName:"Lovelace"' in strict
    assert f'creators.name:"{escaped_author}"' in strict

    title_only = build_work_query_plan(
        BibliographicQuery(title="Only a Title", year=2020)
    )
    assert "creators." not in title_only[0].as_params()["query"]
    author_only = build_work_query_plan(
        BibliographicQuery(title="", authors=("Ada Lovelace",))
    )
    assert len(author_only) == 1
    assert "titles.title:" not in author_only[0].as_params()["query"]
    assert build_work_query_plan(BibliographicQuery(title="")) == ()


def test_search_work_stops_after_plausible_strict_hit_and_caches():
    client, calls = _client([_body([_fixture()["data"][0]])])
    query = BibliographicQuery(
        title="Attention Is All You Need",
        authors=("Ashish Vaswani",),
        year=2017,
    )

    first = asyncio.run(client.search_work(query))
    second = asyncio.run(client.search_work(query))

    assert [record.doi for record in first] == [
        "10.48550/arxiv.1706.03762"
    ]
    assert [record.doi for record in second] == [record.doi for record in first]
    assert len(calls) == 1
    params = _params(calls[0][0])
    assert params["sort"] == ["relevance"]
    assert params["disable-facets"] == ["true"]
    assert "fields[dois]" in params
    assert params["query"][0].endswith("publicationYear:2017")


def test_search_work_falls_back_conditionally_merges_and_deduplicates_dois():
    miss = _doi_item(
        "10.1000/DUPLICATE",
        "A Completely Unrelated Work",
        authors=("Ada Lovelace",),
        year=1843,
    )
    hit = _doi_item(
        "10.5555/3295222.3295349",
        "Attention Is All You Need",
        authors=("Vaswani, Ashish",),
        year=2018,
    )
    duplicate = _doi_item(
        "10.1000/duplicate",
        "A Completely Unrelated Work",
        authors=("Ada Lovelace",),
        year=1843,
    )
    client, calls = _client([_body([miss]), _body([duplicate, hit])])
    query = BibliographicQuery(
        title="Attention Is All You Need",
        authors=("Ashish Vaswani",),
        year=2017,
    )

    records = asyncio.run(client.search_work(query))

    assert len(calls) == 2
    assert [record.doi for record in records] == [
        "10.1000/duplicate",
        "10.5555/3295222.3295349",
    ]
    assert [record.rank for record in records] == [0, 1]
    assert "publicationYear:2017" in _params(calls[0][0])["query"][0]
    assert "publicationYear:(2016 OR 2017 OR 2018)" in (
        _params(calls[1][0])["query"][0]
    )


def test_search_work_uses_at_most_three_requests_when_every_pass_misses():
    client, calls = _client([_body([]), _body([]), _body([])])
    query = BibliographicQuery(
        title="No Such Work",
        authors=("Missing Author",),
        year=2020,
    )

    assert asyncio.run(client.search_work(query)) == []

    assert len(calls) == 3
    queries = [_params(url)["query"][0] for url, _ in calls]
    assert "publicationYear:2020" in queries[0]
    assert "publicationYear:(2019 OR 2020 OR 2021)" in queries[1]
    assert "publicationYear" not in queries[2]


def test_search_text_encodes_once_caps_rows_and_wrapper_uses_same_cache():
    client, calls = _client([_body()])
    query = 'attention & "transformers" \\ notes'

    first = asyncio.run(client.search_text(query, rows=100))
    second = asyncio.run(client.search(query, rows=100))

    assert len(first) == len(second) == 2
    assert len(calls) == 1
    url, headers = calls[0]
    params = _params(url)
    assert params["query"] == [query]
    assert params["page[size]"] == ["20"]
    assert params["sort"] == ["relevance"]
    assert params["disable-facets"] == ["true"]
    assert "fields[dois]" in params
    assert "%2526" not in url
    assert "mailto:dev@example.org" in headers["User-Agent"]


def test_search_text_date_filter_uses_publication_year_and_cache_key():
    cache = TTLCache()
    client, calls = _client([_body([]), _body([])], cache=cache)
    date_filter = PublishedDateFilter.from_year_range(2021, 2026)

    asyncio.run(client.search_text("q", date_filter=date_filter))
    asyncio.run(client.search_text("q"))
    asyncio.run(client.search_text("q", date_filter=date_filter))

    assert len(calls) == 2
    assert _params(calls[0][0])["query"] == [
        "(q) AND publicationYear:[2021 TO 2026]"
    ]
    assert _params(calls[1][0])["query"] == ["q"]


@pytest.mark.parametrize(
    ("headers", "oversized"),
    [
        ({"content-length": str(MAX_RESPONSE_BYTES + 1)}, False),
        ({"content-length": "1"}, True),
        ({}, True),
    ],
)
def test_oversized_response_is_rejected_and_not_cached(headers, oversized):
    calls = 0

    async def fetcher(url, request_headers):
        nonlocal calls
        calls += 1
        body = b"x" * (MAX_RESPONSE_BYTES + 1) if oversized else b"{}"
        return FetchResponse(200, headers, body)

    cache = TTLCache()
    client = DataCiteClient(
        fetcher=fetcher,
        cache=cache,
        limiter=AsyncRateLimiter(max_concurrency=1),
    )

    with pytest.raises(ProviderError, match="exceeds"):
        asyncio.run(client.search_text("x"))

    assert len(cache) == 0
    assert calls == 1


@pytest.mark.parametrize(
    "body",
    [b"not json", b'{"data": {"not": "a list"}}'],
)
def test_invalid_payload_is_an_error_and_is_not_cached(body):
    cache = TTLCache()
    client, _ = _client([FetchResponse(200, {}, body)], cache=cache)

    with pytest.raises(ProviderError, match="unparseable"):
        asyncio.run(client.search_text("x"))

    assert len(cache) == 0


def test_empty_result_is_success_distinct_from_invalid_payload():
    client, calls = _client([_body([])])

    assert asyncio.run(client.search_text("no hits")) == []
    assert asyncio.run(client.search_text("no hits")) == []
    assert len(calls) == 1


def test_search_work_errors_are_not_cached_but_success_is_cached():
    query = BibliographicQuery(title="Attention Is All You Need")
    cache = TTLCache()
    client, calls = _client(
        [FetchResponse(status=500), _body([_fixture()["data"][0]])],
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
