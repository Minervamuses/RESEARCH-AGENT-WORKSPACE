"""Public Python API for the KMS."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from rag.config import RAGConfig, KNOWLEDGE_COLLECTION
from rag.filters import build_where, date_to_int
from rag.retriever.vector import VectorRetriever
from rag.store.chroma_store import ChromaStore
from rag.store.json_store import JSONStore
from rag.types import ContextChunk, ContextWindow, FolderSummary, Hit, Inventory
from rag.utils.paths import extract_date

if TYPE_CHECKING:
    from langchain_core.documents import Document


_store_cache: dict[tuple[str, str], ChromaStore] = {}
_store_cache_lock = threading.Lock()


def _get_store(cfg: RAGConfig) -> ChromaStore:
    """Return a process-wide ChromaStore, one per (persist_dir, collection).

    Why: chromadb's SharedSystemClient caches a System per persist_dir and
    pops it on client release. Instantiating a new Chroma client per search
    race-conditions against that cache under LangGraph's ToolNode
    ThreadPoolExecutor (KeyError on `_identifier_to_system[identifier]`).
    """
    key = (cfg.persist_dir, KNOWLEDGE_COLLECTION)
    with _store_cache_lock:
        store = _store_cache.get(key)
        if store is None:
            store = ChromaStore(KNOWLEDGE_COLLECTION, cfg)
            _store_cache[key] = store
        return store


def _doc_to_hit(doc: "Document") -> Hit:
    """Convert a LangChain document into a framework-neutral Hit."""
    metadata = dict(doc.metadata or {})
    raw_tags = metadata.get("tags")
    if isinstance(raw_tags, str):
        try:
            tags = json.loads(raw_tags)
        except json.JSONDecodeError:
            tags = []
    elif isinstance(raw_tags, list):
        tags = raw_tags
    else:
        tags = []

    return Hit(
        pid=str(metadata.get("pid", "")),
        chunk_id=int(metadata.get("chunk_id", 0) or 0),
        text=doc.page_content,
        file_path=str(metadata.get("file_path", "")),
        category=metadata.get("category"),
        file_type=metadata.get("file_type"),
        folder=metadata.get("folder"),
        date=int(metadata.get("date", 0) or 0),
        tags=tags,
        metadata=metadata,
    )


def search(
    query: str,
    *,
    k: int = 5,
    folder_prefix: str | None = None,
    category: str | None = None,
    file_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    config: RAGConfig | None = None,
) -> list[Hit]:
    """Return the top semantic matches from the knowledge collection.

    `query` is embedded with the configured Ollama embedding model and
    matched against the Chroma `knowledge` collection. `k` limits the final
    number of returned hits. `category`, `file_type`, `date_from`, and
    `date_to` are Chroma metadata filters; dates are `YYYY-MM-DD` strings
    compared as `YYYYMMDD` integers, and chunks with `date == 0` represent
    files that did not live under a dated folder on disk. `folder_prefix` is
    a strict `str.startswith` match on the stored folder path after trailing
    slashes are stripped; Chroma cannot express that prefix query, so rag
    fetches extra vector candidates and applies the prefix filter in Python.

    Returns:
        A list of `rag.types.Hit` objects. Each hit contains the document id,
        chunk id, chunk text, source metadata, tags, and raw Chroma metadata.

    Example:
        ```python
        from rag import search

        hits = search(
            "How is the embedding model configured?",
            k=3,
            folder_prefix="rag/embedder",
            file_type=".py",
        )
        for hit in hits:
            print(hit.pid, hit.chunk_id, hit.text[:120])
        ```
    """
    cfg = config or RAGConfig()
    where = build_where(
        category=category,
        file_type=file_type,
        date_from=date_from,
        date_to=date_to,
    )
    store = _get_store(cfg)
    retriever = VectorRetriever(store)
    retrieval_k = k * 3 if folder_prefix else k
    docs = retriever.retrieve(query, k=retrieval_k, where=where)
    hits = [_doc_to_hit(doc) for doc in docs]
    if folder_prefix is not None:
        prefix = folder_prefix.rstrip("/")
        hits = [h for h in hits if (h.folder or "").startswith(prefix)]
    return hits[:k]


def explore(
    *,
    category: str | None = None,
    config: RAGConfig | None = None,
) -> Inventory:
    """Return folder-level inventory metadata for the knowledge base.

    Inventory is read from `folder_meta.json`, which repo ingest creates next
    to the raw JSON backup. If `category` is supplied, only matching folder
    summaries are included in `Inventory.folders`; aggregate `categories`,
    `tags`, and `date_range` still describe the whole metadata file. Folder
    dates are extracted from folder paths as `YYYYMMDD` integers; folders
    without a date do not contribute to `date_range`.

    Returns:
        A `rag.types.Inventory` containing category counts, all tags, an
        optional `(min_date, max_date)` tuple, and folder summaries. If no
        metadata file exists yet, the inventory is empty.

    Example:
        ```python
        from rag import explore

        inventory = explore(category="docs")
        print(inventory.categories)
        for folder in inventory.folders:
            print(folder.folder, folder.summary)
        ```
    """
    cfg = config or RAGConfig()
    meta_path = Path(cfg.folder_meta_path())
    if not meta_path.exists():
        return Inventory(categories={}, tags=[], date_range=None, folders=[])

    with meta_path.open("r", encoding="utf-8") as file_obj:
        folder_meta: dict[str, dict] = json.load(file_obj)

    categories: dict[str, int] = {}
    all_tags: set[str] = set()
    dates: list[int] = []
    folders: list[FolderSummary] = []

    for folder_rel, meta in folder_meta.items():
        tags = meta.get("tags", [])
        summary = meta.get("summary", "")
        cat = tags[0] if tags else "unknown"

        categories[cat] = categories.get(cat, 0) + 1
        all_tags.update(tags)

        date = extract_date(folder_rel)
        if date:
            dates.append(date)

        if category and cat != category:
            continue

        folders.append(
            FolderSummary(
                folder=folder_rel,
                category=cat,
                tags=list(tags),
                summary=summary,
            )
        )

    date_range = (min(dates), max(dates)) if dates else None
    return Inventory(
        categories=categories,
        tags=sorted(all_tags),
        date_range=date_range,
        folders=folders,
    )


def list_chunks(
    *,
    folder_prefix: str | None = None,
    pid: str | None = None,
    category: str | None = None,
    file_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    config: RAGConfig | None = None,
) -> list[Hit]:
    """Enumerate stored chunks from the raw JSON backup.

    Filters mirror `search` so agents and eval harnesses can move between
    ranked and unranked retrieval without relearning the surface. `pid`
    restricts the scan to one document id. `folder_prefix` is a strict
    `str.startswith` match on the stored folder path after trailing slashes
    are stripped. `category` and `file_type` are exact metadata matches.
    `date_from` and `date_to` are `YYYY-MM-DD` strings compared as
    `YYYYMMDD` integers; any date filter drops chunks with `date == 0`, which
    means the source file did not live under a dated folder on disk. All
    filters are applied in Python, with no embedding model or Chroma
    round-trip.

    Returns:
        A list of `rag.types.Hit` objects in raw JSON backup order. `score`
        is currently `None` because this path is unranked.

    Example:
        ```python
        from rag import list_chunks

        chunks = list_chunks(
            folder_prefix="docs",
            file_type=".md",
            date_from="2026-01-01",
        )
        for chunk in chunks:
            print(chunk.file_path, chunk.chunk_id)
        ```
    """
    cfg = config or RAGConfig()
    json_store = JSONStore(cfg.raw_json_path())
    docs = json_store.get(pid=pid)
    hits = [_doc_to_hit(doc) for doc in docs]
    if folder_prefix is not None:
        prefix = folder_prefix.rstrip("/")
        hits = [h for h in hits if (h.folder or "").startswith(prefix)]
    if category is not None:
        hits = [h for h in hits if h.category == category]
    if file_type is not None:
        hits = [h for h in hits if h.file_type == file_type]
    if date_from is not None:
        lo = date_to_int(date_from)
        hits = [h for h in hits if h.date and h.date >= lo]
    if date_to is not None:
        hi = date_to_int(date_to)
        hits = [h for h in hits if h.date and h.date <= hi]
    return hits


def get_context(
    pid: str,
    chunk_id: int,
    *,
    window: int = 1,
    config: RAGConfig | None = None,
) -> ContextWindow | None:
    """Return a target chunk with neighboring chunks from the same document.

    `pid` selects the document and `chunk_id` selects the target chunk within
    that document. `window` is clamped to the inclusive range `[0, 3]`; `0`
    returns only the target chunk, while larger values include that many
    chunks before and after the target when available. If the document id is
    absent from the raw JSON backup, `None` is returned. If the document
    exists but `chunk_id` is not present, `ValueError` lists the available
    chunk ids.

    Returns:
        A `rag.types.ContextWindow` containing the target chunk, neighboring
        `ContextChunk` objects, and the total chunk count for the document, or
        `None` when `pid` does not exist.

    Example:
        ```python
        from rag import get_context

        window = get_context("readme", 2, window=2)
        if window is not None:
            for chunk in window.chunks:
                marker = ">" if chunk.is_target else " "
                print(marker, chunk.chunk_id, chunk.text[:120])
        ```
    """
    cfg = config or RAGConfig()
    json_store = JSONStore(cfg.raw_json_path())
    bounded_window = min(max(window, 0), 3)
    all_docs = json_store.get(pid=pid)
    if not all_docs:
        return None

    all_docs.sort(key=lambda doc: doc.metadata.get("chunk_id", 0))
    target_idx = next(
        (idx for idx, doc in enumerate(all_docs) if doc.metadata.get("chunk_id") == chunk_id),
        None,
    )
    if target_idx is None:
        available = [doc.metadata.get("chunk_id") for doc in all_docs]
        raise ValueError(
            f"chunk_id={chunk_id} not found in pid={pid!r}. Available: {available}"
        )

    start = max(0, target_idx - bounded_window)
    end = min(len(all_docs), target_idx + bounded_window + 1)
    chunks = [
        ContextChunk(
            chunk_id=int(doc.metadata.get("chunk_id", 0) or 0),
            text=doc.page_content,
            is_target=(doc.metadata.get("chunk_id") == chunk_id),
        )
        for doc in all_docs[start:end]
    ]
    return ContextWindow(
        pid=pid,
        target_chunk_id=chunk_id,
        chunks=chunks,
        total_chunks_in_doc=len(all_docs),
    )
