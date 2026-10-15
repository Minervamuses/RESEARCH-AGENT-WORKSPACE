"""Immutable, strictly validated canonical conversation models."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any, Literal
from uuid import RFC_4122, UUID


SCHEMA_VERSION = 2
LATEST_CONTEXT_TURNS = 10

MAX_TURNS = 4_096
MAX_CONVERSATION_FILES = 4_096
MAX_INPUT_BYTES = 1024 * 1024
MAX_TOOL_ACTIVITIES = 128
MAX_IDENTIFIER_BYTES = 256
MAX_TOOL_SUMMARY_BYTES = 64 * 1024
MAX_FAILURE_MESSAGE_BYTES = 4 * 1024
MAX_TIMESTAMP_BYTES = 64
MAX_TITLE_BYTES = 256

ConversationKind = Literal["conversational", "display-only"]
ConversationState = Literal["pending", "completed", "failed", "interrupted"]
ThinkingMode = Literal["normal", "extended"]
ToolActivityStatus = Literal["ok", "failed", "denied", "incomplete"]
FailureCode = Literal[
    "execution_failed",
    "persistence_failed",
    "interrupted",
    "cancelled",
]

CONVERSATION_KINDS = frozenset({"conversational", "display-only"})
CONVERSATION_STATES = frozenset({
    "pending",
    "completed",
    "failed",
    "interrupted",
})
THINKING_MODES = frozenset({"normal", "extended"})
TOOL_ACTIVITY_STATUSES = frozenset({"ok", "failed", "denied", "incomplete"})
FAILURE_CODES = frozenset({
    "execution_failed",
    "persistence_failed",
    "interrupted",
    "cancelled",
})

_UUID4_HEX_RE = re.compile(r"[0-9a-f]{32}\Z")
_PROJECT_ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")
_TOOL_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]*\Z")
_UTC_TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z\Z"
)


class ConversationError(Exception):
    """Base class for safe canonical conversation failures."""


class ConversationValidationError(ConversationError, ValueError):
    """A caller-provided model or document violates the canonical schema."""


class ConversationConflictError(ConversationError):
    """A write conflicts with existing durable conversation state."""


class ConversationMalformedError(ConversationError):
    """Existing conversation content is not valid canonical JSON."""


class ConversationUnavailableError(ConversationError):
    """Conversation persistence is unavailable."""


class InvalidTransitionError(ConversationValidationError):
    """A requested turn state transition is not allowed."""


def _invalid(message: str) -> None:
    raise ConversationValidationError(message)


def _utf8_size(value: str, field: str) -> int:
    try:
        return len(value.encode("utf-8"))
    except UnicodeEncodeError:
        _invalid(f"{field} must be valid UTF-8 text")


def _validate_text(
    value: object,
    field: str,
    maximum_bytes: int | None,
    *,
    nonblank: bool = False,
) -> str:
    if type(value) is not str:
        _invalid(f"{field} must be a string")
    assert isinstance(value, str)
    if nonblank and not value.strip():
        _invalid(f"{field} must be nonblank")
    size = _utf8_size(value, field)
    if maximum_bytes is not None and size > maximum_bytes:
        _invalid(f"{field} exceeds the {maximum_bytes}-byte limit")
    return value


def _validate_optional_text(
    value: object,
    field: str,
    maximum_bytes: int | None,
    *,
    nonblank: bool = False,
) -> str | None:
    if value is None:
        return None
    return _validate_text(value, field, maximum_bytes, nonblank=nonblank)


def _validate_positive_integer(value: object, field: str) -> int:
    if type(value) is not int or value < 1:
        _invalid(f"{field} must be a positive integer")
    assert isinstance(value, int)
    return value


def is_canonical_uuid4_hex(value: object) -> bool:
    """Return whether *value* is a lowercase RFC 4122 UUIDv4 hex string."""
    if type(value) is not str or _UUID4_HEX_RE.fullmatch(value) is None:
        return False
    try:
        parsed = UUID(hex=value)
    except ValueError:
        return False
    return (
        parsed.variant == RFC_4122
        and parsed.version == 4
        and parsed.hex == value
    )


def _validate_uuid4_hex(value: object, field: str) -> str:
    if not is_canonical_uuid4_hex(value):
        _invalid(f"{field} must be a canonical lowercase UUIDv4 hex string")
    assert isinstance(value, str)
    return value


def validate_conversation_id(value: object) -> str:
    """Validate and return one canonical conversation ID."""
    return _validate_uuid4_hex(value, "conversationId")


def validate_turn_id(value: object) -> str:
    """Validate and return one canonical logical turn ID."""
    return _validate_uuid4_hex(value, "turnId")


def validate_project_id(value: object) -> str | None:
    """Validate a nullable, lowercase local project identifier."""
    if value is None:
        return None
    if type(value) is not str or _PROJECT_ID_RE.fullmatch(value) is None:
        _invalid("projectId must be null or a lowercase local identifier")
    assert isinstance(value, str)
    return value



def _context_object(value: object, required: set[str], optional: set[str] = frozenset()) -> dict[str, Any]:
    if type(value) is not dict or not required <= set(value) or set(value) - required - optional:
        _invalid("submittedContext object has missing or unexpected fields")
    return value


def _context_integer(value: object, field: str) -> int:
    if type(value) is not int or not 0 <= value <= 9_007_199_254_740_991:
        _invalid(f"{field} must be a non-negative safe integer")
    return value


def _context_path(value: object, field: str) -> str:
    value = _validate_text(value, field, 8192, nonblank=True)
    path = PurePosixPath(value)
    if (
        not value.startswith("/") or value.startswith("//") or "\\" in value
        or ".." in path.parts or str(path) != value
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        _invalid(f"{field} must be a canonical absolute Linux path")
    return value


def _context_fingerprint(value: object, field: str) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        _invalid(f"{field} must be a SHA-256 fingerprint")
    return value


def _context_slice(source: str, start: int, end: int) -> tuple[str, int, int]:
    _context_integer(start, "startUtf16")
    _context_integer(end, "endUtf16")
    if end < start:
        _invalid("submittedContext range is reversed")
    boundaries = {0: 0}
    offset = 0
    for index, character in enumerate(source):
        offset += 2 if ord(character) > 0xffff else 1
        if offset in {start, end}:
            boundaries[offset] = index + 1
    if start not in boundaries or end not in boundaries:
        _invalid("submittedContext range exceeds source text or splits a surrogate pair")
    left, right = boundaries[start], boundaries[end]
    return source[left:right], left, right


def _context_document(value: object, root: str, *, selected: bool) -> dict[str, Any]:
    required = {"rootPath", "path", "editorRevision", "sourceText", "diskFingerprint"}
    ranges = {"rangeStartUtf16", "rangeEndUtf16"}
    snapshot = _context_object(value, required | ranges if selected else required, set() if selected else ranges)
    if snapshot["rootPath"] != root:
        _invalid("document snapshot belongs to a different project root")
    path = _context_path(snapshot["path"], "document.path")
    if path == root or not PurePosixPath(path).is_relative_to(root):
        _invalid("document path must be inside its project root")
    _context_integer(snapshot["editorRevision"], "editorRevision")
    source = _validate_text(snapshot["sourceText"], "sourceText", MAX_INPUT_BYTES)
    _context_fingerprint(snapshot["diskFingerprint"], "diskFingerprint")
    if ("rangeStartUtf16" in snapshot) != ("rangeEndUtf16" in snapshot):
        _invalid("document snapshot requires both UTF-16 range endpoints")
    if "rangeStartUtf16" in snapshot:
        _context_slice(source, snapshot["rangeStartUtf16"], snapshot["rangeEndUtf16"])
    return snapshot


def validate_submitted_context(value: object) -> dict[str, Any] | None:
    """Validate frozen submission data without reading files; return detached JSON."""
    if value is None:
        return None
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ConversationValidationError("submittedContext must be valid JSON") from exc
    if len(encoded) > MAX_INPUT_BYTES:
        _invalid("submittedContext exceeds the 1 MiB input limit")
    context = _context_object(value, {
        "projectId", "rootPath", "permissionMode", "requestedThinkingMode",
        "skillReferences", "projectRules", "references",
    }, {"documentContext"})
    project_id = validate_project_id(context["projectId"])
    if project_id is None:
        _invalid("submittedContext.projectId must not be null")
    root = _context_path(context["rootPath"], "rootPath")
    if context["permissionMode"] not in ("ask", "bypass"):
        _invalid("permissionMode must be ask or bypass")
    if context["requestedThinkingMode"] not in ("normal", "extended"):
        _invalid("requestedThinkingMode must be normal or extended")
    skills = context["skillReferences"]
    if type(skills) is not list or len(skills) > 128:
        _invalid("skillReferences must be an array of at most 128 items")
    for item in skills:
        skill = _context_object(item, {"name", "startUtf16", "endUtf16"})
        _validate_text(skill["name"], "skill.name", MAX_IDENTIFIER_BYTES, nonblank=True)
        start = _context_integer(skill["startUtf16"], "skill.startUtf16")
        end = _context_integer(skill["endUtf16"], "skill.endUtf16")
        if end <= start:
            _invalid("skill reference range must be nonempty")
    rules = _context_object(context["projectRules"], {"text", "fingerprint"})
    rules_text = _validate_text(rules["text"], "projectRules.text", MAX_INPUT_BYTES)
    _context_fingerprint(rules["fingerprint"], "projectRules.fingerprint")
    if hashlib.sha256(rules_text.encode("utf-8")).hexdigest() != rules["fingerprint"]:
        _invalid("projectRules fingerprint does not match its text")
    if "documentContext" in context:
        _context_document(context["documentContext"], root, selected=False)
    references = context["references"]
    if type(references) is not list:
        _invalid("references must be an array")
    seen: set[str] = set()
    for item in references:
        if type(item) is not dict or item.get("kind") not in ("document", "chat"):
            _invalid("reference kind must be document or chat")
        kind = item["kind"]
        reference = _context_object(item, {"referenceId", "kind", "text", kind})
        reference_id = _validate_text(reference["referenceId"], "referenceId", MAX_IDENTIFIER_BYTES, nonblank=True)
        if reference_id in seen:
            _invalid("referenceId must be unique within a submission")
        seen.add(reference_id)
        frozen = _validate_text(reference["text"], "reference.text", MAX_INPUT_BYTES)
        if not frozen:
            _invalid("reference text must not be empty")
        if kind == "document":
            document = _context_object(reference["document"], {"snapshot", "startLine", "endLine"})
            snapshot = _context_document(document["snapshot"], root, selected=True)
            selected_text, left, right = _context_slice(
                snapshot["sourceText"], snapshot["rangeStartUtf16"], snapshot["rangeEndUtf16"],
            )
            if selected_text != frozen:
                _invalid("document reference text does not match its frozen snapshot range")
            breaks = [match.end() for match in re.finditer(r"\r\n|\r|\n", snapshot["sourceText"])]
            start_line = 1 + sum(end <= left for end in breaks)
            end_line = 1 + sum(end < right for end in breaks)
            if (type(document["startLine"]) is not int or type(document["endLine"]) is not int
                    or document["startLine"] != start_line or document["endLine"] != end_line):
                _invalid("document reference line numbers do not match the frozen source range")
        else:
            chat = _context_object(reference["chat"], {
                "projectId", "sessionId", "turnId", "role", "messageFingerprint", "startUtf16", "endUtf16",
            })
            if chat["projectId"] != project_id:
                _invalid("chat reference belongs to another project")
            validate_conversation_id(chat["sessionId"])
            validate_turn_id(chat["turnId"])
            if chat["role"] not in ("user", "assistant"):
                _invalid("chat reference role must be user or assistant")
            _context_fingerprint(chat["messageFingerprint"], "messageFingerprint")
            start = _context_integer(chat["startUtf16"], "chat.startUtf16")
            end = _context_integer(chat["endUtf16"], "chat.endUtf16")
            if end <= start or end - start != len(frozen.encode("utf-16-le")) // 2:
                _invalid("chat reference range does not match its selected text length")
    return json.loads(encoded)

def validate_timestamp(value: object, field: str = "timestamp") -> str:
    """Validate a bounded ISO 8601 UTC timestamp ending in ``Z``."""
    timestamp = _validate_text(value, field, MAX_TIMESTAMP_BYTES)
    if _UTC_TIMESTAMP_RE.fullmatch(timestamp) is None:
        _invalid(f"{field} must be a UTC ISO 8601 timestamp ending in Z")
    try:
        datetime.fromisoformat(timestamp.removesuffix("Z") + "+00:00")
    except ValueError:
        _invalid(f"{field} must be a valid UTC ISO 8601 timestamp")
    return timestamp


def _timestamp_value(value: object, field: str) -> tuple[str, datetime]:
    timestamp = validate_timestamp(value, field)
    return timestamp, datetime.fromisoformat(
        timestamp.removesuffix("Z") + "+00:00"
    )


@dataclass(frozen=True)
class ToolActivitySummary:
    """One bounded, display-safe tool activity summary."""

    call_id: str | None
    name: str
    status: ToolActivityStatus
    summary: str

    def __post_init__(self) -> None:
        _validate_optional_text(
            self.call_id,
            "callId",
            MAX_IDENTIFIER_BYTES,
            nonblank=True,
        )
        _validate_text(
            self.name,
            "name",
            MAX_IDENTIFIER_BYTES,
            nonblank=True,
        )
        if _TOOL_NAME_RE.fullmatch(self.name) is None:
            _invalid("name must be a simple tool identifier")
        if type(self.status) is not str or self.status not in TOOL_ACTIVITY_STATUSES:
            _invalid("status contains an unknown tool activity value")
        _validate_text(self.summary, "summary", MAX_TOOL_SUMMARY_BYTES)


@dataclass(frozen=True)
class FailureInfo:
    """Bounded user-safe information for a failed or interrupted turn."""

    code: FailureCode
    message: str
    retryable: bool

    def __post_init__(self) -> None:
        if type(self.code) is not str or self.code not in FAILURE_CODES:
            _invalid("code contains an unknown failure value")
        _validate_text(
            self.message,
            "message",
            MAX_FAILURE_MESSAGE_BYTES,
            nonblank=True,
        )
        if type(self.retryable) is not bool:
            _invalid("retryable must be a boolean")


@dataclass(frozen=True)
class ConversationTurn:
    """One lifecycle-aware turn in a canonical conversation."""

    turn_id: str
    turn_number: int
    kind: ConversationKind
    state: ConversationState
    display_input: str
    semantic_input: str | None
    context_eligible: bool
    thinking_mode: ThinkingMode | None
    submitted_at: str
    finished_at: str | None
    assistant_output: str | None
    tool_activities: tuple[ToolActivitySummary, ...]
    failure: FailureInfo | None
    submitted_context: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "submitted_context", validate_submitted_context(self.submitted_context))
        validate_turn(self)


@dataclass(frozen=True)
class ConversationDocument:
    """The exact versioned contents of one canonical conversation file."""

    schema_version: int
    conversation_id: str
    project_id: str | None
    created_at: str
    updated_at: str
    turns: tuple[ConversationTurn, ...]

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version not in (1, SCHEMA_VERSION):
            _invalid(f"schemaVersion must equal 1 or {SCHEMA_VERSION}")
        validate_conversation_id(self.conversation_id)
        validate_project_id(self.project_id)
        _created_at, created_value = _timestamp_value(
            self.created_at,
            "createdAt",
        )
        _updated_at, updated_value = _timestamp_value(
            self.updated_at,
            "updatedAt",
        )
        if updated_value < created_value:
            _invalid("updatedAt must not precede createdAt")
        if type(self.turns) is not tuple:
            _invalid("turns must be a tuple")
        if len(self.turns) > MAX_TURNS:
            _invalid(f"turns exceeds the {MAX_TURNS}-item limit")
        if any(type(turn) is not ConversationTurn for turn in self.turns):
            _invalid("turns must contain ConversationTurn values")


@dataclass(frozen=True)
class ConversationSummary:
    """Bounded sidebar data derived from a canonical conversation."""

    conversation_id: str
    project_id: str | None
    created_at: str
    updated_at: str
    turn_count: int
    title: str | None

    def __post_init__(self) -> None:
        validate_conversation_id(self.conversation_id)
        validate_project_id(self.project_id)
        validate_timestamp(self.created_at, "createdAt")
        validate_timestamp(self.updated_at, "updatedAt")
        if type(self.turn_count) is not int or not 0 <= self.turn_count <= MAX_TURNS:
            _invalid(f"turnCount must be between 0 and {MAX_TURNS}")
        _validate_optional_text(
            self.title,
            "title",
            MAX_TITLE_BYTES,
            nonblank=True,
        )


@dataclass(frozen=True)
class ContextTurn:
    """The only turn shape exposed to model-context assembly."""

    turn_id: str
    turn_number: int
    user_input: str
    assistant_output: str

    def __post_init__(self) -> None:
        validate_turn_id(self.turn_id)
        _validate_positive_integer(self.turn_number, "turnNumber")
        _validate_text(
            self.user_input,
            "userInput",
            MAX_INPUT_BYTES,
            nonblank=True,
        )
        _validate_text(
            self.assistant_output,
            "assistantOutput",
            None,
            nonblank=True,
        )


def validate_turn(turn: ConversationTurn) -> ConversationTurn:
    """Validate one turn's exact field types and lifecycle shape."""
    if type(turn) is not ConversationTurn:
        _invalid("turn must be a ConversationTurn")
    validate_turn_id(turn.turn_id)
    _validate_positive_integer(turn.turn_number, "turnNumber")
    if type(turn.kind) is not str or turn.kind not in CONVERSATION_KINDS:
        _invalid("kind contains an unknown conversation value")
    if type(turn.state) is not str or turn.state not in CONVERSATION_STATES:
        _invalid("state contains an unknown turn value")
    _validate_text(
        turn.display_input,
        "displayInput",
        MAX_INPUT_BYTES,
        nonblank=True,
    )
    context = validate_submitted_context(turn.submitted_context)
    if context is not None:
        submitted = json.dumps(
            {"text": turn.display_input, "submittedContext": context},
            ensure_ascii=False, allow_nan=False, separators=(",", ":"),
        ).encode("utf-8")
        if len(submitted) > MAX_INPUT_BYTES:
            _invalid("text plus submittedContext exceeds the 1 MiB input limit")
        for skill in context["skillReferences"]:
            selected, left, right = _context_slice(turn.display_input, skill["startUtf16"], skill["endUtf16"])
            if selected != "@" + skill["name"]:
                _invalid("skillReferences do not match displayInput")
            if left and re.match(r"[A-Za-z0-9_.@+-]", turn.display_input[left - 1]):
                _invalid("skillReferences must begin at a token boundary")
            suffix = turn.display_input[right:]
            if re.match(r"[A-Za-z0-9_-]", suffix) or re.match(r"\.[A-Za-z0-9]", suffix):
                _invalid("skillReferences must end at a token boundary")
    if type(turn.context_eligible) is not bool:
        _invalid("contextEligible must be a boolean")
    _submitted_at, submitted_value = _timestamp_value(
        turn.submitted_at,
        "submittedAt",
    )
    if turn.finished_at is not None:
        _finished_at, finished_value = _timestamp_value(
            turn.finished_at,
            "finishedAt",
        )
        if finished_value < submitted_value:
            _invalid("finishedAt must not precede submittedAt")
    if type(turn.tool_activities) is not tuple:
        _invalid("toolActivities must be a tuple")
    if len(turn.tool_activities) > MAX_TOOL_ACTIVITIES:
        _invalid(
            f"toolActivities exceeds the {MAX_TOOL_ACTIVITIES}-item limit"
        )
    if any(type(activity) is not ToolActivitySummary for activity in turn.tool_activities):
        _invalid("toolActivities must contain ToolActivitySummary values")
    if turn.failure is not None and type(turn.failure) is not FailureInfo:
        _invalid("failure must be FailureInfo or null")

    if turn.kind == "display-only":
        if turn.semantic_input is not None:
            _invalid("display-only semanticInput must be null")
        if turn.context_eligible:
            _invalid("display-only contextEligible must be false")
        if turn.thinking_mode is not None:
            _invalid("display-only thinkingMode must be null")
    else:
        _validate_text(
            turn.semantic_input,
            "semanticInput",
            MAX_INPUT_BYTES,
            nonblank=True,
        )
        if type(turn.thinking_mode) is not str or turn.thinking_mode not in THINKING_MODES:
            _invalid("conversational thinkingMode must be normal or extended")

    if turn.state == "pending":
        if turn.finished_at is not None:
            _invalid("pending finishedAt must be null")
        if turn.assistant_output is not None:
            _invalid("pending assistantOutput must be null")
        if turn.tool_activities:
            _invalid("pending toolActivities must be empty")
        if turn.failure is not None:
            _invalid("pending failure must be null")
    elif turn.state == "completed":
        if turn.finished_at is None:
            _invalid("completed finishedAt is required")
        _validate_text(
            turn.assistant_output,
            "assistantOutput",
            None,
            nonblank=True,
        )
        if turn.failure is not None:
            _invalid("completed failure must be null")
    else:
        if turn.finished_at is None:
            _invalid(f"{turn.state} finishedAt is required")
        if turn.assistant_output is not None:
            _invalid(f"{turn.state} assistantOutput must be null")
        if turn.failure is None:
            _invalid(f"{turn.state} failure is required")
        if turn.state == "interrupted" and turn.failure.code not in {
            "interrupted",
            "cancelled",
        }:
            _invalid("interrupted failure code must be interrupted or cancelled")
        if turn.state == "failed" and turn.failure.code not in {
            "execution_failed",
            "persistence_failed",
        }:
            _invalid("failed failure code must describe an execution or persistence failure")
    return turn


def validate_document(document: ConversationDocument) -> ConversationDocument:
    """Validate cross-turn ordering and single-pending document invariants."""
    if type(document) is not ConversationDocument:
        _invalid("document must be a ConversationDocument")
    if not document.turns:
        _invalid("turns must contain at least one turn")
    if len(document.turns) > MAX_TURNS:
        _invalid(f"turns exceeds the {MAX_TURNS}-item limit")

    seen_ids: set[str] = set()
    pending_seen = False
    for index, turn in enumerate(document.turns):
        validate_turn(turn)
        if turn.submitted_context is not None:
            if document.schema_version == 1:
                _invalid("schemaVersion 1 cannot contain submittedContext")
            if turn.submitted_context["projectId"] != document.project_id:
                _invalid("submittedContext belongs to another conversation project")
        if turn.turn_number != index + 1:
            _invalid("turnNumber values must be contiguous starting at 1")
        if turn.turn_id in seen_ids:
            _invalid("turnId values must be unique within a conversation")
        seen_ids.add(turn.turn_id)
        if turn.state == "pending":
            if pending_seen:
                _invalid("a conversation may contain at most one pending turn")
            pending_seen = True
    return document


__all__ = [
    "CONVERSATION_KINDS",
    "CONVERSATION_STATES",
    "FAILURE_CODES",
    "LATEST_CONTEXT_TURNS",
    "MAX_CONVERSATION_FILES",
    "MAX_FAILURE_MESSAGE_BYTES",
    "MAX_IDENTIFIER_BYTES",
    "MAX_INPUT_BYTES",
    "MAX_TIMESTAMP_BYTES",
    "MAX_TITLE_BYTES",
    "MAX_TOOL_ACTIVITIES",
    "MAX_TOOL_SUMMARY_BYTES",
    "MAX_TURNS",
    "SCHEMA_VERSION",
    "THINKING_MODES",
    "TOOL_ACTIVITY_STATUSES",
    "ContextTurn",
    "ConversationConflictError",
    "ConversationDocument",
    "ConversationError",
    "ConversationKind",
    "ConversationMalformedError",
    "ConversationState",
    "ConversationSummary",
    "ConversationTurn",
    "ConversationUnavailableError",
    "ConversationValidationError",
    "FailureCode",
    "FailureInfo",
    "InvalidTransitionError",
    "ThinkingMode",
    "ToolActivityStatus",
    "ToolActivitySummary",
    "is_canonical_uuid4_hex",
    "validate_conversation_id",
    "validate_document",
    "validate_project_id",
    "validate_timestamp",
    "validate_turn",
    "validate_turn_id",
    "validate_submitted_context",
]
