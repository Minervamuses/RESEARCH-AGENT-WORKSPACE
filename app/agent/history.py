"""Utilities for tool-call traces."""

from collections import Counter

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage


def extract_tool_calls(messages: list[BaseMessage]) -> list[dict]:
    """Extract normalized tool-call records from AI messages."""
    calls: list[dict] = []
    for message in messages:
        if not isinstance(message, AIMessage) or not message.tool_calls:
            continue
        for tool_call in message.tool_calls:
            if isinstance(tool_call, dict):
                name = tool_call.get("name", "unknown")
                args = tool_call.get("args", {})
                tool_id = tool_call.get("id")
            else:
                name = getattr(tool_call, "name", "unknown")
                args = getattr(tool_call, "args", {}) or {}
                tool_id = getattr(tool_call, "id", None)
            calls.append({
                "id": tool_id,
                "name": name,
                "args": args,
            })
    return calls


def format_tool_counts(tool_calls: list[dict]) -> str:
    """Render compact per-tool counts for logs and notes."""
    counts = Counter(call["name"] for call in tool_calls if call.get("name"))
    if not counts:
        return ""
    return ", ".join(f"{name} x{counts[name]}" for name in sorted(counts))


def group_tool_messages_by_call_id(messages: list[BaseMessage]) -> dict[str, list[ToolMessage]]:
    """Group ToolMessages by tool_call_id, preserving arrival order."""
    tool_messages: dict[str, list[ToolMessage]] = {}
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        call_id = getattr(message, "tool_call_id", None)
        if call_id:
            tool_messages.setdefault(str(call_id), []).append(message)
    return tool_messages
