"""Restart-activation tests for applied Skill bundles."""

from pathlib import Path

from agent.config import AgentConfig
from agent.extensions.discovery import scan_extensions
from agent.extensions.models import ExtensionRegistry
from agent.extensions.registry import install_scanned_extension, write_registry
from agent.extensions.startup import load_extension_startup
from agent.skills import SkillMetadata
from agent.skills.runtime import load_skill_runtime


class _Tool:
    name = "read_file"


def _config(tmp_path: Path) -> AgentConfig:
    return AgentConfig(
        extension_dropin_dir=str(tmp_path / "dropins"),
        extension_state_dir=str(tmp_path / "state"),
    )


def _write_skill(root: Path, name: str, description: str = "Drop-in") -> Path:
    bundle = root / "skill" / name
    bundle.mkdir(parents=True)
    (bundle / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        "---\n\n"
        "Use the drop-in instructions.\n",
        encoding="utf-8",
    )
    (bundle / "manifest.yaml").write_text(
        "tools:\n"
        "  optional:\n"
        "    local: [read_file]\n",
        encoding="utf-8",
    )
    return bundle


def _apply_skill(config: AgentConfig, name: str) -> ExtensionRegistry:
    root = Path(config.extension_dropin_dir)
    item = scan_extensions(root, config=config).items[f"skill:{name}"]
    entry = install_scanned_extension(
        item,
        state_root=Path(config.extension_state_dir),
        config=config,
    )
    registry = ExtensionRegistry(
        revision=1,
        source_root=str(root.resolve()),
        extensions={f"skill:{name}": entry},
    )
    write_registry(Path(config.extension_state_dir), registry)
    return registry


def test_startup_loads_verified_applied_skill(tmp_path):
    config = _config(tmp_path)
    _write_skill(Path(config.extension_dropin_dir), "writer")
    _apply_skill(config, "writer")

    startup = load_extension_startup(config)

    assert startup.revision == 1
    assert [skill.name for skill in startup.skills] == ["writer"]
    assert startup.diagnostics == ()


def test_runtime_loads_from_startup_catalog_not_raw_dropin(tmp_path):
    config = _config(tmp_path)
    raw = _write_skill(Path(config.extension_dropin_dir), "writer")
    registry = _apply_skill(config, "writer")
    startup = load_extension_startup(config)
    (raw / "SKILL.md").write_text(
        "---\nname: writer\ndescription: Raw changed\n---\n\nUNAPPLIED\n",
        encoding="utf-8",
    )

    runtime = load_skill_runtime(
        "writer",
        config=config,
        all_tools=[_Tool()],
        catalog=startup.skills,
    )

    assert "Use the drop-in instructions." in runtime.instructions
    assert "UNAPPLIED" not in runtime.instructions
    assert runtime.root == (
        Path(config.extension_state_dir)
        / registry.extensions["skill:writer"].installed_relpath
    ).resolve()


def test_startup_skips_tampered_installed_skill(tmp_path):
    config = _config(tmp_path)
    _write_skill(Path(config.extension_dropin_dir), "writer")
    registry = _apply_skill(config, "writer")
    installed = (
        Path(config.extension_state_dir)
        / registry.extensions["skill:writer"].installed_relpath
        / "SKILL.md"
    )
    installed.write_text("tampered", encoding="utf-8")

    startup = load_extension_startup(config)

    assert startup.revision == 1
    assert startup.skills == ()
    assert "applied_but_unavailable" in startup.diagnostics[0]


def test_startup_refuses_dropin_that_collides_with_builtin(tmp_path):
    config = _config(tmp_path)
    _write_skill(Path(config.extension_dropin_dir), "citation")
    _apply_skill(config, "citation")
    builtin = SkillMetadata(
        name="citation",
        description="Built in",
        path=tmp_path / "builtin" / "SKILL.md",
    )

    startup = load_extension_startup(config, builtin_skills=[builtin])

    assert startup.skills == ()
    assert "cannot replace a built-in Skill" in startup.diagnostics[0]


def test_invalid_registry_falls_back_to_builtins_only(tmp_path):
    config = _config(tmp_path)
    state = Path(config.extension_state_dir)
    state.mkdir(parents=True)
    (state / "registry.json").write_text("{broken", encoding="utf-8")

    startup = load_extension_startup(config)

    assert startup.revision == 0
    assert startup.skills == ()
    assert "extension registry unavailable" in startup.diagnostics[0]
