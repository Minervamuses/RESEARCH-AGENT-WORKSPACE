import assert from "node:assert/strict";
import test, { after } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer, type ViteDevServer } from "vite";
import { createOutlineTracker, emptyOutlineDocument, parseOutline } from "../src/lib/outline/index.ts";
import {
  INITIAL_SIDEBAR_VIEW_STATE,
  selectSidebarView,
  sidebarStateOnDocumentCleared,
  sidebarStateOnDocumentOpen,
} from "../src/lib/sidebar.ts";

type OutlineViewModule = typeof import("../src/components/OutlineView.tsx");
type ActivityBarModule = typeof import("../src/components/ActivityBar.tsx");
type SidebarModule = typeof import("../src/components/Sidebar.tsx");

let server: Promise<ViteDevServer> | undefined;
function getServer(): Promise<ViteDevServer> {
  server ??= createServer({
    configFile: false,
    root: new URL("..", import.meta.url).pathname,
    server: { middlewareMode: true, hmr: false, ws: false },
    appType: "custom",
  });
  return server;
}
function loadOutlineView(): Promise<OutlineViewModule> {
  return getServer().then((srv) => srv.ssrLoadModule("/src/components/OutlineView.tsx") as Promise<OutlineViewModule>);
}
function loadActivityBar(): Promise<ActivityBarModule> {
  return getServer().then((srv) => srv.ssrLoadModule("/src/components/ActivityBar.tsx") as Promise<ActivityBarModule>);
}
function loadSidebar(): Promise<SidebarModule> {
  return getServer().then((srv) => srv.ssrLoadModule("/src/components/Sidebar.tsx") as Promise<SidebarModule>);
}
after(async () => { await (await server)?.close(); });

test("OutlineView renders nested hierarchy with aria-level, depth indentation and collapses hidden descendants", async () => {
  const { OutlineView } = await loadOutlineView();
  const outline = parseOutline("paper.md", "# Chapter 1\n## Section A\n### Deep Leaf\n# Chapter 2\n");
  const chapter1Id = outline.roots[0].id;

  const expandedHtml = renderToStaticMarkup(createElement(OutlineView, {
    documentPath: "chapters/paper.md",
    outline,
    collapsedIds: new Set<string>(),
    onToggleCollapse: () => {},
    onSelect: () => {},
  }));
  assert.match(expandedHtml, /paper\.md/);
  assert.match(expandedHtml, /role="tree"/);
  assert.match(expandedHtml, /aria-level="1"/);
  assert.match(expandedHtml, /aria-level="2"/);
  assert.match(expandedHtml, /aria-level="3"/);
  assert.match(expandedHtml, /--outline-depth:0/);
  assert.match(expandedHtml, /--outline-depth:1/);
  assert.match(expandedHtml, /--outline-depth:2/);
  assert.match(expandedHtml, /Deep Leaf/);

  const collapsedHtml = renderToStaticMarkup(createElement(OutlineView, {
    documentPath: "chapters/paper.md",
    outline,
    collapsedIds: new Set([chapter1Id]),
    onToggleCollapse: () => {},
    onSelect: () => {},
  }));
  assert.match(collapsedHtml, /Chapter 1/);
  assert.match(collapsedHtml, /Chapter 2/);
  assert.doesNotMatch(collapsedHtml, /Section A/, "collapsed branch must not render child nodes");
  assert.doesNotMatch(collapsedHtml, /Deep Leaf/, "collapsed branch must not render grandchild nodes");
});

test("OutlineView renders empty states and safely escapes HTML special characters in headings", async () => {
  const { OutlineView } = await loadOutlineView();

  const noDocHtml = renderToStaticMarkup(createElement(OutlineView, {
    documentPath: null,
    outline: emptyOutlineDocument(),
    collapsedIds: new Set<string>(),
    onToggleCollapse: () => {},
    onSelect: () => {},
  }));
  assert.match(noDocHtml, /Open a document to see its outline/);

  const noHeadingsHtml = renderToStaticMarkup(createElement(OutlineView, {
    documentPath: "draft.md",
    outline: parseOutline("draft.md", "Just plain paragraph text without headings."),
    collapsedIds: new Set<string>(),
    onToggleCollapse: () => {},
    onSelect: () => {},
  }));
  assert.match(noHeadingsHtml, /No headings found/);

  const xssOutline = parseOutline("xss.md", "# <script>alert(1)</script> & A < B\n");
  const escapedHtml = renderToStaticMarkup(createElement(OutlineView, {
    documentPath: "xss.md",
    outline: xssOutline,
    collapsedIds: new Set<string>(),
    onToggleCollapse: () => {},
    onSelect: () => {},
  }));
  assert.doesNotMatch(escapedHtml, /<script>alert\(1\)<\/script>/, "raw <script> must never be injected");
  assert.match(escapedHtml, /&lt;script&gt;alert\(1\)&lt;\/script&gt; &amp; A &lt; B/);
});

test("sidebar view state machine handles open, reset, active-icon collapse and expand transitions", () => {
  assert.deepEqual(INITIAL_SIDEBAR_VIEW_STATE, { view: "conversations", collapsed: false });

  // Open document switches to outline while keeping expanded.
  const opened = sidebarStateOnDocumentOpen(INITIAL_SIDEBAR_VIEW_STATE);
  assert.deepEqual(opened, { view: "outline", collapsed: false });

  // Clicking the active icon collapses the sidebar; clicking again expands it.
  const collapsed = selectSidebarView(opened, "outline");
  assert.deepEqual(collapsed, { view: "outline", collapsed: true });
  assert.deepEqual(selectSidebarView(collapsed, "outline"), { view: "outline", collapsed: false });

  // Clicking the other icon while collapsed switches and expands.
  const switchedExpanded = selectSidebarView(collapsed, "conversations");
  assert.deepEqual(switchedExpanded, { view: "conversations", collapsed: false });

  // Opening a document while collapsed switches view to outline but keeps sidebar collapsed (A4).
  const collapsedConv = selectSidebarView(switchedExpanded, "conversations");
  assert.deepEqual(collapsedConv, { view: "conversations", collapsed: true });
  assert.deepEqual(sidebarStateOnDocumentOpen(collapsedConv), { view: "outline", collapsed: true });

  // Clearing the document returns view to conversations (A5).
  assert.deepEqual(sidebarStateOnDocumentCleared(opened), { view: "conversations", collapsed: false });
  assert.deepEqual(sidebarStateOnDocumentCleared({ view: "outline", collapsed: true }), { view: "conversations", collapsed: true });
});

test("ActivityBar and Sidebar SSR preserve brand, backend controls, conversation view and ARIA state", async () => {
  const { ActivityBar } = await loadActivityBar();
  const { Sidebar } = await loadSidebar();
  const { OutlineView } = await loadOutlineView();

  const barExpanded = renderToStaticMarkup(createElement(ActivityBar, {
    view: "conversations",
    collapsed: false,
    onSelectView: () => {},
  }));
  assert.match(barExpanded, /aria-label="Conversations"[^>]*aria-pressed="true"[^>]*aria-expanded="true"/);
  assert.match(barExpanded, /aria-label="Outline"[^>]*aria-pressed="false"[^>]*aria-expanded="false"/);

  const barCollapsed = renderToStaticMarkup(createElement(ActivityBar, {
    view: "outline",
    collapsed: true,
    inert: true,
    onSelectView: () => {},
  }));
  assert.match(barCollapsed, /\binert\b/);
  assert.match(barCollapsed, /aria-label="Outline"[^>]*aria-pressed="false"[^>]*aria-expanded="false"/);
  assert.match(barCollapsed, /is-selected-collapsed/);

  const baseSidebarProps = {
    inert: false,
    phase: "backend-ready" as const,
    snapshot: null,
    hasError: false,
    project: null,
    list: null,
    selected: null,
    selectedSaved: false,
    historyLoaded: false,
    newConversationDisabled: false,
    chooserDisabled: false,
    selectionDisabled: false,
    canStart: false,
    canRestart: true,
    canShutdown: true,
    onCreateConversation: () => {},
    onShowChooser: () => {},
    onSelectConversation: () => {},
    onLoadMore: () => {},
    onOpenMenu: () => {},
    onLifecycle: () => {},
  };

  const convHtml = renderToStaticMarkup(createElement(Sidebar, { ...baseSidebarProps, view: "conversations" }));
  assert.match(convHtml, /Research Agent/);
  assert.match(convHtml, /New conversation/);
  assert.match(convHtml, /Open project/);
  assert.match(convHtml, /Start/);
  assert.match(convHtml, /Restart/);
  assert.match(convHtml, /Shut down/);

  const outlineHtml = renderToStaticMarkup(createElement(Sidebar, {
    ...baseSidebarProps,
    view: "outline",
    outlineContent: createElement(OutlineView, {
      documentPath: "thesis.md",
      outline: parseOutline("thesis.md", "# Chapter 1\n"),
      collapsedIds: new Set<string>(),
      onToggleCollapse: () => {},
      onSelect: () => {},
    }),
  }));
  assert.match(outlineHtml, /Research Agent/, "brand stays visible in outline view");
  assert.match(outlineHtml, /Chapter 1/, "outline content renders in middle section");
  assert.match(outlineHtml, /Start/);
  assert.match(outlineHtml, /Restart/);
  assert.match(outlineHtml, /Shut down/);
  assert.doesNotMatch(outlineHtml, /New conversation/, "conversation list is hidden while outline view is active");
});

test("OutlineView SSR reflects tracker active item and collapsed-ancestor highlight classes", async () => {
  const { OutlineView } = await loadOutlineView();
  const outline = parseOutline("paper.md", "# Chapter 1\n## Section A\n### Leaf\n# Chapter 2\n");
  const [ch1, secA, leaf] = outline.flat;
  const tracker = createOutlineTracker(outline);
  tracker.reportCursorLine(leaf.lineNumber);

  const expandedHtml = renderToStaticMarkup(createElement(OutlineView, {
    documentPath: "paper.md",
    outline,
    collapsedIds: new Set<string>(),
    tracker,
    onToggleCollapse: () => {},
    onSelect: () => {},
  }));
  assert.match(expandedHtml, /aria-current="location"[^>]*data-outline-id="[^"]*leaf/i);
  assert.match(expandedHtml, /outline-row is-active/);
  assert.doesNotMatch(expandedHtml, /is-active-ancestor/);

  const collapsedHtml = renderToStaticMarkup(createElement(OutlineView, {
    documentPath: "paper.md",
    outline,
    collapsedIds: new Set<string>([secA.id]),
    tracker,
    onToggleCollapse: () => {},
    onSelect: () => {},
  }));
  assert.match(collapsedHtml, /outline-row is-active-ancestor/);
  assert.doesNotMatch(collapsedHtml, /outline-row is-active(?=["\s])/);
  assert.doesNotMatch(collapsedHtml, /aria-current="location"/);
  assert.doesNotMatch(collapsedHtml, />Leaf</);
  assert.match(collapsedHtml, new RegExp(ch1.title));
});

test("OutlineView SSR enforces roving tabindex with exactly one tabIndex=0 and valid tree ARIA attributes", async () => {
  const { OutlineView } = await loadOutlineView();
  const outline = parseOutline("paper.md", "# Chapter 1\n## Section A\n### Leaf\n# Chapter 2\n");
  const [, secA] = outline.flat;

  const html = renderToStaticMarkup(createElement(OutlineView, {
    documentPath: "paper.md",
    outline,
    collapsedIds: new Set<string>([secA.id]),
    onToggleCollapse: () => {},
    onSelect: () => {},
  }));

  const tabZeroMatches = html.match(/tabindex="0"/gi) ?? [];
  assert.equal(tabZeroMatches.length, 1, "roving tabindex must expose exactly one tabIndex=0 element in the tree");
  assert.match(html, /role="tree"/);
  assert.match(html, /role="treeitem"[^>]*aria-level="1"[^>]*aria-expanded="true"/);
  assert.match(html, /role="treeitem"[^>]*aria-level="2"[^>]*aria-expanded="false"/);
  assert.match(html, /class="outline-toggle[^"]*"[^>]*tabindex="-1"|tabindex="-1"[^>]*class="outline-toggle/i);
});
