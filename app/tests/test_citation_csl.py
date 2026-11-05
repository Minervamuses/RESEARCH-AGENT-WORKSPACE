"""CSL-JSON sanitizing: whitelist, type mapping, names, and authority items."""

import asyncio
import json

from skills.citation.authority import AuthorityRecord
from skills.citation.csl import (
    CSL_TYPES,
    TYPE_MAP,
    csl_from_authority,
    minimal_csl,
    normalize_type,
    sanitize_csl,
)
from skills.citation.providers.doi_org import DoiOrgClient, parse_csl
from skills.citation.providers.net import AsyncRateLimiter, FetchResponse, TTLCache
from skills.citation.types import CanonicalIdentity

CROSSREF_LIKE = {
    "indexed": {"date-parts": [[2025, 1, 2]]},
    "reference-count": 2,
    "reference": [{"key": "r1", "unstructured": "Someone 1999"}],
    "publisher": "Elsevier BV",
    "license": [{"URL": "https://creativecommons.org/licenses/by/4.0/"}],
    "funder": [{"name": "NSF"}],
    "abstract": "<jats:p>Secret abstract that must never be stored.</jats:p>",
    "DOI": "10.1016/J.COMPAG.2024.108999",
    "type": "posted-content",
    "created": {"date-parts": [[2024, 5, 1]]},
    "title": "Deep <i>Arabidopsis</i> phenotyping with <scp>LiDAR</scp> &amp; RGB",
    "container-title": ["Computers and Electronics in Agriculture"],
    "author": [
        {
            "ORCID": "https://orcid.org/0000-0000-0000-0001",
            "authenticated-orcid": True,
            "given": "Ana",
            "family": "Silva",
            "sequence": "first",
            "affiliation": [{"name": "Somewhere"}],
        },
        {"name": "Plant Lab Consortium", "sequence": "additional"},
        {"given": "Ludwig", "family": "Beethoven", "non-dropping-particle": "van"},
    ],
    "issued": {"date-parts": [[2024, "6", 3]]},
    "volume": 221,
    "page": "108999",
    "ISSN": ["0168-1699"],
    "link": [{"URL": "https://api.elsevier.com/x"}],
    "assertion": [{"name": "received"}],
    "URL": "https://doi.org/10.1016/j.compag.2024.108999",
    "event": {"name": "AgEng 2024"},
}


def test_sanitize_keeps_only_whitelisted_csl_fields():
    item = sanitize_csl(CROSSREF_LIKE)

    assert "abstract" not in item
    assert not {"reference", "license", "funder", "link", "assertion", "indexed",
                "created", "reference-count", "id"} & set(item)
    assert item["type"] == "article"  # posted-content mapped
    assert item["title"] == "Deep <i>Arabidopsis</i> phenotyping with LiDAR & RGB"
    assert item["container-title"] == "Computers and Electronics in Agriculture"
    assert item["author"] == [
        {"family": "Silva", "given": "Ana"},
        {"literal": "Plant Lab Consortium"},
        {"family": "Beethoven", "given": "Ludwig", "non-dropping-particle": "van"},
    ]
    assert item["issued"] == {"date-parts": [[2024, 6, 3]]}
    assert item["volume"] == "221"
    assert item["ISSN"] == "0168-1699"
    assert item["DOI"] == "10.1016/j.compag.2024.108999"
    assert item["event-title"] == "AgEng 2024"
    assert "Secret" not in json.dumps(item)
    assert "orcid" not in json.dumps(item).casefold()


def test_type_map_is_fixed_and_targets_csl_types():
    assert set(TYPE_MAP.values()) <= CSL_TYPES
    assert normalize_type("journal-article") == "article-journal"
    assert normalize_type("proceedings-article") == "paper-conference"
    assert normalize_type("posted-content") == "article"
    assert normalize_type("book-chapter") == "chapter"
    assert normalize_type("article-journal") == "article-journal"
    assert normalize_type("something-new") == "document"
    assert normalize_type(None) == "document"


def test_parse_csl_carries_sanitized_item_with_canonical_doi():
    record = parse_csl("10.1016/j.compag.2024.108999", CROSSREF_LIKE)
    assert record.csl["DOI"] == "10.1016/j.compag.2024.108999"
    assert "abstract" not in record.csl
    assert "id" not in record.csl


def test_fetch_structured_caches_the_sanitized_item():
    calls = []

    async def fetcher(url, headers):
        calls.append(url)
        return FetchResponse(status=200, body=json.dumps(CROSSREF_LIKE).encode())

    client = DoiOrgClient(
        fetcher=fetcher, cache=TTLCache(), limiter=AsyncRateLimiter(max_concurrency=1)
    )
    first = asyncio.run(client.fetch_structured("10.1016/j.compag.2024.108999"))
    second = asyncio.run(client.fetch_structured("10.1016/J.COMPAG.2024.108999"))
    assert len(calls) == 1
    assert second.csl == first.csl
    assert first.csl["type"] == "article"


def test_arxiv_authority_record_builds_csl():
    record = AuthorityRecord(
        CanonicalIdentity("arxiv", "2401.01234"),
        "A preprint about crops",
        ("Ana Maria Silva", "Bo Li"),
        2024,
        "arXiv",
        "preprint",
        "https://arxiv.org/abs/2401.01234",
        "arxiv",
    )
    item = csl_from_authority(record)
    assert item == {
        "type": "article",
        "title": "A preprint about crops",
        "author": [
            {"family": "Silva", "given": "Ana Maria"},
            {"family": "Li", "given": "Bo"},
        ],
        "issued": {"date-parts": [[2024]]},
        "URL": "https://arxiv.org/abs/2401.01234",
        "number": "arXiv:2401.01234",
    }


def test_minimal_csl_uses_only_given_fields():
    item = minimal_csl(
        title="T", authors=["Solo"], year=2020, venue="V",
        work_type="journal-article", doi="10.1/x", url=None,
    )
    assert item == {
        "type": "article-journal",
        "title": "T",
        "author": [{"literal": "Solo"}],
        "issued": {"date-parts": [[2020]]},
        "container-title": "V",
        "DOI": "10.1/x",
    }


def test_exact_doi_resolution_carries_csl_to_the_eligible_record():
    from skills.citation.resolution import WorkIdentifier, WorkIntent, WorkResolver

    class StubDoiOrg:
        async def fetch_structured(self, doi):
            return parse_csl(doi, CROSSREF_LIKE)

    resolver = WorkResolver(crossref=None, datacite=None, openalex=None, doi_org=StubDoiOrg())
    intent = WorkIntent(
        "Silva 2024",
        identifiers=(WorkIdentifier("doi", "10.1016/j.compag.2024.108999"),),
    )
    resolution = asyncio.run(resolver.resolve(intent))
    assert resolution.decision.status == "eligible"
    assert resolution.decision.record.csl["DOI"] == "10.1016/j.compag.2024.108999"
    assert "abstract" not in resolution.decision.record.csl
