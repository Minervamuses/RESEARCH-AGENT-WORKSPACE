"""Ollama LLM provider — local inference for fast/cheap tasks."""

import ollama as _ollama

from rag.config import RAGConfig
from rag.llm.base import BaseLLM


class OllamaLLM(BaseLLM):
    """LLM provider via local Ollama server."""

    def __init__(self, model_name: str | None = None, config: RAGConfig | None = None):
        if not model_name:
            raise ValueError("OllamaLLM requires model_name (no default in RAGConfig)")
        _ = config
        self.model = model_name
        self._client = _ollama.Client()

    def invoke(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float | None = None,
    ) -> str:
        """Send a prompt to the local Ollama model and return the response."""
        options: dict = {"num_predict": max_tokens}
        if temperature is not None:
            options["temperature"] = temperature
        resp = self._client.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            options=options,
        )
        content = resp.message.content
        return content.strip() if content else ""
