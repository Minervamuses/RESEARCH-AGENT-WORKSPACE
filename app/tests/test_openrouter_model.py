"""Tests for LangChain LLM model factories."""

from agent.config import AgentConfig
from agent.llm import openrouter
from agent.llm.openrouter import get_chat_model, get_openrouter_chat_model
from agent.llm.text import invoke_text


def test_get_chat_model_uses_main_model_and_configured_token_limit(monkeypatch, tmp_path):
    calls: list[dict] = []

    class FakeChatOpenRouter:
        def __init__(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(openrouter, "ChatOpenRouter", FakeChatOpenRouter)
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
    cfg = AgentConfig(persist_dir=str(tmp_path), llm_max_retries=7)

    get_chat_model(cfg)

    assert calls[0]["max_retries"] == 7


def test_get_openrouter_chat_model_applies_eval_overrides(monkeypatch, tmp_path):
    calls: list[dict] = []

    class FakeChatOpenRouter:
        def __init__(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(openrouter, "ChatOpenRouter", FakeChatOpenRouter)
    cfg = AgentConfig(persist_dir=str(tmp_path), llm_max_retries=7)

    get_openrouter_chat_model(
        cfg,
        model_name="openai/gpt-5.2",
        max_tokens=300,
        temperature=0.0,
        extra_body={"reasoning": {"enabled": False}},
    )

    assert calls[0]["model"] == "openai/gpt-5.2"
    assert calls[0]["max_tokens"] == 300
    assert calls[0]["temperature"] == 0.0
    assert calls[0]["max_retries"] == 7
    # reasoning is a first-class ChatOpenRouter field, not raw request body.
    assert calls[0]["reasoning"] == {"enabled": False}
    assert "extra_body" not in calls[0]
    assert "model_kwargs" not in calls[0]


def test_get_openrouter_chat_model_passes_unknown_body_via_model_kwargs(
    monkeypatch, tmp_path
):
    calls: list[dict] = []

    class FakeChatOpenRouter:
        def __init__(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(openrouter, "ChatOpenRouter", FakeChatOpenRouter)
    cfg = AgentConfig(persist_dir=str(tmp_path))

    get_openrouter_chat_model(
        cfg,
        extra_body={
            "reasoning": {"enabled": True},
            "transforms": ["middle-out"],
        },
    )

    assert calls[0]["reasoning"] == {"enabled": True}
    assert calls[0]["model_kwargs"] == {"transforms": ["middle-out"]}


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


def test_real_chat_openrouter_accepts_reasoning_override(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    cfg = AgentConfig(persist_dir=str(tmp_path))

    model = get_openrouter_chat_model(
        cfg,
        model_name="openai/gpt-5.2",
        temperature=0.0,
        extra_body={"reasoning": {"enabled": False}},
    )

    assert model.reasoning == {"enabled": False}
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
