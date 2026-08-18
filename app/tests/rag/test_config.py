"""RAG configuration path tests for the integrated app layout."""

from pathlib import Path

from rag.config import RAGConfig


def test_default_store_lives_at_app_root(monkeypatch):
    monkeypatch.delenv("KMS_STORE_DIR", raising=False)
    app_root = Path(__file__).resolve().parents[2]

    assert Path(RAGConfig().persist_dir) == app_root / "store"
