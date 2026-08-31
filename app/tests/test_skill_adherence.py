"""End-to-end adherence checks for slash-command skill runtime."""

import asyncio
import json

from langchain_core.messages import AIMessage

from agent.cli.slash_commands import (
    SlashCommandContext,
    build_default_registry,
    execute_slash_command,
    parse_slash_command,
)
from agent.config import AgentConfig
from agent.session import ChatSession
from agent.tools.read_file import _read_file


def _write_academic_skill(tmp_path):
    skills_dir = tmp_path / "skills"
    root = skills_dir / "academic-paper-writing"
    refs = root / "references"
    refs.mkdir(parents=True)
    (root / "SKILL.md").write_text(
        """---
name: academic-paper-writing
description: Use when writing academic papers.
---

# Academic Paper Writing
""",
        encoding="utf-8",
    )
    (refs / "section-playbooks.md").write_text("section reference", encoding="utf-8")
    (root / "manifest.yaml").write_text(
        """
resources:
  - path: references/section-playbooks.md
    pinned: true
""",
        encoding="utf-8",
    )
    return skills_dir, root


class _CaptureGraph:
    def __init__(self, captured):
        self.captured = captured

    async def astream(self, state, config=None, stream_mode="updates"):
        self.captured["state"] = state
        yield {"agent": {"messages": [AIMessage(content="ok")]}}


def _make_session(tmp_path, monkeypatch, captured):
    skills_dir, _root = _write_academic_skill(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _cfg, extra_tools=None, history_store=None, **kwargs: _CaptureGraph(captured),
    )
    cfg = AgentConfig(persist_dir=str(tmp_path), skills_dir=str(skills_dir))
    return ChatSession(cfg)


def test_slash_skill_command_selects_exactly_one_runtime_turn(tmp_path, monkeypatch):
    captured = {}
    session = _make_session(tmp_path, monkeypatch, captured)
    registry = build_default_registry(session)

    result = asyncio.run(execute_slash_command(
        parse_slash_command("/academic-paper-writing revise  this abstract"),
        SlashCommandContext(session=session, registry=registry),
    ))
    assert result.skill_name == "academic-paper-writing"
    assert result.followup_input == "revise  this abstract"
    assert session.active_skill_runtime is None

    answer = asyncio.run(session.turn(
        result.followup_input,
        skill_name=result.skill_name,
    ))
    assert answer == "ok"
    assert captured["state"]["active_skill"] == "academic-paper-writing"
    assert session.active_skill_runtime is None


def test_active_skill_state_and_prompt_are_ready_before_turn(tmp_path, monkeypatch):
    captured = {}
    session = _make_session(tmp_path, monkeypatch, captured)

    answer = asyncio.run(session.turn(
        "revise this abstract",
        skill_name="academic-paper-writing",
    ))
    state = captured["state"]
    prompt_text = "\n".join(message.content for message in state["messages"])

    assert answer == "ok"
    # The session initial state carries the same serialized active-skill slice
    # as the graph loader.
    serialized_keys = {
        "active_skill",
        "skill_root",
        "skill_instructions",
        "loaded_references",
        "effective_tools",
    }
    assert serialized_keys <= set(state)
    assert state["active_skill"] == "academic-paper-writing"
    assert state["skill_instructions"].startswith("---")
    assert state["loaded_references"] == {
        "references/section-playbooks.md": "section reference"
    }
    assert "# Academic Paper Writing" in prompt_text


def test_active_skill_relative_reference_resolves_to_skill_bundle(tmp_path, monkeypatch):
    captured = {}
    session = _make_session(tmp_path, monkeypatch, captured)
    asyncio.run(session.turn(
        "read the reference",
        skill_name="academic-paper-writing",
    ))

    payload = json.loads(
        _read_file(
            "references/section-playbooks.md",
            skill_root=captured["state"]["skill_root"],
        )
    )

    assert payload["path"].endswith(
        "skills/academic-paper-writing/references/section-playbooks.md"
    )
    assert payload["content"] == "section reference"


def test_active_skill_keeps_global_tools(tmp_path, monkeypatch):
    captured = {}
    session = _make_session(tmp_path, monkeypatch, captured)
    asyncio.run(session.turn(
        "draft",
        skill_name="academic-paper-writing",
    ))

    assert "read_file" in captured["state"]["effective_tools"]
    assert "bash" in captured["state"]["effective_tools"]


def test_no_skill_turn_keeps_skill_state_empty(tmp_path, monkeypatch):
    captured = {}
    session = _make_session(tmp_path, monkeypatch, captured)

    answer = asyncio.run(session.turn("hello"))

    assert answer == "ok"
    assert session.active_skill_runtime is None
    assert "active_skill" not in captured["state"]
