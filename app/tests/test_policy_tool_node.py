"""Tests for effective-tool-set enforcement at the tool execution layer."""

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import START, StateGraph

from agent.policy_tool_node import PolicyToolNode
from agent.state import AgentState


@tool("echo")
def _echo(text: str) -> str:
    """Echo text."""
    return text


@tool("bash")
def _bash(command: str) -> str:
    """Run shell."""
    return command


@tool("citation_workflow")
def _citation_workflow(action: str) -> str:
    """Skill-scoped workflow tool."""
    return f"did {action}"


DEFAULT_NAMES = frozenset({"echo", "bash"})


def _tool_call(name: str, call_id: str, args: dict) -> dict:
    return {
        "name": name,
        "args": args,
        "id": call_id,
        "type": "tool_call",
    }


def _invoke_policy_node(state: dict, *, default_tool_names=DEFAULT_NAMES):
    graph = StateGraph(AgentState)
    graph.add_node("tools", PolicyToolNode(
        [_echo, _bash, _citation_workflow],
        default_tool_names=default_tool_names,
    ))
    graph.add_edge(START, "tools")
    return graph.compile().invoke(state)


def test_default_tool_call_executes_without_effective_tools_state():
    ai_message = AIMessage(
        content="",
        tool_calls=[_tool_call("echo", "call-1", {"text": "ok"})],
    )

    result = _invoke_policy_node({"messages": [ai_message]})

    message = result["messages"][-1]
    assert isinstance(message, ToolMessage)
    assert message.tool_call_id == "call-1"
    assert message.content == "ok"


def test_call_outside_effective_tools_is_denied_with_same_call_id():
    ai_message = AIMessage(
        content="",
        tool_calls=[_tool_call("bash", "call-1", {"command": "ls"})],
    )

    result = _invoke_policy_node({
        "messages": [ai_message],
        "effective_tools": ["echo"],
    })

    message = result["messages"][-1]
    assert isinstance(message, ToolMessage)
    assert message.tool_call_id == "call-1"
    assert message.content == "Tool error: tool not available in the current mode: bash"
    assert message.status == "error"


def test_mixed_allowed_and_denied_calls_preserve_order():
    ai_message = AIMessage(
        content="",
        tool_calls=[
            _tool_call("echo", "call-1", {"text": "ok"}),
            _tool_call("citation_workflow", "call-2", {"action": "search"}),
        ],
    )

    result = _invoke_policy_node({
        "messages": [ai_message],
        "effective_tools": ["echo"],
    })

    messages = result["messages"][-2:]
    assert [message.tool_call_id for message in messages] == ["call-1", "call-2"]
    assert messages[0].content == "ok"
    assert "tool not available" in messages[1].content
    assert messages[1].status == "error"


def test_forged_skill_tool_call_is_denied_in_normal_mode():
    """Execution-layer defense: a fabricated citation_workflow call outside
    the default global tools is rejected, and sibling default calls run."""
    ai_message = AIMessage(
        content="",
        tool_calls=[
            _tool_call("citation_workflow", "call-1", {"action": "search"}),
            _tool_call("echo", "call-2", {"text": "ok"}),
        ],
    )

    result = _invoke_policy_node({"messages": [ai_message]})

    messages = result["messages"][-2:]
    assert [m.tool_call_id for m in messages] == ["call-1", "call-2"]
    assert messages[0].status == "error"
    assert "tool not available" in messages[0].content
    assert messages[1].content == "ok"


def test_skill_tool_call_denied_under_foreign_skill_effective_tools():
    ai_message = AIMessage(
        content="",
        tool_calls=[_tool_call("citation_workflow", "call-1", {"action": "search"})],
    )

    result = _invoke_policy_node({
        "messages": [ai_message],
        "effective_tools": ["echo", "bash"],
    })

    message = result["messages"][-1]
    assert message.status == "error"
    assert "tool not available" in message.content


def test_skill_tool_call_runs_when_effective_tools_grant_it():
    ai_message = AIMessage(
        content="",
        tool_calls=[_tool_call("citation_workflow", "call-1", {"action": "search"})],
    )

    result = _invoke_policy_node({
        "messages": [ai_message],
        "effective_tools": ["echo", "bash", "citation_workflow"],
    })

    message = result["messages"][-1]
    assert isinstance(message, ToolMessage)
    assert message.content == "did search"
