"""Compare on-disk repo state against the knowledge store.

Hosts drive incremental ingest with explicit slash commands rather than an
automatic mtime/hash diff, so this module exposes only the primitives the
host needs: list the disk-vs-store delta, and prune store entries whose
source file no longer exists on disk.

Only entries written by `ingest_repo` are in scope (they carry a
`file_path` metadata tag that is the rel_path under the ingest root).
Single-file ingests done via `ingest_single` set no such tag and are
therefore ignored — they don't represent a tracked tree.
"""

from __future__ import annotations

from pathlib import Path

from rag.cli.ingest import _collect_folders
from rag.config import RAGConfig, KNOWLEDGE_COLLECTION
from rag.store.chroma_store import ChromaStore
from rag.store.json_store import JSONStore


def _stored_file_paths(config: RAGConfig) -> set[str]:
    """Return the set of `file_path` values currently in the store.

    Reads from the JSON backup since it holds full metadata without a
    Chroma round-trip. Pids without a `file_path` (single-file ingests)
    are skipped — they aren't part of any tracked tree.
    """
    json_store = JSONStore(config.raw_json_path())
    paths: set[str] = set()
    for doc in json_store.get():
        file_path = doc.metadata.get("file_path")
        if file_path:
            paths.add(file_path)
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

    folders = _collect_folders(root, extra_skip=extra_skip)
    on_disk: set[str] = set()
    for files in folders.values():
        for file_path in files:
            on_disk.add(str(file_path.relative_to(root)))

    in_store = _stored_file_paths(cfg)

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
    extra_skip: set[str] | None = None,
) -> list[str]:
    """Delete store entries whose source file no longer exists on disk.

    Args:
        repo_root: Directory the store entries are anchored under.
        config: Pipeline configuration; defaults to `RAGConfig()`.
        extra_skip: Additional directory names to skip (passed through to
            `list_diff` for parity).

    Returns:
        Sorted list of pids that were deleted from both Chroma and the
        JSON backup. The list is empty if nothing was orphaned.
    """
    cfg = config or RAGConfig()
    diff = list_diff(repo_root, cfg, extra_skip)
    orphans = diff["missing_from_disk"]
    if not orphans:
        return []

    chroma = ChromaStore(KNOWLEDGE_COLLECTION, cfg)
    json_store = JSONStore(cfg.raw_json_path())
    for pid in orphans:
        chroma.delete(pid)
        json_store.delete(pid)
    return orphans
