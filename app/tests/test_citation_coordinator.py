"""Coordinator workflow E2E against a fixture-routed hub (no network)."""

import asyncio
import json

from skills.citation.coordinator import CitationCoordinator
from skills.citation.hub import CitationProviderHub
from skills.citation.providers.net import FetchResponse

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
        "score": 10.0,
    },
    {
        "DOI": DOI_B,
        "title": ["Paper B"],
        "issued": {"date-parts": [[2020]]},
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


def test_doi_query_uses_singleton_lookup_only(tmp_path):
    coordinator, fetcher = _coordinator(tmp_path)
    outcome = asyncio.run(coordinator.search(f"https://doi.org/{DOI_A}"))

    assert len(outcome.candidates) == 1
    candidate = outcome.candidates[0]
    assert candidate.doi == DOI_A
    assert candidate.title == "Paper A"
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
    # Selection and matches were cleared: old match id is stale now.
    stale = asyncio.run(coordinator.confirm(select.matches[0].match_id))
    assert stale.status == "invalid_state"
    assert stale.accepted_doi is None


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


def test_user_source_registration_rules(tmp_path):
    coordinator, _ = _coordinator(tmp_path)
    ref = coordinator.registry.register_user_source("doi:10.1234/user-given")
    assert ref is not None
    assert ref.verification_level == "user_supplied_unverified"
    assert ref.doi == "10.1234/user-given"

    url_ref = coordinator.registry.register_user_source("https://example.org/x")
    assert url_ref is not None and url_ref.doi is None

    assert coordinator.registry.register_user_source("just words") is None
    # Idempotent for the same input.
    again = coordinator.registry.register_user_source("doi:10.1234/user-given")
    assert again.source_id == ref.source_id


def test_prompt_registry_caps_at_20_most_recent(tmp_path):
    coordinator, _ = _coordinator(tmp_path)
    for i in range(25):
        coordinator.registry.register_user_source(f"10.1234/source-{i:02d}")
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
