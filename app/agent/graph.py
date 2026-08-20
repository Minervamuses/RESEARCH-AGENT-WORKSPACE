"""LangGraph agent graph for conversational RAG."""

from __future__ import annotations

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from agent.config import AgentConfig

from agent.llm.openrouter import get_chat_model
from agent.observability import (
    log_model_response,
    log_recovery_fallback,
)
from agent.tools.policy_node import PolicyToolNode
from agent.state import AgentState, skill_runtime_to_agent_state
from agent.tools.access import resolve_tool_access
from agent.tools import inventory as tool_inventory
from agent.turns.safety import (
    build_empty_upstream_message,
    build_recovery_message,
    content_text,
    find_content_tool_protocol_artifact,
    final_response_problem,
    has_tool_results,
    last_user_text,
)


# Immediate same-request retries after a truly empty upstream reply, before
# the recovery ladder is even considered.
_EMPTY_RESPONSE_RETRY_LIMIT = 2


def _is_empty_model_response(message: AIMessage) -> bool:
    """A reply with no text, no tool calls, and no malformed tool calls.

    This is upstream flakiness (typically a lone EOS token), not a reasoning
    failure: structured or malformed tool responses are excluded so they keep
    flowing through the normal tool or recovery paths.
    """
    return (
        not (getattr(message, "tool_calls", None) or [])
        and not (getattr(message, "invalid_tool_calls", None) or [])
        and not content_text(message.content).strip()
    )


def _strip_tool_calls(message: AIMessage) -> tuple[AIMessage, int]:
    """Remove structured tool calls from a response that must be tool-free."""
    tool_calls = list(getattr(message, "tool_calls", None) or [])
    if not tool_calls:
        return message, 0
    return message.model_copy(update={
        "additional_kwargs": {
            key: value
            for key, value in message.additional_kwargs.items()
            if key != "tool_calls"
        },
        "tool_calls": [],
    }), len(tool_calls)


_REPAIR_INSTRUCTION = SystemMessage(content=(
    "[Response repair]\nYour previous response could not be shown because it "
    "was empty or contained an unexecuted tool-call protocol. Using only the "
    "evidence and tool results already present above, write the final user-facing "
    "answer now. Do not call or describe a tool invocation. If evidence is "
    "insufficient, state that plainly. Return only the answer."
))

_GRAPH_LIMIT_FINALIZATION_INSTRUCTION = SystemMessage(content=(
    "[Graph limit]\nThe graph is near its emergency superstep limit. Using only "
    "the context and completed tool results already available, write the best "
    "user-facing final answer now. Do not call or describe a tool invocation. "
    "If the evidence is insufficient, state that plainly. Return only the answer."
))


def _with_recovery_metadata(message: AIMessage, reason: str) -> AIMessage:
    metadata = dict(message.response_metadata or {})
    metadata["turn_recovery"] = reason
    return AIMessage(
        content=message.content,
        additional_kwargs=dict(message.additional_kwargs or {}),
        response_metadata=metadata,
        tool_calls=list(getattr(message, "tool_calls", None) or []),
    )


def build_graph(
    config: AgentConfig,
    extra_tools: list | None = None,
    history_store=None,
    skill_runtime_getter=None,
    skill_tools: list | None = None,
    mcp_families: dict[str, str] | None = None,
    global_mcp_families: set[str] | frozenset[str] | None = None,
):
    """Build and compile the conversational RAG agent graph.

    Args:
        config: Agent configuration.
        extra_tools: Optional additional LangChain-compatible tools (e.g. MCP
            tools loaded at startup) appended after the local agent tools.
        history_store: Optional store injected into the recall_history tool.
        skill_runtime_getter: Optional callable returning the active SkillRuntime.
        skill_tools: Optional skill-scoped tools. They join the executable tool
            universe but are bound/callable only while the active skill's
            manifest requests them — never in normal mode. A name collision
            with a base tool fails fast.
        mcp_families: MCP tool-name to family map. Tools in the ``web_search``
            family are global; other families are skill-scoped.

    Returns:
        A compiled LangGraph that accepts AgentState and manages
        the agent ↔ tools loop for a single graph invocation.
    """
    model = get_chat_model(config)
    base_tools = tool_inventory.build_base_tools(
        config,
        history_store=history_store,
        extra_tools=extra_tools,
    )
    skill_tools = list(skill_tools or [])
    base_names = [getattr(tool, "name", str(tool)) for tool in base_tools]
    skill_tool_names = frozenset(
        getattr(tool, "name", str(tool)) for tool in skill_tools
    )
    conflicts = skill_tool_names.intersection(base_names)
    if conflicts:
        raise ValueError(
            "skill tool names collide with default tools: "
            + ", ".join(sorted(conflicts))
        )
    tools = [*base_tools, *skill_tools]
    tools_by_name = {getattr(tool, "name", str(tool)): tool for tool in tools}
    tool_order = [getattr(tool, "name", str(tool)) for tool in tools]
    # The normal-mode default binding: global tools only (local base tools
    # plus web_search-family MCP tools) — never skill-scoped tools.
    default_names = resolve_tool_access(
        None,
        tools,
        mcp_families=mcp_families or {},
        global_mcp_families=global_mcp_families,
    ).effective_tools
    default_tools = [tools_by_name[name] for name in default_names]
    bound_model_cache = {default_names: model.bind_tools(default_tools)}

    def _effective_names(state: AgentState) -> tuple[str, ...]:
        effective = state.get("effective_tools")
        if effective is None:
            return default_names
        selected = set(effective)
        return tuple(name for name in tool_order if name in selected)

    def _model_for_state(state: AgentState):
        key = _effective_names(state)
        if key not in bound_model_cache:
            bound_model_cache[key] = model.bind_tools(
                [tools_by_name[name] for name in key]
            )
        return bound_model_cache[key]

    def agent_node(state: AgentState):
        messages = state["messages"]
        tool_names = _effective_names(state)
        graph_steps_remaining = int(state["remaining_steps"])
        force_final = graph_steps_remaining < 3
        prompt_messages = [
            *messages,
            *([_GRAPH_LIMIT_FINALIZATION_INSTRUCTION] if force_final else []),
        ]
        invoke_model = model if force_final else _model_for_state(state)
        response = invoke_model.invoke(prompt_messages)
        # A truly empty reply is upstream flakiness: retry the identical
        # request instead of entering the recovery ladder, whose no-tool
        # repair stage cannot finish tool work and must never invent it.
        empty_attempts = 0
        while (
            _is_empty_model_response(response)
            and empty_attempts < _EMPTY_RESPONSE_RETRY_LIMIT
        ):
            empty_attempts += 1
            log_model_response(
                response,
                stage=(
                    "initial" if empty_attempts == 1
                    else f"empty_retry_{empty_attempts - 1}"
                ),
                issue="empty_model_response",
                dropped_tool_calls=0,
                graph_steps_remaining=graph_steps_remaining,
                messages=messages,
            )
            response = invoke_model.invoke(prompt_messages)
        if _is_empty_model_response(response):
            log_model_response(
                response,
                stage=f"empty_retry_{empty_attempts}",
                issue="empty_model_response",
                dropped_tool_calls=0,
                graph_steps_remaining=graph_steps_remaining,
                messages=messages,
            )
            log_recovery_fallback(
                issue="empty_model_response",
                repair_issue="empty_retries_exhausted",
                graph_steps_remaining=graph_steps_remaining,
                messages=messages,
            )
            return {"messages": [AIMessage(
                content=build_empty_upstream_message(
                    user_input=last_user_text(messages),
                    had_tool_results=has_tool_results(messages),
                ),
                response_metadata={
                    "turn_recovery": "fallback:empty_model_response",
                },
            )]}
        dropped = 0
        if force_final:
            response, dropped = _strip_tool_calls(response)
        if response.tool_calls:
            log_model_response(
                response,
                stage="initial",
                issue=None,
                dropped_tool_calls=0,
                graph_steps_remaining=graph_steps_remaining,
                messages=messages,
            )
            return {"messages": [response]}

        issue = find_content_tool_protocol_artifact(
            response.content,
            tool_names=tool_names,
        ) or final_response_problem(
            content_text(response.content),
            tool_names=tool_names,
            dropped_tool_calls=dropped > 0,
        )
        log_model_response(
            response,
            stage="initial",
            issue=issue,
            dropped_tool_calls=dropped,
            graph_steps_remaining=graph_steps_remaining,
            messages=messages,
        )
        if issue is None:
            if force_final:
                response = _with_recovery_metadata(
                    response, "finalized:graph_recursion_limit"
                )
            return {"messages": [response]}

        repaired = model.invoke([*prompt_messages, _REPAIR_INSTRUCTION])
        repaired, repair_dropped = _strip_tool_calls(repaired)
        repair_issue = find_content_tool_protocol_artifact(
            repaired.content,
            tool_names=tool_names,
        ) or final_response_problem(
            content_text(repaired.content),
            tool_names=tool_names,
            dropped_tool_calls=repair_dropped > 0,
        )
        log_model_response(
            repaired,
            stage="repair",
            issue=repair_issue,
            dropped_tool_calls=repair_dropped,
            graph_steps_remaining=graph_steps_remaining,
            messages=messages,
        )
        if repair_issue is None and not repaired.tool_calls:
            recovery_reason = f"repaired:{issue}"
            if force_final:
                recovery_reason = f"repaired:graph_recursion_limit:{issue}"
            return {"messages": [
                _with_recovery_metadata(repaired, recovery_reason)
            ]}

        log_recovery_fallback(
            issue=issue,
            repair_issue=repair_issue,
            graph_steps_remaining=graph_steps_remaining,
            messages=messages,
        )
        fallback = build_recovery_message(
            user_input=last_user_text(messages),
            had_tool_results=has_tool_results(messages),
        )
        return {"messages": [AIMessage(
            content=fallback,
            response_metadata={
                "turn_recovery": (
                    f"fallback:graph_recursion_limit:{issue};repair:{repair_issue}"
                    if force_final
                    else f"fallback:{issue};repair:{repair_issue}"
                )
            },
        )]}

    def _tool_error_to_message(exc: Exception) -> str:
        return f"Tool error: {type(exc).__name__}: {exc}"

    def skill_loader_node(state: AgentState):
        if state.get("skill_instructions"):
            return {}
        if skill_runtime_getter is None:
            return {}
        return skill_runtime_to_agent_state(skill_runtime_getter())

    def route_after_agent(state: AgentState):
        messages = state.get("messages") or []
        last_message = messages[-1] if messages else None
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("skill_loader", skill_loader_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", PolicyToolNode(
        tools,
        default_tool_names=default_names,
        handle_tool_errors=_tool_error_to_message,
    ))

    graph.add_edge(START, "skill_loader")
    graph.add_edge("skill_loader", "agent")
    graph.add_conditional_edges("agent", route_after_agent)
    graph.add_edge("tools", "agent")

    return graph.compile()
