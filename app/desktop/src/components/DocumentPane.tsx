import type { ComponentProps } from "react";

import type { BibliographyEntryDto } from "../citations.ts";
import type { DocumentContextDto } from "../protocol.ts";
import type { DocumentConflict } from "../lib/documents.ts";
import { focusLeftContainer } from "../lib/interaction.ts";
import type { EditorOutlineHandle } from "../lib/outline/tracking.ts";
import { CitationPanel } from "../CitationPanel.tsx";
import { DocumentEditor } from "../DocumentEditor.tsx";
import type { AnnotationControls } from "./Annotation.tsx";

function DocumentHeader({ path, dirty, busy, openDisabled, saveDisabled, undoDisabled, onOpen, onSave, onUndo }: {
  path: string | null; dirty: boolean; busy: boolean;
  openDisabled: boolean; saveDisabled: boolean; undoDisabled: boolean;
  onOpen: () => void; onSave: () => void; onUndo: () => void;
}) {
  const activate = (event: React.MouseEvent<HTMLButtonElement>, action: () => void) => {
    const menu = event.currentTarget.closest("details");
    if (menu !== null) {
      menu.open = false;
      menu.querySelector("summary")?.focus();
    }
    action();
  };
  return <header className="document-header">
    <span className="document-name" title={path ?? undefined}>{path?.split("/").at(-1) ?? "No source file"}</span>
    {dirty && <span className="document-dirty" role="status" aria-label="Unsaved changes" title="Unsaved changes">●</span>}
    {busy && <span className="document-busy" role="status">Working…</span>}
    <details className="document-menu" onKeyDown={(event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.currentTarget.open = false;
        event.currentTarget.querySelector("summary")?.focus();
      }
    }} onBlur={(event) => {
      if (focusLeftContainer(event.currentTarget, event.relatedTarget as Node | null)) event.currentTarget.open = false;
    }}>
      <summary aria-label="Document actions" title="Document actions">•••</summary>
      <div className="document-menu-actions">
        <button type="button" disabled={openDisabled} onClick={(event) => activate(event, onOpen)}>Open file…</button>
        <button type="button" disabled={saveDisabled} onClick={(event) => activate(event, onSave)}>Save <kbd>Ctrl+S</kbd></button>
        <button type="button" disabled={undoDisabled} onClick={(event) => activate(event, onUndo)}>Undo last Agent edit</button>
      </div>
    </details>
  </header>;
}

type CitationProps = Pick<ComponentProps<typeof CitationPanel>, "refreshToken" | "api" | "contextPayload" | "onEntries" | "requestAdd" | "writesDisabled">;

function DocumentConflictPanel({ conflict, document, busy, onResolve }: {
  conflict: DocumentConflict; document: DocumentContextDto | null; busy: boolean;
  onResolve: (resolution: "keep" | "use" | "cancel") => void;
}) {
  return <section className="document-conflict" aria-label="Document version conflict">
    <h3>{conflict.result.status === "failed" ? "Save failed" : "Choose a document version"}</h3>
    <p>Keeping the editor or cancelling leaves disk unchanged. Using the candidate replaces this file after checking its version again.</p>
    <div className="conflict-versions">
      <details><summary>Original source</summary><pre>{conflict.base.sourceText}</pre></details>
      <details><summary>Current editor</summary><pre>{document?.sourceText}</pre></details>
      <details><summary>Current disk</summary><pre>{conflict.result.currentDiskText ?? "Unavailable"}</pre></details>
      <details open><summary>Agent candidate / requested save</summary><pre>{conflict.result.candidateText ?? document?.sourceText}</pre></details>
    </div>
    <div className="action-row">
      <button type="button" disabled={busy} onClick={() => onResolve("keep")}>Keep editor</button>
      <button type="button" disabled={busy || conflict.result.expectedSnapshot === undefined} onClick={() => onResolve("use")}>Use candidate and save</button>
      <button type="button" disabled={busy} onClick={() => onResolve("cancel")}>Cancel</button>
    </div>
  </section>;
}

/** The source-document column: header menu, editor, citation panel and the version-conflict chooser. */
export function DocumentPane({ document, dirty, busy, notice, header, editor, citation, conflict, onResolveConflict }: {
  document: DocumentContextDto | null; dirty: boolean; busy: boolean; notice: string | null;
  header: { openDisabled: boolean; saveDisabled: boolean; undoDisabled: boolean; onOpen: () => void; onSave: () => void; onUndo: () => void };
  /** `onChange` also receives snapshots from the citation panel. */
  editor: {
    onChange: (snapshot: DocumentContextDto) => void;
    annotationControls: AnnotationControls;
    onAddReference?: (snapshot: DocumentContextDto) => void;
    citationEntries: readonly BibliographyEntryDto[];
    onCursorLine?: (lineNumber: number) => void;
    onViewport?: (viewport: { topLine: number; scrollTop: number }) => void;
    onHandle?: (handle: EditorOutlineHandle | null) => void;
  };
  /** `null` hides the panel (no document open or backend not ready). */
  citation: CitationProps | null;
  conflict: DocumentConflict | null;
  onResolveConflict: (resolution: "keep" | "use" | "cancel") => void;
}) {
  return <section className="document-pane" aria-label="Source document workspace">
    <DocumentHeader path={document?.path ?? null} dirty={dirty} busy={busy} {...header} />
    {notice !== null && <p className="document-error" role="status">{notice}</p>}
    <DocumentEditor value={document} onChange={editor.onChange} annotationControls={editor.annotationControls}
      onAddReference={editor.onAddReference} onSave={header.onSave} saveDisabled={busy} citationEntries={editor.citationEntries}
      onCursorLine={editor.onCursorLine} onViewport={editor.onViewport} onHandle={editor.onHandle} />
    {document !== null && citation !== null && <CitationPanel document={document} onSelect={editor.onChange} {...citation} />}
    {conflict !== null && <DocumentConflictPanel conflict={conflict} document={document} busy={busy} onResolve={onResolveConflict} />}
  </section>;
}
