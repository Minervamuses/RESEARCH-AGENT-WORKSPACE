"""Single source of truth for global vs skill-scoped tool access.

Tools fall into exactly two classes:

1. Global tools — the local base tools (:func:`base_tool_names`) plus every
   MCP tool whose family is ``web_search``. They are available in normal mode
   and under every skill, whenever they actually exist in the session's tool
   universe.
2. Skill tools — everything else. They exist for a turn only when the active
   skill's manifest requests them in its ``tools`` section.

Graph tool binding, prompt availability rendering, the fusion proposers'
read-only intersection, and PolicyToolNode's runtime enforcement all consume
the same :class:`ToolAccessResolution`; none of them re-derives access rules.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from agent.tools.inventory import base_tool_names

# The only MCP family granted globally. Every other family is skill-scoped.
GLOBAL_MCP_FAMILY = "web_search"


@dataclass(frozen=True)
class ToolAccessResolution:
    """Resolved tool access for one mode (normal mode or one active skill)."""

    global_tools: tuple[str, ...]
    skill_tools: tuple[str, ...]
    effective_tools: tuple[str, ...]
    missing_required: tuple[str, ...]
    missing_optional: tuple[str, ...]


def resolve_tool_access(
    manifest: Mapping[str, Any] | None,
    all_tools: Sequence[Any],
    *,
    mcp_families: Mapping[str, str],
    global_mcp_families: Collection[str] | None = None,
) -> ToolAccessResolution:
    """Resolve the effective tool set for a manifest over a tool universe.

    ``all_tools`` is the universe of tools that actually exist right now
    (objects with a ``name`` attribute, or plain names). ``mcp_families``
    maps MCP tool names to their family identifier. ``manifest`` is a
    validated skill manifest, or ``None``/tool-less for normal mode.

    ``missing_required`` names required manifest entries (local tool names or
    MCP families) that resolved to nothing; callers must refuse skill
    activation when it is non-empty. ``missing_optional`` never blocks.
    """
    ordered_names = _dedupe(_tool_name(tool) for tool in all_tools)
    available = set(ordered_names)
    families = dict(mcp_families)
    global_families = set(
        global_mcp_families
        if global_mcp_families is not None
        else (GLOBAL_MCP_FAMILY,)
    )
    base_names = set(base_tool_names())

    global_selected = {
        name
        for name in available
        if name in base_names or families.get(name) in global_families
    }

    tools_section = (manifest or {}).get("tools") or {}
    skill_selected: set[str] = set()
    missing_required: list[str] = []
    missing_optional: list[str] = []
    for key, missing in (
        ("required", missing_required),
        ("optional", missing_optional),
    ):
        selector = tools_section.get(key) or {}
        for name in selector.get("local") or []:
            if name in available:
                skill_selected.add(name)
            else:
                missing.append(name)
        for family in selector.get("mcp_families") or []:
            members = {
                name
                for name in available
                if families.get(name) == family
            }
            if members:
                skill_selected.update(members)
            else:
                missing.append(family)

    return ToolAccessResolution(
        global_tools=tuple(
            name for name in ordered_names if name in global_selected
        ),
        skill_tools=tuple(
            name
            for name in ordered_names
            if name in skill_selected and name not in global_selected
        ),
        effective_tools=tuple(
            name
            for name in ordered_names
            if name in global_selected or name in skill_selected
        ),
        missing_required=tuple(_dedupe(missing_required)),
        missing_optional=tuple(_dedupe(missing_optional)),
    )


def _tool_name(tool: Any) -> str:
    return getattr(tool, "name", str(tool))


def _dedupe(names) -> list[str]:
    return list(dict.fromkeys(name for name in names if name))
