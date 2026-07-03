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

    if name in {"OPENROUTER_BASE_URL", "get_openrouter_api_key"}:
        from rag.llm.openrouter import OPENROUTER_BASE_URL, get_openrouter_api_key

        exports = {
            "OPENROUTER_BASE_URL": OPENROUTER_BASE_URL,
            "get_openrouter_api_key": get_openrouter_api_key,
        }
        return exports[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "OPENROUTER_BASE_URL",
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
    "get_openrouter_api_key",
    "ingest_repo",
    "ingest_single",
    "list_chunks",
    "list_diff",
    "prune_orphans",
    "search",
]
