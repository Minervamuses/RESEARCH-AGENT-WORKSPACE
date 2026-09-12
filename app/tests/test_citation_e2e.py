"""Citation journeys through the real graph, policy node, tool, and service."""

import asyncio
import json
from pathlib import Path
import threading
from types import SimpleNamespace
import uuid

import pytest
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from agent.config import AgentConfig
from agent.conversations import ConversationUnavailableError
from agent.session import ChatSession
from skills.citation.hub import CitationProviderHub
from skills.citation.providers.net import FetchResponse
from skills.citation.service import CitationService
from skills.citation.tool import CitationWorkflowInput
from skills.citation.types import (
    SAVE_BATCH_KIND,
    SAVE_BATCH_SCHEMA_VERSION,
    SaveBatchOutcome,
)
from tests.citation_fixtures import DOI_A, DOI_B, RoutingFetcher


@tool("rag_search")
def _rag_search(query: str) -> str:
    """Search stub not invoked by these citation journeys."""
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


def _save_content(message: ToolMessage) -> SaveBatchOutcome:
    prefix = "Actual citation save result:\n"
    assert message.content.startswith(prefix)
    return SaveBatchOutcome.from_artifact(json.loads(message.content.removeprefix(prefix)))


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
        self.invoked_tool_names: list[list[str]] = []
        self.invocations = []
        self.search_message: ToolMessage | None = None
        self.save_message: ToolMessage | None = None
        self.receipt = None

    def bind_tools(self, tools):
        names = [tool.name for tool in tools]
        self.bound_tool_names.append(names)

        def invoke(messages):
            self.invoked_tool_names.append(names)
            return self.invoke(messages)

        return SimpleNamespace(invoke=invoke)

    def invoke(self, messages):
        self.invocations.append([message.model_copy(deep=True) for message in messages])
        if "citation_workflow" not in self.invoked_tool_names[-1]:
            return AIMessage(content="ordinary answer")
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
            batch = _save_content(results[1])
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
    """Reject a save result unless its model-visible content decodes strictly."""

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
            _save_content(save_message)
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
    monkeypatch.setattr("agent.session.find_app_root", lambda: tmp_path)
    config = AgentConfig(persist_dir=str(tmp_path / "persist"))
    return ChatSession(config)


def _seed_fixture_service(session, tmp_path, fetcher=None):
    hub = CitationProviderHub(env={}, fetcher=fetcher or RoutingFetcher())
    service = CitationService(hub, output_dir=tmp_path / "cite")
    session._citation_service = service
    return service


def _fixture_services(monkeypatch, tmp_path, fetcher=None):
    """Keep lazy per-task service construction real with offline I/O boundaries."""
    hub = CitationProviderHub(env={}, fetcher=fetcher or RoutingFetcher())
    services = []

    def create(provider_hub, *, config):
        assert provider_hub is hub
        service = CitationService(hub, output_dir=tmp_path / "cite")
        services.append(service)
        return service

    monkeypatch.setattr("skills.citation.hub.get_provider_hub", lambda: hub)
    monkeypatch.setattr("skills.citation.service.CitationService", create)
    return services


class _SaveReportingModel:
    """Generate each attempt's report from content and its matching tool call."""

    def __init__(self, works, *, retry=False):
        self.works = works
        self.retry = retry
        self.invocations = []
        self.answer = None

    def bind_tools(self, _tools):
        return self

    def invoke(self, messages):
        self.invocations.append([message.model_copy(deep=True) for message in messages])
        results = _workflow_results(messages)
        if not results:
            assert len(self.invocations) == 1
            return _workflow_call({"action": "save", "works": self.works}, "save-1")

        lines = []
        retry_works = []
        for attempt, message in enumerate(results, start=1):
            assert message.status == "success"
            calls = [
                call for prior in messages[:messages.index(message)]
                if isinstance(prior, AIMessage)
                for call in prior.tool_calls
                if call["id"] == message.tool_call_id
            ]
            assert len(calls) == 1 and calls[0]["args"]["action"] == "save"
            batch = _save_content(message)
            lines.append(f"第 {attempt} 次保存：")
            for item in batch.items:
                work = calls[0]["args"]["works"][item.request_index]
                assert item.requested_label == work["requested_label"]
                doi = next(value["value"] for value in work["identifiers"] if value["kind"] == "doi")
                if item.status in {"saved", "reused"}:
                    assert item.receipt is not None and item.receipt.doi == doi
                    result = "新保存" if item.status == "saved" else "重用"
                else:
                    result = "失敗"
                    retry_works.append(work)
                lines.append(f"{item.requested_label} ({doi})：{result}（{item.reason_code}）。")
        if self.retry and len(results) == 1 and retry_works:
            assert self.answer is None
            return _workflow_call({"action": "save", "works": retry_works}, "save-2")
        self.answer = "\n".join(lines)
        return AIMessage(content=self.answer)


class _SaveResultFetcher(RoutingFetcher):
    """Fail B's first BibTeX request with a wrong DOI or uncached HTTP error."""

    def __init__(self, failures, *, transient=False):
        super().__init__()
        self.failures = failures
        self.transient = transient
        self.bibtex_b_calls = 0

    async def __call__(self, url, headers):
        if url == f"https://doi.org/{DOI_B}" and "x-bibtex" in headers.get("Accept", ""):
            self.bibtex_b_calls += 1
            if self.bibtex_b_calls <= self.failures:
                self.calls.append((url, headers["Accept"]))
                if self.transient:
                    return FetchResponse(503)
                return FetchResponse(200, body=(
                    f"@article{{b, title={{Paper B}}, year={{2020}}, doi={{{DOI_A}}}}}"
                ).encode())
        return await super().__call__(url, headers)


@pytest.mark.parametrize("scenario", ["all_success", "all_failure", "mixed", "retry"])
def test_save_reporting_reaches_model_history_and_cli(
    monkeypatch, tmp_path, capsys, scenario,
):
    works = [
        {"requested_label": title, "identifiers": [{"kind": "doi", "value": doi}]}
        for title, doi in (("Paper A", DOI_A), ("Paper B", DOI_B))
    ]
    selected = works if scenario in {"all_success", "mixed"} else works[1:]
    model = _SaveReportingModel(selected, retry=scenario == "retry")
    session = _make_session(monkeypatch, tmp_path, model)
    fetcher = _SaveResultFetcher(
        0 if scenario == "all_success" else 1, transient=scenario == "retry",
    )
    service = _seed_fixture_service(session, tmp_path, fetcher=fetcher)
    services = _fixture_services(monkeypatch, tmp_path, fetcher=fetcher)
    prior_files = {}
    if scenario == "all_success":
        intent = CitationWorkflowInput.model_validate({"action": "save", "works": works[:1]})
        prepared = asyncio.run(service.save(tuple(work.to_domain() for work in intent.works)))
        assert prepared.items[0].status == "saved"
        prior_files = {
            path: (path.read_bytes(), path.stat().st_mtime_ns)
            for path in Path(prepared.items[0].receipt.bundle_path).iterdir()
        }

    turn_answers = []
    if scenario == "mixed":
        from agent.cli import chat

        async def create(_config, **kwargs):
            assert kwargs["load_mcp"] is False
            return session

        inputs = iter(["/citation 保存 A 與 B 並逐項回報", "q"])

        async def read_line(_prompt):
            return next(inputs)

        real_turn = session.turn

        async def record_turn(*args, **kwargs):
            answer = await real_turn(*args, **kwargs)
            turn_answers.append(answer)
            return answer

        monkeypatch.setattr(chat.ChatSession, "create", create)
        monkeypatch.setattr(session, "turn", record_turn)
        asyncio.run(chat._run(
            SimpleNamespace(no_mcp=True, max_graph_steps=None), read_line=read_line,
        ))
        output = capsys.readouterr().out
        assert len(turn_answers) == 1
        answer = turn_answers[0]
        assert output.endswith(f"\n{answer}\n\n")
        assert output.count(answer) == 1
    else:
        answer = asyncio.run(session.turn(
            "保存並逐項回報：" + json.dumps(selected, ensure_ascii=False)
            + ("；若失敗可重試一次" if scenario == "retry" else ""),
            skill_name="citation",
        ))

    assert len(services) == 1
    service = services[0]
    assert session.active_skill_runtime is None
    assert session._citation_service is None
    assert session._build_sources_hint() is None
    assert "citation_workflow" not in session.tool_access_resolution().effective_tools

    assert answer == model.answer == session.recent_turns[-1].assistant_output
    persisted = session.conversation_repository.load(session.session_id)
    assert persisted.document.turns[-1].assistant_output == answer
    assert _workflow_results(model.invocations[0]) == []
    assert [len(_workflow_results(snapshot)) for snapshot in model.invocations] == (
        [0, 1, 2] if scenario == "retry" else [0, 1]
    )
    results = _workflow_results(model.invocations[-1])
    batches = [_save_content(message) for message in results]
    assert [message.tool_call_id for message in results] == (
        ["save-1", "save-2"] if scenario == "retry" else ["save-1"]
    )
    assert len({batch.batch_id for batch in batches}) == len(batches)
    for message, batch in zip(results, batches, strict=True):
        assert batch.to_artifact() == message.artifact
    expected = {
        "all_success": [["reused", "saved"]],
        "all_failure": [["verification_failed"]],
        "mixed": [["saved", "verification_failed"]],
        "retry": [["verification_failed"], ["saved"]],
    }[scenario]
    assert [[item.status for item in batch.items] for batch in batches] == expected
    for batch in batches:
        for item in batch.items:
            if item.receipt is None:
                assert item.reason_code == (
                    "bibtex_lookup_failed" if scenario == "retry" else "bibtex_doi_mismatch"
                )
                assert f"：失敗（{item.reason_code}）。" in answer
            else:
                receipt = item.receipt
                assert service.registry.trusted_receipt(receipt.source_id) == receipt
                bundle = Path(receipt.bundle_path)
                assert receipt.doi in (bundle / "reference.bib").read_text(encoding="utf-8")
                sidecar = json.loads((bundle / "citation.json").read_text(encoding="utf-8"))
                assert sidecar["source_ref"]["doi"] == receipt.doi
                if item.status == "saved":
                    assert sidecar["creation_evidence"]["batch_id"] == batch.batch_id
                    assert sidecar["creation_evidence"]["request_index"] == item.request_index
                result = "重用" if item.status == "reused" else "新保存"
                assert f"{item.requested_label} ({receipt.doi})：{result}（{item.reason_code}）。" in answer

    expected_dois = {
        "all_success": {DOI_A, DOI_B}, "all_failure": set(),
        "mixed": {DOI_A}, "retry": {DOI_B},
    }[scenario]
    assert {source.doi for source in service.registry.list()} == expected_dois
    assert len(list(service.output_dir.glob("*/reference.bib"))) == len(expected_dois)
    for path, original in prior_files.items():
        assert (path.read_bytes(), path.stat().st_mtime_ns) == original
    if scenario == "all_failure":
        assert "新保存" not in answer and "重用" not in answer
    if scenario == "retry":
        assert fetcher.bibtex_b_calls == 2
        calls = [call for message in model.invocations[-1] if isinstance(message, AIMessage)
                 for call in message.tool_calls]
        assert calls[0]["args"]["works"] == calls[1]["args"]["works"] == works[1:]
        assert [batch.items[0].request_index for batch in batches] == [0, 0]
        assert answer.index("失敗") < answer.index("新保存")


def test_search_selection_save_bundle_journey_reads_tool_messages(
    monkeypatch,
    tmp_path,
):
    model = _SearchSaveModel()
    session = _make_session(monkeypatch, tmp_path, model)
    session.activate_citation_skill()
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
    outcome = asyncio.run(session.turn_outcome(
        "查 HPC 論文",
        skill_name=active_skill,
    ))

    denial = model.denial_message
    assert denial is not None
    assert denial.status == "error"
    assert model.denial_message is denial
    assert outcome.text == f"citation unavailable: {denial.content}"
    assert session._citation_service is None
    assert session.active_skill_runtime is None


def test_search_selection_journey_stops_when_search_is_empty(
    monkeypatch,
    tmp_path,
):
    model = _EmptySearchAwareModel()
    fetcher = _EmptyFetcher()
    session = _make_session(monkeypatch, tmp_path, model)
    services = _fixture_services(monkeypatch, tmp_path, fetcher=fetcher)
    session.thinking_mode = "extended"

    answer = asyncio.run(session.turn("搜尋並保存不存在的論文", skill_name="citation"))
    service = services[0]

    assert model.search_message is not None
    assert answer == "搜尋沒有 bibliographic records，因此未保存任何來源。"
    assert [call["name"] for call in session.last_tool_calls] == [
        "citation_workflow"
    ]
    assert service.registry.list() == []
    assert list((tmp_path / "cite").glob("*/reference.bib")) == []
    assert len(fetcher.calls) == 2
    assert session._citation_service is None
    assert session.active_skill_runtime is None
    assert session.thinking_mode == "extended"

    def ordinary(messages):
        assert "citation_workflow" not in session.tool_access_resolution().effective_tools
        assert not any("[Citable sources]" in m.content for m in messages if isinstance(m, SystemMessage))
        return AIMessage(content="ordinary answer")

    monkeypatch.setattr(model, "invoke", ordinary)
    monkeypatch.setattr(session._fusion, "run_extended_turn", session._run_normal_turn)
    assert asyncio.run(session.turn("ordinary question")) == "ordinary answer"


def test_search_selection_journey_rejects_malformed_save_receipt(
    monkeypatch,
    tmp_path,
):
    model = _RejectingReceiptModel()
    session = _make_session(monkeypatch, tmp_path, model)
    session.activate_citation_skill()
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


def test_one_shot_cli_cites_then_runs_ordinary_turn(monkeypatch, tmp_path, capsys):
    from agent.cli import chat

    model = _SearchSaveModel()
    session = _make_session(monkeypatch, tmp_path, model)
    services = _fixture_services(monkeypatch, tmp_path)
    prompt = "搜尋 Paper A，選擇 2021 年正式記錄，保存並引用"

    async def create(*_args, **kwargs):
        assert kwargs["load_mcp"] is False
        return session

    inputs = iter([f"/citation {prompt}", "ordinary question", "q"])

    async def read_line(_prompt):
        value = next(inputs)
        if value == "ordinary question":
            assert session.active_skill_runtime is None
            assert session._citation_service is None
        return value

    monkeypatch.setattr(chat.ChatSession, "create", create)
    asyncio.run(chat._run(SimpleNamespace(no_mcp=True, max_graph_steps=None), read_line=read_line))
    output = capsys.readouterr().out
    turns = session.conversation_repository.load(session.session_id).document.turns
    assert len(turns) == 2
    answer = turns[0].assistant_output
    assert "已保存並引用來源 [1]。" in answer
    assert "Sources:" in answer and f"DOI: {DOI_A}" in answer
    assert answer in output and "ordinary answer" in output and "normal" in output
    assert turns[0].display_input == f"/citation {prompt}"
    assert turns[0].semantic_input == prompt
    assert turns[1].assistant_output == "ordinary answer"
    assert len(model.invocations) == 4
    assert model.invocations[0][-1].content == prompt
    assert len(services) == 1
    assert services[0].registry.trusted_receipt(model.receipt.source_id) == model.receipt
    assert Path(model.receipt.bundle_path, "reference.bib").is_file()
    assert "citation_workflow" not in model.invoked_tool_names[-1]
    assert not any("[Citable sources]" in m.content for m in model.invocations[-1] if isinstance(m, SystemMessage))


@pytest.mark.parametrize("terminal", ["success", "gate", "provider", "persistence"])
def test_citation_terminal_cleanup_preserves_bundle_and_restores_thinking(
    monkeypatch, tmp_path, terminal,
):
    class Model(_SearchSaveModel):
        def invoke(self, messages):
            answer = super().invoke(messages)
            if len(_workflow_results(messages)) == 2:
                if terminal == "provider":
                    raise RuntimeError("fixture provider failed after save")
                if terminal == "gate":
                    return AIMessage(content="Untrusted [[cite:src-forged]]")
            return answer

    model = Model()
    session = _make_session(monkeypatch, tmp_path, model)
    services = _fixture_services(monkeypatch, tmp_path)
    session.thinking_mode = "extended"
    if terminal == "success":
        # Simulate the existing installer's temporary mode awaiting cleanup.
        session._installer_previous_mode = "extended"
        session.thinking_mode = "normal"
    complete = session.conversation_repository.complete_turn

    def check_completion(*args, **kwargs):
        assert session.citation_skill_active
        assert session.thinking_mode == "normal"
        assert session._citation_service is services[0]
        assert services[0].registry.trusted_receipt(model.receipt.source_id) == model.receipt
        if terminal == "persistence":
            raise ConversationUnavailableError("fixture final write failed")
        return complete(*args, **kwargs)

    monkeypatch.setattr(session.conversation_repository, "complete_turn", check_completion)
    turn_id = uuid.uuid4().hex
    request = "搜尋 Paper A，保存並正式引用"
    if terminal in {"provider", "persistence"}:
        error = RuntimeError if terminal == "provider" else ConversationUnavailableError
        with pytest.raises(error, match="fixture"):
            asyncio.run(session.turn_outcome(request, skill_name="citation", turn_id=turn_id))
    else:
        outcome = asyncio.run(session.turn_outcome(request, skill_name="citation", turn_id=turn_id))
        assert bool(outcome.validation_errors) == (terminal == "gate")
        if terminal == "gate":
            assert "已被封鎖" in outcome.text
            assert not outcome.text.startswith("Untrusted")
        else:
            assert "[[cite:" not in outcome.text
        assert ("Sources:" in outcome.text) == (terminal == "success")

    turn = session.conversation_repository.load(session.session_id).document.turns[-1]
    assert turn.state == ("failed" if terminal in {"provider", "persistence"} else "completed")
    assert turn.thinking_mode == "normal"
    if turn.state == "failed":
        assert turn.assistant_output is None
    assert session.thinking_mode == "extended"
    assert session.active_skill_runtime is None
    assert session._citation_service is None
    assert session._build_sources_hint() is None
    assert "citation_workflow" not in session.tool_access_resolution().effective_tools
    assert Path(model.receipt.bundle_path, "reference.bib").is_file()

    if terminal == "success":
        count = len(model.invocations)
        with monkeypatch.context() as patch:
            def no_load(_name):
                raise AssertionError("completed duplicate must not load a runtime")
            patch.setattr(session, "_load_skill_runtime", no_load)
            duplicate = asyncio.run(session.turn_outcome(request, skill_name="citation", turn_id=turn_id))
        assert duplicate.text == turn.assistant_output
        assert len(model.invocations) == count and len(services) == 1

    monkeypatch.setattr(session.conversation_repository, "complete_turn", complete)
    # Exercise the next ordinary graph without invoking live Fusion models.
    monkeypatch.setattr(session._fusion, "run_extended_turn", session._run_normal_turn)
    assert asyncio.run(session.turn("ordinary question")) == "ordinary answer"
    assert session.thinking_mode == "extended"
    assert "citation_workflow" not in model.invoked_tool_names[-1]
    assert not any("[Citable sources]" in m.content for m in model.invocations[-1] if isinstance(m, SystemMessage))


def test_later_citation_requires_new_receipt_and_reuses_saved_bundle(monkeypatch, tmp_path):
    model = _SearchSaveModel()
    session = _make_session(monkeypatch, tmp_path, model)
    services = _fixture_services(monkeypatch, tmp_path)
    first = asyncio.run(session.turn("搜尋 Paper A，保存並引用", skill_name="citation"))
    receipt = model.receipt
    bundle = Path(receipt.bundle_path)
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in bundle.iterdir()}
    invoke = model.invoke

    def cite_old(messages):
        assert any(isinstance(m, AIMessage) and m.content == first for m in messages)
        assert session.citation_service.registry.list() == []
        return AIMessage(content=f"Old marker {receipt.cite_marker}")

    monkeypatch.setattr(model, "invoke", cite_old)
    rejected = asyncio.run(session.turn_outcome("引用先前選擇", skill_name="citation"))
    assert rejected.validation_errors and "已被封鎖" in rejected.text
    assert "Sources:" not in rejected.text
    assert session._citation_service is None
    monkeypatch.setattr(model, "invoke", invoke)
    assert asyncio.run(session.turn("重用先前選擇並保存引用", skill_name="citation")) == first
    assert len(services) == 3
    assert len({id(service) for service in services}) == 3
    assert _save_content(model.save_message).items[0].status == "reused"
    assert services[-1].registry.trusted_receipt(receipt.source_id) == model.receipt
    assert {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in bundle.iterdir()} == before


def test_cancelled_save_late_writer_cannot_populate_next_citation(monkeypatch, tmp_path):
    from skills.citation import service as citation_service

    model = _SearchSaveModel()
    session = _make_session(monkeypatch, tmp_path, model)
    services = _fixture_services(monkeypatch, tmp_path)
    session.thinking_mode = "extended"
    entered = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    write = citation_service.write_identity_bundle

    def delayed_write(*args, **kwargs):
        entered.set()
        try:
            assert release.wait(5), "test must release writer"
            return write(*args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(citation_service, "write_identity_bundle", delayed_write)

    async def scenario():
        task = asyncio.create_task(session.turn("搜尋 Paper A，保存並引用", skill_name="citation"))
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            old = services[0]
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert session._citation_service is None
            assert session.active_skill_runtime is None
            assert session.thinking_mode == "extended"
            assert session.conversation_repository.load(session.session_id).document.turns[-1].state == "interrupted"

            def next_task(messages):
                assert session.citation_service is not old
                release.set()
                assert finished.wait(5)
                assert old.registry.list() == []
                assert session.citation_service.registry.list() == []
                return AIMessage(content="晚到的磁碟寫入沒有本次可信 receipt。")

            monkeypatch.setattr(model, "invoke", next_task)
            answer = await session.turn("檢查來源", skill_name="citation")
            assert "沒有本次可信 receipt" in answer
            assert session._citation_service is None
            assert session.thinking_mode == "extended"
            assert list((tmp_path / "cite").glob("*/reference.bib"))

            def ordinary(messages):
                assert session._citation_service is None
                assert "citation_workflow" not in session.tool_access_resolution().effective_tools
                assert not any("[Citable sources]" in m.content for m in messages if isinstance(m, SystemMessage))
                return AIMessage(content="ordinary answer")

            monkeypatch.setattr(model, "invoke", ordinary)
            monkeypatch.setattr(session._fusion, "run_extended_turn", session._run_normal_turn)
            assert await session.turn("ordinary question") == "ordinary answer"
        finally:
            release.set()
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            if entered.is_set():
                assert await asyncio.to_thread(finished.wait, 5)

    asyncio.run(scenario())
