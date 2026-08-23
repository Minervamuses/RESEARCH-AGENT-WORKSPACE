"""Shared fakes for app tests.

One canonical copy of the stubs that used to be duplicated per test file:
history store, queued chat model, scripted astream graphs, and the CLI-level
ChatSession stand-in. Divergent behavior between the old copies is kept as
explicit parameters (raise_on_add, record_repr, ...), never silently dropped.
"""

import hashlib
import math
import re

import pytest
from langchain_core.messages import AIMessage, ToolMessage

import rag.cli.ingest as rag_ingest_module
import rag.store.cache as rag_cache_module
import rag.store.chroma_store as rag_chroma_store_module
from agent.turns.memory import TurnRecord
from rag.config import RAGConfig
from rag.tagger.llm_tagger import FolderMeta


class FakeHistoryStore:
    """In-memory ChatHistoryStore stand-in recording every add_turn call.

    Each entry keeps the full call payload (record plus keyword metadata) so a
    test can assert on any subset; raise_on_add simulates a store outage.
    """

    def __init__(self, raise_on_add: bool = False):
        self.adds: list[dict] = []
        self.raise_on_add = raise_on_add

    def add_turn(self, turn: TurnRecord, *, session_id: str, turn_id: int, timestamp: str) -> None:
        if self.raise_on_add:
            raise RuntimeError("ollama unavailable")
        self.adds.append(
            {
                "turn": turn,
                "user_input": turn.user_input,
                "assistant_output": turn.assistant_output,
                "session_id": session_id,
                "turn_id": turn_id,
                "timestamp": timestamp,
            }
        )


class QueuedModel:
    """Chat-model stub whose invoke pops the next scripted text response."""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls: list[list] = []

    def invoke(self, messages):
        self.calls.append(messages)
        return AIMessage(content=self.outputs.pop(0))


def answer_updates(text):
    """One agent update carrying a plain assistant answer."""
    return [{"agent": {"messages": [AIMessage(content=text)]}}]


def tool_then_answer_updates(name, args, call_id, result, text):
    """Agent tool call -> tool result -> final answer, as three updates."""
    return [
        {"agent": {"messages": [AIMessage(
            content="",
            tool_calls=[{"name": name, "args": args, "id": call_id}],
        )]}},
        {"tools": {"messages": [ToolMessage(
            content=result, name=name, tool_call_id=call_id,
        )]}},
        {"agent": {"messages": [AIMessage(content=text)]}},
    ]


class AstreamGraph:
    """Compiled-LangGraph stand-in: astream records state and replays updates."""

    def __init__(self, updates, *, on_state=None):
        self.updates = list(updates)
        self.on_state = on_state
        self.states: list[dict] = []

    async def astream(self, state, config=None, stream_mode="updates"):
        self.states.append(state)
        if self.on_state is not None:
            self.on_state(state)
        for update in self.updates:
            yield update


def make_astream_graph(updates=None, *, answer="ok", on_state=None) -> AstreamGraph:
    """Graph stub yielding the given updates (default: one plain answer)."""
    if updates is None:
        updates = answer_updates(answer)
    return AstreamGraph(updates, on_state=on_state)


class FakeChatSession:
    """ChatSession stand-in for CLI-level tests: records turns and flushes."""

    def __init__(self, *, turn_result="ok", turn_error=None, record_repr=False,
                 status=None, config=None):
        self.calls: list[str] = []
        self.config = config
        self._turn_result = turn_result
        self._turn_error = turn_error
        self._record_repr = record_repr
        self._status = status

    async def turn(self, user_input: str) -> str:
        self.calls.append(
            f"turn:{user_input!r}" if self._record_repr else f"turn:{user_input}"
        )
        if self._turn_error is not None:
            raise self._turn_error
        return self._turn_result

    def status_snapshot(self) -> dict:
        return dict(self._status or {})

    async def flush_recent_turns(self) -> None:
        self.calls.append("flush")


_RAG_TOKEN_PATTERN = re.compile(r"[\w-]+", re.UNICODE)
_RAG_VECTOR_SIZE = 128


class _DeterministicEmbeddings:
    """Stable token-feature embeddings for offline Chroma queries."""

    @staticmethod
    def _embed(text: str) -> list[float]:
        vector = [0.0] * _RAG_VECTOR_SIZE
        for token in _RAG_TOKEN_PATTERN.findall(text.casefold()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % _RAG_VECTOR_SIZE
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if not norm:
            vector[0] = 1.0
            return vector
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class _DeterministicFolderTagger:
    """Replace only the external LLM call while preserving tagging flow."""

    def __init__(self, _config: RAGConfig):
        pass

    def tag(
        self,
        folder_path: str,
        file_names: list[str],
        _file_previews: dict[str, str],
    ) -> FolderMeta:
        return FolderMeta(
            tags=["documentation", "offline-fixture"],
            summary=f"{folder_path}: {', '.join(sorted(file_names))}",
        )


@pytest.fixture
def offline_rag_config(monkeypatch):
    """Patch external model boundaries and return temp-store configs."""
    rag_cache_module._retriever_cache.clear()
    rag_cache_module._store_cache.clear()
    rag_cache_module._json_store_cache.clear()
    monkeypatch.setenv("ANONYMIZED_TELEMETRY", "FALSE")
    monkeypatch.setattr(
        rag_chroma_store_module,
        "OllamaEmbedder",
        lambda _config: _DeterministicEmbeddings(),
    )
    monkeypatch.setattr(
        rag_ingest_module,
        "LLMTagger",
        _DeterministicFolderTagger,
    )

    def make_config(persist_dir, **overrides) -> RAGConfig:
        return RAGConfig(persist_dir=str(persist_dir), **overrides)

    yield make_config

    rag_cache_module._retriever_cache.clear()
    rag_cache_module._store_cache.clear()
    rag_cache_module._json_store_cache.clear()
