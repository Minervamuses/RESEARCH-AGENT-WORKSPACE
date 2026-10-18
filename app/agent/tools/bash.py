"""LangChain tool factory for executing shell commands with user approval.

Every call prompts the user for y/n approval before executing. Non-interactive
environments (eval harness, pytest, piped stdin) auto-deny so that the tool
cannot hang or silently execute commands without supervision.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from agent.config import AgentConfig
from agent.ingest import current_local_work, run_local_work
from agent.paths import find_app_root
from rag.types import check_cancelled

TOOL_NAME = "bash"
TOOL_DESCRIPTION = (
    "Execute a shell command. Execution is governed by the active runtime permission policy "
    "(prompting for user approval when required); the user reads `description` to decide. Use only "
    "when no narrower tool fits (e.g., listing/finding files when path is "
    "unknown, or quick disk inspection like ls/find/wc). Prefer read_file "
    "or rag_search whenever they apply. Always include a `description` "
    "explaining your intent in one sentence; vague descriptions get denied."
)

MAX_OUTPUT_BYTES = 256_000
DEFAULT_TIMEOUT_SEC = 30
MAX_TIMEOUT_SEC = 300

BashApprovalHandler = Callable[[str, str, int], bool]
BashCommandRunner = Callable[..., Any]


class BashInput(BaseModel):
    """Input schema for the bash tool."""

    command: str = Field(description="The shell command to execute.")
    description: str = Field(
        description=(
            "One-sentence human-readable explanation of why this command "
            "is being run; the user reads this to decide whether to approve."
        )
    )
    timeout_sec: int = Field(
        default=DEFAULT_TIMEOUT_SEC,
        description=(
            f"Seconds to wait before killing the command "
            f"(default {DEFAULT_TIMEOUT_SEC}, max {MAX_TIMEOUT_SEC})."
        ),
    )


def _denied(reason: str, command: str) -> str:
    return json.dumps(
        {"approved": False, "error": reason, "command": command},
        ensure_ascii=False,
    )


def _truncate(text: str) -> str:
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= MAX_OUTPUT_BYTES:
        return text
    head = encoded[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
    return f"{head}\n[truncated, original {len(encoded)} bytes]"


def _render_approval_prompt(command: str, description: str) -> str:
    bar = "─" * 60
    return (
        f"\n{bar}\n"
        f"[bash] Agent wants to run a shell command.\n\n"
        f"  Why: {description or '(no description provided)'}\n"
        f"  Cmd: {command}\n\n"
        f"Approve? [y/N] (Enter = no) "
    )


def _user_approves(command: str, description: str) -> bool:
    """Show approval prompt on stderr, read y/n from stdin.

    Default-deny on empty input or anything other than y/yes (case-insensitive).
    Auto-deny when stdin is not a TTY (e.g., eval harness, CI, piped chat).
    """
    if not sys.stdin.isatty():
        return False
    sys.stderr.write(_render_approval_prompt(command, description))
    sys.stderr.flush()
    try:
        answer = input().strip().lower()
    except EOFError:
        return False
    return answer in {"y", "yes"}


def _group_running(group_id: int) -> bool:
    """Ignore exited zombies while waiting for this Linux process group."""
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        if int(fields[2]) == group_id and fields[0] != "Z":
            return True
    return False


def _stop_process_group(process: subprocess.Popen[str]) -> None:
    """Terminate the command's group and reap its direct shell process."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            break
        deadline = time.monotonic() + 0.5
        while _group_running(process.pid) and time.monotonic() < deadline:
            time.sleep(0.01)
        if not _group_running(process.pid):
            break
    if _group_running(process.pid):
        raise RuntimeError("The stopped bash process group has not exited.")
    process.wait()
    for stream in (process.stdout, process.stderr):
        if stream is not None:
            stream.close()


def _run_controlled_command(command: str, *, timeout: int, capture_output: bool, **kwargs: Any):
    scope = current_local_work()
    check_cancelled()
    process = subprocess.Popen(
        command, start_new_session=True,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
        **kwargs,
    )
    if scope is not None:
        scope.register_bash_process(process)
    deadline = time.monotonic() + timeout
    try:
        while True:
            check_cancelled()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            try:
                stdout, stderr = process.communicate(timeout=min(0.05, remaining))
                check_cancelled()
                return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
            except subprocess.TimeoutExpired:
                continue
    except BaseException:
        _stop_process_group(process)
        raise


def _run_bash(
    command: str,
    description: str,
    timeout_sec: int,
    *,
    approval_handler: BashApprovalHandler | None = None,
    command_runner: BashCommandRunner | None = None,
) -> str:
    check_cancelled()
    capped_timeout = max(1, min(int(timeout_sec), MAX_TIMEOUT_SEC))
    if approval_handler is None:
        if not sys.stdin.isatty():
            return _denied("non-interactive environment; bash auto-denied", command)
        approved = _user_approves(command, description)
    else:
        try:
            approved = bool(
                approval_handler(command, description, capped_timeout)
            )
        except Exception:
            approved = False

    if not approved:
        return _denied(f"user denied execution of: {command}", command)

    check_cancelled()
    cwd = str(find_app_root())
    runner = command_runner or (
        _run_controlled_command if current_local_work() is not None else subprocess.run
    )

    try:
        completed = runner(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=capped_timeout,
            stdin=subprocess.DEVNULL,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        return json.dumps(
            {
                "approved": True,
                "error": f"timeout after {capped_timeout}s",
                "command": command,
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "approved": True,
            "exit_code": completed.returncode,
            "stdout": _truncate(completed.stdout or ""),
            "stderr": _truncate(completed.stderr or ""),
            "command": command,
            "cwd": cwd,
        },
        ensure_ascii=False,
    )


def create_bash_tool(
    config: AgentConfig,
    *,
    approval_handler: BashApprovalHandler | None = None,
    command_runner: BashCommandRunner | None = None,
) -> StructuredTool:
    """Build the bash tool. `config` accepted for factory symmetry."""
    del config

    def _run(command: str, description: str, timeout_sec: int = DEFAULT_TIMEOUT_SEC) -> str:
        return _run_bash(
            command,
            description,
            timeout_sec,
            approval_handler=approval_handler,
            command_runner=command_runner,
        )

    async def _arun(command: str, description: str, timeout_sec: int = DEFAULT_TIMEOUT_SEC) -> str:
        return await run_local_work(_run, command, description, timeout_sec)

    _run.__name__ = TOOL_NAME

    return StructuredTool.from_function(
        func=_run,
        coroutine=_arun,
        name=TOOL_NAME,
        description=TOOL_DESCRIPTION,
        args_schema=BashInput,
        infer_schema=False,
    )
