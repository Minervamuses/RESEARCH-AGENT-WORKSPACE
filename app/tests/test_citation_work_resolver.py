import asyncio
from dataclasses import dataclass

from skills.citation.providers.base import ProviderRecord
from skills.citation.providers.doi_org import StructuredRecord
from skills.citation.providers.net import ProviderError
from skills.citation.resolution import WorkIdentifier, WorkIntent, WorkResolver


class SearchProvider:
    def __init__(self, records=(), error=None):
        self.records = list(records)
        self.error = error
        self.calls = []

    async def search(self, query, *, rows):
        self.calls.append((query, rows))
        if self.error:
            raise self.error
        return list(self.records)


class DoiProvider:
    def __init__(self, record=None, error=None):
        self.record = record
        self.error = error
        self.calls = []

    async def fetch_structured(self, doi):
        self.calls.append(doi)
        if self.error:
            raise self.error
        return self.record


def record(provider, doi="10.1000/work", *, title="A Work", version="published", authors=None):
    return ProviderRecord(
        provider, f"{provider}:{doi}", 0, title=title,
        authors=authors or ["Ada Author"], year=2020, doi=doi,
        venue="A Venue" if version == "published" else "",
        work_type="article" if version == "published" else "preprint",
        version_kind=version,
    )


def csl(doi="10.1000/work", *, title="A Work"):
    return StructuredRecord(doi, title=title, authors=["Ada Author"], year=2020, venue="A Venue", work_type="article")


def run(resolver, intent=None):
    return asyncio.run(resolver.resolve(intent or WorkIntent("work", title="A Work", authors=("Ada Author",))))


def test_provider_order_does_not_change_resolution_and_deduplicates_doi():
    a, b = SearchProvider([record("crossref")]), SearchProvider([record("datacite")])
    first = run(WorkResolver(crossref=a, datacite=b, doi_org=DoiProvider(csl())))
    second = run(WorkResolver(crossref=b, datacite=a, doi_org=DoiProvider(csl())))
    assert first.decision.status == second.decision.status == "eligible"
    assert first.decision.record.provider == second.decision.record.provider == "doi.org"


def test_partial_provider_failure_can_resolve_but_all_failure_cannot():
    good = SearchProvider([record("datacite")])
    failed = SearchProvider(error=ProviderError("crossref", "secret should not propagate"))
    outcome = run(WorkResolver(crossref=failed, datacite=good, doi_org=DoiProvider(csl())))
    assert outcome.decision.status == "eligible"
    assert all("secret" not in state.detail for state in outcome.provider_states)
    all_failed = run(WorkResolver(crossref=failed, datacite=failed, doi_org=DoiProvider(csl())))
    assert all_failed.decision.status == "provider_failed"


def test_refetch_conflict_blocks_eligibility():
    resolver = WorkResolver(
        crossref=SearchProvider([record("crossref")]),
        datacite=SearchProvider([]),
        doi_org=DoiProvider(csl(title="Different Work")),
    )
    assert run(resolver).decision.status == "verification_failed"


def test_same_title_different_versions_requires_clarification_before_refetch():
    resolver = WorkResolver(
        crossref=SearchProvider([record("crossref", "10.1000/pub")]),
        datacite=SearchProvider([record("datacite", "10.1000/pre", version="preprint")]),
        doi_org=DoiProvider(csl()),
    )
    outcome = run(resolver)
    assert outcome.decision.status == "ambiguous"
    assert outcome.decision.reason_code == "version_clarification_required"
    assert resolver._doi_org.calls == []


def test_exact_doi_refetch_still_cannot_override_metadata_veto():
    intent = WorkIntent("work", title="A Work", identifiers=(WorkIdentifier("doi", "10.1000/work"),))
    resolver = WorkResolver(
        crossref=SearchProvider([record("crossref", title="Different Work")]),
        datacite=SearchProvider([]), doi_org=DoiProvider(csl()),
    )
    assert run(resolver, intent).decision.status == "identity_conflict"


def test_queries_are_deterministic_and_bounded():
    intent = WorkIntent("x", title="A Work", authors=("Ada Author",), year=2020, venue="A Venue", identifiers=(WorkIdentifier("doi", "10.1000/work"),))
    assert WorkResolver.queries_for(intent) == ("10.1000/work", "A Work Ada Author 2020 A Venue")


def test_no_doi_never_becomes_write_eligible():
    item = record("openalex", doi="")
    item.doi = None
    outcome = run(WorkResolver(crossref=SearchProvider([item]), datacite=SearchProvider([]), doi_org=DoiProvider(csl())))
    assert outcome.decision.status == "unsupported"
    assert outcome.decision.reason_code == "unsupported_no_doi"
