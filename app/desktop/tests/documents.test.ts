import type { AnnotationControls, DocumentSnapshot } from "../src/DocumentEditor.tsx";
import type { DraftAnnotation } from "../src/conversations.ts";
import assert from "node:assert/strict";
import test, { after } from "node:test";
import { createServer, type ViteDevServer } from "vite";

interface Position { lineNumber: number; column: number }
interface SourceChange {
  range: { startLineNumber: number; startColumn: number; endLineNumber: number; endColumn: number };
  text: string;
}
interface DocumentHelpers {
  AnnotationComment: (props: { annotation: DraftAnnotation; controls: AnnotationControls }) => unknown;
  handleAnnotationKey: (event: { key: string; shiftKey: boolean; isComposing: boolean;
    preventDefault: () => void; stopPropagation: () => void }, confirm: () => void) => void;
  documentOffsetAt: (source: string, position: Position) => number;
  documentPositionAt: (source: string, offset: number) => Position;
  applyDocumentChanges: (source: string, changes: readonly SourceChange[]) => string;
}

let server: Promise<ViteDevServer> | undefined;
let helpers: Promise<DocumentHelpers> | undefined;
function loadHelpers(): Promise<DocumentHelpers> {
  server ??= createServer({
    configFile: false,
    root: new URL("..", import.meta.url).pathname,
    server: { middlewareMode: true, hmr: false, ws: false },
    appType: "custom",
  });
  helpers ??= server.then((value) => value.ssrLoadModule("/src/DocumentEditor.tsx") as Promise<DocumentHelpers>);
  return helpers;
}
after(async () => { await (await server)?.close(); });

test("a source selection targets the second duplicate without changing BOM, tabs or mixed newlines", async () => {
  const { documentOffsetAt, documentPositionAt, applyDocumentChanges } = await loadHelpers();
  const source = "\uFEFF前言\r\n相同😀\t文字\r\n\n相同😀\t文字\r\n";
  const start = documentOffsetAt(source, { lineNumber: 4, column: 1 });
  const end = documentOffsetAt(source, { lineNumber: 4, column: 8 });
  assert.equal(source.slice(start, end), "相同😀\t文字");
  assert.equal(start, source.lastIndexOf("相同"));
  assert.deepEqual(documentPositionAt(source, start + 4), { lineNumber: 4, column: 5 });
  assert.equal(applyDocumentChanges(source, [{
    range: { startLineNumber: 4, startColumn: 1, endLineNumber: 4, endColumn: 8 },
    text: "修改後😀",
  }]), "\uFEFF前言\r\n相同😀\t文字\r\n\n修改後😀\r\n");
});

test("source lines 40–45 use stored lines even when one source line is long", async () => {
  const { documentOffsetAt, applyDocumentChanges } = await loadHelpers();
  const lines = Array.from({ length: 47 }, (_, index) => index === 27 ? "長行".repeat(200) : `第 ${index + 1} 行`);
  const source = `${lines.join("\r\n")}\r\n`;
  const start = documentOffsetAt(source, { lineNumber: 40, column: 1 });
  const end = documentOffsetAt(source, { lineNumber: 46, column: 1 });
  assert.equal(source.slice(start, end), `${lines.slice(39, 45).join("\r\n")}\r\n`);
  const result = applyDocumentChanges(source, [{
    range: { startLineNumber: 40, startColumn: 1, endLineNumber: 46, endColumn: 1 },
    text: "- 清單\r\n",
  }]);
  assert.equal(result, `${lines.slice(0, 39).join("\r\n")}\r\n- 清單\r\n${lines.slice(45).join("\r\n")}\r\n`);
});

test("multiple Monaco edits resolve against one pre-edit source snapshot", async () => {
  const { applyDocumentChanges } = await loadHelpers();
  assert.equal(applyDocumentChanges("一😀二\n三\t四\n", [
    { range: { startLineNumber: 1, startColumn: 2, endLineNumber: 1, endColumn: 4 }, text: "🙂" },
    { range: { startLineNumber: 2, startColumn: 2, endLineNumber: 2, endColumn: 3 }, text: "" },
  ]), "一🙂二\n三四\n");
});

async function reconcile() {
  await loadHelpers();
  return (await (await server!).ssrLoadModule("/src/App.tsx")).reconcileSavedDocument as (
    current: DocumentSnapshot, captured: DocumentSnapshot,
    saved: Partial<DocumentSnapshot> & { sourceText: string; diskFingerprint: string },
    agentOperation: boolean,
  ) => DocumentSnapshot;
}

test("manual Save preserves an empty or narrow selection and does not advance an unchanged revision", async () => {
  const save = await reconcile();
  const base = { rootPath: "/tmp/project", path: "/tmp/project/draft.md", sourceText: "one\ntwo\n", editorRevision: 1, diskFingerprint: "a".repeat(64) };
  const receipt = { ...base, rangeStartUtf16: 0, rangeEndUtf16: base.sourceText.length, diskFingerprint: "b".repeat(64) };
  const noSelection = save(base, base, receipt, false);
  assert.equal(noSelection.editorRevision, 1);
  assert.equal(noSelection.rangeStartUtf16, undefined);
  const narrow = { ...base, rangeStartUtf16: 4, rangeEndUtf16: 7 };
  assert.deepEqual(save(narrow, narrow, receipt, false), { ...narrow, diskFingerprint: receipt.diskFingerprint });
});

test("Agent saved snapshots use the post-replacement selection and preserve edits made after send", async () => {
  const save = await reconcile();
  const base = { rootPath: "/tmp/project", path: "/tmp/project/draft.md", sourceText: "long source", editorRevision: 4, diskFingerprint: "a".repeat(64), rangeStartUtf16: 0, rangeEndUtf16: 11 };
  const receipt = { ...base, sourceText: "短😀", editorRevision: 5, rangeEndUtf16: 3, diskFingerprint: "b".repeat(64) };
  assert.deepEqual(save(base, base, receipt, true), receipt);
  const newer = { ...base, sourceText: "new user text", editorRevision: 6 };
  assert.deepEqual(save(newer, base, receipt, true), { ...newer, diskFingerprint: receipt.diskFingerprint });
});

test("a selection collapsed during approval omits optional range keys from every document payload", async () => {
  await loadHelpers();
  const payload = (await (await server!).ssrLoadModule("/src/App.tsx")).documentContextPayload;
  const base = { rootPath: "/tmp/project", path: "/tmp/project/draft.md", sourceText: "one\ntwo\n", editorRevision: 1, diskFingerprint: "a".repeat(64) };
  const collapsed = payload({ ...base, rangeStartUtf16: undefined, rangeEndUtf16: undefined });
  assert.deepEqual(collapsed, base);
  assert.equal(Object.hasOwn(collapsed, "rangeStartUtf16"), false);
  assert.equal(Object.hasOwn(collapsed, "rangeEndUtf16"), false);
  assert.deepEqual(payload({ ...base, rangeStartUtf16: 4, rangeEndUtf16: 7 }), { ...base, rangeStartUtf16: 4, rangeEndUtf16: 7 });
});

test("annotation Enter confirms locally while IME and Shift+Enter keep editing", async () => {
  const { AnnotationComment, handleAnnotationKey } = await loadHelpers();
  let confirms = 0, prevented = 0, stopped = 0;
  const event = { key: "Enter", shiftKey: false, isComposing: false,
    preventDefault: () => { prevented++; }, stopPropagation: () => { stopped++; } };
  handleAnnotationKey({ ...event, isComposing: true }, () => { confirms++; });
  handleAnnotationKey({ ...event, shiftKey: true }, () => { confirms++; });
  assert.equal(confirms, 0);
  handleAnnotationKey(event, () => { confirms++; });
  assert.equal(confirms, 1);
  assert.equal(prevented, 1);
  assert.equal(stopped, 3, "comment keyboard events never reach the batch composer");
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { createElement } = await import("react");
  const annotation = { referenceId: "reference", number: 3, comment: "Revise this", expanded: true };
  const controls = { annotations: [annotation], references: [], disabled: false,
    onChange: () => {}, onToggle: () => {}, onRemove: () => {} };
  const open = renderToStaticMarkup(createElement(AnnotationComment, { annotation, controls }));
  assert.match(open, /data-reference-exclude/);
  assert.match(open, /aria-expanded="true"/);
  assert.match(open, /<textarea[^>]*aria-label="Comment 3"[^>]*>Revise this<\/textarea>/);
  assert.match(open, />Remove<\/button>/);
  assert.doesNotMatch(open, /type="submit"/);
  const closed = renderToStaticMarkup(createElement(AnnotationComment, { annotation: { ...annotation, expanded: false }, controls }));
  assert.match(closed, /aria-expanded="false"/);
  assert.doesNotMatch(closed, /textarea/);
});

test("saved document receipts advance two UTF-16 references without changing the submitted context", async () => {
  await loadHelpers();
  const { advanceWorkingDocumentSources, documentOperationContext, documentContextPayload, submittedDocumentSource } = await (await server!).ssrLoadModule("/src/App.tsx");
  const source = "前言\r\n甲😀段\r\n保留\r\n乙😀段\r\n尾聲";
  const base = { rootPath: "/tmp/project", path: "/tmp/project/draft.md", sourceText: source, editorRevision: 3, diskFingerprint: "a".repeat(64) };
  const firstStart = source.indexOf("甲"), firstEnd = firstStart + "甲😀段".length;
  const secondStart = source.indexOf("乙"), secondEnd = secondStart + "乙😀段".length;
  const submitted = { documentContext: base, references: [
    { referenceId: "first", kind: "document", text: "甲😀段", document: { startLine: 2, endLine: 2,
      snapshot: { ...base, rangeStartUtf16: firstStart, rangeEndUtf16: firstEnd } } },
    { referenceId: "second", kind: "document", text: "乙😀段", document: { startLine: 4, endLine: 4,
      snapshot: { ...base, rangeStartUtf16: secondStart, rangeEndUtf16: secondEnd } } },
  ] };
  const original = structuredClone(submitted);
  let working = structuredClone(submitted);
  const beforeFirst = submittedDocumentSource(working, "first");
  const replacement = "修改甲😀\r\n新增";
  const firstSaved = { ...base, status: "saved", sourceText: source.slice(0, firstStart) + replacement + source.slice(firstEnd),
    editorRevision: 4, diskFingerprint: "b".repeat(64), rangeStartUtf16: firstStart, rangeEndUtf16: firstStart + replacement.length };
  for (const status of ["conflict", "failed", "cancelled"]) {
    assert.equal(advanceWorkingDocumentSources(working, beforeFirst, { ...firstSaved, status }), working);
  }
  working = advanceWorkingDocumentSources(working, beforeFirst, firstSaved);
  assert.deepEqual(submitted, original);
  assert.deepEqual(advanceWorkingDocumentSources(working, beforeFirst, firstSaved), working, "duplicate receipt cannot move a range twice");
  const beforeSecond = submittedDocumentSource(working, "second");
  const delta = firstSaved.rangeEndUtf16 - firstEnd;
  assert.equal(beforeSecond.rangeStartUtf16, secondStart + delta);
  assert.equal(beforeSecond.rangeEndUtf16, secondEnd + delta);
  assert.equal(beforeSecond.sourceText.slice(beforeSecond.rangeStartUtf16, beforeSecond.rangeEndUtf16), "乙😀段");
  assert.equal(beforeSecond.editorRevision, 4);
  assert.equal(beforeSecond.diskFingerprint, firstSaved.diskFingerprint);
  const currentEditor = { ...base, ...firstSaved };
  const applyContext = documentOperationContext(currentEditor, beforeSecond);
  assert.equal(applyContext.sourceText, firstSaved.sourceText);
  assert.equal(applyContext.rangeStartUtf16, beforeSecond.rangeStartUtf16, "apply and Ask use the second reference instead of the prior editor selection");
  assert.equal(documentContextPayload(applyContext).rangeEndUtf16, beforeSecond.rangeEndUtf16);
  const secondSaved = { ...base, status: "saved", sourceText: firstSaved.sourceText.slice(0, beforeSecond.rangeStartUtf16) + "乙改🙂" + firstSaved.sourceText.slice(beforeSecond.rangeEndUtf16),
    editorRevision: 5, diskFingerprint: "c".repeat(64), rangeStartUtf16: beforeSecond.rangeStartUtf16,
    rangeEndUtf16: beforeSecond.rangeStartUtf16 + "乙改🙂".length };
  working = advanceWorkingDocumentSources(working, beforeSecond, secondSaved);
  assert.equal(working.documentContext.sourceText, "前言\r\n修改甲😀\r\n新增\r\n保留\r\n乙改🙂\r\n尾聲");
  assert.equal(working.documentContext.rangeStartUtf16, secondSaved.rangeStartUtf16);
  assert.equal(working.references[0].document.snapshot.sourceText, secondSaved.sourceText);
  assert.deepEqual(advanceWorkingDocumentSources(working, beforeFirst, firstSaved), working, "an older saved base cannot roll back the current snapshot");
  assert.deepEqual(submitted, original);
});
