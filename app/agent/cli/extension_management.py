"""User-facing slash command for disk-only extension management."""

from __future__ import annotations

import asyncio
import json

from agent.extensions.manager import (
    ApplyReport,
    ExtensionManager,
    ExtensionPreview,
    ExtensionStatus,
    ManagementError,
)

_YES = frozenset({"y", "yes"})


def _manager_for(session: object) -> ExtensionManager:
    injected = getattr(session, "extension_manager", None)
    if injected is not None:
        return injected
    config = getattr(session, "config", None)
    if config is None:
        raise ManagementError("session has no AgentConfig")
    return ExtensionManager(config)


def render_preview(preview: ExtensionPreview) -> str:
    plan = {item.key: item for item in preview.plan.items}
    lines = [
        "Extension Management plan",
        f"drop-in root: {preview.paths.dropin_root}",
        f"applied revision: {preview.registry.revision}",
    ]
    for change in preview.diff.changes:
        if change.operation == "unchanged":
            lines.append(f"- {change.key}: unchanged")
            continue
        item = plan[change.key]
        detail = item.summary
        if item.reason:
            detail += f" ({item.reason})"
        lines.append(
            f"- {change.key}: {change.operation} -> {item.decision}: {detail}"
        )
        candidate = preview.mcp_candidates.get(change.key)
        if candidate is not None:
            descriptor = candidate.descriptor
            env_bindings = []
            for target, binding in sorted(descriptor.environment.items()):
                if binding.from_env is not None:
                    requirement = "required" if binding.required else "optional"
                    env_bindings.append(
                        f"{target} <- ${binding.from_env} ({requirement})"
                    )
                else:
                    env_bindings.append(
                        f"{target} = {json.dumps(binding.value)}"
                    )
            lines.extend(
                [
                    f"  family/scope: {descriptor.family}/{descriptor.scope}",
                    f"  command: {candidate.resolved_command}",
                    f"  args: {json.dumps(candidate.args)}",
                    f"  cwd: {candidate.cwd}",
                    f"  env: {', '.join(env_bindings) or '(none)'}",
                    f"  binding: {candidate.binding_hash}",
                ]
            )
        if change.key in preview.host_blocks:
            lines.append(f"  host blocked: {preview.host_blocks[change.key]}")
    for diagnostic in preview.diff.diagnostics:
        lines.append(f"! {diagnostic}")
    return "\n".join(lines)


def render_apply_report(report: ApplyReport) -> str:
    lines = [
        (
            "Extension Management applied "
            f"revision {report.previous_revision} -> {report.applied_revision}"
        )
    ]
    for item in report.items:
        lines.append(f"- {item.key}: {item.outcome}: {item.detail}")
    for diagnostic in report.diagnostics:
        lines.append(f"! {diagnostic}")
    lines.append(f"restart_required: {str(report.restart_required).lower()}")
    return "\n".join(lines)


def render_status(status: ExtensionStatus) -> str:
    lines = [
        "Extension Management status",
        f"drop-in root: {status.dropin_root}",
        f"state root: {status.state_root}",
        f"desired: {status.desired_count}",
        f"applied: {status.applied_count}",
        f"applied revision: {status.applied_revision}",
        f"running revision: {status.running_revision}",
        f"restart_required: {str(status.restart_required).lower()}",
        (
            "running MCP: " + ", ".join(status.running_mcp_families)
            if status.running_mcp_families
            else "running MCP: none"
        ),
        (
            "manager: available"
            if status.manager_available
            else f"manager: unavailable ({status.manager_error})"
        ),
    ]
    lines.extend(f"! {diagnostic}" for diagnostic in status.diagnostics)
    return "\n".join(lines)


async def handle_extension_management(context, parsed):
    """Handle apply, dry-run, and status without entering session.turn()."""
    from agent.cli.slash_commands import SlashCommandError, SlashCommandResult

    args = tuple(arg.casefold() for arg in parsed.args)
    if args not in {(), ("--dry-run",), ("status",)}:
        raise SlashCommandError(
            "usage: /Extension-Management [--dry-run|status]"
        )
    manager = _manager_for(context.session)
    try:
        if args == ("status",):
            running = int(
                getattr(context.session, "running_extension_revision", 0)
            )
            status = await asyncio.to_thread(
                manager.status,
                running_revision=running,
                running_mcp_families=tuple(
                    getattr(context.session, "mcp_families", {}).values()
                ),
                startup_diagnostics=tuple(
                    getattr(
                        context.session,
                        "extension_startup_diagnostics",
                        (),
                    )
                ),
            )
            return SlashCommandResult(message=render_status(status))

        preview = await asyncio.to_thread(manager.preview)
        rendered = render_preview(preview)
        if args == ("--dry-run",):
            return SlashCommandResult(message=rendered + "\n\ndry-run: no changes written")
        raw = await asyncio.to_thread(
            input,
            rendered + "\n\nApply this exact plan? [y/N]: ",
        )
        if raw.strip().casefold() not in _YES:
            return SlashCommandResult(message=rendered + "\n\ncancelled")
        approvals = {
            candidate.binding_hash
            for candidate in preview.mcp_candidates.values()
        }
        report = await asyncio.to_thread(
            manager.apply,
            preview,
            approved_mcp_bindings=approvals,
        )
        return SlashCommandResult(message=render_apply_report(report))
    except ManagementError as exc:
        raise SlashCommandError(str(exc)) from exc
