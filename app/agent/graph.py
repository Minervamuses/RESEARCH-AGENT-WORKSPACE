"""LangGraph agent graph for conversational RAG."""

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from agent.config import AgentConfig

from agent.llm.openrouter import get_chat_model
from agent.policy_tool_node import PolicyToolNode
from agent.state import AgentState, skill_runtime_to_agent_state
from agent.tool_policy import evaluate_policy
from agent.tools import inventory as tool_inventory


def _tool_interaction_count(messages: list) -> int:
    """Count completed tool interactions in the current graph state."""
    return sum(1 for message in messages if isinstance(message, ToolMessage))


def _cap_tool_calls(message: AIMessage, remaining: int) -> AIMessage:
    """Trim parallel tool calls so one round cannot overshoot the budget.

    The tool budget is checked once before each round, so a round that emits
    several parallel tool calls could push the per-turn tool count past the
    limit. Keep only the first ``remaining`` calls; the rest are dropped from
    the message (never committed to history) so the chat protocol stays valid.
    """
    tool_calls = getattr(message, "tool_calls", None)
    if not tool_calls or remaining < 0 or len(tool_calls) <= remaining:
        return message
    return AIMessage(
        content=message.content,
        additional_kwargs={
            key: value
            for key, value in message.additional_kwargs.items()
            if key != "tool_calls"
        },
        response_metadata=message.response_metadata,
        tool_calls=tool_calls[:remaining],
    )


def _tool_budget_note(*, used: int, limit: int, exhausted: bool) -> SystemMessage:
    if exhausted:
        content = (
            "[Tool budget exhausted]\n"
            f"You have already received {used} tool result(s), and this turn's "
            f"tool interaction limit is {limit}. Do not call tools again. "
            "Synthesize the best answer from the available context and evidence. "
            "If the evidence is insufficient, state what is missing instead of searching more."
        )
    else:
        content = (
            "[Tool budget]\n"
            f"You have used {used}/{limit} available tool result(s) in this turn. "
            "Use another tool only if it is necessary; otherwise synthesize an answer now."
        )
    return SystemMessage(content=content)


def build_graph(
    config: AgentConfig,
    extra_tools: list | None = None,
    history_store=None,
    skill_runtime_getter=None,
    skill_tools: list | None = None,
):
    """Build and compile the conversational RAG agent graph.

    Args:
        config: Agent configuration.
        extra_tools: Optional additional LangChain-compatible tools (e.g. MCP
            tools loaded at startup) appended after the local agent tools.
        history_store: Optional store injected into the recall_history tool.
        skill_runtime_getter: Optional callable returning the active SkillRuntime.
        skill_tools: Optional skill-only tools. They join the executable tool
            universe but are bound/callable only while an active skill's
            allowlist grants them — never in normal mode, never via a deny-only
            policy. A name collision with a default tool fails fast.

    Returns:
        A compiled LangGraph that accepts AgentState and manages
        the bounded agent ↔ tools loop for a single turn.
    """
    model = get_chat_model(config)
    default_tools = tool_inventory.build_base_tools(
        config,
        history_store=history_store,
        extra_tools=extra_tools,
    )
    skill_tools = list(skill_tools or [])
    default_names = [getattr(tool, "name", str(tool)) for tool in default_tools]
    skill_only_names = frozenset(
        getattr(tool, "name", str(tool)) for tool in skill_tools
    )
    conflicts = skill_only_names.intersection(default_names)
    if conflicts:
        raise ValueError(
            "skill-only tool names collide with default tools: "
            + ", ".join(sorted(conflicts))
        )
    tools = [*default_tools, *skill_tools]
    tools_by_name = {getattr(tool, "name", str(tool)): tool for tool in tools}
    tool_order = [getattr(tool, "name", str(tool)) for tool in tools]
    # The no-skill default binding never includes skill-only tools.
    bound_model_cache = {
        (None, None, False, (), ()): model.bind_tools(default_tools),
    }

    def _select_tools(state: AgentState) -> list:
        selected_names = evaluate_policy(
            tool_order,
            active=bool(state.get("tool_policy_active")),
            allowed=state.get("allowed_tools") or (),
            denied=state.get("denied_tools") or (),
            skill_only=skill_only_names,
        )
        return [tools_by_name[name] for name in selected_names]

    def _model_for_state(state: AgentState):
        policy_active = bool(state.get("tool_policy_active"))
        allowed = tuple(sorted(state.get("allowed_tools") or []))
        denied = tuple(sorted(state.get("denied_tools") or []))
        key = (
            state.get("active_skill"),
            state.get("task_mode"),
            policy_active,
            allowed,
            denied,
        )
        if key not in bound_model_cache:
            bound_model_cache[key] = model.bind_tools(_select_tools(state))
        return bound_model_cache[key]

    def agent_node(state: AgentState):
        messages = state["messages"]
        tool_count = _tool_interaction_count(messages)
        tool_limit = max(int(config.agent_max_tool_interactions), 0)
        tool_budget_exhausted = tool_count >= tool_limit
        prompt_messages = [
            *messages,
            _tool_budget_note(
                used=tool_count,
                limit=tool_limit,
                exhausted=tool_budget_exhausted,
            ),
        ]
        if tool_budget_exhausted:
            return {"messages": [_cap_tool_calls(model.invoke(prompt_messages), 0)]}
        response = _model_for_state(state).invoke(prompt_messages)
        return {"messages": [_cap_tool_calls(response, tool_limit - tool_count)]}

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
        skill_only_names=skill_only_names,
        handle_tool_errors=_tool_error_to_message,
    ))

    graph.add_edge(START, "skill_loader")
    graph.add_edge("skill_loader", "agent")
    graph.add_conditional_edges("agent", route_after_agent)
    graph.add_edge("tools", "agent")

    return graph.compile()
