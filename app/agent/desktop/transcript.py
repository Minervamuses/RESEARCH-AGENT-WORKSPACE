"""Conversation transcript pages and the bounded DTOs built from saved turns."""

from __future__ import annotations

import asyncio
import copy
from typing import Any
from agent.conversations import (
    ConversationError,
    ConversationSummary,
    ConversationTurn,
    ToolActivitySummary,
)
from agent.desktop.errors import DesktopServiceError, EventSink


_MAX_TRANSCRIPT_TOOL_ACTIVITIES = 128


_MAX_TRANSCRIPT_TOOL_CALL_ID_BYTES = 256


_MAX_TRANSCRIPT_TOOL_NAME_BYTES = 256


_MAX_TRANSCRIPT_TOOL_RESULT_BYTES = 65_536


_TRANSCRIPT_TOOL_STATUSES = frozenset({"ok", "failed", "denied", "incomplete"})


class _TranscriptOps:
    """DesktopService methods moved here unchanged; `self` is the DesktopService."""

    async def _session_transcript(
        self, params: dict[str, Any], _event_sink: EventSink | None
    ) -> dict[str, Any]:
        if self._turn_active:
            raise DesktopServiceError(
                "BUSY_TURN",
                "The transcript is unavailable during an active turn.",
                retryable=True,
            )
        project = self._require_opened_project(params["projectId"])
        session_id = params["sessionId"]
        self._require_saved_conversation(project["projectId"], session_id)
        offset = int(params.get("offset", 0))
        limit = int(params.get("limit", 20))
        try:
            turns = await asyncio.to_thread(
                self._read_conversation_turns,
                session_id,
                project["projectId"],
            )
        except ConversationError:
            return self._transcript_result(
                project["projectId"],
                session_id,
                status="degraded",
                issue="The stored transcript is malformed or incomplete.",
                turns=[],
                offset=offset,
                limit=limit,
                total=0,
            )
        if not turns:
            return self._transcript_result(
                project["projectId"],
                session_id,
                status="unavailable",
                issue="No persisted transcript is available.",
                turns=[],
                offset=offset,
                limit=limit,
                total=0,
            )
        page = turns[offset : offset + limit]
        if any(not self._transcript_turn_is_bounded(turn) for turn in page):
            return self._transcript_result(
                project["projectId"],
                session_id,
                status="degraded",
                issue="The requested transcript page contains an oversized turn.",
                turns=[],
                offset=offset,
                limit=limit,
                total=len(turns),
            )
        return self._transcript_result(
            project["projectId"],
            session_id,
            status="ready",
            issue=None,
            turns=page,
            offset=offset,
            limit=limit,
            total=len(turns),
        )

    @staticmethod
    def _summary_dto(summary: ConversationSummary) -> dict[str, Any]:
        return {
            "sessionId": summary.conversation_id,
            "title": summary.title or f"Conversation {summary.conversation_id[:8]}",
            "turnCount": summary.turn_count,
            "createdAt": summary.created_at,
            "updatedAt": summary.updated_at,
            "status": "ready",
            "issue": None,
        }

    def _read_conversation_turns(
        self,
        session_id: str,
        project_id: str,
    ) -> list[ConversationTurn]:
        snapshot = self._load_conversation(session_id, project_id)
        if snapshot is None:
            return []
        return list(snapshot.document.turns)

    @staticmethod
    def _tool_activity_payload(activity: ToolActivitySummary) -> dict[str, Any]:
        return {
            "callId": activity.call_id,
            "name": activity.name,
            "arguments": "(not retained)",
            "result": activity.summary or "(no summary)",
            "status": activity.status,
            "promptEligible": False,
        }

    @classmethod
    def _transcript_turn_is_bounded(cls, turn: ConversationTurn) -> bool:
        if (
            len(turn.submitted_at.encode("utf-8")) > 64
            or (
                turn.failure is not None
                and len(turn.failure.message.encode("utf-8")) > 4_096
            )
            or len(turn.tool_activities) > _MAX_TRANSCRIPT_TOOL_ACTIVITIES
        ):
            return False
        for activity in turn.tool_activities:
            if not isinstance(activity, ToolActivitySummary):
                return False
            result = activity.summary or "(no summary)"
            if (
                activity.status not in _TRANSCRIPT_TOOL_STATUSES
                or not activity.name
                or len(activity.name.encode("utf-8"))
                > _MAX_TRANSCRIPT_TOOL_NAME_BYTES
                or len(result.encode("utf-8"))
                > _MAX_TRANSCRIPT_TOOL_RESULT_BYTES
                or (
                    activity.call_id is not None
                    and (
                        not activity.call_id
                        or len(activity.call_id.encode("utf-8"))
                        > _MAX_TRANSCRIPT_TOOL_CALL_ID_BYTES
                    )
                )
            ):
                return False
        return True

    @staticmethod
    def _transcript_result(
        project_id: str,
        session_id: str,
        *,
        status: str,
        issue: str | None,
        turns: list[ConversationTurn],
        offset: int,
        limit: int,
        total: int,
    ) -> dict[str, Any]:
        return {
            "projectId": project_id,
            "sessionId": session_id,
            "status": status,
            "issue": issue,
            "items": [
                {
                    "turnId": turn.turn_id,
                    "turnNumber": turn.turn_number,
                    "kind": turn.kind,
                    "state": turn.state,
                    "timestamp": turn.submitted_at,
                    "userText": turn.display_input,
                    "submittedContext": copy.deepcopy(turn.submitted_context),
                    "assistantText": turn.assistant_output,
                    "failureCode": (
                        turn.failure.code if turn.failure is not None else None
                    ),
                    "failureMessage": (
                        turn.failure.message if turn.failure is not None else None
                    ),
                    "failureRetryable": (
                        turn.failure.retryable if turn.failure is not None else None
                    ),
                    "toolActivities": [
                        _TranscriptOps._tool_activity_payload(activity)
                        for activity in turn.tool_activities
                    ],
                }
                for turn in turns
            ],
            "total": total,
            "offset": offset,
            "limit": limit,
            "hasMore": status == "ready" and offset + len(turns) < total,
        }
