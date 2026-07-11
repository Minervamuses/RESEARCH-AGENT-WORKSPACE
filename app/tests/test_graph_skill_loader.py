"""Tests for graph skill state loading."""

from pathlib import Path
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from agent.config import AgentConfig
from agent.graph import _budget_class, build_graph
from agent.tool_access import ToolAccessResolution


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


def test_budget_class_treats_read_only_citation_actions_as_local():
    for action in (
        "list", "show", "status", "explain", "sources", "source", "refine",
        "cancel",
    ):
        assert _budget_class("citation_workflow", {"action": action}) == "local"

    assert _budget_class("citation_workflow", {"action": "search"}) == "primary"
    assert _budget_class("citation_workflow", {}) == "primary"
    assert _budget_class("bash", {"action": "explain"}) == "primary"


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


def test_agent_node_forces_answer_after_tool_budget(monkeypatch, tmp_path):
    class BudgetModel:
        def __init__(self):
            self.bound_calls: list[list] = []
            self.raw_calls: list[list] = []

        def bind_tools(self, _tools):
            model = self

            class Bound:
                def invoke(self, messages):
                    model.bound_calls.append(messages)
                    return AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "rag_search",
                                "args": {"query": "x"},
                                "id": "call-1",
                            }
                        ],
                    )

            return Bound()

        def invoke(self, messages):
            self.raw_calls.append(messages)
            return AIMessage(content="final answer")

    model = BudgetModel()
    monkeypatch.setattr("agent.graph.get_chat_model", lambda _cfg: model)
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools",
        lambda _cfg: [_rag_explore, _rag_search, _rag_get_context],
    )
    monkeypatch.setattr(
        "agent.tools.inventory.create_history_tool",
        lambda _cfg, store=None: _recall_history,
    )
    cfg = AgentConfig(persist_dir=str(tmp_path), agent_max_tool_interactions=1)
    graph = build_graph(cfg)

    result = graph.invoke(
        {"messages": [HumanMessage(content="hi")]},
        config={"recursion_limit": 8},
    )

    assert result["messages"][-1].content == "final answer"
    assert len(model.bound_calls) == 1
    assert len(model.raw_calls) == 1
    assert any(
        "Both budgets are exhausted" in message.content
        for message in model.raw_calls[0]
    )


def test_agent_node_caps_parallel_tool_calls_to_budget(monkeypatch, tmp_path):
    """A round emitting more parallel calls than the remaining budget is trimmed
    so the per-turn tool count cannot overshoot the limit."""

    class OvershootModel:
        def __init__(self):
            self.bound_calls: list[list] = []
            self.raw_calls: list[list] = []

        def bind_tools(self, _tools):
            model = self

            class Bound:
                def invoke(self, messages):
                    model.bound_calls.append(messages)
                    return AIMessage(
                        content="",
                        tool_calls=[
                            {"name": "rag_search", "args": {"query": "a"}, "id": "call-1"},
                            {"name": "rag_search", "args": {"query": "b"}, "id": "call-2"},
                            {"name": "rag_search", "args": {"query": "c"}, "id": "call-3"},
                        ],
                    )

            return Bound()

        def invoke(self, messages):
            self.raw_calls.append(messages)
            return AIMessage(content="final answer")

    model = OvershootModel()
    monkeypatch.setattr("agent.graph.get_chat_model", lambda _cfg: model)
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools",
        lambda _cfg: [_rag_explore, _rag_search, _rag_get_context],
    )
    monkeypatch.setattr(
        "agent.tools.inventory.create_history_tool",
        lambda _cfg, store=None: _recall_history,
    )
    cfg = AgentConfig(persist_dir=str(tmp_path), agent_max_tool_interactions=1)
    graph = build_graph(cfg)

    result = graph.invoke(
        {"messages": [HumanMessage(content="hi")]},
        config={"recursion_limit": 8},
    )

    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    # model emitted 3 parallel calls but budget was 1 -> capped to a single call
    assert len(tool_messages) == 1
    assert result["messages"][-1].content == "final answer"


def test_agent_node_never_exceeds_cap_across_multiple_rounds(monkeypatch, tmp_path):
    """Across several rounds, each emitting extra parallel calls, the per-turn
    tool count must never exceed agent_max_tool_interactions."""

    class GreedyModel:
        def __init__(self):
            self.bound_calls: list[list] = []
            self.raw_calls: list[list] = []

        def bind_tools(self, _tools):
            model = self

            class Bound:
                def invoke(self, messages):
                    model.bound_calls.append(messages)
                    # Always asks for two parallel searches every round.
                    return AIMessage(
                        content="",
                        tool_calls=[
                            {"name": "rag_search", "args": {"query": "a"}, "id": f"a{len(model.bound_calls)}"},
                            {"name": "rag_search", "args": {"query": "b"}, "id": f"b{len(model.bound_calls)}"},
                        ],
                    )

            return Bound()

        def invoke(self, messages):
            self.raw_calls.append(messages)
            return AIMessage(content="final answer")

    model = GreedyModel()
    monkeypatch.setattr("agent.graph.get_chat_model", lambda _cfg: model)
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools",
        lambda _cfg: [_rag_explore, _rag_search, _rag_get_context],
    )
    monkeypatch.setattr(
        "agent.tools.inventory.create_history_tool",
        lambda _cfg, store=None: _recall_history,
    )
    cfg = AgentConfig(persist_dir=str(tmp_path), agent_max_tool_interactions=3)
    graph = build_graph(cfg)

    result = graph.invoke(
        {"messages": [HumanMessage(content="hi")]},
        config={"recursion_limit": 16},
    )

    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    # Round 1 runs 2 of 3; round 2 is capped to the remaining 1; then exhausted.
    assert len(tool_messages) == 3
    assert result["messages"][-1].content == "final answer"


def test_agent_node_strips_tool_calls_from_exhausted_raw_model(monkeypatch, tmp_path):
    """The exhausted path uses an unbound model, but any returned tool calls must
    still be dropped so the budget is enforced mechanically."""

    class RawToolCallModel:
        def __init__(self):
            self.bound_calls: list[list] = []
            self.raw_calls: list[list] = []

        def bind_tools(self, _tools):
            model = self

            class Bound:
                def invoke(self, messages):
                    model.bound_calls.append(messages)
                    return AIMessage(
                        content="",
                        tool_calls=[
                            {"name": "rag_search", "args": {"query": "a"}, "id": "call-1"},
                        ],
                    )

            return Bound()

        def invoke(self, messages):
            self.raw_calls.append(messages)
            return AIMessage(
                content="raw tried tool",
                tool_calls=[
                    {"name": "rag_search", "args": {"query": "b"}, "id": "call-2"},
                ],
            )

    model = RawToolCallModel()
    monkeypatch.setattr("agent.graph.get_chat_model", lambda _cfg: model)
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools",
        lambda _cfg: [_rag_explore, _rag_search, _rag_get_context],
    )
    monkeypatch.setattr(
        "agent.tools.inventory.create_history_tool",
        lambda _cfg, store=None: _recall_history,
    )
    cfg = AgentConfig(persist_dir=str(tmp_path), agent_max_tool_interactions=1)
    graph = build_graph(cfg)

    result = graph.invoke(
        {"messages": [HumanMessage(content="hi")]},
        config={"recursion_limit": 8},
    )

    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert len(model.bound_calls) == 1
    # The first raw response is invalid because its structured call was
    # dropped. One raw repair is attempted, then deterministic fallback wins.
    assert len(model.raw_calls) == 2
    assert "could not produce a final summary" in result["messages"][-1].content
    assert not result["messages"][-1].tool_calls


def test_agent_node_repairs_dsml_after_budget_exhaustion(monkeypatch, tmp_path):
    class DsmlModel:
        def __init__(self):
            self.raw_calls = 0

        def bind_tools(self, _tools):
            class Bound:
                def invoke(_self, _messages):
                    return AIMessage(
                        content="",
                        tool_calls=[{
                            "name": "rag_search",
                            "args": {"query": "x"},
                            "id": "search-1",
                        }],
                    )
            return Bound()

        def invoke(self, _messages):
            self.raw_calls += 1
            if self.raw_calls == 1:
                return AIMessage(
                    content='citation_workflow(action="list", page=5)'
                )
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
        AgentConfig(
            persist_dir=str(tmp_path),
            agent_max_tool_interactions=1,
            agent_max_local_tool_interactions=0,
        ),
        skill_tools=[_citation_workflow],
    )

    result = graph.invoke(
        {
            "messages": [HumanMessage(content="find it")],
            "active_skill": "citation",
            "skill_instructions": "use citation",
            "effective_tools": ["rag_search", "citation_workflow"],
        },
        config={"recursion_limit": 8},
    )

    final = result["messages"][-1]
    assert final.content == "I found one relevant result."
    assert final.response_metadata["turn_recovery"].startswith("repaired:")
    assert model.raw_calls == 2


def test_agent_node_repairs_non_exhausted_blank_answer(monkeypatch, tmp_path):
    class BlankThenRepairModel:
        def bind_tools(self, _tools):
            class Bound:
                def invoke(_self, _messages):
                    return AIMessage(content="   ")
            return Bound()

        def invoke(self, _messages):
            return AIMessage(content="Recovered answer")

    monkeypatch.setattr(
        "agent.graph.get_chat_model", lambda _cfg: BlankThenRepairModel()
    )
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

    assert result["messages"][-1].content == "Recovered answer"
    assert result["messages"][-1].response_metadata["turn_recovery"] == (
        "repaired:empty_final_answer"
    )


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


def test_primary_and_local_tool_budgets_are_independent(monkeypatch, tmp_path):
    class MixedBudgetModel:
        def bind_tools(self, _tools):
            class Bound:
                def invoke(_self, messages):
                    completed = sum(isinstance(m, ToolMessage) for m in messages)
                    suffix = str(completed)
                    return AIMessage(content="", tool_calls=[
                        {
                            "name": "rag_search",
                            "args": {"query": suffix},
                            "id": f"primary-{suffix}",
                        },
                        {
                            "name": "citation_workflow",
                            "args": {"action": "list"},
                            "id": f"local-{suffix}",
                        },
                    ])
            return Bound()

        def invoke(self, _messages):
            return AIMessage(content="done")

    monkeypatch.setattr("agent.graph.get_chat_model", lambda _cfg: MixedBudgetModel())
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools",
        lambda _cfg: [_rag_explore, _rag_search, _rag_get_context],
    )
    monkeypatch.setattr(
        "agent.tools.inventory.create_history_tool",
        lambda _cfg, store=None: _recall_history,
    )
    graph = build_graph(
        AgentConfig(
            persist_dir=str(tmp_path),
            agent_max_tool_interactions=1,
            agent_max_local_tool_interactions=2,
        ),
        skill_tools=[_citation_workflow],
    )

    result = graph.invoke({
        "messages": [HumanMessage(content="browse")],
        "active_skill": "citation",
        "skill_instructions": "use citation",
        "effective_tools": ["rag_search", "citation_workflow"],
    }, config={"recursion_limit": 12})

    completed = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert [m.name for m in completed].count("rag_search") == 1
    assert [m.name for m in completed].count("citation_workflow") == 2
    assert result["messages"][-1].content == "done"
