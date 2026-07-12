"""Regression tests for empty-response retries and the recovery ladder.

Live incidents showed two failure shapes. First, the citation workflow being
cut between select and confirm by a malformed tool call, which the no-tool
repair path could never finish. Second, truly empty upstream replies (a lone
EOS token) whose no-tool repair invited the model to invent tool results.
These tests pin the current handling:

    truly empty reply -> identical retry (twice) -> honest empty-upstream
    fallback; other issues -> continuation (tools allowed, once) -> no-tool
    repair -> fallback
"""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool, tool

from agent.config import AgentConfig
from agent.graph import build_graph
from skills.citation.types import (
    ConfirmBatchOutcome,
    ConfirmReceipt,
    PendingMatchNote,
)


@tool("rag_search")
def _rag_search(query: str) -> str:
    """Search."""
    return query


def _make_citation_tool(calls: list[dict]) -> StructuredTool:
    """A citation_workflow stand-in that emits a real confirm batch artifact."""

    def _run(
        action: str,
        identifier: str | None = None,
        identifiers: list[str] | None = None,
    ):
        calls.append({
            "action": action,
            "identifier": identifier,
            "identifiers": identifiers,
        })
        if action == "select":
            artifact = ConfirmBatchOutcome(pending=(PendingMatchNote(
                candidate_id="c3",
                match_id="m1",
            ),)).to_artifact()
            return "Confirmable matches from this request: [c3] -> [m1]", artifact
        if action == "confirm":
            artifact = ConfirmBatchOutcome(receipts=(ConfirmReceipt(
                source_id="src-1",
                accepted_doi="10.1234/x",
                bundle_path="/tmp/bundle",
                verification_level="identity_verified",
                cite_marker="[[cite:src-1]]",
            ),)).to_artifact()
            return "citation confirmed", artifact
        return f"ok {action}", None

    return StructuredTool.from_function(
        func=_run,
        name="citation_workflow",
        description="Citation workflow stand-in.",
        response_format="content_and_artifact",
    )


class ScriptedModel:
    """Replays a fixed script for bound calls; raw calls use raw_response."""

    def __init__(self, bound_script: list[AIMessage], raw_response: AIMessage):
        self.bound_script = list(bound_script)
        self.raw_response = raw_response
        self.bound_calls: list[list] = []
        self.raw_calls: list[list] = []

    def bind_tools(self, _tools):
        model = self

        class Bound:
            def invoke(_self, messages):
                model.bound_calls.append(messages)
                index = min(
                    len(model.bound_calls) - 1,
                    len(model.bound_script) - 1,
                )
                return model.bound_script[index]

        return Bound()

    def invoke(self, messages):
        self.raw_calls.append(messages)
        return self.raw_response


def _select_call() -> AIMessage:
    return AIMessage(content="", tool_calls=[{
        "name": "citation_workflow",
        "args": {"action": "select", "identifier": "c3"},
        "id": "select-1",
    }])


def _confirm_call() -> AIMessage:
    return AIMessage(content="", tool_calls=[{
        "name": "citation_workflow",
        "args": {"action": "confirm", "identifier": "m1"},
        "id": "confirm-1",
    }])


def _build(monkeypatch, tmp_path, model, **config_overrides):
    monkeypatch.setattr("agent.graph.get_chat_model", lambda _cfg: model)
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools",
        lambda _cfg: [_rag_search],
    )
    monkeypatch.setattr(
        "agent.tools.inventory.create_history_tool",
        lambda _cfg, store=None: _rag_search,
    )
    calls: list[dict] = []
    graph = build_graph(
        AgentConfig(persist_dir=str(tmp_path), **config_overrides),
        skill_tools=[_make_citation_tool(calls)],
    )
    return graph, calls


def _invoke(graph, user_input: str = "把 c3 的 bibtex 存起來"):
    return graph.invoke({
        "messages": [HumanMessage(content=user_input)],
        "active_skill": "citation",
        "skill_instructions": "use citation",
        "effective_tools": ["rag_search", "citation_workflow"],
    }, config={"recursion_limit": 16})


def test_blank_after_select_is_healed_by_an_identical_retry_that_confirms(
    monkeypatch, tmp_path
):
    model = ScriptedModel(
        bound_script=[
            _select_call(),
            AIMessage(content=""),
            _confirm_call(),
            AIMessage(content="Saved m1."),
        ],
        raw_response=AIMessage(content="repair must not run"),
    )
    graph, calls = _build(monkeypatch, tmp_path, model)

    result = _invoke(graph)

    assert [call["action"] for call in calls] == ["select", "confirm"]
    assert result["messages"][-1].content == "Saved m1."
    assert model.raw_calls == []
    # The empty reply was retried with the identical request — no recovery
    # marker, no continuation instruction — and the retry finished the save.
    assert not any(
        (message.response_metadata or {}).get("turn_recovery")
        for message in result["messages"]
        if isinstance(message, AIMessage)
    )
    assert not any(
        "[Continuation]" in getattr(message, "content", "")
        for message in model.bound_calls[2]
    )


def test_consecutive_blanks_never_fake_success_and_keep_pending_matches(
    monkeypatch, tmp_path
):
    model = ScriptedModel(
        bound_script=[
            _select_call(),
            AIMessage(content=""),
            AIMessage(content="   "),
        ],
        raw_response=AIMessage(content="repair must not run"),
    )
    graph, calls = _build(monkeypatch, tmp_path, model)

    result = _invoke(graph, user_input="save c3 for me")

    # Exactly one select; the workflow state was never touched again, so the
    # pending match survives for the next turn.
    assert [call["action"] for call in calls] == ["select"]
    final = result["messages"][-1]
    assert final.response_metadata["turn_recovery"] == (
        "fallback:empty_model_response"
    )
    assert "empty responses" in final.content
    assert "Saved" not in final.content
    # Initial + two identical retries on the bound model; the no-tool repair
    # (which could invent a save report) never runs.
    assert len(model.bound_calls) == 4
    assert model.raw_calls == []


def test_invalid_tool_calls_after_select_trigger_the_continuation(
    monkeypatch, tmp_path
):
    malformed = AIMessage(
        content="I'll save it now.",
        invalid_tool_calls=[{
            "name": "citation_workflow",
            "args": '{"action": "confirm", "identifier": "m1"',
            "id": "bad-1",
            "error": "unparsable arguments",
            "type": "invalid_tool_call",
        }],
    )
    model = ScriptedModel(
        bound_script=[
            _select_call(),
            malformed,
            _confirm_call(),
            AIMessage(content="done"),
        ],
        raw_response=AIMessage(content="repair must not run"),
    )
    graph, calls = _build(monkeypatch, tmp_path, model)

    result = _invoke(graph)

    assert [call["action"] for call in calls] == ["select", "confirm"]
    assert result["messages"][-1].content == "done"
    continuation = next(
        message for message in result["messages"]
        if isinstance(message, AIMessage)
        and (message.response_metadata or {}).get("turn_recovery")
    )
    assert continuation.response_metadata["turn_recovery"] == (
        "continuation:invalid_tool_calls"
    )


def test_no_continuation_without_remaining_primary_budget(monkeypatch, tmp_path):
    # A malformed-call husk (not a truly empty reply) keeps the ladder in
    # charge: with the primary budget spent, continuation is skipped and the
    # no-tool repair runs.
    husk = AIMessage(
        content="",
        invalid_tool_calls=[{
            "name": "citation_workflow",
            "args": '{"action": "confirm", "identifier": "m1"',
            "id": "bad-1",
            "error": "unparsable arguments",
            "type": "invalid_tool_call",
        }],
    )
    model = ScriptedModel(
        bound_script=[
            _select_call(),
            husk,
        ],
        raw_response=AIMessage(content="repaired text"),
    )
    graph, calls = _build(
        monkeypatch, tmp_path, model, agent_max_tool_interactions=1
    )

    result = _invoke(graph)

    assert [call["action"] for call in calls] == ["select"]
    # No third bound call: the budget was spent, so the ladder skips straight
    # to the no-tool repair.
    assert len(model.bound_calls) == 2
    assert len(model.raw_calls) == 1
    final = result["messages"][-1]
    assert final.content == "repaired text"
    assert final.response_metadata["turn_recovery"] == (
        "repaired:empty_final_answer"
    )


def test_blanks_after_receipts_never_rerun_tools_and_report_honestly(
    monkeypatch, tmp_path
):
    model = ScriptedModel(
        bound_script=[
            _select_call(),
            _confirm_call(),
            AIMessage(content=""),
        ],
        raw_response=AIMessage(content="repair must not run"),
    )
    graph, calls = _build(monkeypatch, tmp_path, model)

    result = _invoke(graph)

    # The bundle write ran exactly once; the blank summaries were retried
    # identically and then reported honestly — no model call may invent a
    # summary on top of the trusted receipts.
    assert [call["action"] for call in calls] == ["select", "confirm"]
    assert len(model.bound_calls) == 5
    assert model.raw_calls == []
    final = result["messages"][-1]
    assert final.response_metadata["turn_recovery"] == (
        "fallback:empty_model_response"
    )
    # Default _invoke user input is Chinese, so the honest notice is too.
    assert "空回應" in final.content


def test_empty_reply_is_retried_identically_before_any_recovery(
    monkeypatch, tmp_path
):
    model = ScriptedModel(
        bound_script=[
            AIMessage(content=""),
            AIMessage(content="Here you go."),
        ],
        raw_response=AIMessage(content="repair must not run"),
    )
    graph, calls = _build(monkeypatch, tmp_path, model)

    result = _invoke(graph, user_input="just answer")

    final = result["messages"][-1]
    assert final.content == "Here you go."
    assert not (final.response_metadata or {}).get("turn_recovery")
    assert calls == []
    assert model.raw_calls == []
    assert len(model.bound_calls) == 2
    # The retry re-sent the identical request, without extra instructions.
    assert [
        getattr(message, "content", "") for message in model.bound_calls[0]
    ] == [
        getattr(message, "content", "") for message in model.bound_calls[1]
    ]


def test_exhausted_empty_retries_report_the_empty_upstream_in_chinese(
    monkeypatch, tmp_path
):
    model = ScriptedModel(
        bound_script=[AIMessage(content="")],
        raw_response=AIMessage(content="repair must not run"),
    )
    graph, calls = _build(monkeypatch, tmp_path, model)

    result = _invoke(graph, user_input="幫我引用 aiayn 的原始論文")

    final = result["messages"][-1]
    assert final.response_metadata["turn_recovery"] == (
        "fallback:empty_model_response"
    )
    assert "空回應" in final.content
    assert calls == []
    assert model.raw_calls == []
    # Initial call plus exactly two identical retries.
    assert len(model.bound_calls) == 3


def test_prose_with_invalid_tool_calls_outside_citation_window_is_kept(
    monkeypatch, tmp_path
):
    prose = AIMessage(
        content="Here is my answer without any tool.",
        invalid_tool_calls=[{
            "name": "rag_search",
            "args": '{"query": "x"',
            "id": "bad-1",
            "error": "unparsable arguments",
            "type": "invalid_tool_call",
        }],
    )
    model = ScriptedModel(
        bound_script=[prose],
        raw_response=AIMessage(content="repair must not run"),
    )
    graph, _calls = _build(monkeypatch, tmp_path, model)

    result = _invoke(graph, user_input="just answer")

    assert result["messages"][-1].content == "Here is my answer without any tool."
    assert model.raw_calls == []
    assert len(model.bound_calls) == 1
