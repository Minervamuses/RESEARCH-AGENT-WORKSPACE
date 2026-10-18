"""Ollama-based embedder — local embedding via Ollama server."""

from langchain_core.embeddings import Embeddings

from rag.config import RAGConfig
from rag.types import invoke_provider


class OllamaEmbedder(Embeddings):
    """Embed text using a local Ollama model (e.g., bge-m3).

    Also implements langchain's `Embeddings` protocol (via `embed_documents`
    + `embed_query`) so it can be passed straight into `Chroma(
    embedding_function=...)` — that lets `ChromaStore` depend on this
    rag-owned wrapper instead of reaching into `OllamaEmbeddings` directly.
    """

    def __init__(self, config: RAGConfig):
        from langchain_ollama import OllamaEmbeddings

        self.config = config
        self._embeddings = OllamaEmbeddings(model=config.embed_model)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed documents through the langchain ``Embeddings`` protocol."""
        return invoke_provider(
            lambda: self._embeddings.embed_documents(texts),
            lambda: self._embeddings.aembed_documents(texts),
        )

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query text."""
        return invoke_provider(
            lambda: self._embeddings.embed_query(text),
            lambda: self._embeddings.aembed_query(text),
        )
