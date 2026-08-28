"""Plan-mode markdown persistence and turn-block rendering."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from itertools import islice
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from agent.config import AgentConfig
from agent.turns.trace import group_tool_messages_by_call_id

if TYPE_CHECKING:
    from agent.thinking.schemas import FusionCandidateTrace

from agent.turns.memory import TurnRecord

MAX_PLAN_RESTORE_FILE_BYTES = 1024 * 1024
MAX_PLAN_RESTORE_FILES = 4096
MAX_PLAN_RESTORE_TOTAL_BYTES = 8 * 1024 * 1024
MAX_PLAN_RESTORE_TURNS = 4096
MAX_PLAN_RESTORE_TURN_CHARS = 131_072

_PLAN_HEADER_RE = re.compile(
    r"\A---\n"
    r"generated_by: agent\.plan_mode\n"
    r"session_id: (?P<session_id>[0-9a-f]{32})\n"
    r"created_at: [^\n]{1,128}\n"
    r"---\n\n"
    r"# Plan log\n\n"
)
_TURN_HEADING_RE = re.compile(r"(?m)^## Turn ")
_TURN_BLOCK_RE = re.compile(
    r"\A## Turn (?P<turn_id>[1-9][0-9]*) - (?P<timestamp>[^\n]{1,128})\n\n"
    r"\*\*User:\*\*\n\n(?P<user>.*?)\n\n"
    r"\*\*Assistant:\*\*\n\n(?P<assistant>.*?)\n\n"
    r"---\n\Z",
    re.DOTALL,
)


class PlanLogRestoreError(RuntimeError):
    """A plan log cannot be safely reduced to direct user/answer turns."""


def _canonical_uuid4(value: str) -> bool:
    try:
        parsed = uuid.UUID(hex=value)
    except ValueError:
        return False
    return parsed.version == 4 and parsed.hex == value


class PlanLog:
    """Renders and persists plan-mode turn blocks as markdown.

    Writes during a turn must still flow through the session facade's
    ``_append_block_to_md`` (which delegates to :meth:`append_block`) so a
    per-instance patch of that method keeps intercepting every write and a
    failed write still aborts the whole turn.
    """

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

    def new_log_file(self) -> Path:
        created = datetime.now(timezone.utc)
        created_at = created.isoformat()
        safe_ts = created.strftime("%Y%m%dT%H%M%SZ")
        log_dir = self._app_root_resolver() / self._config.plan_logs_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / f"plan-{self._session_id}-{safe_ts}.md"
        header = (
            "---\n"
            "generated_by: agent.plan_mode\n"
            f"session_id: {self._session_id}\n"
            f"created_at: {created_at}\n"
            "---\n\n"
            "# Plan log\n\n"
        )
        path.write_text(header, encoding="utf-8")
        return path

    def resume_log_file(self, path: str | Path) -> Path:
        """Validate and return this session's existing in-process plan log."""
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
        return candidate

    def read_direct_answer_turns(self) -> list[TurnRecord]:
        """Read bounded tool-free plan turns, rejecting ambiguous markdown."""
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
                with path.open("rb") as handle:
                    raw = handle.read(MAX_PLAN_RESTORE_FILE_BYTES + 1)
                if len(raw) > MAX_PLAN_RESTORE_FILE_BYTES:
                    raise PlanLogRestoreError("plan log exceeds the file limit")
                total_bytes += len(raw)
                if total_bytes > MAX_PLAN_RESTORE_TOTAL_BYTES:
                    raise PlanLogRestoreError("plan logs exceed the total limit")
                content = raw.decode("utf-8")
            except PlanLogRestoreError:
                raise
            except (OSError, UnicodeError) as exc:
                raise PlanLogRestoreError("plan log is unavailable or not UTF-8") from exc
            for turn in self._parse_direct_answer_file(content):
                if turn.turn_id in turns:
                    raise PlanLogRestoreError("plan logs contain a duplicate turn_id")
                turns[turn.turn_id] = turn
                if len(turns) > MAX_PLAN_RESTORE_TURNS:
                    raise PlanLogRestoreError("plan logs exceed the turn limit")
        return [turns[turn_id] for turn_id in sorted(turns)]

    def _parse_direct_answer_file(self, content: str) -> list[TurnRecord]:
        if "\r" in content:
            raise PlanLogRestoreError("plan log line endings are ambiguous")
        header = _PLAN_HEADER_RE.match(content)
        if header is None or header.group("session_id") != self._session_id:
            raise PlanLogRestoreError("plan log header is malformed")
        body = content[header.end():]
        if not body:
            return []
        headings = list(_TURN_HEADING_RE.finditer(body))
        if not headings or headings[0].start() != 0:
            raise PlanLogRestoreError("plan log contains an incomplete turn")

        parsed: list[TurnRecord] = []
        for index, heading in enumerate(headings):
            end = headings[index + 1].start() if index + 1 < len(headings) else len(body)
            block = body[heading.start():end]
            if any(marker in block for marker in (
                "\n### Tool:",
                "\n### Fusion candidate ",
                "\n**Candidate answer excerpt:**\n",
                "\n**Result:**\n",
            )):
                raise PlanLogRestoreError("plan log contains non-answer trace content")
            if len(re.findall(r"(?m)^\*\*User:\*\*$", block)) != 1:
                raise PlanLogRestoreError("plan log user marker is ambiguous")
            if len(re.findall(r"(?m)^\*\*Assistant:\*\*$", block)) != 1:
                raise PlanLogRestoreError("plan log assistant marker is ambiguous")
            if len(re.findall(r"(?m)^---$", block)) != 1:
                raise PlanLogRestoreError("plan log boundary is ambiguous")
            match = _TURN_BLOCK_RE.fullmatch(block)
            if match is None:
                raise PlanLogRestoreError("plan log turn is malformed")
            user_input = match.group("user")
            assistant_output = match.group("assistant")
            timestamp = match.group("timestamp")
            if not user_input or not assistant_output:
                raise PlanLogRestoreError("plan log contains an empty turn side")
            if (
                len(user_input) > MAX_PLAN_RESTORE_TURN_CHARS
                or len(assistant_output) > MAX_PLAN_RESTORE_TURN_CHARS
            ):
                raise PlanLogRestoreError("plan log turn exceeds the text limit")
            try:
                parsed_timestamp = datetime.fromisoformat(
                    timestamp.removesuffix("Z") + (
                        "+00:00" if timestamp.endswith("Z") else ""
                    )
                )
            except ValueError as exc:
                raise PlanLogRestoreError(
                    "plan log turn timestamp is malformed"
                ) from exc
            if parsed_timestamp.tzinfo is None:
                raise PlanLogRestoreError(
                    "plan log turn timestamp is malformed"
                )
            parsed.append(TurnRecord(
                user_input=user_input,
                assistant_output=assistant_output,
                turn_id=int(match.group("turn_id")),
                timestamp=timestamp,
                persist_target="none",
            ))
        return parsed

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
            # Candidate tool calls are rendered per-segment above; never re-render
            # them flat (their tool_call_ids collide across candidates). Only the
            # reviser / final-validation tool calls (no candidate_id) remain.
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
        """Render one segment per fusion candidate, pairing tool_call_ids inside
        the segment so candidate A's result never lands under candidate B."""
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
        with Path(log_path).open("a", encoding="utf-8") as f:
            f.write(block)
