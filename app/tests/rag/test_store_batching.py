"""Real local-store coverage for batched document deletion."""

from langchain_core.documents import Document

from rag.config import KNOWLEDGE_COLLECTION
from rag.store.cache import get_chroma_store, get_json_store
from rag.store.document_store import DocumentStore


def test_document_store_delete_many_round_trips_through_chroma(
    offline_rag_config,
    tmp_path,
):
    config = offline_rag_config(tmp_path / "store")
    chroma_store = get_chroma_store(KNOWLEDGE_COLLECTION, config)
    json_store = get_json_store(config)
    store = DocumentStore(chroma_store, json_store)
    store.add([
        Document(page_content="alpha zero", metadata={"pid": "a", "chunk_id": 0}),
        Document(page_content="alpha one", metadata={"pid": "a", "chunk_id": 1}),
        Document(page_content="beta", metadata={"pid": "b", "chunk_id": 0}),
        Document(page_content="keep", metadata={"pid": "keep", "chunk_id": 0}),
    ])

    assert sorted(doc.metadata["pid"] for doc in chroma_store.get()) == [
        "a",
        "a",
        "b",
        "keep",
    ]

    # This executes Chroma's real metadata `$in` query before deleting ids.
    store.delete_many(["a", "b", "missing"])

    assert [doc.metadata["pid"] for doc in json_store.get()] == ["keep"]
    assert [doc.metadata["pid"] for doc in chroma_store.get()] == ["keep"]

    store.delete_many([])
    store.delete_many(["ghost"])
    assert [doc.metadata["pid"] for doc in json_store.get()] == ["keep"]
    assert [doc.metadata["pid"] for doc in chroma_store.get()] == ["keep"]
