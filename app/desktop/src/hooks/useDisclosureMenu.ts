import { useEffect, useRef, useState, type FocusEvent, type KeyboardEvent, type RefObject } from "react";

import { focusLeftContainer, menuShouldClose } from "../lib/interaction.ts";

export interface DisclosureMenu<M extends HTMLElement> {
  open: boolean;
  setOpen: (open: boolean) => void;
  /** Close and hand focus back to the trigger (item chosen or Esc). */
  close: () => void;
  triggerRef: RefObject<HTMLButtonElement | null>;
  menuRef: RefObject<M | null>;
  /** Spread on the element wrapping trigger and menu: blur outside closes, Esc closes with focus return. */
  containerProps: {
    onBlur: (event: FocusEvent<HTMLElement>) => void;
    onKeyDown: (event: KeyboardEvent<HTMLElement>) => void;
  };
}

/**
 * Trigger-plus-popup behaviour shared by ThinkingControl and ExportMenu: a disabled menu is
 * closed, opening focuses `initialFocus` inside the popup, blur outside closes, Esc closes and
 * focuses the trigger. Item keys, labels and roles stay with each menu.
 */
export function useDisclosureMenu<M extends HTMLElement>(disabled: boolean, initialFocus: string): DisclosureMenu<M> {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<M>(null);
  useEffect(() => {
    if (disabled) setOpen(false);
    else if (open) menuRef.current?.querySelector<HTMLElement>(initialFocus)?.focus();
  }, [disabled, open, initialFocus]);
  const close = () => { setOpen(false); triggerRef.current?.focus(); };
  return {
    open, setOpen, close, triggerRef, menuRef,
    containerProps: {
      onBlur: (event) => {
        if (focusLeftContainer(event.currentTarget, event.relatedTarget as Node | null)) setOpen(false);
      },
      onKeyDown: (event) => {
        if (menuShouldClose(event.key, open)) { event.preventDefault(); close(); }
      },
    },
  };
}
