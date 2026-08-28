"""Tests for agent.history_rag.store.

Mocks rag.ChromaStore + VectorRetriever so we never hit Ollama or
ChromaDB. The point is to verify the wiring (metadata schema, role
filter, cache behavior), not the underlying vector store.
"""

import pytest
from langchain_core.documents import Document


@pytest.fixture
def fake_chroma(monkeypatch):
    """Replace ChromaStore inside the shared rag cache + VectorRetriever."""
    captured: dict = {
        "add_calls": [],
        "retrieve_calls": [],
        "get_calls": [],
        "get_documents": [],
    }

    class FakeChromaStore:
        def __init__(self, collection_name, config):
            captured["collection_name"] = collection_name
            captured["persist_dir"] = config.persist_dir

        def add(self, documents):
            captured["add_calls"].append(documents)

        def get_where(self, where, *, limit=None):
            captured["get_calls"].append({"where": where, "limit": limit})
            return list(captured["get_documents"])

    class FakeVectorRetriever:
        def __init__(self, store):
            self._store = store

        def retrieve(self, query, k, where=None):
            captured["retrieve_calls"].append({"query": query, "k": k, "where": where})
            return []

    from rag.store import cache as cache_mod
    monkeypatch.setattr(cache_mod, "ChromaStore", FakeChromaStore)
    monkeypatch.setattr(cache_mod, "_store_cache", {})
    monkeypatch.setattr("agent.history_rag.store.VectorRetriever", FakeVectorRetriever)

    return captured


def test_add_turn_emits_two_documents_with_role_metadata(tmp_path, fake_chroma):
    from agent.config import AgentConfig
    from agent.turns.memory import TurnRecord
    from agent.history_rag.store import ChatHistoryStore

    store = ChatHistoryStore(AgentConfig(persist_dir=str(tmp_path)))
    store.add_turn(
        TurnRecord(user_input="hi", assistant_output="hello"),
        session_id="sess-1",
        turn_id=3,
        timestamp="2026-04-25T12:00:00",
    )

    docs = fake_chroma["add_calls"][0]
    assert len(docs) == 2

    by_role = {d.metadata["role"]: d for d in docs}
    assert set(by_role) == {"user", "assistant"}
    assert by_role["user"].page_content == "hi"
    assert by_role["assistant"].page_content == "hello"

    expected_meta = {
        "role": "user",
        "turn_id": 3,
        "session_id": "sess-1",
        "timestamp": "2026-04-25T12:00:00",
    }
    assert by_role["user"].metadata == expected_meta
    assert by_role["assistant"].metadata == {**expected_meta, "role": "assistant"}


def test_add_turn_skips_empty_strings(tmp_path, fake_chroma):
    from agent.config import AgentConfig
    from agent.turns.memory import TurnRecord
    from agent.history_rag.store import ChatHistoryStore

    store = ChatHistoryStore(AgentConfig(persist_dir=str(tmp_path)))
    store.add_turn(
        TurnRecord(user_input="hi", assistant_output=""),
        session_id="s",
        turn_id=1,
        timestamp="t",
    )

    docs = fake_chroma["add_calls"][0]
    assert len(docs) == 1
    assert docs[0].metadata["role"] == "user"


def test_add_turn_with_both_empty_does_not_call_store(tmp_path, fake_chroma):
    from agent.config import AgentConfig
    from agent.turns.memory import TurnRecord
    from agent.history_rag.store import ChatHistoryStore

    store = ChatHistoryStore(AgentConfig(persist_dir=str(tmp_path)))
    store.add_turn(
        TurnRecord(user_input="", assistant_output=""),
        session_id="s",
        turn_id=1,
        timestamp="t",
    )
    assert fake_chroma["add_calls"] == []


def test_search_passes_role_where_clause(tmp_path, fake_chroma):
    from agent.config import AgentConfig
    from agent.history_rag.store import ChatHistoryStore

    store = ChatHistoryStore(AgentConfig(persist_dir=str(tmp_path)))
    store.search("what did I ask?", k=4, role="user")

    call = fake_chroma["retrieve_calls"][0]
    assert call == {"query": "what did I ask?", "k": 4, "where": {"role": {"$eq": "user"}}}


def test_search_without_role_passes_no_where(tmp_path, fake_chroma):
    from agent.config import AgentConfig
    from agent.history_rag.store import ChatHistoryStore

    store = ChatHistoryStore(AgentConfig(persist_dir=str(tmp_path)))
    store.search("anything", k=5)

    call = fake_chroma["retrieve_calls"][0]
    assert call == {"query": "anything", "k": 5, "where": None}


def test_collection_name_and_persist_dir(tmp_path, fake_chroma):
    from agent.config import AgentConfig
    from agent.history_rag.store import CHAT_HISTORY_COLLECTION, ChatHistoryStore

    ChatHistoryStore(AgentConfig(persist_dir=str(tmp_path)))

    assert fake_chroma["collection_name"] == CHAT_HISTORY_COLLECTION
    assert fake_chroma["persist_dir"].endswith("/chat_history")
    assert fake_chroma["persist_dir"].startswith(str(tmp_path))


def test_chat_history_stores_share_one_chroma_client_per_dir(tmp_path, fake_chroma):
    from agent.config import AgentConfig
    from agent.history_rag.store import get_chat_history_store

    cfg_a = AgentConfig(persist_dir=str(tmp_path / "a"))
    cfg_b = AgentConfig(persist_dir=str(tmp_path / "b"))

    a1 = get_chat_history_store(cfg_a)
    a2 = get_chat_history_store(cfg_a)
    b1 = get_chat_history_store(cfg_b)

    # The underlying Chroma client is deduped process-wide by rag's shared
    # cache (SharedSystemClient race guard); the wrapper itself is cheap.
    assert a1._store is a2._store
    assert a1._store is not b1._store


def test_search_returns_documents_from_retriever(tmp_path, monkeypatch):
    """Sanity: results from the retriever are returned verbatim."""
    sentinel = [Document(page_content="x", metadata={"role": "user"})]

    class FakeChromaStore:
        def __init__(self, *a, **kw):
            pass

        def add(self, docs):
            pass

    class FakeVectorRetriever:
        def __init__(self, store):
            pass

        def retrieve(self, query, k, where=None):
            return sentinel

    from rag.store import cache as cache_mod
    monkeypatch.setattr(cache_mod, "ChromaStore", FakeChromaStore)
    monkeypatch.setattr(cache_mod, "_store_cache", {})
    monkeypatch.setattr("agent.history_rag.store.VectorRetriever", FakeVectorRetriever)

    from agent.config import AgentConfig
    from agent.history_rag.store import ChatHistoryStore

    store = ChatHistoryStore(AgentConfig(persist_dir=str(tmp_path)))
    assert store.search("q") is sentinel


def test_read_session_turns_pairs_roles_without_semantic_search(tmp_path, fake_chroma):
    from agent.config import AgentConfig
    from agent.history_rag.store import ChatHistoryStore

    session_id = "28b222e0cc6543aa8d7bbdc423de99a7"
    fake_chroma["get_documents"] = [
        Document(
            page_content="answer",
            metadata={
                "role": "assistant",
                "turn_id": 2,
                "session_id": session_id,
                "timestamp": "2026-08-28T01:00:00+00:00",
            },
        ),
        Document(
            page_content="question",
            metadata={
                "role": "user",
                "turn_id": 2,
                "session_id": session_id,
                "timestamp": "2026-08-28T01:00:00+00:00",
            },
        ),
    ]
    store = ChatHistoryStore(AgentConfig(persist_dir=str(tmp_path)))

    turns = store.read_session_turns(session_id)

    assert fake_chroma["retrieve_calls"] == []
    assert fake_chroma["get_calls"] == [{
        "where": {"session_id": {"$eq": session_id}},
        "limit": 8193,
    }]
    assert len(turns) == 1
    assert turns[0].user_input == "question"
    assert turns[0].assistant_output == "answer"
    assert turns[0].turn_id == 2
    assert turns[0].persist_target == "none"


def test_read_session_turns_rejects_non_iso_or_naive_timestamps(
    tmp_path,
    fake_chroma,
):
    from agent.config import AgentConfig
    from agent.history_rag.store import ChatHistoryStore, HistoryRestoreError

    session_id = "28b222e0cc6543aa8d7bbdc423de99a7"
    store = ChatHistoryStore(AgentConfig(persist_dir=str(tmp_path)))
    for timestamp in ("not-a-timestamp", "2026-08-28T01:00:00"):
        fake_chroma["get_documents"] = [
            Document(
                page_content=text,
                metadata={
                    "role": role,
                    "turn_id": 1,
                    "session_id": session_id,
                    "timestamp": timestamp,
                },
            )
            for role, text in (("user", "question"), ("assistant", "answer"))
        ]

        with pytest.raises(HistoryRestoreError, match="timestamp"):
            store.read_session_turns(session_id)


@pytest.mark.parametrize(
    "documents",
    [
        [Document(
            page_content="question",
            metadata={
                "role": "user",
                "turn_id": 1,
                "session_id": "28b222e0cc6543aa8d7bbdc423de99a7",
                "timestamp": "t",
            },
        )],
        [
            Document(
                page_content="q1",
                metadata={
                    "role": "user",
                    "turn_id": 1,
                    "session_id": "28b222e0cc6543aa8d7bbdc423de99a7",
                    "timestamp": "t",
                },
            ),
            Document(
                page_content="q2",
                metadata={
                    "role": "user",
                    "turn_id": 1,
                    "session_id": "28b222e0cc6543aa8d7bbdc423de99a7",
                    "timestamp": "t",
                },
            ),
        ],
    ],
)
def test_read_session_turns_fails_closed_on_incomplete_or_duplicate_roles(
    tmp_path,
    fake_chroma,
    documents,
):
    from agent.config import AgentConfig
    from agent.history_rag.store import ChatHistoryStore, HistoryRestoreError

    fake_chroma["get_documents"] = documents
    store = ChatHistoryStore(AgentConfig(persist_dir=str(tmp_path)))

    with pytest.raises(HistoryRestoreError):
        store.read_session_turns("28b222e0cc6543aa8d7bbdc423de99a7")


def test_chroma_get_where_is_a_bounded_raw_metadata_read():
    from rag.store.chroma_store import ChromaStore

    captured = {}

    class RawStore:
        def get(self, **kwargs):
            captured.update(kwargs)
            return {
                "documents": ["raw text"],
                "metadatas": [{"session_id": "s"}],
            }

    store = ChromaStore.__new__(ChromaStore)
    store._store = RawStore()

    documents = store.get_where(
        {"session_id": {"$eq": "s"}},
        limit=3,
    )

    assert captured == {
        "where": {"session_id": {"$eq": "s"}},
        "limit": 3,
    }
    assert documents == [Document(
        page_content="raw text",
        metadata={"session_id": "s"},
    )]
