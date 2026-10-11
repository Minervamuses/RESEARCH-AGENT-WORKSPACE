"""Fault injection: one item's unexpected exception never sinks the batch."""

import asyncio
import json
import logging
from pathlib import Path

from skills.citation import service as service_module
from skills.citation.hub import CitationProviderHub
from skills.citation.providers.base import BibliographicQuery
from skills.citation.providers.net import FetchResponse, ProviderError
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
    assert states == ["crossref:ok", "datacite:internal_error"]
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
