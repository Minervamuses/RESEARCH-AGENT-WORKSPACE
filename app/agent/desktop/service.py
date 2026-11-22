"""Application service exposed through the structured desktop protocol."""

from __future__ import annotations

import asyncio
import importlib.metadata
import os
import platform
import sys
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain_core.tools import StructuredTool

from agent.config import AgentConfig
from agent.conversations import ConversationRepository
from agent.cli.slash_commands import SlashCommandRegistry
from agent.diagnostics import attach_incident, incident_reference
from agent.desktop.project import ProjectError
from agent.desktop.protocol import PROTOCOL_VERSION
from agent.desktop.documents import DocumentError, DocumentWorkspace
from agent.extensions.manager import ExtensionManager, ExtensionPreview
from agent.ingest import diff_folder, ingest_file, ingest_folder, init_workspace, prune_folder
from agent.paths import find_app_root
from agent.session import ChatSession
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
from agent.desktop.turn_ops import _TurnWork
from agent.desktop.conversation_ops import _ConversationOps
from agent.desktop.project_ops import _ProjectOps
from agent.desktop.conversation_ops import _ConversationControlSnapshot


class DesktopService(_ProjectOps, _ConversationOps, _TurnOps, _TurnContextOps, _TranscriptOps, _KnowledgeCommandOps, _ExtensionOps, _DocumentOps, _BibliographyOps, _ApprovalOps, _ErrorMapping):
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


    # --- bibliography.* (adapters over skills.citation) ---------------------


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
