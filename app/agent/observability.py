"""Structured, redaction-safe logging for model responses in the agent loop.

One log line per model response at each recovery stage (initial, repair,
fallback, and any future continuation stage) so a live incident can be
diagnosed after the fact: was the response a true zero-content reply, a
malformed tool call (``invalid_tool_calls``), or a budget-capped one?

Privacy contract: only counts, lengths, identifiers, and enum-like fields are
ever logged. Message content, tool-call arguments, DOIs, and provider free
text never reach the log record.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from langchain_core.messages import AIMessage, ToolMessage

from agent.llm.text import normalize_content

logger = logging.getLogger(__name__)

_CITATION_TOOL_NAME = "citation_workflow"


def last_completed_citation_action(messages: Iterable[object]) -> str | None:
    """The action of the most recent completed citation_workflow call.

    Completed means the structured call has a matching ToolMessage result.
    Only the action string is returned — never the remaining arguments.
    """
    action_by_id: dict[str, str] = {}
    for message in messages:
        if not isinstance(message, AIMessage):
            continue
        for tool_call in getattr(message, "tool_calls", None) or []:
            if not isinstance(tool_call, dict):
                continue
            if tool_call.get("name") != _CITATION_TOOL_NAME:
                continue
            call_id = tool_call.get("id")
            args = tool_call.get("args")
            if call_id is None or not isinstance(args, dict):
                continue
            action = args.get("action")
            if isinstance(action, str):
                action_by_id[str(call_id)] = action

    last_action: str | None = None
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        action = action_by_id.get(str(getattr(message, "tool_call_id", None)))
        if action is not None:
            last_action = action
    return last_action


def _usage_tokens(message: AIMessage) -> tuple[object, object, object]:
    usage = getattr(message, "usage_metadata", None)
    if isinstance(usage, dict) and usage:
        return (
            usage.get("input_tokens"),
            usage.get("output_tokens"),
            usage.get("total_tokens"),
        )
    token_usage = (message.response_metadata or {}).get("token_usage")
    if isinstance(token_usage, dict):
        return (
            token_usage.get("prompt_tokens"),
            token_usage.get("completion_tokens"),
            token_usage.get("total_tokens"),
        )
    return (None, None, None)


def summarize_model_response(
    message: AIMessage,
    *,
    stage: str,
    issue: str | None,
    dropped_tool_calls: int,
    primary_remaining: int,
    local_remaining: int,
    last_citation_action: str | None,
) -> dict[str, object]:
    """Build the redaction-safe summary record for one model response."""
    metadata = message.response_metadata or {}
    input_tokens, output_tokens, total_tokens = _usage_tokens(message)
    return {
        "stage": stage,
        "response_id": metadata.get("id") or message.id,
        "finish_reason": metadata.get("finish_reason"),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "content_chars": len(
            normalize_content(message.content, drop_unknown_parts=False)
        ),
        "tool_calls": len(getattr(message, "tool_calls", None) or []),
        "invalid_tool_calls": len(
            getattr(message, "invalid_tool_calls", None) or []
        ),
        "dropped_tool_calls": dropped_tool_calls,
        "last_citation_action": last_citation_action,
        "primary_budget_remaining": primary_remaining,
        "local_budget_remaining": local_remaining,
        "issue": issue,
    }


def _format_record(record: dict[str, object]) -> str:
    return " ".join(f"{key}={record[key]}" for key in record)


def log_model_response(
    message: AIMessage,
    *,
    stage: str,
    issue: str | None,
    dropped_tool_calls: int,
    primary_remaining: int,
    local_remaining: int,
    messages: Iterable[object],
) -> None:
    """Log one model response summary at a severity useful in the default CLI.

    ``messages`` is the pre-response history used solely to derive the last
    completed citation action; nothing from it is logged verbatim. Invalid
    responses are warnings so an incident is visible without logging setup;
    normal responses stay at debug to avoid noisy interactive output.
    """
    record = summarize_model_response(
        message,
        stage=stage,
        issue=issue,
        dropped_tool_calls=dropped_tool_calls,
        primary_remaining=primary_remaining,
        local_remaining=local_remaining,
        last_citation_action=last_completed_citation_action(messages),
    )
    log = logger.warning if issue is not None else logger.debug
    log("model_response %s", _format_record(record))


def log_recovery_fallback(
    *,
    issue: str | None,
    repair_issue: str | None,
    primary_remaining: int,
    local_remaining: int,
    messages: Iterable[object],
) -> None:
    """Log the deterministic-fallback event (no model response to summarize)."""
    record = {
        "stage": "fallback",
        "issue": issue,
        "repair_issue": repair_issue,
        "last_citation_action": last_completed_citation_action(messages),
        "primary_budget_remaining": primary_remaining,
        "local_budget_remaining": local_remaining,
    }
    logger.warning("model_response %s", _format_record(record))
