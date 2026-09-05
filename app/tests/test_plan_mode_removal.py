"""Phase 05 contract tests for retiring Product Plan Mode."""

import asyncio

import pytest

from agent.cli.slash_commands import (
    SlashCommandContext,
    SlashCommandError,
    build_default_registry,
    execute_slash_command,
    parse_slash_command,
)
from agent.desktop.protocol import CONTRACT, METHODS
from agent.session import ChatSession


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


def test_protocol_retires_plan_surface_but_keeps_extended_thinking() -> None:
    assert "session.set_mode" not in METHODS
    assert "session.set_thinking" in METHODS
    for method in ("session.create", "session.select"):
        fields = CONTRACT["resultDataSchemas"][method]
        assert "planMode" not in fields
        assert "planLogPath" not in fields
        assert fields["thinkingMode"]["enum"] == ["normal", "extended"]
