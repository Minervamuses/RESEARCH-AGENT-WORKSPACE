// Pure scheduling and collapse-state helpers for useDocumentOutline.

import { parseOutline } from "./index.ts";
import type { OutlineDocument } from "./types.ts";

export const OUTLINE_DEBOUNCE_MS = 180;

export interface OutlineSourceInput {
  rootPath: string;
  path: string;
  sourceText: string;
}

export type OutlineUpdatePlan = "noop" | "clear" | "immediate" | "debounce";

export function emptyOutlineDocument(): OutlineDocument {
  return { format: null, sourceText: "", roots: [], flat: [] };
}

/** Decide how to react to a new document snapshot without parsing on cursor-only changes. */
export function planOutlineUpdate(
  previous: OutlineSourceInput | null,
  next: OutlineSourceInput | null,
): OutlineUpdatePlan {
  if (next === null) {
    return previous === null ? "noop" : "clear";
  }
  if (previous === null) {
    return "immediate";
  }
  if (previous.rootPath !== next.rootPath || previous.path !== next.path) {
    return "immediate";
  }
  if (previous.sourceText !== next.sourceText) {
    return "debounce";
  }
  return "noop";
}

/** Retain only collapsed node IDs that still exist in the freshly parsed outline. */
export function pruneCollapsedIds(
  collapsedIds: ReadonlySet<string>,
  outline: OutlineDocument,
): Set<string> {
  if (collapsedIds.size === 0) return new Set();
  const validIds = new Set(outline.flat.map((node) => node.id));
  const kept = new Set<string>();
  for (const id of collapsedIds) {
    if (validIds.has(id)) kept.add(id);
  }
  return kept;
}

/** Toggle one heading's collapsed state immutably. */
export function toggleCollapsedId(collapsedIds: ReadonlySet<string>, id: string): Set<string> {
  const next = new Set(collapsedIds);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return next;
}

/** Parse and reconcile collapse state synchronously (used on file open or stale-click refresh). */
export function recomputeOutline(
  input: OutlineSourceInput | null,
  previousCollapsed: ReadonlySet<string>,
  resetCollapse: boolean,
): { outline: OutlineDocument; collapsedIds: Set<string> } {
  if (input === null) {
    return { outline: emptyOutlineDocument(), collapsedIds: new Set() };
  }
  const outline = parseOutline(input.path, input.sourceText);
  const collapsedIds = resetCollapse ? new Set<string>() : pruneCollapsedIds(previousCollapsed, outline);
  return { outline, collapsedIds };
}
