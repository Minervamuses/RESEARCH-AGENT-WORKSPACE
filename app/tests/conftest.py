"""Shared fakes for app tests.

One canonical copy of the stubs that used to be duplicated per test file:
history store, queued chat model, scripted astream graphs, and the CLI-level
ChatSession stand-in. Divergent behavior between the old copies is kept as
explicit parameters (raise_on_add, record_repr, ...), never silently dropped.
"""

from langchain_core.messages import AIMessage, ToolMessage

from agent.memory import TurnRecord


class FakeHistoryStore:
    """In-memory ChatHistoryStore stand-in recording every add_turn call.

    Each entry keeps the full call payload (record plus keyword metadata) so a
    test can assert on any subset; raise_on_add simulates a store outage.
    """

    def __init__(self, raise_on_add: bool = False):
        self.adds: list[dict] = []
        self.raise_on_add = raise_on_add

    def add_turn(self, turn: TurnRecord, *, session_id: str, turn_id: int, timestamp: str) -> None:
        if self.raise_on_add:
            raise RuntimeError("ollama unavailable")
        self.adds.append(
            {
                "turn": turn,
                "user_input": turn.user_input,
                "assistant_output": turn.assistant_output,
                "session_id": session_id,
                "turn_id": turn_id,
                "timestamp": timestamp,
            }
        )


class QueuedModel:
    """Chat-model stub whose invoke pops the next scripted text response."""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls: list[list] = []

    def invoke(self, messages):
        self.calls.append(messages)
        return AIMessage(content=self.outputs.pop(0))


def answer_updates(text):
    """One agent update carrying a plain assistant answer."""
    return [{"agent": {"messages": [AIMessage(content=text)]}}]


def tool_then_answer_updates(name, args, call_id, result, text):
    """Agent tool call -> tool result -> final answer, as three updates."""
    return [
        {"agent": {"messages": [AIMessage(
            content="",
            tool_calls=[{"name": name, "args": args, "id": call_id}],
        )]}},
        {"tools": {"messages": [ToolMessage(
            content=result, name=name, tool_call_id=call_id,
        )]}},
        {"agent": {"messages": [AIMessage(content=text)]}},
    ]


class AstreamGraph:
    """Compiled-LangGraph stand-in: astream records state and replays updates."""

    def __init__(self, updates, *, on_state=None):
        self.updates = list(updates)
        self.on_state = on_state
        self.states: list[dict] = []

    async def astream(self, state, config=None, stream_mode="updates"):
        self.states.append(state)
        if self.on_state is not None:
            self.on_state(state)
        for update in self.updates:
            yield update


def make_astream_graph(updates=None, *, answer="ok", on_state=None) -> AstreamGraph:
    """Graph stub yielding the given updates (default: one plain answer)."""
    if updates is None:
        updates = answer_updates(answer)
    return AstreamGraph(updates, on_state=on_state)


class FakeChatSession:
    """ChatSession stand-in for CLI-level tests: records turns and flushes."""

    recursion_limit = 32

    def __init__(self, *, turn_result="ok", turn_error=None, record_repr=False,
                 status=None, config=None):
        self.calls: list[str] = []
        self.config = config
        self._turn_result = turn_result
        self._turn_error = turn_error
        self._record_repr = record_repr
        self._status = status

    async def turn(self, user_input: str) -> str:
        self.calls.append(
            f"turn:{user_input!r}" if self._record_repr else f"turn:{user_input}"
        )
        if self._turn_error is not None:
            raise self._turn_error
        return self._turn_result

    def status_snapshot(self) -> dict:
        return dict(self._status or {})

    async def flush_recent_turns(self) -> None:
        self.calls.append("flush")
