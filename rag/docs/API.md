# rag API Reference

## What rag is

`rag` is a framework-neutral Python library for indexing text files into a local knowledge store.
It stores chunks in Chroma for semantic search and in a JSON backup for deterministic enumeration and context windows.
The public API is intentionally small: four functions, five return dataclasses, one configuration dataclass, and an optional tool-calling layer.

## Install & Prerequisites

Install the package and dependencies from the repository root:

```bash
poetry install
```

External services:

- Ollama must be running for ingest and semantic search.
- The Ollama embedding model defaults to `bge-m3`; install it before ingest/search:

```bash
ollama pull bge-m3
```

- `OPENROUTER_API_KEY` is required only for repo ingest folder tagging. It is not required for `search`, `explore`, `list_chunks`, or `get_context` after data has been ingested.

The default store location is `<rag repo root>/store`. Set `KMS_STORE_DIR` to point rag at another store directory.

## The Four Functions

Import the public API from `rag`:

```python
from rag import explore, get_context, list_chunks, search
```

All functions accept an optional keyword-only `config: RAGConfig | None = None`. If omitted, `RAGConfig()` is used.

### `search`

Signature:

```python
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
    ...
```

Arguments:

- `query: str` is embedded with the configured Ollama embedding model and matched against the Chroma `knowledge` collection.
- `k: int = 5` limits the final number of returned hits.
- `folder_prefix: str | None = None` filters on `Hit.folder` using strict `str.startswith` after stripping trailing slashes from the provided prefix. This filter is applied in Python after vector retrieval because Chroma metadata filters cannot express prefix matching.
- `category: str | None = None` is an exact Chroma metadata match.
- `file_type: str | None = None` is an exact Chroma metadata match, usually a file extension such as `.md` or `.py`.
- `date_from: str | None = None` is a lower bound date in `YYYY-MM-DD` format, converted to a `YYYYMMDD` integer for Chroma metadata filtering.
- `date_to: str | None = None` is an upper bound date in `YYYY-MM-DD` format, converted to a `YYYYMMDD` integer for Chroma metadata filtering.
- `config: RAGConfig | None = None` injects storage/model settings. Tool schemas do not expose config fields to an LLM.

Date metadata uses `YYYYMMDD` integers. `date == 0` means the source file did not live under a dated folder on disk.

Returns:

- `list[Hit]`: ranked semantic hits. `Hit.score` is currently `None`; raw retriever scores are not surfaced through this API yet.

Runnable example:

```python
from rag import search


def main() -> None:
    hits = search(
        "How is the embedding model configured?",
        k=3,
        folder_prefix="rag/embedder",
        file_type=".py",
    )
    for hit in hits:
        print(f"{hit.pid} chunk={hit.chunk_id} path={hit.file_path}")
        print(hit.text[:240])


if __name__ == "__main__":
    main()
```

### `explore`

Signature:

```python
def explore(
    *,
    category: str | None = None,
    config: RAGConfig | None = None,
) -> Inventory:
    ...
```

Arguments:

- `category: str | None = None` filters only the returned `Inventory.folders` list to folders whose primary category equals this value.
- `config: RAGConfig | None = None` injects storage settings.

Aggregate fields in the returned `Inventory` still describe the whole metadata file: `categories`, `tags`, and `date_range` are not narrowed by the `category` argument. If `folder_meta.json` does not exist, `explore` returns an empty inventory.

Returns:

- `Inventory`: category counts, all tags, optional date range, and folder summaries.

Runnable example:

```python
from rag import explore


def main() -> None:
    inventory = explore(category="docs")
    print("categories:", inventory.categories)
    print("tags:", inventory.tags)
    print("date range:", inventory.date_range)
    for folder in inventory.folders:
        print(f"{folder.folder}: {folder.summary}")


if __name__ == "__main__":
    main()
```

### `list_chunks`

Signature:

```python
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
    ...
```

Arguments:

- `folder_prefix: str | None = None` filters on `Hit.folder` using strict `str.startswith` after stripping trailing slashes from the provided prefix.
- `pid: str | None = None` restricts enumeration to one document id.
- `category: str | None = None` is an exact metadata match.
- `file_type: str | None = None` is an exact metadata match, usually a file extension such as `.md` or `.py`.
- `date_from: str | None = None` is a lower bound date in `YYYY-MM-DD` format, converted to a `YYYYMMDD` integer.
- `date_to: str | None = None` is an upper bound date in `YYYY-MM-DD` format, converted to a `YYYYMMDD` integer.
- `config: RAGConfig | None = None` injects storage settings.

All filters run in Python over the raw JSON backup. `list_chunks` does not call the embedding model and does not query Chroma. If either date bound is supplied, chunks with `date == 0` are dropped because they have no dated folder on disk.

Returns:

- `list[Hit]`: stored chunks in raw JSON backup order. `Hit.score` is currently `None`.

Runnable example:

```python
from rag import list_chunks


def main() -> None:
    chunks = list_chunks(
        folder_prefix="docs",
        file_type=".md",
        date_from="2026-01-01",
    )
    for chunk in chunks:
        print(f"{chunk.file_path} chunk={chunk.chunk_id}")


if __name__ == "__main__":
    main()
```

### `get_context`

Signature:

```python
def get_context(
    pid: str,
    chunk_id: int,
    *,
    window: int = 1,
    config: RAGConfig | None = None,
) -> ContextWindow | None:
    ...
```

Arguments:

- `pid: str` selects the document id.
- `chunk_id: int` selects the target chunk within that document.
- `window: int = 1` is clamped to the inclusive range `[0, 3]`. `0` returns only the target chunk; larger values include that many chunks before and after the target when available.
- `config: RAGConfig | None = None` injects storage settings.

If `pid` does not exist in the raw JSON backup, `get_context` returns `None`. If `pid` exists but `chunk_id` is absent, it raises `ValueError` and lists the available chunk ids.

Returns:

- `ContextWindow | None`: target chunk, neighboring chunks, and total chunk count for the document, or `None` if the document id does not exist.

Runnable example:

```python
from rag import get_context


def main() -> None:
    window = get_context("readme", 2, window=2)
    if window is None:
        print("document not found")
        return

    for chunk in window.chunks:
        marker = ">" if chunk.is_target else " "
        print(f"{marker} chunk={chunk.chunk_id}")
        print(chunk.text[:240])


if __name__ == "__main__":
    main()
```

## Dataclasses

### `Hit`

```python
@dataclass(frozen=True)
class Hit:
    pid: str
    chunk_id: int
    text: str
    file_path: str
    category: str | None = None
    file_type: str | None = None
    folder: str | None = None
    date: int = 0
    tags: list[str] = field(default_factory=list)
    score: float | None = None
    metadata: dict = field(default_factory=dict)
```

Fields:

- `pid`: stable document identifier assigned during chunking or ingest.
- `chunk_id`: zero-based chunk ordinal within the source document.
- `text`: chunk text exactly as stored in the knowledge base.
- `file_path`: source file path relative to the ingested root.
- `category`: primary folder tag used as the high-level category, when available.
- `file_type`: source file extension such as `.md` or `.py`, when available.
- `folder`: source parent folder relative to the ingested root, when available.
- `date`: date encoded as `YYYYMMDD`; `0` means no date folder was found on disk.
- `tags`: folder tags copied from ingest metadata.
- `score`: retrieval score when populated; currently always `None` in public APIs.
- `metadata`: verbatim Chroma document metadata; keys and values may change over time.

### `FolderSummary`

```python
@dataclass(frozen=True)
class FolderSummary:
    folder: str
    category: str
    tags: list[str]
    summary: str
```

Fields:

- `folder`: folder path relative to the ingested root.
- `category`: primary folder tag used as the folder category.
- `tags`: all tags assigned to the folder during repo ingest.
- `summary`: LLM-generated folder summary from repo ingest metadata.

### `Inventory`

```python
@dataclass(frozen=True)
class Inventory:
    categories: dict[str, int]
    tags: list[str]
    date_range: tuple[int, int] | None
    folders: list[FolderSummary]
```

Fields:

- `categories`: count of folders per primary category across the metadata file.
- `tags`: sorted unique tags found across the metadata file.
- `date_range`: inclusive `(min_date, max_date)` as `YYYYMMDD` ints, or `None`.
- `folders`: folder summaries, optionally filtered by category.

### `ContextChunk`

```python
@dataclass(frozen=True)
class ContextChunk:
    chunk_id: int
    text: str
    is_target: bool
```

Fields:

- `chunk_id`: zero-based chunk ordinal within the source document.
- `text`: chunk text exactly as stored in the raw JSON backup.
- `is_target`: whether this chunk is the requested target chunk.

### `ContextWindow`

```python
@dataclass(frozen=True)
class ContextWindow:
    pid: str
    target_chunk_id: int
    chunks: list[ContextChunk]
    total_chunks_in_doc: int
```

Fields:

- `pid`: stable document identifier shared by every chunk in the window.
- `target_chunk_id`: chunk id requested by the caller.
- `chunks`: ordered chunks included in the bounded context window.
- `total_chunks_in_doc`: total number of chunks stored for the source document.

## Configuration

```python
@dataclass
class RAGConfig:
    persist_dir: str = field(default_factory=_default_persist_dir)
    chunk_size: int = 1200
    chunk_overlap: int = 100
    encoding_model: str = "o200k_base"
    embed_model: str = "bge-m3"
    default_k: int = 10
    tagger_model: str = "z-ai/glm-5"
    raw_collection: str = "raw"
```

Fields:

- `persist_dir`: directory containing Chroma state, `raw.json`, and `folder_meta.json`. Defaults to `KMS_STORE_DIR` if set, otherwise `<rag repo root>/store`.
- `chunk_size`: maximum token count per chunk produced during ingest.
- `chunk_overlap`: number of tokens repeated between adjacent chunks during ingest.
- `encoding_model`: tiktoken encoding name used by the token chunker.
- `embed_model`: Ollama embedding model name used for ingest and semantic search.
- `default_k`: default retrieval count for callers that choose to use config defaults.
- `tagger_model`: OpenRouter model name used by repo ingest folder tagging.
- `raw_collection`: legacy raw collection name retained for store compatibility.

Use subclassing for host-specific settings:

```python
from dataclasses import dataclass

from rag import RAGConfig


@dataclass
class HostConfig(RAGConfig):
    agent_model: str = "example-model"
    max_turns: int = 12
```

Pass a config instance explicitly when a call should use non-default storage or models:

```python
from rag import RAGConfig, search

config = RAGConfig(persist_dir="/tmp/my-rag-store", embed_model="bge-m3")
hits = search("configuration", config=config)
```

## Error Model

`rag` currently has no typed exception hierarchy.

Errors propagate from the layer that raises them:

- Chroma errors propagate from vector store reads/writes.
- Ollama errors propagate when embeddings are requested and Ollama is offline, missing `bge-m3`, or otherwise unavailable.
- OpenRouter errors propagate during repo ingest folder tagging when `OPENROUTER_API_KEY` or the configured model is invalid.
- JSON/file errors propagate from the local store paths.
- `get_context` raises `ValueError` when a document exists but the requested chunk id is absent.

Callers that need stable application-level failures should wrap these calls at the integration boundary. A typed `rag` exception hierarchy is intentionally left for future work.

## Tool-Calling

`rag.tools` exposes a framework-neutral tool layer for LLM agents:

```python
from rag import TOOL_SCHEMAS, dispatch
```

`TOOL_SCHEMAS` contains four tool definitions:

- `rag_search`
- `rag_explore`
- `rag_list_chunks`
- `rag_get_context`

Each definition has exactly these keys:

```python
{
    "name": "...",
    "description": "...",
    "input_schema": {...},
}
```

The `input_schema` value is pure JSON Schema draft-7. The outer `input_schema` key follows Anthropic's tool convention. For OpenAI tools, wrap the same object as a function and rename `input_schema` to `parameters`. For MCP tools, rename `input_schema` to `inputSchema`.

Example dispatch:

```python
from rag import dispatch

result = dispatch("rag_explore", {})
print(result["categories"])
```

`dispatch(name: str, args: dict, *, config: RAGConfig | None = None) -> Any` routes to the matching public function and serializes dataclass returns with `dataclasses.asdict`. Lists of dataclasses become lists of dictionaries.

The tool schemas intentionally do not expose ingest. Ingest remains a CLI/API operation controlled by the host process, not an LLM tool. The schemas also do not expose config fields; inject config through the `dispatch(..., config=...)` keyword from trusted code.
