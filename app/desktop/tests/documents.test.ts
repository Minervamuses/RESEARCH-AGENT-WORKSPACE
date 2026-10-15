import type { DocumentSnapshot } from "../src/DocumentEditor.tsx";
import assert from "node:assert/strict";
import test, { after } from "node:test";
import { createServer, type ViteDevServer } from "vite";

interface Position { lineNumber: number; column: number }
interface SourceChange {
  range: { startLineNumber: number; startColumn: number; endLineNumber: number; endColumn: number };
  text: string;
}
interface DocumentHelpers {
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
