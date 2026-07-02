"""Ollama-based embedder — local embedding via Ollama server."""

from langchain_core.embeddings import Embeddings
from langchain_ollama import OllamaEmbeddings

from rag.config import RAGConfig
from rag.embedder.base import BaseEmbedder


class OllamaEmbedder(BaseEmbedder, Embeddings):
    """Embed text using a local Ollama model (e.g., bge-m3).

    Also implements langchain's `Embeddings` protocol (via `embed_documents`
    + `embed_query`) so it can be passed straight into `Chroma(
    embedding_function=...)` — that lets `ChromaStore` depend on this
    rag-owned wrapper instead of reaching into `OllamaEmbeddings` directly.
    """

    def __init__(self, config: RAGConfig):
        self.config = config
        self._embeddings = OllamaEmbeddings(model=config.embed_model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts into vectors."""
        return self._embeddings.embed_documents(texts)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """langchain `Embeddings` protocol alias for `embed`."""
        return self.embed(texts)

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query text."""
        return self._embeddings.embed_query(text)
