"""The chat CLI must run from the Conda-managed app environment."""

import pytest

from agent.cli.runtime import CondaRuntimeError, require_conda_runtime


def test_require_conda_runtime_accepts_matching_prefix(tmp_path):
    prefix = tmp_path / "envs/app"
    require_conda_runtime(
        "app",
        environ={
            "CONDA_PREFIX": str(prefix),
            "CONDA_DEFAULT_ENV": "app",
            # Poetry sets VIRTUAL_ENV to the Conda prefix during `poetry run`;
            # that is still the same Conda runtime and must remain valid.
            "VIRTUAL_ENV": str(prefix),
        },
        runtime_prefix=str(prefix),
    )


def test_require_conda_runtime_rejects_missing_conda():
    with pytest.raises(CondaRuntimeError, match="conda activate app"):
        require_conda_runtime(
            "app",
            environ={},
            runtime_prefix="/usr",
        )


def test_require_conda_runtime_rejects_nested_virtualenv(tmp_path):
    conda_prefix = tmp_path / "envs/app"
    venv_prefix = tmp_path / "workspace/.venv"
    with pytest.raises(CondaRuntimeError, match="nested virtualenv"):
        require_conda_runtime(
            "app",
            environ={
                "CONDA_PREFIX": str(conda_prefix),
                "CONDA_DEFAULT_ENV": "app",
                "VIRTUAL_ENV": str(venv_prefix),
            },
            runtime_prefix=str(venv_prefix),
        )


def test_require_conda_runtime_rejects_wrong_conda_env(tmp_path):
    prefix = tmp_path / "envs/rag"
    with pytest.raises(CondaRuntimeError, match="current environment is 'rag'"):
        require_conda_runtime(
            "app",
            environ={
                "CONDA_PREFIX": str(prefix),
                "CONDA_DEFAULT_ENV": "rag",
            },
            runtime_prefix=str(prefix),
        )
