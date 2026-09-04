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
    validate_result_data,
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
        "session.shutdown",
        "runtime.shutdown",
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


def test_normal_answers_use_only_the_final_terminal_result() -> None:
    assert "answer.chunk" not in CONTRACT["requestEvents"]
    assert "answer.chunk" not in CONTRACT["eventDataSchemas"]
    turn = CONTRACT["resultDataSchemas"]["session.turn"]
    assert turn["streamKind"] == {
        "type": "string",
        "required": False,
        "enum": ["final_only"],
    }
    assert turn["chunkCount"] == {
        "type": "integer",
        "required": False,
        "minimum": 0,
        "maximum": 0,
    }


def test_session_turn_carries_canonical_lifecycle_identity_end_to_end() -> None:
    method = METHODS["session.turn"]
    assert method["requiredParams"] == ["text", "turnId", "retry"]
    assert method["params"]["turnId"] == {
        "type": "turnId",
        "required": True,
    }
    assert method["params"]["retry"] == {
        "type": "boolean",
        "required": True,
    }
    result = CONTRACT["resultDataSchemas"]["session.turn"]
    assert result["turnNumber"] == {
        "type": "integer",
        "required": True,
        "minimum": 1,
        "maximum": 4_096,
    }
    assert result["state"] == {
        "type": "string",
        "required": True,
        "enum": ["completed"],
    }
    assert result["accepted"] == {"type": "boolean", "required": True}
    assert result["persisted"] == {"type": "boolean", "required": True}


def test_session_turn_failure_lifecycle_details_are_exact_and_bounded() -> None:
    assert CONTRACT["turnErrorDetailsSchema"] == {
        "turnId": {"type": "turnId", "required": True},
        "state": {
            "type": "nullableString",
            "required": True,
            "enum": ["pending", "completed", "failed", "interrupted"],
        },
        "accepted": {"type": "boolean", "required": True},
        "persisted": {"type": "boolean", "required": True},
    }


def test_session_summary_and_transcript_expose_complete_durable_lifecycle() -> None:
    summary = CONTRACT["resultDataSchemas"]["session.list"]["items"]["items"]
    assert summary["createdAt"] == {
        "type": "nullableString",
        "required": True,
        "maxBytes": 64,
    }

    turn = CONTRACT["resultDataSchemas"]["session.transcript"]["items"]["items"]
    assert set(turn) == {
        "turnId",
        "turnNumber",
        "kind",
        "state",
        "timestamp",
        "userText",
        "assistantText",
        "failureCode",
        "failureMessage",
        "failureRetryable",
        "toolActivities",
    }
    assert turn["turnId"] == {"type": "turnId", "required": True}
    assert turn["kind"] == {
        "type": "string",
        "required": True,
        "enum": ["conversational", "display-only"],
    }
    assert turn["state"] == {
        "type": "string",
        "required": True,
        "enum": ["pending", "completed", "failed", "interrupted"],
    }
    assert turn["assistantText"] == {
        "type": "nullableString",
        "required": True,
        "maxBytes": 32_768,
    }
    assert turn["failureCode"] == {
        "type": "nullableString",
        "required": True,
        "maxBytes": 256,
        "enum": [
            "execution_failed",
            "persistence_failed",
            "interrupted",
            "cancelled",
        ],
    }
    assert turn["failureMessage"] == {
        "type": "nullableString",
        "required": True,
        "maxBytes": 4_096,
    }
    assert turn["failureRetryable"] == {
        "type": "nullableBoolean",
        "required": True,
    }


@pytest.mark.parametrize(
    ("state", "assistant_text", "failure_code", "failure_message", "retryable"),
    [
        ("pending", None, None, None, None),
        ("completed", "done", None, None, None),
        ("failed", None, "execution_failed", "request failed", True),
        ("interrupted", None, "interrupted", "turn interrupted", True),
    ],
)
def test_transcript_schema_accepts_each_durable_lifecycle_state(
    state: str,
    assistant_text: str | None,
    failure_code: str | None,
    failure_message: str | None,
    retryable: bool | None,
) -> None:
    validate_result_data(
        "session.transcript",
        {
            "projectId": "local",
            "sessionId": "0123456789abcdef0123456789abcdef",
            "status": "ready",
            "issue": None,
            "items": [
                {
                    "turnId": "00000000000040008000000000000094",
                    "turnNumber": 1,
                    "kind": "conversational",
                    "state": state,
                    "timestamp": "2026-09-04T12:00:00Z",
                    "userText": "fixture prompt",
                    "assistantText": assistant_text,
                    "failureCode": failure_code,
                    "failureMessage": failure_message,
                    "failureRetryable": retryable,
                    "toolActivities": [],
                }
            ],
            "total": 1,
            "offset": 0,
            "limit": 20,
            "hasMore": False,
        },
    )


def test_shutdown_contract_has_truthful_status_without_legacy_flush_fields() -> None:
    assert "CONVERSATION_FLUSH_FAILED" not in CONTRACT["errorCodes"]
    assert "SHUTDOWN_FLUSH_FAILED" not in CONTRACT["errorCodes"]
    for method in ("session.shutdown", "runtime.shutdown"):
        assert CONTRACT["resultDataSchemas"][method] == {
            "status": {
                "type": "string",
                "required": True,
                "enum": ["stopped", "no_session"],
            }
        }


def test_transcript_tool_activity_schema_is_bounded_and_parser_derived() -> None:
    turn = CONTRACT["resultDataSchemas"]["session.transcript"]["items"]["items"]
    activities = turn["toolActivities"]
    assert activities["required"] is True
    assert activities["maxItems"] == 128
    assert activities["items"] == {
        "callId": {"type": "nullableString", "required": True, "maxBytes": 256},
        "name": {"type": "string", "required": True, "maxBytes": 256},
        "arguments": {"type": "string", "required": True, "maxBytes": 32_768},
        "result": {"type": "string", "required": True, "maxBytes": 65_536},
        "status": {
            "type": "string",
            "required": True,
            "enum": ["ok", "failed", "denied", "incomplete"],
        },
        "promptEligible": {"type": "boolean", "required": True},
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
