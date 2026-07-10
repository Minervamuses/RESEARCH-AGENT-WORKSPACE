"""History integration: versioned source mapping and recall rehydration."""

import json

from langchain_core.documents import Document

from agent.config import AgentConfig
from agent.history_rag.store import (
    SOURCES_METADATA_KEY,
    render_sources_metadata,
    sources_from_metadata,
)
from agent.history_rag.tool import create_history_tool
from agent.memory import TurnRecord
from skills.citation.coordinator import SourceRegistry
from skills.citation.types import SourceRef


def _ref(source_id="src-x"):
    return SourceRef(
        source_id=source_id,
        doi="10.1234/x",
        title="Recalled Paper",
        authors=["Ada Lovelace"],
        year=2021,
        verification_level="identity_verified",
    )


def test_sources_metadata_round_trip_is_versioned():
    raw = render_sources_metadata([_ref()])
    payload = json.loads(raw)
    assert payload["schema_version"] == 1
    restored = sources_from_metadata({SOURCES_METADATA_KEY: raw})
    assert len(restored) == 1
    assert restored[0].source_id == "src-x"
    assert restored[0].verification_level == "identity_verified"


def test_old_records_without_mapping_are_empty_never_upgraded():
    assert sources_from_metadata(None) == []
    assert sources_from_metadata({}) == []
    assert sources_from_metadata({SOURCES_METADATA_KEY: "not json"}) == []
    assert sources_from_metadata({SOURCES_METADATA_KEY: '{"sources": "bad"}'}) == []


class _StoreWithDocs:
    """ChatHistoryStore stand-in returning canned documents."""

    def __init__(self, documents):
        self.documents = documents
        self.searches = []

    def search(self, query, k=5, role=None):
        self.searches.append((query, k, role))
        return self.documents


def _assistant_doc(sources=None, text="old answer"):
    metadata = {"role": "assistant", "turn_id": 7, "timestamp": "t"}
    if sources:
        metadata[SOURCES_METADATA_KEY] = render_sources_metadata(sources)
    return Document(page_content=text, metadata=metadata)


def test_recall_returns_sources_and_rehydrates_registry():
    registry = SourceRegistry()
    store = _StoreWithDocs([_assistant_doc(sources=[_ref()])])
    tool = create_history_tool(
        AgentConfig(), store=store, registry_getter=lambda: registry
    )
    result = json.loads(tool.func(query="old paper"))
    assert result[0]["sources"][0]["source_id"] == "src-x"
    # Rehydrated: citable again through the gate.
    assert registry.get("src-x") is not None
    assert registry.get("src-x").title == "Recalled Paper"


def test_recall_without_sources_does_not_touch_registry():
    calls = []

    def getter():
        calls.append(1)
        raise AssertionError("registry must not be built for sourceless recalls")

    store = _StoreWithDocs([_assistant_doc(sources=None)])
    tool = create_history_tool(AgentConfig(), store=store, registry_getter=getter)
    result = json.loads(tool.func(query="q"))
    assert result[0]["sources"] == []
    assert calls == []


def test_add_turn_attaches_mapping_to_assistant_doc_only():
    added = []

    class _ChromaSpy:
        def add(self, documents):
            added.extend(documents)

    from agent.history_rag import store as store_module

    chat_store = store_module.ChatHistoryStore.__new__(store_module.ChatHistoryStore)
    chat_store._store = _ChromaSpy()

    turn = TurnRecord(
        user_input="asked", assistant_output="answered [1]",
        sources=[_ref()],
    )
    chat_store.add_turn(turn, session_id="s", turn_id=1, timestamp="t")

    by_role = {doc.metadata["role"]: doc for doc in added}
    assert SOURCES_METADATA_KEY in by_role["assistant"].metadata
    assert SOURCES_METADATA_KEY not in by_role["user"].metadata
    payload = json.loads(by_role["assistant"].metadata[SOURCES_METADATA_KEY])
    assert payload["sources"][0]["doi"] == "10.1234/x"


def test_turn_record_sources_survive_eviction(monkeypatch, tmp_path):
    import asyncio

    from conftest import FakeHistoryStore, make_astream_graph
    from agent.session import ChatSession

    monkeypatch.setattr("agent.session.find_app_root", lambda: tmp_path)
    monkeypatch.setattr(
        "agent.session.build_graph",
        lambda _cfg, extra_tools=None, history_store=None, **kwargs: make_astream_graph(),
    )
    cfg = AgentConfig(persist_dir=str(tmp_path / "persist"))
    cfg.agent_recent_turns_window = 1
    store = FakeHistoryStore()
    session = ChatSession(cfg, history_store=store)
    session.recent_turns.append(
        TurnRecord(user_input="q0", assistant_output="a0", turn_id=1,
                   timestamp="t", sources=[_ref()])
    )
    asyncio.run(session.turn("q1"))  # evicts turn 1 into the store
    evicted = store.adds[0]["turn"]
    assert evicted.sources[0].source_id == "src-x"
