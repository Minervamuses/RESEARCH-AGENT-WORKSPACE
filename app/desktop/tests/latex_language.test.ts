import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  editorLanguageForPath,
  LATEX_LANGUAGE_CONFIGURATION,
  LATEX_LANGUAGE_ID,
  LATEX_MONARCH_LANGUAGE,
  registerLatexLanguage,
  type MonacoLanguagesRegistrar,
} from "../src/lib/latexLanguage.ts";

function collectTokens(action: unknown, out: string[]): void {
  if (typeof action === "string") {
    out.push(action);
    return;
  }
  if (Array.isArray(action)) {
    for (const entry of action) collectTokens(entry, out);
    return;
  }
  if (action && typeof action === "object") {
    const obj = action as Record<string, unknown>;
    if (typeof obj.token === "string") out.push(obj.token);
    if (obj.cases && typeof obj.cases === "object") {
      for (const value of Object.values(obj.cases as Record<string, unknown>)) {
        collectTokens(value, out);
      }
    }
  }
}

test("editorLanguageForPath maps Markdown, LaTeX and plaintext extensions case-insensitively", () => {
  assert.equal(editorLanguageForPath("chapter.md"), "markdown");
  assert.equal(editorLanguageForPath("README.MARKDOWN"), "markdown");
  assert.equal(editorLanguageForPath("manuscript.tex"), "latex");
  assert.equal(editorLanguageForPath("THESIS.TEX"), "latex");
  assert.equal(editorLanguageForPath("notes.txt"), "plaintext");
});

test("registerLatexLanguage registers once per Monaco registry even when called repeatedly", () => {
  let registerCalls = 0;
  let tokensCalls = 0;
  let configCalls = 0;
  const fakeLanguages: MonacoLanguagesRegistrar = {
    register(language) {
      assert.equal(language.id, LATEX_LANGUAGE_ID);
      registerCalls += 1;
    },
    setMonarchTokensProvider(id) {
      assert.equal(id, LATEX_LANGUAGE_ID);
      tokensCalls += 1;
    },
    setLanguageConfiguration(id) {
      assert.equal(id, LATEX_LANGUAGE_ID);
      configCalls += 1;
    },
    getLanguages: () => [],
  };

  assert.equal(registerLatexLanguage({ languages: fakeLanguages }), true);
  assert.equal(registerLatexLanguage({ languages: fakeLanguages }), false);
  assert.equal(registerLatexLanguage({ languages: fakeLanguages }), false);
  assert.equal(registerCalls, 1);
  assert.equal(tokensCalls, 1);
  assert.equal(configCalls, 1);
});

test("LaTeX Monarch rules compile cleanly and citation argument states never emit string or comment tokens", () => {
  const tokenizer = LATEX_MONARCH_LANGUAGE.tokenizer;
  assert.ok(tokenizer.root && tokenizer.citationArgs && tokenizer.citationOptional && tokenizer.citationKeys);

  // Every regex pattern across all tokenizer states must compile cleanly.
  for (const [stateName, rules] of Object.entries(tokenizer)) {
    for (const rule of rules) {
      if (Array.isArray(rule)) {
        const pattern = rule[0];
        if (pattern instanceof RegExp) {
          assert.doesNotThrow(() => new RegExp(pattern.source, pattern.flags), `${stateName}: ${pattern}`);
        } else if (typeof pattern === "string") {
          assert.doesNotThrow(() => new RegExp(pattern), `${stateName}: ${pattern}`);
        }
      }
    }
  }

  // Citation states must never use any token name containing "string" or "comment"
  // so Monaco quick suggestions remain enabled inside \cite{...}, \citep{...}, \citet{...}, \textcite{...}.
  for (const stateName of ["citationArgs", "citationOptional", "citationKeys"] as const) {
    const tokens: string[] = [];
    for (const rule of tokenizer[stateName]) {
      if (Array.isArray(rule)) collectTokens(rule[1], tokens);
    }
    for (const token of tokens) {
      assert.doesNotMatch(token, /string|comment/i, `forbidden token "${token}" in ${stateName}`);
    }
  }

  // Verify the four required citation commands match the citation command rule in root.
  const citeRule = tokenizer.root.find((rule) => (
    Array.isArray(rule)
    && typeof rule[1] === "object"
    && rule[1] !== null
    && (rule[1] as { next?: string }).next === "@citationArgs"
  ));
  assert.ok(citeRule && Array.isArray(citeRule) && citeRule[0] instanceof RegExp);
  for (const cmd of ["\\cite{", "\\citep{", "\\citet{", "\\textcite{"]) {
    assert.ok(citeRule[0].test(cmd), `${cmd} must enter @citationArgs`);
  }

  // Language configuration sets % line comment and standard bracket pairs.
  assert.equal(LATEX_LANGUAGE_CONFIGURATION.comments?.lineComment, "%");
  assert.ok(LATEX_LANGUAGE_CONFIGURATION.brackets?.some(([open, close]) => open === "{" && close === "}"));
});

test("DocumentEditor registers LaTeX before createModel and binds citation completion to model.getLanguageId()", () => {
  const source = readFileSync(new URL("../src/DocumentEditor.tsx", import.meta.url), "utf8");
  const regIndex = source.indexOf("registerLatexLanguage(monaco)");
  const createModelIndex = source.indexOf("monaco.editor.createModel(");
  assert.ok(regIndex >= 0 && regIndex < createModelIndex, "registerLatexLanguage must run before createModel");
  assert.match(source, /editorLanguageForPath\(initial\.path\)/);
  assert.match(source, /registerCompletionItemProvider\(model\.getLanguageId\(\)/);
});
