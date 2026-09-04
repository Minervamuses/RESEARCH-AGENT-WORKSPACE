"""Legacy turn DTOs and canonical completed-turn prompt views."""

from dataclasses import dataclass
from typing import Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage


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
    """One strict legacy turn before canonical migration."""

    user_input: str
    assistant_output: str
    turn_id: int = 0
    timestamp: str = ""
    tool_activities: tuple[ToolActivityRecord, ...] = ()


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
