"""Plan-mode markdown log: file creation and turn-block rendering."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from agent.config import AgentConfig
from agent.history import group_tool_messages_by_call_id
from agent.thinking import FusionCandidateTrace


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
            "do_not_index: true\n"
            "generated_by: agent.plan_mode\n"
            f"session_id: {self._session_id}\n"
            f"created_at: {created_at}\n"
            "---\n\n"
            "# Plan log\n\n"
        )
        path.write_text(header, encoding="utf-8")
        return path

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
