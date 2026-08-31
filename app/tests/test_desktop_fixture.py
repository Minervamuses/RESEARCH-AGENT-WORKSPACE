"""Focused isolated no-provider desktop fixture tests."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

import pytest

from agent.desktop.catalog import CATALOG_FILENAME, DesktopProjectCatalog
from agent.desktop.fixture_session import (
    FIXTURE_BASH_APPROVE,
    FIXTURE_BASH_DENY,
    FIXTURE_CHANGED_ORPHAN_MARKER,
    FIXTURE_KNOWLEDGE_DIRNAME,
    FIXTURE_MODE,
    FIXTURE_MODE_ENV,
    FIXTURE_RAG_QUESTION,
    FIXTURE_ROOT_ENV,
    FIXTURE_ROOT_PREFIX,
    SESSION_A,
    SESSION_B,
    SESSION_C,
    FixtureConfigurationError,
    FixtureBashRunner,
    FixtureExtensionProvider,
    FixtureKnowledgeOperations,
    build_phase02_fixture_service,
    require_fixture_root,
)
from agent.desktop.service import DesktopServiceError


@pytest.fixture
def fixture_root():
    root = Path(tempfile.mkdtemp(prefix=FIXTURE_ROOT_PREFIX, dir="/tmp"))
    try:
        yield root
    finally:
        shutil.rmtree(root)
        assert not root.exists()


def _environ(root: Path) -> dict[str, str]:
    return {
        FIXTURE_MODE_ENV: FIXTURE_MODE,
        FIXTURE_ROOT_ENV: str(root),
        "CONDA_DEFAULT_ENV": "app",
        "CONDA_PREFIX": "/isolated/conda/app",
        "OPENROUTER_API_KEY": "must-not-be-copied",
    }


def _service(root: Path):
    return build_phase02_fixture_service(
        original_cwd=root,
        environ=_environ(root),
    )


@pytest.mark.parametrize(
    "raw",
    [
        "relative-fixture",
        "/tmp",
        "/var/tmp/research-agent-desktop-phase02-unsafe",
    ],
)
def test_fixture_root_rejects_missing_relative_or_unsafe_paths(raw: str) -> None:
    with pytest.raises(FixtureConfigurationError):
        require_fixture_root({FIXTURE_ROOT_ENV: raw})


def test_fixture_root_rejects_symlink(fixture_root: Path) -> None:
    link = Path("/tmp") / f"{FIXTURE_ROOT_PREFIX}symlink-{fixture_root.name}"
    try:
        link.symlink_to(fixture_root, target_is_directory=True)
        with pytest.raises(FixtureConfigurationError, match="non-symlink"):
            require_fixture_root({FIXTURE_ROOT_ENV: str(link)})
    finally:
        link.unlink(missing_ok=True)


def test_fixture_rejects_symlinked_child_store(fixture_root: Path) -> None:
    (fixture_root / "store").symlink_to(fixture_root, target_is_directory=True)

    with pytest.raises(FixtureConfigurationError, match="child roots"):
        _service(fixture_root)


def test_seed_is_deterministic_and_restart_preserves_catalog_order(
    fixture_root: Path,
) -> None:
    first = _service(fixture_root)
    first_projects = asyncio.run(first.dispatch("project.list", {}))
    assert [
        (item["projectId"], item["sessionCount"])
        for item in first_projects["projects"]
    ] == [("p1", 2), ("p2", 1)]
    snapshot = DesktopProjectCatalog(first.config.persist_dir).snapshot()
    assert snapshot == {
        "projects": [
            {
                "projectId": "p1",
                "name": "Project One",
                "sessionIds": [SESSION_A, SESSION_B],
            },
            {
                "projectId": "p2",
                "name": "Project Two",
                "sessionIds": [SESSION_C],
            },
        ]
    }
    original_catalog = (
        Path(first.config.persist_dir) / CATALOG_FILENAME
    ).read_bytes()

    second = _service(fixture_root)
    assert DesktopProjectCatalog(second.config.persist_dir).snapshot() == snapshot
    assert (
        Path(second.config.persist_dir) / CATALOG_FILENAME
    ).read_bytes() == original_catalog
    transcripts = asyncio.run(
        second.dispatch(
            "session.transcript",
            {"projectId": "p1", "sessionId": SESSION_A, "limit": 20},
        )
    )
    assert transcripts["status"] == "ready"
    assert transcripts["items"][0]["userText"] == "A seed question"


def test_real_service_round_trip_registration_restore_and_final_only_answer(
    fixture_root: Path,
) -> None:
    service = _service(fixture_root)
    events: list[tuple[str, dict]] = []

    async def run():
        created = await service.dispatch(
            "session.create",
            {"projectId": "p1", "loadMcp": True},
        )
        transient_id = created["sessionId"]
        assert created["registered"] is False
        before = DesktopProjectCatalog(service.config.persist_dir).snapshot()
        assert transient_id not in before["projects"][0]["sessionIds"]

        result = await service.dispatch(
            "session.turn",
            {"text": "register D"},
            event_sink=lambda event, data: events.append((event, data)),
        )
        assert result["registrationStatus"] == "registered"
        assert result["streamKind"] == "final_only"
        assert result["chunkCount"] == 0
        assert all(event != "answer.chunk" for event, _data in events)
        assert result["text"] not in repr(events)

        await service.dispatch(
            "session.select",
            {"projectId": "p1", "sessionId": SESSION_A},
        )
        await service.dispatch("session.turn", {"text": "A second"})
        await service.dispatch(
            "session.select",
            {"projectId": "p1", "sessionId": SESSION_B},
        )
        await service.dispatch("session.turn", {"text": "B second"})
        selected_a = await service.dispatch(
            "session.select",
            {"projectId": "p1", "sessionId": SESSION_A},
        )
        continued_a = await service.dispatch("session.turn", {"text": "A third"})
        return transient_id, selected_a, continued_a

    transient_id, selected_a, continued_a = asyncio.run(run())
    assert selected_a["turnCount"] == 2
    assert "turn 3" in continued_a["text"]
    assert "A second" in continued_a["text"]
    assert "B second" not in continued_a["text"]
    durable = DesktopProjectCatalog(service.config.persist_dir).snapshot()
    assert durable["projects"][0]["sessionIds"] == [
        SESSION_A,
        SESSION_B,
        transient_id,
    ]

    restarted = _service(fixture_root)
    reopened = asyncio.run(
        restarted.dispatch(
            "session.select",
            {"projectId": "p1", "sessionId": SESSION_A},
        )
    )
    assert reopened["turnCount"] == 3


def test_fixture_routes_fake_rag_and_knowledge_commands_without_real_store_writes(
    fixture_root: Path,
) -> None:
    service = _service(fixture_root)
    source = fixture_root / FIXTURE_KNOWLEDGE_DIRNAME
    document = source / "fixture-notes.md"
    events: list[tuple[str, dict]] = []

    async def run():
        await service.dispatch(
            "session.select",
            {"projectId": "p1", "sessionId": SESSION_A},
        )
        answer = await service.dispatch(
            "session.turn",
            {"text": FIXTURE_RAG_QUESTION},
            event_sink=lambda event, data: events.append((event, data)),
        )
        transcript = await service.dispatch(
            "session.transcript",
            {"projectId": "p1", "sessionId": SESSION_A, "limit": 20},
        )
        plan_logs = {
            path: path.read_bytes()
            for path in Path(service.config.plan_logs_dir).glob("*.md")
        }
        store_snapshot = {
            path.relative_to(service.config.persist_dir): path.read_bytes()
            for path in Path(service.config.persist_dir).rglob("*")
            if path.is_file()
        }
        source_snapshot = {
            path.relative_to(source): path.read_bytes()
            for path in source.rglob("*")
            if path.is_file()
        }
        commands = [
            "/init",
            f"/ingest {document}",
            f"/ingest {source}",
            f"/sync {source}",
            f"/prune {source}",
            f"/prune {source} --yes",
        ]
        results = [
            await service.dispatch("session.turn", {"text": command})
            for command in commands
        ]
        empty_preview = await service.dispatch(
            "session.turn",
            {"text": f"/prune {source}"},
        )
        marker = source / FIXTURE_CHANGED_ORPHAN_MARKER
        marker.write_text("changed after preview\n", encoding="utf-8")
        try:
            with pytest.raises(DesktopServiceError) as changed:
                await service.dispatch(
                    "session.turn",
                    {"text": f"/prune {source} --yes"},
                )
        finally:
            marker.unlink(missing_ok=True)
        return (
            answer,
            transcript,
            results,
            empty_preview,
            changed.value,
            plan_logs,
            store_snapshot,
            source_snapshot,
        )

    (
        answer,
        transcript,
        results,
        empty_preview,
        changed_error,
        plan_logs,
        store_snapshot,
        source_snapshot,
    ) = asyncio.run(run())

    assert answer["responseKind"] == "answer"
    assert answer["text"].startswith("Fixture knowledge says:")
    assert any(
        summary["name"] == "rag_search"
        for summary in answer["toolSummaries"]
    )
    assert any(
        event == "tool.finished" and data["name"] == "rag_search"
        for event, data in events
    )
    assert transcript["items"][-1]["toolActivities"] == [{
        "callId": "fixture-rag-search",
        "name": "rag_search",
        "arguments": f'{{"query":"{FIXTURE_RAG_QUESTION}"}}',
        "result": transcript["items"][-1]["toolActivities"][0]["result"],
        "status": "ok",
        "promptEligible": True,
    }]
    assert "fixture knowledge" in transcript["items"][-1]["toolActivities"][0][
        "result"
    ].casefold()
    assert all(result["responseKind"] == "command" for result in results)
    assert "fixture-file-pid" in results[1]["text"]
    assert "fixture-notes.md" in results[3]["text"]
    assert "removed-from-disk.md" in results[4]["text"]
    assert "pruned 1 orphaned pid(s)" in results[5]["text"]
    assert "Would prune 0 orphaned path(s)" in empty_preview["text"]
    assert changed_error.code == "PRUNE_PREVIEW_STALE"
    assert "previewId" not in repr(results)
    assert {
        path: path.read_bytes()
        for path in Path(service.config.plan_logs_dir).glob("*.md")
    } == plan_logs
    assert {
        path.relative_to(service.config.persist_dir): path.read_bytes()
        for path in Path(service.config.persist_dir).rglob("*")
        if path.is_file()
    } == store_snapshot
    assert {
        path.relative_to(source): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file()
    } == source_snapshot
    operations = service._knowledge_operations
    spy = operations.init_workspace.__self__
    assert isinstance(spy, FixtureKnowledgeOperations)
    assert [name for name, _target in spy.calls] == [
        "init",
        "ingest_file",
        "ingest_folder",
        "diff",
        "diff",
        "diff",
        "prune",
        "diff",
        "diff",
    ]


def test_extended_success_and_scripted_provider_errors_are_bounded(
    fixture_root: Path,
) -> None:
    service = _service(fixture_root)

    async def run():
        await service.dispatch(
            "session.select",
            {"projectId": "p1", "sessionId": SESSION_A},
        )
        thinking = await service.dispatch(
            "session.set_thinking",
            {"mode": "extended"},
        )
        events: list[tuple[str, dict]] = []
        success = await service.dispatch(
            "session.turn",
            {"text": "extended success"},
            event_sink=lambda event, data: events.append((event, data)),
        )
        errors = []
        for marker in ("[[fixture:rate-limit]]", "[[fixture:provider-error]]"):
            try:
                await service.dispatch("session.turn", {"text": marker})
            except DesktopServiceError as exc:
                errors.append(exc)
        return thinking, events, success, errors

    thinking, events, success, errors = asyncio.run(run())
    assert thinking["thinkingMode"] == "extended"
    assert success["text"].startswith("Fixture extended")
    assert [data["stage"] for event, data in events if event == "stage.changed"] == [
        "fixture.prepare",
        "fixture.extended.aggregate",
        "fixture.finalized",
    ]
    assert [error.code for error in errors] == [
        "PROVIDER_RATE_LIMITED",
        "PROVIDER_REQUEST_FAILED",
    ]
    assert [error.retryable for error in errors] == [True, True]
    assert all("synthetic" not in str(error) for error in errors)


def test_scripted_flush_failure_retains_current_conversation(
    fixture_root: Path,
) -> None:
    service = _service(fixture_root)

    async def run():
        await service.dispatch(
            "session.select",
            {"projectId": "p1", "sessionId": SESSION_A},
        )
        await service.dispatch(
            "session.turn",
            {"text": "[[fixture:flush-failure]]"},
        )
        with pytest.raises(DesktopServiceError) as captured:
            await service.dispatch(
                "session.select",
                {"projectId": "p1", "sessionId": SESSION_B},
            )
        return captured.value

    error = asyncio.run(run())
    assert error.code == "CONVERSATION_FLUSH_FAILED"
    assert error.retryable is True
    assert service.session is not None
    assert service.session.session_id == SESSION_A


def test_fixture_never_uses_chat_session_factory_or_exposes_credentials(
    fixture_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def forbidden_provider_factory(*_args, **_kwargs):
        raise AssertionError("real ChatSession factory must not run")

    monkeypatch.setattr("agent.session.ChatSession.create", forbidden_provider_factory)
    service = _service(fixture_root)
    diagnostics = asyncio.run(service.dispatch("runtime.diagnostics", {}))
    assert diagnostics["openRouterConfigured"] is False
    assert diagnostics["storePath"].startswith(str(fixture_root))
    result = asyncio.run(
        service.dispatch(
            "session.create",
            {"projectId": "p1", "loadMcp": True},
        )
    )
    assert result["mcpFamilies"] == []


def test_fixture_extension_preview_apply_and_restart_load_are_isolated(
    fixture_root: Path,
) -> None:
    service = _service(fixture_root)
    provider = service._extension_manager.model_factory.__self__
    assert isinstance(provider, FixtureExtensionProvider)

    async def run_first_process():
        created = await service.dispatch(
            "session.create",
            {"projectId": "p1", "loadMcp": True},
        )
        status_turn = await service.dispatch(
            "session.turn",
            {"text": "/extension-management status"},
        )
        preview_gate = await service.dispatch(
            "session.turn",
            {"text": "/extension-management"},
        )
        direct_status = await service.dispatch("extensions.status", {})
        preview = await service.dispatch("extensions.preview", {})
        status_after_preview = await service.dispatch("extensions.status", {})
        binding = preview["bindings"][0]
        applied = await service.dispatch(
            "extensions.apply",
            {
                "previewId": preview["previewId"],
                "approvedBindingHashes": [binding["bindingHash"]],
            },
        )
        post_apply = await service.dispatch("extensions.status", {})
        with pytest.raises(DesktopServiceError) as replayed:
            await service.dispatch(
                "extensions.apply",
                {
                    "previewId": preview["previewId"],
                    "approvedBindingHashes": [binding["bindingHash"]],
                },
            )
        return (
            created,
            status_turn,
            preview_gate,
            direct_status,
            preview,
            status_after_preview,
            applied,
            post_apply,
            replayed.value,
        )

    (
        created,
        status_turn,
        preview_gate,
        direct_status,
        preview,
        status_after_preview,
        applied,
        post_apply,
        replayed,
    ) = asyncio.run(run_first_process())
    assert created["extensionRevision"] == 0
    assert status_turn["extensionAction"] == "status"
    assert preview_gate["extensionAction"] == "preview"
    assert direct_status["appliedRevision"] == 0
    assert provider.calls == 1
    assert status_after_preview["appliedRevision"] == 0
    assert preview["proposedSkills"] == ["fixture-writer"]
    assert len(preview["bindings"]) == 1
    binding = preview["bindings"][0]
    assert binding["name"] == "fixture-clock"
    assert binding["server"] == "fixture-clock"
    assert binding["arguments"] == ["--stdio"]
    assert binding["environmentNames"] == ["FIXTURE_MODE"]
    assert binding["command"].startswith(str(fixture_root.resolve()))
    assert binding["workingDirectory"].startswith(str(fixture_root.resolve()))
    assert "must-not-be-copied" not in repr((direct_status, preview, applied))
    assert applied["previousRevision"] == 0
    assert applied["appliedRevision"] == 1
    assert applied["restartRequired"] is True
    assert {item["outcome"] for item in applied["items"]} == {"added"}
    assert post_apply["runningRevision"] == 0
    assert post_apply["restartRequired"] is True
    assert replayed.code == "EXTENSION_APPLY_FAILED"

    restarted = _service(fixture_root)
    restarted_provider = restarted._extension_manager.model_factory.__self__

    async def run_restarted_process():
        loaded = await restarted.dispatch(
            "session.create",
            {"projectId": "p1", "loadMcp": True},
        )
        skill_turn = await restarted.dispatch(
            "session.turn",
            {"text": '/fixture-writer Draft  "quoted"   body'},
        )
        ordinary_turn = await restarted.dispatch(
            "session.turn",
            {"text": "ordinary follow-up"},
        )
        transcript = await restarted.dispatch(
            "session.transcript",
            {
                "projectId": "p1",
                "sessionId": loaded["sessionId"],
                "limit": 20,
            },
        )
        status = await restarted.dispatch("extensions.status", {})
        return loaded, skill_turn, ordinary_turn, transcript, status

    loaded, skill_turn, ordinary_turn, transcript, status = asyncio.run(
        run_restarted_process()
    )
    assert loaded["extensionRevision"] == 1
    assert loaded["loadedSkills"] == ["fixture-writer"]
    assert "activeSkill" not in loaded
    assert "taskMode" not in loaded
    assert loaded["mcpFamilies"] == ["fixture-clock"]
    assert skill_turn["responseKind"] == "answer"
    assert "Fixture skill fixture-writer" in skill_turn["text"]
    assert ordinary_turn["responseKind"] == "answer"
    assert "Fixture skill" not in ordinary_turn["text"]
    assert [item["userText"] for item in transcript["items"][-2:]] == [
        'Draft  "quoted"   body',
        "ordinary follow-up",
    ]
    assert status["runningRevision"] == 1
    assert status["restartRequired"] is False
    assert isinstance(restarted_provider, FixtureExtensionProvider)
    assert restarted_provider.calls == 0


def test_fixture_bash_approval_and_denial_use_only_the_fake_runner(
    fixture_root: Path,
) -> None:
    service = _service(fixture_root)
    runner = service._bash_command_runner
    assert isinstance(runner, FixtureBashRunner)

    class EventSink:
        def __init__(self, request_id: str) -> None:
            self.request_id = request_id
            self.events: list[tuple[str, dict]] = []
            self.approval_ready = asyncio.Event()

        def __call__(self, event: str, data: dict) -> None:
            self.events.append((event, data))
            if event == "approval.required":
                self.approval_ready.set()

    async def decide(marker: str, approved: bool, request_id: str):
        sink = EventSink(request_id)
        turn = asyncio.create_task(
            service.dispatch(
                "session.turn",
                {"text": marker},
                event_sink=sink,
            )
        )
        await asyncio.wait_for(sink.approval_ready.wait(), timeout=2)
        approval = next(
            data for event, data in sink.events if event == "approval.required"
        )
        resolved = await service.dispatch(
            "approval.resolve",
            {
                "approvalId": approval["approvalId"],
                "parentRequestId": approval["parentRequestId"],
                "turnId": approval["turnId"],
                "approved": approved,
            },
        )
        result = await asyncio.wait_for(turn, timeout=2)
        return sink, approval, resolved, result

    async def run():
        await service.dispatch(
            "session.select",
            {"projectId": "p1", "sessionId": SESSION_A},
        )
        approved = await decide(
            FIXTURE_BASH_APPROVE,
            True,
            "00000000-0000-4000-8000-000000000501",
        )
        denied = await decide(
            FIXTURE_BASH_DENY,
            False,
            "00000000-0000-4000-8000-000000000502",
        )
        with pytest.raises(DesktopServiceError) as replayed:
            await service.dispatch(
                "approval.resolve",
                {
                    "approvalId": denied[1]["approvalId"],
                    "parentRequestId": denied[1]["parentRequestId"],
                    "turnId": denied[1]["turnId"],
                    "approved": True,
                },
            )
        return approved, denied, replayed.value

    approved, denied, replayed = asyncio.run(run())
    assert approved[1]["command"] == "printf fixture-approved"
    assert approved[1]["executionTimeoutSeconds"] == 5
    assert approved[2]["approved"] is True
    assert approved[3]["toolSummaries"] == [{
        "name": "bash",
        "status": "ok",
        "callId": "fixture-bash-2",
    }]
    assert denied[1]["command"] == "printf fixture-denied"
    assert denied[2]["approved"] is False
    assert denied[3]["toolSummaries"] == [{
        "name": "bash",
        "status": "denied",
        "callId": "fixture-bash-3",
    }]
    assert len(runner.calls) == 1
    assert runner.calls[0][0] == ("printf fixture-approved",)
    assert replayed.code == "APPROVAL_DENIED"


def test_malformed_existing_catalog_is_preserved_and_reported_unavailable(
    fixture_root: Path,
) -> None:
    store = fixture_root / "store"
    store.mkdir()
    path = store / CATALOG_FILENAME
    original = b'{"projects":[{"unexpected":true}]}\n'
    path.write_bytes(original)

    service = _service(fixture_root)
    projects = asyncio.run(service.dispatch("project.list", {}))

    assert path.read_bytes() == original
    assert projects["status"] == "unavailable"
    assert projects["projects"] == []
