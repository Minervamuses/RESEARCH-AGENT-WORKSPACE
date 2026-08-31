import assert from "node:assert/strict";
import test from "node:test";
import { createServer } from "vite";

interface SafeContentModule {
  SafeContent: (props: { content: string; openExternal?: (url: string) => void | Promise<void> }) => unknown;
  safeExternalUrl: (value: string) => string | null;
  openSafeExternalUrl: (value: string, opener: (url: string) => void | Promise<void>) => Promise<boolean>;
}

interface SessionSummary {
  sessionId: string;
  title: string;
  turnCount: number;
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
  sessionCreateParams: (projectId: string) => Record<string, unknown>;
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
  assert.equal(saved.length, 1, "the catalog DTO remains unchanged");
});

test("sidebar rows never duplicate a registered or already-listed conversation", async () => {
  const { sidebarRowsForProject } = await loadAppHelpers();
  const saved: SessionSummary[] = [{
    sessionId: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    title: "Saved research",
    turnCount: 2,
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

test("new conversations delegate the MCP default to the backend", async () => {
  const { sessionCreateParams } = await loadAppHelpers();

  const params = sessionCreateParams("local");

  assert.deepEqual(params, { projectId: "local" });
  assert.equal("loadMcp" in params, false);
});

test("conversation pages preserve membership order and replace duplicate summaries", async () => {
  const { mergeSessionItems } = await loadAppHelpers();
  const session = (sessionId: string, title: string): SessionSummary => ({
    sessionId,
    title,
    turnCount: 1,
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
