import assert from "node:assert/strict";
import test, { after } from "node:test";
import { createServer, type ViteDevServer } from "vite";
import { handleAnnotationKey } from "../src/lib/composer.ts";
import {
  advanceWorkingDocumentSources,
  documentContextPayload,
  documentOperationContext,
  planConflictResolution,
  planDocumentResult,
  reconcileSavedDocument,
  submittedDocumentSource,
  type WorkingDocumentSources,
} from "../src/lib/documents.ts";
import {
  applyDocumentChanges,
  documentOffsetAt,
  documentPositionAt,
} from "../src/lib/documentSource.ts";

// Only the annotation rendering test needs a .tsx component (monaco-free SSR load).
type DocumentEditorModule = typeof import("../src/DocumentEditor.tsx");

let server: Promise<ViteDevServer> | undefined;
function loadDocumentEditor(): Promise<DocumentEditorModule> {
  server ??= createServer({
    configFile: false,
    root: new URL("..", import.meta.url).pathname,
    server: { middlewareMode: true, hmr: false, ws: false },
    appType: "custom",
  });
  return server.then((value) => value.ssrLoadModule("/src/DocumentEditor.tsx") as Promise<DocumentEditorModule>);
}
after(async () => { await (await server)?.close(); });

test("a source selection targets the second duplicate without changing BOM, tabs or mixed newlines", () => {
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

test("source lines 40–45 use stored lines even when one source line is long", () => {
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

test("multiple Monaco edits resolve against one pre-edit source snapshot", () => {
  assert.equal(applyDocumentChanges("一😀二\n三\t四\n", [
    { range: { startLineNumber: 1, startColumn: 2, endLineNumber: 1, endColumn: 4 }, text: "🙂" },
    { range: { startLineNumber: 2, startColumn: 2, endLineNumber: 2, endColumn: 3 }, text: "" },
  ]), "一🙂二\n三四\n");
});

const save = reconcileSavedDocument;

test("manual Save preserves an empty or narrow selection and does not advance an unchanged revision", () => {
  const base = { rootPath: "/tmp/project", path: "/tmp/project/draft.md", sourceText: "one\ntwo\n", editorRevision: 1, diskFingerprint: "a".repeat(64) };
  const receipt = { ...base, rangeStartUtf16: 0, rangeEndUtf16: base.sourceText.length, diskFingerprint: "b".repeat(64) };
  const noSelection = save(base, base, receipt, false);
  assert.equal(noSelection.editorRevision, 1);
  assert.equal(noSelection.rangeStartUtf16, undefined);
  const narrow = { ...base, rangeStartUtf16: 4, rangeEndUtf16: 7 };
  assert.deepEqual(save(narrow, narrow, receipt, false), { ...narrow, diskFingerprint: receipt.diskFingerprint });
});

test("Agent saved snapshots use the post-replacement selection and preserve edits made after send", () => {
  const base = { rootPath: "/tmp/project", path: "/tmp/project/draft.md", sourceText: "long source", editorRevision: 4, diskFingerprint: "a".repeat(64), rangeStartUtf16: 0, rangeEndUtf16: 11 };
  const receipt = { ...base, sourceText: "短😀", editorRevision: 5, rangeEndUtf16: 3, diskFingerprint: "b".repeat(64) };
  assert.deepEqual(save(base, base, receipt, true), receipt);
  const newer = { ...base, sourceText: "new user text", editorRevision: 6 };
  assert.deepEqual(save(newer, base, receipt, true), { ...newer, diskFingerprint: receipt.diskFingerprint });
});

test("a selection collapsed during approval omits optional range keys from every document payload", () => {
  const base = { rootPath: "/tmp/project", path: "/tmp/project/draft.md", sourceText: "one\ntwo\n", editorRevision: 1, diskFingerprint: "a".repeat(64) };
  const collapsed = documentContextPayload({ ...base, rangeStartUtf16: undefined, rangeEndUtf16: undefined });
  assert.deepEqual(collapsed, base);
  assert.equal(Object.hasOwn(collapsed, "rangeStartUtf16"), false);
  assert.equal(Object.hasOwn(collapsed, "rangeEndUtf16"), false);
  assert.deepEqual(documentContextPayload({ ...base, rangeStartUtf16: 4, rangeEndUtf16: 7 }), { ...base, rangeStartUtf16: 4, rangeEndUtf16: 7 });
});

test("annotation Enter confirms locally while IME and Shift+Enter keep editing", async () => {
  const { AnnotationComment } = await loadDocumentEditor();
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

test("saved document receipts advance two UTF-16 references without changing the submitted context", () => {
  const source = "前言\r\n甲😀段\r\n保留\r\n乙😀段\r\n尾聲";
  const base = { rootPath: "/tmp/project", path: "/tmp/project/draft.md", sourceText: source, editorRevision: 3, diskFingerprint: "a".repeat(64) };
  const firstStart = source.indexOf("甲"), firstEnd = firstStart + "甲😀段".length;
  const secondStart = source.indexOf("乙"), secondEnd = secondStart + "乙😀段".length;
  const submitted: WorkingDocumentSources = { documentContext: base, references: [
    { referenceId: "first", kind: "document" as const, text: "甲😀段", document: { startLine: 2, endLine: 2,
      snapshot: { ...base, rangeStartUtf16: firstStart, rangeEndUtf16: firstEnd } } },
    { referenceId: "second", kind: "document" as const, text: "乙😀段", document: { startLine: 4, endLine: 4,
      snapshot: { ...base, rangeStartUtf16: secondStart, rangeEndUtf16: secondEnd } } },
  ] };
  const original = structuredClone(submitted);
  let working = structuredClone(submitted);
  const advance = (...args: Parameters<typeof advanceWorkingDocumentSources>): WorkingDocumentSources => {
    const next = advanceWorkingDocumentSources(...args);
    assert.ok(next !== null);
    return next;
  };
  const beforeFirst = submittedDocumentSource(working, "first")!;
  const replacement = "修改甲😀\r\n新增";
  const firstSaved = { ...base, status: "saved" as const, sourceText: source.slice(0, firstStart) + replacement + source.slice(firstEnd),
    editorRevision: 4, diskFingerprint: "b".repeat(64), rangeStartUtf16: firstStart, rangeEndUtf16: firstStart + replacement.length };
  for (const status of ["conflict", "failed", "cancelled"] as const) {
    assert.equal(advanceWorkingDocumentSources(working, beforeFirst, { ...firstSaved, status }), working);
  }
  working = advance(working, beforeFirst, firstSaved);
  assert.deepEqual(submitted, original);
  assert.deepEqual(advanceWorkingDocumentSources(working, beforeFirst, firstSaved), working, "duplicate receipt cannot move a range twice");
  const beforeSecond = submittedDocumentSource(working, "second")!;
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
  const secondSaved = { ...base, status: "saved" as const, sourceText: firstSaved.sourceText.slice(0, beforeSecond.rangeStartUtf16) + "乙改🙂" + firstSaved.sourceText.slice(beforeSecond.rangeEndUtf16),
    editorRevision: 5, diskFingerprint: "c".repeat(64), rangeStartUtf16: beforeSecond.rangeStartUtf16,
    rangeEndUtf16: beforeSecond.rangeStartUtf16 + "乙改🙂".length };
  working = advance(working, beforeSecond, secondSaved);
  assert.equal(working.documentContext!.sourceText, "前言\r\n修改甲😀\r\n新增\r\n保留\r\n乙改🙂\r\n尾聲");
  assert.equal(working.documentContext!.rangeStartUtf16, secondSaved.rangeStartUtf16);
  const firstReference = working.references[0];
  assert.equal(firstReference.kind, "document");
  assert.equal(firstReference.kind === "document" && firstReference.document.snapshot.sourceText, secondSaved.sourceText);
  assert.deepEqual(advanceWorkingDocumentSources(working, beforeFirst, firstSaved), working, "an older saved base cannot roll back the current snapshot");
  assert.deepEqual(submitted, original);
});

const snap = { rootPath: "/p", path: "a.md", editorRevision: 3, sourceText: "old", diskFingerprint: "fp0" };
const savedResult = { path: "a.md", rootPath: "/p", status: "saved" as const, sourceText: "new", diskFingerprint: "fp1", editorRevision: 4 };

test("document result: a result for another open file or a different source is not applied", () => {
  assert.deepEqual(planDocumentResult(savedResult, snap, null, null, null), { kind: "ignore" });
  assert.deepEqual(planDocumentResult(savedResult, snap, { ...snap, path: "b.md" }, null, null), { kind: "ignore" });
  assert.deepEqual(planDocumentResult({ ...savedResult, path: "b.md" }, snap, snap, null, null), { kind: "mismatch" });
  assert.deepEqual(planDocumentResult({ ...savedResult, rootPath: "/q" }, snap, snap, null, null), { kind: "mismatch" });
});

test("document result: saved reconciles an unchanged editor and only advances the fingerprint after edits", () => {
  const plain = planDocumentResult(savedResult, snap, snap, null, null);
  assert.equal(plain.kind, "saved");
  if (plain.kind !== "saved") return;
  assert.equal(plain.document.sourceText, "new");
  assert.equal(plain.baseline.diskFingerprint, "fp1");
  assert.equal(plain.lastAction, null);
  assert.equal(plain.advanceSources, false);

  const edited = planDocumentResult(savedResult, snap, { ...snap, editorRevision: 4, sourceText: "typed" }, null, null);
  assert.equal(edited.kind === "saved" && edited.document.sourceText, "typed");
  assert.equal(edited.kind === "saved" && edited.document.diskFingerprint, "fp1");

  const action = { turnId: "t", callId: "c1", sourceSnapshot: snap };
  const applied = planDocumentResult(savedResult, snap, snap, action, null);
  assert.equal(applied.kind === "saved" && applied.advanceSources, true);
  assert.deepEqual(applied.kind === "saved" && applied.lastAction, { set: action });
  const undo = planDocumentResult(savedResult, snap, snap, { ...action, undoOfCallId: "c0" }, null);
  assert.deepEqual(undo.kind === "saved" && undo.lastAction, { set: null });
  // A "saved" result without its text and fingerprint is treated like a cancelled one.
  assert.equal(planDocumentResult({ ...savedResult, diskFingerprint: undefined }, snap, snap, null, null).kind, "cancelled");
});

test("document result: conflict and failure keep the editor and pick the right base for the conflict panel", () => {
  const conflict = { path: "a.md", status: "conflict" as const, expectedSnapshot: snap };
  const direct = planDocumentResult(conflict, snap, snap, null, null);
  assert.equal(direct.kind, "conflict");
  assert.equal(direct.kind === "conflict" && direct.conflict.base, snap);
  assert.match(direct.kind === "conflict" ? direct.notice : "", /Choose which version to keep/);

  const submitted = { ...snap, sourceText: "sent" };
  const agent = { turnId: "t" };
  const viaSubmitted = planDocumentResult(conflict, snap, snap, agent, submitted);
  assert.equal(viaSubmitted.kind === "conflict" && viaSubmitted.conflict.base, submitted);
  const source = { ...snap, sourceText: "source" };
  const viaSource = planDocumentResult(conflict, snap, snap, { ...agent, sourceSnapshot: source }, submitted);
  assert.equal(viaSource.kind === "conflict" && viaSource.conflict.base, source);

  const failed = planDocumentResult({ path: "a.md", status: "failed", issue: "disk full" }, snap, snap, null, null);
  assert.equal(failed.kind === "failed" && failed.notice, "disk full");
  const bare = planDocumentResult({ path: "a.md", status: "failed" }, snap, snap, null, null);
  assert.equal(bare.kind === "failed" && bare.notice, "Save failed. The editor and candidate are retained.");
  const cancelled = planDocumentResult({ path: "a.md", status: "cancelled" }, snap, snap, null, null);
  assert.deepEqual(cancelled, { kind: "cancelled", notice: "Operation cancelled. Your current text is retained." });
});

test("conflict resolution: agent operations resend, a manual save needs the editor unchanged since the conflict", () => {
  const result = { path: "a.md", status: "conflict" as const, expectedSnapshot: { ...snap, diskFingerprint: "fp9" } };
  const action = { turnId: "t" };
  assert.deepEqual(planConflictResolution({ action, result, base: snap }, "keep", snap),
    { kind: "apply", action, expectedSnapshot: result.expectedSnapshot });
  const manual = { action: null, result, base: snap };
  assert.deepEqual(planConflictResolution(manual, "use", snap), { kind: "save-again", diskFingerprint: "fp9" });
  assert.deepEqual(planConflictResolution(manual, "use", null), { kind: "no-document" });
  assert.equal(planConflictResolution(manual, "use", { ...snap, sourceText: "changed" }).kind, "editor-changed");
  assert.equal(planConflictResolution(manual, "use", { ...snap, editorRevision: 9 }).kind, "editor-changed");
  assert.deepEqual(planConflictResolution(manual, "keep", snap), { kind: "dismiss" });
  assert.deepEqual(planConflictResolution(manual, "cancel", snap), { kind: "dismiss" });
  assert.deepEqual(planConflictResolution({ action: null, result: { path: "a.md", status: "conflict" }, base: snap }, "use", snap), { kind: "dismiss" });
});
