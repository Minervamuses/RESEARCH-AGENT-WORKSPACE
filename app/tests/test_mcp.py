"""Tests for MCP loader behavior and MCP-aware session startup."""

import asyncio

import pytest

from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from agent import mcp as mcp_module


def _clear_mcp_env(monkeypatch):
    for key in [
        "MAX_CONTENT_LENGTH",
        "DEFAULT_TIMEOUT",
        "MAX_CONCURRENT_PAGES",
        "MAX_CONCURRENT_HTTP",
        "BROWSER_HEADLESS",
        "AGENT_ENABLE_MCP_WEB_SEARCH",
        "AGENT_MCP_WEB_SEARCH_COMMAND",
        "AGENT_MCP_WEB_SEARCH_ARGS",
        "AGENT_ENABLE_MCP_GITHUB",
        "AGENT_MCP_GITHUB_COMMAND",
        "AGENT_MCP_GITHUB_ARGS",
        "AGENT_MCP_GITHUB_TOOLSETS",
        "GITHUB_PERSONAL_ACCESS_TOKEN",
    ]:
        monkeypatch.delenv(key, raising=False)


def _install_default_web_search(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_module, "find_app_root", lambda: tmp_path)
    entrypoint = tmp_path / "vendor/web-search-mcp/dist/index.js"
    entrypoint.parent.mkdir(parents=True)
    entrypoint.write_text("// test server", encoding="utf-8")
    monkeypatch.setattr(mcp_module.shutil, "which", lambda name: "/usr/bin/node")
    return entrypoint


def test_resolve_mcp_specs_defaults_to_vendored_web_search_build(
    monkeypatch, tmp_path
):
    _clear_mcp_env(monkeypatch)
    entrypoint = _install_default_web_search(tmp_path, monkeypatch)

    specs = mcp_module.resolve_mcp_specs()

    assert specs == [
        mcp_module.MCPServerSpec(
            name="web_search",
            command="/usr/bin/node",
            args=[str(entrypoint)],
            env={},
        )
    ]


def test_resolve_mcp_specs_skips_missing_default_web_search(
    monkeypatch, tmp_path, caplog
):
    _clear_mcp_env(monkeypatch)
    monkeypatch.setattr(mcp_module, "find_app_root", lambda: tmp_path)
    monkeypatch.setattr(mcp_module.shutil, "which", lambda name: "/usr/bin/node")

    diagnostics = []
    specs = mcp_module.resolve_mcp_specs(diagnostics=diagnostics)

    assert specs == []
    assert "entrypoint/node" in diagnostics[0]
    assert "enabled by default" in caplog.text
    assert "app/vendor/web-search-mcp" in caplog.text


def test_resolve_mcp_specs_allows_explicit_web_search_disable(
    monkeypatch, tmp_path
):
    _clear_mcp_env(monkeypatch)
    _install_default_web_search(tmp_path, monkeypatch)
    monkeypatch.setenv("AGENT_ENABLE_MCP_WEB_SEARCH", "0")

    assert mcp_module.resolve_mcp_specs() == []


def test_resolve_mcp_specs_web_search(monkeypatch):
    _clear_mcp_env(monkeypatch)
    monkeypatch.setenv("AGENT_ENABLE_MCP_WEB_SEARCH", "true")
    monkeypatch.setenv("AGENT_MCP_WEB_SEARCH_COMMAND", "npx")
    monkeypatch.setenv("AGENT_MCP_WEB_SEARCH_ARGS", "-y web-search-mcp@latest")
    specs = mcp_module.resolve_mcp_specs()
    assert len(specs) == 1
    spec = specs[0]
    assert spec.name == "web_search"
    assert spec.command == "npx"
    assert spec.args == ["-y", "web-search-mcp@latest"]
    assert spec.env == {}


def test_resolve_mcp_specs_github_carries_token_and_toolsets(monkeypatch):
    _clear_mcp_env(monkeypatch)
    monkeypatch.setenv("AGENT_ENABLE_MCP_WEB_SEARCH", "0")
    monkeypatch.setenv("AGENT_ENABLE_MCP_GITHUB", "yes")
    monkeypatch.setenv("AGENT_MCP_GITHUB_COMMAND", "/opt/github-mcp-server")
    monkeypatch.setenv("AGENT_MCP_GITHUB_ARGS", "stdio")
    monkeypatch.setenv("AGENT_MCP_GITHUB_TOOLSETS", "repos,pull_requests")
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ghp_test")
    specs = mcp_module.resolve_mcp_specs()
    assert len(specs) == 1
    spec = specs[0]
    assert spec.name == "github"
    assert spec.command == "/opt/github-mcp-server"
    assert spec.args == ["stdio"]
    assert spec.env == {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_test",
        "GITHUB_TOOLSETS": "repos,pull_requests",
    }


def test_resolve_mcp_specs_both_servers(monkeypatch):
    _clear_mcp_env(monkeypatch)
    monkeypatch.setenv("AGENT_ENABLE_MCP_WEB_SEARCH", "1")
    monkeypatch.setenv("AGENT_MCP_WEB_SEARCH_COMMAND", "npx")
    monkeypatch.setenv("AGENT_ENABLE_MCP_GITHUB", "1")
    monkeypatch.setenv("AGENT_MCP_GITHUB_COMMAND", "gh-mcp")
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ghp_test")
    specs = mcp_module.resolve_mcp_specs()
    names = {spec.name for spec in specs}
    assert names == {"web_search", "github"}


def test_load_mcp_tools_with_families_empty_without_specs():
    tools, families = asyncio.run(mcp_module.load_mcp_tools_with_families(specs=[]))
    assert tools == []
    assert families == {}


def test_load_mcp_tools_with_families_skips_failing_server(monkeypatch):
    @tool("web_fetch")
    def fake_web(url: str) -> str:
        """Fake web search tool."""
        return url

    async def ok_get_tools(self, *, server_name=None):
        return [fake_web]

    async def bad_get_tools(self, *, server_name=None):
        raise RuntimeError("mcp server crashed")

    class FakeClient:
        def __init__(self, connections=None, **_kwargs):
            self.connections = connections
            server = next(iter(connections.keys()))
            if server == "github":
                self.get_tools = bad_get_tools.__get__(self, FakeClient)
            else:
                self.get_tools = ok_get_tools.__get__(self, FakeClient)

    import langchain_mcp_adapters.client as client_module
    monkeypatch.setattr(client_module, "MultiServerMCPClient", FakeClient)

    specs = [
        mcp_module.MCPServerSpec(name="web_search", command="x", args=[], env={}),
        mcp_module.MCPServerSpec(name="github", command="y", args=[], env={}),
    ]
    diagnostics = []
    tools, families = asyncio.run(
        mcp_module.load_mcp_tools_with_families(specs=specs, diagnostics=diagnostics)
    )
    assert "load: RuntimeError: mcp server crashed" in diagnostics[0]
    assert len(tools) == 1
    assert tools[0].name == "web_fetch"
    assert families == {"web_fetch": "web_search"}


def test_load_mcp_tools_with_families_maps_loaded_tools(monkeypatch):
    @tool("web_fetch")
    def fake_web(url: str) -> str:
        """Fake web search tool."""
        return url

    @tool("github_repo")
    def fake_github(repo: str) -> str:
        """Fake GitHub tool."""
        return repo

    async def get_tools(self, *, server_name=None):
        server = next(iter(self.connections.keys()))
        return [fake_web] if server == "web_search" else [fake_github]

    class FakeClient:
        def __init__(self, connections=None, **_kwargs):
            self.connections = connections
            self.get_tools = get_tools.__get__(self, FakeClient)

    import langchain_mcp_adapters.client as client_module
    monkeypatch.setattr(client_module, "MultiServerMCPClient", FakeClient)

    specs = [
        mcp_module.MCPServerSpec(name="web_search", command="x", args=[], env={}),
        mcp_module.MCPServerSpec(name="github", command="y", args=[], env={}),
    ]
    tools, families = asyncio.run(mcp_module.load_mcp_tools_with_families(specs=specs))

    assert [tool.name for tool in tools] == ["web_fetch", "github_repo"]
    assert families == {"web_fetch": "web_search", "github_repo": "github"}


def test_two_dropins_with_same_tool_are_both_excluded(monkeypatch):
    @tool("shared_tool")
    def shared_tool(value: str) -> str:
        """A tool name claimed by two drop-in servers."""
        return value

    class FakeClient:
        def __init__(self, connections=None, **_kwargs):
            self.connections = connections

        async def get_tools(self):
            return [shared_tool]

    import langchain_mcp_adapters.client as client_module
    monkeypatch.setattr(client_module, "MultiServerMCPClient", FakeClient)
    diagnostics: list[str] = []
    specs = [
        mcp_module.MCPServerSpec(
            name="alpha",
            family="alpha",
            command="x",
            args=[],
            env={},
            dropin=True,
        ),
        mcp_module.MCPServerSpec(
            name="beta",
            family="beta",
            command="y",
            args=[],
            env={},
            dropin=True,
        ),
    ]

    tools, families = asyncio.run(
        mcp_module.load_mcp_tools_with_families(
            specs=specs,
            diagnostics=diagnostics,
        )
    )

    assert tools == []
    assert families == {}
    assert len(diagnostics) == 2
    assert all("tool shared_tool" in item for item in diagnostics)


def test_builtin_server_wins_tool_collision_with_dropin(monkeypatch):
    @tool("shared_tool")
    def shared_tool(value: str) -> str:
        """A tool name shared with an attempted drop-in."""
        return value

    class FakeClient:
        def __init__(self, connections=None, **_kwargs):
            self.connections = connections

        async def get_tools(self):
            return [shared_tool]

    import langchain_mcp_adapters.client as client_module
    monkeypatch.setattr(client_module, "MultiServerMCPClient", FakeClient)
    diagnostics: list[str] = []
    specs = [
        mcp_module.MCPServerSpec(
            name="legacy",
            command="x",
            args=[],
            env={},
        ),
        mcp_module.MCPServerSpec(
            name="dropin",
            family="dropin",
            command="y",
            args=[],
            env={},
            dropin=True,
        ),
    ]

    tools, families = asyncio.run(
        mcp_module.load_mcp_tools_with_families(
            specs=specs,
            diagnostics=diagnostics,
        )
    )

    assert [item.name for item in tools] == ["shared_tool"]
    assert families == {"shared_tool": "legacy"}
    assert diagnostics == ["mcp:dropin: collision: tool shared_tool"]


def test_session_create_without_mcp(monkeypatch, tmp_path):
    from agent.session import ChatSession
    from agent.config import AgentConfig

    class DummyModel:
        def bind_tools(self, _tools):
            return self

        def invoke(self, _messages):
            return AIMessage(content="ok")

    @tool("rag_explore")
    def fake_explore() -> str:
        """e"""
        return "explore"

    @tool("rag_search")
    def fake_search(query: str) -> str:
        """s"""
        return query

    @tool("rag_get_context")
    def fake_context(pid: str, chunk_id: int) -> str:
        """c"""
        return f"{pid}:{chunk_id}"

    monkeypatch.setattr("agent.graph.get_chat_model", lambda _c: DummyModel())
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools",
        lambda _c: [fake_explore, fake_search, fake_context],
    )

    cfg = AgentConfig(persist_dir=str(tmp_path))
    session = asyncio.run(ChatSession.create(cfg, load_mcp=False))
    assert session is not None
    assert session.recent_turns == []


def test_session_create_loads_mcp_tools(monkeypatch, tmp_path):
    from agent.session import ChatSession
    from agent.config import AgentConfig

    @tool("web_fetch")
    def fake_web(url: str) -> str:
        """fake mcp tool"""
        return url

    @tool("rag_explore")
    def fake_explore() -> str:
        """e"""
        return "explore"

    @tool("rag_search")
    def fake_search(query: str) -> str:
        """s"""
        return query

    @tool("rag_get_context")
    def fake_context(pid: str, chunk_id: int) -> str:
        """c"""
        return f"{pid}:{chunk_id}"

    seen_tools: dict = {}

    def capture_bind(tools):
        seen_tools["bound"] = tools

        class M:
            def invoke(self, _m):
                return AIMessage(content="ok")

        return M()

    class DummyModel:
        def bind_tools(self, tools):
            return capture_bind(tools)

    monkeypatch.setattr("agent.graph.get_chat_model", lambda _c: DummyModel())
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools",
        lambda _c: [fake_explore, fake_search, fake_context],
    )
    async def fake_load(**_kwargs):
        return [fake_web], {"web_fetch": "web_search"}

    monkeypatch.setattr("agent.mcp.load_mcp_tools_with_families", fake_load)

    cfg = AgentConfig(persist_dir=str(tmp_path))
    session = asyncio.run(ChatSession.create(cfg, load_mcp=True))
    bound_names = [t.name for t in seen_tools["bound"]]
    assert bound_names == [
        "rag_explore",
        "rag_search",
        "rag_get_context",
        "read_file",
        "bash",
        "web_fetch",
    ]
    assert session is not None


def test_session_create_survives_mcp_failure(monkeypatch, tmp_path):
    from agent.session import ChatSession
    from agent.config import AgentConfig

    @tool("rag_explore")
    def fake_explore() -> str:
        """e"""
        return "explore"

    @tool("rag_search")
    def fake_search(query: str) -> str:
        """s"""
        return query

    @tool("rag_get_context")
    def fake_context(pid: str, chunk_id: int) -> str:
        """c"""
        return f"{pid}:{chunk_id}"

    seen: dict = {}

    class DummyModel:
        def bind_tools(self, tools):
            seen["bound"] = tools

            class M:
                def invoke(self, _m):
                    return AIMessage(content="ok")

            return M()

    monkeypatch.setattr("agent.graph.get_chat_model", lambda _c: DummyModel())
    monkeypatch.setattr(
        "agent.tools.inventory.create_rag_tools",
        lambda _c: [fake_explore, fake_search, fake_context],
    )
    async def failing_load(**_kwargs):
        raise RuntimeError("mcp unavailable")

    monkeypatch.setattr("agent.mcp.load_mcp_tools_with_families", failing_load)

    cfg = AgentConfig(persist_dir=str(tmp_path))
    session = asyncio.run(ChatSession.create(cfg, load_mcp=True))
    assert session is not None
    # Only local agent tools bound (RAG + read_file + bash); MCP load failed.
    assert [t.name for t in seen["bound"]] == [
        "rag_explore",
        "rag_search",
        "rag_get_context",
        "read_file",
        "bash",
    ]


def test_web_search_passes_only_supported_settings_to_both_commands(monkeypatch, tmp_path):
    _clear_mcp_env(monkeypatch)
    _install_default_web_search(tmp_path, monkeypatch)
    expected = {
        "MAX_CONTENT_LENGTH": "37", "DEFAULT_TIMEOUT": "9000",
        "MAX_CONCURRENT_PAGES": "1", "MAX_CONCURRENT_HTTP": "2", "BROWSER_HEADLESS": "false",
    }
    for key, value in expected.items():
        monkeypatch.setenv(key, value)
    for key in ("TMPDIR", "HTTPS_PROXY", "OTHER_PROVIDER_SECRET", "ENABLE_RELEVANCE_CHECKING", "DEBUG_BING_SEARCH"):
        monkeypatch.setenv(key, "must-not-forward")
    assert mcp_module._web_search_spec().env == expected
    monkeypatch.setenv("AGENT_MCP_WEB_SEARCH_COMMAND", "custom-server")
    monkeypatch.setenv("AGENT_MCP_WEB_SEARCH_ARGS", "--custom")
    spec = mcp_module._web_search_spec()
    assert spec.env == expected
    assert spec.command == "custom-server"
    assert spec.args == ["--custom"]
    monkeypatch.setenv("MAX_CONTENT_LENGTH", "invalid")
    monkeypatch.setenv("AGENT_ENABLE_MCP_WEB_SEARCH", "false")
    assert mcp_module._web_search_spec() is None


@pytest.mark.parametrize(("name", "value"), [
    ("MAX_CONTENT_LENGTH", "10001"), ("DEFAULT_TIMEOUT", "300001"),
    ("MAX_CONCURRENT_PAGES", "0"), ("MAX_CONCURRENT_HTTP", "2junk"), ("BROWSER_HEADLESS", "yes"),
])
def test_web_search_rejects_invalid_settings(monkeypatch, name, value):
    _clear_mcp_env(monkeypatch)
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=name):
        mcp_module._web_search_spec()


def test_resolvers_fail_independently_with_stage_diagnostics(monkeypatch):
    def broken():
        raise ValueError("app root unavailable")
    healthy = mcp_module.MCPServerSpec("helper", "helper", [], {})
    monkeypatch.setattr(mcp_module, "_web_search_spec", broken)
    monkeypatch.setattr(mcp_module, "_github_spec", lambda: healthy)
    diagnostics = []
    assert mcp_module.resolve_mcp_specs(diagnostics=diagnostics) == [healthy]
    assert diagnostics == ["mcp:web_search: resolve: ValueError: app root unavailable"]


def test_connection_preparation_failure_keeps_other_server(monkeypatch):
    @tool("healthy_fetch")
    def healthy_fetch(query: str) -> str:
        """Healthy MCP."""
        return query

    def prepare(spec):
        if spec.name == "broken":
            raise PermissionError("log directory unwritable")
        return {"transport": "stdio", "command": spec.command}

    class FakeClient:
        def __init__(self, connections=None, **_kwargs):
            pass
        async def get_tools(self):
            return [healthy_fetch]

    import langchain_mcp_adapters.client as client_module
    monkeypatch.setattr(client_module, "MultiServerMCPClient", FakeClient)
    monkeypatch.setattr(mcp_module, "_spec_to_connection", prepare)
    diagnostics = []
    specs = [mcp_module.MCPServerSpec(name, name, [], {}) for name in ("broken", "healthy")]
    tools, families = asyncio.run(mcp_module.load_mcp_tools_with_families(
        specs=specs, diagnostics=diagnostics,
    ))
    assert [item.name for item in tools] == ["healthy_fetch"]
    assert families == {"healthy_fetch": "healthy"}
    assert "prepare: PermissionError: log directory unwritable" in diagnostics[0]


@pytest.mark.parametrize("with_extension", [False, True])
def test_startup_keeps_local_and_healthy_tools_and_diagnostics(monkeypatch, tmp_path, with_extension):
    from types import SimpleNamespace
    from conftest import make_astream_graph
    from agent.config import AgentConfig
    from agent.session import ChatSession

    @tool("healthy_fetch")
    def healthy_fetch(query: str) -> str:
        """Healthy MCP."""
        return query

    @tool("extension_fetch")
    def extension_fetch(query: str) -> str:
        """Extension MCP."""
        return query

    def broken():
        raise RuntimeError("resolver failed")
    healthy = mcp_module.MCPServerSpec("healthy", "healthy", [], {})
    dropin = mcp_module.MCPServerSpec("extension", "extension", [], {}, dropin=True)
    monkeypatch.setattr(mcp_module, "_web_search_spec", broken)
    monkeypatch.setattr(mcp_module, "_github_spec", lambda: healthy)
    monkeypatch.setattr("agent.extensions.startup.load_extension_startup", lambda *_args, **_kwargs: SimpleNamespace(
        skills=[], diagnostics=(), mcp_specs=[dropin] if with_extension else [],
        global_mcp_families={"healthy", "extension"}, revision=0,
    ))
    monkeypatch.setattr("agent.session.build_graph", lambda *_args, **_kwargs: make_astream_graph())
    class FakeClient:
        def __init__(self, connections=None, **_kwargs):
            self.name = next(iter(connections))
        async def get_tools(self):
            return [extension_fetch] if self.name == "extension" else [healthy_fetch]
    import langchain_mcp_adapters.client as client_module
    monkeypatch.setattr(client_module, "MultiServerMCPClient", FakeClient)
    session = asyncio.run(ChatSession.create(AgentConfig(persist_dir=str(tmp_path/"persist"))))
    expected = ["healthy_fetch", "extension_fetch"] if with_extension else ["healthy_fetch"]
    assert [item.name for item in session.extra_tools] == expected
    effective = session.tool_access_resolution().effective_tools
    assert {"read_file", "bash", "rag_search", "healthy_fetch"}.issubset(effective)
    assert any("web_search: resolve: RuntimeError: resolver failed" in item
               for item in session.extension_startup_diagnostics)


def _lifecycle_server(tmp_path, mode):
    import sys

    source = tmp_path / "lifecycle_server.py"
    pid_file = tmp_path / "lifecycle.pid"
    source.write_text(
        """
import json, os, signal, sys, time
from pathlib import Path
mode, pid_file = sys.argv[1:]
fields = Path(f"/proc/{os.getpid()}/stat").read_text().split(") ", 1)[1].split()
Path(pid_file).write_text(f"{os.getpid()} {os.getpgrp()} {fields[19]}")
signal.signal(signal.SIGTERM, lambda *_args: None)
if mode == "startup": time.sleep(2)
called = False
for line in sys.stdin:
    message = json.loads(line)
    if "id" not in message: continue
    method = message["method"]
    if method == "initialize":
        if mode == "initialize": time.sleep(2)
        if mode == "meta": time.sleep(.05)
        result = {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}}, "serverInfo": {"name": "local", "version": "1"}}
    elif method == "tools/list":
        result = {"tools": [{"name": "local_probe", "inputSchema": {"type": "object", "properties": {}}}]}
    else:
        called = True
        if mode == "tool": time.sleep(2)
        if mode == "tool_error":
            print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32602, "message": "explicit invalid argument"}}), flush=True)
            continue
        text = json.dumps(message["params"].get("_meta", {})) if mode == "meta" else "known result"
        result = {"content": [{"type": "text", "text": text}]}
    print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}), flush=True)
if called and mode == "close": time.sleep(2)
""",
        encoding="utf-8",
    )
    return {"transport": "stdio", "command": sys.executable, "args": [str(source), mode, str(pid_file)]}, pid_file


def _assert_lifecycle_pid_gone(pid_file):
    from pathlib import Path

    pid, group, started = pid_file.read_text().split()
    stat = Path(f"/proc/{pid}/stat")
    if stat.exists():
        fields = stat.read_text().split(") ", 1)[1].split()
        assert fields[19] != started or fields[0] == "Z", f"live child {pid}, pgid {group}"


@pytest.mark.parametrize("mode", ["startup", "initialize", "tool", "close", "meta"])
def test_web_search_real_session_budget_and_cleanup(tmp_path, mode):
    import json
    import time

    connection, pid_file = _lifecycle_server(tmp_path, mode)
    async def run():
        started = time.monotonic()
        if mode in ("startup", "initialize"):
            with pytest.raises(TimeoutError, match="before a result"):
                await mcp_module._load_web_search_tools(connection, 800)
        else:
            tools = await mcp_module._load_web_search_tools(connection, 800)
            started = time.monotonic()
            if mode == "tool":
                with pytest.raises(TimeoutError, match="before a result"):
                    await tools[0].ainvoke({})
            else:
                response = await tools[0].ainvoke({})
                text = response if isinstance(response, str) else response[0]["text"]
                if mode == "close":
                    assert text == "known result"
                else:
                    assert 0 < json.loads(text)["web_search_work_ms"] < 350
        elapsed = time.monotonic() - started
        assert elapsed < .8, elapsed
        _assert_lifecycle_pid_gone(pid_file)
        assert not [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
    asyncio.run(run())


def test_web_search_cancellation_during_cleanup_is_bounded(tmp_path, caplog):
    import logging
    import time

    connection, pid_file = _lifecycle_server(tmp_path, "close")
    async def run():
        tools = await mcp_module._load_web_search_tools(connection, 800)
        started = time.monotonic()
        task = asyncio.create_task(tools[0].ainvoke({}))
        await asyncio.sleep(.15)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert time.monotonic() - started < .8
        _assert_lifecycle_pid_gone(pid_file)
    with caplog.at_level(logging.INFO, logger="agent.mcp"):
        asyncio.run(run())
    assert "result_received=True" in caplog.text


def test_web_search_preserves_protocol_error_message(tmp_path):
    connection, pid_file = _lifecycle_server(tmp_path, "tool_error")
    async def run():
        tools = await mcp_module._load_web_search_tools(connection, 800)
        with pytest.raises(Exception, match="explicit invalid argument"):
            await tools[0].ainvoke({})
        _assert_lifecycle_pid_gone(pid_file)
    asyncio.run(run())
