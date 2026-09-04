"""Phase 05 contract tests for retiring Product Plan Mode."""

import asyncio
from pathlib import Path

import pytest

from agent.cli.slash_commands import (
    SlashCommandContext,
    SlashCommandError,
    build_default_registry,
    execute_slash_command,
    parse_slash_command,
)
from agent.config import AgentConfig
from agent.desktop.protocol import CONTRACT, METHODS
from agent.session import ChatSession
from agent.turns.plan_log import PlanLog


def test_cli_retires_mode_command_but_keeps_thinking() -> None:
    registry = build_default_registry()

    assert registry.get("mode") is None
    assert registry.get("thinking") is not None
    parsed = parse_slash_command("/mode plan")
    assert parsed is not None
    with pytest.raises(SlashCommandError, match="unknown slash command: /mode"):
        asyncio.run(
            execute_slash_command(
                parsed,
                SlashCommandContext(session=object(), registry=registry),
            )
        )


def test_session_retires_product_plan_api() -> None:
    for name in (
        "plan_mode",
        "plan_log_path",
        "enter_plan_mode",
        "resume_plan_mode",
        "exit_plan_mode",
        "_build_plan_mode_hint",
    ):
        assert not hasattr(ChatSession, name)
    assert hasattr(ChatSession, "set_thinking_mode")


def test_legacy_plan_reader_has_no_writer_surface(tmp_path: Path) -> None:
    reader = PlanLog(
        AgentConfig(plan_logs_dir=str(tmp_path / "legacy-plan-logs")),
        session_id="0123456789ab4def8123456789abcdef",
        app_root_resolver=lambda: Path("/"),
    )

    assert callable(reader.read_direct_answer_turns)
    for name in (
        "new_log_file",
        "resume_log_file",
        "build_tool_activities",
        "render_block",
        "append_block",
    ):
        assert not hasattr(reader, name)


def test_protocol_retires_plan_surface_but_keeps_extended_thinking() -> None:
    assert "session.set_mode" not in METHODS
    assert "session.set_thinking" in METHODS
    for method in ("session.create", "session.select"):
        fields = CONTRACT["resultDataSchemas"][method]
        assert "planMode" not in fields
        assert "planLogPath" not in fields
        assert fields["thinkingMode"]["enum"] == ["normal", "extended"]
