// Local Monaco Monarch tokenizer and language configuration for LaTeX (.tex).
// Bundled offline with zero extra dependencies; citation key tokens intentionally
// avoid "string" and "comment" so Monaco quick suggestions keep firing.

import type { languages } from "monaco-editor/editor/editor.api";

export const LATEX_LANGUAGE_ID = "latex";

export type EditorLanguageId = "markdown" | "latex" | "plaintext";

export function editorLanguageForPath(path: string): EditorLanguageId {
  if (/\.(md|markdown)$/i.test(path)) return "markdown";
  if (/\.tex$/i.test(path)) return "latex";
  return "plaintext";
}

export const LATEX_LANGUAGE_CONFIGURATION: languages.LanguageConfiguration = {
  comments: {
    lineComment: "%",
  },
  brackets: [
    ["{", "}"],
    ["[", "]"],
    ["(", ")"],
  ],
  autoClosingPairs: [
    { open: "{", close: "}" },
    { open: "[", close: "]" },
    { open: "(", close: ")" },
    { open: "$", close: "$" },
  ],
  surroundingPairs: [
    { open: "{", close: "}" },
    { open: "[", close: "]" },
    { open: "(", close: ")" },
    { open: "$", close: "$" },
  ],
};

export const LATEX_MONARCH_LANGUAGE: languages.IMonarchLanguage = {
  defaultToken: "",
  tokenPostfix: ".latex",

  tokenizer: {
    root: [
      // Escaped control symbols (e.g. `\%` is literal, not a comment).
      [/\\[%$&_{}#~^\\]/, "constant.character.escape"],

      // Line comments.
      [/%.*$/, "comment"],

      // Math environments enter math state.
      [
        /(\\begin)(\s*)(\{)(equation\*?|align\*?|gather\*?|multline\*?|eqnarray\*?|flalign\*?|alignat\*?|math|displaymath)(\})/,
        ["keyword.control", "", "delimiter.curly", "type.identifier", { token: "delimiter.curly", next: "@mathEnv" }],
      ],

      // General environments.
      [
        /(\\begin|\\end)(\s*)(\{)([A-Za-z0-9*_-]+)(\})/,
        ["keyword.control", "", "delimiter.curly", "type.identifier", "delimiter.curly"],
      ],

      // Sectioning commands.
      [
        /\\(?:part|chapter|section|subsection|subsubsection|paragraph|subparagraph)\*?(?![A-Za-z])/,
        "keyword",
      ],

      // Citation commands: switch into citation states whose tokens never contain "string" or "comment".
      [
        /\\(?:cite|citep|citet|parencite|textcite|autocite|nocite|Cite|Citep|Citet|Parencite|Textcite|Autocite|citealp|citealt|citeauthor|citeyear|footcite|smartcite|supercite)\*?(?![A-Za-z])/,
        { token: "annotation", next: "@citationArgs" },
      ],

      // Cross-reference and label commands.
      [
        /\\(?:ref|eqref|pageref|autoref|cref|Cref|nameref|label)\*?(?![A-Za-z])/,
        { token: "type", next: "@refArgs" },
      ],

      // Display and inline math delimiters.
      [/\$\$/, { token: "number.math", next: "@displayMathDollar" }],
      [/\$/, { token: "number.math", next: "@inlineMathDollar" }],
      [/\\\[/, { token: "number.math", next: "@displayMathBracket" }],
      [/\\\(/, { token: "number.math", next: "@inlineMathParen" }],

      // Generic TeX commands.
      [/\\[A-Za-z@]+/, "tag"],

      // Brackets and delimiters.
      [/[{}]/, "delimiter.curly"],
      [/[\[\]]/, "delimiter.square"],
      [/[()]/, "delimiter.parenthesis"],
    ],

    // Citation optional notes `[...]` and `{key1, key2}`: no token name contains "string" or "comment".
    citationArgs: [
      [/[ \t\r\n]+/, ""],
      [/\[/, { token: "delimiter.square", next: "@citationOptional" }],
      [/\{/, { token: "delimiter.curly", switchTo: "@citationKeys" }],
      [/./, { token: "@rematch", next: "@pop" }],
    ],

    citationOptional: [
      [/\]/, { token: "delimiter.square", next: "@pop" }],
      [/\\[%$&_{}#~^\\]/, "constant.character.escape"],
      [/[^\]\\]+/, "variable"],
      [/\\/, "tag"],
    ],

    citationKeys: [
      [/\}/, { token: "delimiter.curly", next: "@pop" }],
      [/,/, "delimiter"],
      [/[ \t\r\n]+/, ""],
      [/[^,}\s]+/, "identifier"],
    ],

    // Cross-reference target `{sec:intro}`.
    refArgs: [
      [/[ \t\r\n]+/, ""],
      [/\{/, { token: "delimiter.curly", switchTo: "@refKey" }],
      [/./, { token: "@rematch", next: "@pop" }],
    ],

    refKey: [
      [/\}/, { token: "delimiter.curly", next: "@pop" }],
      [/[^}]+/, "variable.name"],
    ],

    inlineMathDollar: [
      [/\$/, { token: "number.math", next: "@pop" }],
      { include: "@mathCommon" },
    ],

    displayMathDollar: [
      [/\$\$/, { token: "number.math", next: "@pop" }],
      { include: "@mathCommon" },
    ],

    inlineMathParen: [
      [/\\\)/, { token: "number.math", next: "@pop" }],
      { include: "@mathCommon" },
    ],

    displayMathBracket: [
      [/\\\]/, { token: "number.math", next: "@pop" }],
      { include: "@mathCommon" },
    ],

    mathEnv: [
      [
        /(\\end)(\s*)(\{)(equation\*?|align\*?|gather\*?|multline\*?|eqnarray\*?|flalign\*?|alignat\*?|math|displaymath)(\})/,
        ["keyword.control", "", "delimiter.curly", "type.identifier", { token: "delimiter.curly", next: "@pop" }],
      ],
      { include: "@mathCommon" },
    ],

    mathCommon: [
      [/\\[%$&_{}#~^\\]/, "constant.character.escape"],
      [/%.*$/, "comment"],
      [/\\[A-Za-z@]+/, "number.math"],
      [/[0-9]+(?:\.[0-9]+)?/, "number"],
      [/[=+\-*/^_&]/, "operator"],
      [/[{}]/, "delimiter.curly"],
      [/[\[\]]/, "delimiter.square"],
      [/[()]/, "delimiter.parenthesis"],
      [/[^\\$%0-9=+\-*/^_&{}[\]()]+/, "number.math"],
    ],
  },
};

export interface MonacoLanguagesRegistrar {
  register(language: { id: string; extensions?: string[]; aliases?: string[] }): void;
  setMonarchTokensProvider(languageId: string, languageDef: languages.IMonarchLanguage): unknown;
  setLanguageConfiguration(languageId: string, configuration: languages.LanguageConfiguration): unknown;
  getLanguages?: () => { id: string }[];
}

const registeredRegistries = new WeakSet<object>();

/** Register the local `latex` language idempotently once per Monaco languages registry. */
export function registerLatexLanguage(monaco: { languages: MonacoLanguagesRegistrar }): boolean {
  const registry = monaco.languages;
  if (registeredRegistries.has(registry)) return false;
  registeredRegistries.add(registry);

  const alreadyKnown = registry.getLanguages?.().some((lang) => lang.id === LATEX_LANGUAGE_ID) ?? false;
  if (!alreadyKnown) {
    registry.register({
      id: LATEX_LANGUAGE_ID,
      extensions: [".tex"],
      aliases: ["LaTeX", "latex", "TeX"],
    });
  }
  registry.setMonarchTokensProvider(LATEX_LANGUAGE_ID, LATEX_MONARCH_LANGUAGE);
  registry.setLanguageConfiguration(LATEX_LANGUAGE_ID, LATEX_LANGUAGE_CONFIGURATION);
  return true;
}
