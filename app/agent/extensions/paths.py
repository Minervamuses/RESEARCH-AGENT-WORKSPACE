"""Resolve drop-in and private state paths without writing to packages."""

from __future__ import annotations

import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from agent.config import AgentConfig
from agent.paths import find_app_root


@dataclass(frozen=True)
class ExtensionPaths:
    """Resolved roots for one extension-management workspace."""

    dropin_root: Path
    state_root: Path


def _platform_data_root(env: dict[str, str]) -> Path:
    if sys.platform == "win32":
        raw = env.get("APPDATA", "")
        return Path(raw) if raw else Path.home() / "AppData" / "Roaming"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    raw = env.get("XDG_DATA_HOME", "").strip()
    return Path(raw).expanduser() if raw else Path.home() / ".local" / "share"


def _platform_state_root(env: dict[str, str]) -> Path:
    if sys.platform == "win32":
        raw = env.get("LOCALAPPDATA", "") or env.get("APPDATA", "")
        return Path(raw) if raw else Path.home() / "AppData" / "Local"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    raw = env.get("XDG_STATE_HOME", "").strip()
    return Path(raw).expanduser() if raw else Path.home() / ".local" / "state"


def _source_checkout_tool_root() -> Path | None:
    try:
        app_root = find_app_root()
    except RuntimeError:
        return None
    return app_root / "tool"


def _configured_path(raw: str | None) -> Path | None:
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def resolve_extension_paths(
    config: AgentConfig,
    *,
    env: dict[str, str] | None = None,
) -> ExtensionPaths:
    """Resolve desired-state and host-state roots by fixed precedence."""
    env = dict(os.environ) if env is None else dict(env)
    dropin = _configured_path(config.extension_dropin_dir)
    if dropin is None:
        dropin = _source_checkout_tool_root()
    if dropin is None:
        dropin = _platform_data_root(env) / "research-agent" / "tool"
    dropin = dropin.resolve()

    state = _configured_path(config.extension_state_dir)
    if state is None:
        workspace_id = hashlib.sha256(
            str(dropin).encode("utf-8")
        ).hexdigest()[:16]
        state = (
            _platform_state_root(env)
            / "research-agent"
            / "extensions"
            / workspace_id
        )
    state = state.resolve()
    if (
        state == dropin
        or state.is_relative_to(dropin)
        or dropin.is_relative_to(state)
    ):
        raise ValueError("extension drop-in and state roots must not overlap")
    return ExtensionPaths(dropin_root=dropin, state_root=state)
