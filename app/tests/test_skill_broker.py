"""Tests for the skill activation gate over tool access resolution."""

import pytest
from langchain_core.tools import tool

from agent.skills.broker import resolve_skill_tool_access


@tool("read_file")
def _read_file(path: str) -> str:
    """Read a file."""
    return path


@tool("rag_search")
def _rag_search(query: str) -> str:
    """Search RAG."""
    return query


@tool("bash")
def _bash(command: str) -> str:
    """Run shell."""
    return command


@tool("full-web-search")
def _full_web_search(query: str) -> str:
    """Search web."""
    return query


@tool("github_search")
def _github_search(query: str) -> str:
    """Read GitHub."""
    return query


@tool("citation_workflow")
def _citation_workflow(action: str) -> str:
    """Citation workflow."""
    return action


ALL_TOOLS = [
    _read_file,
    _rag_search,
    _bash,
    _full_web_search,
    _github_search,
    _citation_workflow,
]

MCP_FAMILIES = {"full-web-search": "web_search", "github_search": "github"}


def test_manifest_without_tools_keeps_global_tools_only():
    resolution = resolve_skill_tool_access({}, ALL_TOOLS, mcp_families=MCP_FAMILIES)

    assert resolution.effective_tools == (
        "read_file",
        "rag_search",
        "bash",
        "full-web-search",
    )
    assert resolution.skill_tools == ()


def test_required_local_tool_is_granted():
    manifest = {"tools": {"required": {"local": ["citation_workflow"]}}}

    resolution = resolve_skill_tool_access(
        manifest, ALL_TOOLS, mcp_families=MCP_FAMILIES
    )

    assert resolution.skill_tools == ("citation_workflow",)
    assert "citation_workflow" in resolution.effective_tools
    assert "github_search" not in resolution.effective_tools


def test_missing_required_skill_tool_blocks_activation():
    manifest = {"tools": {"required": {"local": ["citation_workflow"]}}}

    with pytest.raises(
        ValueError,
        match="required skill tools are unavailable: citation_workflow",
    ):
        resolve_skill_tool_access(
            manifest,
            [_read_file, _rag_search, _bash],
            mcp_families={},
        )


def test_missing_required_mcp_family_blocks_activation():
    manifest = {"tools": {"required": {"mcp_families": ["github"]}}}

    with pytest.raises(
        ValueError,
        match="required skill tools are unavailable: github",
    ):
        resolve_skill_tool_access(
            manifest,
            [_read_file, _full_web_search],
            mcp_families={"full-web-search": "web_search"},
        )


def test_missing_optional_skill_tool_does_not_block_activation():
    manifest = {
        "tools": {
            "required": {"local": ["citation_workflow"]},
            "optional": {"mcp_families": ["github"]},
        }
    }

    resolution = resolve_skill_tool_access(
        manifest,
        [_read_file, _citation_workflow],
        mcp_families={},
    )

    assert resolution.missing_optional == ("github",)
    assert "citation_workflow" in resolution.effective_tools


def test_skill_can_request_non_web_mcp_family():
    manifest = {"tools": {"optional": {"mcp_families": ["github"]}}}

    resolution = resolve_skill_tool_access(
        manifest, ALL_TOOLS, mcp_families=MCP_FAMILIES
    )

    assert "github_search" in resolution.effective_tools
    assert resolution.skill_tools == ("github_search",)
