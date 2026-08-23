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


@tool("citation_workflow")
def _citation_workflow(action: str) -> str:
    """Citation workflow."""
    return action


@pytest.mark.parametrize(
    ("manifest", "tools", "families", "missing"),
    [
        pytest.param(
            {"tools": {"required": {"local": ["citation_workflow"]}}},
            [_read_file, _rag_search, _bash],
            {},
            "citation_workflow",
            id="local-tool",
        ),
        pytest.param(
            {"tools": {"required": {"mcp_families": ["github"]}}},
            [_read_file, _full_web_search],
            {"full-web-search": "web_search"},
            "github",
            id="mcp-family",
        ),
    ],
)
def test_missing_required_tool_blocks_activation(
    manifest,
    tools,
    families,
    missing,
):
    with pytest.raises(
        ValueError,
        match=f"required skill tools are unavailable: {missing}",
    ):
        resolve_skill_tool_access(manifest, tools, mcp_families=families)


def test_missing_optional_tool_does_not_block_activation():
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
