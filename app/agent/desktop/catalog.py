"""Small durable project-to-conversation catalog for the desktop client."""

from __future__ import annotations

import copy
import json
import os
import re
import tempfile
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from agent.conversations import ConversationSummary

CATALOG_FILENAME = "desktop-projects.json"
CATALOG_MAX_BYTES = 1024 * 1024
CATALOG_MAX_PROJECTS = 32
CATALOG_MAX_SESSIONS = 4096
DEFAULT_PROJECT_ID = "local"
DEFAULT_PROJECT_NAME = "Local research"

_PROJECT_ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")
_SESSION_ID_RE = re.compile(r"[0-9a-f]{32}\Z")


class CatalogError(RuntimeError):
    """Base class for explicit catalog failures."""


class CatalogUnavailableError(CatalogError):
    """The catalog could not be read or durably written."""


class CatalogMalformedError(CatalogError):
    """Existing catalog content failed the strict durable schema."""


class CatalogConflictError(CatalogError):
    """A requested catalog mutation conflicts with existing ownership."""


def is_canonical_session_id(value: object) -> bool:
    """Return whether *value* is a canonical lowercase UUIDv4 hex string."""
    if not isinstance(value, str) or _SESSION_ID_RE.fullmatch(value) is None:
        return False
    try:
        parsed = uuid.UUID(hex=value)
    except ValueError:
        return False
    return parsed.version == 4 and parsed.hex == value


def _validate_project_id(value: object) -> str:
    if not isinstance(value, str) or _PROJECT_ID_RE.fullmatch(value) is None:
        raise CatalogMalformedError("projectId must be a lowercase local identifier")
    return value


def _validate_project_name(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > 256
    ):
        raise CatalogMalformedError("project name must contain 1-256 UTF-8 bytes")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise CatalogMalformedError("project name must not contain control characters")
    return value


def _validate_snapshot(value: object) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(value, dict) or set(value) != {"projects"}:
        raise CatalogMalformedError("catalog must contain exactly a projects array")
    projects = value["projects"]
    if not isinstance(projects, list) or len(projects) > CATALOG_MAX_PROJECTS:
        raise CatalogMalformedError(
            f"catalog projects must be an array of at most {CATALOG_MAX_PROJECTS} items"
        )

    seen_projects: set[str] = set()
    seen_sessions: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for project in projects:
        if not isinstance(project, dict) or set(project) != {
            "projectId",
            "name",
            "sessionIds",
        }:
            raise CatalogMalformedError("catalog project has unexpected fields")
        project_id = _validate_project_id(project["projectId"])
        if project_id in seen_projects:
            raise CatalogMalformedError(f"duplicate projectId: {project_id}")
        seen_projects.add(project_id)
        name = _validate_project_name(project["name"])
        session_ids = project["sessionIds"]
        if not isinstance(session_ids, list):
            raise CatalogMalformedError("sessionIds must be an array")

        normalized_ids: list[str] = []
        for session_id in session_ids:
            if not is_canonical_session_id(session_id):
                raise CatalogMalformedError("sessionIds must contain canonical UUIDv4 hex")
            if session_id in seen_sessions:
                raise CatalogMalformedError(
                    f"sessionId appears more than once: {session_id}"
                )
            seen_sessions.add(session_id)
            normalized_ids.append(session_id)
        normalized.append({
            "projectId": project_id,
            "name": name,
            "sessionIds": normalized_ids,
        })

    if len(seen_sessions) > CATALOG_MAX_SESSIONS:
        raise CatalogMalformedError(
            f"catalog contains more than {CATALOG_MAX_SESSIONS} sessions"
        )
    return {"projects": normalized}


def _encode_snapshot(snapshot: dict[str, Any]) -> bytes:
    encoded = (
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    if len(encoded) > CATALOG_MAX_BYTES:
        raise CatalogMalformedError(
            f"catalog exceeds the {CATALOG_MAX_BYTES}-byte limit"
        )
    return encoded


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class DesktopProjectCatalog:
    """Validated catalog with fail-closed reads and atomic mutations."""

    def __init__(self, persist_dir: str | Path):
        self.path = Path(persist_dir) / CATALOG_FILENAME
        self._snapshot = self._load_or_bootstrap()

    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        """Return a detached durable-schema snapshot."""
        return copy.deepcopy(self._snapshot)

    def project_for_session(self, session_id: str) -> str | None:
        """Return the owning project ID, if the session is registered."""
        for project in self._snapshot["projects"]:
            if session_id in project["sessionIds"]:
                return project["projectId"]
        return None

    def register_session(self, project_id: str, session_id: str) -> bool:
        """Durably append one session; return False when already registered there."""
        if not is_canonical_session_id(session_id):
            raise CatalogConflictError("sessionId must be canonical UUIDv4 hex")
        owner = self.project_for_session(session_id)
        if owner is not None:
            if owner == project_id:
                return False
            raise CatalogConflictError(
                f"session {session_id} is already registered to project {owner}"
            )

        candidate = copy.deepcopy(self._snapshot)
        target = next(
            (
                project
                for project in candidate["projects"]
                if project["projectId"] == project_id
            ),
            None,
        )
        if target is None:
            raise CatalogConflictError(f"unknown projectId: {project_id}")
        target["sessionIds"].append(session_id)
        validated = _validate_snapshot(candidate)
        self._atomic_replace(validated)
        self._snapshot = validated
        return True

    @classmethod
    def rebuild_from_conversations(
        cls,
        persist_dir: str | Path,
        summaries: Iterable[ConversationSummary],
    ) -> "DesktopProjectCatalog":
        """Replace a missing or malformed index from healthy JSON summaries."""
        catalog = cls.__new__(cls)
        catalog.path = Path(persist_dir) / CATALOG_FILENAME
        grouped: dict[str, list[ConversationSummary]] = {}
        for summary in summaries:
            if summary.project_id is None:
                continue
            grouped.setdefault(summary.project_id, []).append(summary)

        project_ids = sorted(grouped)
        if DEFAULT_PROJECT_ID in project_ids:
            project_ids.remove(DEFAULT_PROJECT_ID)
        project_ids.insert(0, DEFAULT_PROJECT_ID)
        candidate = {
            "projects": [
                {
                    "projectId": project_id,
                    "name": (
                        DEFAULT_PROJECT_NAME
                        if project_id == DEFAULT_PROJECT_ID
                        else project_id
                    ),
                    "sessionIds": [
                        summary.conversation_id
                        for summary in sorted(
                            grouped.get(project_id, ()),
                            key=lambda item: (
                                item.created_at,
                                item.conversation_id,
                            ),
                        )
                    ],
                }
                for project_id in project_ids
            ]
        }
        validated = _validate_snapshot(candidate)
        catalog._atomic_replace(validated)
        catalog._snapshot = validated
        return catalog

    def reconcile_conversations(
        self,
        summaries: Iterable[ConversationSummary],
    ) -> bool:
        """Add or relocate healthy JSON sessions without removing missing entries."""
        candidate = copy.deepcopy(self._snapshot)
        additions: dict[str, list[ConversationSummary]] = {}
        changed = False
        for summary in summaries:
            project_id = summary.project_id
            if project_id is None:
                continue
            owner = self.project_for_session(summary.conversation_id)
            if owner == project_id:
                continue
            if owner is not None:
                owner_entry = next(
                    project
                    for project in candidate["projects"]
                    if project["projectId"] == owner
                )
                owner_entry["sessionIds"].remove(summary.conversation_id)
            additions.setdefault(project_id, []).append(summary)
            changed = True

        known_projects = {
            project["projectId"]: project for project in candidate["projects"]
        }
        for project_id in sorted(additions):
            project = known_projects.get(project_id)
            if project is None:
                project = {
                    "projectId": project_id,
                    "name": (
                        DEFAULT_PROJECT_NAME
                        if project_id == DEFAULT_PROJECT_ID
                        else project_id
                    ),
                    "sessionIds": [],
                }
                candidate["projects"].append(project)
                known_projects[project_id] = project
            project["sessionIds"].extend(
                summary.conversation_id
                for summary in sorted(
                    additions[project_id],
                    key=lambda item: (item.created_at, item.conversation_id),
                )
            )

        if not changed:
            return False
        validated = _validate_snapshot(candidate)
        self._atomic_replace(validated)
        self._snapshot = validated
        return True

    def _load_or_bootstrap(self) -> dict[str, list[dict[str, Any]]]:
        try:
            if self.path.exists():
                return self._read_existing()
            default = _validate_snapshot({
                "projects": [{
                    "projectId": DEFAULT_PROJECT_ID,
                    "name": DEFAULT_PROJECT_NAME,
                    "sessionIds": [],
                }]
            })
            return self._create_absent(default)
        except CatalogError:
            raise
        except OSError as exc:
            raise CatalogUnavailableError(f"catalog unavailable: {exc}") from exc

    def _read_existing(self) -> dict[str, list[dict[str, Any]]]:
        try:
            with self.path.open("rb") as handle:
                raw = handle.read(CATALOG_MAX_BYTES + 1)
            if len(raw) > CATALOG_MAX_BYTES:
                raise CatalogMalformedError(
                    f"catalog exceeds the {CATALOG_MAX_BYTES}-byte limit"
                )
        except CatalogError:
            raise
        except OSError as exc:
            raise CatalogUnavailableError(f"catalog unavailable: {exc}") from exc
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CatalogMalformedError("catalog is not valid UTF-8 JSON") from exc
        return _validate_snapshot(parsed)

    def _write_temp(self, snapshot: dict[str, Any]) -> Path:
        encoded = _encode_snapshot(snapshot)
        temp_path: Path | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, raw_path = tempfile.mkstemp(
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                dir=self.path.parent,
            )
            temp_path = Path(raw_path)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            return temp_path
        except OSError as exc:
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass
            raise CatalogUnavailableError(f"catalog write unavailable: {exc}") from exc

    def _create_absent(
        self,
        snapshot: dict[str, list[dict[str, Any]]],
    ) -> dict[str, list[dict[str, Any]]]:
        temp_path = self._write_temp(snapshot)
        try:
            try:
                os.link(temp_path, self.path)
            except FileExistsError:
                return self._read_existing()
            _fsync_directory(self.path.parent)
            return snapshot
        except CatalogError:
            raise
        except OSError as exc:
            raise CatalogUnavailableError(f"catalog write unavailable: {exc}") from exc
        finally:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass

    def _atomic_replace(self, snapshot: dict[str, Any]) -> None:
        temp_path = self._write_temp(snapshot)
        try:
            os.replace(temp_path, self.path)
            _fsync_directory(self.path.parent)
        except OSError as exc:
            raise CatalogUnavailableError(f"catalog write unavailable: {exc}") from exc
        finally:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
