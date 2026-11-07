import assert from "node:assert/strict";
import test, { after } from "node:test";
import { createServer, type ViteDevServer } from "vite";
import {
  exportFormats,
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

test("only Markdown documents export, and never BibTeX", () => {
  assert.deepEqual(exportFormats("markdown"), ["docx", "markdown"]);
  assert.deepEqual(exportFormats("latex"), []);
  assert.deepEqual(exportFormats(null), []);
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
    key: "a2019", authors: ["Ann"], year: "2019", title: "T", doi: null, type: "article-journal",
    verification: "verified" as const, citedCount: 1,
  };
  const cited = renderToStaticMarkup(createElement(CitedRow as never, {
    item: { key: "a2019", number: null, entry, count: 1, uses: [{ start: 4, end: 12, line: 3 }] },
    onJump: () => undefined,
  }));
  assert.match(cited, />Line 3<\/button>/);
  assert.equal((cited.match(/<button/g) ?? []).length, 1, "only the Line jump");
  assert.ok(!/Remove|Insert/.test(cited));
  const uncited = renderToStaticMarkup(createElement(UncitedRow as never, { entry, onRemove: () => undefined, disabled: false }));
  assert.match(uncited, /<button type="button" class="link-button">Remove<\/button>/);
  assert.ok(!uncited.includes("Insert"));
  const locked = renderToStaticMarkup(createElement(UncitedRow as never, { entry, onRemove: () => undefined, disabled: true }));
  assert.match(locked, /<button type="button" class="link-button" disabled="">Remove<\/button>/);
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
