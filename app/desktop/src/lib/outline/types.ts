// Pure types for the document outline tree shared by Markdown and LaTeX parsers.

export type OutlineFormat = "markdown" | "latex";

export interface RawHeading {
  /** Plain display title with inline markup stripped. */
  title: string;
  /** Semantic heading level (Markdown 1..6; LaTeX 0 \part .. 6 \subparagraph). */
  level: number;
  /** 1-based line number of the heading start in sourceText. */
  lineNumber: number;
  /** UTF-16 offset of the heading start in raw sourceText (after leading BOM). */
  startOffsetUtf16: number;
  /** UTF-16 offset immediately after the heading construct in raw sourceText. */
  headingEndOffsetUtf16: number;
}

export interface OutlineNode {
  /** Stable path-based ID: segments of (level, normalizedTitle, siblingOccurrence). */
  id: string;
  title: string;
  level: number;
  /** 0-based visual nesting depth in the built outline tree. */
  depth: number;
  lineNumber: number;
  startOffsetUtf16: number;
  headingEndOffsetUtf16: number;
  /** UTF-16 offset just before the next same-or-higher-level heading, or sourceText.length. */
  sectionEndOffsetUtf16: number;
  parentId: string | null;
  children: OutlineNode[];
}

export interface OutlineDocument {
  format: OutlineFormat | null;
  /** Exact sourceText snapshot this outline was derived from. */
  sourceText: string;
  roots: OutlineNode[];
  /** Preorder flat list matching document order. */
  flat: OutlineNode[];
}
