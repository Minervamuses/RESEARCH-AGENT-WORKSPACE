"""Strict, read-only normalization of legacy conversation sources."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal, Protocol

from langchain_core.documents import Document

from agent.history_rag.store import (
    CHAT_HISTORY_COLLECTION,
    CHAT_HISTORY_SUBDIR,
    ChatHistoryStore,
    HistoryRestoreError,
)
from agent.conversations.models import (
    MAX_CONVERSATION_BYTES,
    MAX_INPUT_BYTES,
    MAX_OUTPUT_BYTES,
    MAX_TIMESTAMP_BYTES,
    MAX_TOOL_ACTIVITIES,
    MAX_TURNS,
    ConversationValidationError,
    validate_conversation_id,
    validate_timestamp,
)
from agent.turns.memory import ToolActivityRecord, TurnRecord


LegacySourceKind = Literal["chroma", "plan"]
LegacyRead = Callable[[str], list[TurnRecord]]

_SOURCE_KINDS = frozenset({"chroma", "plan"})
_FINGERPRINT_RE = re.compile(r"[0-9a-f]{64}\Z")
_TURN_ID_DOMAIN = b"agent.conversations.legacy-turn.v1\0"


class LegacyReadError(RuntimeError):
    """A legacy source cannot be reduced to one safe immutable snapshot."""


class _RawChromaCollection(Protocol):
    def get(self, **kwargs: object) -> object: ...


class _ChromaClient(Protocol):
    def get_collection(self, **kwargs: object) -> _RawChromaCollection: ...

    def close(self) -> None: ...


ChromaClientFactory = Callable[[str], _ChromaClient]


def _legacy_error(message: str) -> None:
    raise LegacyReadError(message)


def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev,
        left.st_ino,
        left.st_mode,
        left.st_size,
        left.st_mtime_ns,
        left.st_ctime_ns,
    ) == (
        right.st_dev,
        right.st_ino,
        right.st_mode,
        right.st_size,
        right.st_mtime_ns,
        right.st_ctime_ns,
    )


def _write_all(file_descriptor: int, content: bytes) -> None:
    offset = 0
    while offset < len(content):
        written = os.write(file_descriptor, content[offset:])
        if written < 1:
            _legacy_error("legacy Chroma source could not be cloned safely")
        offset += written


def _copy_regular_file(
    source_directory: int,
    destination_directory: int,
    name: str,
    expected: os.stat_result,
) -> None:
    source_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    destination_flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    source_file = os.open(name, source_flags, dir_fd=source_directory)
    try:
        opened = os.fstat(source_file)
        if not stat.S_ISREG(opened.st_mode) or not _same_file(expected, opened):
            _legacy_error("legacy Chroma source changed while being cloned")
        destination_file = os.open(
            name,
            destination_flags,
            0o600,
            dir_fd=destination_directory,
        )
        try:
            while True:
                block = os.read(source_file, 1024 * 1024)
                if not block:
                    break
                _write_all(destination_file, block)
            os.fsync(destination_file)
        finally:
            os.close(destination_file)
        if not _same_file(opened, os.fstat(source_file)):
            _legacy_error("legacy Chroma source changed while being cloned")
    finally:
        os.close(source_file)


def _copy_directory_tree(
    source_directory: int,
    destination_directory: int,
) -> None:
    names = sorted(os.listdir(source_directory))
    for name in names:
        expected = os.stat(
            name,
            dir_fd=source_directory,
            follow_symlinks=False,
        )
        if stat.S_ISLNK(expected.st_mode):
            _legacy_error("legacy Chroma source contains a symbolic link")
        if stat.S_ISREG(expected.st_mode):
            _copy_regular_file(
                source_directory,
                destination_directory,
                name,
                expected,
            )
            continue
        if not stat.S_ISDIR(expected.st_mode):
            _legacy_error("legacy Chroma source contains a non-regular entry")

        os.mkdir(name, mode=0o700, dir_fd=destination_directory)
        directory_flags = (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        source_child = os.open(
            name,
            directory_flags,
            dir_fd=source_directory,
        )
        try:
            destination_child = os.open(
                name,
                directory_flags,
                dir_fd=destination_directory,
            )
            try:
                opened = os.fstat(source_child)
                if (
                    not stat.S_ISDIR(opened.st_mode)
                    or not _same_file(expected, opened)
                ):
                    _legacy_error(
                        "legacy Chroma source changed while being cloned"
                    )
                _copy_directory_tree(source_child, destination_child)
                if not _same_file(opened, os.fstat(source_child)):
                    _legacy_error(
                        "legacy Chroma source changed while being cloned"
                    )
            finally:
                os.close(destination_child)
        finally:
            os.close(source_child)

    if names != sorted(os.listdir(source_directory)):
        _legacy_error("legacy Chroma source changed while being cloned")


def _clone_chroma_source(root: Path, destination: Path) -> bool:
    """Clone ``root/chat_history`` without following any source links."""
    try:
        root_status = os.lstat(root)
    except FileNotFoundError:
        return False
    except OSError:
        _legacy_error("legacy Chroma root is unavailable")
    if stat.S_ISLNK(root_status.st_mode):
        _legacy_error("legacy Chroma root must not be a symbolic link")
    if not stat.S_ISDIR(root_status.st_mode):
        _legacy_error("legacy Chroma root must be a directory")

    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        root_descriptor = os.open(root, directory_flags)
    except OSError:
        _legacy_error("legacy Chroma root is unavailable")
    try:
        if not _same_file(root_status, os.fstat(root_descriptor)):
            _legacy_error("legacy Chroma root changed while being opened")
        try:
            source_status = os.stat(
                CHAT_HISTORY_SUBDIR,
                dir_fd=root_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return False
        except OSError:
            _legacy_error("legacy Chroma source is unavailable")
        if stat.S_ISLNK(source_status.st_mode):
            _legacy_error("legacy Chroma source must not be a symbolic link")
        if not stat.S_ISDIR(source_status.st_mode):
            _legacy_error("legacy Chroma source must be a directory")

        try:
            source_descriptor = os.open(
                CHAT_HISTORY_SUBDIR,
                directory_flags,
                dir_fd=root_descriptor,
            )
        except OSError:
            _legacy_error("legacy Chroma source is unavailable")
        try:
            if not _same_file(source_status, os.fstat(source_descriptor)):
                _legacy_error("legacy Chroma source changed while being opened")
            destination.mkdir(mode=0o700)
            destination_descriptor = os.open(destination, directory_flags)
            try:
                _copy_directory_tree(
                    source_descriptor,
                    destination_descriptor,
                )
                os.fsync(destination_descriptor)
            finally:
                os.close(destination_descriptor)
        finally:
            os.close(source_descriptor)
    except LegacyReadError:
        raise
    except OSError:
        _legacy_error("legacy Chroma source could not be cloned safely")
    finally:
        os.close(root_descriptor)
    return True


class _RawChromaStore:
    """Expose raw Chroma rows through the existing strict history parser."""

    def __init__(self, collection: _RawChromaCollection) -> None:
        self._collection = collection

    def get_where(
        self,
        where: dict[str, object],
        *,
        limit: int | None = None,
    ) -> list[Document]:
        raw = self._collection.get(
            where=where,
            limit=limit,
            include=["documents", "metadatas"],
        )
        if type(raw) is not dict:
            raise ValueError("unexpected Chroma response")
        documents = raw.get("documents")
        metadatas = raw.get("metadatas")
        if documents is None and metadatas is None:
            return []
        if type(documents) is not list or type(metadatas) is not list:
            raise ValueError("unexpected Chroma response")
        if len(documents) != len(metadatas):
            raise ValueError("unexpected Chroma response")
        restored: list[Document] = []
        for content, metadata in zip(documents, metadatas, strict=True):
            restored.append(Document(page_content=content, metadata=metadata))
        return restored


class LegacyChromaReader:
    """Read legacy Chroma only through a disposable, non-following clone."""

    def __init__(
        self,
        persist_dir: str | os.PathLike[str],
        *,
        client_factory: ChromaClientFactory | None = None,
    ) -> None:
        try:
            self._persist_dir = Path(persist_dir)
        except TypeError as exc:
            raise TypeError("persist_dir must be path-like") from exc
        if client_factory is not None and not callable(client_factory):
            raise TypeError("client_factory must be callable or None")
        self._client_factory = client_factory

    def __call__(self, conversation_id: str) -> list[TurnRecord]:
        """Return strict role pairs without opening or mutating the source."""
        try:
            validate_conversation_id(conversation_id)
        except ConversationValidationError:
            raise LegacyReadError(
                "conversation_id must be canonical UUIDv4 hex"
            ) from None

        with tempfile.TemporaryDirectory(prefix="agent-legacy-chroma-") as temp_dir:
            clone = Path(temp_dir) / CHAT_HISTORY_SUBDIR
            if not _clone_chroma_source(self._persist_dir, clone):
                return []

            client: _ChromaClient | None = None
            result: list[TurnRecord] | None = None
            problem: LegacyReadError | None = None
            try:
                factory = self._client_factory
                if factory is None:
                    from chromadb import PersistentClient

                    factory = PersistentClient
                client = factory(str(clone))
                collection = client.get_collection(
                    name=CHAT_HISTORY_COLLECTION,
                    embedding_function=None,
                )
                strict_reader = ChatHistoryStore.__new__(ChatHistoryStore)
                strict_reader._store = _RawChromaStore(collection)
                result = ChatHistoryStore.read_session_turns(
                    strict_reader,
                    conversation_id,
                )
            except HistoryRestoreError:
                problem = LegacyReadError(
                    "legacy Chroma conversation is malformed"
                )
            except Exception:
                problem = LegacyReadError("legacy Chroma source is unavailable")
            finally:
                if client is not None:
                    try:
                        close = getattr(client, "close")
                        if not callable(close):
                            raise TypeError
                        close()
                    except Exception:
                        if problem is None:
                            problem = LegacyReadError(
                                "legacy Chroma client could not be closed"
                            )
            if problem is not None:
                raise problem from None
            assert result is not None
            return result

    def read(self, conversation_id: str) -> list[TurnRecord]:
        """Named equivalent of the migration reader callable."""
        return self(conversation_id)


def _utf8_size(value: str, field: str) -> int:
    try:
        return len(value.encode("utf-8", errors="strict"))
    except UnicodeEncodeError:
        _legacy_error(f"legacy {field} is not valid UTF-8 text")


def _bounded_nonblank_text(
    value: object,
    field: str,
    maximum_bytes: int,
) -> str:
    if type(value) is not str or not value.strip():
        _legacy_error(f"legacy {field} must be nonblank text")
    assert isinstance(value, str)
    if _utf8_size(value, field) > maximum_bytes:
        _legacy_error(f"legacy {field} exceeds the configured limit")
    return value


def _normalized_timestamp(value: object) -> str:
    if type(value) is not str or not value:
        _legacy_error("legacy timestamp is malformed")
    assert isinstance(value, str)
    if _utf8_size(value, "timestamp") > MAX_TIMESTAMP_BYTES:
        _legacy_error("legacy timestamp exceeds the configured limit")
    try:
        parsed = datetime.fromisoformat(
            value.removesuffix("Z")
            + ("+00:00" if value.endswith("Z") else "")
        )
        if parsed.tzinfo is None:
            raise ValueError
        normalized = parsed.astimezone(timezone.utc).isoformat().replace(
            "+00:00",
            "Z",
        )
        validate_timestamp(normalized, "legacy timestamp")
    except (ConversationValidationError, OverflowError, ValueError):
        _legacy_error("legacy timestamp is malformed")
    return normalized


def _validate_positive_integer(value: object, field: str) -> int:
    if type(value) is not int or value < 1:
        _legacy_error(f"legacy {field} must be a positive integer")
    assert isinstance(value, int)
    return value


@dataclass(frozen=True)
class LegacyTurn:
    """One completed legacy pair after bounded, UTC normalization."""

    turn_number: int
    user_input: str
    assistant_output: str
    timestamp: str
    dropped_activity_count: int

    def __post_init__(self) -> None:
        turn_number = _validate_positive_integer(
            self.turn_number,
            "turn_id",
        )
        if turn_number > MAX_TURNS:
            _legacy_error("legacy turn_id exceeds the configured limit")
        _bounded_nonblank_text(self.user_input, "user input", MAX_INPUT_BYTES)
        _bounded_nonblank_text(
            self.assistant_output,
            "assistant output",
            MAX_OUTPUT_BYTES,
        )
        try:
            validate_timestamp(self.timestamp, "legacy timestamp")
        except ConversationValidationError:
            _legacy_error("legacy timestamp is malformed")
        if (
            type(self.dropped_activity_count) is not int
            or not 0 <= self.dropped_activity_count <= MAX_TOOL_ACTIVITIES
        ):
            _legacy_error("legacy tool activity count is outside bounds")


@dataclass(frozen=True)
class LegacySourceCount:
    """Safe count of normalized turns read from one configured source."""

    kind: LegacySourceKind
    count: int

    def __post_init__(self) -> None:
        if type(self.kind) is not str or self.kind not in _SOURCE_KINDS:
            _legacy_error("legacy source kind is unknown")
        if type(self.count) is not int or not 0 <= self.count <= MAX_TURNS:
            _legacy_error("legacy source count is outside bounds")


@dataclass(frozen=True)
class LegacyConversationSnapshot:
    """One immutable, deterministic view across configured legacy sources."""

    conversation_id: str
    turns: tuple[LegacyTurn, ...]
    source_counts: tuple[LegacySourceCount, ...]
    fingerprint: str
    dropped_activity_count: int

    def __post_init__(self) -> None:
        try:
            validate_conversation_id(self.conversation_id)
        except ConversationValidationError:
            _legacy_error("conversation_id must be canonical UUIDv4 hex")
        if type(self.turns) is not tuple or any(
            type(turn) is not LegacyTurn for turn in self.turns
        ):
            _legacy_error("legacy snapshot turns must be immutable LegacyTurn values")
        if len(self.turns) > MAX_TURNS:
            _legacy_error("legacy snapshot exceeds the turn limit")
        if type(self.source_counts) is not tuple or any(
            type(count) is not LegacySourceCount for count in self.source_counts
        ):
            _legacy_error("legacy source counts must be immutable values")
        if sum(count.count for count in self.source_counts) != len(self.turns):
            _legacy_error("legacy source counts do not match the snapshot")
        if (
            type(self.fingerprint) is not str
            or _FINGERPRINT_RE.fullmatch(self.fingerprint) is None
        ):
            _legacy_error("legacy fingerprint must be a SHA-256 hex digest")
        expected_dropped = sum(
            turn.dropped_activity_count for turn in self.turns
        )
        if (
            type(self.dropped_activity_count) is not int
            or self.dropped_activity_count != expected_dropped
        ):
            _legacy_error("legacy dropped activity count is inconsistent")


def legacy_turn_id(conversation_id: str, turn_number: int) -> str:
    """Derive a stable canonical UUIDv4-shaped ID for one legacy turn."""
    validated_id = validate_conversation_id(conversation_id)
    number = _validate_positive_integer(turn_number, "turn number")
    digest = bytearray(hashlib.sha256(
        _TURN_ID_DOMAIN
        + validated_id.encode("ascii")
        + b"\0"
        + str(number).encode("ascii")
    ).digest()[:16])
    digest[6] = (digest[6] & 0x0F) | 0x40
    digest[8] = (digest[8] & 0x3F) | 0x80
    return bytes(digest).hex()


class LegacyConversationReader:
    """Read configured legacy sources without mutating or retaining raw activity."""

    def __init__(
        self,
        *,
        chroma_read: LegacyRead | None = None,
        plan_read: LegacyRead | None = None,
    ) -> None:
        for name, reader in (("chroma", chroma_read), ("plan", plan_read)):
            if reader is not None and not callable(reader):
                raise TypeError(f"{name}_read must be callable or None")
        self._readers: tuple[tuple[LegacySourceKind, LegacyRead], ...] = tuple(
            (kind, reader)
            for kind, reader in (
                ("chroma", chroma_read),
                ("plan", plan_read),
            )
            if reader is not None
        )

    def read(self, conversation_id: str) -> LegacyConversationSnapshot:
        """Return one strict merged snapshot or fail the whole conversation."""
        try:
            validated_id = validate_conversation_id(conversation_id)
        except ConversationValidationError:
            raise LegacyReadError(
                "conversation_id must be canonical UUIDv4 hex"
            ) from None

        source_counts: list[LegacySourceCount] = []
        source_payloads: list[dict[str, object]] = []
        by_number: dict[int, LegacyTurn] = {}
        total_text_bytes = 0

        for kind, read_source in self._readers:
            try:
                raw_turns = read_source(validated_id)
            except Exception:
                raise LegacyReadError(
                    f"{kind} legacy source is unavailable"
                ) from None
            if type(raw_turns) not in {list, tuple}:
                raise LegacyReadError(
                    f"{kind} legacy source returned an invalid collection"
                )
            if len(raw_turns) > MAX_TURNS:
                raise LegacyReadError(
                    f"{kind} legacy source exceeds the turn limit"
                )

            normalized_for_source: list[LegacyTurn] = []
            for raw_turn in tuple(raw_turns):
                try:
                    normalized = self._normalize_turn(raw_turn)
                except LegacyReadError:
                    raise LegacyReadError(
                        f"{kind} legacy source contains a malformed turn"
                    ) from None
                if normalized.turn_number in by_number:
                    raise LegacyReadError(
                        "legacy sources contain a duplicate turn_id"
                    )
                by_number[normalized.turn_number] = normalized
                normalized_for_source.append(normalized)
                total_text_bytes += (
                    _utf8_size(normalized.user_input, "user input")
                    + _utf8_size(
                        normalized.assistant_output,
                        "assistant output",
                    )
                )
                if total_text_bytes > MAX_CONVERSATION_BYTES:
                    raise LegacyReadError(
                        "legacy conversation exceeds the document limit"
                    )

            normalized_for_source.sort(key=lambda turn: turn.turn_number)
            source_counts.append(LegacySourceCount(kind, len(normalized_for_source)))
            source_payloads.append({
                "kind": kind,
                "turns": [self._fingerprint_turn(turn) for turn in normalized_for_source],
            })

        if len(by_number) > MAX_TURNS:
            raise LegacyReadError("legacy conversation exceeds the turn limit")
        ordered = tuple(by_number[number] for number in sorted(by_number))
        expected = list(range(1, len(ordered) + 1))
        if [turn.turn_number for turn in ordered] != expected:
            raise LegacyReadError(
                "legacy turn_id values must be contiguous starting at 1"
            )

        fingerprint_payload = json.dumps(
            {
                "conversationId": validated_id,
                "sources": source_payloads,
            },
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8", errors="strict")
        dropped_activity_count = sum(
            turn.dropped_activity_count for turn in ordered
        )
        return LegacyConversationSnapshot(
            conversation_id=validated_id,
            turns=ordered,
            source_counts=tuple(source_counts),
            fingerprint=hashlib.sha256(fingerprint_payload).hexdigest(),
            dropped_activity_count=dropped_activity_count,
        )

    @staticmethod
    def _normalize_turn(value: object) -> LegacyTurn:
        if type(value) is not TurnRecord:
            _legacy_error("legacy turn has an unexpected type")
        assert isinstance(value, TurnRecord)
        number = _validate_positive_integer(value.turn_id, "turn_id")
        if number > MAX_TURNS:
            _legacy_error("legacy turn_id exceeds the configured limit")
        user_input = _bounded_nonblank_text(
            value.user_input,
            "user input",
            MAX_INPUT_BYTES,
        )
        assistant_output = _bounded_nonblank_text(
            value.assistant_output,
            "assistant output",
            MAX_OUTPUT_BYTES,
        )
        timestamp = _normalized_timestamp(value.timestamp)
        if value.persist_target != "none" or value.log_path is not None:
            _legacy_error("legacy turn contains unexpected runtime provenance")
        activities = value.tool_activities
        if type(activities) is not tuple:
            _legacy_error("legacy tool activities must be a tuple")
        if len(activities) > MAX_TOOL_ACTIVITIES:
            _legacy_error("legacy tool activities exceed the configured limit")
        if any(type(activity) is not ToolActivityRecord for activity in activities):
            _legacy_error("legacy tool activities contain an unexpected type")
        return LegacyTurn(
            turn_number=number,
            user_input=user_input,
            assistant_output=assistant_output,
            timestamp=timestamp,
            dropped_activity_count=len(activities),
        )

    @staticmethod
    def _fingerprint_turn(turn: LegacyTurn) -> dict[str, object]:
        return {
            "assistantOutput": turn.assistant_output,
            "droppedActivityCount": turn.dropped_activity_count,
            "timestamp": turn.timestamp,
            "turnNumber": turn.turn_number,
            "userInput": turn.user_input,
        }


__all__ = [
    "ChromaClientFactory",
    "LegacyChromaReader",
    "LegacyConversationReader",
    "LegacyConversationSnapshot",
    "LegacyReadError",
    "LegacySourceCount",
    "LegacySourceKind",
    "LegacyTurn",
    "legacy_turn_id",
]
