"""Desktop research projects: RESEARCH.md metadata and conversation history roots.

A project's conversation list is the scan of its history directory; nothing
else records which conversations belong to it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from agent.conversations import ConversationError, ConversationRepository, ConversationSummary

# Written by desktop builds before the conversation list was derived from the
# history scan. Never read or written; an otherwise empty history directory
# that still contains it may be initialized.
LEGACY_CATALOG_FILENAME = "desktop-projects.json"


class ProjectError(RuntimeError):
    """Base class for explicit project setting and history failures."""


class ProjectUnavailableError(ProjectError):
    """Project settings or history could not be read or durably written."""


class ProjectMalformedError(ProjectError):
    """Existing project settings failed the strict schema."""


class ProjectConflictError(ProjectError):
    """A requested project operation conflicts with existing settings or ownership."""


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


_PROJECT_MARKER = "<!-- research-agent-project"
_PROJECT_MAX_BYTES = 1_048_576


def _project_root(root_path: str) -> Path:
    if not isinstance(root_path, str) or not root_path.startswith("/") or "\\\\" in root_path:
        raise ProjectMalformedError("rootPath must be an absolute Linux directory")
    if len(root_path.encode("utf-8")) > 8192:
        raise ProjectMalformedError("rootPath exceeds the path limit")
    try:
        root = Path(root_path).resolve(strict=True)
        if not root.is_dir():
            raise ProjectUnavailableError("rootPath must be a directory")
        return root
    except (OSError, RuntimeError) as exc:
        raise ProjectUnavailableError(f"project root is unavailable: {exc}") from exc


def _research_bytes(path: Path) -> bytes | None:
    try:
        with path.open("rb") as handle:
            raw = handle.read(_PROJECT_MAX_BYTES + 1)
    except FileNotFoundError:
        if path.is_symlink():
            raise ProjectUnavailableError("RESEARCH.md is an unavailable symbolic link")
        return None
    except OSError as exc:
        raise ProjectUnavailableError(f"RESEARCH.md is unavailable: {exc}") from exc
    if len(raw) > _PROJECT_MAX_BYTES:
        raise ProjectMalformedError("RESEARCH.md exceeds the 1 MiB input limit")
    try:
        raw.decode("utf-8")
    except UnicodeError as exc:
        raise ProjectMalformedError("RESEARCH.md must contain UTF-8 text") from exc
    return raw


def _metadata_and_rules(raw: bytes | None) -> tuple[dict[str, Any] | None, str]:
    text = raw.decode("utf-8") if raw is not None else ""
    span = _metadata_span(text)
    if span is None:
        return None, text
    start, end = span
    payload = text[start + len(_PROJECT_MARKER):end]
    metadata = _parse_metadata(payload)
    return metadata, text[:start] + text[end + 3:]


def _metadata_span(text: str) -> tuple[int, int] | None:
    """(marker start, "-->" start) of the single metadata block, or None."""
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
        return None
    if len(markers) != 1:
        raise ProjectMalformedError("RESEARCH.md must contain exactly one project metadata block")
    start = markers[0]
    end = text.find("-->", start)
    if end < 0:
        raise ProjectMalformedError("RESEARCH.md project metadata block is incomplete")
    return start, end


def _parse_metadata(payload: str) -> dict[str, Any]:
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ProjectMalformedError(f"duplicate project metadata key: {key}")
            result[key] = value
        return result

    try:
        metadata = json.loads(payload, object_pairs_hook=unique_keys)
    except (ValueError, TypeError) as exc:
        raise ProjectMalformedError("RESEARCH.md project metadata is not valid JSON") from exc
    if (
        not isinstance(metadata, dict)
        or not {"version", "historyDirectory"} <= set(metadata) <= _PROJECT_METADATA_KEYS
        or type(metadata["version"]) is not int
        or metadata["version"] != 1
        or not isinstance(metadata["historyDirectory"], str)
        or not metadata["historyDirectory"].strip()
    ):
        raise ProjectMalformedError("project metadata requires version 1 and a nonempty historyDirectory")
    if "bibliography" in metadata:
        _bibliography_relative_path(metadata["bibliography"])
    if "citationStyle" in metadata and (
        not isinstance(metadata["citationStyle"], str)
        or not metadata["citationStyle"].strip()
        or len(metadata["citationStyle"]) > 128
    ):
        raise ProjectMalformedError("citationStyle must be a nonempty style ID")
    return metadata


_PROJECT_METADATA_KEYS = frozenset({"version", "historyDirectory", "bibliography", "citationStyle"})
DEFAULT_BIBLIOGRAPHY = "references.json"


def _bibliography_relative_path(value: Any) -> PurePosixPath:
    """Validate the optional ``bibliography`` metadata value (shape only)."""
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.encode("utf-8")) > 4096
        or re.search(r"[\\$~\x00-\x1f\x7f]", value)
        or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value)
    ):
        raise ProjectMalformedError("bibliography must be a relative project path without URL or expansion syntax")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.suffix.casefold() != ".json":
        raise ProjectMalformedError("bibliography must be a .json path inside the project root")
    return path


def project_citation_settings(root_path: str | Path) -> dict[str, Any]:
    """Return the project bibliography path and citation style from RESEARCH.md.

    ``bibliography`` defaults to ``references.json`` in the project root; the
    resolved path must stay inside the root (symbolic links included).
    """
    root = Path(root_path).resolve()
    metadata, _rules = _metadata_and_rules(_research_bytes(root / "RESEARCH.md"))
    metadata = metadata or {}
    relative = _bibliography_relative_path(metadata.get("bibliography", DEFAULT_BIBLIOGRAPHY))
    try:
        resolved = (root / relative).resolve()
    except (OSError, RuntimeError) as exc:
        raise ProjectUnavailableError(f"bibliography is unavailable: {exc}") from exc
    if not resolved.is_relative_to(root):
        raise ProjectMalformedError("bibliography must stay inside the project root")
    return {"bibliographyPath": resolved, "citationStyle": metadata.get("citationStyle")}


_EDITABLE_METADATA_KEYS = frozenset({"citationStyle"})


def update_project_metadata(root_path: str | Path, updates: dict[str, Any]) -> str:
    """Rewrite only the metadata block's JSON object in RESEARCH.md.

    Text outside the block (the project rules) stays byte for byte, and so do
    the other keys and their order. The file is re-read before the atomic
    replace; a concurrent change raises ProjectConflictError and nothing is
    written. Returns the new researchFingerprint.
    """
    if not updates or set(updates) - _EDITABLE_METADATA_KEYS:
        raise ProjectMalformedError("only citationStyle can be changed this way")
    root = Path(root_path).resolve()
    path = root / "RESEARCH.md"
    if path.is_symlink():
        raise ProjectConflictError("RESEARCH.md is a symbolic link; edit its metadata explicitly")
    raw = _research_bytes(path)
    if raw is None:
        raise ProjectMalformedError("RESEARCH.md has no project metadata; initialize the project first")
    fingerprint = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8")
    span = _metadata_span(text)
    if span is None:
        raise ProjectMalformedError("RESEARCH.md has no project metadata; initialize the project first")
    start, end = span
    payload_start = start + len(_PROJECT_MARKER)
    payload = text[payload_start:end]
    metadata = _parse_metadata(payload)
    metadata.update(updates)
    left = payload.index("{")
    right = payload.rindex("}") + 1
    pretty = "\n" in payload[left:right]
    rendered = (
        json.dumps(metadata, ensure_ascii=False, indent=2)
        if pretty
        else json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
    )
    candidate_text = text[:payload_start] + payload[:left] + rendered + payload[right:] + text[end:]
    candidate = candidate_text.encode("utf-8")
    if len(candidate) > _PROJECT_MAX_BYTES:
        raise ProjectMalformedError("metadata would exceed the 1 MiB input limit")
    checked, rules_after = _metadata_and_rules(candidate)
    _metadata, rules_before = _metadata_and_rules(raw)
    if checked != metadata or rules_after != rules_before:
        raise ProjectMalformedError("metadata rewrite would change text outside the metadata block")
    temporary: Path | None = None
    try:
        mode = path.stat().st_mode & 0o7777
        descriptor, name = tempfile.mkstemp(prefix=".RESEARCH.md.", suffix=".tmp", dir=root)
        temporary = Path(name)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(candidate)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        current = _research_bytes(path)
        if current is None or hashlib.sha256(current).hexdigest() != fingerprint:
            raise ProjectConflictError("RESEARCH.md changed while saving the citation style; nothing was written")
        os.replace(temporary, path)
        temporary = None
        _fsync_directory(root)
    except OSError as exc:
        raise ProjectUnavailableError(f"RESEARCH.md could not be saved: {exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return hashlib.sha256(candidate).hexdigest()


def _history_path(value: str, root: Path) -> Path:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.encode("utf-8")) > 8192
        or re.search(r"[\\\\$~\x00-\x1f\x7f]", value)
        or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value)
    ):
        raise ProjectMalformedError("historyDirectory must be an explicit Linux path without URL or expansion syntax")
    try:
        path = Path(value)
        return (path if path.is_absolute() else root / path).resolve()
    except (OSError, RuntimeError) as exc:
        raise ProjectUnavailableError(f"historyDirectory is unavailable: {exc}") from exc


def inspect_project(
    root_path: str,
    persist_dir: str | Path,
    *,
    history_directory: str | None = None,
) -> dict[str, Any]:
    """Read project settings without creating history or metadata."""
    root = _project_root(root_path)
    project_id = "p-" + hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:32]
    raw = _research_bytes(root / "RESEARCH.md")
    metadata, rules = _metadata_and_rules(raw)
    proposed = history_directory if history_directory is not None else str(
        Path(persist_dir).resolve() / "projects" / project_id
    )
    history = _history_path(metadata["historyDirectory"] if metadata else proposed, root)
    if metadata is not None and history_directory is not None and _history_path(history_directory, root) != history:
        raise ProjectConflictError("RESEARCH.md already specifies another historyDirectory; edit it explicitly before reopening")
    status = "needs_configuration" if metadata is None else "ready"
    try:
        if history.exists() and not history.is_dir():
            raise ProjectUnavailableError("historyDirectory must be a directory")
        conversations = history / "conversations"
        if conversations.exists() and not conversations.is_dir():
            raise ProjectUnavailableError("conversations must be a directory")
        if metadata is not None and (not history.is_dir() or not conversations.is_dir()):
            status = "needs_initialization"
    except OSError as exc:
        raise ProjectUnavailableError(f"historyDirectory is unavailable: {exc}") from exc
    return {
        "rootPath": str(root),
        "projectId": project_id,
        "historyDirectory": str(history),
        "rulesText": rules,
        "rulesFingerprint": hashlib.sha256(rules.encode("utf-8")).hexdigest(),
        "researchFingerprint": hashlib.sha256(raw).hexdigest() if raw is not None else None,
        "status": status,
    }


def project_conversations(project_id: str, repository: ConversationRepository) -> list[ConversationSummary]:
    """The project's conversation list: one scan of its history, oldest first.

    Fails closed when the scan reports any unreadable or unsupported
    conversation, or when any conversation belongs to another project.
    """
    try:
        scan = repository.scan()
    except ConversationError as exc:
        raise ProjectUnavailableError(f"project history cannot be scanned: {exc}") from exc
    if scan.issues:
        raise ProjectUnavailableError("project history scan is incomplete or contains unreadable/malformed conversations")
    if any(summary.project_id != project_id for summary in scan.summaries):
        raise ProjectConflictError("history contains conversations with different or unknown project ownership; explicit mapping is required")
    return sorted(scan.summaries, key=lambda item: (item.created_at, item.conversation_id))


def open_project_history(project_id: str, history_directory: str | Path) -> ConversationRepository:
    """Open one verified history root; never guess or repair ownership."""
    history = Path(history_directory)
    if not history.is_dir() or not (history / "conversations").is_dir():
        raise ProjectUnavailableError("project history is missing; explicitly initialize new history or correct RESEARCH.md")
    repository = ConversationRepository(history)
    project_conversations(project_id, repository)
    return repository


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
        open_project_history(inspected["projectId"], inspected["historyDirectory"])
        return inspected
    if inspected["researchFingerprint"] != expected_fingerprint:
        raise ProjectConflictError("RESEARCH.md changed after the preview; inspect the project again")
    if path.is_symlink():
        raise ProjectConflictError("RESEARCH.md is a symbolic link; configure its metadata explicitly")
    raw = _research_bytes(path)
    if (hashlib.sha256(raw).hexdigest() if raw is not None else None) != expected_fingerprint:
        raise ProjectConflictError("RESEARCH.md changed after the preview; inspect the project again")
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
            raise ProjectMalformedError("metadata would exceed the 1 MiB input limit")
        candidate_metadata, _candidate_rules = _metadata_and_rules(candidate)
        if candidate_metadata is None:
            raise ProjectMalformedError("close the unfinished Markdown code fence before appending project metadata")
    try:
        if history.exists():
            names = {entry.name for entry in history.iterdir()}
            if names - {"conversations", LEGACY_CATALOG_FILENAME}:
                raise ProjectConflictError("history initialization requires an empty directory or the same empty project initialization")
        conversations = history / "conversations"
        if conversations.exists() and any(conversations.iterdir()):
            raise ProjectConflictError("history initialization cannot overwrite existing conversations")
        conversations.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ProjectUnavailableError(f"cannot initialize empty history at {history}: {exc}") from exc
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
                raise ProjectConflictError(f"RESEARCH.md changed; empty history remains at {history}")
            if raw is None:
                try:
                    os.link(temporary, path)
                except FileExistsError as exc:
                    raise ProjectConflictError(f"RESEARCH.md appeared; empty history remains at {history}") from exc
            else:
                os.replace(temporary, path)
            _fsync_directory(root)
        except OSError as exc:
            raise ProjectUnavailableError(f"RESEARCH.md could not be saved; empty history remains at {history}: {exc}") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    result = inspect_project(root_path, persist_dir)
    if result["historyDirectory"] != str(history) or result["status"] != "ready":
        raise ProjectConflictError(f"project settings changed during initialization; history remains at {history}")
    open_project_history(result["projectId"], history)
    return result
