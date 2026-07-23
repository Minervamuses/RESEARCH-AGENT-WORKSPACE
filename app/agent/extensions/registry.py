"""Single-file applied registry and immutable installed bundle copies."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

from pydantic import ValidationError

from agent.config import AgentConfig
from agent.extensions.discovery import inspect_bundle
from agent.extensions.models import (
    AppliedExtension,
    ExtensionRegistry,
    ScannedExtension,
)

REGISTRY_FILENAME = "registry.json"


class RegistryError(RuntimeError):
    """Applied registry or installed-copy validation failed."""


def load_registry(state_root: Path) -> ExtensionRegistry:
    """Read the applied registry, returning an empty state when absent."""
    path = state_root / REGISTRY_FILENAME
    if not path.exists():
        return ExtensionRegistry()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return ExtensionRegistry.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise RegistryError(f"invalid extension registry: {exc}") from exc


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_registry(state_root: Path, registry: ExtensionRegistry) -> Path:
    """Durably replace registry.json without exposing a partial document."""
    state_root.mkdir(parents=True, exist_ok=True)
    path = state_root / REGISTRY_FILENAME
    temp = state_root / f".registry-{uuid.uuid4().hex}.tmp"
    payload = (
        json.dumps(
            registry.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            offset = 0
            while offset < len(payload):
                offset += os.write(fd, payload[offset:])
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temp, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        _fsync_dir(state_root)
    except OSError as exc:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise RegistryError(f"could not write extension registry: {exc}") from exc
    return path


def _copy_bundle(source: ScannedExtension, staging: Path) -> None:
    staging.mkdir(parents=True, exist_ok=False)
    for rel in source.relative_files:
        src = source.source_path / rel
        dst = staging / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_symlink() or not src.is_file():
            raise RegistryError(f"source changed while copying: {rel}")
        shutil.copy2(src, dst, follow_symlinks=False)


def install_scanned_extension(
    item: ScannedExtension,
    *,
    state_root: Path,
    config: AgentConfig,
) -> AppliedExtension:
    """Copy one valid scan item into a content-addressed installed path."""
    if not item.valid or not item.source_hash:
        raise RegistryError("cannot install an invalid scanned extension")
    before = inspect_bundle(item.kind, item.id, item.source_path, config=config)
    if not before.valid or before.source_hash != item.source_hash:
        raise RegistryError("source_changed before copy")

    staging_root = state_root / "staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    staging = staging_root / uuid.uuid4().hex
    destination = (
        state_root
        / "installed"
        / item.kind
        / item.id
        / item.source_hash
    )
    try:
        _copy_bundle(item, staging)
        copied = inspect_bundle(item.kind, item.id, staging, config=config)
        if not copied.valid or copied.source_hash != item.source_hash:
            raise RegistryError("source_changed during copy")
        after = inspect_bundle(
            item.kind, item.id, item.source_path, config=config
        )
        if not after.valid or after.source_hash != item.source_hash:
            raise RegistryError("source_changed during copy")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            existing = inspect_bundle(
                item.kind, item.id, destination, config=config
            )
            if not existing.valid or existing.source_hash != item.source_hash:
                raise RegistryError("installed path conflicts with source hash")
            shutil.rmtree(staging)
        else:
            os.replace(staging, destination)
            _fsync_dir(destination.parent)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise

    return AppliedExtension(
        kind=item.kind,
        id=item.id,
        source_hash=item.source_hash,
        installed_relpath=destination.relative_to(state_root).as_posix(),
        skill_manifest=item.skill_manifest if item.kind == "skill" else None,
    )
