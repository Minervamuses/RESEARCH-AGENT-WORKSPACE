"""Compare on-disk repo state against the knowledge store.

Hosts drive incremental ingest with explicit slash commands rather than an
automatic mtime/hash diff, so this module exposes only the primitives the
host needs: list the disk-vs-store delta, and prune store entries whose
source file no longer exists on disk.

Only entries written by `ingest_repo` are in scope. They carry both a
deterministic `source_namespace` for the canonical ingest root and a
root-relative `file_path`. Single-file ingests done via `ingest_single` set
neither tag and are ignored because they don't represent a tracked tree.
"""

from __future__ import annotations

from pathlib import Path

from rag.collect import collect_folders
from rag.config import RAGConfig, KNOWLEDGE_COLLECTION
from rag.store.cache import get_chroma_store, get_json_store
from rag.utils.paths import source_namespace


def _stored_file_paths(config: RAGConfig, namespace: str) -> dict[str, str]:
    """Return root-relative file paths mapped to their pids for one root.

    Reads from the JSON backup since it holds full metadata without a
    Chroma round-trip. Entries from other roots and single-file ingests are
    skipped.
    """
    json_store = get_json_store(config)
    paths: dict[str, str] = {}
    for doc in json_store.get():
        metadata = doc.metadata
        if metadata.get("source_namespace") != namespace:
            continue
        file_path = metadata.get("file_path")
        pid = metadata.get("pid")
        if file_path and pid:
            paths[file_path] = pid
    return paths


def list_diff(
    repo_root: str,
    config: RAGConfig | None = None,
    extra_skip: set[str] | None = None,
) -> dict[str, list[str]]:
    """List the on-disk vs in-store delta rooted at `repo_root`.

    Args:
        repo_root: Directory to scan for ingestable files.
        config: Pipeline configuration; defaults to `RAGConfig()`.
        extra_skip: Additional directory names to skip during the disk scan
            (mirrors `ingest_repo`'s argument so callers stay symmetric).

    Returns:
        Dict with two sorted lists keyed by `missing_from_store` (files on
        disk under `repo_root` that have no entry in the store) and
        `missing_from_disk` (file_paths the store knows about but whose
        `repo_root / file_path` no longer exists on disk).
    """
    cfg = config or RAGConfig()
    root = Path(repo_root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Repo root not found: {root}")
    namespace = source_namespace(root)

    folders = collect_folders(root, extra_skip=extra_skip)
    on_disk: set[str] = set()
    for files in folders.values():
        for file_path in files:
            on_disk.add(str(file_path.relative_to(root)))

    in_store = set(_stored_file_paths(cfg, namespace))

    missing_from_store = sorted(on_disk - in_store)
    missing_from_disk = sorted(
        path for path in in_store if not (root / path).is_file()
    )

    return {
        "missing_from_store": missing_from_store,
        "missing_from_disk": missing_from_disk,
    }


def prune_orphans(
    repo_root: str,
    config: RAGConfig | None = None,
) -> list[str]:
    """Delete store entries whose source file no longer exists on disk.

    Args:
        repo_root: Directory the store entries are anchored under.
        config: Pipeline configuration; defaults to `RAGConfig()`.

    Returns:
        Sorted list of namespaced pids that were deleted from both Chroma and
        the JSON backup. The list is empty if nothing was orphaned.
    """
    cfg = config or RAGConfig()
    root = Path(repo_root).resolve()
    namespace = source_namespace(root)
    diff = list_diff(str(root), cfg)
    orphan_paths = diff["missing_from_disk"]
    if not orphan_paths:
        return []

    stored_paths = _stored_file_paths(cfg, namespace)
    orphan_pids = sorted(stored_paths[path] for path in orphan_paths)
    chroma = get_chroma_store(KNOWLEDGE_COLLECTION, cfg)
    json_store = get_json_store(cfg)
    for pid in orphan_pids:
        chroma.delete(pid)
        json_store.delete(pid)
    return orphan_pids
