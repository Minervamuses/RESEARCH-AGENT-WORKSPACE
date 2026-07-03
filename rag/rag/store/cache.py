"""Process-wide ChromaStore cache shared by every Chroma consumer."""

from __future__ import annotations

import threading

from rag.config import RAGConfig
from rag.store.chroma_store import ChromaStore

_store_cache: dict[tuple[str, str], ChromaStore] = {}
_store_cache_lock = threading.Lock()


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
