"""Integration contract: one WorkIntent becomes three provider-native queries."""

import asyncio
import json
import urllib.parse

from skills.citation.hub import CitationProviderHub
from skills.citation.providers.net import FetchResponse
from skills.citation.resolution import WorkIntent
from skills.citation.service import CitationService


DOI = "10.1234/paper-a"


class ProviderRoutingFetcher:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, url, headers):
        self.calls.append((url, headers.get("Accept", "")))
        if url.startswith("https://api.crossref.org/works?"):
            body = {
                "message": {
                    "items": [{
                        "DOI": DOI,
                        "title": ["Paper A"],
                        "author": [{"given": "Ada", "family": "Lovelace"}],
                        "issued": {"date-parts": [[2021]]},
                        "container-title": ["Journal A"],
                        "type": "journal-article",
                    }]
                }
            }
            return FetchResponse(200, body=json.dumps(body).encode())
        if url.startswith("https://api.datacite.org/dois?"):
            body = {
                "data": [{
                    "id": DOI,
                    "type": "dois",
                    "attributes": {
                        "doi": DOI,
                        "titles": [{"title": "Paper A"}],
                        "creators": [{
                            "name": "Lovelace, Ada",
                            "givenName": "Ada",
                            "familyName": "Lovelace",
                        }],
                        "publicationYear": 2021,
                        "publisher": {"name": "Journal A"},
                        "container": {"title": "Journal A"},
                        "types": {"resourceTypeGeneral": "JournalArticle"},
                        "url": f"https://doi.org/{DOI}",
                        "state": "findable",
                    },
                }]
            }
            return FetchResponse(200, body=json.dumps(body).encode())
        if url.startswith("https://api.openalex.org/works?"):
            body = {
                "results": [{
                    "id": "https://openalex.org/W1234567890",
                    "doi": f"https://doi.org/{DOI}",
                    "display_name": "Paper A",
                    "publication_year": 2021,
                    "type": "article",
                    "authorships": [{
                        "author": {"display_name": "Ada Lovelace"}
                    }],
                    "primary_location": {
                        "landing_page_url": f"https://doi.org/{DOI}",
                        "source": {"display_name": "Journal A"},
                        "version": "publishedVersion",
                        "is_accepted": True,
                        "is_published": True,
                    },
                    "locations": [{
                        "landing_page_url": f"https://doi.org/{DOI}",
                        "source": {"display_name": "Journal A"},
                        "version": "publishedVersion",
                        "is_accepted": True,
                        "is_published": True,
                    }],
                    "ids": {
                        "openalex": "https://openalex.org/W1234567890",
                        "doi": f"https://doi.org/{DOI}",
                    },
                }]
            }
            return FetchResponse(200, body=json.dumps(body).encode())
        if url == f"https://doi.org/{DOI}":
            if "csl+json" in headers.get("Accept", ""):
                body = {
                    "DOI": DOI,
                    "title": "Paper A",
                    "author": [{"given": "Ada", "family": "Lovelace"}],
                    "issued": {"date-parts": [[2021]]},
                    "container-title": "Journal A",
                    "type": "journal-article",
                }
                return FetchResponse(200, body=json.dumps(body).encode())
            if "x-bibtex" in headers.get("Accept", ""):
                return FetchResponse(
                    200,
                    body=(
                        "@article{paper_a, title={Paper A}, "
                        "author={Lovelace, Ada}, year={2021}, "
                        f"doi={{{DOI}}}}}\n"
                    ).encode(),
                )
        raise AssertionError(f"unexpected request: {url}")


def _query_params(url: str) -> dict[str, list[str]]:
    return urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)


def test_save_routes_structured_identity_through_three_distinct_query_plans(
    tmp_path,
):
    fetcher = ProviderRoutingFetcher()
    hub = CitationProviderHub(
        env={
            "CROSSREF_MAILTO": "tests@example.org",
            "DATACITE_MAILTO": "tests@example.org",
            "OPENALEX_API_KEY": "openalex-test-key",
        },
        fetcher=fetcher,
    )
    service = CitationService(hub, output_dir=tmp_path / "cite")
    intent = WorkIntent(
        "Paper A",
        title="Paper A",
        authors=("Ada Lovelace",),
        year=2021,
        venue="Journal A",
        work_type="journal article",
    )

    outcome = asyncio.run(service.save((intent,)))

    assert outcome.items[0].status == "saved"
    assert outcome.items[0].receipt.canonical_identity.value == DOI
    provider_urls = {
        host: [url for url, _accept in fetcher.calls if host in url]
        for host in (
            "api.crossref.org",
            "api.datacite.org",
            "api.openalex.org",
        )
    }
    assert all(len(urls) == 1 for urls in provider_urls.values())

    crossref = _query_params(provider_urls["api.crossref.org"][0])
    assert crossref["query.title"] == ["Paper A"]
    assert crossref["query.author"] == ["Lovelace"]
    assert "query.bibliographic" not in crossref

    datacite = _query_params(provider_urls["api.datacite.org"][0])
    assert 'titles.title:"Paper A"' in datacite["query"][0]
    assert 'creators.familyName:"Lovelace"' in datacite["query"][0]
    assert "publicationYear:2021" in datacite["query"][0]

    openalex = _query_params(provider_urls["api.openalex.org"][0])
    assert openalex["search.exact"] == ['"Paper A"']
    assert 'raw_author_name.search:"Ada Lovelace"' in openalex["filter"][0]
    assert "from_publication_date:2020-01-01" in openalex["filter"][0]

    provider_query_values = {
        crossref["query.title"][0],
        datacite["query"][0],
        openalex["search.exact"][0],
    }
    assert len(provider_query_values) == 3
