"""NDJSON server concurrency and stdout-discipline tests."""

from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path
from typing import Any

import pytest

from agent.desktop.protocol import PROTOCOL_VERSION, ProtocolError, parse_line
from agent.desktop.server import DesktopServer, ProtocolWriter, _build_runtime_service
from agent.desktop.service import DesktopService


def _request(request_id: str, method: str, params: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            {
                "protocolVersion": PROTOCOL_VERSION,
                "messageType": "request",
                "requestId": request_id,
                "method": method,
                "params": params,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _reader(*lines: bytes) -> asyncio.StreamReader:
    reader = asyncio.StreamReader()
    for line in lines:
        reader.feed_data(line)
    reader.feed_eof()
    return reader


def _turn_params(text: str, request_id: str) -> dict[str, Any]:
    """Build a protocol-valid logical turn identifier for a fixture request."""
    return {
        "text": text,
        "turnId": request_id.replace("-", ""),
        "retry": False,
    }


def _messages(output: io.StringIO) -> list[dict[str, Any]]:
    lines = output.getvalue().splitlines()
    assert lines
    return [parse_line(line) for line in lines]


def test_malformed_input_does_not_kill_diagnostics_or_shutdown(
    tmp_path: Path,
) -> None:
    async def run() -> list[dict[str, Any]]:
        output = io.StringIO()
        service = DesktopService(
            original_cwd=tmp_path,
            environ={
                "CONDA_DEFAULT_ENV": "app",
                "CONDA_PREFIX": "/conda/envs/app",
            },
        )
        server = DesktopServer(service, ProtocolWriter(output))
        reader = _reader(
            b"{not-json}\n",
            _request(
                "00000000-0000-4000-8000-000000000201",
                "runtime.diagnostics",
                {},
            ),
            _request(
                "00000000-0000-4000-8000-000000000202",
                "runtime.shutdown",
                {},
            ),
        )
        assert await server.run(reader) == 0
        return _messages(output)

    messages = asyncio.run(run())

    assert messages[0]["event"] == "backend.ready"
    assert any(
        message.get("event") == "backend.protocol_error" for message in messages
    )
    diagnostics = next(
        message
        for message in messages
        if message.get("requestId")
        == "00000000-0000-4000-8000-000000000201"
        and message["messageType"] == "result"
    )
    assert diagnostics["ok"] is True
    assert diagnostics["data"]["openRouterConfigured"] is False
    shutdown = next(
        message
        for message in messages
        if message.get("requestId")
        == "00000000-0000-4000-8000-000000000202"
        and message["messageType"] == "result"
    )
    assert shutdown == {
        "protocolVersion": 1,
        "messageType": "result",
        "requestId": "00000000-0000-4000-8000-000000000202",
        "ok": True,
        "data": {"status": "stopped"},
    }
    assert messages[-1]["event"] == "backend.shutting_down"


class _ConcurrentService:
    def __init__(self) -> None:
        self.lifecycle = "ready"
        self.turn_started = asyncio.Event()
        self.release_turn = asyncio.Event()

    async def dispatch(self, method, params, *, event_sink=None):
        if method == "session.turn":
            self.turn_started.set()
            if event_sink is not None:
                event_sink("stage.changed", {"stage": "agent"})
            await self.release_turn.wait()
            return {
                "sessionId": "session-1",
                "turnId": params["turnId"],
                "turnNumber": 1,
                "state": "completed",
                "accepted": True,
                "persisted": True,
                "text": "多行\nUnicode 回答：" + "界" * 20_000,
                "validationErrors": [],
                "toolSummaries": [],
            }
        if method == "session.status":
            assert self.turn_started.is_set()
            self.release_turn.set()
            return {"ready": True}
        if method == "runtime.shutdown":
            self.lifecycle = "stopped"
            return {"status": "stopped"}
        raise AssertionError(method)


def test_reader_accepts_status_while_turn_is_active_and_lines_never_interleave() -> None:
    async def run() -> tuple[str, list[dict[str, Any]]]:
        output = io.StringIO()
        service = _ConcurrentService()
        server = DesktopServer(service, ProtocolWriter(output))
        reader = _reader(
            _request(
                "00000000-0000-4000-8000-000000000203",
                "session.turn",
                _turn_params(
                    "請回答", "00000000-0000-4000-8000-000000000203"
                ),
            ),
            _request(
                "00000000-0000-4000-8000-000000000204",
                "session.status",
                {},
            ),
            _request(
                "00000000-0000-4000-8000-000000000205",
                "runtime.shutdown",
                {},
            ),
        )
        assert await server.run(reader) == 0
        return output.getvalue(), _messages(output)

    raw, messages = asyncio.run(run())

    assert len(raw.splitlines()) == len(messages)
    turn_result = next(
        message
        for message in messages
        if message.get("requestId")
        == "00000000-0000-4000-8000-000000000203"
        and message["messageType"] == "result"
    )
    status_result = next(
        message
        for message in messages
        if message.get("requestId")
        == "00000000-0000-4000-8000-000000000204"
        and message["messageType"] == "result"
    )
    assert messages.index(status_result) < messages.index(turn_result)
    assert turn_result["data"]["text"].startswith("多行\nUnicode")
    assert "界" * 100 in turn_result["data"]["text"]


class _ApprovalRelayService:
    def __init__(self) -> None:
        self.lifecycle = "ready"
        self.staged = asyncio.Event()
        self.released = asyncio.Event()

    async def dispatch(self, method, params, *, event_sink=None):
        if method == "session.turn":
            assert event_sink is not None
            parent_request_id = event_sink.request_id
            turn_id = params["turnId"]
            event_sink("approval.required", {
                "approvalId": "approval-server-1",
                "parentRequestId": parent_request_id,
                "turnId": turn_id,
                "command": "printf fixture",
                "description": "Exercise the bounded relay.",
                "executionTimeoutSeconds": 5,
                "createdAt": "2026-08-28T04:00:00.000Z",
                "expiresAt": "2026-08-28T04:01:00.000Z",
            })
            self.staged.set()
            await self.released.wait()
            return {
                "sessionId": "session-1",
                "turnId": turn_id,
                "state": "completed",
                "accepted": True,
                "persisted": True,
                "text": "approved through relay",
                "validationErrors": [],
                "toolSummaries": [],
            }
        if method == "approval.resolve":
            await self.staged.wait()
            assert params == {
                "approvalId": "approval-server-1",
                "parentRequestId": "00000000-0000-4000-8000-000000000212",
                "turnId": "00000000000040008000000000000212",
                "approved": True,
            }
            self.released.set()
            return {"approvalId": "approval-server-1", "approved": True}
        if method == "runtime.shutdown":
            self.lifecycle = "stopped"
            return {"status": "stopped"}
        raise AssertionError(method)


def test_server_correlates_and_relays_approval_while_parent_turn_is_pending() -> None:
    turn_id = "00000000-0000-4000-8000-000000000212"
    resolve_id = "00000000-0000-4000-8000-000000000213"

    async def run() -> list[dict[str, Any]]:
        output = io.StringIO()
        server = DesktopServer(_ApprovalRelayService(), ProtocolWriter(output))
        reader = _reader(
            _request(turn_id, "session.turn", _turn_params("approve", turn_id)),
            _request(resolve_id, "approval.resolve", {
                "approvalId": "approval-server-1",
                "parentRequestId": turn_id,
                "turnId": "00000000000040008000000000000212",
                "approved": True,
            }),
            _request(
                "00000000-0000-4000-8000-000000000214",
                "runtime.shutdown",
                {},
            ),
        )
        assert await server.run(reader) == 0
        return _messages(output)

    messages = asyncio.run(run())
    approval_event = next(
        message
        for message in messages
        if message.get("event") == "approval.required"
    )
    resolve_result = next(
        message
        for message in messages
        if message.get("requestId") == resolve_id
        and message.get("messageType") == "result"
    )
    turn_result = next(
        message
        for message in messages
        if message.get("requestId") == turn_id
        and message.get("messageType") == "result"
    )
    assert approval_event["requestId"] == turn_id
    assert approval_event["data"]["parentRequestId"] == turn_id
    assert messages.index(approval_event) < messages.index(resolve_result)
    assert messages.index(resolve_result) < messages.index(turn_result)
    assert resolve_result["data"] == {
        "approvalId": "approval-server-1",
        "approved": True,
    }


class _DurableLocalCommandService:
    def __init__(self) -> None:
        self.lifecycle = "ready"
        self.turn_calls = 0

    async def dispatch(self, method, params, *, event_sink=None):
        if method == "session.turn":
            self.turn_calls += 1
            assert params["retry"] is False
            return {
                "sessionId": "session-1",
                "turnId": params["turnId"],
                "turnNumber": 1,
                "state": "completed",
                "accepted": True,
                "persisted": True,
                "text": "Available commands: /help",
                "validationErrors": [],
                "toolSummaries": [],
                "responseKind": "command",
            }
        if method == "runtime.shutdown":
            self.lifecycle = "stopped"
            return {"status": "stopped"}
        raise AssertionError(method)


def test_local_command_result_is_a_durable_completed_turn() -> None:
    request_id = "00000000-0000-4000-8000-000000000215"

    async def run() -> tuple[_DurableLocalCommandService, list[dict[str, Any]]]:
        output = io.StringIO()
        service = _DurableLocalCommandService()
        server = DesktopServer(service, ProtocolWriter(output))
        assert await server.run(
            _reader(
                _request(
                    request_id,
                    "session.turn",
                    _turn_params("/help", request_id),
                )
            )
        ) == 0
        return service, _messages(output)

    service, messages = asyncio.run(run())
    result = next(
        message
        for message in messages
        if message.get("requestId") == request_id
        and message.get("messageType") == "result"
    )
    assert service.turn_calls == 1
    assert result["ok"] is True
    assert result["data"] == {
        "sessionId": "session-1",
        "turnId": "00000000000040008000000000000215",
        "turnNumber": 1,
        "state": "completed",
        "accepted": True,
        "persisted": True,
        "text": "Available commands: /help",
        "validationErrors": [],
        "toolSummaries": [],
        "responseKind": "command",
    }


class _LifecycleFailureService:
    def __init__(self) -> None:
        self.lifecycle = "ready"

    async def dispatch(self, method, params, *, event_sink=None):
        if method == "session.turn":
            raise ProtocolError(
                "PROVIDER_REQUEST_FAILED",
                "Provider request failed.",
                retryable=True,
                details={
                    "turnId": params["turnId"],
                    "state": "failed",
                    "accepted": True,
                    "persisted": True,
                },
            )
        if method == "runtime.shutdown":
            self.lifecycle = "stopped"
            return {"status": "stopped"}
        raise AssertionError(method)


def test_session_turn_failure_preserves_exact_durable_lifecycle_details() -> None:
    request_id = "00000000-0000-4000-8000-000000000216"

    async def run() -> list[dict[str, Any]]:
        output = io.StringIO()
        server = DesktopServer(_LifecycleFailureService(), ProtocolWriter(output))
        assert await server.run(
            _reader(
                _request(
                    request_id,
                    "session.turn",
                    _turn_params("fail", request_id),
                )
            )
        ) == 0
        return _messages(output)

    messages = asyncio.run(run())
    result = next(
        message
        for message in messages
        if message.get("requestId") == request_id
        and message.get("messageType") == "result"
    )
    assert result == {
        "protocolVersion": 1,
        "messageType": "result",
        "requestId": request_id,
        "ok": False,
        "error": {
            "code": "PROVIDER_REQUEST_FAILED",
            "message": "Provider request failed.",
            "retryable": True,
            "details": {
                "turnId": "00000000000040008000000000000216",
                "state": "failed",
                "accepted": True,
                "persisted": True,
            },
        },
    }


def test_duplicate_request_id_reports_process_error_without_second_result(
    tmp_path: Path,
) -> None:
    request_id = "00000000-0000-4000-8000-000000000206"

    async def run() -> list[dict[str, Any]]:
        output = io.StringIO()
        service = DesktopService(original_cwd=tmp_path)
        server = DesktopServer(service, ProtocolWriter(output))
        reader = _reader(
            _request(request_id, "session.status", {}),
            _request(request_id, "session.status", {}),
            _request(
                "00000000-0000-4000-8000-000000000207",
                "runtime.shutdown",
                {},
            ),
        )
        await server.run(reader)
        return _messages(output)

    messages = asyncio.run(run())

    results = [
        message
        for message in messages
        if message.get("requestId") == request_id
        and message["messageType"] == "result"
    ]
    assert len(results) == 1
    assert any(
        message.get("event") == "backend.protocol_error"
        and "Duplicate requestId" in message["data"]["message"]
        for message in messages
    )


class _InvalidResultService:
    def __init__(self) -> None:
        self.lifecycle = "ready"

    async def dispatch(self, method, _params, *, event_sink=None):
        if method == "runtime.diagnostics":
            return {}
        if method == "session.turn":
            return {
                "sessionId": "session-1",
                "turnId": _params["turnId"],
                "state": "completed",
                "accepted": True,
                "persisted": True,
                "text": "shape-invalid result",
                "validationErrors": [],
                "toolSummaries": [],
            }
        if method == "runtime.shutdown":
            self.lifecycle = "stopped"
            return {"status": "stopped"}
        raise AssertionError(method)


@pytest.mark.parametrize(
    ("method", "params"),
    [
        ("runtime.diagnostics", {}),
        (
            "session.turn",
            _turn_params(
                "oversized answer", "00000000-0000-4000-8000-000000000208"
            ),
        ),
    ],
)
def test_invalid_success_payload_becomes_exactly_one_failure_result(
    method: str, params: dict[str, Any]
) -> None:
    request_id = "00000000-0000-4000-8000-000000000208"

    async def run() -> list[dict[str, Any]]:
        output = io.StringIO()
        service = _InvalidResultService()
        server = DesktopServer(service, ProtocolWriter(output))
        assert await server.run(_reader(_request(request_id, method, params))) == 0
        return _messages(output)

    messages = asyncio.run(run())
    results = [
        message
        for message in messages
        if message.get("requestId") == request_id
        and message.get("messageType") == "result"
    ]
    assert len(results) == 1
    assert results[0]["ok"] is False
    assert results[0]["error"]["code"] == "PROTOCOL_INVALID"


class _LargeAnswerService:
    def __init__(self, answer: str) -> None:
        self.lifecycle = "ready"
        self.answer = answer

    async def dispatch(self, method, params, *, event_sink=None):
        if method == "session.turn":
            return {
                "sessionId": "session-1",
                "turnId": params["turnId"],
                "turnNumber": 1,
                "state": "completed",
                "accepted": True,
                "persisted": True,
                "text": self.answer,
                "validationErrors": [],
                "toolSummaries": [],
                "streamKind": "final_only",
                "chunkCount": 0,
            }
        if method == "session.transcript":
            return {
                "projectId": params["projectId"],
                "sessionId": params["sessionId"],
                "status": "ready",
                "issue": None,
                "items": [{
                    "turnId": "00000000000040008000000000000218",
                    "turnNumber": 1,
                    "kind": "conversational",
                    "state": "completed",
                    "timestamp": "2026-09-05T00:00:00Z",
                    "userText": "question",
                    "assistantText": self.answer,
                    "failureCode": None,
                    "failureMessage": None,
                    "failureRetryable": None,
                    "toolActivities": [],
                }],
                "total": 1,
                "offset": params.get("offset", 0),
                "limit": params.get("limit", 20),
                "hasMore": False,
            }
        if method == "runtime.shutdown":
            self.lifecycle = "stopped"
            return {"status": "stopped"}
        raise AssertionError(method)


def test_large_complete_answer_is_written_as_one_final_only_result() -> None:
    request_id = "00000000-0000-4000-8000-000000000218"
    answer = "完整 Unicode 回答🙂\n" + "界" * 750_000

    async def run() -> list[dict[str, Any]]:
        output = io.StringIO()
        server = DesktopServer(_LargeAnswerService(answer), ProtocolWriter(output))
        assert await server.run(
            _reader(
                _request(
                    request_id,
                    "session.turn",
                    _turn_params("large answer", request_id),
                )
            )
        ) == 0
        lines = output.getvalue().splitlines()
        assert lines
        return [json.loads(line) for line in lines]

    messages = asyncio.run(run())
    result = next(
        message
        for message in messages
        if message.get("requestId") == request_id
        and message.get("messageType") == "result"
    )
    assert result["ok"] is True
    assert result["data"]["text"] == answer
    assert result["data"]["streamKind"] == "final_only"
    assert result["data"]["chunkCount"] == 0


def test_large_transcript_answer_is_written_whole() -> None:
    request_id = "00000000-0000-4000-8000-000000000219"
    session_id = "28b222e0cc6543aa8d7bbdc423de99a7"
    answer = 'BEGIN 中文🙂\n"quoted"\\path\n' + "界" * 750_000 + "\nEND"

    async def run() -> list[dict[str, Any]]:
        output = io.StringIO()
        server = DesktopServer(_LargeAnswerService(answer), ProtocolWriter(output))
        assert await server.run(_reader(_request(
            request_id,
            "session.transcript",
            {
                "projectId": "p1",
                "sessionId": session_id,
                "offset": 0,
                "limit": 20,
            },
        ))) == 0
        return [json.loads(line) for line in output.getvalue().splitlines()]

    messages = asyncio.run(run())
    result = next(
        message
        for message in messages
        if message.get("requestId") == request_id
        and message.get("messageType") == "result"
    )
    assert result["ok"] is True
    assert result["data"]["items"][0]["assistantText"] == answer


class _ShutdownFailureService:
    lifecycle = "ready"

    async def dispatch(self, method, _params, *, event_sink=None):
        assert method == "runtime.shutdown"
        raise ProtocolError(
            "SHUTDOWN_FAILED",
            "The desktop backend could not shut down cleanly.",
            retryable=True,
        )


def test_eof_shutdown_failure_is_visible_and_returns_nonzero() -> None:
    async def run() -> tuple[int, list[dict[str, Any]]]:
        output = io.StringIO()
        server = DesktopServer(_ShutdownFailureService(), ProtocolWriter(output))
        exit_code = await server.run(_reader())
        return exit_code, _messages(output)

    exit_code, messages = asyncio.run(run())
    assert exit_code == 1
    failure = messages[-1]
    assert failure["event"] == "backend.shutting_down"
    assert failure["data"]["status"] == "shutdown_failed"
    assert failure["data"]["code"] == "SHUTDOWN_FAILED"


def test_overlong_physical_line_cannot_execute_json_tail(tmp_path: Path) -> None:
    shutdown_id = "00000000-0000-4000-8000-000000000209"

    async def run() -> tuple[int, list[dict[str, Any]]]:
        output = io.StringIO()
        reader = asyncio.StreamReader(limit=64)
        reader.feed_data(b"x" * 65 + _request(shutdown_id, "runtime.shutdown", {}))
        reader.feed_eof()
        service = DesktopService(original_cwd=tmp_path)
        server = DesktopServer(service, ProtocolWriter(output))
        exit_code = await server.run(reader)
        return exit_code, _messages(output)

    exit_code, messages = asyncio.run(run())
    assert exit_code == 2
    assert any(message.get("event") == "backend.protocol_error" for message in messages)
    assert not any(message.get("requestId") == shutdown_id for message in messages)


class _StuckTurnService:
    def __init__(self) -> None:
        self.lifecycle = "ready"
        self.turn_started = asyncio.Event()
        self.cancelled = False

    async def dispatch(self, method, _params, *, event_sink=None):
        if method == "session.turn":
            self.turn_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                self.cancelled = True
        if method == "runtime.shutdown":
            self.lifecycle = "stopped"
            return {"status": "stopped"}
        raise AssertionError(method)


def test_stdin_eof_cancels_stuck_request_after_bounded_grace() -> None:
    request_id = "00000000-0000-4000-8000-000000000210"

    async def run() -> tuple[int, _StuckTurnService, list[dict[str, Any]]]:
        output = io.StringIO()
        service = _StuckTurnService()
        server = DesktopServer(
            service,
            ProtocolWriter(output),
            eof_grace_seconds=0.01,
        )
        exit_code = await asyncio.wait_for(
            server.run(
                _reader(
                    _request(
                        request_id,
                        "session.turn",
                        _turn_params("wait", request_id),
                    )
                )
            ),
            timeout=1,
        )
        return exit_code, service, _messages(output)

    exit_code, service, messages = asyncio.run(run())
    assert exit_code == 1
    assert service.cancelled is True
    assert not any(
        message.get("requestId") == request_id
        and message.get("messageType") == "result"
        for message in messages
    )


class _LateProgressService:
    def __init__(self) -> None:
        self.lifecycle = "ready"
        self.late_error: ProtocolError | None = None
        self.late_task: asyncio.Task[None] | None = None

    async def dispatch(self, method, _params, *, event_sink=None):
        if method == "session.status":
            assert event_sink is not None

            async def emit_late_progress() -> None:
                await asyncio.sleep(0)
                try:
                    event_sink("stage.changed", {"stage": "late"})
                except ProtocolError as exc:
                    self.late_error = exc

            self.late_task = asyncio.create_task(emit_late_progress())
            return {"ready": False, "lifecycle": "ready"}
        if method == "runtime.shutdown":
            self.lifecycle = "stopped"
            return {"status": "stopped"}
        raise AssertionError(method)


def test_late_progress_cannot_follow_terminal_result() -> None:
    request_id = "00000000-0000-4000-8000-000000000211"

    async def run() -> tuple[_LateProgressService, list[dict[str, Any]]]:
        output = io.StringIO()
        service = _LateProgressService()
        server = DesktopServer(service, ProtocolWriter(output))
        assert await server.run(
            _reader(_request(request_id, "session.status", {}))
        ) == 0
        assert service.late_task is not None
        await service.late_task
        return service, _messages(output)

    service, messages = asyncio.run(run())
    result_index = next(
        index
        for index, message in enumerate(messages)
        if message.get("requestId") == request_id
        and message.get("messageType") == "result"
    )
    assert service.late_error is not None
    assert all(
        not (
            index > result_index
            and message.get("requestId") == request_id
            and message.get("messageType") == "event"
        )
        for index, message in enumerate(messages)
    )


def test_runtime_service_uses_production_for_unset_or_nonexact_fixture_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = object()
    calls: list[Path] = []

    def production_service(*, original_cwd: Path):
        calls.append(original_cwd)
        return sentinel

    monkeypatch.setattr("agent.desktop.service.DesktopService", production_service)
    monkeypatch.delenv("RESEARCH_AGENT_DESKTOP_FIXTURE", raising=False)
    assert _build_runtime_service(tmp_path) is sentinel
    monkeypatch.setenv("RESEARCH_AGENT_DESKTOP_FIXTURE", "Phase02")
    assert _build_runtime_service(tmp_path) is sentinel
    assert calls == [tmp_path, tmp_path]


def test_exact_fixture_gate_refuses_startup_without_caller_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agent.desktop.fixture_session import FixtureConfigurationError

    monkeypatch.setenv("RESEARCH_AGENT_DESKTOP_FIXTURE", "phase02")
    monkeypatch.delenv("RESEARCH_AGENT_DESKTOP_FIXTURE_ROOT", raising=False)

    with pytest.raises(FixtureConfigurationError, match="is required"):
        _build_runtime_service(tmp_path)
