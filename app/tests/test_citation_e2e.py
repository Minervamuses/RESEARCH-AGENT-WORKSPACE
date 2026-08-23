"""Citation journeys through the real graph, policy node, tool, and service."""

import asyncio
import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool

from conftest import FakeHistoryStore

from agent.config import AgentConfig
from agent.session import ChatSession
from skills.citation.hub import CitationProviderHub
from skills.citation.providers.net import FetchResponse
from skills.citation.service import CitationService
from skills.citation.types import (
    SAVE_BATCH_KIND,
    SAVE_BATCH_SCHEMA_VERSION,
    SaveBatchOutcome,
)
from tests.citation_fixtures import DOI_A, RoutingFetcher


@tool("rag_search")
def _rag_search(query: str) -> str:
    """Search stub not invoked by these citation journeys."""
    return query


@tool("recall_history")
def _recall_history(query: str) -> str:
    """History stub not invoked by these citation journeys."""
    return query


def _workflow_call(args: dict, call_id: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{
            "name": "citation_workflow",
            "args": args,
            "id": call_id,
            "type": "tool_call",
        }],
    )


def _workflow_results(messages) -> list[ToolMessage]:
    return [
        message
        for message in messages
        if isinstance(message, ToolMessage)
        and message.name == "citation_workflow"
    ]


def _save_call_from_search_result(
    message: ToolMessage,
    *,
    call_id: str,
) -> AIMessage:
    if message.status != "success":
        raise AssertionError("search tool call failed")
    record_line = next(
        (
            line
            for line in message.content.splitlines()
            if line.startswith("- Paper A |")
        ),
        None,
    )
    if record_line is None:
        raise AssertionError("Paper A was not present in the production search result")
    fields = [field.strip() for field in record_line[2:].split(" | ")]
    doi_field = next((field for field in fields if field.startswith("DOI: ")), None)
    if len(fields) < 5 or doi_field is None:
        raise AssertionError("search result omitted saveable bibliographic metadata")
    title, authors_text, year_text, venue, work_type = fields[:5]
    authors = [author.strip() for author in authors_text.split(",") if author.strip()]
    return _workflow_call(
        {
            "action": "save",
            "works": [{
                "requested_label": title,
                "title": title,
                "authors": authors,
                "year": int(year_text),
                "venue": venue,
                "work_type": work_type,
                "identifiers": [{
                    "kind": "doi",
                    "value": doi_field.removeprefix("DOI: "),
                }],
            }],
        },
        call_id,
    )


class _SearchSaveModel:
    """Select from search output and cite only a decoded save receipt."""

    def __init__(self):
        self.bound_tool_names: list[list[str]] = []
        self.search_message: ToolMessage | None = None
        self.save_message: ToolMessage | None = None
        self.receipt = None

    def bind_tools(self, tools):
        self.bound_tool_names.append([tool.name for tool in tools])
        return self

    def invoke(self, messages):
        results = _workflow_results(messages)
        if not results:
            return _workflow_call(
                {
                    "action": "search",
                    "query": "Paper A",
                    "year_from": 2021,
                    "year_to": 2021,
                },
                "search-1",
            )
        if len(results) == 1:
            self.search_message = results[0]
            return _save_call_from_search_result(results[0], call_id="save-1")
        if len(results) == 2:
            self.save_message = results[1]
            batch = SaveBatchOutcome.from_artifact(results[1].artifact)
            if len(batch.items) != 1:
                raise AssertionError("expected one production save outcome")
            item = batch.items[0]
            if item.status not in {"saved", "reused"} or item.receipt is None:
                raise AssertionError("production save did not return a usable receipt")
            self.receipt = item.receipt
            return AIMessage(
                content=f"已保存並引用來源 {item.receipt.cite_marker}。"
            )
        raise AssertionError("unexpected extra citation workflow result")


class _DenialAwareModel:
    """Produce fallback prose only from PolicyToolNode's denial message."""

    def __init__(self):
        self.denial_message: ToolMessage | None = None

    def bind_tools(self, _tools):
        return self

    def invoke(self, messages):
        results = _workflow_results(messages)
        if not results:
            return _workflow_call(
                {"action": "search", "query": "HPC"},
                "forged-1",
            )
        denial = results[-1]
        if (
            denial.tool_call_id != "forged-1"
            or denial.status != "error"
            or "tool not available" not in denial.content
        ):
            raise AssertionError("model did not receive the production policy denial")
        self.denial_message = denial
        return AIMessage(content=f"citation unavailable: {denial.content}")


class _EmptySearchAwareModel:
    """Stop instead of inventing a selection when search returns no records."""

    def __init__(self):
        self.search_message: ToolMessage | None = None

    def bind_tools(self, _tools):
        return self

    def invoke(self, messages):
        results = _workflow_results(messages)
        if not results:
            return _workflow_call(
                {"action": "search", "query": "missing paper"},
                "empty-search",
            )
        search_message = results[-1]
        if "No bibliographic records found" not in search_message.content:
            raise AssertionError("empty-search journey unexpectedly found a record")
        self.search_message = search_message
        return AIMessage(
            content="搜尋沒有 bibliographic records，因此未保存任何來源。"
        )


class _RejectingReceiptModel:
    """Reject a save result unless its ToolMessage artifact decodes strictly."""

    def __init__(self):
        self.save_message: ToolMessage | None = None
        self.decode_error = ""

    def bind_tools(self, _tools):
        return self

    def invoke(self, messages):
        results = _workflow_results(messages)
        if not results:
            return _workflow_call(
                {"action": "search", "query": "Paper A"},
                "search-before-malformed",
            )
        if len(results) == 1:
            return _save_call_from_search_result(
                results[0],
                call_id="malformed-save",
            )
        save_message = results[-1]
        self.save_message = save_message
        try:
            SaveBatchOutcome.from_artifact(save_message.artifact)
        except (TypeError, ValueError) as exc:
            self.decode_error = str(exc)
            return AIMessage(content="保存失敗：save receipt 無法驗證。")
        raise AssertionError("malformed save receipt was incorrectly accepted")


class _EmptyFetcher:
    def __init__(self):
        self.calls: list[str] = []

    async def __call__(self, url, _headers):
        self.calls.append(url)
        if "api.crossref.org" in url:
            return FetchResponse(
                200,
                body=b'{"message": {"items": []}}',
            )
        if "api.datacite.org" in url:
            return FetchResponse(200, body=b'{"data": []}')
        raise AssertionError(f"empty search must not fetch a save target: {url}")


class _MalformedSaveOutcome:
    def to_artifact(self):
        return {
            "kind": SAVE_BATCH_KIND,
            "schema_version": SAVE_BATCH_SCHEMA_VERSION,
            "batch_id": "malformed-batch",
            "items": [{
                "request_index": 0,
                "requested_label": "Paper A",
                "status": "saved",
                "reason_code": "saved",
                "receipt": {
                    "source_id": "src-malformed",
                    # canonical_identity is deliberately missing.
                    "doi": DOI_A,
                    "title": "Paper A",
                    "year": 2021,
                    "work_type": "journal-article",
                    "bundle_path": "/not/a/trusted/bundle",
                    "verification_level": "doi_identity_verified",
                    "cite_marker": "[[cite:src-malformed]]",
                    "version_kind": "published",
                },
                "alternatives": [],
            }],
        }


def _make_session(monkeypatch, tmp_path, model) -> ChatSession:
    monkeypatch.setattr("agent.graph.get_chat_model", lambda _config: model)
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools",
        lambda _config: [_rag_search],
    )
    monkeypatch.setattr(
        "agent.tools.inventory.create_history_tool",
        lambda _config, store=None: _recall_history,
    )
    monkeypatch.setattr("agent.session.find_app_root", lambda: tmp_path)
    config = AgentConfig(persist_dir=str(tmp_path / "persist"))
    return ChatSession(config, history_store=FakeHistoryStore())


def _seed_fixture_service(session, tmp_path, fetcher=None):
    hub = CitationProviderHub(env={}, fetcher=fetcher or RoutingFetcher())
    service = CitationService(hub, output_dir=tmp_path / "cite")
    session._citation_service = service
    return service


def test_search_selection_save_bundle_journey_reads_tool_messages(
    monkeypatch,
    tmp_path,
):
    model = _SearchSaveModel()
    session = _make_session(monkeypatch, tmp_path, model)
    session.activate_skill("citation")
    service = _seed_fixture_service(session, tmp_path)

    answer = asyncio.run(
        session.turn("搜尋 Paper A，選擇 2021 年正式記錄，保存並引用")
    )

    assert model.search_message is not None
    assert model.save_message is not None
    assert model.receipt is not None
    assert [call["name"] for call in session.last_tool_calls] == [
        "citation_workflow",
        "citation_workflow",
    ]
    assert "已保存並引用來源 [1]。" in answer
    assert "Sources:" in answer
    assert "Paper A" in answer
    assert f"DOI: {DOI_A}" in answer
    assert model.receipt.bundle_path not in answer

    bundles = list((tmp_path / "cite").glob("*/reference.bib"))
    assert len(bundles) == 1
    assert DOI_A in bundles[0].read_text(encoding="utf-8")
    sidecar = json.loads(
        (bundles[0].parent / "citation.json").read_text(encoding="utf-8")
    )
    assert sidecar["source_ref"]["doi"] == DOI_A
    assert "bundle_path" not in sidecar["source_ref"]
    assert service.registry.trusted_receipt(model.receipt.source_id) == model.receipt
    assert session.recent_turns[-1].assistant_output == answer


@pytest.mark.parametrize(
    "active_skill",
    [None, "academic-paper-writing"],
    ids=["no-skill", "wrong-skill"],
)
def test_citation_workflow_denial_is_consumed_by_model(
    monkeypatch,
    tmp_path,
    active_skill,
):
    model = _DenialAwareModel()
    session = _make_session(monkeypatch, tmp_path, model)
    if active_skill is not None:
        session.activate_skill(active_skill)

    result = asyncio.run(session._run_graph_turn("查 HPC 論文"))

    denial = next(
        message
        for message in result.new_messages
        if isinstance(message, ToolMessage) and message.name == "citation_workflow"
    )
    assert denial.status == "error"
    assert model.denial_message is denial
    assert result.answer == f"citation unavailable: {denial.content}"
    assert session._citation_service is None


def test_search_selection_journey_stops_when_search_is_empty(
    monkeypatch,
    tmp_path,
):
    model = _EmptySearchAwareModel()
    fetcher = _EmptyFetcher()
    session = _make_session(monkeypatch, tmp_path, model)
    session.activate_skill("citation")
    service = _seed_fixture_service(session, tmp_path, fetcher=fetcher)

    answer = asyncio.run(session.turn("搜尋並保存不存在的論文"))

    assert model.search_message is not None
    assert answer == "搜尋沒有 bibliographic records，因此未保存任何來源。"
    assert [call["name"] for call in session.last_tool_calls] == [
        "citation_workflow"
    ]
    assert service.registry.list() == []
    assert list((tmp_path / "cite").glob("*/reference.bib")) == []
    assert len(fetcher.calls) == 2


def test_search_selection_journey_rejects_malformed_save_receipt(
    monkeypatch,
    tmp_path,
):
    model = _RejectingReceiptModel()
    session = _make_session(monkeypatch, tmp_path, model)
    session.activate_skill("citation")
    service = _seed_fixture_service(session, tmp_path)

    async def malformed_save(_intents):
        return _MalformedSaveOutcome()

    service.save = malformed_save
    answer = asyncio.run(session.turn("搜尋 Paper A 並保存"))

    assert model.save_message is not None
    assert model.save_message.status == "success"
    assert "invalid save receipt fields" in model.decode_error
    assert answer == "保存失敗：save receipt 無法驗證。"
    assert [call["name"] for call in session.last_tool_calls] == [
        "citation_workflow",
        "citation_workflow",
    ]
    assert service.registry.list() == []
    assert list((tmp_path / "cite").glob("*/reference.bib")) == []
