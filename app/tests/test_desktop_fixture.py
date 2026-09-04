"""Focused isolated no-provider desktop fixture tests."""

from __future__ import annotations

import asyncio
import itertools
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from agent.conversations import ConversationRepository
from agent.desktop.catalog import CATALOG_FILENAME, DesktopProjectCatalog
from agent.desktop.fixture_session import (
    FIXTURE_BASH_APPROVE,
    FIXTURE_BASH_DENY,
    FIXTURE_CHANGED_ORPHAN_MARKER,
    FIXTURE_DELAYED_FINAL,
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


@pytest.fixture
def phase07_fixture_root():
    configured = os.environ.get(FIXTURE_ROOT_ENV)
    if configured is not None:
        yield require_fixture_root({FIXTURE_ROOT_ENV: configured})
        return
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


_TURN_SEQUENCE = itertools.count(1)


def _turn_params(text: str, *, turn_id: str | None = None) -> dict[str, object]:
    logical_id = turn_id or f"00000000000040008000{next(_TURN_SEQUENCE):012x}"
    return {"text": text, "turnId": logical_id, "retry": False}


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
    asyncio.run(second.dispatch(
        "session.select",
        {"projectId": "p1", "sessionId": SESSION_A},
    ))
    transcripts = asyncio.run(second.dispatch(
        "session.transcript",
        {"projectId": "p1", "sessionId": SESSION_A, "limit": 20},
    ))
    assert transcripts["status"] == "ready"
    assert transcripts["items"][0]["userText"] == "A seed question"
    assert ConversationRepository(second.config.persist_dir).path_for(
        SESSION_A
    ).is_file()


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

        turn_id = "00000000000040008000000000001001"
        result = await service.dispatch(
            "session.turn",
            _turn_params("register D", turn_id=turn_id),
            event_sink=lambda event, data: events.append((event, data)),
        )
        assert result["turnId"] == turn_id
        assert result["turnNumber"] == 1
        assert result["state"] == "completed"
        assert result["accepted"] is True
        assert result["persisted"] is True
        assert result["registrationStatus"] == "registered"
        assert result["streamKind"] == "final_only"
        assert result["chunkCount"] == 0
        assert all(event != "answer.chunk" for event, _data in events)
        assert result["text"] not in repr(events)

        await service.dispatch(
            "session.select",
            {"projectId": "p1", "sessionId": SESSION_A},
        )
        await service.dispatch("session.turn", _turn_params("A second"))
        await service.dispatch(
            "session.select",
            {"projectId": "p1", "sessionId": SESSION_B},
        )
        await service.dispatch("session.turn", _turn_params("B second"))
        selected_a = await service.dispatch(
            "session.select",
            {"projectId": "p1", "sessionId": SESSION_A},
        )
        continued_a = await service.dispatch(
            "session.turn",
            _turn_params("A third"),
        )
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
    transient = ConversationRepository(service.config.persist_dir).load(transient_id)
    assert transient.document.turns[0].display_input == "register D"
    assert transient.document.turns[0].semantic_input == "register D"

    restarted = _service(fixture_root)
    reopened = asyncio.run(
        restarted.dispatch(
            "session.select",
            {"projectId": "p1", "sessionId": SESSION_A},
        )
    )
    assert reopened["turnCount"] == 3


def test_fixture_routes_fake_rag_and_knowledge_commands_without_real_data_writes(
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
            _turn_params(FIXTURE_RAG_QUESTION),
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
            await service.dispatch("session.turn", _turn_params(command))
            for command in commands
        ]
        empty_preview = await service.dispatch(
            "session.turn",
            _turn_params(f"/prune {source}"),
        )
        marker = source / FIXTURE_CHANGED_ORPHAN_MARKER
        marker.write_text("changed after preview\n", encoding="utf-8")
        try:
            with pytest.raises(DesktopServiceError) as changed:
                await service.dispatch(
                    "session.turn",
                    _turn_params(f"/prune {source} --yes"),
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
        "arguments": "(not retained)",
        "result": "Fixture knowledge search completed.",
        "status": "ok",
        "promptEligible": False,
    }]
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
    after_store = {
        path.relative_to(service.config.persist_dir): path.read_bytes()
        for path in Path(service.config.persist_dir).rglob("*")
        if path.is_file()
    }
    assert {
        path: content
        for path, content in after_store.items()
        if path.parts[0] != "conversations"
    } == {
        path: content
        for path, content in store_snapshot.items()
        if path.parts[0] != "conversations"
    }
    durable = ConversationRepository(service.config.persist_dir).load(SESSION_A)
    assert [turn.kind for turn in durable.document.turns[-8:]] == [
        "display-only"
    ] * 8
    assert durable.document.turns[-1].state == "failed"
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
        success_turn_id = "00000000000040008000000000002001"
        success = await service.dispatch(
            "session.turn",
            _turn_params("extended success", turn_id=success_turn_id),
            event_sink=lambda event, data: events.append((event, data)),
        )
        errors = []
        failed_turn_ids = [
            "00000000000040008000000000002002",
            "00000000000040008000000000002003",
        ]
        for marker, turn_id in zip(
            ("[[fixture:rate-limit]]", "[[fixture:provider-error]]"),
            failed_turn_ids,
            strict=True,
        ):
            try:
                await service.dispatch(
                    "session.turn",
                    _turn_params(marker, turn_id=turn_id),
                )
            except DesktopServiceError as exc:
                errors.append(exc)
        return thinking, events, success, errors, success_turn_id, failed_turn_ids

    thinking, events, success, errors, success_turn_id, failed_turn_ids = asyncio.run(
        run()
    )
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
    snapshot = ConversationRepository(service.config.persist_dir).load(SESSION_A)
    by_id = {turn.turn_id: turn for turn in snapshot.document.turns}
    assert by_id[success_turn_id].state == "completed"
    assert [by_id[turn_id].state for turn_id in failed_turn_ids] == [
        "failed",
        "failed",
    ]
    assert all(by_id[turn_id].assistant_output is None for turn_id in failed_turn_ids)


def test_switch_and_shutdown_leave_legacy_plan_logs_unchanged(
    fixture_root: Path,
) -> None:
    service = _service(fixture_root)
    plan_dir = Path(service.config.plan_logs_dir)
    legacy_before = {
        path: path.read_bytes()
        for path in plan_dir.glob("*.md")
    }

    async def run():
        await service.dispatch(
            "session.select",
            {"projectId": "p1", "sessionId": SESSION_A},
        )
        await service.dispatch(
            "session.turn",
            _turn_params("canonical before switch"),
        )
        selected = await service.dispatch(
            "session.select",
            {"projectId": "p1", "sessionId": SESSION_B},
        )
        shutdown = await service.dispatch("session.shutdown", {})
        return selected, shutdown

    selected, shutdown = asyncio.run(run())
    assert selected["sessionId"] == SESSION_B
    assert shutdown == {"status": "stopped"}
    assert {
        path: path.read_bytes()
        for path in plan_dir.glob("*.md")
    } == legacy_before
    canonical = ConversationRepository(service.config.persist_dir).load(SESSION_A)
    assert canonical.document.turns[-1].display_input == "canonical before switch"
    assert canonical.document.turns[-1].state == "completed"


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
            _turn_params("/extension-management status"),
        )
        preview_gate = await service.dispatch(
            "session.turn",
            _turn_params("/extension-management"),
        )
        direct_status = await service.dispatch("extensions.status", {})
        preview = await service.dispatch("extensions.preview", {})
        status_after_preview = await service.dispatch("extensions.status", {})
        binding = preview["bindings"][0]
        apply_turn_id = "00000000000040008000000000000549"
        apply_params = {
            "previewId": preview["previewId"],
            "approvedBindingHashes": [binding["bindingHash"]],
            "turnId": apply_turn_id,
            "retry": False,
        }
        applied = await service.dispatch(
            "extensions.apply",
            apply_params,
        )
        post_apply = await service.dispatch("extensions.status", {})
        replayed = await service.dispatch("extensions.apply", apply_params)
        return (
            created,
            status_turn,
            preview_gate,
            direct_status,
            preview,
            status_after_preview,
            applied,
            post_apply,
            replayed,
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
    assert replayed == applied

    restarted = _service(fixture_root)
    restarted_provider = restarted._extension_manager.model_factory.__self__

    async def run_restarted_process():
        loaded = await restarted.dispatch(
            "session.create",
            {"projectId": "p1", "loadMcp": True},
        )
        skill_turn = await restarted.dispatch(
            "session.turn",
            _turn_params('/fixture-writer Draft  "quoted"   body'),
        )
        ordinary_turn = await restarted.dispatch(
            "session.turn",
            _turn_params("ordinary follow-up"),
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
        '/fixture-writer Draft  "quoted"   body',
        "ordinary follow-up",
    ]
    snapshot = ConversationRepository(restarted.config.persist_dir).load(
        loaded["sessionId"]
    )
    skill_record = snapshot.document.turns[-2]
    assert skill_record.display_input == '/fixture-writer Draft  "quoted"   body'
    assert skill_record.semantic_input == 'Draft  "quoted"   body'
    assert status["runningRevision"] == 1
    assert status["restartRequired"] is False
    assert isinstance(restarted_provider, FixtureExtensionProvider)
    assert restarted_provider.calls == 0


def test_phase07_integrated_final_only_skill_tool_restore_journey(
    phase07_fixture_root: Path,
) -> None:
    root = phase07_fixture_root
    first = _service(root)

    async def run_first_process():
        created = await first.dispatch("session.create", {"projectId": "p1"})
        diagnostics = await first.dispatch("runtime.diagnostics", {})
        events: list[tuple[str, dict]] = []
        crossed_old_deadline = asyncio.Event()
        delayed_turn_id = "00000000000040008000000000003001"

        def capture(event: str, data: dict) -> None:
            events.append((event, data))
            if (
                event == "stage.changed"
                and data.get("stage") == "fixture.after-old-deadline"
            ):
                crossed_old_deadline.set()

        pending = asyncio.create_task(first.dispatch(
            "session.turn",
            _turn_params(FIXTURE_DELAYED_FINAL, turn_id=delayed_turn_id),
            event_sink=capture,
        ))
        await asyncio.wait_for(crossed_old_deadline.wait(), timeout=1)
        assert not pending.done()
        pending_snapshot = ConversationRepository(first.config.persist_dir).load(
            created["sessionId"]
        )
        assert pending_snapshot.document.turns[-1].turn_id == delayed_turn_id
        assert pending_snapshot.document.turns[-1].state == "pending"
        assert all(event != "answer.chunk" for event, _data in events)
        delayed = await asyncio.wait_for(pending, timeout=3)
        assert delayed["turnId"] == delayed_turn_id

        preview = await first.dispatch("extensions.preview", {})
        binding = preview["bindings"][0]
        applied = await first.dispatch(
            "extensions.apply",
            {
                "previewId": preview["previewId"],
                "approvedBindingHashes": [binding["bindingHash"]],
                "turnId": "00000000000040008000000000000706",
                "retry": False,
            },
        )
        shutdown = await first.dispatch("session.shutdown", {})
        return created, diagnostics, events, delayed, applied, shutdown

    created, diagnostics, delayed_events, delayed, applied, shutdown = asyncio.run(
        run_first_process()
    )
    delayed_stages = [
        data["stage"]
        for event, data in delayed_events
        if event == "stage.changed"
    ]
    assert created["registered"] is False
    assert diagnostics["mcpEnabled"] is True
    assert delayed_stages == [
        "fixture.prepare",
        "fixture.before-old-deadline",
        "fixture.after-old-deadline",
        "fixture.finalized",
    ]
    assert delayed["streamKind"] == "final_only"
    assert delayed["chunkCount"] == 0
    assert all(event != "answer.chunk" for event, _data in delayed_events)
    assert delayed["text"] not in repr(delayed_events)
    assert applied["restartRequired"] is True
    assert shutdown == {"status": "stopped"}

    tool_invocations: list[str] = []

    def counting_search(query: str) -> list[dict[str, str]]:
        tool_invocations.append(query)
        return [{
            "pid": "phase07-fixture-knowledge",
            "file_path": "fixture-notes.md",
            "text": f"Local fixture result for: {query}",
        }]

    second = _service(root)

    async def run_second_process():
        loaded = await second.dispatch("session.create", {"projectId": "p1"})
        diagnostics = await second.dispatch("runtime.diagnostics", {})
        assert second.session is not None
        before_skill_turn = second.session._turn_count
        skill_events: list[tuple[str, dict]] = []
        skill = await second.dispatch(
            "session.turn",
            _turn_params('/fixture-writer Draft  "quoted"   body'),
            event_sink=lambda event, data: skill_events.append((event, data)),
        )
        assert second.session._turn_count == before_skill_turn + 1
        ordinary = await second.dispatch(
            "session.turn",
            _turn_params("ordinary after skill"),
        )

        failed_events: list[tuple[str, dict]] = []
        with pytest.raises(DesktopServiceError) as failed:
            await second.dispatch(
                "session.turn",
                _turn_params("/fixture-writer [[fixture:provider-error]]"),
                event_sink=lambda event, data: failed_events.append((event, data)),
            )
        retry = await second.dispatch(
            "session.turn",
            _turn_params("retry after skill error"),
        )

        assert second.session is not None
        second.session._search_handler = counting_search
        tool_events: list[tuple[str, dict]] = []
        tool_answer = await second.dispatch(
            "session.turn",
            _turn_params(FIXTURE_RAG_QUESTION),
            event_sink=lambda event, data: tool_events.append((event, data)),
        )
        transcript = await second.dispatch(
            "session.transcript",
            {
                "projectId": "p1",
                "sessionId": loaded["sessionId"],
                "limit": 20,
            },
        )
        shutdown = await second.dispatch("session.shutdown", {})
        return (
            loaded,
            diagnostics,
            skill_events,
            skill,
            ordinary,
            failed.value,
            failed_events,
            retry,
            tool_events,
            tool_answer,
            transcript,
            shutdown,
        )

    (
        loaded,
        restarted_diagnostics,
        skill_events,
        skill,
        ordinary,
        skill_failure,
        failed_events,
        retry,
        tool_events,
        tool_answer,
        transcript,
        second_shutdown,
    ) = asyncio.run(run_second_process())
    assert restarted_diagnostics["mcpEnabled"] is True
    assert restarted_diagnostics["mcpFamilies"] == ["fixture-clock"]
    assert loaded["loadedSkills"] == ["fixture-writer"]
    assert "activeSkill" not in loaded and "taskMode" not in loaded
    assert skill["streamKind"] == "final_only" and skill["chunkCount"] == 0
    assert skill["text"].startswith("Fixture skill fixture-writer")
    assert all(event != "answer.chunk" for event, _data in skill_events)
    assert skill["text"] not in repr(skill_events)
    assert ordinary["streamKind"] == "final_only"
    assert "Fixture skill" not in ordinary["text"]
    assert skill_failure.code == "PROVIDER_REQUEST_FAILED"
    assert all(event != "answer.chunk" for event, _data in failed_events)
    assert retry["streamKind"] == "final_only"
    assert "Fixture skill" not in retry["text"]
    assert tool_answer["streamKind"] == "final_only"
    assert tool_answer["chunkCount"] == 0
    assert all(event != "answer.chunk" for event, _data in tool_events)
    assert tool_answer["text"] not in repr(tool_events)
    assert tool_invocations == [FIXTURE_RAG_QUESTION]
    assert all(
        item["userText"] != "[[fixture:provider-error]]"
        for item in transcript["items"]
    )
    tool_turn = next(
        item for item in transcript["items"]
        if item["userText"] == FIXTURE_RAG_QUESTION
    )
    assert tool_turn["toolActivities"][0]["name"] == "rag_search"
    assert tool_turn["toolActivities"][0]["promptEligible"] is False
    assert tool_turn["toolActivities"][0]["arguments"] == "(not retained)"
    assert second_shutdown == {"status": "stopped"}

    plan_dir = root / "plan_logs"
    for path in plan_dir.glob(f"plan-{SESSION_B}-*.md"):
        path.unlink()
    legacy_sentinel = "phase07 legacy tool sentinel"
    (plan_dir / f"plan-{SESSION_B}-20990101T000000Z.md").write_text(
        "---\n"
        "generated_by: agent.plan_mode\n"
        f"session_id: {SESSION_B}\n"
        "created_at: 2099-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Plan log\n\n"
        "## Turn 1 - 2099-01-01T00:00:01+00:00\n\n"
        "**User:**\n\nlegacy question\n\n"
        "### Tool: rag_search\n\n```json\n"
        '{"query": "legacy"}\n'
        "```\n\n**Result:**\n\n```\n"
        f"{legacy_sentinel}\n"
        "```\n\n**Assistant:**\n\nlegacy answer\n\n---\n",
        encoding="utf-8",
    )

    third = _service(root)
    third._session_factory._search_handler = counting_search

    async def run_third_process():
        await third.dispatch("session.create", {"projectId": "p1"})
        diagnostics = await third.dispatch("runtime.diagnostics", {})
        restored = await third.dispatch(
            "session.transcript",
            {
                "projectId": "p1",
                "sessionId": loaded["sessionId"],
                "limit": 20,
            },
        )
        selected = await third.dispatch(
            "session.select",
            {"projectId": "p1", "sessionId": loaded["sessionId"]},
        )
        continued_events: list[tuple[str, dict]] = []
        continued = await third.dispatch(
            "session.turn",
            _turn_params("continue after restore"),
            event_sink=lambda event, data: continued_events.append((event, data)),
        )
        legacy_selected = await third.dispatch(
            "session.select",
            {"projectId": "p1", "sessionId": SESSION_B},
        )
        legacy = await third.dispatch(
            "session.transcript",
            {"projectId": "p1", "sessionId": SESSION_B, "limit": 20},
        )
        shutdown = await third.dispatch("session.shutdown", {})
        return (
            diagnostics,
            restored,
            selected,
            continued_events,
            continued,
            legacy,
            legacy_selected,
            shutdown,
        )

    (
        final_diagnostics,
        restored,
        selected,
        continued_events,
        continued,
        legacy,
        legacy_selected,
        final_shutdown,
    ) = asyncio.run(run_third_process())
    assert final_diagnostics["mcpEnabled"] is True
    restored_snapshot = ConversationRepository(third.config.persist_dir).load(
        loaded["sessionId"]
    )
    assert selected["turnCount"] + 1 == len(restored_snapshot.document.turns)
    assert len(restored["items"]) + 1 == len(restored_snapshot.document.turns)
    assert any(item["state"] == "failed" for item in restored["items"])
    restored_tool_turn = next(
        turn
        for turn in restored_snapshot.document.turns
        if turn.semantic_input == FIXTURE_RAG_QUESTION
    )
    assert restored_tool_turn.tool_activities[0].summary == (
        "Fixture knowledge search completed."
    )
    assert tool_invocations == [FIXTURE_RAG_QUESTION]
    assert continued["streamKind"] == "final_only"
    assert continued["chunkCount"] == 0
    assert all(event != "answer.chunk" for event, _data in continued_events)
    assert continued["text"] not in repr(continued_events)
    assert legacy_selected["turnCount"] == 1
    assert legacy["items"][0]["toolActivities"] == []
    imported = ConversationRepository(third.config.persist_dir).load(SESSION_B)
    assert imported.document.turns[0].display_input == "legacy question"
    assert imported.document.turns[0].kind == "display-only"
    assert imported.document.turns[0].semantic_input is None
    assert imported.document.turns[0].tool_activities == ()
    assert legacy_sentinel not in repr(imported.document)
    assert tool_invocations == [FIXTURE_RAG_QUESTION]
    assert final_shutdown == {"status": "stopped"}


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
                _turn_params(marker),
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


def test_malformed_existing_catalog_is_rebuilt_from_canonical_conversations(
    fixture_root: Path,
) -> None:
    store = fixture_root / "store"
    store.mkdir()
    path = store / CATALOG_FILENAME
    original = b'{"projects":[{"unexpected":true}]}\n'
    path.write_bytes(original)

    service = _service(fixture_root)
    projects = asyncio.run(service.dispatch("project.list", {}))

    assert path.read_bytes() != original
    assert projects["status"] == "ready"
    assert projects["projects"] == [{
        "projectId": "local",
        "name": "Local research",
        "sessionCount": 0,
    }]
