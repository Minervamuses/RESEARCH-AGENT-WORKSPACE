"""Standalone interactive citation CLI.

Runs the same session-scoped :class:`~citation.coordinator.CitationCoordinator`
(over the process provider hub) that chat's ``/citation`` uses, with the same
subcommands and formatting. Strictly interactive: search, inspect, select,
and confirm are separate user actions — there is no ``--auto`` mode and no
non-interactive save path of any kind.

Run from ``app/``::

    python -m citation "attention is all you need"
    python -m citation            # start with an empty prompt

Then drive the workflow with the /citation subcommands (the ``/citation``
prefix is optional here): ``search <query>``, ``list [page]``,
``show <candidate-id>``, ``more [query]``, ``select <candidate-id>``,
``confirm <match-id>``, ``status``, ``cancel``, ``sources [page]``,
``source <source-id>``, ``help``, ``quit``.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import shlex
import sys

from agent.cli.citation_command import USAGE, run_citation_command
from citation.coordinator import CitationCoordinator

logger = logging.getLogger("citation.cli")

_EXIT_TOKENS = {"q", "quit", "exit"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m citation",
        description=(
            "Interactive citation workflow: search structured providers "
            "(Crossref, OpenAlex with OPENALEX_API_KEY), resolve DOIs via "
            "doi.org, and save verified BibTeX bundles. Selection and "
            "confirmation are always interactive."
        ),
    )
    parser.add_argument(
        "query", nargs="*",
        help="Optional initial search query (e.g. '注意力機制 論文').",
    )
    parser.add_argument(
        "--no-mcp", action="store_true",
        help="Skip loading the Web Search MCP (web fallback and 'more' are "
             "then reported as disabled).",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable debug logging.",
    )
    return parser


async def _dispatch(coordinator: CitationCoordinator, line: str, write) -> None:
    text = line.strip()
    if text.startswith("/citation"):
        text = text[len("/citation"):].strip()
    elif text.startswith("/"):
        write(f"(unknown command; {USAGE})")
        return
    try:
        args = tuple(shlex.split(text))
    except ValueError as exc:
        write(f"(parse error: {exc})")
        return
    try:
        message = await run_citation_command(coordinator, args)
    except ValueError as exc:
        write(f"(error: {exc})")
        return
    write(message)


async def run_repl(
    coordinator: CitationCoordinator,
    *,
    initial_query: str = "",
    read_line=None,
    write=print,
) -> int:
    """Drive one interactive session; returns the process exit code."""

    async def _default_read(prompt: str) -> str:
        return await asyncio.to_thread(input, prompt)

    read_line = read_line or _default_read

    write(
        "Citation workflow (interactive). Type 'help' for commands, "
        "'quit' to exit."
    )
    if initial_query.strip():
        await _dispatch(coordinator, f"search {initial_query.strip()}", write)

    while True:
        try:
            raw = await read_line("citation> ")
        except (EOFError, KeyboardInterrupt):
            write("")
            break
        text = raw.strip()
        if not text:
            continue
        if text.lower() in _EXIT_TOKENS:
            break
        if text.lower() in {"help", "?"}:
            write(USAGE)
            continue
        await _dispatch(coordinator, text, write)
    return 0


async def _load_web_tools() -> dict[str, object]:
    """Load Web Search MCP tool handles (standalone owns its MCP lifetime)."""
    from agent.mcp import load_mcp_tools_with_families

    try:
        tools, families = await load_mcp_tools_with_families()
    except Exception as exc:  # noqa: BLE001 - web is optional here
        logger.warning("MCP loading failed: %s", exc)
        return {}
    return {
        tool.name: tool
        for tool in tools
        if families.get(getattr(tool, "name", "")) == "web_search"
    }


async def _amain(args: argparse.Namespace) -> int:
    from dotenv import load_dotenv

    from agent.paths import find_app_root

    load_dotenv(dotenv_path=find_app_root() / ".env", override=False)

    from agent.config import AgentConfig
    from citation.hub import get_provider_hub

    config = AgentConfig()

    def _llm_factory():
        from agent.llm import get_chat_model

        return get_chat_model(config)

    web_tools = {} if args.no_mcp else await _load_web_tools()
    coordinator = CitationCoordinator(
        get_provider_hub(),
        web_tools=web_tools,
        llm_factory=_llm_factory,
        config=config,
    )
    return await run_repl(coordinator, initial_query=" ".join(args.query))


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        rc = asyncio.run(_amain(args))
    except KeyboardInterrupt:
        rc = 130
    sys.exit(rc)


if __name__ == "__main__":
    main()
