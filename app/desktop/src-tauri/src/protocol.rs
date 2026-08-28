use std::collections::HashMap;
use std::error::Error;
use std::fmt::{Display, Formatter};

use serde::de::Error as DeserializeError;
use serde::{Deserialize, Deserializer, Serialize};
use serde_json::{Map, Value};

pub const PROTOCOL_VERSION: u64 = 1;
pub const MAX_PROTOCOL_LINE_BYTES: usize = 2 * 1024 * 1024;
pub const MAX_REQUEST_ID_BYTES: usize = 128;
pub const MAX_ERROR_MESSAGE_BYTES: usize = 4096;

pub const PROTOCOL_METHODS: &[&str] = &[
    "runtime.diagnostics",
    "project.list",
    "session.create",
    "session.list",
    "session.select",
    "session.retry_registration",
    "session.transcript",
    "session.status",
    "session.turn",
    "session.set_mode",
    "session.set_thinking",
    "session.list_skills",
    "session.activate_skill",
    "session.deactivate_skill",
    "session.shutdown",
    "knowledge.overview",
    "knowledge.search",
    "knowledge.list_chunks",
    "knowledge.get_context",
    "knowledge.init_workspace",
    "knowledge.ingest_file",
    "knowledge.ingest_folder",
    "knowledge.sync",
    "knowledge.prune_preview",
    "knowledge.prune_apply",
    "extensions.status",
    "extensions.preview",
    "extensions.apply",
    "approval.resolve",
    "runtime.shutdown",
];

pub const REQUEST_EVENTS: &[&str] = &[
    "request.started",
    "request.progress",
    "stage.changed",
    "tool.started",
    "tool.finished",
    "tool.failed",
    "approval.required",
    "knowledge.progress",
    "shutdown.progress",
    "collecting.started",
    "collecting.completed",
    "tagging.started",
    "tagging.folder_completed",
    "metadata.written",
    "writing.started",
    "writing.file_completed",
    "ingest.completed",
    "ingest.failed",
    "answer.chunk",
];

pub const PROCESS_EVENTS: &[&str] = &[
    "backend.ready",
    "backend.crashed",
    "backend.shutting_down",
    "backend.protocol_error",
];

pub const PROTOCOL_ERROR_CODES: &[&str] = &[
    "PROTOCOL_INVALID",
    "PROTOCOL_VERSION_UNSUPPORTED",
    "RUNTIME_WRONG_CONDA_ENV",
    "SESSION_NOT_READY",
    "OPENROUTER_NOT_CONFIGURED",
    "OLLAMA_UNREACHABLE",
    "OLLAMA_MODEL_MISSING",
    "GRAPH_LIMIT_REACHED",
    "BUSY_TURN",
    "BUSY_KNOWLEDGE_MUTATION",
    "BUSY_EXTENSION_OPERATION",
    "INVALID_PATH",
    "RAG_READ_FAILED",
    "RAG_WRITE_FAILED",
    "RAG_PARTIAL_WRITE_POSSIBLE",
    "PRUNE_PREVIEW_STALE",
    "EXTENSION_PREVIEW_FAILED",
    "EXTENSION_APPLY_FAILED",
    "APPROVAL_DENIED",
    "CONVERSATION_FLUSH_FAILED",
    "PROVIDER_RATE_LIMITED",
    "PROVIDER_REQUEST_FAILED",
    "SHUTDOWN_FLUSH_FAILED",
    "INTERNAL_ERROR",
];

const TOOL_EVENT_DATA_KEYS: &[&str] = &["name", "callId", "status", "candidateId"];
const TOOL_STATUSES: &[&str] = &["started", "ok", "failed", "denied"];
const FORBIDDEN_DATA_KEY_FRAGMENTS: &[&str] = &[
    "apikey",
    "authorization",
    "langchain",
    "messages",
    "rawpayload",
    "rawprovider",
    "responsemetadata",
    "secret",
    "token",
    "toolargs",
    "toolcalls",
    "toolresult",
    "traceback",
    "turnlogs",
];

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ProtocolOrigin {
    Python,
    Rust,
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
    if value.as_f64() == Some(PROTOCOL_VERSION as f64) {
        Ok(PROTOCOL_VERSION)
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

fn required_params(method: &str) -> Option<&'static [&'static str]> {
    match method {
        "runtime.diagnostics" => Some(&[]),
        "project.list" => Some(&[]),
        "session.create" => Some(&[]),
        "session.list" => Some(&["projectId"]),
        "session.select" | "session.retry_registration" | "session.transcript" => {
            Some(&["projectId", "sessionId"])
        }
        "session.status" => Some(&[]),
        "session.turn" => Some(&["text"]),
        "session.set_mode" => Some(&["mode"]),
        "session.set_thinking" => Some(&["mode"]),
        "session.list_skills" => Some(&[]),
        "session.activate_skill" => Some(&["name"]),
        "session.deactivate_skill" => Some(&[]),
        "session.shutdown" => Some(&[]),
        "knowledge.overview" => Some(&[]),
        "knowledge.search" => Some(&["query"]),
        "knowledge.list_chunks" => Some(&[]),
        "knowledge.get_context" => Some(&["pid", "chunkId"]),
        "knowledge.init_workspace" => Some(&[]),
        "knowledge.ingest_file" => Some(&["path"]),
        "knowledge.ingest_folder" => Some(&["path"]),
        "knowledge.sync" => Some(&["path"]),
        "knowledge.prune_preview" => Some(&["path"]),
        "knowledge.prune_apply" => Some(&["previewId"]),
        "extensions.status" => Some(&[]),
        "extensions.preview" => Some(&[]),
        "extensions.apply" => Some(&["previewId", "approvedBindingHashes"]),
        "approval.resolve" => Some(&["approvalId", "approved"]),
        "runtime.shutdown" => Some(&[]),
        _ => None,
    }
}

fn allowed_params(method: &str) -> Option<&'static [&'static str]> {
    match method {
        "runtime.diagnostics"
        | "project.list"
        | "session.status"
        | "session.list_skills"
        | "session.deactivate_skill"
        | "session.shutdown"
        | "knowledge.overview"
        | "knowledge.init_workspace"
        | "extensions.status"
        | "extensions.preview"
        | "runtime.shutdown" => Some(&[]),
        "session.create" => Some(&["loadMcp", "graphRecursionLimit", "projectId"]),
        "session.list" => Some(&["projectId", "offset", "limit"]),
        "session.select" | "session.retry_registration" => Some(&["projectId", "sessionId"]),
        "session.transcript" => Some(&["projectId", "sessionId", "offset", "limit"]),
        "session.turn" => Some(&["text"]),
        "session.set_mode" | "session.set_thinking" => Some(&["mode"]),
        "session.activate_skill" => Some(&["name", "taskMode"]),
        "knowledge.search" => Some(&[
            "query",
            "k",
            "folderPrefix",
            "category",
            "fileType",
            "dateFrom",
            "dateTo",
        ]),
        "knowledge.list_chunks" => Some(&[
            "folderPrefix",
            "pid",
            "category",
            "fileType",
            "dateFrom",
            "dateTo",
            "offset",
            "limit",
        ]),
        "knowledge.get_context" => Some(&["pid", "chunkId", "window"]),
        "knowledge.ingest_file"
        | "knowledge.ingest_folder"
        | "knowledge.sync"
        | "knowledge.prune_preview" => Some(&["path"]),
        "knowledge.prune_apply" => Some(&["previewId"]),
        "extensions.apply" => Some(&["previewId", "approvedBindingHashes"]),
        "approval.resolve" => Some(&["approvalId", "approved"]),
        _ => None,
    }
}

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
    if value.is_empty() || value.len() > MAX_REQUEST_ID_BYTES {
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

fn expect_bounded_string<'a>(
    value: &'a Value,
    field: &str,
    max_bytes: usize,
) -> Result<&'a str, ProtocolViolation> {
    let text = expect_non_empty_string(value, field)?;
    if text.len() > max_bytes {
        return Err(ProtocolViolation::invalid(format!("{field} is too large")));
    }
    Ok(text)
}

fn expect_integer_range(
    value: &Value,
    field: &str,
    minimum: i64,
    maximum: i64,
) -> Result<i64, ProtocolViolation> {
    let integer = json_integer(value)
        .ok_or_else(|| ProtocolViolation::invalid(format!("{field} must be an integer")))?;
    if integer < minimum || integer > maximum {
        return Err(ProtocolViolation::invalid(format!(
            "{field} must be between {minimum} and {maximum}"
        )));
    }
    Ok(integer)
}

fn validate_optional_string(
    params: &Map<String, Value>,
    field: &str,
    max_bytes: usize,
) -> Result<(), ProtocolViolation> {
    if let Some(value) = params.get(field) {
        expect_bounded_string(value, &format!("params.{field}"), max_bytes)?;
    }
    Ok(())
}

fn validate_optional_integer(
    params: &Map<String, Value>,
    field: &str,
    minimum: i64,
    maximum: i64,
) -> Result<(), ProtocolViolation> {
    if let Some(value) = params.get(field) {
        expect_integer_range(value, &format!("params.{field}"), minimum, maximum)?;
    }
    Ok(())
}

fn validate_params(method: &str, params: &Map<String, Value>) -> Result<(), ProtocolViolation> {
    let required = required_params(method)
        .ok_or_else(|| ProtocolViolation::invalid(format!("Unknown method: {method}")))?;
    let allowed = allowed_params(method)
        .ok_or_else(|| ProtocolViolation::invalid(format!("Unknown method: {method}")))?;
    for field in required {
        if !params.contains_key(*field) {
            return Err(ProtocolViolation::invalid(format!(
                "params.{field} is required for {method}"
            )));
        }
    }
    for field in params.keys() {
        if !allowed.contains(&field.as_str()) {
            return Err(ProtocolViolation::invalid(format!(
                "params contains unknown field: {field}"
            )));
        }
    }

    match method {
        "session.create" => {
            if let Some(load_mcp) = params.get("loadMcp") {
                if !load_mcp.is_boolean() {
                    return Err(ProtocolViolation::invalid(
                        "params.loadMcp must be a boolean",
                    ));
                }
            }
            validate_optional_integer(params, "graphRecursionLimit", 3, u32::MAX as i64)?;
            validate_optional_string(params, "projectId", 256)?;
        }
        "session.list" => {
            validate_optional_string(params, "projectId", 256)?;
            validate_optional_integer(params, "offset", 0, u32::MAX as i64)?;
            validate_optional_integer(params, "limit", 1, 50)?;
        }
        "session.select" | "session.retry_registration" => {
            validate_optional_string(params, "projectId", 256)?;
            validate_optional_string(params, "sessionId", 32)?;
        }
        "session.transcript" => {
            validate_optional_string(params, "projectId", 256)?;
            validate_optional_string(params, "sessionId", 32)?;
            validate_optional_integer(params, "offset", 0, u32::MAX as i64)?;
            validate_optional_integer(params, "limit", 1, 20)?;
        }
        "session.turn" => {
            expect_bounded_string(&params["text"], "params.text", 1_048_576)?;
        }
        "session.set_mode" => {
            let mode = expect_non_empty_string(&params["mode"], "params.mode")?;
            if !["normal", "plan"].contains(&mode) {
                return Err(ProtocolViolation::invalid(format!(
                    "params.mode contains an unknown enum value: {mode}"
                )));
            }
        }
        "session.set_thinking" => {
            let mode = expect_non_empty_string(&params["mode"], "params.mode")?;
            if !["normal", "extended"].contains(&mode) {
                return Err(ProtocolViolation::invalid(format!(
                    "params.mode contains an unknown enum value: {mode}"
                )));
            }
        }
        "session.activate_skill" => {
            validate_optional_string(params, "name", 256)?;
            validate_optional_string(params, "taskMode", 256)?;
        }
        "knowledge.search" => {
            validate_optional_string(params, "query", 16_384)?;
            validate_optional_integer(params, "k", 1, 20)?;
            for (field, max_bytes) in [
                ("folderPrefix", 8_192),
                ("category", 256),
                ("fileType", 64),
                ("dateFrom", 10),
                ("dateTo", 10),
            ] {
                validate_optional_string(params, field, max_bytes)?;
            }
        }
        "knowledge.list_chunks" => {
            for (field, max_bytes) in [
                ("folderPrefix", 8_192),
                ("pid", 1_024),
                ("category", 256),
                ("fileType", 64),
                ("dateFrom", 10),
                ("dateTo", 10),
            ] {
                validate_optional_string(params, field, max_bytes)?;
            }
            validate_optional_integer(params, "offset", 0, u32::MAX as i64)?;
            validate_optional_integer(params, "limit", 1, 100)?;
        }
        "knowledge.get_context" => {
            validate_optional_string(params, "pid", 1_024)?;
            validate_optional_integer(params, "chunkId", 0, u32::MAX as i64)?;
            validate_optional_integer(params, "window", 0, 3)?;
        }
        "knowledge.ingest_file"
        | "knowledge.ingest_folder"
        | "knowledge.sync"
        | "knowledge.prune_preview" => {
            validate_optional_string(params, "path", 8_192)?;
        }
        "knowledge.prune_apply" => {
            validate_optional_string(params, "previewId", 256)?;
        }
        "extensions.apply" => {
            validate_optional_string(params, "previewId", 256)?;
            let hashes = params["approvedBindingHashes"].as_array().ok_or_else(|| {
                ProtocolViolation::invalid("params.approvedBindingHashes must be an array")
            })?;
            if hashes.len() > 512 {
                return Err(ProtocolViolation::invalid(
                    "params.approvedBindingHashes contains too many items",
                ));
            }
            for hash in hashes {
                expect_non_empty_string(hash, "params.approvedBindingHashes[]")?;
            }
        }
        "approval.resolve" => {
            validate_optional_string(params, "approvalId", 256)?;
            if !params["approved"].is_boolean() {
                return Err(ProtocolViolation::invalid(
                    "params.approved must be a boolean",
                ));
            }
        }
        _ => {}
    }
    Ok(())
}

fn validate_tool_event(event: &str, data: &Map<String, Value>) -> Result<(), ProtocolViolation> {
    if !event.starts_with("tool.") {
        return Ok(());
    }
    for key in data.keys() {
        if !TOOL_EVENT_DATA_KEYS.contains(&key.as_str()) {
            return Err(ProtocolViolation::invalid(format!(
                "Unsafe tool event field: {key}"
            )));
        }
    }
    expect_non_empty_string(
        data.get("name")
            .ok_or_else(|| ProtocolViolation::invalid("data.name is required"))?,
        "data.name",
    )?;
    let status = expect_non_empty_string(
        data.get("status")
            .ok_or_else(|| ProtocolViolation::invalid("data.status is required"))?,
        "data.status",
    )?;
    if !TOOL_STATUSES.contains(&status) {
        return Err(ProtocolViolation::invalid(format!(
            "Unknown tool status: {status}"
        )));
    }
    for optional in ["callId", "candidateId"] {
        if let Some(value) = data.get(optional) {
            expect_non_empty_string(value, &format!("data.{optional}"))?;
        }
    }
    Ok(())
}

fn normalized_data_key(key: &str) -> String {
    key.chars()
        .flat_map(char::to_lowercase)
        .filter(|character| character.is_ascii_alphanumeric())
        .collect()
}

fn validate_safe_data(value: &Value, field: &str) -> Result<(), ProtocolViolation> {
    match value {
        Value::Array(items) => {
            for (index, item) in items.iter().enumerate() {
                validate_safe_data(item, &format!("{field}[{index}]"))?;
            }
        }
        Value::Object(object) => validate_safe_object(object, field)?,
        _ => {}
    }
    Ok(())
}

fn validate_safe_object(object: &Map<String, Value>, field: &str) -> Result<(), ProtocolViolation> {
    for (key, item) in object {
        let normalized = normalized_data_key(key);
        if FORBIDDEN_DATA_KEY_FRAGMENTS
            .iter()
            .any(|fragment| normalized.contains(fragment))
        {
            return Err(ProtocolViolation::invalid(format!(
                "{field} contains forbidden field: {key}"
            )));
        }
        validate_safe_data(item, &format!("{field}.{key}"))?;
    }
    Ok(())
}

fn validate_data_keys(
    data: &Map<String, Value>,
    allowed: &[&str],
    required: &[&str],
) -> Result<(), ProtocolViolation> {
    for key in data.keys() {
        if !allowed.contains(&key.as_str()) {
            return Err(ProtocolViolation::invalid(format!(
                "data contains unknown field: {key}"
            )));
        }
    }
    for field in required {
        if !data.contains_key(*field) {
            return Err(ProtocolViolation::invalid(format!(
                "data.{field} is required"
            )));
        }
    }
    Ok(())
}

fn validate_exact_data_keys(
    data: &Map<String, Value>,
    allowed: &[&str],
) -> Result<(), ProtocolViolation> {
    validate_data_keys(data, allowed, allowed)
}

fn is_utc_timestamp(value: &str) -> bool {
    let Some(prefix) = value.strip_suffix('Z') else {
        return false;
    };
    let (seconds, fraction) = match prefix.split_once('.') {
        Some((seconds, fraction)) => (seconds, Some(fraction)),
        None => (prefix, None),
    };
    if seconds.len() != 19 {
        return false;
    }
    for (index, byte) in seconds.bytes().enumerate() {
        let expected_separator = match index {
            4 | 7 => Some(b'-'),
            10 => Some(b'T'),
            13 | 16 => Some(b':'),
            _ => None,
        };
        if let Some(separator) = expected_separator {
            if byte != separator {
                return false;
            }
        } else if !byte.is_ascii_digit() {
            return false;
        }
    }
    let valid_fraction = fraction.is_none_or(|digits| {
        !digits.is_empty() && digits.len() <= 6 && digits.bytes().all(|byte| byte.is_ascii_digit())
    });
    if !valid_fraction {
        return false;
    }
    let number = |start: usize, end: usize| seconds[start..end].parse::<u32>().ok();
    let (Some(year), Some(month), Some(day), Some(hour), Some(minute), Some(second)) = (
        number(0, 4),
        number(5, 7),
        number(8, 10),
        number(11, 13),
        number(14, 16),
        number(17, 19),
    ) else {
        return false;
    };
    if year == 0 || !(1..=12).contains(&month) || hour > 23 || minute > 59 || second > 59 {
        return false;
    }
    let leap_year = year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
    let days_in_month = [
        31,
        if leap_year { 29 } else { 28 },
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ];
    day >= 1 && day <= days_in_month[month as usize - 1]
}

fn validate_event_data(
    event: &str,
    request_id: &str,
    data: &Map<String, Value>,
) -> Result<(), ProtocolViolation> {
    validate_safe_object(data, "data")?;
    validate_tool_event(event, data)?;
    match event {
        "answer.chunk" => {
            validate_exact_data_keys(
                data,
                &["sessionId", "turnId", "chunkIndex", "streamKind", "text"],
            )?;
            expect_bounded_string(&data["sessionId"], "data.sessionId", 32)?;
            expect_bounded_string(&data["turnId"], "data.turnId", 64)?;
            expect_integer_range(&data["chunkIndex"], "data.chunkIndex", 0, 127)?;
            if data["streamKind"] != "post_finalized" {
                return Err(ProtocolViolation::invalid(
                    "data.streamKind contains an unknown enum value",
                ));
            }
            expect_bounded_string(&data["text"], "data.text", 16_384)?;
        }
        "approval.required" => {
            const KEYS: &[&str] = &[
                "approvalId",
                "parentRequestId",
                "turnId",
                "command",
                "description",
                "executionTimeoutSeconds",
                "createdAt",
                "expiresAt",
            ];
            validate_exact_data_keys(data, KEYS)?;
            for (field, max_bytes) in [
                ("approvalId", 256),
                ("turnId", 256),
                ("command", 65_536),
                ("description", 4_096),
            ] {
                expect_bounded_string(&data[field], &format!("data.{field}"), max_bytes)?;
            }
            let parent_request_id =
                expect_non_empty_string(&data["parentRequestId"], "data.parentRequestId")?;
            validate_request_id(parent_request_id)?;
            if parent_request_id != request_id {
                return Err(ProtocolViolation::invalid(
                    "data.parentRequestId must match the event requestId",
                ));
            }
            expect_integer_range(
                &data["executionTimeoutSeconds"],
                "data.executionTimeoutSeconds",
                1,
                3_600,
            )?;
            for field in ["createdAt", "expiresAt"] {
                let timestamp = expect_non_empty_string(&data[field], &format!("data.{field}"))?;
                if !is_utc_timestamp(timestamp) {
                    return Err(ProtocolViolation::invalid(format!(
                        "data.{field} must be a UTC ISO 8601 timestamp"
                    )));
                }
            }
        }
        "collecting.started" | "writing.started" => validate_exact_data_keys(data, &[])?,
        "collecting.completed" => {
            validate_exact_data_keys(data, &["folders", "files"])?;
            for field in ["folders", "files"] {
                expect_integer_range(&data[field], &format!("data.{field}"), 0, u32::MAX as i64)?;
            }
        }
        "tagging.started" => {
            validate_exact_data_keys(data, &["total"])?;
            expect_integer_range(&data["total"], "data.total", 0, u32::MAX as i64)?;
        }
        "tagging.folder_completed" => {
            validate_exact_data_keys(data, &["completed", "total", "folder"])?;
            for field in ["completed", "total"] {
                expect_integer_range(&data[field], &format!("data.{field}"), 0, u32::MAX as i64)?;
            }
            expect_bounded_string(&data["folder"], "data.folder", 8_192)?;
        }
        "metadata.written" => {
            validate_exact_data_keys(data, &["path"])?;
            expect_bounded_string(&data["path"], "data.path", 8_192)?;
        }
        "writing.file_completed" => {
            validate_exact_data_keys(data, &["filePath", "chunks", "filesCompleted"])?;
            expect_bounded_string(&data["filePath"], "data.filePath", 8_192)?;
            for field in ["chunks", "filesCompleted"] {
                expect_integer_range(&data[field], &format!("data.{field}"), 0, u32::MAX as i64)?;
            }
        }
        "ingest.completed" => {
            validate_exact_data_keys(data, &["files", "chunks"])?;
            for field in ["files", "chunks"] {
                expect_integer_range(&data[field], &format!("data.{field}"), 0, u32::MAX as i64)?;
            }
        }
        "ingest.failed" => {
            validate_exact_data_keys(data, &["stage", "partialWritePossible"])?;
            expect_bounded_string(&data["stage"], "data.stage", 256)?;
            if !data["partialWritePossible"].is_boolean() {
                return Err(ProtocolViolation::invalid(
                    "data.partialWritePossible must be a boolean",
                ));
            }
        }
        _ => {}
    }
    Ok(())
}

fn validate_nullable_string(
    data: &Map<String, Value>,
    field: &str,
    max_bytes: usize,
) -> Result<(), ProtocolViolation> {
    if !data[field].is_null() {
        expect_bounded_string(&data[field], &format!("data.{field}"), max_bytes)?;
    }
    Ok(())
}

fn validate_nullable_boolean(
    data: &Map<String, Value>,
    field: &str,
) -> Result<(), ProtocolViolation> {
    if !data[field].is_null() && !data[field].is_boolean() {
        return Err(ProtocolViolation::invalid(format!(
            "data.{field} must be a boolean or null"
        )));
    }
    Ok(())
}

fn validate_string_array(
    value: &Value,
    field: &str,
    max_items: usize,
    item_max_bytes: usize,
) -> Result<(), ProtocolViolation> {
    let items = value
        .as_array()
        .ok_or_else(|| ProtocolViolation::invalid(format!("{field} must be an array")))?;
    if items.len() > max_items {
        return Err(ProtocolViolation::invalid(format!(
            "{field} contains too many items"
        )));
    }
    for (index, item) in items.iter().enumerate() {
        expect_bounded_string(item, &format!("{field}[{index}]"), item_max_bytes)?;
    }
    Ok(())
}

fn validate_enum(value: &Value, field: &str, allowed: &[&str]) -> Result<(), ProtocolViolation> {
    let text = expect_non_empty_string(value, field)?;
    if !allowed.contains(&text) {
        return Err(ProtocolViolation::invalid(format!(
            "{field} contains an unknown enum value"
        )));
    }
    Ok(())
}

fn validate_session_snapshot(
    data: &Map<String, Value>,
    require_registration: bool,
) -> Result<(), ProtocolViolation> {
    const BASE_KEYS: &[&str] = &[
        "sessionId",
        "turnCount",
        "graphRecursionLimit",
        "planMode",
        "planLogPath",
        "thinkingMode",
        "activeSkill",
        "taskMode",
        "loadedSkills",
        "mcpFamilies",
        "startupDiagnostics",
        "extensionRevision",
    ];
    const ALL_KEYS: &[&str] = &[
        "sessionId",
        "turnCount",
        "graphRecursionLimit",
        "planMode",
        "planLogPath",
        "thinkingMode",
        "activeSkill",
        "taskMode",
        "loadedSkills",
        "mcpFamilies",
        "startupDiagnostics",
        "extensionRevision",
        "projectId",
        "registered",
    ];
    let required = if require_registration {
        ALL_KEYS
    } else {
        BASE_KEYS
    };
    validate_data_keys(data, ALL_KEYS, required)?;
    expect_bounded_string(&data["sessionId"], "data.sessionId", 256)?;
    expect_integer_range(&data["turnCount"], "data.turnCount", 0, u32::MAX as i64)?;
    expect_integer_range(
        &data["graphRecursionLimit"],
        "data.graphRecursionLimit",
        3,
        u32::MAX as i64,
    )?;
    if !data["planMode"].is_boolean() {
        return Err(ProtocolViolation::invalid(
            "data.planMode must be a boolean",
        ));
    }
    validate_nullable_string(data, "planLogPath", 8_192)?;
    validate_enum(
        &data["thinkingMode"],
        "data.thinkingMode",
        &["normal", "extended"],
    )?;
    validate_nullable_string(data, "activeSkill", 256)?;
    validate_nullable_string(data, "taskMode", 256)?;
    validate_string_array(&data["loadedSkills"], "data.loadedSkills", 512, 256)?;
    validate_string_array(&data["mcpFamilies"], "data.mcpFamilies", 512, 256)?;
    validate_string_array(
        &data["startupDiagnostics"],
        "data.startupDiagnostics",
        512,
        4_096,
    )?;
    expect_integer_range(
        &data["extensionRevision"],
        "data.extensionRevision",
        0,
        u32::MAX as i64,
    )?;
    if let Some(project_id) = data.get("projectId") {
        expect_bounded_string(project_id, "data.projectId", 256)?;
    }
    if let Some(registered) = data.get("registered") {
        if !registered.is_boolean() {
            return Err(ProtocolViolation::invalid(
                "data.registered must be a boolean",
            ));
        }
    }
    Ok(())
}

pub fn validate_result_data(method: &str, value: &Value) -> Result<(), ProtocolViolation> {
    let data = expect_object(value, "data")?;
    validate_safe_object(data, "data")?;
    match method {
        "runtime.diagnostics" => {
            const KEYS: &[&str] = &[
                "backendState",
                "platform",
                "appRoot",
                "workingDirectory",
                "originalWorkingDirectory",
                "pythonVersion",
                "sysPrefix",
                "condaEnvironment",
                "condaPrefix",
                "protocolVersion",
                "backendVersion",
                "openRouterConfigured",
                "openAlexConfigured",
                "storePath",
                "citationOutputPath",
                "ollamaReachable",
                "ollamaModelAvailable",
                "mcpEnabled",
                "mcpFamilies",
                "mcpDiagnostics",
            ];
            validate_exact_data_keys(data, KEYS)?;
            let backend_state =
                expect_non_empty_string(&data["backendState"], "data.backendState")?;
            if !["starting", "ready", "shutting_down", "stopped", "crashed"]
                .contains(&backend_state)
            {
                return Err(ProtocolViolation::invalid(
                    "data.backendState contains an unknown enum value",
                ));
            }
            if data["platform"] != "linux" {
                return Err(ProtocolViolation::invalid(
                    "data.platform contains an unknown enum value",
                ));
            }
            for (field, max_bytes) in [
                ("appRoot", 8_192),
                ("workingDirectory", 8_192),
                ("originalWorkingDirectory", 8_192),
                ("pythonVersion", 256),
                ("sysPrefix", 8_192),
                ("backendVersion", 256),
                ("storePath", 8_192),
                ("citationOutputPath", 8_192),
            ] {
                expect_bounded_string(&data[field], &format!("data.{field}"), max_bytes)?;
            }
            validate_nullable_string(data, "condaEnvironment", 256)?;
            validate_nullable_string(data, "condaPrefix", 8_192)?;
            expect_integer_range(&data["protocolVersion"], "data.protocolVersion", 1, 1)?;
            for field in ["openRouterConfigured", "openAlexConfigured", "mcpEnabled"] {
                if !data[field].is_boolean() {
                    return Err(ProtocolViolation::invalid(format!(
                        "data.{field} must be a boolean"
                    )));
                }
            }
            validate_nullable_boolean(data, "ollamaReachable")?;
            validate_nullable_boolean(data, "ollamaModelAvailable")?;
            validate_string_array(&data["mcpFamilies"], "data.mcpFamilies", 512, 256)?;
            validate_string_array(&data["mcpDiagnostics"], "data.mcpDiagnostics", 512, 4_096)?;
        }
        "session.create" => validate_session_snapshot(data, false)?,
        "session.select" => validate_session_snapshot(data, true)?,
        "session.turn" => {
            validate_data_keys(
                data,
                &[
                    "sessionId",
                    "turnId",
                    "text",
                    "validationErrors",
                    "toolSummaries",
                    "responseKind",
                    "streamKind",
                    "chunkCount",
                    "registrationStatus",
                    "registrationIssue",
                ],
                &[
                    "sessionId",
                    "turnId",
                    "text",
                    "validationErrors",
                    "toolSummaries",
                ],
            )?;
            expect_bounded_string(&data["sessionId"], "data.sessionId", 256)?;
            expect_bounded_string(&data["turnId"], "data.turnId", 256)?;
            expect_bounded_string(&data["text"], "data.text", MAX_PROTOCOL_LINE_BYTES)?;
            validate_string_array(
                &data["validationErrors"],
                "data.validationErrors",
                128,
                4_096,
            )?;
            let summaries = data["toolSummaries"]
                .as_array()
                .ok_or_else(|| ProtocolViolation::invalid("data.toolSummaries must be an array"))?;
            if summaries.len() > 512 {
                return Err(ProtocolViolation::invalid(
                    "data.toolSummaries contains too many items",
                ));
            }
            for (index, summary) in summaries.iter().enumerate() {
                let summary = expect_object(summary, &format!("data.toolSummaries[{index}]"))?;
                validate_data_keys(
                    summary,
                    &["name", "status", "callId", "candidateId"],
                    &["name", "status"],
                )?;
                expect_bounded_string(
                    &summary["name"],
                    &format!("data.toolSummaries[{index}].name"),
                    256,
                )?;
                let status = expect_non_empty_string(
                    &summary["status"],
                    &format!("data.toolSummaries[{index}].status"),
                )?;
                if !["ok", "failed", "denied"].contains(&status) {
                    return Err(ProtocolViolation::invalid(
                        "data.toolSummaries status contains an unknown enum value",
                    ));
                }
                for optional in ["callId", "candidateId"] {
                    if let Some(value) = summary.get(optional) {
                        expect_bounded_string(
                            value,
                            &format!("data.toolSummaries[{index}].{optional}"),
                            256,
                        )?;
                    }
                }
            }
            if let Some(value) = data.get("responseKind") {
                validate_enum(value, "data.responseKind", &["answer", "command"])?;
            }
            if let Some(value) = data.get("streamKind") {
                validate_enum(value, "data.streamKind", &["post_finalized", "final_only"])?;
            }
            if let Some(value) = data.get("chunkCount") {
                expect_integer_range(value, "data.chunkCount", 0, 128)?;
            }
            if let Some(value) = data.get("registrationStatus") {
                validate_enum(
                    value,
                    "data.registrationStatus",
                    &["registered", "pending", "not_required"],
                )?;
            }
            if let Some(value) = data.get("registrationIssue") {
                if !value.is_null() {
                    expect_bounded_string(value, "data.registrationIssue", 4_096)?;
                }
            }
        }
        "project.list" => {
            validate_exact_data_keys(
                data,
                &[
                    "status",
                    "issue",
                    "projects",
                    "selectedProjectId",
                    "selectedSessionId",
                ],
            )?;
            validate_enum(&data["status"], "data.status", &["ready", "unavailable"])?;
            validate_nullable_string(data, "issue", 4_096)?;
            validate_nullable_string(data, "selectedProjectId", 256)?;
            validate_nullable_string(data, "selectedSessionId", 32)?;
            let projects = data["projects"]
                .as_array()
                .ok_or_else(|| ProtocolViolation::invalid("data.projects must be an array"))?;
            if projects.len() > 50 {
                return Err(ProtocolViolation::invalid(
                    "data.projects contains too many items",
                ));
            }
            for (index, project) in projects.iter().enumerate() {
                let project = expect_object(project, &format!("data.projects[{index}]"))?;
                validate_exact_data_keys(project, &["projectId", "name", "sessionCount"])?;
                expect_bounded_string(
                    &project["projectId"],
                    &format!("data.projects[{index}].projectId"),
                    256,
                )?;
                expect_bounded_string(
                    &project["name"],
                    &format!("data.projects[{index}].name"),
                    256,
                )?;
                expect_integer_range(
                    &project["sessionCount"],
                    &format!("data.projects[{index}].sessionCount"),
                    0,
                    u32::MAX as i64,
                )?;
            }
        }
        "session.list" => {
            validate_exact_data_keys(
                data,
                &[
                    "projectId",
                    "status",
                    "issue",
                    "items",
                    "total",
                    "offset",
                    "limit",
                    "hasMore",
                ],
            )?;
            expect_bounded_string(&data["projectId"], "data.projectId", 256)?;
            validate_enum(&data["status"], "data.status", &["ready", "unavailable"])?;
            validate_nullable_string(data, "issue", 4_096)?;
            let items = data["items"]
                .as_array()
                .ok_or_else(|| ProtocolViolation::invalid("data.items must be an array"))?;
            if items.len() > 50 {
                return Err(ProtocolViolation::invalid(
                    "data.items contains too many items",
                ));
            }
            for (index, item) in items.iter().enumerate() {
                let item = expect_object(item, &format!("data.items[{index}]"))?;
                validate_exact_data_keys(
                    item,
                    &[
                        "sessionId",
                        "title",
                        "turnCount",
                        "updatedAt",
                        "status",
                        "issue",
                    ],
                )?;
                expect_bounded_string(
                    &item["sessionId"],
                    &format!("data.items[{index}].sessionId"),
                    32,
                )?;
                expect_bounded_string(&item["title"], &format!("data.items[{index}].title"), 256)?;
                expect_integer_range(
                    &item["turnCount"],
                    &format!("data.items[{index}].turnCount"),
                    0,
                    u32::MAX as i64,
                )?;
                if !item["updatedAt"].is_null() {
                    expect_bounded_string(
                        &item["updatedAt"],
                        &format!("data.items[{index}].updatedAt"),
                        64,
                    )?;
                }
                validate_enum(
                    &item["status"],
                    &format!("data.items[{index}].status"),
                    &["ready", "degraded", "unavailable"],
                )?;
                if !item["issue"].is_null() {
                    expect_bounded_string(
                        &item["issue"],
                        &format!("data.items[{index}].issue"),
                        4_096,
                    )?;
                }
            }
            for field in ["total", "offset"] {
                expect_integer_range(&data[field], &format!("data.{field}"), 0, u32::MAX as i64)?;
            }
            expect_integer_range(&data["limit"], "data.limit", 1, 50)?;
            if !data["hasMore"].is_boolean() {
                return Err(ProtocolViolation::invalid("data.hasMore must be a boolean"));
            }
        }
        "session.retry_registration" => {
            validate_exact_data_keys(data, &["projectId", "sessionId", "status", "issue"])?;
            expect_bounded_string(&data["projectId"], "data.projectId", 256)?;
            expect_bounded_string(&data["sessionId"], "data.sessionId", 32)?;
            validate_enum(&data["status"], "data.status", &["registered", "pending"])?;
            validate_nullable_string(data, "issue", 4_096)?;
        }
        "session.transcript" => {
            validate_exact_data_keys(
                data,
                &[
                    "projectId",
                    "sessionId",
                    "status",
                    "issue",
                    "items",
                    "total",
                    "offset",
                    "limit",
                    "hasMore",
                ],
            )?;
            expect_bounded_string(&data["projectId"], "data.projectId", 256)?;
            expect_bounded_string(&data["sessionId"], "data.sessionId", 32)?;
            validate_enum(
                &data["status"],
                "data.status",
                &["ready", "degraded", "unavailable"],
            )?;
            validate_nullable_string(data, "issue", 4_096)?;
            let items = data["items"]
                .as_array()
                .ok_or_else(|| ProtocolViolation::invalid("data.items must be an array"))?;
            if items.len() > 20 {
                return Err(ProtocolViolation::invalid(
                    "data.items contains too many items",
                ));
            }
            for (index, item) in items.iter().enumerate() {
                let item = expect_object(item, &format!("data.items[{index}]"))?;
                validate_exact_data_keys(
                    item,
                    &["turnNumber", "timestamp", "userText", "assistantText"],
                )?;
                expect_integer_range(
                    &item["turnNumber"],
                    &format!("data.items[{index}].turnNumber"),
                    1,
                    u32::MAX as i64,
                )?;
                for (field, max_bytes) in [
                    ("timestamp", 64),
                    ("userText", 32_768),
                    ("assistantText", 32_768),
                ] {
                    expect_bounded_string(
                        &item[field],
                        &format!("data.items[{index}].{field}"),
                        max_bytes,
                    )?;
                }
            }
            for field in ["total", "offset"] {
                expect_integer_range(&data[field], &format!("data.{field}"), 0, u32::MAX as i64)?;
            }
            expect_integer_range(&data["limit"], "data.limit", 1, 20)?;
            if !data["hasMore"].is_boolean() {
                return Err(ProtocolViolation::invalid("data.hasMore must be a boolean"));
            }
        }
        "extensions.preview" => {
            validate_exact_data_keys(
                data,
                &["previewId", "summary", "proposedSkills", "bindings"],
            )?;
            expect_bounded_string(&data["previewId"], "data.previewId", 256)?;
            expect_bounded_string(&data["summary"], "data.summary", 4_096)?;
            validate_string_array(&data["proposedSkills"], "data.proposedSkills", 512, 256)?;
            let bindings = data["bindings"]
                .as_array()
                .ok_or_else(|| ProtocolViolation::invalid("data.bindings must be an array"))?;
            if bindings.len() > 512 {
                return Err(ProtocolViolation::invalid(
                    "data.bindings contains too many items",
                ));
            }
            for (index, binding) in bindings.iter().enumerate() {
                let binding = expect_object(binding, &format!("data.bindings[{index}]"))?;
                validate_exact_data_keys(
                    binding,
                    &["name", "server", "bindingHash", "requiresApproval"],
                )?;
                for field in ["name", "server", "bindingHash"] {
                    expect_bounded_string(
                        &binding[field],
                        &format!("data.bindings[{index}].{field}"),
                        256,
                    )?;
                }
                if !binding["requiresApproval"].is_boolean() {
                    return Err(ProtocolViolation::invalid(
                        "data.bindings requiresApproval must be a boolean",
                    ));
                }
            }
        }
        _ => {}
    }
    Ok(())
}

pub fn validate_process_event_origin(
    event: &str,
    origin: ProtocolOrigin,
) -> Result<(), ProtocolViolation> {
    let allowed = match event {
        "backend.ready" => origin == ProtocolOrigin::Python,
        "backend.crashed" => origin == ProtocolOrigin::Rust,
        "backend.shutting_down" | "backend.protocol_error" => true,
        _ => false,
    };
    if !allowed {
        return Err(ProtocolViolation::invalid(format!(
            "{event} cannot originate from {origin:?}"
        )));
    }
    Ok(())
}

pub fn parse_protocol_line(line: &str) -> Result<ProtocolMessage, ProtocolViolation> {
    if line.len() > MAX_PROTOCOL_LINE_BYTES {
        return Err(ProtocolViolation::invalid(
            "Protocol line exceeds the 2 MiB limit",
        ));
    }
    let value: Value = serde_json::from_str(line)
        .map_err(|_| ProtocolViolation::invalid("Protocol line is not valid JSON"))?;
    parse_protocol_value(value)
}

pub fn parse_protocol_line_from_origin(
    line: &str,
    origin: ProtocolOrigin,
) -> Result<ProtocolMessage, ProtocolViolation> {
    let message = parse_protocol_line(line)?;
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
    if version.as_f64() != Some(PROTOCOL_VERSION as f64) {
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
            let params = expect_object(&request.params, "params")?;
            validate_params(&request.method, params)?;
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
            let data = expect_object(&event.data, "data")?;
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
                if !REQUEST_EVENTS.contains(&event.event.as_str()) {
                    return Err(ProtocolViolation::invalid(format!(
                        "Unknown request event: {}",
                        event.event
                    )));
                }
                validate_event_data(&event.event, request_id, data)?;
            } else {
                if !PROCESS_EVENTS.contains(&event.event.as_str()) {
                    return Err(ProtocolViolation::invalid(format!(
                        "Unknown process event: {}",
                        event.event
                    )));
                }
                validate_safe_data(&event.data, "data")?;
            }
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
            if result.ok {
                if result.error.is_some() {
                    return Err(ProtocolViolation::invalid(
                        "Successful results cannot contain error",
                    ));
                }
                let data = result
                    .data
                    .as_ref()
                    .ok_or_else(|| ProtocolViolation::invalid("data is required"))?;
                expect_object(
                    result
                        .data
                        .as_ref()
                        .ok_or_else(|| ProtocolViolation::invalid("data is required"))?,
                    "data",
                )?;
                validate_safe_data(data, "data")?;
            } else {
                if result.data.is_some() {
                    return Err(ProtocolViolation::invalid(
                        "Failed results cannot contain data",
                    ));
                }
                let error = result
                    .error
                    .as_ref()
                    .ok_or_else(|| ProtocolViolation::invalid("error is required"))?;
                if !PROTOCOL_ERROR_CODES.contains(&error.code.as_str()) {
                    return Err(ProtocolViolation::invalid(format!(
                        "Unknown error code: {}",
                        error.code
                    )));
                }
                if error.message.is_empty() || error.message.len() > MAX_ERROR_MESSAGE_BYTES {
                    return Err(ProtocolViolation::invalid(
                        "error.message has an invalid size",
                    ));
                }
                let details = expect_object(&error.details, "error.details")?;
                validate_safe_data(&error.details, "error.details")?;
                if error.code == "INTERNAL_ERROR" && !details.is_empty() {
                    return Err(ProtocolViolation::invalid(
                        "INTERNAL_ERROR details must be empty",
                    ));
                }
            }
            Ok(ProtocolMessage::Result(result))
        }
        other => Err(ProtocolViolation::invalid(format!(
            "Unknown messageType: {other}"
        ))),
    }
}

#[derive(Debug, Default)]
pub struct ProtocolTraceValidator {
    requests: HashMap<String, RequestTraceState>,
}

#[derive(Debug)]
struct RequestTraceState {
    next_sequence: u64,
    terminal: bool,
    method: String,
}

impl ProtocolTraceValidator {
    pub fn accept(&mut self, message: &ProtocolMessage) -> Result<(), ProtocolViolation> {
        match message {
            ProtocolMessage::Request(request) => {
                if self.requests.contains_key(&request.request_id) {
                    return Err(ProtocolViolation::invalid(format!(
                        "Duplicate requestId: {}",
                        request.request_id
                    )));
                }
                self.requests.insert(
                    request.request_id.clone(),
                    RequestTraceState {
                        next_sequence: 1,
                        terminal: false,
                        method: request.method.clone(),
                    },
                );
            }
            ProtocolMessage::Event(event) => {
                let Some(request_id) = &event.request_id else {
                    return Ok(());
                };
                let state = self.requests.get_mut(request_id).ok_or_else(|| {
                    ProtocolViolation::invalid(format!(
                        "Event references unknown requestId: {request_id}"
                    ))
                })?;
                if state.terminal {
                    return Err(ProtocolViolation::invalid(format!(
                        "Event arrived after terminal result: {request_id}"
                    )));
                }
                let sequence = event.sequence.expect("validated request event sequence");
                if sequence != state.next_sequence {
                    return Err(ProtocolViolation::invalid(format!(
                        "Expected sequence {}, received {sequence}",
                        state.next_sequence
                    )));
                }
                state.next_sequence += 1;
            }
            ProtocolMessage::Result(result) => {
                let state = self.requests.get_mut(&result.request_id).ok_or_else(|| {
                    ProtocolViolation::invalid(format!(
                        "Result references unknown requestId: {}",
                        result.request_id
                    ))
                })?;
                if state.terminal {
                    return Err(ProtocolViolation::invalid(format!(
                        "Duplicate terminal result: {}",
                        result.request_id
                    )));
                }
                if result.ok {
                    validate_result_data(
                        &state.method,
                        result.data.as_ref().expect("validated success result data"),
                    )?;
                }
                state.terminal = true;
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const CONTRACT: &str = include_str!("../../protocol/v1/contract.json");
    const FIXTURES: &str = include_str!("../../protocol/v1/fixtures.json");

    fn expected_error(case: &Map<String, Value>) -> &str {
        case["errorCode"]
            .as_str()
            .expect("invalid fixture errorCode")
    }

    fn sample_field_value(rule: &Value, request_id: &str) -> Value {
        match rule["type"].as_str().expect("field type") {
            "string" => rule["enum"]
                .as_array()
                .and_then(|values| values.first())
                .cloned()
                .unwrap_or_else(|| Value::String("x".to_owned())),
            "boolean" => Value::Bool(false),
            "nullableString" | "nullableBoolean" => Value::Null,
            "integer" => Value::from(rule["minimum"].as_i64().unwrap_or(0)),
            "stringArray" => Value::Array(Vec::new()),
            "objectArray" => {
                let item = rule["items"]
                    .as_object()
                    .expect("object array item schema")
                    .iter()
                    .map(|(field, item_rule)| {
                        (field.clone(), sample_field_value(item_rule, request_id))
                    })
                    .collect::<Map<_, _>>();
                Value::Array(vec![Value::Object(item)])
            }
            "requestId" => Value::String(request_id.to_owned()),
            "utcTimestamp" => Value::String("2026-08-24T01:02:03Z".to_owned()),
            other => panic!("unknown field type: {other}"),
        }
    }

    fn invalid_boundary_values(rule: &Value) -> Vec<Value> {
        let mut invalid_values = vec![match rule["type"].as_str().expect("field type") {
            "string" | "nullableString" | "requestId" | "utcTimestamp" => Value::Bool(true),
            "boolean" | "nullableBoolean" | "integer" => Value::String("wrong".to_owned()),
            "stringArray" | "objectArray" => Value::Bool(true),
            other => panic!("unknown field type: {other}"),
        }];
        if let Some(minimum) = rule["minimum"].as_i64() {
            invalid_values.push(Value::from(minimum - 1));
        }
        if let Some(maximum) = rule["maximum"].as_i64() {
            invalid_values.push(Value::from(maximum + 1));
        }
        if let Some(max_bytes) = rule["maxBytes"].as_u64() {
            invalid_values.push(Value::String("x".repeat(max_bytes as usize + 1)));
        }
        if let Some(max_items) = rule["maxItems"].as_u64() {
            invalid_values.push(Value::Array(vec![
                Value::String("x".to_owned());
                max_items as usize + 1
            ]));
        }
        if let Some(item_max_bytes) = rule["itemMaxBytes"].as_u64() {
            invalid_values.push(Value::Array(vec![Value::String(
                "x".repeat(item_max_bytes as usize + 1),
            )]));
        }
        if rule["enum"].is_array() {
            invalid_values.push(Value::String("unknown-enum".to_owned()));
        }
        if rule["type"] == "utcTimestamp" {
            invalid_values.push(Value::String("2026-08-24 01:02:03".to_owned()));
        }
        if rule["type"] == "requestId" {
            invalid_values.push(Value::String("not-a-uuid".to_owned()));
        }
        invalid_values
    }

    fn assert_field_boundaries_rejected(base: &Value, container: &str, field: &str, rule: &Value) {
        for invalid_value in invalid_boundary_values(rule) {
            let mut message = base.clone();
            message[container][field] = invalid_value;
            assert!(
                parse_protocol_value(message).is_err(),
                "{container}.{field} boundary must be rejected"
            );
        }
    }

    fn validate_result_trace(
        method: &str,
        params: Value,
        data: Value,
    ) -> Result<(), ProtocolViolation> {
        const REQUEST_ID: &str = "00000000-0000-4000-8000-000000000052";
        let request = parse_protocol_value(serde_json::json!({
            "protocolVersion": PROTOCOL_VERSION,
            "messageType": "request",
            "requestId": REQUEST_ID,
            "method": method,
            "params": params,
        }))?;
        let result = parse_protocol_value(serde_json::json!({
            "protocolVersion": PROTOCOL_VERSION,
            "messageType": "result",
            "requestId": REQUEST_ID,
            "ok": true,
            "data": data,
        }))?;
        let mut tracker = ProtocolTraceValidator::default();
        tracker.accept(&request)?;
        tracker.accept(&result)
    }

    #[test]
    fn manifest_matches_rust_constants() {
        let contract: Value = serde_json::from_str(CONTRACT).expect("contract JSON");
        assert_eq!(contract["protocolVersion"].as_u64(), Some(PROTOCOL_VERSION));
        assert_eq!(
            contract["maxLineBytes"].as_u64(),
            Some(MAX_PROTOCOL_LINE_BYTES as u64)
        );
        assert_eq!(
            contract["requestIdMaxBytes"].as_u64(),
            Some(MAX_REQUEST_ID_BYTES as u64)
        );
        assert_eq!(
            contract["errorMessageMaxBytes"].as_u64(),
            Some(MAX_ERROR_MESSAGE_BYTES as u64)
        );

        let methods = contract["methods"]
            .as_array()
            .expect("methods")
            .iter()
            .map(|method| method["name"].as_str().expect("method name"))
            .collect::<Vec<_>>();
        assert_eq!(methods, PROTOCOL_METHODS);
        let request_events = contract["requestEvents"]
            .as_array()
            .expect("request events")
            .iter()
            .map(|event| event.as_str().expect("request event"))
            .collect::<Vec<_>>();
        assert_eq!(request_events, REQUEST_EVENTS);
        let process_events = contract["processEvents"]
            .as_array()
            .expect("process events")
            .iter()
            .map(|event| event.as_str().expect("process event"))
            .collect::<Vec<_>>();
        assert_eq!(process_events, PROCESS_EVENTS);
        for event in PROCESS_EVENTS {
            let declared_origins = contract["processEventOrigins"][event]
                .as_array()
                .expect("process event origins");
            for (name, origin) in [
                ("python", ProtocolOrigin::Python),
                ("rust", ProtocolOrigin::Rust),
            ] {
                assert_eq!(
                    validate_process_event_origin(event, origin).is_ok(),
                    declared_origins.iter().any(|value| value == name),
                    "{event} from {name}"
                );
            }
        }
        let forbidden_data_keys = contract["forbiddenDataKeyFragments"]
            .as_array()
            .expect("forbidden data keys")
            .iter()
            .map(|key| key.as_str().expect("forbidden data key"))
            .collect::<Vec<_>>();
        assert_eq!(forbidden_data_keys, FORBIDDEN_DATA_KEY_FRAGMENTS);
        let error_codes = contract["errorCodes"]
            .as_array()
            .expect("error codes")
            .iter()
            .map(|code| code.as_str().expect("error code"))
            .collect::<Vec<_>>();
        assert_eq!(error_codes, PROTOCOL_ERROR_CODES);

        for method in contract["methods"].as_array().expect("methods") {
            let name = method["name"].as_str().expect("method name");
            let required = method["requiredParams"]
                .as_array()
                .expect("required params")
                .iter()
                .map(|field| field.as_str().expect("required field"))
                .collect::<Vec<_>>();
            assert_eq!(
                required,
                required_params(name).expect("known method"),
                "{name}"
            );
            let mut declared_allowed = method["params"]
                .as_object()
                .expect("params schema")
                .keys()
                .map(String::as_str)
                .collect::<Vec<_>>();
            let mut rust_allowed = allowed_params(name).expect("known method").to_vec();
            declared_allowed.sort_unstable();
            rust_allowed.sort_unstable();
            assert_eq!(declared_allowed, rust_allowed, "{name}");
            if method["operation"] == "destructive" {
                assert!(required.contains(&"previewId"), "{name}");
            }
        }
        for forbidden in [
            "run_slash_command",
            "run_shell",
            "read_arbitrary_file",
            "set_any_config_field",
        ] {
            assert!(!PROTOCOL_METHODS.contains(&forbidden));
        }
    }

    #[test]
    fn rust_request_param_rules_match_manifest() {
        const REQUEST_ID: &str = "00000000-0000-4000-8000-000000000050";
        let contract: Value = serde_json::from_str(CONTRACT).expect("contract JSON");
        for method in contract["methods"].as_array().expect("methods") {
            let method_name = method["name"].as_str().expect("method name");
            let schema = method["params"].as_object().expect("params schema");
            let params = schema
                .iter()
                .map(|(field, rule)| (field.clone(), sample_field_value(rule, REQUEST_ID)))
                .collect::<Map<_, _>>();
            let message = serde_json::json!({
                "protocolVersion": PROTOCOL_VERSION,
                "messageType": "request",
                "requestId": REQUEST_ID,
                "method": method_name,
                "params": params,
            });
            assert!(
                parse_protocol_value(message.clone()).is_ok(),
                "{method_name} full schema"
            );

            let mut extra = message.clone();
            extra["params"]["unexpected"] = Value::Bool(true);
            assert!(
                parse_protocol_value(extra).is_err(),
                "{method_name} extra param"
            );

            for (field, rule) in schema {
                let mut null_value = message.clone();
                null_value["params"][field] = Value::Null;
                assert!(
                    parse_protocol_value(null_value).is_err(),
                    "{method_name}.{field} null"
                );
                if rule["required"] == true {
                    let mut missing = message.clone();
                    missing["params"]
                        .as_object_mut()
                        .expect("params")
                        .remove(field);
                    assert!(
                        parse_protocol_value(missing).is_err(),
                        "{method_name}.{field} missing"
                    );
                }
                assert_field_boundaries_rejected(&message, "params", field, rule);
            }
        }
    }

    #[test]
    fn rust_event_data_rules_match_manifest() {
        const REQUEST_ID: &str = "00000000-0000-4000-8000-000000000051";
        let contract: Value = serde_json::from_str(CONTRACT).expect("contract JSON");
        for (event, schema_value) in contract["eventDataSchemas"]
            .as_object()
            .expect("event data schemas")
        {
            let schema = schema_value.as_object().expect("event data schema");
            let data = schema
                .iter()
                .map(|(field, rule)| (field.clone(), sample_field_value(rule, REQUEST_ID)))
                .collect::<Map<_, _>>();
            let message = serde_json::json!({
                "protocolVersion": PROTOCOL_VERSION,
                "messageType": "event",
                "requestId": REQUEST_ID,
                "sequence": 1,
                "event": event,
                "data": data,
            });
            assert!(
                parse_protocol_value(message.clone()).is_ok(),
                "{event} full schema"
            );

            let mut extra = message.clone();
            extra["data"]["unexpected"] = Value::Bool(true);
            assert!(parse_protocol_value(extra).is_err(), "{event} extra data");

            for (field, rule) in schema {
                let mut null_value = message.clone();
                null_value["data"][field] = Value::Null;
                assert!(
                    parse_protocol_value(null_value).is_err(),
                    "{event}.{field} null"
                );
                let mut missing = message.clone();
                missing["data"].as_object_mut().expect("data").remove(field);
                assert!(
                    parse_protocol_value(missing).is_err(),
                    "{event}.{field} missing"
                );
                assert_field_boundaries_rejected(&message, "data", field, rule);
            }
        }
    }

    #[test]
    fn rust_result_data_rules_match_manifest() {
        const REQUEST_ID: &str = "00000000-0000-4000-8000-000000000052";
        let contract: Value = serde_json::from_str(CONTRACT).expect("contract JSON");
        for (method, schema_value) in contract["resultDataSchemas"]
            .as_object()
            .expect("result data schemas")
        {
            let method_contract = contract["methods"]
                .as_array()
                .expect("methods")
                .iter()
                .find(|item| item["name"] == *method)
                .expect("result method contract");
            let params = method_contract["params"]
                .as_object()
                .expect("params schema")
                .iter()
                .map(|(field, rule)| (field.clone(), sample_field_value(rule, REQUEST_ID)))
                .collect::<Map<_, _>>();
            let schema = schema_value.as_object().expect("result data schema");
            let data = schema
                .iter()
                .map(|(field, rule)| (field.clone(), sample_field_value(rule, REQUEST_ID)))
                .collect::<Map<_, _>>();
            assert!(
                validate_result_trace(
                    method,
                    Value::Object(params.clone()),
                    Value::Object(data.clone()),
                )
                .is_ok(),
                "{method} full result schema"
            );

            let mut extra = data.clone();
            extra.insert("unexpected".to_owned(), Value::Bool(true));
            assert!(
                validate_result_trace(method, Value::Object(params.clone()), Value::Object(extra),)
                    .is_err(),
                "{method} extra result data"
            );

            for (field, rule) in schema {
                let nullable = matches!(
                    rule["type"].as_str(),
                    Some("nullableString" | "nullableBoolean")
                );
                let mut null_value = data.clone();
                null_value.insert(field.clone(), Value::Null);
                assert_eq!(
                    validate_result_trace(
                        method,
                        Value::Object(params.clone()),
                        Value::Object(null_value),
                    )
                    .is_ok(),
                    nullable,
                    "{method}.{field} null"
                );

                let mut missing = data.clone();
                missing.remove(field);
                assert_eq!(
                    validate_result_trace(
                        method,
                        Value::Object(params.clone()),
                        Value::Object(missing),
                    )
                    .is_ok(),
                    rule["required"] == false,
                    "{method}.{field} missing"
                );

                for invalid_value in invalid_boundary_values(rule) {
                    let mut invalid_data = data.clone();
                    invalid_data.insert(field.clone(), invalid_value);
                    assert!(
                        validate_result_trace(
                            method,
                            Value::Object(params.clone()),
                            Value::Object(invalid_data),
                        )
                        .is_err(),
                        "{method}.{field} boundary"
                    );
                }

                if rule["type"] == "objectArray" {
                    let item_schema = rule["items"].as_object().expect("item schema");
                    let mut extra_item = data.clone();
                    extra_item[field][0]["unexpected"] = Value::Bool(true);
                    assert!(
                        validate_result_trace(
                            method,
                            Value::Object(params.clone()),
                            Value::Object(extra_item),
                        )
                        .is_err(),
                        "{method}.{field} extra item field"
                    );
                    for (item_field, item_rule) in item_schema {
                        let mut missing_item = data.clone();
                        missing_item[field][0]
                            .as_object_mut()
                            .expect("item")
                            .remove(item_field);
                        assert_eq!(
                            validate_result_trace(
                                method,
                                Value::Object(params.clone()),
                                Value::Object(missing_item),
                            )
                            .is_ok(),
                            item_rule["required"] == false,
                            "{method}.{field}.{item_field} missing"
                        );
                        for invalid_value in invalid_boundary_values(item_rule) {
                            let mut invalid_item = data.clone();
                            invalid_item[field][0][item_field] = invalid_value;
                            assert!(
                                validate_result_trace(
                                    method,
                                    Value::Object(params.clone()),
                                    Value::Object(invalid_item),
                                )
                                .is_err(),
                                "{method}.{field}.{item_field} boundary"
                            );
                        }
                    }
                }
            }
        }
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
            let result = validate_process_event_origin(
                case["event"].as_str().expect("process event"),
                origin,
            );
            let line = serde_json::json!({
                "protocolVersion": PROTOCOL_VERSION,
                "messageType": "event",
                "event": case["event"],
                "data": {},
            })
            .to_string();
            let parsed_from_origin = parse_protocol_line_from_origin(&line, origin);
            if case["valid"].as_bool() == Some(true) {
                assert!(result.is_ok(), "{}: {result:?}", case["name"]);
                assert!(
                    parsed_from_origin.is_ok(),
                    "{}: {parsed_from_origin:?}",
                    case["name"]
                );
            } else {
                assert_eq!(
                    result.expect_err("invalid origin").code(),
                    expected_error(case)
                );
                assert_eq!(
                    parsed_from_origin.expect_err("invalid origin line").code(),
                    expected_error(case)
                );
            }
        }
    }

    #[test]
    fn shared_message_fixtures() {
        let fixtures: Value = serde_json::from_str(FIXTURES).expect("fixtures JSON");
        for case in fixtures["messages"].as_array().expect("messages") {
            let case = case.as_object().expect("message case");
            let result = parse_protocol_value(case["message"].clone());
            if case["valid"].as_bool() == Some(true) {
                assert!(result.is_ok(), "{}: {result:?}", case["name"]);
            } else {
                assert_eq!(
                    result.expect_err("invalid message").code(),
                    expected_error(case)
                );
            }
        }
    }

    #[test]
    fn shared_raw_lines_and_size_limit() {
        let fixtures: Value = serde_json::from_str(FIXTURES).expect("fixtures JSON");
        for case in fixtures["rawLines"].as_array().expect("raw lines") {
            let case = case.as_object().expect("raw line case");
            let result = parse_protocol_line(case["line"].as_str().expect("line"));
            if case["valid"].as_bool() == Some(true) {
                assert!(result.is_ok(), "{}: {result:?}", case["name"]);
            } else {
                assert_eq!(
                    result.expect_err("invalid line").code(),
                    expected_error(case)
                );
            }
        }

        let oversized = format!(
            "{{\"padding\":\"{}\"}}",
            "x".repeat(MAX_PROTOCOL_LINE_BYTES)
        );
        assert_eq!(
            parse_protocol_line(&oversized)
                .expect_err("oversized line")
                .code(),
            "PROTOCOL_INVALID"
        );
    }

    #[test]
    fn shared_ordering_and_correlation_traces() {
        let fixtures: Value = serde_json::from_str(FIXTURES).expect("fixtures JSON");
        for case in fixtures["traces"].as_array().expect("traces") {
            let case = case.as_object().expect("trace case");
            let mut tracker = ProtocolTraceValidator::default();
            let result = case["messages"]
                .as_array()
                .expect("trace messages")
                .iter()
                .try_for_each(|value| {
                    let message = parse_protocol_value(value.clone())?;
                    tracker.accept(&message)
                });
            if case["valid"].as_bool() == Some(true) {
                assert!(result.is_ok(), "{}: {result:?}", case["name"]);
            } else {
                assert_eq!(
                    result.expect_err("invalid trace").code(),
                    expected_error(case)
                );
            }
        }
    }
}
