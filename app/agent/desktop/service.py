"""Application service exposed through the structured desktop protocol."""

from __future__ import annotations

import asyncio
import importlib.metadata
import os
import platform
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from langchain_core.messages import SystemMessage
from langchain_core.tools import StructuredTool

from agent.config import AgentConfig, validate_graph_recursion_limit
from agent.conversations import (
    ConversationConflictError,
    ConversationError,
    ConversationRepository,
    ConversationSnapshot,
    ConversationUnavailableError,
)
from agent.conversations.models import MAX_TITLE_BYTES
from agent.cli.slash_commands import SlashCommand, SlashCommandRegistry, build_default_registry
from agent.diagnostics import attach_incident, incident_reference
from agent.desktop.project import (
    ProjectError,
    inspect_project,
    initialize_project,
    open_project_history,
    project_conversations,
)
from agent.desktop.protocol import PROTOCOL_VERSION
from agent.desktop.documents import DocumentError, DocumentWorkspace
from agent.extensions.manager import ExtensionManager, ExtensionPreview
from agent.ingest import (
    await_sync_work,
    run_local_work,
    diff_folder,
    ingest_file,
    ingest_folder,
    init_workspace,
    prune_folder,
)
from agent.paths import find_app_root
from agent.session import ChatSession, SYSTEM_PROMPT
from agent.skills.runtime import SkillSelectionError
from agent.desktop.errors import _ErrorMapping
from agent.desktop.errors import DesktopServiceError, EventSink, _SELF_EXPLANATORY_FAILURE_CODES, logger
from agent.desktop.approvals import _ApprovalOps
from agent.desktop.bibliography_ops import _BibliographyOps
from agent.desktop.approvals import _PendingApproval
from agent.desktop.document_ops import _DocumentOps
from agent.desktop.extension_ops import _ExtensionOps
from agent.desktop.document_ops import _DocumentCandidate
from agent.desktop.command_ops import _KnowledgeCommandOps
from agent.desktop.transcript import _TranscriptOps
from agent.desktop.command_ops import DesktopKnowledgeOperations, _PrunePreview
from agent.desktop.turn_context import _TurnContextOps
from agent.desktop.turn_ops import _TurnOps
from agent.desktop.turn_ops import _DESKTOP_EXTENSION_COMMAND, _DESKTOP_KNOWLEDGE_COMMANDS, _TurnWork


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


class DesktopService(_TurnOps, _TurnContextOps, _TranscriptOps, _KnowledgeCommandOps, _ExtensionOps, _DocumentOps, _BibliographyOps, _ApprovalOps, _ErrorMapping):
    """Own one backend lifecycle and adapt existing domain APIs to safe DTOs."""

    def __init__(
        self,
        *,
        original_cwd: Path | None = None,
        environ: Mapping[str, str] | None = None,
        config: AgentConfig | None = None,
        extension_manager: ExtensionManager | None = None,
        session_factory: Callable[..., Any] | None = None,
        slash_registry: SlashCommandRegistry | None = None,
        conversation_repository: ConversationRepository | None = None,
        knowledge_operations: DesktopKnowledgeOperations | None = None,
        bash_command_runner: Callable[..., Any] | None = None,
        approval_timeout_seconds: float = 60.0,
    ) -> None:
        self.original_cwd = (original_cwd or Path.cwd()).expanduser().resolve()
        self.environ = dict(os.environ if environ is None else environ)
        self.config = config or AgentConfig()
        self.lifecycle = "ready"
        self.session: ChatSession | None = None

        self._session_factory = session_factory or ChatSession.create
        self._bash_command_runner = bash_command_runner
        self._approval_timeout_seconds = max(
            0.01,
            min(float(approval_timeout_seconds), 3_600.0),
        )
        self._slash_registry_override = slash_registry
        self._knowledge_operations = knowledge_operations or DesktopKnowledgeOperations(
            init_workspace=init_workspace,
            ingest_file=ingest_file,
            ingest_folder=ingest_folder,
            diff_folder=diff_folder,
            prune_folder=prune_folder,
        )
        self._extension_manager = extension_manager or ExtensionManager(self.config)
        # An explicit project open is the only entry to conversation storage.
        self._conversation_repository: ConversationRepository | None = None
        self._injected_repository = conversation_repository
        self._project: dict[str, Any] | None = None
        self._selected_project_id: str | None = None
        self._workspace_opening = False
        self._project_operation_count = 0
        self._project_read_count = 0
        self._project_epoch = 0
        # Whether the current session's conversation has a saved prompt, so it
        # appears in the project's conversation list.
        self._session_saved = False
        self._control_snapshots: dict[str, _ConversationControlSnapshot] = {}
        self._permission_mode: str = "ask"
        self._load_mcp = True
        self._session_creating = False
        self._turn_active = False
        self._turn_work: _TurnWork | None = None
        self._last_stopped_turn: _TurnWork | None = None
        self._session_closing = False
        self._knowledge_active = False
        self._extension_active = False
        self._pending_approval: _PendingApproval | None = None
        self._extension_previews: dict[str, ExtensionPreview] = {}
        self._composer_prune_preview: tuple[str, _PrunePreview] | None = None
        self._documents = DocumentWorkspace()
        self._document_candidates: dict[str, _DocumentCandidate] = {}
        self._operation_approval_lock = asyncio.Lock()
        self._document_apply_lock = asyncio.Lock()
        self._document_tool_lock = asyncio.Lock()
        self._approval_document_snapshots: dict[str, dict[str, Any]] = {}
        self._document_tool = StructuredTool.from_function(
            coroutine=self._desktop_document_edit,
            name="document_edit",
            description=(
                "Replace only the selected source range in the active desktop document. "
                "Supply replacement_text for that range only. For a frozen document reference, "
                "supply its reference_id. When the user's requests identify several references, "
                "handle each requested edit in order with its own reference_id. Ask for clarification "
                "only when the target or requested change is unclear. Chat references are read-only. For analysis, answer without "
                "calling this tool. The tool waits for the user's single-operation approval "
                "and the actual version-checked save. Only status=saved proves a write. "
                "Never use bash or another file tool to bypass this document operation."
            ),
        )

        self._bibliography_tool = StructuredTool.from_function(
            func=self._desktop_bibliography_lookup,
            name="bibliography_lookup",
            description=(
                "Read-only search of the open project's bibliography (CSL-JSON). Give a key, "
                "author, title words, year, or DOI; returns up to 20 entries with key, authors, "
                "year, title, and DOI. Cite documents only with keys this tool returns: "
                "[@key] in Markdown, \\cite{key} in LaTeX. It never writes."
            ),
        )

    @property
    def permission_mode(self) -> str:
        return self._permission_mode

    async def dispatch(
        self,
        method: str,
        params: dict[str, Any],
        *,
        event_sink: EventSink | None = None,
    ) -> dict[str, Any]:
        """Execute one allowlisted protocol method and return a safe DTO."""
        handlers: dict[str, Callable[[dict[str, Any], EventSink | None], Any]] = {
            "runtime.diagnostics": self._runtime_diagnostics,
            "session.create": self._session_create,
            "session.list": self._session_list,
            "session.select": self._session_select,
            "session.rename": self._session_rename,
            "session.delete": self._session_delete,
            "session.transcript": self._session_transcript,
            "session.turn": self._session_turn,
            "session.stop": self._session_stop,
            "workspace.select": self._workspace_select,
            "document.open": self._document_open,
            "document.save": self._document_save,
            "document.apply": self._document_apply,
            "session.set_thinking": self._session_set_thinking,
            "session.set_permission": self._session_set_permission,
            "extensions.preview": self._extensions_preview,
            "extensions.apply": self._extensions_apply,
            "approval.resolve": self._approval_resolve,
            "runtime.shutdown": self._runtime_shutdown,
            "bibliography.inspect": self._bibliography_inspect,
            "bibliography.render": self._bibliography_render,
            "bibliography.set_style": self._bibliography_set_style,
            "bibliography.remove": self._bibliography_remove,
            "bibliography.add": self._bibliography_add,
            "bibliography.export": self._bibliography_export,
        }
        handler = handlers.get(method)
        if handler is None:
            raise DesktopServiceError(
                "PROTOCOL_INVALID", f"Unknown desktop method: {method}"
            )
        if self.lifecycle == "shutting_down" and method != "runtime.diagnostics":
            raise DesktopServiceError(
                "SESSION_NOT_READY", "The desktop backend is shutting down."
            )
        if self.lifecycle == "stopped" and method not in {
            "runtime.diagnostics",
            "runtime.shutdown",
        }:
            raise DesktopServiceError(
                "SESSION_NOT_READY", "The desktop backend is shutting down or stopped."
            )
        if self._session_closing and method != "runtime.diagnostics":
            raise DesktopServiceError(
                "SESSION_NOT_READY", "The desktop session is shutting down."
            )
        project_operation = (
            method.startswith(("document.", "bibliography."))
            or method.startswith("session.")
        )
        project_operation_admitted = False
        project_read = method in {"session.list", "session.transcript"}
        try:
            if self._workspace_opening and method != "runtime.diagnostics":
                raise DesktopServiceError(
                    "SESSION_NOT_READY", "Wait for the project open operation to finish.", retryable=True,
                )
            if project_operation:
                self._require_project()
                self._project_operation_count += 1
                self._project_read_count += int(project_read)
                project_operation_admitted = True
            return await handler(params, event_sink)
        except (DocumentError, SkillSelectionError, ProjectError) as exc:
            error = DesktopServiceError("PROTOCOL_INVALID", str(exc))
            if method == "session.turn":
                error = self._with_turn_lifecycle(error, method, params)
            raise error from exc
        except DesktopServiceError as exc:
            if method in {"session.turn", "extensions.apply"}:
                raise self._with_turn_lifecycle(exc, method, params) from exc
            raise
        except Exception as exc:
            mapped = self._map_exception(method, exc)
            if mapped.code in _SELF_EXPLANATORY_FAILURE_CODES:
                logger.warning(
                    "Desktop method %s returned %s (%s)",
                    method,
                    mapped.code,
                    type(exc).__name__,
                )
            else:
                # Reuse the session's incident when it already logged the
                # traceback; otherwise this is the first layer to see it.
                incident, is_new = attach_incident(exc)
                (logger.error if mapped.code == "INTERNAL_ERROR" else logger.warning)(
                    "Desktop method %s returned %s (incident %s): %s",
                    method,
                    mapped.code,
                    incident,
                    type(exc).__name__,
                    exc_info=exc if is_new else None,
                )
                mapped = DesktopServiceError(
                    mapped.code,
                    f"{mapped} {incident_reference(incident, exc)}",
                    retryable=mapped.retryable,
                    details=mapped.details,
                )
            if method in {"session.turn", "extensions.apply"}:
                mapped = self._with_turn_lifecycle(mapped, method, params)
            raise mapped from exc
        finally:
            if project_operation_admitted:
                self._project_operation_count -= 1
                self._project_read_count -= int(project_read)


    async def _runtime_diagnostics(
        self, _params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        session = self.session
        mcp_families = (
            sorted(set(session.mcp_families.values())) if session is not None else []
        )
        mcp_diagnostics = (
            [
                self._bounded_text(str(item), 4_096)
                for item in session.extension_startup_diagnostics[:512]
                if str(item)
            ]
            if session is not None
            else []
        )
        try:
            backend_version = importlib.metadata.version("agent")
        except importlib.metadata.PackageNotFoundError:
            backend_version = "0.1.0"
        conda_environment = self.environ.get("CONDA_DEFAULT_ENV", "").strip() or None
        conda_prefix = self.environ.get("CONDA_PREFIX", "").strip() or None
        return {
            "backendState": self.lifecycle,
            "platform": "linux",
            "appRoot": str(find_app_root().resolve()),
            "workingDirectory": str(Path.cwd().resolve()),
            "originalWorkingDirectory": str(self.original_cwd),
            "pythonVersion": platform.python_version(),
            "sysPrefix": str(Path(sys.prefix).resolve()),
            "condaEnvironment": conda_environment,
            "condaPrefix": str(Path(conda_prefix).resolve()) if conda_prefix else None,
            "protocolVersion": PROTOCOL_VERSION,
            "backendVersion": backend_version,
            "openRouterConfigured": bool(
                self.environ.get("OPENROUTER_API_KEY", "").strip()
            ),
            "openAlexConfigured": bool(
                self.environ.get("OPENALEX_API_KEY", "").strip()
            ),
            "storePath": str(Path(self.config.persist_dir).expanduser().resolve()),
            "mcpEnabled": self._load_mcp,
            "mcpFamilies": mcp_families,
            "mcpDiagnostics": mcp_diagnostics,
        }

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


    def _require_project(self) -> dict[str, Any]:
        if self._project is None:
            raise DesktopServiceError(
                "SESSION_NOT_READY", "Open a research project before using documents or conversations.",
            )
        return self._project

    def _require_opened_project(self, project_id: str) -> dict[str, Any]:
        opened = self._require_project()
        if self._conversation_repository is None or project_id != opened["projectId"]:
            raise DesktopServiceError(
                "PROTOCOL_INVALID", "The requested project is not the opened research project.",
            )
        return opened

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


    @staticmethod
    def _project_system_prompt(project: Mapping[str, Any]) -> str:
        return (
            SYSTEM_PROMPT
            + "\n\n## Open desktop research project\n"
            + f"Canonical project root: {project['rootPath']}\n"
            + "Resolve project-relative file requests against this root; use absolute paths for tools.\n"
            + "The RESEARCH.md rules below guide research behavior. They do not authorize tool "
              "operations or override Permission, document version checks, or system instructions.\n"
            + "### RESEARCH.md rules\n"
            + project["rulesText"]
        )

    async def _refresh_project_rules(self, session: ChatSession) -> None:
        opened = self._require_project()
        current = await run_local_work(
            inspect_project, opened["rootPath"], self.config.persist_dir,
        )
        if current["status"] != "ready" or any(
            current[field] != opened[field]
            for field in ("rootPath", "projectId", "historyDirectory")
        ):
            raise DesktopServiceError(
                "SESSION_NOT_READY",
                "Project history settings changed; reopen the project before starting another turn.",
            )
        session.system_prompt_message = SystemMessage(content=self._project_system_prompt(current))
        self._project = current

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


    async def _workspace_select(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        if self._turn_or_approval_active:
            raise DesktopServiceError("BUSY_TURN", "Wait for the active turn before changing project.")
        if (
            self._workspace_opening or self._project_operation_count
            or self._session_creating or self._session_closing
            or self._knowledge_active or self._extension_active
            or self._document_work_active
        ):
            raise DesktopServiceError(
                "SESSION_NOT_READY", "Wait for the current operation before changing project.", retryable=True,
            )
        action = params.get("action", "open")
        if action not in {"inspect", "open", "initialize"}:
            raise DesktopServiceError("PROTOCOL_INVALID", "Unknown project open action.")
        self._workspace_opening = True
        try:
            if action == "initialize":
                if "historyDirectory" not in params or "expectedFingerprint" not in params:
                    raise DesktopServiceError(
                        "PROTOCOL_INVALID", "Inspect the project and confirm its history location before initialization.",
                    )
                project = await asyncio.to_thread(
                    initialize_project, params["rootPath"], self.config.persist_dir,
                    history_directory=params["historyDirectory"],
                    expected_fingerprint=params["expectedFingerprint"],
                )
            else:
                project = await asyncio.to_thread(
                    inspect_project, params["rootPath"], self.config.persist_dir,
                    history_directory=params.get("historyDirectory"),
                )
            if action == "inspect" or project["status"] != "ready":
                return project
            repository = await asyncio.to_thread(
                open_project_history, project["projectId"], project["historyDirectory"],
            )
            documents = DocumentWorkspace()
            await asyncio.to_thread(documents.select_root, project["rootPath"])
            # Injection never establishes ownership or skips the explicit open boundary.
            if self._injected_repository is not None and self._injected_repository.root.resolve() == repository.root.resolve():
                repository = self._injected_repository
            if self.lifecycle != "ready":
                raise DesktopServiceError("SESSION_NOT_READY", "The backend changed state while opening the project.")
            # Cleanup may fail; commit the new binding only after it succeeds.
            await self._shutdown_session()
            self._documents = documents
            self._conversation_repository = repository
            self._project = project
            self._selected_project_id = project["projectId"]
            self._project_epoch += 1
            self._document_candidates.clear()
            self._approval_document_snapshots.clear()
            return {**project, "status": "opened"}
        finally:
            self._workspace_opening = False


    # --- bibliography.* (adapters over skills.citation) ---------------------


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

    async def _runtime_shutdown(
        self, _params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        if self.lifecycle == "stopped":
            return {"status": "stopped"}
        if self._session_creating:
            raise DesktopServiceError(
                "SESSION_NOT_READY",
                "A desktop session is still being created.",
                retryable=True,
            )
        if self._turn_or_approval_active:
            raise DesktopServiceError(
                "BUSY_TURN", "A session turn is still active.", retryable=True
            )
        self._raise_if_knowledge_or_extension_active()
        self.lifecycle = "shutting_down"
        try:
            await self._shutdown_session()
        except DesktopServiceError:
            self.lifecycle = "ready"
            raise
        self.lifecycle = "stopped"
        return {"status": "stopped"}

    async def _shutdown_session(
        self, *, allow_current_project_operation: bool = False,
    ) -> dict[str, Any]:
        if self._session_creating:
            raise DesktopServiceError(
                "SESSION_NOT_READY",
                "A desktop session is still being created.",
                retryable=True,
            )
        if self._turn_or_approval_active:
            raise DesktopServiceError(
                "BUSY_TURN", "A session turn is still active.", retryable=True
            )
        if self._session_closing:
            raise DesktopServiceError(
                "SESSION_NOT_READY",
                "The desktop session is already shutting down.",
                retryable=True,
            )
        self._raise_if_knowledge_or_extension_active()
        if (
            self._document_work_active
            or self._project_operation_count > int(allow_current_project_operation)
        ):
            raise DesktopServiceError(
                "SESSION_NOT_READY", "Wait for the current document or conversation operation.", retryable=True,
            )
        session = self.session
        if session is None:
            self._session_saved = False
            self._control_snapshots.clear()
            self._clear_session_caches()
            return {"status": "no_session"}
        self._session_closing = True
        try:
            self._clear_installer_for_replacement(session)
            self.session = None
        finally:
            self._session_closing = False
        self._load_mcp = True
        self._session_saved = False
        self._control_snapshots.clear()
        self._clear_session_caches()
        self._permission_mode = "ask"
        return {"status": "stopped"}

    def _clear_session_caches(self) -> None:
        self._complete_pending_approval(False)
        self._extension_previews.clear()
        self._composer_prune_preview = None

    def _require_session(self) -> ChatSession:
        self._require_project()
        if self._session_creating:
            raise DesktopServiceError(
                "SESSION_NOT_READY",
                "A desktop session is being materialized.",
                retryable=True,
            )
        if self._session_closing:
            raise DesktopServiceError(
                "SESSION_NOT_READY", "The desktop session is shutting down."
            )
        if self.session is None:
            raise DesktopServiceError(
                "SESSION_NOT_READY", "No desktop chat session is ready."
            )
        return self.session

    # Shared busy queries (U21): each checkpoint keeps its own order, code,
    # message and retryable flag; only the repeated conditions live here.
    @property
    def _turn_or_approval_active(self) -> bool:
        """A turn is running (or held by an unfinished Stop) or an approval is pending."""
        return self._turn_active or self._pending_approval is not None

    @property
    def _document_work_active(self) -> bool:
        return self._document_apply_lock.locked() or self._document_tool_lock.locked()

    def _other_operation_active(self, *, ignore_reads: bool) -> bool:
        """Knowledge, extension or document work, or a project request besides this one."""
        others = self._project_operation_count - (self._project_read_count if ignore_reads else 0)
        return self._knowledge_active or self._extension_active or self._document_work_active or others > 1

    def _raise_if_knowledge_or_extension_active(
        self, knowledge_message: str = "A knowledge mutation is still active.",
    ) -> None:
        if self._knowledge_active:
            raise DesktopServiceError("BUSY_KNOWLEDGE_MUTATION", knowledge_message, retryable=True)
        if self._extension_active:
            raise DesktopServiceError(
                "BUSY_EXTENSION_OPERATION", "An extension operation is still active.", retryable=True,
            )

    def _require_idle_session(self) -> ChatSession:
        if self._turn_or_approval_active:
            raise DesktopServiceError(
                "BUSY_TURN", "A session turn is still active.", retryable=True
            )
        self._raise_if_knowledge_or_extension_active("A knowledge operation is still active.")
        return self._require_session()

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


    @staticmethod
    def _utc_timestamp(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")


    @staticmethod
    def _bounded_text(text: str, max_bytes: int) -> str:
        encoded = text.encode("utf-8")
        if len(encoded) <= max_bytes:
            return text
        return encoded[:max_bytes].decode("utf-8", errors="ignore")

    @staticmethod
    def _bounded_cache_insert(cache: dict[str, Any], key: str, value: Any) -> None:
        while len(cache) >= 8:
            cache.pop(next(iter(cache)))
        cache[key] = value
