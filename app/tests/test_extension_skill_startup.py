"""Restart-activation tests for applied Skill bundles."""

from pathlib import Path
import traceback

import pytest

from agent.config import AgentConfig
from agent.extensions.discovery import scan_extensions
from agent.extensions.models import ExtensionRegistry
from agent.extensions.models import AppliedExtension
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


def _add_pinned_reference(bundle: Path) -> None:
    (bundle / "reference.md").write_text("Approved reference A\n", encoding="utf-8")
    with (bundle / "manifest.yaml").open("a", encoding="utf-8") as handle:
        handle.write("resources:\n  - path: reference.md\n    pinned: true\n")


@pytest.mark.parametrize("changed_file", ["SKILL.md", "manifest.yaml", "reference.md"])
def test_runtime_rejects_applied_bundle_changed_after_startup(tmp_path, changed_file):
    config = _config(tmp_path)
    raw = _write_skill(Path(config.extension_dropin_dir), "writer")
    _add_pinned_reference(raw)
    _apply_skill(config, "writer")
    startup = load_extension_startup(config)
    assert startup.diagnostics == ()
    installed = startup.skills[0].path.parent
    path = installed / changed_file
    if changed_file == "manifest.yaml":
        path.write_text("tools:\n  optional:\n    local: [bash]\n", encoding="utf-8")
    else:
        with path.open("a", encoding="utf-8") as handle:
            handle.write("UNAPPROVED_CONTENT\n")

    with pytest.raises(ValueError, match="applied bundle changed; restart or re-apply required"):
        load_skill_runtime("writer", config=config, all_tools=[_Tool()], catalog=startup.skills)
    restarted = load_extension_startup(config)
    assert restarted.skills == ()
    assert "applied_but_unavailable" in restarted.diagnostics[0]


def test_startup_loads_verified_applied_skill(tmp_path):
    config = _config(tmp_path)
    _write_skill(Path(config.extension_dropin_dir), "writer")
    registry = _apply_skill(config, "writer")

    startup = load_extension_startup(config)

    assert startup.revision == 1
    assert [skill.name for skill in startup.skills] == ["writer"]
    assert startup.diagnostics == ()
    assert startup.skills[0].applied_source_hash == registry.extensions["skill:writer"].source_hash


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


def test_startup_reports_legacy_task_modes_manifest_as_unavailable(tmp_path):
    config = _config(tmp_path)
    state = Path(config.extension_state_dir)
    source_hash = "legacy-task-modes"
    bundle = state / "installed" / "skill" / "writer" / source_hash
    bundle.mkdir(parents=True)
    (bundle / "SKILL.md").write_text(
        "---\nname: writer\ndescription: Legacy writer\n---\n",
        encoding="utf-8",
    )
    (bundle / "manifest.yaml").write_text(
        "task_modes:\n  - revision\n",
        encoding="utf-8",
    )
    write_registry(
        state,
        ExtensionRegistry(
            revision=1,
            source_root=str(Path(config.extension_dropin_dir).resolve()),
            extensions={
                "skill:writer": AppliedExtension(
                    kind="skill",
                    id="writer",
                    source_hash=source_hash,
                    installed_relpath=bundle.relative_to(state).as_posix(),
                    skill_manifest={"task_modes": ["revision"]},
                )
            },
        ),
    )

    startup = load_extension_startup(config)

    assert startup.skills == ()
    assert len(startup.diagnostics) == 1
    assert "applied_but_unavailable" in startup.diagnostics[0]
    assert "task_modes" in startup.diagnostics[0]


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


@pytest.mark.parametrize("damage", [
    "missing_skill", "missing_manifest", "missing_reference", "invalid_yaml",
    "root_symlink", "file_symlink", "file_limit", "executable_bit", "unreadable",
])
def test_applied_activation_failure_is_safe(tmp_path, caplog, damage):
    config = _config(tmp_path)
    config.extension_max_file_bytes = 1024
    raw = _write_skill(Path(config.extension_dropin_dir), "writer")
    _add_pinned_reference(raw)
    _apply_skill(config, "writer")
    startup = load_extension_startup(config)
    assert startup.diagnostics == ()
    installed = startup.skills[0].path.parent
    registry_path = Path(config.extension_state_dir) / "registry.json"
    registry_before = registry_path.read_bytes()
    raw_before = {path.name: path.read_bytes() for path in raw.iterdir()}
    marker = "PRIVATE_ACTIVATION_TEST_CONTENT"
    if damage.startswith("missing_"):
        filename = {
            "missing_skill": "SKILL.md",
            "missing_manifest": "manifest.yaml",
            "missing_reference": "reference.md",
        }[damage]
        (installed / filename).unlink()
    elif damage == "invalid_yaml":
        (installed / "manifest.yaml").write_text(f"resources: [{marker}\n", encoding="utf-8")
    elif damage == "root_symlink":
        moved = tmp_path / "moved-bundle"
        installed.rename(moved)
        installed.symlink_to(moved, target_is_directory=True)
    elif damage == "file_symlink":
        path = installed / "reference.md"
        moved = tmp_path / "moved-reference.md"
        path.rename(moved)
        path.symlink_to(moved)
    elif damage == "file_limit":
        (installed / "reference.md").write_text(marker * 100, encoding="utf-8")
    elif damage == "executable_bit":
        path = installed / "reference.md"
        path.chmod(path.stat().st_mode ^ 0o100)
    else:
        (installed / "reference.md").chmod(0)

    with pytest.raises(ValueError) as caught:
        load_skill_runtime("writer", config=config, all_tools=[_Tool()], catalog=startup.skills)

    assert str(caught.value) == "applied bundle changed; restart or re-apply required"
    assert marker not in "".join(traceback.format_exception(caught.value))
    assert marker not in caplog.text
    assert registry_path.read_bytes() == registry_before
    assert {path.name: path.read_bytes() for path in raw.iterdir()} == raw_before


def test_applied_revision_stays_pinned_until_restart(tmp_path):
    from agent.extensions.manager import ExtensionManager
    from test_extension_user_journey import _DeterministicManagementModel

    config = _config(tmp_path)
    raw = _write_skill(Path(config.extension_dropin_dir), "writer")
    manifest = raw / "manifest.yaml"
    manifest.write_text(manifest.read_text().replace("read_file", "revision_a"), encoding="utf-8")
    _add_pinned_reference(raw)
    registry_a = _apply_skill(config, "writer")
    startup_a = load_extension_startup(config)

    def load(startup):
        return load_skill_runtime(
            "WRITER", config=config, catalog=startup.skills,
            all_tools=["read_file", "revision_a", "revision_b"],
        )

    runtime_a = load(startup_a)
    assert startup_a.revision == 1
    assert "Use the drop-in instructions." in runtime_a.instructions
    assert runtime_a.pinned_references == {"reference.md": "Approved reference A\n"}
    assert runtime_a.tool_access.skill_tools == ("revision_a",)
    assert runtime_a.root == (
        Path(config.extension_state_dir) / registry_a.extensions["skill:writer"].installed_relpath
    )

    skill_file = raw / "SKILL.md"
    skill_file.write_text(skill_file.read_text().replace("drop-in", "version B"), encoding="utf-8")
    manifest.write_text(manifest.read_text().replace("revision_a", "revision_b"), encoding="utf-8")
    (raw / "reference.md").write_text("Approved reference B\n", encoding="utf-8")
    assert load(startup_a) == runtime_a
    before_apply = load_extension_startup(config)
    assert before_apply == startup_a
    assert load(before_apply) == runtime_a

    manager = ExtensionManager(config, model_factory=lambda _cfg: _DeterministicManagementModel())
    report = manager.apply(manager.preview())
    assert report.applied_revision == 2
    assert load(startup_a) == runtime_a
    assert startup_a.revision == 1

    startup_b = load_extension_startup(config)
    runtime_b = load(startup_b)
    assert startup_b.diagnostics == ()
    assert startup_b.revision == 2
    assert startup_b.skills[0].applied_source_hash != startup_a.skills[0].applied_source_hash
    assert runtime_b.root != runtime_a.root
    assert "Use the version B instructions." in runtime_b.instructions
    assert runtime_b.pinned_references == {"reference.md": "Approved reference B\n"}
    assert runtime_b.tool_access.skill_tools == ("revision_b",)

    # A fresh registry must not rebind the old catalog's identity or expected hash.
    (runtime_a.root / "SKILL.md").write_text("damaged old A", encoding="utf-8")
    with pytest.raises(ValueError, match="applied bundle changed"):
        load(startup_a)
    assert load(load_extension_startup(config)) == runtime_b


def test_legacy_metadata_constructor_has_no_applied_identity(tmp_path):
    assert SkillMetadata("writer", "Local", tmp_path / "SKILL.md").applied_source_hash is None
