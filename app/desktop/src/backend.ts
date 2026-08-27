import {
  PROTOCOL_VERSION,
  type JsonObject,
  type ProcessEventEnvelope,
  type ProtocolMessage,
  type ProtocolMethod,
  type ProtocolOrigin,
  type RequestEnvelope,
  type RuntimeDiagnosticsDto,
  type SessionCreatedDto,
  parseProtocolMessage,
  parseProtocolMessageFromOrigin,
  validateResultData,
} from "./protocol.ts";

export const BACKEND_EVENT_NAME = "research-agent://backend-event";
export const MAX_UI_ERROR_CHARS = 320;
export const MAX_UI_PATH_CHARS = 512;
export const MAX_UI_MCP_FAMILIES = 16;

export type BackendLifecycle =
  | "stopped"
  | "starting"
  | "ready"
  | "degraded"
  | "crashed"
  | "restarting"
  | "shutting_down";

export interface BridgeError {
  code: string;
  message: string;
  retryable: boolean;
}

export interface ShutdownReport {
  kind: "graceful" | "forced" | "not_running";
  flushed: boolean | null;
}

export interface BackendSnapshot {
  lifecycle: BackendLifecycle;
  generation: number;
  childRunning: boolean;
  pendingRequests: number;
  stderrLines: number;
  stderrBytes: number;
  lastError: BridgeError | null;
  lastShutdown: ShutdownReport | null;
}

export interface SafeUiError extends BridgeError {
  source: "transport" | "business" | "protocol" | "lifecycle" | "preview";
}

export interface BoundedRuntimeDiagnostics {
  platform: "linux";
  pythonVersion: string;
  protocolVersion: number;
  backendVersion: string;
  condaEnvironment: string | null;
  condaPrefix: string | null;
  appRoot: string;
  workingDirectory: string;
  storePath: string;
  citationOutputPath: string;
  openRouterConfigured: boolean;
  openAlexConfigured: boolean;
  ollamaReachable: boolean | null;
  ollamaModelAvailable: boolean | null;
  mcpEnabled: boolean;
  mcpFamilies: string[];
}

export type UiLifecycle =
  | "starting"
  | "backend-ready"
  | "session-ready"
  | "busy"
  | "degraded"
  | "crashed"
  | "restarting"
  | "shutting-down"
  | "stopped";

export type BackendActionName = "start" | "restart" | "shutdown" | "diagnostics" | "session";

export interface BackendUiState {
  phase: UiLifecycle;
  snapshot: BackendSnapshot | null;
  diagnostics: BoundedRuntimeDiagnostics | null;
  session: SessionCreatedDto | null;
  error: SafeUiError | null;
  activeAction: BackendActionName | null;
  browserPreview: boolean;
}

export const initialBackendState: BackendUiState = {
  phase: "stopped",
  snapshot: null,
  diagnostics: null,
  session: null,
  error: null,
  activeAction: null,
  browserPreview: false,
};

export type BackendUiAction =
  | { type: "browser-preview" }
  | { type: "snapshot"; snapshot: BackendSnapshot }
  | { type: "protocol-event"; message: ProtocolMessage }
  | { type: "action-started"; action: BackendActionName }
  | { type: "action-completed"; action: BackendActionName }
  | { type: "diagnostics-succeeded"; diagnostics: BoundedRuntimeDiagnostics }
  | { type: "session-created"; session: SessionCreatedDto }
  | { type: "action-failed"; error: SafeUiError };

const backendLifecycles: readonly BackendLifecycle[] = [
  "stopped",
  "starting",
  "ready",
  "degraded",
  "crashed",
  "restarting",
  "shutting_down",
];

const sensitiveMessagePattern = /api[ _-]?key|authorization|bearer|secret|token|traceback/i;
const safeCodePattern = /^[A-Z][A-Z0-9_]{0,63}$/;

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requireExactKeys(
  value: Record<string, unknown>,
  expected: readonly string[],
  field: string,
): void {
  const actual = Object.keys(value);
  if (actual.length !== expected.length || actual.some((key) => !expected.includes(key))) {
    throw new Error(`${field} contains unexpected fields`);
  }
}

function requireNonNegativeInteger(value: unknown, field: string): number {
  if (!Number.isSafeInteger(value) || Number(value) < 0) {
    throw new Error(`${field} must be a non-negative integer`);
  }
  return Number(value);
}

function boundText(value: string, limit: number): string {
  const normalized = value.replace(/[\u0000-\u001f\u007f]+/g, " ").replace(/\s+/g, " ").trim();
  if (normalized.length <= limit) {
    return normalized;
  }
  return `${normalized.slice(0, Math.max(0, limit - 1))}…`;
}

function parseBridgeError(value: unknown): BridgeError {
  if (!isObject(value)) {
    throw new Error("bridge error must be an object");
  }
  requireExactKeys(value, ["code", "message", "retryable"], "bridge error");
  if (typeof value.code !== "string" || typeof value.message !== "string") {
    throw new Error("bridge error code and message must be strings");
  }
  if (typeof value.retryable !== "boolean") {
    throw new Error("bridge error retryable must be a boolean");
  }
  return { code: value.code, message: value.message, retryable: value.retryable };
}

function parseShutdownReport(value: unknown): ShutdownReport {
  if (!isObject(value)) {
    throw new Error("shutdown report must be an object");
  }
  requireExactKeys(value, ["kind", "flushed"], "shutdown report");
  if (value.kind !== "graceful" && value.kind !== "forced" && value.kind !== "not_running") {
    throw new Error("shutdown report kind is invalid");
  }
  if (value.flushed !== null && typeof value.flushed !== "boolean") {
    throw new Error("shutdown report flushed must be a boolean or null");
  }
  return { kind: value.kind, flushed: value.flushed };
}

export function parseBackendSnapshot(value: unknown): BackendSnapshot {
  if (!isObject(value)) {
    throw new Error("backend snapshot must be an object");
  }
  requireExactKeys(
    value,
    [
      "lifecycle",
      "generation",
      "childRunning",
      "pendingRequests",
      "stderrLines",
      "stderrBytes",
      "lastError",
      "lastShutdown",
    ],
    "backend snapshot",
  );
  if (
    typeof value.lifecycle !== "string" ||
    !backendLifecycles.includes(value.lifecycle as BackendLifecycle)
  ) {
    throw new Error("backend snapshot lifecycle is invalid");
  }
  if (typeof value.childRunning !== "boolean") {
    throw new Error("backend snapshot childRunning must be a boolean");
  }
  return {
    lifecycle: value.lifecycle as BackendLifecycle,
    generation: requireNonNegativeInteger(value.generation, "generation"),
    childRunning: value.childRunning,
    pendingRequests: requireNonNegativeInteger(value.pendingRequests, "pendingRequests"),
    stderrLines: requireNonNegativeInteger(value.stderrLines, "stderrLines"),
    stderrBytes: requireNonNegativeInteger(value.stderrBytes, "stderrBytes"),
    lastError: value.lastError === null ? null : parseBridgeError(value.lastError),
    lastShutdown: value.lastShutdown === null ? null : parseShutdownReport(value.lastShutdown),
  };
}

export function normalizeUiError(
  value: unknown,
  source: SafeUiError["source"] = "transport",
): SafeUiError {
  let code = "BACKEND_UNAVAILABLE";
  let message = "The desktop backend could not complete this action.";
  let retryable = true;

  if (isObject(value)) {
    if (typeof value.code === "string") {
      code = value.code;
    }
    if (typeof value.message === "string") {
      message = value.message;
    }
    if (typeof value.retryable === "boolean") {
      retryable = value.retryable;
    }
  } else if (value instanceof Error) {
    message = value.message;
  } else if (typeof value === "string") {
    message = value;
  }

  const safeCode = safeCodePattern.test(code) ? code : "BACKEND_UNAVAILABLE";
  const boundedMessage = sensitiveMessagePattern.test(message)
    ? "Sensitive backend details were withheld. Check the local backend logs."
    : boundText(message, MAX_UI_ERROR_CHARS) || "The desktop backend could not complete this action.";
  return { code: safeCode, message: boundedMessage, retryable, source };
}

function phaseForSnapshot(state: BackendUiState, snapshot: BackendSnapshot): UiLifecycle {
  if (snapshot.lifecycle === "ready") {
    if (state.activeAction === "diagnostics" || state.activeAction === "session") {
      return "busy";
    }
    return state.session === null ? "backend-ready" : "session-ready";
  }
  if (snapshot.lifecycle === "starting") return "starting";
  if (snapshot.lifecycle === "restarting") return "restarting";
  if (snapshot.lifecycle === "shutting_down") return "shutting-down";
  if (snapshot.lifecycle === "crashed") return "crashed";
  if (snapshot.lifecycle === "degraded") return "degraded";
  return "stopped";
}

function settledReadyPhase(state: BackendUiState): UiLifecycle {
  if (state.snapshot?.lifecycle !== "ready") {
    return state.phase;
  }
  return state.session === null ? "backend-ready" : "session-ready";
}

export function backendReducer(state: BackendUiState, action: BackendUiAction): BackendUiState {
  if (action.type === "browser-preview") {
    return {
      ...state,
      phase: "degraded",
      browserPreview: true,
      error: {
        code: "BROWSER_PREVIEW",
        message: "Browser preview cannot connect to the desktop backend. Open the Tauri application.",
        retryable: false,
        source: "preview",
      },
    };
  }
  if (action.type === "snapshot") {
    const generationChanged =
      state.snapshot !== null && state.snapshot.generation !== action.snapshot.generation;
    const nextState: BackendUiState = {
      ...state,
      snapshot: action.snapshot,
      diagnostics: generationChanged ? null : state.diagnostics,
      session:
        generationChanged || action.snapshot.lifecycle !== "ready" ? null : state.session,
      error:
        action.snapshot.lastError === null
          ? state.error
          : normalizeUiError(action.snapshot.lastError, "lifecycle"),
    };
    return { ...nextState, phase: phaseForSnapshot(nextState, action.snapshot) };
  }
  if (action.type === "protocol-event") {
    if (action.message.messageType !== "event" || "requestId" in action.message) {
      return state;
    }
    if (action.message.event === "backend.ready") {
      return { ...state, phase: state.session === null ? "backend-ready" : "session-ready" };
    }
    if (action.message.event === "backend.crashed") {
      return { ...state, phase: "crashed", session: null, activeAction: null };
    }
    if (action.message.event === "backend.shutting_down") {
      return { ...state, phase: "shutting-down", activeAction: null };
    }
    if (action.message.event === "backend.protocol_error") {
      return {
        ...state,
        phase: "degraded",
        error: normalizeUiError(
          { code: "PROTOCOL_INVALID", message: "The backend reported a protocol error.", retryable: true },
          "protocol",
        ),
        activeAction: null,
      };
    }
    return state;
  }
  if (action.type === "action-started") {
    if (state.activeAction !== null) {
      return state;
    }
    const phase =
      action.action === "start"
        ? "starting"
        : action.action === "restart"
          ? "restarting"
          : action.action === "shutdown"
            ? "shutting-down"
            : "busy";
    return { ...state, phase, activeAction: action.action, error: null };
  }
  if (action.type === "action-completed") {
    if (state.activeAction !== action.action) {
      return state;
    }
    const nextState = { ...state, activeAction: null };
    return { ...nextState, phase: phaseForSnapshot(nextState, nextState.snapshot ?? {
      lifecycle: "stopped",
      generation: 0,
      childRunning: false,
      pendingRequests: 0,
      stderrLines: 0,
      stderrBytes: 0,
      lastError: null,
      lastShutdown: null,
    }) };
  }
  if (action.type === "diagnostics-succeeded") {
    const nextState = { ...state, diagnostics: action.diagnostics, error: null, activeAction: null };
    return { ...nextState, phase: settledReadyPhase(nextState) };
  }
  if (action.type === "session-created") {
    return {
      ...state,
      phase: "session-ready",
      session: action.session,
      error: null,
      activeAction: null,
    };
  }
  const fallbackPhase: UiLifecycle =
    state.snapshot?.lifecycle === "crashed"
      ? "crashed"
      : state.snapshot?.lifecycle === "stopped"
        ? "stopped"
        : "degraded";
  return { ...state, phase: fallbackPhase, error: action.error, activeAction: null };
}

export function buildProtocolRequest(
  method: ProtocolMethod,
  params: JsonObject,
  idFactory: () => string = () => globalThis.crypto.randomUUID(),
): RequestEnvelope {
  const parsed = parseProtocolMessage({
    protocolVersion: PROTOCOL_VERSION,
    messageType: "request",
    requestId: idFactory(),
    method,
    params,
  });
  if (parsed.messageType !== "request") {
    throw new Error("request builder produced a non-request message");
  }
  return parsed;
}

export type ParsedBridgeEvent =
  | { type: "lifecycle"; snapshot: BackendSnapshot }
  | { type: "protocol"; origin: ProtocolOrigin; message: ProtocolMessage };

export function parseBridgeEvent(value: unknown): ParsedBridgeEvent {
  if (!isObject(value) || typeof value.type !== "string") {
    throw new Error("backend event must be a tagged object");
  }
  if (value.type === "lifecycle") {
    requireExactKeys(value, ["type", "snapshot"], "lifecycle event");
    return { type: "lifecycle", snapshot: parseBackendSnapshot(value.snapshot) };
  }
  if (value.type === "protocol") {
    requireExactKeys(value, ["type", "origin", "message"], "protocol event");
    if (value.origin !== "python" && value.origin !== "rust") {
      throw new Error("protocol event origin is invalid");
    }
    return {
      type: "protocol",
      origin: value.origin,
      message: parseProtocolMessageFromOrigin(value.message, value.origin),
    };
  }
  throw new Error("backend event type is invalid");
}

function boundedPath(value: string): string {
  return boundText(value, MAX_UI_PATH_CHARS);
}

export function toBoundedDiagnostics(value: RuntimeDiagnosticsDto): BoundedRuntimeDiagnostics {
  return {
    platform: value.platform,
    pythonVersion: boundText(value.pythonVersion, 80),
    protocolVersion: value.protocolVersion,
    backendVersion: boundText(value.backendVersion, 80),
    condaEnvironment:
      value.condaEnvironment === null ? null : boundText(value.condaEnvironment, 80),
    condaPrefix: value.condaPrefix === null ? null : boundedPath(value.condaPrefix),
    appRoot: boundedPath(value.appRoot),
    workingDirectory: boundedPath(value.workingDirectory),
    storePath: boundedPath(value.storePath),
    citationOutputPath: boundedPath(value.citationOutputPath),
    openRouterConfigured: value.openRouterConfigured,
    openAlexConfigured: value.openAlexConfigured,
    ollamaReachable: value.ollamaReachable,
    ollamaModelAvailable: value.ollamaModelAvailable,
    mcpEnabled: value.mcpEnabled,
    mcpFamilies: value.mcpFamilies
      .slice(0, MAX_UI_MCP_FAMILIES)
      .map((family) => boundText(family, 80)),
  };
}

export type InvokeCommand = <T>(
  command: string,
  args?: Record<string, unknown>,
) => Promise<T>;

export interface BackendClient {
  start(): Promise<BackendSnapshot>;
  snapshot(): Promise<BackendSnapshot>;
  request(method: ProtocolMethod, params: JsonObject): Promise<JsonObject>;
  shutdown(): Promise<BackendSnapshot>;
  restart(): Promise<BackendSnapshot>;
}

export class BackendClientError extends Error {
  readonly uiError: SafeUiError;

  constructor(uiError: SafeUiError) {
    super(uiError.message);
    this.name = "BackendClientError";
    this.uiError = uiError;
  }
}

function asClientError(value: unknown, source: SafeUiError["source"]): BackendClientError {
  if (value instanceof BackendClientError) {
    return value;
  }
  return new BackendClientError(normalizeUiError(value, source));
}

export function createBackendClient(options: {
  invoke: InvokeCommand;
  idFactory?: () => string;
}): BackendClient {
  const idFactory = options.idFactory ?? (() => globalThis.crypto.randomUUID());

  async function snapshot(): Promise<BackendSnapshot> {
    try {
      return parseBackendSnapshot(await options.invoke<unknown>("backend_snapshot"));
    } catch (error) {
      throw asClientError(error, "transport");
    }
  }

  async function lifecycleCommand(command: "backend_start" | "backend_restart") {
    try {
      return parseBackendSnapshot(await options.invoke<unknown>(command));
    } catch (error) {
      throw asClientError(error, "transport");
    }
  }

  async function shutdown(): Promise<BackendSnapshot> {
    try {
      parseShutdownReport(await options.invoke<unknown>("backend_shutdown"));
    } catch (error) {
      throw asClientError(error, "transport");
    }
    return snapshot();
  }

  return {
    start: () => lifecycleCommand("backend_start"),
    snapshot,
    async request(method, params) {
      let request: RequestEnvelope;
      try {
        request = buildProtocolRequest(method, params, idFactory);
      } catch (error) {
        throw asClientError(error, "protocol");
      }

      let raw: unknown;
      try {
        raw = await options.invoke<unknown>("backend_request", { request });
      } catch (error) {
        throw asClientError(error, "transport");
      }

      try {
        const message = parseProtocolMessage(raw);
        if (message.messageType !== "result" || message.requestId !== request.requestId) {
          throw new Error("Backend returned an uncorrelated response.");
        }
        if (!message.ok) {
          throw new BackendClientError(normalizeUiError(message.error, "business"));
        }
        validateResultData(method, message.data);
        return message.data;
      } catch (error) {
        throw asClientError(error, "protocol");
      }
    },
    shutdown,
    restart: () => lifecycleCommand("backend_restart"),
  };
}

export function isProcessEvent(message: ProtocolMessage): message is ProcessEventEnvelope {
  return message.messageType === "event" && !("requestId" in message);
}
