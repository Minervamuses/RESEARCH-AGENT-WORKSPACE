"""Regression tests for the academic-paper-writing skill's tool access."""

from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool

from agent.config import AgentConfig
from agent.graph import build_graph
from agent.skills.runtime import load_skill_runtime
from agent.tool_access import resolve_tool_access


APP_ROOT = Path(__file__).resolve().parents[1]


@tool("rag_explore")
def _rag_explore() -> str:
    """Explore the indexed knowledge base."""
    return "explore"


@tool("rag_search")
def _rag_search(query: str) -> str:
    """Search the indexed knowledge base."""
    return query


@tool("rag_get_context")
def _rag_get_context(pid: str, chunk_id: int) -> str:
    """Expand one search hit."""
    return f"{pid}:{chunk_id}"


@tool("recall_history")
def _recall_history(query: str) -> str:
    """Search persisted chat history."""
    return query


@tool("read_file")
def _read_file(path: str) -> str:
    """Read a text file."""
    return path


@tool("bash")
def _bash(command: str) -> str:
    """Run a shell command."""
    return command


@tool("full-web-search")
def _full_web_search(query: str) -> str:
    """Search the web."""
    return query


MCP_FAMILIES = {"full-web-search": "web_search"}


def _cfg(tmp_path) -> AgentConfig:
    return AgentConfig(
        persist_dir=str(tmp_path / "persist"),
        skills_dir=str(APP_ROOT / "skills"),
    )


def _all_tools() -> list:
    return [
        _rag_explore,
        _rag_search,
        _rag_get_context,
        _recall_history,
        _read_file,
        _bash,
        _full_web_search,
    ]


def test_writing_keeps_same_tools_as_normal_mode(tmp_path):
    normal = resolve_tool_access(None, _all_tools(), mcp_families=MCP_FAMILIES)

    runtime = load_skill_runtime(
        "academic-paper-writing",
        config=_cfg(tmp_path),
        all_tools=_all_tools(),
        mcp_families=MCP_FAMILIES,
    )

    assert runtime.tool_access.effective_tools == normal.effective_tools
    assert runtime.tool_access.skill_tools == ()
    assert "bash" in runtime.tool_access.effective_tools
    assert "full-web-search" in runtime.tool_access.effective_tools


def test_writing_activation_does_not_require_web_search(tmp_path):
    runtime = load_skill_runtime(
        "academic-paper-writing",
        config=_cfg(tmp_path),
        all_tools=[
            _rag_explore,
            _rag_search,
            _rag_get_context,
            _recall_history,
            _read_file,
            _bash,
        ],
        mcp_families={},
    )

    assert runtime.tool_access.missing_required == ()
    assert "full-web-search" not in runtime.tool_access.effective_tools


def test_academic_skill_writer_binding_matches_normal_mode(
    monkeypatch,
    tmp_path,
):
    bind_calls: list[list[str]] = []

    class RecordingModel:
        def bind_tools(self, tools):
            bind_calls.append([tool.name for tool in tools])

            class Bound:
                def invoke(self, _messages):
                    return AIMessage(content="ok")

            return Bound()

    runtime = load_skill_runtime(
        "academic-paper-writing",
        config=_cfg(tmp_path),
        all_tools=_all_tools()[:-1],  # local base tools only
    )

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

    graph = build_graph(_cfg(tmp_path), skill_runtime_getter=lambda: runtime)
    graph.invoke({
        "messages": [
            HumanMessage(
                content=(
                    "我一月上半的成果如果要寫成論文，abstract 重點是什麼？"
                    "我不記得了，你自行看一下。"
                )
            )
        ],
    })

    expected = [
        "rag_explore",
        "rag_search",
        "rag_get_context",
        "recall_history",
        "read_file",
        "bash",
    ]
    # The default binding and the active-skill binding are identical: the
    # writing skill adds no tools and removes none.
    assert bind_calls[0] == expected
    assert all(call == expected for call in bind_calls)
