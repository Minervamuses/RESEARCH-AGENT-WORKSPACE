"""The built-in citation skill bundle and its session activation contract."""

import asyncio
from pathlib import Path
import traceback

import pytest

from conftest import make_astream_graph

from agent.config import AgentConfig
from agent.session import ChatSession
from agent.skills import SkillMetadata, discover_skills
from agent.turns.safety import find_tool_protocol_artifact


@pytest.fixture
def make_session(monkeypatch, tmp_path):
    monkeypatch.setattr("agent.session.find_app_root", lambda: tmp_path)
    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _cfg, extra_tools=None, **kwargs: make_astream_graph(),
    )

    def _make():
        cfg = AgentConfig(persist_dir=str(tmp_path / "persist"))
        return ChatSession(cfg)

    return _make


def test_citation_bundle_is_discovered_with_architecture_docs():
    skills = {skill.name: skill for skill in discover_skills(None)}
    assert "citation" in skills
    bundle_root = skills["citation"].path.parent
    assert (bundle_root / "manifest.yaml").exists()
    # Source bundles include developer-facing architecture docs, but not a
    # generated .skill archive.
    assert (bundle_root / "README.md").exists()
    assert not list(bundle_root.glob("*.skill"))


def test_citation_skill_text_is_free_of_protocol_artifacts():
    skill_path = Path(__file__).parents[1] / "skills" / "citation" / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8")
    tool_names = [
        "citation_workflow",
        "bash",
        "read_file",
        "rag_explore",
        "rag_search",
        "rag_get_context",
    ]

    assert find_tool_protocol_artifact(text, tool_names=tool_names) is None


def test_activation_adds_only_the_workflow_tool(make_session):
    session = make_session()
    normal_effective = session.tool_access_resolution().effective_tools

    runtime = session.activate_citation_skill()

    assert runtime.name == "citation"
    assert runtime.tool_access.skill_tools == ("citation_workflow",)
    assert runtime.tool_access.effective_tools == (
        *normal_effective,
        "citation_workflow",
    )
    availability = session._tool_availability_block()
    assert "citation_workflow" in availability
    # Global base tools stay available while the citation skill is active.
    assert "read_file" in availability
    assert "bash" in availability


def test_activation_forces_normal_thinking(make_session):
    session = make_session()
    session.thinking_mode = "extended"
    session.activate_citation_skill()
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
    session.activate_citation_skill()
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
    session.activate_citation_skill()
    service = session.citation_service  # lazily built
    from skills.citation.types import SourceRef

    service.registry.register(SourceRef(
        source_id="src-x", doi="10.1234/x", title="X",
        verification_level="identity_verified",
    ))
    assert session._citation_service is not None

    session.deactivate_citation_skill()
    assert session.active_skill_runtime is None
    assert session._citation_service is None
    # A later activation starts from a fresh registry.
    session.activate_citation_skill()
    assert session.citation_service.registry.list() == []


def test_switching_to_another_skill_tears_down_citation_state(make_session):
    session = make_session()
    session.activate_citation_skill()
    _ = session.citation_service
    answer = asyncio.run(session.turn(
        "draft this paper",
        skill_name="academic-paper-writing",
    ))
    assert answer == "ok"
    assert session._citation_service is None
    assert session.active_skill_runtime is None
    assert session.citation_skill_active is False


def test_failed_activation_keeps_previous_skill_and_state(make_session, monkeypatch):
    session = make_session()
    session.activate_citation_skill()
    marker = session.citation_service

    with pytest.raises(KeyError):
        asyncio.run(session.turn("draft", skill_name="no-such-skill"))
    assert session.citation_skill_active is True
    assert session._citation_service is marker


def test_failed_generic_slash_resolution_preserves_citation_state(
    make_session,
    tmp_path,
):
    from agent.cli.slash_commands import (
        SlashCommandContext,
        SlashCommandError,
        build_default_registry,
        execute_slash_command,
        parse_slash_command,
    )

    session = make_session()
    session.activate_citation_skill()
    marker = session.citation_service
    session.loaded_skills.append(SkillMetadata(
        name="help",
        description="Must not replace static help.",
        path=tmp_path / "collision" / "SKILL.md",
    ))
    registry = build_default_registry(session)
    context = SlashCommandContext(session=session, registry=registry)

    for raw in ("/academic-paper-writing", "/missing prompt"):
        with pytest.raises(SlashCommandError):
            asyncio.run(execute_slash_command(parse_slash_command(raw), context))
        assert session.citation_skill_active is True
        assert session._citation_service is marker

    assert any("/help" in item and "collision" in item for item in registry.diagnostics)
    assert session.citation_skill_active is True
    assert session._citation_service is marker


def test_non_citation_skills_unaffected_by_teardown_logic(make_session):
    session = make_session()
    answer = asyncio.run(session.turn(
        "draft this paper",
        skill_name="academic-paper-writing",
    ))
    assert answer == "ok"
    assert session.active_skill_runtime is None


def test_citation_turn_scope_restores_mode_and_records_actual_normal(make_session):
    session = make_session()
    session.thinking_mode = "extended"
    observed = []

    def inspect(_state):
        assert session.citation_skill_active
        assert session.thinking_mode == "normal"
        assert "citation_workflow" in session.tool_access_resolution().effective_tools
        observed.append(session.conversation_repository.load(session.session_id).document.turns[-1])

    session.graph = make_astream_graph(on_state=inspect)
    outcome = asyncio.run(session.turn_outcome("find Paper A", skill_name="citation"))
    assert outcome.text == "ok"
    assert observed[0].thinking_mode == "normal"
    assert session.thinking_mode == "extended"
    assert session.active_skill_runtime is None
    assert session._citation_service is None
    assert session._build_sources_hint() is None
    assert "citation_workflow" not in session.tool_access_resolution().effective_tools


def test_citation_turn_replaces_legacy_service_under_lock(make_session):
    session = make_session()
    session.activate_citation_skill()
    legacy = session.citation_service

    def inspect(_state):
        assert session._turn_execution_lock.locked()
        assert session.citation_skill_active
        assert session._citation_service is None

    session.graph = make_astream_graph(on_state=inspect)
    assert asyncio.run(session.turn("find Paper A", skill_name="CITATION")) == "ok"
    assert session._citation_service is None
    assert session.active_skill_runtime is None
    assert legacy.registry.list() == []


def _applied_session(tmp_path, monkeypatch, name):
    from agent.extensions.startup import load_extension_startup
    from test_extension_skill_startup import _config, _write_skill, _apply_skill

    config = _config(tmp_path)
    config.persist_dir = str(tmp_path / "persist")
    if name == "citation":
        # An isolated catalog exercises applied Citation without a built-in collision.
        config.skills_dir = str(tmp_path / "empty-skills")
    builtins = discover_skills(config)
    if name == "citation":
        assert builtins == []
    _write_skill(Path(config.extension_dropin_dir), name)
    _apply_skill(config, name)
    startup = load_extension_startup(config, builtin_skills=builtins)
    assert startup.diagnostics == ()
    assert [skill.name for skill in startup.skills] == [name]
    graph = make_astream_graph()
    monkeypatch.setattr("agent.session.find_app_root", lambda: tmp_path)
    monkeypatch.setattr("agent.session.build_graph", lambda *_args, **_kwargs: graph)
    session = ChatSession(
        config, loaded_skills=[*builtins, *startup.skills],
        running_extension_revision=startup.revision,
    )
    return session, startup.skills[0].path.parent, graph


def test_tampered_one_shot_slash_preserves_citation_before_graph(tmp_path, monkeypatch, caplog):
    from agent.cli.slash_commands import (
        SlashCommandContext, build_default_registry, execute_slash_command, parse_slash_command,
    )

    session, installed, graph = _applied_session(tmp_path, monkeypatch, "writer")
    previous = session.activate_citation_skill()
    service = session.citation_service
    thinking = session.thinking_mode
    tools = session.tool_access_resolution()
    marker = "PRIVATE_ONE_SHOT_TEST_CONTENT"
    with (installed / "SKILL.md").open("a", encoding="utf-8") as handle:
        handle.write(marker)
    context = SlashCommandContext(session=session, registry=build_default_registry(session))
    result = asyncio.run(execute_slash_command(parse_slash_command("/writer draft"), context))
    assert result.skill_name == "writer"
    assert result.followup_input == "draft"

    with pytest.raises(ValueError) as caught:
        asyncio.run(session.turn(result.followup_input, skill_name=result.skill_name))

    assert str(caught.value) == "applied bundle changed; restart or re-apply required"
    assert graph.states == []
    assert session.active_skill_runtime is previous
    assert session._citation_service is service
    assert session.thinking_mode == thinking
    assert session.tool_access_resolution() == tools
    assert marker not in session._active_skill_context_block()
    assert marker not in caplog.text
    assert marker not in "".join(traceback.format_exception(caught.value))
    conversation_path = session.conversation_repository.path_for(session.session_id)
    assert marker not in conversation_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("entry", ["direct", "slash"])
def test_tampered_applied_citation_activation_preserves_state(tmp_path, monkeypatch, caplog, entry):
    from agent.cli.slash_commands import (
        SlashCommandContext, SlashCommandError, build_default_registry,
        execute_slash_command, parse_slash_command,
    )

    session, installed, graph = _applied_session(tmp_path, monkeypatch, "citation")
    if entry == "direct":
        session.activate_citation_skill()
    else:
        session.set_thinking_mode("extended")
    previous = session.active_skill_runtime
    service = session.citation_service
    thinking = session.thinking_mode
    tools = session.tool_access_resolution()
    marker = "PRIVATE_CITATION_TEST_CONTENT"
    (installed / "manifest.yaml").write_text(f"tools: [{marker}\n", encoding="utf-8")

    with pytest.raises(ValueError) as caught:
        if entry == "direct":
            session.activate_citation_skill()
        else:
            context = SlashCommandContext(session=session, registry=build_default_registry(session))
            result = asyncio.run(execute_slash_command(parse_slash_command("/citation find Paper A"), context))
            asyncio.run(session.turn(result.followup_input, skill_name=result.skill_name))

    assert "applied bundle changed; restart or re-apply required" in str(caught.value)
    assert graph.states == []
    assert session.active_skill_runtime is previous
    assert session._citation_service is service
    assert session.thinking_mode == thinking
    assert session.tool_access_resolution() == tools
    assert marker not in caplog.text
    assert marker not in "".join(traceback.format_exception(caught.value))
