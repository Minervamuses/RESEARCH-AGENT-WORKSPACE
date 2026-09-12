"""Focused durable-catalog and conversation-restoration tests."""

import asyncio
import json
import threading
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from conftest import make_astream_graph, tool_then_answer_updates

from agent.config import AgentConfig
from agent.conversations import (
    ConversationRepository,
    ConversationTurn,
    ConversationUnavailableError,
    FailureInfo,
    ToolActivitySummary,
)
from agent.desktop.catalog import (
    CATALOG_FILENAME,
    CATALOG_MAX_BYTES,
    CatalogConflictError,
    CatalogMalformedError,
    CatalogUnavailableError,
    DesktopProjectCatalog,
    is_canonical_session_id,
)
from agent.desktop.protocol import success_result
from agent.desktop.service import DesktopService, DesktopServiceError
from agent.session import ChatSession
from agent.turns.results import TurnOutcome

SESSION_A = "28b222e0cc6543aa8d7bbdc423de99a7"
SESSION_B = "f2ddf2369f994905afa0b85d8cca79b1"
SESSION_C = "7a9708991f8f420bbdadc3e430a78c10"
SESSION_D = "a4d80f49d67a4e969af88f3f6f45a7c1"


class _CoordinatorSession:
    def __init__(
        self,
        config,
        *,
        session_id,
        project_id,
        conversation_repository,
        progress_cb,
    ):
        self.config = config
        self._repository = conversation_repository
        self.project_id = project_id
        self.progress_cb = progress_cb
        self.session_id = session_id
        self.turn_inputs = []
        self.turn_requests = []
        self.contexts = []
        self.thinking_mode = "normal"
        self.loaded_skills = []
        self.mcp_families = {}
        self.running_extension_revision = 0
        self.extension_startup_diagnostics = ()
        self._prompt_persisted_callback = None

    def _set_prompt_persisted_callback(self, callback):
        self._prompt_persisted_callback = callback

    def _notify_prompt_persisted(self):
        if self._prompt_persisted_callback is not None:
            self._prompt_persisted_callback()

    @property
    def _snapshot(self):
        return self._repository.load_optional(self.session_id)

    @property
    def recent_turns(self):
        snapshot = self._snapshot
        if snapshot is None:
            return []
        return [
            SimpleNamespace(
                user_input=turn.user_input,
                assistant_output=turn.assistant_output,
                turn_id=turn.turn_number,
                logical_turn_id=turn.turn_id,
            )
            for turn in self._repository.latest_context(snapshot)
        ]

    async def turn_outcome(
        self,
        text,
        *,
        display_input=None,
        turn_id=None,
        skill_name=None,
        retry=False,
    ):
        assert skill_name is None
        assert isinstance(turn_id, str)
        snapshot = self._snapshot
        context = self._repository.latest_context(snapshot) if snapshot else ()
        self.contexts.append([turn.user_input for turn in context])
        display = text if display_input is None else display_input
        values = {
            "turn_id": turn_id,
            "kind": "conversational",
            "display_input": display,
            "semantic_input": text,
            "context_eligible": True,
            "thinking_mode": self.thinking_mode,
        }
        next_number = len(snapshot.document.turns) + 1 if snapshot else 1
        timestamp = f"2026-08-29T00:{next_number:02d}:00Z"
        if snapshot is None:
            snapshot = self._repository.create(
                conversation_id=self.session_id,
                project_id=self.project_id,
                submitted_at=timestamp,
                **values,
            )
        else:
            existing = next(
                (
                    turn
                    for turn in snapshot.document.turns
                    if turn.turn_id == turn_id
                ),
                None,
            )
            if existing is not None and existing.state in {"failed", "interrupted"}:
                assert retry is True
                snapshot = self._repository.retry_turn(
                    snapshot,
                    retry_at=timestamp,
                    **values,
                )
            else:
                snapshot = self._repository.append_pending(
                    snapshot,
                    submitted_at=timestamp,
                    **values,
                )
            existing = next(
                turn for turn in snapshot.document.turns if turn.turn_id == turn_id
            )
            if existing.state == "completed":
                self._notify_prompt_persisted()
                return TurnOutcome(
                    text=existing.assistant_output or "",
                    turn_id=turn_id,
                    turn_number=existing.turn_number,
                    state="completed",
                    accepted=True,
                    persisted=True,
                )

        self._notify_prompt_persisted()
        self.turn_inputs.append(text)
        self.turn_requests.append({
            "semantic_input": text,
            "display_input": display,
            "turn_id": turn_id,
        })
        answer = f"answer:{self.session_id[:4]}:{text}"
        snapshot = self._repository.complete_turn(
            snapshot,
            turn_id=turn_id,
            assistant_output=answer,
            finished_at=timestamp,
        )
        completed = next(
            turn for turn in snapshot.document.turns if turn.turn_id == turn_id
        )
        return TurnOutcome(
            text=answer,
            validation_errors=[],
            turn_id=turn_id,
            turn_number=completed.turn_number,
            state="completed",
            accepted=True,
            persisted=True,
        )

    async def run_display_only_turn(
        self,
        display_input,
        action,
        render_result,
        *,
        turn_id,
        retry=False,
        failure_retryable=True,
    ):
        del failure_retryable
        snapshot = self._snapshot
        values = {
            "turn_id": turn_id,
            "kind": "display-only",
            "display_input": display_input,
            "semantic_input": None,
            "context_eligible": False,
            "thinking_mode": None,
        }
        next_number = len(snapshot.document.turns) + 1 if snapshot else 1
        timestamp = f"2026-08-29T00:{next_number:02d}:00Z"
        if snapshot is None:
            snapshot = self._repository.create(
                conversation_id=self.session_id,
                project_id=self.project_id,
                submitted_at=timestamp,
                **values,
            )
        else:
            existing = next(
                (
                    turn
                    for turn in snapshot.document.turns
                    if turn.turn_id == turn_id
                ),
                None,
            )
            if existing is not None and existing.state in {"failed", "interrupted"}:
                assert retry is True
                snapshot = self._repository.retry_turn(
                    snapshot,
                    retry_at=timestamp,
                    **values,
                )
            else:
                snapshot = self._repository.append_pending(
                    snapshot,
                    submitted_at=timestamp,
                    **values,
                )
            existing = next(
                turn for turn in snapshot.document.turns if turn.turn_id == turn_id
            )
            if existing.state == "completed":
                self._notify_prompt_persisted()
                return None, TurnOutcome(
                    text=existing.assistant_output or "",
                    turn_id=turn_id,
                    turn_number=existing.turn_number,
                    state="completed",
                    accepted=True,
                    persisted=True,
                )

        self._notify_prompt_persisted()
        try:
            result = await action()
            text = render_result(result)
            completed = self._repository.complete_turn(
                snapshot,
                turn_id=turn_id,
                assistant_output=text,
                finished_at=timestamp,
            )
            turn = next(
                item for item in completed.document.turns if item.turn_id == turn_id
            )
            return result, TurnOutcome(
                text=text,
                turn_id=turn_id,
                turn_number=turn.turn_number,
                state="completed",
                accepted=True,
                persisted=True,
            )
        except asyncio.CancelledError:
            self._repository.fail_turn(
                snapshot,
                turn_id=turn_id,
                state="interrupted",
                failure=FailureInfo(
                    code="cancelled",
                    message="The command was cancelled.",
                    retryable=True,
                ),
                finished_at=timestamp,
            )
            raise
        except Exception:
            self._repository.fail_turn(
                snapshot,
                turn_id=turn_id,
                state="failed",
                failure=FailureInfo(
                    code="execution_failed",
                    message="The command failed.",
                    retryable=True,
                ),
                finished_at=timestamp,
            )
            raise

    def set_thinking_mode(self, mode):
        self.thinking_mode = mode

    def status_snapshot(self):
        snapshot = self._snapshot
        turn_count = len(snapshot.document.turns) if snapshot else 0
        return {
            "session_id": self.session_id,
            "conversation_root": "/tmp/canonical-conversations",
            "turn_count": turn_count,
            "recent_turn_count": len(self.recent_turns),
            "graph_recursion_limit": self.config.graph_recursion_limit,
            "last_tool_counts": "none",
            "thinking_mode": self.thinking_mode,
            "mcp_families": "none",
        }


class _CoordinatorFactory:
    def __init__(self, new_ids=()):
        self.new_ids = list(new_ids)
        self.sessions = []
        self.load_mcp_calls = []

    async def __call__(
        self,
        config,
        *,
        load_mcp,
        progress_cb,
        session_id=None,
        conversation_repository=None,
        project_id=None,
    ):
        self.load_mcp_calls.append(load_mcp)
        resolved_id = session_id or self.new_ids.pop(0)
        session = _CoordinatorSession(
            config,
            session_id=resolved_id,
            project_id=project_id,
            conversation_repository=conversation_repository,
            progress_cb=progress_cb,
        )
        self.sessions.append(session)
        return session


def _logical_turn_id(value: int) -> str:
    return uuid.UUID(int=value, version=4).hex


def _append_completed_turn(
    repository,
    session_id,
    project_id,
    turn_number=1,
    *,
    display_input=None,
    semantic_input=None,
    assistant_output=None,
    tool_activities=(),
):
    display = display_input or f"{session_id[:4]} question {turn_number}"
    semantic = semantic_input or display
    answer = assistant_output or f"{session_id[:4]} answer {turn_number}"
    turn_id = _logical_turn_id(turn_number)
    timestamp = f"2026-08-27T00:{turn_number:02d}:00Z"
    snapshot = repository.load_optional(session_id)
    values = {
        "turn_id": turn_id,
        "kind": "conversational",
        "display_input": display,
        "semantic_input": semantic,
        "context_eligible": True,
        "thinking_mode": "normal",
        "submitted_at": timestamp,
    }
    if snapshot is None:
        snapshot = repository.create(
            conversation_id=session_id,
            project_id=project_id,
            **values,
        )
    else:
        snapshot = repository.append_pending(snapshot, **values)
    return repository.complete_turn(
        snapshot,
        turn_id=turn_id,
        assistant_output=answer,
        finished_at=timestamp,
        tool_activities=tuple(tool_activities),
    )


def _append_lifecycle_turn(
    repository,
    session_id,
    project_id,
    turn_number,
    *,
    kind="conversational",
    state="completed",
    display_input=None,
):
    display = display_input or f"turn {turn_number}"
    timestamp = f"2026-08-27T00:{turn_number:02d}:00Z"
    values = {
        "turn_id": _logical_turn_id(turn_number),
        "kind": kind,
        "display_input": display,
        "semantic_input": None if kind == "display-only" else display,
        "context_eligible": kind == "conversational",
        "thinking_mode": "normal" if kind == "conversational" else None,
        "submitted_at": timestamp,
    }
    snapshot = repository.load_optional(session_id)
    if snapshot is None:
        snapshot = repository.create(
            conversation_id=session_id,
            project_id=project_id,
            **values,
        )
    else:
        snapshot = repository.append_pending(snapshot, **values)
    if state == "pending":
        return snapshot
    if state == "completed":
        return repository.complete_turn(
            snapshot,
            turn_id=values["turn_id"],
            assistant_output=f"result {turn_number}",
            finished_at=timestamp,
        )
    failure_code = "interrupted" if state == "interrupted" else "execution_failed"
    return repository.fail_turn(
        snapshot,
        turn_id=values["turn_id"],
        state=state,
        failure=FailureInfo(
            code=failure_code,
            message=f"safe {state} result",
            retryable=True,
        ),
        finished_at=timestamp,
    )


def _seed_coordinator(
    tmp_path,
    *,
    new_ids=(),
    seeded_sessions=(SESSION_A, SESSION_B, SESSION_C),
):
    persist_dir = tmp_path / "coordinator-store"
    persist_dir.mkdir()
    (persist_dir / CATALOG_FILENAME).write_text(json.dumps({
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
    }), encoding="utf-8")
    repository = ConversationRepository(persist_dir)
    projects = {
        SESSION_A: "p1",
        SESSION_B: "p1",
        SESSION_C: "p2",
    }
    for session_id in seeded_sessions:
        _append_completed_turn(
            repository,
            session_id,
            projects[session_id],
        )
    catalog = DesktopProjectCatalog(persist_dir)
    factory = _CoordinatorFactory(new_ids=new_ids)
    config = AgentConfig(
        persist_dir=str(persist_dir),
        plan_logs_dir=str(tmp_path / "plans"),
    )
    service = DesktopService(
        original_cwd=tmp_path,
        config=config,
        project_catalog=catalog,
        conversation_repository=repository,
        session_factory=factory,
        environ={
            "CONDA_DEFAULT_ENV": "app",
            "CONDA_PREFIX": "/conda/envs/app",
        },
    )

    return service, catalog, factory, repository


def _assert_result(method, data, suffix):
    success_result(
        f"00000000-0000-4000-8000-{suffix:012d}",
        method,
        data,
    )


def test_catalog_follows_materialized_session_and_same_session_select(tmp_path):
    from agent.skills import SkillMetadata

    service, _catalog, factory, _repository = _seed_coordinator(tmp_path)
    original_factory = service._session_factory
    desired = {SESSION_A: "writer", SESSION_B: "reviewer"}

    async def with_skills(*args, **kwargs):
        session = await original_factory(*args, **kwargs)
        session.loaded_skills = [SkillMetadata(
            desired[session.session_id], "Session skill", Path(__file__),
        )]
        return session

    service._session_factory = with_skills

    async def select(session_id):
        snapshot = await service.dispatch("session.select", {
            "projectId": "p1", "sessionId": session_id,
        })
        _assert_result("session.select", snapshot, 910)
        return snapshot["slashCommands"][-1]["name"]

    assert asyncio.run(select(SESSION_A)) == "writer"
    desired[SESSION_A] = "new-writer"
    assert asyncio.run(select(SESSION_A)) == "writer"
    assert len(factory.sessions) == 1
    assert asyncio.run(select(SESSION_B)) == "reviewer"
    assert asyncio.run(select(SESSION_A)) == "new-writer"
    asyncio.run(service.dispatch("session.shutdown", {}))
    desired[SESSION_A] = "restarted-writer"
    assert asyncio.run(select(SESSION_A)) == "restarted-writer"


def test_catalog_bootstraps_only_the_exact_default_schema(tmp_path):
    catalog = DesktopProjectCatalog(tmp_path)

    assert catalog.snapshot() == {
        "projects": [{
            "projectId": "local",
            "name": "Local research",
            "sessionIds": [],
        }]
    }
    durable = json.loads((tmp_path / CATALOG_FILENAME).read_text(encoding="utf-8"))
    assert durable == catalog.snapshot()


def test_catalog_registration_is_ordered_and_idempotent(tmp_path):
    catalog = DesktopProjectCatalog(tmp_path)

    assert catalog.register_session("local", SESSION_A) is True
    assert catalog.register_session("local", SESSION_A) is False
    assert catalog.register_session("local", SESSION_B) is True

    assert catalog.snapshot()["projects"][0]["sessionIds"] == [
        SESSION_A,
        SESSION_B,
    ]
    assert DesktopProjectCatalog(tmp_path).snapshot() == catalog.snapshot()


def test_catalog_malformed_existing_file_is_not_overwritten(tmp_path):
    path = tmp_path / CATALOG_FILENAME
    original = b'{"projects":[{"unexpected":true}]}\n'
    path.write_bytes(original)

    with pytest.raises(CatalogMalformedError):
        DesktopProjectCatalog(tmp_path)

    assert path.read_bytes() == original


def test_catalog_rejects_an_oversized_existing_file(tmp_path):
    path = tmp_path / CATALOG_FILENAME
    path.write_bytes(b"x" * (CATALOG_MAX_BYTES + 1))

    with pytest.raises(CatalogMalformedError, match="byte limit"):
        DesktopProjectCatalog(tmp_path)


def test_catalog_duplicate_session_across_projects_fails_closed(tmp_path):
    path = tmp_path / CATALOG_FILENAME
    original = {
        "projects": [
            {"projectId": "one", "name": "One", "sessionIds": [SESSION_A]},
            {"projectId": "two", "name": "Two", "sessionIds": [SESSION_A]},
        ]
    }
    path.write_text(json.dumps(original), encoding="utf-8")

    with pytest.raises(CatalogMalformedError, match="more than once"):
        DesktopProjectCatalog(tmp_path)


def test_catalog_failed_replace_keeps_memory_and_durable_file(tmp_path, monkeypatch):
    catalog = DesktopProjectCatalog(tmp_path)
    path = tmp_path / CATALOG_FILENAME
    original = path.read_bytes()

    def fail_replace(_source, _target):
        raise OSError("disk unavailable")

    monkeypatch.setattr("agent.desktop.catalog.os.replace", fail_replace)

    with pytest.raises(CatalogUnavailableError):
        catalog.register_session("local", SESSION_A)

    assert catalog.snapshot()["projects"][0]["sessionIds"] == []
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    "value",
    [
        SESSION_A.upper(),
        "28b222e0-cc65-43aa-8d7b-bdc423de99a7",
        "28b222e0cc6533aa8d7bbdc423de99a7",
        "not-a-session",
    ],
)
def test_catalog_rejects_noncanonical_uuid4_session_ids(tmp_path, value):
    catalog = DesktopProjectCatalog(tmp_path)

    assert is_canonical_session_id(value) is False
    with pytest.raises(CatalogConflictError):
        catalog.register_session("local", value)


def test_service_rebuilds_malformed_catalog_from_healthy_json_deterministically(
    tmp_path,
):
    persist_dir = tmp_path / "catalog-rebuild"
    persist_dir.mkdir()
    repository = ConversationRepository(persist_dir)
    for session_id in (SESSION_B, SESSION_A):
        _append_completed_turn(repository, session_id, "local")
    conversation_bytes = {
        session_id: repository.path_for(session_id).read_bytes()
        for session_id in (SESSION_A, SESSION_B)
    }
    catalog_path = persist_dir / CATALOG_FILENAME
    catalog_path.write_bytes(b'{"projects":[{"unexpected":true}]}\n')

    config = AgentConfig(persist_dir=str(persist_dir))
    service = DesktopService(
        original_cwd=tmp_path,
        config=config,
        session_factory=_CoordinatorFactory(),
        environ={},
    )
    projects = asyncio.run(service.dispatch("project.list", {}))
    sessions = asyncio.run(service.dispatch(
        "session.list",
        {"projectId": "local", "offset": 0, "limit": 50},
    ))

    assert projects["status"] == "ready"
    assert projects["projects"] == [{
        "projectId": "local",
        "name": "Local research",
        "sessionCount": 2,
    }]
    assert [item["sessionId"] for item in sessions["items"]] == [
        SESSION_A,
        SESSION_B,
    ]
    assert json.loads(catalog_path.read_text(encoding="utf-8")) == {
        "projects": [{
            "projectId": "local",
            "name": "Local research",
            "sessionIds": [SESSION_A, SESSION_B],
        }]
    }
    assert {
        session_id: repository.path_for(session_id).read_bytes()
        for session_id in (SESSION_A, SESSION_B)
    } == conversation_bytes

    restarted = DesktopService(
        original_cwd=tmp_path,
        config=config,
        session_factory=_CoordinatorFactory(),
        environ={},
    )
    restarted_sessions = asyncio.run(restarted.dispatch(
        "session.list",
        {"projectId": "local", "offset": 0, "limit": 50},
    ))
    assert [item["sessionId"] for item in restarted_sessions["items"]] == [
        SESSION_A,
        SESSION_B,
    ]


def test_unknown_project_orphan_uses_deterministic_project_name_fallback(tmp_path):
    persist_dir = tmp_path / "unknown-project"
    persist_dir.mkdir()
    repository = ConversationRepository(persist_dir)
    _append_completed_turn(
        repository,
        SESSION_D,
        "research-one",
        assistant_output="recoverable answer",
    )
    conversation_path = repository.path_for(SESSION_D)
    conversation_bytes = conversation_path.read_bytes()
    config = AgentConfig(persist_dir=str(persist_dir))
    factory = _CoordinatorFactory()

    service = DesktopService(
        original_cwd=tmp_path,
        config=config,
        conversation_repository=repository,
        session_factory=factory,
        environ={},
    )
    projects = asyncio.run(service.dispatch("project.list", {}))
    sessions = asyncio.run(service.dispatch(
        "session.list",
        {"projectId": "research-one", "offset": 0, "limit": 50},
    ))
    selected = asyncio.run(service.dispatch(
        "session.select",
        {"projectId": "research-one", "sessionId": SESSION_D},
    ))

    assert projects["projects"] == [
        {
            "projectId": "local",
            "name": "Local research",
            "sessionCount": 0,
        },
        {
            "projectId": "research-one",
            "name": "research-one",
            "sessionCount": 1,
        },
    ]
    assert [item["sessionId"] for item in sessions["items"]] == [SESSION_D]
    assert selected["sessionId"] == SESSION_D
    assert factory.sessions[-1].turn_inputs == []
    assert conversation_path.read_bytes() == conversation_bytes


def test_catalog_only_missing_json_stays_unavailable_without_fake_transcript(
    tmp_path,
):
    service, catalog, _factory, repository = _seed_coordinator(
        tmp_path,
        seeded_sessions=(SESSION_A,),
    )
    missing_path = repository.path_for(SESSION_B)

    selected = asyncio.run(service.dispatch(
        "session.select",
        {"projectId": "p1", "sessionId": SESSION_A},
    ))
    asyncio.run(service.dispatch("session.set_bash_permission", {"mode": "bypass"}))
    sessions = asyncio.run(service.dispatch(
        "session.list",
        {"projectId": "p1", "offset": 0, "limit": 50},
    ))
    transcript = asyncio.run(service.dispatch(
        "session.transcript",
        {"projectId": "p1", "sessionId": SESSION_B, "offset": 0, "limit": 20},
    ))
    missing_summary = next(
        item for item in sessions["items"] if item["sessionId"] == SESSION_B
    )
    with pytest.raises(DesktopServiceError) as raised:
        asyncio.run(service.dispatch(
            "session.select",
            {"projectId": "p1", "sessionId": SESSION_B},
        ))

    assert selected["sessionId"] == SESSION_A
    assert missing_summary["status"] == "unavailable"
    assert missing_summary["turnCount"] == 0
    assert transcript == {
        "projectId": "p1",
        "sessionId": SESSION_B,
        "status": "unavailable",
        "issue": "No persisted transcript is available.",
        "items": [],
        "total": 0,
        "offset": 0,
        "limit": 20,
        "hasMore": False,
    }
    assert raised.value.code == "SESSION_NOT_READY"
    assert service.session is not None
    assert service.session.session_id == SESSION_A
    assert catalog.project_for_session(SESSION_B) == "p1"
    assert not missing_path.exists()
    controls = asyncio.run(service.dispatch(
        "session.set_thinking", {"mode": "extended"}
    ))
    assert controls["sessionId"] == SESSION_A
    assert controls["bashPermissionMode"] == "bypass"


def test_malformed_conversation_is_isolated_while_healthy_session_lists_and_selects(
    tmp_path,
):
    base, _catalog, _factory, repository = _seed_coordinator(tmp_path)
    malformed_path = repository.path_for(SESSION_B)
    malformed_bytes = b'{"schemaVersion":1,"private":"do not expose"}\n'
    malformed_path.write_bytes(malformed_bytes)
    factory = _CoordinatorFactory()
    service = DesktopService(
        original_cwd=tmp_path,
        config=base.config,
        project_catalog=DesktopProjectCatalog(base.config.persist_dir),
        conversation_repository=repository,
        session_factory=factory,
        environ={},
    )

    sessions = asyncio.run(service.dispatch(
        "session.list",
        {"projectId": "p1", "offset": 0, "limit": 50},
    ))
    selected = asyncio.run(service.dispatch(
        "session.select",
        {"projectId": "p1", "sessionId": SESSION_A},
    ))
    transcript = asyncio.run(service.dispatch(
        "session.transcript",
        {"projectId": "p1", "sessionId": SESSION_A, "offset": 0, "limit": 20},
    ))
    by_session = {item["sessionId"]: item for item in sessions["items"]}

    assert by_session[SESSION_A]["status"] == "ready"
    assert by_session[SESSION_B]["status"] == "degraded"
    assert "private" not in by_session[SESSION_B]["issue"]
    assert selected["sessionId"] == SESSION_A
    assert transcript["status"] == "ready"
    assert factory.sessions[-1].turn_inputs == []
    assert malformed_path.read_bytes() == malformed_bytes


def test_session_restore_uses_only_canonical_history_and_writes_through(
    tmp_path,
    monkeypatch,
):
    async def fake_startup(_config, *, load_mcp):
        assert load_mcp is False
        return SimpleNamespace(
            extra_tools=(),
            mcp_families={},
            global_mcp_families=frozenset(),
            loaded_skills=(),
            running_extension_revision=0,
            extension_startup_diagnostics=(),
        )

    config = AgentConfig(persist_dir=str(tmp_path / "persist"))
    repository = ConversationRepository(config.persist_dir)
    _append_completed_turn(
        repository,
        SESSION_A,
        "p1",
        display_input="canonical display q1",
        semantic_input="canonical semantic q1",
        assistant_output="canonical a1",
    )
    monkeypatch.setattr("agent.session.find_app_root", lambda: tmp_path)
    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _cfg, **_kwargs: make_astream_graph(answer="canonical a2"),
    )
    monkeypatch.setattr("agent.startup.load_session_startup", fake_startup)

    session = asyncio.run(ChatSession.restore(
        config,
        session_id=SESSION_A,
        conversation_repository=repository,
        project_id="p1",
        load_mcp=False,
    ))

    assert session.session_id == SESSION_A
    assert [turn.user_input for turn in session.recent_turns] == [
        "canonical semantic q1"
    ]
    assert session._turn_counter == 1
    answer = asyncio.run(session.turn(
        "canonical semantic q2",
        display_input="/skill canonical semantic q2",
        turn_id=_logical_turn_id(102),
    ))
    snapshot = repository.load(SESSION_A)

    assert answer == "canonical a2"
    assert [turn.state for turn in snapshot.document.turns] == [
        "completed",
        "completed",
    ]
    assert snapshot.document.turns[1].display_input == (
        "/skill canonical semantic q2"
    )
    assert snapshot.document.turns[1].semantic_input == "canonical semantic q2"


def test_coordinator_preserves_p1_p2_membership_order_across_restart(tmp_path):
    service, catalog, _factory, repository = _seed_coordinator(tmp_path)

    projects = asyncio.run(service.dispatch("project.list", {}))
    p1 = asyncio.run(service.dispatch(
        "session.list",
        {"projectId": "p1", "offset": 0, "limit": 50},
    ))
    p2 = asyncio.run(service.dispatch(
        "session.list",
        {"projectId": "p2", "offset": 0, "limit": 50},
    ))
    _assert_result("project.list", projects, 201)
    _assert_result("session.list", p1, 202)
    _assert_result("session.list", p2, 203)
    assert [item["projectId"] for item in projects["projects"]] == ["p1", "p2"]
    assert [item["sessionId"] for item in p1["items"]] == [SESSION_A, SESSION_B]
    assert [item["sessionId"] for item in p2["items"]] == [SESSION_C]
    assert set(catalog.snapshot()["projects"][0]) == {
        "projectId",
        "name",
        "sessionIds",
    }

    restarted_catalog = DesktopProjectCatalog(service.config.persist_dir)
    restarted_factory = _CoordinatorFactory()
    restarted = DesktopService(
        original_cwd=tmp_path,
        config=service.config,
        project_catalog=restarted_catalog,
        conversation_repository=repository,
        session_factory=restarted_factory,
        environ={
            "CONDA_DEFAULT_ENV": "app",
            "CONDA_PREFIX": "/conda/envs/app",
        },
    )

    after_restart = asyncio.run(restarted.dispatch("project.list", {}))
    p1_after = asyncio.run(restarted.dispatch(
        "session.list",
        {"projectId": "p1", "offset": 0, "limit": 50},
    ))
    selected = asyncio.run(restarted.dispatch(
        "session.select",
        {"projectId": "p1", "sessionId": SESSION_A},
    ))
    _assert_result("project.list", after_restart, 204)
    _assert_result("session.list", p1_after, 205)
    _assert_result("session.select", selected, 206)
    assert [item["projectId"] for item in after_restart["projects"]] == ["p1", "p2"]
    assert [item["sessionId"] for item in p1_after["items"]] == [
        SESSION_A,
        SESSION_B,
    ]
    assert selected["sessionId"] == SESSION_A
    assert selected["turnCount"] == 1
    assert selected["thinkingMode"] == "normal"
    assert restarted_factory.sessions[-1].turn_inputs == []


def test_restart_discovers_completed_json_missing_from_catalog_without_replay(
    tmp_path,
):
    service, catalog, _factory, repository = _seed_coordinator(tmp_path)
    _append_completed_turn(
        repository,
        SESSION_D,
        "p1",
        display_input="saved before catalog registration",
        assistant_output="already answered",
    )
    durable_path = repository.path_for(SESSION_D)
    durable_before = durable_path.read_bytes()
    assert catalog.project_for_session(SESSION_D) is None

    restarted_catalog = DesktopProjectCatalog(service.config.persist_dir)
    restarted_factory = _CoordinatorFactory()
    restarted = DesktopService(
        original_cwd=tmp_path,
        config=service.config,
        project_catalog=restarted_catalog,
        conversation_repository=repository,
        session_factory=restarted_factory,
        environ={
            "CONDA_DEFAULT_ENV": "app",
            "CONDA_PREFIX": "/conda/envs/app",
        },
    )

    sessions = asyncio.run(restarted.dispatch(
        "session.list",
        {"projectId": "p1", "offset": 0, "limit": 50},
    ))
    transcript = asyncio.run(restarted.dispatch(
        "session.transcript",
        {"projectId": "p1", "sessionId": SESSION_D, "limit": 20},
    ))
    selected = asyncio.run(restarted.dispatch(
        "session.select",
        {"projectId": "p1", "sessionId": SESSION_D},
    ))

    assert [item["sessionId"] for item in sessions["items"]] == [
        SESSION_A,
        SESSION_B,
        SESSION_D,
    ]
    assert restarted_catalog.project_for_session(SESSION_D) == "p1"
    assert transcript["status"] == "ready"
    assert transcript["items"][0]["assistantText"] == "already answered"
    assert selected["turnCount"] == 1
    assert restarted_factory.sessions[-1].turn_inputs == []
    assert durable_path.read_bytes() == durable_before


def test_session_select_defaults_mcp_on_initially_and_after_shutdown(tmp_path):
    service, _catalog, factory, _repository = _seed_coordinator(
        tmp_path,
        new_ids=(SESSION_D,),
    )

    async def run():
        diagnostics = await service.dispatch("runtime.diagnostics", {})
        assert diagnostics["mcpEnabled"] is True

        await service.dispatch(
            "session.create",
            {"projectId": "p1", "loadMcp": False},
        )
        assert factory.load_mcp_calls == [False]

        assert await service.dispatch("session.shutdown", {}) == {
            "status": "stopped",
        }
        selected = await service.dispatch(
            "session.select",
            {"projectId": "p1", "sessionId": SESSION_A},
        )

        assert selected["sessionId"] == SESSION_A
        assert factory.load_mcp_calls == [False, True]

    asyncio.run(run())


def test_ready_conversation_and_transcript_pages_report_exact_boundaries(tmp_path):
    service, _catalog, _factory, repository = _seed_coordinator(tmp_path)
    _append_completed_turn(repository, SESSION_A, "p1", 2)

    sessions_first = asyncio.run(service.dispatch(
        "session.list",
        {"projectId": "p1", "offset": 0, "limit": 1},
    ))
    sessions_second = asyncio.run(service.dispatch(
        "session.list",
        {"projectId": "p1", "offset": 1, "limit": 1},
    ))
    transcript_first = asyncio.run(service.dispatch(
        "session.transcript",
        {"projectId": "p1", "sessionId": SESSION_A, "offset": 0, "limit": 1},
    ))
    transcript_second = asyncio.run(service.dispatch(
        "session.transcript",
        {"projectId": "p1", "sessionId": SESSION_A, "offset": 1, "limit": 1},
    ))

    assert [item["sessionId"] for item in sessions_first["items"]] == [SESSION_A]
    assert sessions_first["total"] == 2
    assert sessions_first["hasMore"] is True
    assert [item["sessionId"] for item in sessions_second["items"]] == [SESSION_B]
    assert sessions_second["total"] == 2
    assert sessions_second["hasMore"] is False
    assert [item["turnNumber"] for item in transcript_first["items"]] == [1]
    assert transcript_first["total"] == 2
    assert transcript_first["hasMore"] is True
    assert [item["turnNumber"] for item in transcript_second["items"]] == [2]
    assert transcript_second["total"] == 2
    assert transcript_second["hasMore"] is False


def test_sidebar_summary_is_derived_from_json_lifecycle_metadata(tmp_path):
    persist_dir = tmp_path / "summary-store"
    persist_dir.mkdir()
    (persist_dir / CATALOG_FILENAME).write_text(json.dumps({
        "projects": [{
            "projectId": "p1",
            "name": "Project One",
            "sessionIds": [SESSION_A],
        }]
    }), encoding="utf-8")
    repository = ConversationRepository(persist_dir)
    _append_lifecycle_turn(
        repository,
        SESSION_A,
        "p1",
        1,
        kind="display-only",
        display_input="/status",
    )
    _append_lifecycle_turn(
        repository,
        SESSION_A,
        "p1",
        2,
        state="failed",
        display_input="  First   accepted\nresearch question  ",
    )
    _append_lifecycle_turn(
        repository,
        SESSION_A,
        "p1",
        3,
        display_input="later prompt cannot replace the title",
    )
    service = DesktopService(
        original_cwd=tmp_path,
        config=AgentConfig(persist_dir=str(persist_dir)),
        project_catalog=DesktopProjectCatalog(persist_dir),
        conversation_repository=repository,
        session_factory=_CoordinatorFactory(),
        environ={},
    )

    sessions = asyncio.run(service.dispatch(
        "session.list",
        {"projectId": "p1", "offset": 0, "limit": 50},
    ))
    summary = sessions["items"][0]

    assert summary == {
        "sessionId": SESSION_A,
        "title": "First accepted research question",
        "turnCount": 3,
        "createdAt": "2026-08-27T00:01:00Z",
        "updatedAt": "2026-08-27T00:03:00Z",
        "status": "ready",
        "issue": None,
    }


def test_fifty_turn_transcript_pages_preserve_every_lifecycle_record(tmp_path):
    persist_dir = tmp_path / "fifty-turn-store"
    persist_dir.mkdir()
    (persist_dir / CATALOG_FILENAME).write_text(json.dumps({
        "projects": [{
            "projectId": "p1",
            "name": "Project One",
            "sessionIds": [SESSION_A],
        }]
    }), encoding="utf-8")
    repository = ConversationRepository(persist_dir)
    for number in range(1, 51):
        if number == 50:
            state = "pending"
        elif number % 11 == 0:
            state = "interrupted"
        elif number % 7 == 0:
            state = "failed"
        else:
            state = "completed"
        _append_lifecycle_turn(
            repository,
            SESSION_A,
            "p1",
            number,
            kind="display-only" if number % 5 == 0 else "conversational",
            state=state,
        )
    service = DesktopService(
        original_cwd=tmp_path,
        config=AgentConfig(persist_dir=str(persist_dir)),
        project_catalog=DesktopProjectCatalog(persist_dir),
        conversation_repository=repository,
        session_factory=_CoordinatorFactory(),
        environ={},
    )

    pages = [
        asyncio.run(service.dispatch("session.transcript", {
            "projectId": "p1",
            "sessionId": SESSION_A,
            "offset": offset,
            "limit": 20,
        }))
        for offset in (0, 20, 40)
    ]
    items = [item for page in pages for item in page["items"]]

    assert [page["status"] for page in pages] == ["ready", "ready", "ready"]
    assert [page["total"] for page in pages] == [50, 50, 50]
    assert [len(page["items"]) for page in pages] == [20, 20, 10]
    assert [page["hasMore"] for page in pages] == [True, True, False]
    assert [item["turnNumber"] for item in items] == list(range(1, 51))
    assert [item["turnId"] for item in items] == [
        _logical_turn_id(number) for number in range(1, 51)
    ]
    assert {item["state"] for item in items} == {
        "pending",
        "completed",
        "failed",
        "interrupted",
    }
    assert {item["kind"] for item in items} == {
        "conversational",
        "display-only",
    }
    assert next(item for item in items if item["turnNumber"] == 50)[
        "assistantText"
    ] is None


def test_long_transcript_survives_switch_back_and_backend_recreation(tmp_path):
    persist_dir = tmp_path / "long-transcript-store"
    persist_dir.mkdir()
    (persist_dir / CATALOG_FILENAME).write_text(json.dumps({
        "projects": [{
            "projectId": "p1",
            "name": "Project One",
            "sessionIds": [SESSION_A, SESSION_B],
        }]
    }), encoding="utf-8")
    repository = ConversationRepository(persist_dir)
    first_answer = '中文🙂\n"quoted"\\path\n' + "a" * 40_000
    second_answer = "b" * 1_100_000
    _append_completed_turn(
        repository,
        SESSION_A,
        "p1",
        assistant_output=first_answer,
    )
    _append_completed_turn(
        repository,
        SESSION_A,
        "p1",
        turn_number=2,
        assistant_output=second_answer,
    )
    _append_completed_turn(repository, SESSION_B, "p1")

    def make_service() -> DesktopService:
        return DesktopService(
            original_cwd=tmp_path,
            config=AgentConfig(persist_dir=str(persist_dir)),
            project_catalog=DesktopProjectCatalog(persist_dir),
            conversation_repository=ConversationRepository(persist_dir),
            session_factory=_CoordinatorFactory(),
            environ={},
        )

    first = make_service()
    asyncio.run(first.dispatch(
        "session.select", {"projectId": "p1", "sessionId": SESSION_A}
    ))
    initial = asyncio.run(first.dispatch("session.transcript", {
        "projectId": "p1",
        "sessionId": SESSION_A,
        "offset": 0,
        "limit": 20,
    }))
    asyncio.run(first.dispatch(
        "session.select", {"projectId": "p1", "sessionId": SESSION_B}
    ))
    asyncio.run(first.dispatch(
        "session.select", {"projectId": "p1", "sessionId": SESSION_A}
    ))
    switched = asyncio.run(first.dispatch("session.transcript", {
        "projectId": "p1",
        "sessionId": SESSION_A,
        "offset": 0,
        "limit": 20,
    }))

    restarted = make_service()
    selected = asyncio.run(restarted.dispatch(
        "session.select", {"projectId": "p1", "sessionId": SESSION_A}
    ))
    restored = asyncio.run(restarted.dispatch("session.transcript", {
        "projectId": "p1",
        "sessionId": SESSION_A,
        "offset": 0,
        "limit": 20,
    }))

    for transcript in (initial, switched, restored):
        assert transcript["status"] == "ready"
        assert [item["assistantText"] for item in transcript["items"]] == [
            first_answer,
            second_answer,
        ]
    assert selected["turnCount"] == 2


def test_transient_d_registers_once_after_first_durable_turn(tmp_path):
    service, catalog, factory, repository = _seed_coordinator(
        tmp_path,
        new_ids=(SESSION_D,),
    )

    created = asyncio.run(service.dispatch(
        "session.create",
        {"projectId": "p1", "loadMcp": False},
    ))
    _assert_result("session.create", created, 211)
    assert created["sessionId"] == SESSION_D
    assert created["registered"] is False
    assert catalog.snapshot()["projects"][0]["sessionIds"] == [
        SESSION_A,
        SESSION_B,
    ]

    local = asyncio.run(service.dispatch("session.turn", {
        "text": "/status",
        "turnId": _logical_turn_id(211),
        "retry": False,
    }))
    _assert_result("session.turn", local, 212)
    assert local["responseKind"] == "command"
    assert local["registrationStatus"] == "registered"
    assert factory.sessions[-1].turn_inputs == []
    assert catalog.project_for_session(SESSION_D) == "p1"

    first = asyncio.run(service.dispatch("session.turn", {
        "text": "first",
        "turnId": _logical_turn_id(212),
        "retry": False,
    }))
    second = asyncio.run(service.dispatch("session.turn", {
        "text": "second",
        "turnId": _logical_turn_id(213),
        "retry": False,
    }))
    _assert_result("session.turn", first, 213)
    _assert_result("session.turn", second, 214)
    assert first["registrationStatus"] == "registered"
    assert second["registrationStatus"] == "registered"
    assert first["turnId"] == _logical_turn_id(212)
    assert first["state"] == "completed"
    assert first["accepted"] is True
    assert first["persisted"] is True
    assert factory.sessions[-1].turn_inputs == ["first", "second"]
    assert catalog.snapshot()["projects"][0]["sessionIds"] == [
        SESSION_A,
        SESSION_B,
        SESSION_D,
    ]
    assert [
        turn.display_input
        for turn in repository.load(SESSION_D).document.turns
    ] == ["/status", "first", "second"]


def test_first_prompt_registers_catalog_before_provider_failure(
    tmp_path,
    monkeypatch,
):
    config = AgentConfig(
        persist_dir=str(tmp_path / "store"),
        plan_logs_dir=str(tmp_path / "plans"),
    )
    catalog = DesktopProjectCatalog(config.persist_dir)
    repository = ConversationRepository(config.persist_dir)
    created_id: str | None = None
    observed: dict[str, object] = {}

    def fail_at_provider_boundary(_state):
        assert created_id is not None
        turn = repository.load(created_id).document.turns[-1]
        observed.update({
            "state": turn.state,
            "owner": catalog.project_for_session(created_id),
        })
        raise RuntimeError("synthetic provider boundary failure")

    graph = make_astream_graph(on_state=fail_at_provider_boundary)
    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _config, extra_tools=None, **kwargs: graph,
    )

    async def session_factory(
        current_config,
        *,
        load_mcp,
        progress_cb,
        session_id=None,
        conversation_repository=None,
        project_id=None,
    ):
        del load_mcp
        session = ChatSession(
            current_config,
            progress_cb=progress_cb,
            loaded_skills=[],
            global_mcp_families=frozenset(),
            session_id=session_id,
            conversation_repository=conversation_repository,
            project_id=project_id,
        )
        session.graph = graph
        return session

    service = DesktopService(
        original_cwd=tmp_path,
        config=config,
        project_catalog=catalog,
        conversation_repository=repository,
        session_factory=session_factory,
        environ={
            "CONDA_DEFAULT_ENV": "app",
            "CONDA_PREFIX": "/conda/envs/app",
        },
    )
    created = asyncio.run(service.dispatch(
        "session.create",
        {"projectId": "local", "loadMcp": False},
    ))
    created_id = created["sessionId"]
    turn_id = _logical_turn_id(214)

    with pytest.raises(DesktopServiceError) as raised:
        asyncio.run(service.dispatch("session.turn", {
            "text": "persist before provider",
            "turnId": turn_id,
            "retry": False,
        }))

    assert observed == {"state": "pending", "owner": "local"}
    assert raised.value.details == {
        "turnId": turn_id,
        "state": "failed",
        "accepted": True,
        "persisted": True,
    }
    assert catalog.project_for_session(created_id) == "local"
    assert repository.load(created_id).document.turns[-1].state == "failed"


def test_select_a_b_a_isolates_canonical_context_without_flushing(tmp_path):
    service, _catalog, factory, repository = _seed_coordinator(tmp_path)

    selected_a = asyncio.run(service.dispatch(
        "session.select",
        {"projectId": "p1", "sessionId": SESSION_A},
    ))
    thinking = asyncio.run(service.dispatch(
        "session.set_thinking",
        {"mode": "extended"},
    ))
    a_second = asyncio.run(service.dispatch("session.turn", {
        "text": "A second",
        "turnId": _logical_turn_id(221),
        "retry": False,
    }))
    selected_b = asyncio.run(service.dispatch(
        "session.select",
        {"projectId": "p1", "sessionId": SESSION_B},
    ))
    b_second = asyncio.run(service.dispatch("session.turn", {
        "text": "B second",
        "turnId": _logical_turn_id(222),
        "retry": False,
    }))
    returned_a = asyncio.run(service.dispatch(
        "session.select",
        {"projectId": "p1", "sessionId": SESSION_A},
    ))
    a_third = asyncio.run(service.dispatch("session.turn", {
        "text": "A third",
        "turnId": _logical_turn_id(223),
        "retry": False,
    }))

    for suffix, method, result in (
        (221, "session.select", selected_a),
        (222, "session.set_thinking", thinking),
        (224, "session.turn", a_second),
        (225, "session.select", selected_b),
        (226, "session.turn", b_second),
        (227, "session.select", returned_a),
        (228, "session.turn", a_third),
    ):
        _assert_result(method, result, suffix)

    assert selected_b["turnCount"] == 1
    assert selected_b["thinkingMode"] == "normal"
    assert returned_a["turnCount"] == 2
    assert returned_a["thinkingMode"] == "extended"
    assert a_third["text"].startswith(f"answer:{SESSION_A[:4]}:")
    assert b_second["text"].startswith(f"answer:{SESSION_B[:4]}:")
    final_a = factory.sessions[-1]
    assert final_a.session_id == SESSION_A
    assert final_a.contexts[-1] == [
        f"{SESSION_A[:4]} question 1",
        "A second",
    ]
    durable_a = repository.load(SESSION_A).document.turns
    durable_b = repository.load(SESSION_B).document.turns
    assert all("B second" not in turn.display_input for turn in durable_a)
    assert [turn.turn_number for turn in durable_b] == [1, 2]
    assert [turn.state for turn in durable_a] == [
        "completed",
        "completed",
        "completed",
    ]
    assert a_third["registrationStatus"] == "registered"


def test_control_snapshots_are_not_evicted_at_the_old_128_session_boundary(
    tmp_path,
):
    service, _catalog, factory, _repository = _seed_coordinator(tmp_path)
    asyncio.run(service.dispatch(
        "session.select",
        {"projectId": "p1", "sessionId": SESSION_A},
    ))
    snapshot = service._capture_controls(factory.sessions[-1])
    session_ids = [uuid.UUID(int=index + 1, version=4).hex for index in range(129)]

    for session_id in session_ids:
        service._store_control_snapshot(session_id, snapshot)

    assert service._control_snapshots[session_ids[0]] == snapshot


def test_registration_failure_is_pending_and_retry_does_not_rerun_turn(
    tmp_path,
    monkeypatch,
):
    service, catalog, factory, repository = _seed_coordinator(
        tmp_path,
        new_ids=(SESSION_D,),
    )
    created = asyncio.run(service.dispatch(
        "session.create",
        {"projectId": "p1", "loadMcp": False},
    ))
    _assert_result("session.create", created, 231)
    durable_path = Path(service.config.persist_dir) / CATALOG_FILENAME
    durable_before = durable_path.read_bytes()
    atomic_replace = catalog._atomic_replace

    def fail_replace(_snapshot):
        raise CatalogUnavailableError("simulated atomic replacement failure")

    monkeypatch.setattr(catalog, "_atomic_replace", fail_replace)
    turn_id = _logical_turn_id(231)
    answer = asyncio.run(service.dispatch("session.turn", {
        "text": "record once",
        "turnId": turn_id,
        "retry": False,
    }))
    _assert_result("session.turn", answer, 232)
    assert answer["registrationStatus"] == "pending"
    assert answer["text"] == f"answer:{SESSION_D[:4]}:record once"
    assert durable_path.read_bytes() == durable_before
    assert catalog.project_for_session(SESSION_D) is None
    stored_before_retry = repository.load(SESSION_D)
    assert stored_before_retry.document.turns[0].turn_id == turn_id
    assert stored_before_retry.document.turns[0].state == "completed"

    monkeypatch.setattr(catalog, "_atomic_replace", atomic_replace)
    retry = asyncio.run(service.dispatch(
        "session.retry_registration",
        {"projectId": "p1", "sessionId": SESSION_D},
    ))
    repeated_retry = asyncio.run(service.dispatch(
        "session.retry_registration",
        {"projectId": "p1", "sessionId": SESSION_D},
    ))
    transcript = asyncio.run(service.dispatch(
        "session.transcript",
        {"projectId": "p1", "sessionId": SESSION_D, "offset": 0, "limit": 20},
    ))
    _assert_result("session.retry_registration", retry, 233)
    _assert_result("session.retry_registration", repeated_retry, 234)
    _assert_result("session.transcript", transcript, 235)
    assert retry["status"] == "registered"
    assert repeated_retry["status"] == "registered"
    assert factory.sessions[-1].turn_inputs == ["record once"]
    assert catalog.snapshot()["projects"][0]["sessionIds"].count(SESSION_D) == 1
    assert transcript["status"] == "ready"
    assert transcript["items"][0]["assistantText"] == answer["text"]


def test_canonical_tool_summary_restore_never_replays_raw_tool_payload(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("agent.session.find_app_root", lambda: tmp_path)
    monkeypatch.setattr("agent.desktop.service.find_app_root", lambda: tmp_path)
    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _cfg, extra_tools=None, **kwargs: (
            make_astream_graph(answer="constructor placeholder")
        ),
    )
    persist_dir = tmp_path / "plan-lifecycle-store"
    catalog = DesktopProjectCatalog(persist_dir)
    config = AgentConfig(
        persist_dir=str(persist_dir),
        plan_logs_dir="plans",
    )
    repository = ConversationRepository(persist_dir)

    fake_tool_invocations: list[str] = []
    first_graph = make_astream_graph(
        tool_then_answer_updates(
            "rag_search",
            {"query": "persisted tool"},
            "call-persisted",
            "persisted tool result",
            "persisted final answer",
        ),
        on_state=lambda _state: fake_tool_invocations.append("call-persisted"),
    )

    async def first_factory(
        current_config,
        *,
        load_mcp,
        progress_cb,
        session_id=None,
        conversation_repository=None,
        project_id=None,
    ):
        del load_mcp
        assert conversation_repository is repository
        session = ChatSession(
            current_config,
            progress_cb=progress_cb,
            loaded_skills=[],
            global_mcp_families=frozenset(),
            session_id=session_id or SESSION_D,
            conversation_repository=conversation_repository,
            project_id=project_id,
        )
        session.graph = first_graph
        return session

    first = DesktopService(
        original_cwd=tmp_path,
        config=config,
        project_catalog=catalog,
        conversation_repository=repository,
        session_factory=first_factory,
        environ={
            "CONDA_DEFAULT_ENV": "app",
            "CONDA_PREFIX": "/conda/envs/app",
        },
    )

    async def run_first_process():
        created = await first.dispatch(
            "session.create",
            {"projectId": "local", "loadMcp": False},
        )
        answer = await first.dispatch(
            "session.turn",
            {
                "text": "persist this tool turn",
                "turnId": _logical_turn_id(251),
                "retry": False,
            },
        )
        shutdown = await first.dispatch("session.shutdown", {})
        return created, answer, shutdown

    created, first_answer, first_shutdown = asyncio.run(run_first_process())
    assert created["sessionId"] == SESSION_D
    assert first_answer["text"] == "persisted final answer"
    assert first_answer["turnId"] == _logical_turn_id(251)
    assert first_answer["state"] == "completed"
    assert first_shutdown == {"status": "stopped"}
    assert fake_tool_invocations == ["call-persisted"]
    assert catalog.project_for_session(SESSION_D) == "local"

    second_graph = make_astream_graph(answer="continued answer")

    async def second_factory(
        current_config,
        *,
        load_mcp,
        progress_cb,
        session_id=None,
        conversation_repository=None,
        project_id=None,
    ):
        del load_mcp
        assert conversation_repository is repository
        session = ChatSession(
            current_config,
            progress_cb=progress_cb,
            loaded_skills=[],
            global_mcp_families=frozenset(),
            session_id=session_id,
            conversation_repository=conversation_repository,
            project_id=project_id,
        )
        session.graph = second_graph
        return session

    second = DesktopService(
        original_cwd=tmp_path,
        config=config,
        project_catalog=DesktopProjectCatalog(persist_dir),
        conversation_repository=repository,
        session_factory=second_factory,
        environ={
            "CONDA_DEFAULT_ENV": "app",
            "CONDA_PREFIX": "/conda/envs/app",
        },
    )

    async def run_second_process():
        transcript = await second.dispatch(
            "session.transcript",
            {"projectId": "local", "sessionId": SESSION_D, "limit": 20},
        )
        selected = await second.dispatch(
            "session.select",
            {"projectId": "local", "sessionId": SESSION_D},
        )
        continued = await second.dispatch(
            "session.turn",
            {
                "text": "continue without replay",
                "turnId": _logical_turn_id(252),
                "retry": False,
            },
        )
        return transcript, selected, continued

    transcript, selected, continued = asyncio.run(run_second_process())

    assert selected["turnCount"] == 1
    assert continued["text"] == "continued answer"
    assert fake_tool_invocations == ["call-persisted"]
    assert transcript["status"] == "ready"
    assert transcript["items"] == [{
        "turnId": _logical_turn_id(251),
        "turnNumber": 1,
        "kind": "conversational",
        "state": "completed",
        "timestamp": transcript["items"][0]["timestamp"],
        "userText": "persist this tool turn",
        "assistantText": "persisted final answer",
        "failureCode": None,
        "failureMessage": None,
        "failureRetryable": None,
        "toolActivities": [{
            "callId": "call-persisted",
            "name": "rag_search",
            "arguments": "(not retained)",
            "result": "Tool execution completed.",
            "status": "ok",
            "promptEligible": False,
        }],
    }]
    prompt_messages = [
        message
        for message in second_graph.states[0]["messages"]
        if not isinstance(message, SystemMessage)
    ]
    assert [type(message) for message in prompt_messages] == [
        HumanMessage,
        AIMessage,
        HumanMessage,
    ]
    assert prompt_messages[0].content == "persist this tool turn"
    assert prompt_messages[1].content == "persisted final answer"
    assert prompt_messages[2].content == "continue without replay"


def test_transcript_complete_text_and_bounded_tool_page_are_returned_whole(
    tmp_path,
    monkeypatch,
):
    service, _catalog, _factory, _repository = _seed_coordinator(tmp_path)

    def activity(summary: str, index: int = 1) -> ToolActivitySummary:
        return ToolActivitySummary(
            call_id=f"call-{index}",
            name="rag_search",
            status="ok",
            summary=summary,
        )

    long_answer = 'BEGIN 中文🙂\n"quoted"\\path\n' + "界" * 400_000 + "\nEND"
    long_text_turn = ConversationTurn(
        turn_id=_logical_turn_id(301),
        turn_number=1,
        kind="conversational",
        state="completed",
        display_input="x" * 32_769,
        semantic_input="bounded question",
        context_eligible=True,
        thinking_mode="normal",
        submitted_at="2026-08-27T00:01:00Z",
        finished_at="2026-08-27T00:01:00Z",
        assistant_output=long_answer,
        tool_activities=(),
        failure=None,
    )
    monkeypatch.setattr(
        service,
        "_read_conversation_turns",
        lambda _session_id, _project_id: [long_text_turn],
    )
    field_result = asyncio.run(service.dispatch(
        "session.transcript",
        {"projectId": "p1", "sessionId": SESSION_A, "limit": 20},
    ))
    assert field_result["status"] == "ready"
    assert field_result["items"][0]["userText"] == "x" * 32_769
    assert field_result["items"][0]["assistantText"] == long_answer

    page_turn = ConversationTurn(
        turn_id=_logical_turn_id(302),
        turn_number=1,
        kind="conversational",
        state="completed",
        display_input="bounded question",
        semantic_input="bounded question",
        context_eligible=True,
        thinking_mode="normal",
        submitted_at="2026-08-27T00:01:00Z",
        finished_at="2026-08-27T00:01:00Z",
        assistant_output="bounded answer",
        tool_activities=tuple(
            activity("x" * 65_536, index)
            for index in range(1, 17)
        ),
        failure=None,
    )
    monkeypatch.setattr(
        service,
        "_read_conversation_turns",
        lambda _session_id, _project_id: [page_turn],
    )
    page_result = asyncio.run(service.dispatch(
        "session.transcript",
        {"projectId": "p1", "sessionId": SESSION_A, "limit": 20},
    ))
    assert page_result["status"] == "ready"
    assert len(page_result["items"][0]["toolActivities"]) == 16
    assert page_result["items"][0]["toolActivities"][-1]["result"] == "x" * 65_536


def test_duplicate_caller_turn_id_returns_saved_answer_without_model_replay(tmp_path):
    service, _catalog, factory, repository = _seed_coordinator(tmp_path)
    selected = asyncio.run(service.dispatch(
        "session.select",
        {"projectId": "p1", "sessionId": SESSION_A},
    ))
    turn_id = _logical_turn_id(311)
    first = asyncio.run(service.dispatch("session.turn", {
        "text": "record exactly once",
        "turnId": turn_id,
        "retry": False,
    }))
    duplicate = asyncio.run(service.dispatch("session.turn", {
        "text": "record exactly once",
        "turnId": turn_id,
        "retry": False,
    }))
    _assert_result("session.select", selected, 241)
    _assert_result("session.turn", first, 242)
    _assert_result("session.turn", duplicate, 243)
    assert duplicate == first
    assert factory.sessions[-1].turn_inputs == ["record exactly once"]
    turns = repository.load(SESSION_A).document.turns
    assert [turn.turn_id for turn in turns].count(turn_id) == 1


def test_unknown_degraded_unavailable_and_busy_coordinator_states(
    tmp_path,
    monkeypatch,
):
    service, _catalog, _factory, _repository = _seed_coordinator(tmp_path)
    selected = asyncio.run(service.dispatch(
        "session.select",
        {"projectId": "p1", "sessionId": SESSION_A},
    ))
    _assert_result("session.select", selected, 251)

    for method, params in (
        ("session.list", {"projectId": "missing", "offset": 0, "limit": 20}),
        ("session.select", {"projectId": "p1", "sessionId": SESSION_C}),
        (
            "session.transcript",
            {"projectId": "p1", "sessionId": SESSION_C, "offset": 0, "limit": 20},
        ),
    ):
        with pytest.raises(DesktopServiceError) as raised:
            asyncio.run(service.dispatch(method, params))
        assert raised.value.code == "PROTOCOL_INVALID"

    def degraded(_session_id, _project_id):
        raise ConversationUnavailableError("private malformed record detail")

    monkeypatch.setattr(service, "_read_conversation_turns", degraded)
    degraded_result = asyncio.run(service.dispatch(
        "session.transcript",
        {"projectId": "p1", "sessionId": SESSION_A, "offset": 0, "limit": 20},
    ))
    _assert_result("session.transcript", degraded_result, 252)
    assert degraded_result["status"] == "degraded"
    assert degraded_result["hasMore"] is False
    assert "private malformed record detail" not in degraded_result["issue"]

    monkeypatch.setattr(
        service,
        "_read_conversation_turns",
        lambda _session_id, _project_id: [],
    )
    unavailable = asyncio.run(service.dispatch(
        "session.transcript",
        {"projectId": "p1", "sessionId": SESSION_A, "offset": 0, "limit": 20},
    ))
    _assert_result("session.transcript", unavailable, 253)
    assert unavailable["status"] == "unavailable"
    assert unavailable["hasMore"] is False

    service._turn_active = True
    for method, params in (
        ("session.create", {"projectId": "p1", "loadMcp": False}),
        ("session.select", {"projectId": "p1", "sessionId": SESSION_B}),
        ("session.set_thinking", {"mode": "normal"}),
    ):
        with pytest.raises(DesktopServiceError) as raised:
            asyncio.run(service.dispatch(method, params))
        assert raised.value.code == "BUSY_TURN"
    service._turn_active = False

    with pytest.raises(DesktopServiceError) as retired:
        asyncio.run(service.dispatch("session.set_mode", {"mode": "normal"}))
    assert retired.value.code == "PROTOCOL_INVALID"

    malformed_dir = tmp_path / "malformed-store"
    malformed_dir.mkdir()
    malformed_bytes = b'{"projects":[{"unexpected":true}]}\n'
    (malformed_dir / CATALOG_FILENAME).write_bytes(malformed_bytes)
    malformed_service = DesktopService(
        original_cwd=tmp_path,
        config=AgentConfig(persist_dir=str(malformed_dir)),
        session_factory=_CoordinatorFactory(new_ids=(SESSION_D,)),
        environ={},
    )
    rebuilt_projects = asyncio.run(malformed_service.dispatch("project.list", {}))
    _assert_result("project.list", rebuilt_projects, 254)
    assert rebuilt_projects == {
        "status": "ready",
        "issue": None,
        "projects": [{
            "projectId": "local",
            "name": "Local research",
            "sessionCount": 0,
        }],
        "selectedProjectId": "local",
        "selectedSessionId": None,
    }
    assert json.loads(
        (malformed_dir / CATALOG_FILENAME).read_text(encoding="utf-8")
    ) == {
        "projects": [{
            "projectId": "local",
            "name": "Local research",
            "sessionIds": [],
        }]
    }


def test_select_a_b_a_preserves_bash_permission_mode_in_memory_across_conversations(
    tmp_path: Path,
) -> None:
    service, _catalog, _factory, _repository = _seed_coordinator(tmp_path)

    selected_a = asyncio.run(service.dispatch(
        "session.select",
        {"projectId": "p1", "sessionId": SESSION_A},
    ))
    assert selected_a["bashPermissionMode"] == "ask"

    ack_bypass = asyncio.run(service.dispatch(
        "session.set_bash_permission",
        {"mode": "bypass"},
    ))
    assert ack_bypass["bashPermissionMode"] == "bypass"

    selected_b = asyncio.run(service.dispatch(
        "session.select",
        {"projectId": "p1", "sessionId": SESSION_B},
    ))
    assert selected_b["bashPermissionMode"] == "ask"

    returned_a = asyncio.run(service.dispatch(
        "session.select",
        {"projectId": "p1", "sessionId": SESSION_A},
    ))
    assert returned_a["bashPermissionMode"] == "bypass"


def test_select_blocks_turn_during_conversation_read(tmp_path, monkeypatch):
    async def run():
        service, _catalog, _factory, _repository = _seed_coordinator(tmp_path)
        await service.dispatch(
            "session.select", {"projectId": "p1", "sessionId": SESSION_B}
        )
        await service.dispatch("session.set_bash_permission", {"mode": "bypass"})
        selected_a = await service.dispatch(
            "session.select", {"projectId": "p1", "sessionId": SESSION_A}
        )
        assert selected_a["bashPermissionMode"] == "ask"
        original_session = service.session
        original_load = service._load_conversation
        read_started = asyncio.Event()
        resume_read = threading.Event()
        loop = asyncio.get_running_loop()

        def paused_load(session_id, project_id):
            loop.call_soon_threadsafe(read_started.set)
            assert resume_read.wait(timeout=5), "conversation read was not released"
            return original_load(session_id, project_id)

        monkeypatch.setattr(service, "_load_conversation", paused_load)
        selection = asyncio.create_task(service.dispatch(
            "session.select", {"projectId": "p1", "sessionId": SESSION_B}
        ))
        try:
            await asyncio.wait_for(read_started.wait(), timeout=5)
            with pytest.raises(DesktopServiceError) as raised:
                await service.dispatch("session.turn", {
                    "text": "prompt while selecting",
                    "turnId": _logical_turn_id(99),
                    "retry": False,
                })
            assert raised.value.code == "SESSION_NOT_READY"
            assert original_session.turn_inputs == []
        finally:
            resume_read.set()
            selected_b = await asyncio.wait_for(selection, timeout=5)

        assert selected_b["sessionId"] == SESSION_B
        assert selected_b["bashPermissionMode"] == "bypass"
        returned_a = await service.dispatch(
            "session.select", {"projectId": "p1", "sessionId": SESSION_A}
        )
        assert returned_a["bashPermissionMode"] == "ask"

    asyncio.run(run())
