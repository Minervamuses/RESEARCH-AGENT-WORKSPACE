"""Knowledge-base ingest service: the agent-side wrapper around rag.

The CLI layer (slash commands) only parses arguments and renders messages;
every rag call goes through here so cli/ never imports rag directly.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import subprocess
import threading
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, TypeVar

from rag import ingest_repo, ingest_single, list_diff, prune_orphans
from rag.types import WorkCallbacks, work_callbacks

from agent.config import AgentConfig
from agent.paths import find_app_root


_T = TypeVar("_T")
_local_scope: ContextVar["LocalWorkScope | None"] = ContextVar("agent_local_work", default=None)


class LocalWorkScope:
    """Own cancellation of the current turn's existing threads and provider awaits."""

    def __init__(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._loop_thread = threading.get_ident()
        self._stopped = threading.Event()
        self._bash_processes: list[subprocess.Popen[str]] = []
        self._bash_cleanup: asyncio.Task[None] | None = None

    @contextmanager
    def bind(self):
        """Bind this turn in each owning task without sharing ContextVar tokens."""
        callbacks_token = work_callbacks.set(WorkCallbacks(
            self.check_cancelled, self.request_stop, self.run_async,
        ))
        scope_token = _local_scope.set(self)
        try:
            yield self
        finally:
            _local_scope.reset(scope_token)
            work_callbacks.reset(callbacks_token)

    def register_bash_process(self, process: subprocess.Popen[str]) -> None:
        self._bash_processes.append(process)

    async def finish_stop(self) -> None:
        """Settle retained bash groups after the turn's tool workers have returned."""
        if not self._stopped.is_set() or not self._bash_processes:
            return
        if self._bash_cleanup is None:
            from agent.tools.bash import _stop_process_group

            def finish() -> None:
                for process in self._bash_processes:
                    _stop_process_group(process)

            self._bash_cleanup = asyncio.create_task(asyncio.to_thread(finish))
        while not self._bash_cleanup.done():
            try:
                await asyncio.shield(self._bash_cleanup)
            except asyncio.CancelledError:
                continue
        self._bash_cleanup.result()

    def request_stop(self) -> None:
        self._stopped.set()

    def check_cancelled(self) -> None:
        if self._stopped.is_set():
            raise asyncio.CancelledError()

    def run_async(self, call: Callable[[], Awaitable[_T]]) -> _T:
        """Bridge only a synchronous worker's provider request to its owning loop."""
        self.check_cancelled()
        if threading.get_ident() == self._loop_thread:
            raise RuntimeError("A synchronous provider wait must run in a worker thread.")
        started = threading.Event()
        finished = threading.Event()

        async def request() -> _T:
            started.set()
            try:
                self.check_cancelled()
                result = await call()
                self.check_cancelled()
                return result
            finally:
                finished.set()

        future = asyncio.run_coroutine_threadsafe(request(), self._loop)
        while True:
            try:
                result = future.result(timeout=0.05)
                self.check_cancelled()
                return result
            except concurrent.futures.TimeoutError:
                if future.done():
                    return future.result()
                # Do not cancel before the coroutine can enter its cleanup block.
                if self._stopped.is_set() and started.is_set():
                    future.cancel()
                    finished.wait()
                    self.check_cancelled()
            except concurrent.futures.CancelledError:
                if started.is_set():
                    finished.wait()
                raise asyncio.CancelledError() from None


def current_local_work() -> LocalWorkScope | None:
    """Return the current turn's scope for its actual bash process ownership."""
    return _local_scope.get()


async def await_sync_work(call: Callable[..., _T], *args: Any, **kwargs: Any) -> _T:
    """Drain short sync work before propagating cancellation; never reject a save."""
    worker = asyncio.create_task(asyncio.to_thread(call, *args, **kwargs))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError:
        callbacks = work_callbacks.get()
        if callbacks is not None:
            callbacks.request_stop()
        while not worker.done():
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if not worker.cancelled():
            worker.exception()
        raise


async def run_local_work(call: Callable[..., _T], *args: Any, **kwargs: Any) -> _T:
    """Check the turn before effects and await the actual worker after Stop."""
    callbacks = work_callbacks.get()
    if callbacks is None:
        return await asyncio.to_thread(call, *args, **kwargs)

    def run() -> _T:
        callbacks.check_cancelled()
        result = call(*args, **kwargs)
        callbacks.check_cancelled()
        return result

    return await await_sync_work(run)


async def init_workspace(config: AgentConfig) -> tuple[int, int, Path, set[str]]:
    """Ingest the host workspace root, skipping the app project.

    Returns (files, chunks, host_root, excluded_names).
    """
    app_root = find_app_root()
    host_root = app_root.parent
    skip = {app_root.name}
    files, chunks = await run_local_work(
        ingest_repo,
        str(host_root),
        config=config,
        skip_rel_paths=skip,
    )
    return files, chunks, host_root, skip


async def ingest_file(target: Path, config: AgentConfig) -> tuple[str, int]:
    """Ingest one file; returns (pid, chunk count)."""
    return await run_local_work(ingest_single, str(target), config=config)


async def ingest_folder(target: Path, config: AgentConfig) -> tuple[int, int]:
    """Ingest a directory tree; returns (files, chunks)."""
    return await run_local_work(ingest_repo, str(target), config=config)


async def diff_folder(target: Path, config: AgentConfig) -> dict:
    """Diff the store against a directory tree."""
    return await run_local_work(list_diff, str(target), config)


async def prune_folder(target: Path, config: AgentConfig) -> list[str]:
    """Remove store entries whose files no longer exist under target."""
    return await run_local_work(prune_orphans, str(target), config)
