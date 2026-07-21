"""Full-stack citation turns: real session, real graph, fixture providers."""

import asyncio
import json
import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool

from conftest import FakeHistoryStore

from agent.config import AgentConfig
from agent.session import ChatSession
from skills.citation.hub import CitationProviderHub
from skills.citation.service import CitationService

from tests.citation_fixtures import RoutingFetcher


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


def _seed_fixture_service(session, tmp_path):
    hub = CitationProviderHub(env={}, fetcher=RoutingFetcher())
    session._citation_service = CitationService(hub, output_dir=tmp_path / "cite")
    return session._citation_service


def test_citation_turn_runs_stateless_search_with_year_filter(
    monkeypatch, tmp_path
):
    responses = [
        _workflow_call({
            "action": "search",
            "query": "HPC",
            "year_from": 2021,
        }),
        AIMessage(content="Paper A — Ada Lovelace — 2021 — Journal A — journal-article。"),
    ]
    session = _make_session(monkeypatch, tmp_path, responses)
    session.activate_skill("citation")
    _seed_fixture_service(session, tmp_path)

    answer = asyncio.run(session.turn("幫我尋找近5年內關於HPC的論文"))

    assert "Paper A" in answer and "Ada Lovelace" in answer and "2021" in answer
    assert [c["name"] for c in session.last_tool_calls] == ["citation_workflow"]
    assert "c1" not in answer and "m1" not in answer


def test_forged_workflow_call_outside_skill_is_denied_end_to_end(
    monkeypatch, tmp_path
):
    """No active skill: the graph must answer the forged call with a policy
    error ToolMessage and never build the citation service."""
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
    assert session._citation_service is None  # noqa: SLF001


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
    assert session._citation_service is None  # noqa: SLF001


def test_search_and_one_work_intent_save_in_one_user_turn_end_to_end(monkeypatch, tmp_path):
    responses = [
        _workflow_call({"action": "search", "query": "paper"}),
        _workflow_call({
            "action": "save",
            "works": [{
                "requested_label": "Paper A",
                "title": "Paper A",
                "authors": ["Ada Lovelace"],
                "year": 2021,
                "venue": "Journal A",
                "work_type": "journal-article"
            }]
        }, "call-2"),
        AIMessage(content="已保存來源。"),
    ]
    session = _make_session(monkeypatch, tmp_path, responses)
    session.activate_skill("citation")
    _seed_fixture_service(session, tmp_path)

    receipt = asyncio.run(session.turn("幫我找出並保存 2021 年 Ada Lovelace 的 Paper A"))
    bundles = list((tmp_path / "cite").glob("*/reference.bib"))
    assert len(bundles) == 1
    assert "引用保存結果" in receipt
    assert "source ID" in receipt
    assert str(bundles[0].parent) in receipt
    sidecar = json.loads((bundles[0].parent / "citation.json").read_text())
    assert "bundle_path" not in sidecar["source_ref"]
    refs = session.citation_service.registry.list()
    assert [r.verification_level for r in refs] == ["doi_identity_verified"]
    # The deterministic receipt, not the model's generic sentence, is the
    # prompt-visible fact on the next turn.
    assert session.recent_turns[-1].assistant_output == receipt
