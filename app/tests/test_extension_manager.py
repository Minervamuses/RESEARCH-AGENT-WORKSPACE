"""Tests for the private planner and host-owned apply path."""

import asyncio
import errno
import fcntl
import json
import multiprocessing
import os
import signal
import zipfile
from contextlib import contextmanager
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from agent.cli.slash_commands import (
    SlashCommandContext,
    SlashCommandError,
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
from agent.extensions.discovery import scan_extensions
from agent.extensions.models import ExtensionRegistry
from agent.extensions.registry import (
    RegistryError,
    install_scanned_extension,
    load_registry,
    write_registry,
)
from agent.extensions import manager as manager_module
from agent.extensions import registry as registry_module


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


def _write_skill(
    config: AgentConfig, description: str = "Example", *, name: str = "writer"
) -> Path:
    root = Path(config.extension_dropin_dir)
    bundle = root / "skill" / name
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "SKILL.md").write_text(
        "---\n"
        f"name: {name}\n"
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


def _apply_process(root, name, connection, pause):
    """Run a real manager with a child-local fake planner and bounded IPC."""
    try:
        config = _config(root)
        item = dict(_plan_item(), key=f"skill:{name}")
        manager = _manager(config, root / "private/SKILL.md", _PlanModel([item]))
        preview = manager.preview(selected_skill_keys={item["key"]})
        connection.send((name, "ready", preview.registry.revision))
        with pytest.MonkeyPatch.context() as patch:
            if pause:
                module, attribute = {
                    "before_write": (manager_module, "write_registry"),
                    "before_read": (manager_module, "load_registry"),
                    "directory_fsync": (registry_module, "fsync_directory"),
                }[pause]
                original = getattr(module, attribute)

                def paused_call(*args, **kwargs):
                    if pause == "directory_fsync" and args[0] != preview.paths.state_root:
                        return original(*args, **kwargs)
                    connection.send((name, "paused", pause))
                    assert connection.poll(10), "apply release timed out"
                    assert connection.recv() == "release"
                    return original(*args, **kwargs)

                patch.setattr(module, attribute, paused_call)
            while True:
                assert connection.poll(10), "child command timed out"
                command = connection.recv()
                if command == "quit":
                    return
                if command == "probe":
                    with (preview.paths.state_root / ".apply.lock").open("rb") as handle:
                        try:
                            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        except BlockingIOError:
                            outcome = "locked"
                        else:
                            outcome = "available"
                    connection.send((name, "probe", outcome))
                    continue
                if command == "preview":
                    preview = manager.preview(selected_skill_keys={item["key"]})
                    connection.send((name, "ready", preview.registry.revision))
                    continue
                assert command == "apply"
                try:
                    report = manager.apply(preview)
                except ManagementError as exc:
                    connection.send((name, "error", str(exc)))
                else:
                    connection.send((name, "success", report.applied_revision))
    finally:
        connection.close()


@contextmanager
def _apply_processes(*specs, terminated=()):
    context = multiprocessing.get_context("spawn")
    children = []
    try:
        for root, name, pause in specs:
            parent, child = context.Pipe()
            process = context.Process(
                target=_apply_process, args=(root, name, child, pause)
            )
            process.start()
            child.close()
            children.append((process, parent))
        yield children
        for process, connection in children:
            if process.is_alive():
                connection.send("quit")
        for index, (process, _) in enumerate(children):
            process.join(10)
            assert process.exitcode == (-signal.SIGTERM if index in terminated else 0)
            print(f"child {process.pid}: exit={process.exitcode}")
    finally:
        for process, connection in children:
            if process.is_alive():
                process.terminate()
            process.join(10)
            assert not process.is_alive(), "test child did not exit"
            connection.close()
            process.close()


def _process_message(connection):
    assert connection.poll(10), "child response timed out"
    result = connection.recv()
    print(f"child outcome: {result}")
    return result


def test_cross_process_apply_preserves_successful_update(tmp_path):
    config = _config(tmp_path)
    _write_private(tmp_path)
    sources = {name: _write_skill(config, name=name) for name in ("alpha", "beta")}
    state = Path(config.extension_state_dir)
    scan = scan_extensions(Path(config.extension_dropin_dir), config=config)

    with _apply_processes(
        (tmp_path, "alpha", "before_write"), (tmp_path, "beta", None)
    ) as children:
        (_, a), (_, b) = children
        assert _process_message(a) == ("alpha", "ready", 0)
        assert _process_message(b) == ("beta", "ready", 0)
        assert not state.exists()
        a.send("apply")
        assert _process_message(a) == ("alpha", "paused", "before_write")
        b.send("apply")
        result_b = _process_message(b)
        a.send("release")
        result_a = _process_message(a)
        registry = load_registry(state)
        print(f"registry: revision={registry.revision}, keys={sorted(registry.extensions)}")

        assert sum(result[1] == "success" for result in (result_a, result_b)) == 1
        assert result_a == ("alpha", "success", 1)
        assert result_b == ("beta", "error", "another extension apply is already running")
        assert registry.revision == 1
        assert set(registry.extensions) == {"skill:alpha"}
        installed = registry.extensions["skill:alpha"]
        assert installed.source_hash == scan.items["skill:alpha"].source_hash
        assert (state / installed.installed_relpath / "SKILL.md").read_bytes() == (
            sources["alpha"] / "SKILL.md"
        ).read_bytes()
        assert not (state / "installed/skill/beta").exists()

        b.send("apply")
        assert _process_message(b) == (
            "beta", "error", "extension registry changed; run preview again"
        )
        assert not (state / "installed/skill/beta").exists()
        b.send("preview")
        assert _process_message(b) == ("beta", "ready", 1)
        b.send("apply")
        assert _process_message(b) == ("beta", "success", 2)
        registry = load_registry(state)
        assert registry.revision == 2
        assert set(registry.extensions) == {"skill:alpha", "skill:beta"}
        for name, source in sources.items():
            installed = registry.extensions[f"skill:{name}"]
            assert installed.source_hash == scan.items[f"skill:{name}"].source_hash
            assert (state / installed.installed_relpath / "SKILL.md").read_bytes() == (
                source / "SKILL.md"
            ).read_bytes()


def test_cross_process_lock_covers_directory_fsync(tmp_path):
    config = _config(tmp_path)
    _write_private(tmp_path)
    _write_skill(config, name="alpha")
    _write_skill(config, name="beta")
    state = Path(config.extension_state_dir)
    with _apply_processes(
        (tmp_path, "alpha", "directory_fsync"), (tmp_path, "beta", None)
    ) as children:
        (_, a), (_, b) = children
        assert _process_message(a) == ("alpha", "ready", 0)
        assert _process_message(b) == ("beta", "ready", 0)
        a.send("apply")
        assert _process_message(a) == ("alpha", "paused", "directory_fsync")
        assert load_registry(state).revision == 1
        lock_file = state / ".apply.lock"
        inode = lock_file.stat().st_ino
        assert lock_file.stat().st_mode & 0o777 == 0o600
        assert lock_file.read_bytes() == b""
        b.send("probe")
        assert _process_message(b) == ("beta", "probe", "locked")
        a.send("release")
        assert _process_message(a) == ("alpha", "success", 1)
        b.send("probe")
        assert _process_message(b) == ("beta", "probe", "available")
        assert lock_file.stat().st_ino == inode


def test_cross_process_crash_releases_lock_before_revision_read(tmp_path):
    config = _config(tmp_path)
    _write_private(tmp_path)
    _write_skill(config, name="alpha")
    source = _write_skill(config, name="beta")
    state = Path(config.extension_state_dir)
    with _apply_processes(
        (tmp_path, "alpha", "before_read"), (tmp_path, "beta", None), terminated=(0,)
    ) as children:
        (process_a, a), (_, b) = children
        assert _process_message(a) == ("alpha", "ready", 0)
        assert _process_message(b) == ("beta", "ready", 0)
        a.send("apply")
        assert _process_message(a) == ("alpha", "paused", "before_read")
        lock_file = state / ".apply.lock"
        inode = lock_file.stat().st_ino
        b.send("probe")
        assert _process_message(b) == ("beta", "probe", "locked")
        assert not (state / "registry.json").exists()
        assert not (state / "installed").exists()
        process_a.terminate()
        process_a.join(10)
        assert process_a.exitcode == -signal.SIGTERM
        b.send("apply")
        assert _process_message(b) == ("beta", "success", 1)
        registry = load_registry(state)
        assert registry.revision == 1
        assert set(registry.extensions) == {"skill:beta"}
        installed = registry.extensions["skill:beta"]
        assert (state / installed.installed_relpath / "SKILL.md").read_bytes() == (
            source / "SKILL.md"
        ).read_bytes()
        assert lock_file.stat().st_ino == inode


def test_cross_process_apply_uses_separate_state_root_locks(tmp_path):
    roots = [tmp_path / name for name in ("x", "y")]
    for root, name in zip(roots, ("alpha", "beta")):
        root.mkdir()
        _write_private(root)
        _write_skill(_config(root), name=name)
    with _apply_processes(
        (roots[0], "alpha", "before_write"), (roots[1], "beta", None)
    ) as children:
        (_, a), (_, b) = children
        assert _process_message(a) == ("alpha", "ready", 0)
        assert _process_message(b) == ("beta", "ready", 0)
        a.send("apply")
        assert _process_message(a) == ("alpha", "paused", "before_write")
        b.send("apply")
        assert _process_message(b) == ("beta", "success", 1)
        a.send("release")
        assert _process_message(a) == ("alpha", "success", 1)
        for root, name in zip(roots, ("alpha", "beta")):
            registry = load_registry(root / "state")
            assert registry.revision == 1
            assert set(registry.extensions) == {f"skill:{name}"}


@pytest.mark.parametrize("failure", ["read", "write"])
def test_cross_process_apply_exception_releases_locks(monkeypatch, tmp_path, failure):
    config = _config(tmp_path)
    private = _write_private(tmp_path)
    _write_skill(config, name="alpha")
    _write_skill(config, name="beta")
    state = Path(config.extension_state_dir)
    write_registry(state, ExtensionRegistry(revision=7))
    original_bytes = (state / "registry.json").read_bytes()
    manager = _manager(config, private, _PlanModel([dict(_plan_item(), key="skill:alpha")]))
    preview = manager.preview(selected_skill_keys={"skill:alpha"})

    with _apply_processes((tmp_path, "beta", None)) as children:
        (_, b), = children
        assert _process_message(b) == ("beta", "ready", 7)

        def fail(*_args, **_kwargs):
            if failure == "read":
                raise OSError("injected revision read failure")
            raise RegistryError("injected writer failure before replace")

        with monkeypatch.context() as patch:
            patch.setattr(
                manager_module, "load_registry" if failure == "read" else "write_registry", fail
            )
            with pytest.raises(ManagementError, match="extension apply failed: injected"):
                manager.apply(preview)
        assert (state / "registry.json").read_bytes() == original_bytes
        assert manager.apply(preview).applied_revision == 8
        b.send("preview")
        assert _process_message(b) == ("beta", "ready", 8)
        b.send("apply")
        assert _process_message(b) == ("beta", "success", 9)
        registry = load_registry(state)
        assert registry.revision == 9
        assert set(registry.extensions) == {"skill:alpha", "skill:beta"}


@pytest.mark.parametrize("failure", ["open", "flock"])
def test_apply_lock_io_failure_does_not_enter_transaction(monkeypatch, tmp_path, failure):
    config = _config(tmp_path)
    _write_skill(config)
    manager = _manager(config, _write_private(tmp_path), _PlanModel([_plan_item()]))
    preview = manager.preview()

    def fail(*_args, **_kwargs):
        raise OSError(errno.EIO, "injected lock I/O failure")

    def unexpected_transaction(*_args, **_kwargs):
        pytest.fail("lock failure entered apply transaction")

    with monkeypatch.context() as patch:
        patch.setattr(manager, "_apply_locked", unexpected_transaction)
        if failure == "open":
            patch.setattr(manager_module.os, "open", fail)
        else:
            patch.setattr(manager_module.fcntl, "flock", fail)
        with pytest.raises(ManagementError, match="extension apply failed:.*injected lock I/O"):
            manager.apply(preview)
    assert not (preview.paths.state_root / "registry.json").exists()
    assert not (preview.paths.state_root / "installed").exists()
    assert manager.apply(preview).applied_revision == 1


def test_apply_lock_busy_is_slash_command_error(monkeypatch, tmp_path):
    config = _config(tmp_path)
    _write_skill(config)
    manager = _manager(config, _write_private(tmp_path), _PlanModel([_plan_item()]))
    monkeypatch.setattr("builtins.input", lambda _prompt: "yes")
    state = Path(config.extension_state_dir)
    state.mkdir()
    fd = os.open(state / ".apply.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(SlashCommandError, match="another extension apply is already running"):
            asyncio.run(execute_slash_command(
                parse_slash_command("/extension-management"),
                SlashCommandContext(session=_Session(config, manager), registry=build_default_registry()),
            ))
        assert not (state / "registry.json").exists()
        assert not (state / "installed").exists()
    finally:
        os.close(fd)
    assert manager.apply(manager.preview()).applied_revision == 1


def _installer_bundle(tmp_path, *, name="writer", description="ZIP writer"):
    prepared = tmp_path / f"prepared-{name}"
    prepared.mkdir()
    files = {
        "SKILL.md": (
            f"---\nname: {name}\ndescription: {description}\n---\nOriginal instructions.\n"
        ).encode(),
        "forms.md": b"Original root resource\n",
        "scripts/example.py": b"raise RuntimeError('must never run')\n",
    }
    archive = tmp_path / f"{name}.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        for relative, raw in files.items():
            handle.writestr(f"wrapper/{name}/{relative}", raw)
            target = prepared / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
    return archive, prepared, files


def _installer(tmp_path, config, *, operation="add", decision="apply"):
    manager = _manager(
        config, _write_private(tmp_path), _PlanModel([_plan_item(operation, decision)])
    )
    return manager_module.SkillInstaller(
        config, manager_factory=lambda: manager, builtin_names={"citation", "skill-installer"}
    )


def test_installer_prepared_bundle_installs_only_authorized_skill(tmp_path):
    config = _config(tmp_path)
    unselected = _write_skill(config, name="untouched")
    unselected_raw = (unselected / "SKILL.md").read_bytes()
    archive, prepared, files = _installer_bundle(tmp_path)
    installer = _installer(tmp_path, config)
    installer.begin(f"請用 skill-installer 安裝 {archive}", "conversation-a")

    ready = installer.run("preview", source_zip=str(archive), prepared_path=str(prepared))
    assert ready["status"] == "preview_ready"
    report = installer.run("apply", preview_id=ready["preview_id"])

    assert report["status"] == "complete"
    assert report["outcomes"][0]["outcome"] == "added"
    assert report["restart_required"] is True
    assert installer.pending is False
    registry = load_registry(Path(config.extension_state_dir))
    assert set(registry.extensions) == {"skill:writer"}
    managed = Path(config.extension_state_dir) / registry.extensions["skill:writer"].installed_relpath
    for relative, raw in files.items():
        assert (managed / relative).read_bytes() == raw
        assert (Path(config.extension_dropin_dir) / "skill/writer" / relative).read_bytes() == raw
    assert archive.is_file()
    assert (unselected / "SKILL.md").read_bytes() == unselected_raw
    assert installer.run("apply", preview_id=ready["preview_id"])["status"] == "blocked"


def test_installer_requires_real_update_reply_before_staging(tmp_path):
    config = _config(tmp_path)
    source = _write_skill(config, description="Existing user source")
    original = (source / "SKILL.md").read_bytes()
    archive, prepared, _ = _installer_bundle(tmp_path)
    installer = _installer(tmp_path, config)
    installer.begin(f"請用 skill-installer 安裝 {archive}", "conversation-a")

    waiting = installer.run("preview", prepared_path=str(prepared))
    assert waiting["status"] == "needs_update_approval"
    assert (source / "SKILL.md").read_bytes() == original
    assert installer.run("apply", preview_id="model-approved")["status"] == "blocked"
    installer.continue_request("是，更新", "conversation-a")
    ready = installer.run("preview", prepared_path=str(prepared))
    assert ready["status"] == "preview_ready"
    installer.clear()
    assert (source / "SKILL.md").read_bytes() == original
    assert installer.pending is False


def test_installer_multi_candidate_selection_is_bound_to_user_reply(tmp_path):
    config = _config(tmp_path)
    archive, prepared, files = _installer_bundle(tmp_path)
    with zipfile.ZipFile(archive, "a") as handle:
        handle.writestr("wrapper/alpha/SKILL.md", "---\nname: alpha\ndescription: Alpha\n---\n")
    installer = _installer(tmp_path, config)
    installer.begin(f"請用 skill-installer 安裝 {archive}", "conversation-a")

    waiting = installer.run("preview", candidate_root="wrapper/writer", prepared_path=str(prepared))
    assert waiting["status"] == "needs_selection"
    assert [choice["name"] for choice in waiting["candidates"]] == ["alpha", "writer"]
    assert not (Path(config.extension_dropin_dir) / "skill/writer").exists()
    installer.continue_request("第二個", "conversation-a")
    ready = installer.run("preview", candidate_root="wrapper/writer", prepared_path=str(prepared))
    assert ready["status"] == "preview_ready"
    installer.clear()


def test_installer_stale_source_preserves_user_changes(tmp_path):
    config = _config(tmp_path)
    source = _write_skill(config, description="Existing user source")
    archive, prepared, _ = _installer_bundle(tmp_path)
    installer = _installer(tmp_path, config)
    installer.begin(f"請用 skill-installer 更新 {archive}", "conversation-a")
    ready = installer.run("preview", prepared_path=str(prepared))
    assert ready["status"] == "preview_ready"
    (source / "forms.md").write_text("new user modification", encoding="utf-8")

    result = installer.run("apply", preview_id=ready["preview_id"])
    assert result["status"] == "blocked"
    assert result["cleanup_conflict"] is True
    assert (source / "forms.md").read_text() == "new user modification"
    assert installer.pending is False
    assert not load_registry(Path(config.extension_state_dir)).extensions


@pytest.mark.parametrize("name", ["citation", "skill-installer"])
def test_installer_rejects_builtin_collision_before_dropin_write(tmp_path, name):
    config = _config(tmp_path)
    archive, prepared, _ = _installer_bundle(tmp_path, name=name)
    installer = _installer(tmp_path, config)
    installer.begin(f"請用 skill-installer 安裝 {archive}", "conversation-a")

    result = installer.run("preview", prepared_path=str(prepared))
    assert result["status"] == "blocked"
    assert "builtin" in result["detail"]
    assert not Path(config.extension_dropin_dir).exists()


def test_installer_accepts_real_followup_path_but_not_tool_source(tmp_path):
    config = _config(tmp_path)
    archive, prepared, _ = _installer_bundle(tmp_path)
    installer = _installer(tmp_path, config)
    assert installer.begin("請用 skill-installer 安裝 ZIP", "a")["status"] == "needs_source"
    assert installer.run("preview", source_zip=str(archive), prepared_path=str(prepared))["status"] == "needs_source"
    assert not Path(config.extension_dropin_dir).exists()
    resumed = installer.continue_request(f'"{archive}"', "a")
    assert resumed["status"] == "needs_preparation"
    assert resumed["limits"]["max_files"] == config.extension_max_files
    ready = installer.run("preview", prepared_path=str(prepared))
    assert ready["status"] == "preview_ready"
    installer.clear()


@pytest.mark.parametrize("changed", ["archive", "registry"])
def test_installer_pending_approval_rejects_stale_binding(tmp_path, changed):
    config = _config(tmp_path)
    source = _write_skill(config)
    original = (source / "SKILL.md").read_bytes()
    archive, prepared, _ = _installer_bundle(tmp_path)
    installer = _installer(tmp_path, config)
    installer.begin(f"安裝 {archive}", "a")
    assert installer.run("preview", prepared_path=str(prepared))["status"] == "needs_update_approval"
    if changed == "archive":
        with zipfile.ZipFile(archive, "a") as handle:
            handle.writestr("wrapper/writer/extra.txt", "changed ZIP")
    else:
        write_registry(Path(config.extension_state_dir), ExtensionRegistry(revision=1))
    result = installer.continue_request("是，更新", "a")
    assert result["status"] == "blocked"
    assert installer.pending is False
    assert (source / "SKILL.md").read_bytes() == original


def test_installer_blocked_apply_restores_existing_source(tmp_path):
    config = _config(tmp_path)
    source = _write_skill(config)
    original = (source / "SKILL.md").read_bytes()
    archive, prepared, _ = _installer_bundle(tmp_path)
    installer = _installer(tmp_path, config, decision="block")
    installer.begin(f"更新 {archive}", "a")
    ready = installer.run("preview", prepared_path=str(prepared))
    result = installer.run("apply", preview_id=ready["preview_id"])
    assert result["status"] == "blocked"
    assert result["outcomes"][0]["outcome"] == "blocked"
    assert (source / "SKILL.md").read_bytes() == original
    assert not (source / "forms.md").exists()
    assert not load_registry(Path(config.extension_state_dir)).extensions


def test_installer_apply_exception_checks_registry_before_cleanup(tmp_path, monkeypatch):
    config = _config(tmp_path)
    archive, prepared, files = _installer_bundle(tmp_path)
    installer = _installer(tmp_path, config)
    installer.begin(f"安裝 {archive}", "a")
    ready = installer.run("preview", prepared_path=str(prepared))
    actual_apply = installer._manager.apply

    def apply_then_raise(preview):
        actual_apply(preview)
        raise RuntimeError("receipt failed after registry write")

    monkeypatch.setattr(installer._manager, "apply", apply_then_raise)
    result = installer.run("apply", preview_id=ready["preview_id"])
    assert result["status"] == "blocked"
    assert result["outcomes"][0]["outcome"] == "added"
    assert result["restart_required"] is True
    assert "receipt failed" in result["message"]
    assert (Path(config.extension_dropin_dir) / "skill/writer/SKILL.md").read_bytes() == files["SKILL.md"]
    assert installer.pending is False


def test_installer_invalid_zip_and_other_session_clear_authority(tmp_path):
    config = _config(tmp_path)
    invalid = tmp_path / "invalid.zip"
    invalid.write_bytes(b"not a ZIP")
    installer = _installer(tmp_path, config)
    assert installer.begin(f"安裝 {invalid}", "a")["status"] == "blocked"
    assert installer.pending is False
    archive, prepared, _ = _installer_bundle(tmp_path)
    installer.begin(f"安裝 {archive}", "a")
    ready = installer.run("preview", prepared_path=str(prepared))
    assert installer.continue_request("yes", "b")["status"] == "blocked"
    assert installer.run("apply", preview_id=ready["preview_id"])["status"] == "blocked"
    assert not (Path(config.extension_dropin_dir) / "skill/writer").exists()


def test_installer_update_word_in_zip_path_does_not_authorize_overwrite(tmp_path):
    config = _config(tmp_path)
    source = _write_skill(config)
    original = (source / "SKILL.md").read_bytes()
    archive, prepared, _ = _installer_bundle(tmp_path)
    renamed = archive.with_name("update.zip")
    archive.rename(renamed)
    installer = _installer(tmp_path, config)
    installer.begin(f"Install {renamed}", "a")
    assert installer.run("preview", prepared_path=str(prepared))["status"] == "needs_update_approval"
    assert (source / "SKILL.md").read_bytes() == original
    installer.clear()


@pytest.mark.parametrize("user_request", [
    "請用 skill-installer 安裝 {archive}，更新前先問我",
    "use skill-installer to install {archive}; ask me before update",
])
def test_installer_deferred_update_request_requires_real_approval(tmp_path, user_request):
    config = _config(tmp_path)
    source = _write_skill(config)
    original = (source / "SKILL.md").read_bytes()
    archive, prepared, _ = _installer_bundle(tmp_path)
    installer = _installer(tmp_path, config)
    installer.begin(user_request.format(archive=archive), "a")

    result = installer.run("preview", prepared_path=str(prepared))

    assert result["status"] == "needs_update_approval"
    assert (source / "SKILL.md").read_bytes() == original
    assert not load_registry(Path(config.extension_state_dir)).extensions
    installer.continue_request("是，更新", "a")
    assert installer.run("preview", prepared_path=str(prepared))["status"] == "preview_ready"
    installer.clear()


@pytest.mark.parametrize("failure", ["cancel", "preview"])
def test_installer_old_matching_registry_does_not_discard_pending_source(tmp_path, monkeypatch, failure):
    config = _config(tmp_path)
    archive, prepared, _ = _installer_bundle(tmp_path)
    installer = _installer(tmp_path, config)
    installer.begin(f"安裝 {archive}", "a")
    ready = installer.run("preview", prepared_path=str(prepared))
    assert installer.run("apply", preview_id=ready["preview_id"])["status"] == "complete"
    source = _write_skill(config, description="Unapplied user source modification")
    original = (source / "SKILL.md").read_bytes()
    installer = _installer(tmp_path, config)
    installer.begin(f"更新 {archive}", "a")
    if failure == "preview":
        def fail_preview(**kwargs):
            raise RuntimeError("preview failed")
        monkeypatch.setattr(installer.manager_factory(), "preview", fail_preview)
    result = installer.run("preview", prepared_path=str(prepared))
    if failure == "cancel":
        assert result["status"] == "preview_ready"
        result = installer.run("cancel")
    else:
        assert result["status"] == "blocked"
        assert not result.get("outcomes")
    assert (source / "SKILL.md").read_bytes() == original
    assert installer.pending is False


def test_installer_rejects_parent_symlink_replacement_before_staging(tmp_path):
    config = _config(tmp_path)
    archive, prepared, _ = _installer_bundle(tmp_path)
    kind_root = Path(config.extension_dropin_dir) / "skill"
    kind_root.mkdir(parents=True)
    installer = _installer(tmp_path, config)
    installer.begin(f"安裝 {archive}", "a")
    kind_root.rmdir()
    outside = tmp_path / "unrelated"
    outside.mkdir()
    (outside / "keep.txt").write_text("user data", encoding="utf-8")
    kind_root.symlink_to(outside, target_is_directory=True)
    result = installer.run("preview", prepared_path=str(prepared))
    assert result["status"] == "blocked"
    assert "parent changed" in result["detail"]
    assert sorted(path.name for path in outside.iterdir()) == ["keep.txt"]


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

    status = no_model.status(
        running_revision=0,
        running_mcp_families=("clock",),
        startup_diagnostics=("mcp:broken: applied_but_unavailable",),
    )

    assert status.applied_count == 1
    assert status.dropin_root == Path(config.extension_dropin_dir).resolve()
    assert status.state_root == Path(config.extension_state_dir).resolve()
    assert status.applied_revision == 1
    assert status.restart_required is True
    assert status.manager_available is True
    assert status.running_mcp_families == ("clock",)
    assert "mcp:broken: applied_but_unavailable" in status.diagnostics


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


@pytest.mark.parametrize("operation", ["add", "update"])
def test_selected_skill_apply_preserves_other_pending_changes(tmp_path, operation):
    config = _config(tmp_path)
    root = Path(config.extension_dropin_dir)
    state = Path(config.extension_state_dir)
    if operation == "update":
        _write_skill(config, "Original selected skill")
    for name in ("other-update", "other-delete"):
        _write_skill(config, name=name)
    for name in ("mcp-update", "mcp-delete"):
        bundle = root / "mcp" / name
        bundle.mkdir(parents=True)
        (bundle / "server.py").write_text("# original\n", encoding="utf-8")
    initial = scan_extensions(root, config=config)
    entries = {
        key: install_scanned_extension(item, state_root=state, config=config)
        for key, item in initial.items.items()
    }
    write_registry(
        state,
        ExtensionRegistry(revision=1, source_root=str(root), extensions=entries),
    )
    for kind, name in (("skill", "other-delete"), ("mcp", "mcp-delete")):
        bundle = root / kind / name
        for path in bundle.iterdir():
            path.unlink()
        bundle.rmdir()
    selected = _write_skill(config, "Requested version")
    _write_skill(config, "Unselected new version", name="other-update")
    _write_skill(config, name="other-add")
    (root / "mcp" / "mcp-update" / "server.py").write_text(
        "# unselected new version\n", encoding="utf-8"
    )
    added_mcp = root / "mcp" / "mcp-add"
    added_mcp.mkdir()
    (added_mcp / "server.py").write_text("# unselected new MCP\n", encoding="utf-8")
    sources_before = {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*") if path.is_file()
    }
    managed_before = {
        path.relative_to(state): path.read_bytes()
        for path in (state / "installed").rglob("*") if path.is_file()
    }
    model = _PlanModel([_plan_item(operation=operation)])
    manager = _manager(config, _write_private(tmp_path), model)
    scope = {"skill:writer"}

    preview = manager.preview(selected_skill_keys=scope)
    scope.add("skill:other-add")
    report = manager.apply(preview)
    registry = load_registry(state)

    assert preview.selected_skill_keys == frozenset({"skill:writer"})
    assert [(change.key, change.operation) for change in preview.diff.changes] == [
        ("skill:writer", operation)
    ]
    payload = json.loads(model.calls[0][1].content.split("\n\n", 1)[1])
    assert [item["key"] for item in payload["authoritative_changes"]] == ["skill:writer"]
    assert [(item.key, item.outcome) for item in report.items] == [
        ("skill:writer", "added" if operation == "add" else "updated")
    ]
    assert registry.revision == 2
    assert set(registry.extensions) == set(entries) | {"skill:writer"}
    for key, entry in entries.items():
        if key != "skill:writer":
            assert registry.extensions[key] == entry
    for relative, content in managed_before.items():
        assert (state / relative).read_bytes() == content
    assert {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*") if path.is_file()
    } == sources_before
    installed = state / registry.extensions["skill:writer"].installed_relpath
    assert (installed / "SKILL.md").read_bytes() == (selected / "SKILL.md").read_bytes()
    repeat = manager.preview(selected_skill_keys={"skill:writer"})
    assert [(change.key, change.operation) for change in repeat.diff.changes] == [
        ("skill:writer", "unchanged")
    ]
    assert repeat.plan.items == []
    assert len(model.calls) == 1


@pytest.mark.parametrize(
    "scope",
    [set(), {"mcp:clock"}, {"writer"}, {"skill:../writer"}, {"skill:missing"},
     {"skill:writer", "mcp:clock"}, ["skill:writer"], "skill:writer"],
)
def test_selected_skill_scope_rejects_invalid_selection_before_planning(tmp_path, scope):
    config = _config(tmp_path)
    _write_skill(config)
    model = _PlanModel([_plan_item()])
    manager = _manager(config, _write_private(tmp_path), model)

    with pytest.raises(ManagementError) as error:
        manager.preview(selected_skill_keys=scope)

    assert str(error.value)
    assert model.calls == []
    assert not Path(config.extension_state_dir).exists()


def test_selected_skill_scope_rejects_pending_delete(tmp_path):
    config = _config(tmp_path)
    bundle = _write_skill(config)
    model = _PlanModel([_plan_item()])
    manager = _manager(config, _write_private(tmp_path), model)
    manager.apply(manager.preview())
    state = Path(config.extension_state_dir)
    registry_before = (state / "registry.json").read_bytes()
    (bundle / "SKILL.md").unlink()
    bundle.rmdir()

    with pytest.raises(ManagementError):
        manager.preview(selected_skill_keys={"skill:writer"})

    assert (state / "registry.json").read_bytes() == registry_before
    assert len(model.calls) == 1


@pytest.mark.parametrize("changed", ["source", "registry"])
def test_selected_skill_apply_rejects_stale_preview(tmp_path, changed):
    config = _config(tmp_path)
    bundle = _write_skill(config)
    manager = _manager(config, _write_private(tmp_path), _PlanModel([_plan_item()]))
    preview = manager.preview(selected_skill_keys={"skill:writer"})
    state = Path(config.extension_state_dir)
    if changed == "source":
        (bundle / "SKILL.md").write_text("User changed source\n", encoding="utf-8")
        expected_message = "drop-in contents changed"
    else:
        write_registry(state, ExtensionRegistry(revision=1))
        expected_message = "registry changed"
    before = load_registry(state)
    source_before = (bundle / "SKILL.md").read_bytes()

    with pytest.raises(ManagementError, match=expected_message):
        manager.apply(preview)

    assert load_registry(state) == before
    assert (bundle / "SKILL.md").read_bytes() == source_before
    assert not (state / "installed").exists()


def test_selected_skill_scope_rejects_model_added_item(tmp_path):
    config = _config(tmp_path)
    _write_skill(config)
    _write_skill(config, name="other")
    extra = dict(_plan_item(), key="skill:other")
    model = _PlanModel([_plan_item(), extra])
    manager = _manager(config, _write_private(tmp_path), model)

    with pytest.raises(ManagementError, match="coverage mismatch"):
        manager.preview(selected_skill_keys={"skill:writer"})

    assert not Path(config.extension_state_dir).exists()


def test_selected_skill_scope_preserves_cross_kind_collision_check(tmp_path):
    config = _config(tmp_path)
    _write_skill(config)
    mcp = Path(config.extension_dropin_dir) / "mcp" / "writer"
    mcp.mkdir(parents=True)
    (mcp / "server.py").write_text("# inert\n", encoding="utf-8")
    model = _PlanModel([_plan_item(operation="blocked", decision="block")])
    manager = _manager(config, _write_private(tmp_path), model)

    preview = manager.preview(selected_skill_keys={"skill:writer"})
    report = manager.apply(preview)

    assert preview.diff.changes[0].operation == "blocked"
    assert "collides across kinds" in preview.diff.changes[0].reason
    assert [(item.key, item.outcome) for item in report.items] == [
        ("skill:writer", "blocked")
    ]
    assert load_registry(Path(config.extension_state_dir)).extensions == {}
