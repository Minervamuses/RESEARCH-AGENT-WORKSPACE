import asyncio
from pathlib import Path

from skills.citation.authority import AuthorityRegistry, export_bibtex
from skills.citation.hub import CitationProviderHub
from skills.citation.providers.net import FetchResponse, ProviderError
from skills.citation.resolution import (
    ResolutionDecision,
    WorkIdentifier,
    WorkIntent,
    WorkResolution,
)
from skills.citation.service import CitationService


ATOM = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2001.00001v1</id><title>A Preprint</title><published>2020-01-02T00:00:00Z</published><author><name>Ada Author</name></author></entry></feed>'''
MISMATCHED_ATOM = ATOM.replace(b"2001.00001v1", b"2001.99999v1")


def test_official_arxiv_record_and_deterministic_bibtex():
    async def fetch(url, headers):
        assert url.startswith("https://export.arxiv.org/api/query?")
        return FetchResponse(200, body=ATOM)
    registry = AuthorityRegistry(fetcher=fetch)
    record = asyncio.run(registry.resolve(WorkIntent("x", identifiers=(WorkIdentifier("arxiv", "2001.00001"),))))
    assert record.identity.key == "arxiv:2001.00001"
    canonical = export_bibtex(record)
    assert canonical.title == "A Preprint" and canonical.doi is None


def test_arxiv_authority_rejects_a_mismatched_returned_identifier():
    async def fetch(_url, _headers):
        return FetchResponse(200, body=MISMATCHED_ATOM)

    registry = AuthorityRegistry(fetcher=fetch)
    record = asyncio.run(registry.resolve(WorkIntent(
        "x", identifiers=(WorkIdentifier("arxiv", "2001.00001"),),
    )))

    assert record is None


def test_neurips_adapter_is_exact_allowlisted_metadata():
    async def no_fetch(url, headers):
        raise AssertionError("network not expected")
    registry = AuthorityRegistry(fetcher=no_fetch)
    record = asyncio.run(registry.resolve(WorkIntent("x", title="Attention Is All You Need", year=2017, venue="NeurIPS")))
    assert record.identity.key == "venue:neurips:2017:7181"
    assert export_bibtex(record).entry_type == "inproceedings"


def test_untrusted_or_unknown_venue_abstains():
    async def no_fetch(url, headers):
        raise AssertionError
    registry = AuthorityRegistry(fetcher=no_fetch)
    assert asyncio.run(registry.resolve(WorkIntent("x", title="Unknown", year=2020, venue="example.com"))) is None


def test_exact_arxiv_selection_uses_authoritative_metadata_when_saving(tmp_path: Path):
    class Resolver:
        async def resolve(self, _intent):
            return WorkResolution(
                ResolutionDecision("unsupported", "exact_arxiv_requires_authority"),
                (),
            )

    async def fetch(url, headers):
        assert url.startswith("https://export.arxiv.org/api/query?")
        return FetchResponse(200, body=ATOM)

    hub = CitationProviderHub(env={}, fetcher=fetch)
    service = CitationService(hub, output_dir=tmp_path / "cite")
    service.resolver = Resolver()
    intent = WorkIntent(
        "wrong title",
        title="A Completely Different Work",
        identifiers=(WorkIdentifier("arxiv", "2001.00001"),),
    )

    outcome = asyncio.run(service.save((intent,)))

    item = outcome.items[0]
    assert item.status == "saved"
    assert item.receipt is not None
    assert item.receipt.title == "A Preprint"
    assert item.receipt.canonical_identity.key == "arxiv:2001.00001"
    assert item.receipt.version_kind == "preprint"
    assert (Path(item.receipt.bundle_path) / "reference.bib").is_file()


def test_missing_exact_arxiv_authority_is_not_found(tmp_path: Path):
    class Resolver:
        async def resolve(self, _intent):
            return WorkResolution(
                ResolutionDecision("unsupported", "exact_arxiv_requires_authority"),
                (),
            )

    async def fetch(_url, _headers):
        return FetchResponse(200, body=MISMATCHED_ATOM)

    service = CitationService(
        CitationProviderHub(env={}, fetcher=fetch),
        output_dir=tmp_path / "cite",
    )
    service.resolver = Resolver()

    outcome = asyncio.run(service.save((WorkIntent(
        "preprint", identifiers=(WorkIdentifier("arxiv", "2001.00001"),),
    ),)))

    assert outcome.items[0].status == "not_found"
    assert outcome.items[0].reason_code == "exact_arxiv_not_found"
    assert not (tmp_path / "cite").exists()


def test_authority_provider_error_becomes_a_truthful_per_item_failure(tmp_path: Path):
    class Resolver:
        async def resolve(self, _intent):
            return WorkResolution(
                ResolutionDecision("unsupported", "exact_arxiv_requires_authority"),
                (),
            )

    class FailingAuthority:
        async def resolve(self, _intent):
            raise ProviderError("arxiv", "private provider detail")

    async def no_fetch(_url, _headers):
        raise AssertionError("network not expected")

    service = CitationService(
        CitationProviderHub(env={}, fetcher=no_fetch),
        output_dir=tmp_path / "cite",
    )
    service.resolver = Resolver()
    service.authorities = FailingAuthority()

    outcome = asyncio.run(service.save((WorkIntent(
        "preprint", identifiers=(WorkIdentifier("arxiv", "2001.00001"),),
    ),)))

    assert outcome.items[0].status == "provider_failed"
    assert outcome.items[0].reason_code == "authority_lookup_failed"
    assert not (tmp_path / "cite").exists()


def test_failed_exact_doi_never_falls_back_to_a_different_authority_identity(
    tmp_path: Path,
):
    class Resolver:
        async def resolve(self, _intent):
            return WorkResolution(
                ResolutionDecision("not_found", "exact_doi_not_found"),
                (),
            )

    class AuthorityMustNotRun:
        async def resolve(self, _intent):
            raise AssertionError("exact DOI must not fall back to another identity")

    async def no_fetch(_url, _headers):
        raise AssertionError("network not expected")

    service = CitationService(
        CitationProviderHub(env={}, fetcher=no_fetch),
        output_dir=tmp_path / "cite",
    )
    service.resolver = Resolver()
    service.authorities = AuthorityMustNotRun()
    intent = WorkIntent(
        "missing DOI",
        title="Attention Is All You Need",
        year=2017,
        venue="NeurIPS",
        identifiers=(WorkIdentifier("doi", "10.1000/not-found"),),
    )

    outcome = asyncio.run(service.save((intent,)))

    assert outcome.items[0].status == "not_found"
    assert outcome.items[0].reason_code == "exact_doi_not_found"
    assert not (tmp_path / "cite").exists()
