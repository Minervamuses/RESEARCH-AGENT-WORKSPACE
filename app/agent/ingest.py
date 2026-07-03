"""Knowledge-base ingest service: the agent-side wrapper around rag.

The CLI layer (slash commands) only parses arguments and renders messages;
every rag call goes through here so cli/ never imports rag directly.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from rag import ingest_repo, ingest_single, list_diff, prune_orphans

from agent.config import AgentConfig
from agent.paths import find_app_root


async def init_workspace(config: AgentConfig) -> tuple[int, int, Path, set[str]]:
    """Ingest the host workspace root, skipping the app (and rag) projects.

    Returns (files, chunks, host_root, excluded_names).
    """
    app_root = find_app_root()
    host_root = app_root.parent
    skip = {app_root.name}
    rag_root = host_root / "rag"
    if rag_root.is_dir():
        skip.add(rag_root.name)
    files, chunks = await asyncio.to_thread(
        ingest_repo,
        str(host_root),
        config=config,
        skip_rel_paths=skip,
    )
    return files, chunks, host_root, skip


async def ingest_file(target: Path, config: AgentConfig) -> tuple[str, int]:
    """Ingest one file; returns (pid, chunk count)."""
    return await asyncio.to_thread(ingest_single, str(target), config=config)


async def ingest_folder(target: Path, config: AgentConfig) -> tuple[int, int]:
    """Ingest a directory tree; returns (files, chunks)."""
    return await asyncio.to_thread(ingest_repo, str(target), config=config)


async def diff_folder(target: Path, config: AgentConfig) -> dict:
    """Diff the store against a directory tree."""
    return await asyncio.to_thread(list_diff, str(target), config)


async def prune_folder(target: Path, config: AgentConfig) -> list[str]:
    """Remove store entries whose files no longer exist under target."""
    return await asyncio.to_thread(prune_orphans, str(target), config)
