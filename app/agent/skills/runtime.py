"""Runtime representation and resource loading for active skills."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Collection, Mapping, Sequence

import yaml

from agent.config import AgentConfig
from agent.skills.broker import resolve_skill_tool_access
from agent.skills.manifest_schema import validate_skill_manifest
from agent.skills.metadata import SkillMetadata, discover_skills, load_skill_file
from agent.tool_access import ToolAccessResolution, resolve_tool_access
from agent.tools import inventory as tool_inventory


_NONE = "(none)"


@dataclass(frozen=True)
class SkillRuntime:
    """Loaded runtime context for one active skill."""

    name: str
    root: Path
    instructions: str
    manifest: Mapping[str, Any]
    pinned_references: dict[str, str]
    tool_access: ToolAccessResolution
    task_mode: str | None = None

    def read_skill_resource(self, rel_path: str) -> str:
        """Read a resource path relative to this skill root."""
        path = (self.root / rel_path).expanduser().resolve()
        root = self.root.resolve()
        if not path.is_relative_to(root):
            raise PermissionError(f"skill resource escapes skill root: {rel_path}")
        if not path.exists():
            raise FileNotFoundError(f"skill resource does not exist: {rel_path}")
        if not path.is_file():
            raise IsADirectoryError(f"skill resource is not a regular file: {rel_path}")
        return path.read_text(encoding="utf-8", errors="replace")

    def context_block(self) -> str:
        """Render prompt-visible context for the active skill."""
        lines = [
            "[Active skill]",
            f"name: {self.name}",
        ]
        if self.task_mode:
            lines.append(f"task_mode: {self.task_mode}")
        lines.extend([
            "",
            "[SKILL.md]",
            self.instructions,
        ])
        if self.pinned_references:
            lines.append("")
            lines.append("[Pinned skill references]")
            for path, content in self.pinned_references.items():
                lines.extend([
                    f"--- {path} ---",
                    content,
                ])
        return "\n".join(lines)


def render_tool_availability_block(
    *,
    resolution: ToolAccessResolution | None = None,
    active_skill: str | None = None,
    task_mode: str | None = None,
    all_tool_names: Sequence[str] | None = None,
    mcp_families: Mapping[str, str] | None = None,
    global_mcp_families: Collection[str] | None = None,
) -> str:
    """Render prompt-visible tool availability from a shared resolution.

    The graph binds exactly ``resolution.effective_tools``; this helper renders
    the same resolution for prompts so rewriter, writer, and reviewer never
    carry their own stale tool lists. ``all_tool_names`` is the full tool
    universe; names outside ``effective_tools`` are listed as unavailable.

    ``resolution=None`` falls back to the normal-mode resolution over the
    shared base tool inventory, so a caller that omits everything still
    renders the real global tools.
    """
    if resolution is None:
        resolution = resolve_tool_access(
            None,
            all_tool_names
            if all_tool_names is not None
            else tool_inventory.base_tool_names(),
            mcp_families=mcp_families or {},
            global_mcp_families=global_mcp_families,
        )
    effective = _dedupe_strings(resolution.effective_tools)
    skill_tools = _dedupe_strings(resolution.skill_tools)
    unavailable = [
        name
        for name in _dedupe_strings(all_tool_names or ())
        if name not in set(effective)
    ]

    lines = [
        "[Tool availability]",
        f"active_skill: {active_skill or _NONE}",
        f"task_mode: {task_mode or _NONE}",
        f"available_tools: {_format_tool_names(effective, mcp_families)}",
        f"skill_tools: {_format_tool_names(skill_tools, mcp_families)}",
        f"unavailable_tools: {_format_tool_names(unavailable, mcp_families)}",
    ]
    if active_skill:
        lines.append(
            "note: Global tools stay available; skill_tools are added by the "
            "active skill."
        )
    else:
        lines.append("note: No active skill; only global tools are bound.")
    return "\n".join(lines)


def _dedupe_strings(items: Sequence[str]) -> list[str]:
    return [item for item in dict.fromkeys(items) if isinstance(item, str) and item]


def _format_tool_names(
    names: Sequence[str],
    mcp_families: Mapping[str, str] | None,
) -> str:
    rendered = _tool_names_with_families(names, mcp_families)
    return ", ".join(rendered) if rendered else _NONE


def _tool_names_with_families(
    names: Sequence[str],
    mcp_families: Mapping[str, str] | None,
) -> list[str]:
    if not mcp_families:
        return list(names)

    rendered: list[str] = []
    seen_families: set[str] = set()
    for name in names:
        family = mcp_families.get(name)
        if family:
            if family in seen_families:
                continue
            rendered.append(f"MCP family: {family}")
            seen_families.add(family)
        else:
            rendered.append(name)
    return rendered


def load_skill_runtime(
    name: str,
    *,
    config: AgentConfig,
    all_tools: Sequence[Any],
    mcp_families: Mapping[str, str] | None = None,
    global_mcp_families: Collection[str] | None = None,
    task_mode: str | None = None,
    catalog: Sequence[SkillMetadata] | None = None,
) -> SkillRuntime:
    """Load a skill and resolve its runtime tool access."""
    metadata = find_skill_metadata(name, config=config, catalog=catalog)
    if metadata is None:
        raise KeyError(f"unknown skill: {name}")

    root = metadata.path.parent.resolve()
    manifest = load_skill_manifest(root)
    _validate_task_mode(task_mode, manifest)

    _frontmatter, instructions = load_skill_file(metadata.path)
    tool_access = resolve_skill_tool_access(
        manifest,
        all_tools,
        mcp_families=mcp_families or {},
        global_mcp_families=global_mcp_families,
    )
    runtime = SkillRuntime(
        name=metadata.name,
        root=root,
        instructions=instructions,
        manifest=manifest,
        pinned_references={},
        tool_access=tool_access,
        task_mode=task_mode,
    )
    pinned_references = _load_pinned_references(runtime, manifest, config)
    _validate_total_skill_context(
        instructions=runtime.instructions,
        pinned_references=pinned_references,
        config=config,
    )
    return SkillRuntime(
        name=runtime.name,
        root=runtime.root,
        instructions=runtime.instructions,
        manifest=runtime.manifest,
        pinned_references=pinned_references,
        tool_access=runtime.tool_access,
        task_mode=runtime.task_mode,
    )


def find_skill_metadata(
    name: str,
    *,
    config: AgentConfig,
    catalog: Sequence[SkillMetadata] | None = None,
) -> SkillMetadata | None:
    """Find a discovered skill by name."""
    normalized = name.casefold()
    skills = discover_skills(config) if catalog is None else catalog
    for skill in skills:
        if skill.name.casefold() == normalized:
            return skill
    return None


def load_skill_manifest(root: Path) -> dict[str, Any]:
    """Load a skill manifest, if present."""
    manifest_path = root / "manifest.yaml"
    if not manifest_path.exists():
        return {}
    with manifest_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"skill manifest must be a mapping: {manifest_path}")
    return validate_skill_manifest(data, source=manifest_path)


def _load_pinned_references(
    runtime: SkillRuntime,
    manifest: Mapping[str, Any],
    config: AgentConfig,
) -> dict[str, str]:
    resources = manifest.get("resources")
    if not isinstance(resources, list):
        return {}

    loaded: dict[str, str] = {}
    for item in resources:
        if not isinstance(item, Mapping):
            continue
        if item.get("pinned") is not True:
            continue
        path = item.get("path")
        if not isinstance(path, str):
            continue
        content = runtime.read_skill_resource(path)
        _validate_pinned_reference_size(path, content, config)
        loaded[path] = content
    return loaded


def _validate_pinned_reference_size(
    path: str,
    content: str,
    config: AgentConfig,
) -> None:
    limit = config.skill_max_pinned_reference_chars
    size = len(content)
    if size > limit:
        raise ValueError(
            f"pinned skill reference too large: {path} "
            f"({size} chars, limit {limit})"
        )


def _validate_total_skill_context(
    *,
    instructions: str,
    pinned_references: Mapping[str, str],
    config: AgentConfig,
) -> None:
    limit = config.skill_max_total_skill_context_chars
    size = len(instructions) + sum(len(content) for content in pinned_references.values())
    if size > limit:
        raise ValueError(
            f"total skill context too large: {size} chars (limit {limit})"
        )


def _validate_task_mode(task_mode: str | None, manifest: Mapping[str, Any]) -> None:
    if task_mode is None:
        return
    modes = manifest.get("task_modes")
    if not isinstance(modes, list):
        return
    valid_modes = {mode for mode in modes if isinstance(mode, str)}
    if valid_modes and task_mode not in valid_modes:
        valid = ", ".join(sorted(valid_modes))
        raise ValueError(f"unknown task mode for skill: {task_mode} (available: {valid})")
