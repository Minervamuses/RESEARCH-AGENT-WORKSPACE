import assert from "node:assert/strict";
import test, { after } from "node:test";
import { createServer, type ViteDevServer } from "vite";

import {
  composeTurnText,
  conversationInteractionState,
  conversationReducer,
  conversationToRestore,
  initialConversationState,
  mergeConversationTurns,
  type ConversationFailure,
} from "../src/conversations.ts";
import { composerSlashCommands, filterSlashCommands, handleComposerKey, insertSlashCommand, shouldSubmitComposerKey, slashPrefix } from "../src/lib/composer.ts";
import { loadSelectedProjectHistory, mergeSessionItems, projectDisplayName, sidebarRowsForProject } from "../src/lib/sidebar.ts";
import { isPersistedTurnFailure, selectConversationWithPreview, visibleMessageRange } from "../src/lib/transcript.ts";
import { safeExternalUrl, openSafeExternalUrl } from "../src/lib/safeUrl.ts";
import { parseProtocolMessage } from "../src/protocol.ts";
import type { Api } from "../src/api.ts";
import type { JsonObject, SessionCreatedDto, SessionListDto, SessionSelectedDto, SessionSummaryDto, SessionTranscriptDto } from "../src/protocol.ts";

type FakeMethod = "session.list" | "session.select" | "session.transcript";

/** The api functions the sidebar and transcript helpers use, answered by one request-style handler. */
function fakeApi(handler: (method: FakeMethod, params: JsonObject) => Promise<JsonObject>) {
  return {
    sessionList: ((params) => handler("session.list", params) as unknown as Promise<SessionListDto>) as Api["sessionList"],
    sessionSelect: ((params) => handler("session.select", params) as unknown as Promise<SessionSelectedDto>) as Api["sessionSelect"],
    sessionTranscript: ((params) => handler("session.transcript", params) as unknown as Promise<SessionTranscriptDto>) as Api["sessionTranscript"],
  };
}

type SafeContentModule = typeof import("../src/SafeContent.tsx");
type DialogsModule = typeof import("../src/components/ConversationDialogs.tsx");
type TranscriptModule = typeof import("../src/components/Transcript.tsx");
type ComposerModule = typeof import("../src/components/Composer.tsx");

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

// One dev server and one SSR load per module, reused across this file's tests.
let devServer: Promise<ViteDevServer> | undefined;
let safeContentModule: Promise<SafeContentModule> | undefined;
let dialogsModule: Promise<DialogsModule> | undefined;
let transcriptModule: Promise<TranscriptModule> | undefined;
let composerModule: Promise<ComposerModule> | undefined;

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

function loadTranscript(): Promise<TranscriptModule> {
  return (transcriptModule ??= ssrLoad<TranscriptModule>("/src/components/Transcript.tsx"));
}

function loadComposer(): Promise<ComposerModule> {
  return (composerModule ??= ssrLoad<ComposerModule>("/src/components/Composer.tsx"));
}

function loadDialogs(): Promise<DialogsModule> {
  return (dialogsModule ??= ssrLoad<DialogsModule>("/src/components/ConversationDialogs.tsx"));
}

after(async () => {
  if (devServer !== undefined) await (await devServer).close();
});

test("conversation deletion confirms its scope and Cancel does not confirm", async () => {
  const { DeleteConversationDialog } = await loadDialogs();
  const { renderToStaticMarkup } = await import("react-dom/server");
  let confirmed = 0, cancelled = 0;
  const props = { title: "Research notes", status: null, error: null,
    onConfirm: () => { confirmed++; }, onCancel: () => { cancelled++; } };
  const dialog = DeleteConversationDialog(props);
  const html = renderToStaticMarkup(dialog);
  assert.match(html, /Delete the conversation record/);
  assert.match(html, /The project and its output files will remain/);
  assert.match(html, /stopped before deletion/);
  const actions = elementChildren(dialog).at(-1);
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

test("slash menu filters backend names only at a complete command prefix", () => {
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

test("menu Enter selects with zero requests; later Enter submits once", () => {
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

test("catalog requires a verified current session owner after switch or restart", () => {
  const selected = { projectId: "p1", sessionId: "a" };
  const owner = { ...selected, generation: 1 };
  const session: SessionCreatedDto = {
    ...selected, turnCount: 0, graphRecursionLimit: 64, thinkingMode: "normal",
    permissionMode: "ask", slashCommands: [{ name: "skill-a", description: "A" }],
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
  const { SlashCommandList } = await loadComposer();
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

test("safe content accepts only credential-free absolute HTTP(S) URLs", () => {
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

test("content-sized inputs reach the parser and the renderers whole, from first marker to last", async () => {
  // One synthetic-data test for every size-sensitive path: the protocol parser, the restored-turn
  // renderer (a multi-megabyte answer), and SafeContent's inline, list and paragraph collections,
  // which must be passed to createElement as one array instead of being spread as arguments.
  const answer = 'BEGIN 中文🙂\n"quoted"\\path\n<script>unsafe()</script>\n' + "界".repeat(750_000) + "\nEND";
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");

  assert.doesNotThrow(() => parseProtocolMessage({
    protocolVersion: 1,
    messageType: "result",
    requestId: "123e4567-e89b-42d3-a456-426614174000",
    ok: true,
    data: {
      sessionId: "session-a",
      turnId: "123e4567e89b42d3a456426614174000",
      turnNumber: 1,
      state: "completed",
      accepted: true,
      persisted: true,
      text: answer,
      validationErrors: [],
      toolSummaries: [],
      responseKind: "answer",
    },
  }));

  const { RestoredTurn } = await loadTranscript();
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

  const { SafeContent } = await loadSafeContent();
  const repetitions = LARGE_DYNAMIC_CHILD_COUNT / 2;
  const inline = renderToStaticMarkup(createElement(SafeContent, { content: "`x` ".repeat(repetitions) }));
  assert.equal(inline.match(/<code>x<\/code>/g)?.length, repetitions);

  const listContent = Array.from({ length: LARGE_DYNAMIC_CHILD_COUNT }, (_, index) => `- item ${index}`).join("\n");
  const [list] = contentChildren(SafeContent({ content: listContent }));
  const items = contentChildren(list);
  assert.equal(items.length, LARGE_DYNAMIC_CHILD_COUNT);
  assert.equal(
    (elementChildren(items.at(-1))[0] as ReactElementLike).props.value,
    `item ${LARGE_DYNAMIC_CHILD_COUNT - 1}`,
  );

  const paragraphContent = Array.from({ length: LARGE_DYNAMIC_CHILD_COUNT }, (_, index) => `paragraph ${index}`).join("\n\n");
  const paragraphs = contentChildren(SafeContent({ content: paragraphContent }));
  assert.equal(paragraphs.length, LARGE_DYNAMIC_CHILD_COUNT);
  assert.equal(
    (elementChildren(paragraphs.at(-1))[0] as ReactElementLike).props.value,
    `paragraph ${LARGE_DYNAMIC_CHILD_COUNT - 1}`,
  );
});

test("markdown link activation reparses the URL before calling the injected opener", async () => {
  const { SafeContent } = await loadSafeContent();
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const rendered = renderToStaticMarkup(
    createElement(SafeContent, { content: "[Docs](https://example.com/docs)" }),
  );
  assert.match(rendered, /<button[^>]*>Docs<\/button>/);
  assert.doesNotMatch(rendered, /\bhref=/);
  const opened: string[] = [];
  assert.equal(
    await openSafeExternalUrl("https://example.com/docs", (url) => { opened.push(url); }),
    true,
  );
  assert.deepEqual(opened, ["https://example.com/docs"]);
  assert.equal(
    await openSafeExternalUrl("javascript:alert(1)", (url) => { opened.push(url); }),
    false,
  );
  assert.deepEqual(opened, ["https://example.com/docs"]);
});

test("sidebar rows show an unsaved selected conversation without changing the saved list", () => {
  const saved: SessionSummaryDto[] = [{
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
  assert.equal(saved.length, 1, "the saved list DTO remains unchanged");
});

const RESTORE_ITEMS: SessionSummaryDto[] = ["aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"].map((sessionId) => ({
  sessionId, title: `Saved ${sessionId[0]}`, turnCount: 1, createdAt: "2026-08-28T09:00:00Z",
  updatedAt: null, status: "ready", issue: null,
}));

test("restart reselects the conversation that was selected when it is still listed", () => {
  const list = { projectId: "p1", items: RESTORE_ITEMS };
  const resume = { projectId: "p1", sessionId: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" };
  assert.equal(conversationToRestore("p1", list, resume), RESTORE_ITEMS[1]);
});

test("restart selects nothing when the previously selected conversation was deleted", () => {
  const list = { projectId: "p1", items: [RESTORE_ITEMS[0]] };
  const resume = { projectId: "p1", sessionId: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" };
  assert.equal(conversationToRestore("p1", list, resume), null);
});

test("restart selects nothing without a resumable selection for the opened project", () => {
  const list = { projectId: "p1", items: RESTORE_ITEMS };
  assert.equal(conversationToRestore("p1", list, null), null);
  assert.equal(conversationToRestore(null, list, { projectId: "p1", sessionId: RESTORE_ITEMS[0].sessionId }), null);
  assert.equal(conversationToRestore("p1", null, { projectId: "p1", sessionId: RESTORE_ITEMS[0].sessionId }), null);
  // A selection or list left over from another project never restores.
  assert.equal(conversationToRestore("p1", list, { projectId: "p2", sessionId: RESTORE_ITEMS[0].sessionId }), null);
  assert.equal(conversationToRestore("p2", list, { projectId: "p2", sessionId: RESTORE_ITEMS[0].sessionId }), null);
});

test("project history loads with one session.list request for the opened project", async () => {
  const requests: Array<[string, JsonObject]> = [];
  const page = { projectId: "p1", status: "ready", issue: null, items: RESTORE_ITEMS, total: 2, offset: 0, limit: 50, hasMore: false };
  const loaded = await loadSelectedProjectHistory("p1", fakeApi(async (method, params) => {
    requests.push([method, params]);
    return page as unknown as JsonObject;
  }).sessionList);
  assert.deepEqual(requests, [["session.list", { projectId: "p1", offset: 0, limit: 50 }]]);
  assert.equal(loaded, page);
  assert.equal(await loadSelectedProjectHistory(null, fakeApi(async () => assert.fail("no project, no request")).sessionList), null);
  // A result for another project is rejected by the api echo check (tests/api.test.ts).
  assert.equal(await loadSelectedProjectHistory("p1", fakeApi(async () => page as unknown as JsonObject).sessionList, () => false), null);
  assert.equal(projectDisplayName("/home/me/thesis/"), "thesis");
  assert.equal(projectDisplayName("C:\\Users\\me\\thesis"), "thesis");
});

test("composer sends with Enter while preserving Shift+Enter and IME composition", () => {

  assert.equal(shouldSubmitComposerKey("Enter", false, false), true);
  assert.equal(shouldSubmitComposerKey("Enter", true, false), false);
  assert.equal(shouldSubmitComposerKey("Enter", false, true), false);
  assert.equal(shouldSubmitComposerKey("a", false, false), false);
});

test("sidebar rows never duplicate a saved or already-listed conversation", () => {
  const saved: SessionSummaryDto[] = [{
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

test("only an accepted and persisted prompt qualifies for a saved-conversation refresh", () => {
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
  const { ConversationTurns } = await loadTranscript();
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

test("a live turn renders its own cards: a complete answer or a local command, never restored labels", async () => {
  const { ConversationTurns } = await loadTranscript();
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const sessionId = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
  const live = (turnId: string, responseKind: "answer" | "command", userText: string, assistantText: string) =>
    ({ sessionId, turnId, turnNumber: 1, userText, assistantText, responseKind });
  const answer = renderToStaticMarkup(createElement(ConversationTurns, {
    turns: mergeConversationTurns([], [live("123e4567e89b42d3a456426614174001", "answer", "a question", "an <b>answer</b>")]),
  }));
  assert.match(answer, /<p[^>]*>You<\/p>/);
  assert.match(answer, /<p[^>]*>Assistant · complete<\/p>/);
  assert.match(answer, /a question/);
  assert.doesNotMatch(answer, /<b>answer<\/b>|restored|pending/);
  const command = renderToStaticMarkup(createElement(ConversationTurns, {
    turns: mergeConversationTurns([], [live("123e4567e89b42d3a456426614174002", "command", "/help", "Available commands")]),
  }));
  assert.match(command, /<p[^>]*>Local command output · complete<\/p>/);
  assert.doesNotMatch(command, /Assistant/);
});

test("a pending turn renders the prompt, a working card with a spinner and its stage and tool activity", async () => {
  const { ConversationTurns } = await loadTranscript();
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const turns = mergeConversationTurns([], [], {
    sessionId: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", turnId: "123e4567e89b42d3a456426614174003", userText: "still working",
    activity: [{ kind: "stage", label: "Retrieving", status: null }, { kind: "tool", label: "rag_search", status: "running" }],
  });
  const html = renderToStaticMarkup(createElement(ConversationTurns, { turns }));
  assert.equal(html.match(/<article/g)?.length, 1, "one turn group");
  assert.match(html, /<p[^>]*>You · pending<\/p>/);
  assert.match(html, /still working/);
  assert.match(html, /<p[^>]*>Assistant · working<\/p><div[^>]*aria-label="Waiting for answer"/);
  assert.match(html, /<strong>Stage:<\/strong> Retrieving<\/li>/);
  assert.match(html, /<strong>Tool:<\/strong> rag_search · running<\/li>/);
  assert.doesNotMatch(html, /restored|Assistant · complete/);
});

test("restored turns keep tool details lazy between user and assistant", async () => {
  const { RestoredTurn } = await loadTranscript();
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
  assert.match(html, /<details[^>]*><summary/);
  assert.doesNotMatch(html, /Tool result · rag_search/);
  assert.doesNotMatch(html, /<details[^>]*open=/);
});

test("citation menu inserts a task and restore displays its saved answer and tool activity", async () => {
  const { RestoredTurn } = await loadTranscript();
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
  const { RestoredTurn } = await loadTranscript();
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

test("conversation pages preserve membership order and replace duplicate summaries", () => {
  const session = (sessionId: string, title: string): SessionSummaryDto => ({
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
  const { summary, transcript, selected } = selectionFixture();
  const selection = Promise.withResolvers<JsonObject>();
  const preview = Promise.withResolvers<SessionTranscriptDto>();
  const confirmed: SessionSelectedDto[] = [];
  const requests: string[] = [];
  const result = selectConversationWithPreview("local", summary, {
    isCurrent: () => true,
    onPreview: preview.resolve,
    onSelected: (session) => confirmed.push(session),
  }, fakeApi(async (method) => {
    requests.push(method);
    return method === "session.select" ? selection.promise : transcript as unknown as JsonObject;
  }));
  assert.deepEqual(await preview.promise, transcript);
  assert.deepEqual(requests, ["session.select", "session.transcript"]);
  assert.equal(confirmed.length, 0, "preview must not permit sending to the new session");
  selection.resolve(selected);
  assert.deepEqual(await result, transcript);
  assert.equal(confirmed.length, 1);
  assert.equal(requests.length, 2, "healthy saved turns need no second read");
});

test("selection failure rejects late previews and consumes outstanding read failures", async () => {
  const { summary, transcript: saved } = selectionFixture();
  for (const readSucceeds of [true, false]) {
    const selection = Promise.withResolvers<JsonObject>();
    const transcript = Promise.withResolvers<JsonObject>();
    let updates = 0;
    const result = selectConversationWithPreview("local", summary, {
      isCurrent: () => true,
      onPreview: () => { updates += 1; },
      onSelected: () => { updates += 1; },
    }, fakeApi(async (method) => method === "session.select" ? selection.promise : transcript.promise));
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
  const { summary, transcript, selected } = selectionFixture();
  const selection = Promise.withResolvers<JsonObject>();
  const read = Promise.withResolvers<JsonObject>();
  let current = true;
  let updates = 0;
  const result = selectConversationWithPreview("local", summary, {
    isCurrent: () => current,
    onPreview: () => { updates += 1; },
    onSelected: () => { updates += 1; },
  }, fakeApi(async (method) => method === "session.select" ? selection.promise : read.promise));
  current = false;
  read.resolve(transcript as unknown as JsonObject);
  selection.resolve(selected);
  assert.equal(await result, null);
  assert.equal(updates, 0);
});

test("pending saved turns are refreshed after selection recovers them", async () => {
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
  }, fakeApi(async (method) => {
    if (method === "session.select") return selection.promise;
    reads += 1;
    if (reads === 1) return {
      ...transcript, items: [{ ...transcript.items[0], state: "pending", assistantText: null }],
    } as unknown as JsonObject;
    assert.equal(confirmed, true, "recovery refresh follows session materialization");
    return recovered as unknown as JsonObject;
  }));
  assert.equal((await preview.promise).items[0].state, "pending");
  selection.resolve(selected);
  assert.deepEqual(await result, recovered);
  assert.equal(reads, 2);
});


test("composer replaces disabled Send with Stop and disables only the pending stop", async () => {
  const { ComposerFooter } = await loadComposer();
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
  state = conversationReducer(state, { type: "conversation-selected", generation: 1, projectEpoch: 0, projectId: "project", sessionId: "session" });
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
    state = conversationReducer(state, { type: "reference-added", generation: 1, projectEpoch: 0, reference });
  }
  assert.deepEqual(state.annotations.map((item) => [item.number, item.expanded]), [[1, false], [2, false], [3, true]]);
  assert.equal(conversationInteractionState(state).sendDisabled, true, "source selection alone is not a request");
  for (const [referenceId, comment] of [["first", "Rewrite this paragraph."], ["second", "Remove this."], ["reply", "Explain this."]]) {
    state = conversationReducer(state, { type: "annotation-changed", generation: 1, projectEpoch: 0, referenceId, comment });
    state = conversationReducer(state, { type: "annotation-toggled", generation: 1, projectEpoch: 0, referenceId, expanded: false });
  }
  state = conversationReducer(state, { type: "annotation-toggled", generation: 1, projectEpoch: 0, referenceId: "reply", expanded: true });
  state = conversationReducer(state, { type: "annotation-changed", generation: 1, projectEpoch: 0, referenceId: "reply", comment: "  Explain the evidence.  " });
  state = conversationReducer(state, { type: "reference-removed", generation: 1, projectEpoch: 0, referenceId: "second" });
  assert.deepEqual(state.annotations.map((item) => [item.number, item.referenceId, item.expanded]), [[1, "first", false], [3, "reply", true]]);
  assert.deepEqual(state.draftReferences, [first, reply], "wire references contain source data only");
  assert.equal(conversationInteractionState(state).sendDisabled, false);
  assert.equal(composeTurnText(state.draft, state.annotations), "Requests for frozen references:\n\nReference first:\nRewrite this paragraph.\n\nReference reply:\nExplain the evidence.");
  assert.equal(composeTurnText("Use @citation", state.annotations), "Main request:\nUse @citation\n\nRequests for frozen references:\n\nReference first:\nRewrite this paragraph.\n\nReference reply:\nExplain the evidence.");
  assert.match(composeTurnText(" /status ", state.annotations), /^Main request:\n \/status \n\nRequests for frozen references:/);
  assert.equal(composeTurnText(" /status ", []), " /status ");
  const requests = "Requests for frozen references:\n\nReference first:\nRewrite this paragraph.\n\nReference reply:\nExplain the evidence.";
  assert.equal(composeTurnText("/citation 找來源", state.annotations), `/citation Main request:\n找來源\n\n${requests}`);
  assert.equal(composeTurnText("  /CITATION\n找來源 ", state.annotations), `/CITATION Main request:\n找來源\n\n${requests}`);
  assert.equal(composeTurnText("/citation", state.annotations), `/citation ${requests}`);
  for (const draft of ["/citation off", "/citation NONE", " /citation deactivate", "/citationfoo 找來源", "請用 /citation 找來源", "@citation 找來源"]) {
    assert.equal(composeTurnText(draft, state.annotations), `Main request:\n${draft}\n\n${requests}`, draft);
  }
  const commented = state.annotations.map((item) => ({ ...item, comment: "/citation 找來源" }));
  assert.match(composeTurnText("說明這段", commented), /^Main request:\n說明這段\n\nRequests for frozen references:\n\nReference first:\n\/citation 找來源/);
  assert.equal(composeTurnText("/citation 找來源", []), "/citation 找來源");
  assert.equal(state.nextAnnotationNumber, 4);
});

test("chat ranges exclude number and comment UI without shifting duplicate source text", () => {
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
