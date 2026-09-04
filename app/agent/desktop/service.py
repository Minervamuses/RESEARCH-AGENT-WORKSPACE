"""Application service exposed through the structured desktop protocol."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.metadata
import json
import logging
import math
import os
import platform
import re
import sys
import uuid
from collections.abc import Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.errors import GraphRecursionError

from agent.config import AgentConfig, validate_graph_recursion_limit
from agent.conversations import (
    ConversationConflictError,
    ConversationError,
    ConversationRepository,
    ConversationSnapshot,
    ConversationTurn,
    ConversationUnavailableError,
    ToolActivitySummary,
)
from agent.conversations.legacy import LegacyChromaReader, LegacyConversationReader
from agent.conversations.migration import ConversationMigrator
from agent.cli.slash_commands import (
    ParsedSlashCommand,
    SlashCommandContext,
    SlashCommandError,
    SlashCommandRegistry,
    SlashCommandResult,
    build_default_registry,
    execute_slash_command,
    parse_slash_command,
)
from agent.desktop.catalog import (
    CATALOG_MAX_SESSIONS,
    DEFAULT_PROJECT_ID,
    CatalogError,
    CatalogMalformedError,
    CatalogUnavailableError,
    DesktopProjectCatalog,
)
from agent.desktop.protocol import (
    PROTOCOL_VERSION,
    ProtocolError,
    encode_message,
    success_result,
)
from agent.extensions.manager import (
    ApplyReport,
    ExtensionManager,
    ExtensionPreview,
    ExtensionStatus,
    ManagementError,
)
from agent.extensions.paths import resolve_extension_paths
from agent.ingest import (
    diff_folder,
    ingest_file,
    ingest_folder,
    init_workspace,
    prune_folder,
)
from agent.paths import find_app_root
from agent.session import ChatSession
from agent.skills import DEFAULT_SKILLS_DIR
from agent.turns.safety import content_text
from agent.turns.plan_log import PlanLog
from rag import explore, get_context, list_chunks, search
from rag.collect import SKIP_DIRS, TEXT_EXTENSIONS
from skills.citation.storage import resolve_output_dir


logger = logging.getLogger(__name__)

EventSink = Callable[[str, dict[str, Any]], None]
_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")
_BINDING_HASH = re.compile(r"^[0-9a-f]{64}$")
_EXTENSIONLESS_INGEST_FILES = {
    "Dockerfile",
    "Makefile",
    "Procfile",
    ".env.example",
    ".gitignore",
}
_KNOWLEDGE_MUTATIONS = {
    "knowledge.init_workspace",
    "knowledge.ingest_file",
    "knowledge.ingest_folder",
    "knowledge.prune_apply",
}
_DESKTOP_KNOWLEDGE_COMMANDS = frozenset({"init", "ingest", "sync", "prune"})
_DESKTOP_EXTENSION_COMMAND = "extension-management"
_DESKTOP_SLASH_COMMANDS = frozenset({
    "help",
    "status",
    _DESKTOP_EXTENSION_COMMAND,
    *_DESKTOP_KNOWLEDGE_COMMANDS,
})
_MAX_ANSWER_BYTES = 2_097_152
_MAX_LOCAL_COMMAND_BYTES = 65_536
_MAX_TRANSCRIPT_PAGE_BYTES = 1_048_576
_MAX_TRANSCRIPT_TOOL_ACTIVITIES = 128
_MAX_TRANSCRIPT_TOOL_CALL_ID_BYTES = 256
_MAX_TRANSCRIPT_TOOL_NAME_BYTES = 256
_MAX_TRANSCRIPT_TOOL_RESULT_BYTES = 65_536
_TRANSCRIPT_TOOL_STATUSES = frozenset({"ok", "failed", "denied", "incomplete"})
_MAX_CONTROL_SNAPSHOTS = CATALOG_MAX_SESSIONS
_MAX_KNOWLEDGE_RESULT_PATHS = 512
_MAX_KNOWLEDGE_PATH_BYTES = 4_096
_MAX_APPROVAL_COMMAND_BYTES = 65_536
_MAX_APPROVAL_DESCRIPTION_BYTES = 4_096
_MAX_EXTENSION_ARGUMENTS = 128
_MAX_EXTENSION_ENVIRONMENT_NAMES = 128
_WIRE_BUDGET_REQUEST_ID = "00000000-0000-4000-8000-000000000000"
_WIRE_BUDGET_TURN_ID = "00000000000040008000000000000000"
_SECRET_APPROVAL_CONTEXT = re.compile(
    r"(?i)(?:authorization\s*:|(?:api[_-]?key|access[_-]?token|secret|password)\s*[:=])\s*\S+"
)
_SECRET_FLAG_VALUE = re.compile(
    r"(?i)(?:^|\s)--?(?:api[-_]?key|access[-_]?token|token|secret|password|private[-_]?key)(?:\s+|[:=])\S+"
)
_CREDENTIAL_URL = re.compile(r"(?i)https?://[^\s/:@]+:[^\s/@]+@")


class DesktopServiceError(ProtocolError):
    """A domain or lifecycle failure safe to return over the desktop wire."""


@dataclass(frozen=True)
class DesktopKnowledgeOperations:
    """Concrete Python-owned knowledge calls injectable at the desktop edge."""

    init_workspace: Callable[
        [AgentConfig],
        Awaitable[tuple[int, int, Path, set[str]]],
    ]
    ingest_file: Callable[
        [Path, AgentConfig],
        Awaitable[tuple[str, int]],
    ]
    ingest_folder: Callable[
        [Path, AgentConfig],
        Awaitable[tuple[int, int]],
    ]
    diff_folder: Callable[[Path, AgentConfig], Awaitable[dict[str, Any]]]
    prune_folder: Callable[[Path, AgentConfig], Awaitable[list[str]]]


@dataclass(frozen=True)
class _PrunePreview:
    root: Path
    orphans: tuple[str, ...]
    digest: str


@dataclass(frozen=True)
class _PendingApproval:
    approval_id: str
    parent_request_id: str
    turn_id: str
    expires_at: datetime
    future: asyncio.Future[bool]


@dataclass(frozen=True)
class _ConversationControlSnapshot:
    plan_mode: bool
    plan_log_path: str | None
    thinking_mode: str


class DesktopService:
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
        project_catalog: DesktopProjectCatalog | None = None,
        conversation_repository: ConversationRepository | None = None,
        conversation_migrator: ConversationMigrator | None = None,
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
        self._session_factory_accepts_bash = (
            session_factory is None or bash_command_runner is not None
        )
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
        self._conversation_repository = (
            conversation_repository or ConversationRepository(self.config.persist_dir)
        )
        self._conversation_migrator = conversation_migrator or ConversationMigrator(
            self._conversation_repository,
            LegacyConversationReader(
                chroma_read=LegacyChromaReader(self.config.persist_dir),
                plan_read=lambda conversation_id: PlanLog(
                    self.config,
                    session_id=conversation_id,
                    app_root_resolver=lambda: find_app_root(),
                ).read_direct_answer_turns(),
            ),
        )
        self._catalog: DesktopProjectCatalog | None = project_catalog
        self._catalog_issue: str | None = None
        if self._catalog is None:
            try:
                self._catalog = DesktopProjectCatalog(self.config.persist_dir)
            except CatalogMalformedError:
                try:
                    scan = self._conversation_repository.scan()
                    self._catalog = DesktopProjectCatalog.rebuild_from_conversations(
                        self.config.persist_dir,
                        scan.summaries,
                    )
                except (ConversationError, CatalogError):
                    self._catalog_issue = "The local project catalog is unavailable."
            except CatalogUnavailableError:
                self._catalog_issue = "The local project catalog is unavailable."
        self._reconcile_lagged_catalog_entries()
        catalog_projects = (
            self._catalog.snapshot()["projects"] if self._catalog is not None else []
        )
        project_ids = [project["projectId"] for project in catalog_projects]
        self._selected_project_id: str | None = (
            DEFAULT_PROJECT_ID
            if DEFAULT_PROJECT_ID in project_ids
            else (project_ids[0] if project_ids else None)
        )
        self._session_registered = False
        self._pending_registration: tuple[str, str] | None = None
        self._control_snapshots: dict[str, _ConversationControlSnapshot] = {}
        self._load_mcp = True
        self._session_creating = False
        self._turn_active = False
        self._session_closing = False
        self._knowledge_active = False
        self._extension_active = False
        self._turn_event_sink: EventSink | None = None
        self._turn_loop: asyncio.AbstractEventLoop | None = None
        self._active_parent_request_id: str | None = None
        self._active_turn_id: str | None = None
        self._pending_approval: _PendingApproval | None = None
        self._tool_names: dict[str, str] = {}
        self._tool_summaries: dict[str, dict[str, str]] = {}
        self._extension_previews: dict[str, ExtensionPreview] = {}
        self._prune_previews: dict[str, _PrunePreview] = {}
        self._composer_prune_preview: tuple[str, _PrunePreview] | None = None

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
            "project.list": self._project_list,
            "session.create": self._session_create,
            "session.list": self._session_list,
            "session.select": self._session_select,
            "session.retry_registration": self._session_retry_registration,
            "session.transcript": self._session_transcript,
            "session.status": self._session_status,
            "session.turn": self._session_turn,
            "session.set_mode": self._session_set_mode,
            "session.set_thinking": self._session_set_thinking,
            "session.shutdown": self._session_shutdown,
            "knowledge.overview": self._knowledge_overview,
            "knowledge.search": self._knowledge_search,
            "knowledge.list_chunks": self._knowledge_list_chunks,
            "knowledge.get_context": self._knowledge_get_context,
            "knowledge.init_workspace": self._knowledge_init_workspace,
            "knowledge.ingest_file": self._knowledge_ingest_file,
            "knowledge.ingest_folder": self._knowledge_ingest_folder,
            "knowledge.sync": self._knowledge_sync,
            "knowledge.prune_preview": self._knowledge_prune_preview,
            "knowledge.prune_apply": self._knowledge_prune_apply,
            "extensions.status": self._extensions_status,
            "extensions.preview": self._extensions_preview,
            "extensions.apply": self._extensions_apply,
            "approval.resolve": self._approval_resolve,
            "runtime.shutdown": self._runtime_shutdown,
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
        if self._session_closing and method not in {
            "runtime.diagnostics",
            "session.status",
        }:
            raise DesktopServiceError(
                "SESSION_NOT_READY", "The desktop session is shutting down."
            )
        try:
            return await handler(params, event_sink)
        except DesktopServiceError as exc:
            if method == "session.turn":
                raise self._with_turn_lifecycle(exc, params) from exc
            raise
        except Exception as exc:
            mapped = self._map_exception(method, exc)
            if mapped.code == "INTERNAL_ERROR":
                logger.exception(
                    "Desktop method %s failed with %s",
                    method,
                    type(exc).__name__,
                )
            else:
                logger.warning(
                    "Desktop method %s returned %s (%s)",
                    method,
                    mapped.code,
                    type(exc).__name__,
                )
            if method == "session.turn":
                mapped = self._with_turn_lifecycle(mapped, params)
            raise mapped from exc

    def _with_turn_lifecycle(
        self,
        error: DesktopServiceError,
        params: Mapping[str, Any],
    ) -> DesktopServiceError:
        turn_id = params.get("turnId")
        display_input = params.get("text")
        state: str | None = None
        accepted = False
        persisted = False
        snapshot: ConversationSnapshot | None = None
        session = self.session
        if isinstance(turn_id, str) and session is not None:
            try:
                snapshot = self._conversation_repository.load_optional(
                    session.session_id
                )
            except ConversationError:
                candidate = getattr(session, "_conversation_snapshot", None)
                if isinstance(candidate, ConversationSnapshot):
                    snapshot = candidate
            if snapshot is not None:
                turn = next(
                    (
                        item
                        for item in snapshot.document.turns
                        if item.turn_id == turn_id
                        and item.display_input == display_input
                    ),
                    None,
                )
                if turn is not None:
                    state = turn.state
                    accepted = True
                    persisted = True
        return DesktopServiceError(
            error.code,
            str(error),
            retryable=error.retryable,
            details={
                "turnId": turn_id,
                "state": state,
                "accepted": accepted,
                "persisted": persisted,
            },
        )

    def _map_exception(self, method: str, exc: Exception) -> DesktopServiceError:
        if isinstance(exc, GraphRecursionError):
            return DesktopServiceError(
                "GRAPH_LIMIT_REACHED",
                "The agent reached its graph recursion safety limit.",
                retryable=True,
            )
        if self._exception_chain_contains(exc, "OPENROUTER_API_KEY is not set"):
            return DesktopServiceError(
                "OPENROUTER_NOT_CONFIGURED",
                "OpenRouter is not configured.",
            )
        if method == "session.turn":
            status_code = self._exception_http_status(exc)
            if status_code == 429:
                return DesktopServiceError(
                    "PROVIDER_RATE_LIMITED",
                    "The model provider is rate limited. Your draft was preserved.",
                    retryable=True,
                )
            if status_code is not None or self._exception_chain_looks_provider_owned(exc):
                retryable = status_code is None or status_code >= 500 or status_code in {
                    408,
                    409,
                }
                return DesktopServiceError(
                    "PROVIDER_REQUEST_FAILED",
                    "The model provider could not complete the turn.",
                    retryable=retryable,
                )
        if isinstance(exc, ManagementError):
            code = (
                "EXTENSION_APPLY_FAILED"
                if method == "extensions.apply"
                else "EXTENSION_PREVIEW_FAILED"
            )
            if "another extension apply is already running" in str(exc):
                code = "BUSY_EXTENSION_OPERATION"
            return DesktopServiceError(
                code,
                "The extension operation could not be completed.",
                retryable=code == "BUSY_EXTENSION_OPERATION",
            )
        if method.startswith("knowledge."):
            if isinstance(exc, (FileNotFoundError, IsADirectoryError, NotADirectoryError)):
                return DesktopServiceError("INVALID_PATH", "The selected path is invalid.")
            lowered = self._exception_chain_text(exc).lower()
            partial_write = method in _KNOWLEDGE_MUTATIONS
            if "model" in lowered and (
                "not found" in lowered or "pull" in lowered
            ):
                return DesktopServiceError(
                    "OLLAMA_MODEL_MISSING",
                    f"The configured Ollama model {self.config.embed_model} is unavailable.",
                    retryable=True,
                    details={"partialWritePossible": partial_write},
                )
            if any(
                marker in lowered
                for marker in (
                    "connection refused",
                    "connection error",
                    "connect error",
                    "failed to connect",
                    "timed out",
                    "timeout",
                )
            ):
                return DesktopServiceError(
                    "OLLAMA_UNREACHABLE",
                    "Ollama is unreachable.",
                    retryable=True,
                    details={"partialWritePossible": partial_write},
                )
            if "modified by another process" in lowered:
                return DesktopServiceError(
                    "RAG_PARTIAL_WRITE_POSSIBLE",
                    "The knowledge store changed during the operation; refresh and retry.",
                    retryable=True,
                )
            code = (
                "RAG_WRITE_FAILED"
                if method
                in {
                    "knowledge.init_workspace",
                    "knowledge.ingest_file",
                    "knowledge.ingest_folder",
                    "knowledge.prune_apply",
                }
                else "RAG_READ_FAILED"
            )
            return DesktopServiceError(
                code,
                "The knowledge operation could not be completed.",
                retryable=True,
                details=(
                    {"partialWritePossible": True}
                    if code == "RAG_WRITE_FAILED"
                    else None
                ),
            )
        if isinstance(exc, (ValueError, KeyError)) and method.startswith("session."):
            return DesktopServiceError(
                "PROTOCOL_INVALID",
                "The requested session mode or skill is invalid.",
            )
        return DesktopServiceError(
            "INTERNAL_ERROR",
            "The desktop backend encountered an internal error.",
        )

    @staticmethod
    def _exception_chain_contains(exc: BaseException, text: str) -> bool:
        current: BaseException | None = exc
        seen: set[int] = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            if text in str(current):
                return True
            current = current.__cause__ or current.__context__
        return False

    @staticmethod
    def _exception_chain_text(exc: BaseException) -> str:
        parts: list[str] = []
        current: BaseException | None = exc
        seen: set[int] = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            parts.append(f"{type(current).__module__}.{type(current).__name__}: {current}")
            current = current.__cause__ or current.__context__
        return " | ".join(parts)

    @staticmethod
    def _exception_http_status(exc: BaseException) -> int | None:
        current: BaseException | None = exc
        seen: set[int] = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            for source in (current, getattr(current, "response", None)):
                status = getattr(source, "status_code", None)
                if type(status) is int and 400 <= status <= 599:
                    return status
            current = current.__cause__ or current.__context__
        return None

    @staticmethod
    def _exception_chain_looks_provider_owned(exc: BaseException) -> bool:
        current: BaseException | None = exc
        seen: set[int] = set()
        prefixes = ("httpx", "openai", "langchain_openrouter")
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            if type(current).__module__.startswith(prefixes):
                return True
            current = current.__cause__ or current.__context__
        return False

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
            "citationOutputPath": str(
                resolve_output_dir(self.config, self.environ).expanduser().resolve()
            ),
            "ollamaReachable": None,
            "ollamaModelAvailable": None,
            "mcpEnabled": self._load_mcp,
            "mcpFamilies": mcp_families,
            "mcpDiagnostics": mcp_diagnostics,
        }

    async def _project_list(
        self, _params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        self._reconcile_lagged_catalog_entries()
        if self._catalog is None:
            return {
                "status": "unavailable",
                "issue": self._catalog_issue
                or "The local project catalog is unavailable.",
                "projects": [],
                "selectedProjectId": None,
                "selectedSessionId": None,
            }
        snapshot = self._catalog.snapshot()
        return {
            "status": "ready",
            "issue": None,
            "projects": [
                {
                    "projectId": project["projectId"],
                    "name": project["name"],
                    "sessionCount": len(project["sessionIds"]),
                }
                for project in snapshot["projects"]
            ],
            "selectedProjectId": self._selected_project_id,
            "selectedSessionId": (
                self.session.session_id if self.session is not None else None
            ),
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
        self._reconcile_lagged_catalog_entries()
        project = self._require_catalog_project(params["projectId"])
        offset = int(params.get("offset", 0))
        limit = int(params.get("limit", 50))
        session_ids = project["sessionIds"]
        items: list[dict[str, Any]] = []
        for session_id in session_ids[offset : offset + limit]:
            items.append(
                await self._conversation_summary(session_id, project["projectId"])
            )
        return {
            "projectId": project["projectId"],
            "status": "ready",
            "issue": None,
            "items": items,
            "total": len(session_ids),
            "offset": offset,
            "limit": limit,
            "hasMore": offset + len(items) < len(session_ids),
        }

    async def _session_select(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        self._complete_pending_approval(False)
        if self._turn_active:
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
        if self._knowledge_active or self._extension_active:
            raise DesktopServiceError(
                "SESSION_NOT_READY",
                "The selected conversation cannot change during another operation.",
                retryable=True,
            )
        project = self._require_catalog_project(params["projectId"])
        session_id = params["sessionId"]
        if session_id not in project["sessionIds"]:
            raise DesktopServiceError(
                "PROTOCOL_INVALID",
                "The requested conversation does not belong to that project.",
            )
        if (
            self.session is not None
            and self.session.session_id == session_id
            and self._selected_project_id == project["projectId"]
        ):
            return {
                **self._session_snapshot(self.session),
                "projectId": project["projectId"],
                "registered": True,
            }

        try:
            await asyncio.to_thread(
                self._load_or_import_conversation,
                session_id,
                project["projectId"],
            )
        except ConversationError as exc:
            raise DesktopServiceError(
                "SESSION_NOT_READY",
                "The stored conversation is degraded and cannot be selected.",
            ) from exc

        self._session_creating = True
        current = self.session
        saved_controls: _ConversationControlSnapshot | None = None
        if current is not None:
            saved_controls = self._capture_controls(current)
        try:
            target = await self._materialize_session(
                self.config,
                load_mcp=self._load_mcp,
                project_id=project["projectId"],
                session_id=session_id,
            )
            await self._apply_controls(
                target,
                self._control_snapshots.get(session_id),
            )
            if self.lifecycle != "ready":
                raise DesktopServiceError(
                    "SESSION_NOT_READY",
                    "The desktop backend changed state while selecting a conversation.",
                )
        finally:
            self._session_creating = False

        if (
            current is not None
            and saved_controls is not None
            and self._session_registered
        ):
            self._store_control_snapshot(current.session_id, saved_controls)
        self.session = target
        self._selected_project_id = project["projectId"]
        self._session_registered = True
        self._pending_registration = None
        return {
            **self._session_snapshot(target),
            "projectId": project["projectId"],
            "registered": True,
        }

    async def _session_retry_registration(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        session = self._require_idle_session()
        project_id = params["projectId"]
        session_id = params["sessionId"]
        self._require_catalog_project(project_id)
        if session.session_id != session_id or self._selected_project_id != project_id:
            raise DesktopServiceError(
                "PROTOCOL_INVALID",
                "Registration can only be retried for the selected conversation.",
            )
        if self._catalog is None:
            return {
                "projectId": project_id,
                "sessionId": session_id,
                "status": "pending",
                "issue": "The local project catalog is unavailable.",
            }
        owner = self._catalog.project_for_session(session_id)
        if owner == project_id:
            self._session_registered = True
            self._pending_registration = None
            return {
                "projectId": project_id,
                "sessionId": session_id,
                "status": "registered",
                "issue": None,
            }
        if self._pending_registration != (project_id, session_id):
            raise DesktopServiceError(
                "PROTOCOL_INVALID",
                "The selected conversation has no pending catalog registration.",
            )
        try:
            self._catalog.register_session(project_id, session_id)
        except CatalogError:
            return {
                "projectId": project_id,
                "sessionId": session_id,
                "status": "pending",
                "issue": "The conversation is saved, but catalog registration still failed.",
            }
        self._session_registered = True
        self._pending_registration = None
        return {
            "projectId": project_id,
            "sessionId": session_id,
            "status": "registered",
            "issue": None,
        }

    async def _session_transcript(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        if self._turn_active:
            raise DesktopServiceError(
                "BUSY_TURN",
                "The transcript is unavailable during an active turn.",
                retryable=True,
            )
        project = self._require_catalog_project(params["projectId"])
        session_id = params["sessionId"]
        if session_id not in project["sessionIds"]:
            raise DesktopServiceError(
                "PROTOCOL_INVALID",
                "The requested conversation does not belong to that project.",
            )
        offset = int(params.get("offset", 0))
        limit = int(params.get("limit", 20))
        try:
            turns = await asyncio.to_thread(
                self._read_conversation_turns,
                session_id,
                project["projectId"],
            )
        except ConversationError:
            return self._transcript_result(
                project["projectId"],
                session_id,
                status="degraded",
                issue="The stored transcript is malformed or incomplete.",
                turns=[],
                offset=offset,
                limit=limit,
                total=0,
            )
        if not turns:
            return self._transcript_result(
                project["projectId"],
                session_id,
                status="unavailable",
                issue="No persisted transcript is available.",
                turns=[],
                offset=offset,
                limit=limit,
                total=0,
            )
        page = turns[offset : offset + limit]
        if any(not self._transcript_turn_is_bounded(turn) for turn in page):
            return self._transcript_result(
                project["projectId"],
                session_id,
                status="degraded",
                issue="The requested transcript page contains an oversized turn.",
                turns=[],
                offset=offset,
                limit=limit,
                total=len(turns),
            )
        page_bytes = sum(self._transcript_turn_bytes(turn) for turn in page)
        if page_bytes > _MAX_TRANSCRIPT_PAGE_BYTES:
            return self._transcript_result(
                project["projectId"],
                session_id,
                status="degraded",
                issue="The requested transcript page exceeds the desktop limit.",
                turns=[],
                offset=offset,
                limit=limit,
                total=len(turns),
            )
        return self._transcript_result(
            project["projectId"],
            session_id,
            status="ready",
            issue=None,
            turns=page,
            offset=offset,
            limit=limit,
            total=len(turns),
        )

    async def _conversation_summary(
        self,
        session_id: str,
        project_id: str,
    ) -> dict[str, Any]:
        try:
            snapshot = await asyncio.to_thread(
                self._load_conversation,
                session_id,
                project_id,
            )
        except ConversationError:
            return {
                "sessionId": session_id,
                "title": f"Conversation {session_id[:8]}",
                "turnCount": 0,
                "createdAt": None,
                "updatedAt": None,
                "status": "degraded",
                "issue": "The stored transcript is malformed or incomplete.",
            }
        if snapshot is None:
            return {
                "sessionId": session_id,
                "title": f"Conversation {session_id[:8]}",
                "turnCount": 0,
                "createdAt": None,
                "updatedAt": None,
                "status": "unavailable",
                "issue": "No persisted transcript is available.",
            }
        summary = self._conversation_repository.summary(snapshot)
        return {
            "sessionId": session_id,
            "title": summary.title or f"Conversation {session_id[:8]}",
            "turnCount": summary.turn_count,
            "createdAt": summary.created_at,
            "updatedAt": summary.updated_at,
            "status": "ready",
            "issue": None,
        }

    def _reconcile_lagged_catalog_entries(self) -> None:
        """Re-register healthy JSON conversations after a catalog-write gap."""
        catalog = self._catalog
        if catalog is None:
            return
        try:
            scan = self._conversation_repository.scan()
            catalog.reconcile_conversations(scan.summaries)
        except (ConversationError, CatalogError):
            return

    def _require_catalog_project(self, project_id: str) -> dict[str, Any]:
        if self._catalog is None:
            raise DesktopServiceError(
                "SESSION_NOT_READY",
                self._catalog_issue or "The local project catalog is unavailable.",
                retryable=True,
            )
        project = next(
            (
                item
                for item in self._catalog.snapshot()["projects"]
                if item["projectId"] == project_id
            ),
            None,
        )
        if project is None:
            raise DesktopServiceError(
                "PROTOCOL_INVALID", "The requested project does not exist."
            )
        return project

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

    def _load_or_import_conversation(
        self,
        session_id: str,
        project_id: str,
    ) -> ConversationSnapshot:
        snapshot = self._load_conversation(session_id, project_id)
        if snapshot is not None:
            return snapshot
        migration = self._conversation_migrator.import_conversation(
            session_id,
            project_id,
        )
        if migration.status not in {"created", "already_present"}:
            raise ConversationUnavailableError(
                "legacy conversation could not be imported"
            )
        snapshot = self._load_conversation(session_id, project_id)
        if snapshot is None:
            raise ConversationUnavailableError(
                "canonical conversation is unavailable after import"
            )
        return snapshot

    def _read_conversation_turns(
        self,
        session_id: str,
        project_id: str,
    ) -> list[ConversationTurn]:
        snapshot = self._load_conversation(session_id, project_id)
        if snapshot is None:
            return []
        return list(snapshot.document.turns)

    @staticmethod
    def _tool_activity_payload(activity: ToolActivitySummary) -> dict[str, Any]:
        return {
            "callId": activity.call_id,
            "name": activity.name,
            "arguments": "(not retained)",
            "result": activity.summary or "(no summary)",
            "status": activity.status,
            "promptEligible": False,
        }

    @classmethod
    def _transcript_turn_is_bounded(cls, turn: ConversationTurn) -> bool:
        if (
            len(turn.display_input.encode("utf-8")) > 32_768
            or len(turn.submitted_at.encode("utf-8")) > 64
            or (
                turn.assistant_output is not None
                and len(turn.assistant_output.encode("utf-8")) > 32_768
            )
            or (
                turn.failure is not None
                and len(turn.failure.message.encode("utf-8")) > 4_096
            )
            or len(turn.tool_activities) > _MAX_TRANSCRIPT_TOOL_ACTIVITIES
        ):
            return False
        for activity in turn.tool_activities:
            if not isinstance(activity, ToolActivitySummary):
                return False
            result = activity.summary or "(no summary)"
            if (
                activity.status not in _TRANSCRIPT_TOOL_STATUSES
                or not activity.name
                or len(activity.name.encode("utf-8"))
                > _MAX_TRANSCRIPT_TOOL_NAME_BYTES
                or len(result.encode("utf-8"))
                > _MAX_TRANSCRIPT_TOOL_RESULT_BYTES
                or (
                    activity.call_id is not None
                    and (
                        not activity.call_id
                        or len(activity.call_id.encode("utf-8"))
                        > _MAX_TRANSCRIPT_TOOL_CALL_ID_BYTES
                    )
                )
            ):
                return False
        return True

    @staticmethod
    def _transcript_turn_bytes(turn: ConversationTurn) -> int:
        total = (
            len(turn.display_input.encode("utf-8"))
            + len((turn.assistant_output or "").encode("utf-8"))
            + len(turn.submitted_at.encode("utf-8"))
            + len((turn.failure.message if turn.failure else "").encode("utf-8"))
        )
        for activity in turn.tool_activities:
            total += (
                len((activity.call_id or "").encode("utf-8"))
                + len(activity.name.encode("utf-8"))
                + len("(not retained)".encode("utf-8"))
                + len((activity.summary or "(no summary)").encode("utf-8"))
                + len(activity.status.encode("utf-8"))
                + 1
            )
        return total

    @staticmethod
    def _transcript_result(
        project_id: str,
        session_id: str,
        *,
        status: str,
        issue: str | None,
        turns: list[ConversationTurn],
        offset: int,
        limit: int,
        total: int,
    ) -> dict[str, Any]:
        return {
            "projectId": project_id,
            "sessionId": session_id,
            "status": status,
            "issue": issue,
            "items": [
                {
                    "turnId": turn.turn_id,
                    "turnNumber": turn.turn_number,
                    "kind": turn.kind,
                    "state": turn.state,
                    "timestamp": turn.submitted_at,
                    "userText": turn.display_input,
                    "assistantText": turn.assistant_output,
                    "failureCode": (
                        turn.failure.code if turn.failure is not None else None
                    ),
                    "failureMessage": (
                        turn.failure.message if turn.failure is not None else None
                    ),
                    "failureRetryable": (
                        turn.failure.retryable if turn.failure is not None else None
                    ),
                    "toolActivities": [
                        DesktopService._tool_activity_payload(activity)
                        for activity in turn.tool_activities
                    ],
                }
                for turn in turns
            ],
            "total": total,
            "offset": offset,
            "limit": limit,
            "hasMore": status == "ready" and offset + len(turns) < total,
        }

    async def _materialize_session(
        self,
        config: AgentConfig,
        *,
        load_mcp: bool,
        project_id: str,
        session_id: str | None = None,
    ) -> ChatSession:
        kwargs: dict[str, Any] = {
            "load_mcp": load_mcp,
            "progress_cb": self._on_session_progress,
        }
        if self._session_factory_accepts_bash:
            kwargs.update({
                "bash_approval_handler": self._desktop_bash_approval,
                "bash_command_runner": self._bash_command_runner,
            })
        kwargs.update({
            "conversation_repository": self._conversation_repository,
            "project_id": project_id,
        })
        if session_id is not None:
            kwargs["session_id"] = session_id
        session = await self._session_factory(config, **kwargs)
        if isinstance(session, ChatSession):
            session._set_final_text_validator(
                lambda text, errors: self._validate_final_text_before_record(
                    session.session_id,
                    text,
                    errors,
                )
            )
        set_prompt_persisted_callback = getattr(
            session,
            "_set_prompt_persisted_callback",
            None,
        )
        if callable(set_prompt_persisted_callback):
            set_prompt_persisted_callback(
                lambda: self._register_saved_session(session)
            )
        return session

    @staticmethod
    def _capture_controls(session: ChatSession) -> _ConversationControlSnapshot:
        return _ConversationControlSnapshot(
            plan_mode=bool(session.plan_mode),
            plan_log_path=(
                str(session.plan_log_path) if session.plan_log_path else None
            ),
            thinking_mode=str(session.thinking_mode),
        )

    async def _apply_controls(
        self,
        session: ChatSession,
        snapshot: _ConversationControlSnapshot | None,
    ) -> None:
        if snapshot is None:
            return
        session.set_thinking_mode(snapshot.thinking_mode)
        if snapshot.plan_mode:
            if snapshot.plan_log_path is not None:
                await session.resume_plan_mode(snapshot.plan_log_path)
            else:
                await session.enter_plan_mode()

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
        self._complete_pending_approval(False)
        if self._session_creating:
            raise DesktopServiceError(
                "SESSION_NOT_READY",
                "A desktop session is already being created.",
                retryable=True,
            )
        if self._turn_active:
            raise DesktopServiceError("BUSY_TURN", "A session turn is still active.")
        if self._knowledge_active or self._extension_active:
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
        self._require_catalog_project(project_id)
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
        saved_controls: _ConversationControlSnapshot | None = None
        if current is not None:
            saved_controls = self._capture_controls(current)
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
        if (
            current is not None
            and saved_controls is not None
            and self._session_registered
        ):
            self._store_control_snapshot(current.session_id, saved_controls)
        self.config = config
        self.session = session
        self._load_mcp = load_mcp
        self._selected_project_id = project_id
        self._session_registered = False
        self._pending_registration = None
        return {
            **self._session_snapshot(session),
            "projectId": project_id,
            "registered": False,
        }

    async def _session_status(
        self, _params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        if self.session is None:
            return {"ready": False, "lifecycle": self.lifecycle}
        return {"ready": True, **self._session_snapshot(self.session)}

    def _validation_error_dtos(self, errors: list[Any]) -> list[str]:
        return [
            self._bounded_text(str(item), 4_096)
            for item in errors[:128]
            if str(item)
        ]

    def _ensure_turn_result_fits_wire(
        self,
        *,
        session_id: str,
        text: str,
        validation_errors: list[str],
        tool_summaries: list[dict[str, str]],
    ) -> None:
        """Budget the complete worst-case success line before side effects."""
        candidate = {
            "sessionId": session_id,
            "turnId": _WIRE_BUDGET_TURN_ID,
            "turnNumber": 4_096,
            "state": "completed",
            "accepted": True,
            "persisted": True,
            "text": text,
            "validationErrors": validation_errors,
            "toolSummaries": tool_summaries,
            "responseKind": "answer",
            "streamKind": "final_only",
            "chunkCount": 0,
            "registrationStatus": "pending",
            "registrationIssue": "\u0000" * 4_096,
        }
        try:
            encode_message(success_result(
                _WIRE_BUDGET_REQUEST_ID,
                "session.turn",
                candidate,
            ))
        except ProtocolError as exc:
            raise DesktopServiceError(
                "INTERNAL_ERROR",
                "The finalized answer exceeded the desktop response limit.",
            ) from exc

    def _validate_final_text_before_record(
        self,
        session_id: str,
        text: str,
        errors: list[str],
    ) -> None:
        self._ensure_turn_result_fits_wire(
            session_id=session_id,
            text=text,
            validation_errors=self._validation_error_dtos(errors),
            tool_summaries=list(self._tool_summaries.values())[:512],
        )

    async def _execute_desktop_knowledge_command(
        self,
        session: ChatSession,
        parsed: ParsedSlashCommand,
    ) -> SlashCommandResult:
        method = {
            "init": "knowledge.init_workspace",
            "ingest": "knowledge.ingest_file",
            "sync": "knowledge.sync",
            "prune": (
                "knowledge.prune_apply"
                if parsed.args and parsed.args[-1] == "--yes"
                else "knowledge.prune_preview"
            ),
        }[parsed.name.casefold()]
        try:
            if parsed.name.casefold() == "init":
                return await self._desktop_init_command(parsed)
            if parsed.name.casefold() == "ingest":
                return await self._desktop_ingest_command(parsed)
            if parsed.name.casefold() == "sync":
                return await self._desktop_sync_command(parsed)
            return await self._desktop_prune_command(session, parsed)
        except DesktopServiceError:
            raise
        except Exception as exc:
            raise self._map_exception(method, exc) from exc

    async def _desktop_init_command(
        self,
        parsed: ParsedSlashCommand,
    ) -> SlashCommandResult:
        if parsed.args:
            raise DesktopServiceError(
                "PROTOCOL_INVALID",
                "/init takes no arguments.",
            )
        async with self._knowledge_operation(turn_owned=True):
            files, chunks, host_root, excluded = (
                await self._knowledge_operations.init_workspace(self.config)
            )
        files = self._knowledge_count(files, "file")
        chunks = self._knowledge_count(chunks, "chunk")
        excluded_names = self._knowledge_string_items(excluded, "excluded name")
        root = self._bounded_text(str(host_root), _MAX_KNOWLEDGE_PATH_BYTES)
        excluded_text = ", ".join(excluded_names) or "none"
        return self._knowledge_result(
            (
                f"initialized: {files} files, {chunks} chunks "
                f"(root={root}, excluded {excluded_text})"
            ),
            mutation=True,
        )

    async def _desktop_ingest_command(
        self,
        parsed: ParsedSlashCommand,
    ) -> SlashCommandResult:
        if len(parsed.args) != 1:
            raise DesktopServiceError(
                "PROTOCOL_INVALID",
                "usage: /ingest <absolute-file-or-directory>",
            )
        target = self._validated_path(
            parsed.args[0],
            kind="file-or-directory",
            destructive_root=True,
        )
        if target.is_file():
            if (
                target.suffix.lower() not in TEXT_EXTENSIONS
                and target.name not in _EXTENSIONLESS_INGEST_FILES
            ):
                raise DesktopServiceError(
                    "INVALID_PATH",
                    "The selected file type is not supported for ingest.",
                )
            async with self._knowledge_operation(turn_owned=True):
                pid, chunks = await self._knowledge_operations.ingest_file(
                    target,
                    self.config,
                )
            chunks = self._knowledge_count(chunks, "chunk")
            if chunks == 0:
                raise DesktopServiceError(
                    "RAG_WRITE_FAILED",
                    "The selected file contains no indexable UTF-8 text.",
                    details={"partialWritePossible": True},
                )
            safe_pid = self._bounded_text(str(pid), _MAX_KNOWLEDGE_PATH_BYTES)
            if not safe_pid:
                raise DesktopServiceError(
                    "RAG_WRITE_FAILED",
                    "The ingest operation returned no document identifier.",
                    details={"partialWritePossible": True},
                )
            return self._knowledge_result(
                f"ingested {safe_pid} ({chunks} chunks)",
                mutation=True,
            )

        async with self._knowledge_operation(turn_owned=True):
            files, chunks = await self._knowledge_operations.ingest_folder(
                target,
                self.config,
            )
        files = self._knowledge_count(files, "file")
        chunks = self._knowledge_count(chunks, "chunk")
        return self._knowledge_result(
            f"ingested {files} files ({chunks} chunks) under {target}",
            mutation=True,
        )

    async def _desktop_sync_command(
        self,
        parsed: ParsedSlashCommand,
    ) -> SlashCommandResult:
        if len(parsed.args) != 1:
            raise DesktopServiceError(
                "PROTOCOL_INVALID",
                "usage: /sync <absolute-directory>",
            )
        target = self._validated_path(
            parsed.args[0],
            kind="directory",
            destructive_root=True,
        )
        async with self._knowledge_operation(turn_owned=True):
            diff = await self._knowledge_operations.diff_folder(target, self.config)
        missing_store, missing_disk = self._knowledge_diff_paths(diff)
        return self._knowledge_result(
            self._render_knowledge_diff(
                target,
                missing_store,
                missing_disk,
            )
        )

    async def _desktop_prune_command(
        self,
        session: ChatSession,
        parsed: ParsedSlashCommand,
    ) -> SlashCommandResult:
        apply = len(parsed.args) == 2 and parsed.args[1] == "--yes"
        if len(parsed.args) not in {1, 2} or (
            len(parsed.args) == 2 and not apply
        ):
            raise DesktopServiceError(
                "PROTOCOL_INVALID",
                "usage: /prune <absolute-directory> [--yes]",
            )
        target = self._validated_path(
            parsed.args[0],
            kind="directory",
            destructive_root=True,
        )
        if not apply:
            async with self._knowledge_operation(turn_owned=True):
                diff = await self._knowledge_operations.diff_folder(
                    target,
                    self.config,
                )
            _missing_store, orphans = self._knowledge_diff_paths(diff)
            preview = _PrunePreview(
                root=target,
                orphans=orphans,
                digest=self._prune_digest(target, orphans),
            )
            lines = [
                f"Would prune {len(orphans)} orphaned path(s) under {target}:"
            ]
            lines.extend(f"  - {path}" for path in orphans)
            if not orphans:
                lines.append("  (none)")
            lines.append("Re-run the same command with --yes to apply.")
            result = self._knowledge_result("\n".join(lines))
            self._composer_prune_preview = (session.session_id, preview)
            return result

        stored = self._composer_prune_preview
        self._composer_prune_preview = None
        if (
            stored is None
            or stored[0] != session.session_id
            or stored[1].root != target
        ):
            raise DesktopServiceError(
                "PRUNE_PREVIEW_STALE",
                "Preview this exact directory before confirming prune.",
            )
        preview = stored[1]
        async with self._knowledge_operation(turn_owned=True):
            latest = await self._knowledge_operations.diff_folder(
                target,
                self.config,
            )
            _missing_store, latest_orphans = self._knowledge_diff_paths(latest)
            if self._prune_digest(target, latest_orphans) != preview.digest:
                raise DesktopServiceError(
                    "PRUNE_PREVIEW_STALE",
                    "The orphan set changed; preview again before applying.",
                )
            removed = await self._knowledge_operations.prune_folder(
                target,
                self.config,
            )
        if isinstance(removed, (str, bytes)) or not isinstance(removed, (list, tuple)):
            raise DesktopServiceError(
                "RAG_WRITE_FAILED",
                "The prune operation returned an invalid result.",
                details={"partialWritePossible": True},
            )
        return self._knowledge_result(
            f"pruned {len(removed)} orphaned pid(s) under {target}",
            mutation=True,
        )

    @staticmethod
    def _knowledge_count(value: Any, label: str) -> int:
        if type(value) is not int or value < 0:
            raise DesktopServiceError(
                "RAG_WRITE_FAILED",
                f"The knowledge operation returned an invalid {label} count.",
                details={"partialWritePossible": True},
            )
        return value

    @staticmethod
    def _knowledge_result(
        message: str,
        *,
        mutation: bool = False,
    ) -> SlashCommandResult:
        if len(message.encode("utf-8")) > _MAX_LOCAL_COMMAND_BYTES:
            raise DesktopServiceError(
                "RAG_WRITE_FAILED" if mutation else "RAG_READ_FAILED",
                "The knowledge result is too large; choose a narrower directory.",
                details={"partialWritePossible": True} if mutation else None,
            )
        return SlashCommandResult(message=message)

    @staticmethod
    def _knowledge_string_items(values: Any, label: str) -> tuple[str, ...]:
        if isinstance(values, (str, bytes)) or not isinstance(
            values,
            (list, tuple, set, frozenset),
        ):
            raise DesktopServiceError(
                "RAG_READ_FAILED",
                f"The knowledge operation returned invalid {label} data.",
            )
        if len(values) > _MAX_KNOWLEDGE_RESULT_PATHS:
            raise DesktopServiceError(
                "RAG_READ_FAILED",
                "The knowledge result is too large; choose a narrower directory.",
            )
        normalized: list[str] = []
        for value in values:
            if not isinstance(value, str) or not value or "\x00" in value:
                raise DesktopServiceError(
                    "RAG_READ_FAILED",
                    f"The knowledge operation returned invalid {label} data.",
                )
            if len(value.encode("utf-8")) > _MAX_KNOWLEDGE_PATH_BYTES:
                raise DesktopServiceError(
                    "RAG_READ_FAILED",
                    "A knowledge result path exceeded the desktop limit.",
                )
            normalized.append(value)
        return tuple(sorted(set(normalized)))

    @classmethod
    def _knowledge_diff_paths(
        cls,
        diff: Any,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        if not isinstance(diff, dict):
            raise DesktopServiceError(
                "RAG_READ_FAILED",
                "The knowledge comparison returned an invalid result.",
            )
        return (
            cls._knowledge_string_items(
                diff.get("missing_from_store"),
                "disk-only path",
            ),
            cls._knowledge_string_items(
                diff.get("missing_from_disk"),
                "store-only path",
            ),
        )

    @staticmethod
    def _render_knowledge_diff(
        target: Path,
        missing_store: tuple[str, ...],
        missing_disk: tuple[str, ...],
    ) -> str:
        lines = [
            f"Diff against {target}:",
            f"  on disk, not in store ({len(missing_store)}):",
        ]
        lines.extend(f"    + {path}" for path in missing_store)
        if not missing_store:
            lines.append("    (none)")
        lines.append(f"  in store, not on disk ({len(missing_disk)}):")
        lines.extend(f"    - {path}" for path in missing_disk)
        if not missing_disk:
            lines.append("    (none)")
        return "\n".join(lines)

    async def _execute_desktop_extension_command(
        self,
        parsed: ParsedSlashCommand,
    ) -> tuple[SlashCommandResult, str]:
        args = tuple(arg.casefold() for arg in parsed.args)
        if args == ("status",):
            status = await self._extensions_status({}, None)
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
            return SlashCommandResult(message=message), "status"
        if args in {(), ("--dry-run",)}:
            return SlashCommandResult(message=(
                "Extension preview is ready to request. Preview may contact "
                "the configured model provider, but it writes no changes. "
                "Review the exact preview before applying."
            )), "preview"
        raise DesktopServiceError(
            "PROTOCOL_INVALID",
            "usage: /extension-management [--dry-run|status]",
        )

    def _register_saved_session(
        self,
        session: ChatSession,
    ) -> tuple[str, str | None]:
        if self._session_registered:
            return "registered", None
        project_id = self._selected_project_id
        if self._catalog is None or project_id is None:
            status = "pending"
            issue = "The conversation is saved, but the project catalog is unavailable."
        else:
            try:
                self._catalog.register_session(project_id, session.session_id)
            except CatalogError:
                status = "pending"
                issue = "The conversation is saved, but catalog registration failed."
            else:
                status = "registered"
                issue = None
        if status == "registered":
            self._session_registered = True
            self._pending_registration = None
        elif project_id is not None:
            self._pending_registration = (project_id, session.session_id)
        return status, issue

    def _saved_session_registration_result(
        self,
        session: ChatSession,
    ) -> tuple[str, str | None]:
        if self._session_registered:
            return "registered", None
        project_id = self._selected_project_id
        if self._pending_registration == (project_id, session.session_id):
            issue = (
                "The conversation is saved, but the project catalog is unavailable."
                if self._catalog is None
                else "The conversation is saved, but catalog registration failed."
            )
            return "pending", issue
        if (
            self._catalog is not None
            and project_id is not None
            and self._catalog.project_for_session(session.session_id) == project_id
        ):
            self._session_registered = True
            return "registered", None
        return "not_required", None

    async def _session_turn(
        self, params: dict[str, Any], event_sink: EventSink | None
    ) -> dict[str, Any]:
        session = self._require_session()
        if self._turn_active:
            raise DesktopServiceError(
                "BUSY_TURN", "Another session turn is already active.", retryable=True
            )
        if self._knowledge_active:
            raise DesktopServiceError(
                "BUSY_KNOWLEDGE_MUTATION",
                "A knowledge operation is already active.",
                retryable=True,
            )
        if self._extension_active:
            raise DesktopServiceError(
                "BUSY_EXTENSION_OPERATION",
                "An extension operation is already active.",
                retryable=True,
            )
        self._turn_active = True
        self._turn_event_sink = event_sink
        self._tool_names = {}
        self._tool_summaries = {}
        turn_id = params["turnId"]
        parent_request_id = getattr(event_sink, "request_id", None)
        self._turn_loop = asyncio.get_running_loop()
        self._active_parent_request_id = (
            parent_request_id if isinstance(parent_request_id, str) else None
        )
        self._active_turn_id = turn_id
        try:
            original_text = params["text"]
            turn_text = original_text
            turn_skill_name: str | None = None
            try:
                parsed = parse_slash_command(original_text)
            except SlashCommandError as exc:
                raise DesktopServiceError(
                    "PROTOCOL_INVALID",
                    self._bounded_text(str(exc), 4_096),
                ) from exc

            if parsed is not None:
                registry = (
                    self._slash_registry_override
                    or build_default_registry(session)
                )
                command = registry.get(parsed.name)
                if command is None:
                    raise DesktopServiceError(
                        "PROTOCOL_INVALID",
                        f"Unknown slash command: /{self._bounded_text(parsed.name, 256)}",
                    )
                if parsed.name.casefold() != command.name.casefold():
                    raise DesktopServiceError(
                        "PROTOCOL_INVALID",
                        "That slash command is not available in the desktop composer.",
                    )
                if command.skill_name is not None:
                    try:
                        result = await execute_slash_command(
                            parsed,
                            SlashCommandContext(
                                session=session,
                                registry=registry,
                            ),
                        )
                    except SlashCommandError as exc:
                        raise DesktopServiceError(
                            "PROTOCOL_INVALID",
                            self._bounded_text(str(exc), 4_096),
                        ) from exc
                    if (
                        result.should_exit
                        or result.clear_screen
                        or not isinstance(result.followup_input, str)
                        or not result.followup_input.strip()
                        or result.skill_name != command.skill_name
                    ):
                        raise DesktopServiceError(
                            "PROTOCOL_INVALID",
                            "That Skill command returned an unsupported result.",
                        )
                    turn_text = result.followup_input
                    turn_skill_name = result.skill_name
                elif command.name not in _DESKTOP_SLASH_COMMANDS:
                    raise DesktopServiceError(
                        "PROTOCOL_INVALID",
                        "That slash command is not available in the desktop composer.",
                    )
                else:
                    extension_action: str | None = (
                        (
                            "status"
                            if tuple(arg.casefold() for arg in parsed.args)
                            == ("status",)
                            else "preview"
                        )
                        if command.name == _DESKTOP_EXTENSION_COMMAND
                        else None
                    )

                    async def execute_local_command() -> object:
                        if command.name in _DESKTOP_KNOWLEDGE_COMMANDS:
                            return await self._execute_desktop_knowledge_command(
                                session,
                                parsed,
                            )
                        if command.name == _DESKTOP_EXTENSION_COMMAND:
                            result, _action = (
                                await self._execute_desktop_extension_command(parsed)
                            )
                            return result
                        return await execute_slash_command(
                            parsed,
                            SlashCommandContext(
                                session=session,
                                registry=registry,
                            ),
                        )

                    def render_local_command(value: object) -> str:
                        if not isinstance(value, SlashCommandResult):
                            raise DesktopServiceError(
                                "INTERNAL_ERROR",
                                "The slash command returned an invalid result.",
                            )
                        result = value
                        if (
                            result.should_exit
                            or result.clear_screen
                            or result.followup_input is not None
                        ):
                            raise DesktopServiceError(
                                "PROTOCOL_INVALID",
                                "That slash-command result is not supported by the desktop composer.",
                            )
                        message = self._bounded_text(
                            str(result.message),
                            _MAX_LOCAL_COMMAND_BYTES,
                        )
                        if not message.strip():
                            raise DesktopServiceError(
                                "PROTOCOL_INVALID",
                                "The slash command returned no displayable result.",
                            )
                        return message

                    try:
                        _result, outcome = await session.run_display_only_turn(
                            original_text,
                            execute_local_command,
                            render_local_command,
                            turn_id=turn_id,
                            retry=params["retry"],
                        )
                    except SlashCommandError as exc:
                        raise DesktopServiceError(
                            "PROTOCOL_INVALID",
                            self._bounded_text(str(exc), 4_096),
                        ) from exc
                    if (
                        outcome.turn_id != turn_id
                        or not 1 <= outcome.turn_number <= 4_096
                        or outcome.state != "completed"
                        or outcome.accepted is not True
                        or outcome.persisted is not True
                        or not isinstance(outcome.text, str)
                        or not outcome.text.strip()
                        or len(outcome.text.encode("utf-8"))
                        > _MAX_LOCAL_COMMAND_BYTES
                    ):
                        raise DesktopServiceError(
                            "INTERNAL_ERROR",
                            "The session returned an invalid durable command result.",
                        )
                    registration_status, registration_issue = (
                        self._saved_session_registration_result(session)
                    )
                    response = {
                        "sessionId": session.session_id,
                        "turnId": outcome.turn_id,
                        "turnNumber": outcome.turn_number,
                        "state": outcome.state,
                        "accepted": outcome.accepted,
                        "persisted": outcome.persisted,
                        "text": outcome.text,
                        "validationErrors": [],
                        "toolSummaries": [],
                        "responseKind": "command",
                        "streamKind": "final_only",
                        "chunkCount": 0,
                        "registrationStatus": registration_status,
                        "registrationIssue": registration_issue,
                    }
                    if extension_action is not None:
                        response["extensionAction"] = extension_action
                    return response

            if turn_skill_name is None:
                outcome = await session.turn_outcome(
                    turn_text,
                    display_input=original_text,
                    turn_id=turn_id,
                    retry=params["retry"],
                )
            else:
                outcome = await session.turn_outcome(
                    turn_text,
                    display_input=original_text,
                    turn_id=turn_id,
                    skill_name=turn_skill_name,
                    retry=params["retry"],
                )
            if (
                outcome.turn_id != turn_id
                or not 1 <= outcome.turn_number <= 4_096
                or outcome.state != "completed"
                or outcome.accepted is not True
                or outcome.persisted is not True
            ):
                raise DesktopServiceError(
                    "INTERNAL_ERROR",
                    "The session returned an invalid durable turn result.",
                )
            if not isinstance(outcome.text, str) or not outcome.text.strip():
                raise DesktopServiceError(
                    "INTERNAL_ERROR", "The session returned no displayable answer."
                )
            if len(outcome.text.encode("utf-8")) > _MAX_ANSWER_BYTES:
                raise DesktopServiceError(
                    "INTERNAL_ERROR", "The session answer exceeded the desktop limit."
                )
            validation_errors = self._validation_error_dtos(
                outcome.validation_errors
            )
            tool_summaries = list(self._tool_summaries.values())[:512]
            self._ensure_turn_result_fits_wire(
                session_id=session.session_id,
                text=outcome.text,
                validation_errors=validation_errors,
                tool_summaries=tool_summaries,
            )
            registration_status, registration_issue = (
                self._saved_session_registration_result(session)
            )
            return {
                "sessionId": session.session_id,
                "turnId": outcome.turn_id,
                "turnNumber": outcome.turn_number,
                "state": outcome.state,
                "accepted": outcome.accepted,
                "persisted": outcome.persisted,
                "text": outcome.text,
                "validationErrors": validation_errors,
                "toolSummaries": tool_summaries,
                "responseKind": "answer",
                "streamKind": "final_only",
                "chunkCount": 0,
                "registrationStatus": registration_status,
                "registrationIssue": registration_issue,
            }
        finally:
            self._complete_pending_approval(False)
            self._active_parent_request_id = None
            self._active_turn_id = None
            self._turn_loop = None
            self._turn_event_sink = None
            self._tool_names = {}
            self._tool_summaries = {}
            self._turn_active = False

    async def _session_set_mode(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        session = self._require_idle_session()
        if params["mode"] == "plan":
            if not session.plan_mode:
                await session.enter_plan_mode()
        elif session.plan_mode:
            await session.exit_plan_mode()
        return self._session_snapshot(session)

    async def _session_set_thinking(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        session = self._require_idle_session()
        session.set_thinking_mode(params["mode"])
        return self._session_snapshot(session)

    async def _session_shutdown(
        self, _params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        return await self._shutdown_session()

    async def _runtime_shutdown(
        self, _params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        self._complete_pending_approval(False)
        if self.lifecycle == "stopped":
            return {"status": "stopped"}
        if self._session_creating:
            raise DesktopServiceError(
                "SESSION_NOT_READY",
                "A desktop session is still being created.",
                retryable=True,
            )
        if self._turn_active:
            raise DesktopServiceError(
                "BUSY_TURN", "A session turn is still active.", retryable=True
            )
        if self._knowledge_active:
            raise DesktopServiceError(
                "BUSY_KNOWLEDGE_MUTATION",
                "A knowledge mutation is still active.",
                retryable=True,
            )
        if self._extension_active:
            raise DesktopServiceError(
                "BUSY_EXTENSION_OPERATION",
                "An extension operation is still active.",
                retryable=True,
            )
        self.lifecycle = "shutting_down"
        try:
            await self._shutdown_session()
        except DesktopServiceError:
            self.lifecycle = "ready"
            raise
        self.lifecycle = "stopped"
        return {"status": "stopped"}

    async def _shutdown_session(self) -> dict[str, Any]:
        self._complete_pending_approval(False)
        if self._session_creating:
            raise DesktopServiceError(
                "SESSION_NOT_READY",
                "A desktop session is still being created.",
                retryable=True,
            )
        if self._turn_active:
            raise DesktopServiceError(
                "BUSY_TURN", "A session turn is still active.", retryable=True
            )
        if self._session_closing:
            raise DesktopServiceError(
                "SESSION_NOT_READY",
                "The desktop session is already shutting down.",
                retryable=True,
            )
        if self._knowledge_active:
            raise DesktopServiceError(
                "BUSY_KNOWLEDGE_MUTATION",
                "A knowledge mutation is still active.",
                retryable=True,
            )
        if self._extension_active:
            raise DesktopServiceError(
                "BUSY_EXTENSION_OPERATION",
                "An extension operation is still active.",
                retryable=True,
            )
        session = self.session
        if session is None:
            self._session_registered = False
            self._pending_registration = None
            self._control_snapshots.clear()
            self._clear_session_caches()
            return {"status": "no_session"}
        self._session_closing = True
        try:
            self.session = None
        finally:
            self._session_closing = False
        self._load_mcp = True
        self._session_registered = False
        self._pending_registration = None
        self._control_snapshots.clear()
        self._clear_session_caches()
        return {"status": "stopped"}

    def _clear_session_caches(self) -> None:
        self._complete_pending_approval(False)
        self._extension_previews.clear()
        self._prune_previews.clear()
        self._composer_prune_preview = None

    def _require_session(self) -> ChatSession:
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

    def _require_idle_session(self) -> ChatSession:
        if self._turn_active:
            raise DesktopServiceError(
                "BUSY_TURN", "A session turn is still active.", retryable=True
            )
        if self._knowledge_active:
            raise DesktopServiceError(
                "BUSY_KNOWLEDGE_MUTATION",
                "A knowledge operation is still active.",
                retryable=True,
            )
        return self._require_session()

    def _session_snapshot(self, session: ChatSession) -> dict[str, Any]:
        status = session.status_snapshot()
        return {
            "sessionId": session.session_id,
            "turnCount": int(status.get("turn_count", 0)),
            "graphRecursionLimit": int(session.config.graph_recursion_limit),
            "planMode": bool(session.plan_mode),
            "planLogPath": str(session.plan_log_path) if session.plan_log_path else None,
            "thinkingMode": session.thinking_mode,
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

    def _on_session_progress(self, node_name: str, new_messages: list[Any]) -> None:
        sink = self._turn_event_sink
        if sink is None:
            return
        sink("stage.changed", {"stage": str(node_name)})
        for message in new_messages:
            if isinstance(message, AIMessage):
                for call in message.tool_calls:
                    name = str(call.get("name", "")).strip()
                    call_id = str(call.get("id", "")).strip()
                    if not name:
                        continue
                    name = self._bounded_text(name, 256)
                    call_id = self._bounded_text(call_id, 256) if call_id else ""
                    if call_id:
                        self._tool_names[call_id] = name
                    data: dict[str, Any] = {"name": name, "status": "started"}
                    if call_id:
                        data["callId"] = call_id
                    sink("tool.started", data)
                continue
            if not isinstance(message, ToolMessage):
                continue
            call_id = str(message.tool_call_id or "").strip()
            name = str(message.name or self._tool_names.get(call_id, "")).strip()
            if not name:
                continue
            name = self._bounded_text(name, 256)
            call_id = self._bounded_text(call_id, 256) if call_id else ""
            status = self._tool_message_status(message)
            summary: dict[str, str] = {"name": name, "status": status}
            if call_id:
                summary["callId"] = call_id
            self._tool_summaries[call_id or f"{name}:{len(self._tool_summaries)}"] = summary
            sink(
                "tool.failed" if status in {"failed", "denied"} else "tool.finished",
                dict(summary),
            )

    @staticmethod
    def _tool_message_status(message: ToolMessage) -> str:
        text = content_text(message.content)
        if getattr(message, "status", None) == "error":
            if "tool not available in the current mode" in text.casefold():
                return "denied"
            return "failed"
        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            payload = None
        if isinstance(payload, dict) and payload.get("approved") is False:
            return "denied"
        return "ok"

    async def _knowledge_overview(
        self, _params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        inventory = await asyncio.to_thread(explore, config=self.config)
        meta_path = Path(self.config.folder_meta_path())
        return {
            "storePath": str(Path(self.config.persist_dir).expanduser().resolve()),
            "folderMetadataPresent": meta_path.is_file(),
            "categories": [
                {"name": name, "count": count}
                for name, count in sorted(inventory.categories.items())
            ],
            "tags": list(inventory.tags),
            "dateRange": list(inventory.date_range) if inventory.date_range else None,
            "folders": [
                {
                    "folder": item.folder,
                    "category": item.category,
                    "tags": list(item.tags),
                    "summary": item.summary,
                }
                for item in inventory.folders
            ],
        }

    async def _knowledge_search(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        if self._knowledge_active:
            raise DesktopServiceError(
                "BUSY_KNOWLEDGE_MUTATION",
                "A knowledge mutation is active.",
                retryable=True,
            )
        hits = await asyncio.to_thread(
            search,
            params["query"],
            k=params.get("k", 5),
            folder_prefix=params.get("folderPrefix"),
            category=params.get("category"),
            file_type=params.get("fileType"),
            date_from=params.get("dateFrom"),
            date_to=params.get("dateTo"),
            config=self.config,
        )
        return {"items": [self._hit_dto(hit) for hit in hits]}

    async def _knowledge_list_chunks(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        hits = await asyncio.to_thread(
            list_chunks,
            folder_prefix=params.get("folderPrefix"),
            pid=params.get("pid"),
            category=params.get("category"),
            file_type=params.get("fileType"),
            date_from=params.get("dateFrom"),
            date_to=params.get("dateTo"),
            config=self.config,
        )
        offset = params.get("offset", 0)
        limit = params.get("limit", 50)
        page = hits[offset : offset + limit]
        return {
            "items": [self._hit_dto(hit) for hit in page],
            "total": len(hits),
            "offset": offset,
            "limit": limit,
            "hasMore": offset + len(page) < len(hits),
        }

    async def _knowledge_get_context(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        window = await asyncio.to_thread(
            get_context,
            params["pid"],
            params["chunkId"],
            window=params.get("window", 1),
            config=self.config,
        )
        if window is None:
            return {
                "found": False,
                "pid": params["pid"],
                "targetChunkId": params["chunkId"],
                "chunks": [],
                "totalChunksInDoc": 0,
            }
        return {
            "found": True,
            "pid": window.pid,
            "targetChunkId": window.target_chunk_id,
            "chunks": [
                {
                    "chunkId": chunk.chunk_id,
                    "text": chunk.text,
                    "isTarget": chunk.is_target,
                }
                for chunk in window.chunks
            ],
            "totalChunksInDoc": window.total_chunks_in_doc,
        }

    async def _knowledge_init_workspace(
        self, _params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        raise DesktopServiceError(
            "RAG_WRITE_FAILED",
            "Workspace ingest requires structured progress and is not enabled yet.",
        )

    async def _knowledge_ingest_file(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        target = self._validated_path(params["path"], kind="file")
        if (
            target.suffix.lower() not in TEXT_EXTENSIONS
            and target.name not in _EXTENSIONLESS_INGEST_FILES
        ):
            raise DesktopServiceError(
                "INVALID_PATH", "The selected file type is not supported for ingest."
            )
        async with self._knowledge_operation():
            pid, chunks = await ingest_file(target, self.config)
        if chunks <= 0:
            raise DesktopServiceError(
                "RAG_WRITE_FAILED",
                "The selected file contains no indexable UTF-8 text.",
            )
        return {"path": str(target), "pid": pid, "chunks": chunks}

    async def _knowledge_ingest_folder(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        self._validated_path(params["path"], kind="directory")
        raise DesktopServiceError(
            "RAG_WRITE_FAILED",
            "Folder ingest requires structured progress and is not enabled yet.",
        )

    async def _knowledge_sync(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        target = self._validated_path(params["path"], kind="directory")
        async with self._knowledge_operation():
            diff = await diff_folder(target, self.config)
        return {
            "root": str(target),
            "missingFromStore": list(diff["missing_from_store"]),
            "missingFromDisk": list(diff["missing_from_disk"]),
            "comparison": "path_presence_only",
        }

    async def _knowledge_prune_preview(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        target = self._validated_path(
            params["path"], kind="directory", destructive_root=True
        )
        async with self._knowledge_operation():
            diff = await diff_folder(target, self.config)
        orphans = tuple(sorted(diff["missing_from_disk"]))
        digest = self._prune_digest(target, orphans)
        preview_id = uuid.uuid4().hex
        self._bounded_cache_insert(
            self._prune_previews,
            preview_id,
            _PrunePreview(target, orphans, digest),
        )
        return {
            "previewId": preview_id,
            "root": str(target),
            "orphans": list(orphans),
            "count": len(orphans),
            "hash": digest,
        }

    async def _knowledge_prune_apply(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        preview = self._prune_previews.get(params["previewId"])
        if preview is None:
            raise DesktopServiceError(
                "PRUNE_PREVIEW_STALE", "The prune preview is unknown or already used."
            )
        async with self._knowledge_operation():
            latest = await diff_folder(preview.root, self.config)
            latest_orphans = tuple(sorted(latest["missing_from_disk"]))
            if self._prune_digest(preview.root, latest_orphans) != preview.digest:
                self._prune_previews.pop(params["previewId"], None)
                raise DesktopServiceError(
                    "PRUNE_PREVIEW_STALE",
                    "The prune preview changed; preview again before applying.",
                )
            try:
                removed = await prune_folder(preview.root, self.config)
            finally:
                self._prune_previews.pop(params["previewId"], None)
        return {"root": str(preview.root), "deleted": list(removed)}

    @staticmethod
    def _prune_digest(root: Path, orphans: tuple[str, ...]) -> str:
        payload = json.dumps(
            {"root": str(root), "orphans": list(orphans)},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def _extensions_status(
        self, _params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        session = self.session
        status = await asyncio.to_thread(
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

    async def _extensions_apply(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        preview_id = params["previewId"]
        preview = self._extension_previews.get(preview_id)
        if preview is None:
            raise DesktopServiceError(
                "EXTENSION_APPLY_FAILED",
                "The extension preview is unknown or already used.",
            )
        approved = set(params["approvedBindingHashes"])
        known = {
            candidate.binding_hash for candidate in preview.mcp_candidates.values()
        }
        if any(not _BINDING_HASH.fullmatch(item) for item in approved) or not approved <= known:
            raise DesktopServiceError(
                "PROTOCOL_INVALID",
                "The approved extension binding list is invalid.",
            )
        async with self._extension_operation():
            try:
                report = await asyncio.to_thread(
                    self._extension_manager.apply,
                    preview,
                    approved_mcp_bindings=approved,
                )
            finally:
                self._extension_previews.pop(preview_id, None)
        return self._extension_apply_dto(report)

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

    @staticmethod
    def _utc_timestamp(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z")

    def _desktop_bash_approval(
        self,
        command: str,
        description: str,
        execution_timeout_seconds: int,
    ) -> bool:
        loop = self._turn_loop
        if loop is None or loop.is_closed():
            return False
        staged = asyncio.run_coroutine_threadsafe(
            self._stage_bash_approval(
                command,
                description,
                execution_timeout_seconds,
            ),
            loop,
        )
        try:
            return bool(staged.result(timeout=self._approval_timeout_seconds + 1.0))
        except Exception:
            staged.cancel()
            return False

    async def _stage_bash_approval(
        self,
        command: str,
        description: str,
        execution_timeout_seconds: int,
    ) -> bool:
        sink = self._turn_event_sink
        parent_request_id = self._active_parent_request_id
        turn_id = self._active_turn_id
        if (
            self._pending_approval is not None
            or sink is None
            or parent_request_id is None
            or turn_id is None
            or not self._approval_context_is_safe(command, description)
        ):
            return False

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self._approval_timeout_seconds)
        pending = _PendingApproval(
            approval_id=uuid.uuid4().hex,
            parent_request_id=parent_request_id,
            turn_id=turn_id,
            expires_at=expires_at,
            future=asyncio.get_running_loop().create_future(),
        )
        self._pending_approval = pending
        try:
            sink("approval.required", {
                "approvalId": pending.approval_id,
                "parentRequestId": pending.parent_request_id,
                "turnId": pending.turn_id,
                "command": command,
                "description": description,
                "executionTimeoutSeconds": execution_timeout_seconds,
                "createdAt": self._utc_timestamp(now),
                "expiresAt": self._utc_timestamp(expires_at),
            })
        except Exception:
            self._complete_pending_approval(False)
            return False

        try:
            return bool(await asyncio.wait_for(
                asyncio.shield(pending.future),
                timeout=self._approval_timeout_seconds,
            ))
        except (TimeoutError, asyncio.CancelledError):
            return False
        finally:
            if self._pending_approval is pending:
                self._pending_approval = None
            if not pending.future.done():
                pending.future.cancel()

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
        self._complete_pending_approval(approved)
        return {"approvalId": approval_id, "approved": approved}

    @asynccontextmanager
    async def _knowledge_operation(self, *, turn_owned: bool = False):
        if self._knowledge_active or (self._turn_active and not turn_owned):
            raise DesktopServiceError(
                "BUSY_KNOWLEDGE_MUTATION",
                "Another knowledge mutation is active.",
                retryable=True,
            )
        self._knowledge_active = True
        try:
            yield
        finally:
            self._knowledge_active = False

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

    def _validated_path(
        self,
        raw: str,
        *,
        kind: str,
        destructive_root: bool = False,
    ) -> Path:
        if (
            not raw
            or _WINDOWS_DRIVE.match(raw)
            or raw.startswith("\\\\")
            or raw.startswith("//")
        ):
            raise DesktopServiceError(
                "INVALID_PATH", "Select an absolute Linux path."
            )
        candidate = Path(raw)
        if not candidate.is_absolute() or any(
            part.is_symlink() for part in (candidate, *candidate.parents)
        ):
            raise DesktopServiceError(
                "INVALID_PATH", "Select a non-symlink absolute Linux path."
            )
        try:
            resolved = candidate.resolve(strict=True)
        except (FileNotFoundError, OSError) as exc:
            raise DesktopServiceError(
                "INVALID_PATH", "The selected path does not exist."
            ) from exc
        if kind == "file" and not resolved.is_file():
            raise DesktopServiceError("INVALID_PATH", "The selected path is not a file.")
        if kind == "directory" and not resolved.is_dir():
            raise DesktopServiceError(
                "INVALID_PATH", "The selected path is not a directory."
            )
        if kind == "file-or-directory" and not (
            resolved.is_file() or resolved.is_dir()
        ):
            raise DesktopServiceError(
                "INVALID_PATH",
                "The selected path is not a file or directory.",
            )
        if destructive_root and resolved == Path(resolved.anchor):
            raise DesktopServiceError(
                "INVALID_PATH", "The filesystem root cannot be used here."
            )
        if any(part in SKIP_DIRS for part in resolved.parts):
            raise DesktopServiceError(
                "INVALID_PATH", "The selected path is under an excluded directory."
            )
        for protected in self._protected_roots():
            if (
                resolved == protected
                or resolved.is_relative_to(protected)
                or (resolved.is_dir() and protected.is_relative_to(resolved))
            ):
                raise DesktopServiceError(
                    "INVALID_PATH", "The selected path overlaps application state."
                )
        return resolved

    def _protected_roots(self) -> tuple[Path, ...]:
        extension_paths = resolve_extension_paths(self.config, env=self.environ)
        skills_root = (
            Path(self.config.skills_dir).expanduser().resolve()
            if self.config.skills_dir
            else DEFAULT_SKILLS_DIR.resolve()
        )
        roots = {
            Path(self.config.persist_dir).expanduser().resolve(),
            (find_app_root() / self.config.plan_logs_dir).resolve(),
            skills_root,
            resolve_output_dir(self.config, self.environ).expanduser().resolve(),
            extension_paths.dropin_root.resolve(),
            extension_paths.state_root.resolve(),
        }
        return tuple(sorted(roots, key=str))

    @staticmethod
    def _hit_dto(hit: Any) -> dict[str, Any]:
        score = hit.score
        if not isinstance(score, (int, float)) or not math.isfinite(score):
            score = None
        return {
            "pid": hit.pid,
            "chunkId": hit.chunk_id,
            "text": hit.text,
            "filePath": hit.file_path,
            "category": hit.category,
            "fileType": hit.file_type,
            "folder": hit.folder,
            "date": hit.date,
            "tags": list(hit.tags),
            "score": score,
        }

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
    def _extension_apply_dto(cls, report: ApplyReport) -> dict[str, Any]:
        return {
            "previousRevision": report.previous_revision,
            "appliedRevision": report.applied_revision,
            "restartRequired": report.restart_required,
            "items": [
                {
                    "key": cls._bounded_text(item.key, 256),
                    "outcome": cls._bounded_text(item.outcome, 64),
                    "detail": cls._extension_outcome_detail(item.outcome),
                }
                for item in report.items
            ],
            "diagnostics": [
                "The extension manager reported a host validation diagnostic."
                for _diagnostic in report.diagnostics[:128]
            ],
        }

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
