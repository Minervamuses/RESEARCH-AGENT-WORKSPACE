"""OpenRouter chat-model factories for the agent layer.

Built on the dedicated ``langchain-openrouter`` integration (pinned; the
package is still marked beta) instead of ``ChatOpenAI``: it understands
OpenRouter's tool calling, reasoning, and provider metadata natively, so
finish_reason/native_finish_reason and usage reach ``response_metadata``
for turn observability. The rag package keeps its own factory; only the
agent layer migrates here.
"""

import httpx
import openrouter
from langchain_openrouter import ChatOpenRouter
from openrouter.utils import BackoffStrategy, RetryConfig
from rag import OPENROUTER_BASE_URL, get_openrouter_api_key

from agent.config import AgentConfig

# Bounded SDK retry policy for transient 5XX and connection failures. A new
# attempt starts only while the retry window (llm_max_retries x this budget)
# is open; each backoff sleep, including a server Retry-After hint, is capped.
RETRY_WINDOW_MS_PER_RETRY = 5_000
RETRY_MAX_INTERVAL_MS = 8_000


def _cap_retry_after(response: httpx.Response) -> None:
    """Keep a server Retry-After hint inside the bounded retry policy."""
    value = response.headers.get("retry-after")
    if value is None:
        return
    try:
        too_long = float(value) > RETRY_MAX_INTERVAL_MS / 1000
    except ValueError:
        too_long = True  # HTTP dates are capped instead of trusted.
    if too_long:
        response.headers["retry-after"] = str(RETRY_MAX_INTERVAL_MS // 1000)


async def _cap_retry_after_async(response: httpx.Response) -> None:
    _cap_retry_after(response)


def bounded_sdk_client(
    model: ChatOpenRouter,
    config: AgentConfig,
    *,
    transport: httpx.BaseTransport | None = None,
    async_transport: httpx.AsyncBaseTransport | None = None,
) -> openrouter.OpenRouter:
    """Build the SDK client with a finite HTTP timeout and retry window.

    ``ChatOpenRouter`` maps ``max_retries=0`` to the SDK's 60-minute default
    window and leaves the HTTP timeout unset, so the factory supplies its own
    client. Attribution headers match the integration's. Transports exist
    only for offline tests.
    """
    headers: dict[str, str] = {}
    if model.app_url:
        headers["HTTP-Referer"] = model.app_url
    if model.app_title:
        headers["X-Title"] = model.app_title
    if model.app_categories:
        headers["X-OpenRouter-Categories"] = ",".join(model.app_categories)
    retry_config = None  # Explicit None disables SDK retries; UNSET would not.
    if config.llm_max_retries > 0:
        retry_config = RetryConfig(
            "backoff",
            BackoffStrategy(
                initial_interval=1_000,
                max_interval=RETRY_MAX_INTERVAL_MS,
                exponent=2.0,
                max_elapsed_time=config.llm_max_retries * RETRY_WINDOW_MS_PER_RETRY,
            ),
            retry_connection_errors=True,
        )
    return openrouter.OpenRouter(
        api_key=model.openrouter_api_key.get_secret_value(),
        server_url=model.openrouter_api_base,
        client=httpx.Client(
            headers=headers, follow_redirects=True, transport=transport,
            event_hooks={"response": [_cap_retry_after]},
        ),
        async_client=httpx.AsyncClient(
            headers=headers, follow_redirects=True, transport=async_transport,
            event_hooks={"response": [_cap_retry_after_async]},
        ),
        retry_config=retry_config,
        timeout_ms=config.llm_request_timeout_ms,
    )


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
        "timeout": config.llm_request_timeout_ms,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if temperature is not None:
        kwargs["temperature"] = temperature
    model = ChatOpenRouter(**kwargs)
    model.client = bounded_sdk_client(model, config)
    return model
