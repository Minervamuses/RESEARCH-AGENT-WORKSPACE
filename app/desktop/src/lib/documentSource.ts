import type { IPosition, IRange } from "monaco-editor/editor/editor.api";
import type { DocumentContextDto } from "../protocol.ts";

export interface SourceChange {
  range: IRange;
  text: string;
}

// Monaco columns use UTF-16 units, but its model normalizes newlines and hides a
// leading BOM. Resolve against the source so unrelated bytes survive an edit.
export function documentOffsetAt(source: string, position: IPosition): number {
  let start = source.startsWith("\uFEFF") ? 1 : 0;
  const newline = /\r\n|\r|\n/g;
  newline.lastIndex = start;
  for (let line = 1; line < position.lineNumber; line += 1) {
    const match = newline.exec(source);
    if (!match) return source.length;
    start = match.index + match[0].length;
  }
  newline.lastIndex = start;
  const end = newline.exec(source)?.index ?? source.length;
  return Math.min(end, start + Math.max(0, position.column - 1));
}

export function documentPositionAt(source: string, offset: number): IPosition {
  const target = Math.max(source.startsWith("\uFEFF") ? 1 : 0, Math.min(source.length, offset));
  let start = source.startsWith("\uFEFF") ? 1 : 0;
  let lineNumber = 1;
  const newline = /\r\n|\r|\n/g;
  newline.lastIndex = start;
  for (let match = newline.exec(source); match; match = newline.exec(source)) {
    const next = match.index + match[0].length;
    if (next > target) return { lineNumber, column: Math.min(target, match.index) - start + 1 };
    start = next;
    lineNumber += 1;
  }
  return { lineNumber, column: target - start + 1 };
}

export function applyDocumentChanges(source: string, changes: readonly SourceChange[]): string {
  const edits = changes.map(({ range, text }) => ({
    start: documentOffsetAt(source, { lineNumber: range.startLineNumber, column: range.startColumn }),
    end: documentOffsetAt(source, { lineNumber: range.endLineNumber, column: range.endColumn }),
    text,
  })).sort((left, right) => right.start - left.start);
  return edits.reduce((text, change) => text.slice(0, change.start) + change.text + text.slice(change.end), source);
}

export function captureDocumentSelection(snapshot: DocumentContextDto | null): DocumentContextDto | null {
  if (!snapshot) return null;
  const start = snapshot.rangeStartUtf16;
  const end = snapshot.rangeEndUtf16;
  if (start === undefined || end === undefined || !Number.isInteger(start) || !Number.isInteger(end)
    || start < 0 || start >= end || end > snapshot.sourceText.length) return null;
  // Every field is a string or number; a frozen copy cannot follow later editor changes.
  return Object.freeze({ ...snapshot, rangeStartUtf16: start, rangeEndUtf16: end });
}
