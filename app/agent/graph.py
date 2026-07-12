"""LangGraph agent graph for conversational RAG."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from skills.citation.types import CONFIRM_BATCH_KIND

from agent.config import AgentConfig

from agent.llm.openrouter import get_chat_model
from agent.observability import (
    last_completed_citation_action,
    log_model_response,
    log_recovery_fallback,
)
from agent.policy_tool_node import PolicyToolNode
from agent.state import AgentState, skill_runtime_to_agent_state
from agent.tool_access import resolve_tool_access
from agent.tools import inventory as tool_inventory
from agent.turn_safety import (
    build_recovery_message,
    content_text,
    find_content_tool_protocol_artifact,
    final_response_problem,
    has_tool_results,
    last_user_text,
)


_LOCAL_CITATION_ACTIONS = frozenset({
    "list", "show", "status", "explain", "sources", "source", "refine",
    "cancel",
})


@dataclass(frozen=True)
class _BudgetUsage:
    primary: int = 0
    local: int = 0


def _tool_call_parts(tool_call) -> tuple[str, dict, str | None]:
    if isinstance(tool_call, dict):
        raw_args = tool_call.get("args", {})
        return (
            str(tool_call.get("name", "unknown")),
            raw_args if isinstance(raw_args, dict) else {},
            tool_call.get("id"),
        )
    return (
        str(getattr(tool_call, "name", "unknown")),
        getattr(tool_call, "args", {}) or {},
        getattr(tool_call, "id", None),
    )


def _budget_class(tool_name: str, args: dict) -> str:
    if tool_name != "citation_workflow":
        return "primary"
    action = args.get("action")
    return "local" if action in _LOCAL_CITATION_ACTIONS else "primary"


def _tool_budget_usage(messages: list) -> _BudgetUsage:
    """Count completed primary/local calls by matching call ids to results."""
    classes_by_id: dict[str, str] = {}
    for message in messages:
        if not isinstance(message, AIMessage):
            continue
        for tool_call in getattr(message, "tool_calls", None) or []:
            name, args, tool_id = _tool_call_parts(tool_call)
            if tool_id:
                classes_by_id[str(tool_id)] = _budget_class(name, args)

    primary = local = 0
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        tool_id = getattr(message, "tool_call_id", None)
        category = classes_by_id.get(str(tool_id), "primary")
        if category == "local":
            local += 1
        else:
            primary += 1
    return _BudgetUsage(primary=primary, local=local)


def _cap_tool_calls(
    message: AIMessage,
    *,
    primary_remaining: int,
    local_remaining: int,
) -> tuple[AIMessage, int]:
    """Trim parallel calls independently against primary and local budgets.

    The tool budget is checked once before each round, so a round that emits
    several parallel tool calls could push the per-turn tool count past the
    limits. Preserve emission order and keep a call only while its category
    has room; dropped calls are never committed to history.
    """
    tool_calls = list(getattr(message, "tool_calls", None) or [])
    if not tool_calls:
        return message, 0
    kept = []
    primary_used = local_used = 0
    for tool_call in tool_calls:
        name, args, _tool_id = _tool_call_parts(tool_call)
        category = _budget_class(name, args)
        if category == "local":
            if local_used >= max(local_remaining, 0):
                continue
            local_used += 1
        else:
            if primary_used >= max(primary_remaining, 0):
                continue
            primary_used += 1
        kept.append(tool_call)
    dropped = len(tool_calls) - len(kept)
    if not dropped:
        return message, 0
    return AIMessage(
        content=message.content,
        additional_kwargs={
            key: value
            for key, value in message.additional_kwargs.items()
            if key != "tool_calls"
        },
        response_metadata=message.response_metadata,
        tool_calls=kept,
    ), dropped


def _tool_budget_note(
    *, primary_used: int, primary_limit: int, local_used: int, local_limit: int
) -> SystemMessage:
    primary_exhausted = primary_used >= primary_limit
    local_exhausted = local_used >= local_limit
    content = (
        "[Tool budgets]\n"
        f"Primary/external tool results: {primary_used}/{primary_limit}. "
        f"Local citation navigation results: {local_used}/{local_limit}. "
    )
    if primary_exhausted:
        content += "Do not request another primary/external operation. "
    if local_exhausted:
        content += "Do not request another local citation navigation operation. "
    if primary_exhausted and local_exhausted:
        content += (
            "Both budgets are exhausted. Do not call tools again. Synthesize the "
            "best answer from available context and evidence."
        )
    else:
        content += (
            "Use another allowed operation only if necessary; otherwise synthesize "
            "the answer now."
        )
    return SystemMessage(content=content)


_CONTINUATION_INSTRUCTION = SystemMessage(content=(
    "[Continuation]\nYour previous response was empty or contained a "
    "malformed tool call while the citation workflow sits between select "
    "and confirm. Continue from the most recent tool result; do not repeat "
    "operations that already completed (no new search or re-select). If the "
    "user's current request authorizes saving, call citation_workflow with "
    "action='confirm' and the pending match id(s) now; otherwise present "
    "the pending matches and ask. Remaining tool budgets still apply."
))

_REPAIR_INSTRUCTION = SystemMessage(content=(
    "[Response repair]\nYour previous response could not be shown because it "
    "was empty or contained an unexecuted tool-call protocol. Using only the "
    "evidence and tool results already present above, write the final user-facing "
    "answer now. Do not call or describe a tool invocation. If evidence is "
    "insufficient, state that plainly. Return only the answer."
))


def _has_confirm_batch_artifact(messages: list) -> bool:
    """Whether any citation confirm receipts already exist in this turn."""
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        if getattr(message, "name", None) != "citation_workflow":
            continue
        artifact = getattr(message, "artifact", None)
        if isinstance(artifact, Mapping) and artifact.get("kind") == CONFIRM_BATCH_KIND:
            return True
    return False


def _between_select_and_confirm(messages: list) -> bool:
    """A select completed, and no confirm receipts exist yet, in this turn."""
    return (
        last_completed_citation_action(messages) == "select"
        and not _has_confirm_batch_artifact(messages)
    )


def _continuation_attempted(messages: list) -> bool:
    """Whether this turn already spent its single tool-capable continuation."""
    return any(
        isinstance(message, AIMessage)
        and str(
            (message.response_metadata or {}).get("turn_recovery", "")
        ).startswith("continuation:")
        for message in messages
    )


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
        the bounded agent ↔ tools loop for a single turn.
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
        usage = _tool_budget_usage(messages)
        primary_limit = max(int(config.agent_max_tool_interactions), 0)
        local_limit = (
            max(int(config.agent_max_local_tool_interactions), 0)
            if "citation_workflow" in tool_names
            else 0
        )
        primary_exhausted = usage.primary >= primary_limit
        local_exhausted = usage.local >= local_limit
        prompt_messages = [
            *messages,
            _tool_budget_note(
                primary_used=usage.primary,
                primary_limit=primary_limit,
                local_used=usage.local,
                local_limit=local_limit,
            ),
        ]
        if primary_exhausted and local_exhausted:
            response = model.invoke(prompt_messages)
        else:
            response = _model_for_state(state).invoke(prompt_messages)
        primary_remaining = primary_limit - usage.primary
        local_remaining = local_limit - usage.local
        capped, dropped = _cap_tool_calls(
            response,
            primary_remaining=primary_remaining,
            local_remaining=local_remaining,
        )
        if capped.tool_calls:
            log_model_response(
                capped,
                stage="initial",
                issue=None,
                dropped_tool_calls=dropped,
                primary_remaining=primary_remaining,
                local_remaining=local_remaining,
                messages=messages,
            )
            return {"messages": [capped]}

        continuation_window = _between_select_and_confirm(messages)
        issue = find_content_tool_protocol_artifact(
            capped.content,
            tool_names=tool_names,
        ) or final_response_problem(
            content_text(capped.content),
            tool_names=tool_names,
            dropped_tool_calls=dropped > 0,
        )
        if (
            issue is None
            and continuation_window
            and getattr(capped, "invalid_tool_calls", None)
        ):
            # A malformed call between select and confirm never completes the
            # save; treat it as a recoverable problem instead of prose.
            issue = "invalid_tool_calls"
        log_model_response(
            capped,
            stage="initial",
            issue=issue,
            dropped_tool_calls=dropped,
            primary_remaining=primary_remaining,
            local_remaining=local_remaining,
            messages=messages,
        )
        if issue is None:
            return {"messages": [capped]}

        if (
            continuation_window
            and primary_remaining > 0
            and not _continuation_attempted(messages)
        ):
            # One tool-capable retry: unlike the no-tool repair below, the
            # bound model may still finish the pending confirm within the
            # remaining budgets. Only a second failure forfeits tool access.
            continued = _model_for_state(state).invoke(
                [*prompt_messages, _CONTINUATION_INSTRUCTION]
            )
            continued, continued_dropped = _cap_tool_calls(
                continued,
                primary_remaining=primary_remaining,
                local_remaining=local_remaining,
            )
            if continued.tool_calls:
                log_model_response(
                    continued,
                    stage="continuation",
                    issue=None,
                    dropped_tool_calls=continued_dropped,
                    primary_remaining=primary_remaining,
                    local_remaining=local_remaining,
                    messages=messages,
                )
                return {"messages": [
                    _with_recovery_metadata(continued, f"continuation:{issue}")
                ]}
            continued_issue = find_content_tool_protocol_artifact(
                continued.content,
                tool_names=tool_names,
            ) or final_response_problem(
                content_text(continued.content),
                tool_names=tool_names,
                dropped_tool_calls=continued_dropped > 0,
            )
            if continued_issue is None and getattr(
                continued, "invalid_tool_calls", None
            ):
                continued_issue = "invalid_tool_calls"
            log_model_response(
                continued,
                stage="continuation",
                issue=continued_issue,
                dropped_tool_calls=continued_dropped,
                primary_remaining=primary_remaining,
                local_remaining=local_remaining,
                messages=messages,
            )
            if continued_issue is None:
                return {"messages": [
                    _with_recovery_metadata(continued, f"continued:{issue}")
                ]}

        repaired = model.invoke([*prompt_messages, _REPAIR_INSTRUCTION])
        repaired, repair_dropped = _cap_tool_calls(
            repaired,
            primary_remaining=0,
            local_remaining=0,
        )
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
            primary_remaining=primary_remaining,
            local_remaining=local_remaining,
            messages=messages,
        )
        if repair_issue is None and not repaired.tool_calls:
            return {"messages": [
                _with_recovery_metadata(repaired, f"repaired:{issue}")
            ]}

        log_recovery_fallback(
            issue=issue,
            repair_issue=repair_issue,
            primary_remaining=primary_remaining,
            local_remaining=local_remaining,
            messages=messages,
        )
        fallback = build_recovery_message(
            user_input=last_user_text(messages),
            had_tool_results=has_tool_results(messages),
        )
        return {"messages": [AIMessage(
            content=fallback,
            response_metadata={
                "turn_recovery": f"fallback:{issue};repair:{repair_issue}"
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
