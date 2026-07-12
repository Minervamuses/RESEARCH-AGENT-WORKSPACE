"""Tests for redaction-safe model-response observability."""

import logging

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.config import AgentConfig
from agent.graph import build_graph
from agent.observability import (
    last_completed_citation_action,
    log_model_response,
    summarize_model_response,
)


def _summary(message: AIMessage, **overrides) -> dict:
    kwargs = {
        "stage": "initial",
        "issue": None,
        "dropped_tool_calls": 0,
        "primary_remaining": 4,
        "local_remaining": 4,
        "last_citation_action": None,
    }
    kwargs.update(overrides)
    return summarize_model_response(message, **kwargs)


def test_summary_captures_provider_metadata_and_counts():
    message = AIMessage(
        content="short answer",
        response_metadata={
            "id": "gen-abc123",
            "finish_reason": "stop",
        },
        usage_metadata={
            "input_tokens": 120,
            "output_tokens": 0,
            "total_tokens": 120,
        },
        invalid_tool_calls=[
            {
                "name": "citation_workflow",
                "args": '{"action": "confirm"',
                "id": "bad-1",
                "error": "unparsable",
                "type": "invalid_tool_call",
            }
        ],
    )

    record = _summary(message, issue="empty_final_answer")

    assert record["response_id"] == "gen-abc123"
    assert record["finish_reason"] == "stop"
    assert record["input_tokens"] == 120
    assert record["output_tokens"] == 0
    assert record["total_tokens"] == 120
    assert record["content_chars"] == len("short answer")
    assert record["tool_calls"] == 0
    assert record["invalid_tool_calls"] == 1
    assert record["issue"] == "empty_final_answer"
    assert record["stage"] == "initial"


def test_summary_falls_back_to_openai_token_usage():
    message = AIMessage(
        content="",
        response_metadata={
            "token_usage": {
                "prompt_tokens": 10,
                "completion_tokens": 2,
                "total_tokens": 12,
            },
        },
    )

    record = _summary(message)

    assert record["input_tokens"] == 10
    assert record["output_tokens"] == 2
    assert record["total_tokens"] == 12


def test_last_completed_citation_action_requires_a_tool_result():
    select_call = AIMessage(content="", tool_calls=[{
        "name": "citation_workflow",
        "args": {"action": "select", "identifier": "c3"},
        "id": "call-1",
    }])
    completed = ToolMessage(content="ok", tool_call_id="call-1")
    dangling_confirm = AIMessage(content="", tool_calls=[{
        "name": "citation_workflow",
        "args": {"action": "confirm", "identifier": "m1"},
        "id": "call-2",
    }])

    assert last_completed_citation_action([select_call]) is None
    assert last_completed_citation_action(
        [select_call, completed, dangling_confirm]
    ) == "select"


def test_last_completed_citation_action_ignores_other_tools():
    bash_call = AIMessage(content="", tool_calls=[{
        "name": "bash",
        "args": {"command": "ls"},
        "id": "call-1",
    }])
    result = ToolMessage(content="ok", tool_call_id="call-1")

    assert last_completed_citation_action([bash_call, result]) is None


def test_invalid_response_warning_never_contains_content_args_or_dois(caplog):
    doi = "10.1234/secret-doi"
    select_call = AIMessage(content="", tool_calls=[{
        "name": "citation_workflow",
        "args": {"action": "select", "identifier": doi},
        "id": "call-1",
    }])
    completed = ToolMessage(content=f"resolved {doi}", tool_call_id="call-1")
    message = AIMessage(
        content=f"the DOI is {doi} and provider said something",
        invalid_tool_calls=[{
            "name": "citation_workflow",
            "args": f'{{"action": "confirm", "identifier": "{doi}"',
            "id": "bad-1",
            "error": f"provider free text mentioning {doi}",
            "type": "invalid_tool_call",
        }],
    )

    with caplog.at_level(logging.WARNING, logger="agent.observability"):
        log_model_response(
            message,
            stage="initial",
            issue="invalid_tool_calls",
            dropped_tool_calls=0,
            primary_remaining=3,
            local_remaining=4,
            messages=[select_call, completed],
        )

    assert len(caplog.records) == 1
    line = caplog.records[0].getMessage()
    assert doi not in line
    assert "provider said" not in line
    assert "identifier" not in line
    assert "last_citation_action=select" in line
    assert "invalid_tool_calls=1" in line
    assert "content_chars=" in line
    assert caplog.records[0].levelno == logging.WARNING


def test_valid_response_is_debug_only(caplog):
    with caplog.at_level(logging.DEBUG, logger="agent.observability"):
        log_model_response(
            AIMessage(content="done"),
            stage="initial",
            issue=None,
            dropped_tool_calls=0,
            primary_remaining=4,
            local_remaining=4,
            messages=[],
        )

    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.DEBUG


class _StubTools:
    """Shared monkeypatching of the graph tool inventory."""

    @staticmethod
    def apply(monkeypatch, model):
        from langchain_core.tools import tool

        @tool("rag_search")
        def _rag_search(query: str) -> str:
            """Search."""
            return query

        monkeypatch.setattr("agent.graph.get_chat_model", lambda _cfg: model)
        monkeypatch.setattr(
            "agent.tools.inventory.create_rag_tools",
            lambda _cfg: [_rag_search],
        )
        monkeypatch.setattr(
            "agent.tools.inventory.create_history_tool",
            lambda _cfg, store=None: _rag_search,
        )


def test_graph_logs_initial_repair_and_fallback_stages(
    monkeypatch, tmp_path, caplog
):
    class ArtifactThenBlankModel:
        def bind_tools(self, _tools):
            class Bound:
                def invoke(_self, _messages):
                    return AIMessage(content='rag_search(query="x")')
            return Bound()

        def invoke(self, _messages):
            return AIMessage(content="   ")

    _StubTools.apply(monkeypatch, ArtifactThenBlankModel())
    graph = build_graph(AgentConfig(persist_dir=str(tmp_path)))

    with caplog.at_level(logging.DEBUG, logger="agent.observability"):
        graph.invoke({"messages": [HumanMessage(content="hi")]})

    lines = [record.getMessage() for record in caplog.records]
    assert any(
        "stage=initial" in line and "issue=call_like_tool_protocol" in line
        for line in lines
    )
    assert any("stage=repair" in line for line in lines)
    assert any("stage=fallback" in line for line in lines)


def test_graph_logs_empty_retry_stages_and_honest_fallback(
    monkeypatch, tmp_path, caplog
):
    class AlwaysBlankModel:
        def bind_tools(self, _tools):
            class Bound:
                def invoke(_self, _messages):
                    return AIMessage(content="")
            return Bound()

        def invoke(self, _messages):
            return AIMessage(content="repair must not run")

    _StubTools.apply(monkeypatch, AlwaysBlankModel())
    graph = build_graph(AgentConfig(persist_dir=str(tmp_path)))

    with caplog.at_level(logging.DEBUG, logger="agent.observability"):
        graph.invoke({"messages": [HumanMessage(content="hi")]})

    lines = [record.getMessage() for record in caplog.records]
    assert any(
        "stage=initial" in line and "issue=empty_model_response" in line
        for line in lines
    )
    assert any("stage=empty_retry_1" in line for line in lines)
    assert any("stage=empty_retry_2" in line for line in lines)
    assert any(
        "stage=fallback" in line
        and "repair_issue=empty_retries_exhausted" in line
        for line in lines
    )
    assert not any("stage=repair " in line for line in lines)


def test_graph_logs_invalid_tool_calls_on_initial_stage(
    monkeypatch, tmp_path, caplog
):
    class MalformedToolCallModel:
        def bind_tools(self, _tools):
            class Bound:
                def invoke(_self, _messages):
                    return AIMessage(
                        content="",
                        invalid_tool_calls=[{
                            "name": "citation_workflow",
                            "args": '{"action": "confirm"',
                            "id": "bad-1",
                            "error": "unparsable",
                            "type": "invalid_tool_call",
                        }],
                    )
            return Bound()

        def invoke(self, _messages):
            return AIMessage(content="repaired answer")

    _StubTools.apply(monkeypatch, MalformedToolCallModel())
    graph = build_graph(AgentConfig(persist_dir=str(tmp_path)))

    with caplog.at_level(logging.DEBUG, logger="agent.observability"):
        result = graph.invoke({"messages": [HumanMessage(content="hi")]})

    assert result["messages"][-1].content == "repaired answer"
    initial_lines = [
        record.getMessage()
        for record in caplog.records
        if "stage=initial" in record.getMessage()
    ]
    assert any("invalid_tool_calls=1" in line for line in initial_lines)


def test_graph_logs_tool_call_round_with_budget(monkeypatch, tmp_path, caplog):
    class OneToolModel:
        def __init__(self):
            self.rounds = 0

        def bind_tools(self, _tools):
            model = self

            class Bound:
                def invoke(_self, _messages):
                    model.rounds += 1
                    if model.rounds == 1:
                        return AIMessage(content="", tool_calls=[{
                            "name": "rag_search",
                            "args": {"query": "x"},
                            "id": "call-1",
                        }])
                    return AIMessage(content="done")
            return Bound()

        def invoke(self, _messages):
            return AIMessage(content="done")

    _StubTools.apply(monkeypatch, OneToolModel())
    graph = build_graph(AgentConfig(persist_dir=str(tmp_path)))

    with caplog.at_level(logging.DEBUG, logger="agent.observability"):
        graph.invoke(
            {"messages": [HumanMessage(content="hi")]},
            config={"recursion_limit": 8},
        )

    lines = [record.getMessage() for record in caplog.records]
    assert any(
        "tool_calls=1" in line and "primary_budget_remaining=4" in line
        for line in lines
    )
    assert any("primary_budget_remaining=3" in line for line in lines)
