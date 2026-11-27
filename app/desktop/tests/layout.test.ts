import assert from "node:assert/strict";
import test, { after } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer, type ViteDevServer } from "vite";
import {
  ACTIVITY_BAR_WIDTH,
  clampDocumentRatio,
  clampSidebarWidth,
  clearDocumentRatio,
  clearSidebarWidth,
  computeDraggedDocumentRatio,
  computeDraggedSidebarWidth,
  DOCUMENT_RATIO_KEY,
  documentSplitFrValues,
  MAX_DOCUMENT_RATIO,
  MAX_SIDEBAR_WIDTH,
  MIN_DOCUMENT_RATIO,
  MIN_SIDEBAR_WIDTH,
  MIN_WORKSPACE_PANE_WIDTH,
  readDocumentRatio,
  readSidebarWidth,
  RESIZER_WIDTH,
  resolveLayoutWidths,
  SIDEBAR_WIDTH_KEY,
  writeDocumentRatio,
  writeSidebarWidth,
  type LayoutStorage,
} from "../src/lib/layout.ts";

function memory(initial: Record<string, string> = {}): LayoutStorage & { values: Record<string, string> } {
  const values = { ...initial };
  return {
    values,
    getItem: (key) => values[key] ?? null,
    setItem: (key, value) => { values[key] = value; },
    removeItem: (key) => { delete values[key]; },
  };
}

const broken: LayoutStorage = {
  getItem: () => { throw new Error("SecurityError"); },
  setItem: () => { throw new Error("QuotaExceededError"); },
  removeItem: () => { throw new Error("SecurityError"); },
};

test("sidebar width and document ratio round-trip valid values, reject invalid ones, and reset cleanly", () => {
  const storage = memory();
  assert.equal(readSidebarWidth(storage), null);
  assert.equal(readDocumentRatio(storage), null);
  assert.equal(readSidebarWidth(null), null);
  assert.equal(readDocumentRatio(null), null);

  writeSidebarWidth(280, storage);
  assert.equal(storage.values[SIDEBAR_WIDTH_KEY], "280");
  assert.equal(readSidebarWidth(storage), 280);

  writeDocumentRatio(0.625, storage);
  assert.equal(storage.values[DOCUMENT_RATIO_KEY], "0.625");
  assert.equal(readDocumentRatio(storage), 0.625);

  // Writes clamp out-of-range values to bounds.
  writeSidebarWidth(999, storage);
  assert.equal(readSidebarWidth(storage), MAX_SIDEBAR_WIDTH);
  writeSidebarWidth(50, storage);
  assert.equal(readSidebarWidth(storage), MIN_SIDEBAR_WIDTH);
  writeDocumentRatio(0.95, storage);
  assert.equal(readDocumentRatio(storage), MAX_DOCUMENT_RATIO);
  writeDocumentRatio(0.05, storage);
  assert.equal(readDocumentRatio(storage), MIN_DOCUMENT_RATIO);

  // Clearing returns to CSS default (null).
  clearSidebarWidth(storage);
  clearDocumentRatio(storage);
  assert.equal(readSidebarWidth(storage), null);
  assert.equal(readDocumentRatio(storage), null);

  // Corrupted or out-of-range stored values fall back to default (null).
  for (const invalid of ["159", "421", "abc", "", "200.5", "-200", " 240", "1000"]) {
    assert.equal(readSidebarWidth(memory({ [SIDEBAR_WIDTH_KEY]: invalid })), null, `sidebar: ${invalid}`);
  }
  for (const invalid of ["0.19", "0.81", "1", "1.0", "abc", "", "-0.5", " 0.5", "NaN"]) {
    assert.equal(readDocumentRatio(memory({ [DOCUMENT_RATIO_KEY]: invalid })), null, `ratio: ${invalid}`);
  }
});

test("storage exceptions fall back safely without throwing", () => {
  assert.equal(readSidebarWidth(broken), null);
  assert.equal(readDocumentRatio(broken), null);
  assert.doesNotThrow(() => writeSidebarWidth(240, broken));
  assert.doesNotThrow(() => writeDocumentRatio(0.5, broken));
  assert.doesNotThrow(() => clearSidebarWidth(broken));
  assert.doesNotThrow(() => clearDocumentRatio(broken));
  assert.doesNotThrow(() => clearSidebarWidth(null));
  assert.doesNotThrow(() => clearDocumentRatio(null));
});

test("minimum pane widths and ratio clamping stay bounded across workspace sizes", () => {
  assert.equal(clampSidebarWidth(100), MIN_SIDEBAR_WIDTH);
  assert.equal(clampSidebarWidth(500), MAX_SIDEBAR_WIDTH);
  assert.equal(clampDocumentRatio(0.1), MIN_DOCUMENT_RATIO);
  assert.equal(clampDocumentRatio(0.9), MAX_DOCUMENT_RATIO);

  // 806 px workspace => 800 px pane area => 300 px min is ratio 0.375..0.625.
  assert.equal(clampDocumentRatio(0.2, 806, RESIZER_WIDTH), 0.375);
  assert.equal(clampDocumentRatio(0.8, 806, RESIZER_WIDTH), 0.625);
  assert.deepEqual(documentSplitFrValues(0.6), { documentFr: "0.6fr", conversationFr: "0.4fr" });
});

test("stored 420px sidebar + 0.8 ratio never overflows at 1051px or 800px and keeps document/conversation >= 300px", () => {
  const stored = { sidebarWidthPx: 420, documentRatio: 0.8 };

  const wide = resolveLayoutWidths(1051, stored, { activityBarWidth: ACTIVITY_BAR_WIDTH, resizerWidth: RESIZER_WIDTH });
  assert.equal(wide.stackedWorkspace, false);
  assert.ok(wide.totalUsedPx <= 1051, `total ${wide.totalUsedPx} > 1051`);
  assert.ok(wide.sidebarPx >= MIN_SIDEBAR_WIDTH && wide.sidebarPx <= MAX_SIDEBAR_WIDTH);
  assert.ok(wide.documentPx >= MIN_WORKSPACE_PANE_WIDTH, `doc ${wide.documentPx} < 300`);
  assert.ok(wide.conversationPx >= MIN_WORKSPACE_PANE_WIDTH, `conv ${wide.conversationPx} < 300`);

  // Also verify without activity bar (D3 pre-D4 state).
  const wideNoBar = resolveLayoutWidths(1051, stored, { activityBarWidth: 0, resizerWidth: RESIZER_WIDTH });
  assert.ok(wideNoBar.totalUsedPx <= 1051);
  assert.ok(wideNoBar.documentPx >= MIN_WORKSPACE_PANE_WIDTH);
  assert.ok(wideNoBar.conversationPx >= MIN_WORKSPACE_PANE_WIDTH);

  const medium = resolveLayoutWidths(800, stored, { activityBarWidth: ACTIVITY_BAR_WIDTH, resizerWidth: RESIZER_WIDTH });
  assert.equal(medium.stackedWorkspace, true);
  assert.ok(medium.totalUsedPx <= 800, `total ${medium.totalUsedPx} > 800`);
  assert.ok(medium.documentPx >= MIN_WORKSPACE_PANE_WIDTH, `doc ${medium.documentPx} < 300`);
  assert.ok(medium.conversationPx >= MIN_WORKSPACE_PANE_WIDTH, `conv ${medium.conversationPx} < 300`);

  // Tightest non-stacked-sidebar breakpoint: 761 px.
  const tight = resolveLayoutWidths(761, stored, { activityBarWidth: ACTIVITY_BAR_WIDTH, resizerWidth: RESIZER_WIDTH });
  assert.ok(tight.totalUsedPx <= 761);
  assert.ok(tight.documentPx >= MIN_WORKSPACE_PANE_WIDTH);
  assert.ok(tight.sidebarPx >= MIN_SIDEBAR_WIDTH);
});

test("drag delta calculations clamp out-of-range pointer movement", () => {
  assert.equal(computeDraggedSidebarWidth(200, 50, 1400), 250);
  assert.equal(computeDraggedSidebarWidth(200, -100, 1400), MIN_SIDEBAR_WIDTH);
  assert.equal(computeDraggedSidebarWidth(200, 500, 1400), MAX_SIDEBAR_WIDTH);
  assert.equal(computeDraggedSidebarWidth(200, 500, 1051, { activityBarWidth: ACTIVITY_BAR_WIDTH }), 395);

  // 1006 px workspace => 1000 px pane area => 300..700 px document pane (ratio 0.3..0.7).
  assert.equal(computeDraggedDocumentRatio(500, 100, 1006), 0.6);
  assert.equal(computeDraggedDocumentRatio(500, 400, 1006), 0.7);
  assert.equal(computeDraggedDocumentRatio(500, -400, 1006), 0.3);
});

type ColumnResizerModule = typeof import("../src/components/ColumnResizer.tsx");
let viteServer: Promise<ViteDevServer> | undefined;
function loadColumnResizer(): Promise<ColumnResizerModule> {
  viteServer ??= createServer({
    configFile: false,
    root: new URL("..", import.meta.url).pathname,
    server: { middlewareMode: true, hmr: false, ws: false },
    appType: "custom",
  });
  return viteServer.then((srv) => srv.ssrLoadModule("/src/components/ColumnResizer.tsx") as Promise<ColumnResizerModule>);
}
after(async () => { await (await viteServer)?.close(); });

test("ColumnResizer SSR renders vertical separator role, ARIA bounds and inert tabIndex", async () => {
  const { ColumnResizer } = await loadColumnResizer();
  const noop = () => {};
  const activeHtml = renderToStaticMarkup(createElement(ColumnResizer, {
    className: "column-resizer-sidebar",
    label: "Resize sidebar width",
    valueNow: 240,
    valueMin: 160,
    valueMax: 420,
    onDragStart: () => null,
    onDragMove: noop,
    onDragEnd: noop,
    onKeyboardStep: noop,
    onReset: noop,
  }));
  assert.match(activeHtml, /role="separator"/);
  assert.match(activeHtml, /aria-orientation="vertical"/);
  assert.match(activeHtml, /aria-label="Resize sidebar width"/);
  assert.match(activeHtml, /aria-valuenow="240"/);
  assert.match(activeHtml, /aria-valuemin="160"/);
  assert.match(activeHtml, /aria-valuemax="420"/);
  assert.match(activeHtml, /tabindex="0"/i);

  const inertHtml = renderToStaticMarkup(createElement(ColumnResizer, {
    label: "Resize sidebar width",
    valueNow: 240,
    valueMin: 160,
    valueMax: 420,
    inert: true,
    onDragStart: () => null,
    onDragMove: noop,
    onDragEnd: noop,
    onKeyboardStep: noop,
    onReset: noop,
  }));
  assert.match(inertHtml, /tabindex="-1"/i);
  assert.match(inertHtml, /\binert\b/);
});
