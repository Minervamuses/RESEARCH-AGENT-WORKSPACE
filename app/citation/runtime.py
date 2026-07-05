"""Bridge to the host project's config, chat model, and Web Search MCP.

Everything here is a *read-only consumer* of the existing ``agent`` package:
we import its config, its chat-model factory, and its MCP loader, but never
modify them. If those abstractions change, this prototype adapts here and only
here.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger("citation.runtime")

# The three tools exposed by mrkrsl/web-search-mcp (family "web_search").
SUMMARIES_TOOL = "get-web-search-summaries"
FULL_SEARCH_TOOL = "full-web-search"
PAGE_CONTENT_TOOL = "get-single-web-page-content"
WEB_SEARCH_FAMILY = "web_search"

# One cheap round-trip that proves the key/model/API actually work before any
# discovery starts; a broken OpenRouter setup must fail here, not masquerade
# as "no candidates found" later.
_PROBE_PROMPT = "Reply with the single word: OK"
_PROBE_TIMEOUT_SECONDS = 30.0


class WebSearchUnavailable(RuntimeError):
    """Raised when the Web Search MCP family is not loaded/enabled."""


class OpenRouterUnavailable(RuntimeError):
    """Raised when the OpenRouter chat model cannot be built or probed.

    Covers a missing/invalid ``OPENROUTER_API_KEY``, an invalid model name,
    and OpenRouter rejecting or failing the probe call.
    """


@dataclass
class CitationRuntime:
    """Resolved, reusable handles for one prototype run."""

    config: object  # agent.config.AgentConfig
    llm: object  # langchain chat model (required; probed at build time)
    web_tools: dict[str, object]  # tool name -> LangChain tool
    app_root: Path

    @property
    def cite_dir(self) -> Path:
        return self.app_root / "citation" / "cite"

    def require_web_tool(self, name: str):
        tool = self.web_tools.get(name)
        if tool is None:
            raise WebSearchUnavailable(
                f"Web Search MCP tool {name!r} is not available. "
                "Enable it in .env (AGENT_ENABLE_MCP_WEB_SEARCH=1 plus the "
                "AGENT_MCP_WEB_SEARCH_COMMAND/ARGS), and make sure the MCP "
                "server starts cleanly."
            )
        return tool


def _load_env() -> None:
    """Load the host project's .env exactly like agent.cli.chat does."""
    from agent.paths import find_app_root

    env_path = find_app_root() / ".env"
    # override=False: never clobber variables already set in the real shell.
    load_dotenv(dotenv_path=env_path, override=False)


def _build_llm(config):
    """Return the host project's chat model; the citation CLI requires one.

    The LLM drives search decisions and candidate ranking/annotation (never
    BibTeX generation), so a setup that cannot build a model is a hard
    configuration error, not something to degrade around.
    """
    from agent.llm import get_chat_model

    try:
        return get_chat_model(config)
    except Exception as exc:
        raise OpenRouterUnavailable(
            f"could not build the OpenRouter chat model: {exc}"
        ) from exc


async def _probe_llm(llm) -> None:
    """Run one lightweight OpenRouter call to prove the model is usable."""
    try:
        await asyncio.wait_for(
            llm.ainvoke([("human", _PROBE_PROMPT)]),
            timeout=_PROBE_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        raise OpenRouterUnavailable(
            f"OpenRouter probe call failed: {type(exc).__name__}: {exc}"
        ) from exc


async def build_runtime(*, load_mcp: bool = True) -> CitationRuntime:
    """Assemble a :class:`CitationRuntime` using the host project's plumbing.

    Args:
        load_mcp: When False, skip MCP loading entirely (offline/unit use).

    Raises:
        OpenRouterUnavailable: when the chat model cannot be built or the
            probe call fails — citation requires a working OpenRouter setup.
    """
    _load_env()

    from agent.config import AgentConfig
    from agent.paths import find_app_root

    config = AgentConfig()
    llm = _build_llm(config)
    await _probe_llm(llm)

    web_tools: dict[str, object] = {}
    if load_mcp:
        from agent.mcp import load_mcp_tools_with_families

        try:
            tools, families = await load_mcp_tools_with_families()
        except Exception as exc:  # noqa: BLE001 - surfaced later as WebSearchUnavailable
            logger.warning("MCP loading failed: %s", exc)
            tools, families = [], {}
        for tool in tools:
            name = getattr(tool, "name", None)
            if name and families.get(name) == WEB_SEARCH_FAMILY:
                web_tools[name] = tool

    return CitationRuntime(
        config=config,
        llm=llm,
        web_tools=web_tools,
        app_root=find_app_root(),
    )
