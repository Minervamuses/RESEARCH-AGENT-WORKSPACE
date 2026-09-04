"""Phase 07 contracts for explicit catalog-wide legacy migration."""

from __future__ import annotations

import dataclasses
import json
import shutil
import tempfile
from collections import Counter
from pathlib import Path

import pytest

import agent.conversations as conversations
import agent.conversations.legacy as conversation_legacy
from agent.config import AgentConfig
from agent.conversations import ConversationRepository
from agent.conversations import migration as conversation_migration
from agent.desktop.fixture_session import (
    FIXTURE_MODE,
    FIXTURE_MODE_ENV,
    FIXTURE_ROOT_ENV,
    FIXTURE_ROOT_PREFIX,
    SESSION_A,
    SESSION_B,
    SESSION_C,
    build_phase02_fixture_service,
)


FIXTURE_CATALOG_MIGRATION_ENV = (
    "RESEARCH_AGENT_DESKTOP_FIXTURE_MIGRATE_CATALOG"
)
SESSION_D = "3b0c8d53d6b94d8a9b744f1b8cd4c960"
TURN_A = "00000000000040008000000000000001"
TIMESTAMP = "2026-08-28T01:00:00Z"


@pytest.fixture
def isolated_fixture_root():
    root = Path(tempfile.mkdtemp(prefix=FIXTURE_ROOT_PREFIX, dir="/tmp"))
    try:
        yield root
    finally:
        shutil.rmtree(root)
        assert not root.exists()


@pytest.fixture
def chroma_clone_calls(monkeypatch):
    calls: list[tuple[Path, Path]] = []
    real_clone = conversation_legacy._clone_chroma_source

    def recording_clone(root: Path, destination: Path) -> bool:
        calls.append((root, destination))
        return real_clone(root, destination)

    monkeypatch.setattr(
        conversation_legacy,
        "_clone_chroma_source",
        recording_clone,
    )
    return calls


def _fixture_environ(root: Path, *, migrate: str | None = None) -> dict[str, str]:
    environ = {
        FIXTURE_MODE_ENV: FIXTURE_MODE,
        FIXTURE_ROOT_ENV: str(root),
        "CONDA_DEFAULT_ENV": "app",
        "CONDA_PREFIX": "/isolated/conda/app",
    }
    if migrate is not None:
        environ[FIXTURE_CATALOG_MIGRATION_ENV] = migrate
    return environ


def _seed_completed(
    repository: ConversationRepository,
    conversation_id: str,
    project_id: str,
) -> bytes:
    snapshot = repository.create(
        conversation_id=conversation_id,
        project_id=project_id,
        turn_id=TURN_A,
        kind="conversational",
        display_input="canonical prompt",
        semantic_input="canonical prompt",
        context_eligible=True,
        thinking_mode="normal",
        submitted_at=TIMESTAMP,
    )
    repository.complete_turn(
        snapshot,
        turn_id=TURN_A,
        assistant_output="canonical answer",
        finished_at=TIMESTAMP,
    )
    return repository.path_for(conversation_id).read_bytes()


def _raw_pair(
    conversation_id: str,
    *,
    user: str,
    assistant: str,
) -> tuple[list[str], list[dict[str, object]]]:
    return (
        [user, assistant],
        [
            {
                "role": "user",
                "turn_id": 1,
                "session_id": conversation_id,
                "timestamp": TIMESTAMP,
            },
            {
                "role": "assistant",
                "turn_id": 1,
                "session_id": conversation_id,
                "timestamp": TIMESTAMP,
            },
        ],
    )


class _FakeChromaFactory:
    def __init__(
        self,
        source: Path,
        rows: dict[str, tuple[list[str], list[dict[str, object]]]],
    ) -> None:
        self.source = source
        self.rows = rows
        self.client_paths: list[Path] = []
        self.queries: list[str] = []
        self.collection_requests: list[dict[str, object]] = []
        self.close_count = 0

    def __call__(self, clone_path: str):
        factory = self
        clone = Path(clone_path)
        factory.client_paths.append(clone)
        assert clone != factory.source
        assert clone.is_dir()
        assert (clone / "marker.bin").read_bytes() == b"legacy source sentinel"

        class FakeCollection:
            def get(self, **kwargs):
                conversation_id = kwargs["where"]["session_id"]["$eq"]
                factory.queries.append(conversation_id)
                documents, metadatas = factory.rows[conversation_id]
                return {
                    "documents": list(documents),
                    "metadatas": list(metadatas),
                }

        class FakeClient:
            def get_collection(self, **kwargs):
                factory.collection_requests.append(dict(kwargs))
                return FakeCollection()

            def close(self):
                factory.close_count += 1

        return FakeClient()


def _legacy_setup(
    tmp_path: Path,
    rows: dict[str, tuple[list[str], list[dict[str, object]]]],
) -> tuple[AgentConfig, ConversationRepository, _FakeChromaFactory, Path]:
    persist_dir = tmp_path / "isolated-store"
    source = persist_dir / "chat_history"
    source.mkdir(parents=True)
    marker = source / "marker.bin"
    marker.write_bytes(b"legacy source sentinel")
    config = AgentConfig(
        persist_dir=str(persist_dir),
        plan_logs_dir=str(tmp_path / "isolated-plan-logs"),
    )
    return (
        config,
        ConversationRepository(persist_dir),
        _FakeChromaFactory(source, rows),
        marker,
    )


def _run_batch(
    config: AgentConfig,
    repository: ConversationRepository,
    targets: tuple[tuple[str, str], ...],
    factory,
):
    return conversation_migration.migrate_legacy_targets(
        config,
        repository,
        targets,
        chroma_client_factory=factory,
    )


def test_fixture_catalog_migration_is_default_off_and_exactly_opted_in(
    isolated_fixture_root: Path,
) -> None:
    default_service = build_phase02_fixture_service(
        original_cwd=isolated_fixture_root,
        environ=_fixture_environ(isolated_fixture_root),
    )
    repository = ConversationRepository(default_service.config.persist_dir)
    assert [repository.load_optional(item) for item in (SESSION_A, SESSION_B, SESSION_C)] == [
        None,
        None,
        None,
    ]

    nonexact_service = build_phase02_fixture_service(
        original_cwd=isolated_fixture_root,
        environ=_fixture_environ(isolated_fixture_root, migrate="true"),
    )
    repository = ConversationRepository(nonexact_service.config.persist_dir)
    assert [repository.load_optional(item) for item in (SESSION_A, SESSION_B, SESSION_C)] == [
        None,
        None,
        None,
    ]

    source_before = {
        path.name: path.read_bytes()
        for path in Path(nonexact_service.config.plan_logs_dir).glob("*.md")
    }
    opted_in_service = build_phase02_fixture_service(
        original_cwd=isolated_fixture_root,
        environ=_fixture_environ(isolated_fixture_root, migrate="1"),
    )
    repository = ConversationRepository(opted_in_service.config.persist_dir)
    assert [
        repository.load(item).document.project_id
        for item in (SESSION_A, SESSION_B, SESSION_C)
    ] == ["p1", "p1", "p2"]
    assert {
        path.name: path.read_bytes()
        for path in Path(opted_in_service.config.plan_logs_dir).glob("*.md")
    } == source_before


def test_empty_batch_is_lazy_and_internal(
    tmp_path: Path,
    chroma_clone_calls,
) -> None:
    config, repository, _factory, marker = _legacy_setup(tmp_path, {})
    calls = 0

    def must_not_open(_clone_path: str):
        nonlocal calls
        calls += 1
        raise AssertionError("an empty batch must not clone or initialize Chroma")

    results = _run_batch(config, repository, (), must_not_open)

    assert results == ()
    assert calls == 0
    assert chroma_clone_calls == []
    assert marker.read_bytes() == b"legacy source sentinel"
    assert "migrate_legacy_targets" not in conversations.__all__


def test_valid_target_is_success_marker_without_opening_legacy(
    tmp_path: Path,
    chroma_clone_calls,
) -> None:
    config, repository, _factory, marker = _legacy_setup(tmp_path, {})
    canonical_before = _seed_completed(repository, SESSION_A, "p1")
    calls = 0

    def must_not_open(_clone_path: str):
        nonlocal calls
        calls += 1
        raise AssertionError("a valid canonical target must bypass legacy sources")

    results = _run_batch(config, repository, ((SESSION_A, "p1"),), must_not_open)

    assert len(results) == 1
    assert results[0].conversation_id == SESSION_A
    assert results[0].project_id == "p1"
    assert results[0].result.status == "already_present"
    assert results[0].result.reason is None
    assert calls == 0
    assert chroma_clone_calls == []
    assert repository.path_for(SESSION_A).read_bytes() == canonical_before
    assert marker.read_bytes() == b"legacy source sentinel"


def test_catalog_order_and_per_conversation_failure_are_isolated(tmp_path: Path) -> None:
    malformed_b = (
        ["MALFORMED_SECRET_USER_B"],
        [{
            "role": "user",
            "turn_id": 1,
            "session_id": SESSION_B,
            "timestamp": TIMESTAMP,
        }],
    )
    rows = {
        SESSION_B: malformed_b,
        SESSION_C: _raw_pair(
            SESSION_C,
            user="SAFE_SECRET_USER_C",
            assistant="SAFE_SECRET_ANSWER_C",
        ),
    }
    config, repository, factory, marker = _legacy_setup(tmp_path, rows)
    canonical_before = _seed_completed(repository, SESSION_A, "p1")
    repository.root.mkdir(parents=True, exist_ok=True)
    invalid_target = repository.path_for(SESSION_D)
    invalid_target.write_bytes(b"{truncated canonical target")
    invalid_before = invalid_target.read_bytes()
    source_before = marker.read_bytes()

    results = _run_batch(
        config,
        repository,
        (
            (SESSION_A, "p1"),
            (SESSION_D, "p1"),
            (SESSION_B, "p1"),
            (SESSION_C, "p2"),
        ),
        factory,
    )

    assert [item.conversation_id for item in results] == [
        SESSION_A,
        SESSION_D,
        SESSION_B,
        SESSION_C,
    ]
    assert [item.result.status for item in results] == [
        "already_present",
        "failed",
        "failed",
        "created",
    ]
    assert [item.result.reason for item in results] == [
        None,
        "canonical_target_invalid",
        "legacy_read_failed",
        None,
    ]
    assert SESSION_A not in factory.queries
    assert SESSION_D not in factory.queries
    assert factory.queries == [SESSION_B, SESSION_C, SESSION_C]
    assert repository.path_for(SESSION_A).read_bytes() == canonical_before
    assert invalid_target.read_bytes() == invalid_before
    assert repository.load(SESSION_C).document.turns[0].assistant_output == (
        "SAFE_SECRET_ANSWER_C"
    )
    assert marker.read_bytes() == source_before


def test_multiple_missing_targets_share_one_chroma_snapshot_and_rerun_is_lazy(
    tmp_path: Path,
    chroma_clone_calls,
) -> None:
    rows = {
        SESSION_B: _raw_pair(
            SESSION_B,
            user="B private prompt",
            assistant="B private answer",
        ),
        SESSION_C: _raw_pair(
            SESSION_C,
            user="C private prompt",
            assistant="C private answer",
        ),
    }
    config, repository, factory, marker = _legacy_setup(tmp_path, rows)
    source_before = marker.read_bytes()
    targets = ((SESSION_B, "p1"), (SESSION_C, "p2"))

    first = _run_batch(config, repository, targets, factory)
    canonical_before = {
        conversation_id: repository.path_for(conversation_id).read_bytes()
        for conversation_id, _project_id in targets
    }
    second = _run_batch(config, repository, targets, factory)

    assert [item.result.status for item in first] == ["created", "created"]
    assert [item.result.status for item in second] == [
        "already_present",
        "already_present",
    ]
    assert len(factory.client_paths) == 1
    assert len(chroma_clone_calls) == 1
    assert factory.close_count == 1
    assert factory.collection_requests == [{
        "name": "chat_history",
        "embedding_function": None,
    }]
    assert Counter(factory.queries) == Counter({SESSION_B: 2, SESSION_C: 2})
    assert factory.queries == [SESSION_B, SESSION_B, SESSION_C, SESSION_C]
    clone = factory.client_paths[0]
    assert not clone.exists()
    assert {
        conversation_id: repository.path_for(conversation_id).read_bytes()
        for conversation_id, _project_id in targets
    } == canonical_before
    assert marker.read_bytes() == source_before


def test_batch_results_are_structured_and_never_echo_legacy_text(tmp_path: Path) -> None:
    secret_user = "RAW-USER-SECRET-DO-NOT-LOG"
    secret_answer = "RAW-ANSWER-SECRET-DO-NOT-LOG"
    rows = {
        SESSION_C: _raw_pair(
            SESSION_C,
            user=secret_user,
            assistant=secret_answer,
        )
    }
    config, repository, factory, _marker = _legacy_setup(tmp_path, rows)

    results = _run_batch(config, repository, ((SESSION_C, "p2"),), factory)
    serialized = json.dumps(
        [dataclasses.asdict(item) for item in results],
        ensure_ascii=False,
        sort_keys=True,
    )

    assert len(results) == 1
    assert dataclasses.is_dataclass(results[0])
    assert set(dataclasses.asdict(results[0])) == {
        "conversation_id",
        "project_id",
        "result",
    }
    assert secret_user not in serialized
    assert secret_answer not in serialized
    assert "created" in serialized
    assert SESSION_C in serialized
    assert repository.load(SESSION_C).document.turns[0].display_input == secret_user
