"""Tests for graph skill state loading."""

from pathlib import Path
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from agent.config import AgentConfig
from agent.graph import build_graph
from agent.tools.access import ToolAccessResolution


class _DummyModel:
    def bind_tools(self, _tools):
        return self

    def invoke(self, _messages):
        return AIMessage(content="ok")


@tool("rag_explore")
def _rag_explore() -> str:
    """Explore."""
    return "explore"


@tool("rag_search")
def _rag_search(query: str) -> str:
    """Search."""
    return query


@tool("rag_get_context")
def _rag_get_context(pid: str, chunk_id: int) -> str:
    """Context."""
    return f"{pid}:{chunk_id}"


@tool("recall_history")
def _recall_history(query: str) -> str:
    """Recall."""
    return query


def _patch_graph_tools(monkeypatch):
    monkeypatch.setattr("agent.graph.get_chat_model", lambda _cfg: _DummyModel())
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools",
        lambda _cfg: [_rag_explore, _rag_search, _rag_get_context],
    )
    monkeypatch.setattr(
        "agent.tools.inventory.create_history_tool",
        lambda _cfg, store=None: _recall_history,
    )


def _resolution(effective, skill=()):
    effective = tuple(effective)
    skill = tuple(skill)
    return ToolAccessResolution(
        global_tools=tuple(name for name in effective if name not in set(skill)),
        skill_tools=skill,
        effective_tools=effective,
        missing_required=(),
        missing_optional=(),
    )


def test_skill_loader_no_skill_is_noop(monkeypatch, tmp_path):
    _patch_graph_tools(monkeypatch)
    cfg = AgentConfig(persist_dir=str(tmp_path))
    graph = build_graph(cfg, skill_runtime_getter=lambda: None)

    result = graph.invoke({"messages": [HumanMessage(content="hi")]})

    assert "active_skill" not in result
    assert result["messages"][-1].content == "ok"


def test_skill_loader_populates_state_from_runtime(monkeypatch, tmp_path):
    _patch_graph_tools(monkeypatch)
    runtime = SimpleNamespace(
        name="paper-writing",
        root=Path(tmp_path / "skills" / "paper-writing"),
        instructions="# Skill",
        pinned_references={"references/guide.md": "guide"},
        task_mode="revision",
        tool_access=_resolution(["read_file"]),
    )
    cfg = AgentConfig(persist_dir=str(tmp_path))
    graph = build_graph(cfg, skill_runtime_getter=lambda: runtime)

    result = graph.invoke({"messages": [HumanMessage(content="hi")]})

    # The loader fills the complete serialized active-skill slice.
    serialized_keys = {
        "active_skill",
        "skill_root",
        "skill_instructions",
        "loaded_references",
        "task_mode",
        "effective_tools",
    }
    assert serialized_keys <= set(result)
    assert result["active_skill"] == "paper-writing"
    assert result["skill_root"] == str(runtime.root)
    assert result["skill_instructions"] == "# Skill"
    assert result["loaded_references"] == {"references/guide.md": "guide"}
    assert result["task_mode"] == "revision"
    assert result["effective_tools"] == ["read_file"]


def test_agent_node_binds_effective_tools_for_active_skill(monkeypatch, tmp_path):
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
    cfg = AgentConfig(persist_dir=str(tmp_path))
    graph = build_graph(cfg)
    state = {
        "messages": [HumanMessage(content="hi")],
        "active_skill": "paper-writing",
        "task_mode": "revision",
        "effective_tools": ["read_file"],
    }

    graph.invoke(state)
    graph.invoke(state)

    assert bind_calls[0] == [
        "rag_explore",
        "rag_search",
        "rag_get_context",
        "recall_history",
        "read_file",
        "bash",
    ]
    assert bind_calls[1] == ["read_file"]
    assert len(bind_calls) == 2


def test_agent_node_binding_preserves_universe_order(monkeypatch, tmp_path):
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
    cfg = AgentConfig(persist_dir=str(tmp_path))
    graph = build_graph(cfg)

    graph.invoke({
        "messages": [HumanMessage(content="hi")],
        "active_skill": "paper-writing",
        "effective_tools": ["read_file", "rag_explore", "recall_history"],
    })

    # The binding follows the tool-universe order, not the state list order.
    assert bind_calls[1] == ["rag_explore", "recall_history", "read_file"]


@tool("citation_workflow")
def _citation_workflow(action: str) -> str:
    """Skill-scoped workflow tool."""
    return action


@tool("github_search")
def _github_search(query: str) -> str:
    """GitHub MCP tool."""
    return query


@tool("full-web-search")
def _full_web_search(query: str) -> str:
    """Web search MCP tool."""
    return query


def test_default_binding_includes_web_mcp_but_not_other_families(
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

    monkeypatch.setattr("agent.graph.get_chat_model", lambda _cfg: RecordingModel())
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools",
        lambda _cfg: [_rag_explore, _rag_search, _rag_get_context],
    )
    monkeypatch.setattr(
        "agent.tools.inventory.create_history_tool",
        lambda _cfg, store=None: _recall_history,
    )
    cfg = AgentConfig(persist_dir=str(tmp_path))
    graph = build_graph(
        cfg,
        extra_tools=[_full_web_search, _github_search],
        skill_tools=[_citation_workflow],
        mcp_families={"full-web-search": "web_search", "github_search": "github"},
    )

    graph.invoke({"messages": [HumanMessage(content="hi")]})

    assert "full-web-search" in bind_calls[0]
    assert "github_search" not in bind_calls[0]
    assert "citation_workflow" not in bind_calls[0]


def test_skill_tools_bound_only_when_effective_tools_grant_them(
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

    monkeypatch.setattr("agent.graph.get_chat_model", lambda _cfg: RecordingModel())
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools",
        lambda _cfg: [_rag_explore, _rag_search, _rag_get_context],
    )
    monkeypatch.setattr(
        "agent.tools.inventory.create_history_tool",
        lambda _cfg, store=None: _recall_history,
    )
    cfg = AgentConfig(persist_dir=str(tmp_path))
    graph = build_graph(cfg, skill_tools=[_citation_workflow])

    # Normal mode: the default binding must not contain the skill tool.
    graph.invoke({"messages": [HumanMessage(content="hi")]})
    assert "citation_workflow" not in bind_calls[0]

    # Foreign skill: effective tools without the skill tool keep it out.
    graph.invoke({
        "messages": [HumanMessage(content="hi")],
        "active_skill": "paper-writing",
        "effective_tools": ["rag_search", "read_file"],
    })
    assert "citation_workflow" not in bind_calls[1]

    # Granting skill: the skill tool joins the global tools.
    graph.invoke({
        "messages": [HumanMessage(content="hi")],
        "active_skill": "citation",
        "effective_tools": [
            "rag_explore",
            "rag_search",
            "rag_get_context",
            "recall_history",
            "read_file",
            "bash",
            "citation_workflow",
        ],
    })
    assert bind_calls[2] == [
        "rag_explore",
        "rag_search",
        "rag_get_context",
        "recall_history",
        "read_file",
        "bash",
        "citation_workflow",
    ]


def test_skill_tool_name_collision_fails_fast(monkeypatch, tmp_path):
    import pytest

    _patch_graph_tools(monkeypatch)

    @tool("rag_search")
    def _imposter(query: str) -> str:
        """Colliding tool."""
        return query

    cfg = AgentConfig(persist_dir=str(tmp_path))
    with pytest.raises(ValueError, match="collide"):
        build_graph(cfg, skill_tools=[_imposter])


def test_agent_node_allows_more_than_legacy_primary_quota(monkeypatch, tmp_path):
    class LongRunningModel:
        def bind_tools(self, _tools):
            class Bound:
                def invoke(_self, messages):
                    completed = sum(isinstance(m, ToolMessage) for m in messages)
                    if completed >= 25:
                        return AIMessage(content="final answer")
                    return AIMessage(content="", tool_calls=[{
                        "name": "rag_search",
                        "args": {"query": str(completed)},
                        "id": f"search-{completed}",
                    }])

            return Bound()

        def invoke(self, _messages):
            raise AssertionError("repair model should not run")

    monkeypatch.setattr("agent.graph.get_chat_model", lambda _cfg: LongRunningModel())
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools",
        lambda _cfg: [_rag_explore, _rag_search, _rag_get_context],
    )
    monkeypatch.setattr(
        "agent.tools.inventory.create_history_tool",
        lambda _cfg, store=None: _recall_history,
    )
    cfg = AgentConfig(persist_dir=str(tmp_path))
    graph = build_graph(cfg)

    result = graph.invoke(
        {"messages": [HumanMessage(content="hi")]},
        config={"recursion_limit": cfg.graph_recursion_limit},
    )

    completed = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(completed) == 25
    assert result["messages"][-1].content == "final answer"


def test_agent_node_allows_more_than_legacy_citation_local_quota(
    monkeypatch, tmp_path
):
    class CitationNavigationModel:
        def bind_tools(self, _tools):
            class Bound:
                def invoke(_self, messages):
                    completed = sum(isinstance(m, ToolMessage) for m in messages)
                    if completed >= 5:
                        return AIMessage(content="done")
                    return AIMessage(content="", tool_calls=[{
                        "name": "citation_workflow",
                        "args": {"action": "sources"},
                        "id": f"source-{completed}",
                    }])

            return Bound()

        def invoke(self, _messages):
            raise AssertionError("repair model should not run")

    monkeypatch.setattr(
        "agent.graph.get_chat_model", lambda _cfg: CitationNavigationModel()
    )
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools",
        lambda _cfg: [_rag_explore, _rag_search, _rag_get_context],
    )
    monkeypatch.setattr(
        "agent.tools.inventory.create_history_tool",
        lambda _cfg, store=None: _recall_history,
    )
    graph = build_graph(
        AgentConfig(persist_dir=str(tmp_path)),
        skill_tools=[_citation_workflow],
    )

    result = graph.invoke({
        "messages": [HumanMessage(content="browse")],
        "active_skill": "citation",
        "skill_instructions": "use citation",
        "effective_tools": ["citation_workflow"],
    }, config={"recursion_limit": 16})

    completed = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(completed) == 5
    assert result["messages"][-1].content == "done"


def test_agent_node_strips_tool_calls_from_repair_response(monkeypatch, tmp_path):
    class InvalidRepairModel:
        def __init__(self):
            self.raw_calls = 0

        def bind_tools(self, _tools):
            class Bound:
                def invoke(_self, _messages):
                    return AIMessage(content='rag_search(query="x")')

            return Bound()

        def invoke(self, _messages):
            self.raw_calls += 1
            return AIMessage(content="repair tried tool", tool_calls=[{
                "name": "rag_search",
                "args": {"query": "x"},
                "id": "repair-search",
            }])

    model = InvalidRepairModel()
    monkeypatch.setattr("agent.graph.get_chat_model", lambda _cfg: model)
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools",
        lambda _cfg: [_rag_explore, _rag_search, _rag_get_context],
    )
    monkeypatch.setattr(
        "agent.tools.inventory.create_history_tool",
        lambda _cfg, store=None: _recall_history,
    )
    graph = build_graph(AgentConfig(persist_dir=str(tmp_path)))

    result = graph.invoke({"messages": [HumanMessage(content="hi")]})

    assert not [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert model.raw_calls == 1
    final = result["messages"][-1]
    assert final.response_metadata["turn_recovery"] == (
        "fallback:call_like_tool_protocol;repair:dropped_tool_calls"
    )
    assert not final.tool_calls


def test_agent_node_repairs_dsml_protocol_artifact(monkeypatch, tmp_path):
    class DsmlModel:
        def __init__(self):
            self.raw_calls = 0

        def bind_tools(self, _tools):
            class Bound:
                def invoke(_self, _messages):
                    return AIMessage(
                        content='citation_workflow(action="sources", page=5)'
                    )

            return Bound()

        def invoke(self, _messages):
            self.raw_calls += 1
            return AIMessage(content="I found one relevant result.")

    model = DsmlModel()
    monkeypatch.setattr("agent.graph.get_chat_model", lambda _cfg: model)
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools",
        lambda _cfg: [_rag_explore, _rag_search, _rag_get_context],
    )
    monkeypatch.setattr(
        "agent.tools.inventory.create_history_tool",
        lambda _cfg, store=None: _recall_history,
    )
    graph = build_graph(
        AgentConfig(persist_dir=str(tmp_path)),
        skill_tools=[_citation_workflow],
    )

    result = graph.invoke({
        "messages": [HumanMessage(content="find it")],
        "active_skill": "citation",
        "skill_instructions": "use citation",
        "effective_tools": ["citation_workflow"],
    })

    final = result["messages"][-1]
    assert final.content == "I found one relevant result."
    assert final.response_metadata["turn_recovery"].startswith("repaired:")
    assert model.raw_calls == 1


def test_agent_node_reports_persistent_blank_answers_honestly(
    monkeypatch, tmp_path
):
    class AlwaysBlankModel:
        def __init__(self):
            self.bound_invokes = 0
            self.raw_invokes = 0

        def bind_tools(self, _tools):
            model = self

            class Bound:
                def invoke(_self, _messages):
                    model.bound_invokes += 1
                    return AIMessage(content="   ")
            return Bound()

        def invoke(self, _messages):
            self.raw_invokes += 1
            return AIMessage(content="repair must not run")

    model = AlwaysBlankModel()
    monkeypatch.setattr("agent.graph.get_chat_model", lambda _cfg: model)
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools",
        lambda _cfg: [_rag_explore, _rag_search, _rag_get_context],
    )
    monkeypatch.setattr(
        "agent.tools.inventory.create_history_tool",
        lambda _cfg, store=None: _recall_history,
    )
    graph = build_graph(AgentConfig(persist_dir=str(tmp_path)))

    result = graph.invoke({"messages": [HumanMessage(content="hello")]})

    final = result["messages"][-1]
    # Truly empty replies are retried identically, then reported honestly;
    # the no-tool repair (which could invent an answer) never runs.
    assert final.response_metadata["turn_recovery"] == (
        "fallback:empty_model_response"
    )
    assert "empty responses" in final.content
    assert model.bound_invokes == 3
    assert model.raw_invokes == 0


def test_agent_node_repairs_structured_tool_content(monkeypatch, tmp_path):
    class StructuredContentModel:
        def bind_tools(self, _tools):
            class Bound:
                def invoke(_self, _messages):
                    return AIMessage(content=[{
                        "type": "tool_use",
                        "name": "citation_workflow",
                        "input": {"action": "list"},
                    }])

            return Bound()

        def invoke(self, _messages):
            return AIMessage(content="Recovered answer")

    monkeypatch.setattr(
        "agent.graph.get_chat_model", lambda _cfg: StructuredContentModel()
    )
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools",
        lambda _cfg: [_rag_explore, _rag_search, _rag_get_context],
    )
    monkeypatch.setattr(
        "agent.tools.inventory.create_history_tool",
        lambda _cfg, store=None: _recall_history,
    )
    graph = build_graph(
        AgentConfig(persist_dir=str(tmp_path)),
        skill_tools=[_citation_workflow],
    )

    result = graph.invoke({
        "messages": [HumanMessage(content="continue")],
        "active_skill": "citation",
        "skill_instructions": "use citation",
        "effective_tools": ["citation_workflow"],
    })

    final = result["messages"][-1]
    assert final.content == "Recovered answer"
    assert final.response_metadata["turn_recovery"] == (
        "repaired:structured_tool_content"
    )
