"""Smoke test for LangGraph assembly."""

from langchain_core.messages import AIMessage


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
