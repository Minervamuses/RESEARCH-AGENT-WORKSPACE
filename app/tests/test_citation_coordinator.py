"""Coordinator workflow E2E against a fixture-routed hub (no network)."""

import asyncio
import json

import pytest

from skills.citation.coordinator import CitationCoordinator
from skills.citation.hub import CitationProviderHub
from skills.citation.providers.base import ProviderRecord
from skills.citation.providers.net import FetchResponse
from skills.citation.types import ProviderState
from skills.citation.venue import annotate_venue
from agent.config import AgentConfig

DOI_A = "10.1234/paper-a"
DOI_B = "10.1234/paper-b"

CSL = {
    DOI_A: {
        "DOI": DOI_A,
        "title": "Paper A",
        "author": [{"given": "Ada", "family": "Lovelace"}],
        "issued": {"date-parts": [[2021]]},
        "container-title": "Journal A",
        "type": "journal-article",
    },
    DOI_B: {
        "DOI": DOI_B,
        "title": "Paper B",
        "author": [{"given": "Bob", "family": "Builder"}],
        "issued": {"date-parts": [[2020]]},
        "container-title": "Journal B",
        "type": "journal-article",
    },
}

BIBTEX = {
    DOI_A: (
        "@article{a,\n  title = {Paper A},\n  author = {Lovelace, Ada},\n"
        f"  year = {{2021}},\n  doi = {{{DOI_A}}},\n}}\n"
    ),
    DOI_B: (
        "@article{b,\n  title = {Paper B},\n  author = {Builder, Bob},\n"
        "  year = {2020},\n}\n"  # no DOI: injection path
    ),
}

CROSSREF_ITEMS = [
    {
        "DOI": DOI_A,
        "title": ["Paper A"],
        "author": [{"given": "Ada", "family": "Lovelace"}],
        "issued": {"date-parts": [[2021]]},
        "container-title": ["Journal A"],
        "type": "journal-article",
        "score": 10.0,
    },
    {
        "DOI": DOI_B,
        "title": ["Paper B"],
        "issued": {"date-parts": [[2020]]},
        "type": "journal-article",
        "score": 8.0,
    },
]


class RoutingFetcher:
    """URL-routed fixture transport standing in for httpx."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.crossref_response = FetchResponse(
            status=200,
            body=json.dumps({"message": {"items": CROSSREF_ITEMS}}).encode(),
        )
        self.fail_bibtex = False
        self.fail_csl = False

    async def __call__(self, url: str, headers: dict) -> FetchResponse:
        accept = headers.get("Accept", "")
        self.calls.append((url, accept))
        if "api.crossref.org" in url:
            return self.crossref_response
        if url.startswith("https://doi.org/ra/"):
            return FetchResponse(status=200, body=b'[{"RA": "Crossref"}]')
        if url.startswith("https://doi.org/"):
            doi = url.removeprefix("https://doi.org/")
            if "csl+json" in accept:
                if self.fail_csl:
                    return FetchResponse(status=500)
                body = CSL.get(doi)
                if body is None:
                    return FetchResponse(status=404)
                return FetchResponse(status=200, body=json.dumps(body).encode())
            if "x-bibtex" in accept:
                if self.fail_bibtex:
                    return FetchResponse(status=500)
                text = BIBTEX.get(doi)
                if text is None:
                    return FetchResponse(status=404)
                return FetchResponse(status=200, body=text.encode())
        raise AssertionError(f"unexpected url: {url}")


class StubWebTool:
    def __init__(self, text):
        self.text = text
        self.calls = []

    async def ainvoke(self, args):
        self.calls.append(args)
        return self.text


WEB_TEXT = """**1. Paper C landing page**
URL: https://example.org/paper-c
Description: A web-only result from 2019.
"""


def _coordinator(tmp_path, *, fetcher=None, web_tools=None, llm_factory=None):
    fetcher = fetcher or RoutingFetcher()
    hub = CitationProviderHub(env={}, fetcher=fetcher)
    coordinator = CitationCoordinator(
        hub,
        web_tools=web_tools,
        llm_factory=llm_factory,
        output_dir=tmp_path / "cite",
    )
    return coordinator, fetcher


def test_ranking_mode_defaults_to_lexical_and_env_can_roll_back(monkeypatch):
    monkeypatch.delenv("CITATION_RANKING_MODE", raising=False)
    assert AgentConfig().citation_ranking_mode == "lexical"
    monkeypatch.setenv("CITATION_RANKING_MODE", "rrf")
    assert AgentConfig().citation_ranking_mode == "rrf"


def test_invalid_ranking_mode_fails_fast(tmp_path):
    hub = CitationProviderHub(env={}, fetcher=RoutingFetcher())
    with pytest.raises(ValueError, match="citation_ranking_mode"):
        CitationCoordinator(
            hub,
            config=type("Config", (), {"citation_ranking_mode": "semantic"})(),
            output_dir=tmp_path / "cite",
        )


def test_doi_query_uses_singleton_lookup_only(tmp_path):
    coordinator, fetcher = _coordinator(tmp_path)
    outcome = asyncio.run(coordinator.search(f"https://doi.org/{DOI_A}"))

    assert len(outcome.candidates) == 1
    candidate = outcome.candidates[0]
    assert candidate.doi == DOI_A
    assert candidate.title == "Paper A"
    assert candidate.work_type == "journal-article"
    assert candidate.provider_ids == {"structured": f"structured:{DOI_A}"}
    # No crossref/web call for a DOI-shaped query.
    assert all("api.crossref.org" not in url for url, _ in fetcher.calls)


def test_doi_query_that_does_not_resolve_reports_empty(tmp_path):
    coordinator, _ = _coordinator(tmp_path)
    outcome = asyncio.run(coordinator.search("10.9999/definitely-missing"))
    assert outcome.candidates == []
    assert outcome.provider_states[0].provider == "doi.org"
    assert outcome.provider_states[0].status == "empty"


def test_general_query_runs_structured_providers_and_reports_disabled_openalex(tmp_path):
    coordinator, fetcher = _coordinator(tmp_path)
    outcome = asyncio.run(coordinator.search("paper"))

    assert [c.doi for c in outcome.candidates] == [DOI_A, DOI_B]
    assert [c.work_type for c in outcome.candidates] == [
        "journal-article", "journal-article"
    ]
    assert all(
        c.field_provenance["work_type"] == "crossref"
        for c in outcome.candidates
    )
    providers = {state.provider: state.status for state in outcome.provider_states}
    assert providers["crossref"] == "ok"
    assert providers["openalex"] == "disabled"
    assert outcome.used_web_fallback is False


def test_web_fallback_only_when_structured_is_empty(tmp_path):
    fetcher = RoutingFetcher()
    fetcher.crossref_response = FetchResponse(
        status=200, body=json.dumps({"message": {"items": []}}).encode()
    )
    web_tool = StubWebTool(WEB_TEXT)
    coordinator, _ = _coordinator(
        tmp_path, fetcher=fetcher,
        web_tools={"get-web-search-summaries": web_tool},
    )
    outcome = asyncio.run(coordinator.search("paper c"))
    assert outcome.used_web_fallback is True
    assert len(outcome.candidates) == 1
    assert outcome.candidates[0].title == "Paper C landing page"

    # With structured hits, web is not touched.
    fetcher.crossref_response = FetchResponse(
        status=200, body=json.dumps({"message": {"items": CROSSREF_ITEMS}}).encode()
    )
    outcome2 = asyncio.run(coordinator.search("paper"))
    assert outcome2.used_web_fallback is False
    assert len(web_tool.calls) == 1  # unchanged


def test_more_appends_web_results_keeps_ids_clears_matches(tmp_path):
    web_tool = StubWebTool(WEB_TEXT)
    coordinator, _ = _coordinator(
        tmp_path, web_tools={"get-web-search-summaries": web_tool}
    )
    first = asyncio.run(coordinator.search("paper"))
    ids_before = [c.candidate_id for c in first.candidates]
    select = asyncio.run(coordinator.select(ids_before[0]))
    assert select.matches

    outcome = asyncio.run(coordinator.more())
    # Existing candidate IDs survive; new web candidate appended after them.
    current_ids = [c.candidate_id for c in coordinator.list_candidates()[0]]
    assert current_ids[: len(ids_before)] == ids_before
    assert len(current_ids) == len(ids_before) + 1
    assert outcome.used_web_fallback is True
    assert outcome.updated_groups == 0
    # Selection and matches were cleared: old match id is stale now.
    stale = asyncio.run(coordinator.confirm(select.matches[0].match_id))
    assert stale.status == "invalid_state"
    assert stale.accepted_doi is None


def test_refine_is_non_destructive_stable_and_clears_selection(tmp_path):
    coordinator, fetcher = _coordinator(tmp_path)
    outcome = asyncio.run(coordinator.search("paper"))
    ids_before = [candidate.candidate_id for candidate in outcome.candidates]
    selected = asyncio.run(coordinator.select("c1"))
    assert selected.matches
    calls_before = list(fetcher.calls)

    refined = coordinator.refine(
        keywords=["paper", "a"],
        venues=["journal a", "other"],
        work_types=["journal-article"],
        date_filter=None,
    )

    assert [candidate.candidate_id for candidate in refined.candidates] == ["c1"]
    assert [candidate.candidate_id for candidate in coordinator._candidates] == ids_before
    assert fetcher.calls == calls_before
    listed, pages = coordinator.list_candidates()
    assert [candidate.candidate_id for candidate in listed] == ["c1"]
    assert pages == 1
    assert coordinator.status()["selected"] == "none"
    assert coordinator.status()["matches"] == 0
    assert coordinator.get_candidate("c1") is not None


def test_refine_date_filter_is_fail_closed_for_unknown_year(tmp_path):
    coordinator, _ = _coordinator(tmp_path)
    asyncio.run(coordinator.search("paper"))
    coordinator._candidates.append(type(coordinator._candidates[0])(
        candidate_id="c3",
        workflow_id=coordinator.workflow_id,
        title="Paper without year",
        year=None,
    ))
    coordinator._refresh_candidate_view()

    from skills.citation.types import PublishedDateFilter

    refined = coordinator.refine(
        date_filter=PublishedDateFilter.from_year_range(2020, 2021)
    )

    assert [candidate.candidate_id for candidate in refined.candidates] == ["c1", "c2"]
    assert "c3" not in [candidate.candidate_id for candidate in refined.candidates]


def test_more_reapplies_active_refinement_to_new_candidates(tmp_path):
    web_tool = StubWebTool(WEB_TEXT)
    coordinator, _ = _coordinator(
        tmp_path, web_tools={"get-web-search-summaries": web_tool}
    )
    asyncio.run(coordinator.search("paper"))
    empty = coordinator.refine(keywords=["landing"])
    assert empty.candidates == []

    asyncio.run(coordinator.more())

    listed, _ = coordinator.list_candidates()
    assert [candidate.title for candidate in listed] == ["Paper C landing page"]
    assert listed[0].candidate_id == "c3"


def test_more_groups_distinct_version_without_reidentifying_existing_candidates(
    tmp_path,
):
    coordinator, _ = _coordinator(tmp_path)
    asyncio.run(coordinator.search("paper"))

    async def version_result(query):
        return [ProviderRecord(
            provider="web",
            provider_id="web:paper-a-preprint",
            rank=0,
            title="Paper A",
            authors=["Ada Lovelace"],
            year=2022,
            venue="arXiv",
            doi="10.1234/paper-a-preprint",
            work_type="preprint",
        )], ProviderState("web", "ok", f"query={query!r}")

    coordinator._run_web_search = version_result  # noqa: SLF001
    outcome = asyncio.run(coordinator.more())

    assert outcome.versions_added == 1
    assert outcome.updated_groups == 1
    assert coordinator.get_candidate("c1").doi == DOI_A
    assert coordinator.get_candidate("c3").doi == "10.1234/paper-a-preprint"
    assert coordinator.get_candidate("c1").related_candidate_ids == ["c3"]
    assert [candidate.candidate_id for candidate in coordinator.list_candidates()[0]] == [
        "c1", "c2",
    ]

    # A group-aware refinement can expose the alternate without changing IDs.
    refined = coordinator.refine(venues=["arxiv"])
    assert [candidate.candidate_id for candidate in refined.candidates] == ["c3"]
    reset = coordinator.refine()
    assert [candidate.candidate_id for candidate in reset.candidates] == ["c1", "c2"]


def test_venue_tier_refine_matches_only_catalogued_candidates(tmp_path):
    coordinator, _ = _coordinator(tmp_path)
    asyncio.run(coordinator.search("paper"))
    coordinator._candidates[0].venue = "FPGA"  # noqa: SLF001
    coordinator._candidates[0].venue_annotation = annotate_venue("FPGA")  # noqa: SLF001
    coordinator._refresh_candidate_view()  # noqa: SLF001

    refined = coordinator.refine(venue_tiers=["TOP"])

    assert [candidate.candidate_id for candidate in refined.candidates] == ["c1"]
    assert refined.candidates[0].venue_annotation.tier == "top"


def test_refine_without_constraints_resets_full_view(tmp_path):
    coordinator, _ = _coordinator(tmp_path)
    asyncio.run(coordinator.search("paper"))
    coordinator.refine(venues=["journal a"])

    reset = coordinator.refine()

    assert reset.reset is True
    assert [candidate.candidate_id for candidate in reset.candidates] == ["c1", "c2"]


def test_select_no_doi_candidate_returns_no_doi(tmp_path):
    fetcher = RoutingFetcher()
    fetcher.crossref_response = FetchResponse(
        status=200, body=json.dumps({"message": {"items": []}}).encode()
    )
    web_tool = StubWebTool(WEB_TEXT)
    coordinator, _ = _coordinator(
        tmp_path, fetcher=fetcher,
        web_tools={"get-web-search-summaries": web_tool},
    )
    outcome = asyncio.run(coordinator.search("paper c"))
    [candidate] = outcome.candidates
    select = asyncio.run(coordinator.select(candidate.candidate_id))
    assert select.result is not None
    assert select.result.status == "no_doi"
    assert select.result.accepted_doi is None


def test_select_stale_candidate_returns_invalid_state(tmp_path):
    coordinator, _ = _coordinator(tmp_path)
    asyncio.run(coordinator.search("paper"))
    asyncio.run(coordinator.search("paper"))  # new generation
    select = asyncio.run(coordinator.select("c99"))
    assert select.result.status == "invalid_state"


def test_confirm_happy_path_writes_bundle_and_registers_source(tmp_path):
    coordinator, _ = _coordinator(tmp_path)
    search = asyncio.run(coordinator.search("paper"))
    candidate = search.candidates[0]
    select = asyncio.run(coordinator.select(candidate.candidate_id))
    match = next(m for m in select.matches if m.canonical_doi == DOI_A)
    assert match.registration_agency == "Crossref"

    result = asyncio.run(coordinator.confirm(match.match_id))
    assert result.status == "confirmed"
    assert result.accepted_doi == DOI_A
    assert result.source is not None
    assert result.source.verification_level == "identity_verified"
    assert result.verification.passed

    bundle = tmp_path / "cite"
    dirs = [p for p in bundle.iterdir() if p.is_dir()]
    assert len(dirs) == 1
    assert (dirs[0] / "reference.bib").exists()
    sidecar = json.loads((dirs[0] / "citation.json").read_text(encoding="utf-8"))
    assert sidecar["doi"] == DOI_A
    assert sidecar["source_ref"]["source_id"] == result.source.source_id
    # workflow completed, registry survives
    assert coordinator.list_candidates()[0] == []
    assert coordinator.registry.get(result.source.source_id) is not None


def test_confirm_injects_missing_bibtex_doi_with_code(tmp_path):
    coordinator, _ = _coordinator(tmp_path)
    search = asyncio.run(coordinator.search("paper"))
    candidate = next(c for c in search.candidates if c.doi == DOI_B)
    select = asyncio.run(coordinator.select(candidate.candidate_id))
    result = asyncio.run(coordinator.confirm(select.matches[0].match_id))

    assert result.status == "confirmed"
    assert "doi_injected_from_verified_lookup" in result.verification.codes
    bib_text = (tmp_path / "cite").rglob("reference.bib")
    content = next(bib_text).read_text(encoding="utf-8")
    assert DOI_B in content


def test_confirm_provider_failure_keeps_resolution_for_retry(tmp_path):
    fetcher = RoutingFetcher()
    coordinator, _ = _coordinator(tmp_path, fetcher=fetcher)
    search = asyncio.run(coordinator.search("paper"))
    candidate = search.candidates[0]
    select = asyncio.run(coordinator.select(candidate.candidate_id))
    match = next(m for m in select.matches if m.canonical_doi == DOI_A)

    fetcher.fail_bibtex = True
    failed = asyncio.run(coordinator.confirm(match.match_id))
    assert failed.status == "provider_failed"
    assert failed.accepted_doi is None
    assert not list((tmp_path / "cite").rglob("reference.bib"))

    fetcher.fail_bibtex = False
    retried = asyncio.run(coordinator.confirm(match.match_id))
    assert retried.status == "confirmed"
    assert retried.attempts == 2
    sidecar = json.loads(
        next((tmp_path / "cite").rglob("citation.json")).read_text(encoding="utf-8")
    )
    assert sidecar["previous_attempt_failure_codes"] == ["provider_failed"]


def test_same_doi_reconfirm_is_idempotent(tmp_path):
    coordinator, _ = _coordinator(tmp_path)
    for _ in range(2):
        search = asyncio.run(coordinator.search("paper"))
        candidate = search.candidates[0]
        select = asyncio.run(coordinator.select(candidate.candidate_id))
        match = next(m for m in select.matches if m.canonical_doi == DOI_A)
        result = asyncio.run(coordinator.confirm(match.match_id))
        assert result.status == "confirmed"
    bundles = [p for p in (tmp_path / "cite").iterdir() if p.is_dir()]
    assert len(bundles) == 1
    assert "reused" in result.message


def test_cancel_invalidates_workflow(tmp_path):
    coordinator, _ = _coordinator(tmp_path)
    asyncio.run(coordinator.search("paper"))
    cancelled = coordinator.cancel()
    assert cancelled.status == "cancelled"
    assert coordinator.list_candidates()[0] == []
    select = asyncio.run(coordinator.select("c1"))
    assert select.result.status == "invalid_state"


def test_sessions_are_isolated_but_share_hub(tmp_path):
    fetcher = RoutingFetcher()
    hub = CitationProviderHub(env={}, fetcher=fetcher)
    a = CitationCoordinator(hub, output_dir=tmp_path / "a")
    b = CitationCoordinator(hub, output_dir=tmp_path / "b")
    asyncio.run(a.search("paper"))
    assert a.list_candidates()[0] != []
    assert b.list_candidates()[0] == []
    assert b.status()["workflow_id"] == "none"


def test_registry_has_no_user_supplied_registration_surface(tmp_path):
    coordinator, _ = _coordinator(tmp_path)
    assert not hasattr(coordinator.registry, "register_user_source")


def test_prompt_registry_caps_at_20_most_recent(tmp_path):
    from skills.citation.types import SourceRef

    coordinator, _ = _coordinator(tmp_path)
    for i in range(25):
        coordinator.registry.register(SourceRef(
            source_id=f"src-{i:02d}",
            doi=f"10.1234/source-{i:02d}",
            title=f"Paper {i:02d}",
            verification_level="identity_verified",
        ))
    prompt = coordinator.registry.prompt_sources()
    assert len(prompt) == 20
    assert prompt[0].doi == "10.1234/source-24"


def test_expansion_queries_hit_providers(tmp_path):
    class StubLLM:
        async def ainvoke(self, messages):
            class R:
                content = '["alternative phrasing"]'
            return R()

    coordinator, fetcher = _coordinator(tmp_path, llm_factory=lambda: StubLLM())
    outcome = asyncio.run(coordinator.search("original"))
    assert outcome.queries == ["original", "alternative phrasing"]
    crossref_calls = [url for url, _accept in fetcher.calls if "api.crossref.org" in url]
    assert len(crossref_calls) == 2


def test_date_filter_native_params_and_fail_closed_post_filter(tmp_path):
    from skills.citation.types import PublishedDateFilter

    fetcher = RoutingFetcher()
    # Paper A (2021) is in-window; Paper B (2020) is out; the third item has
    # no year and must be dropped fail-closed despite matching otherwise.
    fetcher.crossref_response = FetchResponse(
        status=200,
        body=json.dumps({"message": {"items": [
            CROSSREF_ITEMS[0],
            CROSSREF_ITEMS[1],
            {"DOI": "10.1234/paper-undated", "title": ["Paper Undated"], "score": 5.0},
        ]}}).encode(),
    )
    coordinator, fetcher = _coordinator(tmp_path, fetcher=fetcher)
    date_filter = PublishedDateFilter.from_year_range(2021, 2026)
    outcome = asyncio.run(coordinator.search("papers", date_filter=date_filter))

    crossref_url = next(url for url, _a in fetcher.calls if "api.crossref.org" in url)
    assert "filter=from-pub-date%3A2021-01-01%2Cuntil-pub-date%3A2026-12-31" in crossref_url
    assert [c.title for c in outcome.candidates] == ["Paper A"]
    assert outcome.candidates[0].candidate_id == "c1"  # renumbered after filtering
    assert outcome.date_filtered_out == 2
    assert coordinator.status()["date_filter"] == "2021-01-01 .. 2026-12-31"


def test_date_filter_applies_to_doi_query_and_more(tmp_path):
    from skills.citation.types import PublishedDateFilter

    web = StubWebTool(WEB_TEXT)
    coordinator, _ = _coordinator(
        tmp_path, web_tools={"get-web-search-summaries": web}
    )
    # DOI-shaped query: Paper A is 2021, window excludes it -> zero candidates.
    outcome = asyncio.run(coordinator.search(
        DOI_A, date_filter=PublishedDateFilter.from_year_range(2022, None)
    ))
    assert outcome.candidates == []
    assert outcome.date_filtered_out == 1

    # `more` inherits the workflow's filter: the undated web hit is dropped.
    coordinator2, _ = _coordinator(tmp_path, web_tools={"get-web-search-summaries": web})
    asyncio.run(coordinator2.search(
        "papers", date_filter=PublishedDateFilter.from_year_range(2021, None)
    ))
    more_outcome = asyncio.run(coordinator2.more("papers"))
    assert more_outcome.candidates == []
    assert more_outcome.date_filtered_out == 1
