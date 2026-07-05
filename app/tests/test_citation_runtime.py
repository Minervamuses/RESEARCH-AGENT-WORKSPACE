"""Tests for the citation runtime's mandatory OpenRouter chat model.

The citation CLI must fail fast (exit code 2) when the OpenRouter setup is
broken — missing/invalid key, invalid model, or a failing probe call — instead
of degrading into a fallback or pretending nothing was found.
"""

import argparse
import asyncio
from types import SimpleNamespace

import pytest

from citation import cli
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


def _cli_args(**overrides) -> argparse.Namespace:
    defaults = dict(request="find papers", limit=6, auto=False, auto_attempts=4)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_cli_exits_2_when_openrouter_is_unavailable(monkeypatch, capsys):
    async def failing_build_runtime(*, load_mcp=True):
        raise OpenRouterUnavailable("could not build the OpenRouter chat model")

    monkeypatch.setattr(cli, "build_runtime", failing_build_runtime)

    rc = asyncio.run(cli._run(_cli_args()))

    captured = capsys.readouterr()
    assert rc == 2
    assert "OPENROUTER_API_KEY" in captured.err
    assert "no LLM configured" not in captured.out


def test_cli_exits_2_when_web_search_mcp_is_missing(monkeypatch, capsys):
    async def build_runtime_without_mcp(*, load_mcp=True):
        return SimpleNamespace(llm=_ProbeOkLLM(), web_tools={})

    monkeypatch.setattr(cli, "build_runtime", build_runtime_without_mcp)

    rc = asyncio.run(cli._run(_cli_args()))

    captured = capsys.readouterr()
    assert rc == 2
    assert "Web Search MCP" in captured.err
    assert "OPENROUTER_API_KEY" not in captured.err


def _patch_ready_runtime(monkeypatch):
    async def build_ready_runtime(*, load_mcp=True):
        return SimpleNamespace(llm=_ProbeOkLLM(), web_tools={"summaries": object()})

    monkeypatch.setattr(cli, "build_runtime", build_ready_runtime)


def test_cli_exits_3_only_when_search_completed_with_no_candidates(monkeypatch, capsys):
    _patch_ready_runtime(monkeypatch)

    async def empty_discover(runtime, request, *, limit, progress_cb=None):
        return []

    monkeypatch.setattr(cli, "agentic_discover", empty_discover)

    rc = asyncio.run(cli._run(_cli_args()))

    captured = capsys.readouterr()
    assert rc == 3
    assert "No candidate papers found" in captured.err


def test_cli_exits_2_when_discovery_llm_call_fails(monkeypatch, capsys):
    from citation.discovery import OpenRouterDiscoveryError

    _patch_ready_runtime(monkeypatch)

    async def failing_discover(runtime, request, *, limit, progress_cb=None):
        raise OpenRouterDiscoveryError("discovery LLM call failed/timed out")

    monkeypatch.setattr(cli, "agentic_discover", failing_discover)

    rc = asyncio.run(cli._run(_cli_args()))

    captured = capsys.readouterr()
    assert rc == 2
    assert "OpenRouter discovery call failed" in captured.err
    assert "No candidate papers found" not in captured.err
