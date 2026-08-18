"""Framework-neutral tool schemas and dispatch for agent integrations."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Callable

from rag.api import explore, get_context, list_chunks, search
from rag.config import RAGConfig


DATE_DESCRIPTION = (
    "Date string in YYYY-MM-DD format; rag converts it to a YYYYMMDD integer "
    "for filtering."
)

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "rag_search",
        "description": (
            "Return the top semantic matches from the knowledge collection. "
            "The query is embedded with the configured Ollama embedding model "
            "and matched against the Chroma knowledge collection. category, "
            "file_type, date_from, and date_to are Chroma metadata filters. "
            "folder_prefix is a strict str.startswith match on the stored "
            "folder path after trailing slashes are stripped; rag fetches "
            "extra vector candidates and applies this prefix filter in Python. "
            "Returns a list of Hit dictionaries."
        ),
        "input_schema": {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Natural-language query to embed and match against the "
                        "Chroma knowledge collection."
                    ),
                },
                "k": {
                    "type": "integer",
                    "default": 5,
                    "minimum": 1,
                    "description": "Maximum number of final hits to return.",
                },
                "folder_prefix": {
                    "type": "string",
                    "description": (
                        "Strict str.startswith match on the stored folder path "
                        "after trailing slashes are stripped."
                    ),
                },
                "category": {
                    "type": "string",
                    "description": "Exact category metadata match.",
                },
                "file_type": {
                    "type": "string",
                    "description": "Exact file type metadata match, such as .md or .py.",
                },
                "date_from": {
                    "type": "string",
                    "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                    "description": f"Inclusive lower bound. {DATE_DESCRIPTION}",
                },
                "date_to": {
                    "type": "string",
                    "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                    "description": f"Inclusive upper bound. {DATE_DESCRIPTION}",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "rag_explore",
        "description": (
            "Return folder-level inventory metadata for the knowledge base. "
            "Inventory is read from folder_meta.json. If category is supplied, "
            "only matching folder summaries are included in Inventory.folders; "
            "aggregate categories, tags, and date_range still describe the "
            "whole metadata file. Returns an Inventory dictionary, or an empty "
            "inventory if no metadata file exists yet."
        ),
        "input_schema": {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "category": {
                    "type": "string",
                    "description": (
                        "Filter returned folder summaries to this primary "
                        "category. Aggregate fields still describe the whole "
                        "metadata file."
                    ),
                },
            },
        },
    },
    {
        "name": "rag_list_chunks",
        "description": (
            "Enumerate stored chunks from the raw JSON backup. Filters mirror "
            "rag_search so agents can move between ranked and unranked "
            "retrieval without relearning the surface. pid restricts the scan "
            "to one document id. folder_prefix is a strict str.startswith "
            "match on the stored folder path after trailing slashes are "
            "stripped. category and file_type are exact metadata matches. "
            "date_from and date_to are YYYY-MM-DD strings compared as YYYYMMDD "
            "integers; any date filter drops chunks with date == 0. No "
            "embedding model or Chroma round-trip is used. Returns a list of "
            "Hit dictionaries in raw JSON backup order."
        ),
        "input_schema": {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "folder_prefix": {
                    "type": "string",
                    "description": (
                        "Strict str.startswith match on the stored folder path "
                        "after trailing slashes are stripped."
                    ),
                },
                "pid": {
                    "type": "string",
                    "description": "Restrict enumeration to one document id.",
                },
                "category": {
                    "type": "string",
                    "description": "Exact category metadata match.",
                },
                "file_type": {
                    "type": "string",
                    "description": "Exact file type metadata match, such as .md or .py.",
                },
                "date_from": {
                    "type": "string",
                    "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                    "description": (
                        f"Inclusive lower bound. {DATE_DESCRIPTION} Any date "
                        "filter drops chunks with date == 0."
                    ),
                },
                "date_to": {
                    "type": "string",
                    "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                    "description": (
                        f"Inclusive upper bound. {DATE_DESCRIPTION} Any date "
                        "filter drops chunks with date == 0."
                    ),
                },
            },
        },
    },
    {
        "name": "rag_get_context",
        "description": (
            "Return a target chunk with neighboring chunks from the same "
            "document. pid selects the document and chunk_id selects the "
            "target chunk within that document. window is clamped to the "
            "inclusive range [0, 3]; 0 returns only the target chunk, while "
            "larger values include that many chunks before and after the "
            "target when available. Returns a ContextWindow dictionary, None "
            "when pid does not exist, or raises ValueError when chunk_id is not "
            "present in an existing document."
        ),
        "input_schema": {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "pid": {
                    "type": "string",
                    "description": "Document id to read from the raw JSON backup.",
                },
                "chunk_id": {
                    "type": "integer",
                    "description": "Target chunk id within the selected document.",
                },
                "window": {
                    "type": "integer",
                    "default": 1,
                    "description": (
                        "Number of neighboring chunks before and after the "
                        "target. The API clamps this value to [0, 3]."
                    ),
                },
            },
            "required": ["pid", "chunk_id"],
        },
    },
]

_CALLS: dict[str, Callable[..., Any]] = {
    "rag_search": search,
    "rag_explore": explore,
    "rag_list_chunks": list_chunks,
    "rag_get_context": get_context,
}


def _to_wire(value: Any) -> Any:
    """Convert public dataclass returns into framework-neutral containers."""
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, list):
        return [_to_wire(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_wire(item) for item in value)
    if isinstance(value, dict):
        return {key: _to_wire(item) for key, item in value.items()}
    return value


def dispatch(
    name: str,
    args: dict,
    *,
    config: RAGConfig | None = None,
) -> Any:
    """Call a rag tool by name and serialize dataclass returns.

    `config` is injected by trusted host code and is intentionally not part of
    any tool input schema.
    """
    if name not in _CALLS:
        available = ", ".join(sorted(_CALLS))
        raise ValueError(f"Unknown rag tool {name!r}. Available tools: {available}")
    if not isinstance(args, dict):
        raise TypeError("args must be a dict")
    if "config" in args:
        raise ValueError("config must be passed as dispatch(..., config=...), not in args")

    call_args = dict(args)
    if config is not None:
        call_args["config"] = config

    return _to_wire(_CALLS[name](**call_args))
