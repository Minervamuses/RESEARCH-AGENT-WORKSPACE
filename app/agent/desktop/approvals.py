"""Single-operation consent: approval events, Bash and tool approvals, and their resolution."""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from agent.desktop.documents import utf16_length, utf16_to_index
from agent.extensions.paths import resolve_extension_paths
from agent.ingest import current_local_work
from agent.desktop.errors import DesktopServiceError, EventSink


_MAX_APPROVAL_COMMAND_BYTES = 65_536


_MAX_APPROVAL_DESCRIPTION_BYTES = 4_096


_SECRET_APPROVAL_CONTEXT = re.compile(
    r"(?i)(?:authorization\s*:|(?:api[_-]?key|access[_-]?token|secret|password)\s*[:=])\s*\S+"
)


_SECRET_FLAG_VALUE = re.compile(
    r"(?i)(?:^|\s)--?(?:api[-_]?key|access[-_]?token|token|secret|password|private[-_]?key)(?:\s+|[:=])\S+"
)


_CREDENTIAL_URL = re.compile(r"(?i)https?://[^\s/:@]+:[^\s/@]+@")


@dataclass(frozen=True)
class _PendingApproval:
    approval_id: str
    parent_request_id: str
    turn_id: str
    expires_at: datetime
    future: asyncio.Future[bool]


class _ApprovalOps:
    """DesktopService methods moved here unchanged; `self` is the DesktopService."""

    async def _single_operation_approval(
        self, payload: dict[str, Any], *, event_sink: EventSink | None = None,
        parent_request_id: str | None = None, turn_id: str | None = None,
        permission_mode: str | None = None, document_context: dict[str, Any] | None = None,
    ) -> tuple[bool, dict[str, Any] | None]:
        """Serialize single-operation consent without changing correctness checks."""
        scope = current_local_work()
        if scope is not None:
            scope.check_cancelled()
        turn = self._running_turn
        mode = permission_mode or (turn.permission_mode if turn is not None else self._permission_mode)
        if mode == "bypass":
            return True, document_context
        sink = event_sink or (turn.event_sink if turn is not None else None)
        active_owner = turn.turn_id if self._turn_active and turn is not None else None
        parent = parent_request_id or (turn.parent_request_id if turn is not None else None) or getattr(sink, "request_id", None)
        operation_turn = turn_id or (turn.turn_id if turn is not None else None) or uuid.uuid4().hex
        if sink is None or not isinstance(parent, str):
            return False, document_context
        async with self._operation_approval_lock:
            if scope is not None:
                scope.check_cancelled()
            current = self._running_turn
            if active_owner is not None and (not self._turn_active or current is None or current.turn_id != active_owner):
                return False, document_context
            if self._pending_approval is not None:
                return False, document_context
            now = datetime.now(timezone.utc)
            pending = _PendingApproval(
                approval_id=uuid.uuid4().hex, parent_request_id=parent,
                turn_id=operation_turn, expires_at=now + timedelta(seconds=self._approval_timeout_seconds),
                future=asyncio.get_running_loop().create_future(),
            )
            self._pending_approval = pending
            if document_context is not None:
                self._approval_document_snapshots[pending.approval_id] = document_context
            try:
                sink("approval.required", {
                    **payload, "approvalId": pending.approval_id,
                    "parentRequestId": parent, "turnId": operation_turn,
                    "createdAt": self._utc_timestamp(now),
                    "expiresAt": self._utc_timestamp(pending.expires_at),
                })
                approved = bool(await asyncio.wait_for(
                    asyncio.shield(pending.future), timeout=self._approval_timeout_seconds,
                ))
                if scope is not None:
                    scope.check_cancelled()
                return approved, self._approval_document_snapshots.get(pending.approval_id, document_context)
            except TimeoutError:
                return False, document_context
            except Exception:
                # A failed event delivery cannot grant permission to execute.
                return False, document_context
            finally:
                self._approval_document_snapshots.pop(pending.approval_id, None)
                if self._pending_approval is pending:
                    self._pending_approval = None
                if not pending.future.done():
                    pending.future.cancel()

    async def _operation_approval(
        self, operation: str, target: str, description: str, *,
        parameters: Any = None, event_sink: EventSink | None = None,
    ) -> bool:
        scope = current_local_work()
        if scope is not None:
            scope.check_cancelled()
        turn = self._running_turn
        mode = turn.permission_mode if turn is not None else self._permission_mode
        if mode == "bypass":
            return True
        summary = json.dumps(parameters, ensure_ascii=False, sort_keys=True, default=str) if parameters is not None else None
        if (summary is not None and len(summary.encode("utf-8")) > 8192) or not self._approval_context_is_safe(target, description):
            return False
        if summary is not None and not self._approval_context_is_safe(summary, description):
            return False
        payload = {"operation": operation, "targetPath": target, "description": description}
        if summary is not None:
            payload["parametersSummary"] = summary
        approved, _context = await self._single_operation_approval(
            payload, event_sink=event_sink, permission_mode=mode,
        )
        return approved

    async def _require_operation_approval(
        self, operation: str, target: str, description: str, *,
        parameters: Any = None, event_sink: EventSink | None = None,
    ) -> None:
        if not await self._operation_approval(
            operation, target, description, parameters=parameters, event_sink=event_sink,
        ):
            raise DesktopServiceError("APPROVAL_DENIED", "The operation was denied or its approval expired; no write occurred.")

    async def _desktop_operation_approval(self, name: str, args: dict[str, Any]) -> bool:
        """Approve executable tools after the graph's existing admission check."""
        family = self.session.mcp_families.get(name) if self.session is not None else None
        citation_save = name == "citation_workflow" and args.get("action") == "save"
        skill_install = name == "skill_install" and args.get("action") in {"preview", "apply"}
        mcp_call = family is not None and family != "desktop_document"
        if not (citation_save or skill_install or mcp_call):
            return True
        turn = self._running_turn
        if not self._turn_active or turn is None or turn.parent_request_id is None:
            return False
        if citation_save:
            policy = self.session.citation_policy
            loaded_service = policy.loaded_service
            library_path = (
                loaded_service.library_path if loaded_service is not None else policy.bibliography_path()
            )
            if library_path is not None:
                target = str(Path(library_path).expanduser().resolve())
                description = (
                    "Verify this batch of citation candidates and add the verified works "
                    f"to the project bibliography {target}."
                )
            else:
                # A malformed bibliography setting leaves the project without one.
                target = "(not written to disk)"
                description = (
                    "Verify this batch of citation candidates for this conversation only; "
                    "the project has no usable bibliography, so nothing is written to disk."
                )
            return await self._operation_approval(
                "citation.save", target, description, parameters=args.get("works"),
            )
        if skill_install:
            context = self.session.installer_context
            paths = self.session.installer_paths or resolve_extension_paths(self.config)
            source = context.get("source_path") or context.get("source_zip")
            target = str(paths.state_root if args["action"] == "apply" else source or paths.dropin_root)
            return await self._operation_approval(
                "extension.install", target,
                f"{args['action'].capitalize()} the selected skill installation.",
                parameters={"arguments": args, "source": source, "installationRoot": str(paths.state_root)},
            )
        return await self._operation_approval(
            "mcp.call", f"{family}/{name}", f"Call the installed MCP tool {name}.", parameters=args,
        )

    async def _document_operation_approval(
        self, *, event_sink: EventSink | None, parent_request_id: str,
        turn_id: str, operation: str, context: dict[str, Any], permission_mode: str,
    ) -> tuple[bool, dict[str, Any]]:
        range_start = context.get("rangeStartUtf16", 0)
        range_end = context.get("rangeEndUtf16", utf16_length(context["sourceText"]))
        source_start = utf16_to_index(context["sourceText"], range_start)
        source_end = utf16_to_index(context["sourceText"], range_end)
        first_line = len(re.findall(r"\r\n|\r|\n", context["sourceText"][:source_start])) + 1
        last_line = len(re.findall(r"\r\n|\r|\n", context["sourceText"][:max(source_start, source_end - 1)])) + 1
        approved, current = await self._single_operation_approval({
            "operation": operation, "targetPath": context["path"],
            "rangeStartUtf16": range_start, "rangeEndUtf16": range_end,
            "description": f"Save {Path(context['path']).name}, source lines {first_line}–{last_line}.",
        }, event_sink=event_sink, parent_request_id=parent_request_id, turn_id=turn_id,
            permission_mode=permission_mode, document_context=context)
        return approved, current or context

    @staticmethod
    def _approval_context_is_safe(command: str, description: str) -> bool:
        if (
            not command.strip()
            or not description.strip()
            or len(command.encode("utf-8")) > _MAX_APPROVAL_COMMAND_BYTES
            or len(description.encode("utf-8")) > _MAX_APPROVAL_DESCRIPTION_BYTES
            or any(ord(character) < 32 or ord(character) == 127 for character in command)
            or any(
                ord(character) < 32 or ord(character) == 127
                for character in description
            )
        ):
            return False
        combined = f"{command}\n{description}"
        return not (
            _SECRET_APPROVAL_CONTEXT.search(combined)
            or _SECRET_FLAG_VALUE.search(combined)
            or _CREDENTIAL_URL.search(combined)
        )

    def _desktop_bash_approval(
        self,
        command: str,
        description: str,
        execution_timeout_seconds: int,
    ) -> bool:
        turn = self._running_turn
        loop = turn.loop if turn is not None else None
        if loop is None or loop.is_closed():
            return False
        if (
            not self._turn_active
            or turn.event_sink is None
            or turn.parent_request_id is None
        ):
            return False
        if turn.permission_mode == "bypass":
            return True
        scope = current_local_work()
        if scope is not None:
            return scope.run_async(lambda: self._stage_bash_approval(
                command, description, execution_timeout_seconds,
            ))
        staged = asyncio.run_coroutine_threadsafe(
            self._stage_bash_approval(
                command,
                description,
                execution_timeout_seconds,
            ),
            loop,
        )
        owner_turn = turn.turn_id
        while True:
            try:
                return bool(staged.result(timeout=1.0))
            except TimeoutError:
                # Another operation can own the single approval UI. Its wait
                # must not consume this operation's own approval deadline.
                current = self._running_turn
                if not self._turn_active or current is None or current.turn_id != owner_turn or loop.is_closed():
                    staged.cancel()
                    return False
            except Exception:
                staged.cancel()
                return False

    async def _stage_bash_approval(
        self, command: str, description: str, execution_timeout_seconds: int,
    ) -> bool:
        turn = self._running_turn
        if (not self._turn_active or turn is None or turn.event_sink is None
                or turn.parent_request_id is None
                or not self._approval_context_is_safe(command, description)):
            return False
        approved, _context = await self._single_operation_approval({
            "command": command, "description": description,
            "executionTimeoutSeconds": execution_timeout_seconds,
        }, permission_mode=turn.permission_mode)
        return approved

    def _complete_pending_approval(self, approved: bool) -> None:
        pending = self._pending_approval
        if pending is None:
            return
        self._pending_approval = None
        if not pending.future.done():
            pending.future.set_result(bool(approved))

    async def _approval_resolve(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        pending = self._pending_approval
        if self._turn_work is not None and self._turn_active and self._turn_work.stopping:
            self._complete_pending_approval(False)
            raise DesktopServiceError("APPROVAL_DENIED", "The owning turn is stopping.")
        if pending is None or params["approvalId"] != pending.approval_id:
            raise DesktopServiceError(
                "APPROVAL_DENIED",
                "The desktop approval is unknown, expired, or already used.",
            )
        if (
            params.get("parentRequestId") != pending.parent_request_id
            or params.get("turnId") != pending.turn_id
            or datetime.now(timezone.utc) >= pending.expires_at
        ):
            self._complete_pending_approval(False)
            raise DesktopServiceError(
                "APPROVAL_DENIED",
                "The desktop approval no longer matches the active request.",
            )
        approved = bool(params["approved"])
        approval_id = pending.approval_id
        if approval_id in self._approval_document_snapshots and "documentContext" in params:
            self._approval_document_snapshots[approval_id] = self._documents.validate_snapshot(params["documentContext"])
        self._complete_pending_approval(approved)
        return {"approvalId": approval_id, "approved": approved}
