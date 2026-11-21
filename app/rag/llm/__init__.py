"""LLM provider used internally by rag (e.g. tagger) and shared OpenRouter helpers.

Chat-model factories for the agent layer live in ``agent.llm``; shared
OpenRouter configuration helpers (``OPENROUTER_BASE_URL`` and
``get_openrouter_api_key``) in ``rag.llm.openrouter`` are re-exported at the
top-level ``rag`` package.
"""

from rag.llm.openrouter import OpenRouterLLM

__all__ = ["OpenRouterLLM"]
