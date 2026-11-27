// Build a hierarchical outline tree with stable path IDs and section ranges
// from a document-ordered list of raw headings.

import type { OutlineDocument, OutlineFormat, OutlineNode, RawHeading } from "./types.ts";

export function normalizeOutlineTitle(title: string): string {
  return title.trim().replace(/\s+/g, " ").toLowerCase();
}

function makeSegment(level: number, title: string, occurrence: number): string {
  return `${level}:${encodeURIComponent(normalizeOutlineTitle(title))}:${occurrence}`;
}

export function buildOutlineTree(
  headings: readonly RawHeading[],
  sourceText: string,
  format: OutlineFormat | null,
): OutlineDocument {
  const roots: OutlineNode[] = [];
  const flat: OutlineNode[] = [];
  const stack: OutlineNode[] = [];
  const rootCounts = new Map<string, number>();
  const childCounts = new Map<OutlineNode, Map<string, number>>();

  for (const raw of headings) {
    while (stack.length > 0 && stack[stack.length - 1].level >= raw.level) {
      const closed = stack.pop()!;
      closed.sectionEndOffsetUtf16 = Math.max(closed.headingEndOffsetUtf16, raw.startOffsetUtf16);
    }

    const parent = stack.length > 0 ? stack[stack.length - 1] : null;
    let counts: Map<string, number>;
    if (parent === null) {
      counts = rootCounts;
    } else {
      let existing = childCounts.get(parent);
      if (!existing) {
        existing = new Map<string, number>();
        childCounts.set(parent, existing);
      }
      counts = existing;
    }

    const siblingKey = `${raw.level}:${normalizeOutlineTitle(raw.title)}`;
    const occurrence = counts.get(siblingKey) ?? 0;
    counts.set(siblingKey, occurrence + 1);

    const segment = makeSegment(raw.level, raw.title, occurrence);
    const id = parent === null ? segment : `${parent.id}/${segment}`;

    const node: OutlineNode = {
      id,
      title: raw.title,
      level: raw.level,
      depth: stack.length,
      lineNumber: raw.lineNumber,
      startOffsetUtf16: raw.startOffsetUtf16,
      headingEndOffsetUtf16: raw.headingEndOffsetUtf16,
      sectionEndOffsetUtf16: sourceText.length,
      parentId: parent === null ? null : parent.id,
      children: [],
    };

    if (parent === null) {
      roots.push(node);
    } else {
      parent.children.push(node);
    }
    flat.push(node);
    stack.push(node);
  }

  for (const open of stack) {
    open.sectionEndOffsetUtf16 = Math.max(open.headingEndOffsetUtf16, sourceText.length);
  }

  return { format, sourceText, roots, flat };
}
