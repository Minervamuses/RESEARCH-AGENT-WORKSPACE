"""Characterization tests for the pre-extension startup contract."""

from agent.cli.slash_commands import build_default_registry
from agent.skills import discover_skills


def test_private_management_skill_is_not_publicly_discovered():
    names = {skill.name for skill in discover_skills(None)}

    assert {"_prompt-master", "academic-paper-writing", "citation"} <= names
    assert "extension-management" not in names


def test_default_slash_commands_use_case_insensitive_local_lookup():
    registry = build_default_registry()

    assert registry.get("STATUS") is registry.get("status")
    assert registry.get("SKILL") is registry.get("skill")
    assert registry.get("Extension-Management") is registry.get(
        "extension-management"
    )
