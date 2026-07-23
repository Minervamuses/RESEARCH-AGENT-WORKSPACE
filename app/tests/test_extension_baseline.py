"""Characterization tests for the pre-extension startup contract."""

from dataclasses import dataclass

from agent.cli.slash_commands import build_default_registry
from agent.skills import discover_skills
from agent.tool_access import resolve_tool_access


@dataclass(frozen=True)
class _Tool:
    name: str


def test_builtin_skills_are_public_but_management_skill_does_not_exist_yet():
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


def test_only_web_search_mcp_is_global_before_extension_changes():
    tools = [_Tool("rag_search"), _Tool("web_fetch"), _Tool("github_repo")]
    families = {
        "web_fetch": "web_search",
        "github_repo": "github",
    }

    normal = resolve_tool_access(None, tools, mcp_families=families)
    github_skill = resolve_tool_access(
        {"tools": {"optional": {"mcp_families": ["github"]}}},
        tools,
        mcp_families=families,
    )

    assert normal.effective_tools == ("rag_search", "web_fetch")
    assert github_skill.effective_tools == (
        "rag_search",
        "web_fetch",
        "github_repo",
    )
