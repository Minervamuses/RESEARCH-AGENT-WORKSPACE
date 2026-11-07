import assert from "node:assert/strict";
import test, { after } from "node:test";
import { createServer, type ViteDevServer } from "vite";
import {
  BIME_LAYOUT_REMINDER,
  EXPORT_LABELS,
  EXPORT_NOTES,
  exportFormats,
  exportSummary,
  previewEntries,
  styleChangeParams,
  type BibliographyRenderDto,
  type RenderSegmentDto,
} from "../src/citations.ts";

let server: Promise<ViteDevServer> | undefined;
function load<T>(path: string): Promise<T> {
  server ??= createServer({
    configFile: false,
    root: new URL("..", import.meta.url).pathname,
    server: { middlewareMode: true, hmr: false, ws: false },
    appType: "custom",
  });
  return server.then((value) => value.ssrLoadModule(path) as Promise<T>);
}
after(async () => { if (server) await (await server).close(); });

const STYLES = [
  { id: "apa", name: "APA", kind: "author-date" as const, origin: "csl-styles" as const },
  { id: "ieee", name: "IEEE", kind: "numeric" as const, origin: "csl-styles" as const },
];

test("style changes send set_style only for a different known style while idle", () => {
  const inspect = { styleId: "apa", styles: STYLES };
  assert.deepEqual(styleChangeParams(inspect, "ieee", false), { styleId: "ieee" });
  assert.equal(styleChangeParams(inspect, "ieee", true), null, "disabled during a turn");
  assert.equal(styleChangeParams(inspect, "apa", false), null, "unchanged");
  assert.equal(styleChangeParams(inspect, "nope", false), null, "unknown");
  assert.equal(styleChangeParams(null, "ieee", false), null);
});

test("only Markdown documents export: Word, BIME Word, then Markdown, never BibTeX", () => {
  assert.deepEqual(exportFormats("markdown"), ["docx", "bime_docx", "markdown"]);
  assert.deepEqual(exportFormats("latex"), []);
  assert.deepEqual(exportFormats(null), []);
  assert.deepEqual(exportFormats("markdown").map((format) => EXPORT_LABELS[format]),
    ["Word (.docx)", "Word – BIME Appendix 17 (bime_word)", "Markdown (.md)"]);
  assert.match(EXPORT_NOTES.bime_docx, /fixed to Appendix 17/);
});

test("export results name the file; BIME results add the audit and the manual-review reminder", () => {
  assert.deepEqual(exportSummary({ format: "docx", path: "/p/a.apa.docx" }),
    { path: "/p/a.apa.docx", audit: null, reportPath: null, hasErrors: false });
  const bime = exportSummary({ format: "bime_docx", path: "/p/a.bime.docx", audit: {
    errors: 2, warnings: 1, manualChecks: 11, reportPath: "/p/a.bime.audit.md", layoutVerified: false,
  } });
  assert.deepEqual(bime, {
    path: "/p/a.bime.docx", audit: "bime_word audit: 2 errors, 1 warning, 11 manual checks.",
    reportPath: "/p/a.bime.audit.md", hasErrors: true,
  });
  const clean = exportSummary({ format: "bime_docx", path: "/p/a.bime.docx", audit: {
    errors: 0, warnings: 0, manualChecks: 1, reportPath: "/p/a.bime.audit.md", layoutVerified: false,
  } });
  assert.equal(clean.audit, "bime_word audit: 0 errors, 0 warnings, 1 manual check.");
  assert.equal(clean.hasErrors, false);
  assert.match(BIME_LAYOUT_REMINDER, /update all fields, and review the layout by hand/);
});

test("Markdown documents get one closed Export button; others get none", async () => {
  type Menu = (props: Record<string, unknown>) => unknown;
  const { ExportMenu } = await load<{ ExportMenu: Menu }>("/src/CitationPanel.tsx");
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const html = renderToStaticMarkup(createElement(ExportMenu as never, {
    formats: exportFormats("markdown"), disabled: false, onExport: () => undefined,
  }));
  assert.equal((html.match(/<button/g) ?? []).length, 1);
  assert.match(html, /aria-haspopup="menu" aria-expanded="false">Export ▾<\/button>/);
  assert.ok(!html.includes("role=\"menu\""), "options render only after opening");
  const busy = renderToStaticMarkup(createElement(ExportMenu as never, {
    formats: exportFormats("markdown"), disabled: true, onExport: () => undefined,
  }));
  assert.match(busy, /<button type="button" disabled=""/);
  assert.equal(renderToStaticMarkup(createElement(ExportMenu as never, {
    formats: exportFormats("latex"), disabled: false, onExport: () => undefined,
  })), "");
});

test("segments are grouped per bibliography entry", () => {
  const render: BibliographyRenderDto = {
    styleId: "apa",
    citations: [{ index: 0, keys: ["a"], start: 0, end: 2, text: "(A, 2020)" }],
    entries: [{ key: "a", text: "A. 2020. T. J." }, { key: "b", text: "B. Plain." }],
    segments: [
      { entry: 0, text: "A. 2020. T. ", italic: false, bold: false, url: null },
      { entry: 0, text: "J", italic: true, bold: false, url: null },
      { entry: 9, text: "orphan", italic: false, bold: false, url: null },
    ],
    missing: [],
  };
  const grouped = previewEntries(render);
  assert.deepEqual(grouped.map((entry) => [entry.key, entry.segments.map((segment) => segment.text)]), [
    ["a", ["A. 2020. T. ", "J"]], ["b", ["B. Plain."]],
  ]);
});

test("cited rows offer only Line jumps; uncited rows offer Remove", async () => {
  type Row = (props: Record<string, unknown>) => unknown;
  const { CitedRow, UncitedRow } = await load<{ CitedRow: Row; UncitedRow: Row }>("/src/CitationPanel.tsx");
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const entry = {
    key: "a2019", authors: ["Ann"], year: "2019", title: "T", doi: null, type: "article-journal", citedCount: 1,
  };
  const cited = renderToStaticMarkup(createElement(CitedRow as never, {
    item: { key: "a2019", number: null, entry, count: 1, uses: [{ start: 4, end: 12, line: 3 }] },
    onJump: () => undefined,
  }));
  assert.match(cited, />Line 3<\/button>/);
  assert.equal((cited.match(/<button/g) ?? []).length, 1, "only the Line jump");
  assert.ok(!/Remove|Insert/.test(cited));
  assert.ok(!/verified|citation-badge/.test(cited), "no verified/unverified badge");
  const uncited = renderToStaticMarkup(createElement(UncitedRow as never, { entry, onRemove: () => undefined, disabled: false }));
  assert.match(uncited, /<button type="button" class="link-button">Remove<\/button>/);
  assert.ok(!uncited.includes("Insert"));
  const locked = renderToStaticMarkup(createElement(UncitedRow as never, { entry, onRemove: () => undefined, disabled: true }));
  assert.match(locked, /<button type="button" class="link-button" disabled="">Remove<\/button>/);
});

test("a newly rendered panel is only the collapsed summary bar", async () => {
  const { CitationPanel } = await load<{ CitationPanel: (props: Record<string, unknown>) => unknown }>("/src/CitationPanel.tsx");
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const html = renderToStaticMarkup(createElement(CitationPanel as never, {
    document: { rootPath: "/p", path: "/p/a.md", editorRevision: 0, sourceText: "", diskFingerprint: "0".repeat(64) },
    refreshToken: 0, request: () => new Promise(() => undefined), contextPayload: () => ({}),
    onSelect: () => undefined, requestAdd: () => new Promise(() => undefined), writesDisabled: false,
  }));
  assert.match(html, /<header class="citation-summary"><h3>Citations<\/h3>/);
  assert.match(html, /class="citation-toggle" aria-expanded="false"[^>]*>Expand ▾<\/button>/);
  assert.ok(!html.includes("citation-body") && !html.includes("Verify and add"), "the body renders only when expanded");
});

test("preview text shows italics and safe links without interpreting markup", async () => {
  const { CitationText } = await load<{ CitationText: (props: { segments: RenderSegmentDto[] }) => unknown }>("/src/CitationText.tsx");
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const html = renderToStaticMarkup(createElement(CitationText as never, { segments: [
    { entry: 0, text: "Smith. <img src=x onerror=alert(1)> *not italic* ", italic: false, bold: false, url: null },
    { entry: 0, text: "Journal_of_Agri", italic: true, bold: false, url: null },
    { entry: 0, text: "https://doi.org/10.1/x", italic: false, bold: false, url: "https://doi.org/10.1/x" },
    { entry: 0, text: "javascript:alert(1)", italic: false, bold: false, url: "javascript:alert(1)" },
  ] }));
  assert.match(html, /<em>Journal_of_Agri<\/em>/);
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt; \*not italic\*/);
  assert.equal((html.match(/<button/g) ?? []).length, 1);
  assert.match(html, /<button type="button" class="safe-link">https:\/\/doi.org\/10.1\/x<\/button>/);
  assert.ok(!html.includes("<img"));
});
