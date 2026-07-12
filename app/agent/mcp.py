"""MCP client loader for the agent.

Resolves MCP server launch specs and asks ``langchain_mcp_adapters`` to load
the merged tool list asynchronously. Web Search is a default capability when
its standard local installation is present; environment variables are only
optional runtime overrides (or an explicit disable), not an activation
requirement.

If an MCP server is disabled, missing, or misconfigured, the rest of the agent
still works with the local KB tools only.
"""

from __future__ import annotations

import logging
import os
import shlex
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Per-server stderr log policy: files are created 0600 before the server
# starts, rotate at 5 MiB keeping 3 rotated copies, and every run appends a
# timestamp/run-ID header so interleaved runs stay attributable.
MCP_LOG_MAX_BYTES = 5 * 1024 * 1024
MCP_LOG_KEEP_ROTATED = 3


@dataclass(frozen=True)
class MCPServerSpec:
    """Resolved stdio MCP server launch spec."""

    name: str
    command: str
    args: list[str]
    env: dict[str, str]


def _parse_args(raw: str | None) -> list[str]:
    if not raw:
        return []
    return shlex.split(raw)


def _env_flag(name: str, *, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _default_web_search_entrypoint() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME")
    root = Path(data_home).expanduser() if data_home else Path.home() / ".local/share"
    return root / "mcp-servers/web-search-mcp/dist/index.js"


def _web_search_spec() -> MCPServerSpec | None:
    if not _env_flag("AGENT_ENABLE_MCP_WEB_SEARCH", default=True):
        return None

    command = os.environ.get("AGENT_MCP_WEB_SEARCH_COMMAND", "").strip()
    if command:
        return MCPServerSpec(
            name="web_search",
            command=command,
            args=_parse_args(os.environ.get("AGENT_MCP_WEB_SEARCH_ARGS")),
            env={},
        )

    entrypoint = _default_web_search_entrypoint()
    node = shutil.which("node")
    if not entrypoint.is_file() or node is None:
        missing = []
        if not entrypoint.is_file():
            missing.append(f"entrypoint {entrypoint}")
        if node is None:
            missing.append("node executable on PATH")
        logger.warning(
            "Web Search MCP is enabled by default but %s is missing; "
            "skipping it. Set AGENT_ENABLE_MCP_WEB_SEARCH=0 to disable it "
            "explicitly, or install the server in the standard user-data path.",
            " and ".join(missing),
        )
        return None
    return MCPServerSpec(
        name="web_search",
        command=node,
        args=[str(entrypoint)],
        env={},
    )


def _github_spec() -> MCPServerSpec | None:
    if not _env_flag("AGENT_ENABLE_MCP_GITHUB", default=False):
        return None
    command = os.environ.get("AGENT_MCP_GITHUB_COMMAND")
    if not command:
        logger.warning(
            "AGENT_ENABLE_MCP_GITHUB is set but AGENT_MCP_GITHUB_COMMAND is empty; "
            "skipping GitHub MCP."
        )
        return None
    token = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN", "")
    if not token:
        logger.warning(
            "AGENT_ENABLE_MCP_GITHUB is set but GITHUB_PERSONAL_ACCESS_TOKEN is empty; "
            "GitHub MCP will start without auth and likely refuse most calls."
        )
    toolsets = os.environ.get(
        "AGENT_MCP_GITHUB_TOOLSETS",
        "repos,pull_requests,issues,actions,context",
    )
    env = {
        "GITHUB_PERSONAL_ACCESS_TOKEN": token,
        "GITHUB_TOOLSETS": toolsets,
    }
    return MCPServerSpec(
        name="github",
        command=command,
        args=_parse_args(os.environ.get("AGENT_MCP_GITHUB_ARGS")),
        env=env,
    )


def resolve_mcp_specs() -> list[MCPServerSpec]:
    """Collect default and explicitly configured MCP server launch specs."""
    specs = []
    for resolver in (_web_search_spec, _github_spec):
        spec = resolver()
        if spec is not None:
            specs.append(spec)
    return specs


def _mcp_log_dir() -> str:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    path = os.path.join(base, "agent-mcp")
    os.makedirs(path, exist_ok=True)
    return path


def _rotate_log(log_path: str) -> None:
    """Shift log -> log.1 -> ... -> log.N, dropping the oldest."""
    oldest = f"{log_path}.{MCP_LOG_KEEP_ROTATED}"
    if os.path.exists(oldest):
        os.unlink(oldest)
    for index in range(MCP_LOG_KEEP_ROTATED - 1, 0, -1):
        source = f"{log_path}.{index}"
        if os.path.exists(source):
            os.rename(source, f"{log_path}.{index + 1}")
    if os.path.exists(log_path):
        os.rename(log_path, f"{log_path}.1")


def prepare_stderr_log(log_path: str, *, run_id: str | None = None) -> str:
    """Create/rotate one server's stderr log before the server starts.

    The file exists with mode 0600 before any subprocess writes to it,
    rotates at 5 MiB (keeping 3 rotated copies), and starts each run with a
    timestamp/run-ID header. Returns the run ID for logging.
    """
    run_id = run_id or uuid.uuid4().hex[:12]
    try:
        if (
            os.path.exists(log_path)
            and os.path.getsize(log_path) >= MCP_LOG_MAX_BYTES
        ):
            _rotate_log(log_path)
        fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            header = (
                f"=== mcp run {run_id} started "
                f"{datetime.now(timezone.utc).isoformat()} ===\n"
            )
            os.write(fd, header.encode("utf-8"))
        finally:
            os.close(fd)
    except OSError as exc:
        logger.warning("could not prepare MCP stderr log %s: %s", log_path, exc)
    return run_id


def _spec_to_connection(spec: MCPServerSpec) -> dict:
    # Some MCP servers (notably mrkrsl/web-search-mcp) are careless about
    # what they write to stdout: startup banners, shutdown notices, etc.
    # The stdio transport then tries to JSON-parse those lines and, on
    # shutdown, the resulting ValidationError races against stream close
    # and surfaces as an ExceptionGroup[BrokenResourceError] inside the
    # tool call. Fix it at the subprocess level:
    #   1. stderr goes to a per-server log file (so we can still debug).
    #   2. stdout passes through grep that only forwards lines starting
    #      with '{' — JSON-RPC messages are always JSON objects, so this
    #      is a safe filter that drops every free-form stdout print.
    inner = shlex.join([spec.command, *spec.args])
    log_path = os.path.join(_mcp_log_dir(), f"{spec.name}.stderr.log")
    prepare_stderr_log(log_path)
    pipeline = (
        f"{inner} 2>>{shlex.quote(log_path)} "
        f"| grep --line-buffered '^{{'"
    )
    conn: dict = {
        "transport": "stdio",
        "command": "/bin/sh",
        "args": ["-c", pipeline],
    }
    if spec.env:
        conn["env"] = dict(spec.env)
    return conn


async def load_mcp_tools(specs: list[MCPServerSpec] | None = None) -> list:
    """Start the configured MCP servers and return the merged LangChain tool list.

    Failures from any single server are logged and that server is skipped;
    tools from surviving servers are still returned.
    """
    tools, _families = await load_mcp_tools_with_families(specs=specs)
    return tools


async def load_mcp_tools_with_families(
    specs: list[MCPServerSpec] | None = None,
) -> tuple[list, dict[str, str]]:
    """Load MCP tools and return a tool-name to server-family map."""
    if specs is None:
        specs = resolve_mcp_specs()
    if not specs:
        return [], {}

    # Some upstream MCP servers (e.g. mrkrsl/web-search-mcp) print banners
    # on stdout instead of stderr. The stdio client logs each non-JSON line
    # as an exception; silence that channel so user-facing output stays clean.
    logging.getLogger("mcp.client.stdio").setLevel(logging.CRITICAL)

    from langchain_mcp_adapters.client import MultiServerMCPClient

    tools: list = []
    families: dict[str, str] = {}
    for spec in specs:
        connections = {spec.name: _spec_to_connection(spec)}
        try:
            client = MultiServerMCPClient(connections=connections)
            server_tools = await client.get_tools()
        except Exception as exc:
            logger.warning("MCP server %r failed to load: %s", spec.name, exc)
            continue
        tools.extend(server_tools)
        for tool in server_tools:
            tool_name = getattr(tool, "name", None)
            if tool_name:
                families[tool_name] = spec.name
    return tools, families
