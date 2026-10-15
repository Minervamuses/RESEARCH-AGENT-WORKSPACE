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
    desktop = tmp_path / "app" / "desktop"
    desktop.mkdir(parents=True)
    for name in ("src", "src-tauri/src", "src-tauri/capabilities", "src-tauri/icons"):
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
