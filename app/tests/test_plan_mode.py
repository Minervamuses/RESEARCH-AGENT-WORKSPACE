"""Plan-control cutover and strict legacy Plan-log reader tests."""

import asyncio
import os

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from conftest import FakeHistoryStore, make_astream_graph, tool_then_answer_updates

from agent.config import AgentConfig
from agent.turns.memory import TurnRecord
from agent.turns.plan_log import (
    MAX_PLAN_RESTORE_FILES,
    PlanLog,
    PlanLogRestoreError,
)
from agent.session import ChatSession


def _web_search_updates():
    return tool_then_answer_updates(
        "tavily_search",
        {"query": "plan mode"},
        "call-1",
        "search result payload",
        "final answer",
    )


def _turn_id(index: int) -> str:
    return f"00000000000040008000{index:012x}"


def _plan_log_bytes(log_dir) -> dict[str, bytes]:
    if not log_dir.exists():
        return {}
    return {path.name: path.read_bytes() for path in sorted(log_dir.glob("*.md"))}


def _write_legacy_log(tmp_path, config, session_id: str, body: str):
    log_dir = tmp_path / config.plan_logs_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"plan-{session_id}-20260828T010000Z.md"
    path.write_text(
        "---\n"
        "generated_by: agent.plan_mode\n"
        f"session_id: {session_id}\n"
        "created_at: 2026-08-28T01:00:00+00:00\n"
        "---\n\n"
        "# Plan log\n\n"
        f"{body}",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def make_session(monkeypatch, tmp_path):
    monkeypatch.setattr("agent.session.find_app_root", lambda: tmp_path)
    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _cfg, extra_tools=None, history_store=None, **kwargs: make_astream_graph(),
    )

    def _make(window: int = 2, graph=None):
        cfg = AgentConfig(persist_dir=str(tmp_path / "persist"))
        cfg.agent_recent_turns_window = window
        store = FakeHistoryStore()
        session = ChatSession(
            cfg,
            history_store=store,
        )
        if graph is not None:
            session.graph = graph
        return session, store, tmp_path / cfg.plan_logs_dir

    return _make


def test_plan_turn_uses_canonical_lifecycle_without_legacy_writes(make_session):
    observed_states: list[str] = []
    session = None

    def inspect_pending(_state):
        snapshot = session.conversation_repository.load(session.session_id)
        observed_states.append(snapshot.document.turns[-1].state)

    graph = make_astream_graph(on_state=inspect_pending)
    session, store, log_dir = make_session(window=2, graph=graph)
    legacy_before = _plan_log_bytes(log_dir)
    asyncio.run(session.enter_plan_mode())

    turn_id = _turn_id(1)
    outcome = asyncio.run(session.turn_outcome(
        "plan question",
        display_input="plan question",
        turn_id=turn_id,
    ))

    snapshot = session.conversation_repository.load(session.session_id)
    turn = snapshot.document.turns[-1]
    assert observed_states == ["pending"]
    assert (outcome.turn_id, outcome.turn_number, outcome.state) == (
        turn_id,
        1,
        "completed",
    )
    assert outcome.accepted is True and outcome.persisted is True
    assert turn.turn_id == turn_id
    assert turn.state == "completed"
    assert turn.display_input == "plan question"
    assert turn.semantic_input == "plan question"
    assert turn.thinking_mode == "normal"
    assert session.plan_mode is True
    assert session.plan_log_path is None
    assert _plan_log_bytes(log_dir) == legacy_before
    assert store.adds == []


def test_exit_plan_keeps_recent_turns_visible(make_session):
    session, store, log_dir = make_session(window=10)
    legacy_before = _plan_log_bytes(log_dir)
    asyncio.run(session.enter_plan_mode())
    asyncio.run(session.turn_outcome("plan q1", turn_id=_turn_id(2)))

    asyncio.run(session.exit_plan_mode())
    asyncio.run(session.turn_outcome("normal q2", turn_id=_turn_id(3)))

    assert [turn.user_input for turn in session.recent_turns] == [
        "plan q1",
        "normal q2",
    ]
    prompt_contents = [message.content for message in session._prompt_history()]
    assert "plan q1" in prompt_contents
    assert "normal q2" in prompt_contents
    snapshot = session.conversation_repository.load(session.session_id)
    assert [turn.turn_id for turn in snapshot.document.turns] == [
        _turn_id(2),
        _turn_id(3),
    ]
    assert all(turn.state == "completed" for turn in snapshot.document.turns)
    assert _plan_log_bytes(log_dir) == legacy_before
    assert store.adds == []


def test_resume_plan_control_leaves_legacy_log_read_only(make_session):
    session, store, log_dir = make_session(window=10)
    legacy = PlanLog(
        session.config,
        session_id=session.session_id,
        app_root_resolver=lambda: log_dir.parent,
    ).new_log_file()
    legacy_before = legacy.read_bytes()

    resumed_path = asyncio.run(session.resume_plan_mode(legacy))
    outcome = asyncio.run(session.turn_outcome(
        "new canonical plan turn",
        turn_id=_turn_id(4),
    ))

    assert resumed_path is None
    assert session.plan_mode is True
    assert session.plan_log_path is None
    assert legacy.read_bytes() == legacy_before
    assert outcome.state == "completed" and outcome.persisted is True
    turn = session.conversation_repository.load(
        session.session_id
    ).document.turns[-1]
    assert turn.turn_id == _turn_id(4)
    assert turn.semantic_input == "new canonical plan turn"
    assert store.adds == []


def test_plan_and_normal_turns_never_write_or_flush_legacy_chroma(
    make_session,
    monkeypatch,
):
    session, store, _log_dir = make_session(window=2)
    legacy_calls: list[str] = []

    async def reject_store(_turn):
        legacy_calls.append("store")
        raise AssertionError("legacy Chroma store must not be called")

    async def reject_flush():
        legacy_calls.append("flush")
        raise AssertionError("legacy Chroma flush must not be called")

    monkeypatch.setattr(session._turn_store, "store_turn", reject_store)
    monkeypatch.setattr(session._turn_store, "flush", reject_flush)
    asyncio.run(session.enter_plan_mode())
    asyncio.run(session.turn_outcome("plan", turn_id=_turn_id(5)))
    asyncio.run(session.exit_plan_mode())
    asyncio.run(session.turn_outcome("normal", turn_id=_turn_id(6)))
    asyncio.run(session.flush_recent_turns())

    assert legacy_calls == []
    assert store.adds == []
    snapshot = session.conversation_repository.load(session.session_id)
    assert [turn.semantic_input for turn in snapshot.document.turns] == [
        "plan",
        "normal",
    ]


def test_plan_write_seam_is_not_invoked(make_session, monkeypatch):
    session, store, _log_dir = make_session(window=2)
    asyncio.run(session.enter_plan_mode())

    def fail_append(_path, _block):
        raise AssertionError("retired Plan writer was invoked")

    monkeypatch.setattr(session, "_append_block_to_md", fail_append)

    outcome = asyncio.run(session.turn_outcome("q", turn_id=_turn_id(7)))

    assert outcome.state == "completed" and outcome.persisted is True
    assert session._turn_counter == 1
    assert session.conversation_repository.load(
        session.session_id
    ).document.turns[0].state == "completed"
    assert store.adds == []


def test_plan_tool_activity_persists_only_safe_canonical_summary(make_session):
    session, store, log_dir = make_session(
        window=2,
        graph=make_astream_graph(_web_search_updates()),
    )
    legacy_before = _plan_log_bytes(log_dir)
    asyncio.run(session.enter_plan_mode())
    asyncio.run(session.turn_outcome(
        "search for plan mode",
        turn_id=_turn_id(8),
    ))

    snapshot = session.conversation_repository.load(session.session_id)
    activity = snapshot.document.turns[0].tool_activities[0]
    assert activity.call_id == "call-1"
    assert activity.name == "tavily_search"
    assert activity.status == "ok"
    assert activity.summary == "Tool execution completed."
    persisted = session.conversation_repository.path_for(
        session.session_id
    ).read_text(encoding="utf-8")
    assert '"query"' not in persisted
    assert "search result payload" not in persisted
    assert _plan_log_bytes(log_dir) == legacy_before
    assert store.adds == []


def test_mode_hint_exists_only_while_plan_control_is_active(make_session):
    session, _store, _log_dir = make_session(window=10)
    asyncio.run(session.enter_plan_mode())

    history = session._prompt_history()
    hint_msgs = [m for m in history if "[Mode hint]" in str(getattr(m, "content", ""))]
    assert len(hint_msgs) == 1
    assert "conversation durability is unchanged" in hint_msgs[0].content
    assert "plan_logs/" not in hint_msgs[0].content

    asyncio.run(session.turn_outcome("plan question", turn_id=_turn_id(9)))
    asyncio.run(session.exit_plan_mode())
    exited = session._prompt_history()
    assert all(
        "[Mode hint]" not in str(getattr(message, "content", ""))
        for message in exited
    )


def test_mode_hint_absent_in_pure_normal_session(make_session):
    session, _store, _log_dir = make_session(window=10)
    asyncio.run(session.turn_outcome("normal question", turn_id=_turn_id(14)))

    history = session._prompt_history()
    hint_msgs = [m for m in history if "[Mode hint]" in str(getattr(m, "content", ""))]
    assert hint_msgs == []


def test_plan_control_does_not_persist_in_canonical_prompt_history(make_session):
    session, _store, _log_dir = make_session(window=2)
    asyncio.run(session.enter_plan_mode())
    asyncio.run(session.turn_outcome("plan q", turn_id=_turn_id(10)))
    asyncio.run(session.exit_plan_mode())
    for index in range(3):
        asyncio.run(session.turn_outcome(
            f"normal {index}",
            turn_id=_turn_id(11 + index),
        ))

    history = session._prompt_history()
    hint_msgs = [m for m in history if "[Mode hint]" in str(getattr(m, "content", ""))]
    assert hint_msgs == []
    contents = [str(getattr(message, "content", "")) for message in history]
    assert "plan q" in contents
    assert all(f"normal {index}" in contents for index in range(3))


def test_direct_answer_reader_round_trips_existing_plan_format(tmp_path):
    session_id = "28b222e0cc6543aa8d7bbdc423de99a7"
    config = AgentConfig(persist_dir=str(tmp_path / "persist"))
    plan_log = PlanLog(
        config,
        session_id=session_id,
        app_root_resolver=lambda: tmp_path,
    )
    path = plan_log.new_log_file()
    block = plan_log.render_block(
        turn_id=1,
        timestamp="2026-08-28T01:00:00+00:00",
        user_input="direct question",
        answer="direct answer\n\n```python\nprint('safe')\n```",
        new_messages=[],
        tool_calls=[],
    )
    plan_log.append_block(str(path), block)

    turns = plan_log.read_direct_answer_turns()

    assert len(turns) == 1
    assert turns[0] == TurnRecord(
        user_input="direct question",
        assistant_output="direct answer\n\n```python\nprint('safe')\n```",
        turn_id=1,
        timestamp="2026-08-28T01:00:00+00:00",
        persist_target="none",
    )


def test_v2_plan_log_round_trips_tool_pair_and_prompt_roles(tmp_path):
    session_id = "28b222e0cc6543aa8d7bbdc423de99a7"
    config = AgentConfig(persist_dir=str(tmp_path / "persist"))
    plan_log = PlanLog(
        config,
        session_id=session_id,
        app_root_resolver=lambda: tmp_path,
    )
    path = plan_log.new_log_file()
    arguments = {"query": "line one\n### Tool: not a marker\n```"}
    result = "unicode 臺灣\n**Result:**\n---\n## Turn 99 - payload"
    plan_log.append_block(
        str(path),
        plan_log.render_block(
            turn_id=1,
            timestamp="2026-08-28T01:00:00+00:00",
            user_input="tool question",
            answer="final answer",
            new_messages=[ToolMessage(content=result, tool_call_id="call-1")],
            tool_calls=[{
                "id": "call-1",
                "name": "rag_search",
                "args": arguments,
            }],
        ),
    )

    assert "format_version: 2\n" in path.read_text(encoding="utf-8")
    turns = plan_log.read_direct_answer_turns()

    assert len(turns) == 1
    assert len(turns[0].tool_activities) == 1
    activity = turns[0].tool_activities[0]
    assert activity.call_id == "call-1"
    assert activity.name == "rag_search"
    assert activity.arguments == '{"query":"line one\\n### Tool: not a marker\\n```"}'
    assert activity.result == result
    assert activity.status == "ok"
    assert activity.prompt_eligible is True
    messages = turns[0].to_messages()
    assert [type(message) for message in messages] == [
        HumanMessage,
        AIMessage,
        ToolMessage,
        AIMessage,
    ]
    assert messages[1].tool_calls == [{
        "name": "rag_search",
        "args": arguments,
        "id": "call-1",
        "type": "tool_call",
    }]
    assert messages[2].tool_call_id == "call-1"
    assert messages[2].content == result


def test_v2_citation_activity_is_display_only(tmp_path):
    session_id = "28b222e0cc6543aa8d7bbdc423de99a7"
    config = AgentConfig(persist_dir=str(tmp_path / "persist"))
    plan_log = PlanLog(
        config,
        session_id=session_id,
        app_root_resolver=lambda: tmp_path,
    )
    path = plan_log.new_log_file()
    plan_log.append_block(str(path), plan_log.render_block(
        turn_id=1,
        timestamp="2026-08-28T01:00:00+00:00",
        user_input="citation question",
        answer="citation answer",
        new_messages=[ToolMessage(
            content='{"saved":true}',
            tool_call_id="citation-1",
            name="citation_workflow",
        )],
        tool_calls=[{
            "id": "citation-1",
            "name": "citation_workflow",
            "args": {"action": "search"},
        }],
        scope="citation",
    ))
    plan_log.append_block(str(path), plan_log.render_block(
        turn_id=2,
        timestamp="2026-08-28T01:00:01+00:00",
        user_input="normal scope cannot restore Citation internals",
        answer="safe normal answer",
        new_messages=[ToolMessage(
            content='{"denied":true}',
            tool_call_id="citation-2",
            name="citation_workflow",
        )],
        tool_calls=[{
            "id": "citation-2",
            "name": "citation_workflow",
            "args": {"action": "search"},
        }],
        scope="normal",
    ))

    turns = plan_log.read_direct_answer_turns()

    for turn in turns:
        assert turn.tool_activities[0].name == "citation_workflow"
        assert turn.tool_activities[0].prompt_eligible is False
        assert [type(message) for message in turn.to_messages()] == [
            HumanMessage,
            AIMessage,
        ]


def test_v2_duplicate_orphan_and_oversize_activities_are_display_only(tmp_path):
    session_id = "28b222e0cc6543aa8d7bbdc423de99a7"
    config = AgentConfig(persist_dir=str(tmp_path / "persist"))
    config.plan_log_max_tool_chars = 64
    plan_log = PlanLog(
        config,
        session_id=session_id,
        app_root_resolver=lambda: tmp_path,
    )
    path = plan_log.new_log_file()
    duplicate_calls = [
        {"id": "duplicate", "name": "rag_search", "args": {"query": "one"}},
        {"id": "duplicate", "name": "rag_search", "args": {"query": "two"}},
    ]
    duplicate_results = [
        ToolMessage(content="one", tool_call_id="duplicate", name="rag_search"),
        ToolMessage(content="two", tool_call_id="duplicate", name="rag_search"),
    ]
    plan_log.append_block(str(path), plan_log.render_block(
        turn_id=1,
        timestamp="2026-08-28T01:00:00+00:00",
        user_input="duplicates",
        answer="handled duplicates",
        new_messages=duplicate_results,
        tool_calls=duplicate_calls,
    ))
    plan_log.append_block(str(path), plan_log.render_block(
        turn_id=2,
        timestamp="2026-08-28T01:00:01+00:00",
        user_input="orphan",
        answer="handled orphan",
        new_messages=[ToolMessage(
            content="orphan result",
            tool_call_id="orphan-1",
            name="rag_search",
        )],
        tool_calls=[],
    ))
    plan_log.append_block(str(path), plan_log.render_block(
        turn_id=3,
        timestamp="2026-08-28T01:00:02+00:00",
        user_input="oversize",
        answer="handled oversize",
        new_messages=[ToolMessage(
            content="界" * 100,
            tool_call_id="large-1",
            name="rag_search",
        )],
        tool_calls=[{
            "id": "large-1",
            "name": "rag_search",
            "args": {"query": "large"},
        }],
    ))

    turns = plan_log.read_direct_answer_turns()

    assert len(turns[0].tool_activities) == 2
    assert len(turns[1].tool_activities) == 1
    assert "[truncated; original 300 bytes]" in turns[2].tool_activities[0].result
    for turn in turns:
        assert all(
            activity.status == "incomplete"
            and activity.prompt_eligible is False
            for activity in turn.tool_activities
        )
        assert [type(message) for message in turn.to_messages()] == [
            HumanMessage,
            AIMessage,
        ]


def test_v2_on_disk_prompt_flag_is_malformed_display_only_not_authority(tmp_path):
    session_id = "28b222e0cc6543aa8d7bbdc423de99a7"
    config = AgentConfig(persist_dir=str(tmp_path / "persist"))
    plan_log = PlanLog(
        config,
        session_id=session_id,
        app_root_resolver=lambda: tmp_path,
    )
    path = plan_log.new_log_file()
    block = plan_log.render_block(
        turn_id=1,
        timestamp="2026-08-28T01:00:00+00:00",
        user_input="untrusted flag",
        answer="safe final",
        new_messages=[ToolMessage(
            content="result",
            tool_call_id="call-1",
            name="rag_search",
        )],
        tool_calls=[{
            "id": "call-1",
            "name": "rag_search",
            "args": {"query": "safe"},
        }],
    )
    block = block.replace(
        '"status":"ok"',
        '"status":"ok","promptEligible":true',
    )
    plan_log.append_block(str(path), block)

    turn = plan_log.read_direct_answer_turns()[0]

    assert turn.user_input == "untrusted flag"
    assert turn.assistant_output == "safe final"
    assert turn.tool_activities[0].name == "unknown"
    assert turn.tool_activities[0].status == "incomplete"
    assert turn.tool_activities[0].prompt_eligible is False


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
    session_id = "28b222e0cc6543aa8d7bbdc423de99a7"
    config = AgentConfig(persist_dir=str(tmp_path / "persist"))
    plan_log = PlanLog(
        config,
        session_id=session_id,
        app_root_resolver=lambda: tmp_path,
    )
    path = plan_log.new_log_file()
    block = plan_log.render_block(
        turn_id=1,
        timestamp="2026-08-28T01:00:00+00:00",
        user_input="strict JSON",
        answer="must reject malformed JSON",
        new_messages=[],
        tool_calls=[],
    )
    assert original in block
    plan_log.append_block(str(path), block.replace(original, replacement))

    with pytest.raises(PlanLogRestoreError, match="payload is malformed"):
        plan_log.read_direct_answer_turns()


def test_unknown_v2_header_version_fails_reader_and_resume(tmp_path):
    session_id = "28b222e0cc6543aa8d7bbdc423de99a7"
    config = AgentConfig(persist_dir=str(tmp_path / "persist"))
    plan_log = PlanLog(
        config,
        session_id=session_id,
        app_root_resolver=lambda: tmp_path,
    )
    path = plan_log.new_log_file()
    content = path.read_text(encoding="utf-8").replace(
        "format_version: 2",
        "format_version: 3",
    )
    path.write_text(content, encoding="utf-8")

    with pytest.raises(PlanLogRestoreError, match="version is unsupported"):
        plan_log.read_direct_answer_turns()
    with pytest.raises(ValueError, match="version is unsupported"):
        plan_log.resume_log_file(path)


def test_resumed_legacy_log_keeps_v1_writer_and_display_only_semantics(tmp_path):
    session_id = "28b222e0cc6543aa8d7bbdc423de99a7"
    config = AgentConfig(persist_dir=str(tmp_path / "persist"))
    path = _write_legacy_log(
        tmp_path,
        config,
        session_id,
        "## Turn 1 - 2026-08-28T01:00:00+00:00\n\n"
        "**User:**\n\nlegacy first\n\n"
        "**Assistant:**\n\nlegacy answer\n\n---\n",
    )
    plan_log = PlanLog(
        config,
        session_id=session_id,
        app_root_resolver=lambda: tmp_path,
    )

    assert plan_log.resume_log_file(path) == path
    assert plan_log.write_format_version == 1
    block = plan_log.render_block(
        turn_id=2,
        timestamp="2026-08-28T01:00:01+00:00",
        user_input="legacy tool question",
        answer="legacy tool answer",
        new_messages=[ToolMessage(
            content="legacy result",
            tool_call_id="legacy-call",
            name="rag_search",
        )],
        tool_calls=[{
            "id": "legacy-call",
            "name": "rag_search",
            "args": {"query": "legacy"},
        }],
    )
    assert "**Turn data v2" not in block
    assert "### Tool: rag_search" in block
    plan_log.append_block(str(path), block)

    turns = plan_log.read_direct_answer_turns()
    assert turns[1].tool_activities[0].call_id is None
    assert turns[1].tool_activities[0].prompt_eligible is False


def test_v2_fusion_scope_remains_non_restorable(tmp_path):
    session_id = "28b222e0cc6543aa8d7bbdc423de99a7"
    config = AgentConfig(persist_dir=str(tmp_path / "persist"))
    plan_log = PlanLog(
        config,
        session_id=session_id,
        app_root_resolver=lambda: tmp_path,
    )
    path = plan_log.new_log_file()
    plan_log.append_block(str(path), plan_log.render_block(
        turn_id=1,
        timestamp="2026-08-28T01:00:00+00:00",
        user_input="fusion question",
        answer="fusion answer",
        new_messages=[],
        tool_calls=[],
        scope="fusion",
    ))

    with pytest.raises(PlanLogRestoreError, match="fusion Plan turns"):
        plan_log.read_direct_answer_turns()


def test_legacy_reader_keeps_tool_content_display_only(tmp_path):
    session_id = "28b222e0cc6543aa8d7bbdc423de99a7"
    config = AgentConfig(persist_dir=str(tmp_path / "persist"))
    plan_log = PlanLog(
        config,
        session_id=session_id,
        app_root_resolver=lambda: tmp_path,
    )
    secret = "private tool payload"
    _write_legacy_log(
        tmp_path,
        config,
        session_id,
        "## Turn 1 - 2026-08-28T01:00:00+00:00\n\n"
        "**User:**\n\nquestion\n\n"
        "### Tool: rag_search\n\n```json\n"
        '{"query": "legacy"}\n'
        "```\n\n**Result:**\n\n```\n"
        f"{secret}\n"
        "```\n\n**Assistant:**\n\nanswer\n\n---\n",
    )

    turns = plan_log.read_direct_answer_turns()

    assert turns[0].user_input == "question"
    assert turns[0].assistant_output == "answer"
    assert len(turns[0].tool_activities) == 1
    assert turns[0].tool_activities[0].call_id is None
    assert turns[0].tool_activities[0].result == secret
    assert turns[0].tool_activities[0].prompt_eligible is False
    assert [type(message) for message in turns[0].to_messages()] == [
        HumanMessage,
        AIMessage,
    ]


def test_legacy_malformed_tool_is_isolated_when_turn_boundaries_are_clear(tmp_path):
    session_id = "28b222e0cc6543aa8d7bbdc423de99a7"
    config = AgentConfig(persist_dir=str(tmp_path / "persist"))
    plan_log = PlanLog(
        config,
        session_id=session_id,
        app_root_resolver=lambda: tmp_path,
    )
    _write_legacy_log(
        tmp_path,
        config,
        session_id,
        "## Turn 1 - 2026-08-28T01:00:00+00:00\n\n"
        "**User:**\n\nlegacy question\n\n"
        "### Tool: rag_search\n\n```\nmalformed sentinel\n```\n\n"
        "**Assistant:**\n\nlegacy answer\n\n---\n",
    )

    turn = plan_log.read_direct_answer_turns()[0]

    assert turn.user_input == "legacy question"
    assert turn.assistant_output == "legacy answer"
    assert turn.tool_activities[0].call_id is None
    assert turn.tool_activities[0].status == "incomplete"
    assert turn.tool_activities[0].prompt_eligible is False
    assert "malformed sentinel" in turn.tool_activities[0].result
    assert all(
        "malformed sentinel" not in str(message.content)
        for message in turn.to_messages()
    )


def test_direct_answer_reader_rejects_ambiguous_markers(tmp_path):
    session_id = "28b222e0cc6543aa8d7bbdc423de99a7"
    config = AgentConfig(persist_dir=str(tmp_path / "persist"))
    plan_log = PlanLog(
        config,
        session_id=session_id,
        app_root_resolver=lambda: tmp_path,
    )
    _write_legacy_log(
        tmp_path,
        config,
        session_id,
        "## Turn 1 - 2026-08-28T01:00:00+00:00\n\n"
        "**User:**\n\nquestion\n\n"
        "**Assistant:**\n\nanswer with a marker\n"
        "**Assistant:**\n\nsecond answer\n\n---\n",
    )

    with pytest.raises(PlanLogRestoreError, match="marker is ambiguous"):
        plan_log.read_direct_answer_turns()


def test_direct_answer_reader_rejects_partial_turn(tmp_path):
    session_id = "28b222e0cc6543aa8d7bbdc423de99a7"
    config = AgentConfig(persist_dir=str(tmp_path / "persist"))
    plan_log = PlanLog(
        config,
        session_id=session_id,
        app_root_resolver=lambda: tmp_path,
    )
    _write_legacy_log(
        tmp_path,
        config,
        session_id,
        "## Turn 1 - 2026-08-28T01:00:00+00:00\n\n"
        "**User:**\n\nquestion without an answer",
    )

    with pytest.raises(PlanLogRestoreError):
        plan_log.read_direct_answer_turns()


def test_direct_answer_reader_rejects_oversize_file(tmp_path):
    session_id = "28b222e0cc6543aa8d7bbdc423de99a7"
    config = AgentConfig(persist_dir=str(tmp_path / "persist"))
    plan_log = PlanLog(
        config,
        session_id=session_id,
        app_root_resolver=lambda: tmp_path,
    )
    path = plan_log.new_log_file()
    plan_log.append_block(str(path), "x" * (1024 * 1024))

    with pytest.raises(PlanLogRestoreError, match="file limit"):
        plan_log.read_direct_answer_turns()


@pytest.mark.parametrize("source_kind", ["symlink", "fifo"])
def test_direct_answer_reader_rejects_nonregular_source_without_following(
    tmp_path,
    source_kind,
):
    session_id = "28b222e0cc6543aa8d7bbdc423de99a7"
    config = AgentConfig(persist_dir=str(tmp_path / "persist"))
    plan_log = PlanLog(
        config,
        session_id=session_id,
        app_root_resolver=lambda: tmp_path,
    )
    source = plan_log.new_log_file()
    if source_kind == "symlink":
        target = source.with_name("valid-target.md")
        source.rename(target)
        source.symlink_to(target)
    else:
        source.unlink()
        os.mkfifo(source)

    with pytest.raises(PlanLogRestoreError, match="unavailable or not UTF-8"):
        plan_log.read_direct_answer_turns()


def test_plan_reader_rejects_wrong_session_header_and_bad_utf8(tmp_path):
    session_id = "28b222e0cc6543aa8d7bbdc423de99a7"
    config = AgentConfig(persist_dir=str(tmp_path / "persist"))
    plan_log = PlanLog(
        config,
        session_id=session_id,
        app_root_resolver=lambda: tmp_path,
    )
    path = plan_log.new_log_file()
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            session_id,
            "f2ddf2369f994905afa0b85d8cca79b1",
        ),
        encoding="utf-8",
    )
    with pytest.raises(PlanLogRestoreError, match="header is malformed"):
        plan_log.read_direct_answer_turns()

    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "f2ddf2369f994905afa0b85d8cca79b1",
            session_id,
        ),
        encoding="utf-8",
    )
    with path.open("ab") as handle:
        handle.write(b"\xff")
    with pytest.raises(PlanLogRestoreError, match="not UTF-8"):
        plan_log.read_direct_answer_turns()


def test_plan_reader_counts_each_file_toward_total_byte_limit(
    tmp_path,
    monkeypatch,
):
    session_id = "28b222e0cc6543aa8d7bbdc423de99a7"
    config = AgentConfig(persist_dir=str(tmp_path / "persist"))
    plan_log = PlanLog(
        config,
        session_id=session_id,
        app_root_resolver=lambda: tmp_path,
    )
    first = plan_log.new_log_file()
    first.write_text(
        first.read_text(encoding="utf-8")
        + plan_log.render_block(
            turn_id=1,
            timestamp="2026-08-28T01:00:00+00:00",
            user_input="first",
            answer="answer one",
            new_messages=[],
            tool_calls=[],
        ),
        encoding="utf-8",
    )
    second = first.with_name(
        f"plan-{session_id}-20260828T010001Z.md"
    )
    second.write_text(
        first.read_text(encoding="utf-8").split("## Turn", 1)[0]
        + plan_log.render_block(
            turn_id=2,
            timestamp="2026-08-28T01:00:01+00:00",
            user_input="second",
            answer="answer two",
            new_messages=[],
            tool_calls=[],
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "agent.turns.plan_log.MAX_PLAN_RESTORE_TOTAL_BYTES",
        first.stat().st_size + second.stat().st_size - 1,
    )

    with pytest.raises(PlanLogRestoreError, match="total limit"):
        plan_log.read_direct_answer_turns()


def test_direct_answer_reader_rejects_too_many_matching_files(
    tmp_path,
    monkeypatch,
):
    session_id = "28b222e0cc6543aa8d7bbdc423de99a7"
    config = AgentConfig(persist_dir=str(tmp_path / "persist"))
    plan_log = PlanLog(
        config,
        session_id=session_id,
        app_root_resolver=lambda: tmp_path,
    )
    path = plan_log.new_log_file()
    monkeypatch.setattr(
        "agent.turns.plan_log.Path.glob",
        lambda _self, _pattern: iter([path] * (MAX_PLAN_RESTORE_FILES + 1)),
    )

    with pytest.raises(PlanLogRestoreError, match="file-count limit"):
        plan_log.read_direct_answer_turns()
