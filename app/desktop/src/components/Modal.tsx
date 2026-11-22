import type { KeyboardEvent, MouseEvent, ReactNode } from "react";

import { dialogKeyDecision } from "../lib/interaction.ts";

export interface ModalDialogProps {
  /** The element carrying `role="dialog"`; a rename form needs `form`, the rest are sections. */
  as?: "section" | "div" | "form";
  /** Extra classes on the dialog panel, after the shared `modal-dialog`. */
  className?: string;
  backdropClassName?: string;
  labelledBy: string;
  describedBy?: string;
  /** `aria-modal`; false also leaves Tab untrapped (the document stays reachable). */
  modal?: boolean;
  /** Esc dismisses only while true. Callers pass `!busy`. */
  dismissible: boolean;
  onDismiss: () => void;
  /** Esc is consumed even when it cannot dismiss. */
  preventEscapeWhenBlocked?: boolean;
  /** Tab with no enabled control is swallowed. */
  blockEmptyTab?: boolean;
  /** Which controls take part in the Tab loop. */
  focusSelector?: string;
  /** A mousedown on the backdrop itself dismisses (never on the panel). */
  dismissOnBackdrop?: boolean;
  onSubmit?: (event: React.FormEvent<HTMLFormElement>) => void;
  children: ReactNode;
}

/**
 * The parts every dialog here shares: backdrop, panel markup, Esc and the Tab loop.
 * What may dismiss it, where focus goes on open/close, and the content stay at the call site.
 */
export function ModalDialog({
  as = "section", className, backdropClassName, labelledBy, describedBy, modal = true, dismissible, onDismiss,
  preventEscapeWhenBlocked = false, blockEmptyTab = false, focusSelector = "button:not(:disabled)",
  dismissOnBackdrop = false, onSubmit, children,
}: ModalDialogProps) {
  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    const controls = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(focusSelector));
    const decision = dialogKeyDecision(event.key, event.shiftKey, controls.indexOf(document.activeElement as HTMLElement), controls.length,
      { dismissible, trapTab: modal, blockEmptyTab, preventEscapeWhenBlocked });
    if (decision.preventDefault) event.preventDefault();
    if (decision.focus === "first") controls[0]?.focus();
    else if (decision.focus === "last") controls.at(-1)?.focus();
    if (decision.dismiss) onDismiss();
  };
  const onBackdropMouseDown = dismissOnBackdrop
    ? (event: MouseEvent<HTMLDivElement>) => { if (modal && event.target === event.currentTarget && dismissible) onDismiss(); }
    : undefined;
  const panelClass = className === undefined ? "modal-dialog" : `modal-dialog ${className}`;
  const shared = {
    className: panelClass, role: "dialog", "aria-modal": modal, "aria-labelledby": labelledBy,
    "aria-describedby": describedBy, onKeyDown,
  } as const;
  return <div className={backdropClassName === undefined ? "modal-backdrop" : `modal-backdrop ${backdropClassName}`} onMouseDown={onBackdropMouseDown}>
    {as === "form" ? <form {...shared} onSubmit={onSubmit}>{children}</form>
      : as === "div" ? <div {...shared}>{children}</div>
      : <section {...shared}>{children}</section>}
  </div>;
}
