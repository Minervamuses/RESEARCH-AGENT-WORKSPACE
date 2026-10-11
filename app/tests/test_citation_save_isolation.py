"""Fault injection: isolated per-item failures and classified provider errors."""

import asyncio
import json
import logging
from pathlib import Path

import pytest

from skills.citation import service as service_module
from skills.citation.hub import CitationProviderHub
from skills.citation.providers.base import BibliographicQuery
from skills.citation.providers.net import (
    FetchResponse,
    ProviderError,
    ProviderTimeout,
    TransportFailure,
)
from skills.citation.resolution import WorkIdentifier, WorkIntent, WorkResolver
from skills.citation.service import CitationService
from tests.citation_fixtures import CSL, DOI_A, DOI_B, RoutingFetcher

DOI_C = "10.1234/paper-c"


class _ThreePaperFetcher(RoutingFetcher):
    """RoutingFetcher plus a third DOI, with an optional per-URL fault."""

    def __init__(self, fault=None):
        super().__init__()
        self.fault = fault

    async def __call__(self, url, headers):
        if self.fault is not None:
            self.fault(url, headers)
        accept = headers.get("Accept", "")
        if url == f"https://doi.org/{DOI_C}":
            self.calls.append((url, accept))
            if "csl+json" in accept:
                return FetchResponse(200, body=json.dumps({
                    "DOI": DOI_C, "title": "Paper C",
                    "issued": {"date-parts": [[2019]]}, "type": "journal-article",
                }).encode())
            return FetchResponse(200, body=(
                f"@article{{c, title={{Paper C}}, year={{2019}}, doi={{{DOI_C}}}}}"
            ).encode())
        return await super().__call__(url, headers)


def _intent(label: str, doi: str) -> WorkIntent:
    return WorkIntent(label, identifiers=(WorkIdentifier("doi", doi),))


def _service(tmp_path: Path, fetcher) -> CitationService:
    return CitationService(
        CitationProviderHub(env={}, fetcher=fetcher), output_dir=tmp_path / "cite",
    )


def _statuses(outcome):
    return [(item.status, item.reason_code) for item in outcome.items]


def test_unexpected_resolution_exception_isolated_to_its_item(tmp_path, caplog):
    service = _service(tmp_path, _ThreePaperFetcher())
    real_resolve = service.resolver.resolve

    async def resolve(intent):
        if intent.requested_label == "B":
            raise KeyError("malformed provider payload")
        return await real_resolve(intent)

    service.resolver.resolve = resolve
    with caplog.at_level(logging.ERROR, logger="skills.citation.service"):
        outcome = asyncio.run(service.save((
            _intent("A", DOI_A), _intent("B", DOI_B), _intent("C", DOI_C),
        )))

    assert _statuses(outcome) == [
        ("saved", "saved_new"),
        ("internal_error", "resolution_internal_error"),
        ("saved", "saved_new"),
    ]
    assert {source.doi for source in service.registry.list()} == {DOI_A, DOI_C}
    record = next(r for r in caplog.records if "failed unexpectedly" in r.getMessage())
    assert outcome.batch_id in record.getMessage()
    assert "item 1" in record.getMessage() and "during resolution" in record.getMessage()
    assert record.exc_info is not None and record.exc_info[0] is KeyError


def test_unexpected_verification_exception_isolated_to_its_item(tmp_path):
    def fault(url, headers):
        if url == f"https://doi.org/{DOI_B}" and "x-bibtex" in headers["Accept"]:
            raise AttributeError("unexpected transport object")

    service = _service(tmp_path, _ThreePaperFetcher(fault))

    outcome = asyncio.run(service.save((
        _intent("A", DOI_A), _intent("B", DOI_B), _intent("C", DOI_C),
    )))

    assert _statuses(outcome) == [
        ("saved", "saved_new"),
        ("internal_error", "verification_internal_error"),
        ("saved", "saved_new"),
    ]
    assert len(list((tmp_path / "cite").glob("*/reference.bib"))) == 2


def test_unexpected_storage_exception_isolated_to_its_item(tmp_path, monkeypatch):
    real_write = service_module.write_identity_bundle

    def write(output_dir, *, identity, **kwargs):
        if identity.value == DOI_A:
            raise PermissionError("read-only bundle directory")
        return real_write(output_dir, identity=identity, **kwargs)

    monkeypatch.setattr(service_module, "write_identity_bundle", write)
    service = _service(tmp_path, _ThreePaperFetcher())

    outcome = asyncio.run(service.save((
        _intent("A", DOI_A), _intent("B", DOI_B), _intent("C", DOI_C),
    )))

    assert _statuses(outcome) == [
        ("internal_error", "storage_internal_error"),
        ("saved", "saved_new"),
        ("saved", "saved_new"),
    ]
    assert {source.doi for source in service.registry.list()} == {DOI_B, DOI_C}


def test_all_items_failing_unexpectedly_still_return_a_batch(tmp_path):
    service = _service(tmp_path, _ThreePaperFetcher())

    async def resolve(_intent):
        raise RuntimeError("bug")

    service.resolver.resolve = resolve
    outcome = asyncio.run(service.save((_intent("A", DOI_A), _intent("B", DOI_B))))

    assert [item.status for item in outcome.items] == ["internal_error"] * 2
    assert [item.request_index for item in outcome.items] == [0, 1]
    assert not (tmp_path / "cite").exists()


def test_cancellation_is_not_converted_into_an_item_failure(tmp_path):
    service = _service(tmp_path, _ThreePaperFetcher())

    async def resolve(_intent):
        raise asyncio.CancelledError()

    service.resolver.resolve = resolve

    async def scenario():
        try:
            await service.save((_intent("A", DOI_A),))
        except asyncio.CancelledError:
            return "cancelled"
        return "completed"

    assert asyncio.run(scenario()) == "cancelled"


def test_search_isolates_an_unexpected_provider_exception(tmp_path, caplog):
    service = _service(tmp_path, _ThreePaperFetcher())

    async def broken_search(*_args, **_kwargs):
        raise TypeError("parser bug")

    service.hub.datacite.search_text = broken_search
    with caplog.at_level(logging.ERROR, logger="skills.citation.service"):
        records, states = asyncio.run(service.search("paper"))

    assert [record.doi for record in records] == [DOI_A, DOI_B]
    assert states == ["crossref:ok", "datacite:internal_error(TypeError)"]
    assert any(record.exc_info for record in caplog.records)


def test_resolver_isolates_an_unexpected_provider_exception():
    class Provider:
        def __init__(self, records=None, error=None):
            self.records = records or []
            self.error = error

        async def search_work(self, _query: BibliographicQuery, *, rows):
            if self.error is not None:
                raise self.error
            return self.records

    from skills.citation.providers.crossref import parse_work_item
    from tests.citation_fixtures import CROSSREF_ITEMS

    class DoiOrg:
        async def fetch_structured(self, doi):
            from skills.citation.providers.doi_org import parse_csl

            return parse_csl(doi, CSL[doi])

    resolver = WorkResolver(
        crossref=Provider([parse_work_item(CROSSREF_ITEMS[0], 0)]),
        datacite=Provider(error=IndexError("bad row")),
        doi_org=DoiOrg(),
    )

    resolution = asyncio.run(resolver.resolve(WorkIntent("A", title="Paper A")))

    assert resolution.decision.status == "eligible"
    assert resolution.decision.record.doi == DOI_A
    datacite_state = next(s for s in resolution.provider_states if s.provider == "datacite")
    assert (datacite_state.status, datacite_state.detail) == ("error", "internal:IndexError")


def test_non_object_csl_payload_is_a_provider_error(tmp_path):
    class ArrayCslFetcher(RoutingFetcher):
        async def __call__(self, url, headers):
            if url == f"https://doi.org/{DOI_A}" and "csl+json" in headers["Accept"]:
                return FetchResponse(200, body=b"[]")
            return await super().__call__(url, headers)

    hub = CitationProviderHub(env={}, fetcher=ArrayCslFetcher())
    try:
        asyncio.run(hub.doi_org.fetch_structured(DOI_A))
    except ProviderError as exc:
        assert "not a JSON object" in str(exc)
    else:  # pragma: no cover - assertion helper
        raise AssertionError("expected ProviderError")

    outcome = asyncio.run(CitationService(hub, output_dir=tmp_path / "cite").save(
        (_intent("A", DOI_A),)
    ))
    assert _statuses(outcome) == [("verification_failed", "doi_refetch_failed")]


class _FaultyDoiFetcher(_ThreePaperFetcher):
    """Serve scripted outcomes for one DOI and media type; others normally."""

    def __init__(self, doi, accept_marker, outcomes):
        super().__init__()
        self.target = (f"https://doi.org/{doi}", accept_marker)
        self.outcomes = list(outcomes)

    async def __call__(self, url, headers):
        if url == self.target[0] and self.target[1] in headers["Accept"]:
            outcome = self.outcomes.pop(0) if self.outcomes else FetchResponse(500)
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
        return await super().__call__(url, headers)


def _refused():
    return TransportFailure("ConnectError", "connection refused", retryable=True)


@pytest.mark.parametrize(
    ("outcomes", "expected"),
    [
        ([_refused() for _ in range(3)], ("provider_failed", "doi_refetch_network_error")),
        ([FetchResponse(503)] * 3, ("provider_failed", "doi_refetch_server_error")),
        ([FetchResponse(429)] * 3, ("provider_failed", "doi_refetch_rate_limited")),
        ([FetchResponse(403)], ("verification_failed", "doi_refetch_failed")),
        ([FetchResponse(404)], ("not_found", "exact_doi_not_found")),
    ],
)
def test_exact_doi_lookup_failures_are_classified(
    tmp_path, no_citation_backoff, outcomes, expected,
):
    fetcher = _FaultyDoiFetcher(DOI_B, "csl+json", outcomes)
    service = _service(tmp_path, fetcher)

    outcome = asyncio.run(service.save((_intent("A", DOI_A), _intent("B", DOI_B))))

    assert _statuses(outcome) == [("saved", "saved_new"), expected]


@pytest.mark.parametrize(
    ("outcomes", "expected"),
    [
        ([_refused() for _ in range(3)], ("provider_failed", "bibtex_lookup_network_error")),
        (
            [asyncio.TimeoutError("slow"), asyncio.TimeoutError("slow")],
            ("provider_failed", "bibtex_lookup_timeout"),
        ),
        ([FetchResponse(404)], ("verification_failed", "bibtex_lookup_failed")),
        (
            [FetchResponse(200, body=b"not bibtex")],
            ("verification_failed", "not_exactly_one_entry"),
        ),
    ],
)
def test_bibtex_failures_are_classified(tmp_path, no_citation_backoff, outcomes, expected):
    fetcher = _FaultyDoiFetcher(DOI_A, "x-bibtex", outcomes)
    service = _service(tmp_path, fetcher)

    outcome = asyncio.run(service.save((_intent("A", DOI_A), _intent("C", DOI_C))))

    assert _statuses(outcome) == [expected, ("saved", "saved_new")]


def test_transient_authority_failure_is_classified(tmp_path):
    service = _service(tmp_path, _ThreePaperFetcher())

    class Authority:
        async def resolve(self, _intent):
            raise ProviderTimeout("arxiv", "slow")

    service.authorities = Authority()
    outcome = asyncio.run(service.save((WorkIntent(
        "preprint", identifiers=(WorkIdentifier("arxiv", "2001.00001"),),
    ),)))

    assert _statuses(outcome) == [("provider_failed", "authority_lookup_timeout")]


def test_search_states_name_the_failing_provider_and_cause(tmp_path, no_citation_backoff):
    import httpx

    from tests.test_citation_hub import _hub_with_transport

    def handler(request):
        if request.url.host == "api.crossref.org":
            return httpx.Response(503)
        raise httpx.ConnectError("connection refused", request=request)

    async def scenario():
        hub = _hub_with_transport(handler)
        try:
            service = CitationService(hub, output_dir=tmp_path / "cite")
            return await service.search("paper")
        finally:
            await hub.aclose()

    records, states = asyncio.run(scenario())

    assert records == []
    assert states == [
        "crossref:server_error(503)",
        "datacite:network_error(ConnectError)",
    ]


def test_search_tool_does_not_present_total_failure_as_no_results(tmp_path):
    from skills.citation.tool import create_citation_workflow_tool

    class Service:
        async def search(self, _query, *, date_filter=None):
            return [], ["crossref:timeout", "datacite:server_error(502)"]

    tool = create_citation_workflow_tool(service_getter=Service)
    content = asyncio.run(tool.ainvoke({"action": "search", "query": "paper"}))

    assert content.startswith("Search failed: no provider answered successfully")
    assert "crossref:timeout; datacite:server_error(502)" in content
    assert "not evidence that the work does not exist" in content
    assert "No bibliographic records found" not in content
