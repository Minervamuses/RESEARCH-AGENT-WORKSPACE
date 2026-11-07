import asyncio
import json
from pathlib import Path

import pytest
from langchain_core.messages import ToolMessage

from skills.citation import service as service_module
from skills.citation.authority import (
    NEURIPS_BASE,
    AuthorityRegistry,
    export_bibtex,
    names_neurips,
    parse_neurips_index,
)
from skills.citation.hub import CitationProviderHub
from skills.citation.providers.base import ProviderRecord
from skills.citation.providers.net import FetchResponse, ProviderError, ProviderNetworkError, TransportFailure
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


def test_arxiv_transport_failure_is_retried_then_reported(no_citation_backoff):
    from skills.citation.providers.net import ProviderNetworkError, TransportFailure

    calls = []

    async def fetch(_url, _headers):
        calls.append(1)
        raise TransportFailure("ConnectError", "connection refused", retryable=True)

    registry = AuthorityRegistry(fetcher=fetch)
    with pytest.raises(ProviderNetworkError) as exc:
        asyncio.run(registry.resolve(WorkIntent(
            "x", identifiers=(WorkIdentifier("arxiv", "2001.00001"),),
        )))

    assert exc.value.provider == "arxiv"
    assert exc.value.exc_type == "ConnectError"
    assert len(calls) == 3


def test_arxiv_transient_status_recovers_and_missing_record_abstains(
    no_citation_backoff,
):
    responses = [FetchResponse(503), FetchResponse(200, body=ATOM), FetchResponse(404)]

    async def fetch(_url, _headers):
        return responses.pop(0)

    registry = AuthorityRegistry(fetcher=fetch)
    intent = WorkIntent("x", identifiers=(WorkIdentifier("arxiv", "2001.00001"),))
    record = asyncio.run(registry.resolve(intent))
    missing = asyncio.run(registry.resolve(intent))

    assert record.identity.key == "arxiv:2001.00001"
    assert missing is None
    assert len(no_citation_backoff) == 1


NEURIPS_FIXTURES = Path(__file__).parent / "fixtures" / "neurips"
NEURIPS_2017 = f"{NEURIPS_BASE}/paper_files/paper/2017"
ATTENTION_HASH = "3f5ee243547dee91fbd053c1c4a845aa"
ATTENTION_PAGE = f"{NEURIPS_2017}/hash/{ATTENTION_HASH}-Abstract.html"


def neurips_site(pages=None):
    """Official proceedings stand-in: the trimmed 2017 list and paper page; 404 elsewhere.

    ``pages`` overrides a URL's body; ``None`` makes that URL 404.
    """
    served = {
        NEURIPS_2017: (NEURIPS_FIXTURES / "2017-index.html").read_bytes(),
        ATTENTION_PAGE: (NEURIPS_FIXTURES / "2017-attention-abstract.html").read_bytes(),
        **(pages or {}),
    }
    calls = []

    async def fetch(url, headers):
        calls.append(url)
        if served.get(url) is not None:
            return FetchResponse(200, body=served[url])
        return FetchResponse(404)

    return fetch, calls


def neurips_intent(title="Attention Is All You Need", year=2017, venue="NeurIPS 2017", **extra):
    return WorkIntent("x", title=title, year=year, venue=venue, **extra)


def test_neurips_lookup_queries_the_official_list_and_paper_page():
    fetch, calls = neurips_site()
    registry = AuthorityRegistry(fetcher=fetch)

    record = asyncio.run(registry.resolve(neurips_intent()))

    assert calls == [NEURIPS_2017, ATTENTION_PAGE]
    assert record.identity.key == f"venue:neurips:2017:{ATTENTION_HASH}"
    assert record.title == "Attention is All you Need", "the proceedings' own title"
    assert record.authors[0] == "Ashish Vaswani" and record.authors[6] == "Łukasz Kaiser"
    assert record.names[5] == ("Gomez", "Aidan N.") and len(record.names) == 8
    assert (record.year, record.venue) == (2017, "Advances in Neural Information Processing Systems 30")
    assert (record.url, record.provider, record.work_type) == (ATTENTION_PAGE, "neurips", "inproceedings")
    bibtex = export_bibtex(record)
    assert bibtex.entry_type == "inproceedings" and bibtex.doi is None
    assert bibtex.title == "Attention is All you Need" and bibtex.venue == record.venue

    # The year's list is fetched once per session.
    assert asyncio.run(registry.resolve(neurips_intent(title="A General Framework for Robust Interactive Learning"))) is None
    assert calls[2:] == [f"{NEURIPS_2017}/hash/3f647cadf56541fb9513cb63ec370187-Abstract.html"]


def test_neurips_lookup_has_no_built_in_answer():
    """Even the one paper the old table knew must come from the official site."""

    async def offline(_url, _headers):
        raise TransportFailure("ConnectError", "connection refused", retryable=False)

    with pytest.raises(ProviderNetworkError):
        asyncio.run(AuthorityRegistry(fetcher=offline).resolve(neurips_intent()))
    empty, calls = neurips_site({NEURIPS_2017: b"<html><ul></ul></html>"})
    assert asyncio.run(AuthorityRegistry(fetcher=empty).resolve(neurips_intent())) is None
    assert calls == [NEURIPS_2017]


def test_neurips_lookup_abstains_unless_the_official_pages_agree():
    page = (NEURIPS_FIXTURES / "2017-attention-abstract.html").read_text(encoding="utf-8")
    index = (NEURIPS_FIXTURES / "2017-index.html").read_text(encoding="utf-8")
    twice = index.replace("</ul>", index[index.index("<li"):index.index("</li>") + 5] + "</ul>")
    cases = {
        "title not listed that year": ({}, neurips_intent(title="Attention Is Not All You Need")),
        "year not published": ({}, neurips_intent(year=2099)),
        "two listed papers share the title": ({NEURIPS_2017: twice.encode()}, neurips_intent()),
        "paper page has another title": (
            {ATTENTION_PAGE: page.replace('citation_title" content="Attention is All you Need',
                                          'citation_title" content="Something Else').encode()}, neurips_intent()),
        "paper page has another year": (
            {ATTENTION_PAGE: page.replace('content="2017"', 'content="2018"').encode()}, neurips_intent()),
        "paper page lists no authors": (
            {ATTENTION_PAGE: page.replace('name="citation_author"', 'name="x_author"').encode()}, neurips_intent()),
        "paper page is gone": ({ATTENTION_PAGE: None}, neurips_intent()),
    }
    for label, (pages, intent) in cases.items():
        fetch, _calls = neurips_site(pages)
        assert asyncio.run(AuthorityRegistry(fetcher=fetch).resolve(intent)) is None, label


def test_neurips_list_parsing_and_venue_names():
    papers = parse_neurips_index((NEURIPS_FIXTURES / "2017-index.html").read_text(encoding="utf-8"), 2017)
    assert [paper.title for paper in papers] == [
        "Attention is All you Need",
        "A General Framework for Robust Interactive Learning",
        "Reconstruct & Crush Network",
        'Decoupling "when to update" from "how to update"',
    ]
    assert papers[0].paper_hash == ATTENTION_HASH and papers[0].path.endswith("-Abstract.html")
    assert parse_neurips_index((NEURIPS_FIXTURES / "2017-index.html").read_text(encoding="utf-8"), 2018) == []
    for venue in ("NeurIPS", "NeurIPS 2017", "NIPS 2017", "Advances in Neural Information Processing Systems 30"):
        assert names_neurips(venue), venue
    for venue in (None, "", "Neural Networks", "SNIPS workshop", "example.com", "ICLR"):
        assert not names_neurips(venue), venue


def test_neurips_save_verifies_online_and_writes_the_project_entry(tmp_path):
    fetch, calls = neurips_site()

    class Resolver:
        async def resolve(self, _intent):
            return WorkResolution(ResolutionDecision("not_found", "no_provider_records"), ())

    library = tmp_path / "references.json"
    service = CitationService(
        CitationProviderHub(env={}, fetcher=fetch), output_dir=tmp_path / "cite", library_path=library,
    )
    service.resolver = Resolver()
    intent = neurips_intent(authors=("Ashish Vaswani",), version_kind="published")

    item = asyncio.run(service.save((intent,))).items[0]

    assert item.status == "saved" and item.reason_code == "saved_new"
    assert item.receipt.canonical_identity.key == f"venue:neurips:2017:{ATTENTION_HASH}"
    assert calls == [NEURIPS_2017, ATTENTION_PAGE]
    sidecar = json.loads((Path(item.receipt.bundle_path) / "citation.json").read_text(encoding="utf-8"))
    assert sidecar["source_ref"]["verification_level"] == "authority_metadata_verified"
    assert sidecar["source_ref"]["provenance"] == "authoritative:neurips"
    [entry] = json.loads(library.read_text(encoding="utf-8"))
    assert entry["type"] == "paper-conference" and entry["URL"] == ATTENTION_PAGE
    assert entry["container-title"] == "Advances in Neural Information Processing Systems 30"
    assert entry["author"][6] == {"family": "Kaiser", "given": "Łukasz"}
    assert entry["issued"] == {"date-parts": [[2017]]} and entry["title"] == "Attention is All you Need"


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
    fetch, calls = neurips_site()
    service = CitationService(
        CitationProviderHub(env={}, fetcher=fetch), output_dir=tmp_path / "cite",
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
        assert item.receipt.canonical_identity.key == f"venue:neurips:2017:{ATTENTION_HASH}"
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
    # Only the official proceedings site is ever contacted (list once, then the page).
    assert set(calls) <= {NEURIPS_2017, ATTENTION_PAGE} and calls.count(NEURIPS_2017) == 1


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
