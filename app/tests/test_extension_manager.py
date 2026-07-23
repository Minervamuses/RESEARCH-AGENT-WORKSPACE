"""Tests for the private planner and host-owned apply path."""

import asyncio
import json
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from agent.cli.slash_commands import (
    SlashCommandContext,
    build_default_registry,
    execute_slash_command,
    parse_slash_command,
)
from agent.config import AgentConfig
from agent.extensions.manager import (
    ExtensionManager,
    ManagementError,
    load_private_skill,
)
from agent.extensions.registry import load_registry


class _PlanModel:
    def __init__(self, items):
        self.items = items
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return AIMessage(content=json.dumps({"items": self.items}))


class _Session:
    def __init__(self, config, manager):
        self.config = config
        self.extension_manager = manager
        self.running_extension_revision = 0
        self.turn_calls = []

    async def turn(self, text):
        self.turn_calls.append(text)
        return "unexpected"


def _config(tmp_path: Path) -> AgentConfig:
    return AgentConfig(
        extension_dropin_dir=str(tmp_path / "dropins"),
        extension_state_dir=str(tmp_path / "state"),
    )


def _write_private(tmp_path: Path, *, suffix: str = "") -> Path:
    bundle = tmp_path / "private"
    bundle.mkdir(exist_ok=True)
    path = bundle / "SKILL.md"
    path.write_text(
        "---\n"
        "name: extension-management\n"
        "description: Private manager\n"
        "---\n\n"
        f"Plan all changes. {suffix}\n",
        encoding="utf-8",
    )
    return path


def _write_skill(config: AgentConfig, description: str = "Example") -> Path:
    root = Path(config.extension_dropin_dir)
    bundle = root / "skill" / "writer"
    bundle.mkdir(parents=True)
    (bundle / "SKILL.md").write_text(
        "---\n"
        "name: writer\n"
        f"description: {description}\n"
        "---\n\n"
        "Write clearly.\n",
        encoding="utf-8",
    )
    return bundle


def _plan_item(operation: str = "add", decision: str = "apply") -> dict:
    return {
        "key": "skill:writer",
        "operation": operation,
        "decision": decision,
        "summary": f"{operation} writer",
        "reason": None,
        "mcp_descriptor": None,
    }


def _manager(config, private_path, model):
    return ExtensionManager(
        config,
        private_skill_path=private_path,
        model_factory=lambda _config: model,
    )


def test_preview_fresh_loads_private_skill_and_writes_nothing(tmp_path):
    config = _config(tmp_path)
    _write_skill(config)
    private_path = _write_private(tmp_path)
    model = _PlanModel([_plan_item()])
    manager = _manager(config, private_path, model)

    preview = manager.preview()

    assert preview.plan.items[0].key == "skill:writer"
    assert preview.private_skill_hash == load_private_skill(private_path).sha256
    assert len(model.calls) == 1
    assert "Plan all changes" in model.calls[0][0].content
    assert not Path(config.extension_state_dir).exists()


def test_apply_installs_skill_updates_registry_and_leaves_raw_source(tmp_path):
    config = _config(tmp_path)
    bundle = _write_skill(config)
    original = (bundle / "SKILL.md").read_bytes()
    private_path = _write_private(tmp_path)
    manager = _manager(config, private_path, _PlanModel([_plan_item()]))

    report = manager.apply(manager.preview())
    registry = load_registry(Path(config.extension_state_dir))

    assert report.previous_revision == 0
    assert report.applied_revision == 1
    assert report.restart_required is True
    assert report.items[0].outcome == "added"
    assert "skill:writer" in registry.extensions
    assert (bundle / "SKILL.md").read_bytes() == original


def test_apply_rejects_stale_private_skill_without_registry_write(tmp_path):
    config = _config(tmp_path)
    _write_skill(config)
    private_path = _write_private(tmp_path)
    manager = _manager(config, private_path, _PlanModel([_plan_item()]))
    preview = manager.preview()
    _write_private(tmp_path, suffix="changed")

    with pytest.raises(ManagementError, match="private Skill changed"):
        manager.apply(preview)

    assert not (Path(config.extension_state_dir) / "registry.json").exists()


def test_manager_rejects_missing_or_changed_authoritative_item(tmp_path):
    config = _config(tmp_path)
    _write_skill(config)
    private_path = _write_private(tmp_path)
    missing = _manager(config, private_path, _PlanModel([]))

    with pytest.raises(ManagementError, match="coverage mismatch"):
        missing.preview()

    changed = _PlanModel([_plan_item(operation="delete")])
    with pytest.raises(ManagementError, match="changed authoritative"):
        _manager(config, private_path, changed).preview()


def test_status_never_constructs_model_and_reports_restart(tmp_path):
    config = _config(tmp_path)
    _write_skill(config)
    private_path = _write_private(tmp_path)
    manager = _manager(config, private_path, _PlanModel([_plan_item()]))
    manager.apply(manager.preview())
    no_model = ExtensionManager(
        config,
        private_skill_path=private_path,
        model_factory=lambda _config: (_ for _ in ()).throw(
            AssertionError("status must not construct a model")
        ),
    )

    status = no_model.status(running_revision=0)

    assert status.applied_count == 1
    assert status.applied_revision == 1
    assert status.restart_required is True
    assert status.manager_available is True


def test_delete_removes_only_applied_entry_and_not_dropin_root(tmp_path):
    config = _config(tmp_path)
    bundle = _write_skill(config)
    private_path = _write_private(tmp_path)
    add_manager = _manager(
        config,
        private_path,
        _PlanModel([_plan_item()]),
    )
    add_manager.apply(add_manager.preview())
    (bundle / "SKILL.md").unlink()
    bundle.rmdir()
    delete_manager = _manager(
        config,
        private_path,
        _PlanModel([_plan_item(operation="delete")]),
    )

    report = delete_manager.apply(delete_manager.preview())

    assert report.items[0].outcome == "removed"
    assert load_registry(Path(config.extension_state_dir)).extensions == {}
    assert Path(config.extension_dropin_dir).is_dir()


def test_preview_wraps_model_failure_as_management_error(tmp_path):
    config = _config(tmp_path)
    _write_skill(config)
    private_path = _write_private(tmp_path)

    class _BrokenModel:
        def invoke(self, _messages):
            raise RuntimeError("provider unavailable")

    manager = _manager(config, private_path, _BrokenModel())

    with pytest.raises(ManagementError, match="provider unavailable"):
        manager.preview()


def test_dry_run_slash_command_does_not_enter_chat_or_write_state(tmp_path):
    config = _config(tmp_path)
    _write_skill(config)
    private_path = _write_private(tmp_path)
    manager = _manager(config, private_path, _PlanModel([_plan_item()]))
    session = _Session(config, manager)
    registry = build_default_registry()

    result = asyncio.run(
        execute_slash_command(
            parse_slash_command("/Extension-Management --dry-run"),
            SlashCommandContext(session=session, registry=registry),
        )
    )

    assert "skill:writer: add -> apply" in result.message
    assert "dry-run: no changes written" in result.message
    assert session.turn_calls == []
    assert not Path(config.extension_state_dir).exists()


def test_apply_slash_command_confirms_and_reports_restart(
    monkeypatch, tmp_path
):
    config = _config(tmp_path)
    _write_skill(config)
    private_path = _write_private(tmp_path)
    manager = _manager(config, private_path, _PlanModel([_plan_item()]))
    session = _Session(config, manager)
    monkeypatch.setattr("builtins.input", lambda _prompt: "yes")

    result = asyncio.run(
        execute_slash_command(
            parse_slash_command("/extension-management"),
            SlashCommandContext(
                session=session,
                registry=build_default_registry(),
            ),
        )
    )

    assert "revision 0 -> 1" in result.message
    assert "restart_required: true" in result.message
    assert session.turn_calls == []
