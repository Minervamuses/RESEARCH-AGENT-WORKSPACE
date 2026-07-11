"""Full-stack citation turns: real session, real graph, fixture providers."""

import asyncio
from datetime import datetime, timezone

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool

from conftest import FakeHistoryStore

from agent.config import AgentConfig
from agent.session import ChatSession
from skills.citation.coordinator import CitationCoordinator
from skills.citation.hub import CitationProviderHub

from tests.test_citation_coordinator import CROSSREF_ITEMS, RoutingFetcher


@tool("rag_search")
def _rag_search(query: str) -> str:
    """Search stub."""
    return query


@tool("recall_history")
def _recall_history(query: str) -> str:
    """Recall stub."""
    return query


class ScriptedModel:
    """Chat model whose bound invoke pops scripted AIMessages."""

    def __init__(self, responses):
        self.responses = list(responses)

    def bind_tools(self, _tools):
        model = self

        class Bound:
            def invoke(self, _messages):
                return model.responses.pop(0)

        return Bound()

    def invoke(self, _messages):
        return self.responses.pop(0)


def _workflow_call(args, call_id="call-1"):
    return AIMessage(
        content="",
        tool_calls=[{
            "name": "citation_workflow",
            "args": args,
            "id": call_id,
            "type": "tool_call",
        }],
    )


def _make_session(monkeypatch, tmp_path, responses):
    monkeypatch.setattr(
        "agent.graph.get_chat_model", lambda _cfg: ScriptedModel(responses)
    )
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools", lambda _cfg: [_rag_search]
    )
    monkeypatch.setattr(
        "agent.tools.inventory.create_history_tool",
        lambda _cfg, store=None: _recall_history,
    )
    monkeypatch.setattr("agent.session.find_app_root", lambda: tmp_path)
    cfg = AgentConfig(persist_dir=str(tmp_path / "persist"))
    return ChatSession(cfg, history_store=FakeHistoryStore())


def _seed_fixture_coordinator(session, tmp_path):
    hub = CitationProviderHub(env={}, fetcher=RoutingFetcher())
    session._citation_coordinator = CitationCoordinator(
        hub, output_dir=tmp_path / "cite"
    )
    return session._citation_coordinator


def test_citation_turn_runs_workflow_tool_with_five_year_filter(
    monkeypatch, tmp_path
):
    """'近5年' natural-language turn: the model calls the tool with
    published_within_years=5, the tool executes through the policy node,
    and the workflow ends with a structured five-year filter applied."""
    responses = [
        _workflow_call({
            "action": "search",
            "query": "HPC",
            "published_within_years": 5,
        }),
        AIMessage(content="這裡是近5年的候選論文清單，請選擇。"),
    ]
    session = _make_session(monkeypatch, tmp_path, responses)
    session.activate_skill("citation")
    coordinator = _seed_fixture_coordinator(session, tmp_path)

    answer = asyncio.run(session.turn("幫我尋找近5年內關於HPC的論文"))

    assert answer == "這裡是近5年的候選論文清單，請選擇。"
    assert [c["name"] for c in session.last_tool_calls] == ["citation_workflow"]
    filt = coordinator._date_filter  # noqa: SLF001
    assert filt is not None
    today = datetime.now(timezone.utc).date()
    assert filt.year_to == today.year
    assert filt.year_from == today.year - 5
    assert filt.date_to == today.isoformat()
    # Fail-closed filtering applied to the fixture candidates (2021 / 2020).
    expected = [c for c in CROSSREF_ITEMS
                if c["issued"]["date-parts"][0][0] >= filt.year_from]
    assert len(coordinator.list_candidates()[0]) == len(expected)


def test_forged_workflow_call_outside_skill_is_denied_end_to_end(
    monkeypatch, tmp_path
):
    """No active skill: the graph must answer the forged call with a policy
    error ToolMessage and never build the Coordinator."""
    responses = [
        _workflow_call({"action": "search", "query": "HPC"}),
        AIMessage(content="fallback answer"),
    ]
    session = _make_session(monkeypatch, tmp_path, responses)

    result = asyncio.run(session._run_graph_turn("查 HPC 論文"))

    denials = [
        m for m in result.new_messages
        if isinstance(m, ToolMessage) and m.status == "error"
    ]
    assert len(denials) == 1
    assert "tool not available" in denials[0].content
    assert result.answer == "fallback answer"
    assert session._citation_coordinator is None  # noqa: SLF001


def test_workflow_call_under_other_skill_is_denied_end_to_end(
    monkeypatch, tmp_path
):
    responses = [
        _workflow_call({"action": "search", "query": "HPC"}),
        AIMessage(content="paper-writing answer"),
    ]
    session = _make_session(monkeypatch, tmp_path, responses)
    session.activate_skill("academic-paper-writing")

    result = asyncio.run(session._run_graph_turn("查 HPC 論文"))

    denials = [
        m for m in result.new_messages
        if isinstance(m, ToolMessage) and m.status == "error"
    ]
    assert len(denials) == 1
    assert "tool not available" in denials[0].content
    assert session._citation_coordinator is None  # noqa: SLF001


def test_select_then_confirm_across_user_turns_end_to_end(monkeypatch, tmp_path):
    """Cross-turn confirm through the real session turn counter: same-turn
    confirm is refused; the next user turn's confirm writes the bundle."""
    responses = [
        # turn 1: search then present
        _workflow_call({"action": "search", "query": "paper"}),
        AIMessage(content="請選擇候選。"),
        # turn 2: select, then an over-eager same-turn confirm, then present
        _workflow_call({"action": "select", "identifier": "c1"}),
        _workflow_call({"action": "confirm", "identifier": "m1"}, "call-2"),
        AIMessage(content="請確認 m1。"),
        # turn 3: the user confirmed -> confirm succeeds
        _workflow_call({"action": "confirm", "identifier": "m1"}, "call-3"),
        AIMessage(content="已保存來源。"),
    ]
    session = _make_session(monkeypatch, tmp_path, responses)
    session.activate_skill("citation")
    _seed_fixture_coordinator(session, tmp_path)

    asyncio.run(session.turn("幫我找 paper"))
    asyncio.run(session.turn("選 c1"))
    # Same-turn confirm was refused: nothing on disk yet.
    assert not list((tmp_path / "cite").glob("*/reference.bib"))
    hint = session._build_citation_confirmation_hint("儲存")  # noqa: SLF001
    assert hint is not None and "identifier=m1" in hint.content

    receipt = asyncio.run(session.turn("儲存"))
    bundles = list((tmp_path / "cite").glob("*/reference.bib"))
    assert len(bundles) == 1
    assert "引用已確認並保存" in receipt
    assert "source ID" in receipt
    assert str(bundles[0].parent) in receipt
    refs = session.citation_coordinator.registry.list()
    assert [r.verification_level for r in refs] == ["identity_verified"]
    # The deterministic receipt, not the model's generic sentence, is the
    # prompt-visible fact on the next turn.
    assert session.recent_turns[-1].assistant_output == receipt
    assert any(
        "Citation confirmation intent" in str(message.content)
        for message in session._prompt_history()  # noqa: SLF001
    ) is False
