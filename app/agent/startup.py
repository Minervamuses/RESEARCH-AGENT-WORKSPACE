"""Session bootstrap coordinator for skills, extensions, and MCP tools."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from agent.config import AgentConfig
from agent.skills import SkillMetadata, discover_skills


@dataclass(frozen=True)
class SessionStartup:
    """Validated constructor inputs loaded before a session is built."""

    extra_tools: tuple[object, ...]
    mcp_families: Mapping[str, str]
    global_mcp_families: frozenset[str]
    loaded_skills: tuple[SkillMetadata, ...]
    running_extension_revision: int
    extension_startup_diagnostics: tuple[str, ...]


async def load_session_startup(
    config: AgentConfig,
    *,
    load_mcp: bool = True,
) -> SessionStartup:
    """Load verified extension state and optional MCP tools for one session."""
    builtin_skills = discover_skills(config)

    from agent.extensions.startup import load_extension_startup

    extension_startup = load_extension_startup(
        config,
        builtin_skills=builtin_skills,
    )
    loaded_skills = [*builtin_skills, *extension_startup.skills]
    runtime_diagnostics = list(extension_startup.diagnostics)
    extra_tools: list = []
    families: dict[str, str] = {}
    if load_mcp:
        from agent.mcp import (
            load_mcp_tools_with_families,
            resolve_mcp_specs,
        )

        try:
            if extension_startup.mcp_specs:
                specs = [
                    *resolve_mcp_specs(),
                    *extension_startup.mcp_specs,
                ]
                extra_tools, families = await load_mcp_tools_with_families(
                    specs=specs,
                    diagnostics=runtime_diagnostics,
                )
            else:
                extra_tools, families = await load_mcp_tools_with_families()
        except Exception as exc:
            extra_tools = []
            families = {}
            runtime_diagnostics.append(
                "MCP loader unavailable: " + type(exc).__name__
            )

    return SessionStartup(
        extra_tools=tuple(extra_tools),
        mcp_families=MappingProxyType(dict(families)),
        global_mcp_families=frozenset(
            {"web_search", *extension_startup.global_mcp_families}
        ),
        loaded_skills=tuple(loaded_skills),
        running_extension_revision=extension_startup.revision,
        extension_startup_diagnostics=tuple(runtime_diagnostics),
    )
