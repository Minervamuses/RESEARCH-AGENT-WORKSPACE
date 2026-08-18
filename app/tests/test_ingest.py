"""Agent-side RAG ingest boundary tests."""

import asyncio
from pathlib import Path

from agent import ingest as ingest_module
from agent.config import AgentConfig


def test_init_workspace_uses_app_parent_as_host_root(monkeypatch, tmp_path):
    app_root = tmp_path / "app"
    app_root.mkdir()
    calls: dict[str, object] = {}

    def fake_ingest_repo(
        repo_root: str,
        *,
        config: AgentConfig,
        skip_rel_paths: set[str],
    ) -> tuple[int, int]:
        calls.update(
            repo_root=Path(repo_root),
            config=config,
            skip_rel_paths=skip_rel_paths,
        )
        return 3, 7

    monkeypatch.setattr(ingest_module, "find_app_root", lambda: app_root)
    monkeypatch.setattr(ingest_module, "ingest_repo", fake_ingest_repo)
    config = AgentConfig(persist_dir=str(tmp_path / "store"))

    result = asyncio.run(ingest_module.init_workspace(config))

    assert result == (3, 7, tmp_path, {"app"})
    assert calls == {
        "repo_root": tmp_path,
        "config": config,
        "skip_rel_paths": {"app"},
    }
