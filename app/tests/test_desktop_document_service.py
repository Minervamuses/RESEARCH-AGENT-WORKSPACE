"""Document edits cross the real session graph and desktop approval boundary."""

import asyncio
import json
import tempfile
import uuid
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.desktop.protocol import request_event, success_result
from agent.desktop.service import DesktopServiceError
from agent.session import ChatSession
from test_desktop_service import _service


class _DocumentModel:
    def __init__(self):
        self.calls = []
        self.bound_names = []
        self.replacement = "第二段已修改🙂"
        self.fail_after_save = False

    def bind_tools(self, tools):
        self.bound_names.append(tuple(tool.name for tool in tools))
        return self

    def invoke(self, messages):
        self.calls.append(messages)
        if isinstance(messages[-1], ToolMessage):
            result = json.loads(messages[-1].content)
            if self.fail_after_save:
                self.fail_after_save = False
                raise RuntimeError("fixture response interrupted after document save")
            return AIMessage(content=f"Document operation: {result['status']}.")
        prompt = next(message.content for message in reversed(messages) if isinstance(message, HumanMessage))
        if prompt.startswith("分析"):
            return AIMessage(content="分析完成，沒有修改稿件。")
        return AIMessage(content="", tool_calls=[{
            "name": "document_edit", "id": "model-document-call",
            "args": {"replacement_text": self.replacement}, "type": "tool_call",
        }])


class _Sink:
    def __init__(self, service, context, *, approve=True, on_approval=None):
        self.request_id = str(uuid.uuid4())
        self.service = service
        self.context = context
        self.approve = approve
        self.on_approval = on_approval
        self.events = []
        self.tasks = []
        self.results = []

    def __call__(self, event, data):
        self.events.append((event, data))
        request_event(self.request_id, len(self.events), event, data)
        if event == "document.proposed":
            async def apply():
                result = await self.service.dispatch("document.apply", {
                    "documentContext": self.context, "turnId": data["turnId"],
                    "callId": data["callId"], "parentRequestId": self.request_id,
                }, event_sink=self)
                success_result(str(uuid.uuid4()), "document.apply", result)
                self.results.append(result)
            self.tasks.append(asyncio.create_task(apply()))
        elif event == "approval.required":
            if self.on_approval:
                self.on_approval(self)
            self.tasks.append(asyncio.create_task(self.service.dispatch("approval.resolve", {
                "approvalId": data["approvalId"], "parentRequestId": data["parentRequestId"],
                "turnId": data["turnId"], "approved": self.approve,
                "documentContext": self.context,
            })))


async def _setup(tmp_path, monkeypatch):
    model = _DocumentModel()
    monkeypatch.setattr("agent.graph.get_chat_model", lambda _config: model)
    monkeypatch.setattr("agent.tools.inventory.create_rag_tools", lambda _config: [])

    async def factory(config, *, load_mcp, **kwargs):
        assert load_mcp is False
        return ChatSession(config, loaded_skills=[], **kwargs)

    service = _service(tmp_path, session_factory=factory)
    preview = await service.dispatch("workspace.select", {"rootPath": str(tmp_path), "action": "inspect"})
    project = await service.dispatch("workspace.select", {
        "rootPath": str(tmp_path), "action": "initialize",
        "historyDirectory": preview["historyDirectory"],
        "expectedFingerprint": preview["researchFingerprint"],
    })
    await service.dispatch("session.create", {"loadMcp": False, "projectId": project["projectId"]})
    path = tmp_path / "稿件.md"
    path.write_text("相同段落🙂\n\n相同段落🙂\n尾段\n", encoding="utf-8")
    context = await service.dispatch("document.open", {"path": str(path)})
    success_result(str(uuid.uuid4()), "document.open", context)
    return service, model, path, context


def test_real_graph_uses_unsaved_selected_snapshot_and_ask_save(tmp_path, monkeypatch):
    async def run():
        service, model, path, context = await _setup(tmp_path, monkeypatch)
        context = {**context, "editorRevision": 1, "sourceText": context["sourceText"] + "未儲存文字\n",
                   "rangeStartUtf16": 8, "rangeEndUtf16": 14}
        service.session.set_thinking_mode("extended")
        sink = _Sink(service, context)
        params = {"text": "改寫選取的第二段", "turnId": uuid.uuid4().hex, "retry": False, "documentContext": context}
        result = await service.dispatch("session.turn", params, event_sink=sink)
        await asyncio.gather(*sink.tasks)
        assert result["text"] == "Document operation: saved."
        assert sink.results[0]["status"] == "saved"
        assert path.read_text() == "相同段落🙂\n\n第二段已修改🙂\n尾段\n未儲存文字\n"
        assert "未儲存文字" in model.calls[0][-1].content
        assert service.session.thinking_mode == "extended"
        assert any("document_edit" in names for names in model.bound_names)
        assert [event for event, _ in sink.events if event in {"document.proposed", "approval.required"}] == ["document.proposed", "approval.required"]
        before = len(model.calls)
        assert (await service.dispatch("session.turn", params, event_sink=sink))["text"] == result["text"]
        assert len(model.calls) == before
        with pytest.raises(DesktopServiceError):
            await service.dispatch("session.turn", {**params, "documentContext": {**context, "editorRevision": 2}}, event_sink=sink)
    asyncio.run(run())


def test_analysis_and_out_of_range_never_modify_disk(tmp_path, monkeypatch):
    async def run():
        service, model, path, context = await _setup(tmp_path, monkeypatch)
        original = path.read_bytes()
        sink = _Sink(service, context)
        await service.dispatch("session.turn", {"text": "分析第 2 行", "turnId": uuid.uuid4().hex, "retry": False, "documentContext": context}, event_sink=sink)
        assert path.read_bytes() == original and sink.results == []
        count = len(model.calls)
        with pytest.raises(DesktopServiceError, match="outside"):
            await service.dispatch("session.turn", {"text": "改寫第 40–45 行", "turnId": uuid.uuid4().hex, "retry": False, "documentContext": context}, event_sink=sink)
        assert len(model.calls) == count and path.read_bytes() == original
        assert not service.session._document_turn_active
    asyncio.run(run())


def test_manual_save_wire_result_reports_actual_disk_conflict(tmp_path, monkeypatch):
    async def run():
        service, _model, path, context = await _setup(tmp_path, monkeypatch)
        current = {**context, "editorRevision": 1, "sourceText": "手動輸入🙂\n"}
        saved = await service.dispatch("document.save", {"documentContext": current})
        success_result(str(uuid.uuid4()), "document.save", saved)
        assert saved["status"] == "saved" and path.read_text() == current["sourceText"]
        path.write_text("outside\n")
        conflict = await service.dispatch("document.save", {"documentContext": current})
        success_result(str(uuid.uuid4()), "document.save", conflict)
        assert conflict["status"] == "conflict" and path.read_text() == "outside\n"
    asyncio.run(run())


def test_edit_during_ask_conflicts_and_later_choice_rechecks(tmp_path, monkeypatch):
    async def run():
        service, _model, path, context = await _setup(tmp_path, monkeypatch)
        original = path.read_bytes()
        def type_while_approval(sink):
            sink.context = {**sink.context, "editorRevision": 1, "sourceText": sink.context["sourceText"] + "等待中輸入\n"}
        sink = _Sink(service, context, on_approval=type_while_approval)
        result = await service.dispatch("session.turn", {"text": "改寫稿件", "turnId": uuid.uuid4().hex, "retry": False, "documentContext": context}, event_sink=sink)
        await asyncio.gather(*sink.tasks)
        assert result["text"] == "Document operation: conflict."
        conflict = sink.results[0]
        assert path.read_bytes() == original
        later_sink = _Sink(service, sink.context)
        path.write_text("外部編輯\n")
        repeated = await service.dispatch("document.apply", {
            "documentContext": sink.context, "turnId": service._document_candidates[conflict["callId"]].turn_id,
            "callId": conflict["callId"], "resolution": "use", "expectedSnapshot": conflict["expectedSnapshot"],
        }, event_sink=later_sink)
        await asyncio.gather(*later_sink.tasks)
        assert repeated["status"] == "conflict" and path.read_text() == "外部編輯\n"
        adopted = await service.dispatch("document.apply", {
            "documentContext": sink.context, "turnId": service._document_candidates[conflict["callId"]].turn_id,
            "callId": conflict["callId"], "resolution": "use", "expectedSnapshot": repeated["expectedSnapshot"],
        }, event_sink=later_sink)
        assert adopted["status"] == "saved" and path.read_text() == "第二段已修改🙂"
    asyncio.run(run())


def test_denied_operation_retains_candidate_and_undo_checks_later_edits(tmp_path, monkeypatch):
    async def run():
        service, _model, path, context = await _setup(tmp_path, monkeypatch)
        original = path.read_bytes()
        turn_id = uuid.uuid4().hex
        sink = _Sink(service, context, approve=False)
        await service.dispatch("session.turn", {"text": "改寫稿件", "turnId": turn_id, "retry": False, "documentContext": context}, event_sink=sink)
        await asyncio.gather(*sink.tasks)
        assert sink.results[0]["status"] == "cancelled" and path.read_bytes() == original
        call_id = sink.results[0]["callId"]
        approved = _Sink(service, context)
        saved = await service.dispatch("document.apply", {"documentContext": context, "turnId": turn_id, "callId": call_id}, event_sink=approved)
        current = {key: saved[key] for key in ("rootPath", "path", "editorRevision", "sourceText", "diskFingerprint")}
        undo_sink = _Sink(service, current)
        undone = await service.dispatch("document.apply", {"documentContext": current, "turnId": turn_id, "undoOfCallId": call_id}, event_sink=undo_sink)
        assert undone["status"] == "saved" and path.read_bytes() == original
        assert any(data.get("operation") == "document.undo" for _, data in undo_sink.events)
        changed = {**current, "editorRevision": current["editorRevision"] + 1, "sourceText": current["sourceText"] + "later"}
        later_sink = _Sink(service, changed)
        conflict = await service.dispatch("document.apply", {"documentContext": changed, "turnId": turn_id, "undoOfCallId": call_id}, event_sink=later_sink)
        assert conflict["status"] == "conflict" and path.read_bytes() == original
        with pytest.raises(DesktopServiceError, match="another turn"):
            await service.dispatch("document.apply", {"documentContext": context, "turnId": turn_id, "callId": call_id, "parentRequestId": str(uuid.uuid4())}, event_sink=approved)
    asyncio.run(run())


def test_retry_after_save_does_not_write_candidate_twice(tmp_path, monkeypatch):
    async def run():
        service, model, path, context = await _setup(tmp_path, monkeypatch)
        service._bash_permission_mode = "bypass"
        writes = []
        original_write = service._documents._write
        def counted_write(target, text):
            writes.append(text)
            original_write(target, text)
        monkeypatch.setattr(service._documents, "_write", counted_write)
        model.fail_after_save = True
        sink = _Sink(service, context)
        params = {"text": "改寫稿件", "turnId": uuid.uuid4().hex, "retry": False, "documentContext": context}
        with pytest.raises(DesktopServiceError):
            await service.dispatch("session.turn", params, event_sink=sink)
        await asyncio.gather(*sink.tasks)
        assert len(writes) == 1
        result = await service.dispatch("session.turn", {**params, "retry": True}, event_sink=sink)
        assert result["text"] == "Document operation: saved." and len(writes) == 1
        assert path.read_text() == "第二段已修改🙂"
    asyncio.run(run())


def test_isolated_desktop_fixture_calls_real_document_coordinator():
    from agent.desktop.fixture_session import (
        FIXTURE_ROOT_ENV, FIXTURE_ROOT_PREFIX, build_phase02_fixture_service,
    )

    async def run(root):
        service = build_phase02_fixture_service(original_cwd=root, environ={FIXTURE_ROOT_ENV: str(root)})
        project_root = root / "projects" / "project-one"
        project = await service.dispatch("workspace.select", {"rootPath": str(project_root)})
        assert project["status"] == "opened"
        await service.dispatch("session.create", {"loadMcp": False, "projectId": project["projectId"]})
        path = project_root / "draft.md"
        path.write_text("first\nsecond\n")
        context = await service.dispatch("document.open", {"path": str(path)})
        context.update(rangeStartUtf16=6, rangeEndUtf16=12)
        sink = _Sink(service, context)
        result = await service.dispatch("session.turn", {
            "text": "[[fixture:document-replace]] changed", "turnId": uuid.uuid4().hex,
            "retry": False, "documentContext": context,
        }, event_sink=sink)
        await asyncio.gather(*sink.tasks)
        assert result["text"] == "Fixture document operation: saved."
        assert path.read_text() == "first\nchanged\n"

    with tempfile.TemporaryDirectory(prefix=FIXTURE_ROOT_PREFIX, dir="/tmp") as directory:
        asyncio.run(run(Path(directory)))
