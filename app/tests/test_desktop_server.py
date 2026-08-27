"""NDJSON server concurrency and stdout-discipline tests."""

from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path
from typing import Any

import pytest

from agent.desktop.protocol import PROTOCOL_VERSION, ProtocolError, parse_line
from agent.desktop.server import DesktopServer, ProtocolWriter
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
        "data": {"status": "stopped", "flushed": True},
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
                "turnId": "turn-1",
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
                {"text": "請回答"},
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
                "turnId": "turn-1",
                "text": "x" * (2 * 1024 * 1024),
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
        ("session.turn", {"text": "oversized answer"}),
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


class _FlushFailureService:
    lifecycle = "ready"

    async def dispatch(self, method, _params, *, event_sink=None):
        assert method == "runtime.shutdown"
        raise ProtocolError(
            "SHUTDOWN_FLUSH_FAILED",
            "Recent turns could not be flushed.",
            retryable=True,
        )


def test_eof_flush_failure_is_visible_and_returns_nonzero() -> None:
    async def run() -> tuple[int, list[dict[str, Any]]]:
        output = io.StringIO()
        server = DesktopServer(_FlushFailureService(), ProtocolWriter(output))
        exit_code = await server.run(_reader())
        return exit_code, _messages(output)

    exit_code, messages = asyncio.run(run())
    assert exit_code == 1
    failure = messages[-1]
    assert failure["event"] == "backend.shutting_down"
    assert failure["data"]["status"] == "flush_failed"
    assert failure["data"]["code"] == "SHUTDOWN_FLUSH_FAILED"


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
            server.run(_reader(_request(request_id, "session.turn", {"text": "wait"}))),
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
