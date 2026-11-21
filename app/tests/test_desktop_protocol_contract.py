"""Python checks for the shared desktop protocol v1 contract and fixtures.

Python is the only schema validator (U1), so these tests are where the contract
is exercised. Fixture convention: every contract method keeps at least one
valid and one invalid case in `protocol/v1/fixtures.json` (a request message or
a trace containing its request). TS runs only the request cases; Rust runs only
the process-event origin cases.
"""

from __future__ import annotations

import json

import pytest

from protocol_trace_oracle import TraceValidator

from agent.desktop.protocol import (
    CONTRACT,
    METHODS,
    PROTOCOL_DIR,
    ProtocolError,
    parse_line,
    validate_message,
    validate_process_event_origin,
    validate_result_data,
)


FIXTURES = json.loads((PROTOCOL_DIR / "fixtures.json").read_text(encoding="utf-8"))


def test_protocol_manifest_safety_invariants() -> None:
    assert CONTRACT["protocolVersion"] == 1
    assert CONTRACT["maxLineBytes"] == 2 * 1024 * 1024
    assert CONTRACT["fullTextResultMethods"] == [
        "session.turn",
        "session.transcript",
    ]
    assert set(CONTRACT["processEventOrigins"]) == set(CONTRACT["processEvents"])
    assert all(
        set(origins) <= {"python", "rust"}
        for origins in CONTRACT["processEventOrigins"].values()
    )
    assert len(METHODS) == len(CONTRACT["methods"])
    assert not {
        "run_slash_command",
        "run_shell",
        "read_arbitrary_file",
        "set_any_config_field",
    } & set(METHODS)


def test_normal_answers_use_only_the_final_terminal_result() -> None:
    assert "answer.chunk" not in CONTRACT["requestEvents"]
    assert "answer.chunk" not in CONTRACT["eventDataSchemas"]
    turn = CONTRACT["resultDataSchemas"]["session.turn"]
    # The retired streaming markers stay out of the wire result.
    assert "streamKind" not in turn and "chunkCount" not in turn
    assert "maxBytes" not in turn["text"]
    transcript_turn = CONTRACT["resultDataSchemas"]["session.transcript"][
        "items"
    ]["items"]
    assert "maxBytes" not in transcript_turn["userText"]
    assert "maxBytes" not in transcript_turn["assistantText"]


def _required_params(method: str) -> list[str]:
    return [name for name, rule in METHODS[method]["params"].items() if rule["required"]]


def test_session_turn_carries_canonical_lifecycle_identity_end_to_end() -> None:
    method = METHODS["session.turn"]
    assert _required_params("session.turn") == ["text", "turnId", "retry"]
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


def test_extension_apply_is_a_durable_display_only_turn() -> None:
    method = METHODS["extensions.apply"]
    assert _required_params("extensions.apply") == [
        "previewId",
        "approvedBindingHashes",
        "turnId",
        "retry",
    ]
    assert method["params"]["turnId"] == {
        "type": "turnId",
        "required": True,
    }
    assert method["params"]["retry"] == {
        "type": "boolean",
        "required": True,
    }

    result = CONTRACT["resultDataSchemas"]["extensions.apply"]
    assert result["sessionId"] == {
        "type": "string",
        "required": True,
        "maxBytes": 256,
    }
    assert result["turnId"] == {"type": "turnId", "required": True}
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
    assert result["displayInput"] == {
        "type": "string",
        "required": True,
        "maxBytes": 256,
    }
    assert result["text"] == {
        "type": "string",
        "required": True,
        "maxBytes": 65_536,
    }


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


def test_extension_apply_uses_the_same_durable_result_and_error_correlation() -> None:
    request = {
        "protocolVersion": 1,
        "messageType": "request",
        "requestId": "00000000-0000-4000-8000-0000000000a1",
        "method": "extensions.apply",
        "params": {
            "previewId": "extension-preview-opaque-1",
            "approvedBindingHashes": [],
            "turnId": "000000000000400080000000000000a1",
            "retry": False,
        },
    }
    result_data = {
        "sessionId": "0123456789abcdef0123456789abcdef",
        "turnId": "000000000000400080000000000000a1",
        "turnNumber": 1,
        "state": "completed",
        "accepted": True,
        "persisted": True,
        "displayInput": "One-shot local action: apply reviewed extension changes [hash]",
        "text": "Extension Management applied revision 0 -> 1\ndiagnostics: 0\nrestart_required: false",
        "previousRevision": 0,
        "appliedRevision": 1,
        "restartRequired": False,
        "items": [],
        "diagnostics": [],
    }
    validate_result_data("extensions.apply", result_data)

    incomplete = {**result_data, "state": "pending"}
    with pytest.raises(ProtocolError, match="unknown enum value"):
        validate_result_data("extensions.apply", incomplete)

    tracker = TraceValidator()
    tracker.accept(validate_message(request))
    with pytest.raises(ProtocolError, match="data.turnId"):
        tracker.accept(
            validate_message(
                {
                    "protocolVersion": 1,
                    "messageType": "result",
                    "requestId": request["requestId"],
                    "ok": True,
                    "data": {
                        **result_data,
                        "turnId": "000000000000400080000000000000a2",
                    },
                }
            )
        )

    tracker = TraceValidator()
    tracker.accept(validate_message(request))
    with pytest.raises(ProtocolError, match="error.details.turnId"):
        tracker.accept(
            validate_message(
                {
                    "protocolVersion": 1,
                    "messageType": "result",
                    "requestId": request["requestId"],
                    "ok": False,
                    "error": {
                        "code": "EXTENSION_APPLY_FAILED",
                        "message": "Extension apply failed.",
                        "retryable": False,
                        "details": {
                            "turnId": "000000000000400080000000000000a2",
                            "state": "failed",
                            "accepted": True,
                            "persisted": True,
                        },
                    },
                }
            )
        )


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
        "submittedContext",
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
    assert turn["userText"] == {"type": "string", "required": True}
    assert turn["assistantText"] == {
        "type": "nullableString",
        "required": True,
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
    assert CONTRACT["resultDataSchemas"]["runtime.shutdown"] == {
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


def test_permission_mode_protocol_contract() -> None:
    method = METHODS["session.set_permission"]
    assert _required_params("session.set_permission") == ["permissionMode"]
    assert method["params"]["permissionMode"] == {
        "type": "string",
        "required": True,
        "enum": ["ask", "bypass"],
    }

    validate_result_data("session.set_permission", {
        "sessionId": "0123456789abcdef0123456789abcdef",
        "permissionMode": "bypass",
    })

    with pytest.raises(ProtocolError):
        validate_result_data("session.set_permission", {
            "sessionId": "0123456789abcdef0123456789abcdef",
            "permissionMode": "bypass",
            "extraKey": "forbidden",
        })

    with pytest.raises(ProtocolError):
        validate_result_data("session.set_permission", {
            "sessionId": "0123456789abcdef0123456789abcdef",
            "permissionMode": "invalid",
        })

    assert CONTRACT["resultDataSchemas"]["session.create"]["permissionMode"] == {
        "type": "string",
        "required": True,
        "enum": ["ask", "bypass"],
    }
    assert CONTRACT["resultDataSchemas"]["session.select"]["permissionMode"] == {
        "type": "string",
        "required": True,
        "enum": ["ask", "bypass"],
    }
    for method in ("session.create", "session.select"):
        assert CONTRACT["resultDataSchemas"][method]["thinkingMode"]["enum"] == ["normal", "extended"]


def test_bibliography_export_formats_exclude_bibtex() -> None:
    method = next(item for item in CONTRACT["methods"] if item["name"] == "bibliography.export")
    assert method["params"]["format"]["enum"] == ["docx", "bime_docx", "markdown"]
    assert CONTRACT["resultDataSchemas"]["bibliography.export"]["format"]["enum"] == ["docx", "bime_docx", "markdown"]


def test_bibliography_export_audit_belongs_only_to_bime_docx() -> None:
    audit = {"errors": 1, "warnings": 0, "manualChecks": 11, "reportPath": "/p/a.bime.audit.md", "layoutVerified": False}
    validate_result_data("bibliography.export", {"format": "bime_docx", "path": "/p/a.bime.docx", "audit": audit})
    validate_result_data("bibliography.export", {"format": "docx", "path": "/p/a.apa.docx"})
    validate_result_data("bibliography.export", {"format": "markdown", "path": "/p/a.apa.md"})
    for data in (
        {"format": "bime_docx", "path": "/p/a.bime.docx"},
        {"format": "docx", "path": "/p/a.apa.docx", "audit": audit},
        {"format": "bime_docx", "path": "/p/a.bime.docx", "audit": {**audit, "errors": 1_000_001}},
        {"format": "bime_docx", "path": "/p/a.bime.docx", "audit": {k: v for k, v in audit.items() if k != "reportPath"}},
        {"format": "bime_docx", "path": "/p/a.bime.docx", "audit": {**audit, "layoutVerified": 0}},
    ):
        with pytest.raises(ProtocolError):
            validate_result_data("bibliography.export", data)
