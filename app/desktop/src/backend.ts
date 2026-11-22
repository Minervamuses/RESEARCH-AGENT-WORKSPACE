import {
  PROTOCOL_VERSION,
  type JsonObject,
  type ProtocolMessage,
  type ProtocolMethod,
  type ProtocolOrigin,
  type RequestEnvelope,
  type RuntimeDiagnosticsDto,
  type SessionCreatedDto,
  type TurnLifecycleDetailsDto,
  parseProtocolMessage,
  parseTurnLifecycleDetails,
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
  turnLifecycle?: TurnLifecycleDetailsDto;
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
  openRouterConfigured: boolean;
  openAlexConfigured: boolean;
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
  | { type: "session-cleared"; sessionId: string }
  | { type: "action-failed"; error: SafeUiError };

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

function boundText(value: string, limit: number): string {
  const normalized = value.replace(/[\u0000-\u001f\u007f]+/g, " ").replace(/\s+/g, " ").trim();
  if (normalized.length <= limit) {
    return normalized;
  }
  return `${normalized.slice(0, Math.max(0, limit - 1))}…`;
}

function parseShutdownReport(value: unknown): ShutdownReport {
  if (!isObject(value)) {
    throw new Error("shutdown report must be an object");
  }
  return value as unknown as ShutdownReport;
}

/** The Rust host serializes snapshots from one typed struct; only the shape is checked. */
export function parseBackendSnapshot(value: unknown): BackendSnapshot {
  if (!isObject(value)) {
    throw new Error("backend snapshot must be an object");
  }
  return value as unknown as BackendSnapshot;
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
  const boundedMessage =
    boundText(message, MAX_UI_ERROR_CHARS) || "The desktop backend could not complete this action.";
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
  if (action.type === "session-cleared") {
    if (state.session?.sessionId !== action.sessionId) return state;
    const nextState = { ...state, session: null, error: null };
    return { ...nextState, phase: settledReadyPhase(nextState) };
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
      message: parseProtocolMessage(value.message),
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
    openRouterConfigured: value.openRouterConfigured,
    openAlexConfigured: value.openAlexConfigured,
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
  initialize(onStarting: () => void): Promise<BackendSnapshot>;
  start(): Promise<BackendSnapshot>;
  snapshot(): Promise<BackendSnapshot>;
  request(method: ProtocolMethod, params: JsonObject): Promise<JsonObject>;
  requestTracked(method: ProtocolMethod, params: JsonObject): TrackedBackendRequest;
  shutdown(): Promise<BackendSnapshot>;
  restart(): Promise<BackendSnapshot>;
}

export interface TrackedBackendRequest {
  requestId: string;
  result: Promise<JsonObject>;
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

/** Methods whose failures carry the turn lifecycle in `error.details`. */
function carriesTurnLifecycle(method: ProtocolMethod): boolean {
  return method === "session.turn" || method === "extensions.apply";
}

function normalizeBusinessError(
  error: { code: string; message: string; retryable: boolean; details: JsonObject },
  request: RequestEnvelope,
): SafeUiError {
  const normalized = normalizeUiError(error, "business");
  if (!carriesTurnLifecycle(request.method)) {
    return normalized;
  }
  const turnLifecycle = parseTurnLifecycleDetails(error.details);
  if (turnLifecycle.turnId !== request.params.turnId) {
    throw new Error("error.details.turnId must match params.turnId");
  }
  return { ...normalized, turnLifecycle };
}

export function createBackendClient(options: {
  invoke: InvokeCommand;
  idFactory?: () => string;
}): BackendClient {
  const idFactory = options.idFactory ?? (() => globalThis.crypto.randomUUID());
  let initialization: Promise<BackendSnapshot> | undefined;

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

  function requestTracked(method: ProtocolMethod, params: JsonObject): TrackedBackendRequest {
    let request: RequestEnvelope;
    try {
      request = buildProtocolRequest(method, params, idFactory);
    } catch (error) {
      throw asClientError(error, "protocol");
    }

    const result = Promise.resolve()
      .then(async () => {
        try {
          return await options.invoke<unknown>("backend_request", { request });
        } catch (error) {
          throw asClientError(error, "transport");
        }
      })
      .then((raw) => {
        try {
          const message = parseProtocolMessage(raw);
          if (message.messageType !== "result" || message.requestId !== request.requestId) {
            throw new Error("Backend returned an uncorrelated response.");
          }
          if (!message.ok) {
            throw new BackendClientError(normalizeBusinessError(message.error, request));
          }
          return message.data;
        } catch (error) {
          throw asClientError(error, "protocol");
        }
      });
    return { requestId: request.requestId, result };
  }

  return {
    initialize(onStarting) {
      initialization ??= snapshot().then((current) => {
        if (current.lifecycle !== "stopped" || current.childRunning) return current;
        onStarting();
        return lifecycleCommand("backend_start");
      });
      return initialization;
    },
    start: () => lifecycleCommand("backend_start"),
    snapshot,
    async request(method, params) {
      return requestTracked(method, params).result;
    },
    requestTracked,
    shutdown,
    restart: () => lifecycleCommand("backend_restart"),
  };
}

export type SnapshotExtensionTransition =
  | "none"
  | "interrupt"
  | "interrupt-restarting"
  | "interrupt-awaiting-load"
  | "awaiting-load";

export interface BackendSnapshotTransitionInput {
  currentGeneration: number;
  historyGeneration: number | null;
  hasProject: boolean;
  selectedConversation: { projectId: string; sessionId: string } | null;
  resumeSelection: { projectId: string; sessionId: string } | null;
  draft: string;
  resumeDraft: string | null;
  snapshot: BackendSnapshot;
  completedAction?: "start" | "restart" | "shutdown";
}

export type BackendSnapshotTransition =
  | { accepted: false }
  | {
      accepted: true;
      nextGeneration: number;
      generationChanged: boolean;
      invalidateOperations: boolean;
      captureResumeState: boolean;
      nextResumeSelection: { projectId: string; sessionId: string } | null;
      nextResumeDraft: string | null;
      clearBindingGeneration: boolean;
      clearTransientUi: boolean;
      resetStaleHistory: boolean;
      extensionTransition: SnapshotExtensionTransition;
      completedAction: "start" | "restart" | "shutdown" | null;
    };

export function planBackendSnapshotTransition(
  input: BackendSnapshotTransitionInput,
): BackendSnapshotTransition {
  const { snapshot, currentGeneration } = input;
  if (snapshot.generation < currentGeneration) {
    return { accepted: false };
  }
  const generationChanged = snapshot.generation !== currentGeneration;
  const captureResumeState = generationChanged && input.hasProject;
  const clearTransientUi = generationChanged || snapshot.lifecycle !== "ready";
  const resetStaleHistory =
    input.historyGeneration !== null && input.historyGeneration !== snapshot.generation;
  let extensionTransition: SnapshotExtensionTransition = "none";
  if (clearTransientUi) {
    if (snapshot.lifecycle === "restarting") {
      extensionTransition = "interrupt-restarting";
    } else if (snapshot.lifecycle === "ready" && generationChanged) {
      extensionTransition = "interrupt-awaiting-load";
    } else {
      extensionTransition = "interrupt";
    }
  } else if (input.completedAction === "restart" && snapshot.lifecycle === "ready") {
    extensionTransition = "awaiting-load";
  }
  return {
    accepted: true,
    nextGeneration: snapshot.generation,
    generationChanged,
    invalidateOperations: generationChanged,
    captureResumeState,
    nextResumeSelection: captureResumeState
      ? input.selectedConversation ?? input.resumeSelection
      : input.resumeSelection,
    nextResumeDraft: captureResumeState ? input.draft : input.resumeDraft,
    clearBindingGeneration: captureResumeState,
    clearTransientUi,
    resetStaleHistory,
    extensionTransition,
    completedAction: input.completedAction ?? null,
  };
}
