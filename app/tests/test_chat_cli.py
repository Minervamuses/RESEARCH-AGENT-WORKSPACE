"""Tests for the interactive chat CLI wrapper."""

import argparse
import asyncio

import pytest

from conftest import FakeChatSession


def _run_cli(monkeypatch, session, inputs):
    """Drive chat._run with a fake session and scripted line inputs."""
    from agent.cli import chat

    async def fake_create(*args, **kwargs):
        return session

    input_iter = iter(inputs)

    async def fake_read_line(_prompt: str) -> str:
        return next(input_iter)

    monkeypatch.setattr(chat.ChatSession, "create", fake_create)

    args = argparse.Namespace(max_turns=32, no_mcp=True)
    asyncio.run(chat._run(args, read_line=fake_read_line))


def test_chat_cli_flushes_recent_turns_on_quit(monkeypatch):
    session = FakeChatSession()

    _run_cli(monkeypatch, session, ["hello", "q"])

    assert session.calls == ["turn:hello", "flush"]


@pytest.mark.parametrize(
    "quit_input",
    [
        "q​",
        "q﻿",
        "ｑ",
    ],
)
def test_chat_cli_normalizes_quit_inputs(monkeypatch, quit_input):
    session = FakeChatSession(record_repr=True)

    _run_cli(monkeypatch, session, [quit_input])

    assert session.calls == ["flush"]


def test_chat_cli_blank_input_does_not_exit(monkeypatch):
    session = FakeChatSession(record_repr=True)

    _run_cli(monkeypatch, session, ["", "   ", "​", "﻿", "q"])

    assert session.calls == ["flush"]


def test_chat_cli_does_not_normalize_regular_messages(monkeypatch):
    session = FakeChatSession(record_repr=True)

    _run_cli(monkeypatch, session, ["hello​", "q"])

    assert session.calls == ["turn:'hello\\u200b'", "flush"]


def test_chat_cli_flushes_recent_turns_on_turn_error(monkeypatch):
    session = FakeChatSession(turn_error=RuntimeError("boom"))

    _run_cli(monkeypatch, session, ["hello", "q"])

    assert session.calls == ["turn:hello", "flush"]


def test_chat_cli_never_prints_a_silent_blank_response(monkeypatch, capsys):
    session = FakeChatSession(turn_result="   ")

    _run_cli(monkeypatch, session, ["請回答", "q"])

    output = capsys.readouterr().out
    assert "未能產生可顯示" in output
    assert session.calls == ["turn:請回答", "flush"]


def test_chat_cli_slash_help_stays_local(monkeypatch, capsys):
    session = FakeChatSession(status={
        "session_id": "session-1",
        "turn_count": 0,
        "recent_turn_count": 0,
        "recursion_limit": 32,
        "last_tool_counts": "none",
    })

    _run_cli(monkeypatch, session, ["/help", "q"])

    output = capsys.readouterr().out
    assert "Available slash commands:" in output
    assert "/help" in output
    assert session.calls == ["flush"]


def test_chat_cli_slash_status_reports_session(monkeypatch, capsys):
    session = FakeChatSession(status={
        "session_id": "session-42",
        "turn_count": 3,
        "recent_turn_count": 2,
        "recursion_limit": 32,
        "last_tool_counts": "rag_search x1",
        "thinking_mode": "extended",
    })

    _run_cli(monkeypatch, session, ["/status", "q"])

    output = capsys.readouterr().out
    assert "Session status:" in output
    assert "session_id: session-42" in output
    assert "last_tool_calls: rag_search x1" in output
    assert "thinking_mode: extended" in output
    assert session.calls == ["flush"]


def test_chat_cli_slash_quit_exits_without_agent_turn(monkeypatch):
    session = FakeChatSession(status={
        "session_id": "session-1",
        "turn_count": 0,
        "recent_turn_count": 0,
        "recursion_limit": 32,
        "last_tool_counts": "none",
    })

    _run_cli(monkeypatch, session, ["/quit"])

    assert session.calls == ["flush"]
