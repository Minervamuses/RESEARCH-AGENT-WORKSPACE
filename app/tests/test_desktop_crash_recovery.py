"""Real Python-process crash contracts for the Phase 07 desktop fixture.

These tests cover the Python backend's NDJSON surface, canonical JSON, and
fixture-owned side-effect ledger.  They deliberately do not claim to exercise
the React reducer, Rust supervisor, native Tauri shell, or the required manual
acceptance journey.  Low-level tempfile/fsync/replace exception injection also
belongs in the repository unit tests rather than substituting for these kills.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Callable

import pytest

from agent.config import AgentConfig
from agent.conversations import ConversationRepository
from agent.desktop.fixture_session import FIXTURE_ROOT_PREFIX, SESSION_A
from agent.desktop.protocol import PROTOCOL_VERSION, parse_line
from agent.skills.citation.session_policy import CitationSessionPolicy


APP_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = APP_ROOT.parent
PROJECT_ID = "p1"
CHECKPOINT_ENV = "RESEARCH_AGENT_DESKTOP_FIXTURE_CRASH_CHECKPOINT"
CHECKPOINT_TURN_ENV = "RESEARCH_AGENT_DESKTOP_FIXTURE_CRASH_TURN_ID"
SIDE_EFFECT_ENV = "RESEARCH_AGENT_DESKTOP_FIXTURE_SIDE_EFFECT_SENTINEL"
CHECKPOINT_PATH = ".fixture-crash-checkpoint.json"
CHECKPOINT_READY_PATH = ".fixture-crash-checkpoint.ready"
SIDE_EFFECT_PATH = ".fixture-side-effects.jsonl"
UNSAFE_CITATION_TOKEN = "fixture-crash-forged"
TIMEOUT_SECONDS = 5.0
STARTUP_TIMEOUT_SECONDS = 15.0
_EOF = object()


def _turn_id(number: int) -> str:
    return f"00000000000040008000{number:012x}"


def _turn_params(text: str, turn_id: str, *, retry: bool = False) -> dict[str, Any]:
    return {"text": text, "turnId": turn_id, "retry": retry}


@pytest.fixture
def crash_root():
    root = Path(tempfile.mkdtemp(prefix=FIXTURE_ROOT_PREFIX, dir="/tmp"))
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)
        assert not root.exists()


class BackendProcess:
    """Bounded NDJSON driver around one direct Python backend child."""

    def __init__(
        self,
        root: Path,
        *,
        checkpoint: str | None = None,
        checkpoint_turn_id: str | None = None,
    ) -> None:
        child_env = dict(os.environ)
        child_env.update({
            "CONDA_DEFAULT_ENV": "app",
            "CONDA_PREFIX": str(Path(sys.executable).resolve().parent.parent),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": os.pathsep.join(
                value
                for value in (str(APP_ROOT), child_env.get("PYTHONPATH", ""))
                if value
            ),
            "RESEARCH_AGENT_DESKTOP_FIXTURE": "phase02",
            "RESEARCH_AGENT_DESKTOP_FIXTURE_ROOT": str(root),
            SIDE_EFFECT_ENV: "1",
        })
        child_env.pop(CHECKPOINT_ENV, None)
        child_env.pop(CHECKPOINT_TURN_ENV, None)
        if checkpoint is not None:
            assert checkpoint_turn_id is not None
            child_env[CHECKPOINT_ENV] = checkpoint
            child_env[CHECKPOINT_TURN_ENV] = checkpoint_turn_id

        self.root = root
        self.process = subprocess.Popen(
            [sys.executable, "-m", "agent.desktop.server"],
            cwd=REPOSITORY_ROOT,
            env=child_env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        assert self.process.stderr is not None
        self._stdout_queue: queue.Queue[object] = queue.Queue()
        self._stderr_lines: deque[bytes] = deque(maxlen=100)
        self.messages: list[dict[str, Any]] = []
        self._stdout_thread = threading.Thread(
            target=self._read_stdout,
            name="desktop-fixture-stdout",
            daemon=True,
        )
        self._stderr_thread = threading.Thread(
            target=self._read_stderr,
            name="desktop-fixture-stderr",
            daemon=True,
        )
        self._stdout_thread.start()
        self._stderr_thread.start()
        try:
            ready = self.read_until(
                lambda message: message.get("event") == "backend.ready",
                timeout=STARTUP_TIMEOUT_SECONDS,
            )
            assert ready == {
                "protocolVersion": PROTOCOL_VERSION,
                "messageType": "event",
                "event": "backend.ready",
                "data": {"status": "ready"},
            }
        except BaseException:
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait(timeout=2)
            for stream in (
                self.process.stdin,
                self.process.stdout,
                self.process.stderr,
            ):
                if stream is not None:
                    stream.close()
            self._stdout_thread.join(timeout=1)
            self._stderr_thread.join(timeout=1)
            raise

    def _read_stdout(self) -> None:
        assert self.process.stdout is not None
        try:
            while raw_line := self.process.stdout.readline():
                line = raw_line.removesuffix(b"\n").removesuffix(b"\r")
                self._stdout_queue.put(parse_line(line))
        except BaseException as exc:
            self._stdout_queue.put(exc)
        finally:
            self._stdout_queue.put(_EOF)

    def _read_stderr(self) -> None:
        assert self.process.stderr is not None
        while raw_line := self.process.stderr.readline():
            self._stderr_lines.append(raw_line)

    def stderr_text(self) -> str:
        return b"".join(self._stderr_lines).decode("utf-8", errors="replace")[-8_192:]

    def read_until(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        *,
        timeout: float = TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError(
                    "timed out waiting for backend message; stderr="
                    + self.stderr_text()
                )
            try:
                item = self._stdout_queue.get(timeout=remaining)
            except queue.Empty as exc:
                raise AssertionError(
                    "timed out waiting for backend message; stderr="
                    + self.stderr_text()
                ) from exc
            if item is _EOF:
                raise AssertionError(
                    f"backend stdout closed with return code {self.process.poll()}; "
                    f"stderr={self.stderr_text()}"
                )
            if isinstance(item, BaseException):
                raise AssertionError("backend emitted invalid NDJSON") from item
            assert isinstance(item, dict)
            self.messages.append(item)
            if predicate(item):
                return item

    def send(self, method: str, params: dict[str, Any]) -> str:
        request_id = str(uuid.uuid4())
        payload = {
            "protocolVersion": PROTOCOL_VERSION,
            "messageType": "request",
            "requestId": request_id,
            "method": method,
            "params": params,
        }
        line = (
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        assert self.process.stdin is not None
        self.process.stdin.write(line)
        self.process.stdin.flush()
        return request_id

    def request(
        self,
        method: str,
        params: dict[str, Any],
        *,
        timeout: float = TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        request_id = self.send(method, params)
        result = self.read_until(
            lambda message: (
                message.get("messageType") == "result"
                and message.get("requestId") == request_id
            ),
            timeout=timeout,
        )
        assert result.get("ok") is True, result
        data = result.get("data")
        assert isinstance(data, dict)
        return data

    def select_fixture_session(self) -> None:
        selected = self.request(
            "session.select",
            {"projectId": PROJECT_ID, "sessionId": SESSION_A},
        )
        assert selected["sessionId"] == SESSION_A

    def transcript(self) -> dict[str, Any]:
        return self.request(
            "session.transcript",
            {
                "projectId": PROJECT_ID,
                "sessionId": SESSION_A,
                "offset": 0,
                "limit": 20,
            },
        )

    def wait_for_checkpoint(
        self,
        checkpoint: str,
        turn_id: str,
        request_id: str,
        *,
        timeout: float = TIMEOUT_SECONDS,
    ) -> None:
        marker = self.root / CHECKPOINT_PATH
        ready = self.root / CHECKPOINT_READY_PATH
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if ready.is_file():
                try:
                    raw = json.loads(marker.read_text(encoding="utf-8"))
                except (FileNotFoundError, json.JSONDecodeError):
                    continue
                assert raw == {"checkpoint": checkpoint, "turnId": turn_id}
                return
            try:
                item = self._stdout_queue.get(timeout=0.05)
            except queue.Empty:
                if self.process.poll() is not None:
                    break
                continue
            if item is _EOF:
                break
            if isinstance(item, BaseException):
                raise AssertionError("backend emitted invalid NDJSON") from item
            assert isinstance(item, dict)
            self.messages.append(item)
            if (
                item.get("messageType") == "result"
                and item.get("requestId") == request_id
            ):
                raise AssertionError(
                    f"checkpoint {checkpoint!r} was not reached before terminal result"
                )
        raise AssertionError(
            f"checkpoint {checkpoint!r} was not reached; "
            f"returncode={self.process.poll()}; stderr={self.stderr_text()}"
        )

    def kill_at_checkpoint(
        self,
        checkpoint: str,
        turn_id: str,
        request_id: str,
    ) -> None:
        self.wait_for_checkpoint(checkpoint, turn_id, request_id)
        self.process.kill()
        assert self.process.wait(timeout=2) == -signal.SIGKILL
        self._stdout_thread.join(timeout=1)
        assert not self._stdout_thread.is_alive()
        while True:
            try:
                item = self._stdout_queue.get_nowait()
            except queue.Empty:
                break
            if item is _EOF:
                continue
            if isinstance(item, BaseException):
                raise AssertionError("backend emitted invalid NDJSON") from item
            assert isinstance(item, dict)
            self.messages.append(item)
        assert not any(
            message.get("messageType") == "result"
            and message.get("requestId") == request_id
            for message in self.messages
        )

    def close(self) -> None:
        if self.process.poll() is None:
            try:
                self.request("runtime.shutdown", {}, timeout=2)
                self.process.wait(timeout=2)
            except BaseException:
                self.process.kill()
                self.process.wait(timeout=2)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            if stream is not None:
                stream.close()
        self._stdout_thread.join(timeout=1)
        self._stderr_thread.join(timeout=1)


def _start(
    root: Path,
    *,
    checkpoint: str | None = None,
    turn_id: str | None = None,
) -> BackendProcess:
    return BackendProcess(
        root,
        checkpoint=checkpoint,
        checkpoint_turn_id=turn_id,
    )


def _effects(root: Path) -> list[dict[str, str]]:
    path = root / SIDE_EFFECT_PATH
    if not path.exists():
        return []
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert all(set(row) == {"effect", "turnId"} for row in rows)
    return rows


def _effect(effect: str, turn_id: str) -> dict[str, str]:
    return {"effect": effect, "turnId": turn_id}


def _turn(root: Path, turn_id: str):
    snapshot = ConversationRepository(root / "store").load(SESSION_A)
    return next(item for item in snapshot.document.turns if item.turn_id == turn_id)


def _transcript_turn(transcript: dict[str, Any], turn_id: str) -> dict[str, Any]:
    return next(item for item in transcript["items"] if item["turnId"] == turn_id)


def test_kill_before_prompt_temp_keeps_draft_unaccepted_and_resendable(
    crash_root: Path,
) -> None:
    checkpoint = "before_prompt_temp"
    turn_id = _turn_id(70_001)
    draft = "draft survives before prompt publication"
    first = _start(crash_root, checkpoint=checkpoint, turn_id=turn_id)
    try:
        first.select_fixture_session()
        repository = ConversationRepository(crash_root / "store")
        before = repository.path_for(SESSION_A).read_bytes()
        request_id = first.send("session.turn", _turn_params(draft, turn_id))
        first.kill_at_checkpoint(checkpoint, turn_id, request_id)
        assert repository.path_for(SESSION_A).read_bytes() == before
        assert _effects(crash_root) == []
    finally:
        first.close()

    restarted = _start(crash_root)
    try:
        restarted.select_fixture_session()
        assert all(
            item["turnId"] != turn_id for item in restarted.transcript()["items"]
        )
        result = restarted.request(
            "session.turn",
            _turn_params(draft, turn_id, retry=False),
        )
        assert result["turnId"] == turn_id
        assert result["state"] == "completed"
        assert result["accepted"] is True and result["persisted"] is True
        assert _effects(crash_root) == [_effect("provider", turn_id)]
    finally:
        restarted.close()


def test_kill_after_pending_publish_recovers_interrupted_without_auto_replay(
    crash_root: Path,
) -> None:
    checkpoint = "after_pending_publish"
    turn_id = _turn_id(70_002)
    text = "pending is durable before provider"
    first = _start(crash_root, checkpoint=checkpoint, turn_id=turn_id)
    try:
        first.select_fixture_session()
        request_id = first.send("session.turn", _turn_params(text, turn_id))
        first.kill_at_checkpoint(checkpoint, turn_id, request_id)
        pending = _turn(crash_root, turn_id)
        assert pending.state == "pending" and pending.assistant_output is None
        assert _effects(crash_root) == []
    finally:
        first.close()

    restarted = _start(crash_root)
    try:
        restarted.select_fixture_session()
        interrupted = _transcript_turn(restarted.transcript(), turn_id)
        assert interrupted["state"] == "interrupted"
        assert interrupted["assistantText"] is None
        assert interrupted["failureRetryable"] is True
        assert _effects(crash_root) == []
        retried = restarted.request(
            "session.turn",
            _turn_params(text, turn_id, retry=True),
        )
        assert retried["state"] == "completed"
        assert retried["turnId"] == turn_id
        assert _effects(crash_root) == [_effect("provider", turn_id)]
    finally:
        restarted.close()


def test_kill_during_tool_preserves_uncertain_side_effect_without_replay(
    crash_root: Path,
) -> None:
    checkpoint = "during_tool_after_side_effect"
    turn_id = _turn_id(70_003)
    text = "[[fixture:crash-tool-after-side-effect]]"
    first = _start(crash_root, checkpoint=checkpoint, turn_id=turn_id)
    try:
        first.select_fixture_session()
        request_id = first.send("session.turn", _turn_params(text, turn_id))
        first.kill_at_checkpoint(checkpoint, turn_id, request_id)
        assert _turn(crash_root, turn_id).state == "pending"
        expected = [_effect("provider", turn_id), _effect("tool", turn_id)]
        assert _effects(crash_root) == expected
    finally:
        first.close()

    restarted = _start(crash_root)
    try:
        restarted.select_fixture_session()
        interrupted = _transcript_turn(restarted.transcript(), turn_id)
        assert interrupted["state"] == "interrupted"
        assert interrupted["assistantText"] is None
        assert interrupted["toolActivities"] == []
        assert _effects(crash_root) == expected
        restarted.request("project.list", {})
        restarted.transcript()
        assert _effects(crash_root) == expected
    finally:
        restarted.close()


def test_kill_after_citation_rejection_never_persists_unsafe_completed_text(
    crash_root: Path,
) -> None:
    checkpoint = "after_citation_rejection"
    turn_id = _turn_id(70_004)
    text = "[[fixture:crash-citation-rejection]]"
    unsafe_draft = (
        "Fixture citation draft "
        f"[[cite:{UNSAFE_CITATION_TOKEN}]]"
    )
    expected_safe, violations = CitationSessionPolicy(
        AgentConfig(
            persist_dir=str(crash_root / "store"),
            citation_output_dir=str(crash_root / "citations"),
        )
    ).finalize_answer(
        unsafe_draft,
        user_input=text,
        citation_active=True,
    )
    assert violations
    first = _start(crash_root, checkpoint=checkpoint, turn_id=turn_id)
    try:
        first.select_fixture_session()
        request_id = first.send("session.turn", _turn_params(text, turn_id))
        first.kill_at_checkpoint(checkpoint, turn_id, request_id)
        pending = _turn(crash_root, turn_id)
        assert pending.state == "pending" and pending.assistant_output is None
        assert unsafe_draft not in (
            ConversationRepository(crash_root / "store")
            .path_for(SESSION_A)
            .read_text(encoding="utf-8")
        )
        assert _effects(crash_root) == [
            _effect("provider", turn_id),
            _effect("citation_rejected", turn_id),
        ]
    finally:
        first.close()

    restarted = _start(crash_root)
    try:
        restarted.select_fixture_session()
        interrupted = _transcript_turn(restarted.transcript(), turn_id)
        assert interrupted["state"] == "interrupted"
        assert interrupted["assistantText"] is None
        assert _effects(crash_root) == [
            _effect("provider", turn_id),
            _effect("citation_rejected", turn_id),
        ]
        safe = restarted.request(
            "session.turn",
            _turn_params(text, turn_id, retry=True),
        )
        assert safe["state"] == "completed"
        assert safe["text"] == expected_safe
        assert unsafe_draft not in safe["text"]
        assert unsafe_draft not in (
            ConversationRepository(crash_root / "store")
            .path_for(SESSION_A)
            .read_text(encoding="utf-8")
        )
        assert _effects(crash_root) == [
            _effect("provider", turn_id),
            _effect("citation_rejected", turn_id),
            _effect("provider", turn_id),
            _effect("citation_rejected", turn_id),
        ]
    finally:
        restarted.close()


def test_kill_after_completed_temp_fsync_leaves_pending_authority(
    crash_root: Path,
) -> None:
    checkpoint = "after_completed_temp_fsync"
    turn_id = _turn_id(70_005)
    text = "completed temp is not the canonical authority"
    first = _start(crash_root, checkpoint=checkpoint, turn_id=turn_id)
    try:
        first.select_fixture_session()
        request_id = first.send("session.turn", _turn_params(text, turn_id))
        first.kill_at_checkpoint(checkpoint, turn_id, request_id)
        pending = _turn(crash_root, turn_id)
        assert pending.state == "pending" and pending.assistant_output is None
        repository = ConversationRepository(crash_root / "store")
        assert list(repository.root.glob(f".{SESSION_A}.*.tmp"))
        assert _effects(crash_root) == [_effect("provider", turn_id)]
    finally:
        first.close()

    restarted = _start(crash_root)
    try:
        restarted.select_fixture_session()
        interrupted = _transcript_turn(restarted.transcript(), turn_id)
        assert interrupted["state"] == "interrupted"
        assert interrupted["assistantText"] is None
        assert _effects(crash_root) == [_effect("provider", turn_id)]
    finally:
        restarted.close()


def test_kill_after_completed_commit_replays_saved_result_without_side_effect(
    crash_root: Path,
) -> None:
    checkpoint = "after_completed_commit"
    turn_id = _turn_id(70_006)
    text = "completed commit survives missing response delivery"
    first = _start(crash_root, checkpoint=checkpoint, turn_id=turn_id)
    try:
        first.select_fixture_session()
        request_id = first.send("session.turn", _turn_params(text, turn_id))
        first.kill_at_checkpoint(checkpoint, turn_id, request_id)
        completed = _turn(crash_root, turn_id)
        assert completed.state == "completed"
        assert completed.assistant_output
        saved_answer = completed.assistant_output
        assert _effects(crash_root) == [_effect("provider", turn_id)]
    finally:
        first.close()

    restarted = _start(crash_root)
    try:
        restarted.select_fixture_session()
        restored = _transcript_turn(restarted.transcript(), turn_id)
        assert restored["state"] == "completed"
        assert restored["assistantText"] == saved_answer
        replayed = restarted.request(
            "session.turn",
            _turn_params(text, turn_id, retry=False),
        )
        assert replayed["turnId"] == turn_id
        assert replayed["state"] == "completed"
        assert replayed["text"] == saved_answer
        assert _effects(crash_root) == [_effect("provider", turn_id)]
        assert sum(
            item["turnId"] == turn_id
            for item in restarted.transcript()["items"]
        ) == 1
    finally:
        restarted.close()
