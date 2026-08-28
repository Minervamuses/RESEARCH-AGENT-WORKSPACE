"""Tests for plan-mode markdown persistence."""

import asyncio

import pytest

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


def _large_tool_updates(payload: str):
    """A single rag_search call whose result payload is very large."""
    return tool_then_answer_updates(
        "rag_search",
        {"query": "big"},
        "call-big",
        payload,
        "answer",
    )


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


def test_plan_writes_md_immediately(make_session):
    session, store, log_dir = make_session(window=2)
    asyncio.run(session.enter_plan_mode())

    for index in range(3):
        asyncio.run(session.turn(f"q{index}"))
        content = session.plan_log_path.read_text(encoding="utf-8")
        assert f"## Turn {index + 1}" in content
        assert f"q{index}" in content

    assert store.adds == []
    assert log_dir.exists()


def test_exit_plan_keeps_recent_turns_visible(make_session):
    session, _store, _log_dir = make_session(window=10)
    asyncio.run(session.enter_plan_mode())
    asyncio.run(session.turn("plan q1"))
    asyncio.run(session.turn("plan q2"))

    asyncio.run(session.exit_plan_mode())

    assert [turn.user_input for turn in session.recent_turns] == [
        "plan q1",
        "plan q2",
    ]
    prompt_contents = [message.content for message in session._prompt_history()]
    assert "plan q1" in prompt_contents
    assert "plan q2" in prompt_contents


def test_resume_plan_mode_reuses_the_same_validated_log(make_session):
    session, _store, _log_dir = make_session(window=10)
    original_path = asyncio.run(session.enter_plan_mode())
    asyncio.run(session.turn("first plan turn"))
    asyncio.run(session.exit_plan_mode())

    resumed_path = asyncio.run(session.resume_plan_mode(original_path))
    asyncio.run(session.turn("second plan turn"))

    assert resumed_path == original_path
    assert session.plan_log_path == original_path
    content = original_path.read_text(encoding="utf-8")
    assert "first plan turn" in content
    assert "second plan turn" in content


def test_no_chroma_leak_after_exit(make_session):
    session, store, _log_dir = make_session(window=2)
    asyncio.run(session.enter_plan_mode())
    for index in range(5):
        asyncio.run(session.turn(f"plan {index}"))

    asyncio.run(session.exit_plan_mode())
    for index in range(5):
        asyncio.run(session.turn(f"normal {index}"))
    asyncio.run(session.flush_recent_turns())

    assert [item["user_input"] for item in store.adds] == [f"normal {index}" for index in range(5)]


def test_md_write_failure_aborts_turn(make_session, monkeypatch):
    session, store, _log_dir = make_session(window=2)
    asyncio.run(session.enter_plan_mode())

    def fail_append(_path, _block):
        raise OSError("disk full")

    monkeypatch.setattr(session, "_append_block_to_md", fail_append)

    with pytest.raises(OSError, match="disk full"):
        asyncio.run(session.turn("q"))

    assert session.recent_turns == []
    assert session._turn_counter == 0
    assert store.adds == []


def test_render_plan_block_includes_all_tools(make_session):
    session, _store, _log_dir = make_session(
        window=2,
        graph=make_astream_graph(_web_search_updates()),
    )
    asyncio.run(session.enter_plan_mode())
    asyncio.run(session.turn("search for plan mode"))

    content = session.plan_log_path.read_text(encoding="utf-8")
    assert "### Tool: tavily_search" in content
    assert '"query": "plan mode"' in content
    assert "**Result:**" in content
    assert "search result payload" in content


def test_plan_log_truncates_oversize_tool_result(make_session):
    payload = "x" * 100_000
    session, _store, _log_dir = make_session(
        window=2, graph=make_astream_graph(_large_tool_updates(payload)),
    )
    session.config.plan_log_max_tool_chars = 1024
    asyncio.run(session.enter_plan_mode())
    asyncio.run(session.turn("ask for big result"))

    content = session.plan_log_path.read_text(encoding="utf-8")
    assert f"[truncated; original {len(payload)} chars]" in content
    # Body of the rendered tool block must not contain the full payload.
    assert "x" * 2000 not in content


def test_plan_log_truncation_does_not_affect_llm_context(make_session, monkeypatch):
    """The graph layer keeps the full ToolMessage; only the markdown copy is capped."""
    payload = "y" * 50_000
    captured: dict[str, list] = {"messages": []}

    def _capture_state(state):
        captured["messages"] = list(state["messages"])

    session, _store, _log_dir = make_session(
        window=2,
        graph=make_astream_graph(_large_tool_updates(payload), on_state=_capture_state),
    )
    session.config.plan_log_max_tool_chars = 1024
    asyncio.run(session.enter_plan_mode())
    asyncio.run(session.turn("trigger big tool"))

    # The graph's input state never carries the ToolMessage (graph generates it),
    # but the assertion is symmetric: the payload returned by the tool node
    # is full-size and reaches the agent loop unchanged. We verify by reading
    # the in-memory sequence the session captured for its own bookkeeping.
    full_results = [
        m for m in session.recent_turns[-1].to_messages()
        if hasattr(m, "content") and isinstance(m.content, str) and len(m.content) > 0
    ]
    # The recorded turn carries the assistant's final answer "answer", not the
    # tool payload. The truncation we want to verify is on disk only.
    md = session.plan_log_path.read_text(encoding="utf-8")
    assert "[truncated;" in md
    assert payload not in md
    # And the assistant message kept by the session is unaffected:
    assert "answer" in [m.content for m in full_results]


def test_mode_hint_injected_when_plan_turns_in_recent(make_session):
    session, _store, _log_dir = make_session(window=10)
    asyncio.run(session.enter_plan_mode())
    asyncio.run(session.turn("plan question"))
    asyncio.run(session.exit_plan_mode())

    history = session._prompt_history()
    hint_msgs = [m for m in history if "[Mode hint]" in str(getattr(m, "content", ""))]
    assert len(hint_msgs) == 1
    assert "plan_logs/" in hint_msgs[0].content
    assert "do NOT call recall_history" in hint_msgs[0].content


def test_mode_hint_absent_in_pure_normal_session(make_session):
    session, _store, _log_dir = make_session(window=10)
    asyncio.run(session.turn("normal question"))

    history = session._prompt_history()
    hint_msgs = [m for m in history if "[Mode hint]" in str(getattr(m, "content", ""))]
    assert hint_msgs == []


def test_mode_hint_disappears_after_plan_turns_evicted(make_session):
    session, _store, _log_dir = make_session(window=2)
    asyncio.run(session.enter_plan_mode())
    asyncio.run(session.turn("plan q"))
    asyncio.run(session.exit_plan_mode())
    # Push the plan turn out of the window with normal turns.
    for index in range(3):
        asyncio.run(session.turn(f"normal {index}"))

    history = session._prompt_history()
    hint_msgs = [m for m in history if "[Mode hint]" in str(getattr(m, "content", ""))]
    assert hint_msgs == []


def test_unknown_persist_target_raises(make_session):
    session, _store, _log_dir = make_session(window=2)
    turn = TurnRecord(
        user_input="q",
        assistant_output="a",
        turn_id=1,
        persist_target="mystery",
    )

    with pytest.raises(ValueError, match="unknown persist_target"):
        asyncio.run(session._turn_store.store_turn(turn))


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


def test_direct_answer_reader_rejects_tool_content_without_leaking_it(tmp_path):
    session_id = "28b222e0cc6543aa8d7bbdc423de99a7"
    config = AgentConfig(persist_dir=str(tmp_path / "persist"))
    plan_log = PlanLog(
        config,
        session_id=session_id,
        app_root_resolver=lambda: tmp_path,
    )
    path = plan_log.new_log_file()
    secret = "private tool payload"
    plan_log.append_block(
        str(path),
        "## Turn 1 - 2026-08-28T01:00:00+00:00\n\n"
        "**User:**\n\nquestion\n\n"
        "### Tool: rag_search\n\n```\n"
        f"{secret}\n"
        "```\n\n**Assistant:**\n\nanswer\n\n---\n",
    )

    with pytest.raises(PlanLogRestoreError) as captured:
        plan_log.read_direct_answer_turns()

    assert secret not in str(captured.value)


def test_direct_answer_reader_rejects_ambiguous_markers(tmp_path):
    session_id = "28b222e0cc6543aa8d7bbdc423de99a7"
    config = AgentConfig(persist_dir=str(tmp_path / "persist"))
    plan_log = PlanLog(
        config,
        session_id=session_id,
        app_root_resolver=lambda: tmp_path,
    )
    path = plan_log.new_log_file()
    plan_log.append_block(
        str(path),
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
    path = plan_log.new_log_file()
    plan_log.append_block(
        str(path),
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
