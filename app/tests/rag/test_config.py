"""RAG configuration path tests for the integrated app layout."""

from pathlib import Path

import pytest

from rag.chunker.token import TokenChunker
from rag.config import RAGConfig


def test_default_store_lives_at_app_root(monkeypatch):
    monkeypatch.delenv("KMS_STORE_DIR", raising=False)
    app_root = Path(__file__).resolve().parents[2]

    assert Path(RAGConfig().persist_dir) == app_root / "store"


@pytest.mark.parametrize("chunk_size", [0, -1, 1.5, True, "10"])
def test_chunk_size_must_be_a_positive_integer(chunk_size):
    with pytest.raises(ValueError, match="chunk_size must be a positive integer"):
        RAGConfig(chunk_size=chunk_size)


@pytest.mark.parametrize("chunk_overlap", [-1, 10, 11, 1.5, False])
def test_chunk_overlap_must_be_an_integer_below_chunk_size(chunk_overlap):
    with pytest.raises(
        ValueError,
        match="chunk_overlap must be an integer satisfying 0 <= chunk_overlap < chunk_size",
    ):
        RAGConfig(chunk_size=10, chunk_overlap=chunk_overlap)


def test_minimum_chunk_window_is_valid():
    config = RAGConfig(chunk_size=1, chunk_overlap=0)

    assert config.chunk_size == 1
    assert config.chunk_overlap == 0


def test_token_chunker_revalidates_a_mutated_config():
    config = RAGConfig(chunk_size=10, chunk_overlap=2)
    config.chunk_overlap = 10

    with pytest.raises(ValueError, match="chunk_overlap"):
        TokenChunker(config)
