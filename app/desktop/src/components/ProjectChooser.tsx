import type { ProjectWorkspaceDto } from "../protocol.ts";
import { ModalDialog } from "./Modal.tsx";

/** Open or switch the research project. All state and actions come from `App()`. */
export function ProjectChooser({
  switching, candidate, candidateHistory, issue, busyLabel, documentDirty, dirtyChoice, hasDraft, discardDraft,
  onHistoryChange, onDirtyChoiceChange, onDiscardDraftChange, onBrowse, onInspectHistory, onConfirm, onCancel,
}: {
  /** A project is already open: the title says "Switch". */
  switching: boolean;
  candidate: ProjectWorkspaceDto | null;
  candidateHistory: string;
  issue: string | null;
  /** The running workspace operation's label, or `null` when idle. */
  busyLabel: string | null;
  documentDirty: boolean;
  dirtyChoice: "save" | "discard";
  /** An unsent draft or reference exists and must be discarded to proceed. */
  hasDraft: boolean;
  discardDraft: boolean;
  onHistoryChange: (history: string) => void;
  onDirtyChoiceChange: (choice: "save" | "discard") => void;
  onDiscardDraftChange: (discard: boolean) => void;
  onBrowse: () => void;
  onInspectHistory: () => void;
  onConfirm: (action: "open" | "initialize") => void;
  onCancel: () => void;
}) {
  const busy = busyLabel !== null;
  return <ModalDialog labelledBy="project-chooser-title" dismissible={!busy} onDismiss={onCancel}
    focusSelector="input:not(:disabled), button:not(:disabled), select:not(:disabled)">
    <p className="section-kicker">LOCAL PROJECT</p>
    <h2 id="project-chooser-title">{switching ? "Switch research project" : "Open a research project"}</h2>
    <p>Choose an existing WSL folder. Its RESEARCH.md defines the project rules and conversation history location.</p>
    <div className="action-row"><button type="button" autoFocus disabled={busy} onClick={onBrowse}>Choose project folder…</button></div>
    {candidate !== null && <div className="approval-context">
      <p><strong>Resolved project:</strong> <code>{candidate.rootPath}</code></p>
      {candidate.status === "needs_configuration" ? <>
        <p>{candidate.researchFingerprint === null ? "Create RESEARCH.md with a new empty history." : "Preserve the existing RESEARCH.md and append its history setting."}</p>
        <label>History directory<input aria-label="History directory" value={candidateHistory}
          disabled={busy} onChange={(event) => onHistoryChange(event.target.value)} /></label>
        <p><strong>Resolved history:</strong> <code>{candidate.historyDirectory}</code></p>
        {candidateHistory !== candidate.historyDirectory && <button type="button" disabled={busy} onClick={onInspectHistory}>Inspect history location</button>}
      </> : <p><strong>History directory:</strong> <code>{candidate.historyDirectory}</code></p>}
      {candidate.status === "needs_initialization" && <p>This configured history does not exist yet. Initialize an empty history here, or cancel and edit RESEARCH.md to change its location.</p>}
      {candidate.status === "ready" && <p>Open this project and validate its existing conversation history.</p>}
      {documentDirty && <fieldset disabled={busy}><legend>The document has unsaved changes</legend>
        <label><input type="radio" name="project-document-choice" checked={dirtyChoice === "save"} onChange={() => onDirtyChoiceChange("save")} /> Save before opening</label>
        <label><input type="radio" name="project-document-choice" checked={dirtyChoice === "discard"} onChange={() => onDirtyChoiceChange("discard")} /> Discard only after the project opens</label>
      </fieldset>}
      {hasDraft && <label><input type="checkbox" checked={discardDraft} disabled={busy}
        onChange={(event) => onDiscardDraftChange(event.target.checked)} /> Discard the unsent draft and references only after the project opens</label>}
      <div className="action-row"><button className="primary-button" type="button"
        disabled={busy || (hasDraft && !discardDraft) || candidateHistory.trim() === "" || (candidate.status === "needs_configuration" && candidateHistory !== candidate.historyDirectory)}
        onClick={() => onConfirm(candidate.status === "ready" ? "open" : "initialize")}>
        {documentDirty && dirtyChoice === "save" ? "Save and " : ""}{candidate.status === "ready" ? "Open project" : "Initialize and open project"}
      </button></div>
    </div>}
    {issue !== null && <p className="extension-error" role="alert">{issue}</p>}
    {busy && <p role="status">{busyLabel}…</p>}
    <button type="button" disabled={busy} onClick={onCancel}>Cancel</button>
  </ModalDialog>;
}
