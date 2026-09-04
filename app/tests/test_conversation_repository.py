"""Executable contract for the canonical per-conversation JSON repository."""

from __future__ import annotations

import json
import os
from dataclasses import replace

import pytest

import agent.conversations.repository as repository_module
from agent.conversations import (
    LATEST_CONTEXT_TURNS,
    MAX_CONVERSATION_BYTES,
    MAX_FAILURE_MESSAGE_BYTES,
    MAX_INPUT_BYTES,
    MAX_OUTPUT_BYTES,
    MAX_TOOL_ACTIVITIES,
    MAX_TOOL_SUMMARY_BYTES,
    ConversationConflictError,
    ConversationMalformedError,
    ConversationRepository,
    ConversationTooLargeError,
    ConversationUnavailableError,
    ConversationValidationError,
    FailureInfo,
    InvalidTransitionError,
    ToolActivitySummary,
)


CONVERSATION_ID = "28b222e0cc6543aa8d7bbdc423de99a7"


def _uuid4_hex(number: int) -> str:
    return f"00000000000040008000{number:012x}"


def _timestamp(number: int) -> str:
    return f"2026-09-04T00:{number:02d}:00Z"


def _create(
    repository: ConversationRepository,
    *,
    conversation_id: str = CONVERSATION_ID,
    turn_id: str | None = None,
    kind: str = "conversational",
    display_input: str = "display prompt",
    semantic_input: str | None = "semantic prompt",
    context_eligible: bool = True,
    thinking_mode: str | None = "normal",
):
    return repository.create(
        conversation_id=conversation_id,
        project_id="local",
        turn_id=turn_id or _uuid4_hex(1),
        kind=kind,
        display_input=display_input,
        semantic_input=semantic_input,
        context_eligible=context_eligible,
        thinking_mode=thinking_mode,
        submitted_at=_timestamp(1),
    )


def _append_completed(
    repository: ConversationRepository,
    snapshot,
    number: int,
    *,
    context_eligible: bool = True,
    kind: str = "conversational",
):
    display = f"display {number}"
    semantic = f"semantic {number}" if kind == "conversational" else None
    thinking = "extended" if number % 2 == 0 else "normal"
    pending = repository.append_pending(
        snapshot,
        turn_id=_uuid4_hex(number),
        kind=kind,
        display_input=display,
        semantic_input=semantic,
        context_eligible=context_eligible if kind == "conversational" else False,
        thinking_mode=thinking if kind == "conversational" else None,
        submitted_at=_timestamp(number),
    )
    return repository.complete_turn(
        pending,
        turn_id=_uuid4_hex(number),
        assistant_output=f"answer {number}",
        finished_at=_timestamp(number + 20),
    )


@pytest.mark.parametrize("thinking_mode", ["normal", "extended"])
def test_pending_completed_round_trip_is_strict_utf8_and_stable(
    tmp_path,
    thinking_mode,
):
    repository = ConversationRepository(tmp_path)
    snapshot = _create(
        repository,
        display_input="/skill 文獻\n第二行",
        semantic_input="實際送入模型的內容\n第二行",
        thinking_mode=thinking_mode,
    )

    assert snapshot.document.turns[0].state == "pending"
    assert repository.path_for(CONVERSATION_ID).exists()

    activity = ToolActivitySummary(
        call_id="call-1",
        name="rag_search",
        status="ok",
        summary="找到一筆可顯示結果",
    )
    completed = repository.complete_turn(
        snapshot,
        turn_id=_uuid4_hex(1),
        assistant_output="完成：αβγ\n保留換行",
        tool_activities=(activity,),
        finished_at=_timestamp(2),
    )
    loaded = repository.load(CONVERSATION_ID)

    assert loaded.document == completed.document
    assert loaded.document.conversation_id == CONVERSATION_ID
    assert loaded.document.project_id == "local"
    assert loaded.document.turns[0].turn_id == _uuid4_hex(1)
    assert loaded.document.turns[0].turn_number == 1
    assert loaded.document.turns[0].display_input == "/skill 文獻\n第二行"
    assert loaded.document.turns[0].semantic_input == "實際送入模型的內容\n第二行"
    assert loaded.document.turns[0].thinking_mode == thinking_mode
    assert loaded.document.turns[0].tool_activities == (activity,)

    raw = json.loads(repository.path_for(CONVERSATION_ID).read_text("utf-8"))
    assert set(raw) == {
        "schemaVersion",
        "conversationId",
        "projectId",
        "createdAt",
        "updatedAt",
        "turns",
    }
    assert set(raw["turns"][0]) == {
        "turnId",
        "turnNumber",
        "kind",
        "state",
        "displayInput",
        "semanticInput",
        "contextEligible",
        "thinkingMode",
        "submittedAt",
        "finishedAt",
        "assistantOutput",
        "toolActivities",
        "failure",
    }
    assert set(raw["turns"][0]["toolActivities"][0]) == {
        "callId",
        "name",
        "status",
        "summary",
    }


@pytest.mark.parametrize(
    ("terminal_state", "failure_code"),
    [("failed", "execution_failed"), ("interrupted", "interrupted")],
)
def test_transition_retry_and_duplicate_contract(
    tmp_path,
    terminal_state,
    failure_code,
):
    repository = ConversationRepository(tmp_path)
    snapshot = _create(repository)
    failed = repository.fail_turn(
        snapshot,
        turn_id=_uuid4_hex(1),
        state=terminal_state,
        failure=FailureInfo(
            code=failure_code,
            message="safe visible failure",
            retryable=True,
        ),
        finished_at=_timestamp(2),
    )

    retried = repository.retry_turn(
        failed,
        turn_id=_uuid4_hex(1),
        kind="conversational",
        display_input="display prompt",
        semantic_input="semantic prompt",
        context_eligible=True,
        thinking_mode="normal",
        retry_at=_timestamp(3),
    )
    assert len(retried.document.turns) == 1
    assert retried.document.turns[0].turn_number == 1
    assert retried.document.turns[0].state == "pending"

    completed = repository.complete_turn(
        retried,
        turn_id=_uuid4_hex(1),
        assistant_output="durable result",
        finished_at=_timestamp(4),
    )
    duplicate = repository.append_pending(
        completed,
        turn_id=_uuid4_hex(1),
        kind="conversational",
        display_input="display prompt",
        semantic_input="semantic prompt",
        context_eligible=True,
        thinking_mode="normal",
        submitted_at=_timestamp(5),
    )
    assert duplicate.document == completed.document
    assert duplicate.document.turns[0].assistant_output == "durable result"

    with pytest.raises(ConversationConflictError, match="different input"):
        repository.append_pending(
            completed,
            turn_id=_uuid4_hex(1),
            kind="conversational",
            display_input="changed",
            semantic_input="changed",
            context_eligible=True,
            thinking_mode="normal",
            submitted_at=_timestamp(5),
        )
    with pytest.raises(InvalidTransitionError):
        repository.fail_turn(
            completed,
            turn_id=_uuid4_hex(1),
            state="failed",
            failure=FailureInfo(
                code="execution_failed",
                message="late failure",
                retryable=False,
            ),
            finished_at=_timestamp(5),
        )


def test_only_one_pending_turn_and_turn_numbers_are_contiguous(tmp_path):
    repository = ConversationRepository(tmp_path)
    snapshot = _create(repository)
    before = repository.path_for(CONVERSATION_ID).read_bytes()

    with pytest.raises(ConversationConflictError, match="pending"):
        repository.append_pending(
            snapshot,
            turn_id=_uuid4_hex(2),
            kind="conversational",
            display_input="two",
            semantic_input="two",
            context_eligible=True,
            thinking_mode="normal",
            submitted_at=_timestamp(2),
        )
    assert repository.path_for(CONVERSATION_ID).read_bytes() == before

    completed = repository.complete_turn(
        snapshot,
        turn_id=_uuid4_hex(1),
        assistant_output="one",
        finished_at=_timestamp(2),
    )
    second = repository.append_pending(
        completed,
        turn_id=_uuid4_hex(2),
        kind="conversational",
        display_input="two",
        semantic_input="two",
        context_eligible=True,
        thinking_mode="normal",
        submitted_at=_timestamp(3),
    )
    assert [turn.turn_number for turn in second.document.turns] == [1, 2]


def test_latest_ten_context_excludes_noneligible_records(tmp_path):
    repository = ConversationRepository(tmp_path)
    snapshot = repository.complete_turn(
        _create(repository, display_input="display 1", semantic_input="semantic 1"),
        turn_id=_uuid4_hex(1),
        assistant_output="answer 1",
        finished_at=_timestamp(2),
    )
    eligible_ids = [_uuid4_hex(1)]
    for number in range(2, 13):
        snapshot = _append_completed(repository, snapshot, number)
        eligible_ids.append(_uuid4_hex(number))

    snapshot = _append_completed(
        repository,
        snapshot,
        13,
        context_eligible=False,
    )
    snapshot = _append_completed(
        repository,
        snapshot,
        14,
        kind="display-only",
    )
    failed = repository.append_pending(
        snapshot,
        turn_id=_uuid4_hex(15),
        kind="conversational",
        display_input="failed",
        semantic_input="failed",
        context_eligible=True,
        thinking_mode="normal",
        submitted_at=_timestamp(15),
    )
    snapshot = repository.fail_turn(
        failed,
        turn_id=_uuid4_hex(15),
        state="failed",
        failure=FailureInfo(
            code="execution_failed",
            message="failed safely",
            retryable=True,
        ),
        finished_at=_timestamp(16),
    )

    context = repository.latest_context(snapshot)

    assert LATEST_CONTEXT_TURNS == 10
    assert [turn.turn_id for turn in context] == eligible_ids[-10:]
    assert [turn.user_input for turn in context] == [
        f"semantic {number}" for number in range(3, 13)
    ]
    assert [turn.assistant_output for turn in context] == [
        f"answer {number}" for number in range(3, 13)
    ]
    assert all(not hasattr(turn, "tool_activities") for turn in context)


def test_title_uses_first_valid_conversational_prompt_and_stays_stable(tmp_path):
    repository = ConversationRepository(tmp_path)
    snapshot = _create(
        repository,
        kind="display-only",
        display_input="/status",
        semantic_input=None,
        context_eligible=False,
        thinking_mode=None,
    )
    snapshot = repository.complete_turn(
        snapshot,
        turn_id=_uuid4_hex(1),
        assistant_output="local status",
        finished_at=_timestamp(2),
    )
    assert repository.summary(snapshot).title is None

    long_title = "  第一個   有效標題\n" + "界" * 100
    pending = repository.append_pending(
        snapshot,
        turn_id=_uuid4_hex(2),
        kind="conversational",
        display_input=long_title,
        semantic_input="semantic title",
        context_eligible=True,
        thinking_mode="normal",
        submitted_at=_timestamp(3),
    )
    title = repository.summary(pending).title
    assert title is not None
    assert title.startswith("第一個 有效標題 ")
    assert len(title.encode("utf-8")) <= 256

    failed = repository.fail_turn(
        pending,
        turn_id=_uuid4_hex(2),
        state="failed",
        failure=FailureInfo(
            code="execution_failed",
            message="failed",
            retryable=True,
        ),
        finished_at=_timestamp(4),
    )
    later = _append_completed(repository, failed, 3)
    assert repository.summary(later).title == title

    before = repository.path_for(CONVERSATION_ID).read_bytes()
    with pytest.raises(ConversationValidationError, match="semanticInput"):
        repository.append_pending(
            later,
            turn_id=_uuid4_hex(4),
            kind="conversational",
            display_input="blank semantic input",
            semantic_input="   \n",
            context_eligible=True,
            thinking_mode="normal",
            submitted_at=_timestamp(5),
        )
    assert repository.path_for(CONVERSATION_ID).read_bytes() == before


def test_field_and_document_bounds_fail_before_publish(tmp_path):
    repository = ConversationRepository(tmp_path)
    maximum_input = "輸" * (MAX_INPUT_BYTES // len("輸".encode("utf-8")))
    maximum_input += "x" * (MAX_INPUT_BYTES - len(maximum_input.encode("utf-8")))
    maximum_output = "a" * MAX_OUTPUT_BYTES
    snapshot = _create(
        repository,
        display_input=maximum_input,
        semantic_input=maximum_input,
    )
    snapshot = repository.complete_turn(
        snapshot,
        turn_id=_uuid4_hex(1),
        assistant_output=maximum_output,
        finished_at=_timestamp(2),
    )
    assert repository.load(CONVERSATION_ID).document == snapshot.document

    oversized_id = _uuid4_hex(90)
    with pytest.raises(ConversationValidationError, match="displayInput"):
        _create(
            repository,
            conversation_id=oversized_id,
            display_input="x" * (MAX_INPUT_BYTES + 1),
            semantic_input="valid",
        )
    assert not repository.path_for(oversized_id).exists()

    pending_id = _uuid4_hex(91)
    pending = _create(repository, conversation_id=pending_id)
    before = repository.path_for(pending_id).read_bytes()
    with pytest.raises(ConversationValidationError, match="assistantOutput"):
        repository.complete_turn(
            pending,
            turn_id=_uuid4_hex(1),
            assistant_output="x" * (MAX_OUTPUT_BYTES + 1),
            finished_at=_timestamp(2),
        )
    assert repository.path_for(pending_id).read_bytes() == before

    with pytest.raises(ConversationValidationError, match="summary"):
        ToolActivitySummary(
            call_id=None,
            name="bash",
            status="ok",
            summary="x" * (MAX_TOOL_SUMMARY_BYTES + 1),
        )
    with pytest.raises(ConversationValidationError, match="message"):
        FailureInfo(
            code="execution_failed",
            message="x" * (MAX_FAILURE_MESSAGE_BYTES + 1),
            retryable=True,
        )
    activities = tuple(
        ToolActivitySummary(
            call_id=f"call-{index}",
            name="tool",
            status="ok",
            summary="ok",
        )
        for index in range(MAX_TOOL_ACTIVITIES + 1)
    )
    with pytest.raises(ConversationValidationError, match="toolActivities"):
        repository.complete_turn(
            pending,
            turn_id=_uuid4_hex(1),
            assistant_output="answer",
            tool_activities=activities,
            finished_at=_timestamp(2),
        )

    second_pending = repository.append_pending(
        snapshot,
        turn_id=_uuid4_hex(2),
        kind="conversational",
        display_input=maximum_input,
        semantic_input=maximum_input,
        context_eligible=True,
        thinking_mode="normal",
        submitted_at=_timestamp(3),
    )
    before_document_overflow = repository.path_for(CONVERSATION_ID).read_bytes()
    with pytest.raises(ConversationTooLargeError):
        repository.complete_turn(
            second_pending,
            turn_id=_uuid4_hex(2),
            assistant_output=maximum_output,
            finished_at=_timestamp(4),
        )
    assert (
        repository.path_for(CONVERSATION_ID).read_bytes()
        == before_document_overflow
    )


@pytest.mark.parametrize(
    ("location", "forbidden_key"),
    [
        ("root", "chainOfThought"),
        ("turn", "rawProviderPayload"),
        ("tool", "toolArgs"),
        ("failure", "apiKey"),
    ],
)
def test_closed_schema_rejects_hidden_or_untyped_payloads(
    tmp_path,
    location,
    forbidden_key,
):
    repository = ConversationRepository(tmp_path)
    snapshot = repository.complete_turn(
        _create(repository),
        turn_id=_uuid4_hex(1),
        assistant_output="answer mentioning token is ordinary user-visible text",
        tool_activities=(ToolActivitySummary(
            call_id="call-1",
            name="tool",
            status="ok",
            summary="safe summary",
        ),),
        finished_at=_timestamp(2),
    )
    raw = json.loads(repository.path_for(CONVERSATION_ID).read_text("utf-8"))
    bad_id = _uuid4_hex({"root": 40, "turn": 41, "tool": 42, "failure": 43}[location])
    raw["conversationId"] = bad_id
    if location == "root":
        raw[forbidden_key] = "never persist this"
    elif location == "turn":
        raw["turns"][0][forbidden_key] = {"internal": True}
    elif location == "tool":
        raw["turns"][0]["toolActivities"][0][forbidden_key] = {"raw": True}
    else:
        raw["turns"][0]["state"] = "failed"
        raw["turns"][0]["assistantOutput"] = None
        raw["turns"][0]["toolActivities"] = []
        raw["turns"][0]["failure"] = {
            "code": "execution_failed",
            "message": "safe",
            "retryable": True,
            forbidden_key: "secret-value",
        }
    repository.path_for(bad_id).write_text(
        json.dumps(raw, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ConversationMalformedError):
        repository.load(bad_id)
    scan = repository.scan()
    issue = next(item for item in scan.issues if item.conversation_id == bad_id)
    assert "never persist this" not in issue.message
    assert "secret-value" not in issue.message
    assert snapshot.document.turns[0].assistant_output.endswith("text")

    object_id = _uuid4_hex(44)
    with pytest.raises(ConversationValidationError, match="displayInput"):
        _create(
            repository,
            conversation_id=object_id,
            display_input=object(),
            semantic_input="semantic",
        )
    assert not repository.path_for(object_id).exists()


def test_scan_isolates_malformed_unknown_oversized_and_identity_mismatch(tmp_path):
    repository = ConversationRepository(tmp_path)
    good = repository.complete_turn(
        _create(repository),
        turn_id=_uuid4_hex(1),
        assistant_output="healthy answer",
        finished_at=_timestamp(2),
    )
    good_raw = json.loads(repository.path_for(CONVERSATION_ID).read_text("utf-8"))

    malformed_id = _uuid4_hex(50)
    repository.path_for(malformed_id).write_bytes(b"{not-json\xff")

    version_id = _uuid4_hex(51)
    version_raw = {**good_raw, "conversationId": version_id, "schemaVersion": 2}
    repository.path_for(version_id).write_text(json.dumps(version_raw), "utf-8")

    oversized_id = _uuid4_hex(52)
    repository.path_for(oversized_id).write_bytes(b"x" * (MAX_CONVERSATION_BYTES + 1))

    mismatch_id = _uuid4_hex(53)
    repository.path_for(mismatch_id).write_text(json.dumps(good_raw), "utf-8")

    scan = repository.scan()

    assert [item.conversation_id for item in scan.summaries] == [CONVERSATION_ID]
    assert scan.summaries[0].turn_count == 1
    assert scan.summaries[0].title == "display prompt"
    assert {issue.code for issue in scan.issues} == {
        "identity_mismatch",
        "malformed",
        "oversized",
        "unsupported_version",
    }
    assert all("healthy answer" not in issue.message for issue in scan.issues)
    assert repository.load(CONVERSATION_ID).document == good.document


def test_external_rewrite_and_replace_failure_preserve_existing_bytes(
    tmp_path,
    monkeypatch,
):
    repository = ConversationRepository(tmp_path)
    snapshot = repository.complete_turn(
        _create(repository),
        turn_id=_uuid4_hex(1),
        assistant_output="one",
        finished_at=_timestamp(2),
    )
    stale = repository.load(CONVERSATION_ID)
    other = ConversationRepository(tmp_path)
    external = _append_completed(other, other.load(CONVERSATION_ID), 2)
    path = repository.path_for(CONVERSATION_ID)
    external_bytes = path.read_bytes()

    with pytest.raises(ConversationConflictError, match="modified"):
        repository.append_pending(
            stale,
            turn_id=_uuid4_hex(3),
            kind="conversational",
            display_input="three",
            semantic_input="three",
            context_eligible=True,
            thinking_mode="normal",
            submitted_at=_timestamp(3),
        )
    assert path.read_bytes() == external_bytes
    assert external.document.turns[-1].turn_number == 2

    current = repository.load(CONVERSATION_ID)
    real_replace = repository_module.os.replace

    def fail_replace(_source, _destination):
        raise OSError("replace failed")

    monkeypatch.setattr(repository_module.os, "replace", fail_replace)
    with pytest.raises(ConversationUnavailableError, match="replace failed"):
        repository.append_pending(
            current,
            turn_id=_uuid4_hex(3),
            kind="conversational",
            display_input="three",
            semantic_input="three",
            context_eligible=True,
            thinking_mode="normal",
            submitted_at=_timestamp(3),
        )
    assert path.read_bytes() == external_bytes
    assert list(path.parent.glob("*.tmp")) == []

    events: list[str] = []
    real_fsync = repository_module.os.fsync

    def recording_fsync(descriptor):
        events.append("fsync")
        return real_fsync(descriptor)

    def recording_replace(source, destination):
        events.append("replace")
        return real_replace(source, destination)

    monkeypatch.setattr(repository_module.os, "fsync", recording_fsync)
    monkeypatch.setattr(repository_module.os, "replace", recording_replace)
    updated = repository.append_pending(
        repository.load(CONVERSATION_ID),
        turn_id=_uuid4_hex(3),
        kind="conversational",
        display_input="three",
        semantic_input="three",
        context_eligible=True,
        thinking_mode="normal",
        submitted_at=_timestamp(3),
    )
    replace_index = events.index("replace")
    assert "fsync" in events[:replace_index]
    assert "fsync" in events[replace_index + 1:]
    assert updated.document.turns[-1].turn_number == 3


@pytest.mark.parametrize("failure_stage", ["create", "write", "fsync"])
def test_pre_replace_temp_failures_preserve_existing_bytes_and_leave_no_residue(
    tmp_path,
    monkeypatch,
    failure_stage: str,
):
    repository = ConversationRepository(tmp_path)
    repository.complete_turn(
        _create(repository),
        turn_id=_uuid4_hex(1),
        assistant_output="one",
        finished_at=_timestamp(2),
    )
    current = repository.load(CONVERSATION_ID)
    path = repository.path_for(CONVERSATION_ID)
    before = path.read_bytes()

    if failure_stage == "create":
        def fail_mkstemp(*_args, **_kwargs):
            raise OSError("temporary creation failed")

        monkeypatch.setattr(repository_module.tempfile, "mkstemp", fail_mkstemp)
    elif failure_stage == "write":
        real_mkstemp = repository_module.tempfile.mkstemp

        def read_only_mkstemp(*args, **kwargs):
            descriptor, raw_path = real_mkstemp(*args, **kwargs)
            os.close(descriptor)
            return os.open(raw_path, os.O_RDONLY), raw_path

        monkeypatch.setattr(repository_module.tempfile, "mkstemp", read_only_mkstemp)
    else:
        def fail_fsync(_descriptor):
            raise OSError("temporary fsync failed")

        monkeypatch.setattr(repository_module.os, "fsync", fail_fsync)

    def forbid_replace(_source, _destination):
        raise AssertionError("replace must not run after a temporary-file failure")

    monkeypatch.setattr(repository_module.os, "replace", forbid_replace)
    with pytest.raises(ConversationUnavailableError):
        repository.append_pending(
            current,
            turn_id=_uuid4_hex(2),
            kind="conversational",
            display_input="two",
            semantic_input="two",
            context_eligible=True,
            thinking_mode="normal",
            submitted_at=_timestamp(3),
        )

    assert path.read_bytes() == before
    assert list(path.parent.glob("*.tmp")) == []


def test_save_rejects_invalid_document_without_touching_disk(tmp_path):
    repository = ConversationRepository(tmp_path)
    snapshot = _create(repository)
    before = repository.path_for(CONVERSATION_ID).read_bytes()
    invalid_turn = replace(snapshot.document.turns[0], turn_number=2)
    invalid_document = replace(snapshot.document, turns=(invalid_turn,))

    with pytest.raises(ConversationValidationError, match="contiguous"):
        repository.save(snapshot, invalid_document)
    assert repository.path_for(CONVERSATION_ID).read_bytes() == before

    rewritten_turn = replace(
        snapshot.document.turns[0],
        display_input="rewritten input",
    )
    rewritten_document = replace(snapshot.document, turns=(rewritten_turn,))
    with pytest.raises(InvalidTransitionError, match="immutable"):
        repository.save(snapshot, rewritten_document)
    assert repository.path_for(CONVERSATION_ID).read_bytes() == before

    duplicate_id = CONVERSATION_ID
    with pytest.raises(ConversationConflictError, match="already exists"):
        _create(repository, conversation_id=duplicate_id)
    assert repository.path_for(CONVERSATION_ID).read_bytes() == before


def test_nonregular_conversation_path_is_rejected_without_blocking(tmp_path):
    repository = ConversationRepository(tmp_path)
    repository.root.mkdir(parents=True, exist_ok=True)
    fifo_id = _uuid4_hex(80)
    os.mkfifo(repository.path_for(fifo_id))

    with pytest.raises(ConversationUnavailableError, match="regular file"):
        repository.load(fifo_id)

    issue = next(
        issue
        for issue in repository.scan().issues
        if issue.conversation_id == fifo_id
    )
    assert issue.code == "unavailable"


def test_document_limit_error_type_is_distinct_from_schema_errors(tmp_path):
    repository = ConversationRepository(tmp_path)
    oversized_id = _uuid4_hex(70)
    repository.root.mkdir(parents=True, exist_ok=True)
    repository.path_for(oversized_id).write_bytes(b"x" * (MAX_CONVERSATION_BYTES + 1))

    with pytest.raises(ConversationTooLargeError):
        repository.load(oversized_id)
    with pytest.raises(ConversationValidationError):
        FailureInfo(
            code="not_allowlisted",
            message="safe",
            retryable=False,
        )
