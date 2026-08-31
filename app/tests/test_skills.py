"""Tests for local skill discovery and prompt rendering."""

import asyncio

import pytest

from agent.config import AgentConfig
from agent.state import AgentState
from agent.skills import discover_skills
from agent.session import ChatSession
from agent.turns.results import TurnOutcome


def test_discover_skills_reads_name_description_and_path(tmp_path):
    skills_dir = tmp_path / "skills"
    target = skills_dir / "sample-skill"
    target.mkdir(parents=True)
    skill_file = target / "SKILL.md"
    skill_file.write_text(
        """---
name: sample-skill
description: Use when the user wants to draft a paper
  abstract or revise a manuscript introduction.
---

# Sample
""",
        encoding="utf-8",
    )

    cfg = AgentConfig(persist_dir=str(tmp_path), skills_dir=str(skills_dir))
    skills = discover_skills(cfg)

    assert len(skills) == 1
    assert skills[0].name == "sample-skill"
    assert skills[0].description == (
        "Use when the user wants to draft a paper abstract or revise a manuscript introduction."
    )
    assert skills[0].path == skill_file.resolve()


def test_discover_skills_reads_yaml_block_scalar_description(tmp_path):
    skills_dir = tmp_path / "skills"
    target = skills_dir / "sample-skill"
    target.mkdir(parents=True)
    skill_file = target / "SKILL.md"
    skill_file.write_text(
        """---
name: sample-skill
description: >
  Use when the user wants to draft a paper
  abstract or revise a manuscript introduction.
---

# Sample
""",
        encoding="utf-8",
    )

    cfg = AgentConfig(persist_dir=str(tmp_path), skills_dir=str(skills_dir))
    skills = discover_skills(cfg)

    assert len(skills) == 1
    assert skills[0].description == (
        "Use when the user wants to draft a paper abstract or revise a manuscript introduction."
    )


def test_discover_skills_skips_malformed_yaml_frontmatter(tmp_path):
    skills_dir = tmp_path / "skills"
    target = skills_dir / "bad-skill"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text(
        """---
name: bad-skill
description: [unterminated
---

# Bad
""",
        encoding="utf-8",
    )

    cfg = AgentConfig(persist_dir=str(tmp_path), skills_dir=str(skills_dir))

    assert discover_skills(cfg) == []


def test_chat_session_discovers_skills_without_injecting_into_system_prompt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    skills_dir = tmp_path / "skills"
    target = skills_dir / "paper-writing"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text(
        """---
name: paper-writing
description: Use when the user wants help with academic writing.
---
""",
        encoding="utf-8",
    )

    class _FakeGraph:
        async def astream(self, state, config=None, stream_mode="updates"):
            if False:  # pragma: no cover
                yield None

    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _cfg, extra_tools=None, history_store=None, **kwargs: _FakeGraph(),
    )

    cfg = AgentConfig(persist_dir=str(tmp_path), skills_dir="skills")
    session = ChatSession(cfg)

    prompt = session.system_prompt_message.content
    assert "**read_file**" in prompt
    assert "paper-writing" not in prompt
    assert "Use when the user wants help with academic writing." not in prompt

    assert len(session.loaded_skills) == 1
    assert session.loaded_skills[0].name == "paper-writing"


def test_agent_state_skill_fields_are_optional():
    assert "messages" in AgentState.__optional_keys__
    assert "active_skill" in AgentState.__optional_keys__
    assert "loaded_references" in AgentState.__optional_keys__
    assert "effective_tools" in AgentState.__optional_keys__


def test_agent_config_exposes_skill_runtime_toggles(tmp_path):
    cfg = AgentConfig(persist_dir=str(tmp_path))

    assert cfg.skill_max_pinned_reference_chars == 65536
    assert cfg.skill_max_total_skill_context_chars == 200000


def test_chat_session_skill_runtime_is_one_shot_and_uses_trailing_prompt(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    skills_dir = tmp_path / "skills"
    target = skills_dir / "paper-writing"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text(
        """---
name: paper-writing
description: Use when the user wants help with academic writing.
---

# Paper Writing
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _cfg, extra_tools=None, history_store=None, **kwargs: object(),
    )
    session = ChatSession(
        AgentConfig(persist_dir=str(tmp_path), skills_dir="skills")
    )
    observed: list[tuple[str, str | None]] = []

    async def capture_turn(user_input: str) -> TurnOutcome:
        runtime = session.active_skill_runtime
        observed.append((user_input, runtime.name if runtime else None))
        return TurnOutcome(text="ok")

    monkeypatch.setattr(session, "_run_turn", capture_turn)

    assert asyncio.run(
        session.turn("draft  this", skill_name="paper-writing")
    ) == "ok"
    assert session.active_skill_runtime is None
    assert asyncio.run(session.turn("next")) == "ok"
    assert observed == [
        ("draft  this", "paper-writing"),
        ("next", None),
    ]


def test_chat_session_one_shot_skill_cleans_up_on_error_and_cancel(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "skills" / "paper-writing"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text(
        "---\nname: paper-writing\n"
        "description: Use when writing papers.\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _cfg, extra_tools=None, history_store=None, **kwargs: object(),
    )
    session = ChatSession(
        AgentConfig(persist_dir=str(tmp_path), skills_dir="skills")
    )

    async def fail(_user_input: str) -> TurnOutcome:
        assert session.active_skill_runtime.name == "paper-writing"
        raise RuntimeError("provider failed")

    monkeypatch.setattr(session, "_run_turn", fail)
    with pytest.raises(RuntimeError, match="provider failed"):
        asyncio.run(session.turn("draft", skill_name="paper-writing"))
    assert session.active_skill_runtime is None

    async def cancel(_user_input: str) -> TurnOutcome:
        assert session.active_skill_runtime.name == "paper-writing"
        raise asyncio.CancelledError

    monkeypatch.setattr(session, "_run_turn", cancel)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(session.turn("draft", skill_name="paper-writing"))
    assert session.active_skill_runtime is None


def test_chat_session_status_has_no_persistent_generic_skill_state(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _cfg, extra_tools=None, history_store=None, **kwargs: object(),
    )
    session = ChatSession(AgentConfig(persist_dir=str(tmp_path)))

    status = session.status_snapshot()

    assert "active_skill" not in status
