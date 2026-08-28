"""Focused durable-catalog and conversation-restoration tests."""

import asyncio
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import make_astream_graph

from agent.config import AgentConfig
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
from agent.history_rag.store import HistoryRestoreError
from agent.session import ChatSession
from agent.turns.memory import TurnRecord
from agent.turns.plan_log import PlanLog
from agent.turns.results import TurnOutcome

SESSION_A = "28b222e0cc6543aa8d7bbdc423de99a7"
SESSION_B = "f2ddf2369f994905afa0b85d8cca79b1"
SESSION_C = "7a9708991f8f420bbdadc3e430a78c10"
SESSION_D = "a4d80f49d67a4e969af88f3f6f45a7c1"


class _CoordinatorSession:
    def __init__(
        self,
        config,
        persisted,
        *,
        session_id,
        restored_turns,
        progress_cb,
    ):
        self.config = config
        self._persisted = persisted
        self.progress_cb = progress_cb
        self.session_id = session_id
        self.recent_turns = [
            TurnRecord(
                turn.user_input,
                turn.assistant_output,
                turn_id=turn.turn_id,
                timestamp=turn.timestamp,
                persist_target="none",
            )
            for turn in restored_turns
        ]
        self._turn_count = self.recent_turns[-1].turn_id if self.recent_turns else 0
        self.turn_inputs = []
        self.contexts = []
        self.plan_mode = False
        self.plan_log_path = None
        self.thinking_mode = "normal"
        self.active_skill_runtime = None
        self.loaded_skills = []
        self.mcp_families = {}
        self.running_extension_revision = 0
        self.extension_startup_diagnostics = ()
        self.fail_flush = False
        self.leave_after_flush = False
        self.flush_calls = 0

    async def turn_outcome(self, text):
        self.turn_inputs.append(text)
        self.contexts.append([turn.user_input for turn in self.recent_turns])
        self._turn_count += 1
        answer = f"answer:{self.session_id[:4]}:{text}"
        self.recent_turns.append(TurnRecord(
            user_input=text,
            assistant_output=answer,
            turn_id=self._turn_count,
            timestamp=f"2026-08-28T00:00:{self._turn_count:02d}Z",
            persist_target="chroma",
        ))
        return TurnOutcome(text=answer, validation_errors=[])

    async def flush_recent_turns(self):
        self.flush_calls += 1
        if self.fail_flush:
            raise OSError("simulated flush failure")
        existing = {
            turn.turn_id: turn
            for turn in self._persisted.get(self.session_id, [])
        }
        for turn in self.recent_turns:
            if turn.persist_target != "none":
                existing[turn.turn_id] = TurnRecord(
                    turn.user_input,
                    turn.assistant_output,
                    turn_id=turn.turn_id,
                    timestamp=turn.timestamp,
                    persist_target="none",
                )
        self._persisted[self.session_id] = [
            existing[turn_id] for turn_id in sorted(existing)
        ]
        if not self.leave_after_flush:
            self.recent_turns.clear()

    async def enter_plan_mode(self):
        self.plan_mode = True
        self.plan_log_path = Path("/tmp/fake-plan.md")
        return self.plan_log_path

    async def resume_plan_mode(self, log_path):
        self.plan_mode = True
        self.plan_log_path = Path(log_path)
        return self.plan_log_path

    async def exit_plan_mode(self):
        self.plan_mode = False
        self.plan_log_path = None

    def set_thinking_mode(self, mode):
        self.thinking_mode = mode

    def activate_skill(self, name, task_mode=None):
        self.active_skill_runtime = SimpleNamespace(name=name, task_mode=task_mode)
        return self.active_skill_runtime

    def deactivate_skill(self):
        self.active_skill_runtime = None

    def status_snapshot(self):
        return {
            "session_id": self.session_id,
            "turn_count": self._turn_count,
            "recent_turn_count": len(self.recent_turns),
            "graph_recursion_limit": self.config.graph_recursion_limit,
            "last_tool_counts": "none",
            "plan_mode": self.plan_mode,
            "plan_log_path": str(self.plan_log_path or ""),
            "thinking_mode": self.thinking_mode,
            "mcp_families": "none",
            "active_skill": "",
            "task_mode": "",
        }


class _CoordinatorFactory:
    def __init__(self, persisted, new_ids=()):
        self.persisted = persisted
        self.new_ids = list(new_ids)
        self.sessions = []

    async def __call__(
        self,
        config,
        *,
        load_mcp,
        progress_cb,
        session_id=None,
        restored_turns=None,
    ):
        del load_mcp
        resolved_id = session_id or self.new_ids.pop(0)
        session = _CoordinatorSession(
            config,
            self.persisted,
            session_id=resolved_id,
            restored_turns=list(restored_turns or []),
            progress_cb=progress_cb,
        )
        self.sessions.append(session)
        return session


def _stored_turn(session_id, turn_id=1):
    return TurnRecord(
        user_input=f"{session_id[:4]} question {turn_id}",
        assistant_output=f"{session_id[:4]} answer {turn_id}",
        turn_id=turn_id,
        timestamp=f"2026-08-27T00:00:{turn_id:02d}Z",
        persist_target="none",
    )


def _seed_coordinator(tmp_path, *, new_ids=()):
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
    persisted = {
        SESSION_A: [_stored_turn(SESSION_A)],
        SESSION_B: [_stored_turn(SESSION_B)],
        SESSION_C: [_stored_turn(SESSION_C)],
    }
    catalog = DesktopProjectCatalog(persist_dir)
    factory = _CoordinatorFactory(persisted, new_ids=new_ids)
    config = AgentConfig(
        persist_dir=str(persist_dir),
        plan_logs_dir=str(tmp_path / "plans"),
    )
    service = DesktopService(
        original_cwd=tmp_path,
        config=config,
        project_catalog=catalog,
        session_factory=factory,
        environ={
            "CONDA_DEFAULT_ENV": "app",
            "CONDA_PREFIX": "/conda/envs/app",
        },
    )

    def read_turns(session_id, include_current):
        by_id = {
            turn.turn_id: TurnRecord(
                turn.user_input,
                turn.assistant_output,
                turn_id=turn.turn_id,
                timestamp=turn.timestamp,
                persist_target="none",
            )
            for turn in persisted.get(session_id, [])
        }
        current = service.session
        if (
            include_current
            and current is not None
            and current.session_id == session_id
        ):
            for turn in current.recent_turns:
                by_id[turn.turn_id] = TurnRecord(
                    turn.user_input,
                    turn.assistant_output,
                    turn_id=turn.turn_id,
                    timestamp=turn.timestamp,
                    persist_target="none",
                )
        return [by_id[turn_id] for turn_id in sorted(by_id)]

    service._read_conversation_turns = read_turns
    return service, catalog, factory, persisted


def _assert_result(method, data, suffix):
    success_result(
        f"00000000-0000-4000-8000-{suffix:012d}",
        method,
        data,
    )


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


def test_session_restore_merges_sources_and_persists_only_the_new_turn(
    tmp_path,
    monkeypatch,
):
    class FakeStore:
        def __init__(self):
            self.adds = []

        def read_session_turns(self, session_id):
            assert session_id == SESSION_A
            return [TurnRecord(
                user_input="stored q1",
                assistant_output="stored a1",
                turn_id=1,
                timestamp="2026-08-28T01:00:00+00:00",
                persist_target="none",
            )]

        def add_turn(self, turn, **metadata):
            self.adds.append((turn, metadata))

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
    config.agent_recent_turns_window = 10
    plan_log = PlanLog(
        config,
        session_id=SESSION_A,
        app_root_resolver=lambda: tmp_path,
    )
    log_path = plan_log.new_log_file()
    plan_log.append_block(str(log_path), plan_log.render_block(
        turn_id=2,
        timestamp="2026-08-28T02:00:00+00:00",
        user_input="plan q2",
        answer="plan a2",
        new_messages=[],
        tool_calls=[],
    ))
    store = FakeStore()
    monkeypatch.setattr("agent.session.find_app_root", lambda: tmp_path)
    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _cfg, **_kwargs: make_astream_graph(),
    )
    monkeypatch.setattr("agent.startup.load_session_startup", fake_startup)

    session = asyncio.run(ChatSession.restore(
        config,
        session_id=SESSION_A,
        history_store=store,
        load_mcp=False,
    ))

    assert session.session_id == SESSION_A
    assert [turn.turn_id for turn in session.recent_turns] == [1, 2]
    assert session._turn_counter == 2
    asyncio.run(session.turn("new q3"))
    asyncio.run(session.flush_recent_turns())
    assert len(store.adds) == 1
    assert store.adds[0][0].turn_id == 3
    assert store.adds[0][0].user_input == "new q3"


def test_coordinator_preserves_p1_p2_membership_order_across_restart(tmp_path):
    service, catalog, _factory, persisted = _seed_coordinator(tmp_path)

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
    restarted_factory = _CoordinatorFactory(persisted)
    restarted = DesktopService(
        original_cwd=tmp_path,
        config=service.config,
        project_catalog=restarted_catalog,
        session_factory=restarted_factory,
        environ={
            "CONDA_DEFAULT_ENV": "app",
            "CONDA_PREFIX": "/conda/envs/app",
        },
    )
    restarted._read_conversation_turns = lambda session_id, _include: [
        TurnRecord(
            turn.user_input,
            turn.assistant_output,
            turn_id=turn.turn_id,
            timestamp=turn.timestamp,
            persist_target="none",
        )
        for turn in persisted.get(session_id, [])
    ]

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
    assert selected["planMode"] is False


def test_ready_conversation_and_transcript_pages_report_exact_boundaries(tmp_path):
    service, _catalog, _factory, persisted = _seed_coordinator(tmp_path)
    persisted[SESSION_A].append(_stored_turn(SESSION_A, 2))

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


def test_transient_d_registers_once_only_after_first_normal_turn(tmp_path):
    service, catalog, factory, _persisted = _seed_coordinator(
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

    local = asyncio.run(service.dispatch("session.turn", {"text": "/status"}))
    _assert_result("session.turn", local, 212)
    assert local["responseKind"] == "command"
    assert local["registrationStatus"] == "not_required"
    assert factory.sessions[-1].turn_inputs == []
    assert catalog.project_for_session(SESSION_D) is None

    first = asyncio.run(service.dispatch("session.turn", {"text": "first"}))
    second = asyncio.run(service.dispatch("session.turn", {"text": "second"}))
    _assert_result("session.turn", first, 213)
    _assert_result("session.turn", second, 214)
    assert first["registrationStatus"] == "registered"
    assert second["registrationStatus"] == "registered"
    assert factory.sessions[-1].turn_inputs == ["first", "second"]
    assert catalog.snapshot()["projects"][0]["sessionIds"] == [
        SESSION_A,
        SESSION_B,
        SESSION_D,
    ]


def test_select_a_b_a_isolates_context_counter_and_control_snapshot(tmp_path):
    service, _catalog, factory, persisted = _seed_coordinator(tmp_path)

    selected_a = asyncio.run(service.dispatch(
        "session.select",
        {"projectId": "p1", "sessionId": SESSION_A},
    ))
    thinking = asyncio.run(service.dispatch(
        "session.set_thinking",
        {"mode": "extended"},
    ))
    plan = asyncio.run(service.dispatch("session.set_mode", {"mode": "plan"}))
    a_second = asyncio.run(service.dispatch("session.turn", {"text": "A second"}))
    selected_b = asyncio.run(service.dispatch(
        "session.select",
        {"projectId": "p1", "sessionId": SESSION_B},
    ))
    b_second = asyncio.run(service.dispatch("session.turn", {"text": "B second"}))
    returned_a = asyncio.run(service.dispatch(
        "session.select",
        {"projectId": "p1", "sessionId": SESSION_A},
    ))
    a_third = asyncio.run(service.dispatch("session.turn", {"text": "A third"}))

    for suffix, method, result in (
        (221, "session.select", selected_a),
        (222, "session.set_thinking", thinking),
        (223, "session.set_mode", plan),
        (224, "session.turn", a_second),
        (225, "session.select", selected_b),
        (226, "session.turn", b_second),
        (227, "session.select", returned_a),
        (228, "session.turn", a_third),
    ):
        _assert_result(method, result, suffix)

    assert selected_b["turnCount"] == 1
    assert selected_b["thinkingMode"] == "normal"
    assert selected_b["planMode"] is False
    assert returned_a["turnCount"] == 2
    assert returned_a["thinkingMode"] == "extended"
    assert returned_a["planMode"] is True
    assert a_third["text"].startswith(f"answer:{SESSION_A[:4]}:")
    assert b_second["text"].startswith(f"answer:{SESSION_B[:4]}:")
    final_a = factory.sessions[-1]
    assert final_a.session_id == SESSION_A
    assert final_a.contexts[-1] == [
        f"{SESSION_A[:4]} question 1",
        "A second",
    ]
    assert all("B second" not in turn.user_input for turn in persisted[SESSION_A])
    assert [turn.turn_id for turn in persisted[SESSION_B]] == [1, 2]
    assert a_third["registrationStatus"] == "registered"


def test_control_snapshots_are_not_evicted_at_the_old_128_session_boundary(
    tmp_path,
):
    service, _catalog, factory, _persisted = _seed_coordinator(tmp_path)
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
    service, catalog, factory, _persisted = _seed_coordinator(
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
    answer = asyncio.run(service.dispatch("session.turn", {"text": "record once"}))
    _assert_result("session.turn", answer, 232)
    assert answer["registrationStatus"] == "pending"
    assert answer["text"] == f"answer:{SESSION_D[:4]}:record once"
    assert durable_path.read_bytes() == durable_before
    assert catalog.project_for_session(SESSION_D) is None

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


def test_flush_failure_retains_current_conversation_and_recent_turns(tmp_path):
    service, _catalog, _factory, _persisted = _seed_coordinator(tmp_path)
    selected = asyncio.run(service.dispatch(
        "session.select",
        {"projectId": "p1", "sessionId": SESSION_A},
    ))
    answer = asyncio.run(service.dispatch("session.turn", {"text": "still here"}))
    _assert_result("session.select", selected, 241)
    _assert_result("session.turn", answer, 242)
    current = service.session
    assert isinstance(current, _CoordinatorSession)
    current.fail_flush = True
    before = [(turn.turn_id, turn.user_input) for turn in current.recent_turns]

    with pytest.raises(DesktopServiceError) as raised:
        asyncio.run(service.dispatch(
            "session.select",
            {"projectId": "p1", "sessionId": SESSION_B},
        ))

    assert raised.value.code == "CONVERSATION_FLUSH_FAILED"
    assert raised.value.retryable is True
    assert service.session is current
    assert service.session.session_id == SESSION_A
    assert [(turn.turn_id, turn.user_input) for turn in current.recent_turns] == before


def test_unknown_degraded_unavailable_and_busy_coordinator_states(
    tmp_path,
    monkeypatch,
):
    service, _catalog, _factory, _persisted = _seed_coordinator(tmp_path)
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

    def degraded(_session_id, _include_current):
        raise HistoryRestoreError("private malformed record detail")

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
        lambda _session_id, _include_current: [],
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
        ("session.set_mode", {"mode": "normal"}),
        ("session.set_thinking", {"mode": "normal"}),
    ):
        with pytest.raises(DesktopServiceError) as raised:
            asyncio.run(service.dispatch(method, params))
        assert raised.value.code == "BUSY_TURN"
    service._turn_active = False

    malformed_dir = tmp_path / "malformed-store"
    malformed_dir.mkdir()
    malformed_bytes = b'{"projects":[{"unexpected":true}]}\n'
    (malformed_dir / CATALOG_FILENAME).write_bytes(malformed_bytes)
    malformed_service = DesktopService(
        original_cwd=tmp_path,
        config=AgentConfig(persist_dir=str(malformed_dir)),
        session_factory=_CoordinatorFactory({}, new_ids=(SESSION_D,)),
        environ={},
    )
    unavailable_projects = asyncio.run(malformed_service.dispatch("project.list", {}))
    _assert_result("project.list", unavailable_projects, 254)
    assert unavailable_projects["status"] == "unavailable"
    assert unavailable_projects["projects"] == []
    assert (malformed_dir / CATALOG_FILENAME).read_bytes() == malformed_bytes
