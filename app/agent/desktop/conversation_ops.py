"""Conversation handlers: list, create, select, rename, delete, controls and the session snapshot."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import yaml
from agent.config import AgentConfig, validate_graph_recursion_limit
from agent.conversations import (
    ConversationConflictError,
    ConversationError,
    ConversationSnapshot,
    ConversationUnavailableError,
)
from agent.conversations.models import MAX_TITLE_BYTES
from agent.cli.slash_commands import SlashCommand, SlashCommandRegistry, build_default_registry
from agent.desktop.project import project_conversations
from agent.ingest import await_sync_work
from agent.session import ChatSession
from agent.desktop.errors import DesktopServiceError, EventSink
from agent.desktop.turn_ops import _DESKTOP_EXTENSION_COMMAND, _DESKTOP_KNOWLEDGE_COMMANDS


_DESKTOP_SLASH_COMMANDS = frozenset({
    "help",
    "status",
    _DESKTOP_EXTENSION_COMMAND,
    *_DESKTOP_KNOWLEDGE_COMMANDS,
})


_MAX_CONTROL_SNAPSHOTS = 4096


@dataclass(frozen=True)
class _ConversationControlSnapshot:
    thinking_mode: str
    permission_mode: str = "ask"


class _ConversationOps:
    """DesktopService methods moved here unchanged; `self` is the DesktopService."""

    async def _session_list(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        if self._turn_active:
            raise DesktopServiceError(
                "BUSY_TURN",
                "Conversation summaries are unavailable during an active turn.",
                retryable=True,
            )
        project = self._require_opened_project(params["projectId"])
        # The list is the history scan itself: a conversation appears once its
        # first prompt is saved and disappears when its file is deleted.
        summaries = await asyncio.to_thread(
            project_conversations, project["projectId"], self._conversation_repository,
        )
        offset = int(params.get("offset", 0))
        limit = int(params.get("limit", 50))
        page = summaries[offset : offset + limit]
        return {
            "projectId": project["projectId"],
            "status": "ready",
            "issue": None,
            "items": [self._summary_dto(summary) for summary in page],
            "total": len(summaries),
            "offset": offset,
            "limit": limit,
            "hasMore": offset + len(page) < len(summaries),
        }

    async def _session_select(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        if self._turn_or_approval_active:
            raise DesktopServiceError(
                "BUSY_TURN",
                "A conversation cannot be changed during an active turn.",
                retryable=True,
            )
        if self._session_creating:
            raise DesktopServiceError(
                "SESSION_NOT_READY",
                "A desktop session is already being materialized.",
                retryable=True,
            )
        if self._other_operation_active(ignore_reads=True):
            raise DesktopServiceError(
                "SESSION_NOT_READY",
                "The selected conversation cannot change during another operation.",
                retryable=True,
            )
        project = self._require_opened_project(params["projectId"])
        session_id = params["sessionId"]
        self._require_saved_conversation(project["projectId"], session_id)
        if (
            self.session is not None
            and self.session.session_id == session_id
            and self._selected_project_id == project["projectId"]
        ):
            return {
                **self._session_snapshot(self.session),
                "projectId": project["projectId"],
            }

        self._session_creating = True
        try:
            try:
                snapshot = await asyncio.to_thread(
                    self._load_conversation,
                    session_id,
                    project["projectId"],
                )
                if snapshot is None:
                    raise ConversationUnavailableError(
                        "canonical conversation is unavailable"
                    )
            except ConversationError as exc:
                raise DesktopServiceError(
                    "SESSION_NOT_READY",
                    "The stored conversation is unavailable and cannot be selected.",
                ) from exc

            current = self.session
            target = await self._materialize_session(
                self.config,
                load_mcp=self._load_mcp,
                project_id=project["projectId"],
                session_id=session_id,
            )
            control_snapshot = self._control_snapshots.get(session_id)
            if control_snapshot is not None:
                target.set_thinking_mode(control_snapshot.thinking_mode)
            if self.lifecycle != "ready":
                raise DesktopServiceError(
                    "SESSION_NOT_READY",
                    "The desktop backend changed state while selecting a conversation.",
                )
        finally:
            self._session_creating = False

        saved_controls: _ConversationControlSnapshot | None = None
        if current is not None:
            self._clear_installer_for_replacement(current)
            saved_controls = self._capture_controls(current)
        if (
            current is not None
            and saved_controls is not None
            and self._session_saved
        ):
            self._store_control_snapshot(current.session_id, saved_controls)
        self.session = target
        self._selected_project_id = project["projectId"]
        self._session_saved = True
        target_snapshot = self._control_snapshots.get(session_id)
        self._permission_mode = (
            target_snapshot.permission_mode
            if target_snapshot is not None
            else "ask"
        )
        return {
            **self._session_snapshot(target),
            "projectId": project["projectId"],
        }

    async def _session_rename(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        if self._turn_or_approval_active:
            raise DesktopServiceError(
                "BUSY_TURN", "Wait for the active turn before renaming a conversation.",
                retryable=True,
            )
        if self._session_creating or self._other_operation_active(ignore_reads=True):
            raise DesktopServiceError(
                "SESSION_NOT_READY", "Wait for the current conversation operation before renaming.",
                retryable=True,
            )
        project = self._require_opened_project(params["projectId"])
        session_id = params["sessionId"]
        self._require_saved_conversation(project["projectId"], session_id)
        title = params["title"]
        if not isinstance(title, str) or not title.strip() or len(title.strip().encode("utf-8")) > MAX_TITLE_BYTES:
            raise DesktopServiceError(
                "PROTOCOL_INVALID", f"A conversation title must contain 1–{MAX_TITLE_BYTES} UTF-8 bytes.",
            )
        title = title.strip()

        def rename_saved_conversation() -> ConversationSnapshot:
            snapshot = self._load_conversation(session_id, project["projectId"])
            if snapshot is None:
                raise ConversationUnavailableError("canonical conversation is unavailable")
            return self._conversation_repository.rename(
                snapshot, title, updated_at=self._utc_timestamp(datetime.now(timezone.utc)),
            )

        # Keep the existing conversation gate closed until the short write settles.
        self._session_creating = True
        try:
            await await_sync_work(rename_saved_conversation)
        except ConversationError as exc:
            raise DesktopServiceError(
                "SESSION_NOT_READY", "The saved conversation could not be renamed. Refresh and try again.",
                retryable=True,
            ) from exc
        finally:
            self._session_creating = False
        return {"projectId": project["projectId"], "sessionId": session_id, "title": title}

    async def _session_delete(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        if self._turn_or_approval_active:
            raise DesktopServiceError(
                "BUSY_TURN", "Stop the active turn and wait for it to finish before deleting.",
                retryable=True,
            )
        # Delete also waits for concurrent reads of the history it changes.
        if self._session_creating or self._other_operation_active(ignore_reads=False):
            raise DesktopServiceError(
                "SESSION_NOT_READY", "Wait for the current conversation operation before deleting.",
                retryable=True,
            )
        project = self._require_opened_project(params["projectId"])
        session_id = params["sessionId"]
        selected = (
            self.session is not None and self.session.session_id == session_id
            and self._selected_project_id == project["projectId"]
        )
        if not selected:
            # The selected session may not have a saved prompt yet.
            self._require_saved_conversation(project["projectId"], session_id)
        try:
            snapshot = self._load_conversation(session_id, project["projectId"])
        except ConversationError as exc:
            raise DesktopServiceError(
                "SESSION_NOT_READY", "The stored conversation is unavailable and cannot be deleted.",
            ) from exc
        if selected:
            await self._shutdown_session(allow_current_project_operation=True)
        try:
            if snapshot is not None:
                self._conversation_repository.delete(snapshot)
        except ConversationError as exc:
            raise DesktopServiceError(
                "SESSION_NOT_READY", "The conversation could not be deleted. Refresh and try again.",
                retryable=True,
            ) from exc
        self._control_snapshots.pop(session_id, None)
        return {"projectId": project["projectId"], "sessionId": session_id, "status": "deleted"}

    def _require_saved_conversation(self, project_id: str, session_id: str) -> None:
        """A conversation is listed exactly when its saved file is in the opened history.

        Only a cheap existence check runs here, on the event loop; the
        handler's own threaded read still rejects a file whose project
        ownership differs (``ConversationConflictError``).
        """
        try:
            saved = self._conversation_repository.path_for(session_id).is_file()
        except (ConversationError, OSError):
            saved = False
        if not saved:
            raise DesktopServiceError(
                "PROTOCOL_INVALID", f"Conversation {session_id!r} is not saved in project {project_id!r}.",
            )

    def _load_conversation(
        self,
        session_id: str,
        project_id: str,
    ) -> ConversationSnapshot | None:
        snapshot = self._conversation_repository.load_optional(session_id)
        if snapshot is not None and snapshot.document.project_id != project_id:
            raise ConversationConflictError(
                "conversation belongs to a different project"
            )
        return snapshot

    async def _materialize_session(
        self,
        config: AgentConfig,
        *,
        load_mcp: bool,
        project_id: str,
        session_id: str | None = None,
    ) -> ChatSession:
        # Every factory, production or test, receives the same complete arguments.
        session = await self._session_factory(
            config,
            load_mcp=load_mcp,
            progress_cb=self._on_session_progress,
            bash_approval_handler=self._desktop_bash_approval,
            bash_command_runner=self._bash_command_runner,
            conversation_repository=self._conversation_repository,
            project_id=project_id,
            system_prompt=self._project_system_prompt(self._require_project()),
            extra_tools=[self._document_tool, self._bibliography_tool],
            operation_approval_handler=self._desktop_operation_approval,
            citation_bibliography_path=lambda: self._project_bibliography_path(project_id),
            session_id=session_id,
        )
        session.set_final_text_validator(
            lambda text, errors: self._validate_final_text_before_record(
                session.session_id,
                text,
                errors,
            )
        )
        session.set_prompt_persisted_callback(
            lambda: self._on_prompt_persisted(session)
        )
        return session

    def _clear_installer_for_replacement(self, session: ChatSession) -> None:
        cleanup = session.clear_skill_installer()
        if cleanup.get("cleanup_conflict"):
            raise DesktopServiceError(
                "SESSION_NOT_READY",
                self._bounded_text(
                    f"Installation cleanup stopped: {cleanup.get('cleanup_detail')}. "
                    f"Preserved backup: {cleanup.get('backup_path')}", 4_096,
                ),
            )

    def _capture_controls(self, session: ChatSession) -> _ConversationControlSnapshot:
        return _ConversationControlSnapshot(
            thinking_mode=str(session.thinking_mode),
            permission_mode=self._permission_mode,
        )

    def _store_control_snapshot(
        self,
        session_id: str,
        snapshot: _ConversationControlSnapshot,
    ) -> None:
        self._control_snapshots.pop(session_id, None)
        while len(self._control_snapshots) >= _MAX_CONTROL_SNAPSHOTS:
            self._control_snapshots.pop(next(iter(self._control_snapshots)))
        self._control_snapshots[session_id] = snapshot

    async def _session_create(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        if self._session_creating:
            raise DesktopServiceError(
                "SESSION_NOT_READY",
                "A desktop session is already being created.",
                retryable=True,
            )
        if self._turn_or_approval_active:
            raise DesktopServiceError("BUSY_TURN", "A session turn is still active.")
        if self._other_operation_active(ignore_reads=True):
            raise DesktopServiceError(
                "SESSION_NOT_READY",
                "A new conversation cannot be created during another operation.",
                retryable=True,
            )
        project_id = params.get("projectId") or self._selected_project_id
        if project_id is None:
            raise DesktopServiceError(
                "SESSION_NOT_READY", "No local project is available."
            )
        self._require_opened_project(project_id)
        load_mcp = bool(params.get("loadMcp", True))
        graph_limit = params.get(
            "graphRecursionLimit", self.config.graph_recursion_limit
        )
        validate_graph_recursion_limit(graph_limit)
        config = AgentConfig(
            **{
                **self.config.__dict__,
                "graph_recursion_limit": graph_limit,
            }
        )
        self._session_creating = True
        current = self.session
        try:
            session = await self._materialize_session(
                config,
                load_mcp=load_mcp,
                project_id=project_id,
            )
            if self.lifecycle != "ready":
                raise DesktopServiceError(
                    "SESSION_NOT_READY",
                    "The desktop backend changed state while creating the session.",
                )
        finally:
            self._session_creating = False
        saved_controls: _ConversationControlSnapshot | None = None
        if current is not None:
            self._clear_installer_for_replacement(current)
            saved_controls = self._capture_controls(current)
        if (
            current is not None
            and saved_controls is not None
            and self._session_saved
        ):
            self._store_control_snapshot(current.session_id, saved_controls)
        self.config = config
        self.session = session
        self._load_mcp = load_mcp
        self._selected_project_id = project_id
        self._session_saved = False
        self._permission_mode = "ask"
        return {
            **self._session_snapshot(session),
            "projectId": project_id,
        }

    async def _session_set_thinking(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        session = self._require_idle_session()
        session.set_thinking_mode(params["mode"])
        return self._session_snapshot(session)

    async def _session_set_permission(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        session = self._require_idle_session()
        mode = params.get("permissionMode")
        if mode not in ("ask", "bypass"):
            raise DesktopServiceError(
                "PROTOCOL_INVALID",
                f"Unknown permission mode: {mode}",
            )
        self._permission_mode = str(mode)
        return {
            "sessionId": session.session_id,
            "permissionMode": self._permission_mode,
        }

    def _session_slash_registry(self, session: ChatSession) -> SlashCommandRegistry:
        return self._slash_registry_override or build_default_registry(session)

    @staticmethod
    def _desktop_command_eligible(command: SlashCommand, session: ChatSession) -> bool:
        if command.name == "citation":
            try:
                runtime = session.skill_runtime_for("citation")
            except (KeyError, ValueError, OSError, yaml.YAMLError):
                return False
            return (runtime.name == "citation"
                    and "citation_workflow" in runtime.tool_access.effective_tools)
        return command.skill_name is not None or command.name in _DESKTOP_SLASH_COMMANDS

    def _session_snapshot(self, session: ChatSession) -> dict[str, Any]:
        status = session.status_snapshot()
        commands = [
            command for command in self._session_slash_registry(session).all_commands()
            if self._desktop_command_eligible(command, session)
        ]
        if len(commands) > 512 or any(
            len(command.name.encode("utf-8")) > 64 for command in commands
        ):
            raise DesktopServiceError(
                "PROTOCOL_INVALID", "Session slash command catalog exceeds protocol limits.",
            )
        return {
            "sessionId": session.session_id,
            "turnCount": int(status.get("turn_count", 0)),
            "graphRecursionLimit": int(session.config.graph_recursion_limit),
            "thinkingMode": session.thinking_mode,
            "permissionMode": self._permission_mode,
            "slashCommands": [
                {"name": command.name, "description": self._bounded_text(command.description, 1_024)}
                for command in commands
            ],
            "loadedSkills": [
                self._bounded_text(skill.name, 256)
                for skill in session.loaded_skills[:512]
                if skill.name
            ],
            "mcpFamilies": sorted(set(session.mcp_families.values()))[:512],
            "startupDiagnostics": [
                self._bounded_text(str(item), 4_096)
                for item in session.extension_startup_diagnostics[:512]
                if str(item)
            ],
            "extensionRevision": int(session.running_extension_revision),
        }
