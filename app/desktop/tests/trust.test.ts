import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

import type {
  ApprovalRequiredDto,
  ExtensionApplyDto,
  ExtensionPreviewDto,
} from "../src/protocol.ts";

interface ApprovalOwners {
  turnRequestId: string | null;
  documentRequestId: string | null;
  citationRequestId: string | null;
}

interface TrustModule {
  approvalHasLiveOwner: (parentRequestId: string, owners: ApprovalOwners) => boolean;
  ApprovalDialog: (props: {
    approval: ApprovalRequiredDto;
    resolving: boolean;
    onResolve: (approved: boolean) => void;
    returnFocus: () => void;
    allowDocumentEditing?: boolean;
    onStop?: () => void;
    stopping?: boolean;
    stopError?: string;
  }) => unknown;
  acceptApprovalEvent: (
    generation: number,
    requestId: string,
    activeRequestId: string | null,
    data: ApprovalRequiredDto,
    now?: number,
  ) => unknown;
  approvedBindingHashes: (flow: unknown) => string[] | null;
  beginExtensionApply: (flow: unknown, turnId: string) => unknown;
  beginExtensionApplyRecovery: (flow: unknown) => unknown;
  extensionApplyRequest: (flow: unknown) => unknown;
  failExtensionApply: (flow: unknown, message: string, lifecycle?: unknown) => unknown;
  interruptExtensionFlow: (flow: unknown) => unknown;
  createExtensionFlow: (turnId: string) => unknown;
  decideExtensionBinding: (
    flow: unknown,
    bindingHash: string,
    decision: "approve" | "deny",
  ) => unknown;
  markExtensionAwaitingLoad: (flow: unknown) => unknown;
  markExtensionRestarting: (flow: unknown) => unknown;
  observeExtensionRevision: (flow: unknown, revision: number) => unknown;
  receiveExtensionApply: (flow: unknown, report: ExtensionApplyDto) => unknown;
  receiveExtensionPreview: (flow: unknown, preview: ExtensionPreviewDto) => unknown;
  ExtensionPanel: (props: {
    flow: unknown; busy: boolean; canRestart: boolean; permissionMode?: "ask" | "bypass";
    onPreview: () => void; onDecision: () => void; onApply: () => void; onRestart: () => void;
  }) => unknown;
  PermissionControl?: (props: {
    mode: "ask" | "bypass";
    disabled: boolean;
    onChange: (mode: "ask" | "bypass") => void;
  }) => unknown;
  reconcilePermissionAck?: (
    generation: number,
    activeGeneration: number,
    selectedSessionId: string,
    ack: { sessionId: string; permissionMode: "ask" | "bypass" },
  ) => ("ask" | "bypass") | null;
}

async function loadTrust(): Promise<TrustModule> {
  const server = await createServer({
    configFile: false,
    root: new URL("..", import.meta.url).pathname,
    server: { middlewareMode: true, hmr: false },
    appType: "custom",
  });
  try {
    return await server.ssrLoadModule("/src/trust.tsx") as TrustModule;
  } finally {
    await server.close();
  }
}

const preview: ExtensionPreviewDto = {
  previewId: "preview-1",
  summary: "Two exact bindings.",
  proposedSkills: ["writer"],
  bindings: [
    {
      name: "clock",
      server: "clock",
      bindingHash: "a".repeat(64),
      requiresApproval: true,
      command: "/conda/envs/app/bin/python",
      arguments: ["server.py"],
      workingDirectory: "/tmp/extensions/clock",
      environmentNames: ["CLOCK_MODE"],
    },
    {
      name: "search",
      server: "search",
      bindingHash: "b".repeat(64),
      requiresApproval: true,
      command: "/conda/envs/app/bin/python",
      arguments: ["search.py", "--stdio"],
      workingDirectory: "/tmp/extensions/search",
      environmentNames: [],
    },
  ],
};

test("extension apply remains disabled until every exact binding has a decision", async () => {
  const trust = await loadTrust();
  let flow = trust.receiveExtensionPreview(trust.createExtensionFlow("turn-1"), preview);
  assert.equal(trust.approvedBindingHashes(flow), null);

  const unchanged = trust.decideExtensionBinding(flow, "unknown", "approve");
  assert.equal(trust.approvedBindingHashes(unchanged), null);

  flow = trust.decideExtensionBinding(flow, "a".repeat(64), "approve");
  assert.equal(trust.approvedBindingHashes(flow), null);
  flow = trust.decideExtensionBinding(flow, "b".repeat(64), "deny");
  assert.deepEqual(trust.approvedBindingHashes(flow), ["a".repeat(64)]);
});

test("an extension preview with no MCP bindings can apply an empty decision set", async () => {
  const trust = await loadTrust();
  const flow = trust.receiveExtensionPreview(
    trust.createExtensionFlow("turn-2"),
    { ...preview, bindings: [] },
  );
  assert.deepEqual(trust.approvedBindingHashes(flow), []);
});

test("extension apply is one-use and only the exact loaded revision completes restart", async () => {
  const trust = await loadTrust();
  let flow = trust.receiveExtensionPreview(trust.createExtensionFlow("turn-3"), preview);
  flow = trust.decideExtensionBinding(flow, "a".repeat(64), "approve");
  flow = trust.decideExtensionBinding(flow, "b".repeat(64), "deny");
  const applyTurnId = "123e4567e89b42d3a456426614174003";
  flow = trust.beginExtensionApply(flow, applyTurnId);
  assert.equal(trust.approvedBindingHashes(flow), null);
  assert.deepEqual(trust.extensionApplyRequest(flow), {
    previewId: "preview-1",
    approvedBindingHashes: ["a".repeat(64)],
    turnId: applyTurnId,
    retry: false,
  });

  const report: ExtensionApplyDto = {
    sessionId: "123e4567e89b42d3a456426614174000",
    turnId: applyTurnId,
    turnNumber: 2,
    state: "completed",
    accepted: true,
    persisted: true,
    displayInput: "One-shot local action: apply reviewed extension changes [123456789abcdef0]",
    text: "Extension Management applied revision 0 -> 1",
    previousRevision: 0,
    appliedRevision: 1,
    restartRequired: true,
    items: [{ key: "skill:writer", outcome: "added", detail: "Installed." }],
    diagnostics: [],
  };
  flow = trust.receiveExtensionApply(flow, report);
  flow = trust.markExtensionRestarting(flow);
  flow = trust.markExtensionAwaitingLoad(flow);
  assert.equal((flow as { phase: string }).phase, "awaiting-load");
  flow = trust.observeExtensionRevision(flow, 0);
  assert.equal((flow as { phase: string }).phase, "awaiting-load");
  flow = trust.observeExtensionRevision(flow, 1);
  assert.equal((flow as { phase: string }).phase, "loaded");
});

test("backend interruption preserves only an uncertain apply for explicit delivery recovery", async () => {
  const trust = await loadTrust();
  let flow = trust.receiveExtensionPreview(
    trust.createExtensionFlow("turn-4"),
    { ...preview, bindings: [] },
  );
  const applyTurnId = "123e4567e89b42d3a456426614174004";
  flow = trust.beginExtensionApply(flow, applyTurnId);
  flow = trust.interruptExtensionFlow(flow);
  assert.equal((flow as { phase: string }).phase, "error");
  flow = trust.beginExtensionApplyRecovery(flow);
  assert.deepEqual(trust.extensionApplyRequest(flow), {
    previewId: "preview-1",
    approvedBindingHashes: [],
    turnId: applyTurnId,
    retry: true,
  });

  const terminal = trust.failExtensionApply(flow, "Apply was interrupted.", {
    turnId: applyTurnId,
    state: "interrupted",
    accepted: true,
    persisted: true,
  });
  assert.equal(trust.extensionApplyRequest(terminal), null);
  assert.equal(trust.interruptExtensionFlow(terminal), null);
});

test("approval events must correlate to the active request and remain unexpired", async () => {
  const { acceptApprovalEvent } = await loadTrust();
  const data: ApprovalRequiredDto = {
    approvalId: "approval-1",
    parentRequestId: "00000000-0000-4000-8000-000000000401",
    turnId: "turn-1",
    command: "printf safe",
    description: "Return deterministic output.",
    executionTimeoutSeconds: 5,
    createdAt: "2026-08-28T04:00:00.000Z",
    expiresAt: "2026-08-28T04:01:00.000Z",
  };
  const now = Date.parse("2026-08-28T04:00:30.000Z");

  assert.notEqual(
    acceptApprovalEvent(3, data.parentRequestId, data.parentRequestId, data, now),
    null,
  );
  assert.equal(
    acceptApprovalEvent(3, data.parentRequestId, "other-request", data, now),
    null,
  );
  assert.equal(
    acceptApprovalEvent(3, data.parentRequestId, data.parentRequestId, data, Date.parse(data.expiresAt)),
    null,
  );
});

test("Bash approval renders inert context with exactly Deny and Approve actions", async () => {
  const { ApprovalDialog } = await loadTrust();
  const approval: ApprovalRequiredDto = {
    approvalId: "approval-2",
    parentRequestId: "00000000-0000-4000-8000-000000000402",
    turnId: "turn-2",
    command: "printf '<script>inert()</script>'",
    description: "Show <img src=x> as text.",
    executionTimeoutSeconds: 5,
    createdAt: "2026-08-28T04:00:00.000Z",
    expiresAt: "2026-08-28T04:01:00.000Z",
  };
  const html = renderToStaticMarkup(createElement(ApprovalDialog, {
    approval,
    resolving: false,
    onResolve: () => undefined,
    returnFocus: () => undefined,
  }));

  assert.match(html, /role="dialog"/);
  assert.match(html, /aria-modal="true"/);
  assert.equal((html.match(/<button\b/g) ?? []).length, 2);
  assert.match(html, />Deny<\/button>/);
  assert.match(html, />Approve<\/button>/);
  assert.doesNotMatch(html, /<script\b|<img\b/i);
  assert.match(html, /&lt;script&gt;inert\(\)&lt;\/script&gt;/);
});

test("Permission control renders Ask/Bypass with project scope and frozen-turn guidance", async () => {
  const trust = await loadTrust();
  assert.ok(trust.PermissionControl, "PermissionControl component must be exported");

  const askHtml = renderToStaticMarkup(createElement(trust.PermissionControl, {
    mode: "ask",
    disabled: false,
    onChange: () => undefined,
  }));
  assert.match(askHtml, /<select\b/);
  assert.doesNotMatch(askHtml, /disabled/);
  assert.equal((askHtml.match(/<option\b/g) ?? []).length, 2);
  assert.match(askHtml, /value="ask"[^>]*selected/);
  assert.match(askHtml, /aria-label="Permission"/);
  assert.match(askHtml, />Ask<\/option>/);
  assert.match(askHtml, />Bypass<\/option>/);
  assert.match(askHtml, /document edits, Bash, citation saves, indexing, MCP and extensions/);

  const disabledHtml = renderToStaticMarkup(createElement(trust.PermissionControl, {
    mode: "bypass",
    disabled: true,
    onChange: () => undefined,
  }));
  assert.match(disabledHtml, /<select\b[^>]*disabled/);
  assert.match(disabledHtml, /value="bypass"[^>]*selected/);
  assert.match(disabledHtml, /Change the mode after it finishes/);
});

test("Bash permission ACK reconciles only for same-generation and same-session", async () => {
  const { reconcilePermissionAck } = await loadTrust();
  assert.ok(reconcilePermissionAck, "reconcilePermissionAck must be exported");

  assert.equal(
    reconcilePermissionAck(1, 1, "session-1", {
      sessionId: "session-1",
      permissionMode: "bypass",
    }),
    "bypass",
  );

  // Mismatched generation (stale ACK from earlier generation)
  assert.equal(
    reconcilePermissionAck(1, 2, "session-1", {
      sessionId: "session-1",
      permissionMode: "bypass",
    }),
    null,
  );

  // Mismatched session (stale ACK from earlier conversation)
  assert.equal(
    reconcilePermissionAck(1, 1, "session-1", {
      sessionId: "session-2",
      permissionMode: "bypass",
    }),
    null,
  );

  // Invalid enum
  assert.equal(
    reconcilePermissionAck(1, 1, "session-1", {
      sessionId: "session-1",
      permissionMode: "invalid" as unknown as "ask",
    }),
    null,
  );
});


test("generic operation approval shows safe action/target/parameters and leaves source editing reachable", async () => {
  const { ApprovalDialog } = await loadTrust();
  const html = renderToStaticMarkup(createElement(ApprovalDialog, {
    approval: {
      approvalId: "generic-approval", parentRequestId: "00000000-0000-4000-8000-000000000402",
      turnId: "turn-2", operation: "mcp.call", targetPath: "research-server/search",
      parametersSummary: "<script>not executable</script>", description: "Call one loaded MCP tool.",
      createdAt: "2026-08-28T04:00:00.000Z", expiresAt: "2026-08-28T04:01:00.000Z",
    },
    resolving: false, onResolve: () => undefined, returnFocus: () => undefined, allowDocumentEditing: true,
  }));
  assert.match(html, /aria-modal="false"/);
  assert.match(html, /Call MCP tool/);
  assert.match(html, /research-server\/search/);
  assert.match(html, /Parameters/);
  assert.doesNotMatch(html, /<script\b|Execution timeout|Exact command/);
  assert.equal((html.match(/<button\b/g) ?? []).length, 2);
});

test("Bypass extension preview keeps exact targets visible without a second binding-consent step", async () => {
  const trust = await loadTrust();
  const flow = trust.receiveExtensionPreview(trust.createExtensionFlow("turn-bypass"), preview);
  const html = renderToStaticMarkup(createElement(trust.ExtensionPanel, {
    flow, busy: false, canRestart: false, permissionMode: "bypass",
    onPreview: () => undefined, onDecision: () => undefined, onApply: () => undefined, onRestart: () => undefined,
  }));
  assert.doesNotMatch(html, /type="radio"/);
  assert.doesNotMatch(html, /Choose Approve or Deny/);
  assert.match(html, /Command/);
  assert.match(html, /<button[^>]*>Apply changes<\/button>/);
});


test("approval keeps Stop and its failure visible inside the modal", async () => {
  const { ApprovalDialog } = await loadTrust();
  const approval: ApprovalRequiredDto = {
    approvalId: "approval-stop", parentRequestId: "00000000-0000-4000-8000-000000000402",
    turnId: "123e4567e89b42d3a456426614174001", command: "sleep 30", description: "Wait locally.",
    executionTimeoutSeconds: 60, createdAt: "2026-10-18T04:00:00.000Z", expiresAt: "2026-10-18T04:01:00.000Z",
  };
  const props = { approval, resolving: true, onResolve: () => undefined, returnFocus: () => undefined, onStop: () => undefined };
  const pending = renderToStaticMarkup(createElement(ApprovalDialog, { ...props, stopping: true }));
  assert.match(pending, /aria-modal="true"/);
  assert.equal((pending.match(/disabled=""/g) ?? []).length, 3);
  assert.match(pending, />Stopping…<\/button>/);
  const failed = renderToStaticMarkup(createElement(ApprovalDialog, { ...props, stopping: false, stopError: "Stop failed; the turn remains active." }));
  assert.match(failed, /role="alert">Stop failed; the turn remains active\./);
  assert.match(failed, /type="button">Stop<\/button>/);
  assert.equal((failed.match(/disabled=""/g) ?? []).length, 2);
});


test("a pending approval stays while its turn, document or bibliography.add request is in flight", async () => {
  const { approvalHasLiveOwner } = await loadTrust();
  const idle = { turnRequestId: null, documentRequestId: null, citationRequestId: null };
  // Acceptance P1: an idle Verify-and-add approval must not be cleared as stale.
  assert.equal(approvalHasLiveOwner("req-add", { ...idle, citationRequestId: "req-add" }), true);
  assert.equal(approvalHasLiveOwner("req-turn", { ...idle, turnRequestId: "req-turn" }), true);
  assert.equal(approvalHasLiveOwner("req-doc", { ...idle, documentRequestId: "req-doc" }), true);
  assert.equal(approvalHasLiveOwner("req-add", idle), false, "finished add request no longer owns it");
  assert.equal(approvalHasLiveOwner("req-old", {
    turnRequestId: "req-turn", documentRequestId: "req-doc", citationRequestId: "req-add",
  }), false);
});

test("App's stale-approval cleanup counts the bibliography.add request as an owner", async () => {
  const { readFile } = await import("node:fs/promises");
  const app = await readFile(new URL("../src/App.tsx", import.meta.url), "utf8");
  const cleanup = app.slice(app.indexOf("// Drop an approval only when no request that can raise one still owns it"));
  assert.match(cleanup.slice(0, 600), /approvalHasLiveOwner\(pendingApproval\.parentRequestId, \{[\s\S]*citationRequestId: citationRequestRef\.current/);
  assert.equal(app.includes("documentRequestRef.current?.requestId !== pendingApproval.parentRequestId"), false,
    "the old two-owner check must not come back");
  // The listener accepts the add request's approval.required and the request sets the owner ref.
  assert.match(app, /citationRequestRef\.current = tracked\.requestId;/);
  assert.match(app, /if \(citationRequest !== null && message\.requestId === citationRequest\)/);
});
