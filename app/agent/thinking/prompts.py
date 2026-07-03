"""zh-TW prompt templates and message builders for extended thinking."""

from __future__ import annotations

from typing import Sequence

from langchain_core.messages import HumanMessage, SystemMessage

from agent.skills.runtime import render_tool_availability_block
from agent.thinking.schemas import FusionCandidate

_CLARIFY_SENTINEL = "<<CLARIFY>>"
_RETRIEVAL_REVIEW_RULES = """
Finding routing contract, highest priority:
- Before writing any finding, choose whether the issue is recoverable by another
  writer/reviser pass or genuinely needs the user.
- Set failure_mode on each finding when one applies:
  retrieval_not_attempted, retrieval_empty, tool_unavailable,
  user_input_missing, or fabrication_risk.
- Use needs_user_input=true only when another writer/reviser pass cannot fix the
  issue with the currently available tools.
- If the user asks for earlier conversation content and the relevant
  history-retrieval tool is listed under available_tools, but the evidence trace
  has no matching tool call, emit decision=revise with one finding shaped as
  severity=major and needs_user_input=false. The revision_instruction is for the
  writer/reviser and must name the available tool and query to try.
- If the relevant history-retrieval tool was called and the result is empty,
  do not ask the user to restate all research content. Use severity=minor or
  severity=note with needs_user_input=false, and allow an honest draft that says
  the search found insufficient records. A narrow follow-up question is allowed.
- If the relevant history-retrieval tool appears under denied_tools or
  unavailable_base_tools, emit severity=blocker with needs_user_input=true and
  decision=block; the revision_instruction must be user-readable and explain
  that this is a tool policy/settings problem.
- If the user truly has not provided necessary information and the available
  tools cannot recover it, needs_user_input=true is allowed, but the
  revision_instruction must be a concrete user-facing question.
- If the draft introduces research results, data, methods, citations, quotes,
  page numbers, or claims not supported by the input or evidence trace, block
  or revise it. Never allow fabricated scholarly content.
""".strip()


def rewrite_messages(
    *,
    skill_text: str,
    user_input: str,
    visible_context: str,
    skill_context: str,
    tool_availability: str = "",
) -> list:
    """Build prompt-master rewrite messages."""
    availability = tool_availability.strip() or render_tool_availability_block()
    wrapper = f"""

[內部 extended-thinking wrapper]

你是內部 pipeline 的一環。target tool 是一個 LangGraph research agent。
以下工具可用性區塊是該 agent 本 turn 的實際工具狀態，必須視為唯一事實來源：

{availability}

請把使用者的 prompt 改寫成給該 agent 看的自然語言指令。
若某工具或工具 family 不在 available_tools 內，或出現在 denied_tools /
unavailable_base_tools 內，不要假設 target agent 可以使用它。

硬性禁令：你不得新增以下「原始輸入、visible context 與 active skill context」
三者都未提供的內容：
- citation、DOI、page number、quote
- 數據、樣本數、dataset 名稱、統計結果
- 研究方法細節、實驗條件、研究發現
- 對使用者意圖的擴張詮釋

若必要事實缺失，不要自行補齊，請向使用者詢問。

若需要使用者補充資訊：
第一行寫 <<CLARIFY>>，然後列出最多 3 個澄清問題。

若資訊足夠：
直接輸出改寫後的 prompt，不要前綴、不要解釋、不要 code fence。

語言策略：改寫後的 prompt 與澄清問題使用與「Original user input」相同的語言。
如果使用者輸入是中文，輸出使用繁體中文（絕對不要使用簡體），保留技術專有名詞
（RAG、GPT、DOI、LangGraph、MCP 等）原文，不要翻譯。
""".strip()
    return [
        SystemMessage(content=f"{skill_text.rstrip()}\n\n{wrapper}"),
        HumanMessage(content=(
            f"Original user input:\n{user_input}\n\n"
            "Visible context (recent turns, tail-truncated):\n"
            f"{visible_context or '(none)'}\n\n"
            "Active skill context (head-truncated):\n"
            f"{skill_context or '(none)'}"
        )),
    ]


def review_messages(
    *,
    raw_user_input: str,
    rewritten_prompt: str,
    draft: str,
    skill_context: str,
    evidence_trace_summary: str,
    previous_rebuttal: str,
    tool_availability: str = "",
) -> list:
    """Build reviewer messages for a structured ReviewReport JSON response."""
    availability = tool_availability.strip() or render_tool_availability_block()
    return [
        SystemMessage(content=(
            "You are an independent reviewer for extended thinking mode. "
            "Review the draft against the raw user input, rewritten prompt, "
            "active skill context, tool availability, evidence trace, and previous rebuttal. "
            "Return only valid JSON matching ReviewReport. Do not rewrite the draft.\n\n"
            "語言策略：JSON 內所有自然語言欄位（problem、evidence_from_draft、"
            "revision_instruction、summary_for_reviser）使用與「Raw user input」"
            "相同的語言。如果 raw input 是中文，所有自然語言欄位都使用繁體中文"
            "（絕對不要使用簡體），保留技術專有名詞（RAG、GPT、DOI、JSON 等）原文。"
        )),
        HumanMessage(content=(
            "ReviewReport schema:\n"
            "{\n"
            '  "decision": "pass|revise|block",\n'
            '  "findings": [\n'
            "    {\n"
            '      "severity": "blocker|major|minor|note",\n'
            '      "dimension": "instruction following|background logic|method logic|'
            'claim-evidence alignment|citation integrity|section coherence|other",\n'
            '      "location": "where the issue appears",\n'
            '      "problem": "what is wrong",\n'
            '      "evidence_from_draft": "quote or paraphrase from the draft",\n'
            '      "revision_instruction": "specific fix or user question",\n'
            '      "needs_user_input": true,\n'
            '      "failure_mode": "retrieval_not_attempted|retrieval_empty|'
            'tool_unavailable|user_input_missing|fabrication_risk|null"\n'
            "    }\n"
            "  ],\n"
            '  "summary_for_reviser": "concise actionable summary"\n'
            "}\n\n"
            f"{_RETRIEVAL_REVIEW_RULES}\n\n"
            f"Raw user input:\n{raw_user_input}\n\n"
            f"Rewritten prompt:\n{rewritten_prompt}\n\n"
            f"Active skill context:\n{skill_context or '(none)'}\n\n"
            f"Tool availability:\n{availability}\n\n"
            f"Evidence trace summary:\n{evidence_trace_summary or '(none)'}\n\n"
            f"Previous rebuttal:\n{previous_rebuttal or '(none)'}\n\n"
            f"Draft:\n{draft}"
        )),
    ]


def aggregate_messages(
    *,
    raw_user_input: str,
    rewritten_prompt: str,
    successful_candidates: Sequence[FusionCandidate],
    skill_context: str = "",
    tool_availability: str = "",
) -> list:
    """Build aggregator messages that fuse successful candidate answers.

    The aggregator is a plain LLM synthesis step, NOT a tool call. Its prompt
    must never describe itself as tool evidence so downstream traces keep the
    aggregator out of ``tool_calls``.
    """
    availability = tool_availability.strip() or render_tool_availability_block()
    candidate_blocks = []
    for candidate in successful_candidates:
        candidate_blocks.append(
            f"--- {candidate.candidate_id} (model: {candidate.model_id}) ---\n"
            f"Answer:\n{candidate.answer}\n\n"
            f"Tool trace summary:\n{candidate.tool_trace_summary or '(none)'}"
        )
    candidates_text = "\n\n".join(candidate_blocks) or "(none)"
    valid_ids = ", ".join(candidate.candidate_id for candidate in successful_candidates)
    return [
        SystemMessage(content=(
            "You are the aggregator for extended thinking mode. Several proposer "
            "agents independently answered the same rewritten prompt. Fuse their "
            "candidate answers into one best full-text draft. You are performing a "
            "synthesis step, not calling a tool, and you must not invent a tool "
            "call. Prefer claims that multiple candidates agree on; drop claims "
            "only one candidate makes that look unsupported by its tool trace. Do "
            "not introduce citations, data, methods, or findings that no candidate "
            "and neither the raw input nor the skill context provides. Return only "
            "valid JSON matching the schema. Use only the supplied candidate ids.\n\n"
            "語言策略：JSON 內所有自然語言欄位（draft、summary_for_reviewer、"
            "removed_or_uncertain_points）使用與「Raw user input」相同的語言。"
            "如果 raw input 是中文，使用繁體中文（絕對不要使用簡體），保留技術專有"
            "名詞（RAG、GPT、DOI、JSON 等）原文。"
        )),
        HumanMessage(content=(
            "Aggregate result schema:\n"
            "{\n"
            '  "draft": "the fused full-text answer for the user",\n'
            '  "selected_candidate_ids": ["candidate ids whose content you kept"],\n'
            '  "dropped_candidate_ids": ["candidate ids you rejected"],\n'
            '  "summary_for_reviewer": "what you merged, agreed, or rejected",\n'
            '  "removed_or_uncertain_points": ["claims you removed or flagged uncertain"]\n'
            "}\n\n"
            f"Valid candidate ids: {valid_ids or '(none)'}\n"
            "selected_candidate_ids and dropped_candidate_ids must each be a subset "
            "of the valid candidate ids and must not overlap.\n\n"
            f"Raw user input:\n{raw_user_input}\n\n"
            f"Rewritten prompt:\n{rewritten_prompt}\n\n"
            f"Active skill context:\n{skill_context or '(none)'}\n\n"
            f"Tool availability:\n{availability}\n\n"
            f"Candidate answers:\n{candidates_text}"
        )),
    ]
