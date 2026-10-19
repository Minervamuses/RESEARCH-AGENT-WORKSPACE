"""Structured, redaction-safe model and citation-save observability.

One log line per model response at each recovery stage (initial, repair,
fallback, and any future continuation stage) so a live incident can be
diagnosed after the fact: was the response a true zero-content reply, a
malformed tool call (``invalid_tool_calls``), or a tool call stripped from a
stage that must be tool-free?
Artifact-derived citation saves additionally emit only aggregate item counts,
clearly separated from tool execution status.

A per-attempt ``TurnTimingTrace`` callback additionally logs when each model
call and admitted tool call actually ran, so a slow turn can be split into
model and tool intervals from the persistent diagnostic log.

Privacy contract: only counts, lengths, identifiers, hashes, durations, and
enum-like fields are ever logged. Message content, tool-call arguments, raw
queries, DOIs, and provider free text never reach the log record.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, ToolMessage

from agent.llm.text import normalize_content

logger = logging.getLogger(__name__)

_CITATION_TOOL_NAME = "citation_workflow"
_CITATION_ACTIONS = frozenset({"search", "save", "sources", "source", "explain"})


@dataclass(frozen=True)
class CitationSaveMetrics:
    """Redaction-safe aggregate of attempted citation save artifacts."""

    batch_count: int = 0
    new_saved_count: int = 0
    reused_count: int = 0
    failed_count: int = 0

    def __post_init__(self) -> None:
        counts = (
            self.batch_count,
            self.new_saved_count,
            self.reused_count,
            self.failed_count,
        )
        if any(type(value) is not int or value < 0 for value in counts):
            raise ValueError("citation save metrics require non-negative counts")
        if self.batch_count == 0 and any(counts[1:]):
            raise ValueError("save item counts require a parsed batch")

    def to_record(self) -> dict[str, object]:
        return {
            "citation_save_batch_count": self.batch_count,
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
    graph_steps_remaining: int,
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
        "graph_steps_remaining": graph_steps_remaining,
        "last_citation_action": last_citation_action,
        "last_citation_tool_status": last_citation_tool_status,
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
    graph_steps_remaining: int,
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
        graph_steps_remaining=graph_steps_remaining,
        last_citation_action=last_action,
        last_citation_tool_status=last_tool_status,
    )
    log = logger.warning if issue is not None else logger.debug
    log("model_response %s", _format_record(record))


def log_recovery_fallback(
    *,
    issue: str | None,
    repair_issue: str | None,
    graph_steps_remaining: int,
    messages: Iterable[object],
) -> None:
    """Log the deterministic-fallback event (no model response to summarize)."""
    last_action, last_tool_status = last_completed_citation_call(messages)
    record = {
        "stage": "fallback",
        "issue": issue,
        "repair_issue": repair_issue,
        "graph_steps_remaining": graph_steps_remaining,
        "last_citation_action": last_action,
        "last_citation_tool_status": last_tool_status,
    }
    logger.warning("model_response %s", _format_record(record))


def log_citation_save_metrics(
    metrics: CitationSaveMetrics,
    *,
    save_call_observed: bool,
) -> None:
    """Log aggregate metrics, or fixed empty metrics when a save lacks them."""
    if metrics.batch_count == 0 and not save_call_observed:
        return
    log = (
        logger.warning
        if metrics.failed_count > 0
        or metrics.batch_count == 0
        else logger.info
    )
    log(
        "citation_save_finalized %s",
        _format_record(metrics.to_record()),
    )


_MAX_TRACE_ID_CHARS = 64


def query_hash(query: str) -> str:
    """Return a short irreversible digest that links repeated queries."""
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]


def _trace_id(value: object) -> str | None:
    return str(value)[:_MAX_TRACE_ID_CHARS] if value is not None else None


def _tool_result_counts(output: object) -> dict[str, object]:
    """Read allowlisted counts from structured tool artifacts only."""
    artifact = getattr(output, "artifact", None)
    if not isinstance(artifact, dict):
        return {}
    if artifact.get("kind") == "citation_search_summary":
        return {
            key: artifact.get(key)
            for key in ("candidate_count", "abstract_count", "provider_count", "failed_provider_count")
        }
    if artifact.get("kind") == "citation_save_batch":
        statuses = [item.get("status") for item in artifact.get("items") or [] if isinstance(item, dict)]
        return {
            "save_items": len(statuses),
            "save_saved": statuses.count("saved"),
            "save_reused": statuses.count("reused"),
        }
    return {}


class TurnTimingTrace(BaseCallbackHandler):
    """Log the real start and end of every model and tool run in one attempt.

    One instance covers one execution attempt of a logical turn; a retry gets
    a new ``attempt``. ``at_ms`` is the monotonic offset from the attempt
    start and ``duration_ms`` the monotonic run length, so parallel tool runs
    keep their own intervals. Model calls include recovery re-invocations;
    SDK-internal HTTP retries stay inside one model interval. Runs still open
    when the turn ends are logged as ``unfinished``.
    """

    run_inline = True

    def __init__(self, turn_id: str, *, clock: Callable[[], float] = time.monotonic):
        self.turn_id = turn_id
        self.attempt = uuid.uuid4().hex[:12]
        self._clock = clock
        self._started = clock()
        self._lock = threading.Lock()
        self._model_seq = 0
        self._tool_count = 0
        self._model_runs: dict[UUID, tuple[int, float]] = {}
        self._tool_runs: dict[UUID, tuple[dict[str, object], float]] = {}
        self._model_by_call: dict[str, int] = {}
        self._finished = False
        self._emit("turn_start", {})

    def _ms(self, since: float | None = None) -> int:
        return round((self._clock() - (self._started if since is None else since)) * 1000)

    def _emit(self, event: str, fields: dict[str, object]) -> None:
        record = {"event": event, "turn_id": self.turn_id, "attempt": self.attempt, **fields}
        logger.info("turn_trace %s", _format_record(record))

    def on_chat_model_start(self, serialized, messages, *, run_id: UUID, **kwargs: Any) -> None:
        with self._lock:
            if self._finished:
                return
            self._model_seq += 1
            self._model_runs[run_id] = (self._model_seq, self._clock())
            self._emit("model_start", {"model_seq": self._model_seq, "at_ms": self._ms()})

    def on_llm_end(self, response, *, run_id: UUID, **kwargs: Any) -> None:
        with self._lock:
            run = self._model_runs.pop(run_id, None)
            if run is None or self._finished:
                return
            seq, started = run
            tool_calls = 0
            input_tokens = output_tokens = None
            for generations in getattr(response, "generations", None) or []:
                for generation in generations:
                    message = getattr(generation, "message", None)
                    if not isinstance(message, AIMessage):
                        continue
                    for call in message.tool_calls or []:
                        tool_calls += 1
                        if call.get("id") is not None:
                            self._model_by_call[str(call["id"])] = seq
                    input_tokens, output_tokens, _total = _usage_tokens(message)
            self._emit("model_end", {
                "model_seq": seq, "status": "ok", "at_ms": self._ms(),
                "duration_ms": self._ms(started), "tool_calls": tool_calls,
                "input_tokens": input_tokens, "output_tokens": output_tokens,
            })

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        with self._lock:
            run = self._model_runs.pop(run_id, None)
            if run is None or self._finished:
                return
            seq, started = run
            self._emit("model_end", {
                "model_seq": seq, "status": "error", "error_type": type(error).__name__,
                "at_ms": self._ms(), "duration_ms": self._ms(started),
            })

    def on_tool_start(self, serialized, input_str, *, run_id: UUID, inputs=None, **kwargs: Any) -> None:
        with self._lock:
            if self._finished:
                return
            name = (serialized or {}).get("name") or kwargs.get("name")
            call_id = _trace_id(kwargs.get("tool_call_id"))
            fields: dict[str, object] = {
                "tool": _trace_id(name), "tool_call_id": call_id,
                "model_seq": self._model_by_call.get(call_id) if call_id is not None else None,
            }
            if isinstance(inputs, dict):
                action = inputs.get("action")
                if name == _CITATION_TOOL_NAME and isinstance(action, str):
                    fields["action"] = action if action in _CITATION_ACTIONS else "unknown"
                if isinstance(inputs.get("query"), str):
                    fields["query_hash"] = query_hash(inputs["query"])
            self._tool_count += 1
            self._tool_runs[run_id] = (fields, self._clock())
            self._emit("tool_start", {**fields, "at_ms": self._ms()})

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        with self._lock:
            run = self._tool_runs.pop(run_id, None)
            if run is None or self._finished:
                return
            fields, started = run
            status = getattr(output, "status", "success") if isinstance(output, ToolMessage) else "success"
            self._emit("tool_end", {
                **fields, "status": "error" if status == "error" else "ok",
                "at_ms": self._ms(), "duration_ms": self._ms(started), **_tool_result_counts(output),
            })

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        with self._lock:
            run = self._tool_runs.pop(run_id, None)
            if run is None or self._finished:
                return
            fields, started = run
            self._emit("tool_end", {
                **fields, "status": "error", "error_type": type(error).__name__,
                "at_ms": self._ms(), "duration_ms": self._ms(started),
            })

    def finish(self, state: str) -> None:
        """Close the attempt; runs that never reported an end stay visible."""
        with self._lock:
            if self._finished:
                return
            self._finished = True
            unfinished = 0
            for seq, started in self._model_runs.values():
                unfinished += 1
                self._emit("model_end", {
                    "model_seq": seq, "status": "unfinished",
                    "at_ms": self._ms(), "duration_ms": self._ms(started),
                })
            for fields, started in self._tool_runs.values():
                unfinished += 1
                self._emit("tool_end", {
                    **fields, "status": "unfinished",
                    "at_ms": self._ms(), "duration_ms": self._ms(started),
                })
            self._model_runs.clear()
            self._tool_runs.clear()
            self._emit("turn_end", {
                "state": state, "duration_ms": self._ms(), "model_calls": self._model_seq,
                "tool_calls": self._tool_count, "unfinished": unfinished,
            })
