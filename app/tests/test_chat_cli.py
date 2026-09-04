"""Tests for the interactive chat CLI wrapper."""

import argparse
import asyncio
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest

from conftest import FakeChatSession, FakeHistoryStore
from agent.cli.slash_commands import (
    SlashCommand,
    SlashCommandRegistry,
    SlashCommandResult,
)
from agent.config import AgentConfig
from agent.conversations import ConversationRepository
from agent.session import ChatSession
from agent.skills import SkillMetadata


def _run_cli(
    monkeypatch,
    session,
    inputs,
    *,
    max_graph_steps=None,
    no_mcp=False,
):
    """Drive chat._run with a fake session and scripted line inputs."""
    from agent.cli import chat

    create_kwargs = {}

    async def fake_create(config, **kwargs):
        session.config = config
        create_kwargs.update(kwargs)
        return session

    input_iter = iter(inputs)

    async def fake_read_line(_prompt: str) -> str:
        return next(input_iter)

    monkeypatch.setattr(chat.ChatSession, "create", fake_create)

    args = argparse.Namespace(max_graph_steps=max_graph_steps, no_mcp=no_mcp)
    asyncio.run(chat._run(args, read_line=fake_read_line))
    return create_kwargs


def _canonical_cli_session(monkeypatch, tmp_path):
    repository = ConversationRepository(tmp_path / "store")
    session_id = uuid.uuid4().hex
    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _config, extra_tools=None, history_store=None, **kwargs: object(),
    )
    session = ChatSession(
        AgentConfig(persist_dir=str(tmp_path / "store")),
        history_store=FakeHistoryStore(),
        loaded_skills=[],
        conversation_repository=repository,
        project_id="local",
        session_id=session_id,
    )
    return session, repository


def _extension_preview(tmp_path):
    return SimpleNamespace(
        paths=SimpleNamespace(dropin_root=tmp_path / "dropins"),
        registry=SimpleNamespace(revision=0),
        diff=SimpleNamespace(
            changes=(
                SimpleNamespace(key="skill:writer", operation="add"),
            ),
            diagnostics=(),
        ),
        plan=SimpleNamespace(
            items=(
                SimpleNamespace(
                    key="skill:writer",
                    decision="apply",
                    summary="Install the writer skill.",
                    reason=None,
                ),
            ),
        ),
        mcp_candidates={},
        host_blocks={},
    )


class _UncleanExit(BaseException):
    """Simulate process loss without giving turn cleanup a catchable error."""


def test_chat_cli_writes_each_turn_without_exit_flush(monkeypatch):
    session = FakeChatSession()

    _run_cli(monkeypatch, session, ["hello", "q"])

    assert session.calls == ["turn:hello"]
    assert session.turn_requests[0]["display_input"] == "hello"


def test_chat_cli_builds_config_from_single_graph_limit_source(monkeypatch):
    default_session = FakeChatSession()
    _run_cli(monkeypatch, default_session, ["q"])
    assert default_session.config.graph_recursion_limit == 64

    overridden_session = FakeChatSession()
    _run_cli(
        monkeypatch,
        overridden_session,
        ["q"],
        max_graph_steps=91,
    )
    assert overridden_session.config.graph_recursion_limit == 91


@pytest.mark.parametrize(
    ("no_mcp", "expected_load_mcp"),
    [(False, True), (True, False)],
)
def test_chat_cli_defaults_mcp_on_and_preserves_explicit_opt_out(
    monkeypatch, no_mcp, expected_load_mcp
):
    session = FakeChatSession()

    create_kwargs = _run_cli(
        monkeypatch,
        session,
        ["q"],
        no_mcp=no_mcp,
    )

    assert create_kwargs["load_mcp"] is expected_load_mcp


@pytest.mark.parametrize("value", ["1", "2", "not-an-int"])
def test_chat_cli_rejects_graph_limits_that_cannot_finalize(
    monkeypatch, capsys, value
):
    from agent.cli import chat

    monkeypatch.setattr(
        "sys.argv", ["chat", "--max-graph-steps", value]
    )

    with pytest.raises(SystemExit) as exc_info:
        chat.main()

    assert exc_info.value.code == 2
    assert "graph" in capsys.readouterr().err


def test_chat_cli_banner_reports_loaded_mcp_families(monkeypatch, capsys):
    session = FakeChatSession()
    session.mcp_families = {
        "full-web-search": "web_search",
        "get-web-search-summaries": "web_search",
    }

    _run_cli(monkeypatch, session, ["q"])

    assert "MCP: web_search" in capsys.readouterr().out


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

    assert session.calls == []


def test_chat_cli_blank_input_does_not_exit(monkeypatch):
    session = FakeChatSession(record_repr=True)

    _run_cli(monkeypatch, session, ["", "   ", "​", "﻿", "q"])

    assert session.calls == []


def test_chat_cli_does_not_normalize_regular_messages(monkeypatch):
    session = FakeChatSession(record_repr=True)

    _run_cli(monkeypatch, session, ["hello​", "q"])

    assert session.calls == ["turn:'hello\\u200b'"]


def test_chat_cli_does_not_need_an_exit_flush_after_turn_error(monkeypatch):
    session = FakeChatSession(turn_error=RuntimeError("boom"))

    _run_cli(monkeypatch, session, ["hello", "q"])

    assert session.calls == ["turn:hello"]


def test_chat_cli_never_prints_a_silent_blank_response(monkeypatch, capsys):
    session = FakeChatSession(turn_result="   ")

    _run_cli(monkeypatch, session, ["請回答", "q"])

    output = capsys.readouterr().out
    assert "未能產生可顯示" in output
    assert session.calls == ["turn:請回答"]


def test_chat_cli_slash_help_stays_local(monkeypatch, capsys):
    session = FakeChatSession(status={
        "session_id": "session-1",
        "turn_count": 0,
        "recent_turn_count": 0,
        "graph_recursion_limit": 64,
        "last_tool_counts": "none",
    })

    _run_cli(monkeypatch, session, ["/help", "q"])

    output = capsys.readouterr().out
    assert "Available slash commands:" in output
    assert "/help" in output
    assert session.calls == []


def test_chat_cli_slash_help_is_durable_display_only_before_handler(
    monkeypatch,
    tmp_path,
    capsys,
):
    from agent.cli import chat

    session, repository = _canonical_cli_session(monkeypatch, tmp_path)
    session_id = session.session_id
    observed = []

    async def help_handler(_context, _parsed):
        snapshot = repository.load_optional(session_id)
        observed.append(
            None
            if snapshot is None
            else (
                snapshot.document.turns[-1].state,
                snapshot.document.turns[-1].kind,
                snapshot.document.turns[-1].display_input,
            )
        )
        return SlashCommandResult(message="canonical local help")

    registry = SlashCommandRegistry([
        SlashCommand(
            name="help",
            description="Show local help.",
            handler=help_handler,
        )
    ])
    monkeypatch.setattr(chat, "build_default_registry", lambda _session: registry)

    _run_cli(monkeypatch, session, ["/help", "q"])

    snapshot = repository.load(session_id)
    turn = snapshot.document.turns[0]
    assert observed == [("pending", "display-only", "/help")]
    assert turn.state == "completed"
    assert turn.kind == "display-only"
    assert turn.semantic_input is None
    assert turn.context_eligible is False
    assert turn.thinking_mode is None
    assert turn.assistant_output == "canonical local help"
    assert repository.latest_context(snapshot) == ()
    assert "canonical local help" in capsys.readouterr().out


def test_chat_cli_extension_apply_stays_pending_through_confirmation(
    monkeypatch,
    tmp_path,
    capsys,
):
    session, repository = _canonical_cli_session(monkeypatch, tmp_path)
    preview = _extension_preview(tmp_path)
    stages = []
    approval = "yEs"

    def observe(stage):
        turn = repository.load(session.session_id).document.turns[-1]
        stages.append((stage, turn.turn_id, turn.state, turn.kind))

    class RecordingManager:
        def preview(self):
            observe("preview")
            return preview

        def apply(self, selected, *, approved_mcp_bindings):
            observe("apply")
            assert selected is preview
            assert approved_mcp_bindings == set()
            return SimpleNamespace(
                previous_revision=0,
                applied_revision=1,
                restart_required=True,
                items=(
                    SimpleNamespace(
                        key="skill:writer",
                        outcome="added",
                        detail="Installed the writer skill.",
                    ),
                ),
                diagnostics=(),
            )

    def confirm(_prompt):
        observe("confirmation")
        return approval

    session.extension_manager = RecordingManager()
    monkeypatch.setattr("builtins.input", confirm)

    _run_cli(monkeypatch, session, ["/Extension-Management", "q"])

    snapshot = repository.load(session.session_id)
    turn = snapshot.document.turns[-1]
    assert [stage[0] for stage in stages] == [
        "preview",
        "confirmation",
        "apply",
    ]
    assert {stage[1] for stage in stages} == {turn.turn_id}
    assert {(stage[2], stage[3]) for stage in stages} == {
        ("pending", "display-only")
    }
    assert len(snapshot.document.turns) == 1
    assert turn.state == "completed"
    assert turn.assistant_output is not None
    assert "applied revision 0 -> 1" in turn.assistant_output
    assert approval not in repository.path_for(session.session_id).read_text(
        encoding="utf-8"
    )
    assert turn.assistant_output in capsys.readouterr().out


def test_chat_cli_confirmed_prune_is_durable_before_side_effect(
    monkeypatch,
    tmp_path,
    capsys,
):
    from agent.cli import slash_commands

    source = tmp_path / "source"
    source.mkdir()
    session, repository = _canonical_cli_session(monkeypatch, tmp_path)
    observed = []
    prune_calls = 0

    async def prune_folder(target, _config):
        nonlocal prune_calls
        prune_calls += 1
        snapshot = repository.load_optional(session.session_id)
        observed.append(
            None
            if snapshot is None
            else (
                snapshot.document.turns[-1].state,
                snapshot.document.turns[-1].kind,
                snapshot.document.turns[-1].display_input,
            )
        )
        assert target == source.resolve()
        return ["gone-pid"]

    monkeypatch.setattr(slash_commands, "prune_folder", prune_folder)

    command = f"/prune {source} --yes"
    _run_cli(monkeypatch, session, [command, "q"])

    snapshot = repository.load(session.session_id)
    turn = snapshot.document.turns[0]
    assert prune_calls == 1
    assert observed == [("pending", "display-only", command)]
    assert turn.state == "completed"
    assert turn.kind == "display-only"
    assert turn.semantic_input is None
    assert turn.context_eligible is False
    assert turn.assistant_output is not None
    assert "pruned 1 orphaned pid(s)" in turn.assistant_output
    assert repository.latest_context(snapshot) == ()
    assert turn.assistant_output in capsys.readouterr().out


@pytest.mark.parametrize("command_kind", ["extension", "prune"])
def test_chat_cli_unclean_local_command_recovers_without_replay(
    monkeypatch,
    tmp_path,
    command_kind,
):
    from agent.cli import slash_commands

    session, repository = _canonical_cli_session(monkeypatch, tmp_path)
    calls = []

    def crash_side_effect():
        turn = repository.load(session.session_id).document.turns[-1]
        calls.append((turn.turn_id, turn.state, turn.kind))
        raise _UncleanExit("simulated process loss")

    if command_kind == "extension":
        preview = _extension_preview(tmp_path)

        class CrashingManager:
            def preview(self):
                return preview

            def apply(self, selected, *, approved_mcp_bindings):
                assert selected is preview
                assert approved_mcp_bindings == set()
                crash_side_effect()

        session.extension_manager = CrashingManager()
        monkeypatch.setattr("builtins.input", lambda _prompt: "yes")
        command = "/Extension-Management"
    else:
        source = tmp_path / "source"
        source.mkdir()

        async def crashing_prune(target, _config):
            assert target == source.resolve()
            crash_side_effect()

        monkeypatch.setattr(slash_commands, "prune_folder", crashing_prune)
        command = f"/prune {source} --yes"

    with pytest.raises(_UncleanExit, match="simulated process loss"):
        _run_cli(monkeypatch, session, [command])

    pending = repository.load(session.session_id).document.turns[-1]
    assert calls == [(pending.turn_id, "pending", "display-only")]
    assert pending.state == "pending"
    assert pending.assistant_output is None

    restored = ChatSession(
        AgentConfig(persist_dir=str(tmp_path / "store")),
        history_store=FakeHistoryStore(),
        loaded_skills=[],
        conversation_repository=repository,
        project_id="local",
        session_id=session.session_id,
    )

    recovered = repository.load(restored.session_id).document.turns[-1]
    assert recovered.turn_id == pending.turn_id
    assert recovered.state == "interrupted"
    assert recovered.assistant_output is None
    assert recovered.failure is not None
    assert recovered.failure.code == "interrupted"
    assert calls == [(pending.turn_id, "pending", "display-only")]


def test_chat_cli_routes_dynamic_skill_with_exact_trailing_prompt(monkeypatch):
    session = FakeChatSession()
    session.loaded_skills = [
        SkillMetadata(
            name="writer",
            description="Write one draft.",
            path=Path("/fixture/writer/SKILL.md"),
        )
    ]

    _run_cli(monkeypatch, session, ['/writer draft  "quoted"   text', "q"])

    assert session.calls == [
        'turn:draft  "quoted"   text skill:writer',
    ]
    assert session.turn_requests[0]["display_input"] == (
        '/writer draft  "quoted"   text'
    )


def test_chat_cli_slash_status_reports_session(monkeypatch, capsys):
    session = FakeChatSession(status={
        "session_id": "session-42",
        "turn_count": 3,
        "recent_turn_count": 2,
        "graph_recursion_limit": 64,
        "last_tool_counts": "rag_search x1",
        "thinking_mode": "extended",
        "mcp_families": "web_search",
    })

    _run_cli(monkeypatch, session, ["/status", "q"])

    output = capsys.readouterr().out
    assert "Session status:" in output
    assert "session_id: session-42" in output
    assert "graph_recursion_limit: 64" in output
    assert "last_tool_calls: rag_search x1" in output
    assert "thinking_mode: extended" in output
    assert "mcp_families: web_search" in output
    assert session.calls == []


def test_chat_cli_slash_quit_exits_without_agent_turn(monkeypatch):
    session = FakeChatSession(status={
        "session_id": "session-1",
        "turn_count": 0,
        "recent_turn_count": 0,
        "graph_recursion_limit": 64,
        "last_tool_counts": "none",
    })

    _run_cli(monkeypatch, session, ["/quit"])

    assert session.calls == []
