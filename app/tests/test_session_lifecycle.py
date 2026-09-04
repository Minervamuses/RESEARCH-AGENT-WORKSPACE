"""Red contracts for the canonical JSON-backed turn lifecycle.

These tests deliberately name the Phase 03 session boundary before the
implementation exists.  They use a real temporary canonical repository and a
scripted graph, so no provider, Ollama, or Chroma service is involved.
"""

import asyncio
import uuid

import pytest

from conftest import FakeHistoryStore, make_astream_graph

from agent.config import AgentConfig
from agent.conversations.models import ConversationUnavailableError
from agent.conversations.repository import ConversationRepository
from agent.session import ChatSession


PROJECT_ID = "research-agent"


def _turn_id() -> str:
    return uuid.uuid4().hex


def _timestamp(second: int) -> str:
    return f"2026-09-04T00:00:{second:02d}Z"


class RecordingRepository:
    """Delegate to the real repository while exposing lifecycle ordering."""

    def __init__(self, delegate: ConversationRepository, *, fail_create=False,
                 fail_complete=False):
        self.delegate = delegate
        self.calls: list[str] = []
        self.fail_create = fail_create
        self.fail_complete = fail_complete

    def create(self, **kwargs):
        self.calls.append("pending")
        if self.fail_create:
            raise ConversationUnavailableError("pending write unavailable")
        return self.delegate.create(**kwargs)

    def append_pending(self, snapshot, **kwargs):
        self.calls.append("pending")
        if self.fail_create:
            raise ConversationUnavailableError("pending write unavailable")
        return self.delegate.append_pending(snapshot, **kwargs)

    def complete_turn(self, snapshot, **kwargs):
        self.calls.append("complete")
        if self.fail_complete:
            raise ConversationUnavailableError("complete write unavailable")
        return self.delegate.complete_turn(snapshot, **kwargs)

    def __getattr__(self, name):
        return getattr(self.delegate, name)


@pytest.fixture
def make_session(monkeypatch, tmp_path):
    """Construct a session with only local scripted dependencies."""

    def _make(
        repository,
        graph,
        *,
        session_id: str | None = None,
    ) -> ChatSession:
        monkeypatch.setattr(
            "agent.session.build_graph",
            lambda _config, extra_tools=None, history_store=None, **kwargs: graph,
        )
        return ChatSession(
            AgentConfig(persist_dir=str(tmp_path)),
            history_store=FakeHistoryStore(),
            conversation_repository=repository,
            project_id=PROJECT_ID,
            session_id=session_id or _turn_id(),
        )

    return _make


def test_pending_json_is_published_before_the_graph_receives_a_turn(
    make_session,
    tmp_path,
):
    delegate = ConversationRepository(tmp_path)
    repository = RecordingRepository(delegate)
    observed: dict[str, object] = {}
    session_id = _turn_id()
    turn_id = _turn_id()

    def inspect_pending(_state):
        document = delegate.load(session_id).document
        turn = document.turns[-1]
        observed.update({
            "turn_id": turn.turn_id,
            "turn_number": turn.turn_number,
            "state": turn.state,
            "display": turn.display_input,
            "semantic": turn.semantic_input,
        })

    graph = make_astream_graph(on_state=inspect_pending)
    session = make_session(repository, graph, session_id=session_id)

    outcome = asyncio.run(session.turn_outcome(
        "What does the skill mean?",
        display_input="/explain What does the skill mean?",
        turn_id=turn_id,
    ))

    assert outcome.text == "ok"
    assert observed == {
        "turn_id": turn_id,
        "turn_number": 1,
        "state": "pending",
        "display": "/explain What does the skill mean?",
        "semantic": "What does the skill mean?",
    }
    assert repository.calls == ["pending", "complete"]


def test_pending_persistence_failure_never_starts_the_graph(make_session, tmp_path):
    repository = RecordingRepository(
        ConversationRepository(tmp_path),
        fail_create=True,
    )
    graph = make_astream_graph()
    session = make_session(repository, graph)

    with pytest.raises(ConversationUnavailableError, match="pending write"):
        asyncio.run(session.turn_outcome(
            "must not execute",
            display_input="must not execute",
            turn_id=_turn_id(),
        ))

    assert graph.states == []
    assert repository.calls == ["pending"]


def test_final_validator_precedes_completed_commit_and_commit_failure_is_not_success(
    make_session,
    tmp_path,
):
    events: list[str] = []
    delegate = ConversationRepository(tmp_path)
    repository = RecordingRepository(delegate)
    graph = make_astream_graph(on_state=lambda _state: events.append("graph"))
    session = make_session(repository, graph)
    original_complete = repository.complete_turn

    def complete_with_trace(snapshot, **kwargs):
        events.append("complete")
        return original_complete(snapshot, **kwargs)

    repository.complete_turn = complete_with_trace
    session._set_final_text_validator(
        lambda _text, _errors: events.append("validator"),
    )

    outcome = asyncio.run(session.turn_outcome(
        "ordered",
        display_input="ordered",
        turn_id=_turn_id(),
    ))

    assert outcome.text == "ok"
    assert events == ["graph", "validator", "complete"]

    failing_repository = RecordingRepository(
        ConversationRepository(tmp_path / "complete-failure"),
        fail_complete=True,
    )
    failing_graph = make_astream_graph()
    failing_session = make_session(failing_repository, failing_graph)

    with pytest.raises(ConversationUnavailableError, match="complete write"):
        asyncio.run(failing_session.turn_outcome(
            "do not return success",
            display_input="do not return success",
            turn_id=_turn_id(),
        ))

    assert len(failing_graph.states) == 1
    assert failing_repository.calls == ["pending", "complete"]


def test_completed_logical_retry_returns_the_durable_answer_without_a_graph_call(
    make_session,
    tmp_path,
):
    repository = RecordingRepository(ConversationRepository(tmp_path))
    graph = make_astream_graph(answer="durable answer")
    session = make_session(repository, graph)
    turn_id = _turn_id()

    first = asyncio.run(session.turn_outcome(
        "retry exactly once",
        display_input="retry exactly once",
        turn_id=turn_id,
    ))
    second = asyncio.run(session.turn_outcome(
        "retry exactly once",
        display_input="retry exactly once",
        turn_id=turn_id,
    ))

    assert first.text == second.text == "durable answer"
    assert len(graph.states) == 1
    assert repository.calls == ["pending", "complete", "pending"]


def test_graph_context_is_the_latest_ten_completed_pairs_plus_current_once(
    make_session,
    tmp_path,
):
    repository = ConversationRepository(tmp_path)
    session_id = _turn_id()
    first_id = _turn_id()
    snapshot = repository.create(
        conversation_id=session_id,
        project_id=PROJECT_ID,
        turn_id=first_id,
        kind="conversational",
        display_input="q1",
        semantic_input="q1",
        context_eligible=True,
        thinking_mode="normal",
        submitted_at=_timestamp(1),
    )
    snapshot = repository.complete_turn(
        snapshot,
        turn_id=first_id,
        assistant_output="a1",
        finished_at=_timestamp(1),
    )
    for number in range(2, 13):
        turn_id = _turn_id()
        snapshot = repository.append_pending(
            snapshot,
            turn_id=turn_id,
            kind="conversational",
            display_input=f"q{number}",
            semantic_input=f"q{number}",
            context_eligible=True,
            thinking_mode="normal",
            submitted_at=_timestamp(number),
        )
        snapshot = repository.complete_turn(
            snapshot,
            turn_id=turn_id,
            assistant_output=f"a{number}",
            finished_at=_timestamp(number),
        )

    graph = make_astream_graph()
    session = make_session(repository, graph, session_id=session_id)
    asyncio.run(session.turn_outcome(
        "q13",
        display_input="q13",
        turn_id=_turn_id(),
    ))

    contents = [message.content for message in graph.states[0]["messages"]]
    assert "q1" not in contents
    assert "a1" not in contents
    for number in range(3, 13):
        assert f"q{number}" in contents
        assert f"a{number}" in contents
    assert contents.count("q13") == 1


def test_restore_marks_leftover_pending_interrupted_without_running_a_graph(
    monkeypatch,
    tmp_path,
):
    repository = ConversationRepository(tmp_path)
    session_id = _turn_id()
    pending_id = _turn_id()
    repository.create(
        conversation_id=session_id,
        project_id=PROJECT_ID,
        turn_id=pending_id,
        kind="conversational",
        display_input="interrupted input",
        semantic_input="interrupted input",
        context_eligible=True,
        thinking_mode="normal",
        submitted_at=_timestamp(1),
    )
    graph = make_astream_graph()
    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _config, extra_tools=None, history_store=None, **kwargs: graph,
    )

    asyncio.run(ChatSession.restore(
        AgentConfig(persist_dir=str(tmp_path)),
        session_id=session_id,
        history_store=FakeHistoryStore(),
        conversation_repository=repository,
        project_id=PROJECT_ID,
        load_mcp=False,
    ))

    turn = repository.load(session_id).document.turns[-1]
    assert turn.state == "interrupted"
    assert turn.failure is not None
    assert turn.failure.code == "interrupted"
    assert graph.states == []
