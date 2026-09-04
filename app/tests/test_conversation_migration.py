"""Focused contract tests for non-destructive legacy conversation import."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest
from langchain_core.documents import Document

from agent.config import AgentConfig
from agent.conversations import (
    ConversationRepository,
    ConversationUnavailableError,
)
from agent.conversations.legacy import (
    LegacyChromaReader,
    LegacyConversationReader,
    LegacyReadError,
    LegacySourceCount,
    legacy_turn_id,
)
from agent.conversations.legacy_plan import LegacyPlanLogReader
from agent.conversations.migration import ConversationMigrator
from agent.turns.memory import ToolActivityRecord, TurnRecord


SESSION_A = "28b222e0cc6543aa8d7bbdc423de99a7"
SESSION_B = "2f5d27696b57482b986df4d8c20f7ff1"


def _turn(
    number: int,
    user: str,
    answer: str,
    *,
    timestamp: str = "2026-08-28T01:00:00+00:00",
    activities: tuple[ToolActivityRecord, ...] = (),
) -> TurnRecord:
    return TurnRecord(
        user_input=user,
        assistant_output=answer,
        turn_id=number,
        timestamp=timestamp,
        persist_target="none",
        tool_activities=activities,
    )


def _reader(
    *,
    chroma=(),
    plan=(),
) -> LegacyConversationReader:
    return LegacyConversationReader(
        chroma_read=lambda _conversation_id: list(chroma),
        plan_read=lambda _conversation_id: list(plan),
    )


def _fake_chroma_reader(tmp_path, documents, observed=None) -> LegacyChromaReader:
    persist_dir = tmp_path / "legacy"
    source = persist_dir / "chat_history"
    source.mkdir(parents=True, exist_ok=True)
    (source / "marker.bin").write_bytes(b"legacy fixture")
    observed = observed if observed is not None else {}
    observed.setdefault("queries", [])
    observed.setdefault("client_paths", [])
    observed.setdefault("closed", 0)

    class FakeCollection:
        def get(self, **kwargs):
            observed["queries"].append(kwargs)
            return {
                "documents": [document.page_content for document in documents],
                "metadatas": [document.metadata for document in documents],
            }

    class FakeClient:
        def __init__(self, clone_path):
            observed["client_paths"].append(Path(clone_path))

        def get_collection(self, **_kwargs):
            return FakeCollection()

        def close(self):
            observed["closed"] += 1

    return LegacyChromaReader(persist_dir, client_factory=FakeClient)


def _v1_plan_log(session_id: str, turn: TurnRecord) -> str:
    return (
        "---\n"
        "generated_by: agent.plan_mode\n"
        f"session_id: {session_id}\n"
        "created_at: 2026-08-28T01:00:00+00:00\n"
        "---\n\n"
        "# Plan log\n\n"
        f"## Turn {turn.turn_id} - {turn.timestamp}\n\n"
        f"**User:**\n\n{turn.user_input}\n\n"
        f"**Assistant:**\n\n{turn.assistant_output}\n\n"
        "---\n"
    )


def _v2_plan_log(
    session_id: str,
    turn: TurnRecord,
    *,
    activities: list[object],
) -> str:
    payload = json.dumps(
        {
            "format_version": 2,
            "turn_id": turn.turn_id,
            "timestamp": turn.timestamp,
            "user": turn.user_input,
            "assistant": turn.assistant_output,
            "scope": "normal",
            "tool_activities": activities,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (
        "---\n"
        "generated_by: agent.plan_mode\n"
        "format_version: 2\n"
        f"session_id: {session_id}\n"
        "created_at: 2026-08-28T01:00:00+00:00\n"
        "---\n\n"
        "# Plan log\n\n"
        f"## Turn {turn.turn_id} - {turn.timestamp}\n\n"
        "**Turn data v2 (JSON):**\n\n"
        f"{payload}\n\n"
        "---\n"
    )


def test_chroma_pairs_import_in_order_with_deterministic_identity(tmp_path):
    documents = [
        Document(
            page_content=text,
            metadata={
                "role": role,
                "turn_id": number,
                "session_id": SESSION_A,
                "timestamp": timestamp,
            },
        )
        for number, timestamp, role, text in (
            (2, "2026-08-28T03:00:00+02:00", "assistant", "答二"),
            (1, "2026-08-28T00:00:00+00:00", "user", "問一"),
            (2, "2026-08-28T03:00:00+02:00", "user", "問二"),
            (1, "2026-08-28T00:00:00+00:00", "assistant", "答一"),
        )
    ]
    before = copy.deepcopy(documents)
    observed: dict[str, object] = {}
    chroma_reader = _fake_chroma_reader(tmp_path, documents, observed)
    repository = ConversationRepository(tmp_path / "target")
    migrator = ConversationMigrator(
        repository,
        LegacyConversationReader(chroma_read=chroma_reader),
    )

    result = migrator.import_conversation(SESSION_A, project_id="project-a")

    assert result.status == "created"
    assert result.source_counts == (LegacySourceCount("chroma", 2),)
    assert result.turn_count == 2
    assert result.dropped_activity_count == 0
    assert len(observed["queries"]) == 2
    assert all(query == {
        "where": {"session_id": {"$eq": SESSION_A}},
        "limit": 8193,
        "include": ["documents", "metadatas"],
    } for query in observed["queries"])
    assert observed["closed"] == 2
    snapshot = repository.load(SESSION_A)
    assert snapshot.document.conversation_id == SESSION_A
    assert snapshot.document.project_id == "project-a"
    assert snapshot.document.created_at == "2026-08-28T00:00:00Z"
    assert snapshot.document.updated_at == "2026-08-28T01:00:00Z"
    assert [turn.turn_number for turn in snapshot.document.turns] == [1, 2]
    assert [turn.turn_id for turn in snapshot.document.turns] == [
        legacy_turn_id(SESSION_A, 1),
        legacy_turn_id(SESSION_A, 2),
    ]
    assert [turn.display_input for turn in snapshot.document.turns] == ["問一", "問二"]
    assert [turn.assistant_output for turn in snapshot.document.turns] == ["答一", "答二"]
    assert [turn.submitted_at for turn in snapshot.document.turns] == [
        "2026-08-28T00:00:00Z",
        "2026-08-28T01:00:00Z",
    ]
    assert [turn.finished_at for turn in snapshot.document.turns] == [
        "2026-08-28T00:00:00Z",
        "2026-08-28T01:00:00Z",
    ]
    assert all(turn.state == "completed" for turn in snapshot.document.turns)
    assert all(turn.kind == "display-only" for turn in snapshot.document.turns)
    assert all(turn.semantic_input is None for turn in snapshot.document.turns)
    assert repository.latest_context(snapshot) == ()
    assert documents == before

    first_bytes = repository.path_for(SESSION_A).read_bytes()
    second = migrator.import_conversation(SESSION_A, project_id="project-a")
    assert second.status == "already_present"
    assert len(observed["queries"]) == 2
    assert repository.path_for(SESSION_A).read_bytes() == first_bytes
    assert len(repository.load(SESSION_A).document.turns) == 2


def test_chroma_migration_reader_opens_only_an_isolated_copy(tmp_path):
    persist_dir = tmp_path / "legacy"
    source = persist_dir / "chat_history"
    source.mkdir(parents=True)
    marker = source / "marker.bin"
    marker.write_bytes(b"source must remain unchanged")
    observed: dict[str, object] = {}

    class FakeCollection:
        def get(self, **kwargs):
            observed["query"] = kwargs
            return {
                "documents": ["question", "answer"],
                "metadatas": [
                    {
                        "role": "user",
                        "turn_id": 1,
                        "session_id": SESSION_A,
                        "timestamp": "2026-08-28T01:00:00+00:00",
                    },
                    {
                        "role": "assistant",
                        "turn_id": 1,
                        "session_id": SESSION_A,
                        "timestamp": "2026-08-28T01:00:00+00:00",
                    },
                ],
            }

    class FakeClient:
        def __init__(self, clone_path):
            clone = Path(clone_path)
            observed["clone"] = clone
            assert clone != source
            assert clone.is_dir()
            (clone / "marker.bin").write_bytes(b"client mutated only the clone")

        def get_collection(self, **kwargs):
            observed["collection"] = kwargs
            return FakeCollection()

        def close(self):
            observed["closed"] = True

    before = marker.read_bytes()
    reader = LegacyChromaReader(persist_dir, client_factory=FakeClient)

    turns = reader(SESSION_A)

    assert [(turn.user_input, turn.assistant_output) for turn in turns] == [
        ("question", "answer")
    ]
    assert marker.read_bytes() == before
    assert observed["closed"] is True
    clone = observed["clone"]
    assert isinstance(clone, Path)
    assert not clone.exists()
    assert observed["collection"] == {
        "name": "chat_history",
        "embedding_function": None,
    }
    assert observed["query"] == {
        "where": {"session_id": {"$eq": SESSION_A}},
        "limit": 8193,
        "include": ["documents", "metadatas"],
    }


def test_chroma_migration_reader_reads_real_temporary_chroma_without_writes(
    tmp_path,
):
    import chromadb

    persist_dir = tmp_path / "legacy"
    source = persist_dir / "chat_history"
    client = chromadb.PersistentClient(path=str(source))
    collection = client.create_collection(
        name="chat_history",
        embedding_function=None,
    )
    collection.add(
        ids=["user-1", "assistant-1"],
        embeddings=[[0.0, 1.0], [1.0, 0.0]],
        documents=["question", "answer"],
        metadatas=[
            {
                "role": "user",
                "turn_id": 1,
                "session_id": SESSION_A,
                "timestamp": "2026-08-28T01:00:00+00:00",
            },
            {
                "role": "assistant",
                "turn_id": 1,
                "session_id": SESSION_A,
                "timestamp": "2026-08-28T01:00:00+00:00",
            },
        ],
    )
    client.close()
    before = {
        path.relative_to(source): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file()
    }

    turns = LegacyChromaReader(persist_dir)(SESSION_A)

    assert [(turn.user_input, turn.assistant_output) for turn in turns] == [
        ("question", "answer")
    ]
    assert {
        path.relative_to(source): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file()
    } == before


def test_chroma_migration_reader_does_not_create_a_missing_source(tmp_path):
    persist_dir = tmp_path / "legacy"

    def must_not_open(_clone_path):
        raise AssertionError("a missing source must not initialize Chroma")

    reader = LegacyChromaReader(persist_dir, client_factory=must_not_open)

    assert reader(SESSION_A) == []
    assert not (persist_dir / "chat_history").exists()


@pytest.mark.parametrize("timestamp", ["not-a-timestamp", "2026-08-28T01:00:00"])
def test_chroma_migration_reader_rejects_invalid_or_naive_timestamps(
    tmp_path,
    timestamp,
):
    documents = [
        Document(
            page_content=text,
            metadata={
                "role": role,
                "turn_id": 1,
                "session_id": SESSION_A,
                "timestamp": timestamp,
            },
        )
        for role, text in (("user", "question"), ("assistant", "answer"))
    ]

    with pytest.raises(LegacyReadError, match="malformed"):
        _fake_chroma_reader(tmp_path, documents)(SESSION_A)


@pytest.mark.parametrize(
    "documents",
    [
        [Document(
                page_content="question",
                metadata={
                    "role": "user",
                    "turn_id": 1,
                    "session_id": SESSION_A,
                    "timestamp": "2026-08-28T01:00:00+00:00",
                },
            )],
        [
            Document(
                page_content=text,
                metadata={
                    "role": "user",
                    "turn_id": 1,
                    "session_id": SESSION_A,
                    "timestamp": "2026-08-28T01:00:00+00:00",
                },
            )
            for text in ("question one", "question two")
        ],
    ],
)
def test_chroma_migration_reader_fails_closed_on_broken_role_pairs(
    tmp_path,
    documents,
):
    with pytest.raises(LegacyReadError, match="malformed"):
        _fake_chroma_reader(tmp_path, documents)(SESSION_A)


def test_chroma_migration_reader_keeps_the_raw_query_bounded(tmp_path):
    documents = [
        Document(
            page_content="x",
            metadata={
                "role": "user",
                "turn_id": number + 1,
                "session_id": SESSION_A,
                "timestamp": "2026-08-28T01:00:00+00:00",
            },
        )
        for number in range(8193)
    ]
    observed: dict[str, object] = {}

    with pytest.raises(LegacyReadError, match="malformed"):
        _fake_chroma_reader(tmp_path, documents, observed)(SESSION_A)

    assert observed["queries"] == [{
        "where": {"session_id": {"$eq": SESSION_A}},
        "limit": 8193,
        "include": ["documents", "metadatas"],
    }]


@pytest.mark.parametrize("unsafe_kind", ["symlink", "fifo"])
def test_chroma_migration_reader_rejects_unsafe_source_entries(
    tmp_path,
    unsafe_kind,
):
    persist_dir = tmp_path / "legacy"
    source = persist_dir / "chat_history"
    source.mkdir(parents=True)
    unsafe = source / "unsafe-entry"
    if unsafe_kind == "symlink":
        outside = tmp_path / "outside"
        outside.write_text("must not be copied", encoding="utf-8")
        unsafe.symlink_to(outside)
    else:
        os.mkfifo(unsafe)

    def must_not_open(_clone_path):
        raise AssertionError("unsafe source must not initialize Chroma")

    reader = LegacyChromaReader(persist_dir, client_factory=must_not_open)

    with pytest.raises(LegacyReadError, match="symbolic link|non-regular"):
        reader(SESSION_A)


def test_plan_v1_v2_import_drops_all_legacy_tool_payloads(tmp_path):
    legacy_root = tmp_path / "legacy"
    log_dir = legacy_root / "plan_logs"
    log_dir.mkdir(parents=True)
    first = _turn(1, "legacy v1", "answer v1")
    second = _turn(2, "legacy v2", "answer v2")
    (log_dir / f"plan-{SESSION_A}-20260828T010000Z.md").write_text(
        _v1_plan_log(SESSION_A, first),
        encoding="utf-8",
    )
    (log_dir / f"plan-{SESSION_A}-20260828T020000Z.md").write_text(
        _v2_plan_log(
            SESSION_A,
            second,
            activities=[
                {
                    "call_id": "call-1",
                    "name": "bash",
                    "arguments": '{"api_key":"DO_NOT_PERSIST"}',
                    "result": "private reasoning and raw result DO_NOT_PERSIST",
                    "status": "ok",
                },
                {
                    "call_id": "call-2",
                    "name": "bash",
                    "arguments": "{}",
                    "result": "DO_NOT_PERSIST",
                    "status": "ok",
                    "unexpected_secret": "DO_NOT_PERSIST",
                },
                {
                    "call_id": "call-3",
                    "name": "bash",
                    "arguments": "{}",
                    "result": "X" * 65_537,
                    "status": "ok",
                },
            ],
        ),
        encoding="utf-8",
    )
    source_before = {
        path: path.read_bytes()
        for path in log_dir.iterdir()
    }
    config = AgentConfig(plan_logs_dir="plan_logs")

    def read_plan(conversation_id: str):
        return LegacyPlanLogReader(
            config,
            session_id=conversation_id,
            app_root_resolver=lambda: legacy_root,
        ).read_direct_answer_turns()

    repository = ConversationRepository(tmp_path / "target")
    result = ConversationMigrator(
        repository,
        LegacyConversationReader(plan_read=read_plan),
    ).import_conversation(SESSION_A, project_id=None)

    assert result.status == "created"
    assert result.source_counts == (LegacySourceCount("plan", 2),)
    assert result.dropped_activity_count == 3
    snapshot = repository.load(SESSION_A)
    assert [turn.display_input for turn in snapshot.document.turns] == [
        "legacy v1",
        "legacy v2",
    ]
    assert all(turn.tool_activities == () for turn in snapshot.document.turns)
    persisted = repository.path_for(SESSION_A).read_text(encoding="utf-8")
    assert "DO_NOT_PERSIST" not in persisted
    assert "private reasoning" not in persisted
    assert repository.latest_context(snapshot) == ()
    assert {
        path: path.read_bytes()
        for path in log_dir.iterdir()
    } == source_before


@pytest.mark.parametrize("invalid_target", ["malformed", "identity_mismatch"])
def test_existing_invalid_canonical_target_fails_closed(tmp_path, invalid_target):
    repository = ConversationRepository(tmp_path)
    repository.root.mkdir(parents=True)
    target = repository.path_for(SESSION_A)
    if invalid_target == "malformed":
        target.write_text("{", encoding="utf-8")
    else:
        other = repository.create(
            conversation_id=SESSION_B,
            project_id=None,
            turn_id=legacy_turn_id(SESSION_B, 1),
            kind="display-only",
            display_input="other",
            semantic_input=None,
            context_eligible=False,
            thinking_mode=None,
            submitted_at="2026-08-28T01:00:00Z",
        )
        other = repository.complete_turn(
            other,
            turn_id=legacy_turn_id(SESSION_B, 1),
            assistant_output="other answer",
            finished_at="2026-08-28T01:00:00Z",
        )
        target.write_bytes(repository.path_for(SESSION_B).read_bytes())
    before = target.read_bytes()

    result = ConversationMigrator(
        repository,
        _reader(chroma=[_turn(1, "question", "answer")]),
    ).import_conversation(SESSION_A, project_id=None)

    assert result.status == "failed"
    assert result.reason == "canonical_target_invalid"
    assert target.read_bytes() == before


def test_valid_existing_target_is_authoritative_without_reading_legacy(tmp_path):
    repository = ConversationRepository(tmp_path)
    snapshot = repository.create(
        conversation_id=SESSION_A,
        project_id=None,
        turn_id=legacy_turn_id(SESSION_A, 1),
        kind="display-only",
        display_input="existing",
        semantic_input=None,
        context_eligible=False,
        thinking_mode=None,
        submitted_at="2026-08-28T01:00:00Z",
    )
    snapshot = repository.complete_turn(
        snapshot,
        turn_id=legacy_turn_id(SESSION_A, 1),
        assistant_output="answer",
        finished_at="2026-08-28T01:00:00Z",
    )
    before = repository.path_for(SESSION_A).read_bytes()

    def must_not_read(_conversation_id):
        raise AssertionError("legacy source must not be read")

    result = ConversationMigrator(
        repository,
        LegacyConversationReader(chroma_read=must_not_read),
    ).import_conversation(SESSION_A, project_id=None)

    assert result.status == "already_present"
    assert result.turn_count == 1
    assert repository.path_for(SESSION_A).read_bytes() == before


def test_existing_target_with_other_project_fails_without_reading_legacy(tmp_path):
    repository = ConversationRepository(tmp_path)
    snapshot = repository.create(
        conversation_id=SESSION_A,
        project_id="project-a",
        turn_id=legacy_turn_id(SESSION_A, 1),
        kind="display-only",
        display_input="existing",
        semantic_input=None,
        context_eligible=False,
        thinking_mode=None,
        submitted_at="2026-08-28T01:00:00Z",
    )
    repository.complete_turn(
        snapshot,
        turn_id=legacy_turn_id(SESSION_A, 1),
        assistant_output="answer",
        finished_at="2026-08-28T01:00:00Z",
    )

    def must_not_read(_conversation_id):
        raise AssertionError("legacy source must not be read")

    result = ConversationMigrator(
        repository,
        LegacyConversationReader(chroma_read=must_not_read),
    ).import_conversation(SESSION_A, project_id="project-b")

    assert result.status == "failed"
    assert result.reason == "canonical_target_invalid"


def test_source_change_between_stage_and_publish_leaves_no_target(tmp_path):
    calls = 0

    def changing_source(_conversation_id):
        nonlocal calls
        calls += 1
        answer = "first" if calls == 1 else "changed"
        return [_turn(1, "question", answer)]

    repository = ConversationRepository(tmp_path)
    result = ConversationMigrator(
        repository,
        LegacyConversationReader(chroma_read=changing_source),
    ).import_conversation(SESSION_A, project_id=None)

    assert calls == 2
    assert result.status == "failed"
    assert result.reason == "legacy_source_changed"
    assert not repository.path_for(SESSION_A).exists()


def test_source_is_confirmed_after_document_staging(tmp_path, monkeypatch):
    answer = "first"

    def read_source(_conversation_id):
        return [_turn(1, "question", answer)]

    repository = ConversationRepository(tmp_path)
    migrator = ConversationMigrator(
        repository,
        LegacyConversationReader(chroma_read=read_source),
    )
    real_to_document = migrator._to_document

    def stage_then_change(snapshot, project_id):
        nonlocal answer
        document = real_to_document(snapshot, project_id)
        answer = "changed during staging"
        return document

    monkeypatch.setattr(migrator, "_to_document", stage_then_change)

    result = migrator.import_conversation(SESSION_A, project_id=None)

    assert result.status == "failed"
    assert result.reason == "legacy_source_changed"
    assert not repository.path_for(SESSION_A).exists()


def test_post_publish_durability_error_uses_valid_target_as_success_marker(
    tmp_path,
    monkeypatch,
):
    repository = ConversationRepository(tmp_path)

    def fail_after_publish():
        raise ConversationUnavailableError("injected directory fsync failure")

    monkeypatch.setattr(repository, "_fsync_root", fail_after_publish)
    result = ConversationMigrator(
        repository,
        _reader(chroma=[_turn(1, "question", "answer")]),
    ).import_conversation(SESSION_A, project_id=None)

    assert result.status == "created"
    assert result.reason is None
    assert repository.load(SESSION_A).document.turns[0].assistant_output == "answer"


@pytest.mark.parametrize(
    "chroma,plan",
    [
        ((_turn(1, "one", "answer"), _turn(3, "three", "answer")), ()),
        ((_turn(1, "one", "answer"),), (_turn(1, "duplicate", "answer"),)),
    ],
)
def test_gap_or_duplicate_source_fails_as_one_conversation(
    tmp_path,
    chroma,
    plan,
):
    repository = ConversationRepository(tmp_path)
    result = ConversationMigrator(
        repository,
        _reader(chroma=chroma, plan=plan),
    ).import_conversation(SESSION_A, project_id=None)

    assert result.status == "failed"
    assert result.reason == "legacy_read_failed"
    assert not repository.path_for(SESSION_A).exists()


def test_publish_failure_receives_complete_document_and_leaves_no_target(
    tmp_path,
    monkeypatch,
):
    repository = ConversationRepository(tmp_path)
    seen_documents = []

    def fail_publish(document):
        seen_documents.append(document)
        raise ConversationUnavailableError("injected publish failure")

    monkeypatch.setattr(repository, "create_document", fail_publish)
    result = ConversationMigrator(
        repository,
        _reader(
            chroma=[
                _turn(1, "one", "answer one"),
                _turn(2, "two", "answer two"),
            ],
        ),
    ).import_conversation(SESSION_A, project_id=None)

    assert result.status == "failed"
    assert result.reason == "canonical_publish_failed"
    assert len(seen_documents) == 1
    assert len(seen_documents[0].turns) == 2
    assert all(turn.state == "completed" for turn in seen_documents[0].turns)
    assert not repository.path_for(SESSION_A).exists()


def test_one_failed_conversation_does_not_block_another(tmp_path):
    def read_chroma(conversation_id: str):
        if conversation_id == SESSION_A:
            raise LegacyReadError("synthetic malformed source")
        return [_turn(1, "healthy", "answer")]

    repository = ConversationRepository(tmp_path)
    migrator = ConversationMigrator(
        repository,
        LegacyConversationReader(chroma_read=read_chroma),
    )

    failed = migrator.import_conversation(SESSION_A, project_id=None)
    created = migrator.import_conversation(SESSION_B, project_id=None)

    assert failed.status == "failed"
    assert failed.reason == "legacy_read_failed"
    assert created.status == "created"
    assert repository.load(SESSION_B).document.turns[0].display_input == "healthy"


def test_empty_sources_are_skipped_without_creating_a_marker(tmp_path):
    repository = ConversationRepository(tmp_path)
    result = ConversationMigrator(
        repository,
        _reader(),
    ).import_conversation(SESSION_A, project_id=None)

    assert result.status == "skipped"
    assert result.reason == "no_legacy_turns"
    assert result.source_counts == (
        LegacySourceCount("chroma", 0),
        LegacySourceCount("plan", 0),
    )
    assert not repository.path_for(SESSION_A).exists()


def test_legacy_turn_identity_is_stable_uuid4_and_input_sensitive():
    first = legacy_turn_id(SESSION_A, 1)

    assert legacy_turn_id(SESSION_A, 1) == first
    assert legacy_turn_id(SESSION_A, 2) != first
    assert legacy_turn_id(SESSION_B, 1) != first
    assert len(first) == 32
    assert first[12] == "4"
    assert first[16] in "89ab"
