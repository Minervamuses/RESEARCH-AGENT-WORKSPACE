"""Versioned NDJSON envelopes shared by the Python desktop backend."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from typing import Any
from uuid import RFC_4122, UUID

from agent.paths import find_app_root


PROTOCOL_DIR = find_app_root() / "desktop" / "protocol" / "v1"
CONTRACT = json.loads((PROTOCOL_DIR / "contract.json").read_text(encoding="utf-8"))
METHODS = {item["name"]: item for item in CONTRACT["methods"]}
PROTOCOL_VERSION = int(CONTRACT["protocolVersion"])
MAX_PROTOCOL_LINE_BYTES = int(CONTRACT["maxLineBytes"])

_UTC_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)
_MAX_SAFE_DATA_DEPTH = 64
_TURN_ERROR_DETAIL_KEYS = frozenset(CONTRACT["turnErrorDetailsSchema"])


class ProtocolError(ValueError):
    """A safe protocol failure with a stable wire code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.details = dict(details or {})


def _invalid(message: str) -> None:
    raise ProtocolError("PROTOCOL_INVALID", message)


def _expect_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _invalid(f"{field} must be a JSON object")
    return value


def _expect_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        _invalid(f"{field} must be a non-empty string")
    return value


def _expect_exact_keys(
    value: dict[str, Any], allowed: set[str], field: str
) -> None:
    unknown = set(value) - allowed
    if unknown:
        _invalid(f"{field} contains unknown field: {sorted(unknown)[0]}")


def _json_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _invalid(f"{field} must be an integer")
    if isinstance(value, float) and (
        not math.isfinite(value) or not value.is_integer()
    ):
        _invalid(f"{field} must be an integer")
    return int(value)


def validate_request_id(value: Any) -> str:
    """Return a canonical RFC 4122 UUID request ID."""
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


def validate_turn_id(value: Any, field: str = "turnId") -> str:
    """Return a canonical lowercase UUIDv4 hex logical turn ID."""
    turn_id = _expect_string(value, field)
    try:
        parsed = UUID(turn_id)
    except ValueError:
        _invalid(f"{field} must be a canonical UUIDv4 hex value")
    if (
        len(turn_id) != 32
        or parsed.hex != turn_id
        or parsed.variant != RFC_4122
        or parsed.version != 4
    ):
        _invalid(f"{field} must be a canonical UUIDv4 hex value")
    return turn_id


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
            if len(text.encode("utf-8")) > rule.get(
                "itemMaxBytes", math.inf
            ):
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
        validate_request_id(value)
        return
    if field_type == "turnId":
        validate_turn_id(value, field)
        return
    timestamp = _expect_string(value, field)
    if not _UTC_TIMESTAMP.fullmatch(timestamp):
        _invalid(f"{field} must be a UTC ISO 8601 timestamp")
    try:
        datetime.fromisoformat(timestamp.removesuffix("Z") + "+00:00")
    except ValueError:
        _invalid(f"{field} must be a UTC ISO 8601 timestamp")


def _validate_object_schema(
    value: dict[str, Any],
    schema: dict[str, dict[str, Any]],
    field: str,
) -> None:
    _expect_exact_keys(value, set(schema), field)
    for name, rule in schema.items():
        if name not in value:
            if rule["required"]:
                _invalid(f"{field}.{name} is required")
            continue
        _validate_field_rule(value[name], rule, f"{field}.{name}")


def _normalize_data_key(key: str) -> str:
    return "".join(
        character
        for character in key.lower()
        if character.isascii() and character.isalnum()
    )


def _validate_safe_data(value: Any, field: str, *, depth: int = 0) -> None:
    if depth > _MAX_SAFE_DATA_DEPTH:
        _invalid(f"{field} exceeds the maximum JSON nesting depth")
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_safe_data(item, f"{field}[{index}]", depth=depth + 1)
        return
    if not isinstance(value, dict):
        return
    for key, item in value.items():
        if not isinstance(key, str):
            _invalid(f"{field} contains a non-string field name")
        normalized = _normalize_data_key(key)
        if any(
            fragment in normalized
            for fragment in CONTRACT["forbiddenDataKeyFragments"]
        ):
            _invalid(f"{field} contains forbidden field: {key}")
        _validate_safe_data(item, f"{field}.{key}", depth=depth + 1)


def _validate_turn_error_details(details: dict[str, Any]) -> None:
    _validate_object_schema(
        details,
        CONTRACT["turnErrorDetailsSchema"],
        "error.details",
    )
    state = details["state"]
    accepted = details["accepted"]
    persisted = details["persisted"]
    if state is None:
        if accepted or persisted:
            _invalid(
                "a null turn error state must not be accepted or persisted"
            )
    elif accepted is not True or persisted is not True:
        _invalid(
            "a durable turn error state must be accepted and persisted"
        )


def _validate_event_data(
    event: str, request_id: str, data: dict[str, Any]
) -> None:
    if event.startswith("tool."):
        _expect_exact_keys(data, set(CONTRACT["toolEventDataKeys"]), "data")
        _expect_string(data.get("name"), "data.name")
        status = _expect_string(data.get("status"), "data.status")
        if status not in CONTRACT["toolStatuses"]:
            _invalid(f"Unknown tool status: {status}")
        for optional in ("callId", "candidateId"):
            if optional in data:
                _expect_string(data[optional], f"data.{optional}")

    schema = CONTRACT["eventDataSchemas"].get(event)
    if schema is not None:
        _validate_object_schema(data, schema, "data")
    if (
        event == "approval.required"
        and data["parentRequestId"] != request_id
    ):
        _invalid("data.parentRequestId must match the event requestId")


def validate_result_data(method: str, data: dict[str, Any]) -> None:
    """Validate safe result data with the originating request method."""
    _validate_safe_data(data, "data")
    schema = CONTRACT["resultDataSchemas"].get(method)
    if schema is not None:
        _validate_object_schema(data, schema, "data")
    if method == "session.turn" and (
        data.get("state") != "completed"
        or data.get("accepted") is not True
        or data.get("persisted") is not True
    ):
        _invalid("session.turn success must be durably completed")
    if method == "session.transcript":
        for item in data["items"]:
            state = item["state"]
            assistant_text = item["assistantText"]
            failure_values = (
                item["failureCode"],
                item["failureMessage"],
                item["failureRetryable"],
            )
            if state == "completed":
                if assistant_text is None or any(
                    value is not None for value in failure_values
                ):
                    _invalid("completed transcript turn has invalid lifecycle fields")
            elif state == "pending":
                if assistant_text is not None or any(
                    value is not None for value in failure_values
                ) or item["toolActivities"]:
                    _invalid("pending transcript turn has invalid lifecycle fields")
            else:
                if assistant_text is not None or any(
                    value is None for value in failure_values
                ) or item["toolActivities"]:
                    _invalid(f"{state} transcript turn has invalid lifecycle fields")
                if state == "failed" and item["failureCode"] not in {
                    "execution_failed",
                    "persistence_failed",
                }:
                    _invalid("failed transcript turn has an invalid failure code")
                if state == "interrupted" and item["failureCode"] not in {
                    "interrupted",
                    "cancelled",
                }:
                    _invalid("interrupted transcript turn has an invalid failure code")


def validate_process_event_origin(event: str, origin: str) -> None:
    """Reject a process event emitted by the wrong boundary owner."""
    if event not in CONTRACT["processEventOrigins"]:
        _invalid(f"Unknown process event: {event}")
    if origin not in CONTRACT["processEventOrigins"][event]:
        _invalid(f"{event} cannot originate from {origin}")


def validate_message(value: Any) -> dict[str, Any]:
    """Validate one decoded protocol envelope and return it unchanged."""
    message = _expect_object(value, "message")
    version = message.get("protocolVersion")
    if (
        isinstance(version, bool)
        or not isinstance(version, (int, float))
        or not math.isfinite(version)
    ):
        _invalid("protocolVersion must be a number")
    if version != PROTOCOL_VERSION:
        raise ProtocolError(
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
        validate_request_id(message.get("requestId"))
        method = _expect_string(message.get("method"), "method")
        if method not in METHODS:
            _invalid(f"Unknown method: {method}")
        params = _expect_object(message.get("params"), "params")
        _validate_object_schema(params, METHODS[method]["params"], "params")
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
        validate_request_id(message["requestId"])
        sequence = _json_integer(message.get("sequence"), "sequence")
        if not 1 <= sequence <= 2**32 - 1:
            _invalid("Request event sequence must fit in a positive u32")
        if event not in CONTRACT["requestEvents"]:
            _invalid(f"Unknown request event: {event}")
        _validate_event_data(event, message["requestId"], data)
        return message

    if message_type == "result":
        validate_request_id(message.get("requestId"))
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
            _expect_exact_keys(
                error,
                {"code", "message", "retryable", "details"},
                "error",
            )
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
            if set(details) & _TURN_ERROR_DETAIL_KEYS:
                _validate_turn_error_details(details)
            elif code == "INTERNAL_ERROR" and details:
                _invalid("INTERNAL_ERROR details must be empty")
            return message
        _invalid("result.ok must be a boolean")

    _invalid(f"Unknown messageType: {message_type}")


def parse_line(line: str | bytes) -> dict[str, Any]:
    """Parse exactly one bounded UTF-8 JSON line."""
    if isinstance(line, bytes):
        try:
            line = line.decode("utf-8")
        except UnicodeDecodeError:
            _invalid("Protocol line is not valid UTF-8")
    if len(line.encode("utf-8")) > MAX_PROTOCOL_LINE_BYTES:
        _invalid("Protocol line exceeds the 2 MiB limit")
    try:
        value = json.loads(
            line,
            parse_constant=lambda constant: (_ for _ in ()).throw(
                ValueError(f"invalid JSON constant: {constant}")
            ),
        )
    except (json.JSONDecodeError, RecursionError, ValueError):
        _invalid("Protocol line is not valid JSON")
    try:
        return validate_message(value)
    except RecursionError:
        _invalid("Protocol JSON nesting is too deep")


def request_id_from_invalid_line(line: str | bytes) -> str | None:
    """Best-effort correlation for an invalid request envelope."""
    try:
        if isinstance(line, bytes):
            line = line.decode("utf-8")
        value = json.loads(line)
        if not isinstance(value, dict):
            return None
        return validate_request_id(value.get("requestId"))
    except (UnicodeDecodeError, json.JSONDecodeError, ProtocolError, RecursionError):
        return None


def request_event(
    request_id: str,
    sequence: int,
    event: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    message = {
        "protocolVersion": PROTOCOL_VERSION,
        "messageType": "event",
        "requestId": request_id,
        "sequence": sequence,
        "event": event,
        "data": data,
    }
    return validate_message(message)


def process_event(event: str, data: dict[str, Any]) -> dict[str, Any]:
    validate_process_event_origin(event, "python")
    message = {
        "protocolVersion": PROTOCOL_VERSION,
        "messageType": "event",
        "event": event,
        "data": data,
    }
    return validate_message(message)


def success_result(
    request_id: str,
    method: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    validate_result_data(method, data)
    message = {
        "protocolVersion": PROTOCOL_VERSION,
        "messageType": "result",
        "requestId": request_id,
        "ok": True,
        "data": data,
    }
    return validate_message(message)


def failure_result(
    request_id: str,
    error: ProtocolError,
) -> dict[str, Any]:
    message = {
        "protocolVersion": PROTOCOL_VERSION,
        "messageType": "result",
        "requestId": request_id,
        "ok": False,
        "error": {
            "code": error.code,
            "message": bounded_error_message(str(error)),
            "retryable": error.retryable,
            "details": error.details,
        },
    }
    return validate_message(message)


def bounded_error_message(message: str) -> str:
    """Return a non-empty error message within the v1 UTF-8 byte limit."""
    maximum = int(CONTRACT["errorMessageMaxBytes"])
    text = message or "Protocol error."
    encoded = text.encode("utf-8")
    if len(encoded) <= maximum:
        return text
    return encoded[:maximum].decode("utf-8", errors="ignore") or "Protocol error."


def encode_message(message: dict[str, Any]) -> str:
    """Serialize a validated envelope to one newline-terminated JSON line."""
    validate_message(message)
    try:
        encoded = json.dumps(
            message,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
    except (RecursionError, TypeError, ValueError) as exc:
        raise ProtocolError(
            "PROTOCOL_INVALID", "Protocol message is not strict JSON."
        ) from exc
    if len(encoded.encode("utf-8")) > MAX_PROTOCOL_LINE_BYTES:
        _invalid("Protocol line exceeds the 2 MiB limit")
    return encoded + "\n"


class TraceValidator:
    """Validate request correlation, event order, and terminal results."""

    def __init__(self) -> None:
        self._requests: dict[str, dict[str, int | bool | str | None]] = {}

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
                "turnId": (
                    message["params"]["turnId"]
                    if message["method"] == "session.turn"
                    else None
                ),
            }
            return
        if message_type == "event" and "requestId" in message:
            request_id = message["requestId"]
            state = self._requests.get(request_id)
            if state is None:
                _invalid(f"Event references unknown requestId: {request_id}")
            if state["terminal"]:
                _invalid(f"Event arrived after terminal result: {request_id}")
            if message["sequence"] != state["nextSequence"]:
                _invalid(
                    f"Expected sequence {state['nextSequence']}, "
                    f"received {message['sequence']}"
                )
            state["nextSequence"] = int(state["nextSequence"]) + 1
            return
        if message_type == "result":
            request_id = message["requestId"]
            state = self._requests.get(request_id)
            if state is None:
                _invalid(f"Result references unknown requestId: {request_id}")
            if state["terminal"]:
                _invalid(f"Duplicate terminal result: {request_id}")
            if message["ok"]:
                validate_result_data(str(state["method"]), message["data"])
                expected_turn_id = state["turnId"]
                if (
                    expected_turn_id is not None
                    and message["data"].get("turnId") != expected_turn_id
                ):
                    _invalid("data.turnId must match params.turnId")
            elif state["method"] == "session.turn":
                details = message["error"]["details"]
                _validate_turn_error_details(details)
                if details["turnId"] != state["turnId"]:
                    _invalid("error.details.turnId must match params.turnId")
            state["terminal"] = True
