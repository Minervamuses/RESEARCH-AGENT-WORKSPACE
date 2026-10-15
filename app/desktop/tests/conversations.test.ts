import assert from "node:assert/strict";
import test, { after } from "node:test";
import { createServer, type ViteDevServer } from "vite";

import {
  mergeConversationTurns,
  conversationReducer,
  initialConversationState,
  ownsWorkspaceOperation,
  type WorkspaceOperationOwner,
  nextTurnSubmission,
  type ConversationFailure,
  type VisibleConversationTurn,
} from "../src/conversations.ts";
import type { JsonObject, SessionCreatedDto, SessionSelectedDto, SessionSummaryDto, SessionTranscriptDto, TranscriptTurnDto, Reference, SubmittedContext } from "../src/protocol.ts";

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

// Content-sized collections must reach createElement as one array, never spread
// variadically. Asserting that directly keeps the guard independent of whatever
// argument-count limit the running engine happens to have.
function contentChildren(element: unknown): unknown[] {
  const children = (element as ReactElementLike).props.children;
  assert.ok(Array.isArray(children), "expected an array-valued children collection");
  return children;
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
  ComposerFooter: (props: { thinkingMode: "normal" | "extended"; permissionMode: "ask" | "bypass"; controlsDisabled: boolean; sendDisabled: boolean; onThinkingChange: () => void; onPermissionChange: () => void }) => unknown;
  DocumentHeader: (props: { path: string | null; dirty: boolean; busy: boolean; openDisabled: boolean; saveDisabled: boolean; undoDisabled: boolean; onOpen: () => void; onSave: () => void; onUndo: () => void }) => unknown;
  documentReference: (snapshot: { rootPath: string; path: string; sourceText: string; editorRevision: number; diskFingerprint: string; rangeStartUtf16?: number; rangeEndUtf16?: number }, referenceId: string) => Reference;
  backgroundDocumentContext: (snapshot: unknown) => Record<string, unknown> | undefined;
  checkSubmissionSize: (text: string, context: SubmittedContext | null) => void;
  submittedDocumentSource: (context: SubmittedContext | null, referenceId?: string) => { sourceText: string } | undefined;
  retrySettingsMatch: (context: SubmittedContext | null, permission: "ask" | "bypass", thinking: "normal" | "extended") => boolean;
  visibleMessageRange: (root: unknown, startNode: unknown, startOffset: number, endNode: unknown, endOffset: number) => { visibleText: string; text: string; startUtf16: number; endUtf16: number } | null;
  ReferenceCards: (props: { references: Reference[]; onRemove?: (id: string) => void }) => unknown;
  loadSelectedProjectHistory: (
    projectId: string | null,
    request: (method: string, params: JsonObject) => Promise<JsonObject>,
    isCurrent?: () => boolean,
  ) => Promise<unknown>;
  selectConversationWithPreview: (
    projectId: string,
    summary: SessionSummaryDto,
    callbacks: {
      isCurrent: () => boolean;
      onPreview: (data: SessionTranscriptDto) => void;
      onSelected: (selected: SessionSelectedDto) => void;
    },
    request: (method: string, params: JsonObject) => Promise<JsonObject>,
  ) => Promise<SessionTranscriptDto | null>;
  composerSlashCommands: (
    session: SessionCreatedDto | null,
    selected: { projectId: string; sessionId: string } | null,
    generation: number | undefined,
    owner: { generation: number; projectId: string; sessionId: string } | null,
    interactive: boolean,
  ) => SessionCreatedDto["slashCommands"];
  SlashCommandList: (props: {
    commands: SessionCreatedDto["slashCommands"]; active: number; onSelect: (index: number) => void;
  }) => unknown;
  slashPrefix: (draft: string, start: number, end: number) => string | null;
  filterSlashCommands: (commands: { name: string; description: string }[], prefix: string) => { name: string; description: string }[];
  insertSlashCommand: (draft: string, name: string) => string;
  handleComposerKey: (
    event: { key: string; shiftKey: boolean; isComposing: boolean; preventDefault: () => void },
    menu: { open: boolean; count: number; active: number },
    actions: { select: (index: number) => void; move: (index: number) => void; close: () => void; submit: () => void },
  ) => void;
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
  shouldSubmitComposerKey: (
    key: string,
    shiftKey: boolean,
    isComposing: boolean,
  ) => boolean;
  isPersistedTurnFailure: (failure: ConversationFailure | null) => boolean;
  sessionCreateParams: (projectId: string) => Record<string, unknown>;
  RestoredTurn: (props: { turn: TranscriptTurnDto }) => unknown;
  ConversationTurns: (props: { turns: readonly VisibleConversationTurn[] }) => unknown;
}

// One dev server and one SSR load per module, reused across this file's tests.
let devServer: Promise<ViteDevServer> | undefined;
let safeContentModule: Promise<SafeContentModule> | undefined;
let appHelpersModule: Promise<AppHelpersModule> | undefined;

function ssrLoad<T>(path: string): Promise<T> {
  devServer ??= createServer({
    configFile: false,
    root: new URL("..", import.meta.url).pathname,
    // SSR-only loads need no HMR socket, and binding one collides with sibling test files.
    server: { middlewareMode: true, hmr: false, ws: false },
    appType: "custom",
  });
  return devServer.then((server) => server.ssrLoadModule(path) as Promise<T>);
}

function loadSafeContent(): Promise<SafeContentModule> {
  return (safeContentModule ??= ssrLoad<SafeContentModule>("/src/SafeContent.tsx"));
}

function loadAppHelpers(): Promise<AppHelpersModule> {
  return (appHelpersModule ??= ssrLoad<AppHelpersModule>("/src/App.tsx"));
}

after(async () => {
  if (devServer !== undefined) await (await devServer).close();
});

test("slash menu filters backend names only at a complete command prefix", async () => {
  const { slashPrefix, filterSlashCommands, insertSlashCommand } = await loadAppHelpers();
  const commands = [
    { name: "status", description: "Status" },
    { name: "arbitrary-skill", description: "Custom skill" },
  ];
  assert.equal(slashPrefix("  /STA", 6, 6), "STA");
  assert.deepEqual(filterSlashCommands(commands, ""), commands);
  assert.deepEqual(filterSlashCommands(commands, "STA"), [commands[0]]);
  assert.deepEqual(filterSlashCommands(commands, "arbitrary"), [commands[1]]);
  assert.deepEqual(filterSlashCommands(commands, "unknown"), []);
  for (const draft of ["", "text /sta", "/status ", "/status arg", "/sta\n", "\n/sta"]) {
    assert.equal(slashPrefix(draft, draft.length, draft.length), null, draft);
  }
  assert.equal(slashPrefix("/sta", 2, 2), null);
  assert.equal(slashPrefix("/sta", 0, 4), null);
  assert.equal(insertSlashCommand("  /ar", "arbitrary-skill"), "  /arbitrary-skill ");
});

test("menu Enter selects with zero requests; later Enter submits once", async () => {
  const { handleComposerKey } = await loadAppHelpers();
  let requests = 0;
  let selected = -1;
  let prevented = 0;
  let closed = 0;
  let active = 0;
  const actions = {
    select: (index: number) => { selected = index; },
    move: (index: number) => { active = index; },
    close: () => { closed++; },
    submit: () => { requests++; },
  };
  const event = { key: "Enter", shiftKey: false, isComposing: false, preventDefault: () => { prevented++; } };
  const menu = { open: true, count: 2, active: 0 };
  handleComposerKey({ ...event, isComposing: true }, menu, actions);
  handleComposerKey({ ...event, shiftKey: true }, menu, actions);
  assert.equal(selected, -1);
  assert.equal(requests, 0);
  assert.equal(prevented, 0);
  handleComposerKey(event, menu, actions);
  assert.equal(selected, 0);
  assert.equal(prevented, 1);
  assert.equal(requests, 0);
  handleComposerKey(event, { ...menu, open: false }, actions);
  assert.equal(requests, 1);
  handleComposerKey({ ...event, key: "ArrowUp" }, menu, actions);
  assert.equal(active, 1);
  handleComposerKey({ ...event, key: "ArrowDown" }, { ...menu, active: 1 }, actions);
  assert.equal(active, 0);
  handleComposerKey({ ...event, key: "Escape" }, menu, actions);
  assert.equal(closed, 1);
  const beforeTab = prevented;
  handleComposerKey({ ...event, key: "Tab" }, menu, actions);
  assert.equal(prevented, beforeTab);
  handleComposerKey(event, { ...menu, count: 0 }, actions);
  assert.equal(requests, 2); // An explicit unknown command still reaches the parser.
});

test("catalog requires a verified current session owner after switch or restart", async () => {
  const { composerSlashCommands } = await loadAppHelpers();
  const selected = { projectId: "p1", sessionId: "a" };
  const owner = { ...selected, generation: 1 };
  const session: SessionCreatedDto = {
    ...selected, turnCount: 0, graphRecursionLimit: 64, thinkingMode: "normal",
    bashPermissionMode: "ask", slashCommands: [{ name: "skill-a", description: "A" }],
    loadedSkills: ["unverified-skill"], mcpFamilies: [], startupDiagnostics: [], extensionRevision: 1,
  };
  assert.equal(composerSlashCommands(session, selected, 1, owner, true), session.slashCommands);
  assert.deepEqual(composerSlashCommands(session, selected, 1, null, true), []); // Failed/in-flight selection.
  assert.deepEqual(composerSlashCommands(session, selected, 2, owner, true), []); // Restart, same ID.
  assert.deepEqual(composerSlashCommands(session, { ...selected, sessionId: "b" }, 1, owner, true), []);
  assert.deepEqual(composerSlashCommands(session, { ...selected, projectId: "p2" }, 1, owner, true), []);
  assert.deepEqual(composerSlashCommands(session, selected, 1, owner, false), []); // Busy/not ready.
  assert.deepEqual(composerSlashCommands(null, selected, 1, owner, true), []);
  const fresh = { ...session, slashCommands: [{ name: "new-skill-a", description: "New A" }] };
  assert.equal(composerSlashCommands(fresh, selected, 2, { ...owner, generation: 2 }, true), fresh.slashCommands);
});

test("slash list exposes named options and renders descriptions as text", async () => {
  const { SlashCommandList } = await loadAppHelpers();
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const html = renderToStaticMarkup(createElement(SlashCommandList, {
    commands: [{ name: "arbitrary-skill", description: '<img src="x">' }],
    active: 0, onSelect: () => assert.fail("Rendering must not select"),
  }));
  assert.match(html, /role="listbox" aria-label="Slash commands"/);
  assert.match(html, /id="composer-slash-option-0" role="option" aria-selected="true"/);
  assert.match(html, /\/arbitrary-skill/);
  assert.match(html, /&lt;img/);
  assert.doesNotMatch(html, /<img/);
});

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

test("safe content preserves inline formatting and unmatched delimiters", async () => {
  const { SafeContent } = await loadSafeContent();
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const html = renderToStaticMarkup(
    createElement(SafeContent, {
      content: "before `code` **bold** __strong__ *italic* _emphasis_ after unmatched `",
    }),
  );

  assert.match(
    html,
    /before <code>code<\/code> <strong>bold<\/strong> <strong>strong<\/strong> <em>italic<\/em> <em>emphasis<\/em> after unmatched `/,
  );
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
  const [list] = contentChildren(SafeContent({ content }));
  const items = contentChildren(list);
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
  const paragraphs = contentChildren(SafeContent({ content }));
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

test("composer sends with Enter while preserving Shift+Enter and IME composition", async () => {
  const { shouldSubmitComposerKey } = await loadAppHelpers();

  assert.equal(shouldSubmitComposerKey("Enter", false, false), true);
  assert.equal(shouldSubmitComposerKey("Enter", true, false), false);
  assert.equal(shouldSubmitComposerKey("Enter", false, true), false);
  assert.equal(shouldSubmitComposerKey("a", false, false), false);
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

test("only an accepted and persisted prompt qualifies for a saved-conversation refresh", async () => {
  const { isPersistedTurnFailure } = await loadAppHelpers();
  const turnId = "123e4567e89b42d3a456426614174001";
  const failure: ConversationFailure = {
    projectId: "local",
    sessionId: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    requestId: "123e4567-e89b-42d3-a456-426614174000",
    turnId,
    message: "The provider request failed.",
    retryable: true,
    draftPreserved: true,
    turnLifecycle: { turnId, state: "failed", accepted: true, persisted: true },
  };

  assert.equal(isPersistedTurnFailure(failure), true);
  assert.equal(isPersistedTurnFailure({
    ...failure,
    turnLifecycle: { turnId, state: null, accepted: false, persisted: false },
  }), false);
  assert.equal(isPersistedTurnFailure({ ...failure, turnLifecycle: null }), false);
  assert.equal(isPersistedTurnFailure(null), false);
});

test("an unresolved retry renders one prompt without a stale failure card", async () => {
  const { ConversationTurns } = await loadAppHelpers();
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const sessionId = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
  const turnId = "123e4567e89b42d3a456426614174001";
  const prompt = "retry this saved prompt";

  for (const state of ["failed", "interrupted"] as const) {
    const turns = mergeConversationTurns(
      [{
        sessionId,
        turn: {
          turnId,
          turnNumber: 1,
          kind: "conversational",
          state,
          timestamp: "2026-09-06T00:00:01Z",
          userText: prompt,
          assistantText: null,
          failureCode: state === "failed" ? "execution_failed" : "interrupted",
          failureMessage: `stale ${state} state`,
          failureRetryable: true,
          toolActivities: [],
        },
      }],
      [],
      {
        sessionId,
        turnId,
        userText: prompt,
        activity: [],
      },
    );
    const html = renderToStaticMarkup(createElement(ConversationTurns, { turns }));

    assert.equal(html.match(/retry this saved prompt/g)?.length, 1, state);
    assert.match(html, /You · retrying/, state);
    assert.match(html, /Assistant · working/, state);
    assert.doesNotMatch(html, /Failed · saved locally|Interrupted · saved locally/, state);
  }
});

test("new conversations delegate the MCP default to the backend", async () => {
  const { sessionCreateParams } = await loadAppHelpers();

  const params = sessionCreateParams("local");

  assert.deepEqual(params, { projectId: "local" });
  assert.equal("loadMcp" in params, false);
});

test("restored turns keep tool details lazy between user and assistant", async () => {
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
        get arguments(): string { throw new Error("Collapsed tool arguments must not be rendered"); },
        get result(): string { throw new Error("Collapsed tool result must not be rendered"); },
        status: "ok",
        promptEligible: true,
      }],
    },
  }));

  const user = html.indexOf("You · restored turn 4");
  const tool = html.indexOf("Tool activity · rag_search · ok · restored context");
  const assistant = html.indexOf("Assistant · restored");
  assert.ok(user >= 0 && user < tool && tool < assistant);
  assert.match(html, /<details[^>]*class="tool-activity"[^>]*><summary/);
  assert.doesNotMatch(html, /Tool result · rag_search/);
  assert.doesNotMatch(html, /<details[^>]*open=/);
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

test("citation menu inserts a task and restore displays its saved answer and tool activity", async () => {
  const { filterSlashCommands, insertSlashCommand, RestoredTurn } = await loadAppHelpers();
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const commands = [{ name: "citation", description: "One citation task in normal thinking" }];
  assert.deepEqual(filterSlashCommands(commands, "CIT"), commands);
  assert.equal(insertSlashCommand("/cit", commands[0].name), "/citation ");
  const saved = "已保存並引用來源 [1]。\n\nSources:\n[1] Paper A. DOI: 10.1234/paper-a.";
  const html = renderToStaticMarkup(createElement(RestoredTurn, { turn: {
    turnId: "123e4567e89b42d3a456426614174001", turnNumber: 1,
    kind: "conversational", state: "completed", timestamp: "2026-09-12T00:00:00Z",
    userText: "/citation 保存 Paper A 並引用", assistantText: saved,
    failureCode: null, failureMessage: null, failureRetryable: null,
    toolActivities: [{
      callId: "save-1", name: "citation_workflow", arguments: "save Paper A",
      result: "Saved Paper A", status: "ok", promptEligible: false,
    }],
  } }));
  assert.match(html, /已保存並引用來源 \[1\]/);
  assert.match(html, /10\.1234\/paper-a/);
  assert.match(html, /Tool activity · citation_workflow · ok · display only/);
  assert.ok(html.indexOf("Tool activity · citation_workflow") < html.indexOf("Assistant · restored"));
  assert.doesNotMatch(html, /Tool result · citation_workflow/);
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


function selectionFixture() {
  const summary: SessionSummaryDto = {
    sessionId: "28b222e0cc6543aa8d7bbdc423de99a7",
    title: "Saved conversation", turnCount: 1,
    createdAt: null, updatedAt: null, status: "ready", issue: null,
  };
  const transcript: SessionTranscriptDto = {
    projectId: "local", sessionId: summary.sessionId,
    status: "ready", issue: null, total: 1, offset: 0, limit: 20, hasMore: false,
    items: [{
      turnId: "f2ddf2369f994905afa0b85d8cca79b1", turnNumber: 1,
      kind: "conversational", state: "completed", timestamp: "2026-09-23T00:00:00Z",
      userText: "Saved question", assistantText: "Saved answer",
      failureCode: null, failureMessage: null, failureRetryable: null, toolActivities: [],
    }],
  };
  const selected = { projectId: "local", sessionId: summary.sessionId, turnCount: 1 };
  return { summary, transcript, selected };
}

test("saved messages preview before selection is ready without confirming a session", async () => {
  const { selectConversationWithPreview } = await loadAppHelpers();
  const { summary, transcript, selected } = selectionFixture();
  const selection = Promise.withResolvers<JsonObject>();
  const preview = Promise.withResolvers<SessionTranscriptDto>();
  const confirmed: SessionSelectedDto[] = [];
  const requests: string[] = [];
  const result = selectConversationWithPreview("local", summary, {
    isCurrent: () => true,
    onPreview: preview.resolve,
    onSelected: (session) => confirmed.push(session),
  }, async (method) => {
    requests.push(method);
    return method === "session.select" ? selection.promise : transcript as unknown as JsonObject;
  });
  assert.deepEqual(await preview.promise, transcript);
  assert.deepEqual(requests, ["session.select", "session.transcript"]);
  assert.equal(confirmed.length, 0, "preview must not permit sending to the new session");
  selection.resolve(selected);
  assert.deepEqual(await result, transcript);
  assert.equal(confirmed.length, 1);
  assert.equal(requests.length, 2, "healthy saved turns need no second read");
});

test("selection failure rejects late previews and consumes outstanding read failures", async () => {
  const { selectConversationWithPreview } = await loadAppHelpers();
  const { summary, transcript: saved } = selectionFixture();
  for (const readSucceeds of [true, false]) {
    const selection = Promise.withResolvers<JsonObject>();
    const transcript = Promise.withResolvers<JsonObject>();
    let updates = 0;
    const result = selectConversationWithPreview("local", summary, {
      isCurrent: () => true,
      onPreview: () => { updates += 1; },
      onSelected: () => { updates += 1; },
    }, async (method) => method === "session.select" ? selection.promise : transcript.promise);
    const failure = assert.rejects(result, /selection failed/);
    selection.reject(new Error("selection failed"));
    await failure;
    if (readSucceeds) transcript.resolve(saved as unknown as JsonObject);
    else transcript.reject(new Error("read failed after selection"));
    await new Promise<void>((resolve) => setImmediate(resolve));
    assert.equal(updates, 0);
  }
});

test("a replaced backend generation discards preview and selection responses", async () => {
  const { selectConversationWithPreview } = await loadAppHelpers();
  const { summary, transcript, selected } = selectionFixture();
  const selection = Promise.withResolvers<JsonObject>();
  const read = Promise.withResolvers<JsonObject>();
  let current = true;
  let updates = 0;
  const result = selectConversationWithPreview("local", summary, {
    isCurrent: () => current,
    onPreview: () => { updates += 1; },
    onSelected: () => { updates += 1; },
  }, async (method) => method === "session.select" ? selection.promise : read.promise);
  current = false;
  read.resolve(transcript as unknown as JsonObject);
  selection.resolve(selected);
  assert.equal(await result, null);
  assert.equal(updates, 0);
});

test("pending saved turns are refreshed after selection recovers them", async () => {
  const { selectConversationWithPreview } = await loadAppHelpers();
  const { summary, transcript, selected } = selectionFixture();
  const selection = Promise.withResolvers<JsonObject>();
  const preview = Promise.withResolvers<SessionTranscriptDto>();
  const recovered: SessionTranscriptDto = {
    ...transcript, items: [{ ...transcript.items[0], state: "interrupted",
      failureCode: "interrupted", failureMessage: "Previous turn interrupted.",
      failureRetryable: true, assistantText: null }],
  };
  let reads = 0;
  let confirmed = false;
  const result = selectConversationWithPreview("local", summary, {
    isCurrent: () => true,
    onPreview: preview.resolve,
    onSelected: () => { confirmed = true; },
  }, async (method) => {
    if (method === "session.select") return selection.promise;
    reads += 1;
    if (reads === 1) return {
      ...transcript, items: [{ ...transcript.items[0], state: "pending", assistantText: null }],
    } as unknown as JsonObject;
    assert.equal(confirmed, true, "recovery refresh follows session materialization");
    return recovered as unknown as JsonObject;
  });
  assert.equal((await preview.promise).items[0].state, "pending");
  selection.resolve(selected);
  assert.deepEqual(await result, recovered);
  assert.equal(reads, 2);
});

test("cold startup makes no catalog or conversation requests before a project is opened", async () => {
  const { loadSelectedProjectHistory } = await loadAppHelpers();
  const calls: string[] = [];
  assert.equal(await loadSelectedProjectHistory(null, async (method) => {
    calls.push(method);
    throw new Error("History must not be read");
  }), null);
  assert.deepEqual(calls, []);
});

test("selected project history rejects a foreign catalog before reading conversations", async () => {
  const { loadSelectedProjectHistory } = await loadAppHelpers();
  const calls: string[] = [];
  await assert.rejects(loadSelectedProjectHistory("project-a", async (method) => {
    calls.push(method);
    return { projects: [{ projectId: "project-b" }], selectedProjectId: "project-b", selectedSessionId: null };
  }), /different project/);
  assert.deepEqual(calls, ["project.list"]);
});

test("selected project history requests only its own first conversation page", async () => {
  const { loadSelectedProjectHistory } = await loadAppHelpers();
  const calls: Array<{ method: string; params: JsonObject }> = [];
  const result = await loadSelectedProjectHistory("project-a", async (method, params) => {
    calls.push({ method, params });
    return method === "project.list"
      ? { projects: [{ projectId: "project-a" }], selectedProjectId: "project-a", selectedSessionId: null }
      : { projectId: "project-a", items: [] };
  });
  assert.ok(result);
  assert.deepEqual(calls, [
    { method: "project.list", params: {} },
    { method: "session.list", params: { projectId: "project-a", offset: 0, limit: 50, reconcile: false } },
  ]);
});

test("only a successful project-open action clears the old conversation draft", () => {
  const selected = conversationReducer(initialConversationState, {
    type: "conversation-selected", generation: 0, projectId: "project-a", sessionId: "session-a",
  });
  const drafted = conversationReducer(selected, { type: "draft-changed", draft: "Keep this draft" });
  assert.equal(conversationReducer(drafted, { type: "project-opened", generation: 1 }), drafted);
  const reopenedBackend = conversationReducer(drafted, { type: "backend-generation-changed", generation: 1 });
  assert.equal(reopenedBackend.draft, "Keep this draft");
  const changedProject = conversationReducer(reopenedBackend, { type: "project-opened", generation: 1 });
  assert.equal(changedProject.draft, "");
  assert.equal(changedProject.selected, null);
  assert.equal(changedProject.failure, null);
});

test("an old catalog response after A to B to A cannot launch a conversation read", async () => {
  const { loadSelectedProjectHistory } = await loadAppHelpers();
  const catalog = Promise.withResolvers<JsonObject>();
  const owner = { generation: 4, projectEpoch: 1, token: Symbol("first A catalog") };
  let current: WorkspaceOperationOwner = owner;
  const requests: string[] = [];
  const result = loadSelectedProjectHistory("project-a", async (method) => {
    requests.push(method);
    if (method !== "project.list") throw new Error("Old A must not read the reopened project's sessions");
    return catalog.promise;
  }, () => ownsWorkspaceOperation(owner, current, 4, current.projectEpoch));
  current = { generation: 4, projectEpoch: 3, token: Symbol("reopened A catalog") };
  catalog.resolve({ projects: [{ projectId: "project-a" }], selectedProjectId: "project-a", selectedSessionId: null });
  assert.equal(await result, null);
  assert.deepEqual(requests, ["project.list"]);
});

test("an old same-project selection cannot publish preview or selection after reopen", async () => {
  const { selectConversationWithPreview } = await loadAppHelpers();
  const { summary, transcript, selected } = selectionFixture();
  const selection = Promise.withResolvers<JsonObject>();
  const read = Promise.withResolvers<JsonObject>();
  const owner = { generation: 4, projectEpoch: 1, token: Symbol("first A selection") };
  let current = owner;
  let updates = 0;
  const result = selectConversationWithPreview("local", summary, {
    isCurrent: () => ownsWorkspaceOperation(owner, current, 4, current.projectEpoch),
    onPreview: () => { updates += 1; },
    onSelected: () => { updates += 1; },
  }, async (method) => method === "session.select" ? selection.promise : read.promise);
  current = { generation: 4, projectEpoch: 3, token: Symbol("reopened A selection") };
  read.resolve(transcript as unknown as JsonObject);
  selection.resolve(selected);
  assert.equal(await result, null);
  assert.equal(updates, 0);
});

test("a stale rejection and finally cannot replace an error or clear the new operation", async () => {
  const deferred = Promise.withResolvers<void>();
  const owner = { generation: 4, projectEpoch: 1, token: Symbol("old document save") };
  let current: WorkspaceOperationOwner | null = owner;
  let projectEpoch = 1;
  let notice = "";
  const completion = deferred.promise.catch(() => {
    if (ownsWorkspaceOperation(owner, current, 4, projectEpoch)) notice = "Old save failed";
  }).finally(() => {
    if (ownsWorkspaceOperation(owner, current, 4, projectEpoch)) current = null;
  });
  const next = { generation: 4, projectEpoch: 3, token: Symbol("new document save") };
  current = next;
  projectEpoch = 3;
  notice = "Current project notice";
  deferred.reject(new Error("Old backend rejection"));
  await completion;
  assert.equal(notice, "Current project notice");
  assert.equal(current, next);
  assert.equal(ownsWorkspaceOperation({ ...next, token: Symbol("earlier operation") }, next, 4, 3), false);
  assert.equal(ownsWorkspaceOperation(next, next, 5, 3), false);
});

test("turn results from the first A cannot update a new A epoch with matching IDs", () => {
  const projectId = "project-a", sessionId = "session-a";
  const turnId = "f2ddf2369f994905afa0b85d8cca79b1";
  let state = conversationReducer(initialConversationState, { type: "project-opened", generation: 0, projectEpoch: 1 });
  state = conversationReducer(state, { type: "project-opened", generation: 0, projectEpoch: 2 });
  state = conversationReducer(state, { type: "project-opened", generation: 0, projectEpoch: 3 });
  state = conversationReducer(state, { type: "conversation-selected", generation: 0, projectEpoch: 3, projectId, sessionId });
  state = conversationReducer(state, { type: "draft-changed", draft: "New A draft" });
  state = conversationReducer(state, { type: "turn-started", generation: 0, projectEpoch: 3, projectId, sessionId, requestId: "same-request", turnId });
  assert.ok(state.activeTurn);
  assert.equal(conversationReducer(state, {
    type: "turn-failed", generation: 0, projectEpoch: 1, projectId, sessionId, requestId: "same-request", message: "Old failure", retryable: true,
  }), state);
  assert.equal(conversationReducer(state, {
    type: "turn-succeeded", generation: 0, projectEpoch: 1, projectId, requestId: "same-request",
    result: { sessionId, turnId, turnNumber: 1, state: "completed", accepted: true, persisted: true, text: "Old answer" },
  }), state);
  assert.equal(conversationReducer(state, {
    type: "activity-received", generation: 0, projectEpoch: 1, sessionId, requestId: "same-request",
    activity: { kind: "tool", label: "Old tool", status: null },
  }), state);
  assert.equal(state.draft, "New A draft");
});

function referenceContext(references: Reference[] = []): SubmittedContext {
  return {
    projectId: "project-a", rootPath: "/tmp/project-a", permissionMode: "bypass", requestedThinkingMode: "extended",
    skillReferences: [{ name: "paper", startUtf16: 0, endUtf16: 6 }],
    projectRules: { text: "Project rules", fingerprint: "a".repeat(64) }, references,
  };
}

test("document reference freezes the second duplicate and background omits the current selection", async () => {
  const { documentReference, backgroundDocumentContext } = await loadAppHelpers();
  const sourceText = "﻿Intro\r\nsame😀\r\nsame😀\r\n";
  const start = sourceText.lastIndexOf("same");
  const snapshot = { rootPath: "/tmp/project-a", path: "/tmp/project-a/draft.md", sourceText,
    editorRevision: 7, diskFingerprint: "b".repeat(64), rangeStartUtf16: start, rangeEndUtf16: start + "same😀".length };
  const reference = documentReference(snapshot, "reference-a");
  assert.equal(reference.kind, "document");
  if (reference.kind !== "document") return;
  assert.equal(reference.text, "same😀");
  assert.equal(reference.document.startLine, 3);
  assert.equal(reference.document.endLine, 3);
  snapshot.sourceText = "Changed later";
  snapshot.rangeStartUtf16 = 0;
  assert.equal(reference.document.snapshot.sourceText, sourceText);
  assert.equal(reference.document.snapshot.rangeStartUtf16, start);
  const background = backgroundDocumentContext(reference.document.snapshot)!;
  assert.equal(background.sourceText, sourceText);
  assert.equal(Object.hasOwn(background, "rangeStartUtf16"), false);
  assert.equal(Object.hasOwn(background, "rangeEndUtf16"), false);
});

test("draft references preserve immutable retry context and editing a card starts a new logical turn", async () => {
  const { documentReference, retrySettingsMatch } = await loadAppHelpers();
  const reference = documentReference({ rootPath: "/tmp/project-a", path: "/tmp/project-a/a.md", sourceText: "old😀 text",
    editorRevision: 3, diskFingerprint: "b".repeat(64), rangeStartUtf16: 0, rangeEndUtf16: 5 }, "reference-a");
  const context = referenceContext([reference]);
  let state = conversationReducer(initialConversationState, { type: "conversation-selected", generation: 0, projectId: "project-a", sessionId: "session-a" });
  state = conversationReducer(state, { type: "draft-changed", draft: "@paper Explain" });
  state = conversationReducer(state, { type: "reference-added", reference });
  const turnId = "f2ddf2369f994905afa0b85d8cca79b1";
  state = conversationReducer(state, { type: "turn-started", generation: 0, projectId: "project-a", sessionId: "session-a", requestId: "request-a", turnId, submittedContext: context });
  context.projectRules.text = "New rules later";
  state = conversationReducer(state, { type: "turn-failed", generation: 0, projectId: "project-a", sessionId: "session-a", requestId: "request-a", message: "Temporary failure", retryable: true });
  assert.equal(state.submittedContext?.projectRules.text, "Project rules");
  assert.deepEqual(nextTurnSubmission(state, () => "new-turn"), { turnId, retry: true });
  assert.equal(retrySettingsMatch(state.submittedContext, "ask", "extended"), false);
  assert.equal(retrySettingsMatch(state.submittedContext, "bypass", "normal"), false);
  assert.equal(retrySettingsMatch(state.submittedContext, "bypass", "extended"), true);
  state = conversationReducer(state, { type: "reference-removed", referenceId: "reference-a" });
  assert.deepEqual(nextTurnSubmission(state, () => "new-turn"), { turnId: "new-turn", retry: false });
  assert.equal(state.draftReferences.length, 0);
  assert.equal(state.submittedContext?.references.length, 1);
});

test("history restores frozen references without a source file and restart keeps a references-only draft", async () => {
  const reference: Reference = { referenceId: "chat-a", kind: "chat", text: "Saved visible text", chat: {
    projectId: "project-a", sessionId: "session-a", turnId: "f2ddf2369f994905afa0b85d8cca79b1", role: "assistant",
    messageFingerprint: "c".repeat(64), startUtf16: 4, endUtf16: 22,
  } };
  let state = conversationReducer(initialConversationState, { type: "conversation-selected", generation: 0, projectId: "project-a", sessionId: "session-a" });
  state = conversationReducer(state, { type: "retry-target-restored", generation: 0, projectId: "project-a", sessionId: "session-a",
    turnId: "f2ddf2369f994905afa0b85d8cca79b1", userText: "Explain", state: "failed", message: "Failed", retryable: true, submittedContext: referenceContext([reference]) });
  assert.deepEqual(state.draftReferences, [reference]);
  state = conversationReducer(state, { type: "draft-changed", draft: "" });
  state = conversationReducer(state, { type: "backend-generation-changed", generation: 1 });
  state = conversationReducer(state, { type: "project-opened", generation: 1, projectEpoch: 1, preserveDraft: true });
  assert.deepEqual(state.draftReferences, [reference]);
  assert.equal(state.draft, "");
  state = conversationReducer(state, { type: "project-opened", generation: 1, projectEpoch: 2 });
  assert.deepEqual(state.draftReferences, []);
  assert.equal(state.submittedContext, null);
});

test("visible chat coordinates preserve formatting text, paragraph breaks and UTF16 without labels or controls", async () => {
  const { visibleMessageRange } = await loadAppHelpers();
  const text = (value: string) => ({ nodeType: 3, textContent: value, childNodes: [] });
  const element = (tagName: string, childNodes: unknown[], attributes: Record<string, string> = {}) => ({
    nodeType: 1, tagName, childNodes, hasAttribute: (name: string) => Object.hasOwn(attributes, name),
    getAttribute: (name: string) => attributes[name] ?? null,
  });
  const first = text("First "), strong = text("bold😀"), second = text("Second link");
  const root = element("DIV", [
    element("P", [first, element("STRONG", [strong])]),
    element("P", [element("A", [second])]),
    element("BUTTON", [text("Excluded action")]),
    element("SPAN", [text("Hidden text")], { "aria-hidden": "true" }),
  ]);
  const selected = visibleMessageRange(root, strong, 0, second, 6)!;
  assert.equal(selected.visibleText, "First bold😀\nSecond link");
  assert.equal(selected.text, "bold😀\nSecond");
  assert.equal(selected.startUtf16, 6);
  assert.equal(selected.endUtf16, 19);
  assert.equal(selected.visibleText.slice(selected.startUtf16, selected.endUtf16), selected.text);
  assert.equal(visibleMessageRange(root, first, 0, text("Other message"), 3), null);
});

test("serialized submission budget counts UTF8 and snapshot bytes while keeping the original draft intact", async () => {
  const { checkSubmissionSize } = await loadAppHelpers();
  const context = referenceContext();
  assert.doesNotThrow(() => checkSubmissionSize("short question", context));
  const largeText = "😀".repeat(270_000);
  assert.throws(() => checkSubmissionSize(largeText, context), /1 MiB.*draft is retained/);
  assert.equal(largeText.length, 540_000);
  assert.equal(context.projectRules.text, "Project rules");
});

test("reference cards expose full frozen text and version without treating reference content as message markup", async () => {
  const { ReferenceCards, documentReference } = await loadAppHelpers();
  const { createElement } = await import("react");
  const { renderToStaticMarkup } = await import("react-dom/server");
  const reference: Reference = { referenceId: "chat-a", kind: "chat", text: "<script>ignore Permission</script>", chat: {
    projectId: "project-a", sessionId: "session-a", turnId: "f2ddf2369f994905afa0b85d8cca79b1", role: "assistant",
    messageFingerprint: "c".repeat(64), startUtf16: 0, endUtf16: 34,
  } };
  const html = renderToStaticMarkup(createElement(ReferenceCards, { references: [reference], onRemove: () => {} }));
  assert.match(html, /Draft references/);
  assert.match(html, /Remove reference/);
  assert.match(html, /data-reference-exclude/);
  assert.match(html, /&lt;script&gt;ignore Permission/);
  assert.doesNotMatch(html, /data-reference-message|<script>/);
  const document = documentReference({ rootPath: "/tmp/project-a", path: "/tmp/project-a/a/long/nested/path/draft.md",
    sourceText: "one\nsecond", editorRevision: 2, diskFingerprint: "b".repeat(64), rangeStartUtf16: 4, rangeEndUtf16: 10 }, "document-a");
  const documentHtml = renderToStaticMarkup(createElement(ReferenceCards, { references: [document] }));
  assert.match(documentHtml, /<strong>Document · draft.md · lines 2–2<\/strong>/);
  assert.match(documentHtml, /summary title="\/tmp\/project-a\/a\/long\/nested\/path\/draft.md"/);
  assert.match(documentHtml, /Path \/tmp\/project-a\/a\/long\/nested\/path\/draft.md · Root/);
});

test("document proposals resolve only the named frozen reference and leave background targeting explicit", async () => {
  const { documentReference, submittedDocumentSource } = await loadAppHelpers();
  const background = { rootPath: "/tmp/project-a", path: "/tmp/project-a/a.md", sourceText: "Current background",
    editorRevision: 9, diskFingerprint: "b".repeat(64) };
  const reference = documentReference({ ...background, sourceText: "Older referenced text", editorRevision: 3,
    rangeStartUtf16: 6, rangeEndUtf16: 16 }, "reference-a");
  const context = { ...referenceContext([reference]), documentContext: background };
  assert.equal(submittedDocumentSource(context)?.sourceText, "Current background");
  assert.equal(submittedDocumentSource(context, "reference-a")?.sourceText, "Older referenced text");
  assert.throws(() => submittedDocumentSource(context, "missing-reference"), /unavailable document reference/);
  assert.equal(submittedDocumentSource(null), undefined);
});

test("reference callbacks from the first A or a prior backend cannot change the returned A draft", () => {
  const reference: Reference = { referenceId: "chat-a", kind: "chat", text: "Saved text", chat: {
    projectId: "project-a", sessionId: "session-a", turnId: "f2ddf2369f994905afa0b85d8cca79b1", role: "user",
    messageFingerprint: "c".repeat(64), startUtf16: 0, endUtf16: 10,
  } };
  let state = conversationReducer(initialConversationState, { type: "backend-generation-changed", generation: 4 });
  state = conversationReducer(state, { type: "project-opened", generation: 4, projectEpoch: 1 });
  state = conversationReducer(state, { type: "project-opened", generation: 4, projectEpoch: 2 });
  state = conversationReducer(state, { type: "project-opened", generation: 4, projectEpoch: 3 });
  state = conversationReducer(state, { type: "conversation-selected", generation: 4, projectEpoch: 3, projectId: "project-a", sessionId: "session-a" });
  assert.equal(conversationReducer(state, { type: "reference-added", generation: 4, projectEpoch: 1, reference }), state);
  assert.equal(conversationReducer(state, { type: "reference-added", generation: 3, projectEpoch: 3, reference }), state);
  state = conversationReducer(state, { type: "reference-added", generation: 4, projectEpoch: 3, reference });
  assert.equal(state.draftReferences.length, 1);
  assert.equal(conversationReducer(state, { type: "reference-removed", generation: 4, projectEpoch: 1, referenceId: reference.referenceId }), state);
});

test("document reference line labels count lone CR boundaries with an exclusive range end", async () => {
  const { documentReference } = await loadAppHelpers();
  const sourceText = "first\rsecond\rthird";
  const reference = documentReference({ rootPath: "/tmp/project-a", path: "/tmp/project-a/cr.md", sourceText,
    editorRevision: 1, diskFingerprint: "b".repeat(64), rangeStartUtf16: 6, rangeEndUtf16: 13 }, "reference-cr");
  assert.equal(reference.kind, "document");
  if (reference.kind !== "document") return;
  assert.equal(reference.text, "second\r");
  assert.equal(reference.document.startLine, 2);
  assert.equal(reference.document.endLine, 2);
});

test("compact document header keeps filename, dirty state and guarded file actions without a permanent path input", async () => {
  const { DocumentHeader } = await loadAppHelpers();
  const { createElement } = await import("react");
  const { renderToStaticMarkup } = await import("react-dom/server");
  const html = renderToStaticMarkup(createElement(DocumentHeader, {
    path: "/tmp/project-a/draft.md", dirty: true, busy: false,
    openDisabled: false, saveDisabled: false, undoDisabled: true,
    onOpen: () => {}, onSave: () => {}, onUndo: () => {},
  }));
  assert.match(html, /title="\/tmp\/project-a\/draft.md"/);
  assert.match(html, />draft.md</);
  assert.match(html, /aria-label="Unsaved changes"/);
  assert.match(html, /aria-label="Document actions"/);
  assert.match(html, /Open file…/);
  assert.match(html, /Save <kbd>Ctrl\+S<\/kbd>/);
  assert.match(html, /<button[^>]*disabled[^>]*>Undo last Agent edit/);
  assert.doesNotMatch(html, /<input|Research folder|Source file/);
  const busyHtml = renderToStaticMarkup(createElement(DocumentHeader, {
    path: null, dirty: false, busy: true,
    openDisabled: true, saveDisabled: true, undoDisabled: true,
    onOpen: () => {}, onSave: () => {}, onUndo: () => {},
  }));
  assert.equal((busyHtml.match(/ disabled/g) ?? []).length, 3);
  assert.match(busyHtml, /Working…/);
  assert.doesNotMatch(busyHtml, /Unsaved changes/);
});

test("composer footer exposes current Thinking and Permission beside guarded Send", async () => {
  const { ComposerFooter } = await loadAppHelpers();
  const { createElement } = await import("react");
  const { renderToStaticMarkup } = await import("react-dom/server");
  const html = renderToStaticMarkup(createElement(ComposerFooter, {
    thinkingMode: "extended", permissionMode: "bypass", controlsDisabled: false, sendDisabled: false,
    onThinkingChange: () => {}, onPermissionChange: () => {},
  }));
  assert.match(html, /class="composer-footer"/);
  assert.match(html, /aria-label="Thinking: Extended"[^>]*aria-haspopup="menu"/);
  assert.match(html, /role="menu" aria-label="Thinking mode" hidden/);
  assert.equal((html.match(/role="menuitemradio"/g) ?? []).length, 2);
  assert.match(html, /aria-checked="true"[^>]*>Extended</);
  assert.match(html, /aria-label="Permission"/);
  assert.match(html, /value="bypass"[^>]*selected/);
  assert.match(html, /type="submit">Send</);
  assert.ok(html.indexOf('class="composer-controls"') < html.indexOf('type="submit"'));
  const busyHtml = renderToStaticMarkup(createElement(ComposerFooter, {
    thinkingMode: "normal", permissionMode: "ask", controlsDisabled: true, sendDisabled: true,
    onThinkingChange: () => {}, onPermissionChange: () => {},
  }));
  assert.match(busyHtml, /<button[^>]*disabled[^>]*aria-label="Thinking: Normal"/);
  assert.match(busyHtml, /<select[^>]*disabled/);
  assert.match(busyHtml, /type="submit" disabled[^>]*>Send/);
});
