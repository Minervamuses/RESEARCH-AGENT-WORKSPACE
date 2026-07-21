import asyncio
from pathlib import Path

from skills.citation.authority import AuthorityRegistry, export_bibtex
from skills.citation.hub import CitationProviderHub
from skills.citation.providers.net import FetchResponse
from skills.citation.resolution import (
    ResolutionDecision,
    WorkIdentifier,
    WorkIntent,
    WorkResolution,
)
from skills.citation.service import CitationService


ATOM = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>A Preprint</title><published>2020-01-02T00:00:00Z</published><author><name>Ada Author</name></author></entry></feed>'''


def test_official_arxiv_record_and_deterministic_bibtex():
    async def fetch(url, headers):
        assert url.startswith("https://export.arxiv.org/api/query?")
        return FetchResponse(200, body=ATOM)
    registry = AuthorityRegistry(fetcher=fetch)
    record = asyncio.run(registry.resolve(WorkIntent("x", identifiers=(WorkIdentifier("arxiv", "2001.00001"),))))
    assert record.identity.key == "arxiv:2001.00001"
    canonical = export_bibtex(record)
    assert canonical.title == "A Preprint" and canonical.doi is None


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


def test_service_rechecks_authority_metadata_before_saving(tmp_path: Path):
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

    assert outcome.items[0].status == "identity_conflict"
    assert outcome.items[0].reason_code == "title_mismatch"
    assert not (tmp_path / "cite").exists()
