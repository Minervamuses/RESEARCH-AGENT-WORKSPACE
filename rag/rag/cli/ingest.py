"""Ingest a project repo into the RAG core.

rag is a tool embedded in a host project. It does not guess where the host
lives — the host points the CLI at the directory to index.

Usage:
    python -m rag.cli.ingest              # Ingest the current working directory
    python -m rag.cli.ingest -r /path     # Ingest a specific directory
    python -m rag.cli.ingest file.md      # Ingest a single file
    python -m rag.cli.ingest -r . --skip rag --skip external/rag
    python -m rag.cli.ingest -h
"""

import argparse
import json
from pathlib import Path

from langchain_core.documents import Document

from rag.chunker.token import TokenChunker
from rag.collect import (
    SKIP_DIRS,
    collect_folders,
    get_file_preview,
    has_do_not_index_sentinel,
)
from rag.config import RAGConfig, KNOWLEDGE_COLLECTION
from rag.store.chroma_store import ChromaStore
from rag.store.document_store import DocumentStore
from rag.store.json_store import JSONStore
from rag.tagger.llm_tagger import LLMTagger
from rag.utils.paths import extract_date

def _tag_folders(folders: dict[str, list[Path]], root: Path, config: RAGConfig) -> dict[str, dict]:
    """Use LLM to tag and summarize each folder.

    Returns dict mapping folder_rel -> {"tags": [...], "summary": "..."}.
    """
    tagger = LLMTagger(config)
    folder_meta: dict[str, dict] = {}

    print(f"Tagging {len(folders)} folders...")
    for folder_rel, files in sorted(folders.items()):
        file_names = [f.name for f in files]
        file_previews = {f.name: get_file_preview(f) for f in files[:10]}

        folder_display = folder_rel or "(root)"
        meta = tagger.tag(folder_rel or "(project root)", file_names, file_previews)
        folder_meta[folder_rel] = {
            "tags": meta.tags,
            "summary": meta.summary,
        }
        print(f"  {folder_display} -> {meta.tags}")
        print(f"    summary: {meta.summary}")

    return folder_meta


def ingest_repo(
    repo_root: str | None = None,
    config: RAGConfig | None = None,
    extra_skip: set[str] | None = None,
    skip_rel_paths: set[str] | None = None,
) -> tuple[int, int]:
    """Ingest all text files into a single 'knowledge' collection with rich metadata.

    Creates:
    - One ChromaDB collection ('knowledge') with category/tags metadata per chunk
    - A JSON backup of all chunks
    - folder_meta.json with per-folder tags and summaries

    Args:
        repo_root: Path to the directory to ingest. Defaults to the current
            working directory — the host project decides what to index.
        config: Pipeline configuration.
        extra_skip: Additional directory names to skip (matched against any
            path component, e.g. the rag clone dir when ingesting a host
            project that embeds rag as a subdirectory).
        skip_rel_paths: Rel paths anchored at ``repo_root`` (POSIX-style) to
            skip exactly. Use this when a name-based skip would over-match —
            e.g. excluding only the top-level ``app/`` of a monorepo without
            also skipping a sibling like ``web/backend/app/``.

    Returns:
        Tuple of (files_ingested, total_chunks).
    """
    config = config or RAGConfig()
    root = Path(repo_root).resolve() if repo_root else Path.cwd()

    if not root.is_dir():
        raise FileNotFoundError(f"Repo root not found: {root}")

    # Phase 1: Collect and tag folders
    folders = collect_folders(root, extra_skip=extra_skip, skip_rel_paths=skip_rel_paths)
    folder_meta = _tag_folders(folders, root, config)

    # Save folder metadata (merge with existing so partial ingest doesn't lose
    # tags from folders outside this run's scope).
    meta_path = Path(config.folder_meta_path())
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    existing_meta: dict[str, dict] = {}
    if meta_path.exists():
        try:
            with meta_path.open("r", encoding="utf-8") as f:
                existing_meta = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing_meta = {}
    existing_meta.update(folder_meta)
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(existing_meta, f, ensure_ascii=False, indent=2)
    print(f"\nFolder metadata saved to {meta_path}")

    # Phase 2: Chunk + write to single collection
    chunker = TokenChunker(config)
    json_store = JSONStore(config.raw_json_path())
    chroma = ChromaStore(KNOWLEDGE_COLLECTION, config)

    files_ingested = 0
    total_chunks = 0

    print(f"\nIngesting files...")
    for folder_rel, files in sorted(folders.items()):
        meta = folder_meta.get(folder_rel, {"tags": [], "summary": ""})
        tags = meta.get("tags", [])
        category = tags[0] if tags else "unknown"

        for file_path in files:
            try:
                text = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue

            if not text.strip():
                continue

            rel_path = str(file_path.relative_to(root))
            date = extract_date(rel_path)

            docs = chunker.chunk(text, rel_path)

            for doc in docs:
                doc.metadata["file_path"] = rel_path
                doc.metadata["file_type"] = file_path.suffix.lower()
                doc.metadata["folder"] = folder_rel
                doc.metadata["date"] = date
                doc.metadata["category"] = category
                doc.metadata["tags"] = json.dumps(tags)

            if docs:
                # Upsert: delete prior chunks for this pid before re-adding so
                # repeated ingest of the same path doesn't accumulate stale
                # chunks. pid == rel_path is stable across runs.
                chroma.delete(rel_path)
                json_store.delete(rel_path)
                chroma.add(docs)
                json_store.add(docs)
                files_ingested += 1
                total_chunks += len(docs)
                print(f"  [{category}] {rel_path} ({len(docs)} chunks)")

    return files_ingested, total_chunks


def ingest_single(
    file_path: str,
    pid: str | None = None,
    config: RAGConfig | None = None,
) -> tuple[str, int]:
    """Ingest a single file into the knowledge collection (no LLM tagging).

    Args:
        file_path: Path to the source file.
        pid: Document identifier. Defaults to slugified filename.
        config: Pipeline configuration.

    Returns:
        Tuple of (pid, chunk_count).
    """
    config = config or RAGConfig()
    path = Path(file_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if any(part in SKIP_DIRS for part in path.parts):
        raise ValueError(f"refusing to ingest: {path} lies under skip dir")
    if has_do_not_index_sentinel(path):
        raise ValueError(f"refusing to ingest: {path} carries do_not_index sentinel")

    pid_val = pid or path.stem.lower().replace(" ", "-").replace("_", "-")

    chunker = TokenChunker(config)
    chroma = ChromaStore(KNOWLEDGE_COLLECTION, config)
    json_store = JSONStore(config.raw_json_path())
    store = DocumentStore(chroma, json_store)

    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError):
        return pid_val, 0

    if not text.strip():
        return pid_val, 0

    docs = chunker.chunk(text, pid_val)
    if docs:
        store.delete(pid_val)
        store.add(docs)
    return pid_val, len(docs)


def main():
    parser = argparse.ArgumentParser(description="Ingest into the RAG core.")
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="File path for single-file ingest. Omit to ingest a directory.",
    )
    parser.add_argument("-p", "--pid", help="Override pid (single-file mode only)")
    parser.add_argument(
        "-r", "--repo",
        help="Directory to ingest (repo mode). Defaults to the current working directory.",
    )
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        help="Directory name to skip, repeatable (e.g. --skip rag --skip external/rag).",
    )
    args = parser.parse_args()

    try:
        if args.target:
            pid, count = ingest_single(args.target, pid=args.pid)
            print(f"ingested pid={pid}, chunks={count}")
        else:
            print("Ingesting repo...")
            files, chunks = ingest_repo(
                repo_root=args.repo,
                extra_skip=set(args.skip) or None,
            )
            print(f"\nDone: {files} files, {chunks} chunks")
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
