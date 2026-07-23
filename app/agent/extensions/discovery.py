"""Strict, side-effect-free discovery of Skill and MCP drop-in bundles."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from agent.config import AgentConfig
from agent.extensions.models import (
    ExtensionChange,
    ExtensionDiff,
    ExtensionRegistry,
    ScanResult,
    ScannedExtension,
)
from agent.skills.manifest_schema import validate_skill_manifest

_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
_RESERVED_IDS = frozenset({"extension-management"})


def _frontmatter(text: str, source: Path) -> dict[str, Any]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{source}: SKILL.md requires YAML frontmatter")
    end = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"),
        None,
    )
    if end is None:
        raise ValueError(f"{source}: unterminated YAML frontmatter")
    data = yaml.safe_load("\n".join(lines[1:end]))
    if not isinstance(data, dict):
        raise ValueError(f"{source}: frontmatter must be a mapping")
    return data


def _validate_skill(bundle: Path, extension_id: str) -> dict[str, Any]:
    skill_file = bundle / "SKILL.md"
    if not skill_file.is_file() or skill_file.is_symlink():
        raise ValueError("SKILL.md is missing or is not a regular file")
    text = skill_file.read_text(encoding="utf-8")
    metadata = _frontmatter(text, skill_file)
    name = metadata.get("name")
    description = metadata.get("description")
    if name != extension_id:
        raise ValueError("SKILL.md frontmatter name must equal folder ID")
    if not isinstance(description, str) or not description.strip():
        raise ValueError("SKILL.md frontmatter description must be non-empty")

    manifest_path = bundle / "manifest.yaml"
    if not manifest_path.exists():
        return {}
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError("manifest.yaml is not a regular file")
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("manifest.yaml must be a mapping")
    manifest = validate_skill_manifest(raw, source=manifest_path)
    for resource in manifest.get("resources", []):
        rel_path = resource["path"]
        target = (bundle / rel_path).resolve()
        if not target.is_relative_to(bundle.resolve()):
            raise ValueError(f"resource escapes bundle: {rel_path}")
        if not target.is_file() or target.is_symlink():
            raise ValueError(f"resource is missing or not regular: {rel_path}")
    return manifest


def _bundle_fingerprint(
    bundle: Path,
    *,
    config: AgentConfig,
) -> tuple[str, tuple[str, ...]]:
    if bundle.is_symlink() or not bundle.is_dir():
        raise ValueError("bundle must be a regular directory")
    digest = hashlib.sha256()
    files: list[str] = []
    total_bytes = 0
    try:
        paths = sorted(bundle.rglob("*"), key=lambda path: path.as_posix())
    except OSError as exc:
        raise ValueError(f"bundle cannot be enumerated: {exc}") from exc

    for path in paths:
        rel = path.relative_to(bundle).as_posix()
        try:
            mode = path.lstat().st_mode
        except OSError as exc:
            raise ValueError(f"cannot stat {rel}: {exc}") from exc
        if stat.S_ISLNK(mode):
            raise ValueError(f"symlink is not allowed: {rel}")
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError(f"special file is not allowed: {rel}")
        size = path.stat().st_size
        if size > config.extension_max_file_bytes:
            raise ValueError(f"file exceeds size limit: {rel}")
        files.append(rel)
        if len(files) > config.extension_max_files:
            raise ValueError("bundle exceeds file-count limit")
        total_bytes += size
        if total_bytes > config.extension_max_bundle_bytes:
            raise ValueError("bundle exceeds total-size limit")
        content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        record = {
            "path": rel,
            "size": size,
            "executable": bool(mode & 0o111),
            "sha256": content_hash,
        }
        digest.update(
            json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        digest.update(b"\n")
    if not files:
        raise ValueError("bundle contains no files")
    return digest.hexdigest(), tuple(files)


def inspect_bundle(
    kind: str,
    extension_id: str,
    bundle: Path,
    *,
    config: AgentConfig,
) -> ScannedExtension:
    """Inspect one bundle and return a valid or blocked scan item."""
    errors: list[str] = []
    source_hash: str | None = None
    relative_files: tuple[str, ...] = ()
    skill_manifest: dict[str, Any] | None = None
    if not _ID_RE.fullmatch(extension_id) or extension_id in _RESERVED_IDS:
        errors.append("invalid or reserved extension ID")
    try:
        source_hash, relative_files = _bundle_fingerprint(bundle, config=config)
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
    if kind == "skill" and not errors:
        try:
            skill_manifest = _validate_skill(bundle, extension_id)
        except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
            errors.append(str(exc))
    return ScannedExtension(
        kind=kind,  # type: ignore[arg-type]
        id=extension_id,
        source_path=bundle.resolve(),
        source_hash=source_hash,
        relative_files=relative_files,
        skill_manifest=skill_manifest,
        valid=not errors,
        errors=tuple(errors),
    )


def scan_extensions(root: Path, *, config: AgentConfig) -> ScanResult:
    """Scan direct children of skill/ and mcp/ without executing content."""
    root = root.expanduser().resolve()
    diagnostics: list[str] = []
    items: dict[str, ScannedExtension] = {}
    if not root.exists():
        return ScanResult(
            root=root,
            items={},
            complete_for_delete=False,
            diagnostics=("drop-in root does not exist",),
        )
    if not root.is_dir():
        return ScanResult(
            root=root,
            items={},
            complete_for_delete=False,
            diagnostics=("drop-in root is not a directory",),
        )

    complete = True
    observed_ids: dict[str, list[str]] = defaultdict(list)
    for kind in ("skill", "mcp"):
        kind_root = root / kind
        if not kind_root.exists():
            continue
        if kind_root.is_symlink() or not kind_root.is_dir():
            diagnostics.append(f"{kind}/ is not a regular directory")
            complete = False
            continue
        try:
            children = sorted(kind_root.iterdir(), key=lambda path: path.name.casefold())
        except OSError as exc:
            diagnostics.append(f"cannot enumerate {kind}/: {exc}")
            complete = False
            continue
        for bundle in children:
            if bundle.name.startswith("."):
                continue
            item = inspect_bundle(kind, bundle.name, bundle, config=config)
            items[item.key] = item
            observed_ids[item.id.casefold()].append(item.key)

    for keys in observed_ids.values():
        if len(keys) < 2:
            continue
        for key in keys:
            item = items[key]
            items[key] = ScannedExtension(
                kind=item.kind,
                id=item.id,
                source_path=item.source_path,
                source_hash=item.source_hash,
                relative_files=item.relative_files,
                skill_manifest=item.skill_manifest,
                valid=False,
                errors=(*item.errors, "extension ID collides across kinds"),
            )

    local_root = root / "local"
    if local_root.exists():
        try:
            unsupported = [
                path.name
                for path in local_root.iterdir()
                if path.name != "README.md"
            ]
        except OSError as exc:
            diagnostics.append(f"cannot enumerate local/: {exc}")
            complete = False
        else:
            if unsupported:
                diagnostics.append("local/ extensions are unsupported in v1")
    return ScanResult(
        root=root,
        items=dict(sorted(items.items())),
        complete_for_delete=complete,
        diagnostics=tuple(diagnostics),
    )


def build_diff(scan: ScanResult, registry: ExtensionRegistry) -> ExtensionDiff:
    """Build the deterministic desired-versus-applied change set."""
    root_matches = (
        registry.source_root is None
        or Path(registry.source_root).resolve() == scan.root.resolve()
    )
    delete_enabled = scan.complete_for_delete and root_matches
    diagnostics = list(scan.diagnostics)
    if not root_matches:
        diagnostics.append("configured drop-in root differs from applied registry")

    changes: list[ExtensionChange] = []
    for key, desired in scan.items.items():
        applied = registry.extensions.get(key)
        if not desired.valid:
            changes.append(
                ExtensionChange(
                    operation="blocked",
                    key=key,
                    desired=desired,
                    applied=applied,
                    reason="; ".join(desired.errors),
                )
            )
        elif applied is None:
            changes.append(
                ExtensionChange(operation="add", key=key, desired=desired)
            )
        elif applied.source_hash != desired.source_hash:
            changes.append(
                ExtensionChange(
                    operation="update",
                    key=key,
                    desired=desired,
                    applied=applied,
                )
            )
        else:
            changes.append(
                ExtensionChange(
                    operation="unchanged",
                    key=key,
                    desired=desired,
                    applied=applied,
                )
            )

    for key, applied in sorted(registry.extensions.items()):
        if key in scan.items:
            continue
        changes.append(
            ExtensionChange(
                operation="delete" if delete_enabled else "guarded",
                key=key,
                applied=applied,
                reason=None if delete_enabled else "delete disabled by incomplete or rebound root",
            )
        )
    return ExtensionDiff(
        changes=tuple(changes),
        delete_enabled=delete_enabled,
        diagnostics=tuple(diagnostics),
    )
