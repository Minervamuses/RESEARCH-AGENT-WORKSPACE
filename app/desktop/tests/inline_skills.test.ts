import assert from "node:assert/strict";
import test, { after } from "node:test";
import { createServer, type ViteDevServer } from "vite";

type Ref = { name: string; startUtf16: number; endUtf16: number };
interface Helpers {
  inlineSkillToken: (text: string, start: number, end: number) => { start: number; end: number; prefix: string } | null;
  insertInlineSkill: (text: string, token: { start: number; end: number }, name: string) => { text: string; caret: number };
  inlineSkillReferences: (text: string, skills: readonly string[], selected?: ReadonlySet<string>) => Ref[];
  handleComposerKey: (event: { key: string; shiftKey: boolean; isComposing: boolean; preventDefault: () => void }, menu: { open: boolean; count: number; active: number }, actions: { select: (i: number) => void; move: (i: number) => void; close: () => void; submit: () => void }) => void;
}
let server: Promise<ViteDevServer> | undefined;
let helpers: Promise<Helpers> | undefined;
function load(): Promise<Helpers> {
  server ??= createServer({ configFile: false, root: new URL("..", import.meta.url).pathname, server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  helpers ??= server.then((value) => value.ssrLoadModule("/src/App.tsx") as Promise<Helpers>);
  return helpers;
}
after(async () => { await (await server)?.close(); });

test("middle and cursor-back Skill insertion replaces only the current token", async () => {
  const h = await load();
  const text = "請先@acade 再找引用，保留後文";
  const cursor = text.indexOf(" 再");
  const token = h.inlineSkillToken(text, cursor, cursor)!;
  assert.equal(token.prefix, "acade");
  const inserted = h.insertInlineSkill(text, token, "academic-paper-writing");
  assert.equal(inserted.text, "請先@academic-paper-writing 再找引用，保留後文");
  assert.equal(inserted.caret, "請先@academic-paper-writing".length);
  const mid = "先 @academic-paper 後";
  const back = mid.indexOf("demic");
  const replacement = h.insertInlineSkill(mid, h.inlineSkillToken(mid, back, back)!, "citation");
  assert.equal(replacement.text, "先 @citation 後");
});

test("references keep original UTF16 order and duplicate positions after editing", async () => {
  const h = await load();
  const text = "😀先@academic-paper-writing，再 @citation 後 @citation";
  const refs = h.inlineSkillReferences(text, ["academic-paper-writing", "citation"]);
  assert.deepEqual(refs.map((r) => r.name), ["academic-paper-writing", "citation", "citation"]);
  for (const ref of refs) assert.equal(text.slice(ref.startUtf16, ref.endUtf16), "@" + ref.name);
  const edited = "前文 " + text;
  const moved = h.inlineSkillReferences(edited, ["academic-paper-writing", "citation"]);
  assert.equal(moved[0].startUtf16, refs[0].startUtf16 + 3);
});

test("email, domain, ordinary at-text and stale picker choices are explicit", async () => {
  const h = await load();
  const text = "a@citation.org @citation.org @ordinary @ text";
  assert.deepEqual(h.inlineSkillReferences(text, ["citation"]), []);
  assert.equal(h.inlineSkillToken("a@cit", 5, 5), null);
  assert.equal(h.inlineSkillToken("@citation.org", 9, 9), null);
  assert.throws(() => h.inlineSkillReferences("@removed", [], new Set(["removed"])), /no longer available/);
});

test("menu Enter selects once, IME and Shift+Enter do not submit, and Esc closes", async () => {
  const h = await load();
  const events: string[] = [];
  const actions = { select: () => events.push("select"), move: () => events.push("move"), close: () => events.push("close"), submit: () => events.push("submit") };
  const key = (name: string, shift = false, composing = false) => h.handleComposerKey({ key: name, shiftKey: shift, isComposing: composing, preventDefault: () => {} }, { open: true, count: 2, active: 0 }, actions);
  key("Enter"); key("Enter", false, true); key("Enter", true); key("ArrowDown"); key("Escape");
  assert.deepEqual(events, ["select", "move", "close"]);
});
