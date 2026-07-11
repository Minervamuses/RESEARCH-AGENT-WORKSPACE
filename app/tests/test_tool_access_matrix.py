"""Acceptance matrix for the global/skill tool access model.

Exercises the plan's acceptance matrix over one tool universe:

    rag_search, recall_history, read_file, bash,
    full-web-search (web_search family),
    github_search (github family),
    citation_workflow (skill tool)

and verifies that prompt rendering, graph binding, the fusion proposer
intersection, and PolicyToolNode all agree with the shared resolution.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from conftest import FakeHistoryStore, make_astream_graph

from agent.config import AgentConfig
from agent.graph import build_graph
from agent.fusion import FUSION_READ_ONLY_ALLOWLIST
from agent.session import ChatSession
from agent.skills.runtime import load_skill_runtime
from agent.tool_access import resolve_tool_access


APP_ROOT = Path(__file__).resolve().parents[1]


@tool("rag_explore")
def _rag_explore() -> str:
    """Explore the knowledge base."""
    return "explore"


@tool("rag_search")
def _rag_search(query: str) -> str:
    """Search the knowledge base."""
    return query


@tool("rag_get_context")
def _rag_get_context(pid: str, chunk_id: int) -> str:
    """Expand one search hit."""
    return f"{pid}:{chunk_id}"


@tool("recall_history")
def _recall_history(query: str) -> str:
    """Search chat history."""
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


MCP_FAMILIES = {"full-web-search": "web_search", "github_search": "github"}

UNIVERSE = [
    _rag_search,
    _recall_history,
    _read_file,
    _bash,
    _full_web_search,
    _github_search,
    _citation_workflow,
]

NORMAL_MODE_TOOLS = (
    "rag_search",
    "recall_history",
    "read_file",
    "bash",
    "full-web-search",
)


def _cfg(tmp_path) -> AgentConfig:
    return AgentConfig(
        persist_dir=str(tmp_path / "persist"),
        skills_dir=str(APP_ROOT / "skills"),
    )


# --- Matrix rows -----------------------------------------------------------


def test_normal_mode_matches_expected_matrix():
    resolution = resolve_tool_access(None, UNIVERSE, mcp_families=MCP_FAMILIES)

    assert resolution.effective_tools == NORMAL_MODE_TOOLS


def test_citation_adds_only_citation_workflow(tmp_path):
    runtime = load_skill_runtime(
        "citation",
        config=_cfg(tmp_path),
        all_tools=UNIVERSE,
        mcp_families=MCP_FAMILIES,
    )

    assert runtime.tool_access.effective_tools == (
        *NORMAL_MODE_TOOLS,
        "citation_workflow",
    )
    assert "github_search" not in runtime.tool_access.effective_tools


def test_writing_matches_normal_mode(tmp_path):
    runtime = load_skill_runtime(
        "academic-paper-writing",
        config=_cfg(tmp_path),
        all_tools=UNIVERSE,
        mcp_families=MCP_FAMILIES,
    )

    assert runtime.tool_access.effective_tools == NORMAL_MODE_TOOLS


def test_web_mcp_not_loaded_keeps_skills_usable_without_web(tmp_path):
    universe = [tool for tool in UNIVERSE if tool.name != "full-web-search"]

    citation = load_skill_runtime(
        "citation",
        config=_cfg(tmp_path),
        all_tools=universe,
        mcp_families={"github_search": "github"},
    )
    writing = load_skill_runtime(
        "academic-paper-writing",
        config=_cfg(tmp_path),
        all_tools=universe,
        mcp_families={"github_search": "github"},
    )

    for runtime in (citation, writing):
        assert "full-web-search" not in runtime.tool_access.effective_tools
        assert runtime.tool_access.missing_required == ()


def test_missing_citation_workflow_blocks_activation(tmp_path):
    universe = [tool for tool in UNIVERSE if tool.name != "citation_workflow"]

    with pytest.raises(
        ValueError,
        match="required skill tools are unavailable: citation_workflow",
    ):
        load_skill_runtime(
            "citation",
            config=_cfg(tmp_path),
            all_tools=universe,
            mcp_families=MCP_FAMILIES,
        )


# --- Consumer consistency ---------------------------------------------------


def _make_session(monkeypatch, tmp_path) -> ChatSession:
    monkeypatch.setattr("agent.session.find_app_root", lambda: tmp_path)
    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _cfg, extra_tools=None, history_store=None, **kwargs: make_astream_graph(),
    )
    return ChatSession(
        _cfg(tmp_path),
        extra_tools=[
            SimpleNamespace(name="full-web-search"),
            SimpleNamespace(name="github_search"),
        ],
        history_store=FakeHistoryStore(),
        web_search_tool_names={"full-web-search"},
        mcp_families=dict(MCP_FAMILIES),
    )


def test_prompt_matches_effective_tools(monkeypatch, tmp_path):
    session = _make_session(monkeypatch, tmp_path)
    session.activate_skill("citation")

    block = session._tool_availability_block()
    available_line = next(
        line for line in block.splitlines() if line.startswith("available_tools:")
    )

    # Web MCP tools collapse to their family; the skill tool renders as-is.
    assert "MCP family: web_search" in available_line
    assert "citation_workflow" in available_line
    for name in ("rag_search", "recall_history", "read_file", "bash"):
        assert name in available_line
    assert "github" not in available_line
    unavailable_line = next(
        line for line in block.splitlines() if line.startswith("unavailable_tools:")
    )
    assert "MCP family: github" in unavailable_line


def test_prompt_does_not_claim_web_search_when_mcp_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("agent.session.find_app_root", lambda: tmp_path)
    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _cfg, extra_tools=None, history_store=None, **kwargs: make_astream_graph(),
    )
    session = ChatSession(_cfg(tmp_path), history_store=FakeHistoryStore())

    block = session._tool_availability_block()

    assert "web_search" not in block
    assert "full-web-search" not in block


def test_fusion_matches_effective_tools(monkeypatch, tmp_path):
    session = _make_session(monkeypatch, tmp_path)
    session.activate_skill("citation")

    state = session._fusion._proposer_read_only_state()
    effective = set(session.tool_access_resolution().effective_tools)

    assert state["effective_tools"] == [
        name for name in FUSION_READ_ONLY_ALLOWLIST if name in effective
    ]
    assert "bash" not in state["effective_tools"]
    assert "citation_workflow" not in state["effective_tools"]


def test_graph_binding_matches_effective_tools(monkeypatch, tmp_path):
    bind_calls: list[list[str]] = []

    class RecordingModel:
        def bind_tools(self, tools):
            bind_calls.append([tool.name for tool in tools])

            class Bound:
                def invoke(self, _messages):
                    return AIMessage(content="ok")

            return Bound()

    monkeypatch.setattr("agent.graph.get_chat_model", lambda _cfg: RecordingModel())
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools",
        lambda _cfg: [_rag_explore, _rag_search, _rag_get_context],
    )
    monkeypatch.setattr(
        "agent.tools.inventory.create_history_tool",
        lambda _cfg, store=None: _recall_history,
    )
    monkeypatch.setattr("agent.tools.inventory.create_read_file_tool", lambda _cfg: _read_file)
    monkeypatch.setattr("agent.tools.inventory.create_bash_tool", lambda _cfg: _bash)

    graph = build_graph(
        _cfg(tmp_path),
        extra_tools=[_full_web_search, _github_search],
        skill_tools=[_citation_workflow],
        mcp_families=MCP_FAMILIES,
    )
    universe = [
        _rag_explore, _rag_search, _rag_get_context, _recall_history,
        _read_file, _bash, _full_web_search, _github_search, _citation_workflow,
    ]
    citation = load_skill_runtime(
        "citation",
        config=_cfg(tmp_path),
        all_tools=universe,
        mcp_families=MCP_FAMILIES,
    )

    graph.invoke({
        "messages": [HumanMessage(content="hi")],
        "active_skill": "citation",
        "effective_tools": list(citation.tool_access.effective_tools),
    })

    # Default binding = normal mode; skill binding = the citation resolution.
    assert bind_calls[0] == [
        "rag_explore", "rag_search", "rag_get_context", "recall_history",
        "read_file", "bash", "full-web-search",
    ]
    assert bind_calls[1] == list(citation.tool_access.effective_tools)
    assert "github_search" not in bind_calls[1]


def test_policy_tool_node_matches_effective_tools(monkeypatch, tmp_path):
    executed: list[str] = []

    @tool("citation_workflow")
    def _recording_workflow(action: str) -> str:
        """Citation workflow."""
        executed.append(action)
        return f"did {action}"

    class ScriptedModel:
        def bind_tools(self, _tools):
            model = self

            class Bound:
                def invoke(self, messages):
                    if any(isinstance(m, ToolMessage) for m in messages):
                        return AIMessage(content="done")
                    return AIMessage(
                        content="",
                        tool_calls=[{
                            "name": "citation_workflow",
                            "args": {"action": "search"},
                            "id": "call-1",
                        }],
                    )

            return Bound()

        def invoke(self, messages):
            return AIMessage(content="done")

    monkeypatch.setattr("agent.graph.get_chat_model", lambda _cfg: ScriptedModel())
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools",
        lambda _cfg: [_rag_explore, _rag_search, _rag_get_context],
    )
    monkeypatch.setattr(
        "agent.tools.inventory.create_history_tool",
        lambda _cfg, store=None: _recall_history,
    )
    monkeypatch.setattr("agent.tools.inventory.create_read_file_tool", lambda _cfg: _read_file)
    monkeypatch.setattr("agent.tools.inventory.create_bash_tool", lambda _cfg: _bash)

    graph = build_graph(_cfg(tmp_path), skill_tools=[_recording_workflow])

    # Normal mode: the forged citation_workflow call is denied, not executed.
    result = graph.invoke(
        {"messages": [HumanMessage(content="hi")]},
        config={"recursion_limit": 8},
    )
    denial = next(m for m in result["messages"] if isinstance(m, ToolMessage))
    assert denial.status == "error"
    assert "tool not available" in denial.content
    assert executed == []

    # Citation effective tools: the same call executes.
    result = graph.invoke(
        {
            "messages": [HumanMessage(content="hi")],
            "active_skill": "citation",
            "effective_tools": [
                "rag_explore", "rag_search", "rag_get_context", "recall_history",
                "read_file", "bash", "citation_workflow",
            ],
        },
        config={"recursion_limit": 8},
    )
    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert tool_messages[-1].content == "did search"
    assert executed == ["search"]


def test_skill_switch_does_not_change_bash_permission_mode(monkeypatch, tmp_path):
    """Bash keeps its per-call approval gate in normal mode and under skills.

    In a non-interactive test run the gate auto-denies, so an approved-run
    result in any mode would mean skill activation bypassed the gate.
    """

    class BashCallingModel:
        def bind_tools(self, _tools):
            class Bound:
                def invoke(self, messages):
                    if any(isinstance(m, ToolMessage) for m in messages):
                        return AIMessage(content="done")
                    return AIMessage(
                        content="",
                        tool_calls=[{
                            "name": "bash",
                            "args": {"command": "echo hi", "description": "say hi"},
                            "id": "call-1",
                        }],
                    )

            return Bound()

        def invoke(self, messages):
            return AIMessage(content="done")

    monkeypatch.setattr("agent.graph.get_chat_model", lambda _cfg: BashCallingModel())
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools",
        lambda _cfg: [_rag_explore, _rag_search, _rag_get_context],
    )
    monkeypatch.setattr(
        "agent.tools.inventory.create_history_tool",
        lambda _cfg, store=None: _recall_history,
    )
    # read_file faked; bash stays the real gated tool.
    monkeypatch.setattr("agent.tools.inventory.create_read_file_tool", lambda _cfg: _read_file)

    graph = build_graph(_cfg(tmp_path))

    states = [
        {"messages": [HumanMessage(content="hi")]},
        {
            "messages": [HumanMessage(content="hi")],
            "active_skill": "citation",
            "effective_tools": [
                "rag_explore", "rag_search", "rag_get_context", "recall_history",
                "read_file", "bash", "citation_workflow",
            ],
        },
    ]
    for state in states:
        result = graph.invoke(state, config={"recursion_limit": 8})
        bash_message = next(
            m for m in result["messages"]
            if isinstance(m, ToolMessage) and m.name == "bash"
        )
        assert '"approved": false' in bash_message.content
