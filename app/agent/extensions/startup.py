"""Load host-validated extension state before normal session construction."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping, Sequence

from agent.config import AgentConfig
from agent.extensions.discovery import inspect_bundle
from agent.extensions.models import AppliedExtension, ExtensionRegistry
from agent.extensions.mcp_manifest import (
    MCPLaunchCandidate,
    MCPManifestError,
    resolve_mcp_candidate,
    validate_mcp_descriptor,
)
from agent.extensions.paths import ExtensionPaths, resolve_extension_paths
from agent.extensions.registry import RegistryError, load_registry
from agent.skills.metadata import SkillMetadata, read_skill_metadata
from agent.mcp import MCPServerSpec


@dataclass(frozen=True)
class ExtensionStartup:
    """Verified extension inputs for one immutable session startup."""

    revision: int
    skills: tuple[SkillMetadata, ...]
    mcp_specs: tuple[MCPServerSpec, ...]
    global_mcp_families: frozenset[str]
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


def _load_mcp(
    entry: AppliedExtension,
    *,
    paths: ExtensionPaths,
    config: AgentConfig,
    env: Mapping[str, str],
) -> MCPLaunchCandidate:
    if not entry.execution_approved:
        raise ValueError("MCP execution is not approved")
    if entry.mcp_descriptor is None or entry.command_binding_hash is None:
        raise ValueError("MCP approval binding is incomplete")
    bundle = _installed_bundle_path(paths, entry)
    scanned = inspect_bundle("mcp", entry.id, bundle, config=config)
    if not scanned.valid:
        raise ValueError("; ".join(scanned.errors))
    if scanned.source_hash != entry.source_hash:
        raise ValueError("installed MCP hash differs from registry")
    descriptor = validate_mcp_descriptor(
        entry.mcp_descriptor,
        extension_id=entry.id,
    )
    candidate = resolve_mcp_candidate(
        descriptor,
        bundle=bundle,
        source_hash=entry.source_hash,
        env=env,
    )
    if candidate.binding_hash != entry.command_binding_hash:
        raise ValueError("MCP command binding differs from approval")
    return candidate


def load_extension_startup(
    config: AgentConfig,
    *,
    builtin_skills: Sequence[SkillMetadata] = (),
    env: Mapping[str, str] | None = None,
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
            mcp_specs=(),
            global_mcp_families=frozenset(),
            diagnostics=(f"extension registry unavailable: {exc}",),
        )

    builtin_names = {skill.name.casefold() for skill in builtin_skills}
    loaded: list[SkillMetadata] = []
    loaded_names: set[str] = set()
    mcp_candidates: list[tuple[str, MCPLaunchCandidate]] = []
    runtime_env = dict(os.environ) if env is None else dict(env)
    for key, entry in sorted(registry.extensions.items()):
        if key != f"{entry.kind}:{entry.id}":
            diagnostics.append(f"{key}: registry key does not match entry")
            continue
        if entry.kind == "mcp":
            try:
                candidate = _load_mcp(
                    entry,
                    paths=paths,
                    config=config,
                    env=runtime_env,
                )
            except (OSError, MCPManifestError, ValueError) as exc:
                diagnostics.append(
                    f"{key}: applied_but_unavailable: {exc}"
                )
            else:
                mcp_candidates.append((key, candidate))
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
    family_owners: dict[str, list[str]] = {}
    for key, candidate in mcp_candidates:
        family_owners.setdefault(
            candidate.descriptor.family.casefold(), []
        ).append(key)
    collided = {
        key
        for owners in family_owners.values()
        if len(owners) > 1
        for key in owners
    }
    for family, owners in family_owners.items():
        if len(owners) > 1:
            diagnostics.append(
                f"MCP family collision {family}: {', '.join(owners)}"
            )
    usable_mcp = [
        candidate
        for key, candidate in mcp_candidates
        if key not in collided
    ]
    return ExtensionStartup(
        revision=registry.revision,
        skills=tuple(loaded),
        mcp_specs=tuple(
            candidate.to_server_spec() for candidate in usable_mcp
        ),
        global_mcp_families=frozenset(
            candidate.descriptor.family
            for candidate in usable_mcp
            if candidate.descriptor.scope == "global"
        ),
        diagnostics=tuple(diagnostics),
    )
