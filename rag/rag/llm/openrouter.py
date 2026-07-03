"""OpenRouter LLM provider used internally by rag (tagger)."""

import os
from typing import Any

from openai import OpenAI

from rag.config import RAGConfig
from rag.llm.base import BaseLLM

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def get_openrouter_api_key() -> str:
    """Return the OpenRouter API key, failing fast when it is missing."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    return api_key


class OpenRouterLLM(BaseLLM):
    """LLM provider via OpenRouter API. Used by LLMTagger for simple prompt→text calls."""

    MAX_RETRIES = 10

    def __init__(self, model_name: str | None = None, config: RAGConfig | None = None):
        # Retries are delegated to the SDK: besides 429 it also retries
        # connection errors and 5xx, with a shorter backoff than the old
        # hand-rolled 10s-doubling loop.
        self.client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=get_openrouter_api_key(),
            max_retries=self.MAX_RETRIES,
        )
        config = config or RAGConfig()
        self.model = model_name or config.tagger_model

    def invoke(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float | None = None,
        response_format: dict[str, Any] | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> str:
        """Send a prompt to the LLM and return the response."""
        kwargs: dict = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if response_format is not None:
            kwargs["response_format"] = response_format
        if extra_body is not None:
            kwargs["extra_body"] = extra_body

        resp = self.client.chat.completions.create(**kwargs)
        content = resp.choices[0].message.content
        return content.strip() if content else ""
