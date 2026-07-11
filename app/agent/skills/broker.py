"""Skill activation gate over the shared tool access resolver."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from agent.tool_access import ToolAccessResolution, resolve_tool_access


def resolve_skill_tool_access(
    manifest: Mapping[str, Any] | None,
    all_tools: Sequence[Any],
    *,
    mcp_families: Mapping[str, str],
) -> ToolAccessResolution:
    """Resolve a skill's tool access, refusing activation on missing required tools.

    Missing optional tools never block activation; they stay visible on the
    returned resolution for diagnostics.
    """
    resolution = resolve_tool_access(manifest, all_tools, mcp_families=mcp_families)
    if resolution.missing_required:
        missing = ", ".join(resolution.missing_required)
        raise ValueError(f"required skill tools are unavailable: {missing}")
    return resolution
