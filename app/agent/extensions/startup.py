"""Load host-validated extension state before normal session construction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from agent.config import AgentConfig
from agent.extensions.discovery import inspect_bundle
from agent.extensions.models import AppliedExtension, ExtensionRegistry
from agent.extensions.paths import ExtensionPaths, resolve_extension_paths
from agent.extensions.registry import RegistryError, load_registry
from agent.skills.metadata import SkillMetadata, read_skill_metadata


@dataclass(frozen=True)
class ExtensionStartup:
    """Verified extension inputs for one immutable session startup."""

    revision: int
    skills: tuple[SkillMetadata, ...]
    diagnostics: tuple[str, ...]


def _installed_bundle_path(
    paths: ExtensionPaths,
    entry: AppliedExtension,
) -> Path:
    raw = Path(entry.installed_relpath)
    if raw.is_absolute():
        raise ValueError("installed path must be relative")
    resolved = (paths.state_root / raw).resolve()
    installed_root = (paths.state_root / "installed").resolve()
    if not resolved.is_relative_to(installed_root):
        raise ValueError("installed path escapes state root")
    expected = (
        installed_root
        / entry.kind
        / entry.id
        / entry.source_hash
    )
    if resolved != expected:
        raise ValueError("installed path does not match extension identity")
    return resolved


def _load_skill(
    entry: AppliedExtension,
    *,
    paths: ExtensionPaths,
    config: AgentConfig,
) -> SkillMetadata:
    bundle = _installed_bundle_path(paths, entry)
    scanned = inspect_bundle("skill", entry.id, bundle, config=config)
    if not scanned.valid:
        raise ValueError("; ".join(scanned.errors))
    if scanned.source_hash != entry.source_hash:
        raise ValueError("installed Skill hash differs from registry")
    return read_skill_metadata(bundle / "SKILL.md")


def load_extension_startup(
    config: AgentConfig,
    *,
    builtin_skills: Sequence[SkillMetadata] = (),
) -> ExtensionStartup:
    """Verify applied Skills and return only entries safe to load this run."""
    diagnostics: list[str] = []
    try:
        paths = resolve_extension_paths(config)
        registry = load_registry(paths.state_root)
    except (OSError, RegistryError, ValueError) as exc:
        return ExtensionStartup(
            revision=0,
            skills=(),
            diagnostics=(f"extension registry unavailable: {exc}",),
        )

    builtin_names = {skill.name.casefold() for skill in builtin_skills}
    loaded: list[SkillMetadata] = []
    loaded_names: set[str] = set()
    for key, entry in sorted(registry.extensions.items()):
        if key != f"{entry.kind}:{entry.id}":
            diagnostics.append(f"{key}: registry key does not match entry")
            continue
        if entry.kind != "skill":
            continue
        normalized = entry.id.casefold()
        if normalized in builtin_names:
            diagnostics.append(f"{key}: drop-in cannot replace a built-in Skill")
            continue
        if normalized in loaded_names:
            diagnostics.append(f"{key}: duplicate applied Skill name")
            continue
        try:
            metadata = _load_skill(entry, paths=paths, config=config)
        except (OSError, UnicodeError, ValueError) as exc:
            diagnostics.append(f"{key}: applied_but_unavailable: {exc}")
            continue
        loaded.append(metadata)
        loaded_names.add(normalized)
    return ExtensionStartup(
        revision=registry.revision,
        skills=tuple(loaded),
        diagnostics=tuple(diagnostics),
    )
