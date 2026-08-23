"""Authentic graph execution for persisted-history recall."""

import json

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.config import AgentConfig
from agent.graph import build_graph


class _RecordingHistorySearch:
    def __init__(self):
        self.calls: list[tuple[str, int, str | None]] = []

    def search(self, query: str, k: int = 5, role: str | None = None):
        self.calls.append((query, k, role))
        return [Document(
            page_content="trained the January model",
            metadata={
                "role": "assistant",
                "turn_id": 7,
                "timestamp": "2026-01-15T00:00:00+00:00",
            },
        )]


class _HistoryAwareModel:
    def __init__(self):
        self.bound_tool_names: list[list[str]] = []
        self.observed_tool_message: ToolMessage | None = None

    def bind_tools(self, tools):
        self.bound_tool_names.append([tool.name for tool in tools])
        return self

    def invoke(self, messages):
        recall_results = [
            message
            for message in messages
            if isinstance(message, ToolMessage) and message.name == "recall_history"
        ]
        if not recall_results:
            return AIMessage(
                content="",
                tool_calls=[{
                    "name": "recall_history",
                    "args": {
                        "query": "January progress",
                        "k": 2,
                        "role": "assistant",
                    },
                    "id": "recall-1",
                }],
            )

        tool_message = recall_results[-1]
        payload = json.loads(tool_message.content)
        if payload != [{
            "role": "assistant",
            "text": "trained the January model",
            "turn_id": 7,
            "timestamp": "2026-01-15T00:00:00+00:00",
        }]:
            raise AssertionError("model did not receive the production history payload")
        self.observed_tool_message = tool_message
        return AIMessage(content=f"Earlier record: {payload[0]['text']}")


def test_build_graph_executes_history_tool_and_model_reads_tool_result(
    monkeypatch,
    tmp_path,
):
    model = _HistoryAwareModel()
    history_search = _RecordingHistorySearch()
    monkeypatch.setattr("agent.graph.get_chat_model", lambda _config: model)
    config = AgentConfig(
        persist_dir=str(tmp_path / "store"),
        graph_recursion_limit=8,
    )

    graph = build_graph(config, history_store=history_search)
    result = graph.invoke(
        {"messages": [HumanMessage(content="What did we finish in January?")]},
        config={"recursion_limit": 8},
    )

    assert history_search.calls == [("January progress", 2, "assistant")]
    assert "recall_history" in model.bound_tool_names[0]
    tool_message = next(
        message
        for message in result["messages"]
        if isinstance(message, ToolMessage) and message.name == "recall_history"
    )
    assert tool_message.tool_call_id == "recall-1"
    assert tool_message.status == "success"
    assert model.observed_tool_message is tool_message
    assert result["messages"][-1].content == (
        "Earlier record: trained the January model"
    )
