import assert from "node:assert/strict";
import test from "node:test";

import {
  BackendClientError,
  MAX_UI_ERROR_CHARS,
  MAX_UI_MCP_FAMILIES,
  MAX_UI_PATH_CHARS,
  backendReducer,
  buildProtocolRequest,
  createBackendClient,
  initialBackendState,
  normalizeUiError,
  parseBridgeEvent,
  toBoundedDiagnostics,
  type BackendSnapshot,
  type InvokeCommand,
} from "../src/backend.ts";
import type { RuntimeDiagnosticsDto, SessionCreatedDto } from "../src/protocol.ts";

const requestId = "123e4567-e89b-42d3-a456-426614174000";

const stoppedSnapshot: BackendSnapshot = {
  lifecycle: "stopped",
  generation: 0,
  childRunning: false,
  pendingRequests: 0,
  stderrLines: 0,
  stderrBytes: 0,
  lastError: null,
  lastShutdown: null,
};

const readySnapshot: BackendSnapshot = {
  ...stoppedSnapshot,
  lifecycle: "ready",
  generation: 1,
  childRunning: true,
};

const diagnostics: RuntimeDiagnosticsDto = {
  backendState: "ready",
  platform: "linux",
  appRoot: "/workspace/app",
  workingDirectory: "/workspace/app",
  originalWorkingDirectory: "/workspace",
  pythonVersion: "3.13.14",
  sysPrefix: "/conda/envs/app",
  condaEnvironment: "app",
  condaPrefix: "/conda/envs/app",
  protocolVersion: 1,
  backendVersion: "0.1.0",
  openRouterConfigured: false,
  openAlexConfigured: true,
  storePath: "/workspace/app/store",
  citationOutputPath: "/workspace/cite",
  ollamaReachable: null,
  ollamaModelAvailable: null,
  mcpEnabled: false,
  mcpFamilies: [],
  mcpDiagnostics: [],
};

const session: SessionCreatedDto = {
  sessionId: "session-1",
  turnCount: 0,
  graphRecursionLimit: 25,
  planMode: false,
  planLogPath: null,
  thinkingMode: "normal",
  loadedSkills: [],
  mcpFamilies: [],
  startupDiagnostics: [],
  extensionRevision: 0,
};

test("lifecycle reducer keeps backend readiness, session readiness, and recovery distinct", () => {
  let state = backendReducer(initialBackendState, { type: "snapshot", snapshot: stoppedSnapshot });
  assert.equal(state.phase, "stopped");

  state = backendReducer(state, { type: "action-started", action: "start" });
  assert.equal(state.phase, "starting");
  state = backendReducer(state, { type: "snapshot", snapshot: readySnapshot });
  state = backendReducer(state, { type: "action-completed", action: "start" });
  assert.equal(state.phase, "backend-ready");

  state = backendReducer(state, { type: "action-started", action: "diagnostics" });
  assert.equal(state.phase, "busy");
  state = backendReducer(state, {
    type: "diagnostics-succeeded",
    diagnostics: toBoundedDiagnostics(diagnostics),
  });
  assert.equal(state.phase, "backend-ready");

  state = backendReducer(state, { type: "action-started", action: "session" });
  assert.equal(state.phase, "busy");
  state = backendReducer(state, { type: "session-created", session });
  assert.equal(state.phase, "session-ready");

  state = backendReducer(state, {
    type: "snapshot",
    snapshot: {
      ...readySnapshot,
      lifecycle: "crashed",
      childRunning: false,
      lastError: { code: "CHILD_EXITED", message: "Backend exited.", retryable: true },
    },
  });
  assert.equal(state.phase, "crashed");
  assert.equal(state.session, null);

  state = backendReducer(state, { type: "action-started", action: "restart" });
  assert.equal(state.phase, "restarting");
  state = backendReducer(state, {
    type: "snapshot",
    snapshot: { ...readySnapshot, generation: 2 },
  });
  state = backendReducer(state, { type: "action-completed", action: "restart" });
  assert.equal(state.phase, "backend-ready");
  assert.equal(state.diagnostics, null);

  state = backendReducer(state, { type: "action-started", action: "shutdown" });
  assert.equal(state.phase, "shutting-down");
  state = backendReducer(state, {
    type: "snapshot",
    snapshot: {
      ...stoppedSnapshot,
      generation: 2,
      lastShutdown: { kind: "graceful", flushed: true },
    },
  });
  state = backendReducer(state, { type: "action-completed", action: "shutdown" });
  assert.equal(state.phase, "stopped");
  assert.equal(state.snapshot?.lastShutdown?.flushed, true);
});

test("request builder creates a canonical protocol-v1 request and validates params", () => {
  assert.deepEqual(buildProtocolRequest("runtime.diagnostics", {}, () => requestId), {
    protocolVersion: 1,
    messageType: "request",
    requestId,
    method: "runtime.diagnostics",
    params: {},
  });
  assert.throws(() => buildProtocolRequest("session.turn", {}, () => requestId));
  assert.deepEqual(
    buildProtocolRequest(
      "session.turn",
      { text: "question", turnId: "123e4567e89b42d3a456426614174001" },
      () => requestId,
    ).params,
    { text: "question", turnId: "123e4567e89b42d3a456426614174001" },
  );
  assert.throws(() => buildProtocolRequest("runtime.diagnostics", {}, () => "not-a-uuid"));
});

test("backend client correlates results and applies method-specific success validation", async () => {
  const calls: Array<{ command: string; args?: Record<string, unknown> }> = [];
  const invoke: InvokeCommand = async <T>(command: string, args?: Record<string, unknown>) => {
    calls.push({ command, args });
    return {
      protocolVersion: 1,
      messageType: "result",
      requestId,
      ok: true,
      data: diagnostics,
    } as T;
  };
  const client = createBackendClient({ invoke, idFactory: () => requestId });
  const result = await client.request("runtime.diagnostics", {});
  assert.equal(result.backendVersion, "0.1.0");
  assert.equal(calls.length, 1);
  assert.equal(calls[0].command, "backend_request");
  assert.deepEqual(calls[0].args?.request, {
    protocolVersion: 1,
    messageType: "request",
    requestId,
    method: "runtime.diagnostics",
    params: {},
  });

  const invalidClient = createBackendClient({
    idFactory: () => requestId,
    invoke: async <T>() => ({
      protocolVersion: 1,
      messageType: "result",
      requestId,
      ok: true,
      data: {},
    }) as T,
  });
  await assert.rejects(
    invalidClient.request("runtime.diagnostics", {}),
    (error) => error instanceof BackendClientError && error.uiError.source === "protocol",
  );
});

test("tracked request exposes its request ID before transport invocation", async () => {
  let invoked = false;
  const client = createBackendClient({
    idFactory: () => requestId,
    invoke: async <T>() => {
      invoked = true;
      return {
        protocolVersion: 1,
        messageType: "result",
        requestId,
        ok: true,
        data: diagnostics,
      } as T;
    },
  });

  const tracked = client.requestTracked("runtime.diagnostics", {});
  assert.equal(tracked.requestId, requestId);
  assert.equal(invoked, false);
  assert.equal((await tracked.result).backendVersion, "0.1.0");
  assert.equal(invoked, true);
});

test("lifecycle commands validate start/restart snapshots and snapshot after shutdown", async () => {
  const restartedSnapshot = { ...readySnapshot, generation: 2 };
  const shutdownSnapshot: BackendSnapshot = {
    ...stoppedSnapshot,
    generation: 2,
    lastShutdown: { kind: "graceful", flushed: true },
  };
  const calls: string[] = [];
  const client = createBackendClient({
    invoke: async <T>(command: string) => {
      calls.push(command);
      if (command === "backend_start") return readySnapshot as T;
      if (command === "backend_restart") return restartedSnapshot as T;
      if (command === "backend_shutdown") {
        return { kind: "graceful", flushed: true } as T;
      }
      if (command === "backend_snapshot") return shutdownSnapshot as T;
      throw new Error(`Unexpected command: ${command}`);
    },
  });

  assert.deepEqual(await client.start(), readySnapshot);
  assert.deepEqual(await client.restart(), restartedSnapshot);
  assert.deepEqual(await client.shutdown(), shutdownSnapshot);
  assert.deepEqual(calls, [
    "backend_start",
    "backend_restart",
    "backend_shutdown",
    "backend_snapshot",
  ]);

  const invalidShutdown = createBackendClient({
    invoke: async <T>(command: string) => {
      if (command === "backend_shutdown") return { kind: "graceful", flushed: "yes" } as T;
      return shutdownSnapshot as T;
    },
  });
  await assert.rejects(invalidShutdown.shutdown(), (error) => {
    assert.ok(error instanceof BackendClientError);
    assert.equal(error.uiError.source, "transport");
    return true;
  });
});

test("backend client maps protocol business failures into safe UI errors", async () => {
  const client = createBackendClient({
    idFactory: () => requestId,
    invoke: async <T>() => ({
      protocolVersion: 1,
      messageType: "result",
      requestId,
      ok: false,
      error: {
        code: "OPENROUTER_NOT_CONFIGURED",
        message: "API token is missing from the local configuration.",
        retryable: true,
        details: {},
      },
    }) as T,
  });
  await assert.rejects(client.request("session.create", { loadMcp: false }), (error) => {
    assert.ok(error instanceof BackendClientError);
    assert.equal(error.uiError.code, "OPENROUTER_NOT_CONFIGURED");
    assert.equal(error.uiError.source, "business");
    assert.doesNotMatch(error.uiError.message, /token/i);
    return true;
  });
});

test("bridge events validate lifecycle payloads and process-event origins", () => {
  assert.deepEqual(parseBridgeEvent({ type: "lifecycle", snapshot: readySnapshot }), {
    type: "lifecycle",
    snapshot: readySnapshot,
  });

  const ready = {
    protocolVersion: 1,
    messageType: "event",
    event: "backend.ready",
    data: {},
  };
  assert.equal(
    parseBridgeEvent({ type: "protocol", origin: "python", message: ready }).type,
    "protocol",
  );
  assert.throws(() => parseBridgeEvent({ type: "protocol", origin: "rust", message: ready }));

  const crashed = { ...ready, event: "backend.crashed" };
  assert.equal(
    parseBridgeEvent({ type: "protocol", origin: "rust", message: crashed }).type,
    "protocol",
  );
  assert.throws(() => parseBridgeEvent({ type: "protocol", origin: "python", message: crashed }));
});

test("error and diagnostic normalization stays bounded and omits unsafe detail", () => {
  const normalized = normalizeUiError({
    code: "not safe code",
    message: `failure\n${"x".repeat(MAX_UI_ERROR_CHARS * 2)}`,
    retryable: false,
  });
  assert.equal(normalized.code, "BACKEND_UNAVAILABLE");
  assert.equal(normalized.retryable, false);
  assert.ok(normalized.message.length <= MAX_UI_ERROR_CHARS);
  assert.doesNotMatch(normalized.message, /\n/);

  const bounded = toBoundedDiagnostics({
    ...diagnostics,
    appRoot: `/${"a".repeat(MAX_UI_PATH_CHARS * 2)}`,
    mcpFamilies: Array.from({ length: MAX_UI_MCP_FAMILIES * 2 }, (_, index) => `family-${index}`),
    mcpDiagnostics: ["must not be copied"],
  });
  assert.ok(bounded.appRoot.length <= MAX_UI_PATH_CHARS);
  assert.equal(bounded.mcpFamilies.length, MAX_UI_MCP_FAMILIES);
  assert.equal("mcpDiagnostics" in bounded, false);
  assert.equal("sysPrefix" in bounded, false);
  assert.equal("originalWorkingDirectory" in bounded, false);
});
