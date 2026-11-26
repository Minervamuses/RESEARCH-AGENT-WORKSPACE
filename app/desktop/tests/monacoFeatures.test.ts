import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

const features = readFileSync(new URL("../src/monacoFeatures.ts", import.meta.url), "utf8");
const editor = readFileSync(new URL("../src/DocumentEditor.tsx", import.meta.url), "utf8");
const specifiers = [...features.matchAll(/^import "([^"]+)";$/gm)].map((match) => match[1]);

test("the document editor bundles find, the right-click menu with clipboard, editing helpers, hover and folding", () => {
  assert.deepEqual(specifiers.map((specifier) => specifier.replace(/^monaco-editor\/features\/(.+)\/register$/, "$1")), [
    "codicon",
    "contextmenu", "clipboard",
    "find",
    "bracketMatching", "comment", "linesOperations", "multicursor", "wordOperations", "cursorUndo", "smartSelect", "indentation",
    "hover", "folding", "wordHighlighter",
  ]);
});

test("every feature entry resolves to a Monaco module that ships its own type declaration", () => {
  for (const specifier of specifiers) {
    const path = fileURLToPath(import.meta.resolve(specifier));
    assert.doesNotThrow(() => readFileSync(path, "utf8"), `${specifier} has no module`);
    assert.doesNotThrow(() => readFileSync(path.replace(/\.js$/, ".d.ts"), "utf8"), `${specifier} has no .d.ts`);
  }
});

test("the editor waits for the feature contributions before it creates the editor", () => {
  assert.match(editor, /Promise\.all\(\[[^\]]*import\("\.\/monacoFeatures\.ts"\),?\s*\]\)/s);
  assert.ok(editor.indexOf('import("./monacoFeatures.ts")') < editor.indexOf("monaco.editor.create("));
});
