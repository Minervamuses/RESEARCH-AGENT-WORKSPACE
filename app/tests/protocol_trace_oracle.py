"""Fixture-only oracle for request correlation, event order, and terminal results.

Production code does not run this: the desktop server enforces one terminal
result per request, Rust checks event sequences, and the TS client compares
logical identifiers. The shared trace fixtures use it to state the expected
ordering and correlation rules for the protocol.
"""

from __future__ import annotations

from typing import Any

from agent.desktop.protocol import (
    ProtocolError,
    _validate_turn_error_details as validate_turn_error_details,
    validate_result_data,
)

DURABLE_TURN_METHODS = frozenset({"session.turn", "extensions.apply"})


def _reject(message: str) -> None:
    raise ProtocolError("PROTOCOL_INVALID", message)


class TraceValidator:
    """Validate request correlation, event order, and terminal results."""

    def __init__(self) -> None:
        self._requests: dict[str, dict[str, int | bool | str | None]] = {}

    def accept(self, message: dict[str, Any]) -> None:
        message_type = message["messageType"]
        if message_type == "request":
            request_id = message["requestId"]
            if request_id in self._requests:
                _reject(f"Duplicate requestId: {request_id}")
            self._requests[request_id] = {
                "nextSequence": 1,
                "terminal": False,
                "method": message["method"],
                "turnId": (
                    message["params"]["turnId"]
                    if message["method"] in DURABLE_TURN_METHODS or message["method"] == "session.stop"
                    else None
                ),
                "sessionId": message["params"].get("sessionId") if message["method"] == "session.stop" else None,
            }
            return
        if message_type == "event" and "requestId" in message:
            request_id = message["requestId"]
            state = self._requests.get(request_id)
            if state is None:
                _reject(f"Event references unknown requestId: {request_id}")
            if state["terminal"]:
                _reject(f"Event arrived after terminal result: {request_id}")
            if message["sequence"] != state["nextSequence"]:
                _reject(
                    f"Expected sequence {state['nextSequence']}, "
                    f"received {message['sequence']}"
                )
            if message["event"] in {"document.proposed", "turn.accepted"} and (
                state["method"] != "session.turn"
                or message["data"]["turnId"] != state["turnId"]
            ):
                _reject(f"{message['event']} must match the active session.turn")
            state["nextSequence"] = int(state["nextSequence"]) + 1
            return
        if message_type == "result":
            request_id = message["requestId"]
            state = self._requests.get(request_id)
            if state is None:
                _reject(f"Result references unknown requestId: {request_id}")
            if state["terminal"]:
                _reject(f"Duplicate terminal result: {request_id}")
            if message["ok"]:
                validate_result_data(str(state["method"]), message["data"])
                expected_turn_id = state["turnId"]
                if (
                    expected_turn_id is not None
                    and message["data"].get("turnId") != expected_turn_id
                ):
                    _reject("data.turnId must match params.turnId")
                if state["method"] == "session.stop" and message["data"]["sessionId"] != state["sessionId"]:
                    _reject("data.sessionId must match params.sessionId")
            elif state["method"] in DURABLE_TURN_METHODS:
                details = message["error"]["details"]
                validate_turn_error_details(details)
                if details["turnId"] != state["turnId"]:
                    _reject("error.details.turnId must match params.turnId")
            state["terminal"] = True
