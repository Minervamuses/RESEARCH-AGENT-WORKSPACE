"""doi.org content-negotiation contracts: CSL, BibTeX, RA, caching, 404."""

import asyncio
import json

import pytest

from citation.providers.doi_org import (
    CSL_ACCEPT,
    BIBTEX_ACCEPT,
    DoiNotFound,
    DoiOrgClient,
    parse_csl,
)
from citation.providers.net import (
    AsyncRateLimiter,
    FetchResponse,
    ProviderError,
    ProviderHTTPError,
    TTLCache,
)

CSL_BODY = {
    "DOI": "10.1038/S41586-021-03819-2",
    "title": "Highly accurate protein structure prediction with AlphaFold",
    "author": [
        {"given": "John", "family": "Jumper"},
        {"literal": "DeepMind Team"},
    ],
    "issued": {"date-parts": [[2021, 7]]},
    "container-title": "Nature",
    "type": "journal-article",
    "URL": "https://doi.org/10.1038/s41586-021-03819-2",
}


def _client(script, cache=None):
    calls = []

    async def fetcher(url, headers):
        calls.append((url, headers))
        item = script[min(len(calls) - 1, len(script) - 1)]
        if isinstance(item, Exception):
            raise item
        return item

    client = DoiOrgClient(
        fetcher=fetcher,
        cache=cache if cache is not None else TTLCache(),
        limiter=AsyncRateLimiter(max_concurrency=1),
    )
    return client, calls


def test_fetch_structured_parses_csl_and_canonicalizes_doi():
    client, calls = _client([
        FetchResponse(status=200, body=json.dumps(CSL_BODY).encode())
    ])
    record = asyncio.run(client.fetch_structured("doi:10.1038/s41586-021-03819-2"))

    assert record.doi == "10.1038/s41586-021-03819-2"
    assert record.title.startswith("Highly accurate protein")
    assert record.authors == ["John Jumper", "DeepMind Team"]
    assert record.year == 2021
    assert record.venue == "Nature"
    assert record.work_type == "journal-article"
    url, headers = calls[0]
    assert url == "https://doi.org/10.1038/s41586-021-03819-2"
    assert headers["Accept"] == CSL_ACCEPT


def test_structured_lookup_is_cached_24h_by_canonical_doi():
    cache = TTLCache()
    client, calls = _client(
        [FetchResponse(status=200, body=json.dumps(CSL_BODY).encode())],
        cache=cache,
    )
    asyncio.run(client.fetch_structured("10.1038/s41586-021-03819-2"))
    # Different spellings of the same DOI hit the same cache entry.
    asyncio.run(client.fetch_structured("https://doi.org/10.1038/S41586-021-03819-2"))
    assert len(calls) == 1


def test_fetch_bibtex_returns_raw_text_with_bibtex_accept():
    client, calls = _client([
        FetchResponse(status=200, body=b"@article{x, title={T}, year={2021}}")
    ])
    text = asyncio.run(client.fetch_bibtex("10.1038/s41586-021-03819-2"))
    assert text.startswith("@article")
    assert calls[0][1]["Accept"] == BIBTEX_ACCEPT


def test_missing_doi_raises_doi_not_found():
    client, _ = _client([FetchResponse(status=404)])
    with pytest.raises(DoiNotFound):
        asyncio.run(client.fetch_structured("10.9999/does-not-exist"))


def test_other_http_errors_stay_http_errors_and_are_not_cached():
    cache = TTLCache()
    client, calls = _client(
        [
            FetchResponse(status=503),
            FetchResponse(status=200, body=json.dumps(CSL_BODY).encode()),
        ],
        cache=cache,
    )
    with pytest.raises(ProviderHTTPError):
        asyncio.run(client.fetch_structured("10.1038/s41586-021-03819-2"))
    assert len(cache) == 0
    record = asyncio.run(client.fetch_structured("10.1038/s41586-021-03819-2"))
    assert record.year == 2021
    assert len(calls) == 2


def test_non_doi_input_is_rejected_before_any_network_call():
    client, calls = _client([])
    with pytest.raises(ProviderError):
        asyncio.run(client.fetch_structured("not-a-doi"))
    assert calls == []


def test_registration_agency_lookup():
    client, calls = _client([
        FetchResponse(
            status=200,
            body=json.dumps([{"DOI": "10.1038/x", "RA": "Crossref"}]).encode(),
        )
    ])
    agency = asyncio.run(client.fetch_registration_agency("10.1038/x"))
    assert agency == "Crossref"
    assert calls[0][0] == "https://doi.org/ra/10.1038/x"


def test_registration_agency_tolerates_garbage():
    client, _ = _client([FetchResponse(status=200, body=b"[]")])
    assert asyncio.run(client.fetch_registration_agency("10.1038/x")) == ""


def test_parse_csl_missing_fields_are_empty_never_guessed():
    record = parse_csl("10.1234/x", {})
    assert record.doi == "10.1234/x"
    assert record.title == ""
    assert record.authors == []
    assert record.year is None
