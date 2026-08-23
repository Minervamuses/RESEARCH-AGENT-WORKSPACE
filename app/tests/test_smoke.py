"""Smoke tests that should pass before and after the decoupling refactor."""

import pytest
from langchain_core.messages import AIMessage


def test_imports():
    """Core modules should import without circular or structural failures."""
    import rag
    import agent
    from agent.config import AgentConfig

    assert rag is not None
    assert agent is not None
    assert AgentConfig is not None
    assert {tool["name"] for tool in rag.TOOL_SCHEMAS} == {
        "rag_search",
        "rag_explore",
        "rag_list_chunks",
        "rag_get_context",
    }

    import agent.graph


@pytest.mark.parametrize("value", [1, 2, True, 3.5])
def test_agent_config_rejects_graph_limits_that_cannot_finalize(value):
    from agent.config import AgentConfig

    with pytest.raises(ValueError, match="greater than or equal to 3"):
        AgentConfig(graph_recursion_limit=value)


def test_agent_config_accepts_minimum_graph_limit():
    from agent.config import AgentConfig

    assert AgentConfig(graph_recursion_limit=3).graph_recursion_limit == 3


def test_agent_config_runs_base_rag_validation():
    from agent.config import AgentConfig

    with pytest.raises(ValueError, match="chunk_size must be a positive integer"):
        AgentConfig(chunk_size=0)


def test_graph_builds_without_error(monkeypatch, tmp_path):
    """The graph should compile with real rag tools and a lightweight model."""
    from agent.graph import build_graph
    from agent.config import AgentConfig

    class DummyModel:
        def bind_tools(self, _tools):
            return self

        def invoke(self, _messages):
            return AIMessage(content="ok")

    monkeypatch.setattr("agent.graph.get_chat_model", lambda _config: DummyModel())

    cfg = AgentConfig(persist_dir=str(tmp_path))
    graph = build_graph(cfg)

    assert graph is not None
