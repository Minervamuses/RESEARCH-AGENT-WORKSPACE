"""Tests for strict drop-in discovery and the single applied registry."""

import os
import stat
from pathlib import Path

import pytest

from agent.config import AgentConfig
from agent.extensions.discovery import build_diff, scan_extensions
from agent.extensions.models import AppliedExtension, ExtensionRegistry
from agent.extensions.paths import resolve_extension_paths
from agent.extensions.registry import (
    RegistryError,
    install_scanned_extension,
    load_registry,
    write_registry,
)


def _config(tmp_path: Path) -> AgentConfig:
    return AgentConfig(
        extension_dropin_dir=str(tmp_path / "dropins"),
        extension_state_dir=str(tmp_path / "state"),
    )


def _write_skill(root: Path, name: str, *, description: str = "Example") -> Path:
    bundle = root / "skill" / name
    bundle.mkdir(parents=True)
    (bundle / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\nInstructions.\n",
        encoding="utf-8",
    )
    return bundle


def _write_mcp(root: Path, name: str) -> Path:
    bundle = root / "mcp" / name
    bundle.mkdir(parents=True)
    (bundle / "server.py").write_text("print('ready')\n", encoding="utf-8")
    return bundle


def _applied(kind: str, name: str, source_hash: str = "a" * 64) -> AppliedExtension:
    return AppliedExtension(
        kind=kind,
        id=name,
        source_hash=source_hash,
        installed_relpath=f"installed/{kind}/{name}/{source_hash}",
    )


def test_resolve_extension_paths_prefers_explicit_config(tmp_path):
    config = _config(tmp_path)

    paths = resolve_extension_paths(config, env={})

    assert paths.dropin_root == (tmp_path / "dropins").resolve()
    assert paths.state_root == (tmp_path / "state").resolve()


def test_resolve_extension_paths_rejects_overlapping_roots(tmp_path):
    config = AgentConfig(
        extension_dropin_dir=str(tmp_path / "tool"),
        extension_state_dir=str(tmp_path / "tool" / "state"),
    )

    with pytest.raises(ValueError, match="must not overlap"):
        resolve_extension_paths(config, env={})


def test_scan_and_diff_cover_add_update_delete_and_unchanged(tmp_path):
    config = _config(tmp_path)
    root = Path(config.extension_dropin_dir)
    _write_skill(root, "writer")
    _write_mcp(root, "search")

    first = scan_extensions(root, config=config)
    first_diff = build_diff(first, ExtensionRegistry())

    assert first.complete_for_delete is True
    assert [(change.key, change.operation) for change in first_diff.changes] == [
        ("mcp:search", "add"),
        ("skill:writer", "add"),
    ]

    registry = ExtensionRegistry(
        revision=1,
        source_root=str(root.resolve()),
        extensions={
            key: _applied(item.kind, item.id, item.source_hash)
            for key, item in first.items.items()
        },
    )
    (root / "skill" / "writer" / "SKILL.md").write_text(
        "---\nname: writer\ndescription: Changed\n---\n\nNew.\n",
        encoding="utf-8",
    )
    for path in (root / "mcp" / "search").iterdir():
        path.unlink()
    (root / "mcp" / "search").rmdir()

    second = build_diff(scan_extensions(root, config=config), registry)

    assert [(change.key, change.operation) for change in second.changes] == [
        ("skill:writer", "update"),
        ("mcp:search", "delete"),
    ]


def test_invalid_update_is_blocked_and_keeps_applied_entry(tmp_path):
    config = _config(tmp_path)
    root = Path(config.extension_dropin_dir)
    _write_skill(root, "writer")
    first = scan_extensions(root, config=config)
    old = first.items["skill:writer"]
    registry = ExtensionRegistry(
        revision=1,
        source_root=str(root.resolve()),
        extensions={"skill:writer": _applied("skill", "writer", old.source_hash)},
    )
    (root / "skill" / "writer" / "SKILL.md").write_text(
        "---\nname: someone-else\ndescription: Invalid\n---\n",
        encoding="utf-8",
    )

    diff = build_diff(scan_extensions(root, config=config), registry)

    assert len(diff.changes) == 1
    change = diff.changes[0]
    assert change.operation == "blocked"
    assert change.applied == registry.extensions["skill:writer"]
    assert "name must equal folder ID" in change.reason


def test_missing_or_rebound_root_disables_delete(tmp_path):
    config = _config(tmp_path)
    missing = Path(config.extension_dropin_dir)
    registry = ExtensionRegistry(
        revision=1,
        source_root=str((tmp_path / "old-root").resolve()),
        extensions={"skill:writer": _applied("skill", "writer")},
    )

    result = scan_extensions(missing, config=config)
    diff = build_diff(result, registry)

    assert result.complete_for_delete is False
    assert diff.delete_enabled is False
    assert diff.changes[0].operation == "guarded"


def test_same_id_across_skill_and_mcp_is_blocked(tmp_path):
    config = _config(tmp_path)
    root = Path(config.extension_dropin_dir)
    _write_skill(root, "shared")
    _write_mcp(root, "shared")

    result = scan_extensions(root, config=config)

    assert result.items["skill:shared"].valid is False
    assert result.items["mcp:shared"].valid is False
    assert all(
        "collides across kinds" in item.errors[-1]
        for item in result.items.values()
    )


def test_symlink_in_bundle_is_rejected(tmp_path):
    config = _config(tmp_path)
    root = Path(config.extension_dropin_dir)
    bundle = _write_skill(root, "writer")
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    try:
        (bundle / "escape.txt").symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable on this platform")

    result = scan_extensions(root, config=config)

    assert result.items["skill:writer"].valid is False
    assert "symlink is not allowed" in result.items["skill:writer"].errors[0]


def test_install_copy_and_registry_round_trip(tmp_path):
    config = _config(tmp_path)
    root = Path(config.extension_dropin_dir)
    _write_skill(root, "writer")
    item = scan_extensions(root, config=config).items["skill:writer"]
    state_root = Path(config.extension_state_dir)

    installed = install_scanned_extension(
        item,
        state_root=state_root,
        config=config,
    )
    registry = ExtensionRegistry(
        revision=1,
        source_root=str(root.resolve()),
        extensions={"skill:writer": installed},
    )
    path = write_registry(state_root, registry)

    assert load_registry(state_root) == registry
    assert (state_root / installed.installed_relpath / "SKILL.md").is_file()
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_install_refuses_source_changed_after_scan(tmp_path):
    config = _config(tmp_path)
    root = Path(config.extension_dropin_dir)
    bundle = _write_skill(root, "writer")
    item = scan_extensions(root, config=config).items["skill:writer"]
    (bundle / "SKILL.md").write_text(
        "---\nname: writer\ndescription: Changed\n---\n",
        encoding="utf-8",
    )

    with pytest.raises(RegistryError, match="source_changed"):
        install_scanned_extension(
            item,
            state_root=Path(config.extension_state_dir),
            config=config,
        )
