"""Tests for JSONStore durability: fingerprint reload, atomic + deferred writes."""

import json

import pytest
from langchain_core.documents import Document

import rag.store.json_store as json_store_module
from rag.store.json_store import JSONStore


def _doc(pid: str, text: str = "text") -> Document:
    return Document(page_content=text, metadata={"pid": pid})


def _read_raw(path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_deferred_save_writes_once(tmp_path, monkeypatch):
    path = tmp_path / "raw.json"
    store = JSONStore(str(path))

    writes = {"count": 0}
    real_write_out = store._write_out

    def counting_write_out():
        writes["count"] += 1
        real_write_out()

    monkeypatch.setattr(store, "_write_out", counting_write_out)

    with store.deferred_save():
        for i in range(10):
            store.delete(f"pid-{i}")
            store.add([_doc(f"pid-{i}")])

    assert writes["count"] == 1
    assert len(_read_raw(path)) == 10


def test_fingerprint_reload_sees_external_rewrite(tmp_path):
    path = tmp_path / "raw.json"
    store_a = JSONStore(str(path))
    store_a.add([_doc("a")])

    store_b = JSONStore(str(path))
    assert [d.metadata["pid"] for d in store_b.get()] == ["a"]

    # store_a rewrites the file behind store_b's back; store_b must notice.
    store_a.add([_doc("b")])
    assert [d.metadata["pid"] for d in store_b.get()] == ["a", "b"]

    # and writes on the stale instance must not resurrect old state
    store_b.add([_doc("c")])
    assert [d.metadata["pid"] for d in store_a.get()] == ["a", "b", "c"]


def test_deferred_save_fails_loudly_on_external_rewrite(tmp_path):
    path = tmp_path / "raw.json"
    store = JSONStore(str(path))
    store.add([_doc("keep")])

    with pytest.raises(RuntimeError, match="Re-run the ingest"):
        with store.deferred_save():
            store.add([_doc("batched")])
            # another process rewrites raw.json mid-batch
            path.write_text(
                json.dumps([{"page_content": "x", "metadata": {"pid": "external"}}]),
                encoding="utf-8",
            )

    # the batch was discarded: the external content survives untouched
    assert [d["metadata"]["pid"] for d in _read_raw(path)] == ["external"]
    assert [d.metadata["pid"] for d in store.get()] == ["external"]


def test_exception_inside_deferred_batch_writes_nothing(tmp_path):
    path = tmp_path / "raw.json"
    store = JSONStore(str(path))
    store.add([_doc("committed")])

    with pytest.raises(ValueError, match="boom"):
        with store.deferred_save():
            store.add([_doc("uncommitted")])
            raise ValueError("boom")

    assert [d["metadata"]["pid"] for d in _read_raw(path)] == ["committed"]
    assert [d.metadata["pid"] for d in store.get()] == ["committed"]

    store.add([_doc("later")])
    assert [d["metadata"]["pid"] for d in _read_raw(path)] == [
        "committed",
        "later",
    ]


def test_failed_write_restores_memory_to_previous_file(tmp_path, monkeypatch):
    path = tmp_path / "raw.json"
    store = JSONStore(str(path))
    store.add([_doc("stable")])

    real_replace = json_store_module.os.replace

    def fail_replace(_source, _destination):
        raise OSError("replace failed")

    monkeypatch.setattr(json_store_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        store.add([_doc("failed")])

    # The atomic replace never happened, and the live instance rolls back too.
    assert [d["metadata"]["pid"] for d in _read_raw(path)] == ["stable"]
    assert [d.metadata["pid"] for d in store.get()] == ["stable"]
    assert list(tmp_path.glob("*.tmp")) == []

    monkeypatch.setattr(json_store_module.os, "replace", real_replace)
    store.add([_doc("later")])
    assert [d["metadata"]["pid"] for d in _read_raw(path)] == [
        "stable",
        "later",
    ]
