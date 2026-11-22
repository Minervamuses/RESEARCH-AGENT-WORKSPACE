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
  type BibliographyAddDto,
  type BibliographyRenderDto,
} from "../src/citations.ts";

let server: Promise<ViteDevServer> | undefined;
type CitationPanelModule = typeof import("../src/CitationPanel.tsx");
type CitationTextModule = typeof import("../src/CitationText.tsx");
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
  const { ExportMenu } = await load<CitationPanelModule>("/src/CitationPanel.tsx");
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const html = renderToStaticMarkup(createElement(ExportMenu, {
    formats: exportFormats("markdown"), disabled: false, onExport: () => undefined,
  }));
  assert.equal((html.match(/<button/g) ?? []).length, 1);
  assert.match(html, /aria-haspopup="menu" aria-expanded="false">Export ▾<\/button>/);
  assert.ok(!html.includes("role=\"menu\""), "options render only after opening");
  const busy = renderToStaticMarkup(createElement(ExportMenu, {
    formats: exportFormats("markdown"), disabled: true, onExport: () => undefined,
  }));
  assert.match(busy, /<button type="button" disabled=""/);
  assert.equal(renderToStaticMarkup(createElement(ExportMenu, {
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
  const { CitedRow, UncitedRow } = await load<CitationPanelModule>("/src/CitationPanel.tsx");
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const entry = {
    key: "a2019", authors: ["Ann"], year: "2019", title: "T", doi: null, type: "article-journal", citedCount: 1,
  };
  const cited = renderToStaticMarkup(createElement(CitedRow, {
    item: { key: "a2019", number: null, entry, count: 1, uses: [{ start: 4, end: 12, line: 3 }] },
    onJump: () => undefined,
  }));
  assert.match(cited, />Line 3<\/button>/);
  assert.equal((cited.match(/<button/g) ?? []).length, 1, "only the Line jump");
  assert.ok(!/Remove|Insert/.test(cited));
  assert.ok(!/verified/i.test(cited), "no verified/unverified badge");
  const uncited = renderToStaticMarkup(createElement(UncitedRow, { entry, onRemove: () => undefined, disabled: false }));
  assert.match(uncited, /<button type="button"[^>]*>Remove<\/button>/);
  assert.ok(!uncited.includes("Insert"));
  const locked = renderToStaticMarkup(createElement(UncitedRow, { entry, onRemove: () => undefined, disabled: true }));
  assert.match(locked, /<button type="button"[^>]*disabled=""[^>]*>Remove<\/button>/);
});

test("a newly rendered panel is only the collapsed summary bar", async () => {
  const { CitationPanel } = await load<CitationPanelModule>("/src/CitationPanel.tsx");
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const snapshot = { rootPath: "/p", path: "/p/a.md", editorRevision: 0, sourceText: "", diskFingerprint: "0".repeat(64) };
  const never = () => new Promise<never>(() => undefined);
  const html = renderToStaticMarkup(createElement(CitationPanel, {
    document: snapshot,
    refreshToken: 0,
    api: {
      bibliographyInspect: () => never(), bibliographyRemove: () => never(), bibliographySetStyle: () => never(),
      bibliographyRender: () => never(), bibliographyExport: () => never(),
    },
    contextPayload: () => snapshot,
    onSelect: () => undefined, requestAdd: () => new Promise<BibliographyAddDto>(() => undefined), writesDisabled: false,
  }));
  assert.match(html, /<h3>Citations<\/h3>/);
  assert.match(html, /<button[^>]*aria-expanded="false"[^>]*>Expand ▾<\/button>/);
  assert.ok(!html.includes("Verify and add"), "the body renders only when expanded");
});

test("preview text shows italics and safe links without interpreting markup", async () => {
  const { CitationText } = await load<CitationTextModule>("/src/CitationText.tsx");
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const html = renderToStaticMarkup(createElement(CitationText, { segments: [
    { entry: 0, text: "Smith. <img src=x onerror=alert(1)> *not italic* ", italic: false, bold: false, url: null },
    { entry: 0, text: "Journal_of_Agri", italic: true, bold: false, url: null },
    { entry: 0, text: "https://doi.org/10.1/x", italic: false, bold: false, url: "https://doi.org/10.1/x" },
    { entry: 0, text: "javascript:alert(1)", italic: false, bold: false, url: "javascript:alert(1)" },
  ] }));
  assert.match(html, /<em>Journal_of_Agri<\/em>/);
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt; \*not italic\*/);
  assert.equal((html.match(/<button/g) ?? []).length, 1);
  assert.match(html, /<button type="button"[^>]*>https:\/\/doi.org\/10.1\/x<\/button>/);
  assert.ok(!html.includes("<img"));
});
