import asyncio
import json
from pathlib import Path

import pytest
from langchain_core.messages import ToolMessage

from skills.citation import service as service_module
from skills.citation.authority import AuthorityRegistry, export_bibtex
from skills.citation.hub import CitationProviderHub
from skills.citation.providers.base import ProviderRecord
from skills.citation.providers.net import FetchResponse, ProviderError
from skills.citation.resolution import (
    ResolutionDecision,
    WorkIdentifier,
    WorkIntent,
    WorkResolution,
)
from skills.citation.service import CitationService
from skills.citation.storage import StorageError
from skills.citation.tool import TOOL_NAME, create_citation_workflow_tool
from skills.citation.types import SaveBatchOutcome
from tests.citation_fixtures import DOI_A, DOI_B, RoutingFetcher
from tests.test_citation_work_resolver import SearchProvider


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


@pytest.fixture
def earliest_authority_case(tmp_path):
    intent = WorkIntent(
        "earliest attention", title="Attention Is All You Need", year=2017,
        venue="Advances in Neural Information Processing Systems 30",
        version_kind="earliest",
    )
    records = [
        ProviderRecord(
            "crossref", "crossref:published", 0, title=intent.title, year=2017,
            venue=intent.venue, doi=DOI_A, version_kind="published",
        ),
        ProviderRecord(
            "datacite", "datacite:preprint", 1, title=intent.title, year=2017,
            doi=DOI_B, version_kind="preprint", identifiers={"arxiv": "1706.03762"},
        ),
    ]
    calls = []

    async def no_fetch(url, headers):
        calls.append((url, headers.get("Accept", "")))
        raise AssertionError(f"unexpected network request: {url}")

    service = CitationService(
        CitationProviderHub(env={}, fetcher=no_fetch), output_dir=tmp_path / "cite",
    )
    return intent, records, service, calls


@pytest.mark.parametrize("year,status,reason", [
    (2017, "ambiguous", "earliest_year_tie"),
    (None, "ambiguous", "earliest_year_missing"),
    (2017, "not_found", "no_provider_records"),
])
def test_earliest_authority_fallback_preserves_year_ambiguity_only(
    earliest_authority_case, year, status, reason,
):
    intent, records, service, calls = earliest_authority_case
    for record in records:
        record.year = year

    class Resolver:
        async def resolve(self, _intent):
            return WorkResolution(
                ResolutionDecision(status, reason, alternatives=tuple(records)), (),
            )

    service.resolver = Resolver()
    assert asyncio.run(service.authorities.resolve(intent)) is not None

    item = asyncio.run(service.save((intent,))).items[0]

    if status == "not_found":
        assert item.status == "saved"
        assert item.receipt.canonical_identity.key == "venue:neurips:2017:7181"
        assert service.registry.receipt_is_trusted(item.receipt)
        assert (Path(item.receipt.bundle_path) / "reference.bib").is_file()
    else:
        assert item.status == "ambiguous"
        assert item.reason_code == reason
        assert item.receipt is None
        assert [(alternative.doi, alternative.year) for alternative in item.alternatives] == [
            (DOI_A, year), (DOI_B, year),
        ]
        assert service.registry.list() == []
        assert not service.output_dir.exists()
    assert calls == []


@pytest.mark.parametrize("year,reason", [(2017, "earliest_year_tie"), (None, "earliest_year_missing")])
def test_earliest_real_resolver_service_tool_returns_ambiguity_without_saving(
    earliest_authority_case, monkeypatch, year, reason,
):
    intent, records, service, calls = earliest_authority_case
    for record in records:
        record.year = year
    crossref, datacite = SearchProvider(records[:1]), SearchProvider(records[1:])
    monkeypatch.setattr(service.hub.crossref, "search_work", crossref.search_work)
    monkeypatch.setattr(service.hub.datacite, "search_work", datacite.search_work)
    tool = create_citation_workflow_tool(service_getter=lambda: service)

    message = asyncio.run(tool.ainvoke({
        "type": "tool_call", "name": TOOL_NAME, "id": "earliest-save",
        "args": {"action": "save", "works": [{
            "requested_label": intent.requested_label, "title": intent.title,
            "year": intent.year, "venue": intent.venue, "version_kind": "earliest",
        }]},
    }))

    assert isinstance(message, ToolMessage)
    content = json.loads(str(message.content).removeprefix("Actual citation save result:\n"))
    assert content == message.artifact
    item = SaveBatchOutcome.from_artifact(content).items[0]
    assert item.status == "ambiguous"
    assert item.reason_code == reason
    assert item.receipt is None
    assert [alternative.to_artifact() for alternative in item.alternatives] == [
        {"title": intent.title, "authors": [], "year": year, "venue": intent.venue,
         "version_kind": "published", "doi": DOI_A, "arxiv": None},
        {"title": intent.title, "authors": [], "year": year, "venue": "",
         "version_kind": "preprint", "doi": DOI_B, "arxiv": "1706.03762"},
    ]
    assert len(crossref.calls) == len(datacite.calls) == 1
    assert calls == []
    assert service.registry.list() == []
    assert not service.output_dir.exists()


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


def test_mixed_doi_and_authority_save_preserves_metadata_and_reuses_bundles(
    tmp_path: Path,
):
    routing = RoutingFetcher()

    async def fetch(url, headers):
        if url.startswith("https://export.arxiv.org/api/query?"):
            return FetchResponse(200, body=ATOM)
        return await routing(url, headers)

    service = CitationService(
        CitationProviderHub(env={}, fetcher=fetch), output_dir=tmp_path / "cite",
    )
    intents = (
        WorkIntent("paper", identifiers=(WorkIdentifier("doi", DOI_A),)),
        WorkIntent("missing", identifiers=(WorkIdentifier("doi", "10.1234/missing"),)),
        WorkIntent("preprint", identifiers=(WorkIdentifier("arxiv", "2001.00001"),)),
    )

    first = asyncio.run(service.save(intents))

    assert [item.status for item in first.items] == ["saved", "not_found", "saved"]
    assert [(item.request_index, item.requested_label) for item in first.items] == [
        (0, "paper"), (1, "missing"), (2, "preprint"),
    ]
    assert first.items[1].reason_code == "exact_doi_not_found"
    assert first.items[1].receipt is None
    artifacts = {}
    for index, title, doi, version, provider, record_id, reason in (
        (0, "Paper A", DOI_A, "published", "doi.org", f"doi.org:{DOI_A}", "exact_identifier"),
        (2, "A Preprint", None, "preprint", "arxiv", "arxiv:2001.00001", "authoritative_exact_record"),
    ):
        item = first.items[index]
        receipt = item.receipt
        assert item.reason_code == "saved_new"
        assert (receipt.title, receipt.doi, receipt.version_kind) == (title, doi, version)
        assert receipt.cite_marker == f"[[cite:{receipt.source_id}]]"
        assert service.registry.receipt_is_trusted(receipt)
        ref = service.registry.get(receipt.source_id)
        bundle = Path(receipt.bundle_path)
        sidecar = json.loads((bundle / "citation.json").read_text())
        assert sidecar["source_ref"] == ref.to_persisted_dict()
        assert sidecar["creation_evidence"]["batch_id"] == first.batch_id
        assert sidecar["creation_evidence"]["request_index"] == index
        assert sidecar["creation_evidence"]["agent_intent"]["identifiers"] == [
            {"kind": intents[index].identifiers[0].kind, "value": intents[index].identifiers[0].value},
        ]
        assert sidecar["resolution"] == {
            "record_source": provider,
            "provider_record_ids": [record_id],
            "version_kind": version,
            "decision_reason_codes": [reason],
        }
        for name in ("reference.bib", "citation.json"):
            path = bundle / name
            artifacts[path] = path.read_bytes()

    second = asyncio.run(service.save(intents))

    assert [item.status for item in second.items] == ["reused", "not_found", "reused"]
    for index in (0, 2):
        assert second.items[index].reason_code == "reused_existing"
        assert second.items[index].receipt == first.items[index].receipt
        assert service.registry.receipt_is_trusted(second.items[index].receipt)
    assert all(path.read_bytes() == content for path, content in artifacts.items())


def test_mixed_save_keeps_storage_and_registry_failures_per_item(
    monkeypatch, tmp_path: Path,
):
    routing = RoutingFetcher()

    async def fetch(url, headers):
        if url.startswith("https://export.arxiv.org/api/query?"):
            return FetchResponse(200, body=ATOM)
        return await routing(url, headers)

    service = CitationService(
        CitationProviderHub(env={}, fetcher=fetch), output_dir=tmp_path / "cite",
    )
    write_bundle = service_module.write_identity_bundle
    register = service.registry.register

    def fail_authority_write(output_dir, **kwargs):
        if kwargs["identity"].kind == "arxiv":
            raise StorageError("write_failed", "test write failure")
        return write_bundle(output_dir, **kwargs)

    def fail_first_doi_registration(ref, *, receipt):
        assert (Path(receipt.bundle_path) / "reference.bib").is_file()
        if ref.doi == DOI_A:
            raise ValueError("test registry conflict")
        return register(ref, receipt=receipt)

    monkeypatch.setattr(service_module, "write_identity_bundle", fail_authority_write)
    monkeypatch.setattr(service.registry, "register", fail_first_doi_registration)
    intents = (
        WorkIntent("preprint", identifiers=(WorkIdentifier("arxiv", "2001.00001"),)),
        WorkIntent("first paper", identifiers=(WorkIdentifier("doi", DOI_A),)),
        WorkIntent("second paper", identifiers=(WorkIdentifier("doi", DOI_B),)),
    )

    batch = asyncio.run(service.save(intents))

    assert [(item.request_index, item.status, item.reason_code) for item in batch.items] == [
        (0, "storage_failed", "write_failed"),
        (1, "storage_failed", "registry_conflict"),
        (2, "saved", "saved_new"),
    ]
    assert batch.items[0].receipt is None
    assert batch.items[1].receipt is None
    receipt = batch.items[2].receipt
    assert receipt.doi == DOI_B
    assert service.registry.receipt_is_trusted(receipt)
    assert [ref.doi for ref in service.registry.list()] == [DOI_B]
    bibs = list(service.output_dir.glob("*/reference.bib"))
    assert len(bibs) == 2
    assert {DOI_A, DOI_B} == {
        doi for path in bibs for doi in (DOI_A, DOI_B) if doi in path.read_text()
    }
