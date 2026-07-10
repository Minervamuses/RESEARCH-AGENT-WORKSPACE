"""The built-in citation skill bundle and its session activation contract."""

import asyncio

import pytest

from conftest import FakeHistoryStore, make_astream_graph

from agent.config import AgentConfig
from agent.session import ChatSession
from agent.skills import discover_skills


@pytest.fixture
def make_session(monkeypatch, tmp_path):
    monkeypatch.setattr("agent.session.find_app_root", lambda: tmp_path)
    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _cfg, extra_tools=None, history_store=None, **kwargs: make_astream_graph(),
    )

    def _make():
        cfg = AgentConfig(persist_dir=str(tmp_path / "persist"))
        return ChatSession(cfg, history_store=FakeHistoryStore())

    return _make


def test_citation_bundle_is_discovered_with_lean_layout():
    skills = {skill.name: skill for skill in discover_skills(None)}
    assert "citation" in skills
    bundle_root = skills["citation"].path.parent
    assert (bundle_root / "manifest.yaml").exists()
    # Lean bundle: no README, no .skill archive inside the bundle.
    assert not (bundle_root / "README.md").exists()
    assert not list(bundle_root.glob("*.skill"))


def test_activation_grants_only_the_workflow_tool(make_session):
    session = make_session()
    runtime = session.activate_skill("citation")
    assert runtime.name == "citation"
    assert runtime.tool_policy_active is True
    assert runtime.allowed_tools == frozenset({"citation_workflow"})
    assert runtime.denied_tools == frozenset()
    assert "citation_workflow" in session._tool_availability_block()


def test_activation_forces_normal_thinking(make_session):
    session = make_session()
    session.thinking_mode = "extended"
    session.activate_skill("citation")
    assert session.thinking_mode == "normal"
    assert session.citation_skill_active is True


def test_extended_thinking_refused_while_citation_active(make_session):
    from agent.cli.slash_commands import (
        SlashCommandContext,
        SlashCommandError,
        build_default_registry,
        execute_slash_command,
        parse_slash_command,
    )

    session = make_session()
    session.activate_skill("citation")
    with pytest.raises(ValueError, match="extended thinking is unavailable"):
        session.set_thinking_mode("extended")

    context = SlashCommandContext(
        session=session, registry=build_default_registry()
    )
    with pytest.raises(SlashCommandError, match="citation"):
        asyncio.run(execute_slash_command(
            parse_slash_command("/thinking extended"), context
        ))
    assert session.thinking_mode == "normal"


def test_deactivation_tears_down_workflow_and_registry(make_session, tmp_path):
    session = make_session()
    session.activate_skill("citation")
    coordinator = session.citation_coordinator  # lazily built
    coordinator.registry.register_user_source("10.1234/x")
    assert session._citation_coordinator is not None

    session.deactivate_skill()
    assert session.active_skill_runtime is None
    assert session._citation_coordinator is None
    # A later activation starts from a fresh registry.
    session.activate_skill("citation")
    assert session.citation_coordinator.registry.list() == []


def test_switching_to_another_skill_tears_down_citation_state(make_session):
    session = make_session()
    session.activate_skill("citation")
    _ = session.citation_coordinator
    session.activate_skill("academic-paper-writing")
    assert session._citation_coordinator is None
    assert session.active_skill_runtime.name == "academic-paper-writing"
    assert session.citation_skill_active is False


def test_failed_activation_keeps_previous_skill_and_state(make_session, monkeypatch):
    session = make_session()
    session.activate_skill("citation")
    marker = session.citation_coordinator

    with pytest.raises(KeyError):
        session.activate_skill("no-such-skill")
    assert session.citation_skill_active is True
    assert session._citation_coordinator is marker


def test_non_citation_skills_unaffected_by_teardown_logic(make_session):
    session = make_session()
    session.activate_skill("academic-paper-writing")
    session.deactivate_skill()
    assert session.active_skill_runtime is None
