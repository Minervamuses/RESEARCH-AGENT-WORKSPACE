"""Focused application-service tests for the Python desktop bridge."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from agent.config import AgentConfig
from agent.cli.slash_commands import (
    SlashCommand,
    SlashCommandRegistry,
    SlashCommandResult,
)
from agent.desktop.protocol import success_result
from agent.desktop.service import DesktopService, DesktopServiceError
from agent.extensions.manager import ApplyItemResult, ApplyReport, ExtensionStatus
from agent.skills import SkillMetadata
from agent.turns.results import TurnOutcome
from rag.types import Hit


@dataclass
class _Runtime:
    name: str
    task_mode: str | None = None


class _FakeSession:
    def __init__(self, config: AgentConfig, progress_cb=None) -> None:
        self.config = config
        self.progress_cb = progress_cb
        self.session_id = "session-safe-1"
        self.plan_mode = False
        self.plan_log_path: Path | None = None
        self.thinking_mode = "normal"
        self.active_skill_runtime: _Runtime | None = None
        self.loaded_skills = [
            SkillMetadata("research", "Research local material.", Path(__file__))
        ]
        self.mcp_families = {"web": "web_search"}
        self.running_extension_revision = 3
        self.extension_startup_diagnostics = ("MCP loader unavailable: TimeoutError",)
        self.recent_turns: list[object] = []
        self.turn_started = asyncio.Event()
        self.turn_release = asyncio.Event()
        self.block_turn = False
        self.flush_calls = 0
        self.leave_turns_after_flush = False
        self.block_flush = False
        self.flush_started = asyncio.Event()
        self.flush_release = asyncio.Event()
        self.turn_inputs: list[str] = []

    async def turn_outcome(self, text: str) -> TurnOutcome:
        self.turn_inputs.append(text)
        self.turn_started.set()
        if self.block_turn:
            await self.turn_release.wait()
        if self.progress_cb is not None:
            self.progress_cb(
                "tools",
                [
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "rag_search",
                                "args": {"query": "private query"},
                                "id": "call-safe-1",
                                "type": "tool_call",
                            }
                        ],
                    ),
                    ToolMessage(
                        content="private tool result",
                        tool_call_id="call-safe-1",
                        name="rag_search",
                        status="success",
                    ),
                ],
            )
        return TurnOutcome(text=f"完成：{text}", validation_errors=[])

    async def enter_plan_mode(self) -> Path:
        self.plan_mode = True
        self.plan_log_path = Path("/tmp/計劃 log.md")
        return self.plan_log_path

    async def exit_plan_mode(self) -> None:
        self.plan_mode = False
        self.plan_log_path = None

    def set_thinking_mode(self, mode: str) -> None:
        self.thinking_mode = mode

    def activate_skill(self, name: str, task_mode: str | None = None) -> _Runtime:
        self.active_skill_runtime = _Runtime(name, task_mode)
        return self.active_skill_runtime

    def deactivate_skill(self) -> None:
        self.active_skill_runtime = None

    def status_snapshot(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "turn_count": 0,
            "recent_turn_count": len(self.recent_turns),
            "graph_recursion_limit": self.config.graph_recursion_limit,
            "last_tool_counts": "none",
            "plan_mode": self.plan_mode,
            "plan_log_path": str(self.plan_log_path or ""),
            "thinking_mode": self.thinking_mode,
            "mcp_families": "web_search",
            "active_skill": (
                self.active_skill_runtime.name
                if self.active_skill_runtime is not None
                else ""
            ),
            "task_mode": (
                self.active_skill_runtime.task_mode
                if self.active_skill_runtime is not None
                else ""
            ),
        }

    async def flush_recent_turns(self) -> None:
        self.flush_calls += 1
        self.flush_started.set()
        if self.block_flush:
            await self.flush_release.wait()
        if not self.leave_turns_after_flush:
            self.recent_turns.clear()


class _SessionFactory:
    def __init__(self) -> None:
        self.calls: list[tuple[AgentConfig, bool]] = []
        self.fail_once = False
        self.created: _FakeSession | None = None

    async def __call__(self, config: AgentConfig, *, load_mcp: bool, progress_cb):
        self.calls.append((config, load_mcp))
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("OPENROUTER_API_KEY is not set")
        self.created = _FakeSession(config, progress_cb)
        return self.created


class _FakeExtensionManager:
    def __init__(self, tmp_path: Path) -> None:
        binding_hash = "a" * 64
        candidate = SimpleNamespace(
            binding_hash=binding_hash,
            descriptor=SimpleNamespace(id="local-search", family="local_search"),
            env={"PRIVATE_TOKEN": "must not cross wire"},
        )
        desired_skill = SimpleNamespace(id="writer", kind="skill")
        self.preview_object = SimpleNamespace(
            private_skill_hash="private-manager-hash",
            diff=SimpleNamespace(
                changes=[
                    SimpleNamespace(
                        operation="add",
                        key="skill:writer",
                        desired=desired_skill,
                    )
                ]
            ),
            plan=SimpleNamespace(
                items=[
                    SimpleNamespace(
                        key="skill:writer",
                        summary="secret-from-untrusted-extension-metadata",
                    )
                ]
            ),
            mcp_candidates={"mcp:local-search": candidate},
        )
        self.status_object = ExtensionStatus(
            dropin_root=tmp_path / "dropin",
            state_root=tmp_path / "state",
            desired_count=1,
            applied_count=0,
            applied_revision=0,
            running_revision=0,
            restart_required=False,
            manager_available=True,
            manager_error=None,
            diagnostics=(),
        )
        self.applied_preview = None

    def status(self, **_kwargs):
        return self.status_object

    def preview(self):
        return self.preview_object

    def apply(self, preview, *, approved_mcp_bindings):
        self.applied_preview = preview
        assert approved_mcp_bindings == {"a" * 64}
        return ApplyReport(
            previous_revision=0,
            applied_revision=1,
            restart_required=True,
            items=(
                ApplyItemResult(
                    "skill:writer",
                    "added",
                    "secret-from-untrusted-extension-metadata",
                ),
            ),
            diagnostics=("secret-from-untrusted-extension-metadata",),
        )


def _service(tmp_path: Path, **kwargs) -> DesktopService:
    config = kwargs.pop(
        "config",
        AgentConfig(
            persist_dir=str(tmp_path / "store"),
            citation_output_dir=str(tmp_path / "cite"),
            extension_dropin_dir=str(tmp_path / "dropin"),
            extension_state_dir=str(tmp_path / "state"),
            plan_logs_dir=str(tmp_path / "plans"),
        ),
    )
    return DesktopService(
        original_cwd=tmp_path,
        environ={
            "CONDA_DEFAULT_ENV": "app",
            "CONDA_PREFIX": "/conda/envs/app",
        },
        config=config,
        **kwargs,
    )


def test_diagnostics_stays_available_without_provider_keys(tmp_path: Path) -> None:
    service = _service(tmp_path)

    diagnostics = asyncio.run(service.dispatch("runtime.diagnostics", {}))

    assert diagnostics["backendState"] == "ready"
    assert diagnostics["openRouterConfigured"] is False
    assert diagnostics["openAlexConfigured"] is False
    assert diagnostics["ollamaReachable"] is None
    assert diagnostics["originalWorkingDirectory"] == str(tmp_path)
    success_result(
        "00000000-0000-4000-8000-000000000101",
        "runtime.diagnostics",
        diagnostics,
    )


def test_session_create_failure_keeps_backend_retryable(tmp_path: Path) -> None:
    factory = _SessionFactory()
    factory.fail_once = True
    service = _service(tmp_path, session_factory=factory)

    with pytest.raises(DesktopServiceError) as raised:
        asyncio.run(
            service.dispatch(
                "session.create",
                {"loadMcp": False, "graphRecursionLimit": 72},
            )
        )

    assert raised.value.code == "OPENROUTER_NOT_CONFIGURED"
    assert service.session is None
    snapshot = asyncio.run(
        service.dispatch(
            "session.create",
            {"loadMcp": False, "graphRecursionLimit": 72},
        )
    )
    assert factory.calls[-1][0].graph_recursion_limit == 72
    assert factory.calls[-1][1] is False
    assert snapshot["loadedSkills"] == ["research"]
    success_result(
        "00000000-0000-4000-8000-000000000102",
        "session.create",
        snapshot,
    )


def test_session_create_is_single_flight_and_blocks_shutdown(tmp_path: Path) -> None:
    async def run() -> None:
        create_started = asyncio.Event()
        create_release = asyncio.Event()
        calls = 0

        async def factory(config, *, load_mcp, progress_cb):
            nonlocal calls
            calls += 1
            create_started.set()
            await create_release.wait()
            session = _FakeSession(config, progress_cb)
            session.session_id = f"session-{calls}"
            return session

        service = _service(tmp_path, session_factory=factory)
        first = asyncio.create_task(
            service.dispatch("session.create", {"loadMcp": False})
        )
        await create_started.wait()

        with pytest.raises(DesktopServiceError) as second:
            await service.dispatch("session.create", {"loadMcp": False})
        with pytest.raises(DesktopServiceError) as shutdown:
            await service.dispatch("runtime.shutdown", {})

        assert second.value.code == "SESSION_NOT_READY"
        assert shutdown.value.code == "SESSION_NOT_READY"
        assert service.lifecycle == "ready"
        assert calls == 1
        create_release.set()
        snapshot = await first
        assert snapshot["sessionId"] == "session-1"
        assert service.session is not None

    asyncio.run(run())


def test_composer_keeps_normal_text_and_runs_status_without_model(
    tmp_path: Path,
) -> None:
    factory = _SessionFactory()
    service = _service(tmp_path, session_factory=factory)
    asyncio.run(service.dispatch("session.create", {"loadMcp": False}))
    session = factory.created
    assert session is not None

    raw_text = "  keep this spacing exactly  "
    answer = asyncio.run(service.dispatch("session.turn", {"text": raw_text}))
    assert session.turn_inputs == [raw_text]
    assert answer["responseKind"] == "answer"

    status = asyncio.run(service.dispatch("session.turn", {"text": "/status"}))
    assert session.turn_inputs == [raw_text]
    assert status["responseKind"] == "command"
    assert status["streamKind"] == "final_only"
    assert status["chunkCount"] == 0
    assert "Session status:" in status["text"]


@pytest.mark.parametrize("text", ["/", "/unknown", "/init"])
def test_composer_rejects_invalid_or_disallowed_commands_before_model(
    tmp_path: Path,
    text: str,
) -> None:
    factory = _SessionFactory()
    service = _service(tmp_path, session_factory=factory)
    asyncio.run(service.dispatch("session.create", {"loadMcp": False}))
    session = factory.created
    assert session is not None

    with pytest.raises(DesktopServiceError) as raised:
        asyncio.run(service.dispatch("session.turn", {"text": text}))

    assert raised.value.code == "PROTOCOL_INVALID"
    assert session.turn_inputs == []


def test_composer_rejects_aliases_and_unsupported_typed_results(
    tmp_path: Path,
) -> None:
    handler_calls = 0

    async def handler(_context, _parsed):
        nonlocal handler_calls
        handler_calls += 1
        return SlashCommandResult(message="local", should_exit=True)

    registry = SlashCommandRegistry(
        [
            SlashCommand(
                name="status",
                aliases=("s",),
                description="test status",
                handler=handler,
            )
        ]
    )
    factory = _SessionFactory()
    service = _service(
        tmp_path,
        session_factory=factory,
        slash_registry=registry,
    )
    asyncio.run(service.dispatch("session.create", {"loadMcp": False}))

    with pytest.raises(DesktopServiceError) as alias_error:
        asyncio.run(service.dispatch("session.turn", {"text": "/s"}))
    assert alias_error.value.code == "PROTOCOL_INVALID"
    assert handler_calls == 0

    with pytest.raises(DesktopServiceError) as result_error:
        asyncio.run(service.dispatch("session.turn", {"text": "/status"}))
    assert result_error.value.code == "PROTOCOL_INVALID"
    assert handler_calls == 1
    assert factory.created is not None
    assert factory.created.turn_inputs == []


def test_composer_bounds_local_command_output_and_safe_errors(
    tmp_path: Path,
) -> None:
    async def large_handler(_context, _parsed):
        return SlashCommandResult(message="🙂" * 20_000)

    registry = SlashCommandRegistry(
        [
            SlashCommand(
                name="status",
                description="large status",
                handler=large_handler,
            )
        ]
    )
    factory = _SessionFactory()
    service = _service(
        tmp_path,
        session_factory=factory,
        slash_registry=registry,
    )
    asyncio.run(service.dispatch("session.create", {"loadMcp": False}))

    result = asyncio.run(service.dispatch("session.turn", {"text": "/status"}))

    assert len(result["text"].encode("utf-8")) == 65_536
    assert result["registrationStatus"] == "not_required"


def test_turn_is_fail_fast_busy_and_emits_only_safe_tool_data(tmp_path: Path) -> None:
    async def run() -> None:
        factory = _SessionFactory()
        service = _service(tmp_path, session_factory=factory)
        await service.dispatch("session.create", {"loadMcp": False})
        session = factory.created
        assert session is not None
        session.block_turn = True
        events: list[tuple[str, dict]] = []
        first = asyncio.create_task(
            service.dispatch(
                "session.turn",
                {"text": "第一題"},
                event_sink=lambda event, data: events.append((event, data)),
            )
        )
        await session.turn_started.wait()

        with pytest.raises(DesktopServiceError) as second:
            await service.dispatch("session.turn", {"text": "第二題"})
        with pytest.raises(DesktopServiceError) as mutation:
            await service.dispatch("session.set_mode", {"mode": "plan"})

        assert second.value.code == "BUSY_TURN"
        assert mutation.value.code == "BUSY_TURN"
        session.turn_release.set()
        result = await first
        assert result["text"] == "完成：第一題"
        assert result["toolSummaries"] == [
            {"name": "rag_search", "status": "ok", "callId": "call-safe-1"}
        ]
        rendered = repr(events) + repr(result)
        assert "private query" not in rendered
        assert "private tool result" not in rendered

    asyncio.run(run())


def test_shutdown_detects_swallowed_flush_failure_and_allows_retry(
    tmp_path: Path,
) -> None:
    factory = _SessionFactory()
    service = _service(tmp_path, session_factory=factory)
    asyncio.run(service.dispatch("session.create", {}))
    session = factory.created
    assert session is not None
    session.recent_turns.append(object())
    session.leave_turns_after_flush = True

    with pytest.raises(DesktopServiceError) as raised:
        asyncio.run(service.dispatch("session.shutdown", {}))

    assert raised.value.code == "SHUTDOWN_FLUSH_FAILED"
    assert raised.value.details == {"remainingTurns": 1}
    assert service.session is session
    session.leave_turns_after_flush = False
    result = asyncio.run(service.dispatch("session.shutdown", {}))
    assert result == {"status": "stopped", "flushed": True}
    assert session.flush_calls == 2
    assert service.session is None


def test_concurrent_runtime_shutdown_cannot_reopen_backend(tmp_path: Path) -> None:
    async def run() -> None:
        factory = _SessionFactory()
        service = _service(tmp_path, session_factory=factory)
        await service.dispatch("session.create", {})
        session = factory.created
        assert session is not None
        session.block_flush = True
        first = asyncio.create_task(service.dispatch("runtime.shutdown", {}))
        await session.flush_started.wait()

        with pytest.raises(DesktopServiceError) as second:
            await service.dispatch("runtime.shutdown", {})
        with pytest.raises(DesktopServiceError) as late_work:
            await service.dispatch("session.turn", {"text": "too late"})

        assert second.value.code == "SESSION_NOT_READY"
        assert late_work.value.code == "SESSION_NOT_READY"
        assert service.lifecycle == "shutting_down"
        session.flush_release.set()
        assert await first == {"status": "stopped", "flushed": True}
        assert service.lifecycle == "stopped"
        assert await service.dispatch("runtime.shutdown", {}) == {
            "status": "stopped",
            "flushed": True,
        }

    asyncio.run(run())


def test_session_shutdown_blocks_new_work_while_flushing(tmp_path: Path) -> None:
    async def run() -> None:
        factory = _SessionFactory()
        service = _service(tmp_path, session_factory=factory)
        await service.dispatch("session.create", {})
        session = factory.created
        assert session is not None
        session.block_flush = True
        shutdown = asyncio.create_task(service.dispatch("session.shutdown", {}))
        await session.flush_started.wait()

        with pytest.raises(DesktopServiceError) as turn:
            await service.dispatch("session.turn", {"text": "too late"})
        with pytest.raises(DesktopServiceError) as extension:
            await service.dispatch("extensions.status", {})

        assert turn.value.code == "SESSION_NOT_READY"
        assert extension.value.code == "SESSION_NOT_READY"
        session.flush_release.set()
        assert await shutdown == {"status": "stopped", "flushed": True}

    asyncio.run(run())


def test_knowledge_pagination_drops_raw_metadata(monkeypatch, tmp_path: Path) -> None:
    import agent.desktop.service as service_module

    hits = [
        Hit(
            pid="研究-1",
            chunk_id=index,
            text=f"內容 {index}",
            file_path="docs/研究.md",
            tags=["研究"],
            metadata={"rawProviderPayload": "must remain in Python"},
        )
        for index in range(3)
    ]
    monkeypatch.setattr(service_module, "list_chunks", lambda **_kwargs: hits)
    service = _service(tmp_path)

    result = asyncio.run(
        service.dispatch("knowledge.list_chunks", {"offset": 1, "limit": 1})
    )

    assert result["total"] == 3
    assert result["hasMore"] is True
    assert result["items"][0]["chunkId"] == 1
    assert "metadata" not in result["items"][0]
    assert "rawProviderPayload" not in repr(result)


@pytest.mark.parametrize("raw", ["relative/path", r"C:\\Users\\research", ""])
def test_desktop_path_guard_rejects_non_linux_paths(
    tmp_path: Path, raw: str
) -> None:
    service = _service(tmp_path)

    with pytest.raises(DesktopServiceError) as raised:
        asyncio.run(service.dispatch("knowledge.ingest_file", {"path": raw}))

    assert raised.value.code == "INVALID_PATH"


def test_single_file_ingest_rejects_unsupported_and_extension_state(
    monkeypatch, tmp_path: Path
) -> None:
    import agent.desktop.service as service_module

    called = False

    async def fake_ingest(_target, _config):
        nonlocal called
        called = True
        return "pid", 1

    monkeypatch.setattr(service_module, "ingest_file", fake_ingest)
    unsupported = tmp_path / ".env"
    unsupported.write_text("PRIVATE=value", encoding="utf-8")
    dropin = tmp_path / "dropin"
    dropin.mkdir()
    private_extension = dropin / "private.md"
    private_extension.write_text("private extension instructions", encoding="utf-8")
    service = _service(tmp_path)

    for target in (unsupported, private_extension):
        with pytest.raises(DesktopServiceError) as raised:
            asyncio.run(
                service.dispatch("knowledge.ingest_file", {"path": str(target)})
            )
        assert raised.value.code == "INVALID_PATH"
    assert called is False


def test_desktop_path_guard_rejects_symlinked_parent(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    target = real / "research.md"
    target.write_text("research", encoding="utf-8")
    linked = tmp_path / "linked"
    linked.symlink_to(real, target_is_directory=True)
    service = _service(tmp_path)

    with pytest.raises(DesktopServiceError) as raised:
        asyncio.run(
            service.dispatch(
                "knowledge.ingest_file", {"path": str(linked / target.name)}
            )
        )

    assert raised.value.code == "INVALID_PATH"


def test_single_file_ingest_rejects_zero_chunks_and_maps_ollama_failures(
    monkeypatch, tmp_path: Path
) -> None:
    import agent.desktop.service as service_module

    target = tmp_path / "research.md"
    target.write_text("research content", encoding="utf-8")
    service = _service(tmp_path)

    async def no_chunks(_target, _config):
        return "research", 0

    monkeypatch.setattr(service_module, "ingest_file", no_chunks)
    with pytest.raises(DesktopServiceError) as empty:
        asyncio.run(
            service.dispatch("knowledge.ingest_file", {"path": str(target)})
        )
    assert empty.value.code == "RAG_WRITE_FAILED"

    async def missing_model(_target, _config):
        raise RuntimeError("embedding model not found; pull it first")

    monkeypatch.setattr(service_module, "ingest_file", missing_model)
    with pytest.raises(DesktopServiceError) as ollama:
        asyncio.run(
            service.dispatch("knowledge.ingest_file", {"path": str(target)})
        )
    assert ollama.value.code == "OLLAMA_MODEL_MISSING"
    assert ollama.value.details == {"partialWritePossible": True}

    async def provider_response_error(_target, _config):
        raise RuntimeError("ollama.ResponseError: prompt too long (status code: 400)")

    monkeypatch.setattr(service_module, "ingest_file", provider_response_error)
    with pytest.raises(DesktopServiceError) as response_error:
        asyncio.run(
            service.dispatch("knowledge.ingest_file", {"path": str(target)})
        )
    assert response_error.value.code == "RAG_WRITE_FAILED"


def test_folder_ingest_waits_for_structured_progress_step(tmp_path: Path) -> None:
    folder = tmp_path / "documents"
    folder.mkdir()
    service = _service(tmp_path)

    with pytest.raises(DesktopServiceError) as raised:
        asyncio.run(
            service.dispatch("knowledge.ingest_folder", {"path": str(folder)})
        )

    assert raised.value.code == "RAG_WRITE_FAILED"
    assert "structured progress" in str(raised.value)


def test_extension_preview_is_opaque_and_apply_cannot_replay(tmp_path: Path) -> None:
    manager = _FakeExtensionManager(tmp_path)
    service = _service(tmp_path, extension_manager=manager)

    preview = asyncio.run(service.dispatch("extensions.preview", {}))

    assert preview["proposedSkills"] == ["writer"]
    assert preview["bindings"] == [
        {
            "name": "local-search",
            "server": "local_search",
            "bindingHash": "a" * 64,
            "requiresApproval": True,
        }
    ]
    assert "private-manager-hash" not in repr(preview)
    assert "PRIVATE_TOKEN" not in repr(preview)
    assert "secret-from-untrusted-extension-metadata" not in repr(preview)
    success_result(
        "00000000-0000-4000-8000-000000000103",
        "extensions.preview",
        preview,
    )

    applied = asyncio.run(
        service.dispatch(
            "extensions.apply",
            {
                "previewId": preview["previewId"],
                "approvedBindingHashes": ["a" * 64],
            },
        )
    )
    assert manager.applied_preview is manager.preview_object
    assert applied["appliedRevision"] == 1
    assert "secret-from-untrusted-extension-metadata" not in repr(applied)
    with pytest.raises(DesktopServiceError) as replay:
        asyncio.run(
            service.dispatch(
                "extensions.apply",
                {
                    "previewId": preview["previewId"],
                    "approvedBindingHashes": ["a" * 64],
                },
            )
        )
    assert replay.value.code == "EXTENSION_APPLY_FAILED"
