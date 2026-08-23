"""Language-neutral desktop protocol v1 fixture checks.

This test-only parser is replaced by ``agent.desktop.protocol`` after the
GUI/05 production-package approval gate.  Keeping it here lets Python verify
the same contract corpus as Rust and TypeScript without starting a backend.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import RFC_4122, UUID

import pytest


PROTOCOL_DIR = Path(__file__).parents[1] / "desktop" / "protocol" / "v1"
CONTRACT = json.loads((PROTOCOL_DIR / "contract.json").read_text(encoding="utf-8"))
FIXTURES = json.loads((PROTOCOL_DIR / "fixtures.json").read_text(encoding="utf-8"))
METHODS = {item["name"]: item for item in CONTRACT["methods"]}


class ProtocolCheckError(ValueError):
    """Stable error code emitted by the temporary fixture checker."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _invalid(message: str) -> None:
    raise ProtocolCheckError("PROTOCOL_INVALID", message)


def _expect_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _invalid(f"{field} must be a JSON object")
    return value


def _expect_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        _invalid(f"{field} must be a non-empty string")
    return value


def _expect_exact_keys(value: dict[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        _invalid(f"{field} contains unknown field: {sorted(unknown)[0]}")


def _json_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _invalid(f"{field} must be an integer")
    if isinstance(value, float) and (not math.isfinite(value) or not value.is_integer()):
        _invalid(f"{field} must be an integer")
    return int(value)


def _validate_request_id(value: Any) -> str:
    request_id = _expect_string(value, "requestId")
    if len(request_id.encode("utf-8")) > CONTRACT["requestIdMaxBytes"]:
        _invalid("requestId is too large")
    try:
        parsed = UUID(request_id)
    except ValueError:
        _invalid("requestId must be a canonical UUID")
    if (
        str(parsed) != request_id.lower()
        or parsed.variant != RFC_4122
        or parsed.version not in range(1, 9)
    ):
        _invalid("requestId must be a canonical UUID")
    return request_id


UTC_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)


def _validate_field_rule(value: Any, rule: dict[str, Any], field: str) -> None:
    field_type = rule["type"]
    if field_type == "string":
        text = _expect_string(value, field)
        if len(text.encode("utf-8")) > rule.get("maxBytes", math.inf):
            _invalid(f"{field} is too large")
        if "enum" in rule and text not in rule["enum"]:
            _invalid(f"{field} contains an unknown enum value: {text}")
        return
    if field_type == "nullableString":
        if value is not None:
            _validate_field_rule(value, {**rule, "type": "string"}, field)
        return
    if field_type == "boolean":
        if not isinstance(value, bool):
            _invalid(f"{field} must be a boolean")
        return
    if field_type == "nullableBoolean":
        if value is not None and not isinstance(value, bool):
            _invalid(f"{field} must be a boolean or null")
        return
    if field_type == "integer":
        integer = _json_integer(value, field)
        if integer < rule.get("minimum", -math.inf):
            _invalid(f"{field} is below its minimum")
        if integer > rule.get("maximum", math.inf):
            _invalid(f"{field} is above its maximum")
        return
    if field_type == "stringArray":
        if not isinstance(value, list):
            _invalid(f"{field} must be an array")
        if len(value) > rule.get("maxItems", math.inf):
            _invalid(f"{field} contains too many items")
        for index, item in enumerate(value):
            text = _expect_string(item, f"{field}[{index}]")
            if len(text.encode("utf-8")) > rule.get("itemMaxBytes", math.inf):
                _invalid(f"{field}[{index}] is too large")
        return
    if field_type == "objectArray":
        if not isinstance(value, list):
            _invalid(f"{field} must be an array")
        if len(value) > rule.get("maxItems", math.inf):
            _invalid(f"{field} contains too many items")
        schema = rule.get("items")
        if not isinstance(schema, dict):
            _invalid(f"{field} is missing its item schema")
        for index, item in enumerate(value):
            _validate_object_schema(
                _expect_object(item, f"{field}[{index}]"),
                schema,
                f"{field}[{index}]",
            )
        return
    if field_type == "requestId":
        _validate_request_id(value)
        return
    timestamp = _expect_string(value, field)
    if not UTC_TIMESTAMP.fullmatch(timestamp):
        _invalid(f"{field} must be a UTC ISO 8601 timestamp")
    try:
        datetime.fromisoformat(timestamp.removesuffix("Z") + "+00:00")
    except ValueError:
        _invalid(f"{field} must be a UTC ISO 8601 timestamp")


def _validate_object_schema(
    value: dict[str, Any], schema: dict[str, dict[str, Any]], field: str
) -> None:
    _expect_exact_keys(value, set(schema), field)
    for name, rule in schema.items():
        if name not in value:
            if rule["required"]:
                _invalid(f"{field}.{name} is required")
            continue
        _validate_field_rule(value[name], rule, f"{field}.{name}")


def _validate_params(method: str, params: dict[str, Any]) -> None:
    _validate_object_schema(params, METHODS[method]["params"], "params")


def _normalize_data_key(key: str) -> str:
    return "".join(
        character
        for character in key.lower()
        if character.isascii() and character.isalnum()
    )


def _validate_safe_data(value: Any, field: str) -> None:
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_safe_data(item, f"{field}[{index}]")
        return
    if not isinstance(value, dict):
        return
    for key, item in value.items():
        normalized = _normalize_data_key(key)
        if any(
            fragment in normalized
            for fragment in CONTRACT["forbiddenDataKeyFragments"]
        ):
            _invalid(f"{field} contains forbidden field: {key}")
        _validate_safe_data(item, f"{field}.{key}")


def _validate_tool_event(event: str, data: dict[str, Any]) -> None:
    if not event.startswith("tool."):
        return
    _expect_exact_keys(data, set(CONTRACT["toolEventDataKeys"]), "data")
    _expect_string(data.get("name"), "data.name")
    status = _expect_string(data.get("status"), "data.status")
    if status not in CONTRACT["toolStatuses"]:
        _invalid(f"Unknown tool status: {status}")
    for optional in ("callId", "candidateId"):
        if optional in data:
            _expect_string(data[optional], f"data.{optional}")


def _validate_event_data(
    event: str, request_id: str, data: dict[str, Any]
) -> None:
    _validate_tool_event(event, data)
    schema = CONTRACT["eventDataSchemas"].get(event)
    if schema is not None:
        _validate_object_schema(data, schema, "data")
    if event == "approval.required" and data["parentRequestId"] != request_id:
        _invalid("data.parentRequestId must match the event requestId")


def _validate_result_data(method: str, data: dict[str, Any]) -> None:
    _validate_safe_data(data, "data")
    schema = CONTRACT["resultDataSchemas"].get(method)
    if schema is not None:
        _validate_object_schema(data, schema, "data")


def _validate_process_event_origin(event: str, origin: str) -> None:
    if origin not in CONTRACT["processEventOrigins"][event]:
        _invalid(f"{event} cannot originate from {origin}")


def _validate_message(value: Any) -> dict[str, Any]:
    message = _expect_object(value, "message")
    version = message.get("protocolVersion")
    if (
        isinstance(version, bool)
        or not isinstance(version, (int, float))
        or not math.isfinite(version)
    ):
        _invalid("protocolVersion must be a number")
    if version != CONTRACT["protocolVersion"]:
        raise ProtocolCheckError(
            "PROTOCOL_VERSION_UNSUPPORTED",
            f"Unsupported protocol version: {version}",
        )

    message_type = _expect_string(message.get("messageType"), "messageType")
    if message_type == "request":
        _expect_exact_keys(
            message,
            {"protocolVersion", "messageType", "requestId", "method", "params"},
            "request",
        )
        _validate_request_id(message.get("requestId"))
        method = _expect_string(message.get("method"), "method")
        if method not in METHODS:
            _invalid(f"Unknown method: {method}")
        params = _expect_object(message.get("params"), "params")
        _validate_params(method, params)
        return message

    if message_type == "event":
        event = _expect_string(message.get("event"), "event")
        data = _expect_object(message.get("data"), "data")
        _validate_safe_data(data, "data")
        if "requestId" not in message:
            _expect_exact_keys(
                message,
                {"protocolVersion", "messageType", "event", "data"},
                "event",
            )
            if event not in CONTRACT["processEvents"]:
                _invalid(f"Unknown process event: {event}")
            return message

        _expect_exact_keys(
            message,
            {"protocolVersion", "messageType", "requestId", "sequence", "event", "data"},
            "event",
        )
        _validate_request_id(message["requestId"])
        sequence = message.get("sequence")
        sequence = _json_integer(sequence, "sequence")
        if not 1 <= sequence <= 2**32 - 1:
            _invalid("Request event sequence must fit in a positive u32")
        if event not in CONTRACT["requestEvents"]:
            _invalid(f"Unknown request event: {event}")
        _validate_event_data(event, message["requestId"], data)
        return message

    if message_type == "result":
        _validate_request_id(message.get("requestId"))
        ok = message.get("ok")
        if ok is True:
            _expect_exact_keys(
                message,
                {"protocolVersion", "messageType", "requestId", "ok", "data"},
                "result",
            )
            data = _expect_object(message.get("data"), "data")
            _validate_safe_data(data, "data")
            return message
        if ok is False:
            _expect_exact_keys(
                message,
                {"protocolVersion", "messageType", "requestId", "ok", "error"},
                "result",
            )
            error = _expect_object(message.get("error"), "error")
            _expect_exact_keys(error, {"code", "message", "retryable", "details"}, "error")
            code = _expect_string(error.get("code"), "error.code")
            if code not in CONTRACT["errorCodes"]:
                _invalid(f"Unknown error code: {code}")
            error_message = _expect_string(error.get("message"), "error.message")
            if len(error_message.encode("utf-8")) > CONTRACT["errorMessageMaxBytes"]:
                _invalid("error.message is too large")
            if not isinstance(error.get("retryable"), bool):
                _invalid("error.retryable must be a boolean")
            details = _expect_object(error.get("details"), "error.details")
            _validate_safe_data(details, "error.details")
            if code == "INTERNAL_ERROR" and details:
                _invalid("INTERNAL_ERROR details must be empty")
            return message
        _invalid("result.ok must be a boolean")

    _invalid(f"Unknown messageType: {message_type}")


def _parse_line(line: str) -> dict[str, Any]:
    if len(line.encode("utf-8")) > CONTRACT["maxLineBytes"]:
        _invalid("Protocol line exceeds the 2 MiB limit")
    try:
        value = json.loads(
            line,
            parse_constant=lambda constant: (_ for _ in ()).throw(
                ValueError(f"invalid JSON constant: {constant}")
            ),
        )
    except (json.JSONDecodeError, ValueError):
        _invalid("Protocol line is not valid JSON")
    return _validate_message(value)


class _TraceValidator:
    def __init__(self) -> None:
        self._requests: dict[str, dict[str, int | bool | str]] = {}

    def accept(self, message: dict[str, Any]) -> None:
        message_type = message["messageType"]
        if message_type == "request":
            request_id = message["requestId"]
            if request_id in self._requests:
                _invalid(f"Duplicate requestId: {request_id}")
            self._requests[request_id] = {
                "nextSequence": 1,
                "terminal": False,
                "method": message["method"],
            }
        elif message_type == "event" and "requestId" in message:
            request_id = message["requestId"]
            state = self._requests.get(request_id)
            if state is None:
                _invalid(f"Event references unknown requestId: {request_id}")
            if state["terminal"]:
                _invalid(f"Event arrived after terminal result: {request_id}")
            if message["sequence"] != state["nextSequence"]:
                _invalid(
                    f"Expected sequence {state['nextSequence']}, received {message['sequence']}"
                )
            state["nextSequence"] = int(state["nextSequence"]) + 1
        elif message_type == "result":
            request_id = message["requestId"]
            state = self._requests.get(request_id)
            if state is None:
                _invalid(f"Result references unknown requestId: {request_id}")
            if state["terminal"]:
                _invalid(f"Duplicate terminal result: {request_id}")
            if message["ok"]:
                _validate_result_data(str(state["method"]), message["data"])
            state["terminal"] = True


def test_protocol_manifest_safety_invariants() -> None:
    assert CONTRACT["protocolVersion"] == 1
    assert CONTRACT["maxLineBytes"] == 2 * 1024 * 1024
    assert set(CONTRACT["processEventOrigins"]) == set(CONTRACT["processEvents"])
    assert all(
        set(origins) <= {"python", "rust"}
        for origins in CONTRACT["processEventOrigins"].values()
    )
    assert set(CONTRACT["resultDataSchemas"]) == {
        "runtime.diagnostics",
        "session.create",
        "session.turn",
        "extensions.preview",
    }
    assert len(METHODS) == len(CONTRACT["methods"])
    assert not {
        "run_slash_command",
        "run_shell",
        "read_arbitrary_file",
        "set_any_config_field",
    } & set(METHODS)
    for method in CONTRACT["methods"]:
        required_from_schema = [
            name for name, rule in method["params"].items() if rule["required"]
        ]
        assert method["requiredParams"] == required_from_schema
        if method["operation"] == "destructive":
            assert "previewId" in method["requiredParams"]


@pytest.mark.parametrize("case", FIXTURES["messages"], ids=lambda case: case["name"])
def test_shared_message_fixture(case: dict[str, Any]) -> None:
    if case["valid"]:
        _validate_message(case["message"])
    else:
        with pytest.raises(ProtocolCheckError) as raised:
            _validate_message(case["message"])
        assert raised.value.code == case["errorCode"]


@pytest.mark.parametrize("case", FIXTURES["rawLines"], ids=lambda case: case["name"])
def test_shared_raw_line_fixture(case: dict[str, Any]) -> None:
    if case["valid"]:
        _parse_line(case["line"])
    else:
        with pytest.raises(ProtocolCheckError) as raised:
            _parse_line(case["line"])
        assert raised.value.code == case["errorCode"]


@pytest.mark.parametrize(
    "case", FIXTURES["originCases"], ids=lambda case: case["name"]
)
def test_shared_process_event_origin_fixture(case: dict[str, Any]) -> None:
    if case["valid"]:
        _validate_process_event_origin(case["event"], case["origin"])
    else:
        with pytest.raises(ProtocolCheckError) as raised:
            _validate_process_event_origin(case["event"], case["origin"])
        assert raised.value.code == case["errorCode"]


@pytest.mark.parametrize("case", FIXTURES["traces"], ids=lambda case: case["name"])
def test_shared_trace_fixture(case: dict[str, Any]) -> None:
    tracker = _TraceValidator()

    def run() -> None:
        for value in case["messages"]:
            tracker.accept(_validate_message(value))

    if case["valid"]:
        run()
    else:
        with pytest.raises(ProtocolCheckError) as raised:
            run()
        assert raised.value.code == case["errorCode"]


def test_protocol_line_limit_is_measured_in_utf8_bytes() -> None:
    oversized = json.dumps(
        {"padding": "界" * CONTRACT["maxLineBytes"]},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    with pytest.raises(ProtocolCheckError, match="2 MiB"):
        _parse_line(oversized)
