// Linear-time LaTeX sectioning scanner following GOALS <解析規格>.

import { buildOutlineTree } from "./tree.ts";
import type { OutlineDocument, RawHeading } from "./types.ts";

const SECTION_LEVELS: Readonly<Record<string, number>> = {
  part: 0,
  chapter: 1,
  section: 2,
  subsection: 3,
  subsubsection: 4,
  paragraph: 5,
  subparagraph: 6,
};

const VERBATIM_ENVS = new Set(["verbatim", "verbatim*", "lstlisting", "minted", "comment"]);

const NEWCOMMAND_MACROS = new Set(["newcommand", "renewcommand", "providecommand"]);
const DEF_MACROS = new Set(["def", "gdef", "edef", "xdef"]);

const INLINE_TEXT_COMMANDS = new Set([
  "textbf", "textit", "emph", "texttt", "textrm", "textsf", "textsc", "textsl",
  "textmd", "textup", "textnormal", "underline", "text", "mbox", "hbox",
  "mathrm", "mathbf", "mathit", "mathcal", "mathsf", "mathtt", "mathbb",
  "mathfrak", "operatorname", "ensuremath", "MakeUppercase", "MakeLowercase",
]);

const STRIP_ARG_COMMANDS = new Set(["label", "index", "footnote", "protect"]);

function isAsciiLetter(ch: string | undefined): boolean {
  if (!ch) return false;
  const code = ch.charCodeAt(0);
  return (code >= 65 && code <= 90) || (code >= 97 && code <= 122);
}

interface Cursor {
  pos: number;
  line: number;
}

function advanceChar(source: string, cursor: Cursor): void {
  const ch = source[cursor.pos];
  if (ch === "\r") {
    cursor.pos += source[cursor.pos + 1] === "\n" ? 2 : 1;
    cursor.line += 1;
  } else if (ch === "\n") {
    cursor.pos += 1;
    cursor.line += 1;
  } else {
    cursor.pos += 1;
  }
}

function skipCommentToEol(source: string, cursor: Cursor): void {
  const len = source.length;
  while (cursor.pos < len && source[cursor.pos] !== "\n" && source[cursor.pos] !== "\r") {
    cursor.pos += 1;
  }
}

function skipSpaceAndComments(source: string, cursor: Cursor): void {
  const len = source.length;
  while (cursor.pos < len) {
    const ch = source[cursor.pos];
    if (ch === " " || ch === "\t" || ch === "\n" || ch === "\r") {
      advanceChar(source, cursor);
    } else if (ch === "%") {
      skipCommentToEol(source, cursor);
    } else {
      break;
    }
  }
}

function readControlWord(source: string, startAfterBackslash: number): string {
  let end = startAfterBackslash;
  while (end < source.length && isAsciiLetter(source[end])) end += 1;
  return source.slice(startAfterBackslash, end);
}

/** Skip a `{...}` group starting at `source[cursor.pos] === "{"`. Returns content bounds or null if unclosed. */
function readBalancedGroup(source: string, cursor: Cursor): { innerStart: number; innerEnd: number; endPos: number } | null {
  const len = source.length;
  if (cursor.pos >= len || source[cursor.pos] !== "{") return null;
  const innerStart = cursor.pos + 1;
  cursor.pos += 1;
  let depth = 1;

  while (cursor.pos < len) {
    const ch = source[cursor.pos];
    if (ch === "\\") {
      cursor.pos += 1;
      if (cursor.pos < len) {
        if (isAsciiLetter(source[cursor.pos])) {
          const cmd = readControlWord(source, cursor.pos);
          cursor.pos += cmd.length;
          if (cmd === "verb") skipVerbPayload(source, cursor);
        } else {
          advanceChar(source, cursor);
        }
      }
      continue;
    }
    if (ch === "%") {
      skipCommentToEol(source, cursor);
      continue;
    }
    if (ch === "{") {
      depth += 1;
      cursor.pos += 1;
      continue;
    }
    if (ch === "}") {
      depth -= 1;
      const closePos = cursor.pos;
      cursor.pos += 1;
      if (depth === 0) {
        return { innerStart, innerEnd: closePos, endPos: cursor.pos };
      }
      continue;
    }
    advanceChar(source, cursor);
  }

  return null;
}

/** Skip an optional `[...]` argument starting at `source[cursor.pos] === "["`. Returns true if closed. */
function skipOptionalBracket(source: string, cursor: Cursor): boolean {
  const len = source.length;
  if (cursor.pos >= len || source[cursor.pos] !== "[") return false;
  cursor.pos += 1;
  let braceDepth = 0;

  while (cursor.pos < len) {
    const ch = source[cursor.pos];
    if (ch === "\\") {
      cursor.pos += 1;
      if (cursor.pos < len) {
        if (isAsciiLetter(source[cursor.pos])) {
          const cmd = readControlWord(source, cursor.pos);
          cursor.pos += cmd.length;
          if (cmd === "verb") skipVerbPayload(source, cursor);
        } else {
          advanceChar(source, cursor);
        }
      }
      continue;
    }
    if (ch === "%") {
      skipCommentToEol(source, cursor);
      continue;
    }
    if (ch === "{") {
      braceDepth += 1;
      cursor.pos += 1;
      continue;
    }
    if (ch === "}" && braceDepth > 0) {
      braceDepth -= 1;
      cursor.pos += 1;
      continue;
    }
    if (ch === "]" && braceDepth === 0) {
      cursor.pos += 1;
      return true;
    }
    advanceChar(source, cursor);
  }
  return false;
}

/** Skip `\verb` / `\verb*` delimiter and body on the current line. */
function skipVerbPayload(source: string, cursor: Cursor): void {
  const len = source.length;
  if (cursor.pos < len && source[cursor.pos] === "*") cursor.pos += 1;
  if (cursor.pos >= len) return;
  const delim = source[cursor.pos];
  if (delim === "\n" || delim === "\r") return;
  cursor.pos += 1;
  while (cursor.pos < len) {
    const ch = source[cursor.pos];
    if (ch === delim) {
      cursor.pos += 1;
      return;
    }
    if (ch === "\n" || ch === "\r") return;
    cursor.pos += 1;
  }
}

/** Skip verbatim-like environment body until literal `\end{envName}` or EOF. */
function skipVerbatimEnvironment(source: string, cursor: Cursor, envName: string): void {
  const endMarker = `\\end{${envName}}`;
  const idx = source.indexOf(endMarker, cursor.pos);
  const target = idx === -1 ? source.length : idx + endMarker.length;
  while (cursor.pos < target) {
    advanceChar(source, cursor);
  }
}

/** Skip `\newcommand`, `\renewcommand`, `\providecommand` definition body so inner section commands are ignored. */
function skipNewCommand(source: string, cursor: Cursor): void {
  skipSpaceAndComments(source, cursor);
  if (cursor.pos < source.length && source[cursor.pos] === "*") {
    cursor.pos += 1;
    skipSpaceAndComments(source, cursor);
  }
  if (cursor.pos >= source.length) return;
  // Macro name: either `{\foo}` or `\foo`.
  if (source[cursor.pos] === "{") {
    if (!readBalancedGroup(source, cursor)) return;
  } else if (source[cursor.pos] === "\\") {
    cursor.pos += 1;
    if (cursor.pos < source.length) {
      if (isAsciiLetter(source[cursor.pos])) {
        cursor.pos += readControlWord(source, cursor.pos).length;
      } else {
        advanceChar(source, cursor);
      }
    }
  } else {
    return;
  }
  // Up to two optional `[...]` arguments (`[argc]` and `[default]`).
  skipSpaceAndComments(source, cursor);
  if (cursor.pos < source.length && source[cursor.pos] === "[") {
    if (!skipOptionalBracket(source, cursor)) return;
    skipSpaceAndComments(source, cursor);
    if (cursor.pos < source.length && source[cursor.pos] === "[") {
      if (!skipOptionalBracket(source, cursor)) return;
    }
  }
  skipSpaceAndComments(source, cursor);
  if (cursor.pos < source.length && source[cursor.pos] === "{") {
    readBalancedGroup(source, cursor);
  }
}

/** Skip `\def` / `\gdef` / `\edef` / `\xdef` macro name, parameter text and `{replacement}`. */
function skipTeXDef(source: string, cursor: Cursor): void {
  skipSpaceAndComments(source, cursor);
  if (cursor.pos < source.length && source[cursor.pos] === "\\") {
    cursor.pos += 1;
    if (cursor.pos < source.length) {
      if (isAsciiLetter(source[cursor.pos])) {
        cursor.pos += readControlWord(source, cursor.pos).length;
      } else {
        advanceChar(source, cursor);
      }
    }
  }
  // Scan parameter text up to `{`.
  while (cursor.pos < source.length) {
    const ch = source[cursor.pos];
    if (ch === "{") {
      readBalancedGroup(source, cursor);
      return;
    }
    if (ch === "%") {
      skipCommentToEol(source, cursor);
      continue;
    }
    if (ch === "\\") {
      cursor.pos += 1;
      if (cursor.pos < source.length) {
        if (isAsciiLetter(source[cursor.pos])) {
          cursor.pos += readControlWord(source, cursor.pos).length;
        } else {
          advanceChar(source, cursor);
        }
      }
      continue;
    }
    advanceChar(source, cursor);
  }
}

/** Clean inline LaTeX formatting inside a heading title into readable plain text. */
export function cleanLatexTitle(raw: string): string {
  const out = cleanRange(raw, 0, raw.length);
  return out.trim().replace(/\s+/g, " ");
}

function cleanRange(text: string, start: number, end: number): string {
  let out = "";
  let i = start;

  while (i < end) {
    const ch = text[i];

    // Comments inside multi-line titles.
    if (ch === "%") {
      while (i < end && text[i] !== "\n" && text[i] !== "\r") i += 1;
      continue;
    }

    // Non-breaking space.
    if (ch === "~") {
      out += " ";
      i += 1;
      continue;
    }

    // Nested bare braces `{...}`: unwrap their text.
    if (ch === "{") {
      const subCursor: Cursor = { pos: i, line: 1 };
      const group = readBalancedGroup(text, subCursor);
      if (group && group.endPos <= end) {
        out += cleanRange(text, group.innerStart, group.innerEnd);
        i = group.endPos;
        continue;
      }
      i += 1;
      continue;
    }

    if (ch === "}") {
      i += 1;
      continue;
    }

    if (ch === "\\") {
      if (i + 1 >= end) break;
      const next = text[i + 1];
      if (!isAsciiLetter(next)) {
        // Control symbol: `\\` -> space, `\,`/`\ ` -> space, `\%`/`\&`/`\_`/`\#`/`\$`/`\{`/`\}` -> literal.
        if (next === "\\" || next === " " || next === "," || next === ";" || next === ":" || next === "!") {
          out += " ";
        } else if (next === "-" || next === "/") {
          // Discretionary hyphen `\-` or italic correction `\/`: omit.
        } else {
          out += next;
        }
        i += 2;
        continue;
      }

      const cmd = readControlWord(text, i + 1);
      const afterCmd = i + 1 + cmd.length;

      if (cmd === "texorpdfstring") {
        const subCursor: Cursor = { pos: afterCmd, line: 1 };
        skipSpaceAndComments(text, subCursor);
        const first = readBalancedGroup(text, subCursor);
        if (first && first.endPos <= end) {
          skipSpaceAndComments(text, subCursor);
          const second = readBalancedGroup(text, subCursor);
          if (second && second.endPos <= end) {
            out += cleanRange(text, first.innerStart, first.innerEnd);
            i = second.endPos;
            continue;
          }
        }
      }

      if (INLINE_TEXT_COMMANDS.has(cmd)) {
        const subCursor: Cursor = { pos: afterCmd, line: 1 };
        skipSpaceAndComments(text, subCursor);
        const group = readBalancedGroup(text, subCursor);
        if (group && group.endPos <= end) {
          out += cleanRange(text, group.innerStart, group.innerEnd);
          i = group.endPos;
          continue;
        }
      }

      if (STRIP_ARG_COMMANDS.has(cmd)) {
        const subCursor: Cursor = { pos: afterCmd, line: 1 };
        if (cmd === "protect") {
          i = afterCmd;
          continue;
        }
        skipSpaceAndComments(text, subCursor);
        const group = readBalancedGroup(text, subCursor);
        if (group && group.endPos <= end) {
          i = group.endPos;
          continue;
        }
      }

      // Preserve unknown control sequences (e.g. `\LaTeX`, `\alpha`) as text.
      out += "\\" + cmd;
      i = afterCmd;
      continue;
    }

    out += ch;
    i += 1;
  }

  return out;
}

export function scanLatexHeadings(sourceText: string): RawHeading[] {
  const headings: RawHeading[] = [];
  const len = sourceText.length;
  const cursor: Cursor = {
    pos: sourceText.startsWith("\uFEFF") ? 1 : 0,
    line: 1,
  };

  while (cursor.pos < len) {
    const ch = sourceText[cursor.pos];

    if (ch === "%") {
      skipCommentToEol(sourceText, cursor);
      continue;
    }

    if (ch !== "\\") {
      advanceChar(sourceText, cursor);
      continue;
    }

    const cmdStart = cursor.pos;
    const cmdLine = cursor.line;
    cursor.pos += 1;
    if (cursor.pos >= len) break;

    if (!isAsciiLetter(sourceText[cursor.pos])) {
      // Escaped control symbol such as `\%`, `\\`, `\{`, `\}`.
      advanceChar(sourceText, cursor);
      continue;
    }

    const cmd = readControlWord(sourceText, cursor.pos);
    cursor.pos += cmd.length;

    if (cmd === "verb") {
      skipVerbPayload(sourceText, cursor);
      continue;
    }

    if (cmd === "begin") {
      const saved: Cursor = { pos: cursor.pos, line: cursor.line };
      skipSpaceAndComments(sourceText, cursor);
      const envGroup = readBalancedGroup(sourceText, cursor);
      if (envGroup) {
        const envName = sourceText.slice(envGroup.innerStart, envGroup.innerEnd).trim();
        if (VERBATIM_ENVS.has(envName)) {
          skipVerbatimEnvironment(sourceText, cursor, envName);
        }
      } else {
        cursor.pos = saved.pos;
        cursor.line = saved.line;
      }
      continue;
    }

    if (NEWCOMMAND_MACROS.has(cmd)) {
      skipNewCommand(sourceText, cursor);
      continue;
    }

    if (DEF_MACROS.has(cmd)) {
      skipTeXDef(sourceText, cursor);
      continue;
    }

    const level = SECTION_LEVELS[cmd];
    if (level === undefined) continue;

    // Parse optional `*`, optional `[short title]`, and mandatory `{full title}`.
    skipSpaceAndComments(sourceText, cursor);
    if (cursor.pos < len && sourceText[cursor.pos] === "*") {
      cursor.pos += 1;
      skipSpaceAndComments(sourceText, cursor);
    }
    if (cursor.pos < len && sourceText[cursor.pos] === "[") {
      if (!skipOptionalBracket(sourceText, cursor)) {
        // Incomplete optional argument reaches EOF; stop without emitting.
        break;
      }
      skipSpaceAndComments(sourceText, cursor);
    }
    if (cursor.pos < len && sourceText[cursor.pos] === "{") {
      const titleGroup = readBalancedGroup(sourceText, cursor);
      if (!titleGroup) {
        // Incomplete `{title` reaches EOF; keep all prior headings intact.
        break;
      }
      const title = cleanLatexTitle(sourceText.slice(titleGroup.innerStart, titleGroup.innerEnd));
      if (title.length > 0) {
        headings.push({
          title,
          level,
          lineNumber: cmdLine,
          startOffsetUtf16: cmdStart,
          headingEndOffsetUtf16: titleGroup.endPos,
        });
      }
    }
  }

  return headings;
}

export function parseLatexOutline(sourceText: string): OutlineDocument {
  return buildOutlineTree(scanLatexHeadings(sourceText), sourceText, "latex");
}
