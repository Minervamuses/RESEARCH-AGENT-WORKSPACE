"""Strict, read-only migration parser for legacy Plan logs."""

from __future__ import annotations

import json
import os
import re
import stat
import uuid
from collections import Counter
from dataclasses import replace
from datetime import datetime
from itertools import islice
from pathlib import Path
from typing import Callable

from agent.config import AgentConfig
from agent.turns.memory import ToolActivityRecord, TurnRecord

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


class LegacyPlanLogReader:
    """Read bounded v1/v2 Plan logs for one legacy conversation."""

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
