"""Strict, read-only legacy Plan-log migration tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from agent.config import AgentConfig
from agent.conversations.legacy_plan import (
    MAX_PLAN_RESTORE_FILES,
    LegacyPlanLogReader,
    PlanLogRestoreError,
)


SESSION_ID = "28b222e0cc6543aa8d7bbdc423de99a7"
OTHER_SESSION_ID = "f2ddf2369f994905afa0b85d8cca79b1"
TIMESTAMP = "2026-08-28T01:00:00+00:00"


def _reader(tmp_path: Path, session_id: str = SESSION_ID) -> LegacyPlanLogReader:
    return LegacyPlanLogReader(
        AgentConfig(plan_logs_dir="plan_logs"),
        session_id=session_id,
        app_root_resolver=lambda: tmp_path,
    )


def _path(tmp_path: Path, suffix: str = "010000") -> Path:
    log_dir = tmp_path / "plan_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"plan-{SESSION_ID}-20260828T{suffix}Z.md"


def _header(session_id: str = SESSION_ID, *, version: int = 1) -> str:
    version_line = "" if version == 1 else f"format_version: {version}\n"
    return (
        "---\n"
        "generated_by: agent.plan_mode\n"
        f"{version_line}"
        f"session_id: {session_id}\n"
        "created_at: 2026-08-28T01:00:00+00:00\n"
        "---\n\n"
        "# Plan log\n\n"
    )


def _v1_turn(
    turn_id: int = 1,
    *,
    user: str = "direct question",
    answer: str = "direct answer",
    tool_text: str = "",
) -> str:
    tools = f"\n\n{tool_text}" if tool_text else ""
    return (
        f"## Turn {turn_id} - {TIMESTAMP}\n\n"
        f"**User:**\n\n{user}{tools}\n\n"
        f"**Assistant:**\n\n{answer}\n\n"
        "---\n"
    )


def _v2_turn(
    turn_id: int = 1,
    *,
    user: str = "direct question",
    answer: str = "direct answer",
    scope: str = "normal",
    activities: list[object] | None = None,
) -> str:
    payload = json.dumps(
        {
            "format_version": 2,
            "turn_id": turn_id,
            "timestamp": TIMESTAMP,
            "user": user,
            "assistant": answer,
            "scope": scope,
            "tool_activities": activities or [],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (
        f"## Turn {turn_id} - {TIMESTAMP}\n\n"
        "**Turn data v2 (JSON):**\n\n"
        f"{payload}\n\n"
        "---\n"
    )


def _write(
    tmp_path: Path,
    body: str,
    *,
    version: int = 1,
    suffix: str = "010000",
    session_id: str = SESSION_ID,
) -> Path:
    path = _path(tmp_path, suffix)
    path.write_text(
        _header(session_id, version=version) + body,
        encoding="utf-8",
    )
    return path


def _activity(
    *,
    call_id: str = "call-1",
    name: str = "rag_search",
    arguments: str = '{"query":"safe"}',
    result: str = "safe result",
    status: str = "ok",
) -> dict[str, object]:
    return {
        "call_id": call_id,
        "name": name,
        "arguments": arguments,
        "result": result,
        "status": status,
    }


def test_v1_reader_restores_direct_answer_without_mutating_source(tmp_path):
    path = _write(
        tmp_path,
        _v1_turn(answer="direct answer\n\n```python\nprint('safe')\n```"),
    )
    before = path.read_bytes()

    turns = _reader(tmp_path).read_direct_answer_turns()

    assert len(turns) == 1
    assert turns[0].user_input == "direct question"
    assert turns[0].assistant_output.endswith("print('safe')\n```")
    assert turns[0].turn_id == 1
    assert turns[0].timestamp == TIMESTAMP
    assert not hasattr(turns[0], "persist_target")
    assert path.read_bytes() == before


def test_v1_tool_content_is_marked_display_only(tmp_path):
    secret = "private tool payload"
    tool_text = (
        "### Tool: rag_search\n\n"
        "```json\n{\"query\": \"legacy\"}\n```\n\n"
        f"**Result:**\n\n```\n{secret}\n```"
    )
    _write(tmp_path, _v1_turn(tool_text=tool_text))

    turn = _reader(tmp_path).read_direct_answer_turns()[0]

    assert len(turn.tool_activities) == 1
    activity = turn.tool_activities[0]
    assert activity.call_id is None
    assert activity.name == "rag_search"
    assert activity.result == secret
    assert activity.prompt_eligible is False


def test_v1_malformed_tool_is_isolated_from_the_answer(tmp_path):
    tool_text = "### Tool: rag_search\n\n```\nmalformed sentinel\n```"
    _write(tmp_path, _v1_turn(tool_text=tool_text))

    turn = _reader(tmp_path).read_direct_answer_turns()[0]

    assert turn.tool_activities[0].status == "incomplete"
    assert turn.tool_activities[0].prompt_eligible is False
    assert "malformed sentinel" in turn.tool_activities[0].result
    assert "malformed sentinel" not in turn.assistant_output


@pytest.mark.parametrize(
    "body,error",
    [
        (
            _v1_turn(answer="answer\n**Assistant:**\n\nsecond answer"),
            "marker is ambiguous",
        ),
        (
            f"## Turn 1 - {TIMESTAMP}\n\n**User:**\n\npartial",
            None,
        ),
    ],
)
def test_v1_reader_rejects_ambiguous_or_partial_turn(tmp_path, body, error):
    _write(tmp_path, body)

    with pytest.raises(PlanLogRestoreError, match=error):
        _reader(tmp_path).read_direct_answer_turns()


def test_v2_reader_restores_safe_tool_pair_metadata(tmp_path):
    arguments = {"query": "line one\n### Tool: not a marker\n```"}
    result = "unicode 臺灣\n**Result:**\n---\n## Turn 99 - payload"
    _write(
        tmp_path,
        _v2_turn(
            user="tool question",
            answer="final answer",
            activities=[_activity(
                arguments=json.dumps(
                    arguments,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                result=result,
            )],
        ),
        version=2,
    )

    turn = _reader(tmp_path).read_direct_answer_turns()[0]

    activity = turn.tool_activities[0]
    assert activity.call_id == "call-1"
    assert activity.name == "rag_search"
    assert activity.arguments == '{"query":"line one\\n### Tool: not a marker\\n```"}'
    assert activity.result == result
    assert activity.status == "ok"
    assert activity.prompt_eligible is True


def test_v2_citation_and_duplicate_calls_are_display_only(tmp_path):
    citation = _activity(call_id="citation-1", name="citation_workflow")
    duplicate_one = _activity(call_id="duplicate", result="one")
    duplicate_two = _activity(call_id="duplicate", result="two")
    _write(
        tmp_path,
        _v2_turn(activities=[citation, duplicate_one, duplicate_two]),
        version=2,
    )

    turn = _reader(tmp_path).read_direct_answer_turns()[0]

    assert [activity.prompt_eligible for activity in turn.tool_activities] == [
        False,
        False,
        False,
    ]


def test_v2_untrusted_prompt_flag_becomes_incomplete_display_only(tmp_path):
    activity = _activity()
    activity["promptEligible"] = True
    _write(
        tmp_path,
        _v2_turn(activities=[activity]),
        version=2,
    )

    restored = _reader(tmp_path).read_direct_answer_turns()[0].tool_activities[0]

    assert restored.name == "unknown"
    assert restored.status == "incomplete"
    assert restored.prompt_eligible is False


def test_v2_oversize_result_is_truncated_and_display_only(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "agent.conversations.legacy_plan.MAX_PLAN_TOOL_RESULT_BYTES",
        64,
    )
    _write(
        tmp_path,
        _v2_turn(activities=[_activity(result="界" * 100)]),
        version=2,
    )

    restored = _reader(tmp_path).read_direct_answer_turns()[0].tool_activities[0]

    assert "[truncated; original 300 bytes]" in restored.result
    assert restored.status == "incomplete"
    assert restored.prompt_eligible is False


@pytest.mark.parametrize(
    "original,replacement",
    [
        ('"scope":"normal"', '"scope":"normal","scope":"citation"'),
        ('"turn_id":1', '"turn_id":NaN'),
    ],
)
def test_v2_reader_rejects_non_strict_json(
    tmp_path,
    original,
    replacement,
):
    body = _v2_turn()
    assert original in body
    _write(tmp_path, body.replace(original, replacement), version=2)

    with pytest.raises(PlanLogRestoreError, match="payload is malformed"):
        _reader(tmp_path).read_direct_answer_turns()


@pytest.mark.parametrize(
    "version,scope,error",
    [
        (3, "normal", "version is unsupported"),
        (2, "fusion", "fusion Plan turns"),
    ],
)
def test_reader_rejects_unsupported_version_and_fusion_scope(
    tmp_path,
    version,
    scope,
    error,
):
    _write(tmp_path, _v2_turn(scope=scope), version=version)

    with pytest.raises(PlanLogRestoreError, match=error):
        _reader(tmp_path).read_direct_answer_turns()


@pytest.mark.parametrize("fault", ["wrong-session", "crlf", "bad-utf8"])
def test_reader_rejects_ambiguous_or_untrusted_file_content(tmp_path, fault):
    path = _write(tmp_path, _v1_turn())
    if fault == "wrong-session":
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                SESSION_ID,
                OTHER_SESSION_ID,
            ),
            encoding="utf-8",
        )
        error = "header is malformed"
    elif fault == "crlf":
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        error = "line endings are ambiguous"
    else:
        with path.open("ab") as handle:
            handle.write(b"\xff")
        error = "not UTF-8"

    with pytest.raises(PlanLogRestoreError, match=error):
        _reader(tmp_path).read_direct_answer_turns()


def test_reader_rejects_oversize_file(tmp_path):
    path = _path(tmp_path)
    path.write_text(_header() + ("x" * (1024 * 1024)), encoding="utf-8")

    with pytest.raises(PlanLogRestoreError, match="file limit"):
        _reader(tmp_path).read_direct_answer_turns()


@pytest.mark.parametrize("source_kind", ["symlink", "fifo"])
def test_reader_rejects_nonregular_source_without_following(tmp_path, source_kind):
    source = _path(tmp_path)
    if source_kind == "symlink":
        target = source.with_name("valid-target.md")
        target.write_text(_header() + _v1_turn(), encoding="utf-8")
        source.symlink_to(target)
    else:
        os.mkfifo(source)

    with pytest.raises(PlanLogRestoreError, match="unavailable or not UTF-8"):
        _reader(tmp_path).read_direct_answer_turns()


def test_reader_counts_each_file_toward_total_byte_limit(tmp_path, monkeypatch):
    first = _write(tmp_path, _v2_turn(1), version=2, suffix="010000")
    second = _write(tmp_path, _v2_turn(2), version=2, suffix="010001")
    monkeypatch.setattr(
        "agent.conversations.legacy_plan.MAX_PLAN_RESTORE_TOTAL_BYTES",
        first.stat().st_size + second.stat().st_size - 1,
    )

    with pytest.raises(PlanLogRestoreError, match="total limit"):
        _reader(tmp_path).read_direct_answer_turns()


def test_reader_rejects_too_many_matching_files(tmp_path, monkeypatch):
    path = _write(tmp_path, _v1_turn())
    monkeypatch.setattr(
        "agent.conversations.legacy_plan.Path.glob",
        lambda _self, _pattern: iter([path] * (MAX_PLAN_RESTORE_FILES + 1)),
    )

    with pytest.raises(PlanLogRestoreError, match="file-count limit"):
        _reader(tmp_path).read_direct_answer_turns()


def test_reader_rejects_noncanonical_session_id(tmp_path):
    with pytest.raises(PlanLogRestoreError, match="canonical UUIDv4"):
        _reader(tmp_path, "not-a-session").read_direct_answer_turns()
