"""Small durable project-to-conversation catalog for the desktop client."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from agent.conversations import ConversationError, ConversationRepository, ConversationSummary

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

    def unregister_session(self, project_id: str, session_id: str) -> bool:
        """Durably remove one session ID while preserving its project entry."""
        if not is_canonical_session_id(session_id):
            raise CatalogConflictError("sessionId must be canonical UUIDv4 hex")
        owner = self.project_for_session(session_id)
        if owner is not None and owner != project_id:
            raise CatalogConflictError(
                f"session {session_id} is registered to project {owner}"
            )
        candidate = copy.deepcopy(self._snapshot)
        target = next(
            (project for project in candidate["projects"] if project["projectId"] == project_id),
            None,
        )
        if target is None:
            raise CatalogConflictError(f"unknown projectId: {project_id}")
        if owner is None:
            return False
        target["sessionIds"].remove(session_id)
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


_PROJECT_MARKER = "<!-- research-agent-project"
_PROJECT_MAX_BYTES = 1_048_576


def _project_root(root_path: str) -> Path:
    if not isinstance(root_path, str) or not root_path.startswith("/") or "\\\\" in root_path:
        raise CatalogMalformedError("rootPath must be an absolute Linux directory")
    if len(root_path.encode("utf-8")) > 8192:
        raise CatalogMalformedError("rootPath exceeds the path limit")
    try:
        root = Path(root_path).resolve(strict=True)
        if not root.is_dir():
            raise CatalogUnavailableError("rootPath must be a directory")
        return root
    except (OSError, RuntimeError) as exc:
        raise CatalogUnavailableError(f"project root is unavailable: {exc}") from exc


def _research_bytes(path: Path) -> bytes | None:
    try:
        with path.open("rb") as handle:
            raw = handle.read(_PROJECT_MAX_BYTES + 1)
    except FileNotFoundError:
        if path.is_symlink():
            raise CatalogUnavailableError("RESEARCH.md is an unavailable symbolic link")
        return None
    except OSError as exc:
        raise CatalogUnavailableError(f"RESEARCH.md is unavailable: {exc}") from exc
    if len(raw) > _PROJECT_MAX_BYTES:
        raise CatalogMalformedError("RESEARCH.md exceeds the 1 MiB input limit")
    try:
        raw.decode("utf-8")
    except UnicodeError as exc:
        raise CatalogMalformedError("RESEARCH.md must contain UTF-8 text") from exc
    return raw


def _metadata_and_rules(raw: bytes | None) -> tuple[dict[str, Any] | None, str]:
    text = raw.decode("utf-8") if raw is not None else ""
    visible = []
    offset = 0
    fence: tuple[str, int] | None = None
    for line in text.splitlines(keepends=True):
        match = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence is not None:
            if match and match[1][0] == fence[0] and len(match[1]) >= fence[1] and not line[match.end():].strip():
                fence = None
        elif match:
            fence = (match[1][0], len(match[1]))
        else:
            visible.append((offset, line))
        offset += len(line)
    markers = [
        position + match.start()
        for position, line in visible
        for match in re.finditer(re.escape(_PROJECT_MARKER), line)
    ]
    if not markers:
        return None, text
    if len(markers) != 1:
        raise CatalogMalformedError("RESEARCH.md must contain exactly one project metadata block")
    start = markers[0]
    end = text.find("-->", start)
    if end < 0:
        raise CatalogMalformedError("RESEARCH.md project metadata block is incomplete")
    payload = text[start + len(_PROJECT_MARKER):end]

    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise CatalogMalformedError(f"duplicate project metadata key: {key}")
            result[key] = value
        return result

    try:
        metadata = json.loads(payload, object_pairs_hook=unique_keys)
    except (ValueError, TypeError) as exc:
        raise CatalogMalformedError("RESEARCH.md project metadata is not valid JSON") from exc
    if (
        not isinstance(metadata, dict)
        or set(metadata) != {"version", "historyDirectory"}
        or type(metadata["version"]) is not int
        or metadata["version"] != 1
        or not isinstance(metadata["historyDirectory"], str)
        or not metadata["historyDirectory"].strip()
    ):
        raise CatalogMalformedError("project metadata requires version 1 and a nonempty historyDirectory")
    return metadata, text[:start] + text[end + 3:]


def _history_path(value: str, root: Path) -> Path:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.encode("utf-8")) > 8192
        or re.search(r"[\\\\$~\x00-\x1f\x7f]", value)
        or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value)
    ):
        raise CatalogMalformedError("historyDirectory must be an explicit Linux path without URL or expansion syntax")
    try:
        path = Path(value)
        return (path if path.is_absolute() else root / path).resolve()
    except (OSError, RuntimeError) as exc:
        raise CatalogUnavailableError(f"historyDirectory is unavailable: {exc}") from exc


def inspect_project(
    root_path: str,
    persist_dir: str | Path,
    *,
    history_directory: str | None = None,
) -> dict[str, Any]:
    """Read project settings without creating a catalog, history, or metadata."""
    root = _project_root(root_path)
    project_id = "p-" + hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:32]
    raw = _research_bytes(root / "RESEARCH.md")
    metadata, rules = _metadata_and_rules(raw)
    proposed = history_directory if history_directory is not None else str(
        Path(persist_dir).resolve() / "projects" / project_id
    )
    history = _history_path(metadata["historyDirectory"] if metadata else proposed, root)
    if metadata is not None and history_directory is not None and _history_path(history_directory, root) != history:
        raise CatalogConflictError("RESEARCH.md already specifies another historyDirectory; edit it explicitly before reopening")
    status = "needs_configuration" if metadata is None else "ready"
    try:
        if history.exists() and not history.is_dir():
            raise CatalogUnavailableError("historyDirectory must be a directory")
        conversations = history / "conversations"
        if conversations.exists() and not conversations.is_dir():
            raise CatalogUnavailableError("conversations must be a directory")
        if metadata is not None and (not history.is_dir() or not conversations.is_dir()):
            status = "needs_initialization"
    except OSError as exc:
        raise CatalogUnavailableError(f"historyDirectory is unavailable: {exc}") from exc
    return {
        "rootPath": str(root),
        "projectId": project_id,
        "historyDirectory": str(history),
        "rulesText": rules,
        "rulesFingerprint": hashlib.sha256(rules.encode("utf-8")).hexdigest(),
        "researchFingerprint": hashlib.sha256(raw).hexdigest() if raw is not None else None,
        "status": status,
    }


def _scoped_catalog(history: Path, project_id: str, project_name: str) -> DesktopProjectCatalog:
    catalog = DesktopProjectCatalog.__new__(DesktopProjectCatalog)
    catalog.path = history / CATALOG_FILENAME
    catalog._snapshot = _validate_snapshot({
        "projects": [{"projectId": project_id, "name": project_name, "sessionIds": []}],
    })
    return catalog


def _check_catalog_owner(snapshot: dict[str, Any], project_id: str) -> None:
    projects = snapshot["projects"]
    if len(projects) != 1 or projects[0]["projectId"] != project_id:
        raise CatalogConflictError("history catalog belongs to another or an unknown project; explicit mapping is required")


def load_project_catalog(
    project_id: str,
    project_name: str,
    history_directory: str | Path,
) -> tuple[DesktopProjectCatalog, ConversationRepository]:
    """Open only one verified history root; never guess or repair ownership."""
    history = Path(history_directory)
    if not history.is_dir() or not (history / "conversations").is_dir():
        raise CatalogUnavailableError("project history is missing; explicitly initialize new history or correct RESEARCH.md")
    repository = ConversationRepository(history)
    try:
        scan = repository.scan()
    except ConversationError as exc:
        raise CatalogUnavailableError(f"project history cannot be scanned: {exc}") from exc
    if scan.issues:
        raise CatalogUnavailableError("project history scan is incomplete or contains unreadable/malformed conversations")
    if any(summary.project_id != project_id for summary in scan.summaries):
        raise CatalogConflictError("history contains conversations with different or unknown project ownership; explicit mapping is required")
    catalog = _scoped_catalog(history, project_id, project_name)
    repair = False
    if catalog.path.exists():
        try:
            catalog._snapshot = catalog._read_existing()
        except CatalogMalformedError:
            if not scan.summaries:
                raise
            repair = True
    else:
        repair = True
    if not repair:
        _check_catalog_owner(catalog.snapshot(), project_id)
        actual_ids = {summary.conversation_id for summary in scan.summaries}
        if any(session_id not in actual_ids for session_id in catalog._snapshot["projects"][0]["sessionIds"]):
            raise CatalogUnavailableError("catalog references missing conversations; existing history is preserved")
        catalog.reconcile_conversations(scan.summaries)
    else:
        catalog._snapshot["projects"][0]["sessionIds"] = [
            summary.conversation_id
            for summary in sorted(scan.summaries, key=lambda item: (item.created_at, item.conversation_id))
        ]
        if catalog.path.exists():
            catalog._atomic_replace(catalog._snapshot)
        else:
            catalog._snapshot = catalog._create_absent(catalog._snapshot)
            _check_catalog_owner(catalog._snapshot, project_id)
    return catalog, repository


def initialize_project(
    root_path: str,
    persist_dir: str | Path,
    *,
    history_directory: str,
    expected_fingerprint: str | None,
) -> dict[str, Any]:
    """Explicitly initialize empty history and append metadata without replacing prose."""
    inspected = inspect_project(root_path, persist_dir, history_directory=history_directory)
    root = Path(inspected["rootPath"])
    path = root / "RESEARCH.md"
    if inspected["status"] == "ready":
        load_project_catalog(inspected["projectId"], root.name, inspected["historyDirectory"])
        return inspected
    if inspected["researchFingerprint"] != expected_fingerprint:
        raise CatalogConflictError("RESEARCH.md changed after the preview; inspect the project again")
    if path.is_symlink():
        raise CatalogConflictError("RESEARCH.md is a symbolic link; configure its metadata explicitly")
    raw = _research_bytes(path)
    if (hashlib.sha256(raw).hexdigest() if raw is not None else None) != expected_fingerprint:
        raise CatalogConflictError("RESEARCH.md changed after the preview; inspect the project again")
    metadata, _rules = _metadata_and_rules(raw)
    history = Path(inspected["historyDirectory"])
    candidate: bytes | None = None
    if metadata is None:
        original = raw if raw is not None else b"# Research project\n\n## Description\n\n## Agent rules\n"
        block = (
            "\n\n" + _PROJECT_MARKER + "\n"
            + json.dumps({"version": 1, "historyDirectory": str(history)}, ensure_ascii=False, separators=(",", ":"))
            + "\n-->\n"
        ).encode("utf-8")
        candidate = original + block
        if len(candidate) > _PROJECT_MAX_BYTES:
            raise CatalogMalformedError("metadata would exceed the 1 MiB input limit")
        candidate_metadata, _candidate_rules = _metadata_and_rules(candidate)
        if candidate_metadata is None:
            raise CatalogMalformedError("close the unfinished Markdown code fence before appending project metadata")
    catalog = _scoped_catalog(history, inspected["projectId"], root.name)
    try:
        if history.exists():
            names = {entry.name for entry in history.iterdir()}
            if names - {"conversations", CATALOG_FILENAME}:
                raise CatalogConflictError("history initialization requires an empty directory or the same empty project initialization")
        conversations = history / "conversations"
        if conversations.exists() and any(conversations.iterdir()):
            raise CatalogConflictError("history initialization cannot overwrite existing conversations")
        if catalog.path.exists():
            existing = catalog._read_existing()
            _check_catalog_owner(existing, inspected["projectId"])
            if existing["projects"][0]["sessionIds"]:
                raise CatalogConflictError("history initialization cannot overwrite an existing catalog")
        conversations.mkdir(parents=True, exist_ok=True)
        catalog._snapshot = catalog._create_absent(catalog._snapshot)
        _check_catalog_owner(catalog._snapshot, inspected["projectId"])
        if catalog._snapshot["projects"][0]["sessionIds"]:
            raise CatalogConflictError("history changed during initialization")
    except OSError as exc:
        raise CatalogUnavailableError(f"cannot initialize empty history at {history}: {exc}") from exc
    if candidate is not None:
        temporary: Path | None = None
        try:
            descriptor, name = tempfile.mkstemp(prefix=".RESEARCH.md.", suffix=".tmp", dir=root)
            temporary = Path(name)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(candidate)
                handle.flush()
                os.fsync(handle.fileno())
            current = _research_bytes(path)
            if (hashlib.sha256(current).hexdigest() if current is not None else None) != expected_fingerprint:
                raise CatalogConflictError(f"RESEARCH.md changed; empty history remains at {history}")
            if raw is None:
                try:
                    os.link(temporary, path)
                except FileExistsError as exc:
                    raise CatalogConflictError(f"RESEARCH.md appeared; empty history remains at {history}") from exc
            else:
                os.replace(temporary, path)
            _fsync_directory(root)
        except OSError as exc:
            raise CatalogUnavailableError(f"RESEARCH.md could not be saved; empty history remains at {history}: {exc}") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    result = inspect_project(root_path, persist_dir)
    if result["historyDirectory"] != str(history) or result["status"] != "ready":
        raise CatalogConflictError(f"project settings changed during initialization; history remains at {history}")
    load_project_catalog(result["projectId"], root.name, history)
    return result
