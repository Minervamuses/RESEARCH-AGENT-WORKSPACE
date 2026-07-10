"""Tests for the legacy citation runtime's OpenRouter probe.

The interactive CLI no longer requires a working LLM (expansion is lazy and
optional); these cover the legacy build_runtime helper until it is removed.
"""

import asyncio
from types import SimpleNamespace

import pytest

from citation import runtime as citation_runtime
from citation.runtime import OpenRouterUnavailable


def _quiet_env(monkeypatch):
    """Keep build_runtime hermetic: no .env loading during tests."""
    monkeypatch.setattr(citation_runtime, "_load_env", lambda: None)


class _ProbeFailLLM:
    async def ainvoke(self, messages):
        raise RuntimeError("model not found: bogus/model")


class _ProbeOkLLM:
    def __init__(self):
        self.probe_messages: list = []

    async def ainvoke(self, messages):
        self.probe_messages.append(messages)
        return SimpleNamespace(content="OK")


def test_build_runtime_fails_fast_when_model_cannot_be_built(monkeypatch):
    _quiet_env(monkeypatch)

    def boom(config):
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    monkeypatch.setattr("agent.llm.get_chat_model", boom)

    with pytest.raises(OpenRouterUnavailable, match="OPENROUTER_API_KEY is not set"):
        asyncio.run(citation_runtime.build_runtime(load_mcp=False))


def test_build_runtime_fails_fast_when_probe_call_fails(monkeypatch):
    _quiet_env(monkeypatch)
    monkeypatch.setattr("agent.llm.get_chat_model", lambda config: _ProbeFailLLM())

    with pytest.raises(OpenRouterUnavailable, match="probe call failed"):
        asyncio.run(citation_runtime.build_runtime(load_mcp=False))


def test_build_runtime_probes_once_and_keeps_the_model(monkeypatch):
    _quiet_env(monkeypatch)
    llm = _ProbeOkLLM()
    monkeypatch.setattr("agent.llm.get_chat_model", lambda config: llm)

    runtime = asyncio.run(citation_runtime.build_runtime(load_mcp=False))

    assert runtime.llm is llm
    assert len(llm.probe_messages) == 1
