"""ToolNode wrapper enforcing the shared tool access resolution."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Mapping
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.prebuilt import ToolNode


class PolicyToolNode(ToolNode):
    """Delegate to ToolNode, denying calls outside the effective tool set.

    The effective set comes from the same ToolAccessResolution the graph
    bound: ``state["effective_tools"]`` when present (active skill or
    proposer state), otherwise the graph's default global tool names. A
    forged call to a tool outside that set — e.g. a skill-scoped tool from
    normal mode — is answered with an error ToolMessage and never executed.
    Optional desktop operation consent runs only after this admission check.
    """

    def __init__(
        self,
        tools: list,
        *,
        default_tool_names: Iterable[str],
        operation_approval_handler: Callable[[str, dict], Awaitable[bool]] | None = None,
        **tool_node_kwargs: Any,
    ):
        super().__init__(tools, **tool_node_kwargs)
        self._default_tool_names = frozenset(default_tool_names)
        self._operation_approval_handler = operation_approval_handler

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
        decision = self._partition(input)
        if decision is None:
            return super().invoke(input, config=config, **kwargs)
        allowed_input, denied_messages, call_order = decision
        if allowed_input is None:
            return {"messages": denied_messages}
        if self._operation_approval_handler is not None:
            # Desktop approval needs its running event loop. Never create an
            # unawaited coroutine or bypass consent through the sync entrypoint.
            for call in allowed_input["messages"][-1].tool_calls:
                denied_messages.append(_denied_message(
                    call,
                    "operation approval requires asynchronous execution",
                ))
            return {"messages": _merge_tool_messages(call_order, denied_messages, {})}
        allowed_result = super().invoke(allowed_input, config=config, **kwargs)
        return {"messages": _merge_tool_messages(call_order, denied_messages, allowed_result)}

    async def ainvoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
        decision = self._partition(input)
        if decision is None:
            return await super().ainvoke(input, config=config, **kwargs)
        allowed_input, denied_messages, call_order = decision
        if allowed_input is None:
            return {"messages": denied_messages}
        if self._operation_approval_handler is not None:
            approved_calls = []
            # One pending desktop request at a time, even if the model emits
            # several tool calls in one response. ToolNode may execute approved
            # calls concurrently only after their individual consent resolves.
            for call in allowed_input["messages"][-1].tool_calls:
                try:
                    approved = await self._operation_approval_handler(
                        call["name"], dict(call.get("args") or {}),
                    )
                except Exception:
                    denied_messages.append(_denied_message(call, "operation approval failed"))
                    continue
                if approved:
                    approved_calls.append(call)
                else:
                    denied_messages.append(_denied_message(call, "operation denied by user"))
            if not approved_calls:
                return {"messages": _merge_tool_messages(call_order, denied_messages, {})}
            allowed_input = _with_tool_calls(allowed_input, approved_calls)
        allowed_result = await super().ainvoke(allowed_input, config=config, **kwargs)
        return {"messages": _merge_tool_messages(call_order, denied_messages, allowed_result)}

    def _effective_names(self, input: Mapping) -> frozenset[str]:
        effective = input.get("effective_tools")
        if effective is None:
            return self._default_tool_names
        return frozenset(effective)

    def _partition(self, input: Any):
        if not isinstance(input, Mapping):
            return None

        messages = input.get("messages") or []
        if not messages:
            return None
        last_message = messages[-1]
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return None

        effective_names = self._effective_names(input)
        allowed_calls: list[dict] = []
        denied_messages: list[ToolMessage] = []
        call_order: list[str] = []
        for call in last_message.tool_calls:
            name = call.get("name", "")
            call_id = call.get("id", "")
            call_order.append(call_id)
            if name in effective_names and name in self.tools_by_name:
                allowed_calls.append(call)
            else:
                denied_messages.append(_denied_message(
                    call, "tool not available in the current mode",
                ))

        if not denied_messages and self._operation_approval_handler is None:
            return None

        if not allowed_calls:
            return None, denied_messages, call_order

        return _with_tool_calls(input, allowed_calls), denied_messages, call_order


def _denied_message(call: dict, reason: str) -> ToolMessage:
    return ToolMessage(
        content=f"Tool error: {reason}: {call.get('name', '')}",
        tool_call_id=call.get("id", ""),
        name=call.get("name", ""),
        status="error",
    )


def _with_tool_calls(input: Mapping, calls: list[dict]) -> dict:
    messages = input["messages"]
    filtered_input = dict(input)
    filtered_input["messages"] = [
        *messages[:-1], messages[-1].model_copy(update={"tool_calls": calls}),
    ]
    return filtered_input


def _merge_tool_messages(
    call_order: list[str],
    denied_messages: list[ToolMessage],
    allowed_result: Any,
) -> list[ToolMessage]:
    messages_by_id: dict[str, ToolMessage] = {
        message.tool_call_id: message
        for message in denied_messages
    }
    if isinstance(allowed_result, Mapping):
        for message in allowed_result.get("messages", []):
            if isinstance(message, ToolMessage):
                messages_by_id[message.tool_call_id] = message
    return [
        messages_by_id[call_id]
        for call_id in call_order
        if call_id in messages_by_id
    ]
