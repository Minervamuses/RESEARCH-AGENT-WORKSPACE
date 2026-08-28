"""Vector store for evicted chat turns.

Each user prompt and assistant response that ages out of the in-prompt
recent_turns window is stored as its own chunk in a single ChromaDB
collection. Metadata distinguishes role and links the prompt/response
pair through turn_id.
"""

from __future__ import annotations

import dataclasses
import os
import uuid
from datetime import datetime
from pathlib import Path

from langchain_core.documents import Document

from rag import VectorRetriever, get_chroma_store

from agent.config import AgentConfig
from agent.turns.memory import TurnRecord

CHAT_HISTORY_COLLECTION = "chat_history"
CHAT_HISTORY_SUBDIR = "chat_history"
MAX_RESTORED_SESSION_TURNS = 4096
MAX_RESTORED_TURN_CHARS = 131_072
MAX_RESTORED_SESSION_CHARS = 8 * 1024 * 1024


class HistoryRestoreError(RuntimeError):
    """Stored session history is incomplete, ambiguous, or outside bounds."""


def _validate_session_id(session_id: str) -> None:
    try:
        parsed = uuid.UUID(hex=session_id)
    except (AttributeError, ValueError) as exc:
        raise HistoryRestoreError("session_id must be canonical UUIDv4 hex") from exc
    if parsed.version != 4 or parsed.hex != session_id:
        raise HistoryRestoreError("session_id must be canonical UUIDv4 hex")


def _resolve_chat_persist_dir(config: AgentConfig) -> str:
    return str(Path(config.persist_dir) / CHAT_HISTORY_SUBDIR)


def _chat_config(config: AgentConfig) -> AgentConfig:
    return dataclasses.replace(
        config,
        persist_dir=_resolve_chat_persist_dir(config),
    )


class ChatHistoryStore:
    """Wraps the shared rag ChromaStore at a chat-history-specific persist dir."""

    def __init__(self, config: AgentConfig):
        chat_config = _chat_config(config)
        os.makedirs(chat_config.persist_dir, exist_ok=True)
        # Keyed on the resolved chat_history subdir, so every ChatHistoryStore
        # for the same dir shares one process-wide Chroma client.
        self._store = get_chroma_store(CHAT_HISTORY_COLLECTION, chat_config)
        self._retriever = VectorRetriever(self._store)

    def add_turn(
        self,
        turn: TurnRecord,
        *,
        session_id: str,
        turn_id: int,
        timestamp: str,
    ) -> None:
        """Embed user_input and assistant_output as two chunks. Empty strings are skipped."""
        documents: list[Document] = []
        for role, text in (("user", turn.user_input), ("assistant", turn.assistant_output)):
            if not text:
                continue
            metadata = {
                "role": role,
                "turn_id": turn_id,
                "session_id": session_id,
                "timestamp": timestamp,
            }
            documents.append(Document(page_content=text, metadata=metadata))
        if documents:
            self._store.add(documents)

    def search(
        self,
        query: str,
        k: int = 5,
        role: str | None = None,
    ) -> list[Document]:
        """Semantic similarity search over stored turns; optional role filter."""
        where = {"role": {"$eq": role}} if role else None
        return self._retriever.retrieve(query, k=k, where=where)

    def read_session_turns(self, session_id: str) -> list[TurnRecord]:
        """Read one session by metadata only and require exact role pairs."""
        _validate_session_id(session_id)
        max_documents = MAX_RESTORED_SESSION_TURNS * 2
        try:
            documents = self._store.get_where(
                {"session_id": {"$eq": session_id}},
                limit=max_documents + 1,
            )
        except Exception as exc:
            raise HistoryRestoreError("stored session history is unavailable") from exc
        if len(documents) > max_documents:
            raise HistoryRestoreError("stored session history exceeds the turn limit")

        by_turn: dict[int, dict[str, tuple[str, str]]] = {}
        total_chars = 0
        for document in documents:
            metadata = document.metadata
            if not isinstance(metadata, dict):
                raise HistoryRestoreError("stored session metadata is malformed")
            if metadata.get("session_id") != session_id:
                raise HistoryRestoreError("stored session contains mismatched metadata")
            role = metadata.get("role")
            if role not in {"user", "assistant"}:
                raise HistoryRestoreError("stored session contains an unknown role")
            turn_id = metadata.get("turn_id")
            if type(turn_id) is not int or turn_id < 1:
                raise HistoryRestoreError("stored session contains an invalid turn_id")
            timestamp = metadata.get("timestamp")
            if not isinstance(timestamp, str) or not timestamp or len(timestamp) > 128:
                raise HistoryRestoreError("stored session contains an invalid timestamp")
            try:
                parsed_timestamp = datetime.fromisoformat(
                    timestamp.removesuffix("Z") + (
                        "+00:00" if timestamp.endswith("Z") else ""
                    )
                )
            except ValueError as exc:
                raise HistoryRestoreError(
                    "stored session contains an invalid timestamp"
                ) from exc
            if parsed_timestamp.tzinfo is None:
                raise HistoryRestoreError(
                    "stored session contains an invalid timestamp"
                )
            text = document.page_content
            if not isinstance(text, str) or not text:
                raise HistoryRestoreError("stored session contains an empty turn side")
            if len(text) > MAX_RESTORED_TURN_CHARS:
                raise HistoryRestoreError("stored session turn exceeds the text limit")
            total_chars += len(text)
            if total_chars > MAX_RESTORED_SESSION_CHARS:
                raise HistoryRestoreError("stored session exceeds the text limit")

            pair = by_turn.setdefault(turn_id, {})
            if role in pair:
                raise HistoryRestoreError("stored session contains a duplicate role")
            pair[role] = (text, timestamp)

        turns: list[TurnRecord] = []
        for turn_id in sorted(by_turn):
            pair = by_turn[turn_id]
            if set(pair) != {"user", "assistant"}:
                raise HistoryRestoreError("stored session contains an incomplete turn")
            user_text, user_timestamp = pair["user"]
            assistant_text, assistant_timestamp = pair["assistant"]
            if user_timestamp != assistant_timestamp:
                raise HistoryRestoreError("stored session turn timestamps do not match")
            turns.append(TurnRecord(
                user_input=user_text,
                assistant_output=assistant_text,
                turn_id=turn_id,
                timestamp=user_timestamp,
                persist_target="none",
            ))
        return turns


def get_chat_history_store(config: AgentConfig) -> ChatHistoryStore:
    """Return a wrapper backed by the shared Chroma client for this config."""
    return ChatHistoryStore(config)
