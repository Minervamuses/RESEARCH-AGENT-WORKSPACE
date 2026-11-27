// Active-section tracking, jump-guard state machine, stale-click resolution,
// and pure editor jump sequence for the document outline.

import { documentPositionAt } from "../documentSource.ts";
import { emptyOutlineDocument } from "./state.ts";
import { normalizeOutlineTitle } from "./tree.ts";
import type { OutlineDocument, OutlineNode } from "./types.ts";

/** Matches Monaco's `editor.ScrollType.Immediate` (1); Smooth is 0. */
export const MONACO_SCROLL_TYPE_IMMEDIATE = 1;

const SCROLL_TOP_EPSILON = 0.5;

export interface ActiveOutlineDisplay {
  /** Direct active heading ID when visible (or null when hidden/none). */
  activeId: string | null;
  /** Nearest visible collapsed ancestor ID when the active heading is hidden inside a collapsed branch. */
  activeAncestorId: string | null;
}

export interface JumpableEditor {
  setPosition(position: { lineNumber: number; column: number }): void;
  revealLineNearTop(lineNumber: number, scrollType: number): void;
  focus(): void;
  getScrollTop(): number;
}

export interface EditorOutlineHandle {
  jumpToOffset(offsetUtf16: number): number | null;
}

export interface OutlineTracker {
  getSnapshot(): string | null;
  subscribe(listener: () => void): () => void;
  setOutline(outline: OutlineDocument): void;
  reset(): void;
  armJump(targetId: string, targetLine: number): void;
  recordJumpScrollTop(scrollTop: number): void;
  cancelJumpGuard(): void;
  reportCursorLine(lineNumber: number): void;
  reportViewport(topLine: number, scrollTop: number): void;
}

/** Binary search on preorder flat headings: returns the last heading with lineNumber <= targetLine. */
export function findActiveHeadingId(flat: readonly OutlineNode[], targetLine: number): string | null {
  if (flat.length === 0 || !Number.isFinite(targetLine) || targetLine < flat[0].lineNumber) {
    return null;
  }
  let lo = 0;
  let hi = flat.length - 1;
  let best = 0;
  while (lo <= hi) {
    const mid = (lo + hi) >>> 1;
    if (flat[mid].lineNumber <= targetLine) {
      best = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return flat[best].id;
}

/**
 * Determine how to highlight `activeId` given `collapsedIds`.
 * If any strict ancestor of `activeId` is collapsed, the highest collapsed ancestor
 * (the nearest ancestor that is actually rendered) receives the ancestor highlight.
 */
export function resolveActiveOutlineDisplay(
  outline: OutlineDocument,
  activeId: string | null,
  collapsedIds: ReadonlySet<string>,
): ActiveOutlineDisplay {
  if (activeId === null || outline.flat.length === 0) {
    return { activeId: null, activeAncestorId: null };
  }
  const byId = new Map<string, OutlineNode>();
  for (const node of outline.flat) byId.set(node.id, node);

  const current = byId.get(activeId);
  if (!current) {
    return { activeId: null, activeAncestorId: null };
  }

  let highestCollapsedAncestor: string | null = null;
  let cursor = current.parentId;
  while (cursor !== null) {
    if (collapsedIds.has(cursor)) {
      highestCollapsedAncestor = cursor;
    }
    cursor = byId.get(cursor)?.parentId ?? null;
  }

  if (highestCollapsedAncestor !== null) {
    return { activeId: null, activeAncestorId: highestCollapsedAncestor };
  }
  return { activeId, activeAncestorId: null };
}

interface JumpGuardState {
  targetId: string;
  targetLine: number;
  expectedScrollTop: number | null;
}

/** External store tracking the active heading ID without re-rendering App on scroll. */
export function createOutlineTracker(initialOutline: OutlineDocument = emptyOutlineDocument()): OutlineTracker {
  let outline: OutlineDocument = initialOutline;
  let activeId: string | null = null;
  let lastCursorLine: number | null = null;
  let lastViewportTopLine: number | null = null;
  let lastSource: "cursor" | "scroll" | null = null;
  let jumpGuard: JumpGuardState | null = null;
  const listeners = new Set<() => void>();

  const setActiveId = (next: string | null) => {
    if (next === activeId) return;
    activeId = next;
    for (const listener of listeners) listener();
  };

  const recomputeFromSaved = () => {
    const line = lastSource === "scroll"
      ? (lastViewportTopLine ?? lastCursorLine)
      : (lastCursorLine ?? lastViewportTopLine);
    if (line === null) {
      setActiveId(null);
      return;
    }
    setActiveId(findActiveHeadingId(outline.flat, line));
  };

  return {
    getSnapshot: () => activeId,

    subscribe: (listener) => {
      listeners.add(listener);
      return () => { listeners.delete(listener); };
    },

    setOutline: (nextOutline) => {
      outline = nextOutline;
      if (jumpGuard !== null) {
        const match = outline.flat.find((node) => node.id === jumpGuard!.targetId);
        if (match) {
          jumpGuard = { ...jumpGuard, targetLine: match.lineNumber };
          setActiveId(match.id);
          return;
        }
        jumpGuard = null;
      }
      recomputeFromSaved();
    },

    reset: () => {
      outline = emptyOutlineDocument();
      lastCursorLine = null;
      lastViewportTopLine = null;
      lastSource = null;
      jumpGuard = null;
      setActiveId(null);
    },

    armJump: (targetId, targetLine) => {
      jumpGuard = { targetId, targetLine, expectedScrollTop: null };
      lastCursorLine = targetLine;
      lastSource = "cursor";
      setActiveId(targetId);
    },

    recordJumpScrollTop: (scrollTop) => {
      if (jumpGuard !== null) {
        jumpGuard = { ...jumpGuard, expectedScrollTop: scrollTop };
      }
    },

    cancelJumpGuard: () => {
      if (jumpGuard === null) return;
      jumpGuard = null;
      recomputeFromSaved();
    },

    reportCursorLine: (lineNumber) => {
      lastCursorLine = lineNumber;
      lastSource = "cursor";
      if (jumpGuard !== null) {
        if (lineNumber === jumpGuard.targetLine) {
          return;
        }
        jumpGuard = null;
      }
      setActiveId(findActiveHeadingId(outline.flat, lineNumber));
    },

    reportViewport: (topLine, scrollTop) => {
      if (jumpGuard !== null) {
        if (
          jumpGuard.expectedScrollTop === null
          || Math.abs(scrollTop - jumpGuard.expectedScrollTop) <= SCROLL_TOP_EPSILON
        ) {
          return;
        }
        jumpGuard = null;
      }
      lastViewportTopLine = topLine;
      lastSource = "scroll";
      setActiveId(findActiveHeadingId(outline.flat, topLine));
    },
  };
}

function isUniquelyIdentifiableChain(outline: OutlineDocument, node: OutlineNode): boolean {
  const byId = new Map<string, OutlineNode>();
  for (const item of outline.flat) byId.set(item.id, item);

  let cursor: OutlineNode | undefined = node;
  while (cursor) {
    const siblings: readonly OutlineNode[] = cursor.parentId === null
      ? outline.roots
      : (byId.get(cursor.parentId)?.children ?? []);
    const normTitle = normalizeOutlineTitle(cursor.title);
    let sameCount = 0;
    for (const sib of siblings) {
      if (sib.level === cursor.level && normalizeOutlineTitle(sib.title) === normTitle) {
        sameCount += 1;
        if (sameCount > 1) return false;
      }
    }
    cursor = cursor.parentId === null ? undefined : byId.get(cursor.parentId);
  }
  return true;
}

export type StaleJumpResolution =
  | { status: "jump"; node: OutlineNode }
  | { status: "refresh-only" };

/**
 * Resolve a click made against an outdated outline after synchronous re-parsing.
 * Only jumps when the ID still exists AND every segment along the root-to-node chain
 * has no same-level, same-title sibling ambiguity in either the old or new tree.
 */
export function resolveOutlineJumpTarget(
  oldOutline: OutlineDocument,
  freshOutline: OutlineDocument,
  clickedNode: OutlineNode,
): StaleJumpResolution {
  const freshNode = freshOutline.flat.find((item) => item.id === clickedNode.id);
  if (!freshNode) return { status: "refresh-only" };
  if (!isUniquelyIdentifiableChain(oldOutline, clickedNode)) return { status: "refresh-only" };
  if (!isUniquelyIdentifiableChain(freshOutline, freshNode)) return { status: "refresh-only" };
  return { status: "jump", node: freshNode };
}

/** Pure jump sequence on an editor-like interface: setPosition -> revealLineNearTop(Immediate) -> focus. */
export function jumpEditorToOffset(
  editor: JumpableEditor,
  sourceText: string,
  offsetUtf16: number,
  scrollTypeImmediate: number = MONACO_SCROLL_TYPE_IMMEDIATE,
): number {
  const position = documentPositionAt(sourceText, offsetUtf16);
  editor.setPosition(position);
  editor.revealLineNearTop(position.lineNumber, scrollTypeImmediate);
  editor.focus();
  return editor.getScrollTop();
}

/** Full outline-click coordinator testable with mock handles and trackers. */
export function performOutlineClick(params: {
  clickedNode: OutlineNode;
  outline: OutlineDocument;
  currentSourceText: string | null;
  refreshOutline: () => OutlineDocument;
  tracker: OutlineTracker;
  handle: EditorOutlineHandle | null;
}): "jumped" | "refreshed" | "ignored" {
  const { clickedNode, outline, currentSourceText, refreshOutline, tracker, handle } = params;
  if (handle === null || currentSourceText === null) return "ignored";

  let target = clickedNode;
  if (outline.sourceText !== currentSourceText) {
    const freshOutline = refreshOutline();
    tracker.setOutline(freshOutline);
    const resolved = resolveOutlineJumpTarget(outline, freshOutline, clickedNode);
    if (resolved.status !== "jump") return "refreshed";
    target = resolved.node;
  }

  tracker.armJump(target.id, target.lineNumber);
  const scrollTop = handle.jumpToOffset(target.startOffsetUtf16);
  if (scrollTop === null) {
    tracker.cancelJumpGuard();
    return "ignored";
  }
  tracker.recordJumpScrollTop(scrollTop);
  return "jumped";
}
