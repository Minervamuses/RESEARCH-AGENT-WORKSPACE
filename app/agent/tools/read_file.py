"""LangChain tool factory for reading a text file from disk.

Exposes a single `read_file` tool the agent can call when it needs the
contents of a specific file. Mirrors the factory pattern used by the
LangChain RAG tool adapter.
"""

from __future__ import annotations

import codecs
import json
from pathlib import Path
from typing import Annotated

from langgraph.prebuilt import InjectedState
from langchain_core.tools import StructuredTool
from pydantic import Field

from agent.config import AgentConfig
from agent.conversations.models import is_canonical_uuid4_hex

TOOL_NAME = "read_file"
TOOL_DESCRIPTION = (
    "Read the contents of a text file from disk. Accepts absolute or "
    "working-directory-relative paths. When a skill is active, relative paths "
    "starting with references/, assets/, or scripts/ are resolved only against "
    "the active skill root and do not fall back to the working directory. "
    "Other relative paths are resolved from the working directory. Reads at "
    "most 1 MB per call. Canonical conversation JSON files may be read in "
    "chunks with an explicit `offset_bytes` (start at 0 "
    "and follow `next_offset`). Returns a JSON "
    "object with `path`, `size`, and `content`; chunked reads also include "
    "`offset_bytes` and `next_offset`. On failure returns a JSON object with "
    "an `error` field."
)

MAX_BYTES = 1_048_576
SKILL_RESOURCE_DIRS = frozenset({"references", "assets", "scripts"})
SENSITIVE_BASENAME_PREFIXES = ("credentials", "token", "secret", "secrets")


def _error(message: str) -> str:
    return json.dumps({"error": message}, ensure_ascii=False)


def _is_skill_resource_path(path: Path) -> bool:
    return bool(path.parts) and path.parts[0] in SKILL_RESOURCE_DIRS


def _would_escape_skill_root(path: Path, root: Path) -> bool:
    return not (root / path).resolve().is_relative_to(root)


def _is_sensitive_path(path: Path) -> bool:
    parts = {part.casefold() for part in path.parts}
    if ".ssh" in parts:
        return True

    name = path.name.casefold()
    if name == ".env" or name.startswith(".env."):
        return True
    if name == "id_rsa" or name.startswith("id_rsa."):
        return True
    return any(name.startswith(prefix) for prefix in SENSITIVE_BASENAME_PREFIXES)


def _read_file(
    path: str,
    skill_root: str | None = None,
    offset_bytes: int | None = None,
    conversation_root: Path | None = None,
) -> str:
    raw_path = Path(path).expanduser()
    if skill_root and not raw_path.is_absolute():
        root = Path(skill_root).expanduser().resolve()
        if _would_escape_skill_root(raw_path, root):
            return _error(f"path escapes active skill root: {path}")
        if _is_skill_resource_path(raw_path):
            return _read_resolved_file(
                (root / raw_path).resolve(),
                offset_bytes=offset_bytes,
                conversation_root=conversation_root,
            )

    resolved = raw_path.resolve()
    return _read_resolved_file(
        resolved,
        offset_bytes=offset_bytes,
        conversation_root=conversation_root,
    )


def _read_resolved_file(
    resolved: Path,
    *,
    offset_bytes: int | None,
    conversation_root: Path | None,
) -> str:

    if _is_sensitive_path(resolved):
        return _error("path blocked by sensitive denylist")

    if not resolved.exists():
        return _error(f"path does not exist: {resolved}")
    if not resolved.is_file():
        return _error(f"path is not a regular file: {resolved}")

    size = resolved.stat().st_size
    if offset_bytes is None:
        if size > MAX_BYTES:
            return _error(
                f"file too large: {size} bytes (single-call limit {MAX_BYTES}); "
                "retry with offset_bytes=0 and follow next_offset"
            )

        content = resolved.read_text(encoding="utf-8", errors="replace")
        return json.dumps(
            {"path": str(resolved), "size": size, "content": content},
            ensure_ascii=False,
        )

    if type(offset_bytes) is not int or offset_bytes < 0:
        return _error("offset_bytes must be a non-negative integer")
    if (
        conversation_root is None
        or resolved.parent != conversation_root
        or resolved.suffix != ".json"
        or not is_canonical_uuid4_hex(resolved.stem)
    ):
        return _error(
            "chunked reads are limited to canonical conversation JSON files"
        )
    if offset_bytes > size:
        return _error(
            f"offset_bytes {offset_bytes} exceeds file size {size}"
        )
    with resolved.open("rb") as handle:
        handle.seek(offset_bytes)
        raw_content = handle.read(MAX_BYTES)
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    at_eof = offset_bytes + len(raw_content) >= size
    content = decoder.decode(raw_content, final=at_eof)
    buffered, _decoder_state = decoder.getstate()
    consumed = len(raw_content) - len(buffered)
    next_value = offset_bytes + consumed
    next_offset = next_value if next_value < size else None
    return json.dumps(
        {
            "path": str(resolved),
            "size": size,
            "offset_bytes": offset_bytes,
            "next_offset": next_offset,
            "content": content,
        },
        ensure_ascii=False,
    )


def create_read_file_tool(config: AgentConfig) -> StructuredTool:
    """Build the read_file tool. `config` accepted for factory symmetry."""
    conversation_root = (
        Path(config.persist_dir).expanduser() / "conversations"
    ).resolve()

    def _run(
        path: Annotated[
            str,
            Field(description="Absolute or cwd-relative path to a UTF-8 text file."),
        ],
        offset_bytes: Annotated[
            int | None,
            Field(
                description=(
                    "Optional zero-based byte offset for a bounded chunk. Use 0 "
                    "for the first chunk of a file over 1 MB, then follow "
                    "next_offset until it is null."
                ),
                ge=0,
            ),
        ] = None,
        state: Annotated[dict, InjectedState] | None = None,
    ) -> str:
        skill_root = state.get("skill_root") if isinstance(state, dict) else None
        return _read_file(
            path,
            skill_root=skill_root,
            offset_bytes=offset_bytes,
            conversation_root=conversation_root,
        )

    _run.__name__ = TOOL_NAME

    return StructuredTool.from_function(
        func=_run,
        name=TOOL_NAME,
        description=TOOL_DESCRIPTION,
        infer_schema=True,
    )
