// The api is the one place that checks result echoes (U1). A fake backend
// answers each request with a canned result, so these tests need no transport.
import assert from "node:assert/strict";
import test from "node:test";

import { createApi, type ApiBackend } from "../src/api.ts";
import { BackendClientError } from "../src/backend.ts";
import type { JsonObject } from "../src/protocol.ts";

const requestId = "123e4567-e89b-42d3-a456-426614174000";
const turnId = "123e4567e89b42d3a456426614174001";
const otherTurnId = "123e4567e89b42d3a456426614174009";
const sessionId = "28b222e0cc6543aa8d7bbdc423de99a7";
const otherSessionId = "38b222e0cc6543aa8d7bbdc423de99a7";
const documentContext = {
  rootPath: "/project",
  path: "/project/draft.md",
  editorRevision: 1,
  sourceText: "text",
  diskFingerprint: "a".repeat(64),
};

/** An api whose backend returns `data` for every request and records what was sent. */
function apiReturning(data: JsonObject) {
  const sent: Array<{ method: string; params: JsonObject }> = [];
  const backend: ApiBackend = {
    requestTracked: (method, params) => {
      sent.push({ method, params });
      return { requestId, result: Promise.resolve(data) };
    },
    initialize: () => assert.fail("no lifecycle call expected"),
    start: () => assert.fail("no lifecycle call expected"),
    restart: () => assert.fail("no lifecycle call expected"),
    shutdown: () => assert.fail("no lifecycle call expected"),
  };
  const nativeCalls: Array<{ command: string; args?: Record<string, unknown> }> = [];
  const api = createApi(backend, async <T>(command: string, args?: Record<string, unknown>) => {
    nativeCalls.push({ command, args });
    return "/picked" as T;
  });
  return { api, sent, nativeCalls };
}

function rejectsAsProtocol(message: string) {
  return (error: unknown) =>
    error instanceof BackendClientError && error.uiError.source === "protocol" &&
    error.uiError.code === "BACKEND_UNAVAILABLE" && error.message === message;
}

test("a matching result is accepted and sent with its method and params", async () => {
  const data = { projectId: "p1", sessionId, title: "New title" };
  const { api, sent } = apiReturning(data);
  const renamed = await api.sessionRename({ projectId: "p1", sessionId, title: "New title" });
  assert.deepEqual(renamed, data);
  assert.deepEqual(sent, [{ method: "session.rename", params: { projectId: "p1", sessionId, title: "New title" } }]);
});

test("a result echoing another session or project is rejected as a protocol error", async () => {
  await assert.rejects(
    apiReturning({ projectId: "p1", sessionId: otherSessionId, title: "t" })
      .api.sessionRename({ projectId: "p1", sessionId, title: "t" }),
    rejectsAsProtocol("data.sessionId must match params.sessionId"),
  );
  await assert.rejects(
    apiReturning({ projectId: "p2", sessionId }).api.sessionSelect({ projectId: "p1", sessionId }),
    rejectsAsProtocol("data.projectId must match params.projectId"),
  );
  await assert.rejects(
    apiReturning({ projectId: "p2", sessionId, items: [] }).api.sessionTranscript({ projectId: "p1", sessionId }),
    rejectsAsProtocol("data.projectId must match params.projectId"),
  );
  await assert.rejects(
    apiReturning({ projectId: "p2", items: [] }).api.sessionList({ projectId: "p1", offset: 0, limit: 50 }),
    rejectsAsProtocol("data.projectId must match params.projectId"),
  );
});

test("session.stop compares the session and turn; session.turn compares the turn", async () => {
  const params = { sessionId, turnId, parentRequestId: requestId };
  const stopped = { sessionId, turnId, state: null, accepted: false, persisted: false };
  assert.equal((await apiReturning(stopped).api.sessionStop(params)).turnId, turnId);
  await assert.rejects(apiReturning({ ...stopped, turnId: otherTurnId }).api.sessionStop(params), rejectsAsProtocol("data.turnId must match params.turnId"));
  await assert.rejects(apiReturning({ ...stopped, sessionId: otherSessionId }).api.sessionStop(params), rejectsAsProtocol("data.sessionId must match params.sessionId"));
  await assert.rejects(
    apiReturning({ sessionId, turnId: otherTurnId }).api.sessionTurnTracked({ text: "q", turnId, retry: false }).result,
    rejectsAsProtocol("data.turnId must match params.turnId"),
  );
});

test("session.create compares projectId only when the request carried it", async () => {
  const created = await apiReturning({ sessionId, projectId: "backend-filled" }).api.sessionCreate({});
  assert.equal(created.projectId, "backend-filled");
  await assert.rejects(
    apiReturning({ sessionId, projectId: "p2" }).api.sessionCreate({ projectId: "p1" }),
    rejectsAsProtocol("data.projectId must match params.projectId"),
  );
  assert.equal((await apiReturning({ sessionId, projectId: "p1" }).api.sessionCreate({ projectId: "p1" })).projectId, "p1");
});

test("document.apply and approval.resolve accept success results without turnId", async () => {
  const applied = await apiReturning({ path: "/project/draft.md", status: "saved" })
    .api.documentApplyTracked({ documentContext, turnId, callId: "call-1" }).result;
  assert.equal(applied.status, "saved");
  const resolved = await apiReturning({ approvalId: "approval-1", approved: true })
    .api.approvalResolve({ approvalId: "approval-1", approved: true, turnId });
  assert.equal(resolved.approved, true);
});

test("extensions.apply compares the turn only", async () => {
  const params = { previewId: "preview-1", approvedBindingHashes: [], turnId, retry: false };
  await assert.rejects(
    apiReturning({ sessionId, turnId: otherTurnId }).api.extensionsApply(params),
    rejectsAsProtocol("data.turnId must match params.turnId"),
  );
});

test("method-specific checks: page offset, deleted status and resolved approval", async () => {
  const page = { projectId: "p1", status: "ready", issue: null, items: [], total: 0, limit: 50, hasMore: false };
  assert.equal((await apiReturning({ ...page, offset: 50 }).api.sessionList({ projectId: "p1", offset: 50, limit: 50 })).offset, 50);
  await assert.rejects(
    apiReturning({ ...page, offset: 0 }).api.sessionList({ projectId: "p1", offset: 50, limit: 50 }),
    rejectsAsProtocol("The backend returned a mismatched conversation page."),
  );
  // Without a requested offset there is nothing to compare.
  assert.equal((await apiReturning({ ...page, offset: 0 }).api.sessionList({ projectId: "p1" })).offset, 0);

  const target = { projectId: "p1", sessionId };
  assert.equal((await apiReturning({ ...target, status: "deleted" }).api.sessionDelete(target)).status, "deleted");
  await assert.rejects(
    apiReturning({ ...target, status: "missing" }).api.sessionDelete(target),
    rejectsAsProtocol("The backend deleted a different conversation."),
  );

  await assert.rejects(
    apiReturning({ approvalId: "approval-2", approved: true }).api.approvalResolve({ approvalId: "approval-1", approved: true }),
    rejectsAsProtocol("The backend resolved a different approval request."),
  );
});

test("session.set_thinking has no result schema but still returns the session summary", async () => {
  const summary = { sessionId, turnCount: 0 };
  const { api, sent } = apiReturning(summary);
  assert.deepEqual(await api.sessionSetThinking({ mode: "extended" }), summary);
  assert.deepEqual(sent, [{ method: "session.set_thinking", params: { mode: "extended" } }]);
});

test("native pickers are invoked with their command names", async () => {
  const { api, nativeCalls } = apiReturning({});
  assert.equal(await api.pickProject("/start"), "/picked");
  assert.equal(await api.pickDocument("/project"), "/picked");
  assert.deepEqual(nativeCalls, [
    { command: "pick_project", args: { initialPath: "/start" } },
    { command: "pick_document", args: { rootPath: "/project" } },
  ]);
});
