"""Long-lived stdin/stdout NDJSON server for the local desktop app."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, TextIO

from agent.cli.runtime import CondaRuntimeError, require_conda_runtime
from agent.desktop.protocol import (
    MAX_PROTOCOL_LINE_BYTES,
    ProtocolError,
    bounded_error_message,
    encode_message,
    encode_success_result,
    failure_result,
    parse_line,
    process_event,
    request_event,
    request_id_from_invalid_line,
)
from agent.paths import find_app_root


logger = logging.getLogger(__name__)
_DEFAULT_EOF_GRACE_SECONDS = 5.0


@dataclass
class _WriteItem:
    line: str
    acknowledgment: asyncio.Future[None] | None


class ProtocolWriter:
    """The single bounded serializer and writer for protocol stdout."""

    def __init__(self, stream: TextIO, *, max_queue: int = 1_024) -> None:
        self._stream = stream
        self._queue: asyncio.Queue[_WriteItem | None] = asyncio.Queue(max_queue)
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._consume())

    async def send(self, message: dict[str, Any]) -> None:
        await self.send_line(encode_message(message))

    async def send_line(self, line: str) -> None:
        """Queue one prevalidated line and wait until it is physically flushed."""
        loop = asyncio.get_running_loop()
        acknowledgment: asyncio.Future[None] = loop.create_future()
        await self._queue.put(_WriteItem(line, acknowledgment))
        await acknowledgment

    def send_nowait(self, message: dict[str, Any]) -> None:
        line = encode_message(message)
        try:
            self._queue.put_nowait(_WriteItem(line, None))
        except asyncio.QueueFull as exc:
            raise ProtocolError(
                "INTERNAL_ERROR", "The desktop protocol output queue is full."
            ) from exc

    async def stop(self) -> None:
        if self._task is None:
            return
        await self._queue.put(None)
        await self._task
        self._task = None

    async def _consume(self) -> None:
        while True:
            item = await self._queue.get()
            if item is None:
                self._queue.task_done()
                return
            try:
                await asyncio.to_thread(self._write_line, item.line)
            except Exception as exc:
                if item.acknowledgment is not None and not item.acknowledgment.done():
                    item.acknowledgment.set_exception(exc)
                logger.exception("Protocol stdout write failed")
            else:
                if item.acknowledgment is not None and not item.acknowledgment.done():
                    item.acknowledgment.set_result(None)
            finally:
                self._queue.task_done()

    def _write_line(self, line: str) -> None:
        self._stream.write(line)
        self._stream.flush()


class RequestContext:
    """Per-request event ordering and exactly-one-terminal enforcement."""

    def __init__(
        self,
        request_id: str,
        method: str,
        writer: ProtocolWriter,
    ) -> None:
        self.request_id = request_id
        self.method = method
        self._writer = writer
        self._next_sequence = 1
        self._terminal = False

    async def started(self) -> None:
        await self._writer.send(
            request_event(
                self.request_id,
                self._next_sequence,
                "request.started",
                {"stage": self.method},
            )
        )
        self._next_sequence += 1

    def __call__(self, event: str, data: dict[str, Any]) -> None:
        """Expose a correlated callable sink without widening wire payloads."""
        self.event_nowait(event, data)

    def event_nowait(self, event: str, data: dict[str, Any]) -> None:
        if self._terminal:
            raise ProtocolError(
                "PROTOCOL_INVALID", "Cannot emit an event after a terminal result."
            )
        message = request_event(
            self.request_id,
            self._next_sequence,
            event,
            data,
        )
        self._writer.send_nowait(message)
        self._next_sequence += 1

    async def success(self, data: dict[str, Any]) -> None:
        if self._terminal:
            raise ProtocolError("PROTOCOL_INVALID", "Duplicate terminal result.")
        line = encode_success_result(self.request_id, self.method, data)
        self._terminal = True
        await self._writer.send_line(line)

    async def failure(self, error: ProtocolError) -> None:
        if self._terminal:
            raise ProtocolError("PROTOCOL_INVALID", "Duplicate terminal result.")
        line = encode_message(failure_result(self.request_id, error))
        self._terminal = True
        await self._writer.send_line(line)


class DesktopServer:
    """Read requests continuously while application tasks execute concurrently."""

    def __init__(
        self,
        service: Any,
        writer: ProtocolWriter,
        *,
        eof_grace_seconds: float = _DEFAULT_EOF_GRACE_SECONDS,
    ) -> None:
        self._service = service
        self._writer = writer
        self._seen_request_ids: set[str] = set()
        self._active_tasks: set[asyncio.Task[None]] = set()
        self._stop_event = asyncio.Event()
        self._input_failed = False
        self._stdin_eof = False
        self._eof_grace_seconds = eof_grace_seconds

    async def run(self, reader: asyncio.StreamReader) -> int:
        self._writer.start()
        await self._writer.send(process_event("backend.ready", {"status": "ready"}))
        try:
            await self._read_requests(reader)
            active_tasks_finished = await self._finish_active_tasks()
            cleanup_succeeded = True
            if self._service.lifecycle != "stopped":
                cleanup_succeeded = await self._best_effort_close()
            if not cleanup_succeeded:
                return 1
            if self._input_failed:
                return 2
            return 0 if active_tasks_finished else 1
        finally:
            await self._writer.stop()

    async def _read_requests(self, reader: asyncio.StreamReader) -> None:
        while not self._stop_event.is_set():
            read_task = asyncio.create_task(reader.readline())
            stop_task = asyncio.create_task(self._stop_event.wait())
            done, pending = await asyncio.wait(
                {read_task, stop_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            if stop_task in done and stop_task.result():
                if not read_task.done():
                    read_task.cancel()
                await asyncio.gather(read_task, return_exceptions=True)
                return
            await asyncio.gather(stop_task, return_exceptions=True)
            try:
                raw_line = read_task.result()
            except ValueError:
                await self._protocol_failure(
                    ProtocolError(
                        "PROTOCOL_INVALID",
                        "Protocol line exceeds the 2 MiB limit.",
                    ),
                    None,
                )
                self._input_failed = True
                return
            if not raw_line:
                self._stdin_eof = True
                return
            line = raw_line.removesuffix(b"\n").removesuffix(b"\r")
            await self._accept_line(line)

    async def _finish_active_tasks(self) -> bool:
        tasks = tuple(self._active_tasks)
        if not tasks:
            return True
        if not (self._stdin_eof or self._input_failed):
            await asyncio.gather(*tasks, return_exceptions=True)
            return True
        _done, pending = await asyncio.wait(
            tasks,
            timeout=self._eof_grace_seconds,
        )
        if not pending:
            return True
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        logger.error("Cancelled %d desktop request(s) after stdin closed", len(pending))
        return False

    async def _accept_line(self, line: bytes) -> None:
        try:
            message = parse_line(line)
            if message["messageType"] != "request":
                raise ProtocolError(
                    "PROTOCOL_INVALID", "The desktop backend accepts requests only."
                )
        except ProtocolError as exc:
            await self._protocol_failure(exc, request_id_from_invalid_line(line))
            return

        request_id = message["requestId"]
        if request_id in self._seen_request_ids:
            await self._protocol_failure(
                ProtocolError("PROTOCOL_INVALID", f"Duplicate requestId: {request_id}"),
                None,
            )
            return
        self._seen_request_ids.add(request_id)
        context = RequestContext(request_id, message["method"], self._writer)
        task = asyncio.create_task(
            self._handle_request(context, message["params"])
        )
        self._active_tasks.add(task)
        task.add_done_callback(self._request_finished)

    async def _protocol_failure(
        self,
        error: ProtocolError,
        request_id: str | None,
    ) -> None:
        if request_id is not None and request_id not in self._seen_request_ids:
            self._seen_request_ids.add(request_id)
            await self._writer.send(failure_result(request_id, error))
            return
        await self._writer.send(
            process_event(
                "backend.protocol_error",
                {"code": error.code, "message": bounded_error_message(str(error))},
            )
        )

    async def _handle_request(
        self,
        context: RequestContext,
        params: dict[str, Any],
    ) -> None:
        try:
            await context.started()
            data = await self._service.dispatch(
                context.method,
                params,
                event_sink=context,
            )
            await context.success(data)
        except ProtocolError as exc:
            await context.failure(exc)
            return
        except Exception as exc:
            logger.exception(
                "Unhandled desktop request failure: %s", type(exc).__name__
            )
            await context.failure(
                ProtocolError(
                    "INTERNAL_ERROR",
                    "The desktop backend encountered an internal error.",
                )
            )
            return
        if context.method == "runtime.shutdown":
            await self._writer.send(
                process_event(
                    "backend.shutting_down", {"status": "shutting_down"}
                )
            )
            self._stop_event.set()

    def _request_finished(self, task: asyncio.Task[None]) -> None:
        self._active_tasks.discard(task)
        if task.cancelled():
            return
        exception = task.exception()
        if exception is not None:
            logger.error(
                "Desktop request task ended with %s", type(exception).__name__
            )

    async def _best_effort_close(self) -> bool:
        try:
            await self._service.dispatch("runtime.shutdown", {})
            return True
        except ProtocolError as exc:
            await self._writer.send(
                process_event(
                    "backend.shutting_down",
                    {
                        "status": "shutdown_failed",
                        "code": exc.code,
                        "message": bounded_error_message(str(exc)),
                    },
                )
            )
            logger.error("Desktop EOF shutdown returned %s", exc.code)
            return False
        except Exception as exc:
            logger.error(
                "Desktop EOF cleanup failed with %s", type(exc).__name__
            )
            await self._writer.send(
                process_event(
                    "backend.shutting_down",
                    {
                        "status": "shutdown_failed",
                        "code": "INTERNAL_ERROR",
                        "message": "The desktop backend could not shut down cleanly.",
                    },
                )
            )
            return False


async def open_stdin_reader(
    stream: BinaryIO,
) -> tuple[asyncio.StreamReader, asyncio.ReadTransport]:
    """Attach an asyncio reader to the Linux stdin pipe."""
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader(limit=MAX_PROTOCOL_LINE_BYTES + 2)
    protocol = asyncio.StreamReaderProtocol(reader)
    transport, _ = await loop.connect_read_pipe(lambda: protocol, stream)
    return reader, transport


async def run_backend(
    protocol_stdout: TextIO,
    protocol_stdin: BinaryIO,
    original_cwd: Path,
) -> int:
    """Run one backend process after the runtime and cwd gates pass."""
    reader, transport = await open_stdin_reader(protocol_stdin)
    try:
        service = _build_runtime_service(original_cwd)
        server = DesktopServer(service, ProtocolWriter(protocol_stdout))
        return await server.run(reader)
    finally:
        transport.close()


def _build_runtime_service(original_cwd: Path) -> Any:
    """Select the exact opt-in isolated fixture or normal production service."""
    if os.environ.get("RESEARCH_AGENT_DESKTOP_FIXTURE") == "phase02":
        from agent.desktop.fixture_session import build_phase02_fixture_service

        return build_phase02_fixture_service(
            original_cwd=original_cwd,
            environ=os.environ,
        )
    from agent.desktop.service import DesktopService

    return DesktopService(original_cwd=original_cwd)


def write_bootstrap_error(
    stream: TextIO,
    code: str,
    message: str,
) -> None:
    """Emit one valid process-level error before the asyncio server exists."""
    envelope = process_event(
        "backend.protocol_error",
        {"code": code, "message": message},
    )
    stream.write(encode_message(envelope))
    stream.flush()


def main() -> None:
    """Validate the Linux Conda runtime, pin cwd, and serve NDJSON."""
    protocol_stdout = sys.stdout
    protocol_stdin = sys.stdin.buffer
    sys.stdout = sys.stderr
    original_cwd = Path.cwd().resolve()
    try:
        require_conda_runtime("app")
        if not sys.platform.startswith("linux"):
            raise RuntimeError("The desktop backend requires Linux.")
        os.chdir(find_app_root())
        exit_code = asyncio.run(
            run_backend(protocol_stdout, protocol_stdin, original_cwd)
        )
    except CondaRuntimeError as exc:
        write_bootstrap_error(
            protocol_stdout,
            "RUNTIME_WRONG_CONDA_ENV",
            str(exc),
        )
        exit_code = 2
    except Exception as exc:
        logger.exception("Desktop backend bootstrap failed")
        write_bootstrap_error(
            protocol_stdout,
            "INTERNAL_ERROR",
            "The desktop backend could not start.",
        )
        exit_code = 1
    finally:
        sys.stdout = protocol_stdout
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
