"""Runtime-environment guard for the Conda-managed chat CLI."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path


class CondaRuntimeError(RuntimeError):
    """Raised when the chat CLI is not running from its Conda environment."""


def require_conda_runtime(
    expected_env: str,
    *,
    environ: Mapping[str, str] | None = None,
    runtime_prefix: str | None = None,
) -> None:
    """Refuse system Python, Poetry venvs, and the wrong Conda environment."""
    env = os.environ if environ is None else environ
    conda_prefix_raw = env.get("CONDA_PREFIX", "").strip()
    if not conda_prefix_raw:
        raise CondaRuntimeError(
            f"Conda environment {expected_env!r} is required. Run "
            f"`conda activate {expected_env}` or prefix the command with "
            f"`conda run -n {expected_env}`."
        )

    conda_prefix = Path(conda_prefix_raw).expanduser().resolve()
    active_prefix = Path(runtime_prefix or sys.prefix).expanduser().resolve()
    if active_prefix != conda_prefix:
        raise CondaRuntimeError(
            f"Refusing Python runtime {active_prefix}: active Conda prefix is "
            f"{conda_prefix}. Deactivate the nested virtualenv and use the "
            "Conda interpreter directly."
        )

    conda_name = env.get("CONDA_DEFAULT_ENV", "").strip() or conda_prefix.name
    if conda_name != expected_env or conda_prefix.name != expected_env:
        raise CondaRuntimeError(
            f"Conda environment {expected_env!r} is required; current environment "
            f"is {conda_name!r} at {conda_prefix}."
        )
