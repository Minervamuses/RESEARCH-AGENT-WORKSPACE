"""CLI entry point for the agent package."""

import argparse
import asyncio
import unicodedata

from langgraph.errors import GraphRecursionError

from agent.cli.prompting import LineReader, build_line_reader
from agent.cli.runtime import CondaRuntimeError, require_conda_runtime
from agent.cli.slash_commands import (
    SlashCommandContext,
    SlashCommandError,
    build_default_registry,
    execute_slash_command,
    parse_slash_command,
)
from agent.config import AgentConfig
from agent.session import ChatSession, DEFAULT_RECURSION_LIMIT
from agent.turn_safety import build_recovery_message

_EXIT_COMMANDS = {"q", "quit", "exit"}


def _normalize_cli_command(value: str) -> str:
    """Normalize short CLI commands without mutating messages sent to the agent."""
    normalized = unicodedata.normalize("NFKC", value.strip())
    visible_chars = [
        char
        for char in normalized
        if unicodedata.category(char) not in {"Cc", "Cf"}
    ]
    return "".join(visible_chars).strip().casefold()


def _is_blank_input(value: str) -> bool:
    return not _normalize_cli_command(value)


def _is_exit_input(value: str) -> bool:
    return _normalize_cli_command(value) in _EXIT_COMMANDS


def _print_progress(node_name: str, new_msgs: list) -> None:
    """Stream tool-call activity to the user without dumping payloads."""
    from langchain_core.messages import AIMessage, ToolMessage

    for msg in new_msgs:
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            for call in msg.tool_calls:
                name = call.get("name", "?")
                print(f"  → calling {name}", flush=True)
        elif isinstance(msg, ToolMessage):
            name = getattr(msg, "name", "?")
            content = getattr(msg, "content", "") or ""
            errored = (
                getattr(msg, "status", None) == "error"
                or (isinstance(content, str) and content.startswith("Tool error:"))
            )
            symbol = "✗" if errored else "✓"
            suffix = " errored" if errored else " returned"
            print(f"  {symbol} {name}{suffix}", flush=True)


def _print_banner(session=None) -> None:
    mode = "plan" if getattr(session, "plan_mode", False) else "default"
    mcp_families = sorted(set(getattr(session, "mcp_families", {}).values()))
    mcp_status = ", ".join(mcp_families) or "none"
    print(
        "Agent Chat (LangGraph mode). Type 'q' to quit.\n"
        f"Mode: {mode}\n"
        f"MCP: {mcp_status}\n"
    )


def _print_cli_message(message: str) -> None:
    print(f"\n{message}\n")


def _clear_terminal() -> None:
    # \033[H = home, \033[2J = clear viewport, \033[3J = clear scrollback.
    # Without 3J modern terminals keep prior lines reachable by scrolling up,
    # so /clear only appears to clear.
    print("\033[H\033[2J\033[3J", end="", flush=True)


async def _run(
    args: argparse.Namespace,
    read_line: LineReader | None = None,
) -> None:
    config = AgentConfig()
    session = await ChatSession.create(
        config,
        recursion_limit=args.max_turns,
        load_mcp=not args.no_mcp,
        progress_cb=_print_progress,
    )
    command_registry = build_default_registry()
    reader = read_line or build_line_reader(command_registry=command_registry)

    _print_banner(session)

    try:
        while True:
            try:
                raw_input = await reader(">> ")
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if _is_blank_input(raw_input):
                continue
            if _is_exit_input(raw_input):
                break

            user_input = raw_input.strip()
            try:
                parsed = parse_slash_command(user_input)
            except SlashCommandError as exc:
                _print_cli_message(f"(cli error: {exc})")
                continue

            if parsed is not None:
                try:
                    result = await execute_slash_command(
                        parsed,
                        SlashCommandContext(
                            session=session,
                            registry=command_registry,
                        ),
                    )
                except SlashCommandError as exc:
                    _print_cli_message(f"(cli error: {exc})")
                    continue

                if result.clear_screen:
                    _clear_terminal()
                    _print_banner(session)
                if result.message:
                    _print_cli_message(result.message)
                if result.should_exit:
                    break
                if not result.followup_input:
                    continue
                # e.g. /citation <text>: the trailing text becomes a normal
                # agent turn (recorded in history/trace like any user turn).
                user_input = result.followup_input

            try:
                response = await session.turn(user_input)
            except GraphRecursionError:
                response = (
                    f"(agent hit recursion limit of {session.recursion_limit} tool "
                    "rounds without settling. Try rephrasing or narrowing the question.)"
                )
            except Exception as exc:
                response = f"(agent error: {type(exc).__name__}: {exc})"
            if not str(response).strip():
                response = build_recovery_message(
                    user_input=user_input,
                    had_tool_results=False,
                )
            print(f"\n{response}\n")
    finally:
        await session.flush_recent_turns()


def main():
    parser = argparse.ArgumentParser(
        description="Conversational agent interface over the RAG core. "
        "Uses LangGraph with tool-calling to let the LLM search the knowledge base."
    )
    parser.add_argument(
        "--max-turns", type=int, default=DEFAULT_RECURSION_LIMIT,
        help=f"Max recursion depth per turn (default: {DEFAULT_RECURSION_LIMIT})",
    )
    parser.add_argument(
        "--no-mcp", action="store_true",
        help="Disable all MCP tool loading for this run.",
    )
    args = parser.parse_args()
    try:
        require_conda_runtime("app")
    except CondaRuntimeError as exc:
        parser.error(str(exc))
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
