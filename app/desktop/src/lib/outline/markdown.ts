// Linear-time Markdown heading scanner following GOALS <解析規格>.

import { buildOutlineTree } from "./tree.ts";
import type { OutlineDocument, RawHeading } from "./types.ts";

interface LineSlice {
  lineNumber: number;
  start: number;
  end: number;
  text: string;
}

const ASCII_PUNCT = new Set(Array.from("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"));

function isAsciiWord(ch: string | undefined): boolean {
  if (!ch) return false;
  const code = ch.charCodeAt(0);
  return (code >= 48 && code <= 57) || (code >= 65 && code <= 90) || (code >= 97 && code <= 122);
}

function isSpaceOrTab(ch: string | undefined): boolean {
  return ch === " " || ch === "\t";
}

function countIndent(line: string): { spaces: number; index: number } {
  let spaces = 0;
  let index = 0;
  while (index < line.length) {
    const ch = line[index];
    if (ch === " ") {
      spaces += 1;
      index += 1;
    } else if (ch === "\t") {
      spaces += 4 - (spaces % 4);
      index += 1;
    } else {
      break;
    }
  }
  return { spaces, index };
}

function isBlank(line: string): boolean {
  for (let i = 0; i < line.length; i += 1) {
    if (line[i] !== " " && line[i] !== "\t") return false;
  }
  return true;
}

function parseFenceOpen(line: string, start: number): { char: "`" | "~"; length: number } | null {
  const ch = line[start];
  if (ch !== "`" && ch !== "~") return null;
  let end = start;
  while (end < line.length && line[end] === ch) end += 1;
  const length = end - start;
  if (length < 3) return null;
  // CommonMark: backtick fence info strings cannot contain backticks.
  if (ch === "`" && line.indexOf("`", end) !== -1) return null;
  return { char: ch, length };
}

function isFenceClose(line: string, start: number, char: "`" | "~", minLength: number): boolean {
  let end = start;
  while (end < line.length && line[end] === char) end += 1;
  if (end - start < minLength) return false;
  for (let i = end; i < line.length; i += 1) {
    if (!isSpaceOrTab(line[i])) return false;
  }
  return true;
}

function isThematicBreak(line: string, start: number): boolean {
  const ch = line[start];
  if (ch !== "-" && ch !== "*" && ch !== "_") return false;
  let count = 0;
  for (let i = start; i < line.length; i += 1) {
    const cur = line[i];
    if (cur === ch) {
      count += 1;
    } else if (!isSpaceOrTab(cur)) {
      return false;
    }
  }
  return count >= 3;
}

function parseSetextUnderline(line: string, start: number): 1 | 2 | null {
  const ch = line[start];
  if (ch !== "=" && ch !== "-") return null;
  let i = start;
  while (i < line.length && line[i] === ch) i += 1;
  while (i < line.length && isSpaceOrTab(line[i])) i += 1;
  if (i !== line.length) return null;
  return ch === "=" ? 1 : 2;
}

/** Match unordered (`- `, `* `, `+ `) or ordered (`1. `, `1) `) list marker; returns content column indent. */
function parseListMarker(line: string, indentSpaces: number, start: number): number | null {
  const ch = line[start];
  if (ch === "-" || ch === "*" || ch === "+") {
    if (start + 1 === line.length) return indentSpaces + 2;
    if (isSpaceOrTab(line[start + 1])) {
      let after = start + 1;
      let extra = 0;
      while (after < line.length && isSpaceOrTab(line[after])) {
        extra += line[after] === "\t" ? 4 - ((indentSpaces + 1 + extra) % 4) : 1;
        after += 1;
      }
      if (after === line.length) return indentSpaces + 2;
      return indentSpaces + 1 + (extra >= 5 ? 1 : extra);
    }
    return null;
  }
  if (ch >= "0" && ch <= "9") {
    let i = start;
    while (i < line.length && line[i] >= "0" && line[i] <= "9" && i - start < 9) i += 1;
    if (i === start || i >= line.length) return null;
    if (line[i] !== "." && line[i] !== ")") return null;
    const markerLen = i - start + 1;
    if (i + 1 === line.length) return indentSpaces + markerLen + 1;
    if (isSpaceOrTab(line[i + 1])) {
      let after = i + 1;
      let extra = 0;
      while (after < line.length && isSpaceOrTab(line[after])) {
        extra += line[after] === "\t" ? 4 - ((indentSpaces + markerLen + extra) % 4) : 1;
        after += 1;
      }
      if (after === line.length) return indentSpaces + markerLen + 1;
      return indentSpaces + markerLen + (extra >= 5 ? 1 : extra);
    }
  }
  return null;
}

function parseAtxHeading(line: string, start: number): { level: number; rawTitle: string } | null {
  if (line[start] !== "#") return null;
  let hashes = 0;
  while (start + hashes < line.length && line[start + hashes] === "#" && hashes <= 7) {
    hashes += 1;
  }
  if (hashes < 1 || hashes > 6) return null;
  const afterHashes = start + hashes;
  if (afterHashes < line.length && !isSpaceOrTab(line[afterHashes])) return null;

  let contentStart = afterHashes;
  while (contentStart < line.length && isSpaceOrTab(line[contentStart])) contentStart += 1;
  let contentEnd = line.length;
  while (contentEnd > contentStart && isSpaceOrTab(line[contentEnd - 1])) contentEnd -= 1;

  // Strip optional closing sequence of `#` preceded by space/tab (or at start of content).
  let trimEnd = contentEnd;
  while (trimEnd > contentStart && line[trimEnd - 1] === "#") trimEnd -= 1;
  if (trimEnd < contentEnd) {
    if (trimEnd === contentStart || isSpaceOrTab(line[trimEnd - 1])) {
      contentEnd = trimEnd;
      while (contentEnd > contentStart && isSpaceOrTab(line[contentEnd - 1])) contentEnd -= 1;
    }
  }

  return { level: hashes, rawTitle: line.slice(contentStart, contentEnd) };
}

/** Update multi-line HTML comment state for one line, ignoring backtick code spans. */
function scanHtmlCommentsInLine(line: string, inComment: boolean): { inComment: boolean; startsWithComment: boolean } {
  let active = inComment;
  let startsWithComment = inComment;
  let i = 0;
  while (i < line.length && isSpaceOrTab(line[i])) i += 1;
  if (!active && line.startsWith("<!--", i)) {
    startsWithComment = true;
  }

  while (i < line.length) {
    if (active) {
      const close = line.indexOf("-->", i);
      if (close === -1) return { inComment: true, startsWithComment };
      active = false;
      i = close + 3;
      continue;
    }
    const ch = line[i];
    if (ch === "\\") {
      i += 2;
      continue;
    }
    if (ch === "`") {
      let ticks = 0;
      while (i + ticks < line.length && line[i + ticks] === "`") ticks += 1;
      const close = findClosingTicks(line, i + ticks, ticks);
      if (close !== -1) {
        i = close + ticks;
        continue;
      }
      i += ticks;
      continue;
    }
    if (line.startsWith("<!--", i)) {
      active = true;
      i += 4;
      continue;
    }
    i += 1;
  }

  return { inComment: active, startsWithComment };
}

function findClosingTicks(text: string, from: number, count: number): number {
  let i = from;
  while (i < text.length) {
    if (text[i] === "`") {
      let run = 0;
      while (i + run < text.length && text[i + run] === "`") run += 1;
      if (run === count) return i;
      i += run;
    } else {
      i += 1;
    }
  }
  return -1;
}

/** Strip inline Markdown formatting markers while preserving plain text in linear time. */
export function stripMarkdownInline(input: string): string {
  const dead = new Set<string>();
  const raw = stripRange(input, 0, input.length, dead);
  return raw.trim().replace(/\s+/g, " ");
}

function stripRange(text: string, start: number, end: number, dead: Set<string>): string {
  let out = "";
  let i = start;

  while (i < end) {
    const ch = text[i];

    // Backslash escape of ASCII punctuation.
    if (ch === "\\" && i + 1 < end && ASCII_PUNCT.has(text[i + 1])) {
      out += text[i + 1];
      i += 2;
      continue;
    }

    // Inline code span.
    if (ch === "`") {
      let ticks = 0;
      while (i + ticks < end && text[i + ticks] === "`") ticks += 1;
      const tickKey = `tick:${ticks}`;
      if (!dead.has(tickKey)) {
        const close = findClosingTicksInRange(text, i + ticks, end, ticks);
        if (close !== -1) {
          let inner = text.slice(i + ticks, close);
          if (inner.length >= 2 && inner.startsWith(" ") && inner.endsWith(" ") && inner.trim().length > 0) {
            inner = inner.slice(1, -1);
          }
          out += inner;
          i = close + ticks;
          continue;
        }
        dead.add(tickKey);
      }
      out += text.slice(i, i + ticks);
      i += ticks;
      continue;
    }

    // Image ![alt](url) or Link [text](url) / [text][ref].
    if ((ch === "!" && i + 1 < end && text[i + 1] === "[") || ch === "[") {
      const bracketStart = ch === "!" ? i + 1 : i;
      if (!dead.has("]")) {
        const bracketEnd = findMatchingBracket(text, bracketStart, end);
        if (bracketEnd !== -1 && bracketEnd + 1 < end) {
          const next = text[bracketEnd + 1];
          if (next === "(") {
            const parenEnd = findMatchingParen(text, bracketEnd + 1, end);
            if (parenEnd !== -1) {
              out += stripRange(text, bracketStart + 1, bracketEnd, dead);
              i = parenEnd + 1;
              continue;
            }
          } else if (next === "[") {
            const refEnd = findMatchingBracket(text, bracketEnd + 1, end);
            if (refEnd !== -1) {
              out += stripRange(text, bracketStart + 1, bracketEnd, dead);
              i = refEnd + 1;
              continue;
            }
          }
        } else if (bracketEnd === -1) {
          dead.add("]");
        }
      }
      out += ch;
      i += 1;
      continue;
    }

    // Strong / Emphasis / Strikethrough delimiters: **, __, ~~, *, _.
    if (ch === "*" || ch === "_" || ch === "~") {
      const doubled = i + 1 < end && text[i + 1] === ch;
      if (ch === "~" && !doubled) {
        out += ch;
        i += 1;
        continue;
      }
      const delim = doubled ? ch + ch : ch;
      const prevCh = i > start ? text[i - 1] : undefined;
      const nextCh = i + delim.length < end ? text[i + delim.length] : undefined;
      const canOpen = nextCh !== undefined && !isSpaceOrTab(nextCh)
        && (ch !== "_" || !isAsciiWord(prevCh));

      if (canOpen && !dead.has(delim)) {
        const close = findClosingDelimiter(text, i + delim.length, end, delim, ch === "_");
        if (close !== -1) {
          out += stripRange(text, i + delim.length, close, dead);
          i = close + delim.length;
          continue;
        }
        dead.add(delim);
      }
      out += ch;
      i += 1;
      continue;
    }

    out += ch;
    i += 1;
  }

  return out;
}

function findClosingTicksInRange(text: string, from: number, end: number, count: number): number {
  let i = from;
  while (i < end) {
    if (text[i] === "`") {
      let run = 0;
      while (i + run < end && text[i + run] === "`") run += 1;
      if (run === count) return i;
      i += run;
    } else {
      i += 1;
    }
  }
  return -1;
}

function findMatchingBracket(text: string, openPos: number, end: number): number {
  let depth = 0;
  let i = openPos;
  while (i < end) {
    const ch = text[i];
    if (ch === "\\" && i + 1 < end) {
      i += 2;
      continue;
    }
    if (ch === "`") {
      let ticks = 0;
      while (i + ticks < end && text[i + ticks] === "`") ticks += 1;
      const close = findClosingTicksInRange(text, i + ticks, end, ticks);
      if (close !== -1) {
        i = close + ticks;
        continue;
      }
      i += ticks;
      continue;
    }
    if (ch === "[") depth += 1;
    else if (ch === "]") {
      depth -= 1;
      if (depth === 0) return i;
    }
    i += 1;
  }
  return -1;
}

function findMatchingParen(text: string, openPos: number, end: number): number {
  let depth = 0;
  let i = openPos;
  while (i < end) {
    const ch = text[i];
    if (ch === "\\" && i + 1 < end) {
      i += 2;
      continue;
    }
    if (ch === "(") depth += 1;
    else if (ch === ")") {
      depth -= 1;
      if (depth === 0) return i;
    }
    i += 1;
  }
  return -1;
}

function findClosingDelimiter(
  text: string,
  from: number,
  end: number,
  delim: string,
  wordBoundary: boolean,
): number {
  const len = delim.length;
  let i = from;
  while (i + len <= end) {
    const ch = text[i];
    if (ch === "\\" && i + 1 < end) {
      i += 2;
      continue;
    }
    if (ch === "`") {
      let ticks = 0;
      while (i + ticks < end && text[i + ticks] === "`") ticks += 1;
      const close = findClosingTicksInRange(text, i + ticks, end, ticks);
      if (close !== -1) {
        i = close + ticks;
        continue;
      }
      i += ticks;
      continue;
    }
    if (text.startsWith(delim, i)) {
      const prevCh = i > from ? text[i - 1] : undefined;
      const nextCh = i + len < end ? text[i + len] : undefined;
      const canClose = i > from && prevCh !== undefined && !isSpaceOrTab(prevCh)
        && (!wordBoundary || !isAsciiWord(nextCh));
      if (canClose) return i;
    }
    i += 1;
  }
  return -1;
}

function* iterateLines(sourceText: string): Generator<LineSlice> {
  const len = sourceText.length;
  let pos = sourceText.startsWith("\uFEFF") ? 1 : 0;
  let lineNumber = 1;

  while (pos < len) {
    let i = pos;
    while (i < len && sourceText[i] !== "\n" && sourceText[i] !== "\r") i += 1;
    const end = i;
    yield { lineNumber, start: pos, end, text: sourceText.slice(pos, end) };
    if (i < len) {
      pos = sourceText[i] === "\r" && sourceText[i + 1] === "\n" ? i + 2 : i + 1;
    } else {
      pos = len;
    }
    lineNumber += 1;
  }
}

function isYamlDelimiter(line: string, allowDots: boolean): boolean {
  const marker = line.startsWith("---") ? "---" : (allowDots && line.startsWith("...") ? "..." : null);
  if (!marker) return false;
  for (let i = 3; i < line.length; i += 1) {
    if (!isSpaceOrTab(line[i])) return false;
  }
  return true;
}

/** Find the 1-based closing line number of YAML front matter, or 0 if none. */
function findYamlFrontMatterEndLine(sourceText: string): number {
  let first = true;
  for (const line of iterateLines(sourceText)) {
    if (first) {
      first = false;
      if (!isYamlDelimiter(line.text, false)) return 0;
      continue;
    }
    if (isYamlDelimiter(line.text, true)) return line.lineNumber;
  }
  return 0;
}

export function scanMarkdownHeadings(sourceText: string): RawHeading[] {
  const headings: RawHeading[] = [];
  const yamlEndLine = findYamlFrontMatterEndLine(sourceText);

  let fence: { char: "`" | "~"; length: number; listBound: number | null } | null = null;
  let inHtmlComment = false;
  let listIndent: number | null = null;
  let paragraph: { lineNumber: number; startOffset: number; lines: string[] } | null = null;

  for (const line of iterateLines(sourceText)) {
    if (line.lineNumber <= yamlEndLine) continue;

    if (isBlank(line.text)) {
      paragraph = null;
      continue;
    }

    const { spaces, index } = countIndent(line.text);

    // Inside a fenced code block: ignore everything until matching closing fence.
    if (fence !== null) {
      if (fence.listBound !== null && spaces < fence.listBound) {
        // List item ended before closing fence.
        fence = null;
        listIndent = null;
      } else {
        const relIndent = fence.listBound !== null ? spaces - fence.listBound : spaces;
        if (relIndent <= 3 && isFenceClose(line.text, index, fence.char, fence.length)) {
          fence = null;
        }
        continue;
      }
    }

    // Inside a multi-line HTML comment: wait for `-->`.
    if (inHtmlComment) {
      const scan = scanHtmlCommentsInLine(line.text, true);
      inHtmlComment = scan.inComment;
      paragraph = null;
      continue;
    }

    // Check list continuation boundary.
    if (listIndent !== null) {
      if (spaces >= listIndent) {
        paragraph = null;
        // Track fenced code blocks nested inside list items.
        const relSpaces = spaces - listIndent;
        if (relSpaces <= 3) {
          const opened = parseFenceOpen(line.text, index);
          if (opened) {
            fence = { ...opened, listBound: listIndent };
            continue;
          }
        }
        const scan = scanHtmlCommentsInLine(line.text, false);
        inHtmlComment = scan.inComment;
        continue;
      }
      listIndent = null;
    }

    // Indented code block (>= 4 spaces or tab when not continuing a paragraph).
    if (spaces >= 4) {
      if (paragraph === null) {
        continue;
      }
      // Lazy paragraph continuation cannot be a Setext underline or ATX heading; append text.
      const scan = scanHtmlCommentsInLine(line.text, false);
      inHtmlComment = scan.inComment;
      paragraph.lines.push(line.text.slice(index));
      continue;
    }

    // Setext heading underline (must check before thematic break / list marker because `---`).
    if (paragraph !== null) {
      const setextLevel = parseSetextUnderline(line.text, index);
      if (setextLevel !== null) {
        const title = stripMarkdownInline(paragraph.lines.join(" "));
        if (title.length > 0) {
          headings.push({
            title,
            level: setextLevel,
            lineNumber: paragraph.lineNumber,
            startOffsetUtf16: paragraph.startOffset,
            headingEndOffsetUtf16: line.end,
          });
        }
        paragraph = null;
        continue;
      }
    }

    // Opening fenced code block.
    const openedFence = parseFenceOpen(line.text, index);
    if (openedFence !== null) {
      fence = { ...openedFence, listBound: null };
      paragraph = null;
      continue;
    }

    // ATX heading.
    const atx = parseAtxHeading(line.text, index);
    if (atx !== null) {
      const title = stripMarkdownInline(atx.rawTitle);
      if (title.length > 0) {
        headings.push({
          title,
          level: atx.level,
          lineNumber: line.lineNumber,
          startOffsetUtf16: line.start + index,
          headingEndOffsetUtf16: line.end,
        });
      }
      paragraph = null;
      continue;
    }

    // Blockquote: ignore headings inside blockquotes.
    if (line.text[index] === ">") {
      paragraph = null;
      continue;
    }

    // Thematic break (`---`, `***`, `___`, `- - -`): never a heading or list item.
    if (isThematicBreak(line.text, index)) {
      paragraph = null;
      continue;
    }

    // List item: ignore headings on this line and indented continuation lines.
    const markerContentIndent = parseListMarker(line.text, spaces, index);
    if (markerContentIndent !== null) {
      listIndent = markerContentIndent;
      paragraph = null;
      const scan = scanHtmlCommentsInLine(line.text, false);
      inHtmlComment = scan.inComment;
      continue;
    }

    // HTML comment starting on this line or spanning multiple lines.
    const commentScan = scanHtmlCommentsInLine(line.text, false);
    if (commentScan.inComment) {
      inHtmlComment = true;
      paragraph = null;
      continue;
    }
    if (commentScan.startsWithComment) {
      paragraph = null;
      continue;
    }

    // Normal paragraph line (candidate for a Setext heading if followed by === or ---).
    if (paragraph === null) {
      paragraph = {
        lineNumber: line.lineNumber,
        startOffset: line.start + index,
        lines: [line.text.slice(index)],
      };
    } else {
      paragraph.lines.push(line.text.slice(index));
    }
  }

  return headings;
}

export function parseMarkdownOutline(sourceText: string): OutlineDocument {
  return buildOutlineTree(scanMarkdownHeadings(sourceText), sourceText, "markdown");
}
