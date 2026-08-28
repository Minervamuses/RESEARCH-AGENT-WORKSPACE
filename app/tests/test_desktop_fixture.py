"""Focused isolated no-provider desktop fixture tests."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

import pytest

from agent.desktop.catalog import CATALOG_FILENAME, DesktopProjectCatalog
from agent.desktop.fixture_session import (
    FIXTURE_MODE,
    FIXTURE_MODE_ENV,
    FIXTURE_ROOT_ENV,
    FIXTURE_ROOT_PREFIX,
    SESSION_A,
    SESSION_B,
    SESSION_C,
    FixtureConfigurationError,
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


def test_real_service_round_trip_transient_registration_restore_and_chunks(
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
        assert result["streamKind"] == "post_finalized"
        assert result["chunkCount"] >= 1
        chunks = [data for event, data in events if event == "answer.chunk"]
        assert [item["chunkIndex"] for item in chunks] == list(range(len(chunks)))
        assert "".join(item["text"] for item in chunks) == result["text"]
        assert all(item["sessionId"] == transient_id for item in chunks)

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
