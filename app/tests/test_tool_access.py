"""Pure contracts for the global/skill tool access resolver."""

import pytest
from langchain_core.tools import tool

from agent.tools.access import resolve_tool_access


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


@tool("clock_now")
def _clock_now() -> str:
    """Read a dynamic MCP clock."""
    return "now"


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


@pytest.mark.parametrize(
    ("manifest", "tools", "families", "expected"),
    [
        pytest.param(
            None,
            ALL_TOOLS,
            MCP_FAMILIES,
            (GLOBAL_NAMES, (), GLOBAL_NAMES, (), ()),
            id="normal-mode",
        ),
        pytest.param(
            {"resources": [], "task_modes": ["revision"]},
            ALL_TOOLS,
            MCP_FAMILIES,
            (GLOBAL_NAMES, (), GLOBAL_NAMES, (), ()),
            id="manifest-without-tools",
        ),
        pytest.param(
            {"tools": {"required": {"local": ["citation_workflow"]}}},
            ALL_TOOLS,
            MCP_FAMILIES,
            (
                GLOBAL_NAMES,
                ("citation_workflow",),
                (*GLOBAL_NAMES, "citation_workflow"),
                (),
                (),
            ),
            id="required-local",
        ),
        pytest.param(
            {"tools": {"optional": {"mcp_families": ["github"]}}},
            ALL_TOOLS,
            MCP_FAMILIES,
            (
                GLOBAL_NAMES,
                ("github_search",),
                (*GLOBAL_NAMES, "github_search"),
                (),
                (),
            ),
            id="optional-mcp-family",
        ),
        pytest.param(
            None,
            [_rag_search, _recall_history, _read_file, _bash],
            {},
            (
                ("rag_search", "recall_history", "read_file", "bash"),
                (),
                ("rag_search", "recall_history", "read_file", "bash"),
                (),
                (),
            ),
            id="web-search-absent",
        ),
        pytest.param(
            {"tools": {"required": {"local": ["citation_workflow"]}}},
            [_citation_workflow, _full_web_search, _bash, _rag_search],
            MCP_FAMILIES,
            (
                ("full-web-search", "bash", "rag_search"),
                ("citation_workflow",),
                ("citation_workflow", "full-web-search", "bash", "rag_search"),
                (),
                (),
            ),
            id="universe-order",
        ),
        pytest.param(
            {"tools": {"required": {"local": ["read_file"]}}},
            ALL_TOOLS,
            MCP_FAMILIES,
            (GLOBAL_NAMES, (), GLOBAL_NAMES, (), ()),
            id="global-request-not-duplicated",
        ),
    ],
)
def test_resolve_tool_access_selection(manifest, tools, families, expected):
    resolution = resolve_tool_access(manifest, tools, mcp_families=families)

    assert (
        resolution.global_tools,
        resolution.skill_tools,
        resolution.effective_tools,
        resolution.missing_required,
        resolution.missing_optional,
    ) == expected


@pytest.mark.parametrize(
    ("manifest", "tools", "families", "expected"),
    [
        pytest.param(
            {"tools": {"required": {"local": ["citation_workflow"]}}},
            [_rag_search, _bash],
            {},
            (("rag_search", "bash"), (), ("rag_search", "bash"), ("citation_workflow",), ()),
            id="missing-required-local",
        ),
        pytest.param(
            {"tools": {"required": {"mcp_families": ["github"]}}},
            [_rag_search, _full_web_search],
            {"full-web-search": "web_search"},
            (
                ("rag_search", "full-web-search"),
                (),
                ("rag_search", "full-web-search"),
                ("github",),
                (),
            ),
            id="missing-required-family",
        ),
        pytest.param(
            {
                "tools": {
                    "required": {"local": ["citation_workflow"]},
                    "optional": {"mcp_families": ["github"]},
                }
            },
            [_rag_search, _citation_workflow],
            {},
            (
                ("rag_search",),
                ("citation_workflow",),
                ("rag_search", "citation_workflow"),
                (),
                ("github",),
            ),
            id="missing-optional-separate",
        ),
    ],
)
def test_resolve_tool_access_missing_reporting(
    manifest,
    tools,
    families,
    expected,
):
    resolution = resolve_tool_access(manifest, tools, mcp_families=families)

    assert (
        resolution.global_tools,
        resolution.skill_tools,
        resolution.effective_tools,
        resolution.missing_required,
        resolution.missing_optional,
    ) == expected


@pytest.mark.parametrize(
    ("global_families", "expected_effective"),
    [
        pytest.param(None, ("rag_search",), id="family-scoped"),
        pytest.param(
            {"web_search", "clock"},
            ("rag_search", "clock_now"),
            id="family-globalized",
        ),
    ],
)
def test_resolve_tool_access_dynamic_global_family(
    global_families,
    expected_effective,
):
    resolution = resolve_tool_access(
        None,
        [_rag_search, _clock_now],
        mcp_families={"clock_now": "clock"},
        global_mcp_families=global_families,
    )

    assert resolution.effective_tools == expected_effective
