"""Tests for the shared active-skill state serializer."""

from pathlib import Path
from types import SimpleNamespace

from agent.state import skill_runtime_to_agent_state
from agent.tool_access import ToolAccessResolution

_EXPECTED_KEYS = {
    "active_skill",
    "skill_root",
    "skill_instructions",
    "loaded_references",
    "task_mode",
    "effective_tools",
}


def _resolution():
    return ToolAccessResolution(
        global_tools=("rag_search", "read_file", "bash"),
        skill_tools=("citation_workflow",),
        effective_tools=("rag_search", "read_file", "bash", "citation_workflow"),
        missing_required=(),
        missing_optional=(),
    )


def _runtime(**overrides):
    base = dict(
        name="paper-writing",
        root=Path("/tmp/skills/paper-writing"),
        instructions="# Skill",
        pinned_references={"references/guide.md": "guide"},
        task_mode="revision",
        tool_access=_resolution(),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_none_runtime_returns_empty_state():
    assert skill_runtime_to_agent_state(None) == {}


def test_active_runtime_returns_exact_key_set_without_messages():
    state = skill_runtime_to_agent_state(_runtime())

    assert set(state) == _EXPECTED_KEYS
    assert "messages" not in state
    assert state["active_skill"] == "paper-writing"
    assert state["skill_root"] == str(Path("/tmp/skills/paper-writing"))
    assert state["skill_instructions"] == "# Skill"
    assert state["task_mode"] == "revision"


def test_effective_tools_preserve_resolution_order():
    state = skill_runtime_to_agent_state(_runtime())

    assert state["effective_tools"] == [
        "rag_search",
        "read_file",
        "bash",
        "citation_workflow",
    ]


def test_loaded_references_is_a_copy():
    refs = {"references/guide.md": "guide"}
    runtime = _runtime(pinned_references=refs)

    state = skill_runtime_to_agent_state(runtime)

    assert state["loaded_references"] == refs
    assert state["loaded_references"] is not refs
