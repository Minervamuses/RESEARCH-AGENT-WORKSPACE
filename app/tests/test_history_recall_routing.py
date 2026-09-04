"""Scripted routing regressions for the archived history-recall failure.

Archived scenario: under the academic-paper-writing skill in extended thinking
mode, the user asks the agent to look at prior records ("你自行看一下紀錄").
The agent repeatedly asked intake questions and eventually surfaced internal
reviewer-style instructions instead of either using recall_history or honestly
explaining what it could retrieve.

These tests intentionally use a scripted graph, including test-created
ToolMessages, to isolate extended-thinking reviewer/reviser routing and
user-facing rendering. They are routing tests, not E2E or journey coverage.
"""

import asyncio
import json
from types import SimpleNamespace

from langchain_core.messages import AIMessage, ToolMessage

from conftest import FakeHistoryStore, QueuedModel

from agent.config import AgentConfig
from agent.session import ChatSession


class _ScriptedGraph:
    """Fake graph whose each call yields one scripted list of messages.

    Each script is a list of BaseMessage objects yielded as a single 'agent'
    update, so ChatSession._run_graph_turn records the tool calls, their
    matching ToolMessages, and the final answer (the last message's content).
    """

    def __init__(self, scripts):
        self.scripts = [list(script) for script in scripts]
        self.calls: list[dict] = []

    async def astream(self, state, config=None, stream_mode="updates"):
        self.calls.append(state)
        if self.scripts:
            script = self.scripts.pop(0)
        else:  # pragma: no cover - guards against unexpected extra graph turns
            script = [AIMessage(content="(unscripted graph call)")]
        yield {"agent": {"messages": list(script)}}


def _config(tmp_path, **overrides):
    data = {
        "persist_dir": str(tmp_path),
        "thinking_rewrite_model": "anthropic/claude-haiku-5",
        "thinking_reviewer_model": "openai/gpt-5.2",
        "thinking_repair_model": "meta-llama/llama-3.1-8b-instruct",
        # One proposer keeps the fusion panel in single-candidate mode, so the
        # reviewer/reviser routing under test runs exactly as the single writer
        # did before fusion (no aggregator, no quorum branch).
        "thinking_fusion_proposer_models": ("writer-model",),
        "thinking_fusion_aggregator_model": "openai/gpt-5.2",
    }
    data.update(overrides)
    return AgentConfig(**data)


def _academic_runtime(tmp_path, *, effective):
    from agent.tools.access import ToolAccessResolution

    effective = tuple(effective)
    return SimpleNamespace(
        name="academic-paper-writing",
        root=tmp_path,
        instructions="# Academic paper writing",
        pinned_references={},
        tool_access=ToolAccessResolution(
            global_tools=effective,
            skill_tools=(),
            effective_tools=effective,
            missing_required=(),
            missing_optional=(),
        ),
        context_block=lambda: "[Active skill]\nname: academic-paper-writing",
    )


def _make_session(monkeypatch, tmp_path, graph, models, runtime, cfg=None):
    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _cfg, extra_tools=None, history_store=None, **kwargs: graph,
    )
    monkeypatch.setattr(
        "agent.session.get_chat_model_for_role",
        lambda _cfg, *, role: models[role],
    )
    session = ChatSession(cfg or _config(tmp_path), history_store=FakeHistoryStore())
    session._prompt_master_skill_text_cache = "prompt-master skill"
    session.active_skill_runtime = runtime
    session.set_thinking_mode("extended")
    return session


def _review_json(decision, findings, summary="see findings"):
    return json.dumps({
        "decision": decision,
        "findings": findings,
        "summary_for_reviser": summary,
    })


def _recall_tool_call(call_id="call-1", query="一月上半研究成果"):
    return {"name": "recall_history", "args": {"query": query}, "id": call_id}


# --- Case A: available recall_history not attempted -> reviser must retry it ---

def test_retrieval_not_attempted_routes_to_reviser_with_recall_history(
    monkeypatch,
    tmp_path,
):
    graph = _ScriptedGraph([
        # Writer round: asks the user instead of searching chat history.
        [AIMessage(content="請提供完整研究背景，我才能寫 abstract。")],
        # Reviser round: actually calls recall_history, then drafts from it.
        [
            AIMessage(content="", tool_calls=[_recall_tool_call()]),
            ToolMessage(
                content=json.dumps([
                    {"role": "user", "text": "一月上半完成了 AI 模型訓練",
                     "turn_id": 3, "timestamp": "2026-01-10T00:00:00+00:00"},
                ], ensure_ascii=False),
                tool_call_id="call-1",
            ),
            AIMessage(content="DRAFT:\n根據對話紀錄，一月上半的成果是 AI 模型訓練。\n\nREBUTTAL:\n(none)"),
        ],
    ])
    models = {
        "rewrite": QueuedModel(["請依據既有對話紀錄整理一月上半成果的 abstract 重點。"]),
        "reviewer": QueuedModel([
            _review_json("revise", [{
                "severity": "major",
                "dimension": "instruction following",
                "location": "whole draft",
                "problem": "writer asked the user instead of searching chat history",
                "evidence_from_draft": "請提供完整研究背景",
                "revision_instruction": "Call recall_history for January progress before asking the user.",
                "needs_user_input": False,
                "failure_mode": "retrieval_not_attempted",
            }]),
            _review_json("pass", []),
        ]),
        "repair": QueuedModel([]),
    }
    runtime = _academic_runtime(
        tmp_path,
        effective=(
            "rag_explore", "rag_search", "rag_get_context",
            "recall_history", "read_file", "bash",
        ),
    )
    session = _make_session(monkeypatch, tmp_path, graph, models, runtime)

    outcome = asyncio.run(
        session.turn_outcome("你應該能看見我的紀錄才對，不應該問我")
    )
    answer, tool_calls = outcome.text, outcome.tool_calls

    # Two graph rounds: writer (no tool) then reviser (recall_history).
    assert len(graph.calls) == 2
    assert "recall_history" in [call["name"] for call in tool_calls]
    # The second graph round's input carried the reviewer feedback.
    reviser_prompt = "\n".join(str(m.content) for m in graph.calls[1]["messages"])
    assert "[Reviewer feedback]" in reviser_prompt
    # Final answer is the reviser draft grounded in retrieved history.
    assert answer == "根據對話紀錄，一月上半的成果是 AI 模型訓練。"
    assert "無法安全自動修正" not in answer


# --- Case B: recall_history attempted but empty -> honest user-facing answer ---

def test_empty_history_routes_to_honest_answer_with_storage_boundaries(
    monkeypatch,
    tmp_path,
):
    honest_draft = (
        "我用 recall_history 查了已保存的對話紀錄，但找不到足夠的一月研究內容。"
        "已索引的知識庫 (rag_search) 也沒有相關資料。"
        "你可以指定要我讀取的檔案，或補一句你記得的關鍵字。"
    )
    graph = _ScriptedGraph([
        [
            AIMessage(content="", tool_calls=[_recall_tool_call()]),
            ToolMessage(content="[]", tool_call_id="call-1"),
            AIMessage(content=honest_draft),
        ],
    ])
    models = {
        "rewrite": QueuedModel(["依據既有對話紀錄回答一月上半的研究成果。"]),
        "reviewer": QueuedModel([
            _review_json("revise", [{
                "severity": "minor",
                "dimension": "claim-evidence alignment",
                "location": "whole draft",
                "problem": "history retrieval returned no records",
                "evidence_from_draft": "找不到足夠的一月研究內容",
                "revision_instruction": "An honest 'insufficient records' answer is acceptable.",
                "needs_user_input": False,
                "failure_mode": "retrieval_empty",
            }]),
        ]),
        "repair": QueuedModel([]),
    }
    runtime = _academic_runtime(
        tmp_path,
        effective=(
            "rag_explore", "rag_search", "rag_get_context",
            "recall_history", "read_file", "bash",
        ),
    )
    session = _make_session(monkeypatch, tmp_path, graph, models, runtime)

    outcome = asyncio.run(
        session.turn_outcome("告訴我一月上半月我做的成果")
    )
    answer, tool_calls = outcome.text, outcome.tool_calls

    # Only the writer round runs; empty retrieval is accepted, not escalated.
    assert len(graph.calls) == 1
    assert "recall_history" in [call["name"] for call in tool_calls]
    assert answer == honest_draft
    # Honest answer distinguishes conversation history from the indexed KB.
    assert "recall_history" in answer
    assert "rag_search" in answer
    # It is not an internal stop/checklist message.
    assert "無法安全自動修正" not in answer
    assert "checklist" not in answer.lower()


# --- Case C: recall_history denied -> stop message blames policy, not the user ---

def test_unavailable_history_tool_routes_to_policy_explanation(
    monkeypatch,
    tmp_path,
):
    graph = _ScriptedGraph([
        [AIMessage(content="請先提供研究資料。")],
    ])
    models = {
        "rewrite": QueuedModel(["依據既有對話紀錄回答一月上半的研究成果。"]),
        "reviewer": QueuedModel([
            _review_json("block", [{
                "severity": "blocker",
                "dimension": "instruction following",
                "location": "whole draft",
                "problem": "history tool is unavailable under the active skill policy",
                "evidence_from_draft": "請先提供研究資料",
                # Internal-sounding instruction must be sanitized, not surfaced.
                "revision_instruction": "reviser 應回到 academic-paper-writing 的 Intake checklist 重新提問。",
                "needs_user_input": True,
                "failure_mode": "tool_unavailable",
            }]),
        ]),
        "repair": QueuedModel([]),
    }
    runtime = _academic_runtime(
        tmp_path,
        effective=(
            "rag_explore", "rag_search", "rag_get_context", "read_file", "bash",
        ),
    )
    session = _make_session(monkeypatch, tmp_path, graph, models, runtime)

    outcome = asyncio.run(
        session.turn_outcome("你應該能看見我的紀錄才對")
    )
    answer = outcome.text

    # No reviser round; the turn stops and asks the user.
    assert len(graph.calls) == 1
    # The stop message blames tool policy / settings, in user-readable terms.
    assert "工具設定" in answer or "active skill policy" in answer
    # The archived leak must not recur: no internal reviser text, no intake checklist.
    assert "reviser" not in answer.lower()
    assert "Intake checklist" not in answer
    assert "checklist" not in answer.lower()
