"""OpenRouter chat-model factories for the agent layer.

Built on the dedicated ``langchain-openrouter`` integration (pinned; the
package is still marked beta) instead of ``ChatOpenAI``: it understands
OpenRouter's tool calling, reasoning, and provider metadata natively, so
finish_reason/native_finish_reason and usage reach ``response_metadata``
for turn observability. The rag package keeps its own factory; only the
agent layer migrates here.
"""

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
) -> ChatOpenRouter:
    """Return an OpenRouter-backed LangChain chat model.

    Core runtime and one-off prompt-to-text helpers share this factory so the
    agent has one model access contract.
    """
    config = config or AgentConfig()
    kwargs: dict[str, object] = {
        "base_url": OPENROUTER_BASE_URL,
        "api_key": get_openrouter_api_key(),
        "model": model_name or config.llm_model,
        "max_retries": config.llm_max_retries,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if temperature is not None:
        kwargs["temperature"] = temperature
    return ChatOpenRouter(**kwargs)
