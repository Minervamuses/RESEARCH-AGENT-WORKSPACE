"""Structured, redaction-safe model and citation-finalizer observability.

One log line per model response at each recovery stage (initial, repair,
fallback, and any future continuation stage) so a live incident can be
diagnosed after the fact: was the response a true zero-content reply, a
malformed tool call (``invalid_tool_calls``), or a budget-capped one?
Finalizer-verified citation saves additionally emit only batch state and item
counts, clearly separated from tool execution status.

Privacy contract: only counts, lengths, identifiers, and enum-like fields are
ever logged. Message content, tool-call arguments, DOIs, and provider free
text never reach the log record.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from langchain_core.messages import AIMessage, ToolMessage

from agent.llm.text import normalize_content

logger = logging.getLogger(__name__)

_CITATION_TOOL_NAME = "citation_workflow"
_CITATION_ACTIONS = frozenset({"search", "save", "sources", "source", "explain"})


@dataclass(frozen=True)
class CitationSaveMetrics:
    """Redaction-safe result of finalizer-verified citation save artifacts."""

    batch_status: Literal["attempted", "rejected"] | None = None
    new_saved_count: int = 0
    reused_count: int = 0
    failed_count: int = 0

    def __post_init__(self) -> None:
        if self.batch_status not in {None, "attempted", "rejected"}:
            raise ValueError("invalid citation save batch status")
        counts = (
            self.new_saved_count,
            self.reused_count,
            self.failed_count,
        )
        if any(type(value) is not int or value < 0 for value in counts):
            raise ValueError("citation save metrics require non-negative counts")
        if self.batch_status != "attempted" and any(counts):
            raise ValueError("only attempted batches can contain item counts")

    def to_record(self) -> dict[str, object]:
        return {
            "citation_save_batch_status": self.batch_status,
            "new_saved_count": self.new_saved_count,
            "reused_count": self.reused_count,
            "failed_count": self.failed_count,
        }


def completed_citation_calls(
    messages: Iterable[object],
) -> tuple[tuple[str, str], ...]:
    """Return redacted action/status pairs for answered citation calls.

    Answered means the structured call has a matching ``ToolMessage``. Tool
    status distinguishes normal execution from an error, but neither value
    claims that a save succeeded. Arguments and result content are ignored.
    """
    message_list = list(messages)
    action_by_id: dict[str, str] = {}
    for message in message_list:
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
            raw_action = args.get("action")
            if isinstance(raw_action, str):
                action = raw_action if raw_action in _CITATION_ACTIONS else "unknown"
                action_by_id[str(call_id)] = action

    completed: list[tuple[str, str]] = []
    for message in message_list:
        if not isinstance(message, ToolMessage):
            continue
        if getattr(message, "name", None) not in {None, _CITATION_TOOL_NAME}:
            continue
        action = action_by_id.get(str(getattr(message, "tool_call_id", None)))
        if action is not None:
            raw_status = getattr(message, "status", "success")
            status = raw_status if raw_status in {"success", "error"} else "unknown"
            completed.append((action, status))
    return tuple(completed)


def last_completed_citation_call(
    messages: Iterable[object],
) -> tuple[str | None, str | None]:
    """Return the latest answered citation call, if one exists."""
    completed = completed_citation_calls(messages)
    return completed[-1] if completed else (None, None)


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
    last_citation_tool_status: str | None,
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
        "last_citation_tool_status": last_citation_tool_status,
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
    last_action, last_tool_status = last_completed_citation_call(messages)
    record = summarize_model_response(
        message,
        stage=stage,
        issue=issue,
        dropped_tool_calls=dropped_tool_calls,
        primary_remaining=primary_remaining,
        local_remaining=local_remaining,
        last_citation_action=last_action,
        last_citation_tool_status=last_tool_status,
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
    last_action, last_tool_status = last_completed_citation_call(messages)
    record = {
        "stage": "fallback",
        "issue": issue,
        "repair_issue": repair_issue,
        "last_citation_action": last_action,
        "last_citation_tool_status": last_tool_status,
        "primary_budget_remaining": primary_remaining,
        "local_budget_remaining": local_remaining,
    }
    logger.warning("model_response %s", _format_record(record))


def log_citation_save_metrics(
    metrics: CitationSaveMetrics,
    *,
    save_call_observed: bool,
) -> None:
    """Log trusted metrics, or fixed empty metrics when a save lacks them."""
    if metrics.batch_status is None and not save_call_observed:
        return
    log = (
        logger.warning
        if metrics.batch_status == "rejected"
        or metrics.failed_count > 0
        or metrics.batch_status is None
        else logger.info
    )
    log(
        "citation_save_finalized %s",
        _format_record(metrics.to_record()),
    )
