import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  DEFAULT_EDITOR_FONT_SIZE,
  editorFontOptions,
  editorSuggestionOptions,
  EDITOR_FONT_SIZE_KEY,
  MAX_EDITOR_FONT_SIZE,
  MIN_EDITOR_FONT_SIZE,
  readEditorFontSize,
  writeEditorFontSize,
  zoomedFontSize,
  zoomKeybindings,
  type ZoomStorage,
} from "../src/editorZoom.ts";

function memory(initial: Record<string, string> = {}): ZoomStorage & { values: Record<string, string> } {
  const values = { ...initial };
  return {
    values,
    getItem: (key) => values[key] ?? null,
    setItem: (key, value) => { values[key] = value; },
  };
}

const broken: ZoomStorage = {
  getItem: () => { throw new Error("SecurityError"); },
  setItem: () => { throw new Error("QuotaExceededError"); },
};

test("the editor starts at 16px within a 10–28px range", () => {
  assert.equal(DEFAULT_EDITOR_FONT_SIZE, 16);
  assert.equal(MIN_EDITOR_FONT_SIZE, 10);
  assert.equal(MAX_EDITOR_FONT_SIZE, 28);
  assert.equal(readEditorFontSize(memory()), 16);
  assert.equal(readEditorFontSize(null), 16);
});

test("a remembered size is used only when it is a whole number in range", () => {
  assert.equal(readEditorFontSize(memory({ [EDITOR_FONT_SIZE_KEY]: "20" })), 20);
  assert.equal(readEditorFontSize(memory({ [EDITOR_FONT_SIZE_KEY]: "10" })), 10);
  assert.equal(readEditorFontSize(memory({ [EDITOR_FONT_SIZE_KEY]: "28" })), 28);
  for (const invalid of ["9", "29", "16.5", "abc", "", " 20", "-12", "1e1", "100"]) {
    assert.equal(readEditorFontSize(memory({ [EDITOR_FONT_SIZE_KEY]: invalid })), 16, invalid);
  }
});

test("storage that throws falls back to 16px and never breaks the editor", () => {
  assert.equal(readEditorFontSize(broken), 16);
  assert.doesNotThrow(() => writeEditorFontSize(20, broken));
  assert.doesNotThrow(() => writeEditorFontSize(20, null));
});

test("zoom steps one pixel, stays within 10–28, and resets to 16; the size is remembered", () => {
  assert.equal(zoomedFontSize(16, "in"), 17);
  assert.equal(zoomedFontSize(16, "out"), 15);
  assert.equal(zoomedFontSize(28, "in"), 28);
  assert.equal(zoomedFontSize(10, "out"), 10);
  assert.equal(zoomedFontSize(23, "reset"), 16);
  const storage = memory();
  writeEditorFontSize(zoomedFontSize(16, "in"), storage);
  assert.deepEqual(storage.values, { [EDITOR_FONT_SIZE_KEY]: "17" });
  assert.equal(readEditorFontSize(storage), 17, "a restarted editor reads the zoomed size");
});

test("Monaco derives the line height from the font size at start and after every zoom", () => {
  for (const size of [MIN_EDITOR_FONT_SIZE, DEFAULT_EDITOR_FONT_SIZE, MAX_EDITOR_FONT_SIZE]) {
    assert.deepEqual(editorFontOptions(size), { fontSize: size, lineHeight: 0 });
  }
});

test("zoom steps bind the documented Ctrl/Cmd chords", () => {
  const mod = { CtrlCmd: 0x100, Shift: 0x200 };
  const code = { Equal: 1, NumpadAdd: 2, Minus: 3, NumpadSubtract: 4, Digit0: 5, Numpad0: 6 };
  assert.deepEqual(zoomKeybindings("in", mod, code), [0x101, 0x301, 0x102]);
  assert.deepEqual(zoomKeybindings("out", mod, code), [0x103, 0x104]);
  assert.deepEqual(zoomKeybindings("reset", mod, code), [0x105, 0x106]);
});

test("citation completion disables word suggestions and keeps string quick suggestions active", () => {
  const options = editorSuggestionOptions();
  assert.equal(options.wordBasedSuggestions, "off");
  assert.deepEqual(options.quickSuggestions, { other: "on", comments: "off", strings: "on" });
});

test("the document editor awaits suggestController and applies suggestion options before create", () => {
  const source = readFileSync(new URL("../src/DocumentEditor.tsx", import.meta.url), "utf8");
  const importIndex = source.indexOf('import("monaco-editor/editor/contrib/suggest/browser/suggestController")');
  const createIndex = source.indexOf("monaco.editor.create(");
  assert.ok(importIndex >= 0, "suggestController import missing");
  assert.ok(importIndex < createIndex, "suggestController must load before monaco.editor.create");
  assert.match(source, /\.\.\.editorSuggestionOptions\(\)/);
});
