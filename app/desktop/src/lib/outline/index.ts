// Format dispatcher and public exports for the pure document outline module.

import { parseLatexOutline } from "./latex.ts";
import { parseMarkdownOutline } from "./markdown.ts";
import type { OutlineDocument, OutlineFormat } from "./types.ts";

export { parseLatexOutline, scanLatexHeadings, cleanLatexTitle } from "./latex.ts";
export { parseMarkdownOutline, scanMarkdownHeadings, stripMarkdownInline } from "./markdown.ts";
export { buildOutlineTree, normalizeOutlineTitle } from "./tree.ts";
export {
  emptyOutlineDocument,
  OUTLINE_DEBOUNCE_MS,
  planOutlineUpdate,
  pruneCollapsedIds,
  recomputeOutline,
  toggleCollapsedId,
  type OutlineSourceInput,
  type OutlineUpdatePlan,
} from "./state.ts";
export type { OutlineDocument, OutlineFormat, OutlineNode, RawHeading } from "./types.ts";

export function outlineFormatForPath(path: string): OutlineFormat | null {
  const lower = path.toLowerCase();
  if (lower.endsWith(".md") || lower.endsWith(".markdown")) return "markdown";
  if (lower.endsWith(".tex")) return "latex";
  return null;
}

export function parseOutline(path: string, sourceText: string): OutlineDocument {
  const format = outlineFormatForPath(path);
  if (format === "markdown") return parseMarkdownOutline(sourceText);
  if (format === "latex") return parseLatexOutline(sourceText);
  return { format: null, sourceText, roots: [], flat: [] };
}
