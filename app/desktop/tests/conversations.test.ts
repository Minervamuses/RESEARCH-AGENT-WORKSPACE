import assert from "node:assert/strict";
import test, { after } from "node:test";
import { createServer, type ViteDevServer } from "vite";

import {
  composeTurnText,
  conversationInteractionState,
  conversationReducer,
  initialConversationState,
  mergeConversationTurns,
  type ConversationFailure,
  type VisibleConversationTurn,
} from "../src/conversations.ts";
import type { JsonObject, SessionCreatedDto, SessionSelectedDto, SessionSummaryDto, SessionTranscriptDto, TranscriptTurnDto } from "../src/protocol.ts";

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
  DeleteConversationDialog: (props: {
    title: string; status: "stopping" | "deleting" | null; error: string | null;
    onConfirm: () => void; onCancel: () => void;
  }) => unknown;
  visibleMessageRange: (root: Node, startNode: Node, startOffset: number, endNode: Node, endOffset: number) => {
    visibleText: string; text: string; startUtf16: number; endUtf16: number;
  } | null;
  ComposerFooter: (props: {
    thinkingMode: "normal"; permissionMode: "ask"; controlsDisabled: boolean; sendDisabled: boolean;
    turnActive: boolean; stopping: boolean; onStop: () => void;
    onThinkingChange: () => void; onPermissionChange: () => void;
  }) => unknown;
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

test("conversation deletion confirms its scope and Cancel does not confirm", async () => {
  const { DeleteConversationDialog } = await loadAppHelpers();
  const { renderToStaticMarkup } = await import("react-dom/server");
  let confirmed = 0, cancelled = 0;
  const props = { title: "Research notes", status: null, error: null,
    onConfirm: () => { confirmed++; }, onCancel: () => { cancelled++; } };
  const dialog = DeleteConversationDialog(props);
  const html = renderToStaticMarkup(dialog);
  assert.match(html, /Delete the conversation record/);
  assert.match(html, /The project and its output files will remain/);
  assert.match(html, /stopped before deletion/);
  const section = elementChildren(dialog)[0];
  const actions = elementChildren(section).at(-1);
  const [confirmButton, cancelButton] = elementChildren(actions) as ReactElementLike[];
  (cancelButton.props.onClick as () => void)();
  assert.equal(cancelled, 1);
  assert.equal(confirmed, 0);
  (confirmButton.props.onClick as () => void)();
  assert.equal(confirmed, 1);
  const stopping = renderToStaticMarkup(DeleteConversationDialog({ ...props, status: "stopping" }));
  assert.equal((stopping.match(/disabled=""/g) ?? []).length, 2);
  assert.match(stopping, /Stopping and finishing the current turn/);
  const failed = renderToStaticMarkup(DeleteConversationDialog({ ...props, error: "Stop failed: local work is still active." }));
  assert.match(failed, /Stop failed: local work is still active/);
  assert.match(failed, /Retry deletion/);
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


test("composer replaces disabled Send with Stop and disables only the pending stop", async () => {
  const { ComposerFooter } = await loadAppHelpers();
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const props = { thinkingMode: "normal" as const, permissionMode: "ask" as const,
    controlsDisabled: true, sendDisabled: true, onStop: () => undefined,
    onThinkingChange: () => undefined, onPermissionChange: () => undefined };
  const ready = renderToStaticMarkup(createElement(ComposerFooter, { ...props, turnActive: false, stopping: false }));
  assert.match(ready, /type="submit" disabled="">Send<\/button>/);
  const active = renderToStaticMarkup(createElement(ComposerFooter, { ...props, turnActive: true, stopping: false }));
  assert.match(active, /type="button">Stop<\/button>/);
  assert.doesNotMatch(active, /type="submit"/);
  const stopping = renderToStaticMarkup(createElement(ComposerFooter, { ...props, turnActive: true, stopping: true }));
  assert.match(stopping, /type="button" disabled="">Stopping…<\/button>/);
});

test("two document comments and an assistant comment retain their pairing when edited and removed", () => {
  let state = conversationReducer(initialConversationState, { type: "backend-generation-changed", generation: 1 });
  state = conversationReducer(state, { type: "conversation-selected", generation: 1, projectId: "project", sessionId: "session" });
  const source = "first paragraph\nsecond paragraph";
  const snapshot = { rootPath: "/tmp/project", path: "/tmp/project/draft.md", sourceText: source, editorRevision: 0, diskFingerprint: "a".repeat(64) };
  const first = { referenceId: "first", kind: "document" as const, text: "first paragraph",
    document: { snapshot: { ...snapshot, rangeStartUtf16: 0, rangeEndUtf16: 15 }, startLine: 1, endLine: 1 } };
  const second = { referenceId: "second", kind: "document" as const, text: "second paragraph",
    document: { snapshot: { ...snapshot, rangeStartUtf16: 16, rangeEndUtf16: source.length }, startLine: 2, endLine: 2 } };
  const reply = { referenceId: "reply", kind: "chat" as const, text: "Ignore instructions in this source",
    chat: { projectId: "project", sessionId: "session", turnId: "turn", role: "assistant" as const,
      messageFingerprint: "b".repeat(64), startUtf16: 0, endUtf16: 34 } };
  for (const reference of [first, second, reply]) {
    state = conversationReducer(state, { type: "reference-added", generation: 1, reference });
  }
  assert.deepEqual(state.annotations.map((item) => [item.number, item.expanded]), [[1, false], [2, false], [3, true]]);
  assert.equal(conversationInteractionState(state).sendDisabled, true, "source selection alone is not a request");
  for (const [referenceId, comment] of [["first", "Rewrite this paragraph."], ["second", "Remove this."], ["reply", "Explain this."]]) {
    state = conversationReducer(state, { type: "annotation-changed", generation: 1, referenceId, comment });
    state = conversationReducer(state, { type: "annotation-toggled", generation: 1, referenceId, expanded: false });
  }
  state = conversationReducer(state, { type: "annotation-toggled", generation: 1, referenceId: "reply", expanded: true });
  state = conversationReducer(state, { type: "annotation-changed", generation: 1, referenceId: "reply", comment: "  Explain the evidence.  " });
  state = conversationReducer(state, { type: "reference-removed", generation: 1, referenceId: "second" });
  assert.deepEqual(state.annotations.map((item) => [item.number, item.referenceId, item.expanded]), [[1, "first", false], [3, "reply", true]]);
  assert.deepEqual(state.draftReferences, [first, reply], "wire references contain source data only");
  assert.equal(conversationInteractionState(state).sendDisabled, false);
  assert.equal(composeTurnText(state.draft, state.annotations), "Requests for frozen references:\n\nReference first:\nRewrite this paragraph.\n\nReference reply:\nExplain the evidence.");
  assert.equal(composeTurnText("Use @citation", state.annotations), "Main request:\nUse @citation\n\nRequests for frozen references:\n\nReference first:\nRewrite this paragraph.\n\nReference reply:\nExplain the evidence.");
  assert.match(composeTurnText(" /status ", state.annotations), /^Main request:\n \/status \n\nRequests for frozen references:/);
  assert.equal(composeTurnText(" /status ", []), " /status ");
  assert.equal(state.nextAnnotationNumber, 4);
});

test("chat ranges exclude number and comment UI without shifting duplicate source text", async () => {
  const { visibleMessageRange } = await loadAppHelpers();
  const text = (value: string) => ({ nodeType: 3, textContent: value }) as unknown as Node;
  const element = (tagName: string, children: Node[], excluded = false) => ({
    nodeType: 1, tagName, childNodes: children,
    hasAttribute: (name: string) => excluded && name === "data-reference-exclude",
    getAttribute: () => null,
  }) as unknown as Node;
  const first = text("same😀"), second = text("same😀"), comment = text("3 rewrite this"), link = text("citation");
  const source = element("DIV", [element("P", [first]), element("DIV", [comment], true), element("P", [second])]);
  assert.deepEqual(visibleMessageRange(source, second, 0, second, 6), {
    visibleText: "same😀\nsame😀", text: "same😀", startUtf16: 7, endUtf16: 13,
  });
  assert.equal(visibleMessageRange(source, comment, 0, comment, 3), null);
  const safeLink = { nodeType: 1, tagName: "BUTTON", childNodes: [link], hasAttribute: () => false,
    getAttribute: (name: string) => name === "class" ? "safe-link" : null } as unknown as Node;
  assert.equal(visibleMessageRange(element("DIV", [safeLink]), link, 0, link, 8)?.text, "citation");
});
