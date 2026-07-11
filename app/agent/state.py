"""Agent state definition for LangGraph."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

if TYPE_CHECKING:
    from agent.skills.runtime import SkillRuntime


class AgentState(TypedDict, total=False):
    """State passed between graph nodes. Messages accumulate via add_messages reducer."""

    messages: Annotated[list[BaseMessage], add_messages]
    active_skill: str | None
    skill_root: str | None
    skill_instructions: str | None
    loaded_references: dict[str, str]
    task_mode: str | None
    # The shared tool access resolution's effective tool names for this turn.
    # Absent/None means normal mode: the graph binds its default global tools.
    effective_tools: list[str] | None


def skill_runtime_to_agent_state(runtime: SkillRuntime | None) -> AgentState:
    """Serialize the active-skill slice of a runtime into agent state.

    Returns an empty mapping when no skill is active, so callers inject no
    skill-state keys. The serialized slice never includes ``messages``; it
    carries only skill identity and the resolved effective tool set.
    """
    if runtime is None:
        return {}
    return {
        "active_skill": runtime.name,
        "skill_root": str(runtime.root),
        "skill_instructions": runtime.instructions,
        "loaded_references": dict(runtime.pinned_references),
        "task_mode": runtime.task_mode,
        "effective_tools": list(runtime.tool_access.effective_tools),
    }
