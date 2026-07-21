import asyncio
from dataclasses import dataclass

from skills.citation.providers.base import BibliographicQuery, ProviderRecord
from skills.citation.providers.doi_org import StructuredRecord
from skills.citation.providers.net import ProviderError
from skills.citation.resolution import WorkIdentifier, WorkIntent, WorkResolver


class SearchProvider:
    def __init__(self, records=(), error=None):
        self.records = list(records)
        self.error = error
        self.calls = []

    async def search_work(self, query, *, rows):
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
    doi_org = DoiProvider(csl(title="Different Work"))
    resolver = WorkResolver(
        crossref=SearchProvider([record("crossref")]),
        datacite=SearchProvider([]), doi_org=doi_org,
    )
    assert run(resolver, intent).decision.status == "identity_conflict"
    assert doi_org.calls == ["10.1000/work"]
    assert resolver._providers[0][1].calls == []


def test_bibliographic_projection_is_structured_and_excludes_policy_fields():
    intent = WorkIntent(
        "x",
        title="A Work",
        authors=("Ada Author",),
        year=2020,
        venue="A Venue",
        work_type="article",
    )
    assert WorkResolver.bibliographic_query_for(intent) == BibliographicQuery(
        "A Work", ("Ada Author",), 2020, "A Venue", "article"
    )


def test_explicit_doi_uses_exact_lane_without_fuzzy_provider_search():
    crossref, datacite = SearchProvider([record("crossref")]), SearchProvider([])
    doi_org = DoiProvider(csl())
    resolver = WorkResolver(
        crossref=crossref, datacite=datacite, doi_org=doi_org
    )
    intent = WorkIntent(
        "work",
        title="A Work",
        identifiers=(WorkIdentifier("doi", "10.1000/work"),),
    )

    outcome = run(resolver, intent)

    assert outcome.decision.status == "eligible"
    assert doi_org.calls == ["10.1000/work"]
    assert crossref.calls == datacite.calls == []


def test_exact_doi_alias_accepts_authoritative_canonical_record():
    crossref, datacite = SearchProvider(), SearchProvider()
    doi_org = DoiProvider(csl("10.1000/canonical"))
    resolver = WorkResolver(
        crossref=crossref, datacite=datacite, doi_org=doi_org
    )
    intent = WorkIntent(
        "work",
        title="A Work",
        identifiers=(WorkIdentifier("doi", "10.1000/legacy"),),
    )

    outcome = run(resolver, intent)

    assert outcome.decision.status == "eligible"
    assert outcome.decision.record.doi == "10.1000/canonical"
    assert outcome.decision.record.aliases == ("10.1000/legacy",)


def test_matching_arxiv_and_datacite_doi_share_one_exact_lane():
    crossref, datacite = SearchProvider(), SearchProvider()
    doi = "10.48550/arxiv.1706.03762"
    doi_org = DoiProvider(csl(doi))
    resolver = WorkResolver(
        crossref=crossref, datacite=datacite, doi_org=doi_org
    )
    intent = WorkIntent(
        "preprint",
        title="A Work",
        identifiers=(
            WorkIdentifier("doi", doi),
            WorkIdentifier("arxiv", "1706.03762v7"),
        ),
    )

    outcome = run(resolver, intent)

    assert outcome.decision.status == "eligible"
    assert outcome.decision.record.identifiers["arxiv"] == "1706.03762"
    assert doi_org.calls == [doi]
    assert crossref.calls == datacite.calls == []


def test_unrelated_doi_and_arxiv_identifiers_require_disambiguation():
    crossref, datacite = SearchProvider(), SearchProvider()
    doi_org = DoiProvider(csl())
    resolver = WorkResolver(
        crossref=crossref, datacite=datacite, doi_org=doi_org
    )
    intent = WorkIntent(
        "two manifestations",
        identifiers=(
            WorkIdentifier("doi", "10.1000/published"),
            WorkIdentifier("arxiv", "1706.03762"),
        ),
    )

    outcome = run(resolver, intent)

    assert outcome.decision.status == "ambiguous"
    assert outcome.decision.reason_code == "multiple_exact_identifiers"
    assert crossref.calls == datacite.calls == doi_org.calls == []


def test_explicit_arxiv_defers_to_authority_without_fuzzy_search():
    crossref, datacite = SearchProvider([record("crossref")]), SearchProvider([])
    resolver = WorkResolver(
        crossref=crossref, datacite=datacite, doi_org=DoiProvider(csl())
    )
    intent = WorkIntent(
        "preprint", identifiers=(WorkIdentifier("arxiv", "2001.00001"),)
    )

    outcome = run(resolver, intent)

    assert outcome.decision.status == "unsupported"
    assert outcome.decision.reason_code == "exact_arxiv_requires_authority"
    assert crossref.calls == datacite.calls == []


def test_conflicting_exact_identifiers_abstain_without_network_calls():
    crossref, datacite = SearchProvider(), SearchProvider()
    doi_org = DoiProvider(csl())
    resolver = WorkResolver(
        crossref=crossref, datacite=datacite, doi_org=doi_org
    )
    intent = WorkIntent(
        "conflict",
        identifiers=(
            WorkIdentifier("doi", "10.1000/one"),
            WorkIdentifier("doi", "10.1000/two"),
        ),
    )

    outcome = run(resolver, intent)

    assert outcome.decision.status == "identity_conflict"
    assert outcome.decision.reason_code == "multiple_exact_identifiers"
    assert crossref.calls == datacite.calls == doi_org.calls == []


def test_no_doi_never_becomes_write_eligible():
    item = record("openalex", doi="")
    item.doi = None
    outcome = run(WorkResolver(crossref=SearchProvider([item]), datacite=SearchProvider([]), doi_org=DoiProvider(csl())))
    assert outcome.decision.status == "unsupported"
    assert outcome.decision.reason_code == "unsupported_no_doi"
