import assert from "node:assert/strict";
import test, { after } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer, type ViteDevServer } from "vite";
import { emptyOutlineDocument, parseOutline } from "../src/lib/outline/index.ts";

type OutlineViewModule = typeof import("../src/components/OutlineView.tsx");

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
after(async () => { await (await server)?.close(); });

test("OutlineView renders nested hierarchy with aria-level, depth indentation and collapses hidden descendants", async () => {
  const { OutlineView } = await loadOutlineView();
  const outline = parseOutline("paper.md", "# Chapter 1\n## Section A\n### Deep Leaf\n# Chapter 2\n");
  const chapter1Id = outline.roots[0].id;

  const expandedHtml = renderToStaticMarkup(createElement(OutlineView, {
    documentPath: "chapters/paper.md",
    outline,
    collapsedIds: new Set(),
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
    collapsedIds: new Set(),
    onToggleCollapse: () => {},
    onSelect: () => {},
  }));
  assert.match(noDocHtml, /Open a document to see its outline/);

  const noHeadingsHtml = renderToStaticMarkup(createElement(OutlineView, {
    documentPath: "draft.md",
    outline: parseOutline("draft.md", "Just plain paragraph text without headings."),
    collapsedIds: new Set(),
    onToggleCollapse: () => {},
    onSelect: () => {},
  }));
  assert.match(noHeadingsHtml, /No headings found/);

  const xssOutline = parseOutline("xss.md", "# <script>alert(1)</script> & A < B\n");
  const escapedHtml = renderToStaticMarkup(createElement(OutlineView, {
    documentPath: "xss.md",
    outline: xssOutline,
    collapsedIds: new Set(),
    onToggleCollapse: () => {},
    onSelect: () => {},
  }));
  assert.doesNotMatch(escapedHtml, /<script>alert\(1\)<\/script>/, "raw <script> must never be injected");
  assert.match(escapedHtml, /&lt;script&gt;alert\(1\)&lt;\/script&gt; &amp; A &lt; B/);
});
