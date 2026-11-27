// Pure WAI-ARIA tree keyboard navigation and roving-tabindex helpers for OutlineView.

import type { OutlineNode } from "./types.ts";

export interface OutlineKeyInput {
  key: string;
  isComposing?: boolean;
  keyCode?: number;
  ctrlKey?: boolean;
  metaKey?: boolean;
  altKey?: boolean;
}

export interface OutlineKeyOutcome {
  /** True when the outline handled the key and the caller should call preventDefault(). */
  handled: boolean;
  nextFocusId: string | null;
  collapseChange: { id: string; collapsed: boolean } | null;
  activateNode: OutlineNode | null;
}

/** Flatten only the currently visible nodes (skipping descendants of collapsed branches) in tree order. */
export function visibleOutlineNodes(
  roots: readonly OutlineNode[],
  collapsedIds: ReadonlySet<string>,
): OutlineNode[] {
  const out: OutlineNode[] = [];
  const visit = (nodes: readonly OutlineNode[]) => {
    for (const node of nodes) {
      out.push(node);
      if (node.children.length > 0 && !collapsedIds.has(node.id)) {
        visit(node.children);
      }
    }
  };
  visit(roots);
  return out;
}

/** Pick the single roving-tabindex node ID among visible nodes (null when empty). */
export function resolveRovingFocusId(
  visibleNodes: readonly OutlineNode[],
  focusedId: string | null,
  preferredActiveId: string | null,
): string | null {
  if (visibleNodes.length === 0) return null;
  if (focusedId !== null && visibleNodes.some((node) => node.id === focusedId)) {
    return focusedId;
  }
  if (preferredActiveId !== null && visibleNodes.some((node) => node.id === preferredActiveId)) {
    return preferredActiveId;
  }
  return visibleNodes[0].id;
}

/** Compute next focus, collapse toggle or jump activation for a key press inside the outline tree. */
export function handleOutlineTreeKey(
  visibleNodes: readonly OutlineNode[],
  collapsedIds: ReadonlySet<string>,
  focusedId: string | null,
  event: OutlineKeyInput,
): OutlineKeyOutcome {
  const noop: OutlineKeyOutcome = {
    handled: false,
    nextFocusId: focusedId,
    collapseChange: null,
    activateNode: null,
  };

  if (
    visibleNodes.length === 0
    || event.isComposing
    || event.keyCode === 229
    || event.ctrlKey
    || event.metaKey
    || event.altKey
  ) {
    return noop;
  }

  const currentIndex = focusedId === null
    ? 0
    : Math.max(0, visibleNodes.findIndex((node) => node.id === focusedId));
  const current = visibleNodes[currentIndex];
  const hasChildren = current.children.length > 0;
  const isCollapsed = hasChildren && collapsedIds.has(current.id);

  switch (event.key) {
    case "ArrowDown": {
      const next = visibleNodes[Math.min(visibleNodes.length - 1, currentIndex + 1)];
      return { handled: true, nextFocusId: next.id, collapseChange: null, activateNode: null };
    }

    case "ArrowUp": {
      const prev = visibleNodes[Math.max(0, currentIndex - 1)];
      return { handled: true, nextFocusId: prev.id, collapseChange: null, activateNode: null };
    }

    case "Home":
      return { handled: true, nextFocusId: visibleNodes[0].id, collapseChange: null, activateNode: null };

    case "End":
      return {
        handled: true,
        nextFocusId: visibleNodes[visibleNodes.length - 1].id,
        collapseChange: null,
        activateNode: null,
      };

    case "ArrowRight": {
      if (!hasChildren) {
        return { handled: true, nextFocusId: current.id, collapseChange: null, activateNode: null };
      }
      if (isCollapsed) {
        return {
          handled: true,
          nextFocusId: current.id,
          collapseChange: { id: current.id, collapsed: false },
          activateNode: null,
        };
      }
      return {
        handled: true,
        nextFocusId: current.children[0].id,
        collapseChange: null,
        activateNode: null,
      };
    }

    case "ArrowLeft": {
      if (hasChildren && !isCollapsed) {
        return {
          handled: true,
          nextFocusId: current.id,
          collapseChange: { id: current.id, collapsed: true },
          activateNode: null,
        };
      }
      if (current.parentId !== null) {
        return { handled: true, nextFocusId: current.parentId, collapseChange: null, activateNode: null };
      }
      return { handled: true, nextFocusId: current.id, collapseChange: null, activateNode: null };
    }

    case "Enter":
      return { handled: true, nextFocusId: current.id, collapseChange: null, activateNode: current };

    default:
      return noop;
  }
}
