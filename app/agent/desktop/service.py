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
from collections.abc import Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.errors import GraphRecursionError

from agent.config import AgentConfig, validate_graph_recursion_limit
from agent.cli.slash_commands import (
    SlashCommandContext,
    SlashCommandError,
    SlashCommandRegistry,
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
    is_canonical_session_id,
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
from agent.ingest import diff_folder, ingest_file, prune_folder
from agent.history_rag.store import HistoryRestoreError, get_chat_history_store
from agent.paths import find_app_root
from agent.session import ChatSession
from agent.skills import DEFAULT_SKILLS_DIR, load_skill_manifest
from agent.turns.safety import content_text
from agent.turns.journal import TurnRestoreError, merge_restored_turns
from agent.turns.memory import TurnRecord
from agent.turns.plan_log import PlanLog, PlanLogRestoreError
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
_DESKTOP_SLASH_COMMANDS = frozenset({"status"})
_MAX_ANSWER_BYTES = 2_097_152
_MAX_ANSWER_CHUNK_BYTES = 16_384
_MAX_ANSWER_CHUNKS = 128
_MAX_LOCAL_COMMAND_BYTES = 65_536
_MAX_TRANSCRIPT_PAGE_BYTES = 1_048_576
_MAX_CONTROL_SNAPSHOTS = CATALOG_MAX_SESSIONS
_WIRE_BUDGET_REQUEST_ID = "00000000-0000-4000-8000-000000000000"
_WIRE_BUDGET_TURN_ID = "0" * 32


class DesktopServiceError(ProtocolError):
    """A domain or lifecycle failure safe to return over the desktop wire."""


@dataclass(frozen=True)
class _PrunePreview:
    root: Path
    orphans: tuple[str, ...]
    digest: str


@dataclass(frozen=True)
class _ConversationControlSnapshot:
    plan_mode: bool
    plan_log_path: str | None
    thinking_mode: str
    active_skill: str | None
    task_mode: str | None


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
    ) -> None:
        self.original_cwd = (original_cwd or Path.cwd()).expanduser().resolve()
        self.environ = dict(os.environ if environ is None else environ)
        self.config = config or AgentConfig()
        self.lifecycle = "ready"
        self.session: ChatSession | None = None

        self._session_factory = session_factory or ChatSession.create
        self._slash_registry = slash_registry or build_default_registry()
        self._extension_manager = extension_manager or ExtensionManager(self.config)
        self._catalog: DesktopProjectCatalog | None = project_catalog
        self._catalog_issue: str | None = None
        if self._catalog is None:
            try:
                self._catalog = DesktopProjectCatalog(self.config.persist_dir)
            except (CatalogMalformedError, CatalogUnavailableError):
                self._catalog_issue = "The local project catalog is unavailable."
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
        self._history_store = None
        self._load_mcp = False
        self._session_creating = False
        self._turn_active = False
        self._session_closing = False
        self._knowledge_active = False
        self._extension_active = False
        self._turn_event_sink: EventSink | None = None
        self._tool_names: dict[str, str] = {}
        self._tool_summaries: dict[str, dict[str, str]] = {}
        self._extension_previews: dict[str, ExtensionPreview] = {}
        self._prune_previews: dict[str, _PrunePreview] = {}

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
            "session.list_skills": self._session_list_skills,
            "session.activate_skill": self._session_activate_skill,
            "session.deactivate_skill": self._session_deactivate_skill,
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
        except DesktopServiceError:
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
            raise mapped from exc

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
        project = self._require_catalog_project(params["projectId"])
        offset = int(params.get("offset", 0))
        limit = int(params.get("limit", 50))
        session_ids = project["sessionIds"]
        items: list[dict[str, Any]] = []
        for session_id in session_ids[offset : offset + limit]:
            items.append(await self._conversation_summary(session_id))
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
            restored_turns = await asyncio.to_thread(
                self._read_conversation_turns,
                session_id,
                False,
            )
        except (HistoryRestoreError, PlanLogRestoreError, TurnRestoreError) as exc:
            raise DesktopServiceError(
                "SESSION_NOT_READY",
                "The stored conversation is degraded and cannot be selected.",
            ) from exc
        if not restored_turns:
            raise DesktopServiceError(
                "SESSION_NOT_READY",
                "The stored conversation has no restorable transcript.",
            )

        self._session_creating = True
        current = self.session
        saved_recent: list[TurnRecord] = []
        saved_controls: _ConversationControlSnapshot | None = None
        if current is not None:
            saved_recent = self._copy_recent_turns(current)
            saved_controls = self._capture_controls(current)
        try:
            if current is not None:
                await self._flush_for_conversation_switch(current, saved_recent)
            target = await self._materialize_session(
                self.config,
                load_mcp=self._load_mcp,
                session_id=session_id,
                restored_turns=restored_turns,
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
        except Exception:
            if current is not None:
                self._restore_recent_turns(current, saved_recent)
            raise
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
                True,
            )
        except (HistoryRestoreError, PlanLogRestoreError, TurnRestoreError):
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
        if any(
            len(turn.user_input.encode("utf-8")) > 32_768
            or len(turn.assistant_output.encode("utf-8")) > 32_768
            or len(turn.timestamp.encode("utf-8")) > 64
            for turn in page
        ):
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
        page_bytes = sum(
            len(turn.user_input.encode("utf-8"))
            + len(turn.assistant_output.encode("utf-8"))
            + len(turn.timestamp.encode("utf-8"))
            for turn in page
        )
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

    async def _conversation_summary(self, session_id: str) -> dict[str, Any]:
        try:
            turns = await asyncio.to_thread(
                self._read_conversation_turns,
                session_id,
                True,
            )
        except (HistoryRestoreError, PlanLogRestoreError, TurnRestoreError):
            return {
                "sessionId": session_id,
                "title": f"Conversation {session_id[:8]}",
                "turnCount": 0,
                "updatedAt": None,
                "status": "degraded",
                "issue": "The stored transcript is malformed or incomplete.",
            }
        if not turns:
            return {
                "sessionId": session_id,
                "title": f"Conversation {session_id[:8]}",
                "turnCount": 0,
                "updatedAt": None,
                "status": "unavailable",
                "issue": "No persisted transcript is available.",
            }
        title = " ".join(turns[0].user_input.split())
        return {
            "sessionId": session_id,
            "title": self._bounded_text(title, 256)
            or f"Conversation {session_id[:8]}",
            "turnCount": turns[-1].turn_id,
            "updatedAt": self._bounded_text(turns[-1].timestamp, 64),
            "status": "ready",
            "issue": None,
        }

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

    def _read_conversation_turns(
        self,
        session_id: str,
        include_current: bool,
    ) -> list[TurnRecord]:
        if not is_canonical_session_id(session_id):
            raise TurnRestoreError("session_id must be canonical UUIDv4 hex")
        if self._history_store is None:
            self._history_store = get_chat_history_store(self.config)
        history_turns = self._history_store.read_session_turns(session_id)
        plan_turns = PlanLog(
            self.config,
            session_id=session_id,
            app_root_resolver=lambda: find_app_root(),
        ).read_direct_answer_turns()
        stored = merge_restored_turns(history_turns, plan_turns)
        if (
            not include_current
            or self.session is None
            or self.session.session_id != session_id
        ):
            return stored

        by_turn = {turn.turn_id: turn for turn in stored}
        for turn in self._copy_recent_turns(self.session):
            restored = replace(turn, persist_target="none")
            existing = by_turn.get(restored.turn_id)
            if existing is not None and (
                existing.user_input != restored.user_input
                or existing.assistant_output != restored.assistant_output
                or existing.timestamp != restored.timestamp
            ):
                raise TurnRestoreError(
                    "current and persisted conversation turns disagree"
                )
            by_turn[restored.turn_id] = restored
        return merge_restored_turns(list(by_turn.values()))

    @staticmethod
    def _transcript_result(
        project_id: str,
        session_id: str,
        *,
        status: str,
        issue: str | None,
        turns: list[TurnRecord],
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
                    "turnNumber": turn.turn_id,
                    "timestamp": turn.timestamp,
                    "userText": turn.user_input,
                    "assistantText": turn.assistant_output,
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
        session_id: str | None = None,
        restored_turns: list[TurnRecord] | None = None,
    ) -> ChatSession:
        kwargs: dict[str, Any] = {
            "load_mcp": load_mcp,
            "progress_cb": self._on_session_progress,
        }
        if session_id is not None:
            kwargs["session_id"] = session_id
            kwargs["restored_turns"] = list(restored_turns or [])
        session = await self._session_factory(config, **kwargs)
        if isinstance(session, ChatSession):
            session._set_final_text_validator(
                lambda text, errors: self._validate_final_text_before_record(
                    session.session_id,
                    text,
                    errors,
                )
            )
        return session

    @staticmethod
    def _capture_controls(session: ChatSession) -> _ConversationControlSnapshot:
        runtime = session.active_skill_runtime
        return _ConversationControlSnapshot(
            plan_mode=bool(session.plan_mode),
            plan_log_path=(
                str(session.plan_log_path) if session.plan_log_path else None
            ),
            thinking_mode=str(session.thinking_mode),
            active_skill=(str(runtime.name) if runtime is not None else None),
            task_mode=(
                str(runtime.task_mode)
                if runtime is not None and runtime.task_mode
                else None
            ),
        )

    async def _apply_controls(
        self,
        session: ChatSession,
        snapshot: _ConversationControlSnapshot | None,
    ) -> None:
        if snapshot is None:
            return
        if snapshot.active_skill is not None:
            session.activate_skill(snapshot.active_skill, snapshot.task_mode)
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

    @staticmethod
    def _copy_recent_turns(session: ChatSession) -> list[TurnRecord]:
        turns: list[TurnRecord] = []
        for turn in getattr(session, "recent_turns", []):
            if not isinstance(turn, TurnRecord):
                continue
            turns.append(replace(turn))
        return turns

    @staticmethod
    def _restore_recent_turns(
        session: ChatSession,
        turns: list[TurnRecord],
    ) -> None:
        recent = getattr(session, "recent_turns", None)
        if not isinstance(recent, list):
            return
        by_id = {
            turn.turn_id: turn
            for turn in recent
            if isinstance(turn, TurnRecord)
        }
        for turn in turns:
            by_id.setdefault(turn.turn_id, replace(turn, persist_target="none"))
        recent[:] = [by_id[turn_id] for turn_id in sorted(by_id)]

    async def _flush_for_conversation_switch(
        self,
        session: ChatSession,
        saved_recent: list[TurnRecord],
    ) -> None:
        try:
            await session.flush_recent_turns()
        except Exception as exc:
            self._restore_recent_turns(session, saved_recent)
            raise DesktopServiceError(
                "CONVERSATION_FLUSH_FAILED",
                "Recent turns could not be flushed before changing conversations.",
                retryable=True,
            ) from exc
        remaining = len(getattr(session, "recent_turns", []))
        if remaining:
            self._restore_recent_turns(session, saved_recent)
            raise DesktopServiceError(
                "CONVERSATION_FLUSH_FAILED",
                "Recent turns remain unflushed; the current conversation was retained.",
                retryable=True,
                details={"remainingTurns": remaining},
            )

    async def _session_create(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
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
        saved_recent: list[TurnRecord] = []
        saved_controls: _ConversationControlSnapshot | None = None
        if current is not None:
            saved_recent = self._copy_recent_turns(current)
            saved_controls = self._capture_controls(current)
        try:
            if current is not None:
                await self._flush_for_conversation_switch(current, saved_recent)
            session = await self._materialize_session(
                config,
                load_mcp=load_mcp,
            )
            if self.lifecycle != "ready":
                raise DesktopServiceError(
                    "SESSION_NOT_READY",
                    "The desktop backend changed state while creating the session.",
                )
        except Exception:
            if current is not None:
                self._restore_recent_turns(current, saved_recent)
            raise
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
            "text": text,
            "validationErrors": validation_errors,
            "toolSummaries": tool_summaries,
            "responseKind": "answer",
            "streamKind": "post_finalized",
            "chunkCount": _MAX_ANSWER_CHUNKS,
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

    async def _session_turn(
        self, params: dict[str, Any], event_sink: EventSink | None
    ) -> dict[str, Any]:
        session = self._require_session()
        if self._turn_active:
            raise DesktopServiceError(
                "BUSY_TURN", "Another session turn is already active.", retryable=True
            )
        self._turn_active = True
        self._turn_event_sink = event_sink
        self._tool_names = {}
        self._tool_summaries = {}
        turn_id = uuid.uuid4().hex
        try:
            original_text = params["text"]
            try:
                parsed = parse_slash_command(original_text)
            except SlashCommandError as exc:
                raise DesktopServiceError(
                    "PROTOCOL_INVALID",
                    self._bounded_text(str(exc), 4_096),
                ) from exc

            if parsed is not None:
                command = self._slash_registry.get(parsed.name)
                if command is None:
                    raise DesktopServiceError(
                        "PROTOCOL_INVALID",
                        f"Unknown slash command: /{self._bounded_text(parsed.name, 256)}",
                    )
                if (
                    parsed.name.casefold() != command.name.casefold()
                    or command.name not in _DESKTOP_SLASH_COMMANDS
                ):
                    raise DesktopServiceError(
                        "PROTOCOL_INVALID",
                        "That slash command is not available in the desktop composer.",
                    )
                try:
                    result = await execute_slash_command(
                        parsed,
                        SlashCommandContext(
                            session=session,
                            registry=self._slash_registry,
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
                return {
                    "sessionId": session.session_id,
                    "turnId": turn_id,
                    "text": message,
                    "validationErrors": [],
                    "toolSummaries": [],
                    "responseKind": "command",
                    "streamKind": "final_only",
                    "chunkCount": 0,
                    "registrationStatus": "not_required",
                    "registrationIssue": None,
                }

            outcome = await session.turn_outcome(original_text)
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
            registration_status = "registered"
            registration_issue: str | None = None
            if not self._session_registered:
                project_id = self._selected_project_id
                if self._catalog is None or project_id is None:
                    registration_status = "pending"
                    registration_issue = (
                        "The answer was saved, but the project catalog is unavailable."
                    )
                else:
                    try:
                        self._catalog.register_session(
                            project_id,
                            session.session_id,
                        )
                    except CatalogError:
                        registration_status = "pending"
                        registration_issue = (
                            "The answer was saved, but catalog registration failed."
                        )
                if registration_status == "registered":
                    self._session_registered = True
                    self._pending_registration = None
                elif project_id is not None:
                    self._pending_registration = (project_id, session.session_id)
            chunk_count = self._emit_answer_chunks(
                event_sink,
                session_id=session.session_id,
                turn_id=turn_id,
                text=outcome.text,
            )
            return {
                "sessionId": session.session_id,
                "turnId": turn_id,
                "text": outcome.text,
                "validationErrors": validation_errors,
                "toolSummaries": tool_summaries,
                "responseKind": "answer",
                "streamKind": (
                    "post_finalized" if chunk_count else "final_only"
                ),
                "chunkCount": chunk_count,
                "registrationStatus": registration_status,
                "registrationIssue": registration_issue,
            }
        finally:
            self._turn_event_sink = None
            self._tool_names = {}
            self._tool_summaries = {}
            self._turn_active = False

    @classmethod
    def _emit_answer_chunks(
        cls,
        event_sink: EventSink | None,
        *,
        session_id: str,
        turn_id: str,
        text: str,
    ) -> int:
        if event_sink is None:
            return 0
        chunks = cls._utf8_chunks(text, _MAX_ANSWER_CHUNK_BYTES)
        if len(chunks) > _MAX_ANSWER_CHUNKS:
            return 0
        emitted = 0
        for chunk_index, chunk in enumerate(chunks):
            try:
                event_sink(
                    "answer.chunk",
                    {
                        "sessionId": session_id,
                        "turnId": turn_id,
                        "chunkIndex": chunk_index,
                        "streamKind": "post_finalized",
                        "text": chunk,
                    },
                )
            except Exception as exc:
                logger.warning(
                    "Desktop answer event sink failed with %s",
                    type(exc).__name__,
                )
                break
            emitted += 1
        return emitted

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

    async def _session_list_skills(
        self, _params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        session = self._require_session()
        active = session.active_skill_runtime
        items: list[dict[str, Any]] = []
        builtin_root = DEFAULT_SKILLS_DIR.resolve()
        for skill in session.loaded_skills:
            task_modes: list[str] = []
            error: str | None = None
            try:
                manifest = load_skill_manifest(skill.path.parent)
                task_modes = [
                    str(mode)
                    for mode in manifest.get("task_modes", [])
                    if isinstance(mode, str)
                ]
            except (OSError, ValueError):
                error = "Skill metadata is unavailable."
            source = (
                "builtin"
                if skill.path.resolve().is_relative_to(builtin_root)
                else "applied"
            )
            is_active = active is not None and active.name == skill.name
            items.append(
                {
                    "name": skill.name,
                    "description": skill.description,
                    "taskModes": task_modes,
                    "source": source,
                    "active": is_active,
                    "activeTaskMode": active.task_mode if is_active else None,
                    "available": error is None,
                    "error": error,
                }
            )
        return {"skills": items}

    async def _session_activate_skill(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        session = self._require_idle_session()
        session.activate_skill(params["name"], params.get("taskMode"))
        return self._session_snapshot(session)

    async def _session_deactivate_skill(
        self, _params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        session = self._require_idle_session()
        session.deactivate_skill()
        return self._session_snapshot(session)

    async def _session_shutdown(
        self, _params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        return await self._shutdown_session()

    async def _runtime_shutdown(
        self, _params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        if self.lifecycle == "stopped":
            return {"status": "stopped", "flushed": True}
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
            shutdown = await self._shutdown_session()
        except DesktopServiceError:
            self.lifecycle = "ready"
            raise
        self.lifecycle = "stopped"
        return {"status": "stopped", "flushed": bool(shutdown["flushed"])}

    async def _shutdown_session(self) -> dict[str, Any]:
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
            return {"status": "no_session", "flushed": True}
        self._session_closing = True
        try:
            try:
                await session.flush_recent_turns()
            except Exception as exc:
                logger.warning(
                    "Desktop session flush failed with %s", type(exc).__name__
                )
                raise DesktopServiceError(
                    "SHUTDOWN_FLUSH_FAILED",
                    "Recent turns could not be flushed.",
                    retryable=True,
                    details={"remainingTurns": len(getattr(session, "recent_turns", []))},
                ) from exc
            remaining = len(getattr(session, "recent_turns", []))
            if remaining:
                raise DesktopServiceError(
                    "SHUTDOWN_FLUSH_FAILED",
                    "Recent turns remain unflushed.",
                    retryable=True,
                    details={"remainingTurns": remaining},
                )
        finally:
            self._session_closing = False
        self.session = None
        self._load_mcp = False
        self._session_registered = False
        self._pending_registration = None
        self._control_snapshots.clear()
        self._clear_session_caches()
        return {"status": "stopped", "flushed": True}

    def _clear_session_caches(self) -> None:
        self._extension_previews.clear()
        self._prune_previews.clear()

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
        return self._require_session()

    def _session_snapshot(self, session: ChatSession) -> dict[str, Any]:
        status = session.status_snapshot()
        runtime = session.active_skill_runtime
        return {
            "sessionId": session.session_id,
            "turnCount": int(status.get("turn_count", 0)),
            "graphRecursionLimit": int(session.config.graph_recursion_limit),
            "planMode": bool(session.plan_mode),
            "planLogPath": str(session.plan_log_path) if session.plan_log_path else None,
            "thinkingMode": session.thinking_mode,
            "activeSkill": (
                self._bounded_text(runtime.name, 256) if runtime is not None else None
            ),
            "taskMode": (
                self._bounded_text(runtime.task_mode, 256)
                if runtime is not None and runtime.task_mode
                else None
            ),
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

    async def _approval_resolve(
        self, _params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        raise DesktopServiceError(
            "APPROVAL_DENIED", "No pending desktop approval exists."
        )

    @asynccontextmanager
    async def _knowledge_operation(self):
        if self._knowledge_active:
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
        if self._extension_active:
            raise DesktopServiceError(
                "BUSY_EXTENSION_OPERATION",
                "Another extension operation is active.",
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
        roots = {
            Path(self.config.persist_dir).expanduser().resolve(),
            (find_app_root() / self.config.plan_logs_dir).resolve(),
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
            "managerError": status.manager_error,
            "diagnostics": list(status.diagnostics),
            "runningMcpFamilies": list(status.running_mcp_families),
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
            {
                "name": candidate.descriptor.id,
                "server": candidate.descriptor.family,
                "bindingHash": candidate.binding_hash,
                "requiresApproval": True,
            }
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
    def _utf8_chunks(text: str, max_bytes: int) -> list[str]:
        """Split text on UTF-8 byte boundaries without losing characters."""
        if max_bytes < 1:
            raise ValueError("max_bytes must be positive")
        chunks: list[str] = []
        current: list[str] = []
        current_bytes = 0
        for character in text:
            encoded_size = len(character.encode("utf-8"))
            if current and current_bytes + encoded_size > max_bytes:
                chunks.append("".join(current))
                current = []
                current_bytes = 0
            current.append(character)
            current_bytes += encoded_size
        if current:
            chunks.append("".join(current))
        return chunks

    @staticmethod
    def _bounded_cache_insert(cache: dict[str, Any], key: str, value: Any) -> None:
        while len(cache) >= 8:
            cache.pop(next(iter(cache)))
        cache[key] = value
