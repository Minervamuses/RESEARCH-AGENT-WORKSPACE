"""Extension handlers: status, preview, apply and the /extension-management command."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from collections.abc import Mapping
from contextlib import asynccontextmanager
from typing import Any
from agent.cli.slash_commands import ParsedSlashCommand, SlashCommandResult
from agent.extensions.manager import ApplyReport, ExtensionPreview, ExtensionStatus
from agent.ingest import run_local_work
from agent.session import ONE_SHOT_DISPLAY_INPUT_PREFIX
from agent.desktop.errors import DesktopServiceError, EventSink
from agent.desktop.approvals import _CREDENTIAL_URL, _SECRET_APPROVAL_CONTEXT, _SECRET_FLAG_VALUE


_BINDING_HASH = re.compile(r"^[0-9a-f]{64}$")


_EXTENSION_APPLY_HEADER = re.compile(
    r"^Extension Management applied revision (0|[1-9][0-9]*) -> (0|[1-9][0-9]*)$"
)


_EXTENSION_APPLY_OUTCOMES = frozenset({
    "added",
    "updated",
    "removed",
    "unchanged",
    "blocked",
    "pending_approval",
})


_MAX_LOCAL_COMMAND_BYTES = 65_536


_MAX_EXTENSION_ARGUMENTS = 128


_MAX_EXTENSION_ENVIRONMENT_NAMES = 128


class _ExtensionOps:
    """DesktopService methods moved here unchanged; `self` is the DesktopService."""

    @staticmethod
    def _desktop_extension_action(parsed: ParsedSlashCommand) -> str:
        args = tuple(arg.casefold() for arg in parsed.args)
        if args == ("status",):
            return "status"
        if args in {(), ("--dry-run",)}:
            return "preview"
        raise DesktopServiceError(
            "PROTOCOL_INVALID",
            "usage: /extension-management [--dry-run|status]",
        )

    async def _execute_desktop_extension_command(
        self,
        parsed: ParsedSlashCommand,
    ) -> SlashCommandResult:
        action = self._desktop_extension_action(parsed)
        if action == "status":
            status = await self._extensions_status()
            diagnostics = len(status["diagnostics"])
            running = ", ".join(status["runningMcpFamilies"]) or "none"
            message = "\n".join([
                "Extension Management status",
                f"desired: {status['desiredCount']}",
                f"applied: {status['appliedCount']}",
                f"applied revision: {status['appliedRevision']}",
                f"running revision: {status['runningRevision']}",
                (
                    "restart required: yes"
                    if status["restartRequired"]
                    else "restart required: no"
                ),
                f"running MCP: {running}",
                f"diagnostics: {diagnostics}",
            ])
            return SlashCommandResult(message=message)
        return SlashCommandResult(message=(
            "Extension preview is ready to request. Preview may contact "
            "the configured model provider, but it writes no changes. "
            "Review the exact preview before applying."
        ))

    async def _extensions_status(self) -> dict[str, Any]:
        """Extension Management status for the `/extension-management status` command."""
        session = self.session
        status = await run_local_work(
            self._extension_manager.status,
            running_revision=(session.running_extension_revision if session else 0),
            running_mcp_families=(
                tuple(session.mcp_families.values()) if session else ()
            ),
            startup_diagnostics=(
                tuple(session.extension_startup_diagnostics) if session else ()
            ),
        )
        return self._extension_status_dto(status)

    async def _extensions_preview(
        self, _params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        async with self._extension_operation():
            preview = await asyncio.to_thread(self._extension_manager.preview)
        preview_id = uuid.uuid4().hex
        self._bounded_cache_insert(self._extension_previews, preview_id, preview)
        return self._extension_preview_dto(preview_id, preview)

    @staticmethod
    def _extension_apply_values(
        params: Mapping[str, Any],
    ) -> tuple[str, tuple[str, ...]]:
        preview_id = params.get("previewId")
        approved_values = params.get("approvedBindingHashes")
        if (
            not isinstance(preview_id, str)
            or not preview_id
            or len(preview_id.encode("utf-8")) > 256
            or not isinstance(approved_values, list)
            or len(approved_values) > 512
            or any(
                not isinstance(item, str) or not _BINDING_HASH.fullmatch(item)
                for item in approved_values
            )
        ):
            raise DesktopServiceError(
                "PROTOCOL_INVALID",
                "The approved extension binding list is invalid.",
            )
        return preview_id, tuple(sorted(set(approved_values)))

    @classmethod
    def _extension_apply_display_input(cls, params: Mapping[str, Any]) -> str:
        preview_id, approved = cls._extension_apply_values(params)
        payload = json.dumps(
            {
                "approvedBindingHashes": list(approved),
                "previewId": preview_id,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        return (
            f"{ONE_SHOT_DISPLAY_INPUT_PREFIX}"
            f"apply reviewed extension changes [{digest}]"
        )

    async def _extensions_apply(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        session = self._require_session()
        preview_id, approved_values = self._extension_apply_values(params)
        approved = set(approved_values)
        permission_mode = self._permission_mode
        display_input = self._extension_apply_display_input(params)

        async def apply_once() -> ApplyReport:
            preview = self._extension_previews.pop(preview_id, None)
            if preview is None:
                raise DesktopServiceError(
                    "EXTENSION_APPLY_FAILED",
                    "The extension preview is unknown or already used.",
                )
            known = {
                candidate.binding_hash
                for candidate in preview.mcp_candidates.values()
            }
            if not approved <= known:
                raise DesktopServiceError(
                    "PROTOCOL_INVALID",
                    "The approved extension binding list is invalid.",
                )
            self._validate_extension_apply_preview_capacity(preview)
            return await asyncio.to_thread(
                self._extension_manager.apply,
                preview,
                # Ask uses the explicit reviewed Apply action. Bypass derives
                # consent only from this validated preview; manager rechecks it.
                approved_mcp_bindings=known if permission_mode == "bypass" else approved,
            )

        async with self._extension_operation():
            raw_report, outcome = await session.run_display_only_turn(
                display_input,
                apply_once,
                self._render_extension_apply_report,
                turn_id=params["turnId"],
                retry=params["retry"],
                failure_retryable=False,
            )

        report = self._parse_extension_apply_report(outcome.text)
        if raw_report is not None:
            current = self._extension_apply_dto(raw_report)
            if current != report:
                raise DesktopServiceError(
                    "INTERNAL_ERROR",
                    "The durable extension result could not be verified.",
                )
        if (
            outcome.turn_id != params["turnId"]
            or outcome.state != "completed"
            or outcome.accepted is not True
            or outcome.persisted is not True
        ):
            raise DesktopServiceError(
                "INTERNAL_ERROR",
                "The durable extension lifecycle result is invalid.",
            )
        return {
            "sessionId": session.session_id,
            "turnId": outcome.turn_id,
            "turnNumber": outcome.turn_number,
            "state": outcome.state,
            "accepted": outcome.accepted,
            "persisted": outcome.persisted,
            "displayInput": display_input,
            "text": outcome.text,
            **report,
        }

    @asynccontextmanager
    async def _extension_operation(self):
        if (
            self._extension_active
            or self._turn_active
            or self._knowledge_active
            or self._session_creating
            or self._session_closing
        ):
            raise DesktopServiceError(
                "BUSY_EXTENSION_OPERATION",
                "An extension operation cannot start while other desktop work is active.",
                retryable=True,
            )
        self._extension_active = True
        try:
            yield
        finally:
            self._extension_active = False

    @staticmethod
    def _extension_status_dto(status: ExtensionStatus) -> dict[str, Any]:
        return {
            "dropinRoot": str(status.dropin_root.resolve()),
            "stateRoot": str(status.state_root.resolve()),
            "desiredCount": status.desired_count,
            "appliedCount": status.applied_count,
            "appliedRevision": status.applied_revision,
            "runningRevision": status.running_revision,
            "restartRequired": status.restart_required,
            "managerAvailable": status.manager_available,
            "managerError": (
                "The extension manager is unavailable."
                if status.manager_error is not None
                else None
            ),
            "diagnostics": [
                "An extension or MCP item is unavailable."
                for _item in status.diagnostics[:128]
            ],
            "runningMcpFamilies": list(status.running_mcp_families),
        }

    @classmethod
    def _extension_binding_dto(cls, candidate: Any) -> dict[str, Any]:
        name = str(candidate.descriptor.id)
        server = str(candidate.descriptor.family)
        binding_hash = str(candidate.binding_hash)
        command = str(candidate.resolved_command)
        arguments = [str(item) for item in candidate.args]
        working_directory = str(candidate.cwd)
        environment_names = [str(item) for item in candidate.env_names]
        display_context = "\n".join((command, *arguments))
        bounded_strings = (
            (name, 256),
            (server, 256),
            (command, 8_192),
            (working_directory, 8_192),
        )
        if (
            any(not value or len(value.encode("utf-8")) > limit for value, limit in bounded_strings)
            or not _BINDING_HASH.fullmatch(binding_hash)
            or len(arguments) > _MAX_EXTENSION_ARGUMENTS
            or any(
                not item or len(item.encode("utf-8")) > 4_096
                for item in arguments
            )
            or len(environment_names) > _MAX_EXTENSION_ENVIRONMENT_NAMES
            or any(
                not item or len(item.encode("utf-8")) > 256
                for item in environment_names
            )
            or _SECRET_APPROVAL_CONTEXT.search(display_context)
            or _SECRET_FLAG_VALUE.search(display_context)
            or _CREDENTIAL_URL.search(display_context)
        ):
            raise DesktopServiceError(
                "EXTENSION_PREVIEW_FAILED",
                "An extension binding cannot be displayed safely.",
            )
        return {
            "name": name,
            "server": server,
            "bindingHash": binding_hash,
            "requiresApproval": True,
            "command": command,
            "arguments": arguments,
            "workingDirectory": working_directory,
            "environmentNames": environment_names,
        }

    def _extension_preview_dto(
        self, preview_id: str, preview: ExtensionPreview
    ) -> dict[str, Any]:
        changed = [
            change
            for change in preview.diff.changes
            if change.operation != "unchanged"
        ]
        operation_counts: dict[str, int] = {}
        for change in changed:
            operation_counts[change.operation] = (
                operation_counts.get(change.operation, 0) + 1
            )
        summary_parts = [
            f"{operation}={count}"
            for operation, count in sorted(operation_counts.items())
        ]
        summary = self._bounded_text(
            (
                f"{len(changed)} extension change(s): " + ", ".join(summary_parts)
                if changed
                else "No extension changes are pending."
            ),
            4_096,
        )
        proposed_skills = sorted(
            {
                change.desired.id
                for change in changed
                if change.desired is not None and change.desired.kind == "skill"
            }
        )
        bindings = [
            self._extension_binding_dto(candidate)
            for _key, candidate in sorted(preview.mcp_candidates.items())
        ]
        return {
            "previewId": preview_id,
            "summary": summary,
            "proposedSkills": proposed_skills,
            "bindings": bindings,
        }

    @classmethod
    def _validate_extension_apply_preview_capacity(
        cls,
        preview: ExtensionPreview,
    ) -> None:
        revision = preview.registry.revision
        changes = preview.diff.changes
        diagnostics = preview.diff.diagnostics
        if (
            type(revision) is not int
            or not 0 <= revision < 4_294_967_295
            or len(changes) > 512
            or len(diagnostics) > 128
        ):
            raise DesktopServiceError(
                "EXTENSION_APPLY_FAILED",
                "The extension preview cannot produce a bounded durable result.",
            )
        items: list[dict[str, str]] = []
        for change in changes:
            key = change.key
            if (
                not isinstance(key, str)
                or not key
                or len(key.encode("utf-8")) > 256
            ):
                raise DesktopServiceError(
                    "EXTENSION_APPLY_FAILED",
                    "The extension preview contains an invalid item key.",
                )
            items.append({
                "key": key,
                "outcome": "pending_approval",
                "detail": cls._extension_outcome_detail("pending_approval"),
            })
        projected = {
            "previousRevision": revision,
            "appliedRevision": revision + 1,
            "restartRequired": True,
            "items": items,
            "diagnostics": [
                "The extension manager reported a host validation diagnostic."
                for _diagnostic in diagnostics
            ],
        }
        cls._serialize_extension_apply_dto(projected)

    @classmethod
    def _extension_apply_dto(cls, report: ApplyReport) -> dict[str, Any]:
        if (
            not isinstance(report, ApplyReport)
            or type(report.previous_revision) is not int
            or type(report.applied_revision) is not int
            or not 0 <= report.previous_revision <= 4_294_967_295
            or not 0 <= report.applied_revision <= 4_294_967_295
            or type(report.restart_required) is not bool
            or len(report.items) > 512
            or len(report.diagnostics) > 128
        ):
            raise DesktopServiceError(
                "EXTENSION_APPLY_FAILED",
                "The extension manager returned an invalid result.",
            )
        items: list[dict[str, str]] = []
        for item in report.items:
            if (
                not isinstance(item.key, str)
                or not item.key
                or len(item.key.encode("utf-8")) > 256
                or item.outcome not in _EXTENSION_APPLY_OUTCOMES
            ):
                raise DesktopServiceError(
                    "EXTENSION_APPLY_FAILED",
                    "The extension manager returned an invalid item result.",
                )
            items.append({
                "key": item.key,
                "outcome": item.outcome,
                "detail": cls._extension_outcome_detail(item.outcome),
            })
        return {
            "previousRevision": report.previous_revision,
            "appliedRevision": report.applied_revision,
            "restartRequired": report.restart_required,
            "items": items,
            "diagnostics": [
                "The extension manager reported a host validation diagnostic."
                for _diagnostic in report.diagnostics
            ],
        }

    @classmethod
    def _serialize_extension_apply_dto(cls, report: Mapping[str, Any]) -> str:
        lines = [
            (
                "Extension Management applied revision "
                f"{report['previousRevision']} -> {report['appliedRevision']}"
            ),
            (
                "restart_required: true"
                if report["restartRequired"]
                else "restart_required: false"
            ),
            f"items: {len(report['items'])}",
        ]
        lines.extend(
            "- " + json.dumps(
                {"key": item["key"], "outcome": item["outcome"]},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            for item in report["items"]
        )
        lines.append(f"diagnostics: {len(report['diagnostics'])}")
        text = "\n".join(lines)
        if len(text.encode("utf-8")) > _MAX_LOCAL_COMMAND_BYTES:
            raise DesktopServiceError(
                "EXTENSION_APPLY_FAILED",
                "The extension result is too large to save safely.",
            )
        return text

    @classmethod
    def _render_extension_apply_report(cls, value: object) -> str:
        if not isinstance(value, ApplyReport):
            raise DesktopServiceError(
                "EXTENSION_APPLY_FAILED",
                "The extension manager returned an invalid result.",
            )
        return cls._serialize_extension_apply_dto(
            cls._extension_apply_dto(value)
        )

    @classmethod
    def _parse_extension_apply_report(cls, text: str) -> dict[str, Any]:
        if (
            not isinstance(text, str)
            or not text
            or len(text.encode("utf-8")) > _MAX_LOCAL_COMMAND_BYTES
        ):
            raise DesktopServiceError(
                "INTERNAL_ERROR",
                "The saved extension result is invalid.",
            )
        lines = text.splitlines()
        if len(lines) < 4:
            raise DesktopServiceError(
                "INTERNAL_ERROR",
                "The saved extension result is invalid.",
            )
        header = _EXTENSION_APPLY_HEADER.fullmatch(lines[0])
        restart_value = {
            "restart_required: true": True,
            "restart_required: false": False,
        }.get(lines[1])
        items_match = re.fullmatch(r"items: (0|[1-9][0-9]*)", lines[2])
        if header is None or restart_value is None or items_match is None:
            raise DesktopServiceError(
                "INTERNAL_ERROR",
                "The saved extension result is invalid.",
            )
        item_count = int(items_match.group(1))
        if item_count > 512 or len(lines) != item_count + 4:
            raise DesktopServiceError(
                "INTERNAL_ERROR",
                "The saved extension result is invalid.",
            )
        diagnostics_match = re.fullmatch(
            r"diagnostics: (0|[1-9][0-9]*)",
            lines[-1],
        )
        if diagnostics_match is None or int(diagnostics_match.group(1)) > 128:
            raise DesktopServiceError(
                "INTERNAL_ERROR",
                "The saved extension result is invalid.",
            )
        items: list[dict[str, str]] = []
        try:
            for line in lines[3:-1]:
                if not line.startswith("- "):
                    raise ValueError("missing item marker")
                item = json.loads(line[2:])
                if not isinstance(item, dict) or set(item) != {"key", "outcome"}:
                    raise ValueError("invalid item shape")
                key = item["key"]
                outcome = item["outcome"]
                if (
                    not isinstance(key, str)
                    or not key
                    or len(key.encode("utf-8")) > 256
                    or outcome not in _EXTENSION_APPLY_OUTCOMES
                ):
                    raise ValueError("invalid item value")
                items.append({
                    "key": key,
                    "outcome": outcome,
                    "detail": cls._extension_outcome_detail(outcome),
                })
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise DesktopServiceError(
                "INTERNAL_ERROR",
                "The saved extension result is invalid.",
            ) from exc
        previous_revision = int(header.group(1))
        applied_revision = int(header.group(2))
        diagnostic_count = int(diagnostics_match.group(1))
        if (
            previous_revision > 4_294_967_295
            or applied_revision > 4_294_967_295
        ):
            raise DesktopServiceError(
                "INTERNAL_ERROR",
                "The saved extension result is invalid.",
            )
        report = {
            "previousRevision": previous_revision,
            "appliedRevision": applied_revision,
            "restartRequired": restart_value,
            "items": items,
            "diagnostics": [
                "The extension manager reported a host validation diagnostic."
                for _index in range(diagnostic_count)
            ],
        }
        if cls._serialize_extension_apply_dto(report) != text:
            raise DesktopServiceError(
                "INTERNAL_ERROR",
                "The saved extension result is invalid.",
            )
        return report

    @staticmethod
    def _extension_outcome_detail(outcome: str) -> str:
        return {
            "added": "The extension was installed.",
            "updated": "The extension was updated.",
            "removed": "The extension was removed.",
            "unchanged": "No extension files changed.",
            "blocked": "The extension was blocked by host validation or policy.",
            "pending_approval": "The extension is waiting for command approval.",
        }.get(outcome, "The extension operation returned a host-defined outcome.")
