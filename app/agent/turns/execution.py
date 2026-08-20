"""Stateless execution of one LangGraph turn."""

from __future__ import annotations

from collections.abc import Callable

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent.turns.results import GraphTurnResult
from agent.turns.safety import content_text
from agent.turns.trace import extract_tool_calls

ProgressCallback = Callable[[str, list], None]


async def execute_graph(
    *,
    graph,
    user_input: str,
    prompt_history: list,
    skill_state: dict,
    graph_recursion_limit: int,
    extra_system_messages: list[SystemMessage] | None = None,
    candidate_id: str | None = None,
    progress_cb: ProgressCallback | None = None,
) -> GraphTurnResult:
    """Run one graph and normalize its messages, calls, and recovery metadata."""
    input_messages = [
        *prompt_history,
        *(extra_system_messages or []),
        HumanMessage(content=user_input),
    ]
    messages: list = list(input_messages)
    initial_state = {
        "messages": input_messages,
        **skill_state,
    }
    async for update in graph.astream(
        initial_state,
        config={"recursion_limit": graph_recursion_limit},
        stream_mode="updates",
    ):
        for node_name, delta in update.items():
            new_msgs = delta.get("messages", []) if isinstance(delta, dict) else []
            messages.extend(new_msgs)
            if progress_cb is not None:
                progress_cb(node_name, new_msgs)

    new_messages = messages[len(input_messages):]
    tool_calls = extract_tool_calls(new_messages)
    if candidate_id is not None:
        tool_calls = [{**call, "candidate_id": candidate_id} for call in tool_calls]
    trace_events = [
        {
            "type": "tool",
            "name": call["name"],
            "args": call["args"],
            "id": call.get("id"),
            **({"candidate_id": candidate_id} if candidate_id is not None else {}),
        }
        for call in tool_calls
    ]
    answer = content_text(messages[-1].content) if messages else ""
    last_ai = next(
        (
            message
            for message in reversed(new_messages)
            if isinstance(message, AIMessage)
        ),
        None,
    )
    recovery_reason = None
    if last_ai is not None:
        recovery_reason = (last_ai.response_metadata or {}).get("turn_recovery")

    return GraphTurnResult(
        answer=answer,
        new_messages=new_messages,
        tool_calls=tool_calls,
        trace_events=trace_events,
        recovery_reason=recovery_reason,
    )
