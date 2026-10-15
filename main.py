import argparse
import os
import subprocess
from pathlib import Path


def _release_is_current(desktop_dir: Path, executable: Path) -> bool:
    """Rebuild when desktop inputs (including directory entries) have changed."""
    if not executable.is_file():
        return False
    built_at = executable.stat().st_mtime_ns
    inputs = [
        desktop_dir / name
        for name in (
            "index.html", "package.json", "package-lock.json", "tsconfig.json",
            "vite.config.ts", "src", "public", "src-tauri/Cargo.toml",
            "src-tauri/Cargo.lock", "src-tauri/build.rs",
            "src-tauri/tauri.conf.json", "src-tauri/src",
            "src-tauri/capabilities", "src-tauri/icons",
        )
    ]
    for path in inputs:
        if not path.exists():
            if path == desktop_dir / "public":
                continue
            return False
        if path.stat().st_mtime_ns > built_at:
            return False
        if path.is_dir() and any(
            item.stat().st_mtime_ns > built_at for item in path.rglob("*")
        ):
            return False
    return True


def _desktop_environment() -> dict[str, str]:
    """Use WSLg's available D3D12 driver without changing the user's shell."""
    env = dict(os.environ)
    overrides = (
        "GALLIUM_DRIVER", "MESA_LOADER_DRIVER_OVERRIDE", "LIBGL_ALWAYS_SOFTWARE",
        "WEBKIT_DISABLE_DMABUF_RENDERER", "WEBKIT_DISABLE_COMPOSITING_MODE",
    )
    if (
        not any(name in env for name in overrides)
        and Path("/dev/dxg").exists()
        and Path("/usr/lib/wsl/lib/libd3d12.so").is_file()
        and Path("/usr/lib/x86_64-linux-gnu/dri/d3d12_dri.so").is_file()
    ):
        env["GALLIUM_DRIVER"] = "d3d12"
        # WSLg's D3D12 path opens the GPU but displays a blank WebKit view
        # with DMA-BUF rendering. Keep compositing and use its other transport.
        env["WEBKIT_DISABLE_DMABUF_RENDERER"] = "1"
    return env


def main(argv: list[str] | None = None) -> int:
    """Launch the release GUI; opt into live development with --dev."""
    parser = argparse.ArgumentParser(description=__doc__ or main.__doc__)
    parser.add_argument("--dev", action="store_true", help="Run Tauri with live reload")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild the release GUI")
    args = parser.parse_args(argv)
    desktop_dir = Path(__file__).resolve().parent / "app" / "desktop"
    if args.dev:
        return subprocess.run(
            ["npm", "run", "tauri", "dev"], cwd=desktop_dir, check=False,
            env=_desktop_environment(),
        ).returncode

    target_dir = Path(os.environ.get("CARGO_TARGET_DIR", "target"))
    if not target_dir.is_absolute():
        target_dir = desktop_dir / "src-tauri" / target_dir
    executable = target_dir / "release" / "research-agent-desktop"
    if args.rebuild or not _release_is_current(desktop_dir, executable):
        print("Building the release desktop app...", flush=True)
        result = subprocess.run(
            ["npm", "run", "tauri", "build", "--", "--no-bundle"],
            cwd=desktop_dir,
            check=False,
        )
        if result.returncode:
            return result.returncode
    return subprocess.run(
        [str(executable)], cwd=desktop_dir, check=False, env=_desktop_environment(),
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
