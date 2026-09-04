"""Versioned Plan-mode persistence and bounded turn restoration."""

from __future__ import annotations

import json
import os
import re
import stat
import uuid
from collections import Counter, defaultdict, deque
from dataclasses import replace
from datetime import datetime, timezone
from itertools import islice
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from langchain_core.messages import ToolMessage

from agent.config import AgentConfig
from agent.turns.memory import ToolActivityRecord, TurnRecord
from agent.turns.safety import content_text
from agent.turns.trace import group_tool_messages_by_call_id

if TYPE_CHECKING:
    from agent.thinking.schemas import FusionCandidateTrace

PLAN_LOG_FORMAT_VERSION = 2
MAX_PLAN_RESTORE_FILE_BYTES = 1024 * 1024
MAX_PLAN_RESTORE_FILES = 4096
MAX_PLAN_RESTORE_TOTAL_BYTES = 8 * 1024 * 1024
MAX_PLAN_RESTORE_TURNS = 4096
MAX_PLAN_RESTORE_TURN_CHARS = 131_072
MAX_PLAN_TOOL_ACTIVITIES = 128
MAX_PLAN_TOOL_CALL_ID_BYTES = 256
MAX_PLAN_TOOL_NAME_BYTES = 256
MAX_PLAN_TOOL_ARGUMENT_BYTES = 32_768
MAX_PLAN_TOOL_RESULT_BYTES = 65_536

_PLAN_HEADER_RE = re.compile(
    r"\A---\n"
    r"generated_by: agent\.plan_mode\n"
    r"(?:format_version: (?P<format_version>[0-9]{1,10})\n)?"
    r"session_id: (?P<session_id>[0-9a-f]{32})\n"
    r"created_at: [^\n]{1,128}\n"
    r"---\n\n"
    r"# Plan log\n\n"
)
_TURN_HEADING_RE = re.compile(r"(?m)^## Turn [1-9][0-9]* - ")
_V2_TURN_BLOCK_RE = re.compile(
    r"\A## Turn (?P<turn_id>[1-9][0-9]*) - (?P<timestamp>[^\n]{1,128})\n\n"
    r"\*\*Turn data v2 \(JSON\):\*\*\n\n"
    r"(?P<payload>\{[^\n]*\})\n\n"
    r"---\n\Z"
)
_LEGACY_TOOL_HEADING_RE = re.compile(r"(?m)^### Tool: (?P<name>[^\n]*)$")
_LEGACY_TOOL_BLOCK_RE = re.compile(
    r"\A### Tool: (?P<name>[^\n]*)\n\n"
    r"```json\n(?P<arguments>.*?)\n```\n\n"
    r"\*\*Result:\*\*\n\n(?P<result>.*)\Z",
    re.DOTALL,
)
_TOOL_NAME_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_.:-]*\Z")
_ACTIVITY_KEYS = {"call_id", "name", "arguments", "result", "status"}
_ACTIVITY_STATUSES = {"ok", "failed", "denied", "incomplete"}
_SCOPES = {"normal", "citation", "fusion"}
_CITATION_TOOL_NAME = "citation_workflow"


class PlanLogRestoreError(RuntimeError):
    """A Plan log cannot be safely reduced to restorable turns."""


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"invalid JSON constant: {value}")


def _load_strict_json(value: str) -> object:
    return json.loads(
        value,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_json_constant,
    )


def _read_bounded_regular_file(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
        try:
            file_stat = os.fstat(descriptor)
            if not stat.S_ISREG(file_stat.st_mode):
                raise PlanLogRestoreError(
                    "plan log is unavailable or not UTF-8"
                )
            chunks: list[bytes] = []
            remaining = MAX_PLAN_RESTORE_FILE_BYTES + 1
            while remaining:
                chunk = os.read(descriptor, min(64 * 1024, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            return b"".join(chunks)
        finally:
            os.close(descriptor)
    except PlanLogRestoreError:
        raise
    except OSError as exc:
        raise PlanLogRestoreError(
            "plan log is unavailable or not UTF-8"
        ) from exc


def _canonical_uuid4(value: str) -> bool:
    try:
        parsed = uuid.UUID(hex=value)
    except ValueError:
        return False
    return parsed.version == 4 and parsed.hex == value


def _header_version(match: re.Match[str]) -> int:
    raw = match.group("format_version")
    return 1 if raw is None else int(raw)


def _valid_timestamp(timestamp: str) -> bool:
    try:
        parsed = datetime.fromisoformat(
            timestamp.removesuffix("Z")
            + ("+00:00" if timestamp.endswith("Z") else "")
        )
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _bounded_utf8(value: str, max_bytes: int) -> tuple[str, bool]:
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value, False
    suffix = f"\n\n[truncated; original {len(encoded)} bytes]"
    suffix_bytes = suffix.encode("utf-8")
    if len(suffix_bytes) >= max_bytes:
        return suffix_bytes[:max_bytes].decode("utf-8", errors="ignore"), True
    budget = max(0, max_bytes - len(suffix_bytes))
    head = encoded[:budget].decode("utf-8", errors="ignore")
    return f"{head}{suffix}", True


def _valid_tool_name(value: str) -> bool:
    return (
        bool(_TOOL_NAME_RE.fullmatch(value))
        and len(value.encode("utf-8")) <= MAX_PLAN_TOOL_NAME_BYTES
    )


def _tool_status(message: ToolMessage, result: str) -> str:
    if getattr(message, "status", None) == "error":
        if "tool not available in the current mode" in result.casefold():
            return "denied"
        return "failed"
    try:
        payload = json.loads(result)
    except (json.JSONDecodeError, TypeError):
        payload = None
    if isinstance(payload, dict) and payload.get("approved") is False:
        return "denied"
    return "ok"


class PlanLog:
    """Render, append, and restore one session's versioned Plan logs."""

    def __init__(
        self,
        config: AgentConfig,
        *,
        session_id: str,
        app_root_resolver: Callable[[], Path],
    ):
        self._config = config
        self._session_id = session_id
        self._app_root_resolver = app_root_resolver
        self._write_format_version = PLAN_LOG_FORMAT_VERSION

    @property
    def write_format_version(self) -> int:
        return self._write_format_version

    def new_log_file(self) -> Path:
        created = datetime.now(timezone.utc)
        created_at = created.isoformat()
        safe_ts = created.strftime("%Y%m%dT%H%M%SZ")
        log_dir = self._app_root_resolver() / self._config.plan_logs_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / f"plan-{self._session_id}-{safe_ts}.md"
        self._write_format_version = PLAN_LOG_FORMAT_VERSION
        header = (
            "---\n"
            "generated_by: agent.plan_mode\n"
            f"format_version: {PLAN_LOG_FORMAT_VERSION}\n"
            f"session_id: {self._session_id}\n"
            f"created_at: {created_at}\n"
            "---\n\n"
            "# Plan log\n\n"
        )
        path.write_text(header, encoding="utf-8")
        return path

    def resume_log_file(self, path: str | Path) -> Path:
        """Validate a same-session v1/v2 log and retain its write format."""
        log_dir = (
            self._app_root_resolver() / self._config.plan_logs_dir
        ).resolve()
        try:
            candidate = Path(path).resolve(strict=True)
        except OSError as exc:
            raise ValueError("plan log is unavailable") from exc
        if (
            candidate.parent != log_dir
            or not candidate.name.startswith(f"plan-{self._session_id}-")
            or candidate.suffix != ".md"
        ):
            raise ValueError("plan log does not belong to this session")
        try:
            with candidate.open("r", encoding="utf-8") as handle:
                header_text = handle.read(512)
        except (OSError, UnicodeError) as exc:
            raise ValueError("plan log is unavailable") from exc
        header = _PLAN_HEADER_RE.match(header_text)
        if header is None or header.group("session_id") != self._session_id:
            raise ValueError("plan log header is malformed")
        version = _header_version(header)
        if version not in {1, PLAN_LOG_FORMAT_VERSION}:
            raise ValueError("plan log format version is unsupported")
        self._write_format_version = version
        return candidate

    def read_direct_answer_turns(self) -> list[TurnRecord]:
        """Read bounded v1/v2 Plan turns without executing stored activity."""
        if not _canonical_uuid4(self._session_id):
            raise PlanLogRestoreError("session_id must be canonical UUIDv4 hex")
        log_dir = self._app_root_resolver() / self._config.plan_logs_dir
        try:
            if not log_dir.exists():
                return []
            paths = sorted(islice(
                log_dir.glob(f"plan-{self._session_id}-*.md"),
                MAX_PLAN_RESTORE_FILES + 1,
            ))
            if len(paths) > MAX_PLAN_RESTORE_FILES:
                raise PlanLogRestoreError("plan logs exceed the file-count limit")
        except OSError as exc:
            raise PlanLogRestoreError("plan logs are unavailable") from exc

        turns: dict[int, TurnRecord] = {}
        total_bytes = 0
        for path in paths:
            try:
                raw = _read_bounded_regular_file(path)
                if len(raw) > MAX_PLAN_RESTORE_FILE_BYTES:
                    raise PlanLogRestoreError("plan log exceeds the file limit")
                total_bytes += len(raw)
                if total_bytes > MAX_PLAN_RESTORE_TOTAL_BYTES:
                    raise PlanLogRestoreError("plan logs exceed the total limit")
                content = raw.decode("utf-8")
            except PlanLogRestoreError:
                raise
            except (OSError, UnicodeError) as exc:
                raise PlanLogRestoreError(
                    "plan log is unavailable or not UTF-8"
                ) from exc
            for turn in self._parse_file(content):
                if turn.turn_id in turns:
                    raise PlanLogRestoreError(
                        "plan logs contain a duplicate turn_id"
                    )
                turns[turn.turn_id] = turn
                if len(turns) > MAX_PLAN_RESTORE_TURNS:
                    raise PlanLogRestoreError("plan logs exceed the turn limit")
        return [turns[turn_id] for turn_id in sorted(turns)]

    def _parse_file(self, content: str) -> list[TurnRecord]:
        if "\r" in content:
            raise PlanLogRestoreError("plan log line endings are ambiguous")
        header = _PLAN_HEADER_RE.match(content)
        if header is None or header.group("session_id") != self._session_id:
            raise PlanLogRestoreError("plan log header is malformed")
        version = _header_version(header)
        body = content[header.end():]
        if version == 1:
            return self._parse_legacy_body(body)
        if version == PLAN_LOG_FORMAT_VERSION:
            return self._parse_v2_body(body)
        raise PlanLogRestoreError("plan log format version is unsupported")

    def _blocks(self, body: str) -> list[str]:
        if not body:
            return []
        headings = list(_TURN_HEADING_RE.finditer(body))
        if not headings or headings[0].start() != 0:
            raise PlanLogRestoreError("plan log contains an incomplete turn")
        return [
            body[
                heading.start():
                headings[index + 1].start()
                if index + 1 < len(headings)
                else len(body)
            ]
            for index, heading in enumerate(headings)
        ]

    def _parse_v2_body(self, body: str) -> list[TurnRecord]:
        parsed: list[TurnRecord] = []
        for block in self._blocks(body):
            if "\n### Fusion candidate " in block:
                raise PlanLogRestoreError("fusion Plan turns are not restorable")
            match = _V2_TURN_BLOCK_RE.fullmatch(block)
            if match is None:
                raise PlanLogRestoreError("plan log v2 turn is malformed")
            if len(block.encode("utf-8")) > MAX_PLAN_RESTORE_FILE_BYTES:
                raise PlanLogRestoreError("plan log turn exceeds the byte limit")
            try:
                payload = _load_strict_json(match.group("payload"))
            except (json.JSONDecodeError, ValueError) as exc:
                raise PlanLogRestoreError("plan log v2 payload is malformed") from exc
            if not isinstance(payload, dict) or set(payload) != {
                "format_version",
                "turn_id",
                "timestamp",
                "user",
                "assistant",
                "scope",
                "tool_activities",
            }:
                raise PlanLogRestoreError("plan log v2 payload shape is malformed")
            turn_id = payload["turn_id"]
            timestamp = payload["timestamp"]
            user_input = payload["user"]
            assistant_output = payload["assistant"]
            scope = payload["scope"]
            raw_activities = payload["tool_activities"]
            if (
                type(payload["format_version"]) is not int
                or payload["format_version"] != PLAN_LOG_FORMAT_VERSION
                or type(turn_id) is not int
                or turn_id < 1
                or turn_id != int(match.group("turn_id"))
                or not isinstance(timestamp, str)
                or timestamp != match.group("timestamp")
                or not _valid_timestamp(timestamp)
                or not isinstance(user_input, str)
                or not user_input
                or not isinstance(assistant_output, str)
                or not assistant_output
                or not isinstance(scope, str)
                or scope not in _SCOPES
                or not isinstance(raw_activities, list)
            ):
                raise PlanLogRestoreError("plan log v2 turn metadata is malformed")
            if scope == "fusion":
                raise PlanLogRestoreError("fusion Plan turns are not restorable")
            if (
                len(user_input) > MAX_PLAN_RESTORE_TURN_CHARS
                or len(assistant_output) > MAX_PLAN_RESTORE_TURN_CHARS
            ):
                raise PlanLogRestoreError("plan log turn exceeds the text limit")
            if len(raw_activities) > MAX_PLAN_TOOL_ACTIVITIES:
                raise PlanLogRestoreError(
                    "plan log turn exceeds the tool-activity limit"
                )
            activity_pairs = [
                self._parse_v2_activity(value) for value in raw_activities
            ]
            counts = Counter(
                activity.call_id
                for activity, _valid in activity_pairs
                if activity.call_id
            )
            activities = tuple(
                replace(
                    activity,
                    prompt_eligible=(
                        scope == "normal"
                        and valid
                        and activity.call_id is not None
                        and counts[activity.call_id] == 1
                        and activity.name.casefold() != _CITATION_TOOL_NAME
                    ),
                )
                for activity, valid in activity_pairs
            )
            parsed.append(TurnRecord(
                user_input=user_input,
                assistant_output=assistant_output,
                turn_id=turn_id,
                timestamp=timestamp,
                persist_target="none",
                tool_activities=activities,
            ))
        return parsed

    def _parse_v2_activity(
        self,
        value: object,
    ) -> tuple[ToolActivityRecord, bool]:
        if not isinstance(value, dict) or set(value) != _ACTIVITY_KEYS:
            return ToolActivityRecord(
                call_id=None,
                name="unknown",
                arguments="{}",
                result="Malformed tool activity was omitted.",
                status="incomplete",
            ), False

        raw_call_id = value["call_id"]
        raw_name = value["name"]
        raw_arguments = value["arguments"]
        raw_result = value["result"]
        raw_status = value["status"]
        call_id_valid = raw_call_id is None or (
            isinstance(raw_call_id, str)
            and bool(raw_call_id)
            and len(raw_call_id.encode("utf-8")) <= MAX_PLAN_TOOL_CALL_ID_BYTES
        )
        call_id = raw_call_id if isinstance(raw_call_id, str) else None
        if call_id is not None:
            call_id, call_id_truncated = _bounded_utf8(
                call_id,
                MAX_PLAN_TOOL_CALL_ID_BYTES,
            )
            call_id_valid = call_id_valid and not call_id_truncated
        name = raw_name if isinstance(raw_name, str) else "unknown"
        name, name_truncated = _bounded_utf8(name, MAX_PLAN_TOOL_NAME_BYTES)
        name_valid = (
            isinstance(raw_name, str)
            and _valid_tool_name(raw_name)
            and not name_truncated
        )
        arguments = raw_arguments if isinstance(raw_arguments, str) else "{}"
        arguments, arguments_truncated = _bounded_utf8(
            arguments,
            MAX_PLAN_TOOL_ARGUMENT_BYTES,
        )
        try:
            parsed_arguments = _load_strict_json(arguments)
        except (json.JSONDecodeError, TypeError, ValueError):
            parsed_arguments = None
        arguments_valid = (
            isinstance(raw_arguments, str)
            and isinstance(parsed_arguments, dict)
            and not arguments_truncated
        )
        result = raw_result if isinstance(raw_result, str) else ""
        result, result_truncated = _bounded_utf8(
            result,
            MAX_PLAN_TOOL_RESULT_BYTES,
        )
        status_valid = (
            isinstance(raw_status, str) and raw_status in _ACTIVITY_STATUSES
        )
        status = raw_status if status_valid else "incomplete"
        valid = (
            call_id_valid
            and call_id is not None
            and name_valid
            and arguments_valid
            and isinstance(raw_result, str)
            and not result_truncated
            and status_valid
            and status != "incomplete"
        )
        if not valid:
            status = "incomplete"
        return ToolActivityRecord(
            call_id=call_id,
            name=name or "unknown",
            arguments=arguments,
            result=result,
            status=status,
        ), valid

    def _parse_legacy_body(self, body: str) -> list[TurnRecord]:
        parsed: list[TurnRecord] = []
        for block in self._blocks(body):
            if any(marker in block for marker in (
                "\n### Fusion candidate ",
                "\n**Candidate answer excerpt:**\n",
            )):
                raise PlanLogRestoreError("fusion Plan turns are not restorable")
            if len(re.findall(r"(?m)^\*\*User:\*\*$", block)) != 1:
                raise PlanLogRestoreError("plan log user marker is ambiguous")
            if len(re.findall(r"(?m)^\*\*Assistant:\*\*$", block)) != 1:
                raise PlanLogRestoreError("plan log assistant marker is ambiguous")
            if len(re.findall(r"(?m)^---$", block)) != 1:
                raise PlanLogRestoreError("plan log boundary is ambiguous")
            heading_end = block.find("\n\n")
            if heading_end < 0:
                raise PlanLogRestoreError("plan log turn is malformed")
            heading = block[:heading_end]
            heading_match = re.fullmatch(
                r"## Turn ([1-9][0-9]*) - ([^\n]{1,128})",
                heading,
            )
            if heading_match is None:
                raise PlanLogRestoreError("plan log turn is malformed")
            remainder = block[heading_end + 2:]
            user_prefix = "**User:**\n\n"
            assistant_marker = "\n\n**Assistant:**\n\n"
            boundary = "\n\n---\n"
            if not remainder.startswith(user_prefix) or not remainder.endswith(boundary):
                raise PlanLogRestoreError("plan log turn is malformed")
            content = remainder[len(user_prefix):-len(boundary)]
            if content.count(assistant_marker) != 1:
                raise PlanLogRestoreError("plan log assistant marker is ambiguous")
            before_assistant, assistant_output = content.split(assistant_marker, 1)
            tool_marker = "\n\n### Tool: "
            if tool_marker in before_assistant:
                user_input, tool_text = before_assistant.split(tool_marker, 1)
                tool_text = f"### Tool: {tool_text}"
                activities = self._parse_legacy_activities(tool_text)
            else:
                user_input = before_assistant
                activities = ()
            timestamp = heading_match.group(2)
            if (
                not user_input
                or not assistant_output
                or not _valid_timestamp(timestamp)
            ):
                raise PlanLogRestoreError(
                    "plan log contains an empty or invalid turn side"
                )
            if (
                len(user_input) > MAX_PLAN_RESTORE_TURN_CHARS
                or len(assistant_output) > MAX_PLAN_RESTORE_TURN_CHARS
            ):
                raise PlanLogRestoreError("plan log turn exceeds the text limit")
            parsed.append(TurnRecord(
                user_input=user_input,
                assistant_output=assistant_output,
                turn_id=int(heading_match.group(1)),
                timestamp=timestamp,
                persist_target="none",
                tool_activities=activities,
            ))
        return parsed

    def _parse_legacy_activities(
        self,
        tool_text: str,
    ) -> tuple[ToolActivityRecord, ...]:
        headings = list(_LEGACY_TOOL_HEADING_RE.finditer(tool_text))
        if not headings or headings[0].start() != 0:
            return (self._legacy_incomplete("unknown", tool_text),)
        if len(headings) > MAX_PLAN_TOOL_ACTIVITIES:
            raise PlanLogRestoreError(
                "plan log turn exceeds the tool-activity limit"
            )
        activities: list[ToolActivityRecord] = []
        for index, heading in enumerate(headings):
            end = (
                headings[index + 1].start()
                if index + 1 < len(headings)
                else len(tool_text)
            )
            segment = tool_text[heading.start():end].rstrip("\n")
            match = _LEGACY_TOOL_BLOCK_RE.fullmatch(segment)
            if match is None:
                activities.append(
                    self._legacy_incomplete(heading.group("name"), segment)
                )
                continue
            raw_arguments = match.group("arguments")
            try:
                arguments_value = json.loads(raw_arguments)
            except json.JSONDecodeError:
                arguments_value = None
            if isinstance(arguments_value, dict):
                arguments = json.dumps(
                    arguments_value,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            else:
                arguments = raw_arguments
            arguments, arguments_truncated = _bounded_utf8(
                arguments,
                MAX_PLAN_TOOL_ARGUMENT_BYTES,
            )
            raw_result = match.group("result").strip()
            fenced = re.findall(r"```\n(.*?)\n```", raw_result, re.DOTALL)
            if (
                fenced
                and re.sub(
                    r"```\n.*?\n```",
                    "",
                    raw_result,
                    flags=re.DOTALL,
                ).strip() == ""
            ):
                result = "\n\n".join(fenced)
                complete = isinstance(arguments_value, dict)
            else:
                result = raw_result
                complete = False
            result, result_truncated = _bounded_utf8(
                result,
                MAX_PLAN_TOOL_RESULT_BYTES,
            )
            name, name_truncated = _bounded_utf8(
                match.group("name") or "unknown",
                MAX_PLAN_TOOL_NAME_BYTES,
            )
            status = "ok" if complete else "incomplete"
            if complete:
                status = self._status_from_legacy_result(result)
            if arguments_truncated or result_truncated or name_truncated:
                status = "incomplete"
            activities.append(ToolActivityRecord(
                call_id=None,
                name=name or "unknown",
                arguments=arguments,
                result=result,
                status=status,
                prompt_eligible=False,
            ))
        return tuple(activities)

    def _legacy_incomplete(self, name: str, segment: str) -> ToolActivityRecord:
        bounded_name, _ = _bounded_utf8(
            name or "unknown",
            MAX_PLAN_TOOL_NAME_BYTES,
        )
        bounded_result, _ = _bounded_utf8(
            segment,
            MAX_PLAN_TOOL_RESULT_BYTES,
        )
        return ToolActivityRecord(
            call_id=None,
            name=bounded_name or "unknown",
            arguments="{}",
            result=bounded_result,
            status="incomplete",
            prompt_eligible=False,
        )

    @staticmethod
    def _status_from_legacy_result(result: str) -> str:
        if "tool not available in the current mode" in result.casefold():
            return "denied"
        try:
            payload = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            payload = None
        if isinstance(payload, dict) and payload.get("approved") is False:
            return "denied"
        return "ok"

    def build_tool_activities(
        self,
        *,
        new_messages: list,
        tool_calls: list[dict],
        scope: str,
    ) -> tuple[ToolActivityRecord, ...]:
        """Pair current-turn calls/results without granting disk authority."""
        if not tool_calls and not any(
            isinstance(message, ToolMessage) for message in new_messages
        ):
            return ()
        if scope not in _SCOPES:
            raise ValueError("unknown Plan turn scope")
        if len(tool_calls) > MAX_PLAN_TOOL_ACTIVITIES:
            raise ValueError("Plan turn exceeds the tool-activity limit")

        result_entries: list[tuple[int, ToolMessage, str | None]] = []
        results_by_id: dict[str, deque[tuple[int, ToolMessage]]] = defaultdict(deque)
        for index, message in enumerate(new_messages):
            if not isinstance(message, ToolMessage):
                continue
            raw_id = getattr(message, "tool_call_id", None)
            call_id = str(raw_id) if raw_id else None
            result_entries.append((index, message, call_id))
            if call_id:
                results_by_id[call_id].append((index, message))

        call_ids = [
            str(call.get("id")) if call.get("id") else None
            for call in tool_calls
        ]
        call_counts = Counter(call_id for call_id in call_ids if call_id)
        result_counts = Counter(
            call_id for _index, _message, call_id in result_entries if call_id
        )
        consumed_results: set[int] = set()
        activities: list[ToolActivityRecord] = []
        allow_prompt = (
            self._write_format_version == PLAN_LOG_FORMAT_VERSION
            and scope == "normal"
        )

        for call, raw_call_id in zip(tool_calls, call_ids, strict=True):
            result_entry = (
                results_by_id[raw_call_id].popleft()
                if raw_call_id and results_by_id[raw_call_id]
                else None
            )
            if result_entry is None:
                result_message = None
                result = ""
                status = "incomplete"
            else:
                result_index, result_message = result_entry
                consumed_results.add(result_index)
                result = content_text(result_message.content)
                status = _tool_status(result_message, result)

            call_id = raw_call_id
            call_id_valid = bool(call_id)
            if call_id is not None:
                call_id, call_id_truncated = _bounded_utf8(
                    call_id,
                    MAX_PLAN_TOOL_CALL_ID_BYTES,
                )
                call_id_valid = call_id_valid and not call_id_truncated
            raw_name = call.get("name", "unknown")
            name = str(raw_name) if raw_name is not None else "unknown"
            name, name_truncated = _bounded_utf8(
                name,
                MAX_PLAN_TOOL_NAME_BYTES,
            )
            name_valid = _valid_tool_name(name) and not name_truncated
            raw_arguments = call.get("args", {})
            try:
                arguments = json.dumps(
                    raw_arguments,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            except (TypeError, ValueError):
                arguments = "{}"
                arguments_serializable = False
            else:
                arguments_serializable = isinstance(raw_arguments, dict)
            arguments, arguments_truncated = _bounded_utf8(
                arguments,
                MAX_PLAN_TOOL_ARGUMENT_BYTES,
            )
            result_limit = min(
                max(0, int(self._config.plan_log_max_tool_chars)),
                MAX_PLAN_TOOL_RESULT_BYTES,
            )
            result, result_truncated = _bounded_utf8(result, result_limit)
            unique_pair = (
                raw_call_id is not None
                and call_counts[raw_call_id] == 1
                and result_counts[raw_call_id] == 1
                and result_message is not None
            )
            valid_pair = (
                unique_pair
                and call_id_valid
                and name_valid
                and arguments_serializable
                and not arguments_truncated
                and not result_truncated
            )
            if not valid_pair:
                status = "incomplete"
            activities.append(ToolActivityRecord(
                call_id=call_id,
                name=name or "unknown",
                arguments=arguments,
                result=result,
                status=status,
                prompt_eligible=(
                    allow_prompt
                    and valid_pair
                    and name.casefold() != _CITATION_TOOL_NAME
                ),
            ))

        for result_index, message, raw_call_id in result_entries:
            if result_index in consumed_results:
                continue
            raw_name = getattr(message, "name", None) or "unknown"
            name, _ = _bounded_utf8(str(raw_name), MAX_PLAN_TOOL_NAME_BYTES)
            if scope == "citation" and name.casefold() == _CITATION_TOOL_NAME:
                continue
            result = content_text(message.content)
            result, _truncated = _bounded_utf8(
                result,
                min(
                    max(0, int(self._config.plan_log_max_tool_chars)),
                    MAX_PLAN_TOOL_RESULT_BYTES,
                ),
            )
            call_id = raw_call_id
            if call_id is not None:
                call_id, _ = _bounded_utf8(
                    call_id,
                    MAX_PLAN_TOOL_CALL_ID_BYTES,
                )
            activities.append(ToolActivityRecord(
                call_id=call_id,
                name=name or "unknown",
                arguments="{}",
                result=result,
                status="incomplete",
                prompt_eligible=False,
            ))
        if len(activities) > MAX_PLAN_TOOL_ACTIVITIES:
            raise ValueError("Plan turn exceeds the tool-activity limit")
        return tuple(activities)

    def render_block(
        self,
        *,
        turn_id: int,
        timestamp: str,
        user_input: str,
        answer: str,
        new_messages: list,
        tool_calls: list[dict],
        candidate_traces: list[FusionCandidateTrace] | None = None,
        scope: str = "normal",
        tool_activities: tuple[ToolActivityRecord, ...] | None = None,
    ) -> str:
        if candidate_traces or self._write_format_version == 1:
            return self._render_legacy_block(
                turn_id=turn_id,
                timestamp=timestamp,
                user_input=user_input,
                answer=answer,
                new_messages=new_messages,
                tool_calls=tool_calls,
                candidate_traces=candidate_traces,
            )
        activities = tool_activities
        if activities is None:
            activities = self.build_tool_activities(
                new_messages=new_messages,
                tool_calls=tool_calls,
                scope=scope,
            )
        payload = {
            "format_version": PLAN_LOG_FORMAT_VERSION,
            "turn_id": turn_id,
            "timestamp": timestamp,
            "user": user_input,
            "assistant": answer,
            "scope": scope,
            "tool_activities": [
                {
                    "call_id": activity.call_id,
                    "name": activity.name,
                    "arguments": activity.arguments,
                    "result": activity.result,
                    "status": activity.status,
                }
                for activity in activities
            ],
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        block = (
            f"## Turn {turn_id} - {timestamp}\n\n"
            "**Turn data v2 (JSON):**\n\n"
            f"{encoded}\n\n"
            "---\n"
        )
        if len(block.encode("utf-8")) > MAX_PLAN_RESTORE_FILE_BYTES:
            raise ValueError("Plan turn exceeds the byte limit")
        return block

    def _render_legacy_block(
        self,
        *,
        turn_id: int,
        timestamp: str,
        user_input: str,
        answer: str,
        new_messages: list,
        tool_calls: list[dict],
        candidate_traces: list[FusionCandidateTrace] | None,
    ) -> str:
        lines = [
            f"## Turn {turn_id} - {timestamp}",
            "",
            "**User:**",
            "",
            user_input,
            "",
        ]
        if candidate_traces:
            lines.extend(self._render_candidate_segments(candidate_traces))
            non_candidate_calls = [
                call for call in tool_calls if not call.get("candidate_id")
            ]
            lines.extend(self._render_tool_blocks(new_messages, non_candidate_calls))
        else:
            lines.extend(self._render_tool_blocks(new_messages, tool_calls))
        lines.extend([
            "**Assistant:**",
            "",
            answer,
            "",
            "---",
            "",
        ])
        return "\n".join(lines)

    def _render_candidate_segments(
        self,
        candidate_traces: list[FusionCandidateTrace],
    ) -> list[str]:
        lines: list[str] = []
        for trace in candidate_traces:
            lines.extend([
                f"### Fusion candidate {trace.candidate_id} "
                f"(model: {trace.model_id}, status: {trace.status})",
                "",
            ])
            lines.extend(self._render_tool_blocks(trace.new_messages, trace.tool_calls))
            if trace.answer_excerpt:
                lines.extend([
                    "**Candidate answer excerpt:**",
                    "",
                    trace.answer_excerpt,
                    "",
                ])
        return lines

    def _render_tool_blocks(self, new_messages: list, tool_calls: list[dict]) -> list[str]:
        if not tool_calls:
            return []
        tool_messages = group_tool_messages_by_call_id(new_messages)
        lines: list[str] = []
        for call in tool_calls:
            call_id = call.get("id")
            results = tool_messages.get(str(call_id), []) if call_id else []
            lines.extend([
                f"### Tool: {call.get('name', 'unknown')}",
                "",
                "```json",
                json.dumps(call.get("args", {}), ensure_ascii=False, indent=2),
                "```",
                "",
                "**Result:**",
                "",
            ])
            if not results:
                lines.extend(["(no ToolMessage matched this tool_call_id)", ""])
            else:
                for result in results:
                    content = getattr(result, "content", "") or ""
                    capped = self._cap_tool_result(str(content))
                    lines.extend(["```", capped, "```", ""])
        return lines

    def _cap_tool_result(self, content: str) -> str:
        cap = self._config.plan_log_max_tool_chars
        if len(content) <= cap:
            return content
        head = content[:cap]
        return f"{head}\n\n[truncated; original {len(content)} chars]"

    @staticmethod
    def append_block(log_path: str, block: str) -> None:
        with Path(log_path).open("a", encoding="utf-8") as handle:
            handle.write(block)
