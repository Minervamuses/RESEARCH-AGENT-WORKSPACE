import type { RefObject } from "react";

import { menuNextIndex, menuShouldClose } from "../lib/interaction.ts";
import { ModalDialog } from "./Modal.tsx";

export function DeleteConversationDialog({ title, status, error, onConfirm, onCancel }: {
  title: string;
  status: "stopping" | "deleting" | null;
  error: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const busy = status !== null;
  return <ModalDialog labelledBy="delete-conversation-title" dismissible={!busy} onDismiss={onCancel} blockEmptyTab>
    <h2 id="delete-conversation-title">Delete conversation?</h2>
    <p>Delete the conversation record “{title}”? The project and its output files will remain.</p>
    <p>If this conversation is running, it will be stopped before deletion.</p>
    {error !== null && <p className="dialog-error" role="alert">{error}</p>}
    {busy && <p role="status">{status === "stopping" ? "Stopping and finishing the current turn…" : "Deleting conversation…"}</p>}
    <div className="action-row">
      <button type="button" disabled={busy} onClick={onConfirm}>{error === null ? "Delete conversation" : "Retry deletion"}</button>
      <button type="button" autoFocus disabled={busy} onClick={onCancel}>Cancel</button>
    </div>
  </ModalDialog>;
}

export function RenameConversationDialog({ title, issue, titleTooLong, busy, saving, canSave, onTitleChange, onSubmit, onCancel }: {
  title: string;
  issue: string | null;
  titleTooLong: boolean;
  /** Another workspace operation is running: Esc, Cancel and the input are disabled. */
  busy: boolean;
  saving: boolean;
  canSave: boolean;
  onTitleChange: (title: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
}) {
  return <ModalDialog as="form" className="file-open-dialog" labelledBy="rename-conversation-title"
    dismissible={!busy} focusSelector="input:not(:disabled), button:not(:disabled)" onDismiss={onCancel}
    onSubmit={(event) => { event.preventDefault(); onSubmit(); }}>
    <h2 id="rename-conversation-title">Rename conversation</h2>
    <label>Name<input autoFocus value={title} disabled={busy}
      onFocus={(event) => event.currentTarget.select()}
      onKeyDown={(event) => { if (event.key === "Enter" && (event.nativeEvent.isComposing || event.keyCode === 229)) event.preventDefault(); }}
      onChange={(event) => onTitleChange(event.target.value)} /></label>
    {titleTooLong && <p className="dialog-error" role="alert">Enter a shorter name.</p>}
    {issue !== null && <p className="dialog-error" role="alert">{issue}</p>}
    <div className="action-row">
      <button type="submit" className="primary-button" disabled={!canSave || title.trim() === "" || titleTooLong}>
        {saving ? "Saving…" : "Save name"}
      </button>
      <button type="button" disabled={busy} onClick={onCancel}>Cancel</button>
    </div>
  </ModalDialog>;
}

/** The right-click menu of a sidebar conversation. Focus return is the caller's: `onClose` restores it, `onDismiss` does not. */
export function ConversationMenu({ left, top, menuRef, canRename, canDelete, onRename, onDelete, onClose, onDismiss }: {
  left: number; top: number; menuRef: RefObject<HTMLDivElement | null>;
  canRename: boolean; canDelete: boolean;
  onRename: () => void; onDelete: () => void;
  onClose: () => void; onDismiss: () => void;
}) {
  return <div className="conversation-menu-backdrop" onClick={onClose}
    onContextMenu={(event) => { event.preventDefault(); onDismiss(); }}>
    <div className="document-menu-actions conversation-menu" role="menu" aria-label="Conversation actions" tabIndex={-1}
      ref={menuRef} style={{ left, top }}
      onClick={(event) => event.stopPropagation()} onKeyDown={(event) => {
        if (menuShouldClose(event.key, true, true)) { event.preventDefault(); onClose(); return; }
        const items = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("button:not(:disabled)"));
        const next = menuNextIndex(event.key, items.indexOf(document.activeElement as HTMLButtonElement), items.length, false);
        if (next !== null) { event.preventDefault(); items[next]?.focus(); }
      }}>
      <button type="button" role="menuitem" disabled={!canRename} onClick={onRename}>Rename</button>
      <button type="button" role="menuitem" disabled={!canDelete} onClick={onDelete}>Delete</button>
    </div>
  </div>;
}
