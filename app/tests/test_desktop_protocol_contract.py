"""Python checks for the shared desktop protocol v1 contract and fixtures."""

from __future__ import annotations

import json

import pytest

from agent.desktop.protocol import (
    CONTRACT,
    METHODS,
    PROTOCOL_DIR,
    ProtocolError,
    TraceValidator,
    parse_line,
    validate_message,
    validate_process_event_origin,
)


FIXTURES = json.loads((PROTOCOL_DIR / "fixtures.json").read_text(encoding="utf-8"))


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
        "project.list",
        "session.create",
        "session.list",
        "session.select",
        "session.retry_registration",
        "session.transcript",
        "session.turn",
        "extensions.status",
        "extensions.preview",
        "extensions.apply",
        "approval.resolve",
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


def test_phase04_approval_correlation_and_extension_action_are_v1_additions() -> None:
    approval = METHODS["approval.resolve"]
    assert approval["requiredParams"] == ["approvalId", "approved"]
    assert approval["params"]["parentRequestId"] == {
        "type": "requestId",
        "required": False,
    }
    assert approval["params"]["turnId"] == {
        "type": "string",
        "required": False,
        "maxBytes": 256,
    }
    assert CONTRACT["resultDataSchemas"]["session.turn"]["extensionAction"] == {
        "type": "string",
        "required": False,
        "enum": ["status", "preview"],
    }
    binding = CONTRACT["resultDataSchemas"]["extensions.preview"]["bindings"][
        "items"
    ]
    assert set(binding) == {
        "name",
        "server",
        "bindingHash",
        "requiresApproval",
        "command",
        "arguments",
        "workingDirectory",
        "environmentNames",
    }


@pytest.mark.parametrize("case", FIXTURES["messages"], ids=lambda case: case["name"])
def test_shared_message_fixture(case: dict) -> None:
    if case["valid"]:
        validate_message(case["message"])
    else:
        with pytest.raises(ProtocolError) as raised:
            validate_message(case["message"])
        assert raised.value.code == case["errorCode"]


@pytest.mark.parametrize("case", FIXTURES["rawLines"], ids=lambda case: case["name"])
def test_shared_raw_line_fixture(case: dict) -> None:
    if case["valid"]:
        parse_line(case["line"])
    else:
        with pytest.raises(ProtocolError) as raised:
            parse_line(case["line"])
        assert raised.value.code == case["errorCode"]


@pytest.mark.parametrize(
    "case", FIXTURES["originCases"], ids=lambda case: case["name"]
)
def test_shared_process_event_origin_fixture(case: dict) -> None:
    if case["valid"]:
        validate_process_event_origin(case["event"], case["origin"])
    else:
        with pytest.raises(ProtocolError) as raised:
            validate_process_event_origin(case["event"], case["origin"])
        assert raised.value.code == case["errorCode"]


@pytest.mark.parametrize("case", FIXTURES["traces"], ids=lambda case: case["name"])
def test_shared_trace_fixture(case: dict) -> None:
    tracker = TraceValidator()

    def run() -> None:
        for value in case["messages"]:
            tracker.accept(validate_message(value))

    if case["valid"]:
        run()
    else:
        with pytest.raises(ProtocolError) as raised:
            run()
        assert raised.value.code == case["errorCode"]


def test_protocol_line_limit_is_measured_in_utf8_bytes() -> None:
    oversized = json.dumps(
        {"padding": "界" * CONTRACT["maxLineBytes"]},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    with pytest.raises(ProtocolError, match="2 MiB"):
        parse_line(oversized)


def test_deeply_nested_json_is_a_bounded_protocol_failure() -> None:
    nested_params = '{"nested":' * 1_100 + "null" + "}" * 1_100
    line = (
        '{"protocolVersion":1,"messageType":"request",'
        '"requestId":"00000000-0000-4000-8000-000000000099",'
        '"method":"runtime.diagnostics","params":'
        + nested_params
        + "}"
    )

    with pytest.raises(ProtocolError) as raised:
        parse_line(line)

    assert raised.value.code == "PROTOCOL_INVALID"
