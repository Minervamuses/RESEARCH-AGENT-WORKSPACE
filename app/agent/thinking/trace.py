"""Evidence-trace summarization utilities for extended thinking."""

from __future__ import annotations

import json
from typing import Sequence

from langchain_core.messages import ToolMessage

from agent.history import group_tool_messages_by_call_id
from agent.llm.text import normalize_content
from agent.thinking.schemas import (
    FusionAggregateResult,
    FusionCandidate,
    FusionCandidateTrace,
    FusionTurnMetadata,
)

_TRUNCATED = "... [truncated]"
_OLDER_EVIDENCE_TRUNCATED = "... [older evidence truncated]"


def trim_tail(text: str, max_chars: int) -> str:
    """Head-truncate text while preserving its tail."""
    if not text:
        return ""
    if max_chars <= 0:
        return _TRUNCATED
    if len(text) <= max_chars:
        return text
    marker = f"{_TRUNCATED}\n"
    keep = max(max_chars - len(marker), 0)
    if keep <= 0:
        return _TRUNCATED
    return marker + text[-keep:]


def trim_head(text: str, max_chars: int) -> str:
    """Tail-truncate text while preserving its head."""
    if not text:
        return ""
    if max_chars <= 0:
        return _TRUNCATED
    if len(text) <= max_chars:
        return text
    marker = f"\n{_TRUNCATED}"
    keep = max(max_chars - len(marker), 0)
    if keep <= 0:
        return _TRUNCATED
    return text[:keep] + marker


def build_fusion_evidence_summary(
    *,
    candidates: Sequence[FusionCandidate],
    candidate_traces: Sequence[FusionCandidateTrace],
    aggregate_result: FusionAggregateResult,
    metadata: FusionTurnMetadata,
    per_result_chars: int = 500,
) -> str:
    """Build the reviewer evidence summary from the fusion result objects.

    Each candidate's tool trace is summarized from that candidate's own
    segmented trace, so the same ``tool_call_id`` appearing in two candidates is
    never cross-matched to the wrong ToolMessage.
    """
    trace_by_id = {trace.candidate_id: trace for trace in candidate_traces}
    lines = [
        "=== Fusion candidate panel ===",
        f"reliability_tier: {metadata.reliability_tier or '(none)'}",
        f"selected_candidate_ids: {', '.join(metadata.selected_ids) or '(none)'}",
        f"dropped_candidate_ids: {', '.join(metadata.dropped_ids) or '(none)'}",
        f"omitted_successful_ids: {', '.join(metadata.omitted_successful_ids) or '(none)'}",
    ]
    if metadata.aggregator_error:
        lines.append(f"aggregator_error: {metadata.aggregator_error}")
    if aggregate_result.summary_for_reviewer:
        lines.append(
            f"aggregator_summary_for_reviewer: {aggregate_result.summary_for_reviewer}"
        )
    if aggregate_result.removed_or_uncertain_points:
        lines.append("removed_or_uncertain_points:")
        lines.extend(
            f"  - {point}" for point in aggregate_result.removed_or_uncertain_points
        )
    for candidate in candidates:
        trace = trace_by_id.get(candidate.candidate_id)
        if trace is not None:
            tool_summary = summarize_tool_trace(
                trace.tool_calls,
                trace.new_messages,
                source_label=f"[{candidate.candidate_id} {candidate.model_id}]",
                per_result_chars=per_result_chars,
            )
        else:
            tool_summary = candidate.tool_trace_summary or "Tool calls: none"
        excerpt = (
            trim_head(candidate.answer, per_result_chars)
            if candidate.answer
            else "(no answer)"
        )
        lines.extend([
            f"--- {candidate.candidate_id} (model: {candidate.model_id}) "
            f"status={candidate.status} ---",
            f"answer_excerpt: {excerpt}",
            tool_summary,
        ])
        if candidate.error:
            lines.append(f"error: {candidate.error}")
    return "\n".join(lines)


def summarize_tool_trace(
    tool_calls: list[dict],
    new_messages: list,
    *,
    source_label: str,
    per_result_chars: int = 500,
) -> str:
    """Summarize graph tool calls and matching ToolMessage result excerpts."""
    lines = [f"=== {source_label} ==="]
    if not tool_calls:
        lines.append("Tool calls: none")
        return "\n".join(lines)

    tool_messages = group_tool_messages_by_call_id(new_messages)
    seen: set[tuple[str, str, str]] = set()
    for call in tool_calls:
        name = str(call.get("name", "unknown"))
        args_text = json.dumps(call.get("args", {}), ensure_ascii=False, sort_keys=True)
        result_text = _tool_result_text(tool_messages.get(str(call.get("id")), []))
        result_excerpt = trim_head(result_text, per_result_chars) if result_text else "(no result)"
        key = (name, args_text, result_excerpt)
        if key in seen:
            continue
        seen.add(key)
        lines.extend([
            f"- tool: {name}",
            f"  args: {args_text}",
            "  result_excerpt: |",
            *_indent_block(result_excerpt, "    "),
        ])
    return "\n".join(lines)


def append_tool_trace(
    existing: str,
    tool_calls: list[dict],
    new_messages: list,
    *,
    source_label: str,
    per_result_chars: int = 500,
    total_chars_cap: int = 4000,
) -> str:
    """Append one trace segment and keep the newest evidence within a char cap."""
    new_segment = summarize_tool_trace(
        tool_calls,
        new_messages,
        source_label=source_label,
        per_result_chars=per_result_chars,
    )
    combined = "\n\n".join(part for part in (existing.strip(), new_segment.strip()) if part)
    if total_chars_cap <= 0 or len(combined) <= total_chars_cap:
        return combined
    marker = f"{_OLDER_EVIDENCE_TRUNCATED}\n"
    keep = max(total_chars_cap - len(marker), 0)
    if keep <= 0:
        return _OLDER_EVIDENCE_TRUNCATED
    return marker + combined[-keep:]


def _tool_result_text(messages: list[ToolMessage]) -> str:
    return "\n".join(
        normalize_content(getattr(message, "content", ""), drop_unknown_parts=False)
        for message in messages
    ).strip()


def _indent_block(text: str, prefix: str) -> list[str]:
    return [f"{prefix}{line}" for line in text.splitlines() or [""]]
