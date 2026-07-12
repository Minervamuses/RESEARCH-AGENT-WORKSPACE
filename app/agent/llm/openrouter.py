"""OpenRouter chat-model factories for the agent layer.

Built on the dedicated ``langchain-openrouter`` integration (pinned; the
package is still marked beta) instead of ``ChatOpenAI``: it understands
OpenRouter's tool calling, reasoning, and provider metadata natively, so
finish_reason/native_finish_reason and usage reach ``response_metadata``
for turn observability. The rag package keeps its own factory; only the
agent layer migrates here.
"""

from typing import Any

from langchain_openrouter import ChatOpenRouter
from rag import OPENROUTER_BASE_URL, get_openrouter_api_key

from agent.config import AgentConfig


def get_chat_model(config: AgentConfig | None = None) -> ChatOpenRouter:
    """Return a ChatOpenRouter model for use with LangGraph.

    Args:
        config: KMS configuration. Uses default if None.

    Returns:
        ChatOpenRouter instance for the configured main chat model.
    """
    config = config or AgentConfig()
    return get_openrouter_chat_model(
        config,
        max_tokens=config.llm_max_tokens,
    )


def get_openrouter_chat_model(
    config: AgentConfig | None = None,
    *,
    model_name: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    extra_body: dict[str, Any] | None = None,
) -> ChatOpenRouter:
    """Return an OpenRouter-backed LangChain chat model.

    Core runtime, evaluation, and one-off prompt-to-text helpers all share this
    factory so the agent has one model access contract. ``extra_body`` keeps
    the historical request-payload contract: keys that are first-class
    ChatOpenRouter fields (``reasoning``) are promoted to the field, the rest
    pass through ``model_kwargs`` into the request body.
    """
    config = config or AgentConfig()
    kwargs: dict[str, Any] = {
        "base_url": OPENROUTER_BASE_URL,
        "api_key": get_openrouter_api_key(),
        "model": model_name or config.llm_model,
        "max_retries": config.llm_max_retries,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if temperature is not None:
        kwargs["temperature"] = temperature
    if extra_body:
        body = dict(extra_body)
        if "reasoning" in body:
            kwargs["reasoning"] = body.pop("reasoning")
        if body:
            kwargs["model_kwargs"] = body
    return ChatOpenRouter(**kwargs)
