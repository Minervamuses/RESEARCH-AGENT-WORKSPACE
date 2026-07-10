"""The /citation slash command: persistent activation, followup, off."""

import asyncio

import pytest

from agent.cli.slash_commands import (
    SlashCommandContext,
    SlashCommandError,
    build_default_registry,
    execute_slash_command,
    parse_slash_command,
)


class StubRuntime:
    def __init__(self, name):
        self.name = name


class StubSession:
    """Session stand-in tracking skill activation calls."""

    def __init__(self, active=None, fail_activation=False):
        self.active_skill_runtime = StubRuntime(active) if active else None
        self.fail_activation = fail_activation
        self.calls: list[str] = []
        self.thinking_mode = "extended"

    def activate_skill(self, name, task_mode=None):
        self.calls.append(f"activate:{name}")
        if self.fail_activation:
            raise ValueError("boom")
        self.active_skill_runtime = StubRuntime(name)
        self.thinking_mode = "normal"
        return self.active_skill_runtime

    def deactivate_skill(self):
        self.calls.append("deactivate")
        self.active_skill_runtime = None


def _run(session, raw):
    parsed = parse_slash_command(raw)
    context = SlashCommandContext(
        session=session, registry=build_default_registry()
    )
    return asyncio.run(execute_slash_command(parsed, context))


def test_registry_has_citation_but_no_cite_alias():
    registry = build_default_registry()
    assert registry.get("citation") is not None
    assert registry.get("cite") is None


def test_bare_citation_activates_persistently_without_followup():
    session = StubSession()
    result = _run(session, "/citation")
    assert session.calls == ["activate:citation"]
    assert "activated" in result.message
    assert "normal" in result.message  # thinking hint shown
    assert result.followup_input is None


def test_citation_with_text_activates_and_forwards_raw_text():
    session = StubSession()
    result = _run(session, "/citation 幫我尋找近5年內關於HPC的論文")
    assert session.calls == ["activate:citation"]
    assert result.followup_input == "幫我尋找近5年內關於HPC的論文"


def test_citation_natural_language_survives_apostrophes():
    session = StubSession()
    result = _run(session, "/citation find papers on Bell's theorem")
    assert result.followup_input == "find papers on Bell's theorem"


def test_second_citation_call_reports_already_active_but_still_forwards():
    session = StubSession(active="citation")
    result = _run(session, "/citation show me more candidates")
    assert session.calls == []  # no re-activation
    assert "already active" in result.message
    assert result.followup_input == "show me more candidates"


def test_citation_off_deactivates_only_when_active():
    session = StubSession(active="citation")
    for token in ("off", "none", "deactivate"):
        session.active_skill_runtime = StubRuntime("citation")
        result = _run(session, f"/citation {token}")
        assert "deactivated" in result.message
    assert session.calls.count("deactivate") == 3


def test_citation_off_never_touches_other_skills():
    session = StubSession(active="academic-paper-writing")
    with pytest.raises(SlashCommandError, match="not active"):
        _run(session, "/citation off")
    assert session.calls == []
    assert session.active_skill_runtime.name == "academic-paper-writing"

    idle = StubSession()
    with pytest.raises(SlashCommandError, match="not active"):
        _run(idle, "/citation off")


def test_failed_activation_is_a_cli_error_and_keeps_prior_skill():
    session = StubSession(active=None, fail_activation=True)
    with pytest.raises(SlashCommandError, match="failed to activate"):
        _run(session, "/citation")
    assert session.active_skill_runtime is None


def test_activation_replaces_current_skill_without_restoration_stack():
    session = StubSession(active="academic-paper-writing")
    _run(session, "/citation")
    assert session.active_skill_runtime.name == "citation"
    # Turning citation off leaves no skill (no restoration of the old one).
    _run(session, "/citation off")
    assert session.active_skill_runtime is None


def test_followup_text_runs_as_agent_turn_via_chat_loop(monkeypatch):
    """/citation <text> reaches session.turn like a normal user message."""
    import argparse

    from agent.cli import chat

    class LoopSession(StubSession):
        recursion_limit = 32

        def __init__(self):
            super().__init__()
            self.turns: list[str] = []

        async def turn(self, user_input):
            self.turns.append(user_input)
            return "answer"

        async def flush_recent_turns(self):
            self.calls.append("flush")

    session = LoopSession()

    async def fake_create(*args, **kwargs):
        return session

    inputs = iter(["/citation 幫我找 HPC 論文", "q"])

    async def fake_read_line(_prompt):
        return next(inputs)

    monkeypatch.setattr(chat.ChatSession, "create", fake_create)
    args = argparse.Namespace(max_turns=32, no_mcp=True)
    asyncio.run(chat._run(args, read_line=fake_read_line))

    assert session.calls[0] == "activate:citation"
    assert session.turns == ["幫我找 HPC 論文"]
