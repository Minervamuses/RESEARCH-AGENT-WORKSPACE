"""Tests for batched deletes on ChromaStore and DocumentStore."""

from langchain_core.documents import Document

from rag.store.chroma_store import ChromaStore
from rag.store.document_store import DocumentStore
from rag.store.json_store import JSONStore


class _FakeChromaBackend:
    """Stub for the underlying langchain Chroma client."""

    def __init__(self):
        self.get_calls: list[dict] = []
        self.delete_calls: list[list[str]] = []
        self.ids_by_where: dict[str, list[str]] = {}

    def get(self, where=None):
        self.get_calls.append(where)
        pid_filter = where.get("pid") if where else None
        if isinstance(pid_filter, dict) and "$in" in pid_filter:
            ids = [i for pid in pid_filter["$in"] for i in self.ids_by_where.get(pid, [])]
        elif pid_filter:
            ids = list(self.ids_by_where.get(pid_filter, []))
        else:
            ids = [i for ids in self.ids_by_where.values() for i in ids]
        return {"ids": ids, "documents": [], "metadatas": []}

    def delete(self, ids):
        self.delete_calls.append(list(ids))


def _chroma_with_backend(backend) -> ChromaStore:
    store = ChromaStore.__new__(ChromaStore)
    store._store = backend
    return store


def test_delete_many_uses_one_in_query():
    backend = _FakeChromaBackend()
    backend.ids_by_where = {"a": ["a-0", "a-1"], "b": ["b-0"]}
    store = _chroma_with_backend(backend)

    store.delete_many(["a", "b", "missing"])

    assert backend.get_calls == [{"pid": {"$in": ["a", "b", "missing"]}}]
    assert backend.delete_calls == [["a-0", "a-1", "b-0"]]


def test_delete_many_with_no_pids_is_a_noop():
    backend = _FakeChromaBackend()
    store = _chroma_with_backend(backend)

    store.delete_many([])

    assert backend.get_calls == []
    assert backend.delete_calls == []


def test_delete_many_without_matches_skips_delete():
    backend = _FakeChromaBackend()
    store = _chroma_with_backend(backend)

    store.delete_many(["ghost"])

    assert backend.delete_calls == []


def test_document_store_delete_many_hits_both_stores(tmp_path):
    backend = _FakeChromaBackend()
    backend.ids_by_where = {"a": ["a-0"]}
    chroma = _chroma_with_backend(backend)
    json_store = JSONStore(str(tmp_path / "raw.json"))
    json_store.add([
        Document(page_content="x", metadata={"pid": "a"}),
        Document(page_content="y", metadata={"pid": "keep"}),
    ])
    store = DocumentStore(chroma, json_store)

    store.delete_many(["a"])

    assert [d.metadata["pid"] for d in json_store.get()] == ["keep"]
    assert backend.delete_calls == [["a-0"]]
