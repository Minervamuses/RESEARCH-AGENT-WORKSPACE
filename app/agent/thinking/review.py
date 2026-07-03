"""Review routing and the rewrite / review / aggregate LLM steps."""

from __future__ import annotations

import re
from typing import Sequence

from agent.llm.text import invoke_text_messages as invoke_text
from agent.thinking.parsers import parse_aggregate_result, parse_structured_output
from agent.thinking.prompts import (
    _CLARIFY_SENTINEL,
    aggregate_messages,
    review_messages,
    rewrite_messages,
)
from agent.thinking.schemas import (
    Clarify,
    FusionAggregateResult,
    FusionCandidate,
    ReviewFinding,
    ReviewReport,
    ReviewRoute,
    Rewrite,
    RewriteResult,
)

MAX_REVIEW_ATTEMPTS = 2

_RECOVERABLE_FAILURE_MODES = frozenset({
    "retrieval_not_attempted",
    "retrieval_empty",
})
_USER_BLOCKING_FAILURE_MODES = frozenset({
    "tool_unavailable",
    "user_input_missing",
})
_INTERNAL_REVISION_RE = re.compile(
    r"\b(?:reviser|writer|reviewer|finding|revision_instruction|"
    r"summary_for_reviser)\b|(?:reviser|writer|reviewer)\s*(?:應|should|must)|"
    r"\bdraft\s+(?:should|must)\b|內部|審稿意見",
    re.IGNORECASE,
)


def route_review_report(
    report: ReviewReport,
    *,
    attempts: int,
    max_attempts: int = MAX_REVIEW_ATTEMPTS,
) -> ReviewRoute:
    """Route review findings with blocker/user-input checks before revision."""
    recoverable_findings = [
        finding
        for finding in report.findings
        if finding.failure_mode in _RECOVERABLE_FAILURE_MODES
    ]
    blocking_findings = [
        finding
        for finding in report.findings
        if finding.failure_mode in _USER_BLOCKING_FAILURE_MODES
    ]

    if blocking_findings:
        return "ask_user"
    if any(
        finding.needs_user_input
        for finding in report.findings
        if finding.failure_mode not in _RECOVERABLE_FAILURE_MODES
    ):
        return "ask_user"
    if report.decision == "block" and recoverable_findings:
        if attempts >= max_attempts:
            return "stop"
        return "revise"
    if report.decision == "block" or any(
        finding.severity == "blocker"
        and finding.failure_mode not in _RECOVERABLE_FAILURE_MODES
        for finding in report.findings
    ):
        return "ask_user"
    if report.decision == "pass":
        return "pass"
    if attempts >= max_attempts:
        return "stop"
    if any(
        finding.failure_mode == "retrieval_not_attempted"
        for finding in report.findings
    ):
        return "revise"
    if any(finding.severity == "major" for finding in report.findings):
        return "revise"
    return "pass"


def render_review_stop_message(report: ReviewReport) -> str:
    """Render a user-facing stop message for blocker or missing-input findings."""
    findings = [
        finding
        for finding in report.findings
        if finding.needs_user_input or finding.severity == "blocker"
    ]
    if not findings:
        return "目前仍有無法安全自動修正的問題，需要使用者確認。"
    lines = ["目前仍有無法安全自動修正的問題，需要使用者確認："]
    lines.extend(f"- {_user_facing_review_instruction(finding)}" for finding in findings)
    return "\n".join(lines)


def _user_facing_review_instruction(finding: ReviewFinding) -> str:
    instruction = (finding.revision_instruction or "").strip()
    if instruction and not _looks_internal_review_instruction(instruction):
        return instruction

    if finding.failure_mode == "tool_unavailable":
        return (
            "目前需要的工具被 active skill policy 或工具設定排除；請切換 skill、"
            "調整工具設定，或提供可由目前工具讀取的資料位置。"
        )
    if finding.failure_mode == "fabrication_risk":
        return (
            "目前草稿包含缺乏 evidence 支撐的研究內容；請提供來源，"
            "或允許我移除那些 unsupported claims。"
        )
    return "需要更多資訊才能安全完成這個任務；請補充缺少的資料或材料位置。"


def _looks_internal_review_instruction(text: str) -> bool:
    return bool(_INTERNAL_REVISION_RE.search(text))


def render_route_message(
    route: ReviewRoute,
    draft: str,
    report: ReviewReport,
    *,
    format_warning: str = "",
) -> str:
    """Render the final user-visible message for a reviewer route."""
    if route == "ask_user":
        return render_review_stop_message(report)
    if route == "stop":
        answer = (
            draft.rstrip()
            + "\n\n仍需確認處：\n"
            + (report.summary_for_reviser or "Reviewer 仍指出未完全修正的問題。")
        )
        return _prepend_warning(answer, format_warning)
    return _prepend_warning(draft, format_warning)


def _prepend_warning(answer: str, warning: str) -> str:
    if not warning:
        return answer
    return f"{warning}\n\n{answer}"


def rewrite_prompt(
    model,
    *,
    skill_text: str,
    user_input: str,
    visible_context: str = "",
    skill_context: str = "",
    tool_availability: str = "",
) -> RewriteResult:
    """Run prompt-master rewrite and parse clarify vs rewritten prompt."""
    text = invoke_text(
        model,
        rewrite_messages(
            skill_text=skill_text,
            user_input=user_input,
            visible_context=visible_context,
            skill_context=skill_context,
            tool_availability=tool_availability,
        ),
    )
    stripped = text.lstrip()
    if stripped.startswith(_CLARIFY_SENTINEL):
        return Clarify(text=stripped[len(_CLARIFY_SENTINEL):].strip())
    return Rewrite(prompt=text.strip())


def review_draft(
    model,
    *,
    raw_user_input: str,
    rewritten_prompt: str,
    draft: str,
    skill_context: str = "",
    evidence_trace_summary: str = "",
    previous_rebuttal: str = "",
    tool_availability: str = "",
) -> ReviewReport:
    """Run the reviewer LLM step and parse a ReviewReport."""
    text = invoke_text(
        model,
        review_messages(
            raw_user_input=raw_user_input,
            rewritten_prompt=rewritten_prompt,
            draft=draft,
            skill_context=skill_context,
            evidence_trace_summary=evidence_trace_summary,
            previous_rebuttal=previous_rebuttal,
            tool_availability=tool_availability,
        ),
    )
    return parse_structured_output(ReviewReport, text)


def aggregate_candidates(
    model,
    *,
    raw_user_input: str,
    rewritten_prompt: str,
    successful_candidates: Sequence[FusionCandidate],
    skill_context: str = "",
    tool_availability: str = "",
) -> FusionAggregateResult:
    """Run the aggregator LLM over successful candidates and parse the result.

    Only successful candidates may be passed; failed, timed-out, or empty
    candidates belong in fusion metadata and reviewer evidence, never in the
    aggregator's candidate input.
    """
    text = invoke_text(
        model,
        aggregate_messages(
            raw_user_input=raw_user_input,
            rewritten_prompt=rewritten_prompt,
            successful_candidates=successful_candidates,
            skill_context=skill_context,
            tool_availability=tool_availability,
        ),
    )
    return parse_aggregate_result(
        text,
        successful_candidate_ids=[c.candidate_id for c in successful_candidates],
    )
