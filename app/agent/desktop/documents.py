"""Local document snapshots and version-checked writes for the desktop editor."""

from __future__ import annotations

import copy
import hashlib
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any

MAX_TEXT_BYTES = 1_048_576
MAX_PATH_BYTES = 8192
MAX_SAFE_INTEGER = 9_007_199_254_740_991
_SUPPORTED_SUFFIXES = {".md", ".markdown", ".tex"}
_FINGERPRINT = re.compile(r"[0-9a-f]{64}\Z")
_LINE_REFERENCE = re.compile(
    r"第\s*(\d+)\s*(?:[-–—～~至到]\s*(\d+)\s*)?行"
    r"|\blines?\s*(\d+)\s*(?:[-–—:~]\s*(\d+))?",
    re.IGNORECASE,
)


class DocumentError(ValueError):
    """A document path, snapshot, or range cannot be used safely."""


def _text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise DocumentError(f"{name} must be a string")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise DocumentError(f"{name} must be valid UTF-8 text") from exc
    if size > MAX_TEXT_BYTES:
        raise DocumentError(f"{name} exceeds {MAX_TEXT_BYTES} UTF-8 bytes")
    return value


def utf16_to_index(text: str, offset: int) -> int:
    """Translate a UTF-16 offset without allowing a split surrogate pair."""
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise DocumentError("document range offsets must be non-negative integers")
    position = 0
    for index, char in enumerate(text):
        if position == offset:
            return index
        position += 2 if ord(char) > 0xFFFF else 1
        if position > offset:
            raise DocumentError("document range splits a UTF-16 surrogate pair")
    if position == offset:
        return len(text)
    raise DocumentError("document range is outside sourceText")


def utf16_length(text: str) -> int:
    """Return the editor's UTF-16 code-unit length."""
    return len(text.encode("utf-16-le")) // 2


def selected_text(snapshot: dict[str, Any]) -> str:
    """Read the half-open selected range from an already validated snapshot."""
    source = snapshot["sourceText"]
    start = snapshot.get("rangeStartUtf16", 0)
    end = snapshot.get("rangeEndUtf16", utf16_length(source))
    return source[utf16_to_index(source, start):utf16_to_index(source, end)]


def resolve_line_range(source: str, start_line: int, end_line: int) -> tuple[int, int]:
    """Resolve 1-based source lines, counting CRLF as a single line break."""
    starts = [0, *(match.end() for match in re.finditer(r"\r\n|\r|\n", source))]
    if start_line < 1 or end_line < start_line or end_line > len(starts):
        raise DocumentError("requested source lines are outside the document")
    start = starts[start_line - 1]
    end = starts[end_line] if end_line < len(starts) else len(source)
    return utf16_length(source[:start]), utf16_length(source[:end])


class DocumentWorkspace:
    """One in-memory workspace; completed writes are never replayed automatically."""

    def __init__(self) -> None:
        self.root: Path | None = None
        self._lock = threading.RLock()
        self._candidates: dict[tuple[str, str], dict[str, Any]] = {}
        self._saved: dict[tuple[str, str], dict[str, Any]] = {}
        self._undos: dict[str, dict[str, Any]] = {}

    def select_root(self, root_path: str) -> dict[str, str]:
        """Select an existing Linux directory without changing durable catalog data."""
        if not isinstance(root_path, str) or not Path(root_path).is_absolute():
            raise DocumentError("rootPath must be an absolute Linux directory")
        if len(root_path.encode("utf-8")) > MAX_PATH_BYTES:
            raise DocumentError("rootPath exceeds the path limit")
        try:
            root = Path(root_path).resolve(strict=True)
        except OSError as exc:
            raise DocumentError(f"workspace root is unavailable: {exc}") from exc
        if not root.is_dir():
            raise DocumentError("rootPath must be a directory")
        with self._lock:
            if root != self.root:
                self._candidates.clear()
                self._saved.clear()
                self._undos.clear()
            self.root = root
        return {"rootPath": str(root)}

    def _path(self, value: object) -> Path:
        if self.root is None:
            raise DocumentError("select a workspace root before opening a document")
        if not isinstance(value, str) or not value or len(value.encode("utf-8")) > MAX_PATH_BYTES:
            raise DocumentError("path must contain 1-8192 UTF-8 bytes")
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        try:
            path = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise DocumentError(f"document is unavailable: {exc}") from exc
        if not path.is_relative_to(self.root):
            raise DocumentError("document path is outside the selected workspace")
        if path.suffix.lower() not in _SUPPORTED_SUFFIXES or not path.is_file():
            raise DocumentError("open an existing UTF-8 .md, .markdown, or .tex document")
        return path

    @staticmethod
    def _disk(path: Path) -> tuple[str, str]:
        try:
            if path.stat().st_size > MAX_TEXT_BYTES:
                raise DocumentError("document exceeds the text byte limit")
            raw = path.read_bytes()
            if len(raw) > MAX_TEXT_BYTES:
                raise DocumentError("document exceeds the text byte limit")
            text = raw.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise DocumentError(f"cannot read UTF-8 document: {exc}") from exc
        return text, hashlib.sha256(raw).hexdigest()

    def open(self, path: str) -> dict[str, Any]:
        """Read bytes directly so original CRLF and trailing newlines survive."""
        with self._lock:
            resolved = self._path(path)
            source, fingerprint = self._disk(resolved)
            return {
                "rootPath": str(self.root), "path": str(resolved),
                "editorRevision": 0, "sourceText": source,
                "diskFingerprint": fingerprint,
            }

    def validate_snapshot(self, snapshot: object, *, require_available: bool = True) -> dict[str, Any]:
        """Validate editor identity and coordinates without assuming it is saved."""
        if not isinstance(snapshot, dict):
            raise DocumentError("documentContext must be an object")
        required = {"rootPath", "path", "editorRevision", "sourceText", "diskFingerprint"}
        optional = {"rangeStartUtf16", "rangeEndUtf16"}
        if not required.issubset(snapshot) or set(snapshot) - required - optional:
            raise DocumentError("documentContext has missing or unexpected fields")
        if snapshot["rootPath"] != str(self.root):
            raise DocumentError("documentContext belongs to another workspace")
        if require_available:
            path = self._path(snapshot["path"])
        else:
            value = snapshot["path"]
            if not isinstance(value, str) or not value or len(value.encode("utf-8")) > MAX_PATH_BYTES:
                raise DocumentError("path must contain 1-8192 UTF-8 bytes")
            path = Path(value).resolve(strict=False)
            if self.root is None or not path.is_relative_to(self.root) or path.suffix.lower() not in _SUPPORTED_SUFFIXES:
                raise DocumentError("document snapshot is outside the selected workspace or has an unsupported type")
        revision = snapshot["editorRevision"]
        if isinstance(revision, bool) or not isinstance(revision, int) or not 0 <= revision <= MAX_SAFE_INTEGER:
            raise DocumentError("editorRevision must be a non-negative safe integer")
        source = _text(snapshot["sourceText"], "sourceText")
        fingerprint = snapshot["diskFingerprint"]
        if not isinstance(fingerprint, str) or _FINGERPRINT.fullmatch(fingerprint) is None:
            raise DocumentError("diskFingerprint must be a SHA-256 fingerprint")
        if ("rangeStartUtf16" in snapshot) != ("rangeEndUtf16" in snapshot):
            raise DocumentError("both document range offsets are required")
        if "rangeStartUtf16" in snapshot:
            start, end = snapshot["rangeStartUtf16"], snapshot["rangeEndUtf16"]
            utf16_to_index(source, start)
            utf16_to_index(source, end)
            if end < start:
                raise DocumentError("document range end precedes its start")
        return {**snapshot, "path": str(path)}

    def resolve_range(self, snapshot: dict[str, Any], prompt: str = "", *, require_available: bool = True) -> dict[str, Any]:
        """Use explicit selection, or one unambiguous line reference in this snapshot."""
        validated = self.validate_snapshot(snapshot, require_available=require_available)
        if "rangeStartUtf16" in validated:
            return validated
        matches = list(_LINE_REFERENCE.finditer(prompt))
        if len(matches) > 1:
            raise DocumentError("multiple source line references require an explicit selection")
        if matches:
            match = matches[0]
            if re.match(r"\s*(?:[-–—~]\s*(?:\d|[A-Za-z])|[.:,、&]\s*\d|(?:至|到|(?:and|or|to|through)\b)\s*\d)", prompt[match.end():], re.IGNORECASE):
                raise DocumentError("source line range is incomplete or non-contiguous")
            first = int(match[1] or match[3])
            last = int(match[2] or match[4] or first)
            start, end = resolve_line_range(validated["sourceText"], first, last)
        else:
            if re.search(r"第[^\n]{0,30}行|\blines?\b", prompt, re.IGNORECASE):
                raise DocumentError("source line reference is ambiguous")
            start, end = 0, utf16_length(validated["sourceText"])
        return {**validated, "rangeStartUtf16": start, "rangeEndUtf16": end}

    def prepare(
        self, snapshot: dict[str, Any], replacement_text: str, *, turn_id: str, call_id: str,
    ) -> dict[str, Any]:
        """Bind a candidate to the captured source and its original exact range."""
        base = self.resolve_range(snapshot)
        replacement = _text(replacement_text, "replacementText")
        if not turn_id or not call_id:
            raise DocumentError("turnId and callId are required")
        key = (turn_id, call_id)
        with self._lock:
            source = base["sourceText"]
            start, end = base["rangeStartUtf16"], base["rangeEndUtf16"]
            left, right = utf16_to_index(source, start), utf16_to_index(source, end)
            newline = re.search(r"\r\n|\r|\n", source[left:right]) or re.search(r"\r\n|\r|\n", source)
            if newline is not None:
                replacement = re.sub(r"\r\n|\r|\n", lambda _: newline[0], replacement)
            previous = self._candidates.get(key)
            if previous is not None:
                if previous["documentContext"] != base or previous["replacementText"] != replacement:
                    raise DocumentError("the document operation identity already has another candidate")
                return copy.deepcopy(previous)
            candidate = {
                "turnId": turn_id, "callId": call_id, "documentContext": base,
                "replacementText": replacement, "candidateText": source[:left] + replacement + source[right:],
                "path": base["path"], "rangeStartUtf16": start, "rangeEndUtf16": end,
            }
            _text(candidate["candidateText"], "candidateText")
            self._candidates[key] = candidate
            return copy.deepcopy(candidate)

    @staticmethod
    def _same_editor(left: dict[str, Any], right: dict[str, Any]) -> bool:
        return all(left[key] == right[key] for key in ("rootPath", "path", "editorRevision", "sourceText"))

    @staticmethod
    def _write(path: Path, text: str) -> None:
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as stream:
                temporary = stream.name
                os.chmod(temporary, path.stat().st_mode & 0o777)
                stream.write(text.encode("utf-8"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            temporary = None
        finally:
            if temporary is not None:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass

    def _result(
        self, candidate: dict[str, Any], current: dict[str, Any], expected: dict[str, Any],
    ) -> dict[str, Any]:
        path = self._path(candidate["path"])
        result = {"path": str(path), "rangeStartUtf16": candidate["rangeStartUtf16"], "rangeEndUtf16": candidate["rangeEndUtf16"]}
        try:
            disk_text, fingerprint = self._disk(path)
        except DocumentError as exc:
            return {**result, "status": "failed", "candidateText": candidate["candidateText"], "issue": str(exc)}
        if not self._same_editor(current, expected) or fingerprint != expected["diskFingerprint"]:
            return {
                **result, "status": "conflict", "candidateText": candidate["candidateText"],
                "currentDiskText": disk_text, "diskFingerprint": fingerprint,
                "expectedSnapshot": {**current, "diskFingerprint": fingerprint},
                "issue": "The editor or disk changed; choose which version to keep.",
            }
        if current["editorRevision"] == MAX_SAFE_INTEGER and candidate["candidateText"] != current["sourceText"]:
            return {**result, "status": "failed", "candidateText": candidate["candidateText"], "issue": "editorRevision cannot advance beyond the safe integer limit"}
        try:
            self._write(path, candidate["candidateText"])
        except OSError as exc:
            return {**result, "status": "failed", "candidateText": candidate["candidateText"], "currentDiskText": disk_text, "issue": str(exc)}
        saved_fingerprint = hashlib.sha256(candidate["candidateText"].encode("utf-8")).hexdigest()
        revision = current["editorRevision"] + (candidate["candidateText"] != current["sourceText"])
        saved_end = candidate["rangeStartUtf16"] + utf16_length(candidate.get("replacementText", candidate["candidateText"]))
        return {
            **result, "rangeEndUtf16": saved_end,
            "status": "saved", "rootPath": current["rootPath"],
            "sourceText": candidate["candidateText"], "editorRevision": revision,
            "diskFingerprint": saved_fingerprint, "savedFingerprint": saved_fingerprint,
        }

    def _duplicate_result(
        self, result: dict[str, Any], current: dict[str, Any], before: dict[str, Any],
    ) -> dict[str, Any]:
        path = self._path(result["path"])
        try:
            disk_text, fingerprint = self._disk(path)
        except DocumentError as exc:
            return {"path": str(path), "status": "failed", "candidateText": result["sourceText"], "issue": str(exc)}
        if (self._same_editor(current, result) or self._same_editor(current, before)) and fingerprint == result["savedFingerprint"]:
            return copy.deepcopy(result)
        return {
            "path": str(path), "status": "conflict", "candidateText": result["sourceText"],
            "rangeStartUtf16": result["rangeStartUtf16"], "rangeEndUtf16": result["rangeEndUtf16"],
            "currentDiskText": disk_text, "diskFingerprint": fingerprint,
            "expectedSnapshot": {**current, "diskFingerprint": fingerprint},
            "issue": "This operation was already saved and a later edit exists; it was not replayed.",
        }

    def apply(
        self, candidate: dict[str, Any], current_snapshot: dict[str, Any], *,
        resolution: str | None = None, expected_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Apply only the prepared candidate, checking again after explicit conflict choice."""
        with self._lock:
            key = (candidate.get("turnId"), candidate.get("callId"))
            known = self._candidates.get(key)
            if known is None:
                raise DocumentError("unknown document operation; do not replay after restart")
            current = self.validate_snapshot(current_snapshot)
            if current["path"] != known["path"]:
                raise DocumentError("current editor belongs to another document")
            if key in self._saved:
                return self._duplicate_result(self._saved[key]["result"], current, self._saved[key]["before"])
            if resolution in {"current", "cancel"}:
                return {"path": known["path"], "status": "cancelled", "candidateText": known["candidateText"]}
            if resolution not in {None, "candidate"}:
                raise DocumentError("unknown conflict resolution")
            expected = known["documentContext"]
            if resolution == "candidate":
                if expected_snapshot is None:
                    raise DocumentError("adopting a candidate requires the versions shown for the conflict")
                expected = self.validate_snapshot(expected_snapshot)
                if expected["path"] != known["path"]:
                    raise DocumentError("conflict snapshot belongs to another document")
            result = self._result(known, current, expected)
            if result["status"] == "saved":
                self._saved[key] = {"before": copy.deepcopy(current), "result": copy.deepcopy(result)}
            return result

    def save(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """Save current editor text only while its last-read disk version still matches."""
        with self._lock:
            current = self.validate_snapshot(snapshot)
            candidate = {
                "path": current["path"], "candidateText": current["sourceText"],
                "rangeStartUtf16": 0, "rangeEndUtf16": utf16_length(current["sourceText"]),
            }
            return self._result(candidate, current, current)

    def undo(
        self, undo_of_call_id: str, current_snapshot: dict[str, Any], *, request_id: str,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        """Restore one successful operation only if its saved editor and disk still match."""
        with self._lock:
            if not request_id:
                raise DocumentError("Undo requires a new requestId")
            current = self.validate_snapshot(current_snapshot)
            if request_id in self._undos:
                recorded = self._undos[request_id]
                if recorded["callId"] != undo_of_call_id or recorded["turnId"] != turn_id:
                    raise DocumentError("Undo requestId already identifies another operation")
                return self._duplicate_result(recorded["result"], current, recorded["before"])
            matches = [value for key, value in self._saved.items() if key[1] == undo_of_call_id and (turn_id is None or key[0] == turn_id)]
            if len(matches) != 1:
                raise DocumentError("Undo requires one successful operation in this editing session")
            original = matches[0]
            current = self.validate_snapshot(current_snapshot)
            saved = original["result"]
            if current["path"] != saved["path"]:
                raise DocumentError("Undo belongs to another document")
            expected = {key: saved[key] for key in ("rootPath", "path", "editorRevision", "sourceText", "diskFingerprint")}
            candidate = {
                "path": current["path"], "candidateText": original["before"]["sourceText"],
                "rangeStartUtf16": 0, "rangeEndUtf16": utf16_length(saved["sourceText"]),
            }
            result = self._result(candidate, current, expected)
            if result["status"] == "saved":
                self._undos[request_id] = {"callId": undo_of_call_id, "turnId": turn_id, "before": copy.deepcopy(current), "result": copy.deepcopy(result)}
            return result
