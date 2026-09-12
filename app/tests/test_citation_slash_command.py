"""The /citation slash command returns a turn intent without activating it."""

import asyncio

import pytest

from conftest import FakeChatSession

from agent.cli.slash_commands import (
    SlashCommandContext,
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

    def activate_citation_skill(self):
        self.calls.append("activate:citation")
        if self.fail_activation:
            raise ValueError("boom")
        self.active_skill_runtime = StubRuntime("citation")
        self.thinking_mode = "normal"
        return self.active_skill_runtime

    def deactivate_citation_skill(self):
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


@pytest.mark.parametrize("raw", ["/citation", "/citation   "])
def test_bare_citation_returns_usage_without_activation(raw):
    session = StubSession()
    result = _run(session, raw)
    assert session.calls == []
    assert "Usage: /citation <prompt>" in result.message
    assert result.followup_input is None
    assert result.skill_name is None


def test_citation_with_text_forwards_intent_without_activation():
    session = StubSession()
    result = _run(session, "/citation 幫我尋找近5年內關於HPC的論文")
    assert session.calls == []
    assert result.skill_name == "citation"
    assert "normal" in result.message
    assert result.followup_input == "幫我尋找近5年內關於HPC的論文"


def test_citation_natural_language_survives_apostrophes():
    session = StubSession()
    result = _run(session, "/citation find papers on Bell's theorem")
    assert result.followup_input == "find papers on Bell's theorem"


def test_citation_parser_leaves_legacy_active_state_for_turn_scope():
    session = StubSession(active="citation")
    result = _run(session, "/citation show me more candidates")
    assert session.calls == []
    assert session.active_skill_runtime.name == "citation"
    assert result.skill_name == "citation"
    assert result.followup_input == "show me more candidates"


@pytest.mark.parametrize("token", ["off", "NONE", "deactivate"])
@pytest.mark.parametrize("active", [None, "citation", "academic-paper-writing"])
def test_legacy_off_returns_migration_hint_without_mutation(token, active):
    session = StubSession(active=active)
    previous = session.active_skill_runtime
    result = _run(session, f"/citation {token}")
    assert "single-turn" in result.message
    assert "/citation <prompt>" in result.message
    assert "deactivated" not in result.message
    assert result.followup_input is None
    assert session.calls == []
    assert session.active_skill_runtime is previous


def test_followup_text_runs_as_agent_turn_via_chat_loop(monkeypatch, capsys):
    """/citation <text> reaches session.turn like a normal user message."""
    import argparse

    from agent.cli import chat

    class LoopSession(FakeChatSession):
        def __init__(self):
            super().__init__()
            self.active_skill_runtime = None

        async def turn(
            self,
            user_input,
            *,
            display_input=None,
            turn_id=None,
            skill_name=None,
        ):
            assert turn_id is not None
            return await super().turn(
                user_input, display_input=display_input,
                turn_id=turn_id, skill_name=skill_name,
            )

    session = LoopSession()

    async def fake_create(*args, **kwargs):
        return session

    inputs = iter([
        "/CiTaTiOn 幫我找 HPC 論文", "/citation off topic",
        "/citation off", "/citation", "ordinary question", "q",
    ])

    async def fake_read_line(_prompt):
        return next(inputs)

    monkeypatch.setattr(chat.ChatSession, "create", fake_create)
    args = argparse.Namespace(max_graph_steps=None, no_mcp=True)
    asyncio.run(chat._run(args, read_line=fake_read_line))

    assert [r["user_input"] for r in session.turn_requests] == [
        "幫我找 HPC 論文", "off topic", "ordinary question",
    ]
    assert [r["skill_name"] for r in session.turn_requests] == ["citation", "citation", None]
    assert session.turn_requests[0]["display_input"] == "/CiTaTiOn 幫我找 HPC 論文"
    output = capsys.readouterr().out
    assert "normal" in output
    assert "Usage: /citation <prompt>" in output
    assert "cli error" not in output


def test_citation_stays_reserved_against_dynamic_collision(tmp_path):
    from agent.skills import SkillMetadata

    session = StubSession()
    session.loaded_skills = [SkillMetadata(
        name="citation", description="dynamic collision", path=tmp_path / "SKILL.md",
    )]
    registry = build_default_registry(session)
    commands = [command for command in registry.all_commands() if command.name == "citation"]
    assert len(commands) == 1
    assert commands[0].description != "dynamic collision"
