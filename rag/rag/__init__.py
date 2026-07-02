"""Framework-neutral RAG library."""

from rag.api import explore, get_context, list_chunks, search
from rag.config import RAGConfig
from rag.tools import TOOL_SCHEMAS, dispatch
from rag.types import ContextChunk, ContextWindow, FolderSummary, Hit, Inventory


def __getattr__(name: str):
    if name in {"ingest_repo", "ingest_single"}:
        from rag.cli.ingest import ingest_repo, ingest_single

        exports = {
            "ingest_repo": ingest_repo,
            "ingest_single": ingest_single,
        }
        return exports[name]

    if name in {"list_diff", "prune_orphans"}:
        from rag.sync import list_diff, prune_orphans

        exports = {
            "list_diff": list_diff,
            "prune_orphans": prune_orphans,
        }
        return exports[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "ContextChunk",
    "ContextWindow",
    "FolderSummary",
    "Hit",
    "Inventory",
    "RAGConfig",
    "TOOL_SCHEMAS",
    "dispatch",
    "explore",
    "get_context",
    "ingest_repo",
    "ingest_single",
    "list_chunks",
    "list_diff",
    "prune_orphans",
    "search",
]
