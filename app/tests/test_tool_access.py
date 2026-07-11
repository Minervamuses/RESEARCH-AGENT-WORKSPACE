"""Tests for the global/skill tool access resolver."""

from langchain_core.tools import tool

from agent.tool_access import resolve_tool_access


@tool("rag_search")
def _rag_search(query: str) -> str:
    """Search RAG."""
    return query


@tool("recall_history")
def _recall_history(query: str) -> str:
    """Recall history."""
    return query


@tool("read_file")
def _read_file(path: str) -> str:
    """Read a file."""
    return path


@tool("bash")
def _bash(command: str) -> str:
    """Run shell."""
    return command


@tool("full-web-search")
def _full_web_search(query: str) -> str:
    """Search the web."""
    return query


@tool("github_search")
def _github_search(query: str) -> str:
    """Search GitHub."""
    return query


@tool("citation_workflow")
def _citation_workflow(action: str) -> str:
    """Citation workflow."""
    return action


ALL_TOOLS = [
    _rag_search,
    _recall_history,
    _read_file,
    _bash,
    _full_web_search,
    _github_search,
    _citation_workflow,
]

MCP_FAMILIES = {"full-web-search": "web_search", "github_search": "github"}

GLOBAL_NAMES = (
    "rag_search",
    "recall_history",
    "read_file",
    "bash",
    "full-web-search",
)


def test_normal_mode_gets_base_and_web_tools():
    resolution = resolve_tool_access(None, ALL_TOOLS, mcp_families=MCP_FAMILIES)

    assert resolution.global_tools == GLOBAL_NAMES
    assert resolution.skill_tools == ()
    assert resolution.effective_tools == GLOBAL_NAMES
    assert resolution.missing_required == ()
    assert resolution.missing_optional == ()


def test_non_web_mcp_is_not_global():
    resolution = resolve_tool_access(None, ALL_TOOLS, mcp_families=MCP_FAMILIES)

    assert "github_search" not in resolution.effective_tools
    assert "citation_workflow" not in resolution.effective_tools


def test_manifest_without_tools_section_keeps_global_tools():
    manifest = {"resources": [], "task_modes": ["revision"]}

    resolution = resolve_tool_access(manifest, ALL_TOOLS, mcp_families=MCP_FAMILIES)

    assert resolution.effective_tools == GLOBAL_NAMES
    assert resolution.skill_tools == ()


def test_required_local_skill_tool_is_added_to_global_tools():
    manifest = {"tools": {"required": {"local": ["citation_workflow"]}}}

    resolution = resolve_tool_access(manifest, ALL_TOOLS, mcp_families=MCP_FAMILIES)

    assert resolution.skill_tools == ("citation_workflow",)
    assert resolution.effective_tools == (*GLOBAL_NAMES, "citation_workflow")
    assert resolution.missing_required == ()


def test_skill_can_request_non_web_mcp_family():
    manifest = {"tools": {"optional": {"mcp_families": ["github"]}}}

    resolution = resolve_tool_access(manifest, ALL_TOOLS, mcp_families=MCP_FAMILIES)

    assert "github_search" in resolution.effective_tools
    assert resolution.skill_tools == ("github_search",)
    assert resolution.missing_optional == ()


def test_missing_required_local_tool_is_reported():
    manifest = {"tools": {"required": {"local": ["citation_workflow"]}}}

    resolution = resolve_tool_access(
        manifest,
        [_rag_search, _bash],
        mcp_families={},
    )

    assert resolution.missing_required == ("citation_workflow",)
    assert resolution.effective_tools == ("rag_search", "bash")


def test_missing_required_mcp_family_is_reported():
    manifest = {"tools": {"required": {"mcp_families": ["github"]}}}

    resolution = resolve_tool_access(
        manifest,
        [_rag_search, _full_web_search],
        mcp_families={"full-web-search": "web_search"},
    )

    assert resolution.missing_required == ("github",)


def test_missing_optional_tool_is_reported_separately():
    manifest = {
        "tools": {
            "required": {"local": ["citation_workflow"]},
            "optional": {"mcp_families": ["github"]},
        }
    }

    resolution = resolve_tool_access(
        manifest,
        [_rag_search, _citation_workflow],
        mcp_families={},
    )

    assert resolution.missing_required == ()
    assert resolution.missing_optional == ("github",)
    assert resolution.effective_tools == ("rag_search", "citation_workflow")


def test_web_search_absent_from_universe_is_simply_not_included():
    resolution = resolve_tool_access(
        None,
        [_rag_search, _recall_history, _read_file, _bash],
        mcp_families={},
    )

    assert resolution.effective_tools == (
        "rag_search",
        "recall_history",
        "read_file",
        "bash",
    )


def test_effective_tools_preserve_universe_order():
    reordered = [_citation_workflow, _full_web_search, _bash, _rag_search]
    manifest = {"tools": {"required": {"local": ["citation_workflow"]}}}

    resolution = resolve_tool_access(manifest, reordered, mcp_families=MCP_FAMILIES)

    assert resolution.effective_tools == (
        "citation_workflow",
        "full-web-search",
        "bash",
        "rag_search",
    )


def test_skill_request_for_global_tool_does_not_duplicate_it():
    manifest = {"tools": {"required": {"local": ["read_file"]}}}

    resolution = resolve_tool_access(manifest, ALL_TOOLS, mcp_families=MCP_FAMILIES)

    assert resolution.skill_tools == ()
    assert resolution.effective_tools == GLOBAL_NAMES
