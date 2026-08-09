"""Path helpers shared by the agent core, CLI, and tests."""

import os
from pathlib import Path


def find_app_root() -> Path:
    """Walk up from this file to the app project root."""
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / "pyproject.toml").exists():
            return candidate
    raise RuntimeError("could not locate app project root (no pyproject.toml found)")


def user_data_root(env: dict[str, str]) -> Path:
    """Return the Linux XDG user-data root."""
    raw = env.get("XDG_DATA_HOME", "").strip()
    return Path(raw).expanduser() if raw else Path.home() / ".local" / "share"


def user_state_root(env: dict[str, str]) -> Path:
    """Return the Linux XDG user-state root."""
    raw = env.get("XDG_STATE_HOME", "").strip()
    return Path(raw).expanduser() if raw else Path.home() / ".local" / "state"


def fsync_directory(path: Path) -> None:
    """Flush directory metadata when the filesystem supports it."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
