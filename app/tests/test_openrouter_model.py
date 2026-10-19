"""Tests for LangChain LLM model factories."""

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from langchain_core.messages import HumanMessage
from openrouter.errors import OpenRouterError

from agent.config import AgentConfig
from agent.llm import openrouter
from agent.llm.openrouter import get_chat_model, get_openrouter_chat_model
from agent.llm.text import invoke_text


def test_default_main_model_is_pinned(tmp_path):
    cfg = AgentConfig(persist_dir=str(tmp_path))

    assert cfg.llm_model == "google/gemini-3.8-flash"


def test_get_chat_model_uses_main_model_and_configured_token_limit(monkeypatch, tmp_path):
    calls: list[dict] = []

    class FakeChatOpenRouter:
        def __init__(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(openrouter, "ChatOpenRouter", FakeChatOpenRouter)
    monkeypatch.setattr(openrouter, "bounded_sdk_client", lambda _model, _config: None)
    cfg = AgentConfig(
        persist_dir=str(tmp_path),
        llm_model="deepseek/deepseek-v4-pro",
        llm_max_tokens=4096,
    )

    get_chat_model(cfg)

    assert calls[0]["model"] == "deepseek/deepseek-v4-pro"
    assert calls[0]["max_tokens"] == 4096


def test_get_chat_model_delegates_retries_to_client(monkeypatch, tmp_path):
    calls: list[dict] = []

    class FakeChatOpenRouter:
        def __init__(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(openrouter, "ChatOpenRouter", FakeChatOpenRouter)
    monkeypatch.setattr(openrouter, "bounded_sdk_client", lambda _model, _config: None)
    cfg = AgentConfig(persist_dir=str(tmp_path), llm_max_retries=7)

    get_chat_model(cfg)

    assert calls[0]["max_retries"] == 7
    assert calls[0]["timeout"] == cfg.llm_request_timeout_ms == 600_000


def test_get_openrouter_chat_model_applies_eval_overrides(monkeypatch, tmp_path):
    calls: list[dict] = []

    class FakeChatOpenRouter:
        def __init__(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(openrouter, "ChatOpenRouter", FakeChatOpenRouter)
    monkeypatch.setattr(openrouter, "bounded_sdk_client", lambda _model, _config: None)
    cfg = AgentConfig(persist_dir=str(tmp_path), llm_max_retries=7)

    get_openrouter_chat_model(
        cfg,
        model_name="openai/gpt-5.2",
        max_tokens=300,
        temperature=0.0,
    )

    assert calls[0]["model"] == "openai/gpt-5.2"
    assert calls[0]["max_tokens"] == 300
    assert calls[0]["temperature"] == 0.0
    assert calls[0]["max_retries"] == 7


def test_real_chat_openrouter_accepts_factory_kwargs(monkeypatch, tmp_path):
    """Offline construction contract against the pinned integration.

    Ensures the real ChatOpenRouter class accepts everything the factory
    passes (aliases included) and exposes tool binding, without any network.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    cfg = AgentConfig(
        persist_dir=str(tmp_path),
        llm_model="deepseek/deepseek-v4-pro",
        llm_max_tokens=1234,
        llm_max_retries=7,
    )

    model = get_chat_model(cfg)

    assert model.model_name == "deepseek/deepseek-v4-pro"
    assert model.max_tokens == 1234
    assert model.max_retries == 7
    assert model.openrouter_api_base == "https://openrouter.ai/api/v1"
    assert callable(model.bind_tools)


def test_real_chat_openrouter_accepts_model_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    cfg = AgentConfig(persist_dir=str(tmp_path))

    model = get_openrouter_chat_model(
        cfg,
        model_name="openai/gpt-5.2",
        temperature=0.0,
    )

    assert model.model_name == "openai/gpt-5.2"
    assert model.temperature == 0.0


def test_invoke_text_invokes_chat_model_with_human_message():
    seen_messages = []

    class FakeResponse:
        content = "  hello  "

    class FakeModel:
        def invoke(self, messages):
            seen_messages.extend(messages)
            return FakeResponse()

    result = invoke_text(FakeModel(), "hi")

    assert result == "hello"
    assert seen_messages[0].content == "hi"


class _VirtualClock:
    """Stand in for the SDK retry loop's wall clock and sleeps; nothing waits."""

    def __init__(self):
        self.now = 1_000.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    async def async_sleep(self, seconds: float) -> None:
        self.sleep(seconds)


def _completion(content: str = "ok") -> dict:
    return {
        "id": "gen-offline", "object": "chat.completion", "created": 1, "model": "m",
        "system_fingerprint": None,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
    }


def _unavailable(**headers) -> httpx.Response:
    return httpx.Response(503, json={"error": {"code": 503, "message": "fixture outage"}}, headers=headers)


@pytest.fixture
def offline_openrouter(monkeypatch, tmp_path):
    """Real factory, ChatOpenRouter and SDK over an httpx MockTransport."""
    from openrouter.utils import retries

    clock = _VirtualClock()
    monkeypatch.setattr(retries, "time", SimpleNamespace(time=clock.time, sleep=clock.sleep))
    monkeypatch.setattr(retries, "asyncio", SimpleNamespace(sleep=clock.async_sleep))
    monkeypatch.setattr(retries, "random", SimpleNamespace(uniform=lambda _low, _high: 0.0))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    requests: list[httpx.Request] = []

    def build(responses, **overrides):
        def handler(request):
            requests.append(request)
            step = responses(request, len(requests)) if callable(responses) else responses[len(requests) - 1]
            return step

        cfg = AgentConfig(persist_dir=str(tmp_path), **overrides)
        model = get_openrouter_chat_model(cfg)
        transport = httpx.MockTransport(handler)
        model.client = openrouter.bounded_sdk_client(model, cfg, transport=transport, async_transport=transport)
        return model

    return SimpleNamespace(clock=clock, requests=requests, build=build)


@pytest.mark.parametrize("path", ["async", "sync"])
def test_persistent_503_stops_inside_the_bounded_retry_window(offline_openrouter, path):
    model = offline_openrouter.build(lambda _request, _count: _unavailable())
    start = offline_openrouter.clock.now
    with pytest.raises(OpenRouterError) as failure:
        if path == "async":
            asyncio.run(model.ainvoke([HumanMessage(content="hi")]))
        else:
            model.invoke([HumanMessage(content="hi")])

    assert failure.value.status_code == 503
    # Default llm_max_retries=4 gives a 20 s window: sleeps 1, 2, 4, 8, then one capped 8.
    assert offline_openrouter.clock.sleeps == [1.0, 2.0, 4.0, 8.0, 8.0]
    assert len(offline_openrouter.requests) == 6
    elapsed = offline_openrouter.clock.now - start
    assert elapsed == 23 <= 20 + openrouter.RETRY_MAX_INTERVAL_MS / 1000


def test_request_timeout_is_finite_milliseconds_and_not_retried_past_the_window(offline_openrouter):
    def timed_out(request, _count):
        offline_openrouter.clock.now += request.extensions["timeout"]["read"]
        raise httpx.ReadTimeout("fixture read timeout", request=request)

    model = offline_openrouter.build(timed_out, llm_request_timeout_ms=1_500)
    start = offline_openrouter.clock.now
    with pytest.raises(httpx.ReadTimeout):
        asyncio.run(model.ainvoke([HumanMessage(content="hi")]))
    assert offline_openrouter.requests[0].extensions["timeout"] == {
        "connect": 1.5, "read": 1.5, "write": 1.5, "pool": 1.5,
    }
    # Short timeouts retry only while the 20 s window is open: ends at 1.5, 4, 7.5, 13, 22.5 s.
    assert len(offline_openrouter.requests) == 5
    assert offline_openrouter.clock.now - start == 22.5 <= 20 + 8 + 1.5

    offline_openrouter.requests.clear()
    model = offline_openrouter.build(timed_out)
    with pytest.raises(httpx.ReadTimeout):
        asyncio.run(model.ainvoke([HumanMessage(content="hi")]))
    assert offline_openrouter.requests[0].extensions["timeout"]["read"] == 600.0
    assert len(offline_openrouter.requests) == 1  # A 600 s attempt already exceeds the window.


def test_long_retry_after_is_capped_and_a_later_success_keeps_usage(offline_openrouter):
    model = offline_openrouter.build([
        _unavailable(**{"retry-after": "3600"}),
        httpx.Response(200, json=_completion("recovered")),
    ])
    message = asyncio.run(model.ainvoke([HumanMessage(content="hi")]))

    assert message.content == "recovered"
    assert message.usage_metadata["input_tokens"] == 3 and message.usage_metadata["output_tokens"] == 1
    assert offline_openrouter.clock.sleeps == [8.0]
    headers = offline_openrouter.requests[0].headers
    assert headers["http-referer"] == model.app_url and headers["x-title"] == model.app_title
    assert offline_openrouter.requests[0].url.host == "openrouter.ai"


def test_one_transient_503_then_success(offline_openrouter):
    model = offline_openrouter.build([_unavailable(), httpx.Response(200, json=_completion())])
    assert model.invoke([HumanMessage(content="hi")]).content == "ok"
    assert offline_openrouter.clock.sleeps == [1.0] and len(offline_openrouter.requests) == 2


@pytest.mark.parametrize("response", [
    _unavailable(),
    httpx.Response(400, json={"error": {"code": 400, "message": "bad request"}}),
])
def test_disabled_retries_and_permanent_errors_make_one_attempt(offline_openrouter, response):
    retries = 0 if response.status_code == 503 else 4
    model = offline_openrouter.build(lambda _request, _count: response, llm_max_retries=retries)
    with pytest.raises(OpenRouterError) as failure:
        asyncio.run(model.ainvoke([HumanMessage(content="hi")]))
    assert failure.value.status_code == response.status_code
    assert len(offline_openrouter.requests) == 1 and offline_openrouter.clock.sleeps == []


def test_cancellation_stops_the_request_without_retrying(offline_openrouter):
    entered = asyncio.Event()

    async def hanging(_request, _count):
        entered.set()
        await asyncio.Event().wait()

    model = offline_openrouter.build(hanging)

    async def run():
        task = asyncio.create_task(model.ainvoke([HumanMessage(content="hi")]))
        await asyncio.wait_for(entered.wait(), 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert len(offline_openrouter.requests) == 1 and offline_openrouter.clock.sleeps == []
