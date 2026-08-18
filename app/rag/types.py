"""Framework-neutral data types for the KMS public API."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Hit:
    """A single retrieval hit."""

    pid: str
    """Stable document identifier assigned during chunking or ingest."""
    chunk_id: int
    """Zero-based chunk ordinal within the source document."""
    text: str
    """Chunk text exactly as stored in the knowledge base."""
    file_path: str
    """Source file path relative to the ingested root."""
    category: str | None = None
    """Primary folder tag used as the high-level category, when available."""
    file_type: str | None = None
    """Source file extension such as `.md` or `.py`, when available."""
    folder: str | None = None
    """Source parent folder relative to the ingested root, when available."""
    date: int = 0
    """Date encoded as `YYYYMMDD`; `0` means no date folder was found on disk."""
    tags: list[str] = field(default_factory=list)
    """Folder tags copied from ingest metadata."""
    score: float | None = None
    """Retrieval score when populated; currently always `None` in public APIs."""
    metadata: dict = field(default_factory=dict)
    """Verbatim Chroma document metadata; keys and values may change over time."""


@dataclass(frozen=True)
class FolderSummary:
    """Summary metadata for one folder in the knowledge base."""

    folder: str
    """Folder path relative to the ingested root."""
    category: str
    """Primary folder tag used as the folder category."""
    tags: list[str]
    """All tags assigned to the folder during repo ingest."""
    summary: str
    """LLM-generated folder summary from repo ingest metadata."""


@dataclass(frozen=True)
class Inventory:
    """Summary of what the knowledge base contains."""

    categories: dict[str, int]
    """Count of folders per primary category across the metadata file."""
    tags: list[str]
    """Sorted unique tags found across the metadata file."""
    date_range: tuple[int, int] | None
    """Inclusive `(min_date, max_date)` as `YYYYMMDD` ints, or `None`."""
    folders: list[FolderSummary]
    """Folder summaries, optionally filtered by category."""


@dataclass(frozen=True)
class ContextChunk:
    """A single chunk in a document context window."""

    chunk_id: int
    """Zero-based chunk ordinal within the source document."""
    text: str
    """Chunk text exactly as stored in the raw JSON backup."""
    is_target: bool
    """Whether this chunk is the requested target chunk."""


@dataclass(frozen=True)
class ContextWindow:
    """A chunk plus its neighbours within the same document."""

    pid: str
    """Stable document identifier shared by every chunk in the window."""
    target_chunk_id: int
    """Chunk id requested by the caller."""
    chunks: list[ContextChunk]
    """Ordered chunks included in the bounded context window."""
    total_chunks_in_doc: int
    """Total number of chunks stored for the source document."""
