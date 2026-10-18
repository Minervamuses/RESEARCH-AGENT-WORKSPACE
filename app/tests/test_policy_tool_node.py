"""Tests for effective-tool-set enforcement at the tool execution layer."""

import asyncio

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import START, StateGraph

from agent.tools.policy_node import PolicyToolNode
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


def test_operation_approvals_follow_admission_and_preserve_mixed_batch_order():
    executed = []
    requested = []

    @tool("write_candidate")
    def write_candidate(text: str) -> str:
        """Save a candidate in the test workspace."""
        executed.append(text)
        return f"saved {text}"

    active_approvals = 0

    async def approve(name, args):
        nonlocal active_approvals
        active_approvals += 1
        assert active_approvals == 1
        requested.append((name, args))
        await asyncio.sleep(0)
        active_approvals -= 1
        return args["text"] != "denied"

    calls = [
        _tool_call("write_candidate", "first", {"text": "first"}),
        _tool_call("bash", "unavailable", {"command": "never"}),
        _tool_call("write_candidate", "rejected", {"text": "denied"}),
        _tool_call("not_installed", "missing", {"text": "missing"}),
        _tool_call("write_candidate", "last", {"text": "last"}),
    ]
    node = PolicyToolNode(
        [write_candidate, _bash],
        default_tool_names=["write_candidate"],
        operation_approval_handler=approve,
    )
    graph = StateGraph(AgentState)
    graph.add_node("tools", node)
    graph.add_edge(START, "tools")
    result = asyncio.run(graph.compile().ainvoke({
        "messages": [AIMessage(content="", tool_calls=calls)],
        "effective_tools": ["write_candidate", "not_installed"],
    }))

    assert requested == [
        ("write_candidate", {"text": "first"}),
        ("write_candidate", {"text": "denied"}),
        ("write_candidate", {"text": "last"}),
    ]
    assert sorted(executed) == ["first", "last"]
    messages = result["messages"][-len(calls):]
    assert [message.tool_call_id for message in messages] == [call["id"] for call in calls]
    assert [message.status for message in messages] == ["success", "error", "error", "error", "success"]
    assert "operation denied by user" in messages[2].content
    assert "tool not available" in messages[1].content
    assert "tool not available" in messages[3].content


def test_sync_operation_approval_fails_closed_inside_running_event_loop():
    created_awaitables = []

    async def consent():
        return True

    def approve(_name, _args):
        created_awaitables.append(True)
        return consent()

    node = PolicyToolNode(
        [_echo], default_tool_names=["echo"], operation_approval_handler=approve,
    )

    async def invoke_sync():
        return node.invoke({"messages": [AIMessage(content="", tool_calls=[
            _tool_call("echo", "sync", {"text": "never executed"}),
        ])]})

    message = asyncio.run(invoke_sync())["messages"][0]
    assert created_awaitables == []
    assert message.status == "error"
    assert "requires asynchronous execution" in message.content


def test_operation_approval_failure_does_not_execute_tool():
    async def approve(_name, _args):
        raise RuntimeError("approval transport unavailable")

    node = PolicyToolNode(
        [_echo], default_tool_names=["echo"], operation_approval_handler=approve,
    )
    message = asyncio.run(node.ainvoke({"messages": [AIMessage(content="", tool_calls=[
        _tool_call("echo", "failed", {"text": "never executed"}),
    ])]}))["messages"][0]

    assert message.status == "error"
    assert "operation approval failed" in message.content


def test_real_session_factory_wires_operation_consent_to_graph_and_fusion(monkeypatch, tmp_path):
    from langchain_core.messages import HumanMessage

    from agent.config import AgentConfig
    from agent.session import ChatSession
    from agent.startup import SessionStartup

    executed = []
    requested = []

    @tool("mcp_save")
    def mcp_save(text: str) -> str:
        """Record the fake external write."""
        executed.append(text)
        return "saved"

    class Model:
        def __init__(self, *, proposer=False):
            self.proposer = proposer

        def bind_tools(self, _tools):
            return self

        async def ainvoke(self, messages):
            return self.invoke(messages)

        def invoke(self, messages):
            if isinstance(messages[-1], ToolMessage):
                return AIMessage(content="completed")
            calls = [
                _tool_call("mcp_save", "write", {"text": "candidate"}),
            ]
            if self.proposer:
                calls.append(_tool_call("read_file", "read", {"path": "draft.md"}))
            return AIMessage(content="", tool_calls=calls)

    async def startup(_config, *, load_mcp):
        return SessionStartup(
            extra_tools=(mcp_save,), mcp_families={"mcp_save": "web_search"},
            global_mcp_families=frozenset({"web_search"}), loaded_skills=(),
            running_extension_revision=0, extension_startup_diagnostics=(),
        )

    async def approve(name, args):
        requested.append((name, args))
        return False

    monkeypatch.setattr("agent.startup.load_session_startup", startup)
    monkeypatch.setattr(
        "agent.graph.get_chat_model",
        lambda config: Model(proposer=config.llm_model == "fake-model"),
    )
    monkeypatch.setattr("agent.tools.inventory.create_rag_tools", lambda _config: [])

    async def run():
        session = await ChatSession.create(
            AgentConfig(persist_dir=str(tmp_path)),
            operation_approval_handler=approve,
        )
        result = await session.graph.ainvoke({"messages": [HumanMessage(content="save")]})
        assert result["messages"][-2].status == "error"
        assert "operation denied by user" in result["messages"][-2].content
        assert requested == [("mcp_save", {"text": "candidate"})]
        # The same callback reaches Extended, while its unchanged fixed policy
        # rejects the forged MCP call before requesting consent, while the
        # admitted read still passes through the callback.
        proposer = session._fusion._proposer_graph("fake-model")
        result = await proposer.ainvoke({
            "messages": [HumanMessage(content="save")],
            **session._fusion._proposer_read_only_state(),
        })
        assert "tool not available" in result["messages"][-3].content
        assert "operation denied by user" in result["messages"][-2].content

    asyncio.run(run())
    assert requested == [
        ("mcp_save", {"text": "candidate"}),
        ("read_file", {"path": "draft.md"}),
    ]
    assert executed == []
