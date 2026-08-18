"""Central configuration for the RAG library.

Only settings rag itself needs belong here. Hosts layer their own config on
top via subclassing.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

KNOWLEDGE_COLLECTION = "knowledge"


def _default_persist_dir() -> str:
    """Resolve the store directory.

    The store is application-owned local state (Chroma + JSON). Default to
    ``store/`` at the app project root, which remains excluded from workspace
    ingest. Order:
      1. ``KMS_STORE_DIR`` env var (explicit override, host may still pin
         it wherever it wants).
      2. ``<app project root>/store/``.
    """
    env = os.environ.get("KMS_STORE_DIR")
    if env:
        return env
    app_root = Path(__file__).resolve().parent.parent
    return str(app_root / "store")


@dataclass
class RAGConfig:
    """Configuration for rag storage, chunking, embedding, retrieval, and tagging.

    Subclassing is the supported extension pattern for host-specific settings;
    keep fields in this base class limited to values rag itself consumes.
    """

    # Storage
    persist_dir: str = field(default_factory=_default_persist_dir)
    """Directory containing Chroma state, `raw.json`, and `folder_meta.json`."""

    # Chunking
    chunk_size: int = 1200
    """Maximum token count per chunk produced during ingest."""
    chunk_overlap: int = 100
    """Number of tokens repeated between adjacent chunks during ingest."""
    encoding_model: str = "o200k_base"
    """Tiktoken encoding name used by the token chunker."""

    # Embedding
    embed_model: str = "bge-m3"
    """Ollama embedding model name used for ingest and semantic search."""

    # LLM used by rag's own tagger
    tagger_model: str = "z-ai/glm-5"
    """OpenRouter model name used by repo ingest folder tagging."""

    def raw_json_path(self) -> str:
        """Path to the raw chunks JSON file."""
        return f"{self.persist_dir}/raw.json"

    def folder_meta_path(self) -> str:
        """Path to the folder metadata JSON file."""
        return f"{self.persist_dir}/folder_meta.json"
