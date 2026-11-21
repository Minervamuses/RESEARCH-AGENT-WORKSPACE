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
  planBackendSnapshotTransition,
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

test("initialization starts once, including overlapping and repeated initialization", async () => {
  const calls: string[] = [];
  const client = createBackendClient({
    invoke: async <T>(command: string) => {
      calls.push(command);
      return (command === "backend_snapshot" ? stoppedSnapshot : readySnapshot) as T;
    },
  });
  let starting = 0;
  const initialize = () => client.initialize(() => { starting += 1; });
  assert.deepEqual(await Promise.all([initialize(), initialize()]), [readySnapshot, readySnapshot]);
  await initialize();
  assert.deepEqual(calls, ["backend_snapshot", "backend_start"]);
  assert.equal(starting, 1);
});

test("initialization adopts a running backend without starting another child", async () => {
  for (const lifecycle of ["starting", "ready"] as const) {
    const current = { ...readySnapshot, lifecycle };
    const client = createBackendClient({
      invoke: async <T>(command: string) => {
        assert.equal(command, "backend_snapshot");
        return current as T;
      },
    });
    assert.deepEqual(await client.initialize(() => assert.fail("must not start")), current);
  }
});

test("failed initialization does not loop and permits explicit retry", async () => {
  let starts = 0;
  const client = createBackendClient({
    invoke: async <T>(command: string) => {
      if (command === "backend_snapshot") return stoppedSnapshot as T;
      starts += 1;
      if (starts === 1) throw new Error("Backend could not start");
      return readySnapshot as T;
    },
  });
  await assert.rejects(client.initialize(() => {}), /could not start/);
  await assert.rejects(client.initialize(() => {}), /could not start/);
  assert.equal(starts, 1);
  assert.deepEqual(await client.start(), readySnapshot);
  assert.equal(starts, 2);
});

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
  mcpEnabled: false,
  mcpFamilies: [],
  mcpDiagnostics: [],
};

const session: SessionCreatedDto = {
  sessionId: "session-1",
  turnCount: 0,
  graphRecursionLimit: 25,
  thinkingMode: "normal",
  slashCommands: [],
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
      lastShutdown: { kind: "graceful" },
    },
  });
  state = backendReducer(state, { type: "action-completed", action: "shutdown" });
  assert.equal(state.phase, "stopped");
  assert.equal(state.snapshot?.lastShutdown?.kind, "graceful");
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
      { text: "question", turnId: "123e4567e89b42d3a456426614174001", retry: false },
      () => requestId,
    ).params,
    { text: "question", turnId: "123e4567e89b42d3a456426614174001", retry: false },
  );
  assert.throws(() => buildProtocolRequest(
    "session.turn",
    { text: "question", turnId: "123e4567e89b42d3a456426614174001", retry: "false" },
    () => requestId,
  ));
  assert.throws(() => buildProtocolRequest("runtime.diagnostics", {}, () => "not-a-uuid"));
});

test("backend client correlates results by request ID", async () => {
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

  const uncorrelatedClient = createBackendClient({
    idFactory: () => requestId,
    invoke: async <T>() => ({
      protocolVersion: 1,
      messageType: "result",
      requestId: "123e4567-e89b-42d3-a456-426614174999",
      ok: true,
      data: diagnostics,
    }) as T,
  });
  await assert.rejects(
    uncorrelatedClient.request("runtime.diagnostics", {}),
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

test("lifecycle commands return start/restart snapshots and snapshot after shutdown", async () => {
  const restartedSnapshot = { ...readySnapshot, generation: 2 };
  const shutdownSnapshot: BackendSnapshot = {
    ...stoppedSnapshot,
    generation: 2,
    lastShutdown: { kind: "graceful" },
  };
  const calls: string[] = [];
  const client = createBackendClient({
    invoke: async <T>(command: string) => {
      calls.push(command);
      if (command === "backend_start") return readySnapshot as T;
      if (command === "backend_restart") return restartedSnapshot as T;
      if (command === "backend_shutdown") {
        return { kind: "graceful" } as T;
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
      if (command === "backend_shutdown") return "graceful" as T;
      return shutdownSnapshot as T;
    },
  });
  await assert.rejects(invalidShutdown.shutdown(), (error) => {
    assert.ok(error instanceof BackendClientError);
    assert.equal(error.uiError.source, "transport");
    return true;
  });
});

test("backend client maps protocol business failures into safe UI errors without hiding legitimate keywords", async () => {
  const message = "Prompt exceeds the context token limit; secret rotation docs are in README.";
  const client = createBackendClient({
    idFactory: () => requestId,
    invoke: async <T>() => ({
      protocolVersion: 1,
      messageType: "result",
      requestId,
      ok: false,
      error: {
        code: "OPENROUTER_NOT_CONFIGURED",
        message,
        retryable: true,
        details: {},
      },
    }) as T,
  });
  await assert.rejects(client.request("session.create", { loadMcp: false }), (error) => {
    assert.ok(error instanceof BackendClientError);
    assert.equal(error.uiError.code, "OPENROUTER_NOT_CONFIGURED");
    assert.equal(error.uiError.source, "business");
    assert.equal(error.uiError.message, message);
    return true;
  });
});

test("backend client preserves validated session-turn lifecycle details", async () => {
  const turnId = "123e4567e89b42d3a456426614174001";
  const turnLifecycle = {
    turnId,
    state: "failed",
    accepted: true,
    persisted: true,
  } as const;
  const client = createBackendClient({
    idFactory: () => requestId,
    invoke: async <T>() => ({
      protocolVersion: 1,
      messageType: "result",
      requestId,
      ok: false,
      error: {
        code: "PROVIDER_REQUEST_FAILED",
        message: "The provider request failed.",
        retryable: true,
        details: turnLifecycle,
      },
    }) as T,
  });

  await assert.rejects(
    client.request("session.turn", { text: "question", turnId, retry: false }),
    (error) => {
      assert.ok(error instanceof BackendClientError);
      assert.equal(error.uiError.source, "business");
      assert.deepEqual(error.uiError.turnLifecycle, turnLifecycle);
      assert.equal("details" in error.uiError, false, "arbitrary protocol details stay outside UI state");
      return true;
    },
  );
});

test("backend client preserves validated extension-apply lifecycle details", async () => {
  const turnId = "123e4567e89b42d3a456426614174002";
  const turnLifecycle = {
    turnId,
    state: "interrupted",
    accepted: true,
    persisted: true,
  } as const;
  const client = createBackendClient({
    idFactory: () => requestId,
    invoke: async <T>() => ({
      protocolVersion: 1,
      messageType: "result",
      requestId,
      ok: false,
      error: {
        code: "EXTENSION_APPLY_FAILED",
        message: "The extension apply was interrupted.",
        retryable: false,
        details: turnLifecycle,
      },
    }) as T,
  });

  await assert.rejects(
    client.request("extensions.apply", {
      previewId: "preview-1",
      approvedBindingHashes: [],
      turnId,
      retry: false,
    }),
    (error) => {
      assert.ok(error instanceof BackendClientError);
      assert.equal(error.uiError.source, "business");
      assert.deepEqual(error.uiError.turnLifecycle, turnLifecycle);
      return true;
    },
  );
});

test("bridge events parse lifecycle payloads and protocol envelopes from a known origin", () => {
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
  assert.throws(() => parseBridgeEvent({ type: "protocol", origin: "browser", message: ready }));
  assert.throws(() => parseBridgeEvent({ type: "protocol", origin: "rust", message: { ...ready, event: "backend.unknown" } }));
  assert.throws(() => parseBridgeEvent({ type: "lifecycle", snapshot: "ready" }));
});

const echoTurnId = "123e4567e89b42d3a456426614174001";
const otherTurnId = "123e4567e89b42d3a456426614174009";
const echoSessionId = "28b222e0cc6543aa8d7bbdc423de99a7";

function resultClient(result: Record<string, unknown>) {
  return createBackendClient({
    idFactory: () => requestId,
    invoke: async <T>() => ({ protocolVersion: 1, messageType: "result", requestId, ...result }) as T,
  });
}

function rejectsAsProtocol(error: unknown): boolean {
  return error instanceof BackendClientError && error.uiError.source === "protocol";
}

const documentContext = {
  rootPath: "/project",
  path: "/project/draft.md",
  editorRevision: 1,
  sourceText: "text",
  diskFingerprint: "a".repeat(64),
};

test("echo: document.apply and approval.resolve accept success results without turnId", async () => {
  const applied = await resultClient({ ok: true, data: { path: "/project/draft.md", status: "saved" } })
    .request("document.apply", { documentContext, turnId: echoTurnId, callId: "call-1" });
  assert.equal(applied.status, "saved");
  const resolved = await resultClient({ ok: true, data: { approvalId: "approval-1", approved: true } })
    .request("approval.resolve", { approvalId: "approval-1", approved: true, turnId: echoTurnId });
  assert.equal(resolved.approved, true);
});

test("echo: session.stop rejects another turn or session and accepts its own", async () => {
  const params = { sessionId: echoSessionId, turnId: echoTurnId, parentRequestId: "123e4567-e89b-42d3-a456-426614174111" };
  const stopped = { sessionId: echoSessionId, turnId: echoTurnId, state: null, accepted: false, persisted: false };
  assert.equal((await resultClient({ ok: true, data: stopped }).request("session.stop", params)).turnId, echoTurnId);
  await assert.rejects(
    resultClient({ ok: true, data: { ...stopped, turnId: otherTurnId } }).request("session.stop", params),
    rejectsAsProtocol,
  );
  await assert.rejects(
    resultClient({ ok: true, data: { ...stopped, sessionId: "38b222e0cc6543aa8d7bbdc423de99a7" } }).request("session.stop", params),
    rejectsAsProtocol,
  );
});

test("echo: session.select rejects a result for another session", async () => {
  await assert.rejects(
    resultClient({ ok: true, data: { projectId: "p1", sessionId: "38b222e0cc6543aa8d7bbdc423de99a7" } })
      .request("session.select", { projectId: "p1", sessionId: echoSessionId }),
    rejectsAsProtocol,
  );
  await assert.rejects(
    resultClient({ ok: true, data: { projectId: "p2", sessionId: echoSessionId } })
      .request("session.select", { projectId: "p1", sessionId: echoSessionId }),
    rejectsAsProtocol,
  );
});

test("echo: session.create compares projectId only when the request carried it", async () => {
  const created = await resultClient({ ok: true, data: { sessionId: echoSessionId, projectId: "backend-filled" } })
    .request("session.create", {});
  assert.equal(created.projectId, "backend-filled");
  await assert.rejects(
    resultClient({ ok: true, data: { sessionId: echoSessionId, projectId: "p2" } })
      .request("session.create", { projectId: "p1" }),
    rejectsAsProtocol,
  );
  const same = await resultClient({ ok: true, data: { sessionId: echoSessionId, projectId: "p1" } })
    .request("session.create", { projectId: "p1" });
  assert.equal(same.projectId, "p1");
});

test("echo: session.turn success must carry the requested turnId", async () => {
  const params = { text: "question", turnId: echoTurnId, retry: false };
  await assert.rejects(
    resultClient({ ok: true, data: { sessionId: echoSessionId, turnId: otherTurnId } }).request("session.turn", params),
    rejectsAsProtocol,
  );
});

test("echo: turn failures compare error.details.turnId and require lifecycle details", async () => {
  const lifecycle = { state: "failed", accepted: true, persisted: true };
  const cases = [
    ["session.turn", { text: "question", turnId: echoTurnId, retry: false }],
    ["extensions.apply", { previewId: "preview-1", approvedBindingHashes: [], turnId: echoTurnId, retry: false }],
  ] as const;
  for (const [method, params] of cases) {
    const failure = (details: Record<string, unknown>) => ({
      ok: false,
      error: { code: "PROVIDER_REQUEST_FAILED", message: "The provider request failed.", retryable: true, details },
    });
    await assert.rejects(
      resultClient(failure({ ...lifecycle, turnId: echoTurnId })).request(method, params),
      (error) => error instanceof BackendClientError && error.uiError.source === "business" &&
        error.uiError.turnLifecycle?.turnId === echoTurnId,
      method,
    );
    await assert.rejects(
      resultClient(failure({ ...lifecycle, turnId: otherTurnId })).request(method, params),
      rejectsAsProtocol,
      method,
    );
    await assert.rejects(resultClient(failure({})).request(method, params), rejectsAsProtocol, method);
  }
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

test("snapshot transition on restart generation change captures resume state and resets stale catalog", () => {
  const selected = { projectId: "project-1", sessionId: "123e4567e89b42d3a456426614174000" };
  const transition = planBackendSnapshotTransition({
    currentGeneration: 1,
    catalogGeneration: 1,
    hasProject: true,
    selectedConversation: selected,
    resumeSelection: null,
    draft: "unsent draft",
    resumeDraft: null,
    snapshot: { ...readySnapshot, generation: 2, lifecycle: "ready" },
    completedAction: "restart",
  });

  assert.deepEqual(transition, {
    accepted: true,
    nextGeneration: 2,
    generationChanged: true,
    invalidateOperations: true,
    captureResumeState: true,
    nextResumeSelection: selected,
    nextResumeDraft: "unsent draft",
    clearBindingGeneration: true,
    clearTransientUi: true,
    resetStaleCatalog: true,
    extensionTransition: "interrupt-awaiting-load",
    completedAction: "restart",
  });

  const stale = planBackendSnapshotTransition({
    currentGeneration: 2,
    catalogGeneration: 2,
    hasProject: true,
    selectedConversation: selected,
    resumeSelection: null,
    draft: "",
    resumeDraft: null,
    snapshot: { ...readySnapshot, generation: 1 },
  });
  assert.deepEqual(stale, { accepted: false });
});

test("snapshot transition on crash clears transient UI without dropping current generation catalog", () => {
  const selected = { projectId: "project-1", sessionId: "123e4567e89b42d3a456426614174000" };
  const transition = planBackendSnapshotTransition({
    currentGeneration: 1,
    catalogGeneration: 1,
    hasProject: true,
    selectedConversation: selected,
    resumeSelection: null,
    draft: "in-flight draft",
    resumeDraft: null,
    snapshot: {
      ...readySnapshot,
      generation: 1,
      lifecycle: "crashed",
      childRunning: false,
      lastError: { code: "BACKEND_EXITED", message: "Backend exited.", retryable: true },
    },
  });

  assert.deepEqual(transition, {
    accepted: true,
    nextGeneration: 1,
    generationChanged: false,
    invalidateOperations: false,
    captureResumeState: false,
    nextResumeSelection: null,
    nextResumeDraft: null,
    clearBindingGeneration: false,
    clearTransientUi: true,
    resetStaleCatalog: false,
    extensionTransition: "interrupt",
    completedAction: null,
  });
});
