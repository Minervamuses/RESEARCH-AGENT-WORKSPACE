"""Desktop service errors: the wire-safe error type and the exception-to-error mapping."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import Any
from langgraph.errors import GraphRecursionError
from agent.conversations import ConversationError, ConversationSnapshot
from agent.desktop.protocol import ProtocolError
from agent.extensions.manager import ManagementError


# Records keep the service logger name used by diagnostics and tests.
logger = logging.getLogger("agent.desktop.service")


# Mapped failures whose message already names the cause and its fix; every
# other exception-derived failure carries an incident reference to the log.
_SELF_EXPLANATORY_FAILURE_CODES = frozenset({
    "BUSY_EXTENSION_OPERATION",
    "GRAPH_LIMIT_REACHED",
    "INVALID_PATH",
    "OPENROUTER_NOT_CONFIGURED",
})


EventSink = Callable[[str, dict[str, Any]], None]


_KNOWLEDGE_MUTATIONS = {
    "knowledge.init_workspace",
    "knowledge.ingest_file",
    "knowledge.ingest_folder",
    "knowledge.prune_apply",
}


class DesktopServiceError(ProtocolError):
    """A domain or lifecycle failure safe to return over the desktop wire."""


class _ErrorMapping:
    """DesktopService methods moved here unchanged; `self` is the DesktopService."""

    def _with_turn_lifecycle(
        self,
        error: DesktopServiceError,
        method: str,
        params: Mapping[str, Any],
    ) -> DesktopServiceError:
        turn_id = params.get("turnId")
        display_input: object = params.get("text")
        if method == "extensions.apply":
            try:
                display_input = self._extension_apply_display_input(params)
            except DesktopServiceError:
                display_input = None
        state: str | None = None
        accepted = False
        persisted = False
        snapshot: ConversationSnapshot | None = None
        session = self.session
        if isinstance(turn_id, str) and session is not None:
            try:
                snapshot = self._conversation_repository.load_optional(
                    session.session_id
                )
            except ConversationError:
                snapshot = session.conversation_snapshot
            if snapshot is not None:
                turn = next(
                    (
                        item
                        for item in snapshot.document.turns
                        if item.turn_id == turn_id
                        and item.display_input == display_input
                    ),
                    None,
                )
                if turn is not None:
                    state = turn.state
                    accepted = True
                    persisted = True
        return DesktopServiceError(
            error.code,
            str(error),
            retryable=error.retryable,
            details={
                "turnId": turn_id,
                "state": state,
                "accepted": accepted,
                "persisted": persisted,
            },
        )

    def _map_exception(self, method: str, exc: Exception) -> DesktopServiceError:
        if isinstance(exc, GraphRecursionError):
            return DesktopServiceError(
                "GRAPH_LIMIT_REACHED",
                "The agent reached its graph recursion safety limit.",
                retryable=True,
            )
        if self._exception_chain_contains(exc, "OPENROUTER_API_KEY is not set"):
            return DesktopServiceError(
                "OPENROUTER_NOT_CONFIGURED",
                "OpenRouter is not configured.",
            )
        if method == "session.turn":
            status_code = self._exception_http_status(exc)
            if status_code == 429:
                return DesktopServiceError(
                    "PROVIDER_RATE_LIMITED",
                    "The model provider is rate limited. Your draft was preserved.",
                    retryable=True,
                )
            if status_code is not None or self._exception_chain_looks_provider_owned(exc):
                retryable = status_code is None or status_code >= 500 or status_code in {
                    408,
                    409,
                }
                return DesktopServiceError(
                    "PROVIDER_REQUEST_FAILED",
                    "The model provider could not complete the turn.",
                    retryable=retryable,
                )
        if isinstance(exc, ManagementError):
            code = (
                "EXTENSION_APPLY_FAILED"
                if method == "extensions.apply"
                else "EXTENSION_PREVIEW_FAILED"
            )
            if "another extension apply is already running" in str(exc):
                code = "BUSY_EXTENSION_OPERATION"
            return DesktopServiceError(
                code,
                "The extension operation could not be completed.",
                retryable=code == "BUSY_EXTENSION_OPERATION",
            )
        if method == "extensions.apply" and isinstance(exc, ConversationError):
            return DesktopServiceError(
                "EXTENSION_APPLY_FAILED",
                "The durable extension operation could not be completed.",
            )
        if method.startswith("knowledge."):
            if isinstance(exc, (FileNotFoundError, IsADirectoryError, NotADirectoryError)):
                return DesktopServiceError("INVALID_PATH", "The selected path is invalid.")
            lowered = self._exception_chain_text(exc).lower()
            partial_write = method in _KNOWLEDGE_MUTATIONS
            if "model" in lowered and (
                "not found" in lowered or "pull" in lowered
            ):
                return DesktopServiceError(
                    "OLLAMA_MODEL_MISSING",
                    f"The configured Ollama model {self.config.embed_model} is unavailable.",
                    retryable=True,
                    details={"partialWritePossible": partial_write},
                )
            if any(
                marker in lowered
                for marker in (
                    "connection refused",
                    "connection error",
                    "connect error",
                    "failed to connect",
                    "timed out",
                    "timeout",
                )
            ):
                return DesktopServiceError(
                    "OLLAMA_UNREACHABLE",
                    "Ollama is unreachable.",
                    retryable=True,
                    details={"partialWritePossible": partial_write},
                )
            if "modified by another process" in lowered:
                return DesktopServiceError(
                    "RAG_PARTIAL_WRITE_POSSIBLE",
                    "The knowledge store changed during the operation; refresh and retry.",
                    retryable=True,
                )
            code = (
                "RAG_WRITE_FAILED"
                if method
                in {
                    "knowledge.init_workspace",
                    "knowledge.ingest_file",
                    "knowledge.ingest_folder",
                    "knowledge.prune_apply",
                }
                else "RAG_READ_FAILED"
            )
            return DesktopServiceError(
                code,
                "The knowledge operation could not be completed.",
                retryable=True,
                details=(
                    {"partialWritePossible": True}
                    if code == "RAG_WRITE_FAILED"
                    else None
                ),
            )
        if isinstance(exc, (ValueError, KeyError)) and method.startswith("session."):
            return DesktopServiceError(
                "PROTOCOL_INVALID",
                "The requested session mode or skill is invalid.",
            )
        return DesktopServiceError(
            "INTERNAL_ERROR",
            "The desktop backend encountered an internal error.",
        )

    @staticmethod
    def _exception_chain_contains(exc: BaseException, text: str) -> bool:
        current: BaseException | None = exc
        seen: set[int] = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            if text in str(current):
                return True
            current = current.__cause__ or current.__context__
        return False

    @staticmethod
    def _exception_chain_text(exc: BaseException) -> str:
        parts: list[str] = []
        current: BaseException | None = exc
        seen: set[int] = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            parts.append(f"{type(current).__module__}.{type(current).__name__}: {current}")
            current = current.__cause__ or current.__context__
        return " | ".join(parts)

    @staticmethod
    def _exception_http_status(exc: BaseException) -> int | None:
        current: BaseException | None = exc
        seen: set[int] = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            for source in (current, getattr(current, "response", None)):
                status = getattr(source, "status_code", None)
                if type(status) is int and 400 <= status <= 599:
                    return status
            current = current.__cause__ or current.__context__
        return None

    @staticmethod
    def _exception_chain_looks_provider_owned(exc: BaseException) -> bool:
        current: BaseException | None = exc
        seen: set[int] = set()
        prefixes = ("httpx", "openai", "langchain_openrouter")
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            if type(current).__module__.startswith(prefixes):
                return True
            current = current.__cause__ or current.__context__
        return False
