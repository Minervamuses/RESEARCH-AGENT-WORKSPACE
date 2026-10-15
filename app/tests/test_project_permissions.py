"""Project permission consent stays separate from tool and version correctness."""

import asyncio
import json
import uuid
from types import SimpleNamespace

import pytest

from agent.desktop.protocol import request_event
from agent.desktop.service import DesktopServiceError
from test_desktop_service import (
    _FakeExtensionManager, _FakeSession, _SessionFactory, _service, _turn_params,
)


class _ApprovalSink:
    def __init__(self, service, *, approve=True, before_resolve=None):
        self.request_id = str(uuid.uuid4())
        self.service = service
        self.approve = approve
        self.before_resolve = before_resolve
        self.events = []
        self.tasks = []

    def __call__(self, event, data):
        self.events.append((event, data))
        request_event(self.request_id, len(self.events), event, data)
        if event == "approval.required":
            async def resolve():
                if self.before_resolve:
                    await self.before_resolve(data)
                await self.service.dispatch("approval.resolve", {
                    "approvalId": data["approvalId"], "parentRequestId": data["parentRequestId"],
                    "turnId": data["turnId"], "approved": self.approve,
                })
            self.tasks.append(asyncio.create_task(resolve()))

    @property
    def approvals(self):
        return [data for event, data in self.events if event == "approval.required"]


@pytest.mark.parametrize("mode,approved,effects", [("ask", True, 1), ("ask", False, 0), ("bypass", False, 1)])
@pytest.mark.parametrize("tool,args,operation", [
    ("citation_workflow", {"action": "save", "works": [{"requested_label": "A paper", "doi": "10.1000/example"}]}, "citation.save"),
    ("fixture_mcp", {"query": "source text"}, "mcp.call"),
    ("skill_install", {"action": "preview", "prepared_path": "/tmp/selected-prepared"}, "extension.install"),
    ("skill_install", {"action": "apply", "preview_id": "selected-preview"}, "extension.install"),
])
def test_tool_operations_receive_frozen_single_operation_consent(tmp_path, tool, args, operation, mode, approved, effects):
    async def run():
        performed = []
        installer_flags = []

        class ToolSession(_FakeSession):
            def __init__(self, config, progress_cb, handler):
                super().__init__(config, progress_cb)
                self.handler = handler
                self.mcp_families["fixture_mcp"] = "fixture_remote"
                self._installer_context = {"source_zip": "/tmp/selected.zip"}
                self._skill_installer = SimpleNamespace(bypass_approval=False)

            async def turn_outcome(self, text, **kwargs):
                installer_flags.append(self._skill_installer.bypass_approval)
                if await self.handler(tool, args):
                    performed.append((tool, args))
                return await super().turn_outcome(text, **kwargs)

        async def factory(config, *, operation_approval_handler, progress_cb, **_kwargs):
            return ToolSession(config, progress_cb, operation_approval_handler)

        service = _service(tmp_path, session_factory=factory)
        await service.dispatch("session.create", {"loadMcp": False})
        await service.dispatch("session.set_bash_permission", {"mode": mode})

        async def assert_mode_is_frozen(_data):
            with pytest.raises(DesktopServiceError) as raised:
                await service.dispatch("session.set_bash_permission", {"mode": "bypass"})
            assert raised.value.code == "BUSY_TURN"

        sink = _ApprovalSink(service, approve=approved, before_resolve=assert_mode_is_frozen)
        await service.dispatch("session.turn", _turn_params("Perform the selected operation."), event_sink=sink)
        await asyncio.gather(*sink.tasks)
        assert len(performed) == effects
        assert installer_flags == [mode == "bypass"]
        assert service.session._skill_installer.bypass_approval is False
        assert len(sink.approvals) == (mode == "ask")
        if sink.approvals:
            event = sink.approvals[0]
            assert event["operation"] == operation
            assert "command" not in event
            parameters = json.loads(event["parametersSummary"])
            assert (parameters["arguments"] if tool == "skill_install" else parameters) == (args["works"] if tool == "citation_workflow" else args)
            if tool == "skill_install":
                assert parameters["source"] == "/tmp/selected.zip"
                assert parameters["installationRoot"] == str(tmp_path / "state")
            if tool == "citation_workflow":
                assert event["targetPath"].endswith("/cite")
    asyncio.run(run())


@pytest.mark.parametrize("mode,approved,effects", [("ask", True, 1), ("ask", False, 0), ("bypass", False, 1)])
@pytest.mark.parametrize("kind", ["init", "file", "folder", "prune"])
def test_slash_index_mutations_ask_or_bypass_without_real_index(tmp_path, kind, mode, approved, effects):
    async def run():
        source = tmp_path / "source"
        source.mkdir()
        document = source / "paper.md"
        document.write_text("source", encoding="utf-8")
        writes = []
        diffs = []

        async def init(_config):
            writes.append("init")
            return 1, 2, source, {"app"}

        async def file(_target, _config):
            writes.append("file")
            return "paper", 1

        async def folder(_target, _config):
            writes.append("folder")
            return 1, 2

        async def diff(_target, _config):
            diffs.append("diff")
            return {"missing_from_store": [], "missing_from_disk": ["removed.md"]}

        async def prune(_target, _config):
            writes.append("prune")
            return ["removed"]

        operations = SimpleNamespace(init_workspace=init, ingest_file=file, ingest_folder=folder,
                                     diff_folder=diff, prune_folder=prune, workspace_root=source)
        service = _service(tmp_path, session_factory=_SessionFactory(), knowledge_operations=operations)
        await service.dispatch("session.create", {"loadMcp": False})
        await service.dispatch("session.set_bash_permission", {"mode": mode})
        command = {"init": "/init", "file": f"/ingest {document}", "folder": f"/ingest {source}", "prune": f"/prune {source}"}[kind]
        if kind == "prune" and mode == "ask":
            preview = await service.dispatch("session.turn", _turn_params(command))
            assert "removed.md" in preview["text"] and writes == []
            command += " --yes"
        sink = _ApprovalSink(service, approve=approved)
        if mode == "ask" and not approved:
            with pytest.raises(DesktopServiceError) as raised:
                await service.dispatch("session.turn", _turn_params(command), event_sink=sink)
            assert raised.value.code == "APPROVAL_DENIED"
        else:
            await service.dispatch("session.turn", _turn_params(command), event_sink=sink)
        await asyncio.gather(*sink.tasks)
        assert len(writes) == effects
        assert document.read_text() == "source"
        assert len(sink.approvals) == (mode == "ask")
        if kind == "prune" and effects:
            assert len(diffs) == 2
        if sink.approvals:
            event = sink.approvals[0]
            assert event["targetPath"] == str(document if kind == "file" else source)
            assert "storePath" in json.loads(event["parametersSummary"])
    asyncio.run(run())


@pytest.mark.parametrize("mode,approved,effects", [("ask", True, 1), ("ask", False, 0), ("bypass", False, 1)])
@pytest.mark.parametrize("kind", ["ingest", "prune"])
def test_direct_index_rpc_mutators_have_correlated_approval(tmp_path, monkeypatch, mode, approved, effects, kind):
    async def run():
        source = tmp_path / "source"
        source.mkdir()
        document = source / "paper.md"
        document.write_text("source", encoding="utf-8")
        writes = []

        async def ingest(_target, _config):
            writes.append("ingest")
            return "paper", 1

        async def diff(_target, _config):
            return {"missing_from_store": [], "missing_from_disk": ["removed.md"]}

        async def prune(_target, _config):
            writes.append("prune")
            return ["removed"]

        monkeypatch.setattr("agent.desktop.service.ingest_file", ingest)
        monkeypatch.setattr("agent.desktop.service.diff_folder", diff)
        monkeypatch.setattr("agent.desktop.service.prune_folder", prune)
        service = _service(tmp_path, session_factory=_SessionFactory())
        await service.dispatch("session.create", {"loadMcp": False})
        await service.dispatch("session.set_bash_permission", {"mode": mode})
        if kind == "ingest":
            method, params = "knowledge.ingest_file", {"path": str(document)}
        else:
            preview = await service.dispatch("knowledge.prune_preview", {"path": str(source)})
            method, params = "knowledge.prune_apply", {"previewId": preview["previewId"]}
        sink = _ApprovalSink(service, approve=approved)
        if mode == "ask" and not approved:
            with pytest.raises(DesktopServiceError) as raised:
                await service.dispatch(method, params, event_sink=sink)
            assert raised.value.code == "APPROVAL_DENIED"
        else:
            await service.dispatch(method, params, event_sink=sink)
        await asyncio.gather(*sink.tasks)
        assert len(writes) == effects
        assert len(sink.approvals) == (mode == "ask")
        if sink.approvals:
            assert sink.approvals[0]["parentRequestId"] == sink.request_id
    asyncio.run(run())


def test_bypass_prune_rechecks_preview_instead_of_silently_accepting_stale_set(tmp_path):
    async def run():
        source = tmp_path / "source"
        source.mkdir()
        called = []
        diffs = 0

        async def diff(_target, _config):
            nonlocal diffs
            diffs += 1
            return {"missing_from_store": [], "missing_from_disk": [f"removed-{diffs}.md"]}

        async def prune(*_args):
            called.append(True)
            return []

        ops = SimpleNamespace(diff_folder=diff, prune_folder=prune)
        service = _service(tmp_path, session_factory=_SessionFactory(), knowledge_operations=ops)
        await service.dispatch("session.create", {"loadMcp": False})
        await service.dispatch("session.set_bash_permission", {"mode": "bypass"})
        with pytest.raises(DesktopServiceError) as raised:
            await service.dispatch("session.turn", _turn_params(f"/prune {source}"))
        assert raised.value.code == "PRUNE_PREVIEW_STALE" and called == []
    asyncio.run(run())


@pytest.mark.parametrize("mode,approved_hashes,expected", [
    ("ask", [], set()), ("ask", ["a" * 64], {"a" * 64}), ("bypass", [], {"a" * 64}),
])
def test_extension_apply_uses_explicit_apply_or_current_bypass_bindings(tmp_path, mode, approved_hashes, expected):
    async def run():
        manager = _FakeExtensionManager(tmp_path)
        service = _service(tmp_path, session_factory=_SessionFactory(), extension_manager=manager)
        await service.dispatch("session.create", {"loadMcp": False})
        await service.dispatch("session.set_bash_permission", {"mode": mode})
        preview = await service.dispatch("extensions.preview", {})
        await service.dispatch("extensions.apply", {
            "previewId": preview["previewId"], "approvedBindingHashes": approved_hashes,
            "turnId": uuid.uuid4().hex, "retry": False,
        })
        assert manager.approved_bindings == expected and manager.apply_calls == 1
    asyncio.run(run())


def test_bypass_document_edit_still_reports_editor_and_disk_conflicts(tmp_path, monkeypatch):
    from test_desktop_document_service import _setup, _Sink

    async def run():
        service, _model, path, context = await _setup(tmp_path, monkeypatch)
        await service.dispatch("session.set_bash_permission", {"mode": "bypass"})
        path.write_text("outside edit\n", encoding="utf-8")
        sink = _Sink(service, {**context, "editorRevision": 1, "sourceText": "editor edit\n"})
        result = await service.dispatch("session.turn", {
            **_turn_params("改寫稿件"), "documentContext": context,
        }, event_sink=sink)
        await asyncio.gather(*sink.tasks)
        assert result["text"] == "Document operation: conflict."
        assert path.read_text() == "outside edit\n"
        assert sink.results[0]["candidateText"] and not any(event == "approval.required" for event, _ in sink.events)
    asyncio.run(run())


def test_document_and_bash_use_one_serial_approval_queue(tmp_path):
    async def run():
        service = _service(tmp_path, approval_timeout_seconds=0.2)
        service._turn_active = True
        service._active_turn_id = uuid.uuid4().hex
        service._active_parent_request_id = str(uuid.uuid4())
        service._active_turn_permission_mode = "ask"
        service._turn_loop = asyncio.get_running_loop()
        sink = _ApprovalSink(service)
        sink.request_id = service._active_parent_request_id
        service._turn_event_sink = sink
        context = {"path": str(tmp_path / "draft.md"), "sourceText": "draft\n"}
        document, bash = await asyncio.gather(
            service._document_operation_approval(event_sink=sink, parent_request_id=service._active_parent_request_id,
                turn_id=service._active_turn_id, operation="document.apply", context=context, permission_mode="ask"),
            asyncio.to_thread(service._desktop_bash_approval, "printf fixture", "Return fixture output.", 5),
        )
        await asyncio.gather(*sink.tasks)
        assert document[0] and bash and len(sink.approvals) == 2
        assert service._pending_approval is None
    asyncio.run(run())
