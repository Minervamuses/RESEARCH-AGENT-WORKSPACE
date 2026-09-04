"""Canonical ChatSession durability and recovery boundaries.

These tests replace the retired recent-turn eviction contract. They use a real
temporary conversation repository and scripted graphs, so no provider, Ollama,
Chroma, or user store is involved.
"""

import asyncio
import uuid

import pytest

from conftest import FakeHistoryStore, make_astream_graph

from agent.config import AgentConfig
from agent.conversations import (
    ConversationRepository,
    ConversationUnavailableError,
)
from agent.session import ChatSession


PROJECT_ID = "research-agent"


def _id() -> str:
    return uuid.uuid4().hex


def _timestamp(second: int) -> str:
    return f"2026-09-04T00:00:{second:02d}Z"


def _session(
    monkeypatch,
    tmp_path,
    *,
    repository: ConversationRepository,
    graph,
    session_id: str,
    history_store: FakeHistoryStore | None = None,
) -> ChatSession:
    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _config, extra_tools=None, history_store=None, **kwargs: graph,
    )
    config = AgentConfig(persist_dir=str(tmp_path))
    config.agent_recent_turns_window = 3
    return ChatSession(
        config,
        history_store=history_store or FakeHistoryStore(),
        conversation_repository=repository,
        project_id=PROJECT_ID,
        session_id=session_id,
    )


class FailingGraph:
    """Provider boundary that records invocation and then fails."""

    def __init__(self) -> None:
        self.states: list[dict] = []

    async def astream(self, state, config=None, stream_mode="updates"):
        self.states.append(state)
        if False:
            yield {}
        raise RuntimeError("provider unavailable")


def test_prompt_is_durable_before_the_graph_starts(monkeypatch, tmp_path):
    repository = ConversationRepository(tmp_path)
    session_id = _id()
    turn_id = _id()
    observed: dict[str, object] = {}

    def inspect_pending(_state):
        turn = repository.load(session_id).document.turns[-1]
        observed.update({
            "turn_id": turn.turn_id,
            "turn_number": turn.turn_number,
            "state": turn.state,
            "display_input": turn.display_input,
            "semantic_input": turn.semantic_input,
        })

    graph = make_astream_graph(on_state=inspect_pending)
    session = _session(
        monkeypatch,
        tmp_path,
        repository=repository,
        graph=graph,
        session_id=session_id,
    )

    outcome = asyncio.run(session.turn_outcome(
        "semantic prompt",
        display_input="/skill semantic prompt",
        turn_id=turn_id,
    ))

    assert observed == {
        "turn_id": turn_id,
        "turn_number": 1,
        "state": "pending",
        "display_input": "/skill semantic prompt",
        "semantic_input": "semantic prompt",
    }
    assert outcome.state == "completed"
    assert repository.load(session_id).document.turns[-1].state == "completed"


def test_pending_write_failure_prevents_graph_or_provider_work(
    monkeypatch,
    tmp_path,
):
    repository = ConversationRepository(tmp_path)
    session_id = _id()
    graph = make_astream_graph()
    session = _session(
        monkeypatch,
        tmp_path,
        repository=repository,
        graph=graph,
        session_id=session_id,
    )

    def reject_pending(**_kwargs):
        raise ConversationUnavailableError("injected pending write failure")

    monkeypatch.setattr(repository, "create", reject_pending)

    with pytest.raises(ConversationUnavailableError, match="pending write"):
        asyncio.run(session.turn_outcome(
            "must not execute",
            display_input="must not execute",
            turn_id=_id(),
        ))

    assert graph.states == []
    assert repository.load_optional(session_id) is None


def test_provider_failure_commits_failed_terminal_state(monkeypatch, tmp_path):
    repository = ConversationRepository(tmp_path)
    session_id = _id()
    turn_id = _id()
    graph = FailingGraph()
    session = _session(
        monkeypatch,
        tmp_path,
        repository=repository,
        graph=graph,
        session_id=session_id,
    )

    with pytest.raises(RuntimeError, match="provider unavailable"):
        asyncio.run(session.turn_outcome(
            "provider will fail",
            display_input="provider will fail",
            turn_id=turn_id,
        ))

    assert len(graph.states) == 1
    turn = repository.load(session_id).document.turns[-1]
    assert turn.turn_id == turn_id
    assert turn.state == "failed"
    assert turn.assistant_output is None
    assert turn.failure is not None
    assert turn.failure.code == "execution_failed"


def test_reload_interrupts_leftover_pending_without_replay(monkeypatch, tmp_path):
    repository = ConversationRepository(tmp_path)
    session_id = _id()
    turn_id = _id()
    repository.create(
        conversation_id=session_id,
        project_id=PROJECT_ID,
        turn_id=turn_id,
        kind="conversational",
        display_input="unfinished prompt",
        semantic_input="unfinished prompt",
        context_eligible=True,
        thinking_mode="normal",
        submitted_at=_timestamp(1),
    )
    graph = make_astream_graph()
    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _config, extra_tools=None, history_store=None, **kwargs: graph,
    )

    restored = asyncio.run(ChatSession.restore(
        AgentConfig(persist_dir=str(tmp_path)),
        session_id=session_id,
        history_store=FakeHistoryStore(),
        conversation_repository=repository,
        project_id=PROJECT_ID,
        load_mcp=False,
    ))

    assert restored.session_id == session_id
    assert graph.states == []
    turn = repository.load(session_id).document.turns[-1]
    assert turn.turn_id == turn_id
    assert turn.state == "interrupted"
    assert turn.assistant_output is None
    assert turn.failure is not None
    assert turn.failure.code == "interrupted"


def test_completed_duplicate_returns_durable_answer_without_graph(
    monkeypatch,
    tmp_path,
):
    repository = ConversationRepository(tmp_path)
    session_id = _id()
    turn_id = _id()
    first_graph = make_astream_graph(answer="durable answer")
    first_session = _session(
        monkeypatch,
        tmp_path,
        repository=repository,
        graph=first_graph,
        session_id=session_id,
    )
    first = asyncio.run(first_session.turn_outcome(
        "same logical request",
        display_input="same logical request",
        turn_id=turn_id,
    ))
    before = repository.path_for(session_id).read_bytes()

    duplicate_graph = FailingGraph()
    duplicate_session = _session(
        monkeypatch,
        tmp_path,
        repository=repository,
        graph=duplicate_graph,
        session_id=session_id,
    )
    duplicate = asyncio.run(duplicate_session.turn_outcome(
        "same logical request",
        display_input="same logical request",
        turn_id=turn_id,
    ))

    assert first.text == duplicate.text == "durable answer"
    assert duplicate.turn_id == turn_id
    assert duplicate.state == "completed"
    assert duplicate.accepted is True
    assert duplicate.persisted is True
    assert duplicate_graph.states == []
    assert repository.path_for(session_id).read_bytes() == before


def test_latest_ten_pairs_and_current_prompt_appear_exactly_once(
    monkeypatch,
    tmp_path,
):
    repository = ConversationRepository(tmp_path)
    session_id = _id()
    first_id = _id()
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
        turn_id = _id()
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

    history_store = FakeHistoryStore()
    graph = make_astream_graph()
    session = _session(
        monkeypatch,
        tmp_path,
        repository=repository,
        graph=graph,
        session_id=session_id,
        history_store=history_store,
    )
    asyncio.run(session.turn_outcome(
        "q13",
        display_input="q13",
        turn_id=_id(),
    ))

    contents = [message.content for message in graph.states[0]["messages"]]
    assert "q1" not in contents
    assert "a1" not in contents
    assert "q2" not in contents
    assert "a2" not in contents
    for number in range(3, 13):
        assert contents.count(f"q{number}") == 1
        assert contents.count(f"a{number}") == 1
    assert contents.count("q13") == 1

    persisted = repository.load(session_id).document
    assert len(persisted.turns) == 13
    assert history_store.adds == []
    asyncio.run(session.flush_recent_turns())
    assert history_store.adds == []
    assert len(repository.load(session_id).document.turns) == 13
