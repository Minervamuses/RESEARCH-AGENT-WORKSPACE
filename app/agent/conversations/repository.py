"""Durable, bounded storage for canonical conversation documents."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import stat
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from agent.conversations.models import (
    LATEST_CONTEXT_TURNS,
    MAX_CONVERSATION_BYTES,
    MAX_CONVERSATION_FILES,
    MAX_TITLE_BYTES,
    SCHEMA_VERSION,
    ContextTurn,
    ConversationConflictError,
    ConversationDocument,
    ConversationMalformedError,
    ConversationSummary,
    ConversationTooLargeError,
    ConversationTurn,
    ConversationUnavailableError,
    ConversationValidationError,
    FailureInfo,
    InvalidTransitionError,
    ToolActivitySummary,
    validate_conversation_id,
    validate_document,
    validate_turn_id,
)


_DOCUMENT_KEYS = frozenset({
    "schemaVersion",
    "conversationId",
    "projectId",
    "createdAt",
    "updatedAt",
    "turns",
})
_TURN_KEYS = frozenset({
    "turnId",
    "turnNumber",
    "kind",
    "state",
    "displayInput",
    "semanticInput",
    "contextEligible",
    "thinkingMode",
    "submittedAt",
    "finishedAt",
    "assistantOutput",
    "toolActivities",
    "failure",
})
_TOOL_ACTIVITY_KEYS = frozenset({"callId", "name", "status", "summary"})
_FAILURE_KEYS = frozenset({"code", "message", "retryable"})
_READ_CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True)
class ConversationSnapshot:
    """One validated document plus the fingerprint it was loaded from."""

    document: ConversationDocument
    fingerprint: str


@dataclass(frozen=True)
class ConversationScanIssue:
    """A safe per-file problem found while scanning the conversation root."""

    conversation_id: str | None
    path: Path
    code: str
    message: str


@dataclass(frozen=True)
class ConversationScanResult:
    """Healthy summaries and isolated issues from one bounded scan."""

    summaries: tuple[ConversationSummary, ...]
    issues: tuple[ConversationScanIssue, ...]


class _DuplicateJsonKeyError(ValueError):
    pass


class _ClassifiedMalformedError(ConversationMalformedError):
    """Internal malformed error retaining a safe scan classification."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKeyError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_json_constant(_value: str) -> None:
    raise ValueError("non-finite JSON number")


def _expect_exact_object(
    value: object,
    expected_keys: frozenset[str],
) -> dict[str, Any]:
    if type(value) is not dict or set(value) != expected_keys:
        raise ValueError("JSON object does not match the canonical schema")
    return value


def _activity_from_json(value: object) -> ToolActivitySummary:
    raw = _expect_exact_object(value, _TOOL_ACTIVITY_KEYS)
    return ToolActivitySummary(
        call_id=raw["callId"],
        name=raw["name"],
        status=raw["status"],
        summary=raw["summary"],
    )


def _failure_from_json(value: object) -> FailureInfo | None:
    if value is None:
        return None
    raw = _expect_exact_object(value, _FAILURE_KEYS)
    return FailureInfo(
        code=raw["code"],
        message=raw["message"],
        retryable=raw["retryable"],
    )


def _turn_from_json(value: object) -> ConversationTurn:
    raw = _expect_exact_object(value, _TURN_KEYS)
    activities = raw["toolActivities"]
    if type(activities) is not list:
        raise ValueError("toolActivities must be a JSON array")
    return ConversationTurn(
        turn_id=raw["turnId"],
        turn_number=raw["turnNumber"],
        kind=raw["kind"],
        state=raw["state"],
        display_input=raw["displayInput"],
        semantic_input=raw["semanticInput"],
        context_eligible=raw["contextEligible"],
        thinking_mode=raw["thinkingMode"],
        submitted_at=raw["submittedAt"],
        finished_at=raw["finishedAt"],
        assistant_output=raw["assistantOutput"],
        tool_activities=tuple(_activity_from_json(item) for item in activities),
        failure=_failure_from_json(raw["failure"]),
    )


def _document_from_json(data: bytes, expected_id: str) -> ConversationDocument:
    try:
        text = data.decode("utf-8", errors="strict")
        raw_value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise _ClassifiedMalformedError(
            "malformed",
            "conversation file is not strict UTF-8 JSON",
        ) from exc

    if type(raw_value) is not dict:
        raise _ClassifiedMalformedError(
            "malformed",
            "conversation file does not contain a JSON object",
        )
    if (
        "schemaVersion" in raw_value
        and (
            type(raw_value["schemaVersion"]) is not int
            or raw_value["schemaVersion"] != SCHEMA_VERSION
        )
    ):
        raise _ClassifiedMalformedError(
            "unsupported_version",
            "conversation file uses an unsupported schema version",
        )

    try:
        raw = _expect_exact_object(raw_value, _DOCUMENT_KEYS)
        conversation_id = validate_conversation_id(raw["conversationId"])
        if conversation_id != expected_id:
            raise _ClassifiedMalformedError(
                "identity_mismatch",
                "conversation ID does not match its filename",
            )
        turns = raw["turns"]
        if type(turns) is not list:
            raise ValueError("turns must be a JSON array")
        document = ConversationDocument(
            schema_version=raw["schemaVersion"],
            conversation_id=conversation_id,
            project_id=raw["projectId"],
            created_at=raw["createdAt"],
            updated_at=raw["updatedAt"],
            turns=tuple(_turn_from_json(item) for item in turns),
        )
        return validate_document(document)
    except _ClassifiedMalformedError:
        raise
    except (ConversationValidationError, TypeError, ValueError) as exc:
        raise _ClassifiedMalformedError(
            "malformed",
            "conversation file does not match the canonical schema",
        ) from exc


def _activity_to_json(activity: ToolActivitySummary) -> dict[str, Any]:
    return {
        "callId": activity.call_id,
        "name": activity.name,
        "status": activity.status,
        "summary": activity.summary,
    }


def _failure_to_json(failure: FailureInfo | None) -> dict[str, Any] | None:
    if failure is None:
        return None
    return {
        "code": failure.code,
        "message": failure.message,
        "retryable": failure.retryable,
    }


def _turn_to_json(turn: ConversationTurn) -> dict[str, Any]:
    return {
        "turnId": turn.turn_id,
        "turnNumber": turn.turn_number,
        "kind": turn.kind,
        "state": turn.state,
        "displayInput": turn.display_input,
        "semanticInput": turn.semantic_input,
        "contextEligible": turn.context_eligible,
        "thinkingMode": turn.thinking_mode,
        "submittedAt": turn.submitted_at,
        "finishedAt": turn.finished_at,
        "assistantOutput": turn.assistant_output,
        "toolActivities": [
            _activity_to_json(activity) for activity in turn.tool_activities
        ],
        "failure": _failure_to_json(turn.failure),
    }


def _document_to_json(document: ConversationDocument) -> dict[str, Any]:
    return {
        "schemaVersion": document.schema_version,
        "conversationId": document.conversation_id,
        "projectId": document.project_id,
        "createdAt": document.created_at,
        "updatedAt": document.updated_at,
        "turns": [_turn_to_json(turn) for turn in document.turns],
    }


def _encode_document(document: ConversationDocument) -> bytes:
    validate_document(document)
    try:
        payload = (
            json.dumps(
                _document_to_json(document),
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8", errors="strict")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ConversationValidationError(
            "document cannot be encoded as canonical UTF-8 JSON"
        ) from exc
    if len(payload) > MAX_CONVERSATION_BYTES:
        raise ConversationTooLargeError(
            f"conversation exceeds the {MAX_CONVERSATION_BYTES}-byte limit"
        )
    try:
        decoded = _document_from_json(payload, document.conversation_id)
    except ConversationMalformedError as exc:
        raise ConversationValidationError(
            "encoded document does not match the canonical schema"
        ) from exc
    if decoded != document:
        raise ConversationValidationError(
            "encoded document does not round-trip through the canonical schema"
        )
    return payload


def _fingerprint(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _same_logical_input(
    turn: ConversationTurn,
    *,
    kind: str,
    display_input: object,
    semantic_input: object,
    context_eligible: object,
    thinking_mode: object,
) -> bool:
    return (
        turn.kind == kind
        and turn.display_input == display_input
        and turn.semantic_input == semantic_input
        and turn.context_eligible == context_eligible
        and turn.thinking_mode == thinking_mode
    )


def _truncate_utf8(value: str, maximum_bytes: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= maximum_bytes:
        return value
    return encoded[:maximum_bytes].decode("utf-8", errors="ignore")


class ConversationRepository:
    """Own canonical JSON parsing, transitions, and durable publication."""

    def __init__(self, persist_dir: str | os.PathLike[str]) -> None:
        self.root = Path(persist_dir) / "conversations"

    def path_for(self, conversation_id: str) -> Path:
        """Return the canonical path for a validated conversation ID."""
        validated_id = validate_conversation_id(conversation_id)
        return self.root / f"{validated_id}.json"

    def create(
        self,
        *,
        conversation_id: str,
        project_id: str | None,
        turn_id: str,
        kind: str,
        display_input: str,
        semantic_input: str | None,
        context_eligible: bool,
        thinking_mode: str | None,
        submitted_at: str,
    ) -> ConversationSnapshot:
        """Atomically create the first pending turn without clobbering a file."""
        turn = ConversationTurn(
            turn_id=turn_id,
            turn_number=1,
            kind=kind,
            state="pending",
            display_input=display_input,
            semantic_input=semantic_input,
            context_eligible=context_eligible,
            thinking_mode=thinking_mode,
            submitted_at=submitted_at,
            finished_at=None,
            assistant_output=None,
            tool_activities=(),
            failure=None,
        )
        document = ConversationDocument(
            schema_version=SCHEMA_VERSION,
            conversation_id=conversation_id,
            project_id=project_id,
            created_at=submitted_at,
            updated_at=submitted_at,
            turns=(turn,),
        )
        return self.create_document(document)

    def create_document(
        self,
        document: ConversationDocument,
    ) -> ConversationSnapshot:
        """Atomically publish one complete validated document without clobbering."""
        payload = _encode_document(document)
        self._ensure_root(create=True)
        target = self.path_for(document.conversation_id)
        self._reject_unsafe_existing_target(target)
        temporary = self._write_validated_temp(payload, document)
        try:
            try:
                os.link(temporary, target, follow_symlinks=False)
            except FileExistsError as exc:
                self._raise_existing_target(target, exc)
            except OSError as exc:
                raise ConversationUnavailableError(
                    f"cannot create conversation: {exc}"
                ) from exc
            try:
                os.unlink(temporary)
            except OSError as exc:
                raise ConversationUnavailableError(
                    f"cannot remove published temporary file: {exc}"
                ) from exc
            temporary = None
            self._fsync_root()
        finally:
            self._cleanup_temp(temporary)
        return ConversationSnapshot(document=document, fingerprint=_fingerprint(payload))

    def load(self, conversation_id: str) -> ConversationSnapshot:
        """Load one strict bounded document and its content fingerprint."""
        validated_id = validate_conversation_id(conversation_id)
        if not self._ensure_root(create=False):
            raise ConversationUnavailableError("conversation does not exist")
        data = self._read_regular_file(self.path_for(validated_id))
        document = _document_from_json(data, validated_id)
        return ConversationSnapshot(document=document, fingerprint=_fingerprint(data))

    def load_optional(self, conversation_id: str) -> ConversationSnapshot | None:
        """Load one document, returning ``None`` only for an exact missing path."""
        validated_id = validate_conversation_id(conversation_id)
        if not self._ensure_root(create=False):
            return None
        target = self.path_for(validated_id)
        try:
            target_stat = os.lstat(target)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise ConversationUnavailableError(
                f"cannot inspect conversation file: {exc}"
            ) from exc
        if stat.S_ISLNK(target_stat.st_mode) or not stat.S_ISREG(target_stat.st_mode):
            raise ConversationUnavailableError(
                "conversation path must be a regular file"
            )
        return self.load(validated_id)

    def save(
        self,
        snapshot: ConversationSnapshot,
        document: ConversationDocument,
    ) -> ConversationSnapshot:
        """Replace a snapshot only if its durable content is still unchanged."""
        self._validate_snapshot_document_pair(snapshot, document)
        self._validate_document_update(snapshot.document, document)
        payload = _encode_document(document)
        self._ensure_root(create=False)
        target = self.path_for(document.conversation_id)
        temporary = self._write_validated_temp(payload, document)
        try:
            self._assert_snapshot_current(snapshot, target)
            try:
                os.replace(temporary, target)
            except OSError as exc:
                raise ConversationUnavailableError(
                    f"cannot replace conversation: {exc}"
                ) from exc
            temporary = None
            self._fsync_root()
        finally:
            self._cleanup_temp(temporary)
        return ConversationSnapshot(document=document, fingerprint=_fingerprint(payload))

    def append_pending(
        self,
        snapshot: ConversationSnapshot,
        *,
        turn_id: str,
        kind: str,
        display_input: str,
        semantic_input: str | None,
        context_eligible: bool,
        thinking_mode: str | None,
        submitted_at: str,
    ) -> ConversationSnapshot:
        """Append a pending turn or return an exact same-ID duplicate."""
        validate_turn_id(turn_id)
        existing = self._turn_with_id(snapshot.document, turn_id)
        if existing is not None:
            if not _same_logical_input(
                existing,
                kind=kind,
                display_input=display_input,
                semantic_input=semantic_input,
                context_eligible=context_eligible,
                thinking_mode=thinking_mode,
            ):
                raise ConversationConflictError(
                    "turnId already exists with different input"
                )
            self._assert_snapshot_current(
                snapshot,
                self.path_for(snapshot.document.conversation_id),
            )
            return snapshot
        if any(turn.state == "pending" for turn in snapshot.document.turns):
            raise ConversationConflictError(
                "conversation already contains a pending turn"
            )
        turn = ConversationTurn(
            turn_id=turn_id,
            turn_number=len(snapshot.document.turns) + 1,
            kind=kind,
            state="pending",
            display_input=display_input,
            semantic_input=semantic_input,
            context_eligible=context_eligible,
            thinking_mode=thinking_mode,
            submitted_at=submitted_at,
            finished_at=None,
            assistant_output=None,
            tool_activities=(),
            failure=None,
        )
        document = replace(
            snapshot.document,
            updated_at=submitted_at,
            turns=(*snapshot.document.turns, turn),
        )
        return self.save(snapshot, document)

    def complete_turn(
        self,
        snapshot: ConversationSnapshot,
        *,
        turn_id: str,
        assistant_output: str,
        finished_at: str,
        tool_activities: tuple[ToolActivitySummary, ...] = (),
    ) -> ConversationSnapshot:
        """Transition one pending turn to completed idempotently."""
        index, turn = self._required_turn(snapshot.document, turn_id)
        if turn.state == "completed":
            if (
                turn.assistant_output != assistant_output
                or turn.tool_activities != tool_activities
            ):
                raise ConversationConflictError(
                    "completed turn already has different terminal payload"
                )
            self._assert_snapshot_current(
                snapshot,
                self.path_for(snapshot.document.conversation_id),
            )
            return snapshot
        if turn.state != "pending":
            raise InvalidTransitionError(
                f"cannot transition {turn.state} turn to completed"
            )
        completed = replace(
            turn,
            state="completed",
            finished_at=finished_at,
            assistant_output=assistant_output,
            tool_activities=tool_activities,
            failure=None,
        )
        document = self._replace_turn(snapshot.document, index, completed, finished_at)
        return self.save(snapshot, document)

    def fail_turn(
        self,
        snapshot: ConversationSnapshot,
        *,
        turn_id: str,
        state: str,
        failure: FailureInfo,
        finished_at: str,
    ) -> ConversationSnapshot:
        """Transition one pending turn to failed or interrupted."""
        if state not in {"failed", "interrupted"}:
            raise InvalidTransitionError(
                "failure transition state must be failed or interrupted"
            )
        index, turn = self._required_turn(snapshot.document, turn_id)
        if turn.state == state:
            if turn.failure != failure:
                raise ConversationConflictError(
                    "terminal turn already has different failure payload"
                )
            self._assert_snapshot_current(
                snapshot,
                self.path_for(snapshot.document.conversation_id),
            )
            return snapshot
        if turn.state != "pending":
            raise InvalidTransitionError(
                f"cannot transition {turn.state} turn to {state}"
            )
        terminal = replace(
            turn,
            state=state,
            finished_at=finished_at,
            assistant_output=None,
            tool_activities=(),
            failure=failure,
        )
        document = self._replace_turn(snapshot.document, index, terminal, finished_at)
        return self.save(snapshot, document)

    def retry_turn(
        self,
        snapshot: ConversationSnapshot,
        *,
        turn_id: str,
        kind: str,
        display_input: str,
        semantic_input: str | None,
        context_eligible: bool,
        thinking_mode: str | None,
        retry_at: str,
    ) -> ConversationSnapshot:
        """Explicitly retry a failed/interrupted logical turn in place."""
        index, turn = self._required_turn(snapshot.document, turn_id)
        if not _same_logical_input(
            turn,
            kind=kind,
            display_input=display_input,
            semantic_input=semantic_input,
            context_eligible=context_eligible,
            thinking_mode=thinking_mode,
        ):
            raise ConversationConflictError(
                "turnId already exists with different input"
            )
        if turn.state in {"pending", "completed"}:
            self._assert_snapshot_current(
                snapshot,
                self.path_for(snapshot.document.conversation_id),
            )
            return snapshot
        if turn.state not in {"failed", "interrupted"}:
            raise InvalidTransitionError(f"cannot retry a {turn.state} turn")
        pending = replace(
            turn,
            state="pending",
            finished_at=None,
            assistant_output=None,
            tool_activities=(),
            failure=None,
        )
        document = self._replace_turn(snapshot.document, index, pending, retry_at)
        return self.save(snapshot, document)

    def latest_context(
        self,
        snapshot: ConversationSnapshot,
    ) -> tuple[ContextTurn, ...]:
        """Return only the latest completed, eligible conversational pairs."""
        eligible = [
            turn
            for turn in snapshot.document.turns
            if turn.kind == "conversational"
            and turn.state == "completed"
            and turn.context_eligible
        ]
        context: list[ContextTurn] = []
        for turn in eligible[-LATEST_CONTEXT_TURNS:]:
            assert turn.semantic_input is not None
            assert turn.assistant_output is not None
            context.append(ContextTurn(
                turn_id=turn.turn_id,
                turn_number=turn.turn_number,
                user_input=turn.semantic_input,
                assistant_output=turn.assistant_output,
            ))
        return tuple(context)

    def summary(self, snapshot: ConversationSnapshot) -> ConversationSummary:
        """Derive bounded sidebar metadata without persisting a second authority."""
        title: str | None = None
        for turn in snapshot.document.turns:
            if turn.kind != "conversational" or not turn.semantic_input.strip():
                continue
            collapsed = " ".join(turn.display_input.split())
            if collapsed:
                title = _truncate_utf8(collapsed, MAX_TITLE_BYTES)
                break
        return ConversationSummary(
            conversation_id=snapshot.document.conversation_id,
            project_id=snapshot.document.project_id,
            created_at=snapshot.document.created_at,
            updated_at=snapshot.document.updated_at,
            turn_count=len(snapshot.document.turns),
            title=title,
        )

    def scan(self) -> ConversationScanResult:
        """Scan a bounded number of files while isolating per-file failures."""
        if not self._ensure_root(create=False):
            return ConversationScanResult(summaries=(), issues=())
        names: list[str] = []
        scan_limited = False
        try:
            with os.scandir(self.root) as entries:
                for entry in entries:
                    if not entry.name.endswith(".json"):
                        continue
                    if len(names) >= MAX_CONVERSATION_FILES:
                        scan_limited = True
                        break
                    names.append(entry.name)
        except OSError as exc:
            raise ConversationUnavailableError(
                f"cannot scan conversation directory: {exc}"
            ) from exc

        summaries: list[ConversationSummary] = []
        issues: list[ConversationScanIssue] = []
        if scan_limited:
            issues.append(ConversationScanIssue(
                conversation_id=None,
                path=self.root,
                code="scan_limit",
                message=(
                    "conversation scan stopped at the configured file limit"
                ),
            ))
        for name in sorted(names):
            path = self.root / name
            candidate_id = name.removesuffix(".json")
            try:
                conversation_id = validate_conversation_id(candidate_id)
            except ConversationValidationError:
                issues.append(ConversationScanIssue(
                    conversation_id=None,
                    path=path,
                    code="invalid_name",
                    message="conversation filename is not a canonical ID",
                ))
                continue
            try:
                snapshot = self.load(conversation_id)
                summaries.append(self.summary(snapshot))
            except ConversationTooLargeError:
                issues.append(ConversationScanIssue(
                    conversation_id=conversation_id,
                    path=path,
                    code="oversized",
                    message="conversation file exceeds the configured size limit",
                ))
            except _ClassifiedMalformedError as exc:
                issues.append(ConversationScanIssue(
                    conversation_id=conversation_id,
                    path=path,
                    code=exc.code,
                    message=str(exc),
                ))
            except ConversationUnavailableError:
                issues.append(ConversationScanIssue(
                    conversation_id=conversation_id,
                    path=path,
                    code="unavailable",
                    message="conversation file is unavailable",
                ))
        summaries.sort(
            key=lambda item: (item.updated_at, item.conversation_id),
            reverse=True,
        )
        return ConversationScanResult(
            summaries=tuple(summaries),
            issues=tuple(issues),
        )

    @staticmethod
    def _turn_with_id(
        document: ConversationDocument,
        turn_id: str,
    ) -> ConversationTurn | None:
        for turn in document.turns:
            if turn.turn_id == turn_id:
                return turn
        return None

    @classmethod
    def _required_turn(
        cls,
        document: ConversationDocument,
        turn_id: str,
    ) -> tuple[int, ConversationTurn]:
        validate_turn_id(turn_id)
        for index, turn in enumerate(document.turns):
            if turn.turn_id == turn_id:
                return index, turn
        raise InvalidTransitionError("turnId does not exist in this conversation")

    @staticmethod
    def _replace_turn(
        document: ConversationDocument,
        index: int,
        turn: ConversationTurn,
        updated_at: str,
    ) -> ConversationDocument:
        turns = list(document.turns)
        turns[index] = turn
        return replace(document, updated_at=updated_at, turns=tuple(turns))

    @staticmethod
    def _validate_snapshot_document_pair(
        snapshot: ConversationSnapshot,
        document: ConversationDocument,
    ) -> None:
        if type(snapshot) is not ConversationSnapshot:
            raise ConversationValidationError(
                "snapshot must be a ConversationSnapshot"
            )
        validate_document(snapshot.document)
        validate_document(document)
        if snapshot.document.conversation_id != document.conversation_id:
            raise ConversationValidationError(
                "save cannot change conversationId"
            )
        if snapshot.document.project_id != document.project_id:
            raise ConversationValidationError("save cannot change projectId")
        if snapshot.document.created_at != document.created_at:
            raise ConversationValidationError("save cannot change createdAt")

    @staticmethod
    def _validate_document_update(
        before: ConversationDocument,
        after: ConversationDocument,
    ) -> None:
        if before == after:
            return
        if len(after.turns) == len(before.turns) + 1:
            if after.turns[:-1] != before.turns:
                raise InvalidTransitionError(
                    "append cannot rewrite existing turns"
                )
            if after.turns[-1].state != "pending":
                raise InvalidTransitionError(
                    "an appended turn must begin as pending"
                )
            return
        if len(after.turns) != len(before.turns):
            raise InvalidTransitionError("save cannot remove or insert turns")

        changed = [
            index
            for index, pair in enumerate(zip(before.turns, after.turns))
            if pair[0] != pair[1]
        ]
        if len(changed) != 1:
            raise InvalidTransitionError(
                "save must apply exactly one turn transition"
            )
        old = before.turns[changed[0]]
        new = after.turns[changed[0]]
        immutable_fields = (
            "turn_id",
            "turn_number",
            "kind",
            "display_input",
            "semantic_input",
            "context_eligible",
            "thinking_mode",
            "submitted_at",
        )
        if any(getattr(old, field) != getattr(new, field) for field in immutable_fields):
            raise InvalidTransitionError(
                "a transition cannot rewrite immutable turn input"
            )
        allowed = {
            ("pending", "completed"),
            ("pending", "failed"),
            ("pending", "interrupted"),
            ("failed", "pending"),
            ("interrupted", "pending"),
        }
        if (old.state, new.state) not in allowed:
            raise InvalidTransitionError(
                f"cannot transition {old.state} turn to {new.state}"
            )

    def _ensure_root(self, *, create: bool) -> bool:
        created = False
        try:
            root_stat = os.lstat(self.root)
        except FileNotFoundError:
            if not create:
                return False
            try:
                self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
                created = True
                root_stat = os.lstat(self.root)
            except OSError as exc:
                raise ConversationUnavailableError(
                    f"cannot create conversation directory: {exc}"
                ) from exc
        except OSError as exc:
            raise ConversationUnavailableError(
                f"cannot inspect conversation directory: {exc}"
            ) from exc
        if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
            raise ConversationUnavailableError(
                "conversation root must be a real directory, not a symlink"
            )
        if created:
            self._fsync_directory(self.root.parent)
        return True

    @staticmethod
    def _read_regular_file(path: Path) -> bytes:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        flags |= getattr(os, "O_NONBLOCK", 0)
        try:
            descriptor = os.open(path, flags)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise ConversationUnavailableError(
                    "conversation file must not be a symlink"
                ) from exc
            raise ConversationUnavailableError(
                f"cannot open conversation file: {exc}"
            ) from exc
        try:
            file_stat = os.fstat(descriptor)
            if not stat.S_ISREG(file_stat.st_mode):
                raise ConversationUnavailableError(
                    "conversation path must be a regular file"
                )
            chunks: list[bytes] = []
            remaining = MAX_CONVERSATION_BYTES + 1
            while remaining:
                chunk = os.read(descriptor, min(_READ_CHUNK_BYTES, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            data = b"".join(chunks)
        except ConversationUnavailableError:
            raise
        except OSError as exc:
            raise ConversationUnavailableError(
                f"cannot read conversation file: {exc}"
            ) from exc
        finally:
            os.close(descriptor)
        if len(data) > MAX_CONVERSATION_BYTES:
            raise ConversationTooLargeError(
                f"conversation exceeds the {MAX_CONVERSATION_BYTES}-byte limit"
            )
        return data

    def _write_validated_temp(
        self,
        payload: bytes,
        document: ConversationDocument,
    ) -> Path:
        descriptor = -1
        temporary: Path | None = None
        succeeded = False
        try:
            descriptor, raw_path = tempfile.mkstemp(
                prefix=f".{document.conversation_id}.",
                suffix=".tmp",
                dir=self.root,
            )
            temporary = Path(raw_path)
            with os.fdopen(descriptor, "wb") as stream:
                descriptor = -1
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            persisted = self._read_regular_file(temporary)
            if persisted != payload:
                raise ConversationUnavailableError(
                    "temporary conversation content changed before publish"
                )
            decoded = _document_from_json(persisted, document.conversation_id)
            if decoded != document:
                raise ConversationUnavailableError(
                    "temporary conversation failed publish validation"
                )
            succeeded = True
            return temporary
        except (ConversationMalformedError, ConversationTooLargeError) as exc:
            raise ConversationUnavailableError(
                "temporary conversation failed publish validation"
            ) from exc
        except ConversationUnavailableError:
            raise
        except OSError as exc:
            raise ConversationUnavailableError(
                f"cannot write temporary conversation file: {exc}"
            ) from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if temporary is not None and not succeeded:
                self._cleanup_temp(temporary)

    def _assert_snapshot_current(
        self,
        snapshot: ConversationSnapshot,
        target: Path,
    ) -> None:
        try:
            current = self._read_regular_file(target)
        except (ConversationTooLargeError, ConversationUnavailableError) as exc:
            if isinstance(exc, ConversationUnavailableError) and not isinstance(
                exc.__cause__, FileNotFoundError
            ):
                raise
            raise ConversationConflictError(
                "conversation was modified or removed after it was loaded"
            ) from exc
        if _fingerprint(current) != snapshot.fingerprint:
            raise ConversationConflictError(
                "conversation was modified after it was loaded"
            )

    @staticmethod
    def _reject_unsafe_existing_target(target: Path) -> None:
        try:
            target_stat = os.lstat(target)
        except FileNotFoundError:
            return
        except OSError as exc:
            raise ConversationUnavailableError(
                f"cannot inspect conversation target: {exc}"
            ) from exc
        if stat.S_ISLNK(target_stat.st_mode) or not stat.S_ISREG(target_stat.st_mode):
            raise ConversationUnavailableError(
                "conversation target must be an absent or regular file"
            )
        raise ConversationConflictError("conversation already exists")

    @staticmethod
    def _raise_existing_target(target: Path, cause: OSError) -> None:
        try:
            target_stat = os.lstat(target)
        except OSError:
            raise ConversationConflictError("conversation already exists") from cause
        if stat.S_ISLNK(target_stat.st_mode) or not stat.S_ISREG(target_stat.st_mode):
            raise ConversationUnavailableError(
                "conversation target must be an absent or regular file"
            ) from cause
        raise ConversationConflictError("conversation already exists") from cause

    def _fsync_root(self) -> None:
        self._fsync_directory(self.root)

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_DIRECTORY", 0)
        try:
            descriptor = os.open(path, flags)
        except OSError as exc:
            raise ConversationUnavailableError(
                f"cannot open conversation directory for fsync: {exc}"
            ) from exc
        try:
            directory_stat = os.fstat(descriptor)
            if not stat.S_ISDIR(directory_stat.st_mode):
                raise ConversationUnavailableError(
                    "conversation durability target is not a directory"
                )
            os.fsync(descriptor)
        except ConversationUnavailableError:
            raise
        except OSError as exc:
            raise ConversationUnavailableError(
                f"cannot fsync conversation directory: {exc}"
            ) from exc
        finally:
            os.close(descriptor)

    @staticmethod
    def _cleanup_temp(temporary: Path | None) -> None:
        if temporary is None:
            return
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            return
        except OSError as exc:
            raise ConversationUnavailableError(
                f"cannot remove temporary conversation file: {exc}"
            ) from exc


__all__ = [
    "ConversationRepository",
    "ConversationScanIssue",
    "ConversationScanResult",
    "ConversationSnapshot",
]
