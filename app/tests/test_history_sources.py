"""Legacy sources_json metadata: ignored by recall, never written anew."""

import json

from langchain_core.documents import Document

from agent.config import AgentConfig
from agent.history_rag.tool import create_history_tool
from agent.memory import TurnRecord


class _StoreWithDocs:
    """ChatHistoryStore stand-in returning canned documents."""

    def __init__(self, documents):
        self.documents = documents
        self.searches = []

    def search(self, query, k=5, role=None):
        self.searches.append((query, k, role))
        return self.documents


LEGACY_SOURCES_JSON = json.dumps({
    "schema_version": 1,
    "sources": [{
        "source_id": "src-legacy",
        "doi": "10.1234/x",
        "title": "Old Paper",
        "verification_level": "identity_verified",
    }],
})


def test_recall_ignores_legacy_sources_metadata():
    """Docs written by the old bridge still recall fine; the retired
    sources_json payload is neither surfaced nor interpreted."""
    doc = Document(
        page_content="old answer",
        metadata={
            "role": "assistant",
            "turn_id": 7,
            "timestamp": "t",
            "sources_json": LEGACY_SOURCES_JSON,
        },
    )
    tool = create_history_tool(AgentConfig(), store=_StoreWithDocs([doc]))
    result = json.loads(tool.func(query="old paper"))
    assert result == [{
        "role": "assistant",
        "text": "old answer",
        "turn_id": 7,
        "timestamp": "t",
    }]


def test_add_turn_writes_no_sources_metadata():
    added = []

    class _ChromaSpy:
        def add(self, documents):
            added.extend(documents)

    from agent.history_rag import store as store_module

    chat_store = store_module.ChatHistoryStore.__new__(store_module.ChatHistoryStore)
    chat_store._store = _ChromaSpy()

    turn = TurnRecord(user_input="asked", assistant_output="answered")
    chat_store.add_turn(turn, session_id="s", turn_id=1, timestamp="t")

    for doc in added:
        assert set(doc.metadata) == {"role", "turn_id", "session_id", "timestamp"}


def test_turn_record_has_no_sources_field():
    assert not hasattr(TurnRecord(user_input="q", assistant_output="a"), "sources")
