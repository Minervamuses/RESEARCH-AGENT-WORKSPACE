"""Tests for the user-approval-gated bash tool."""

import json
import subprocess

import pytest
from langchain_core.tools import StructuredTool

from agent.config import AgentConfig
from agent.tools.bash import (
    BashInput,
    MAX_OUTPUT_BYTES,
    TOOL_NAME,
    create_bash_tool,
)


def _force_tty(monkeypatch, value: bool = True) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: value)


def _patch_input(monkeypatch, response: str) -> list[str]:
    """Patch builtins.input; record nothing about the prompt itself."""
    captured: list[str] = []

    def fake_input(prompt: str = "") -> str:
        captured.append(prompt)
        return response

    monkeypatch.setattr("builtins.input", fake_input)
    return captured


def test_bash_factory_returns_structured_tool():
    tool = create_bash_tool(AgentConfig(persist_dir="/tmp"))
    assert isinstance(tool, StructuredTool)
    assert tool.name == TOOL_NAME
    assert tool.args_schema is BashInput
    schema = tool.args_schema.model_json_schema()
    assert "command" in schema["properties"]
    assert "description" in schema["properties"]
    assert "timeout_sec" in schema["properties"]


def test_bash_runs_when_user_approves(monkeypatch):
    _force_tty(monkeypatch, True)
    _patch_input(monkeypatch, "y")
    tool = create_bash_tool(AgentConfig(persist_dir="/tmp"))

    raw = tool.invoke(
        {"command": "echo hello", "description": "smoke test", "timeout_sec": 5}
    )
    payload = json.loads(raw)

    assert payload["approved"] is True
    assert payload["exit_code"] == 0
    assert payload["stdout"] == "hello\n"
    assert payload["stderr"] == ""


def test_bash_rejects_when_user_denies(monkeypatch):
    _force_tty(monkeypatch, True)
    _patch_input(monkeypatch, "n")

    spy: dict[str, int] = {"calls": 0}

    def spy_run(*args, **kwargs):
        spy["calls"] += 1
        raise AssertionError("subprocess.run must not be called when denied")

    monkeypatch.setattr("agent.tools.bash.subprocess.run", spy_run)

    tool = create_bash_tool(AgentConfig(persist_dir="/tmp"))
    raw = tool.invoke(
        {"command": "rm -rf /", "description": "obviously dangerous"}
    )
    payload = json.loads(raw)

    assert payload["approved"] is False
    assert "user denied" in payload["error"]
    assert spy["calls"] == 0


def test_bash_approval_prompt_on_stderr_includes_command_and_description(
    monkeypatch,
    capsys,
):
    _force_tty(monkeypatch, True)
    _patch_input(monkeypatch, "n")
    calls: list[tuple] = []

    def fail_run(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("subprocess.run must not be called when denied")

    monkeypatch.setattr("agent.tools.bash.subprocess.run", fail_run)
    tool = create_bash_tool(AgentConfig(persist_dir="/tmp"))

    raw = tool.invoke(
        {
            "command": "printf sensitive-command",
            "description": "inspect the requested target",
        }
    )

    assert json.loads(raw)["approved"] is False
    assert calls == []
    prompt = capsys.readouterr().err
    assert "printf sensitive-command" in prompt
    assert "inspect the requested target" in prompt


def test_bash_default_deny_on_empty_input(monkeypatch):
    _force_tty(monkeypatch, True)
    _patch_input(monkeypatch, "")

    def fail_run(*args, **kwargs):
        raise AssertionError("subprocess.run must not be called when default-denied")

    monkeypatch.setattr("agent.tools.bash.subprocess.run", fail_run)

    tool = create_bash_tool(AgentConfig(persist_dir="/tmp"))
    raw = tool.invoke({"command": "echo nope", "description": "should be denied"})
    payload = json.loads(raw)

    assert payload["approved"] is False


def test_bash_auto_deny_when_stdin_not_tty(monkeypatch):
    _force_tty(monkeypatch, False)

    def fail_input(*args, **kwargs):
        raise AssertionError("input() must not be called in non-interactive env")

    def fail_run(*args, **kwargs):
        raise AssertionError("subprocess.run must not be called in non-interactive env")

    monkeypatch.setattr("builtins.input", fail_input)
    monkeypatch.setattr("agent.tools.bash.subprocess.run", fail_run)

    tool = create_bash_tool(AgentConfig(persist_dir="/tmp"))
    raw = tool.invoke({"command": "echo nope", "description": "in eval / ci"})
    payload = json.loads(raw)

    assert payload["approved"] is False
    assert "non-interactive" in payload["error"]


def test_bash_timeout_enforced(monkeypatch):
    _force_tty(monkeypatch, True)
    _patch_input(monkeypatch, "y")

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout", 1))

    monkeypatch.setattr("agent.tools.bash.subprocess.run", fake_run)

    tool = create_bash_tool(AgentConfig(persist_dir="/tmp"))
    raw = tool.invoke(
        {"command": "sleep 60", "description": "would hang", "timeout_sec": 1}
    )
    payload = json.loads(raw)

    assert payload["approved"] is True
    assert "timeout" in payload["error"]


@pytest.mark.parametrize(
    ("requested_timeout", "expected_timeout"),
    [(17, 17), (0, 1), (301, 300)],
)
def test_bash_passes_clamped_timeout_to_subprocess(
    monkeypatch,
    requested_timeout,
    expected_timeout,
):
    _force_tty(monkeypatch, True)
    _patch_input(monkeypatch, "y")
    calls: list[tuple[tuple, dict]] = []

    class _Done:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return _Done()

    monkeypatch.setattr("agent.tools.bash.subprocess.run", fake_run)
    tool = create_bash_tool(AgentConfig(persist_dir="/tmp"))

    raw = tool.invoke(
        {
            "command": "echo bounded",
            "description": "verify timeout forwarding",
            "timeout_sec": requested_timeout,
        }
    )

    assert json.loads(raw)["approved"] is True
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == ("echo bounded",)
    assert kwargs["timeout"] == expected_timeout


def test_bash_output_truncated_when_oversize(monkeypatch):
    _force_tty(monkeypatch, True)
    _patch_input(monkeypatch, "y")

    huge = "x" * (MAX_OUTPUT_BYTES + 5_000)

    class _Done:
        returncode = 0
        stdout = huge
        stderr = ""

    monkeypatch.setattr("agent.tools.bash.subprocess.run", lambda *a, **kw: _Done())

    tool = create_bash_tool(AgentConfig(persist_dir="/tmp"))
    raw = tool.invoke({"command": "yes | head -c 300000", "description": "size test"})
    payload = json.loads(raw)

    assert payload["approved"] is True
    assert "[truncated, original" in payload["stdout"]
    assert len(payload["stdout"].encode("utf-8")) < len(huge.encode("utf-8"))


def test_bash_captures_nonzero_exit(monkeypatch):
    _force_tty(monkeypatch, True)
    _patch_input(monkeypatch, "y")

    tool = create_bash_tool(AgentConfig(persist_dir="/tmp"))
    raw = tool.invoke(
        {"command": "false", "description": "expect non-zero exit"}
    )
    payload = json.loads(raw)

    assert payload["approved"] is True
    assert payload["exit_code"] != 0
    # `false` produces empty output but must not raise.
    assert payload["stdout"] == ""


def test_injected_approval_and_runner_preserve_the_python_execution_path(
    monkeypatch,
):
    _force_tty(monkeypatch, False)
    approvals: list[tuple[str, str, int]] = []
    runs: list[tuple[tuple, dict]] = []

    class _Done:
        returncode = 0
        stdout = "fixture output\n"
        stderr = ""

    def approve(command: str, description: str, timeout_sec: int) -> bool:
        approvals.append((command, description, timeout_sec))
        return True

    def runner(*args, **kwargs):
        runs.append((args, kwargs))
        return _Done()

    tool = create_bash_tool(
        AgentConfig(persist_dir="/tmp"),
        approval_handler=approve,
        command_runner=runner,
    )
    payload = json.loads(tool.invoke({
        "command": "printf fixture",
        "description": "Return deterministic fixture output.",
        "timeout_sec": 17,
    }))

    assert approvals == [(
        "printf fixture",
        "Return deterministic fixture output.",
        17,
    )]
    assert len(runs) == 1
    assert runs[0][0] == ("printf fixture",)
    assert runs[0][1]["timeout"] == 17
    assert payload["approved"] is True
    assert payload["stdout"] == "fixture output\n"


def test_injected_denial_or_failure_never_calls_runner(monkeypatch):
    _force_tty(monkeypatch, False)
    calls = 0

    def runner(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("denied injected request must not run")

    for approval_handler in (
        lambda *_args: False,
        lambda *_args: (_ for _ in ()).throw(RuntimeError("approval unavailable")),
    ):
        tool = create_bash_tool(
            AgentConfig(persist_dir="/tmp"),
            approval_handler=approval_handler,
            command_runner=runner,
        )
        payload = json.loads(tool.invoke({
            "command": "printf denied",
            "description": "Exercise fail-closed approval.",
        }))
        assert payload["approved"] is False

    assert calls == 0
