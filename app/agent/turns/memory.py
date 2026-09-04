"""Turn-aware conversation memory models and prompt assembly.

Two-layer model:

1. Fixed system prompt (owned by :class:`ChatSession`).
2. Recent turns since session start (``recent_turns``).

When ``recent_turns`` exceeds ``agent_recent_turns_window``, the oldest
turn is evicted into the long-term ChromaDB chat-history store. There
is no LLM-driven compaction; spillover is preserved verbatim and
searchable via the ``recall_history`` tool.
"""

import json
from dataclasses import dataclass
from typing import Literal

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)


ToolActivityStatus = Literal["ok", "failed", "denied", "incomplete"]


@dataclass(frozen=True)
class ToolActivityRecord:
    """One bounded tool call/result presentation retained with a turn."""

    call_id: str | None
    name: str
    arguments: str
    result: str
    status: ToolActivityStatus
    prompt_eligible: bool = False


@dataclass
class TurnRecord:
    """One completed turn and any safely restorable tool activity."""

    user_input: str
    assistant_output: str
    turn_id: int = 0
    timestamp: str = ""
    persist_target: str = "chroma"
    log_path: str | None = None
    tool_activities: tuple[ToolActivityRecord, ...] = ()

    def to_messages(self) -> list[BaseMessage]:
        msgs: list[BaseMessage] = [HumanMessage(content=self.user_input)]
        eligible: list[tuple[ToolActivityRecord, dict]] = []
        seen_ids: set[str] = set()
        for activity in self.tool_activities:
            call_id = activity.call_id
            if not activity.prompt_eligible or not call_id or call_id in seen_ids:
                continue
            try:
                arguments = json.loads(activity.arguments)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(arguments, dict):
                continue
            seen_ids.add(call_id)
            eligible.append((activity, arguments))
        if eligible:
            msgs.append(AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": activity.name,
                        "args": arguments,
                        "id": activity.call_id,
                        "type": "tool_call",
                    }
                    for activity, arguments in eligible
                ],
            ))
            msgs.extend(
                ToolMessage(
                    content=activity.result,
                    tool_call_id=activity.call_id or "",
                    name=activity.name,
                    status=(
                        "error"
                        if activity.status in {"failed", "denied"}
                        else "success"
                    ),
                )
                for activity, _arguments in eligible
            )
        if self.assistant_output:
            msgs.append(AIMessage(content=self.assistant_output))
        return msgs


@dataclass(frozen=True)
class CanonicalTurnView:
    """Non-authoritative completed-turn view rebuilt from canonical JSON."""

    user_input: str
    assistant_output: str
    turn_id: int
    logical_turn_id: str
    timestamp: str
    tool_activities: tuple = ()

    def to_messages(self) -> list[BaseMessage]:
        return [
            HumanMessage(content=self.user_input),
            AIMessage(content=self.assistant_output),
        ]


def render_turns(turns: list[TurnRecord]) -> list[BaseMessage]:
    """Flatten turn records into prompt-visible raw messages."""
    out: list[BaseMessage] = []
    for turn in turns:
        out.extend(turn.to_messages())
    return out


def assemble_prompt_history(
    system_prompt: SystemMessage,
    recent_turns: list[TurnRecord],
) -> list[BaseMessage]:
    """Build the long-term prompt history: system prompt followed by raw recent turns."""
    return [system_prompt, *render_turns(recent_turns)]
