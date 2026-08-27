use std::collections::{HashMap, HashSet};
use std::ffi::OsString;
use std::fs;
use std::io::{BufRead, BufReader, Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::mpsc::{self, Receiver, SyncSender, TrySendError};
use std::sync::{Arc, Condvar, Mutex, MutexGuard};
use std::thread;
use std::time::{Duration, Instant};

use serde::Serialize;
use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, Manager, State};

use crate::protocol::{
    parse_protocol_line_from_origin, parse_protocol_value, validate_result_data, ProtocolMessage,
    ProtocolOrigin, RequestEnvelope, MAX_PROTOCOL_LINE_BYTES, PROTOCOL_VERSION,
};

pub const BACKEND_EVENT_NAME: &str = "research-agent://backend-event";
const MAX_PENDING_REQUESTS: usize = 64;
const WRITER_QUEUE_CAPACITY: usize = MAX_PENDING_REQUESTS + 2;
const STARTUP_TIMEOUT: Duration = Duration::from_secs(15);
const REQUEST_TIMEOUT: Duration = Duration::from_secs(600);
const SHUTDOWN_RESPONSE_TIMEOUT: Duration = Duration::from_secs(5);
const SHUTDOWN_EXIT_TIMEOUT: Duration = Duration::from_secs(5);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum BackendLifecycle {
    Stopped,
    Starting,
    Ready,
    Degraded,
    Crashed,
    Restarting,
    ShuttingDown,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BridgeError {
    pub code: String,
    pub message: String,
    pub retryable: bool,
}

impl BridgeError {
    fn new(code: &str, message: &str, retryable: bool) -> Self {
        Self {
            code: code.to_owned(),
            message: message.to_owned(),
            retryable,
        }
    }

    fn protocol() -> Self {
        Self::new(
            "PROTOCOL_INVALID",
            "The desktop backend produced an invalid protocol message.",
            false,
        )
    }

    fn stopped() -> Self {
        Self::new(
            "BACKEND_NOT_READY",
            "The desktop backend is not ready.",
            true,
        )
    }
}

impl std::fmt::Display for BridgeError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str(&self.message)
    }
}

impl std::error::Error for BridgeError {}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ShutdownKind {
    Graceful,
    Forced,
    NotRunning,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ShutdownReport {
    pub kind: ShutdownKind,
    pub flushed: Option<bool>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BackendSnapshot {
    pub lifecycle: BackendLifecycle,
    pub generation: u64,
    pub child_running: bool,
    pub pending_requests: usize,
    pub stderr_lines: u64,
    pub stderr_bytes: u64,
    pub last_error: Option<BridgeError>,
    pub last_shutdown: Option<ShutdownReport>,
}

impl Default for BackendSnapshot {
    fn default() -> Self {
        Self {
            lifecycle: BackendLifecycle::Stopped,
            generation: 0,
            child_running: false,
            pending_requests: 0,
            stderr_lines: 0,
            stderr_bytes: 0,
            last_error: None,
            last_shutdown: None,
        }
    }
}

#[derive(Debug, Clone, Serialize)]
#[serde(tag = "type", rename_all = "camelCase")]
pub enum BackendEvent {
    Protocol {
        origin: ProtocolEventOrigin,
        message: Value,
    },
    Lifecycle {
        snapshot: BackendSnapshot,
    },
}

#[derive(Debug, Clone, Copy, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum ProtocolEventOrigin {
    Python,
    Rust,
}

type EventSink = Arc<dyn Fn(BackendEvent) + Send + Sync>;
type PendingResult = Result<Value, BridgeError>;

struct PendingRequest {
    method: String,
    next_sequence: u64,
    sender: SyncSender<PendingResult>,
}

struct ChildControl {
    generation: u64,
    child: Mutex<Child>,
    writer: SyncSender<Vec<u8>>,
}

struct SupervisorState {
    snapshot: BackendSnapshot,
    child: Option<Arc<ChildControl>>,
    pending: HashMap<String, PendingRequest>,
    seen_request_ids: HashSet<String>,
    internal_request_counter: u64,
}

impl Default for SupervisorState {
    fn default() -> Self {
        Self {
            snapshot: BackendSnapshot::default(),
            child: None,
            pending: HashMap::new(),
            seen_request_ids: HashSet::new(),
            internal_request_counter: 0,
        }
    }
}

struct SupervisorCore {
    state: Mutex<SupervisorState>,
    operation: Mutex<()>,
    changed: Condvar,
    event_sink: EventSink,
}

#[derive(Clone)]
struct LaunchConfig {
    program: PathBuf,
    arguments: Vec<OsString>,
    current_dir: PathBuf,
    python_path: Option<PathBuf>,
    conda_prefix: Option<PathBuf>,
}

#[derive(Clone, Copy)]
struct SupervisorTimeouts {
    startup: Duration,
    request: Duration,
    shutdown_response: Duration,
    shutdown_exit: Duration,
}

impl Default for SupervisorTimeouts {
    fn default() -> Self {
        Self {
            startup: STARTUP_TIMEOUT,
            request: REQUEST_TIMEOUT,
            shutdown_response: SHUTDOWN_RESPONSE_TIMEOUT,
            shutdown_exit: SHUTDOWN_EXIT_TIMEOUT,
        }
    }
}

#[derive(Clone)]
struct BackendSupervisor {
    core: Arc<SupervisorCore>,
    launch_override: Option<LaunchConfig>,
    timeouts: SupervisorTimeouts,
}

impl BackendSupervisor {
    fn new(event_sink: EventSink) -> Self {
        Self {
            core: Arc::new(SupervisorCore {
                state: Mutex::new(SupervisorState::default()),
                operation: Mutex::new(()),
                changed: Condvar::new(),
                event_sink,
            }),
            launch_override: None,
            timeouts: SupervisorTimeouts::default(),
        }
    }

    #[cfg(test)]
    fn for_test(launch: LaunchConfig, event_sink: EventSink, timeouts: SupervisorTimeouts) -> Self {
        Self {
            core: Arc::new(SupervisorCore {
                state: Mutex::new(SupervisorState::default()),
                operation: Mutex::new(()),
                changed: Condvar::new(),
                event_sink,
            }),
            launch_override: Some(launch),
            timeouts,
        }
    }

    fn snapshot(&self) -> BackendSnapshot {
        lock_state(&self.core).snapshot.clone()
    }

    fn start(&self) -> BackendSnapshot {
        let _operation = self
            .core
            .operation
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        self.start_with_lifecycle(BackendLifecycle::Starting)
    }

    fn start_with_lifecycle(&self, starting_lifecycle: BackendLifecycle) -> BackendSnapshot {
        {
            let state = lock_state(&self.core);
            if state.snapshot.child_running {
                return state.snapshot.clone();
            }
        }

        let launch = match self
            .launch_override
            .clone()
            .map(Ok)
            .unwrap_or_else(source_conda_launch)
        {
            Ok(launch) => launch,
            Err(error) => {
                let snapshot = {
                    let mut state = lock_state(&self.core);
                    state.snapshot.lifecycle = BackendLifecycle::Degraded;
                    state.snapshot.child_running = false;
                    state.snapshot.last_error = Some(error);
                    state.snapshot.clone()
                };
                emit_lifecycle(&self.core, snapshot.clone());
                return snapshot;
            }
        };

        let generation = {
            let mut state = lock_state(&self.core);
            state.snapshot.generation = state.snapshot.generation.saturating_add(1);
            state.snapshot.lifecycle = starting_lifecycle;
            state.snapshot.child_running = false;
            state.snapshot.pending_requests = 0;
            state.snapshot.stderr_lines = 0;
            state.snapshot.stderr_bytes = 0;
            state.snapshot.last_error = None;
            state.snapshot.last_shutdown = None;
            state.pending.clear();
            state.seen_request_ids.clear();
            state.snapshot.generation
        };
        emit_lifecycle(&self.core, self.snapshot());

        if let Err(error) = spawn_child(self.core.clone(), launch, generation) {
            let snapshot = {
                let mut state = lock_state(&self.core);
                state.snapshot.lifecycle = BackendLifecycle::Crashed;
                state.snapshot.child_running = false;
                state.snapshot.last_error = Some(error.clone());
                state.snapshot.clone()
            };
            emit_rust_protocol_error(&self.core, "backend.crashed", &error);
            emit_lifecycle(&self.core, snapshot.clone());
            return snapshot;
        }

        let deadline = Instant::now() + self.timeouts.startup;
        let mut state = lock_state(&self.core);
        while state.snapshot.generation == generation
            && state.snapshot.child_running
            && matches!(
                state.snapshot.lifecycle,
                BackendLifecycle::Starting | BackendLifecycle::Restarting
            )
        {
            let now = Instant::now();
            if now >= deadline {
                break;
            }
            let wait = deadline.saturating_duration_since(now);
            let result = self.core.changed.wait_timeout(state, wait);
            state = match result {
                Ok((guard, _)) => guard,
                Err(poisoned) => poisoned.into_inner().0,
            };
        }
        if state.snapshot.generation == generation
            && matches!(
                state.snapshot.lifecycle,
                BackendLifecycle::Starting | BackendLifecycle::Restarting
            )
        {
            let error = BridgeError::new(
                "BACKEND_START_TIMEOUT",
                "The desktop backend did not become ready in time.",
                true,
            );
            state.snapshot.lifecycle = BackendLifecycle::Degraded;
            state.snapshot.last_error = Some(error.clone());
            let child = state.child.clone();
            let snapshot = state.snapshot.clone();
            drop(state);
            fail_all_pending(&self.core, error.clone());
            emit_rust_protocol_error(&self.core, "backend.protocol_error", &error);
            emit_lifecycle(&self.core, snapshot.clone());
            if let Some(child) = child {
                kill_child(&child);
            }
            self.wait_until_stopped(self.timeouts.shutdown_exit);
            return self.snapshot();
        }
        let failed_child = if state.snapshot.generation == generation
            && state.snapshot.lifecycle == BackendLifecycle::Degraded
            && state.snapshot.child_running
        {
            state.child.clone()
        } else {
            None
        };
        let snapshot = state.snapshot.clone();
        drop(state);
        if let Some(child) = failed_child {
            kill_child(&child);
            self.wait_until_stopped(self.timeouts.shutdown_exit);
            self.snapshot()
        } else {
            snapshot
        }
    }

    fn request(&self, request: Value) -> PendingResult {
        self.submit_request(request, false, self.timeouts.request)
    }

    fn submit_request(
        &self,
        request: Value,
        allow_shutting_down: bool,
        timeout: Duration,
    ) -> PendingResult {
        let parsed = parse_protocol_value(request.clone()).map_err(bridge_protocol_violation)?;
        let ProtocolMessage::Request(RequestEnvelope {
            request_id, method, ..
        }) = parsed
        else {
            return Err(BridgeError::new(
                "PROTOCOL_INVALID",
                "Only protocol request envelopes can be sent to the backend.",
                false,
            ));
        };
        let mut line = serde_json::to_vec(&request).map_err(|_| BridgeError::protocol())?;
        if line.len() > MAX_PROTOCOL_LINE_BYTES {
            return Err(BridgeError::protocol());
        }
        line.push(b'\n');

        let (sender, receiver) = mpsc::sync_channel(1);
        let child = {
            let mut state = lock_state(&self.core);
            let allowed_lifecycle = state.snapshot.lifecycle == BackendLifecycle::Ready
                || (allow_shutting_down
                    && state.snapshot.lifecycle == BackendLifecycle::ShuttingDown);
            if !allowed_lifecycle || !state.snapshot.child_running {
                return Err(BridgeError::stopped());
            }
            if state.seen_request_ids.contains(&request_id) {
                return Err(BridgeError::new(
                    "DUPLICATE_REQUEST_ID",
                    "The requestId has already been used for this backend generation.",
                    false,
                ));
            }
            if state.pending.len() >= MAX_PENDING_REQUESTS {
                return Err(BridgeError::new(
                    "BACKEND_BUSY",
                    "The desktop backend request limit has been reached.",
                    true,
                ));
            }
            let Some(child) = state.child.clone() else {
                return Err(BridgeError::stopped());
            };
            state.seen_request_ids.insert(request_id.clone());
            state.pending.insert(
                request_id.clone(),
                PendingRequest {
                    method,
                    next_sequence: 1,
                    sender,
                },
            );
            state.snapshot.pending_requests = state.pending.len();
            child
        };

        match child.writer.try_send(line) {
            Ok(()) => {}
            Err(TrySendError::Full(_)) => {
                self.remove_pending(&request_id);
                return Err(BridgeError::new(
                    "BACKEND_BUSY",
                    "The desktop backend writer queue is full.",
                    true,
                ));
            }
            Err(TrySendError::Disconnected(_)) => {
                self.remove_pending(&request_id);
                let error = BridgeError::new(
                    "BACKEND_WRITE_FAILED",
                    "The desktop backend request pipe is unavailable.",
                    true,
                );
                fatal_generation(&self.core, child.generation, error.clone(), true);
                return Err(error);
            }
        }

        match receiver.recv_timeout(timeout) {
            Ok(result) => result,
            Err(_) => {
                let removed = self.remove_pending(&request_id);
                let error = BridgeError::new(
                    "BACKEND_REQUEST_TIMEOUT",
                    "The desktop backend request did not finish in time.",
                    true,
                );
                if removed {
                    fatal_generation(&self.core, child.generation, error.clone(), true);
                }
                Err(error)
            }
        }
    }

    fn remove_pending(&self, request_id: &str) -> bool {
        let mut state = lock_state(&self.core);
        let removed = state.pending.remove(request_id).is_some();
        state.snapshot.pending_requests = state.pending.len();
        removed
    }

    fn shutdown(&self) -> ShutdownReport {
        let _operation = self
            .core
            .operation
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        self.shutdown_inner()
    }

    fn shutdown_inner(&self) -> ShutdownReport {
        {
            let mut state = lock_state(&self.core);
            if state.snapshot.lifecycle == BackendLifecycle::ShuttingDown {
                let deadline =
                    Instant::now() + self.timeouts.shutdown_response + self.timeouts.shutdown_exit;
                while state.snapshot.lifecycle == BackendLifecycle::ShuttingDown
                    && Instant::now() < deadline
                {
                    let wait = deadline.saturating_duration_since(Instant::now());
                    let result = self.core.changed.wait_timeout(state, wait);
                    state = match result {
                        Ok((guard, _)) => guard,
                        Err(poisoned) => poisoned.into_inner().0,
                    };
                }
                return state
                    .snapshot
                    .last_shutdown
                    .clone()
                    .unwrap_or(ShutdownReport {
                        kind: ShutdownKind::NotRunning,
                        flushed: None,
                    });
            }
            if !state.snapshot.child_running || state.child.is_none() {
                if let Some(report) = state.snapshot.last_shutdown.clone() {
                    return report;
                }
                let report = ShutdownReport {
                    kind: ShutdownKind::NotRunning,
                    flushed: None,
                };
                state.snapshot.lifecycle = BackendLifecycle::Stopped;
                state.snapshot.child_running = false;
                state.snapshot.last_shutdown = Some(report.clone());
                let snapshot = state.snapshot.clone();
                drop(state);
                emit_lifecycle(&self.core, snapshot);
                return report;
            }
            state.snapshot.lifecycle = BackendLifecycle::ShuttingDown;
            state.snapshot.last_error = None;
        }
        emit_lifecycle(&self.core, self.snapshot());

        let request_id = self.next_internal_request_id();
        let request = json!({
            "protocolVersion": PROTOCOL_VERSION,
            "messageType": "request",
            "requestId": request_id,
            "method": "runtime.shutdown",
            "params": {}
        });
        let graceful_result = self.submit_request(request, true, self.timeouts.shutdown_response);
        let flushed = graceful_result
            .as_ref()
            .ok()
            .filter(|value| value.get("ok").and_then(Value::as_bool) == Some(true))
            .and_then(|value| value.get("data"))
            .and_then(|data| data.get("flushed"))
            .and_then(Value::as_bool);
        let mut stopped = flushed.is_some() && self.wait_until_stopped(self.timeouts.shutdown_exit);
        let graceful = flushed.is_some() && stopped;
        if !graceful {
            let child = lock_state(&self.core).child.clone();
            if let Some(child) = child {
                kill_child(&child);
            }
            stopped = self.wait_until_stopped(self.timeouts.shutdown_exit);
        }

        let report = ShutdownReport {
            kind: if graceful {
                ShutdownKind::Graceful
            } else {
                ShutdownKind::Forced
            },
            flushed: if graceful { flushed } else { None },
        };
        let snapshot = {
            let mut state = lock_state(&self.core);
            if stopped {
                state.snapshot.lifecycle = BackendLifecycle::Stopped;
                state.snapshot.child_running = false;
                state.child = None;
            } else {
                state.snapshot.lifecycle = BackendLifecycle::Degraded;
                state.snapshot.last_error = Some(BridgeError::new(
                    "BACKEND_TERMINATION_FAILED",
                    "The desktop backend did not stop after forced termination.",
                    true,
                ));
            }
            state.snapshot.last_shutdown = Some(report.clone());
            state.snapshot.clone()
        };
        self.core.changed.notify_all();
        emit_lifecycle(&self.core, snapshot);
        report
    }

    fn restart(&self) -> BackendSnapshot {
        let _operation = self
            .core
            .operation
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        self.shutdown_inner();
        self.start_replacement_if_stopped()
    }

    fn start_replacement_if_stopped(&self) -> BackendSnapshot {
        let current = self.snapshot();
        if current.child_running {
            return current;
        }
        {
            let mut state = lock_state(&self.core);
            state.snapshot.lifecycle = BackendLifecycle::Restarting;
        }
        emit_lifecycle(&self.core, self.snapshot());
        self.start_with_lifecycle(BackendLifecycle::Restarting)
    }

    fn next_internal_request_id(&self) -> String {
        let mut state = lock_state(&self.core);
        state.internal_request_counter = state.internal_request_counter.saturating_add(1);
        let suffix = state.internal_request_counter & 0x0000_ffff_ffff_ffff;
        format!("00000000-0000-4000-8000-{suffix:012x}")
    }

    fn wait_until_stopped(&self, timeout: Duration) -> bool {
        let deadline = Instant::now() + timeout;
        let mut state = lock_state(&self.core);
        while state.snapshot.child_running && Instant::now() < deadline {
            let wait = deadline.saturating_duration_since(Instant::now());
            let result = self.core.changed.wait_timeout(state, wait);
            state = match result {
                Ok((guard, _)) => guard,
                Err(poisoned) => poisoned.into_inner().0,
            };
        }
        !state.snapshot.child_running
    }
}

pub struct BackendManager {
    supervisor: BackendSupervisor,
}

impl BackendManager {
    pub fn new(app_handle: AppHandle) -> Self {
        let event_sink: EventSink = Arc::new(move |event| {
            let _ = app_handle.emit(BACKEND_EVENT_NAME, event);
        });
        Self {
            supervisor: BackendSupervisor::new(event_sink),
        }
    }

    pub fn shutdown_best_effort(&self) {
        self.supervisor.shutdown();
    }
}

#[tauri::command]
pub async fn backend_start(app_handle: AppHandle) -> BackendSnapshot {
    let supervisor = app_handle.state::<BackendManager>().supervisor.clone();
    tauri::async_runtime::spawn_blocking(move || supervisor.start())
        .await
        .unwrap_or_else(|_| BackendSnapshot {
            lifecycle: BackendLifecycle::Crashed,
            last_error: Some(BridgeError::new(
                "SUPERVISOR_FAILED",
                "The desktop backend supervisor stopped unexpectedly.",
                true,
            )),
            ..BackendSnapshot::default()
        })
}

#[tauri::command]
pub fn backend_snapshot(state: State<'_, BackendManager>) -> BackendSnapshot {
    state.supervisor.snapshot()
}

#[tauri::command]
pub async fn backend_request(request: Value, app_handle: AppHandle) -> Result<Value, BridgeError> {
    let supervisor = app_handle.state::<BackendManager>().supervisor.clone();
    tauri::async_runtime::spawn_blocking(move || supervisor.request(request))
        .await
        .unwrap_or_else(|_| {
            Err(BridgeError::new(
                "SUPERVISOR_FAILED",
                "The desktop backend supervisor stopped unexpectedly.",
                true,
            ))
        })
}

#[tauri::command]
pub async fn backend_shutdown(app_handle: AppHandle) -> ShutdownReport {
    let supervisor = app_handle.state::<BackendManager>().supervisor.clone();
    tauri::async_runtime::spawn_blocking(move || supervisor.shutdown())
        .await
        .unwrap_or(ShutdownReport {
            kind: ShutdownKind::Forced,
            flushed: None,
        })
}

#[tauri::command]
pub async fn backend_restart(app_handle: AppHandle) -> BackendSnapshot {
    let supervisor = app_handle.state::<BackendManager>().supervisor.clone();
    tauri::async_runtime::spawn_blocking(move || supervisor.restart())
        .await
        .unwrap_or_else(|_| BackendSnapshot {
            lifecycle: BackendLifecycle::Crashed,
            last_error: Some(BridgeError::new(
                "SUPERVISOR_FAILED",
                "The desktop backend supervisor stopped unexpectedly.",
                true,
            )),
            ..BackendSnapshot::default()
        })
}

fn lock_state(core: &SupervisorCore) -> MutexGuard<'_, SupervisorState> {
    core.state
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

fn emit_lifecycle(core: &SupervisorCore, snapshot: BackendSnapshot) {
    (core.event_sink)(BackendEvent::Lifecycle { snapshot });
}

fn emit_protocol(core: &SupervisorCore, origin: ProtocolEventOrigin, message: Value) {
    (core.event_sink)(BackendEvent::Protocol { origin, message });
}

fn emit_rust_protocol_error(core: &SupervisorCore, event: &str, error: &BridgeError) {
    emit_protocol(
        core,
        ProtocolEventOrigin::Rust,
        json!({
            "protocolVersion": PROTOCOL_VERSION,
            "messageType": "event",
            "event": event,
            "data": {
                "code": error.code,
                "message": error.message,
                "retryable": error.retryable
            }
        }),
    );
}

fn bridge_protocol_violation(violation: crate::protocol::ProtocolViolation) -> BridgeError {
    if violation.code() == "PROTOCOL_VERSION_UNSUPPORTED" {
        BridgeError::new(
            "PROTOCOL_VERSION_UNSUPPORTED",
            "The desktop backend uses an unsupported protocol version.",
            false,
        )
    } else {
        BridgeError::protocol()
    }
}

fn source_conda_launch() -> Result<LaunchConfig, BridgeError> {
    let prefix = std::env::var_os("CONDA_PREFIX").ok_or_else(|| {
        BridgeError::new(
            "RUNTIME_WRONG_CONDA_ENV",
            "Start the desktop app from the Conda app environment.",
            false,
        )
    })?;
    let default_env = std::env::var_os("CONDA_DEFAULT_ENV");
    validate_conda_identity(Path::new(&prefix), default_env.as_deref())?;

    let manifest_dir = fs::canonicalize(Path::new(env!("CARGO_MANIFEST_DIR"))).map_err(|_| {
        BridgeError::new(
            "SOURCE_CHECKOUT_INVALID",
            "The desktop source checkout could not be resolved.",
            false,
        )
    })?;
    let app_root = manifest_dir
        .parent()
        .and_then(Path::parent)
        .map(Path::to_path_buf)
        .filter(|path| path.join("pyproject.toml").is_file() && path.join("agent").is_dir())
        .ok_or_else(|| {
            BridgeError::new(
                "SOURCE_CHECKOUT_INVALID",
                "The desktop source checkout is missing its app root.",
                false,
            )
        })?;
    let repo_root = app_root.parent().map(Path::to_path_buf).ok_or_else(|| {
        BridgeError::new(
            "SOURCE_CHECKOUT_INVALID",
            "The repository root could not be resolved.",
            false,
        )
    })?;
    Ok(LaunchConfig {
        program: PathBuf::from(&prefix).join("bin/python"),
        arguments: vec![OsString::from("-m"), OsString::from("agent.desktop.server")],
        current_dir: repo_root,
        python_path: Some(app_root),
        conda_prefix: Some(PathBuf::from(prefix)),
    })
}

fn validate_conda_identity(
    prefix: &Path,
    default_env: Option<&std::ffi::OsStr>,
) -> Result<(), BridgeError> {
    let valid_name = default_env == Some(std::ffi::OsStr::new("app"))
        && prefix.file_name() == Some(std::ffi::OsStr::new("app"));
    let interpreter = prefix.join("bin/python");
    if !prefix.is_absolute() || !valid_name || !interpreter.is_file() {
        return Err(BridgeError::new(
            "RUNTIME_WRONG_CONDA_ENV",
            "Start the desktop app from the Conda app environment.",
            false,
        ));
    }
    let canonical_prefix = fs::canonicalize(prefix).map_err(|_| {
        BridgeError::new(
            "RUNTIME_WRONG_CONDA_ENV",
            "The Conda app environment could not be validated.",
            false,
        )
    })?;
    let canonical_interpreter = fs::canonicalize(&interpreter).map_err(|_| {
        BridgeError::new(
            "RUNTIME_WRONG_CONDA_ENV",
            "The Conda app Python interpreter could not be validated.",
            false,
        )
    })?;
    if !canonical_interpreter.starts_with(canonical_prefix.join("bin")) {
        return Err(BridgeError::new(
            "RUNTIME_WRONG_CONDA_ENV",
            "The Conda app Python interpreter could not be validated.",
            false,
        ));
    }
    Ok(())
}

fn spawn_child(
    core: Arc<SupervisorCore>,
    launch: LaunchConfig,
    generation: u64,
) -> Result<(), BridgeError> {
    let mut command = Command::new(&launch.program);
    command
        .args(&launch.arguments)
        .current_dir(&launch.current_dir)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    if let Some(python_path) = &launch.python_path {
        command.env("PYTHONPATH", python_path);
    }
    if let Some(conda_prefix) = &launch.conda_prefix {
        command
            .env("CONDA_PREFIX", conda_prefix)
            .env("CONDA_DEFAULT_ENV", "app");
    }
    let mut child = command.spawn().map_err(|_| {
        BridgeError::new(
            "BACKEND_SPAWN_FAILED",
            "The desktop backend process could not be started.",
            true,
        )
    })?;
    let stdin = child.stdin.take().ok_or_else(|| {
        BridgeError::new(
            "BACKEND_SPAWN_FAILED",
            "The desktop backend input pipe could not be opened.",
            true,
        )
    })?;
    let stdout = child.stdout.take().ok_or_else(|| {
        BridgeError::new(
            "BACKEND_SPAWN_FAILED",
            "The desktop backend output pipe could not be opened.",
            true,
        )
    })?;
    let stderr = child.stderr.take().ok_or_else(|| {
        BridgeError::new(
            "BACKEND_SPAWN_FAILED",
            "The desktop backend diagnostic pipe could not be opened.",
            true,
        )
    })?;
    let (writer, receiver) = mpsc::sync_channel(WRITER_QUEUE_CAPACITY);
    let control = Arc::new(ChildControl {
        generation,
        child: Mutex::new(child),
        writer,
    });
    {
        let mut state = lock_state(&core);
        if state.snapshot.generation != generation {
            kill_child(&control);
            return Err(BridgeError::new(
                "BACKEND_START_CANCELLED",
                "The desktop backend start was superseded.",
                true,
            ));
        }
        state.child = Some(control.clone());
        state.snapshot.child_running = true;
    }
    core.changed.notify_all();
    emit_lifecycle(&core, lock_state(&core).snapshot.clone());

    spawn_writer(core.clone(), generation, receiver, stdin);
    spawn_stdout_reader(core.clone(), generation, stdout);
    spawn_stderr_reader(core.clone(), generation, stderr);
    spawn_exit_monitor(core, control);
    Ok(())
}

fn spawn_writer(
    core: Arc<SupervisorCore>,
    generation: u64,
    receiver: Receiver<Vec<u8>>,
    mut stdin: impl Write + Send + 'static,
) {
    thread::spawn(move || {
        while let Ok(line) = receiver.recv() {
            if stdin.write_all(&line).and_then(|_| stdin.flush()).is_err() {
                fatal_generation(
                    &core,
                    generation,
                    BridgeError::new(
                        "BACKEND_WRITE_FAILED",
                        "The desktop backend request pipe failed.",
                        true,
                    ),
                    true,
                );
                return;
            }
        }
    });
}

fn spawn_stdout_reader(
    core: Arc<SupervisorCore>,
    generation: u64,
    stdout: impl Read + Send + 'static,
) {
    thread::spawn(move || {
        let mut reader = BufReader::new(stdout);
        loop {
            match read_bounded_line(&mut reader) {
                Ok(Some(bytes)) => {
                    let Ok(line) = std::str::from_utf8(&bytes) else {
                        fatal_generation(&core, generation, BridgeError::protocol(), true);
                        return;
                    };
                    if let Err(error) = handle_python_line(&core, generation, line) {
                        fatal_generation(&core, generation, error, true);
                        return;
                    }
                }
                Ok(None) => {
                    stdout_closed(&core, generation);
                    return;
                }
                Err(ReadLineError::Oversized) | Err(ReadLineError::Io) => {
                    fatal_generation(&core, generation, BridgeError::protocol(), true);
                    return;
                }
            }
        }
    });
}

fn spawn_stderr_reader(
    core: Arc<SupervisorCore>,
    generation: u64,
    mut stderr: impl Read + Send + 'static,
) {
    thread::spawn(move || {
        let mut buffer = [0_u8; 8192];
        let mut trailing = false;
        loop {
            match stderr.read(&mut buffer) {
                Ok(0) => {
                    if trailing {
                        let mut state = lock_state(&core);
                        if state.snapshot.generation == generation {
                            state.snapshot.stderr_lines =
                                state.snapshot.stderr_lines.saturating_add(1);
                        }
                    }
                    return;
                }
                Ok(count) => {
                    let newline_count = buffer[..count]
                        .iter()
                        .filter(|byte| **byte == b'\n')
                        .count() as u64;
                    trailing = buffer[count - 1] != b'\n';
                    let mut state = lock_state(&core);
                    if state.snapshot.generation != generation {
                        return;
                    }
                    state.snapshot.stderr_bytes =
                        state.snapshot.stderr_bytes.saturating_add(count as u64);
                    state.snapshot.stderr_lines =
                        state.snapshot.stderr_lines.saturating_add(newline_count);
                }
                Err(_) => return,
            }
        }
    });
}

fn spawn_exit_monitor(core: Arc<SupervisorCore>, control: Arc<ChildControl>) {
    thread::spawn(move || loop {
        let exited = {
            let mut child = control
                .child
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner());
            match child.try_wait() {
                Ok(Some(_)) => true,
                Ok(None) => false,
                Err(_) => true,
            }
        };
        if exited {
            child_exited(&core, control.generation);
            return;
        }
        thread::sleep(Duration::from_millis(20));
    });
}

enum ReadLineError {
    Oversized,
    Io,
}

fn read_bounded_line<R: BufRead>(reader: &mut R) -> Result<Option<Vec<u8>>, ReadLineError> {
    let mut line = Vec::new();
    loop {
        let available = reader.fill_buf().map_err(|_| ReadLineError::Io)?;
        if available.is_empty() {
            return if line.is_empty() {
                Ok(None)
            } else {
                Ok(Some(line))
            };
        }
        let newline = available.iter().position(|byte| *byte == b'\n');
        let take = newline.map_or(available.len(), |index| index + 1);
        if line.len().saturating_add(take) > MAX_PROTOCOL_LINE_BYTES + 1 {
            return Err(ReadLineError::Oversized);
        }
        line.extend_from_slice(&available[..take]);
        reader.consume(take);
        if newline.is_some() {
            line.pop();
            if line.last() == Some(&b'\r') {
                line.pop();
            }
            return Ok(Some(line));
        }
    }
}

fn handle_python_line(
    core: &SupervisorCore,
    generation: u64,
    line: &str,
) -> Result<(), BridgeError> {
    let parsed = parse_protocol_line_from_origin(line, ProtocolOrigin::Python)
        .map_err(bridge_protocol_violation)?;
    let value: Value = serde_json::from_str(line).map_err(|_| BridgeError::protocol())?;
    match parsed {
        ProtocolMessage::Request(_) => return Err(BridgeError::protocol()),
        ProtocolMessage::Event(event) => {
            if let Some(request_id) = event.request_id.as_deref() {
                let mut state = lock_state(core);
                if state.snapshot.generation != generation {
                    return Ok(());
                }
                let pending = state
                    .pending
                    .get_mut(request_id)
                    .ok_or_else(BridgeError::protocol)?;
                let sequence = event.sequence.ok_or_else(BridgeError::protocol)?;
                if sequence != pending.next_sequence {
                    return Err(BridgeError::protocol());
                }
                pending.next_sequence = pending.next_sequence.saturating_add(1);
            } else if event.event == "backend.ready" {
                let valid_ready = event.data.as_object().is_some_and(|data| {
                    data.len() == 1 && data.get("status") == Some(&json!("ready"))
                });
                if !valid_ready {
                    return Err(BridgeError::protocol());
                }
                let snapshot = {
                    let mut state = lock_state(core);
                    if state.snapshot.generation != generation {
                        return Ok(());
                    }
                    if !matches!(
                        state.snapshot.lifecycle,
                        BackendLifecycle::Starting | BackendLifecycle::Restarting
                    ) {
                        return Err(BridgeError::protocol());
                    }
                    state.snapshot.lifecycle = BackendLifecycle::Ready;
                    state.snapshot.last_error = None;
                    state.snapshot.clone()
                };
                core.changed.notify_all();
                emit_lifecycle(core, snapshot);
            } else if event.event == "backend.protocol_error" {
                let code = event
                    .data
                    .get("code")
                    .and_then(Value::as_str)
                    .unwrap_or("PROTOCOL_INVALID");
                let error = if code == "RUNTIME_WRONG_CONDA_ENV" {
                    BridgeError::new(
                        "RUNTIME_WRONG_CONDA_ENV",
                        "The backend is not running in the required Conda app environment.",
                        false,
                    )
                } else {
                    BridgeError::protocol()
                };
                let starting = {
                    let mut state = lock_state(core);
                    if state.snapshot.generation != generation {
                        return Ok(());
                    }
                    state.snapshot.last_error = Some(error.clone());
                    let starting = matches!(
                        state.snapshot.lifecycle,
                        BackendLifecycle::Starting | BackendLifecycle::Restarting
                    );
                    state.snapshot.lifecycle = BackendLifecycle::Degraded;
                    starting
                };
                core.changed.notify_all();
                emit_lifecycle(core, lock_state(core).snapshot.clone());
                if starting {
                    emit_protocol(core, ProtocolEventOrigin::Python, value);
                    return Err(error);
                }
            } else if event.event == "backend.shutting_down" {
                let snapshot = {
                    let mut state = lock_state(core);
                    if state.snapshot.generation != generation {
                        return Ok(());
                    }
                    state.snapshot.lifecycle = BackendLifecycle::ShuttingDown;
                    state.snapshot.clone()
                };
                emit_lifecycle(core, snapshot);
            }
        }
        ProtocolMessage::Result(result) => {
            let sender = {
                let mut state = lock_state(core);
                if state.snapshot.generation != generation {
                    return Ok(());
                }
                let pending = state
                    .pending
                    .get(&result.request_id)
                    .ok_or_else(BridgeError::protocol)?;
                if result.ok {
                    validate_result_data(
                        &pending.method,
                        result.data.as_ref().ok_or_else(BridgeError::protocol)?,
                    )
                    .map_err(|_| BridgeError::protocol())?;
                }
                let pending = state
                    .pending
                    .remove(&result.request_id)
                    .ok_or_else(BridgeError::protocol)?;
                state.snapshot.pending_requests = state.pending.len();
                pending.sender
            };
            emit_protocol(core, ProtocolEventOrigin::Python, value.clone());
            let _ = sender.send(Ok(value));
            return Ok(());
        }
    }
    emit_protocol(core, ProtocolEventOrigin::Python, value);
    Ok(())
}

fn stdout_closed(core: &SupervisorCore, generation: u64) {
    let child = {
        let state = lock_state(core);
        if state.snapshot.generation != generation
            || !state.snapshot.child_running
            || state.snapshot.lifecycle == BackendLifecycle::ShuttingDown
        {
            return;
        }
        state.child.clone()
    };
    let Some(child) = child else {
        return;
    };
    let exited = {
        let mut process = child
            .child
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        matches!(process.try_wait(), Ok(Some(_)))
    };
    if exited {
        child_exited(core, generation);
    } else {
        fatal_generation(
            core,
            generation,
            BridgeError::new(
                "BACKEND_OUTPUT_CLOSED",
                "The desktop backend protocol output closed unexpectedly.",
                true,
            ),
            true,
        );
    }
}

fn fatal_generation(core: &SupervisorCore, generation: u64, error: BridgeError, kill: bool) {
    let (child, snapshot, pending) = {
        let mut state = lock_state(core);
        if state.snapshot.generation != generation || !state.snapshot.child_running {
            return;
        }
        state.snapshot.lifecycle = BackendLifecycle::Degraded;
        state.snapshot.last_error = Some(error.clone());
        let child = state.child.clone();
        let pending = state
            .pending
            .drain()
            .map(|(_, item)| item.sender)
            .collect::<Vec<_>>();
        state.snapshot.pending_requests = 0;
        (child, state.snapshot.clone(), pending)
    };
    for sender in pending {
        let _ = sender.send(Err(error.clone()));
    }
    emit_rust_protocol_error(core, "backend.protocol_error", &error);
    emit_lifecycle(core, snapshot);
    core.changed.notify_all();
    if kill {
        if let Some(child) = child {
            kill_child(&child);
        }
    }
}

fn fail_all_pending(core: &SupervisorCore, error: BridgeError) {
    let pending = {
        let mut state = lock_state(core);
        let pending = state
            .pending
            .drain()
            .map(|(_, item)| item.sender)
            .collect::<Vec<_>>();
        state.snapshot.pending_requests = 0;
        pending
    };
    for sender in pending {
        let _ = sender.send(Err(error.clone()));
    }
}

fn child_exited(core: &SupervisorCore, generation: u64) {
    let (snapshot, pending, unexpected) = {
        let mut state = lock_state(core);
        if state.snapshot.generation != generation || !state.snapshot.child_running {
            return;
        }
        let unexpected = !matches!(
            state.snapshot.lifecycle,
            BackendLifecycle::ShuttingDown | BackendLifecycle::Degraded
        );
        state.snapshot.child_running = false;
        state.child = None;
        if unexpected {
            state.snapshot.lifecycle = BackendLifecycle::Crashed;
            state.snapshot.last_error = Some(BridgeError::new(
                "BACKEND_CRASHED",
                "The desktop backend process exited unexpectedly.",
                true,
            ));
        }
        let pending = state
            .pending
            .drain()
            .map(|(_, item)| item.sender)
            .collect::<Vec<_>>();
        state.snapshot.pending_requests = 0;
        (state.snapshot.clone(), pending, unexpected)
    };
    let error = snapshot
        .last_error
        .clone()
        .unwrap_or_else(BridgeError::stopped);
    for sender in pending {
        let _ = sender.send(Err(error.clone()));
    }
    if unexpected {
        emit_rust_protocol_error(core, "backend.crashed", &error);
    }
    emit_lifecycle(core, snapshot);
    core.changed.notify_all();
}

fn kill_child(child: &ChildControl) {
    let mut process = child
        .child
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner());
    let _ = process.kill();
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};

    static TEMP_COUNTER: AtomicU64 = AtomicU64::new(0);
    const REQUEST_ID: &str = "123e4567-e89b-42d3-a456-426614174000";
    const REQUEST_ID_2: &str = "123e4567-e89b-42d3-a456-426614174001";

    struct TempScript {
        directory: PathBuf,
        script: PathBuf,
    }

    impl TempScript {
        fn new(body: &str) -> Self {
            let serial = TEMP_COUNTER.fetch_add(1, Ordering::Relaxed);
            let directory = std::env::temp_dir().join(format!(
                "research-agent-supervisor-{}-{serial}",
                std::process::id()
            ));
            fs::create_dir(&directory).expect("create test directory");
            let script = directory.join("fake_backend.py");
            fs::write(&script, body).expect("write fake backend");
            Self { directory, script }
        }
    }

    impl Drop for TempScript {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.directory);
        }
    }

    fn timeouts() -> SupervisorTimeouts {
        SupervisorTimeouts {
            startup: Duration::from_millis(500),
            request: Duration::from_millis(500),
            shutdown_response: Duration::from_millis(250),
            shutdown_exit: Duration::from_millis(500),
        }
    }

    fn fake_script(mode: &str) -> TempScript {
        TempScript::new(&format!(
            r#"import json, os, sys, time
MODE = {mode:?}
def send(value):
    print(json.dumps(value, separators=(',', ':')), flush=True)
if MODE == 'timeout':
    time.sleep(5)
    raise SystemExit(0)
if MODE == 'wrong_env':
    send({{'protocolVersion':1,'messageType':'event','event':'backend.protocol_error','data':{{'code':'RUNTIME_WRONG_CONDA_ENV','message':'wrong environment'}}}})
    time.sleep(5)
    raise SystemExit(2)
if MODE == 'wrong_version':
    send({{'protocolVersion':99,'messageType':'event','event':'backend.ready','data':{{'status':'ready'}}}})
    time.sleep(5)
    raise SystemExit(2)
if MODE == 'stderr':
    sys.stderr.write('first diagnostic\nsecond diagnostic\ntrailing')
    sys.stderr.flush()
send({{'protocolVersion':1,'messageType':'event','event':'backend.ready','data':{{'status':'ready'}}}})
for raw in sys.stdin:
    request = json.loads(raw)
    request_id = request['requestId']
    method = request['method']
    if MODE == 'crash':
        os._exit(7)
    if MODE == 'malformed':
        print('{{not-json', flush=True)
        time.sleep(5)
        continue
    if MODE == 'oversized':
        print('x' * (2 * 1024 * 1024 + 1), flush=True)
        time.sleep(5)
        continue
    if MODE == 'forced' and method == 'runtime.shutdown':
        time.sleep(5)
        continue
    if MODE == 'slow_graceful' and method == 'runtime.shutdown':
        time.sleep(0.15)
    send({{'protocolVersion':1,'messageType':'event','requestId':request_id,'sequence':1,'event':'request.started','data':{{'stage':method}}}})
    data = {{'status':'stopped','flushed':True}} if method == 'runtime.shutdown' else {{}}
    send({{'protocolVersion':1,'messageType':'result','requestId':request_id,'ok':True,'data':data}})
    if method == 'runtime.shutdown':
        send({{'protocolVersion':1,'messageType':'event','event':'backend.shutting_down','data':{{'status':'shutting_down'}}}})
        raise SystemExit(0)
"#
        ))
    }

    fn supervisor(mode: &str) -> (BackendSupervisor, TempScript, Arc<Mutex<Vec<BackendEvent>>>) {
        let script = fake_script(mode);
        let prefix = PathBuf::from(std::env::var_os("CONDA_PREFIX").expect("CONDA_PREFIX"));
        let events = Arc::new(Mutex::new(Vec::new()));
        let captured = events.clone();
        let sink: EventSink = Arc::new(move |event| {
            captured
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner())
                .push(event);
        });
        let launch = LaunchConfig {
            program: prefix.join("bin/python"),
            arguments: vec![script.script.clone().into_os_string()],
            current_dir: script.directory.clone(),
            python_path: None,
            conda_prefix: None,
        };
        (
            BackendSupervisor::for_test(launch, sink, timeouts()),
            script,
            events,
        )
    }

    fn request(id: &str) -> Value {
        json!({
            "protocolVersion": 1,
            "messageType": "request",
            "requestId": id,
            "method": "knowledge.overview",
            "params": {}
        })
    }

    #[test]
    fn readiness_request_event_result_and_graceful_shutdown() {
        let (supervisor, _script, events) = supervisor("normal");
        assert_eq!(supervisor.start().lifecycle, BackendLifecycle::Ready);
        let result = supervisor
            .request(request(REQUEST_ID))
            .expect("request result");
        assert_eq!(result["ok"], true);
        let captured = events.lock().expect("events");
        assert!(captured.iter().any(|event| matches!(
            event,
            BackendEvent::Protocol { origin: ProtocolEventOrigin::Python, message }
                if message["event"] == "request.started"
        )));
        drop(captured);
        assert_eq!(
            supervisor.shutdown(),
            ShutdownReport {
                kind: ShutdownKind::Graceful,
                flushed: Some(true)
            }
        );
        assert_eq!(supervisor.shutdown().kind, ShutdownKind::Graceful);
    }

    #[test]
    fn concurrent_starts_share_one_generation() {
        let (supervisor, _script, _events) = supervisor("normal");
        let other = supervisor.clone();
        let first = thread::spawn(move || other.start());
        let second_snapshot = supervisor.start();
        let first_snapshot = first.join().expect("first start caller");
        assert_eq!(first_snapshot.lifecycle, BackendLifecycle::Ready);
        assert_eq!(second_snapshot.lifecycle, BackendLifecycle::Ready);
        assert_eq!(first_snapshot.generation, 1);
        assert_eq!(second_snapshot.generation, 1);
        supervisor.shutdown();
    }

    #[test]
    fn readiness_timeout_is_bounded_and_stops_child() {
        let (mut supervisor, _script, _events) = supervisor("timeout");
        supervisor.timeouts.startup = Duration::from_millis(60);
        let snapshot = supervisor.start();
        assert_eq!(snapshot.lifecycle, BackendLifecycle::Degraded);
        assert!(!snapshot.child_running);
        assert_eq!(snapshot, supervisor.snapshot());
        assert_eq!(
            snapshot
                .last_error
                .as_ref()
                .map(|error| error.code.as_str()),
            Some("BACKEND_START_TIMEOUT")
        );
        assert!(supervisor.wait_until_stopped(Duration::from_secs(1)));
    }

    #[test]
    fn restart_gate_preserves_a_failed_shutdown_state() {
        let (supervisor, _script, _events) = supervisor("normal");
        {
            let mut state = lock_state(&supervisor.core);
            state.snapshot.lifecycle = BackendLifecycle::Degraded;
            state.snapshot.generation = 7;
            state.snapshot.child_running = true;
            state.snapshot.last_error = Some(BridgeError::new(
                "BACKEND_TERMINATION_FAILED",
                "The desktop backend did not stop after forced termination.",
                true,
            ));
        }
        let snapshot = supervisor.start_replacement_if_stopped();
        assert_eq!(snapshot.lifecycle, BackendLifecycle::Degraded);
        assert!(snapshot.child_running);
        assert_eq!(snapshot.generation, 7);
        assert_eq!(snapshot, supervisor.snapshot());
    }

    #[test]
    fn wrong_environment_bootstrap_is_safe_and_degraded() {
        let (supervisor, _script, _events) = supervisor("wrong_env");
        let snapshot = supervisor.start();
        assert_eq!(snapshot.lifecycle, BackendLifecycle::Degraded);
        assert!(!snapshot.child_running);
        assert_eq!(snapshot, supervisor.snapshot());
        let error = snapshot.last_error.as_ref().expect("startup error");
        assert_eq!(error.code, "RUNTIME_WRONG_CONDA_ENV");
        assert!(!error.message.contains("wrong environment"));
    }

    #[test]
    fn unsupported_startup_protocol_version_is_distinct() {
        let (supervisor, _script, _events) = supervisor("wrong_version");
        let snapshot = supervisor.start();
        assert_eq!(snapshot.lifecycle, BackendLifecycle::Degraded);
        assert!(!snapshot.child_running);
        assert_eq!(snapshot, supervisor.snapshot());
        assert_eq!(
            snapshot
                .last_error
                .as_ref()
                .map(|error| error.code.as_str()),
            Some("PROTOCOL_VERSION_UNSUPPORTED")
        );
        assert!(supervisor.wait_until_stopped(Duration::from_secs(1)));
    }

    #[test]
    fn conda_identity_rejects_a_different_environment_name() {
        let prefix = PathBuf::from(std::env::var_os("CONDA_PREFIX").expect("CONDA_PREFIX"));
        let error = validate_conda_identity(&prefix, Some(std::ffi::OsStr::new("other")))
            .expect_err("wrong environment must fail");
        assert_eq!(error.code, "RUNTIME_WRONG_CONDA_ENV");
    }

    #[test]
    fn source_launch_uses_the_exact_active_conda_interpreter() {
        let prefix = PathBuf::from(std::env::var_os("CONDA_PREFIX").expect("CONDA_PREFIX"));
        let launch = source_conda_launch().expect("source Conda launch");
        assert_eq!(launch.program, prefix.join("bin/python"));
        assert_eq!(launch.conda_prefix.as_deref(), Some(prefix.as_path()));
        assert_eq!(
            launch.arguments,
            [OsString::from("-m"), OsString::from("agent.desktop.server")]
        );
        assert!(launch.current_dir.join("app/pyproject.toml").is_file());
    }

    #[test]
    fn duplicate_request_id_is_rejected_before_writing() {
        let (supervisor, _script, _events) = supervisor("normal");
        assert_eq!(supervisor.start().lifecycle, BackendLifecycle::Ready);
        supervisor
            .request(request(REQUEST_ID))
            .expect("first request");
        let error = supervisor
            .request(request(REQUEST_ID))
            .expect_err("duplicate");
        assert_eq!(error.code, "DUPLICATE_REQUEST_ID");
        supervisor.shutdown();
    }

    #[test]
    fn malformed_and_oversized_output_fail_the_pending_request() {
        for mode in ["malformed", "oversized"] {
            let (supervisor, _script, _events) = supervisor(mode);
            assert_eq!(supervisor.start().lifecycle, BackendLifecycle::Ready);
            let error = supervisor.request(request(REQUEST_ID)).expect_err(mode);
            assert_eq!(error.code, "PROTOCOL_INVALID");
            assert_eq!(supervisor.snapshot().pending_requests, 0);
            assert!(supervisor.wait_until_stopped(Duration::from_secs(1)));
        }
    }

    #[test]
    fn stderr_is_drained_but_only_counts_are_retained() {
        let (supervisor, _script, _events) = supervisor("stderr");
        assert_eq!(supervisor.start().lifecycle, BackendLifecycle::Ready);
        let deadline = Instant::now() + Duration::from_secs(1);
        while supervisor.snapshot().stderr_bytes < 43 && Instant::now() < deadline {
            thread::sleep(Duration::from_millis(10));
        }
        let snapshot = supervisor.snapshot();
        assert_eq!(snapshot.stderr_bytes, 43);
        assert_eq!(snapshot.stderr_lines, 2);
        let serialized = serde_json::to_string(&snapshot).expect("serialize snapshot");
        assert!(!serialized.contains("diagnostic"));
        supervisor.shutdown();
    }

    #[test]
    fn forced_shutdown_is_distinct() {
        let (mut supervisor, _script, _events) = supervisor("forced");
        supervisor.timeouts.shutdown_response = Duration::from_millis(60);
        assert_eq!(supervisor.start().lifecycle, BackendLifecycle::Ready);
        let report = supervisor.shutdown();
        assert_eq!(report.kind, ShutdownKind::Forced);
        assert_eq!(report.flushed, None);
    }

    #[test]
    fn concurrent_shutdown_callers_receive_the_same_report() {
        let (supervisor, _script, _events) = supervisor("slow_graceful");
        assert_eq!(supervisor.start().lifecycle, BackendLifecycle::Ready);
        let first = supervisor.clone();
        let first_thread = thread::spawn(move || first.shutdown());
        thread::sleep(Duration::from_millis(20));
        let second_report = supervisor.shutdown();
        let first_report = first_thread.join().expect("first shutdown caller");
        assert_eq!(first_report.kind, ShutdownKind::Graceful);
        assert_eq!(second_report, first_report);
    }

    #[test]
    fn stopped_generation_releases_its_writer_and_child_control() {
        let (supervisor, _script, _events) = supervisor("normal");
        assert_eq!(supervisor.start().lifecycle, BackendLifecycle::Ready);
        let child = {
            let state = lock_state(&supervisor.core);
            Arc::downgrade(state.child.as_ref().expect("child control"))
        };
        assert_eq!(supervisor.shutdown().kind, ShutdownKind::Graceful);
        let deadline = Instant::now() + Duration::from_secs(1);
        while child.upgrade().is_some() && Instant::now() < deadline {
            thread::sleep(Duration::from_millis(10));
        }
        assert!(child.upgrade().is_none());
    }

    #[test]
    fn child_crash_fails_pending_and_restart_is_user_driven() {
        let (crashing, _script, _events) = supervisor("crash");
        assert_eq!(crashing.start().lifecycle, BackendLifecycle::Ready);
        let error = crashing
            .request(request(REQUEST_ID))
            .expect_err("crash failure");
        assert_eq!(error.code, "BACKEND_CRASHED");
        assert_eq!(crashing.snapshot().lifecycle, BackendLifecycle::Crashed);

        let (healthy, _healthy_script, _events) = supervisor("normal");
        assert_eq!(healthy.start().lifecycle, BackendLifecycle::Ready);
        let first_generation = healthy.snapshot().generation;
        let restarted = healthy.restart();
        assert_eq!(restarted.lifecycle, BackendLifecycle::Ready);
        assert!(restarted.generation > first_generation);
        assert_eq!(restarted.last_shutdown, None);
        child_exited(&healthy.core, first_generation);
        assert_eq!(healthy.snapshot(), restarted);
        healthy
            .request(request(REQUEST_ID_2))
            .expect("request after restart");
        healthy.shutdown();
    }

    #[test]
    fn a_new_generation_cannot_reuse_the_prior_shutdown_report() {
        let (supervisor, _script, _events) = supervisor("normal");
        assert_eq!(supervisor.start().lifecycle, BackendLifecycle::Ready);
        assert_eq!(supervisor.shutdown().kind, ShutdownKind::Graceful);
        let restarted = supervisor.start();
        assert_eq!(restarted.lifecycle, BackendLifecycle::Ready);
        assert_eq!(restarted.last_shutdown, None);

        let child = lock_state(&supervisor.core).child.clone().expect("child");
        kill_child(&child);
        let deadline = Instant::now() + Duration::from_secs(1);
        while supervisor.snapshot().child_running && Instant::now() < deadline {
            thread::sleep(Duration::from_millis(10));
        }
        assert_eq!(supervisor.snapshot().lifecycle, BackendLifecycle::Crashed);
        assert_eq!(supervisor.shutdown().kind, ShutdownKind::NotRunning);
    }

    #[test]
    fn snapshot_and_report_use_the_fixed_camel_case_shape() {
        let snapshot = serde_json::to_value(BackendSnapshot::default()).expect("snapshot");
        assert!(snapshot.get("childRunning").is_some());
        assert!(snapshot.get("pendingRequests").is_some());
        assert!(snapshot.get("lastShutdown").is_some());
        let report = serde_json::to_value(ShutdownReport {
            kind: ShutdownKind::NotRunning,
            flushed: None,
        })
        .expect("report");
        assert_eq!(report["kind"], "not_running");
        assert!(report.get("flushed").is_some());
    }
}
