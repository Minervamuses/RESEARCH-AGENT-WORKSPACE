"""The citation_workflow tool: validation, delegation, busy guard, turn rule."""

import asyncio
import json
from dataclasses import replace

from langchain_core.messages import ToolMessage

from agent.turn_safety import find_tool_protocol_artifact, final_response_problem
from skills.citation.coordinator import (
    CitationCoordinator,
    RefineOutcome,
    SearchOutcome,
)
from skills.citation.doi import extract_doi_candidates
from skills.citation.gate import check_citations
from skills.citation.hub import CitationProviderHub
from skills.citation.tool import (
    TOOL_NAME,
    create_citation_workflow_tool,
    format_refine_outcome,
    format_search_outcome,
)
from skills.citation.types import CitationCandidate, ConfirmReceipt

from tests.test_citation_coordinator import DOI_A, RoutingFetcher


class ToolHarness:
    """One session-shaped fixture: coordinator + settable turn counter."""

    def __init__(self, tmp_path, fetcher=None):
        self.fetcher = fetcher or RoutingFetcher()
        hub = CitationProviderHub(env={}, fetcher=self.fetcher)
        self.coordinator = CitationCoordinator(hub, output_dir=tmp_path / "cite")
        self.turn = 0
        self.user_input = ""
        self.tool = create_citation_workflow_tool(
            coordinator_getter=lambda: self.coordinator,
            turn_getter=lambda: self.turn,
            user_input_getter=lambda: self.user_input,
        )

    def run(self, **kwargs) -> str:
        return asyncio.run(self.tool.ainvoke(kwargs))


def test_tool_name_and_schema_fields():
    tool = create_citation_workflow_tool(
        coordinator_getter=lambda: None, turn_getter=lambda: 0,
        user_input_getter=lambda: "",
    )
    assert tool.name == TOOL_NAME
    fields = set(tool.args_schema.model_fields)
    assert fields == {
        "action", "query", "identifier", "page",
        "keywords", "venues", "work_types",
        "published_within_years", "year_from", "year_to",
    }


def test_search_formats_candidates_and_provider_states(tmp_path):
    harness = ToolHarness(tmp_path)
    message = harness.run(action="search", query="paper")
    assert "found 2 candidate(s)" in message
    assert "[c1]" in message
    assert "provider crossref: ok" in message
    assert "provider openalex: disabled" in message


def test_search_presents_only_first_ten_candidates():
    outcome = SearchOutcome(
        candidates=[
            CitationCandidate(
                candidate_id=f"c{index}",
                workflow_id="wf-1",
                title=f"Paper {index}",
            )
            for index in range(1, 13)
        ]
    )

    message = format_search_outcome(outcome)

    assert "found 12 candidate(s)" in message
    assert "Shortlist: 10 of 12 candidate(s)" in message
    assert "[c1]" in message
    assert "[c10]" in message
    assert "[c11]" not in message
    assert "action=refine" in message
    assert "action=list" not in message
    assert len(outcome.candidates) == 12


def test_refine_presents_only_first_ten_candidates():
    candidates = [
        CitationCandidate(
            candidate_id=f"c{index}",
            workflow_id="wf-1",
            title=f"Paper {index}",
        )
        for index in range(1, 13)
    ]

    message = format_refine_outcome(RefineOutcome(
        candidates=candidates,
        pool_size=20,
    ))

    assert "12 match(es) from pool of 20" in message
    assert "Shortlist: 10 of 12 candidate(s)" in message
    assert "[c10]" in message
    assert "[c11]" not in message


def test_search_requires_query_and_rejects_dual_date_modes(tmp_path):
    harness = ToolHarness(tmp_path)
    assert "requires query" in harness.run(action="search")
    both = harness.run(
        action="search", query="q", published_within_years=5, year_from=2020,
    )
    assert "mutually exclusive" in both
    # No provider call was made for either rejected input.
    assert harness.fetcher.calls == []


def test_year_range_search_builds_filter_and_filters_candidates(tmp_path):
    harness = ToolHarness(tmp_path)
    message = harness.run(action="search", query="paper", year_from=2021)
    # Paper B (2020) is dropped fail-closed; Paper A (2021) survives.
    assert "found 1 candidate(s)" in message
    assert "dropped by the date filter" in message
    status = harness.run(action="status")
    assert "date_filter: 2021-01-01 .. ..." in status


def test_explain_returns_public_contract_without_provider_calls(tmp_path):
    harness = ToolHarness(tmp_path)

    message = harness.run(action="explain")

    assert "doi.org" in message
    assert "content negotiation" in message
    assert "never written by the model" in message
    assert "reference.bib" in message
    assert "citation.json" in message
    assert "never inside the project source tree" in message
    assert str(tmp_path / "cite") in message
    assert "action=sources" in message
    assert harness.fetcher.calls == []


def test_explain_output_is_leak_safe_and_doi_free(tmp_path):
    harness = ToolHarness(tmp_path)
    message = harness.run(action="explain")
    tool_names = [
        "citation_workflow",
        "bash",
        "read_file",
        "rag_explore",
        "rag_search",
        "rag_get_context",
        "recall_history",
    ]

    assert find_tool_protocol_artifact(message, tool_names=tool_names) is None
    assert final_response_problem(message, tool_names=tool_names) is None
    assert extract_doi_candidates(message) == []
    assert check_citations(
        message,
        verified_source_ids=frozenset(),
        citation_active=True,
        user_input="workflow 怎麼運作?",
    ) == []
    assert check_citations(
        message,
        verified_source_ids=frozenset(),
        citation_active=False,
        user_input="workflow 怎麼運作?",
    ) == []


def test_explain_carries_no_artifact_and_rejects_page(tmp_path):
    harness = ToolHarness(tmp_path)
    assert "page only applies" in harness.run(action="explain", page=2)

    message = asyncio.run(harness.tool.ainvoke({
        "name": TOOL_NAME,
        "args": {"action": "explain"},
        "id": "explain-1",
        "type": "tool_call",
    }))

    assert isinstance(message, ToolMessage)
    assert message.artifact is None


def test_published_within_years_computes_window_from_today(tmp_path):
    from datetime import datetime, timezone

    harness = ToolHarness(tmp_path)
    harness.run(action="search", query="paper", published_within_years=5)
    today = datetime.now(timezone.utc).date()
    filt = harness.coordinator._date_filter  # noqa: SLF001
    assert filt is not None
    assert filt.date_to == today.isoformat()
    assert filt.year_from == today.year - 5


def test_date_args_rejected_outside_search_or_refine(tmp_path):
    harness = ToolHarness(tmp_path)
    harness.run(action="search", query="paper")
    message = harness.run(action="more", published_within_years=3)
    assert "date filters only apply" in message


def test_refine_filters_existing_pool_and_resets_without_provider_calls(tmp_path):
    harness = ToolHarness(tmp_path)
    harness.run(action="search", query="paper")
    calls_before = list(harness.fetcher.calls)

    refined = harness.run(
        action="refine",
        keywords=["paper", "a"],
        venues=["journal a", "unused"],
        work_types=["journal-article"],
        year_from=2021,
        year_to=2021,
    )
    assert "1 match(es) from pool of 2" in refined
    assert "[c1]" in refined
    assert "[c2]" not in refined
    assert harness.fetcher.calls == calls_before

    listed = harness.run(action="list")
    assert "[c1]" in listed
    assert "[c2]" not in listed

    reset = harness.run(action="refine")
    assert "refinement reset" in reset
    assert "[c1]" in reset and "[c2]" in reset


def test_refine_fields_are_rejected_for_other_actions(tmp_path):
    harness = ToolHarness(tmp_path)
    message = harness.run(action="search", query="paper", keywords=["x"])
    assert "only apply to action='refine'" in message


def test_identifier_actions_require_identifier(tmp_path):
    harness = ToolHarness(tmp_path)
    for action in ("show", "select", "confirm", "source"):
        assert "requires identifier" in harness.run(action=action)


def test_select_then_same_turn_confirm_is_refused(tmp_path):
    harness = ToolHarness(tmp_path)
    harness.run(action="search", query="paper")
    selected = harness.run(action="select", identifier="c1")
    assert "Confirmable matches" in selected
    assert "[m1]" in selected

    refused = harness.run(action="confirm", identifier="m1")
    assert "confirm refused" in refused
    # Nothing was written.
    assert not list((tmp_path / "cite").glob("*/reference.bib"))


def test_confirm_in_later_user_turn_writes_bundle(tmp_path):
    harness = ToolHarness(tmp_path)
    harness.run(action="search", query="paper")
    harness.run(action="select", identifier="c1")
    harness.turn += 1  # the user replied in a new turn
    harness.user_input = "確認 m1"

    confirmed = harness.run(action="confirm", identifier="m1")
    assert "citation confirmed" in confirmed
    assert f"DOI: `{DOI_A}`" in confirmed
    assert "[[cite:src-" in confirmed
    bundles = list((tmp_path / "cite").glob("*/reference.bib"))
    assert len(bundles) == 1

    sources = harness.run(action="sources")
    assert "identity_verified" in sources
    source_id = json.loads(
        next((tmp_path / "cite").glob("*/citation.json")).read_text(
            encoding="utf-8"
        )
    )["source_ref"]["source_id"]
    detail = harness.run(action="source", identifier=source_id)
    assert "re-activated" in detail


def test_confirm_tool_call_carries_structured_receipt_artifact(tmp_path):
    harness = ToolHarness(tmp_path)
    harness.run(action="search", query="paper")
    harness.run(action="select", identifier="c1")
    harness.turn += 1
    harness.user_input = "儲存"

    message = asyncio.run(harness.tool.ainvoke({
        "name": TOOL_NAME,
        "args": {"action": "confirm", "identifier": "m1"},
        "id": "confirm-1",
        "type": "tool_call",
    }))

    assert isinstance(message, ToolMessage)
    receipt = ConfirmReceipt.from_artifact(message.artifact)
    assert receipt.source_id.startswith("src-")
    assert receipt.accepted_doi == DOI_A
    assert receipt.bundle_path.endswith(message.artifact["bundle_path"].split("/")[-1])


def test_confirm_requires_current_user_approval_and_matching_identifier(tmp_path):
    harness = ToolHarness(tmp_path)
    harness.run(action="search", query="paper")
    harness.run(action="select", identifier="c1")
    harness.turn += 1

    harness.user_input = "這篇在說什麼"
    assert "confirm refused" in harness.run(action="confirm", identifier="m1")
    harness.user_input = "不要儲存"
    assert "confirm refused" in harness.run(action="confirm", identifier="m1")
    assert not list((tmp_path / "cite").glob("*/reference.bib"))


def test_multiple_matches_require_explicit_matching_m_id(tmp_path):
    harness = ToolHarness(tmp_path)
    harness.run(action="search", query="paper")
    harness.run(action="select", identifier="c1")
    first = harness.coordinator.pending_matches()[0]
    harness.coordinator._matches["m2"] = replace(first, match_id="m2")  # noqa: SLF001
    harness.turn += 1

    harness.user_input = "就這篇"
    assert "multiple live matches" in harness.run(
        action="confirm", identifier="m1"
    )
    harness.user_input = "確認 m2"
    assert "tool match id differs" in harness.run(
        action="confirm", identifier="m1"
    )
    confirmed = harness.run(action="confirm", identifier="m2")
    assert "citation confirmed" in confirmed
    assert len(list((tmp_path / "cite").glob("*/reference.bib"))) == 1


def test_preconfirm_formatters_do_not_expose_raw_doi(tmp_path):
    harness = ToolHarness(tmp_path)
    searched = harness.run(action="search", query="paper")
    assert DOI_A not in searched
    selected = harness.run(action="select", identifier="c1")
    assert DOI_A not in selected
    assert "use mX ids" in selected


def test_show_detail_is_marked_metadata_only(tmp_path):
    harness = ToolHarness(tmp_path)
    harness.run(action="search", query="paper")

    detail = harness.run(action="show", identifier="c1")

    assert "Grounding: metadata and snippet only" in detail
    assert "DOI is withheld" in detail
    assert DOI_A not in detail


def test_new_search_resets_the_select_turn_rule(tmp_path):
    harness = ToolHarness(tmp_path)
    harness.run(action="search", query="paper")
    harness.run(action="select", identifier="c1")
    harness.turn += 1
    # A fresh search invalidates the old matches; the approval guard refuses
    # before the writer can see a stale id.
    harness.run(action="search", query="paper")
    stale = harness.run(action="confirm", identifier="m1")
    assert "confirm refused" in stale


def test_cancel_and_stale_candidate_pass_through_coordinator_errors(tmp_path):
    harness = ToolHarness(tmp_path)
    harness.run(action="search", query="paper")
    cancelled = harness.run(action="cancel")
    assert "cancelled" in cancelled
    stale = harness.run(action="select", identifier="c1")
    assert "invalid_state" in stale


def test_concurrent_workflow_calls_get_busy_error(tmp_path):
    import skills.citation.tool as tool_module

    class SlowCoordinator:
        async def search(self, query, *, date_filter=None):
            await asyncio.sleep(0.05)
            from skills.citation.coordinator import SearchOutcome

            return SearchOutcome()

    harness_tool = tool_module.create_citation_workflow_tool(
        coordinator_getter=lambda: SlowCoordinator(),
        turn_getter=lambda: 0,
        user_input_getter=lambda: "",
    )

    async def _race():
        first = asyncio.create_task(
            harness_tool.ainvoke({"action": "search", "query": "a"})
        )
        await asyncio.sleep(0.01)
        second = await harness_tool.ainvoke({"action": "search", "query": "b"})
        return await first, second

    first, second = asyncio.run(_race())
    assert "found 0 candidate(s)" in first
    assert "busy" in second


def test_page_validation(tmp_path):
    harness = ToolHarness(tmp_path)
    assert "page must be >= 1" in harness.run(action="list", page=0)
    assert "page only applies" in harness.run(action="status", page=2)


def test_session_binds_citation_tool_as_skill_tool(monkeypatch, tmp_path):
    """ChatSession creates the tool and hands it to build_graph(skill_tools=…)."""
    from agent.config import AgentConfig
    from agent.session import ChatSession
    from tests.conftest import FakeHistoryStore, make_astream_graph

    captured: dict = {}

    def fake_build_graph(_cfg, extra_tools=None, history_store=None, **kwargs):
        captured.update(kwargs)
        return make_astream_graph()

    monkeypatch.setattr("agent.session.build_graph", fake_build_graph)
    monkeypatch.setattr("agent.session.find_app_root", lambda: tmp_path)
    session = ChatSession(
        AgentConfig(persist_dir=str(tmp_path / "p")),
        history_store=FakeHistoryStore(),
    )
    skill_tools = captured.get("skill_tools")
    assert skill_tools is not None and len(skill_tools) == 1
    assert skill_tools[0] is session.citation_workflow_tool
    assert session.citation_workflow_tool.name == TOOL_NAME
