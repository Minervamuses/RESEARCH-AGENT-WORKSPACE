"""Tests for the discovery search agent's concurrent same-round tool calls."""

import asyncio
from types import SimpleNamespace

from langchain_core.messages import ToolMessage

from citation import discovery
from citation.runtime import SUMMARIES_TOOL


class _ScriptedToolLLM:
    """LLM stub: each round pops a scripted tool_calls list; then stops."""

    def __init__(self, rounds):
        self.rounds = list(rounds)
        self.seen_messages: list[list] = []

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        self.seen_messages.append(list(messages))
        tool_calls = self.rounds.pop(0) if self.rounds else []
        return SimpleNamespace(content="", tool_calls=tool_calls)


class _RecordingTool:
    def __init__(self, results):
        self.results = list(results)
        self.calls: list[dict] = []

    async def ainvoke(self, args):
        self.calls.append(args)
        return self.results.pop(0)


def _tc(name, query, call_id):
    return {"id": call_id, "name": name, "args": {"query": query}}


def _runtime(tools, llm):
    return SimpleNamespace(web_tools=tools, llm=llm)


def _round_two_tool_messages(llm):
    """ToolMessages the model saw at the start of round 2, in append order."""
    return [m for m in llm.seen_messages[1] if isinstance(m, ToolMessage)]


def test_budget_slices_before_gather_and_order_is_preserved():
    tool = _RecordingTool(["r1", "r2"])
    llm = _ScriptedToolLLM([
        [
            _tc(SUMMARIES_TOOL, "q1", "c1"),
            _tc(SUMMARIES_TOOL, "q2", "c2"),
            _tc(SUMMARIES_TOOL, "q3", "c3"),
        ],
    ])
    runtime = _runtime({SUMMARIES_TOOL: tool}, llm)

    result_texts, queries = asyncio.run(discovery._run_search_agent(
        runtime, "find papers", max_rounds=3, max_tool_calls=2, progress_cb=None,
    ))

    # only the first two calls ran; the third was sliced off by the budget
    assert [c["query"] for c in tool.calls] == ["q1", "q2"]
    assert result_texts == ["r1", "r2"]
    assert queries == ["q1", "q2"]
    # ToolMessages keep the original call order, budget note included
    contents = [m.content for m in _round_two_tool_messages(llm)] if len(llm.seen_messages) > 1 else None
    # budget reached -> the loop breaks without a second LLM round
    assert contents is None
    assert llm.rounds == []


def test_tool_messages_keep_call_order_across_placeholders():
    tool = _RecordingTool(["real result"])
    llm = _ScriptedToolLLM([
        [
            _tc("missing_tool", "q1", "c1"),
            _tc(SUMMARIES_TOOL, "q2", "c2"),
        ],
        [],
    ])
    runtime = _runtime({SUMMARIES_TOOL: tool}, llm)

    result_texts, queries = asyncio.run(discovery._run_search_agent(
        runtime, "find papers", max_rounds=3, max_tool_calls=8, progress_cb=None,
    ))

    # unavailable tool consumed no budget and kept its slot in order
    contents = [m.content for m in _round_two_tool_messages(llm)]
    assert contents == ["(tool 'missing_tool' is not available)", "real result"]
    assert result_texts == ["real result"]
    assert queries == ["q2"]


def test_same_round_calls_run_concurrently(monkeypatch):
    # Serial execution would deadlock on the event until the (shortened)
    # per-call timeout; concurrent execution finishes immediately.
    monkeypatch.setattr(discovery, "_TOOL_TIMEOUT_SECONDS", 2.0)
    event = asyncio.Event()

    class _WaitTool:
        async def ainvoke(self, args):
            await event.wait()
            return "waited"

    class _SetTool:
        async def ainvoke(self, args):
            event.set()
            return "set"

    llm = _ScriptedToolLLM([
        [_tc("wait_tool", "q1", "c1"), _tc("set_tool", "q2", "c2")],
        [],
    ])
    runtime = _runtime({"wait_tool": _WaitTool(), "set_tool": _SetTool()}, llm)

    asyncio.run(discovery._run_search_agent(
        runtime, "find papers", max_rounds=2, max_tool_calls=8, progress_cb=None,
    ))

    contents = [m.content for m in _round_two_tool_messages(llm)]
    assert contents == ["waited", "set"]
