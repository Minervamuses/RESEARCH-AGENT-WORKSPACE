"""Canonical ChatSession durability and recovery boundaries.

These tests use a real temporary conversation repository and scripted graphs,
so no provider, Ollama, Chroma, or user store is involved.
"""

import asyncio
import threading
import uuid

import pytest

from conftest import make_astream_graph

from agent.config import AgentConfig
from agent.conversations import (
    ConversationConflictError,
    ConversationRepository,
    ConversationUnavailableError,
    FailureInfo,
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
) -> ChatSession:
    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _config, extra_tools=None, **kwargs: graph,
    )
    config = AgentConfig(persist_dir=str(tmp_path))
    return ChatSession(
        config,
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


@pytest.mark.parametrize("write_method", ["create", "append_pending"])
def test_pending_write_failure_prevents_graph_or_provider_work(
    monkeypatch,
    tmp_path,
    write_method,
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

    if write_method == "append_pending":
        asyncio.run(session.turn_outcome("previous prompt", turn_id=_id()))
        graph.states.clear()
    before = repository.load_optional(session_id)
    accepted = []
    session._set_prompt_persisted_callback(lambda: accepted.append("accepted"))

    def reject_pending(*_args, **_kwargs):
        raise ConversationUnavailableError("injected pending write failure")

    monkeypatch.setattr(repository, write_method, reject_pending)

    with pytest.raises(ConversationUnavailableError, match="pending write"):
        asyncio.run(session.turn_outcome(
            "must not execute",
            display_input="must not execute",
            turn_id=_id(),
        ))

    assert graph.states == []
    assert accepted == []
    assert repository.load_optional(session_id) == before


def test_final_write_failure_never_returns_success_or_completed_partial(
    monkeypatch,
    tmp_path,
):
    repository = ConversationRepository(tmp_path)
    session_id = _id()
    turn_id = _id()
    graph = make_astream_graph(answer="complete answer that must not leak")
    session = _session(
        monkeypatch,
        tmp_path,
        repository=repository,
        graph=graph,
        session_id=session_id,
    )

    def reject_final(*_args, **_kwargs):
        raise ConversationUnavailableError("injected final write failure")

    monkeypatch.setattr(repository, "complete_turn", reject_final)

    with pytest.raises(ConversationUnavailableError, match="final write"):
        asyncio.run(session.turn_outcome(
            "persist before success",
            display_input="persist before success",
            turn_id=turn_id,
        ))

    turn = repository.load(session_id).document.turns[-1]
    assert turn.turn_id == turn_id
    assert turn.state == "failed"
    assert turn.assistant_output is None
    assert turn.failure is not None
    assert turn.failure.code == "persistence_failed"


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


def test_failed_turn_records_one_incident_in_log_and_transcript(
    monkeypatch, tmp_path, caplog,
):
    import logging
    import re

    from agent.diagnostics import attach_incident

    repository = ConversationRepository(tmp_path)
    session_id = _id()
    session = _session(
        monkeypatch,
        tmp_path,
        repository=repository,
        graph=FailingGraph(),
        session_id=session_id,
    )

    with caplog.at_level(logging.ERROR, logger="agent.session"):
        with pytest.raises(RuntimeError) as raised:
            asyncio.run(session.turn_outcome("x", display_input="x", turn_id=_id()))

    incident, is_new = attach_incident(raised.value)
    assert is_new is False  # outer layers reuse the session's reference
    message = repository.load(session_id).document.turns[-1].failure.message
    assert message.startswith("The turn could not be completed. ")
    assert re.search(rf"\(incident {incident}; RuntimeError(; details in .+)?\)$", message)
    assert "provider unavailable" not in message
    records = [r for r in caplog.records if incident in r.getMessage()]
    assert len(records) == 1 and records[0].exc_info is not None


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
        lambda _config, extra_tools=None, **kwargs: graph,
    )

    restored = asyncio.run(ChatSession.restore(
        AgentConfig(persist_dir=str(tmp_path)),
        session_id=session_id,
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
    accepted = []
    duplicate_session._set_prompt_persisted_callback(
        lambda: accepted.append(repository.load(session_id).document.turns[-1].state)
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
    assert accepted == ["completed"]
    assert repository.path_for(session_id).read_bytes() == before


@pytest.mark.parametrize("state", ["failed", "interrupted"])
def test_existing_turn_notifies_only_after_successful_explicit_retry(
    monkeypatch, tmp_path, state,
):
    repository = ConversationRepository(tmp_path)
    session_id, turn_id = _id(), _id()
    snapshot = repository.create(
        conversation_id=session_id, project_id=PROJECT_ID, turn_id=turn_id,
        kind="conversational", display_input="retry this prompt",
        semantic_input="retry this prompt", context_eligible=True,
        thinking_mode="normal", submitted_at=_timestamp(1),
    )
    repository.fail_turn(
        snapshot, turn_id=turn_id, state=state,
        failure=FailureInfo(
            code="execution_failed" if state == "failed" else "cancelled",
            message="Try again.", retryable=True,
        ),
        finished_at=_timestamp(2),
    )
    graph = make_astream_graph(answer="retried answer")
    session = _session(
        monkeypatch, tmp_path, repository=repository, graph=graph, session_id=session_id,
    )
    accepted = []
    session._set_prompt_persisted_callback(
        lambda: accepted.append((
            repository.load(session_id).document.turns[-1].state, len(graph.states),
        ))
    )
    with pytest.raises(ConversationConflictError, match="explicit retry"):
        asyncio.run(session.turn_outcome("retry this prompt", turn_id=turn_id))
    assert accepted == []
    assert graph.states == []

    original_retry = repository.retry_turn

    def reject_retry(*_args, **_kwargs):
        raise ConversationUnavailableError("injected retry write failure")

    monkeypatch.setattr(repository, "retry_turn", reject_retry)
    with pytest.raises(ConversationUnavailableError, match="retry write"):
        asyncio.run(session.turn_outcome("retry this prompt", turn_id=turn_id, retry=True))
    assert accepted == []
    assert graph.states == []
    assert repository.load(session_id).document.turns[-1].state == state

    monkeypatch.setattr(repository, "retry_turn", original_retry)
    outcome = asyncio.run(session.turn_outcome(
        "retry this prompt", turn_id=turn_id, retry=True,
    ))
    assert outcome.state == "completed"
    assert outcome.text == "retried answer"
    assert accepted == [("pending", 0)]
    assert len(graph.states) == 1


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

    graph = make_astream_graph()
    session = _session(
        monkeypatch,
        tmp_path,
        repository=repository,
        graph=graph,
        session_id=session_id,
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
    assert [turn.user_input for turn in session.recent_turns] == [
        f"q{number}" for number in range(4, 14)
    ]
    assert session.status_snapshot()["recent_turn_count"] == 10


@pytest.mark.parametrize("display_only", [False, True])
def test_cancelled_pending_save_retains_input_and_finishes_interrupted(
    monkeypatch, tmp_path, display_only,
):
    from agent.ingest import LocalWorkScope

    repository = ConversationRepository(tmp_path)
    graph = make_astream_graph(answer="next answer")
    session = _session(
        monkeypatch, tmp_path, repository=repository, graph=graph, session_id=_id(),
    )
    turn_id = _id()
    entered = threading.Event()
    release = threading.Event()
    action_calls = []
    accepted = []

    def record_acceptance():
        saved = repository.load(session.session_id).document.turns[-1]
        accepted.append((saved.turn_id, saved.state))

    session._set_prompt_persisted_callback(record_acceptance)
    original_create = repository.create

    def held_create(**kwargs):
        snapshot = original_create(**kwargs)
        entered.set()
        assert release.wait(timeout=3)
        return snapshot

    monkeypatch.setattr(repository, "create", held_create)

    async def action():
        action_calls.append("ran")
        return "local result"

    async def run():
        scope = LocalWorkScope()
        with scope.bind():
            work = (
                session.run_display_only_turn(
                    "keep this prompt", action, str, turn_id=turn_id,
                )
                if display_only
                else session.turn_outcome("keep this prompt", turn_id=turn_id)
            )
            task = asyncio.create_task(work)
            try:
                async with asyncio.timeout(3):
                    while not entered.is_set():
                        await asyncio.sleep(0.001)
                task.cancel()
                await asyncio.sleep(0)
                task.cancel()
                await asyncio.sleep(0)
                assert not task.done(), "accepted save must settle before Stop returns"
                assert accepted == []
                release.set()
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(task, timeout=3)
                with pytest.raises(asyncio.CancelledError):
                    scope.check_cancelled()
            finally:
                release.set()
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)

        saved = repository.load(session.session_id).document.turns[-1]
        assert saved.turn_id == turn_id
        assert saved.display_input == "keep this prompt"
        assert saved.state == "interrupted"
        assert saved.failure.code == "cancelled"
        assert saved.assistant_output is None
        assert accepted == [(turn_id, "pending")]
        assert action_calls == []
        assert graph.states == []
        next_turn_id = _id()
        next_outcome = await session.turn_outcome("continue", turn_id=next_turn_id)
        assert next_outcome.state == "completed"
        assert next_outcome.text == "next answer"
        assert accepted == [(turn_id, "pending"), (next_turn_id, "pending")]

    asyncio.run(run())


@pytest.mark.parametrize("display_only", [False, True])
def test_cancelled_completed_save_returns_the_actual_completed_result(
    monkeypatch, tmp_path, display_only,
):
    repository = ConversationRepository(tmp_path)
    graph = make_astream_graph(answer="saved answer")
    session = _session(
        monkeypatch, tmp_path, repository=repository, graph=graph, session_id=_id(),
    )
    turn_id = _id()
    entered = threading.Event()
    release = threading.Event()
    original_complete = repository.complete_turn
    fail_calls = []
    original_fail = repository.fail_turn

    def held_complete(*args, **kwargs):
        snapshot = original_complete(*args, **kwargs)
        entered.set()
        assert release.wait(timeout=3)
        return snapshot

    def observed_fail(*args, **kwargs):
        fail_calls.append(kwargs["state"])
        return original_fail(*args, **kwargs)

    monkeypatch.setattr(repository, "complete_turn", held_complete)
    monkeypatch.setattr(repository, "fail_turn", observed_fail)

    async def action():
        return "saved answer"

    async def run():
        work = (
            session.run_display_only_turn(
                "finish this prompt", action, str, turn_id=turn_id,
            )
            if display_only
            else session.turn_outcome("finish this prompt", turn_id=turn_id)
        )
        task = asyncio.create_task(work)
        try:
            async with asyncio.timeout(3):
                while not entered.is_set():
                    await asyncio.sleep(0.001)
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done(), "terminal save must settle before Stop returns"
            release.set()
            result = await asyncio.wait_for(task, timeout=3)
        finally:
            release.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        outcome = result[1] if display_only else result
        assert outcome.state == "completed"
        assert outcome.text == "saved answer"
        assert outcome.accepted is True
        assert outcome.persisted is True

    asyncio.run(run())
    saved = repository.load(session.session_id).document.turns[-1]
    assert saved.state == "completed"
    assert saved.assistant_output == "saved answer"
    assert session._conversation_snapshot.document.turns[-1] == saved
    assert fail_calls == []


def test_cancellation_waits_for_failure_save_without_starting_another_write(
    monkeypatch, tmp_path,
):
    repository = ConversationRepository(tmp_path)
    session = _session(
        monkeypatch, tmp_path, repository=repository, graph=FailingGraph(),
        session_id=_id(),
    )
    entered = threading.Event()
    release = threading.Event()
    original_fail = repository.fail_turn
    fail_calls = []

    def held_fail(*args, **kwargs):
        fail_calls.append(kwargs["state"])
        entered.set()
        assert release.wait(timeout=3)
        return original_fail(*args, **kwargs)

    monkeypatch.setattr(repository, "fail_turn", held_fail)

    async def run():
        task = asyncio.create_task(session.turn_outcome("failed work", turn_id=_id()))
        try:
            async with asyncio.timeout(3):
                while not entered.is_set():
                    await asyncio.sleep(0.001)
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
            release.set()
            with pytest.raises(RuntimeError, match="provider unavailable"):
                await asyncio.wait_for(task, timeout=3)
        finally:
            release.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(run())
    assert fail_calls == ["failed"]
    assert repository.load(session.session_id).document.turns[-1].state == "failed"
