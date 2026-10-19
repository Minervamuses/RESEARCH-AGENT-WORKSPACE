"""OpenRouter chat-model factories for the agent layer.

Built on the dedicated ``langchain-openrouter`` integration (pinned; the
package is still marked beta) instead of ``ChatOpenAI``: it understands
OpenRouter's tool calling, reasoning, and provider metadata natively, so
finish_reason/native_finish_reason and usage reach ``response_metadata``
for turn observability. The rag package keeps its own factory; only the
agent layer migrates here.
"""

import asyncio
import logging
import time

import httpx
import openrouter
from langchain_openrouter import ChatOpenRouter
from rag import OPENROUTER_BASE_URL, get_openrouter_api_key

from agent.config import AgentConfig

logger = logging.getLogger(__name__)

# Bounded retry policy for transient OpenRouter failures: any 5xx response or a
# network-level error is retried at most ``llm_max_retries`` times, however long
# the failed attempt took. Sleeps grow 1, 2, 4 s and never exceed this cap, which
# also bounds a server Retry-After hint. Timeouts are not retried: one attempt
# may already have waited ``llm_request_timeout_ms``.
RETRY_MAX_INTERVAL_SECONDS = 8.0
_RETRYABLE_ERRORS = (httpx.NetworkError, httpx.RemoteProtocolError)

# Module-level so offline tests can skip real waits.
_sleep = time.sleep
_async_sleep = asyncio.sleep


def _retry_delay(retry: int, retry_after: str | None) -> float:
    """Return the capped wait before retry number ``retry`` (1-based)."""
    if retry_after is not None:
        try:
            return min(max(float(retry_after), 0.0), RETRY_MAX_INTERVAL_SECONDS)
        except ValueError:
            return RETRY_MAX_INTERVAL_SECONDS  # HTTP dates are capped, not trusted.
    return min(2.0 ** (retry - 1), RETRY_MAX_INTERVAL_SECONDS)


def _log_retry(retry: int, max_retries: int, cause: str, delay: float) -> None:
    logger.info("openrouter request retry %d/%d after %s in %.1fs", retry, max_retries, cause, delay)


class _RetryingClient(httpx.Client):
    """httpx client that re-sends a request after a transient failure."""

    def __init__(self, *, max_retries: int, **kwargs):
        super().__init__(**kwargs)
        self._max_retries = max_retries

    def send(self, request, **kwargs):
        retry = 0
        while True:
            try:
                response = super().send(request, **kwargs)
            except _RETRYABLE_ERRORS as exc:
                if retry >= self._max_retries:
                    raise
                retry += 1
                delay = _retry_delay(retry, None)
                _log_retry(retry, self._max_retries, type(exc).__name__, delay)
                _sleep(delay)
                continue
            if response.status_code < 500 or retry >= self._max_retries:
                return response
            retry += 1
            delay = _retry_delay(retry, response.headers.get("retry-after"))
            _log_retry(retry, self._max_retries, f"HTTP {response.status_code}", delay)
            response.close()
            _sleep(delay)


class _RetryingAsyncClient(httpx.AsyncClient):
    """Async counterpart of ``_RetryingClient``; cancellation stops it."""

    def __init__(self, *, max_retries: int, **kwargs):
        super().__init__(**kwargs)
        self._max_retries = max_retries

    async def send(self, request, **kwargs):
        retry = 0
        while True:
            try:
                response = await super().send(request, **kwargs)
            except _RETRYABLE_ERRORS as exc:
                if retry >= self._max_retries:
                    raise
                retry += 1
                delay = _retry_delay(retry, None)
                _log_retry(retry, self._max_retries, type(exc).__name__, delay)
                await _async_sleep(delay)
                continue
            if response.status_code < 500 or retry >= self._max_retries:
                return response
            retry += 1
            delay = _retry_delay(retry, response.headers.get("retry-after"))
            _log_retry(retry, self._max_retries, f"HTTP {response.status_code}", delay)
            await response.aclose()
            await _async_sleep(delay)


def bounded_sdk_client(
    model: ChatOpenRouter,
    config: AgentConfig,
    *,
    transport: httpx.BaseTransport | None = None,
    async_transport: httpx.AsyncBaseTransport | None = None,
) -> openrouter.OpenRouter:
    """Build the SDK client with a finite HTTP timeout and a counted retry policy.

    ``ChatOpenRouter`` maps ``max_retries=N`` to an N x 150 s SDK backoff
    window (``0`` falls back to the SDK's 60-minute default) and leaves the
    HTTP timeout unset, so the factory supplies its own client. SDK retries
    are disabled; the httpx clients above retry instead. Attribution headers
    match the integration's. Transports exist only for offline tests.
    """
    headers: dict[str, str] = {}
    if model.app_url:
        headers["HTTP-Referer"] = model.app_url
    if model.app_title:
        headers["X-Title"] = model.app_title
    if model.app_categories:
        headers["X-OpenRouter-Categories"] = ",".join(model.app_categories)
    retries = max(0, config.llm_max_retries)
    return openrouter.OpenRouter(
        api_key=model.openrouter_api_key.get_secret_value(),
        server_url=model.openrouter_api_base,
        client=_RetryingClient(
            max_retries=retries, headers=headers, follow_redirects=True, transport=transport,
        ),
        async_client=_RetryingAsyncClient(
            max_retries=retries, headers=headers, follow_redirects=True, transport=async_transport,
        ),
        retry_config=None,  # Explicit None disables SDK retries; UNSET would not.
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
