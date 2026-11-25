//! Protocol v1 framing for the Python child.
//!
//! Python is the only schema validator (U1). The host checks only what it needs
//! to route messages safely: JSON envelopes, the line limit and its full-text
//! result exemption, request IDs, request-event sequences, process-event
//! origins, and the forbidden-key scan. Framework values come from the
//! compiled-in `contract.json`, the single hand-written protocol source.

use std::collections::HashMap;
use std::error::Error;
use std::fmt::{Display, Formatter};
use std::sync::OnceLock;

use serde::de::Error as DeserializeError;
use serde::{Deserialize, Deserializer, Serialize};
use serde_json::{Map, Value};

const CONTRACT_JSON: &str = include_str!("../../protocol/v1/contract.json");

/// The framework subset of the protocol contract.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Framework {
    pub protocol_version: u64,
    pub max_line_bytes: usize,
    pub request_id_max_bytes: usize,
    pub error_message_max_bytes: usize,
    pub full_text_result_methods: Vec<String>,
    pub process_events: Vec<String>,
    pub process_event_origins: HashMap<String, Vec<String>>,
    pub forbidden_data_key_fragments: Vec<String>,
}

impl Framework {
    /// Whether a successful result of `method` may exceed the line limit.
    pub fn allows_full_text_result(&self, method: &str) -> bool {
        self.full_text_result_methods.iter().any(|name| name == method)
    }
}

/// Framework values parsed once from the contract compiled into the binary.
pub fn framework() -> &'static Framework {
    static FRAMEWORK: OnceLock<Framework> = OnceLock::new();
    FRAMEWORK.get_or_init(|| {
        serde_json::from_str(CONTRACT_JSON)
            .expect("the compiled-in protocol contract has the framework fields")
    })
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ProtocolOrigin {
    Python,
    Rust,
}

impl ProtocolOrigin {
    fn contract_name(self) -> &'static str {
        match self {
            Self::Python => "python",
            Self::Rust => "rust",
        }
    }
}

fn json_integer(value: &Value) -> Option<i64> {
    if let Some(integer) = value.as_i64() {
        return Some(integer);
    }
    let number = value.as_f64()?;
    if !number.is_finite()
        || number.fract() != 0.0
        || number < i64::MIN as f64
        || number > i64::MAX as f64
    {
        return None;
    }
    Some(number as i64)
}

fn deserialize_protocol_version<'de, D>(deserializer: D) -> Result<u64, D::Error>
where
    D: Deserializer<'de>,
{
    let value = Value::deserialize(deserializer)?;
    let version = framework().protocol_version;
    if value.as_f64() == Some(version as f64) {
        Ok(version)
    } else {
        Err(D::Error::custom("invalid protocol version"))
    }
}

fn deserialize_optional_u64<'de, D>(deserializer: D) -> Result<Option<u64>, D::Error>
where
    D: Deserializer<'de>,
{
    let value = Option::<Value>::deserialize(deserializer)?;
    let Some(value) = value else {
        return Ok(None);
    };
    let integer = json_integer(&value)
        .filter(|integer| *integer >= 0)
        .ok_or_else(|| D::Error::custom("expected a non-negative integer"))?;
    Ok(Some(integer as u64))
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct RequestEnvelope {
    #[serde(deserialize_with = "deserialize_protocol_version")]
    pub protocol_version: u64,
    pub message_type: String,
    pub request_id: String,
    pub method: String,
    pub params: Value,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct EventEnvelope {
    #[serde(deserialize_with = "deserialize_protocol_version")]
    pub protocol_version: u64,
    pub message_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub request_id: Option<String>,
    #[serde(
        default,
        skip_serializing_if = "Option::is_none",
        deserialize_with = "deserialize_optional_u64"
    )]
    pub sequence: Option<u64>,
    pub event: String,
    pub data: Value,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ProtocolErrorDto {
    pub code: String,
    pub message: String,
    pub retryable: bool,
    pub details: Value,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct ResultEnvelope {
    #[serde(deserialize_with = "deserialize_protocol_version")]
    pub protocol_version: u64,
    pub message_type: String,
    pub request_id: String,
    pub ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<ProtocolErrorDto>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum ProtocolMessage {
    Request(RequestEnvelope),
    Event(EventEnvelope),
    Result(ResultEnvelope),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProtocolViolation {
    code: &'static str,
    message: String,
}

impl ProtocolViolation {
    pub fn code(&self) -> &'static str {
        self.code
    }

    pub fn message(&self) -> &str {
        &self.message
    }

    fn invalid(message: impl Into<String>) -> Self {
        Self {
            code: "PROTOCOL_INVALID",
            message: message.into(),
        }
    }

    fn unsupported(version: &Value) -> Self {
        Self {
            code: "PROTOCOL_VERSION_UNSUPPORTED",
            message: format!("Unsupported protocol version: {version}"),
        }
    }
}

impl Display for ProtocolViolation {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> std::fmt::Result {
        write!(formatter, "{}: {}", self.code, self.message)
    }
}

impl Error for ProtocolViolation {}

fn is_canonical_uuid(value: &str) -> bool {
    let bytes = value.as_bytes();
    if bytes.len() != 36
        || bytes[8] != b'-'
        || bytes[13] != b'-'
        || bytes[18] != b'-'
        || bytes[23] != b'-'
    {
        return false;
    }
    for (index, byte) in bytes.iter().enumerate() {
        if matches!(index, 8 | 13 | 18 | 23) {
            continue;
        }
        if !byte.is_ascii_hexdigit() {
            return false;
        }
    }
    matches!(bytes[14].to_ascii_lowercase(), b'1'..=b'8')
        && matches!(bytes[19].to_ascii_lowercase(), b'8' | b'9' | b'a' | b'b')
}

fn validate_request_id(value: &str) -> Result<(), ProtocolViolation> {
    if value.is_empty() || value.len() > framework().request_id_max_bytes {
        return Err(ProtocolViolation::invalid("requestId has an invalid size"));
    }
    if !is_canonical_uuid(value) {
        return Err(ProtocolViolation::invalid(
            "requestId must be a canonical UUID",
        ));
    }
    Ok(())
}

fn expect_object<'a>(
    value: &'a Value,
    field: &str,
) -> Result<&'a Map<String, Value>, ProtocolViolation> {
    value
        .as_object()
        .ok_or_else(|| ProtocolViolation::invalid(format!("{field} must be a JSON object")))
}

fn expect_non_empty_string<'a>(
    value: &'a Value,
    field: &str,
) -> Result<&'a str, ProtocolViolation> {
    value
        .as_str()
        .filter(|text| !text.is_empty())
        .ok_or_else(|| ProtocolViolation::invalid(format!("{field} must be a non-empty string")))
}

fn normalized_data_key(key: &str) -> String {
    key.chars()
        .flat_map(char::to_lowercase)
        .filter(|character| character.is_ascii_alphanumeric())
        .collect()
}

enum DataPathSegment<'a> {
    Index(usize),
    Key(&'a str),
}

fn is_forbidden_data_key(key: &str) -> bool {
    let normalized = normalized_data_key(key);
    framework()
        .forbidden_data_key_fragments
        .iter()
        .any(|fragment| normalized.contains(fragment.as_str()))
}

/// Return the first forbidden key, leaving `path` pointing at its parent.
fn find_forbidden_data_key<'a>(
    value: &'a Value,
    path: &mut Vec<DataPathSegment<'a>>,
) -> Option<&'a str> {
    match value {
        Value::Array(items) => {
            for (index, item) in items.iter().enumerate() {
                path.push(DataPathSegment::Index(index));
                if let Some(key) = find_forbidden_data_key(item, path) {
                    return Some(key);
                }
                path.pop();
            }
        }
        Value::Object(object) => {
            for (key, item) in object {
                if is_forbidden_data_key(key) {
                    return Some(key);
                }
                path.push(DataPathSegment::Key(key));
                if let Some(found) = find_forbidden_data_key(item, path) {
                    return Some(found);
                }
                path.pop();
            }
        }
        _ => {}
    }
    None
}

/// Reject any object key that names provider internals or credentials.
///
/// The field path is only formatted when a violation is found, so valid
/// messages are walked without allocating a path string per node.
fn validate_safe_data(value: &Value, field: &str) -> Result<(), ProtocolViolation> {
    let mut path = Vec::new();
    let Some(key) = find_forbidden_data_key(value, &mut path) else {
        return Ok(());
    };
    let mut location = field.to_owned();
    for segment in &path {
        match segment {
            DataPathSegment::Index(index) => location.push_str(&format!("[{index}]")),
            DataPathSegment::Key(name) => {
                location.push('.');
                location.push_str(name);
            }
        }
    }
    Err(ProtocolViolation::invalid(format!(
        "{location} contains forbidden field: {key}"
    )))
}

pub fn validate_process_event_origin(
    event: &str,
    origin: ProtocolOrigin,
) -> Result<(), ProtocolViolation> {
    let allowed = framework()
        .process_event_origins
        .get(event)
        .is_some_and(|origins| origins.iter().any(|name| name == origin.contract_name()));
    if !allowed {
        return Err(ProtocolViolation::invalid(format!(
            "{event} cannot originate from {origin:?}"
        )));
    }
    Ok(())
}

pub fn parse_protocol_value_from_origin(
    value: Value,
    origin: ProtocolOrigin,
) -> Result<ProtocolMessage, ProtocolViolation> {
    let message = parse_protocol_value(value)?;
    if let ProtocolMessage::Event(event) = &message {
        if event.request_id.is_none() {
            validate_process_event_origin(&event.event, origin)?;
        }
    }
    Ok(message)
}

pub fn parse_protocol_value(value: Value) -> Result<ProtocolMessage, ProtocolViolation> {
    let object = expect_object(&value, "message")?;
    let version = object
        .get("protocolVersion")
        .ok_or_else(|| ProtocolViolation::invalid("protocolVersion is required"))?;
    if !version.is_number() {
        return Err(ProtocolViolation::invalid(
            "protocolVersion must be a number",
        ));
    }
    if version.as_f64() != Some(framework().protocol_version as f64) {
        return Err(ProtocolViolation::unsupported(version));
    }
    let message_type = expect_non_empty_string(
        object
            .get("messageType")
            .ok_or_else(|| ProtocolViolation::invalid("messageType is required"))?,
        "messageType",
    )?
    .to_owned();

    match message_type.as_str() {
        "request" => {
            let request: RequestEnvelope = serde_json::from_value(value)
                .map_err(|error| ProtocolViolation::invalid(error.to_string()))?;
            validate_request_id(&request.request_id)?;
            if request.method.is_empty() {
                return Err(ProtocolViolation::invalid(
                    "method must be a non-empty string",
                ));
            }
            expect_object(&request.params, "params")?;
            Ok(ProtocolMessage::Request(request))
        }
        "event" => {
            let has_request_id = object.contains_key("requestId");
            let has_sequence = object.contains_key("sequence");
            if has_request_id != has_sequence {
                return Err(ProtocolViolation::invalid(
                    "Request events require both requestId and sequence",
                ));
            }
            if has_request_id && (object["requestId"].is_null() || object["sequence"].is_null()) {
                return Err(ProtocolViolation::invalid(
                    "Request event correlation fields cannot be null",
                ));
            }
            let event: EventEnvelope = serde_json::from_value(value)
                .map_err(|error| ProtocolViolation::invalid(error.to_string()))?;
            if event.event.is_empty() {
                return Err(ProtocolViolation::invalid("event must be a non-empty string"));
            }
            expect_object(&event.data, "data")?;
            if has_request_id {
                let request_id = event.request_id.as_ref().ok_or_else(|| {
                    ProtocolViolation::invalid("requestId must be a non-empty string")
                })?;
                let sequence = event.sequence.ok_or_else(|| {
                    ProtocolViolation::invalid("sequence must be a positive integer")
                })?;
                validate_request_id(request_id)?;
                if sequence == 0 || sequence > u32::MAX as u64 {
                    return Err(ProtocolViolation::invalid(
                        "Request event sequence must fit in a positive u32",
                    ));
                }
            } else if !framework().process_events.contains(&event.event) {
                return Err(ProtocolViolation::invalid(format!(
                    "Unknown process event: {}",
                    event.event
                )));
            }
            validate_safe_data(&event.data, "data")?;
            Ok(ProtocolMessage::Event(event))
        }
        "result" => {
            let ok = object
                .get("ok")
                .and_then(Value::as_bool)
                .ok_or_else(|| ProtocolViolation::invalid("result.ok must be a boolean"))?;
            let has_data = object.contains_key("data");
            let has_error = object.contains_key("error");
            if ok && (!has_data || has_error) {
                return Err(ProtocolViolation::invalid(
                    "Successful results require data and cannot contain error",
                ));
            }
            if !ok && (has_data || !has_error) {
                return Err(ProtocolViolation::invalid(
                    "Failed results require error and cannot contain data",
                ));
            }
            let result: ResultEnvelope = serde_json::from_value(value)
                .map_err(|error| ProtocolViolation::invalid(error.to_string()))?;
            validate_request_id(&result.request_id)?;
            if let Some(data) = result.data.as_ref() {
                expect_object(data, "data")?;
                validate_safe_data(data, "data")?;
            }
            if let Some(error) = result.error.as_ref() {
                if error.code.is_empty() {
                    return Err(ProtocolViolation::invalid(
                        "error.code must be a non-empty string",
                    ));
                }
                if error.message.is_empty()
                    || error.message.len() > framework().error_message_max_bytes
                {
                    return Err(ProtocolViolation::invalid(
                        "error.message has an invalid size",
                    ));
                }
                expect_object(&error.details, "error.details")?;
                validate_safe_data(&error.details, "error.details")?;
            }
            Ok(ProtocolMessage::Result(result))
        }
        other => Err(ProtocolViolation::invalid(format!(
            "Unknown messageType: {other}"
        ))),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    const FIXTURES: &str = include_str!("../../protocol/v1/fixtures.json");
    const REQUEST_ID: &str = "123e4567-e89b-42d3-a456-426614174000";

    fn violation_code(value: Value) -> &'static str {
        parse_protocol_value(value)
            .expect_err("message must be rejected")
            .code()
    }

    #[test]
    fn framework_values_come_from_the_compiled_contract() {
        let contract: Value = serde_json::from_str(CONTRACT_JSON).expect("contract JSON");
        let framework = framework();
        assert_eq!(json!(framework.protocol_version), contract["protocolVersion"]);
        assert_eq!(json!(framework.max_line_bytes), contract["maxLineBytes"]);
        assert_eq!(json!(framework.request_id_max_bytes), contract["requestIdMaxBytes"]);
        assert_eq!(
            json!(framework.error_message_max_bytes),
            contract["errorMessageMaxBytes"]
        );
        assert_eq!(
            json!(framework.full_text_result_methods),
            contract["fullTextResultMethods"]
        );
        assert_eq!(json!(framework.process_events), contract["processEvents"]);
        assert_eq!(
            json!(framework.forbidden_data_key_fragments),
            contract["forbiddenDataKeyFragments"]
        );
        assert!(framework.allows_full_text_result("session.turn"));
        assert!(framework.allows_full_text_result("session.transcript"));
        assert!(!framework.allows_full_text_result("runtime.diagnostics"));
    }

    #[test]
    fn shared_process_event_origin_fixtures() {
        let fixtures: Value = serde_json::from_str(FIXTURES).expect("fixtures JSON");
        for case in fixtures["originCases"].as_array().expect("origin cases") {
            let case = case.as_object().expect("origin case");
            let origin = match case["origin"].as_str().expect("origin") {
                "python" => ProtocolOrigin::Python,
                "rust" => ProtocolOrigin::Rust,
                other => panic!("unknown fixture origin: {other}"),
            };
            let parsed = parse_protocol_value_from_origin(
                json!({
                    "protocolVersion": framework().protocol_version,
                    "messageType": "event",
                    "event": case["event"],
                    "data": {},
                }),
                origin,
            );
            if case["valid"].as_bool() == Some(true) {
                assert!(parsed.is_ok(), "{}: {parsed:?}", case["name"]);
            } else {
                assert_eq!(
                    parsed.expect_err("invalid origin").code(),
                    case["errorCode"].as_str().expect("fixture errorCode"),
                    "{}",
                    case["name"]
                );
            }
        }
    }

    #[test]
    fn requests_are_framed_without_per_method_param_rules() {
        let parsed = parse_protocol_value(json!({
            "protocolVersion": 1,
            "messageType": "request",
            "requestId": REQUEST_ID,
            "method": "session.turn",
            "params": {},
        }))
        .expect("Python owns per-method param validation");
        assert!(matches!(parsed, ProtocolMessage::Request(_)));
        assert_eq!(
            violation_code(json!({
                "protocolVersion": 1,
                "messageType": "request",
                "requestId": "not-a-uuid",
                "method": "session.turn",
                "params": {},
            })),
            "PROTOCOL_INVALID"
        );
        assert_eq!(
            violation_code(json!({
                "protocolVersion": 1,
                "messageType": "request",
                "requestId": REQUEST_ID,
                "method": "session.turn",
                "params": [],
            })),
            "PROTOCOL_INVALID"
        );
        assert_eq!(
            violation_code(json!({
                "protocolVersion": 1,
                "messageType": "request",
                "requestId": REQUEST_ID,
                "method": "session.turn",
                "params": {},
                "extra": true,
            })),
            "PROTOCOL_INVALID"
        );
    }

    #[test]
    fn envelope_shape_version_and_sequence_are_checked() {
        assert_eq!(
            violation_code(json!({"protocolVersion": 2, "messageType": "event", "event": "backend.ready", "data": {}})),
            "PROTOCOL_VERSION_UNSUPPORTED"
        );
        assert_eq!(
            violation_code(json!({"protocolVersion": 1, "messageType": "notification"})),
            "PROTOCOL_INVALID"
        );
        assert_eq!(
            violation_code(json!({"protocolVersion": 1, "messageType": "event", "requestId": REQUEST_ID, "sequence": 0, "event": "stage.changed", "data": {}})),
            "PROTOCOL_INVALID"
        );
        assert_eq!(
            violation_code(json!({"protocolVersion": 1, "messageType": "event", "requestId": REQUEST_ID, "event": "stage.changed", "data": {}})),
            "PROTOCOL_INVALID"
        );
        assert_eq!(
            violation_code(json!({"protocolVersion": 1, "messageType": "event", "event": "backend.unknown", "data": {}})),
            "PROTOCOL_INVALID"
        );
        assert_eq!(
            violation_code(json!({"protocolVersion": 1, "messageType": "result", "requestId": REQUEST_ID, "ok": true, "data": {}, "error": {"code": "INTERNAL_ERROR", "message": "x", "retryable": false, "details": {}}})),
            "PROTOCOL_INVALID"
        );
        assert_eq!(
            violation_code(json!({"protocolVersion": 1, "messageType": "result", "requestId": REQUEST_ID, "ok": false, "data": {}})),
            "PROTOCOL_INVALID"
        );
        assert_eq!(
            violation_code(json!({"protocolVersion": 1, "messageType": "result", "requestId": REQUEST_ID, "ok": false, "error": {"code": "INTERNAL_ERROR", "message": "x".repeat(4097), "retryable": false, "details": {}}})),
            "PROTOCOL_INVALID"
        );
        // Result data is routed without per-method schema checks.
        assert!(parse_protocol_value(json!({
            "protocolVersion": 1,
            "messageType": "result",
            "requestId": REQUEST_ID,
            "ok": true,
            "data": {"anyField": "Python validated this result"},
        }))
        .is_ok());
    }

    #[test]
    fn forbidden_keys_are_rejected_in_events_results_and_error_details() {
        let cases = [
            json!({"protocolVersion": 1, "messageType": "event", "requestId": REQUEST_ID, "sequence": 1, "event": "stage.changed", "data": {"nested": [{"apiKey": "x"}]}}),
            json!({"protocolVersion": 1, "messageType": "event", "event": "backend.protocol_error", "data": {"traceback": "x"}}),
            json!({"protocolVersion": 1, "messageType": "result", "requestId": REQUEST_ID, "ok": true, "data": {"toolCalls": []}}),
            json!({"protocolVersion": 1, "messageType": "result", "requestId": REQUEST_ID, "ok": false, "error": {"code": "INTERNAL_ERROR", "message": "x", "retryable": false, "details": {"rawProviderPayload": {}}}}),
        ];
        for case in cases {
            assert_eq!(violation_code(case.clone()), "PROTOCOL_INVALID", "{case}");
        }
    }
}
