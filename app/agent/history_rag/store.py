"""Vector store for evicted chat turns.

Each user prompt and assistant response that ages out of the in-prompt
recent_turns window is stored as its own chunk in a single ChromaDB
collection. Metadata distinguishes role and links the prompt/response
pair through turn_id.
"""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path

from langchain_core.documents import Document

from rag import VectorRetriever, get_chroma_store

from agent.config import AgentConfig
from agent.memory import TurnRecord

CHAT_HISTORY_COLLECTION = "chat_history"
CHAT_HISTORY_SUBDIR = "chat_history"


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


def get_chat_history_store(config: AgentConfig) -> ChatHistoryStore:
    """Return a ChatHistoryStore for the config's chat-history dir.

    The SharedSystemClient race that the old module-local mirror cache
    guarded against is now handled centrally: rag.get_chroma_store dedupes the
    underlying Chroma client per (persist_dir, collection), so the wrapper
    itself can be constructed freely.
    """
    return ChatHistoryStore(config)
