"""Slash command parsing, registry, and local command handlers."""

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
import re
import shlex
from typing import Awaitable, Callable, Sequence

from agent.ingest import (
    diff_folder,
    ingest_file,
    ingest_folder,
    init_workspace,
    prune_folder,
)
from agent.llm.thinking import ExtendedModeNotConfigured, require_thinking_models
from agent.skills import SkillMetadata


class SlashCommandError(ValueError):
    """Raised when CLI slash command input is invalid."""


@dataclass(frozen=True)
class ParsedSlashCommand:
    """A slash command parsed from raw CLI input."""

    raw_text: str
    name: str
    args: tuple[str, ...]


@dataclass(frozen=True)
class SlashCommandResult:
    """Outcome from executing a slash command locally.

    ``followup_input`` asks the chat loop to feed the given text through an
    agent turn (history, trace, and error handling included) right after the
    local command completes. ``skill_name`` selects a transient runtime for
    that turn; Citation followups leave it unset and use their persistent
    static handler.
    """

    message: str = ""
    should_exit: bool = False
    clear_screen: bool = False
    followup_input: str | None = None
    skill_name: str | None = None


@dataclass(frozen=True)
class SlashCommand:
    """Definition for one registered slash command."""

    name: str
    description: str
    handler: Callable[["SlashCommandContext", ParsedSlashCommand], Awaitable[SlashCommandResult]]
    aliases: tuple[str, ...] = ()
    skill_name: str | None = None


@dataclass(frozen=True)
class SlashCommandContext:
    """Runtime context passed into slash command handlers."""

    session: object
    registry: "SlashCommandRegistry"


class SlashCommandRegistry:
    """Lookup and completion support for CLI slash commands."""

    def __init__(
        self,
        commands: list[SlashCommand],
        *,
        diagnostics: Sequence[str] = (),
    ):
        self._commands = tuple(commands)
        self.diagnostics = tuple(diagnostics)
        self._by_name: dict[str, SlashCommand] = {}

        for command in self._commands:
            self._register_name(command.name, command)
            for alias in command.aliases:
                self._register_name(alias, command)

    def _register_name(self, name: str, command: SlashCommand) -> None:
        normalized = name.casefold()
        if normalized in self._by_name:
            raise ValueError(f"duplicate slash command name: {name}")
        self._by_name[normalized] = command

    def all_commands(self) -> tuple[SlashCommand, ...]:
        return self._commands

    def get(self, name: str) -> SlashCommand | None:
        return self._by_name.get(name.casefold())

    def matching_commands(self, prefix: str) -> tuple[SlashCommand, ...]:
        normalized = prefix.casefold()
        return tuple(
            command
            for command in self._commands
            if command.name.casefold().startswith(normalized)
        )


def parse_slash_command(raw_input: str) -> ParsedSlashCommand | None:
    """Parse a leading slash command, or return None for normal chat input."""
    text = raw_input.strip()
    if not text.startswith("/"):
        return None
    if text == "/":
        raise SlashCommandError("slash command cannot be empty")

    try:
        parts = shlex.split(text[1:])
    except ValueError:
        # Natural-language arguments (e.g. an apostrophe after /citation)
        # must not kill the command; fall back to whitespace splitting.
        parts = text[1:].split()

    if not parts:
        raise SlashCommandError("slash command cannot be empty")

    return ParsedSlashCommand(
        raw_text=text,
        name=parts[0],
        args=tuple(parts[1:]),
    )


async def execute_slash_command(
    parsed: ParsedSlashCommand,
    context: SlashCommandContext,
) -> SlashCommandResult:
    """Resolve and run a slash command against the local CLI context."""
    command = context.registry.get(parsed.name)
    if command is None:
        raise SlashCommandError(f"unknown slash command: /{parsed.name}")
    return await command.handler(context, parsed)


def build_default_registry(session: object | None = None) -> SlashCommandRegistry:
    """Create static commands plus this session's validated Skill commands."""
    from agent.cli.extension_management import handle_extension_management

    commands = [
            SlashCommand(
                name="help",
                description="Show available slash commands.",
                handler=_handle_help,
            ),
            SlashCommand(
                name="status",
                description="Show local session status.",
                handler=_handle_status,
            ),
            SlashCommand(
                name="thinking",
                description="Switch reasoning workflow depth (normal or extended).",
                handler=_handle_thinking,
            ),
            SlashCommand(
                name="extension-management",
                description=(
                    "Scan and apply drop-in Skill/MCP changes for next restart."
                ),
                handler=handle_extension_management,
            ),
            SlashCommand(
                name="init",
                description="Ingest the host project workspace, excluding top-level app.",
                handler=_handle_init,
            ),
            SlashCommand(
                name="ingest",
                description="Upsert a file or folder into the rag store.",
                handler=_handle_ingest,
            ),
            SlashCommand(
                name="sync",
                description="Show files on disk vs in the rag store (dry run).",
                handler=_handle_sync,
            ),
            SlashCommand(
                name="prune",
                description="Remove store entries whose source file is gone (add --yes to apply).",
                handler=_handle_prune,
            ),
            SlashCommand(
                name="citation",
                description=(
                    "Run one citation task with /citation <prompt> in normal "
                    "thinking, then restore the session's thinking mode."
                ),
                handler=_handle_citation,
            ),
            SlashCommand(
                name="clear",
                description="Clear the terminal screen.",
                handler=_handle_clear,
            ),
            SlashCommand(
                name="quit",
                description="Exit the chat CLI.",
                aliases=("exit",),
                handler=_handle_quit,
            ),
        ]
    diagnostics: tuple[str, ...] = ()
    if session is not None:
        dynamic, diagnostics = _project_skill_commands(session, commands)
        commands.extend(dynamic)
    return SlashCommandRegistry(commands, diagnostics=diagnostics)


_SKILL_COMMAND_NAME_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$"
)
_PROMPT_MASTER_COMMAND = "_prompt-master"
_RETIRED_SKILL_COMMANDS = frozenset({"skill"})
_MAX_SKILL_COMMAND_DIAGNOSTICS = 20


def _project_skill_commands(
    session: object,
    static_commands: Sequence[SlashCommand],
) -> tuple[list[SlashCommand], tuple[str, ...]]:
    """Fail closed while projecting the immutable session Skill catalog."""
    loaded = getattr(session, "loaded_skills", ()) or ()
    groups: dict[str, list[SkillMetadata]] = {}
    diagnostics: list[str] = []
    for skill in loaded:
        name = getattr(skill, "name", None)
        if not isinstance(name, str) or not name:
            diagnostics.append("Skill command unavailable: invalid catalog name")
            continue
        groups.setdefault(name.casefold(), []).append(skill)

    reserved = set(_RETIRED_SKILL_COMMANDS)
    for command in static_commands:
        reserved.add(command.name.casefold())
        reserved.update(alias.casefold() for alias in command.aliases)

    projected: list[SlashCommand] = []
    for normalized, entries in groups.items():
        # Citation is represented only by its dedicated static command.
        if normalized == _CITATION_SKILL:
            continue
        name = entries[0].name
        if len(entries) != 1:
            diagnostics.append(
                f"Skill command /{name} unavailable: duplicate catalog name"
            )
            continue
        if (
            name != _PROMPT_MASTER_COMMAND
            and _SKILL_COMMAND_NAME_RE.fullmatch(name) is None
        ):
            diagnostics.append(
                f"Skill command /{name} unavailable: invalid command name"
            )
            continue
        if normalized in reserved:
            diagnostics.append(
                f"Skill command /{name} unavailable: reserved command collision"
            )
            continue
        projected.append(
            SlashCommand(
                name=name,
                description=entries[0].description,
                handler=_one_shot_skill_handler(name),
                skill_name=name,
            )
        )

    if len(diagnostics) > _MAX_SKILL_COMMAND_DIAGNOSTICS:
        omitted = len(diagnostics) - _MAX_SKILL_COMMAND_DIAGNOSTICS
        diagnostics = [
            *diagnostics[:_MAX_SKILL_COMMAND_DIAGNOSTICS],
            f"{omitted} additional Skill command diagnostics omitted",
        ]
    return projected, tuple(diagnostics)


def _one_shot_skill_handler(
    skill_name: str,
) -> Callable[["SlashCommandContext", ParsedSlashCommand], Awaitable[SlashCommandResult]]:
    async def _handle(
        context: SlashCommandContext,
        parsed: ParsedSlashCommand,
    ) -> SlashCommandResult:
        del context
        body = parsed.raw_text[1:]
        token = re.match(r"\S+", body)
        prompt = body[token.end():].strip() if token is not None else ""
        if not prompt:
            raise SlashCommandError(f"usage: /{skill_name} <prompt>")
        return SlashCommandResult(
            followup_input=prompt,
            skill_name=skill_name,
        )

    return _handle


async def _handle_help(
    context: SlashCommandContext,
    parsed: ParsedSlashCommand,
) -> SlashCommandResult:
    del parsed

    lines = ["Available slash commands:"]
    for command in context.registry.all_commands():
        alias_suffix = ""
        if command.aliases:
            alias_list = ", ".join(f"/{alias}" for alias in command.aliases)
            alias_suffix = f" (aliases: {alias_list})"
        lines.append(f"/{command.name} - {command.description}{alias_suffix}")
    if context.registry.diagnostics:
        lines.extend(["", "Unavailable Skill commands:"])
        lines.extend(f"- {item}" for item in context.registry.diagnostics)
    return SlashCommandResult(message="\n".join(lines))


async def _handle_status(
    context: SlashCommandContext,
    parsed: ParsedSlashCommand,
) -> SlashCommandResult:
    del parsed

    status = context.session.status_snapshot()
    lines = [
        "Session status:",
        f"session_id: {status['session_id']}",
        "conversation_root: "
        + json.dumps(status["conversation_root"], ensure_ascii=False),
        f"turn_count: {status['turn_count']}",
        f"recent_turn_count: {status['recent_turn_count']}",
        f"graph_recursion_limit: {status['graph_recursion_limit']}",
        f"last_tool_calls: {status['last_tool_counts']}",
        f"thinking_mode: {status.get('thinking_mode', 'normal')}",
        f"mcp_families: {status.get('mcp_families', 'none')}",
    ]
    return SlashCommandResult(message="\n".join(lines))


_THINKING_MODES = ("normal", "extended")
_THINKING_MODE_DESCRIPTIONS = {
    "normal": "default direct agent flow",
    "extended": "prompt rewrite + reviewer/reviser loop",
}

_MENU_CANCEL_TOKENS = frozenset({"", "q", "cancel"})


def _render_numbered_menu(
    *,
    header: list[str],
    options: Sequence[tuple[str, str | None]],
    zero_option: str | None = None,
    footer: str = "Select (number or name; Enter to cancel): ",
) -> str:
    """Render a numbered selection menu shared by every interactive prompt."""
    lines = list(header)
    if zero_option is not None:
        lines.append(zero_option)
    for idx, (name, description) in enumerate(options, start=1):
        if description:
            lines.append(f"  [{idx}] {name}  - {description}")
        else:
            lines.append(f"  [{idx}] {name}")
    lines.append(footer)
    return "\n".join(lines)


def _resolve_numbered_choice(
    raw: str,
    option_names: Sequence[str],
    *,
    cancel_tokens: frozenset[str],
    zero_tokens: frozenset[str] = frozenset(),
    zero_value: str | None = None,
) -> str | None:
    """Map raw menu input to an option name.

    Cancel tokens return None; zero tokens return zero_value; a digit selects
    the 1-based option (out-of-range raises); anything else is returned
    cleaned for the caller to validate.
    """
    cleaned = raw.strip().lower()
    if cleaned in cancel_tokens:
        return None
    if cleaned in zero_tokens:
        return zero_value
    if cleaned.isdigit():
        idx = int(cleaned) - 1
        if 0 <= idx < len(option_names):
            return option_names[idx]
        raise SlashCommandError(f"invalid choice: {cleaned}")
    return cleaned


def _render_thinking_prompt(current: str) -> str:
    return _render_numbered_menu(
        header=[f"Current thinking mode: {current}", "Available thinking modes:"],
        options=[(mode, _THINKING_MODE_DESCRIPTIONS[mode]) for mode in _THINKING_MODES],
    )


def _resolve_thinking_choice(raw: str) -> str | None:
    """Map raw user input to a thinking mode, or None for cancel."""
    return _resolve_numbered_choice(
        raw, _THINKING_MODES, cancel_tokens=_MENU_CANCEL_TOKENS,
    )


async def _handle_thinking(
    context: SlashCommandContext,
    parsed: ParsedSlashCommand,
) -> SlashCommandResult:
    if len(parsed.args) > 1:
        raise SlashCommandError("usage: /thinking [normal|extended]")

    current = getattr(context.session, "thinking_mode", "normal")
    if parsed.args:
        target = parsed.args[0].strip().lower()
    else:
        raw = await asyncio.to_thread(input, _render_thinking_prompt(current))
        target = _resolve_thinking_choice(raw)
        if target is None:
            return SlashCommandResult(message="cancelled")

    if target not in _THINKING_MODES:
        valid = ", ".join(_THINKING_MODES)
        raise SlashCommandError(
            f"unknown thinking mode: {target} (available: {valid})"
        )

    if target == current:
        return SlashCommandResult(message=f"already in {current} thinking mode")

    if target == "extended":
        try:
            require_thinking_models(context.session.config)
        except ExtendedModeNotConfigured as exc:
            raise SlashCommandError(str(exc)) from exc

    setter = getattr(context.session, "set_thinking_mode", None)
    try:
        if setter is not None:
            setter(target)
        else:
            setattr(context.session, "thinking_mode", target)
    except ValueError as exc:
        # e.g. extended thinking refused while the citation skill is active.
        raise SlashCommandError(str(exc)) from exc
    return SlashCommandResult(message=f"thinking -> {target}")


_CITATION_SKILL = "citation"
_CITATION_OFF_TOKENS = frozenset({"off", "none", "deactivate"})


async def _handle_citation(
    context: SlashCommandContext,
    parsed: ParsedSlashCommand,
) -> SlashCommandResult:
    """Return Citation intent; the session owns activation under its turn lock."""
    del context
    if len(parsed.args) == 1 and parsed.args[0].casefold() in _CITATION_OFF_TOKENS:
        return SlashCommandResult(message=(
            "Citation now runs as a single-turn task; use /citation <prompt>."
        ))
    # Preserve natural language instead of reconstructing shlex tokens.
    followup = parsed.raw_text[1 + len(parsed.name):].strip()
    if not followup:
        return SlashCommandResult(message="Usage: /citation <prompt>")
    return SlashCommandResult(
        message=("Citation runs once in normal thinking; your session's "
                 "thinking mode is restored after this task."),
        followup_input=followup,
        skill_name=_CITATION_SKILL,
    )


async def _handle_clear(
    context: SlashCommandContext,
    parsed: ParsedSlashCommand,
) -> SlashCommandResult:
    del context, parsed
    return SlashCommandResult(clear_screen=True)


async def _handle_quit(
    context: SlashCommandContext,
    parsed: ParsedSlashCommand,
) -> SlashCommandResult:
    del context, parsed
    return SlashCommandResult(should_exit=True)


def _resolve_target(arg: str | None) -> Path:
    """Expand `~` and resolve the target path argument."""
    raw = arg if arg else "."
    return Path(raw).expanduser().resolve()


async def _handle_init(
    context: SlashCommandContext,
    parsed: ParsedSlashCommand,
) -> SlashCommandResult:
    if parsed.args:
        raise SlashCommandError("/init takes no arguments")

    files, chunks, host_root, skip = await init_workspace(context.session.config)
    return SlashCommandResult(
        message=(
            f"initialized: {files} files, {chunks} chunks "
            f"(root={host_root}, excluded {', '.join(sorted(skip))})"
        )
    )


async def _handle_ingest(
    context: SlashCommandContext,
    parsed: ParsedSlashCommand,
) -> SlashCommandResult:
    if not parsed.args:
        return SlashCommandResult(message="usage: /ingest <file-or-folder>")
    if len(parsed.args) > 1:
        raise SlashCommandError("/ingest takes exactly one path argument")

    target = _resolve_target(parsed.args[0])
    if not target.exists():
        raise SlashCommandError(f"path does not exist: {target}")

    config = context.session.config

    try:
        if target.is_file():
            pid, count = await ingest_file(target, config)
            return SlashCommandResult(
                message=f"ingested {pid} ({count} chunks)"
            )

        if target.is_dir():
            files, chunks = await ingest_folder(target, config)
            return SlashCommandResult(
                message=f"ingested {files} files ({chunks} chunks) under {target}"
            )
    except ValueError as exc:
        raise SlashCommandError(str(exc)) from exc

    raise SlashCommandError(f"unsupported path type: {target}")


async def _handle_sync(
    context: SlashCommandContext,
    parsed: ParsedSlashCommand,
) -> SlashCommandResult:
    if len(parsed.args) > 1:
        raise SlashCommandError("/sync takes at most one path argument")

    target = _resolve_target(parsed.args[0] if parsed.args else None)
    if not target.is_dir():
        raise SlashCommandError(f"not a directory: {target}")

    try:
        diff = await diff_folder(target, context.session.config)
    except ValueError as exc:
        raise SlashCommandError(str(exc)) from exc

    lines = [f"Diff against {target}:"]
    missing_store = diff["missing_from_store"]
    missing_disk = diff["missing_from_disk"]

    lines.append(f"  on disk, not in store ({len(missing_store)}):")
    if missing_store:
        lines.extend(f"    + {path}" for path in missing_store)
    else:
        lines.append("    (none)")

    lines.append(f"  in store, not on disk ({len(missing_disk)}):")
    if missing_disk:
        lines.extend(f"    - {path}" for path in missing_disk)
    else:
        lines.append("    (none)")

    return SlashCommandResult(message="\n".join(lines))


async def _handle_prune(
    context: SlashCommandContext,
    parsed: ParsedSlashCommand,
) -> SlashCommandResult:
    args = list(parsed.args)
    apply = False
    if "--yes" in args:
        apply = True
        args = [a for a in args if a != "--yes"]
    if len(args) > 1:
        raise SlashCommandError("/prune takes at most one path argument")

    target = _resolve_target(args[0] if args else None)
    if not target.is_dir():
        raise SlashCommandError(f"not a directory: {target}")

    config = context.session.config

    if not apply:
        try:
            diff = await diff_folder(target, config)
        except ValueError as exc:
            raise SlashCommandError(str(exc)) from exc
        orphans = diff["missing_from_disk"]
        lines = [f"Would prune {len(orphans)} orphaned pid(s) under {target}:"]
        if orphans:
            lines.extend(f"  - {path}" for path in orphans)
            lines.append("Re-run with --yes to apply.")
        else:
            lines.append("  (none)")
        return SlashCommandResult(message="\n".join(lines))

    try:
        removed = await prune_folder(target, config)
    except ValueError as exc:
        raise SlashCommandError(str(exc)) from exc
    return SlashCommandResult(
        message=f"pruned {len(removed)} orphaned pid(s) under {target}"
    )
