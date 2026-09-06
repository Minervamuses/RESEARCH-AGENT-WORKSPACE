import assert from "node:assert/strict";
import test from "node:test";
import { createServer } from "vite";

import type { ConversationFailure } from "../src/conversations.ts";
import type { TranscriptTurnDto } from "../src/protocol.ts";

interface SafeContentModule {
  SafeContent: (props: { content: string; openExternal?: (url: string) => void | Promise<void> }) => unknown;
  safeExternalUrl: (value: string) => string | null;
  openSafeExternalUrl: (value: string, opener: (url: string) => void | Promise<void>) => Promise<boolean>;
}

interface ReactElementLike {
  props: Record<string, unknown>;
}

const LARGE_DYNAMIC_CHILD_COUNT = 140_000;

function elementChildren(element: unknown): unknown[] {
  const children = (element as ReactElementLike).props.children;
  if (children === undefined) return [];
  return Array.isArray(children) ? children : [children];
}

interface SessionSummary {
  sessionId: string;
  title: string;
  turnCount: number;
  createdAt: string | null;
  updatedAt: string | null;
  status: "ready" | "degraded" | "unavailable";
  issue: string | null;
}

interface AppHelpersModule {
  mergeSessionItems: (
    current: readonly SessionSummary[],
    next: readonly SessionSummary[],
  ) => SessionSummary[];
  sidebarRowsForProject: (
    projectId: string,
    sessions: readonly SessionSummary[],
    selected: { projectId: string; sessionId: string } | null,
    selectedRegistered: boolean,
  ) => Array<SessionSummary & { transient: boolean }>;
  reconcilePersistedTurnFailure: (
    failure: ConversationFailure | null,
    operations: {
      begin: () => symbol | null;
      refreshCatalog: () => Promise<void>;
      refreshSelectedSession: () => Promise<void>;
      finish: (operation: symbol) => void;
    },
  ) => Promise<boolean>;
  sessionCreateParams: (projectId: string) => Record<string, unknown>;
  RestoredTurn: (props: { turn: TranscriptTurnDto }) => unknown;
}

async function loadSafeContent(): Promise<SafeContentModule> {
  const server = await createServer({
    configFile: false,
    root: new URL("..", import.meta.url).pathname,
    server: { middlewareMode: true },
    appType: "custom",
  });
  try {
    return await server.ssrLoadModule("/src/SafeContent.tsx") as SafeContentModule;
  } finally {
    await server.close();
  }
}

async function loadAppHelpers(): Promise<AppHelpersModule> {
  const server = await createServer({
    configFile: false,
    root: new URL("..", import.meta.url).pathname,
    server: { middlewareMode: true },
    appType: "custom",
  });
  try {
    return await server.ssrLoadModule("/src/App.tsx") as AppHelpersModule;
  } finally {
    await server.close();
  }
}

test("safe content accepts only credential-free absolute HTTP(S) URLs", async () => {
  const { safeExternalUrl } = await loadSafeContent();
  assert.equal(safeExternalUrl("https://example.com/path?q=1"), "https://example.com/path?q=1");
  assert.equal(safeExternalUrl("http://example.com"), "http://example.com/");
  for (const value of [
    "javascript:alert(1)",
    "data:text/html,hello",
    "file:///tmp/example",
    "//example.com/path",
    "/relative/path",
    "https://user:password@example.com/",
    "not a url",
  ]) {
    assert.equal(safeExternalUrl(value), null, value);
  }
});

test("safe content treats raw HTML and Markdown images as inert text", async () => {
  const { SafeContent } = await loadSafeContent();
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const html = renderToStaticMarkup(
    createElement(SafeContent, { content: '<img src="https://example.com/x.png"> ![alt](https://example.com/x.png)' }),
  );
  assert.doesNotMatch(html, /<img\b/i);
  assert.match(html, /&lt;img/);
  assert.match(html, /!\[alt\]/);
});

test("safe content preserves a large array of inline Markdown children", async () => {
  const { SafeContent } = await loadSafeContent();
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const repetitions = LARGE_DYNAMIC_CHILD_COUNT / 2;
  const html = renderToStaticMarkup(
    createElement(SafeContent, { content: "`x` ".repeat(repetitions) }),
  );

  assert.equal(html.match(/<code>x<\/code>/g)?.length, repetitions);
});

test("safe content preserves a large array of Markdown list items", async () => {
  const { SafeContent } = await loadSafeContent();
  const content = Array.from(
    { length: LARGE_DYNAMIC_CHILD_COUNT },
    (_, index) => `- item ${index}`,
  ).join("\n");
  const [list] = elementChildren(SafeContent({ content }));
  const items = elementChildren(list);
  const [lastInlineContent] = elementChildren(items.at(-1));

  assert.equal(items.length, LARGE_DYNAMIC_CHILD_COUNT);
  assert.equal(
    (lastInlineContent as ReactElementLike).props.value,
    `item ${LARGE_DYNAMIC_CHILD_COUNT - 1}`,
  );
});

test("safe content preserves a large array of Markdown paragraph blocks", async () => {
  const { SafeContent } = await loadSafeContent();
  const content = Array.from(
    { length: LARGE_DYNAMIC_CHILD_COUNT },
    (_, index) => `paragraph ${index}`,
  ).join("\n\n");
  const paragraphs = elementChildren(SafeContent({ content }));
  const [lastInlineContent] = elementChildren(paragraphs.at(-1));

  assert.equal(paragraphs.length, LARGE_DYNAMIC_CHILD_COUNT);
  assert.equal(
    (lastInlineContent as ReactElementLike).props.value,
    `paragraph ${LARGE_DYNAMIC_CHILD_COUNT - 1}`,
  );
});

test("markdown link activation reparses the URL before calling the injected opener", async () => {
  const { SafeContent, openSafeExternalUrl } = await loadSafeContent();
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const rendered = renderToStaticMarkup(
    createElement(SafeContent, { content: "[Docs](https://example.com/docs)" }),
  );
  assert.match(rendered, /<button[^>]*class="safe-link"[^>]*>Docs<\/button>/);
  assert.doesNotMatch(rendered, /\bhref=/);
  const opened: string[] = [];
  assert.equal(
    await openSafeExternalUrl("https://example.com/docs", (url) => opened.push(url)),
    true,
  );
  assert.deepEqual(opened, ["https://example.com/docs"]);
  assert.equal(
    await openSafeExternalUrl("javascript:alert(1)", (url) => opened.push(url)),
    false,
  );
  assert.deepEqual(opened, ["https://example.com/docs"]);
});

test("sidebar rows expose a transient selected conversation without cataloging it", async () => {
  const { sidebarRowsForProject } = await loadAppHelpers();
  const saved: SessionSummary[] = [{
    sessionId: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    title: "Saved research",
    turnCount: 2,
    createdAt: "2026-08-28T09:00:00Z",
    updatedAt: "2026-08-28T10:00:00Z",
    status: "ready",
    issue: null,
  }];
  const rows = sidebarRowsForProject(
    "local",
    saved,
    { projectId: "local", sessionId: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" },
    false,
  );
  assert.deepEqual(rows.map(({ sessionId, transient }) => ({ sessionId, transient })), [
    { sessionId: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", transient: true },
    { sessionId: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", transient: false },
  ]);
  assert.equal(rows[0].createdAt, null);
  assert.equal(saved.length, 1, "the catalog DTO remains unchanged");
});

test("sidebar rows never duplicate a registered or already-listed conversation", async () => {
  const { sidebarRowsForProject } = await loadAppHelpers();
  const saved: SessionSummary[] = [{
    sessionId: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    title: "Saved research",
    turnCount: 2,
    createdAt: "2026-08-28T09:00:00Z",
    updatedAt: null,
    status: "ready",
    issue: null,
  }];
  assert.equal(
    sidebarRowsForProject(
      "local",
      saved,
      { projectId: "local", sessionId: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" },
      false,
    ).length,
    1,
  );
  assert.equal(
    sidebarRowsForProject(
      "local",
      saved,
      { projectId: "local", sessionId: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" },
      true,
    ).length,
    1,
  );
});

test("durable first-turn failure remains selectable after creating another conversation", async () => {
  const {
    RestoredTurn,
    reconcilePersistedTurnFailure,
    sidebarRowsForProject,
  } = await loadAppHelpers();
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const projectId = "local";
  const sessionA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
  const sessionB = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
  const turnId = "123e4567e89b42d3a456426614174001";
  const calls: string[] = [];
  let savedSessions: SessionSummary[] = [];
  let restoredTurn: TranscriptTurnDto | null = null;
  const failure: ConversationFailure = {
    projectId,
    sessionId: sessionA,
    requestId: "123e4567-e89b-42d3-a456-426614174000",
    turnId,
    message: "The provider request failed.",
    retryable: true,
    draftPreserved: true,
    turnLifecycle: { turnId, state: "failed" as const, accepted: true, persisted: true },
  };

  assert.equal(await reconcilePersistedTurnFailure(failure, {
    begin: () => {
      calls.push("begin");
      return Symbol("refresh");
    },
    refreshCatalog: async () => {
      calls.push("catalog");
      savedSessions = [{
        sessionId: sessionA,
        title: "persist before provider",
        turnCount: 1,
        createdAt: "2026-09-06T00:00:00Z",
        updatedAt: "2026-09-06T00:00:01Z",
        status: "ready",
        issue: null,
      }];
    },
    refreshSelectedSession: async () => {
      calls.push("session");
      restoredTurn = {
        turnId,
        turnNumber: 1,
        kind: "conversational",
        state: "failed",
        timestamp: "2026-09-06T00:00:01Z",
        userText: "persist before provider",
        assistantText: null,
        failureCode: "execution_failed",
        failureMessage: "The provider request failed.",
        failureRetryable: true,
        toolActivities: [],
      };
    },
    finish: () => calls.push("finish"),
  }), true);
  assert.deepEqual(calls, ["begin", "catalog", "session", "finish"]);

  const rows = sidebarRowsForProject(
    projectId,
    savedSessions,
    { projectId, sessionId: sessionB },
    false,
  );
  assert.deepEqual(rows.map(({ sessionId, transient }) => ({ sessionId, transient })), [
    { sessionId: sessionB, transient: true },
    { sessionId: sessionA, transient: false },
  ]);
  assert.notEqual(restoredTurn, null);
  const html = renderToStaticMarkup(createElement(RestoredTurn, { turn: restoredTurn! }));
  assert.match(html, /persist before provider/);
  assert.match(html, /Failed · saved locally/);
  assert.doesNotMatch(html, /Assistant · restored/);

  const ignoredCalls: string[] = [];
  assert.equal(await reconcilePersistedTurnFailure({
    ...failure,
    turnLifecycle: { turnId, state: null, accepted: false, persisted: false },
  }, {
    begin: () => {
      ignoredCalls.push("begin");
      return Symbol("unexpected");
    },
    refreshCatalog: async () => { ignoredCalls.push("catalog"); },
    refreshSelectedSession: async () => { ignoredCalls.push("session"); },
    finish: () => ignoredCalls.push("finish"),
  }), false);
  assert.deepEqual(ignoredCalls, []);
});

test("new conversations delegate the MCP default to the backend", async () => {
  const { sessionCreateParams } = await loadAppHelpers();

  const params = sessionCreateParams("local");

  assert.deepEqual(params, { projectId: "local" });
  assert.equal("loadMcp" in params, false);
});

test("restored turns render tools between user and assistant without raw HTML", async () => {
  const { RestoredTurn } = await loadAppHelpers();
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const html = renderToStaticMarkup(createElement(RestoredTurn, {
    turn: {
      turnId: "123e4567e89b42d3a456426614174001",
      turnNumber: 4,
      kind: "conversational",
      state: "completed",
      timestamp: "2026-08-28T00:00:00Z",
      userText: "question",
      assistantText: "final answer",
      failureCode: null,
      failureMessage: null,
      failureRetryable: null,
      toolActivities: [{
        callId: "call-1",
        name: "rag_search",
        arguments: '{"query":"<script>bad()</script>"}',
        result: "bounded result",
        status: "ok",
        promptEligible: true,
      }],
    },
  }));

  const user = html.indexOf("You · restored turn 4");
  const tool = html.indexOf("Tool activity · rag_search · ok · restored context");
  const result = html.indexOf("Tool result · rag_search");
  const assistant = html.indexOf("Assistant · restored");
  assert.ok(user >= 0 && user < tool && tool < result && result < assistant);
  assert.doesNotMatch(html, /<script>/i);
  assert.match(html, /&lt;script&gt;/);
});

test("restored turns render a complete multi-megabyte answer from first marker to last", async () => {
  const { RestoredTurn } = await loadAppHelpers();
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const answer = 'BEGIN 中文🙂\n"quoted"\\path\n<script>unsafe()</script>\n'
    + "界".repeat(750_000)
    + "\nEND";
  const html = renderToStaticMarkup(createElement(RestoredTurn, {
    turn: {
      turnId: "123e4567e89b42d3a456426614174001",
      turnNumber: 1,
      kind: "conversational",
      state: "completed",
      timestamp: "2026-09-05T00:00:00Z",
      userText: "question",
      assistantText: answer,
      failureCode: null,
      failureMessage: null,
      failureRetryable: null,
      toolActivities: [],
    },
  }));

  assert.ok(html.indexOf("BEGIN 中文🙂") < html.lastIndexOf("END"));
  assert.match(html, /quoted/);
  assert.match(html, /\\path/);
  assert.doesNotMatch(html, /<script>/i);
  assert.match(html, /&lt;script&gt;/);
  assert.ok(html.length > answer.length);
});

test("restored transcript renders durable non-completed and display-only states without a fake answer", async () => {
  const { RestoredTurn } = await loadAppHelpers();
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const base = {
    turnId: "123e4567e89b42d3a456426614174001",
    turnNumber: 4,
    kind: "conversational" as const,
    timestamp: "2026-08-28T00:00:00Z",
    userText: "question",
    assistantText: null,
    failureCode: null,
    failureMessage: null,
    failureRetryable: null,
    toolActivities: [],
  };

  const pending = renderToStaticMarkup(createElement(RestoredTurn, {
    turn: { ...base, state: "pending" },
  }));
  assert.match(pending, /pending/i);
  assert.doesNotMatch(pending, /Assistant · restored/);

  const failed = renderToStaticMarkup(createElement(RestoredTurn, {
    turn: {
      ...base,
      state: "failed",
      failureCode: "execution_failed",
      failureMessage: "The turn could not be completed.",
      failureRetryable: true,
    },
  }));
  assert.match(failed, /failed/i);
  assert.match(failed, /The turn could not be completed\./);
  assert.doesNotMatch(failed, /Assistant · restored/);

  const interrupted = renderToStaticMarkup(createElement(RestoredTurn, {
    turn: {
      ...base,
      state: "interrupted",
      failureCode: "interrupted",
      failureMessage: "The previous process stopped before completion.",
      failureRetryable: true,
    },
  }));
  assert.match(interrupted, /interrupted/i);
  assert.doesNotMatch(interrupted, /Assistant · restored/);

  const displayOnly = renderToStaticMarkup(createElement(RestoredTurn, {
    turn: {
      ...base,
      turnId: "223e4567e89b42d3a456426614174001",
      state: "completed",
      kind: "display-only",
      userText: "/help",
      assistantText: "Available commands",
    },
  }));
  assert.match(displayOnly, /display.only/i);
  assert.match(displayOnly, /Available commands/);
});

test("conversation pages preserve membership order and replace duplicate summaries", async () => {
  const { mergeSessionItems } = await loadAppHelpers();
  const session = (sessionId: string, title: string): SessionSummary => ({
    sessionId,
    title,
    turnCount: 1,
    createdAt: null,
    updatedAt: null,
    status: "ready",
    issue: null,
  });
  const first = session("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "A old");
  const second = session("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "B");
  const updatedFirst = session(first.sessionId, "A current");
  const merged = mergeSessionItems([first], [second, updatedFirst]);
  assert.deepEqual(merged.map(({ sessionId, title }) => ({ sessionId, title })), [
    { sessionId: first.sessionId, title: "A current" },
    { sessionId: second.sessionId, title: "B" },
  ]);
});
