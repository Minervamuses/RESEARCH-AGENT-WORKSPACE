"""Process-wide store caches shared by every rag consumer."""

from __future__ import annotations

import threading

from rag.config import RAGConfig
from rag.store.chroma_store import ChromaStore
from rag.store.json_store import JSONStore

_store_cache: dict[tuple[str, str], ChromaStore] = {}
_store_cache_lock = threading.Lock()

_json_store_cache: dict[str, JSONStore] = {}
_json_store_cache_lock = threading.Lock()


def get_chroma_store(collection: str, cfg: RAGConfig) -> ChromaStore:
    """Return a process-wide ChromaStore, one per (persist_dir, collection).

    Why: chromadb's SharedSystemClient caches a System per persist_dir and
    pops it on client release. Instantiating a new Chroma client per search
    race-conditions against that cache under LangGraph's ToolNode
    ThreadPoolExecutor (KeyError on `_identifier_to_system[identifier]`).
    """
    key = (cfg.persist_dir, collection)
    with _store_cache_lock:
        store = _store_cache.get(key)
        if store is None:
            store = ChromaStore(collection, cfg)
            _store_cache[key] = store
        return store


def get_json_store(cfg: RAGConfig) -> JSONStore:
    """Return a process-wide JSONStore, one per raw_json_path.

    The store itself revalidates against the file fingerprint on every
    entry point, so sharing one instance avoids re-parsing raw.json per
    call while staying correct under external rewrites.
    """
    key = cfg.raw_json_path()
    with _json_store_cache_lock:
        store = _json_store_cache.get(key)
        if store is None:
            store = JSONStore(key)
            _json_store_cache[key] = store
        return store
