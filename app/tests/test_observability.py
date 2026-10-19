"""Tests for redaction-safe model-response observability."""

import asyncio
import logging
import uuid

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import StructuredTool

from agent.config import AgentConfig
from agent.graph import build_graph
from agent.observability import (
    last_completed_citation_call,
    log_model_response,
    summarize_model_response,
)


def _summary(message: AIMessage, **overrides) -> dict:
    kwargs = {
        "stage": "initial",
        "issue": None,
        "dropped_tool_calls": 0,
        "graph_steps_remaining": 7,
        "last_citation_action": None,
        "last_citation_tool_status": None,
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
                "args": '{"action": "save"',
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
    assert record["graph_steps_remaining"] == 7
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


def test_last_completed_citation_call_requires_result_and_reports_status():
    search_call = AIMessage(content="", tool_calls=[{
        "name": "citation_workflow",
        "args": {"action": "search", "query": "paper"},
        "id": "call-1",
    }])
    completed = ToolMessage(
        content="ok", tool_call_id="call-1", status="success"
    )
    dangling_save = AIMessage(content="", tool_calls=[{
        "name": "citation_workflow",
        "args": {"action": "save", "works": [{"requested_label": "paper"}]},
        "id": "call-2",
    }])

    assert last_completed_citation_call([search_call]) == (None, None)
    assert last_completed_citation_call(
        [search_call, completed, dangling_save]
    ) == ("search", "success")
    assert last_completed_citation_call(
        iter([search_call, completed, dangling_save])
    ) == ("search", "success")

    failed = ToolMessage(
        content="tool error", tool_call_id="call-2", status="error"
    )
    assert last_completed_citation_call(
        [search_call, completed, dangling_save, failed]
    ) == ("save", "error")


def test_last_completed_citation_call_ignores_other_tools():
    bash_call = AIMessage(content="", tool_calls=[{
        "name": "bash",
        "args": {"command": "ls"},
        "id": "call-1",
    }])
    result = ToolMessage(content="ok", tool_call_id="call-1")

    assert last_completed_citation_call([bash_call, result]) == (None, None)


def test_completed_citation_call_redacts_unknown_action_and_name_collision():
    secret = "10.1234/secret-provider-text"
    call = AIMessage(content="", tool_calls=[{
        "name": "citation_workflow",
        "args": {"action": secret},
        "id": "shared-id",
    }])
    wrong_tool = ToolMessage(
        content="ok",
        tool_call_id="shared-id",
        name="another_tool",
    )
    citation_error = ToolMessage(
        content="error",
        tool_call_id="shared-id",
        name="citation_workflow",
        status="error",
    )

    assert last_completed_citation_call([call, wrong_tool]) == (None, None)
    assert last_completed_citation_call(
        [call, wrong_tool, citation_error]
    ) == ("unknown", "error")


def test_invalid_response_warning_never_contains_content_args_or_dois(caplog):
    doi = "10.1234/secret-doi"
    search_call = AIMessage(content="", tool_calls=[{
        "name": "citation_workflow",
        "args": {"action": "search", "query": doi},
        "id": "call-1",
    }])
    completed = ToolMessage(content=f"resolved {doi}", tool_call_id="call-1")
    message = AIMessage(
        content=f"the DOI is {doi} and provider said something",
        invalid_tool_calls=[{
            "name": "citation_workflow",
            "args": f'{{"action": "save", "identifier": "{doi}"',
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
            graph_steps_remaining=5,
            messages=[search_call, completed],
        )

    assert len(caplog.records) == 1
    line = caplog.records[0].getMessage()
    assert doi not in line
    assert "provider said" not in line
    assert "identifier" not in line
    assert "last_citation_action=search" in line
    assert "last_citation_tool_status=success" in line
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
            graph_steps_remaining=5,
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
                            "args": '{"action": "save"',
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


def test_graph_logs_tool_call_round_without_budget_fields(
    monkeypatch, tmp_path, caplog
):
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
    assert any("tool_calls=1" in line for line in lines)
    assert any("graph_steps_remaining=6" in line for line in lines)
    assert any("graph_steps_remaining=4" in line for line in lines)
    assert not any("budget_remaining" in line for line in lines)


def test_tool_exception_is_logged_with_an_incident_shown_to_the_model(
    monkeypatch, tmp_path, caplog
):
    import re

    from langchain_core.tools import tool

    @tool("rag_search")
    def _broken_search(query: str) -> str:
        """Search."""
        raise ConnectionResetError("peer reset")

    class ToolThenAnswerModel:
        def bind_tools(self, _tools):
            class Bound:
                def invoke(_self, messages):
                    if any(isinstance(m, ToolMessage) for m in messages):
                        return AIMessage(content="The search tool failed.")
                    return AIMessage(content="", tool_calls=[{
                        "name": "rag_search", "args": {"query": "x"},
                        "id": "call-1", "type": "tool_call",
                    }])
            return Bound()

        def invoke(self, _messages):
            return AIMessage(content="unused")

    monkeypatch.setattr("agent.graph.get_chat_model", lambda _cfg: ToolThenAnswerModel())
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools", lambda _cfg: [_broken_search],
    )
    graph = build_graph(AgentConfig(persist_dir=str(tmp_path)))

    with caplog.at_level(logging.ERROR, logger="agent.graph"):
        result = graph.invoke({"messages": [HumanMessage(content="hi")]})

    tool_message = next(m for m in result["messages"] if isinstance(m, ToolMessage))
    match = re.fullmatch(
        r"Tool error: ConnectionResetError: peer reset \(incident ([0-9a-f]{8})\)",
        tool_message.content,
    )
    assert match is not None
    record = next(r for r in caplog.records if match.group(1) in r.getMessage())
    assert record.exc_info is not None and record.exc_info[0] is ConnectionResetError


TURN_A, TURN_B, TURN_C, TURN_D, TURN_E = (uuid.uuid4().hex for _ in range(5))


class _ScriptedChatModel(BaseChatModel):
    """A real BaseChatModel so LangChain callbacks observe each invocation."""

    script: list

    @property
    def _llm_type(self) -> str:
        return "scripted-test"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        step = self.script.pop(0)
        if isinstance(step, BaseException):
            raise step
        return ChatResult(generations=[ChatGeneration(message=step(messages) if callable(step) else step)])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def _calls(*calls) -> AIMessage:
    return AIMessage(content="", tool_calls=[
        {"name": name, "args": args, "id": call_id, "type": "tool_call"} for name, args, call_id in calls
    ], usage_metadata={"input_tokens": 11, "output_tokens": 3, "total_tokens": 14})


def _trace_records(caplog, turn_id=None) -> list[dict]:
    records = []
    for record in caplog.records:
        message = record.getMessage()
        if record.name != "agent.observability" or not message.startswith("turn_trace "):
            continue
        fields = dict(item.split("=", 1) for item in message.removeprefix("turn_trace ").split(" "))
        if turn_id is None or fields["turn_id"] == turn_id:
            records.append(fields)
    return records


def _timed_session(monkeypatch, tmp_path, script, tools):
    from agent.session import ChatSession

    model = _ScriptedChatModel(script=script)
    monkeypatch.setattr("agent.graph.get_chat_model", lambda _cfg: model)
    monkeypatch.setattr("agent.tools.inventory.create_rag_tools", lambda _cfg: tools)
    monkeypatch.setattr("agent.session.find_app_root", lambda: tmp_path)
    return ChatSession(AgentConfig(persist_dir=str(tmp_path / "persist")))


async def _fast_lookup(query: str) -> str:
    """Return quickly."""
    await asyncio.sleep(0.01)
    return "fast result"


async def _slow_lookup(query: str) -> str:
    """Return after a measurable delay."""
    await asyncio.sleep(0.25)
    return "slow result"


async def _failing_lookup(query: str) -> str:
    """Raise a tool error."""
    raise ConnectionResetError("peer reset")


def test_turn_trace_records_parallel_tool_intervals_and_model_order(monkeypatch, tmp_path, caplog):
    tools = [
        StructuredTool.from_function(coroutine=_fast_lookup, name="rag_search"),
        StructuredTool.from_function(coroutine=_slow_lookup, name="rag_explore"),
    ]
    session = _timed_session(monkeypatch, tmp_path, [
        _calls(("rag_explore", {"query": "slow private words"}, "call-slow"),
               ("rag_search", {"query": "fast private words"}, "call-fast")),
        AIMessage(content="final answer"),
    ], tools)
    with caplog.at_level(logging.INFO, logger="agent.observability"):
        outcome = asyncio.run(session.turn_outcome("compare both", turn_id=TURN_A))

    assert outcome.state == "completed"
    records = _trace_records(caplog, TURN_A)
    events = [record["event"] for record in records]
    assert events[0] == "turn_start" and events[-1] == "turn_end"
    assert events.count("model_start") == events.count("model_end") == 2
    assert len({record["attempt"] for record in records}) == 1
    ends = {record["tool"]: record for record in records if record["event"] == "tool_end"}
    starts = {record["tool"]: record for record in records if record["event"] == "tool_start"}
    assert ends["rag_search"]["tool_call_id"] == "call-fast" and ends["rag_explore"]["tool_call_id"] == "call-slow"
    assert {record["model_seq"] for record in ends.values()} == {"1"}
    assert {record["status"] for record in ends.values()} == {"ok"}
    # Both started before either finished, and the fast tool finished first.
    assert max(int(record["at_ms"]) for record in starts.values()) < int(ends["rag_search"]["at_ms"])
    assert int(ends["rag_search"]["at_ms"]) < int(ends["rag_explore"]["at_ms"])
    assert int(ends["rag_explore"]["duration_ms"]) >= 200 > int(ends["rag_search"]["duration_ms"])
    assert starts["rag_search"]["query_hash"] != starts["rag_explore"]["query_hash"]
    first_model = next(record for record in records if record["event"] == "model_end")
    assert first_model["tool_calls"] == "2" and first_model["input_tokens"] == "11"
    end = records[-1]
    assert end["state"] == "completed" and end["model_calls"] == "2"
    assert end["tool_calls"] == "2" and end["unfinished"] == "0"
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "private words" not in log_text and "final answer" not in log_text


def test_turn_trace_marks_tool_and_model_errors_denials_and_new_attempts(monkeypatch, tmp_path, caplog):
    tools = [StructuredTool.from_function(coroutine=_failing_lookup, name="rag_search")]
    session = _timed_session(monkeypatch, tmp_path, [
        _calls(("rag_search", {"query": "x"}, "call-error"), ("not_a_tool", {}, "call-denied")),
        AIMessage(content="tool failed"),
        RuntimeError("model unavailable"),
        AIMessage(content="retried answer"),
    ], tools)
    turn_id = TURN_B
    with caplog.at_level(logging.INFO, logger="agent.observability"):
        assert asyncio.run(session.turn_outcome("first", turn_id=TURN_C)).state == "completed"
        with pytest.raises(RuntimeError):
            asyncio.run(session.turn_outcome("second", turn_id=turn_id))
        assert asyncio.run(session.turn_outcome("second", turn_id=turn_id, retry=True)).state == "completed"

    first = _trace_records(caplog, TURN_C)
    tool_ends = [record for record in first if record["event"] == "tool_end"]
    assert [(record["tool"], record["status"], record["error_type"]) for record in tool_ends] == [
        ("rag_search", "error", "ConnectionResetError"),
    ]
    assert not any(record.get("tool_call_id") == "call-denied" for record in first)
    assert first[-1]["tool_calls"] == "1"
    retried = _trace_records(caplog, turn_id)
    attempts = list(dict.fromkeys(record["attempt"] for record in retried))
    assert len(attempts) == 2
    failed = [record for record in retried if record["attempt"] == attempts[0]]
    assert [record["event"] for record in failed] == ["turn_start", "model_start", "model_end", "turn_end"]
    assert failed[2]["status"] == "error" and failed[2]["error_type"] == "RuntimeError"
    assert failed[-1]["state"] == "failed"
    assert [record["state"] for record in retried if record["event"] == "turn_end"] == ["failed", "completed"]


def test_turn_trace_closes_cancelled_tool_as_unfinished(monkeypatch, tmp_path, caplog):
    started = None

    async def blocking_lookup(query: str) -> str:
        """Block until cancelled."""
        started.set()
        await asyncio.Event().wait()
        return "never"

    session = _timed_session(monkeypatch, tmp_path, [
        _calls(("rag_search", {"query": "x"}, "call-blocked")),
    ], [StructuredTool.from_function(coroutine=blocking_lookup, name="rag_search")])

    async def run():
        nonlocal started
        started = asyncio.Event()
        task = asyncio.create_task(session.turn_outcome("wait", turn_id=TURN_D))
        await asyncio.wait_for(started.wait(), 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    with caplog.at_level(logging.INFO, logger="agent.observability"):
        asyncio.run(run())
    records = _trace_records(caplog, TURN_D)
    tool_end = next(record for record in records if record["event"] == "tool_end")
    assert tool_end["tool_call_id"] == "call-blocked" and tool_end["status"] == "unfinished"
    assert records[-1]["state"] == "cancelled" and records[-1]["unfinished"] == "1"


def test_turn_trace_reaches_the_persistent_diagnostic_log(monkeypatch, tmp_path):
    from agent import diagnostics

    session = _timed_session(monkeypatch, tmp_path, [AIMessage(content="ok")], [])
    path = diagnostics.install_diagnostic_log(
        "trace-test", echo_stderr=False, env={"AGENT_LOG_DIR": str(tmp_path / "logs")},
    )
    try:
        asyncio.run(session.turn_outcome("hello", turn_id=TURN_E))
    finally:
        diagnostics.uninstall_diagnostic_log()
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if "turn_trace" in line]
    assert [line.split("event=", 1)[1].split(" ", 1)[0] for line in lines] == [
        "turn_start", "model_start", "model_end", "turn_end",
    ]
    assert all(f"turn_id={TURN_E}" in line and " INFO agent.observability " in line for line in lines)


def test_turn_trace_links_citation_actions_queries_and_counts(monkeypatch, tmp_path, caplog):
    from test_citation_e2e import _seed_fixture_service
    from tests.citation_fixtures import DOI_A

    tools = []
    session = _timed_session(monkeypatch, tmp_path, [
        _calls(("citation_workflow", {"action": "search", "query": "Paper A private topic"}, "search-1")),
        _calls(("citation_workflow", {"action": "search", "query": "Paper A private topic"}, "search-2"),
               ("citation_workflow", {"action": "search", "query": "another private topic", "year_from": 2021}, "search-3")),
        AIMessage(content="候選與限制已說明。"),
    ], tools)
    session.activate_citation_skill()
    _seed_fixture_service(session, tmp_path)
    turn_id = uuid.uuid4().hex
    with caplog.at_level(logging.INFO, logger="agent.observability"):
        assert asyncio.run(session.turn_outcome("找 Paper A", turn_id=turn_id)).state == "completed"

    records = _trace_records(caplog, turn_id)
    ends = {record["tool_call_id"]: record for record in records if record["event"] == "tool_end"}
    assert {record["action"] for record in ends.values()} == {"search"}
    assert ends["search-1"]["query_hash"] == ends["search-2"]["query_hash"] != ends["search-3"]["query_hash"]
    # The offline Crossref fixture returns Paper A (2021) and Paper B (2020) without abstracts.
    assert (ends["search-1"]["candidate_count"], ends["search-1"]["abstract_count"]) == ("2", "0")
    assert (ends["search-3"]["candidate_count"], ends["search-3"]["abstract_count"]) == ("1", "0")
    assert ends["search-1"]["provider_count"] == "2" and ends["search-1"]["failed_provider_count"] == "0"
    # New-evidence increments per search: the repeat and the year-filtered subset add nothing.
    assert [ends[call]["new_candidate_count"] for call in ("search-1", "search-2", "search-3")] == ["2", "0", "0"]
    assert [ends[call]["model_seq"] for call in ("search-1", "search-2", "search-3")] == ["1", "2", "2"]
    assert records[-1]["model_calls"] == "3" and records[-1]["tool_calls"] == "3"
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "private topic" not in log_text and DOI_A not in log_text and "Paper A" not in log_text
