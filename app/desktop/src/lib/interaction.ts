/**
 * Focus and key decisions shared by dialogs and menus. Everything here is a pure
 * function over plain values; the DOM glue lives in `components/Modal.tsx` and
 * `hooks/useDisclosureMenu.ts`. Differences in meaning (what closes a dialog, where
 * focus returns) stay with each caller.
 */

export interface DialogKeyPolicy {
  /** Esc dismisses the dialog only while this is true (false while a request is in flight). */
  dismissible: boolean;
  /** Tab wraps inside the dialog; false for a non-modal dialog that must leave Tab alone. */
  trapTab: boolean;
  /** With no enabled control, Tab is swallowed instead of leaving the dialog. */
  blockEmptyTab: boolean;
  /** Esc is consumed even when it cannot dismiss (the approval dialog never lets Esc leak). */
  preventEscapeWhenBlocked: boolean;
}

export interface DialogKeyDecision {
  preventDefault: boolean;
  dismiss: boolean;
  /** Which control receives focus; `null` leaves focus where the browser puts it. */
  focus: "first" | "last" | null;
}

const NONE: DialogKeyDecision = { preventDefault: false, dismiss: false, focus: null };

/** `activeIndex` is the focused control's index among the enabled controls, or -1 when focus is elsewhere. */
export function dialogKeyDecision(
  key: string, shiftKey: boolean, activeIndex: number, controlCount: number, policy: DialogKeyPolicy,
): DialogKeyDecision {
  if (key === "Escape") {
    if (policy.dismissible) return { preventDefault: true, dismiss: true, focus: null };
    return policy.preventEscapeWhenBlocked ? { preventDefault: true, dismiss: false, focus: null } : NONE;
  }
  if (key !== "Tab" || !policy.trapTab) return NONE;
  if (controlCount === 0) return policy.blockEmptyTab ? { preventDefault: true, dismiss: false, focus: null } : NONE;
  if (shiftKey && activeIndex === 0) return { preventDefault: true, dismiss: false, focus: "last" };
  if (!shiftKey && activeIndex === controlCount - 1) return { preventDefault: true, dismiss: false, focus: "first" };
  return NONE;
}

/** Focus moved outside the menu container (or to nothing): the menu closes. */
export function focusLeftContainer(container: { contains(node: Node | null): boolean }, next: Node | null): boolean {
  return !container.contains(next);
}

/** Esc closes an open menu. `tabCloses` is for the context menu, which has no tab stops of its own. */
export function menuShouldClose(key: string, open: boolean, tabCloses = false): boolean {
  return open && (key === "Escape" || (tabCloses && key === "Tab"));
}

/**
 * The item to focus after a navigation key (-1 when the menu has no items), or `null` for any other key. Moves wrap.
 * `homeEnd` enables Home/End for menus that offer them.
 */
export function menuNextIndex(key: string, current: number, count: number, homeEnd: boolean): number | null {
  const forward = key === "ArrowDown", backward = key === "ArrowUp";
  const home = homeEnd && key === "Home", end = homeEnd && key === "End";
  if (!forward && !backward && !home && !end) return null;
  if (count === 0) return -1; // a navigation key with nothing to focus is still consumed
  if (home) return 0;
  if (end) return count - 1;
  return (current + (forward ? 1 : -1) + count) % count;
}
