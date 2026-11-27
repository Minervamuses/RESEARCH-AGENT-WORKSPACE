"""The daily launcher reuses release output and keeps live reload explicit."""

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


def _launcher(monkeypatch, tmp_path):
    source = Path(__file__).resolve().parents[2] / "main.py"
    spec = importlib.util.spec_from_file_location("desktop_launcher", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "__file__", str(tmp_path / "main.py"))
    monkeypatch.delenv("CARGO_TARGET_DIR", raising=False)
    # Keep launch tests from starting the host's IBus; the IBus tests opt back in.
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    desktop = tmp_path / "app" / "desktop"
    desktop.mkdir(parents=True)
    for name in ("src", "protocol", "src-tauri/src", "src-tauri/capabilities", "src-tauri/icons"):
        (desktop / name).mkdir(parents=True, exist_ok=True)
    for name in (
        "index.html", "package.json", "package-lock.json", "tsconfig.json", "vite.config.ts",
        "src-tauri/Cargo.toml", "src-tauri/Cargo.lock", "src-tauri/build.rs", "src-tauri/tauri.conf.json",
    ):
        (desktop / name).touch()
    return module, desktop


def test_current_release_launch_skips_build_and_live_reload(monkeypatch, tmp_path):
    launcher, desktop = _launcher(monkeypatch, tmp_path)
    binary = desktop / "src-tauri/target/release/research-agent-desktop"
    binary.parent.mkdir(parents=True)
    binary.touch()
    calls = []
    monkeypatch.setattr(launcher.subprocess, "run", lambda command, **kw: (
        calls.append((command, kw)) or SimpleNamespace(returncode=0)
    ))

    assert launcher.main([]) == 0
    assert len(calls) == 1
    assert calls[0][0] == [str(binary)]
    assert calls[0][1]["cwd"] == desktop


def test_protocol_contract_edit_invalidates_release(monkeypatch, tmp_path):
    """TS and Rust both compile the shared contract into the release."""
    launcher, desktop = _launcher(monkeypatch, tmp_path)
    contract = desktop / "protocol/v1/contract.json"
    contract.parent.mkdir(parents=True)
    contract.write_text("{}", encoding="utf-8")
    binary = desktop / "research-agent-desktop"
    binary.touch()
    for path in desktop.rglob("*"):
        os.utime(path, ns=(100, 100))
    assert launcher._release_is_current(desktop, binary)
    os.utime(contract, ns=(200, 200))
    assert not launcher._release_is_current(desktop, binary)


def test_source_edit_or_removal_invalidates_release(monkeypatch, tmp_path):
    launcher, desktop = _launcher(monkeypatch, tmp_path)
    source = desktop / "src/App.tsx"
    source.parent.mkdir(exist_ok=True)
    source.write_text("source", encoding="utf-8")
    binary = desktop / "research-agent-desktop"
    binary.touch()
    for path in desktop.rglob("*"):
        os.utime(path, ns=(100, 100))
    assert launcher._release_is_current(desktop, binary)
    os.utime(source, ns=(200, 200))
    assert not launcher._release_is_current(desktop, binary)
    source.unlink()
    assert not launcher._release_is_current(desktop, binary)


@pytest.mark.parametrize("returncode", [0, 1])
def test_missing_release_builds_and_never_launches_after_failure(
    monkeypatch, tmp_path, returncode,
):
    launcher, desktop = _launcher(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr(launcher.subprocess, "run", lambda command, **kw: (
        calls.append(command) or SimpleNamespace(returncode=returncode)
    ))
    assert launcher.main([]) == returncode
    assert calls[0] == ["npm", "run", "tauri", "build", "--", "--no-bundle"]
    assert len(calls) == (2 if returncode == 0 else 1)


def test_dev_explicitly_preserves_existing_launch(monkeypatch, tmp_path):
    launcher, _ = _launcher(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr(launcher.subprocess, "run", lambda command, **kw: (
        calls.append(command) or SimpleNamespace(returncode=0)
    ))
    assert launcher.main(["--dev"]) == 0
    assert calls == [["npm", "run", "tauri", "dev"]]


def test_wsl_graphics_override_is_process_local(monkeypatch, tmp_path):
    launcher, _ = _launcher(monkeypatch, tmp_path)
    for name in (
        "GALLIUM_DRIVER", "MESA_LOADER_DRIVER_OVERRIDE", "LIBGL_ALWAYS_SOFTWARE",
        "WEBKIT_DISABLE_DMABUF_RENDERER", "WEBKIT_DISABLE_COMPOSITING_MODE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    env = launcher._desktop_environment()
    assert env["GALLIUM_DRIVER"] == "d3d12"
    assert env["WEBKIT_DISABLE_DMABUF_RENDERER"] == "1"
    assert "GALLIUM_DRIVER" not in os.environ
    assert "WEBKIT_DISABLE_DMABUF_RENDERER" not in os.environ


@pytest.mark.parametrize("name,value", [
    ("GALLIUM_DRIVER", "llvmpipe"),
    ("MESA_LOADER_DRIVER_OVERRIDE", "zink"),
    ("LIBGL_ALWAYS_SOFTWARE", "1"),
    ("WEBKIT_DISABLE_DMABUF_RENDERER", "0"),
])
def test_explicit_graphics_preference_is_preserved(monkeypatch, tmp_path, name, value):
    launcher, _ = _launcher(monkeypatch, tmp_path)
    monkeypatch.delenv("GALLIUM_DRIVER", raising=False)
    monkeypatch.setenv(name, value)
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    env = launcher._desktop_environment()
    assert env[name] == value
    if name != "GALLIUM_DRIVER":
        assert "GALLIUM_DRIVER" not in env


def test_non_wsl_does_not_force_a_graphics_driver(monkeypatch, tmp_path):
    launcher, _ = _launcher(monkeypatch, tmp_path)
    monkeypatch.delenv("GALLIUM_DRIVER", raising=False)
    monkeypatch.setattr(Path, "exists", lambda self: False)
    assert "GALLIUM_DRIVER" not in launcher._desktop_environment()


def test_deleted_top_level_build_input_invalidates_release(monkeypatch, tmp_path):
    launcher, desktop = _launcher(monkeypatch, tmp_path)
    binary = desktop / "research-agent-desktop"
    binary.touch()
    assert launcher._release_is_current(desktop, binary)
    (desktop / "index.html").unlink()
    assert not launcher._release_is_current(desktop, binary)


def _ibus_host(monkeypatch, launcher, *, daemon="/usr/bin/ibus-daemon", gtk_module=True):
    """A WSL host whose IBus pieces are faked; returns the recorded subprocess calls."""
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu-24.04")
    for name in ("GTK_IM_MODULE", "XMODIFIERS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(launcher.shutil, "which", lambda name, path=None: daemon if name == "ibus-daemon" else None)
    real_is_file = Path.is_file
    monkeypatch.setattr(Path, "is_file", lambda self: (
        gtk_module if str(self) in launcher._GTK3_IBUS_MODULES else real_is_file(self)
    ))
    calls = []
    monkeypatch.setattr(launcher.subprocess, "run", lambda command, **kw: (
        calls.append((command, kw)) or SimpleNamespace(returncode=0)
    ))
    return calls


@pytest.mark.parametrize("daemon_returncode", [0, 1])
def test_installed_ibus_is_started_and_enabled_for_the_gui_only(monkeypatch, tmp_path, daemon_returncode):
    """A nonzero exit means this display already has a daemon, which is reused."""
    launcher, _ = _launcher(monkeypatch, tmp_path)
    calls = _ibus_host(monkeypatch, launcher)
    monkeypatch.setattr(launcher.subprocess, "run", lambda command, **kw: (
        calls.append((command, kw)) or SimpleNamespace(returncode=daemon_returncode)
    ))
    env = {"WSL_DISTRO_NAME": "Ubuntu-24.04", "PATH": "/usr/bin"}
    launcher._enable_ibus(env)
    assert [command for command, _ in calls] == [["/usr/bin/ibus-daemon", "--daemonize", "--xim"]]
    assert calls[0][1]["timeout"] == 10
    assert env["GTK_IM_MODULE"] == "ibus"
    assert env["XMODIFIERS"] == "@im=ibus"
    assert "GTK_IM_MODULE" not in os.environ


@pytest.mark.parametrize("daemon,gtk_module", [(None, True), ("/usr/bin/ibus-daemon", False)])
def test_missing_ibus_pieces_leave_input_untouched(monkeypatch, tmp_path, daemon, gtk_module):
    launcher, _ = _launcher(monkeypatch, tmp_path)
    calls = _ibus_host(monkeypatch, launcher, daemon=daemon, gtk_module=gtk_module)
    env = {"WSL_DISTRO_NAME": "Ubuntu-24.04", "PATH": "/usr/bin"}
    launcher._enable_ibus(env)
    assert calls == []
    assert "GTK_IM_MODULE" not in env and "XMODIFIERS" not in env


@pytest.mark.parametrize("preset", [{"GTK_IM_MODULE": "fcitx"}, {"XMODIFIERS": "@im=fcitx"}, {}])
def test_user_choice_or_non_wsl_host_is_respected(monkeypatch, tmp_path, preset):
    launcher, _ = _launcher(monkeypatch, tmp_path)
    calls = _ibus_host(monkeypatch, launcher)
    env = {"PATH": "/usr/bin", **preset}
    if preset:
        env["WSL_DISTRO_NAME"] = "Ubuntu-24.04"
    before = dict(env)
    launcher._enable_ibus(env)
    assert calls == []
    assert env == before


@pytest.mark.parametrize("failure", ["exec", "timeout"])
def test_daemon_start_failure_still_launches_without_ibus(monkeypatch, tmp_path, failure):
    launcher, _ = _launcher(monkeypatch, tmp_path)
    _ibus_host(monkeypatch, launcher)

    def run(command, **kw):
        if failure == "exec":
            raise OSError("exec failed")
        raise launcher.subprocess.TimeoutExpired(command, 10)

    monkeypatch.setattr(launcher.subprocess, "run", run)
    env = {"WSL_DISTRO_NAME": "Ubuntu-24.04", "PATH": "/usr/bin"}
    launcher._enable_ibus(env)
    assert "GTK_IM_MODULE" not in env and "XMODIFIERS" not in env


def test_release_launch_passes_ibus_to_the_desktop_binary(monkeypatch, tmp_path):
    launcher, desktop = _launcher(monkeypatch, tmp_path)
    binary = desktop / "src-tauri/target/release/research-agent-desktop"
    binary.parent.mkdir(parents=True)
    binary.touch()
    calls = _ibus_host(monkeypatch, launcher)
    assert launcher.main([]) == 0
    assert [command for command, _ in calls] == [
        ["/usr/bin/ibus-daemon", "--daemonize", "--xim"], [str(binary)],
    ]
    assert calls[1][1]["env"]["GTK_IM_MODULE"] == "ibus"
    assert calls[1][1]["env"]["XMODIFIERS"] == "@im=ibus"
