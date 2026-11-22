import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  type KeyboardEvent,
  type RefObject,
} from "react";

import {
  BackendClientError,
  type BackendActionName,
  type BackendSnapshot,
  type BoundedRuntimeDiagnostics,
  type SafeUiError,
  backendReducer,
  initialBackendState,
  normalizeUiError,
  parseBridgeEvent,
  planBackendSnapshotTransition,
  toBoundedDiagnostics,
} from "./backend.ts";
import {
  conversationInteractionState,
  lifecycleResultIsStale,
  stopScreenState,
  turnEventIsStale,
  conversationToRestore,
  composeTurnText,
  conversationReducer,
  initialConversationState,
  latestRetryableTranscriptTurn,
  mergeConversationTurns,
  nextTurnSubmission,
  turnSubmissionText,
  ownsWorkspaceOperation,
  type WorkspaceOperationOwner,
  sameSelection,
  upsertLiveTurn,
  type ConversationAction,
  type ConversationSelection,
  type LiveTurn,
} from "./conversations.ts";
import type {
  DocumentContextDto,
  DocumentResultDto,
  PermissionMode,
  ProjectWorkspaceDto,
  Reference,
  SessionListDto,
  SessionSummaryDto,
} from "./protocol.ts";
import { DocumentEditor } from "./DocumentEditor.tsx";
import type { AnnotationControls } from "./components/Annotation.tsx";
import { ReferenceCards, SafeContent } from "./components/messageParts.tsx";
import { Transcript } from "./components/Transcript.tsx";
import { CitationPanel } from "./CitationPanel.tsx";
import type { BibliographyAddDto, BibliographyEntryDto } from "./citations.ts";
import { ModalDialog } from "./components/Modal.tsx";
import { focusLeftContainer, menuNextIndex, menuShouldClose } from "./lib/interaction.ts";
import { ApprovalDialog } from "./components/ApprovalDialog.tsx";
import { PermissionControl, ThinkingControl } from "./components/ComposerControls.tsx";
import { ExtensionPanel } from "./components/ExtensionPanel.tsx";
import { approvalExpiry, reconcilePermissionAck } from "./lib/approval.ts";
import {
  approvalToResolve,
  beginApprovalResolve,
  clearApproval,
  clearStaleApproval,
  dropApprovalOwner,
  finishApprovalRequest,
  forgetApprovalRequest,
  initialApprovalOwnerState,
  receiveApprovalEvent,
  registerApprovalRequest,
  type ApprovalOwnerState,
} from "./lib/approvalOwner.ts";
import { applyReducerOnce } from "./lib/reducerOnce.ts";
import { useExtensions } from "./hooks/useExtensions.ts";
import {
  beginExtensionPreview,
  canPreviewExtensions,
  canRestartForExtensions,
  decideExtensionBinding,
  failExtensionApply,
  failExtensionFlow,
  planExtensionApply,
  receiveExtensionPreview,
  settleExtensionApply,
  type ExtensionBindingDecision,
} from "./lib/extensionFlow.ts";
import {
  checkSubmissionSize,
  composerSlashCommands,
  filterSlashCommands,
  handleComposerKey,
  inlineSkillReferences,
  insertInlineSkill,
  insertSlashCommand,
  inlineSkillToken,
  retrySettingsMatch,
  slashPrefix,
  type SlashCatalogOwner,
  type SlashCommands,
} from "./lib/composer.ts";
import {
  advanceWorkingDocumentSources,
  backgroundDocumentContext,
  documentContextPayload,
  documentOperationContext,
  documentReference,
  submittedDocumentSource,
  planConflictResolution,
  planDocumentResult,
  type DocumentAction,
  type DocumentConflict,
  type WorkingDocumentSources,
} from "./lib/documents.ts";
import { protocolMismatch, workspaceError } from "./lib/errors.ts";
import { api, eventData, listenBackendEvents } from "./api.ts";
import {
  loadSelectedProjectHistory,
  mergeSessionItems,
  projectDisplayName,
  sidebarRowsForProject,
  type SidebarSessionRow,
} from "./lib/sidebar.ts";
import {
  TRANSCRIPT_PAGE_SIZE,
  failureLifecycleLabel,
  fetchTranscriptPage,
  isPersistedTurnFailure,
  mergeTranscriptItems,
  selectConversationWithPreview,
  transcriptTailOffset,
  transcriptViewFrom,
  visibleMessageRange,
  type TranscriptView,
} from "./lib/transcript.ts";

const phaseLabels = {
  starting: "Starting backend",
  "backend-ready": "Backend ready",
  "session-ready": "Session ready",
  busy: "Working",
  degraded: "Needs attention",
  crashed: "Backend crashed",
  restarting: "Restarting backend",
  "shutting-down": "Shutting down",
  stopped: "Backend stopped",
} as const;

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
      {error !== null && <p className="extension-error" role="alert">{error}</p>}
      {busy && <p role="status">{status === "stopping" ? "Stopping and finishing the current turn…" : "Deleting conversation…"}</p>}
      <div className="action-row">
        <button type="button" disabled={busy} onClick={onConfirm}>{error === null ? "Delete conversation" : "Retry deletion"}</button>
        <button type="button" autoFocus disabled={busy} onClick={onCancel}>Cancel</button>
      </div>
  </ModalDialog>;
}

export function SlashCommandList({ commands, active, onSelect, inline = false }: {
  commands: SlashCommands; active: number; onSelect: (index: number) => void; inline?: boolean;
}) {
  return <ul id="composer-slash-commands" className="slash-command-list" role="listbox" aria-label={inline ? "Skills" : "Slash commands"}>
    {commands.map((command, index) => <li
      key={command.name} id={`composer-slash-option-${index}`} role="option"
      aria-selected={index === active}
      onPointerDown={(event) => event.preventDefault()}
      onClick={() => onSelect(index)}
    ><strong>{inline ? "@" : "/"}{command.name}</strong><span>{command.description}</span></li>)}
  </ul>;
}

export function ComposerFooter({ thinkingMode, permissionMode, controlsDisabled, sendDisabled, turnActive = false, stopping = false, onStop, onThinkingChange, onPermissionChange }: {
  thinkingMode: "normal" | "extended"; permissionMode: PermissionMode;
  controlsDisabled: boolean; sendDisabled: boolean;
  turnActive?: boolean; stopping?: boolean; onStop?: () => void;
  onThinkingChange: (mode: "normal" | "extended") => void; onPermissionChange: (mode: PermissionMode) => void;
}) {
  return <div className="composer-footer">
    <div className="composer-controls" aria-label="Conversation settings">
      <ThinkingControl mode={thinkingMode} disabled={controlsDisabled} onChange={onThinkingChange} />
      <PermissionControl mode={permissionMode} disabled={controlsDisabled} onChange={onPermissionChange} />
    </div>
    {turnActive
      ? <button className="primary-button" type="button" disabled={stopping} onClick={onStop}>{stopping ? "Stopping…" : "Stop"}</button>
      : <button className="primary-button" type="submit" disabled={sendDisabled}>Send</button>}
  </div>;
}

function SlashComposer({ draft, references, annotationControls, onRemoveReference, commands, skills, onSkillPicked, textareaRef, disabled, sendDisabled, controlsDisabled, turnActive, stopping, onStop, thinkingMode, permissionMode, onThinkingChange, onPermissionChange, turnHint, onChange, onSubmit }: {
  references: readonly Reference[]; onRemoveReference: (id: string) => void;
  annotationControls: AnnotationControls;
  turnActive: boolean; stopping: boolean; onStop: () => void;
  thinkingMode: "normal" | "extended"; permissionMode: PermissionMode; controlsDisabled: boolean; turnHint?: string;
  onThinkingChange: (mode: "normal" | "extended") => void; onPermissionChange: (mode: PermissionMode) => void;
  draft: string; commands: SlashCommands; skills: readonly string[]; onSkillPicked: (name: string) => void; textareaRef: RefObject<HTMLTextAreaElement | null>;
  disabled: boolean; sendDisabled: boolean; onChange: (draft: string) => void; onSubmit: () => void;
}) {
  const [focused, setFocused] = useState(false);
  const [cursor, setCursor] = useState({ start: 0, end: 0 });
  const [dismissed, setDismissed] = useState<string | null>(null);
  const [composing, setComposing] = useState(false);
  const composingRef = useRef(false);
  const insertion = useRef<{ text: string; caret: number } | null>(null);
  const [selection, setSelection] = useState({ draft, commands, index: 0 });
  const prefix = slashPrefix(draft, cursor.start, cursor.end);
  const inline = inlineSkillToken(draft, cursor.start, cursor.end);
  const inlinePrefix = inline?.prefix ?? null;
  const matches = useMemo(() => inlinePrefix === null
    ? filterSlashCommands(commands, prefix ?? "")
    : skills.filter((name) => name.toLowerCase().startsWith(inlinePrefix.toLowerCase()))
      .map((name) => ({ name, description: commands.find((item) => item.name === name)?.description ?? "Use this Skill for the current message" })),
    [commands, skills, prefix, inlinePrefix]);
  const open = focused && !disabled && !composing && (inline !== null || commands.length > 0) &&
    dismissed !== draft && (inline !== null || prefix !== null);
  const active = selection.draft === draft && selection.commands === commands
    ? Math.min(selection.index, Math.max(0, matches.length - 1)) : 0;

  useLayoutEffect(() => {
    if (insertion.current?.text !== draft) return;
    const caret = insertion.current.caret;
    insertion.current = null;
    textareaRef.current?.focus();
    textareaRef.current?.setSelectionRange(caret, caret);
    setCursor({ start: caret, end: caret });
  }, [draft, textareaRef]);

  useEffect(() => {
    if (open) document.getElementById(`composer-slash-option-${active}`)?.scrollIntoView({ block: "nearest" });
  }, [active, open, matches]);

  const select = (index: number) => {
    if (!open || composingRef.current || matches[index] === undefined) return;
    const inserted = inline === null
      ? { text: insertSlashCommand(draft, matches[index].name), caret: insertSlashCommand(draft, matches[index].name).length }
      : insertInlineSkill(draft, inline, matches[index].name);
    if (inline !== null) onSkillPicked(matches[index].name);
    insertion.current = inserted;
    setDismissed(inserted.text);
    onChange(inserted.text);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    handleComposerKey({
      key: event.key, shiftKey: event.shiftKey,
      isComposing: event.nativeEvent.isComposing || composingRef.current,
      preventDefault: () => event.preventDefault(),
    }, { open, count: matches.length, active }, {
      select,
      move: (index) => setSelection({ draft, commands, index }),
      close: () => setDismissed(draft),
      submit: onSubmit,
    });
  };

  return <form className="composer" onSubmit={(event) => {
    event.preventDefault();
    if (!composingRef.current) onSubmit();
  }}>
    <label htmlFor="conversation-draft">Message</label>
    <ReferenceCards references={references.filter((reference) => !annotationControls.annotations.some((item) => item.referenceId === reference.referenceId))}
      onRemove={disabled ? undefined : onRemoveReference} />
    {annotationControls.annotations.length > 0 && <div className="annotation-batch" data-reference-exclude>
      <span>{annotationControls.annotations.length} passage comments</span>
      {annotationControls.annotations.map((annotation) => <button key={annotation.referenceId} type="button" disabled={disabled}
        title={annotation.comment || "No request yet"} onClick={() => annotationControls.onToggle(annotation.referenceId, true)}>
        {annotation.number}{annotation.comment.trim() === "" ? " · empty" : ""}
      </button>)}
      {draft.trim() === "" && annotationControls.annotations.every((item) => item.comment.trim() === "") &&
        <span>Add a comment or a message before sending.</span>}
    </div>}
    {open && <>
      <SlashCommandList commands={matches} active={active} onSelect={select} inline={inline !== null} />
      <span className="slash-command-status" role="status">{matches.length === 0 ? (inline !== null ? "No matching Skill. Unselected @ text is sent literally." : "No matching commands") : `${matches.length} ${inline !== null ? "Skills" : "commands"} · ↑↓ to move · Enter to insert · Esc to close`}</span>
    </>}
    <textarea id="conversation-draft" ref={textareaRef} value={draft}
      onChange={(event) => {
        setDismissed(null);
        setCursor({ start: event.target.selectionStart, end: event.target.selectionEnd });
        onChange(event.target.value);
      }}
      onSelect={(event) => setCursor({ start: event.currentTarget.selectionStart, end: event.currentTarget.selectionEnd })}
      onFocus={(event) => {
        setFocused(true);
        setCursor({ start: event.target.selectionStart, end: event.target.selectionEnd });
      }}
      onBlur={() => setFocused(false)}
      onCompositionStart={() => { composingRef.current = true; setComposing(true); }}
      onCompositionEnd={() => { composingRef.current = false; setComposing(false); }}
      onKeyDown={onKeyDown}
      aria-autocomplete="list" aria-haspopup="listbox"
      aria-controls={open ? "composer-slash-commands" : undefined}
      aria-activedescendant={open && matches.length > 0 ? `composer-slash-option-${active}` : undefined}
      rows={3} title="Enter to send · Shift+Enter for a new line · @ to add a Skill" placeholder="Ask about your research…" disabled={disabled}
    />
    {turnHint !== undefined && <p className="composer-turn-hint" role="status">{turnHint}</p>}
    <ComposerFooter thinkingMode={thinkingMode} permissionMode={permissionMode} controlsDisabled={controlsDisabled}
      sendDisabled={sendDisabled} turnActive={turnActive} stopping={stopping} onStop={onStop}
      onThinkingChange={onThinkingChange} onPermissionChange={onPermissionChange} />
  </form>;
}

function configuredLabel(value: boolean): string {
  return value ? "Configured" : "Not configured";
}

function RuntimeDetails({ diagnostics }: { diagnostics: BoundedRuntimeDiagnostics }) {
  return (
    <details className="runtime-details">
      <summary>Local runtime details</summary>
      <dl>
        <div><dt>Python</dt><dd>{diagnostics.pythonVersion}</dd></div>
        <div><dt>Backend</dt><dd>{diagnostics.backendVersion}</dd></div>
        <div><dt>Protocol</dt><dd>v{diagnostics.protocolVersion}</dd></div>
        <div><dt>Conda environment</dt><dd>{diagnostics.condaEnvironment ?? "Not detected"}</dd></div>
        <div><dt>OpenRouter</dt><dd>{configuredLabel(diagnostics.openRouterConfigured)}</dd></div>
        <div><dt>OpenAlex</dt><dd>{configuredLabel(diagnostics.openAlexConfigured)}</dd></div>
        <div><dt>MCP</dt><dd>{diagnostics.mcpEnabled ? "Enabled" : "Disabled"}</dd></div>
        <div className="wide-detail"><dt>MCP families</dt><dd>{diagnostics.mcpFamilies.length > 0 ? diagnostics.mcpFamilies.join(", ") : "None"}</dd></div>
        <div className="wide-detail"><dt>App root</dt><dd>{diagnostics.appRoot}</dd></div>
        <div className="wide-detail"><dt>Working directory</dt><dd>{diagnostics.workingDirectory}</dd></div>
        <div className="wide-detail"><dt>Conda prefix</dt><dd>{diagnostics.condaPrefix ?? "Not detected"}</dd></div>
        <div className="wide-detail"><dt>Research store</dt><dd>{diagnostics.storePath}</dd></div>
      </dl>
    </details>
  );
}

function shutdownSummary(snapshot: BackendSnapshot | null): string | null {
  const report = snapshot?.lastShutdown;
  if (report === null || report === undefined) return null;
  if (report.kind === "not_running") return "The backend was already stopped.";
  if (report.kind === "forced") return "The backend was forced to stop.";
  return "The backend stopped gracefully.";
}

function newLogicalTurnId(): string {
  return globalThis.crypto.randomUUID().replaceAll("-", "").toLowerCase();
}

export function DocumentHeader({ path, dirty, busy, openDisabled, saveDisabled, undoDisabled, onOpen, onSave, onUndo }: {
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

export default function App() {
  const [state, dispatch] = useReducer(backendReducer, initialBackendState);
  const [conversation, setConversation] = useState(initialConversationState);
  const [project, setProject] = useState<ProjectWorkspaceDto | null>(null);
  const [referenceIssue, setReferenceIssue] = useState<string | null>(null);
  const [chatSelection, setChatSelection] = useState<{
    owner: WorkspaceOperationOwner; projectId: string; sessionId: string; turnId: string; role: "user" | "assistant";
    visibleText: string; text: string; startUtf16: number; endUtf16: number; top: number; left: number;
  } | null>(null);
  const projectRef = useRef<ProjectWorkspaceDto | null>(null);
  const bindingGenerationRef = useRef<number | null>(null);
  const projectEpochRef = useRef(0);
  const resumeSelectionRef = useRef<ConversationSelection | null>(null);
  const resumeDraftRef = useRef<string | null>(null);
  const [chooserOpen, setChooserOpen] = useState(true);
  const [candidateRoot, setCandidateRoot] = useState("");
  const [candidateHistory, setCandidateHistory] = useState("");
  const [candidate, setCandidate] = useState<ProjectWorkspaceDto | null>(null);
  const [chooserIssue, setChooserIssue] = useState<string | null>(null);
  const [discardDraft, setDiscardDraft] = useState(false);
  const [dirtyChoice, setDirtyChoice] = useState<"save" | "discard">("save");
  const documentBaselineRef = useRef<DocumentContextDto | null>(null);
  const [sessionList, setSessionList] = useState<SessionListDto | null>(null);
  const [conversationMenu, setConversationMenu] = useState<{ projectId: string; session: SidebarSessionRow; left: number; top: number } | null>(null);
  const [renameDialog, setRenameDialog] = useState<{ projectId: string; sessionId: string; title: string; issue: string | null; owner: WorkspaceOperationOwner } | null>(null);
  const [deleteDialog, setDeleteDialog] = useState<{ projectId: string; sessionId: string; title: string; status: "stopping" | "deleting" | null; issue: string | null; owner: WorkspaceOperationOwner } | null>(null);
  const deleteOwnerRef = useRef<WorkspaceOperationOwner | null>(null);
  const conversationMenuRef = useRef<HTMLDivElement>(null);
  const conversationMenuReturnFocusRef = useRef<HTMLElement | null>(null);
  const [slashCatalogOwner, setSlashCatalogOwner] = useState<SlashCatalogOwner | null>(null);
  const [historyGeneration, setHistoryGenerationState] = useState<number | null>(null);
  const historyGenerationRef = useRef<number | null>(null);
  const setHistoryGeneration = useCallback((value: number | null) => {
    historyGenerationRef.current = value;
    setHistoryGenerationState(value);
  }, []);
  const [workspaceBusy, setWorkspaceBusy] = useState<string | null>(null);
  const [workspaceIssue, setWorkspaceIssue] = useState<SafeUiError | null>(null);
  const [transcript, setTranscript] = useState<TranscriptView | null>(null);
  const [selectionPreview, setSelectionPreview] = useState<{ title: string; transcript: TranscriptView } | null>(null);
  const [liveTurns, setLiveTurns] = useState<LiveTurn[]>([]);
  const [pendingUserText, setPendingUserText] = useState<string | null>(null);
  const [historyIssue, setHistoryIssue] = useState<string | null>(null);
  const {
    flow: extensionFlow,
    reset: resetExtensions,
    start: startExtensions,
    interrupt: interruptExtensions,
    markRestarting: markExtensionsRestarting,
    applyTransition: applyExtensionTransition,
    observeRevision: observeExtensionsRevision,
    update: updateExtensions,
    updateFor: updateExtensionsFor,
  } = useExtensions();
  const [approval, setApproval] = useState(() => initialApprovalOwnerState<WorkspaceOperationOwner>());
  const [documentValue, setDocumentValue] = useState<DocumentContextDto | null>(null);
  const documentRef = useRef<DocumentContextDto | null>(null);
  const [rootPath, setRootPath] = useState("");
  const [documentBusy, setDocumentBusy] = useState(false);
  const documentBusyRef = useRef(false);
  const [documentNotice, setDocumentNotice] = useState<string | null>(null);
  const [documentConflict, setDocumentConflict] = useState<DocumentConflict | null>(null);
  const [lastDocumentAction, setLastDocumentAction] = useState<DocumentAction | null>(null);
  const documentRequestRef = useRef<{ requestId: string; turnId: string; context: DocumentContextDto } | null>(null);
  const documentApplyPromiseRef = useRef<Promise<void> | null>(null);
  const workingDocumentSourcesRef = useRef<WorkingDocumentSources | null>(null);
  const submittedDocumentRef = useRef<DocumentContextDto | null>(null);
  const selectedSkillNamesRef = useRef(new Set<string>());
  useEffect(() => { selectedSkillNamesRef.current.clear(); }, [conversation.selected?.projectId, conversation.selected?.sessionId]);
  const updateDocument = useCallback((value: DocumentContextDto | null) => {
    documentRef.current = value;
    setDocumentValue(value);
  }, []);
  // Bumped after open, save, and applied operations so the citation panel re-checks.
  const [citationRefresh, setCitationRefresh] = useState(0);
  const [citationEntries, setCitationEntries] = useState<readonly BibliographyEntryDto[]>([]);
  const inFlight = useRef(false);
  const exclusiveOwnerRef = useRef<WorkspaceOperationOwner | null>(null);
  const historyLoading = useRef<WorkspaceOperationOwner | null>(null);
  const diagnosticsAttempt = useRef<number | null>(null);
  const generationRef = useRef(0);
  const conversationRef = useRef(conversation);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const transcriptRef = useRef<HTMLDivElement>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const workspaceOperation = useRef<WorkspaceOperationOwner | null>(null);
  const documentOperationRef = useRef<WorkspaceOperationOwner | null>(null);
  const frameOwnerRef = useRef<WorkspaceOperationOwner | null>(null);
  const turnOwnerRef = useRef<WorkspaceOperationOwner | null>(null);
  const stopPromiseRef = useRef<Promise<void> | null>(null);
  const turnSettlementPromiseRef = useRef<Promise<void> | null>(null);
  const approvalRef = useRef(approval);
  const pendingApproval = approval.pending;
  const approvalResolving = approval.resolving;

  const applyConversation = useCallback((action: ConversationAction) =>
    applyReducerOnce(conversationReducer, conversationRef, setConversation, action), []);

  /** All approval transitions go through lib/approvalOwner.ts; this publishes the result to the ref and to React. */
  const commitApproval = useCallback((next: ApprovalOwnerState<WorkspaceOperationOwner>) => {
    if (next === approvalRef.current) return;
    approvalRef.current = next;
    setApproval(next);
  }, []);

  const captureOwner = useCallback((label: string): WorkspaceOperationOwner => ({
    generation: generationRef.current, projectEpoch: projectEpochRef.current, token: Symbol(label),
  }), []);

  const ownsOperation = useCallback((owner: WorkspaceOperationOwner, current: WorkspaceOperationOwner | null) =>
    ownsWorkspaceOperation(owner, current, generationRef.current, projectEpochRef.current), []);

  /** Route an `approval.required` through the owner module; a newly shown approval resets the pending frame owner. */
  const acceptApproval = useCallback((generation: number, requestId: string, turnRequestId: string | null,
      data: Parameters<typeof receiveApprovalEvent>[1]["data"]) => {
    const result = receiveApprovalEvent(approvalRef.current, {
      generation, requestId, turnRequestId, data, now: Date.now(), owner: captureOwner("approval"),
    });
    if (!result.accepted) return;
    frameOwnerRef.current = null;
    commitApproval(result.state);
  }, [captureOwner, commitApproval]);

  const beginWorkspaceOperation = useCallback((label: string): WorkspaceOperationOwner | null => {
    if (workspaceOperation.current !== null || inFlight.current || documentBusyRef.current ||
        approvalRef.current.pending !== null || conversationRef.current.activeTurn !== null ||
        conversationRef.current.stopRequest !== null) return null;
    const owner = captureOwner(label);
    workspaceOperation.current = owner;
    turnOwnerRef.current = null;
    frameOwnerRef.current = null;
    setWorkspaceBusy(label);
    setWorkspaceIssue(null);
    setConversationMenu(null);
    return owner;
  }, [captureOwner]);

  const finishWorkspaceOperation = useCallback((owner: WorkspaceOperationOwner) => {
    if (!ownsOperation(owner, workspaceOperation.current)) return;
    workspaceOperation.current = null;
    setWorkspaceBusy(null);
  }, [ownsOperation]);

  const scheduleOwnedFrame = useCallback((owner: WorkspaceOperationOwner, update: () => void) => {
    frameOwnerRef.current = owner;
    requestAnimationFrame(() => {
      if (ownsOperation(owner, frameOwnerRef.current) &&
          (workspaceOperation.current === null || workspaceOperation.current.token === owner.token)) update();
    });
  }, [ownsOperation]);

  const invalidateOperations = useCallback(() => {
    workspaceOperation.current = null;
    documentOperationRef.current = null;
    historyLoading.current = null;
    commitApproval(forgetApprovalRequest(dropApprovalOwner(approvalRef.current), "document"));
    frameOwnerRef.current = null;
    turnOwnerRef.current = null;
    documentRequestRef.current = null;
    documentApplyPromiseRef.current = null;
    workingDocumentSourcesRef.current = null;
    submittedDocumentRef.current = null;
    stopPromiseRef.current = null;
    turnSettlementPromiseRef.current = null;
    deleteOwnerRef.current = null;
    documentBusyRef.current = false;
    setDocumentBusy(false);
    setWorkspaceBusy(null);
    setConversationMenu(null);
    setRenameDialog(null);
    setDeleteDialog(null);
  }, [commitApproval]);

  useEffect(() => {
    if (conversationMenu !== null) conversationMenuRef.current?.focus();
  }, [conversationMenu]);

  const receiveDocumentResult = useCallback((result: DocumentResultDto, captured: DocumentContextDto, action: DocumentAction | null) => {
    const plan = planDocumentResult(result, captured, documentRef.current, action, submittedDocumentRef.current);
    if (plan.kind === "ignore") return;
    if (plan.kind === "mismatch") throw protocolMismatch("The backend returned a document result for a different source.");
    if (plan.kind === "saved") {
      setCitationRefresh((value) => value + 1);
      if (plan.advanceSources && action?.sourceSnapshot !== undefined) {
        workingDocumentSourcesRef.current = advanceWorkingDocumentSources(workingDocumentSourcesRef.current, action.sourceSnapshot, result);
      }
      documentBaselineRef.current = plan.baseline;
      updateDocument(plan.document);
      setDocumentNotice(null);
      setDocumentConflict(null);
      if (plan.lastAction !== null) setLastDocumentAction(plan.lastAction.set);
    } else if (plan.kind === "cancelled") {
      setDocumentNotice(plan.notice);
      setDocumentConflict(null);
    } else {
      setDocumentConflict(plan.conflict);
      setDocumentNotice(plan.notice);
    }
  }, [updateDocument]);

  const applyDocumentOperation = useCallback((action: DocumentAction, resolution?: "keep" | "use" | "cancel", expectedSnapshot?: DocumentContextDto): Promise<void> => {
    const current = documentRef.current;
    if (current === null || documentBusyRef.current || workspaceOperation.current !== null ||
        bindingGenerationRef.current !== generationRef.current) return Promise.resolve();
    const captured = documentOperationContext(current, action.sourceSnapshot);
    const pending = (async () => {
      const owner = captureOwner("document.apply");
      documentOperationRef.current = owner;
      frameOwnerRef.current = null;
      documentBusyRef.current = true;
      setDocumentBusy(true);
      try {
        const { sourceSnapshot: _sourceSnapshot, ...requestAction } = action;
        const tracked = api.documentApplyTracked({
          ...requestAction, documentContext: documentContextPayload(captured), ...(resolution === undefined ? {} : { resolution }),
          ...(expectedSnapshot === undefined ? {} : { expectedSnapshot }),
        });
        documentRequestRef.current = { requestId: tracked.requestId, turnId: action.turnId, context: captured };
        commitApproval(registerApprovalRequest(approvalRef.current, "document", tracked.requestId));
        const result = await tracked.result;
        if (ownsOperation(owner, documentOperationRef.current)) receiveDocumentResult(result, captured, action);
      } catch (error) {
        if (ownsOperation(owner, documentOperationRef.current)) setDocumentNotice(workspaceError(error).message + " Your text is retained; check disk before retrying.");
      } finally {
        if (ownsOperation(owner, documentOperationRef.current)) {
          documentOperationRef.current = null;
          documentBusyRef.current = false;
          setDocumentBusy(false);
          const requestId = documentRequestRef.current?.requestId;
          documentRequestRef.current = null;
          commitApproval(finishApprovalRequest(approvalRef.current, "document", requestId));
        }
      }
    })().finally(() => { if (documentApplyPromiseRef.current === pending) documentApplyPromiseRef.current = null; });
    documentApplyPromiseRef.current = pending;
    return pending;
  }, [captureOwner, commitApproval, ownsOperation, receiveDocumentResult]);

  const requestCitationAdd = useCallback(async (identifier: string): Promise<BibliographyAddDto> => {
    const tracked = api.bibliographyAddTracked({ identifier });
    commitApproval(registerApprovalRequest(approvalRef.current, "citation", tracked.requestId));
    try {
      return await tracked.result;
    } finally {
      commitApproval(finishApprovalRequest(approvalRef.current, "citation", tracked.requestId));
    }
  }, [commitApproval]);

  const openDocument = useCallback(async () => {
    if (projectRef.current === null || bindingGenerationRef.current !== generationRef.current || workspaceOperation.current !== null ||
        conversationRef.current.activeTurn !== null || conversationRef.current.stopRequest !== null || documentBusyRef.current || approvalRef.current.pending !== null) return;
    const owner = captureOwner("document.open");
    documentOperationRef.current = owner;
    frameOwnerRef.current = null;
    documentBusyRef.current = true;
    setDocumentBusy(true);
    try {
      const path = await api.pickDocument(projectRef.current.rootPath);
      if (path === null || !ownsOperation(owner, documentOperationRef.current)) return;
      if (documentRef.current !== null && documentRef.current.sourceText !== documentBaselineRef.current?.sourceText &&
          !window.confirm("Discard unsaved document changes and open another file?")) return;
      const opened = await api.documentOpen({ path });
      if (!ownsOperation(owner, documentOperationRef.current)) return;
      const openedRoot = opened.rootPath;
      if (openedRoot === undefined || openedRoot !== projectRef.current?.rootPath) throw protocolMismatch("The backend opened a document from a different project.");
      const snapshot: DocumentContextDto = { ...opened, rootPath: openedRoot, editorRevision: opened.editorRevision ?? 0 };
      documentBaselineRef.current = { ...snapshot };
      updateDocument(snapshot);
      setCitationRefresh((value) => value + 1);
      setDocumentConflict(null);
      setLastDocumentAction(null);
      setDocumentNotice(null);
    } catch (error) {
      if (ownsOperation(owner, documentOperationRef.current)) setDocumentNotice(workspaceError(error).message);
    } finally {
      if (ownsOperation(owner, documentOperationRef.current)) {
        documentOperationRef.current = null;
        documentBusyRef.current = false;
        setDocumentBusy(false);
      }
    }
  }, [captureOwner, ownsOperation, updateDocument]);

  const saveDocument = useCallback(async (parentOperation: WorkspaceOperationOwner | null = null) => {
    const captured = documentRef.current;
    if (captured === null || documentBusyRef.current || bindingGenerationRef.current !== generationRef.current ||
        (workspaceOperation.current !== null && workspaceOperation.current !== parentOperation)) return false;
    const owner = captureOwner("document.save");
    documentOperationRef.current = owner;
    frameOwnerRef.current = null;
    documentBusyRef.current = true;
    setDocumentBusy(true);
    try {
      const result = await api.documentSave({ documentContext: documentContextPayload(captured) });
      if (!ownsOperation(owner, documentOperationRef.current)) return false;
      receiveDocumentResult(result, captured, null);
      return result.status === "saved" && documentRef.current?.sourceText === documentBaselineRef.current?.sourceText;
    } catch (error) {
      if (ownsOperation(owner, documentOperationRef.current)) setDocumentNotice(workspaceError(error).message + " Your editor text is retained.");
      return false;
    } finally {
      if (ownsOperation(owner, documentOperationRef.current)) {
        documentOperationRef.current = null;
        documentBusyRef.current = false;
        setDocumentBusy(false);
      }
    }
  }, [captureOwner, ownsOperation, receiveDocumentResult]);

  const resolveDocumentConflict = useCallback(async (resolution: "keep" | "use" | "cancel") => {
    if (documentConflict === null) return;
    const plan = planConflictResolution(documentConflict, resolution, documentRef.current);
    if (plan.kind === "apply") {
      await applyDocumentOperation(plan.action, resolution, plan.expectedSnapshot);
    } else if (plan.kind === "no-document") {
      return;
    } else if (plan.kind === "editor-changed") {
      setDocumentNotice(plan.notice);
    } else if (plan.kind === "save-again") {
      const current = documentRef.current;
      if (current === null) return;
      updateDocument({ ...current, diskFingerprint: plan.diskFingerprint });
      await saveDocument();
    } else {
      setDocumentConflict(null);
      setDocumentNotice(null);
    }
  }, [documentConflict, applyDocumentOperation, saveDocument, updateDocument]);

  const applyBackendSnapshot = useCallback((
    snapshot: BackendSnapshot,
    completedAction?: "start" | "restart" | "shutdown",
  ) => {
    const transition = planBackendSnapshotTransition({
      currentGeneration: generationRef.current,
      historyGeneration: historyGenerationRef.current,
      hasProject: projectRef.current !== null,
      selectedConversation: conversationRef.current.selected,
      resumeSelection: resumeSelectionRef.current,
      draft: conversationRef.current.draft,
      resumeDraft: resumeDraftRef.current,
      snapshot,
      completedAction,
    });
    if (!transition.accepted) return;
    if (transition.invalidateOperations) invalidateOperations();
    if (transition.captureResumeState) {
      resumeSelectionRef.current = transition.nextResumeSelection;
      resumeDraftRef.current = transition.nextResumeDraft;
      if (transition.clearBindingGeneration) bindingGenerationRef.current = null;
    }
    if (transition.clearTransientUi) {
      setSlashCatalogOwner(null);
      setSelectionPreview(null);
      commitApproval(clearApproval(approvalRef.current));
    }
    if (transition.resetStaleHistory) {
      workspaceOperation.current = null;
      setWorkspaceBusy(null);
      setWorkspaceIssue(null);
      setSessionList(null);
      setTranscript(null);
      setSelectionPreview(null);
      setLiveTurns([]);
      setPendingUserText(null);
      setHistoryIssue(null);
      commitApproval(clearApproval(approvalRef.current));
      setHistoryGeneration(null);
    }
    applyExtensionTransition(transition.extensionTransition);
    generationRef.current = transition.nextGeneration;
    applyConversation({ type: "backend-generation-changed", generation: transition.nextGeneration });
    dispatch({ type: "snapshot", snapshot });
    if (transition.completedAction !== null) {
      dispatch({ type: "action-completed", action: transition.completedAction });
    }
  }, [applyConversation, invalidateOperations, setHistoryGeneration]);

  useEffect(() => {
    let disposed = false;
    let removeListener: (() => void) | undefined;
    void (async () => {
      try {
        const unlisten = await listenBackendEvents((payload) => {
          if (disposed) return;
          try {
            const event = parseBridgeEvent(payload);
            if (event.type === "lifecycle") {
              applyBackendSnapshot(event.snapshot);
              return;
            }
            dispatch({ type: "protocol-event", message: event.message });
            const message = event.message;
            if (
              message.messageType === "event" &&
              !("requestId" in message) &&
              (message.event === "backend.crashed" || message.event === "backend.shutting_down")
            ) {
              commitApproval(clearApproval(approvalRef.current));
              interruptExtensions();
            }
            if (message.messageType !== "event" || !("requestId" in message)) return;
            const active = conversationRef.current.activeTurn;
            const documentRequest = documentRequestRef.current;
            const citationRequest = approvalRef.current.citationRequestId;
            if (active === null && documentRequest === null && citationRequest === null) return;
            if (citationRequest !== null && message.requestId === citationRequest) {
              // bibliography.add runs outside a turn; its citation.save approval uses the shared approval UI.
              if (message.event === "approval.required") {
                acceptApproval(generationRef.current, message.requestId, null, eventData("approval.required", message.data));
              }
              return;
            }
            if (active === null && documentRequest === null) return;
            const generation = generationRef.current;
            if (turnEventIsStale(active, generation, projectEpochRef.current)) return;
            if (documentRequest !== null && (documentOperationRef.current === null || !ownsOperation(documentOperationRef.current, documentOperationRef.current))) return;
            if (message.event === "turn.accepted" && active !== null && turnOwnerRef.current !== null &&
                ownsOperation(turnOwnerRef.current, turnOwnerRef.current) && typeof message.data.sessionId === "string" && typeof message.data.turnId === "string") {
              applyConversation({ type: "turn-accepted", generation, projectEpoch: active.projectEpoch,
                projectId: active.projectId, sessionId: message.data.sessionId, turnId: message.data.turnId, requestId: message.requestId });
              return;
            }
            if (conversationRef.current.stopRequest !== null &&
                (message.event === "document.proposed" || message.event === "approval.required")) return;
            if (message.event === "document.proposed" && active !== null && message.requestId === active.requestId && message.data.turnId === active.turnId && typeof message.data.callId === "string") {
              const owner = turnOwnerRef.current;
              if (owner === null) return;
              const callId = message.data.callId;
              const referenceId = typeof message.data.referenceId === "string" ? message.data.referenceId : undefined;
              void (async () => {
                await documentApplyPromiseRef.current;
                const current = conversationRef.current.activeTurn;
                if (disposed || !ownsOperation(owner, turnOwnerRef.current) || current === null ||
                    current.requestId !== active.requestId || current.turnId !== active.turnId || current.sessionId !== active.sessionId ||
                    conversationRef.current.stopRequest !== null) return;
                const sourceSnapshot = submittedDocumentSource(workingDocumentSourcesRef.current, referenceId);
                await applyDocumentOperation({ turnId: current.turnId, callId, parentRequestId: current.requestId, sourceSnapshot });
              })().catch((error: unknown) => {
                if (ownsOperation(owner, turnOwnerRef.current)) setDocumentNotice(workspaceError(error).message);
              });
              return;
            }
            if (message.event === "approval.required") {
              acceptApproval(generation, message.requestId, active?.requestId ?? null, eventData("approval.required", message.data));
            } else if (active !== null && message.event === "stage.changed" && typeof message.data.stage === "string") {
              applyConversation({
                type: "activity-received",
                generation,
                projectEpoch: active.projectEpoch,
                requestId: message.requestId,
                sessionId: active.sessionId,
                activity: { kind: "stage", label: message.data.stage, status: null },
              });
            } else if (active !== null && message.event.startsWith("tool.") && typeof message.data.name === "string" && typeof message.data.status === "string") {
              applyConversation({
                type: "activity-received",
                generation,
                projectEpoch: active.projectEpoch,
                requestId: message.requestId,
                sessionId: active.sessionId,
                activity: { kind: "tool", label: message.data.name, status: message.data.status },
              });
            }
          } catch (error) {
            dispatch({ type: "action-failed", error: normalizeUiError(error, "protocol") });
          }
        });
        if (disposed) { unlisten(); return; }
        removeListener = unlisten;
        const snapshot = await api.initialize(() => {
          if (!disposed) dispatch({ type: "action-started", action: "start" });
        });
        if (!disposed) {
          applyBackendSnapshot(snapshot, "start");
        }
      } catch (error) {
        if (!disposed) dispatch({ type: "action-failed", error: workspaceError(error) });
      }
    })();
    return () => { disposed = true; removeListener?.(); };
  }, [acceptApproval, applyBackendSnapshot, applyConversation, applyDocumentOperation, commitApproval, invalidateOperations, ownsOperation]);

  const runExclusive = useCallback(async (action: BackendActionName, operation: (owner: WorkspaceOperationOwner) => Promise<void>) => {
    if (inFlight.current) return;
    const owner = captureOwner(action);
    exclusiveOwnerRef.current = owner;
    inFlight.current = true;
    dispatch({ type: "action-started", action });
    try { await operation(owner); }
    catch (error) {
      if (ownsOperation(owner, exclusiveOwnerRef.current)) dispatch({ type: "action-failed", error: workspaceError(error) });
    } finally {
      if (exclusiveOwnerRef.current?.token === owner.token) {
        exclusiveOwnerRef.current = null;
        inFlight.current = false;
      }
    }
  }, [captureOwner, ownsOperation]);

  const runLifecycle = useCallback((action: "start" | "restart" | "shutdown") => {
    const current = conversationRef.current;
    const stopRecovery = action === "restart" && current.stopRequest?.status === "failed" && current.activeTurn === null;
    if (workspaceOperation.current !== null || documentBusyRef.current || approvalRef.current.pending !== null ||
        current.activeTurn !== null || (current.stopRequest !== null && !stopRecovery)) return;
    setSlashCatalogOwner(null);
    if (action === "restart") {
      resumeSelectionRef.current = conversationRef.current.selected;
      resumeDraftRef.current = conversationRef.current.draft;
      bindingGenerationRef.current = null;
      markExtensionsRestarting();
    }
    const operation = action === "start" ? api.start : action === "restart" ? api.restart : api.shutdown;
    void runExclusive(action, async (owner) => {
      const snapshot = await operation();
      if (lifecycleResultIsStale({
        ownerToken: owner.token, currentOwnerToken: exclusiveOwnerRef.current?.token,
        ownerProjectEpoch: owner.projectEpoch, projectEpoch: projectEpochRef.current,
        snapshotGeneration: snapshot.generation, generation: generationRef.current,
      })) return;
      applyBackendSnapshot(snapshot, action);
    });
  }, [applyBackendSnapshot, runExclusive]);

  const loadDiagnostics = useCallback((force: boolean) => {
    const generation = state.snapshot?.generation;
    if (generation === undefined || (!force && diagnosticsAttempt.current === generation)) return;
    diagnosticsAttempt.current = generation;
    void runExclusive("diagnostics", async (owner) => {
      const data = await api.runtimeDiagnostics();
      if (!ownsOperation(owner, exclusiveOwnerRef.current)) return;
      dispatch({ type: "diagnostics-succeeded", diagnostics: toBoundedDiagnostics(data) });
    });
  }, [ownsOperation, runExclusive, state.snapshot?.generation]);

  useEffect(() => {
    if (state.phase === "backend-ready" && state.snapshot?.lifecycle === "ready" && state.diagnostics === null && state.activeAction === null) loadDiagnostics(false);
  }, [loadDiagnostics, state.activeAction, state.diagnostics, state.phase, state.snapshot?.lifecycle]);

  const loadHistory = useCallback(async (generation: number) => {
    const currentProject = projectRef.current;
    if (currentProject === null || bindingGenerationRef.current !== generation || generation !== generationRef.current) return;
    const owner = captureOwner("project history");
    historyLoading.current = owner;
    const isCurrent = () => ownsOperation(owner, historyLoading.current);
    setWorkspaceIssue(null);
    try {
      const loaded = await loadSelectedProjectHistory(currentProject.projectId, api.sessionList, isCurrent);
      if (!isCurrent() || loaded === null) return;
      setSessionList(loaded);
      setHistoryGeneration(generation);
    } catch (error) {
      if (isCurrent()) {
        setHistoryGeneration(generation);
        setWorkspaceIssue(workspaceError(error));
      }
    } finally {
      if (isCurrent()) historyLoading.current = null;
    }
  }, [captureOwner, ownsOperation, setHistoryGeneration]);

  const renameConversation = useCallback(async () => {
    const target = renameDialog;
    if (target === null || !ownsOperation(target.owner, target.owner) ||
        projectRef.current?.projectId !== target.projectId || bindingGenerationRef.current !== generationRef.current ||
        state.snapshot?.lifecycle !== "ready" || state.activeAction !== null ||
        sessionList?.projectId !== target.projectId ||
        !sessionList.items.some((item) => item.sessionId === target.sessionId && item.status === "ready")) return;
    const title = target.title.trim();
    if (title.length === 0 || new TextEncoder().encode(title).length > 256) return;
    const operation = beginWorkspaceOperation("Renaming conversation");
    if (operation === null) return;
    const isCurrent = () => ownsOperation(operation, workspaceOperation.current);
    setRenameDialog({ ...target, issue: null });
    try {
      const result = await api.sessionRename({ projectId: target.projectId, sessionId: target.sessionId, title });
      if (!isCurrent()) return;
      historyLoading.current = null;
      setSessionList((list) => list === null || list.projectId !== target.projectId ? list : {
        ...list, items: list.items.map((item) => item.sessionId === target.sessionId ? { ...item, title: result.title } : item),
      });
      setRenameDialog(null);
      conversationMenuReturnFocusRef.current?.focus();
    } catch (error) {
      if (isCurrent()) setRenameDialog({ ...target, issue: workspaceError(error).message });
    } finally {
      finishWorkspaceOperation(operation);
    }
  }, [beginWorkspaceOperation, finishWorkspaceOperation, ownsOperation, renameDialog, sessionList, state.activeAction, state.snapshot?.lifecycle]);

  const chooseProject = useCallback(async (action: "inspect" | "open" | "initialize", browse = false) => {
    if (conversationRef.current.activeTurn !== null || approvalRef.current.pending !== null ||
        documentBusyRef.current || documentConflict !== null) return;
    const operation = beginWorkspaceOperation(action === "inspect" ? "Inspecting project" : "Opening project");
    if (operation === null) return;
    const generation = operation.generation;
    const isCurrent = () => ownsOperation(operation, workspaceOperation.current);
    setChooserIssue(null);
    try {
      let selectedRoot = candidate?.rootPath ?? candidateRoot;
      if (browse) {
        const picked = await api.pickProject(selectedRoot || null);
        if (picked === null || !isCurrent()) return;
        selectedRoot = picked;
        setCandidateRoot(picked);
        setCandidate(null);
      }
      if (action !== "inspect") {
        if ((conversationRef.current.draft.length > 0 || conversationRef.current.draftReferences.length > 0) && !discardDraft) {
          setChooserIssue("Confirm discarding the unsent draft and references, or cancel to keep it.");
          return;
        }
        if (documentRef.current !== null && documentRef.current.sourceText !== documentBaselineRef.current?.sourceText && dirtyChoice === "save") {
          const saved = await saveDocument(operation);
          if (!isCurrent()) return;
          if (!saved) {
            setChooserIssue("The document was not saved. Resolve the save issue before switching.");
            return;
          }
        }
      }
      if (!isCurrent()) return;
      if (action === "initialize" && candidate?.status === "needs_configuration" && candidateHistory !== candidate.historyDirectory) {
        setChooserIssue("Inspect the edited history location before initializing.");
        return;
      }
      const data = await api.workspaceSelect({
        rootPath: selectedRoot,
        action,
        ...(action === "inspect" && !browse && candidate?.status === "needs_configuration" ? { historyDirectory: candidateHistory } : {}),
        ...(action === "initialize" ? {
          historyDirectory: candidateHistory,
          expectedFingerprint: candidate?.researchFingerprint ?? null,
        } : {}),
      });
      if (!isCurrent()) return;
      if (data.status !== "opened") {
        setCandidate(data);
        setCandidateRoot(data.rootPath);
        setCandidateHistory(data.historyDirectory);
        return;
      }
      finishWorkspaceOperation(operation);
      projectEpochRef.current += 1;
      frameOwnerRef.current = null;
      projectRef.current = data;
      bindingGenerationRef.current = generation;
      setProject(data);
      setRootPath(data.rootPath);
      applyConversation({ type: "project-opened", generation, projectEpoch: projectEpochRef.current });
      setHistoryGeneration(null);
      setSessionList(null);
      setSlashCatalogOwner(null);
      setTranscript(null);
      setSelectionPreview(null);
      setLiveTurns([]);
      setPendingUserText(null);
      setHistoryIssue(null);
      resetExtensions();
      commitApproval(clearApproval(approvalRef.current));
      updateDocument(null);
      documentBaselineRef.current = null;
      submittedDocumentRef.current = null;
      selectedSkillNamesRef.current.clear();
      resumeSelectionRef.current = null;
      resumeDraftRef.current = null;
      setDocumentConflict(null);
      setLastDocumentAction(null);
      setDocumentNotice(null);
      setWorkspaceIssue(null);
      setChooserOpen(false);
      setChatSelection(null);
      setReferenceIssue(null);
      setDiscardDraft(false);
      setDirtyChoice("save");
      await loadHistory(generation);
    } catch (error) {
      if (isCurrent()) {
        setChooserIssue(workspaceError(error).message);
      }
    } finally { finishWorkspaceOperation(operation); }
  }, [applyConversation, beginWorkspaceOperation, candidate, candidateHistory, candidateRoot, dirtyChoice, discardDraft, documentConflict, finishWorkspaceOperation, loadHistory, ownsOperation, saveDocument, setHistoryGeneration, updateDocument]);

  const showProjectChooser = useCallback(() => {
    if (conversationRef.current.activeTurn !== null || conversationRef.current.stopRequest !== null || approvalRef.current.pending !== null ||
        documentBusyRef.current || workspaceOperation.current !== null || inFlight.current) return;
    if (documentConflict !== null) {
      setWorkspaceIssue({ code: "DOCUMENT_CONFLICT", message: "Resolve or cancel the document conflict before switching projects.", retryable: false, source: "business" });
      return;
    }
    setCandidate(null);
    setCandidateRoot(projectRef.current?.rootPath ?? "");
    setCandidateHistory("");
    setChooserIssue(null);
    setDiscardDraft(false);
    setDirtyChoice("save");
    setChooserOpen(true);
  }, [documentConflict]);

  const loadMoreSessions = useCallback(() => {
    const current = sessionList;
    if (current === null || !current.hasMore) return;
    const projectId = current.projectId;
    const operation = beginWorkspaceOperation("Loading more conversations");
    if (operation === null) return;
    const isCurrent = () => ownsOperation(operation, workspaceOperation.current);
    const offset = current.items.length;
    void (async () => {
      try {
        const data = await api.sessionList({ projectId, offset, limit: 50 });
        if (!isCurrent()) return;
        setSessionList((existing) => {
          if (existing === null || existing.projectId !== projectId || existing.items.length !== offset) return existing;
          const items = mergeSessionItems(existing.items, data.items);
          return { ...data, items, offset: 0, limit: items.length };
        });
      } catch (error) {
        if (isCurrent()) setWorkspaceIssue(workspaceError(error));
      } finally {
        finishWorkspaceOperation(operation);
      }
    })();
  }, [ownsOperation, beginWorkspaceOperation, finishWorkspaceOperation, sessionList]);

  useEffect(() => {
    const generation = state.snapshot?.generation;
    if (generation === undefined || state.snapshot?.lifecycle !== "ready" || state.diagnostics === null ||
        project === null || historyGeneration === generation || (historyLoading.current !== null && ownsOperation(historyLoading.current, historyLoading.current)) ||
        workspaceOperation.current !== null) return;
    if (bindingGenerationRef.current === generation) {
      void loadHistory(generation);
      return;
    }
    const operation = beginWorkspaceOperation("Reopening selected project");
    if (operation === null) return;
    const isCurrent = () => ownsOperation(operation, workspaceOperation.current);
    void api.workspaceSelect({ rootPath: project.rootPath, action: "open" }).then(async (opened) => {
      if (!isCurrent()) return;
      if (opened.status !== "opened" || opened.projectId !== project.projectId || opened.rootPath !== project.rootPath) {
        throw protocolMismatch("The selected project could not be restored. Open it explicitly to continue.");
      }
      finishWorkspaceOperation(operation);
      projectEpochRef.current += 1;
      frameOwnerRef.current = null;
      applyConversation({ type: "project-opened", generation, projectEpoch: projectEpochRef.current, preserveDraft: true });
      projectRef.current = opened;
      bindingGenerationRef.current = generation;
      setProject(opened);
      await loadHistory(generation);
    }).catch((error: unknown) => {
      if (!isCurrent()) return;
      setHistoryGeneration(generation);
      setChooserIssue(workspaceError(error).message);
      setCandidate(null);
      setCandidateRoot(project.rootPath);
      setChooserOpen(true);
    }).finally(() => finishWorkspaceOperation(operation));
  }, [applyConversation, beginWorkspaceOperation, historyGeneration, finishWorkspaceOperation, loadHistory, ownsOperation, project, setHistoryGeneration, state.diagnostics, state.snapshot?.generation, state.snapshot?.lifecycle]);

  const focusComposer = useCallback((owner: WorkspaceOperationOwner = captureOwner("composer focus")) => {
    scheduleOwnedFrame(owner, () => composerRef.current?.focus());
  }, [captureOwner, scheduleOwnedFrame]);

  const addDocumentReference = useCallback((snapshot: DocumentContextDto) => {
    if (conversation.backendGeneration !== generationRef.current || conversation.projectEpoch !== projectEpochRef.current ||
        conversationRef.current.selected === null || !sameSelection(conversation.selected, conversationRef.current.selected) ||
        conversationRef.current.activeTurn !== null ||
        workspaceOperation.current !== null || snapshot.rootPath !== projectRef.current?.rootPath) return;
    const owner = captureOwner("document reference");
    try {
      applyConversation({ type: "reference-added", generation: owner.generation, projectEpoch: owner.projectEpoch, reference: documentReference(snapshot, newLogicalTurnId()) });
      setReferenceIssue(null);
    } catch (error) { setReferenceIssue(error instanceof Error ? error.message : "Could not capture the document selection."); }
  }, [applyConversation, captureOwner, conversation.backendGeneration, conversation.projectEpoch, conversation.selected]);

  const captureChatSelection = useCallback(() => {
    const selection = document.getSelection();
    if (selection === null || selection.isCollapsed || selection.rangeCount !== 1) { setChatSelection(null); return; }
    const range = selection.getRangeAt(0);
    const element = (node: Node) => node.nodeType === 1 ? node as Element : node.parentElement;
    const first = element(range.startContainer)?.closest<HTMLElement>("[data-reference-message]");
    const last = element(range.endContainer)?.closest<HTMLElement>("[data-reference-message]");
    if (first === undefined || first === null || last !== first) {
      setChatSelection(null);
      if (first !== undefined && first !== null || last !== undefined && last !== null) setReferenceIssue("Select text within one message at a time.");
      return;
    }
    const { projectId, sessionId, turnId, messageRole: role } = first.dataset;
    if (!first.isConnected || projectId === undefined || projectId !== projectRef.current?.projectId || sessionId === undefined || turnId === undefined ||
        (role !== "user" && role !== "assistant")) { setChatSelection(null); return; }
    const captured = visibleMessageRange(first, range.startContainer, range.startOffset, range.endContainer, range.endOffset);
    if (captured === null || captured.text.trim() === "") { setChatSelection(null); return; }
    const rect = range.getBoundingClientRect();
    setChatSelection({ ...captured, projectId, sessionId, turnId, role, owner: captureOwner("chat selection"),
      top: Math.min(window.innerHeight - 44, rect.bottom + 6), left: Math.max(8, Math.min(window.innerWidth - 180, rect.left)) });
    setReferenceIssue(null);
  }, [captureOwner]);

  useEffect(() => {
    document.addEventListener("selectionchange", captureChatSelection);
    return () => document.removeEventListener("selectionchange", captureChatSelection);
  }, [captureChatSelection]);

  const addChatReference = useCallback(async () => {
    const captured = chatSelection;
    const selected = conversationRef.current.selected;
    if (captured === null || selected === null || selected.projectId !== captured.projectId || selected.sessionId !== captured.sessionId ||
        captured.owner.generation !== generationRef.current || captured.owner.projectEpoch !== projectEpochRef.current) return;
    const owner = beginWorkspaceOperation("Adding chat reference");
    if (owner === null) return;
    try {
      const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(captured.visibleText));
      if (!ownsOperation(owner, workspaceOperation.current)) return;
      const messageFingerprint = Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
      applyConversation({ type: "reference-added", generation: owner.generation, projectEpoch: owner.projectEpoch, reference: {
        referenceId: newLogicalTurnId(), kind: "chat", text: captured.text,
        chat: { projectId: captured.projectId, sessionId: captured.sessionId, turnId: captured.turnId, role: captured.role,
          messageFingerprint, startUtf16: captured.startUtf16, endUtf16: captured.endUtf16 },
      } });
      setChatSelection(null);
      setReferenceIssue(null);
      document.getSelection()?.removeAllRanges();
    } catch (error) {
      if (ownsOperation(owner, workspaceOperation.current)) setReferenceIssue(error instanceof Error ? error.message : "Could not capture the chat selection.");
    } finally { finishWorkspaceOperation(owner); }
  }, [applyConversation, beginWorkspaceOperation, chatSelection, finishWorkspaceOperation, ownsOperation]);

  const stopTurn = useCallback(() => {
    const current = conversationRef.current;
    if (inFlight.current || (current.stopRequest !== null && current.stopRequest.status !== "failed")) return;
    const target = current.stopRequest ?? current.activeTurn;
    if (target === null || current.backendGeneration !== generationRef.current || current.projectEpoch !== projectEpochRef.current) return;
    const generation = current.backendGeneration, projectEpoch = current.projectEpoch;
    const retryingStop = current.stopRequest?.status === "failed";
    const correlation = { generation, projectEpoch, projectId: target.projectId, sessionId: target.sessionId,
      requestId: target.requestId, turnId: target.turnId };
    applyConversation({ type: "stop-requested", generation, projectEpoch });
    workingDocumentSourcesRef.current = null;
    const pending = Promise.resolve().then(() => api.sessionStop({
      sessionId: target.sessionId, turnId: target.turnId, parentRequestId: target.requestId,
    })).then(async () => {
      const next = applyConversation({ type: "stop-succeeded", ...correlation });
      if (!retryingStop || next.stopRequest !== null || next.activeTurn !== null ||
          generation !== generationRef.current || projectEpoch !== projectEpochRef.current || !sameSelection(next.selected, target)) return;
      const operation = beginWorkspaceOperation("Refreshing saved conversation");
      if (operation === null) return;
      try {
        await loadHistory(generation);
        if (!ownsOperation(operation, workspaceOperation.current) || state.session?.sessionId !== target.sessionId) return;
        if (next.failure?.turnLifecycle?.accepted) {
          const data = await fetchTranscriptPage(target.projectId, target.sessionId,
            transcriptTailOffset(state.session.turnCount + 1), TRANSCRIPT_PAGE_SIZE, api.sessionTranscript);
          if (!ownsOperation(operation, workspaceOperation.current)) return;
          dispatch({ type: "session-created", session: { ...state.session, turnCount: data.total } });
          setTranscript(transcriptViewFrom(target.projectId, target.sessionId, data));
          setLiveTurns([]);
        }
        setPendingUserText(null);
      } catch (error: unknown) {
        if (ownsOperation(operation, workspaceOperation.current)) {
          setHistoryIssue(`The turn stopped, but its saved conversation could not be refreshed. ${workspaceError(error).message}`);
        }
      } finally { finishWorkspaceOperation(operation); }
    }).catch((error: unknown) => {
      applyConversation({ type: "stop-failed", ...correlation, message: workspaceError(error).message });
    }).finally(() => {
      if (stopPromiseRef.current === pending) stopPromiseRef.current = null;
    });
    stopPromiseRef.current = pending;
  }, [applyConversation, beginWorkspaceOperation, finishWorkspaceOperation, loadHistory, ownsOperation, state.session]);

  const deleteConversation = useCallback(async () => {
    const target = deleteDialog;
    if (target === null || deleteOwnerRef.current !== null || !ownsOperation(target.owner, target.owner) ||
        projectRef.current?.projectId !== target.projectId || bindingGenerationRef.current !== generationRef.current ||
        state.snapshot?.lifecycle !== "ready" || inFlight.current) return;
    const owner = target.owner;
    deleteOwnerRef.current = owner;
    const isCurrent = () => ownsOperation(owner, deleteOwnerRef.current);
    let operation: WorkspaceOperationOwner | null = null;
    setDeleteDialog({ ...target, issue: null, status: "stopping" });
    try {
      const settlement = turnSettlementPromiseRef.current;
      const running = conversationRef.current.stopRequest ?? conversationRef.current.activeTurn;
      if (running !== null) {
        if (!sameSelection(running, target)) throw new Error("Wait for the current conversation to finish before deleting another conversation.");
        stopTurn();
        await stopPromiseRef.current;
        if (!isCurrent()) return;
        if (conversationRef.current.stopRequest?.status === "failed") {
          throw new Error(conversationRef.current.stopRequest.error ?? "The conversation could not be stopped.");
        }
      }
      await settlement;
      if (!isCurrent()) return;
      await documentApplyPromiseRef.current;
      if (!isCurrent()) return;
      if (conversationRef.current.activeTurn !== null || conversationRef.current.stopRequest !== null) {
        throw new Error("The conversation has not finished stopping. Retry deletion after it stops.");
      }
      operation = beginWorkspaceOperation("Deleting conversation");
      if (operation === null) throw new Error("The workspace is still busy. Retry deletion when the current operation finishes.");
      setDeleteDialog({ ...target, issue: null, status: "deleting" });
      await api.sessionDelete({ projectId: target.projectId, sessionId: target.sessionId });
      if (!isCurrent() || !ownsOperation(operation, workspaceOperation.current)) return;
      historyLoading.current = null;
      const selectedDeleted = sameSelection(conversationRef.current.selected, target);
      setSessionList((list) => {
        if (list === null || list.projectId !== target.projectId) return list;
        const items = list.items.filter((item) => item.sessionId !== target.sessionId);
        return { ...list, items, total: Math.max(0, list.total - (list.items.length - items.length)) };
      });
      if (sameSelection(resumeSelectionRef.current, target)) {
        resumeSelectionRef.current = null;
        resumeDraftRef.current = null;
      }
      if (selectedDeleted) {
        applyConversation({ type: "conversation-deleted", generation: owner.generation, projectEpoch: owner.projectEpoch,
          projectId: target.projectId, sessionId: target.sessionId });
        dispatch({ type: "session-cleared", sessionId: target.sessionId });
        setSlashCatalogOwner(null);
        setTranscript(null);
        setSelectionPreview(null);
        setLiveTurns([]);
        setPendingUserText(null);
        setHistoryIssue(null);
        resetExtensions();
        setChatSelection(null);
        setReferenceIssue(null);
        submittedDocumentRef.current = null;
        workingDocumentSourcesRef.current = null;
      }
      await loadHistory(owner.generation);
      if (!isCurrent()) return;
      setDeleteDialog(null);
      scheduleOwnedFrame(operation, () => document.getElementById("main-workspace")?.focus());
    } catch (error) {
      if (isCurrent()) setDeleteDialog({ ...target, issue: workspaceError(error).message, status: null });
    } finally {
      if (operation !== null) finishWorkspaceOperation(operation);
      if (deleteOwnerRef.current === owner) deleteOwnerRef.current = null;
    }
  }, [applyConversation, beginWorkspaceOperation, deleteDialog, finishWorkspaceOperation, loadHistory, ownsOperation,
    scheduleOwnedFrame, state.snapshot?.lifecycle, stopTurn]);

  const resolvePendingApproval = useCallback((approved: boolean, expectedApprovalId?: string) => {
    const target = approvalToResolve(approvalRef.current, conversationRef.current.stopRequest !== null, expectedApprovalId);
    if (target === null) return;
    const { approval: resolving, owner } = target;
    const isCurrent = () => ownsOperation(owner, approvalRef.current.owner) &&
      approvalRef.current.pending?.approvalId === resolving.approvalId;
    commitApproval(beginApprovalResolve(approvalRef.current));
    void api.approvalResolve({
      approvalId: resolving.approvalId,
      parentRequestId: resolving.parentRequestId,
      turnId: resolving.turnId,
      approved,
      ...(resolving.operation?.startsWith("document.") && documentRef.current !== null ? { documentContext: documentContextPayload(
        documentOperationContext(documentRef.current, documentRequestRef.current?.turnId === resolving.turnId ? documentRequestRef.current.context : undefined),
      ) } : {}),
    }).catch((error: unknown) => {
      if (isCurrent()) setWorkspaceIssue(workspaceError(error));
    }).finally(() => {
      if (!isCurrent()) return;
      commitApproval(clearApproval(approvalRef.current, true));
      focusComposer(owner);
    });
  }, [commitApproval, focusComposer, ownsOperation]);

  const returnApprovalFocus = useCallback(() => {
    const { pending, owner } = approvalRef.current;
    if (pending === null && owner !== null && ownsOperation(owner, owner)) focusComposer(owner);
  }, [focusComposer, ownsOperation]);

  useEffect(() => {
    if (pendingApproval === null) return;
    const expiry = approvalExpiry(pendingApproval.expiresAt, Date.now());
    if (expiry.kind === "expired") {
      resolvePendingApproval(false, pendingApproval.approvalId);
      return;
    }
    const timeout = window.setTimeout(() => resolvePendingApproval(false, pendingApproval.approvalId), expiry.delayMs);
    return () => window.clearTimeout(timeout);
  }, [pendingApproval, resolvePendingApproval]);

  useEffect(() => {
    if (pendingApproval === null) return;
    // Drop an approval only when no request that can raise one still owns it;
    // bibliography.add raises citation.save outside any turn or document operation.
    commitApproval(clearStaleApproval(approvalRef.current, conversation.activeTurn?.requestId ?? null));
  }, [commitApproval, conversation.activeTurn, pendingApproval]);

  const selectConversation = useCallback(async (projectId: string, session: SessionSummaryDto) => {
    if (conversationRef.current.activeTurn !== null || projectRef.current?.projectId !== projectId ||
        bindingGenerationRef.current !== generationRef.current || documentBusyRef.current || approvalRef.current.pending !== null) return;
    if (sameSelection(conversationRef.current.selected, { projectId, sessionId: session.sessionId })) {
      focusComposer();
      return;
    }
    const restoringSelection = resumeSelectionRef.current?.projectId === projectId && resumeSelectionRef.current.sessionId === session.sessionId;
    if (!restoringSelection && (conversationRef.current.draft.length > 0 || conversationRef.current.draftReferences.length > 0) &&
        !window.confirm("Discard the unsent draft and references and select this conversation?")) return;
    const operation = beginWorkspaceOperation("Selecting conversation");
    if (operation === null) return;
    const previousSlashCatalogOwner = slashCatalogOwner;
    setSlashCatalogOwner(null);
    setSelectionPreview(null);
    const generation = operation.generation;
    const isCurrent = () => ownsOperation(operation, workspaceOperation.current);
    let selectionApplied = false;
    try {
      const transcriptData = await selectConversationWithPreview(projectId, session, {
        isCurrent,
        onPreview: (data) => {
          setSelectionPreview({ title: session.title, transcript: transcriptViewFrom(projectId, session.sessionId, data) });
          scheduleOwnedFrame(operation, () => transcriptEndRef.current?.scrollIntoView({ block: "end" }));
        },
        onSelected: (selected) => {
          setSlashCatalogOwner({ generation, projectId, sessionId: selected.sessionId });
          dispatch({ type: "session-created", session: selected });
          observeExtensionsRevision(selected.extensionRevision);
          applyConversation({ type: "conversation-selected", generation, projectEpoch: operation.projectEpoch, preserveDraft: restoringSelection, projectId, sessionId: session.sessionId });
          selectionApplied = true;
          setChatSelection(null);
          setReferenceIssue(null);
          if (!restoringSelection) {
            resumeDraftRef.current = null;
            resumeSelectionRef.current = null;
          }
          setHistoryIssue(null);
          setLiveTurns([]);
          setPendingUserText(null);
          setTranscript({ projectId, sessionId: session.sessionId, status: "unavailable", issue: "Loading saved transcript…", items: [], offset: 0, total: selected.turnCount, hasOlder: false });
        },
      }, api);
      if (transcriptData === null || !isCurrent()) return;
      setTranscript(transcriptViewFrom(projectId, session.sessionId, transcriptData));
      setSelectionPreview(null);
      const submitted = conversationRef.current.submittedTurn;
      const savedSubmission = submitted !== null && sameSelection(submitted, { projectId, sessionId: session.sessionId })
        ? transcriptData.items.find((turn) => turn.turnId === submitted.turnId) : undefined;
      if (savedSubmission !== undefined) {
        applyConversation({ type: "turn-acceptance-reconciled", generation, projectEpoch: operation.projectEpoch,
          projectId, sessionId: session.sessionId, turnId: savedSubmission.turnId, state: savedSubmission.state });
        resumeDraftRef.current = null;
        resumeSelectionRef.current = null;
      }
      const retryTarget = latestRetryableTranscriptTurn(restoringSelection && submitted !== null
        ? savedSubmission === undefined ? [] : [savedSubmission] : transcriptData.items);
      if (retryTarget !== null && resumeDraftRef.current === null) {
        applyConversation({
          type: "retry-target-restored",
          submittedContext: retryTarget.submittedContext ?? null,
          generation,
          projectEpoch: operation.projectEpoch,
          projectId,
          sessionId: session.sessionId,
          turnId: retryTarget.turnId,
          userText: retryTarget.userText,
          state: retryTarget.state,
          message: retryTarget.failureMessage ?? "The saved turn did not complete.",
          retryable: true,
        });
      }
      if (resumeDraftRef.current !== null) {
        applyConversation({ type: "draft-changed", draft: resumeDraftRef.current });
        resumeDraftRef.current = null;
        resumeSelectionRef.current = null;
      }
      scheduleOwnedFrame(operation, () => transcriptEndRef.current?.scrollIntoView({ block: "end" }));
      focusComposer(operation);
    } catch (error) {
      if (!isCurrent()) return;
      const safe = workspaceError(error);
      setSelectionPreview(null);
      if (selectionApplied) {
        setTranscript({ projectId, sessionId: session.sessionId, status: "unavailable", issue: safe.message, items: [], offset: 0, total: 0, hasOlder: false });
      } else {
        setSlashCatalogOwner(previousSlashCatalogOwner);
      }
      setWorkspaceIssue(safe);
      focusComposer(operation);
    } finally { finishWorkspaceOperation(operation); }
  }, [ownsOperation, scheduleOwnedFrame, applyConversation, beginWorkspaceOperation, finishWorkspaceOperation, focusComposer, slashCatalogOwner]);

  useEffect(() => {
    if (sessionList === null || conversation.selected !== null || workspaceBusy !== null) return;
    const summary = conversationToRestore(projectRef.current?.projectId ?? null, sessionList, resumeSelectionRef.current);
    if (summary !== null) void selectConversation(sessionList.projectId, summary);
  }, [conversation.selected, selectConversation, sessionList, workspaceBusy]);

  const activeProjectId = bindingGenerationRef.current === state.snapshot?.generation ? project?.projectId ?? null : null;

  const createSession = useCallback(() => {
    if (activeProjectId === null || conversationRef.current.activeTurn !== null || documentBusyRef.current || approvalRef.current.pending !== null) return;
    if (resumeDraftRef.current === null && (conversationRef.current.draft.length > 0 || conversationRef.current.draftReferences.length > 0) &&
        !window.confirm("Discard the unsent draft and references and create a new conversation?")) return;
    const operation = beginWorkspaceOperation("Creating conversation");
    if (operation === null) return;
    setSlashCatalogOwner(null);
    const generation = operation.generation;
    const isCurrent = () => ownsOperation(operation, workspaceOperation.current);
    void (async () => {
      try {
        const session = await api.sessionCreate({ projectId: activeProjectId });
        if (!isCurrent()) return;
        setSlashCatalogOwner({ generation, projectId: activeProjectId, sessionId: session.sessionId });
        dispatch({ type: "session-created", session });
        observeExtensionsRevision(session.extensionRevision);
        applyConversation({ type: "conversation-selected", generation, projectEpoch: operation.projectEpoch, preserveDraft: resumeDraftRef.current !== null, projectId: activeProjectId, sessionId: session.sessionId });
        if (resumeDraftRef.current !== null) {
          applyConversation({ type: "draft-changed", draft: resumeDraftRef.current });
          resumeDraftRef.current = null;
          resumeSelectionRef.current = null;
        }
        setChatSelection(null);
        setReferenceIssue(null);
        setTranscript({ projectId: activeProjectId, sessionId: session.sessionId, status: "ready", issue: null, items: [], offset: 0, total: 0, hasOlder: false });
        setLiveTurns([]);
        setPendingUserText(null);
        setHistoryIssue(null);
        focusComposer(operation);
      } catch (error) {
        if (!isCurrent()) return;
        setWorkspaceIssue(workspaceError(error));
        focusComposer(operation);
      } finally { finishWorkspaceOperation(operation); }
    })();
  }, [ownsOperation, activeProjectId, applyConversation, beginWorkspaceOperation, finishWorkspaceOperation, focusComposer]);

  const loadOlder = useCallback(() => {
    const current = transcript;
    if (current === null || current.offset <= 0) return;
    const operation = beginWorkspaceOperation("Loading older turns");
    if (operation === null) return;
    const isCurrent = () => ownsOperation(operation, workspaceOperation.current);
    const container = transcriptRef.current;
    const previousHeight = container?.scrollHeight ?? 0;
    const previousTop = container?.scrollTop ?? 0;
    const limit = Math.min(TRANSCRIPT_PAGE_SIZE, current.offset);
    const offset = current.offset - limit;
    void (async () => {
      try {
        const data = await fetchTranscriptPage(current.projectId, current.sessionId, offset, limit, api.sessionTranscript);
        if (!isCurrent()) return;
        setTranscript((value) => value === null || value.projectId !== current.projectId || value.sessionId !== current.sessionId ? value : { ...value, status: data.status, issue: data.issue, items: mergeTranscriptItems(data.items, value.items), offset: data.offset, total: data.total, hasOlder: data.status === "ready" && data.offset > 0 });
        scheduleOwnedFrame(operation, () => { if (container !== null) container.scrollTop = previousTop + container.scrollHeight - previousHeight; });
      } catch (error) {
        if (isCurrent()) setWorkspaceIssue(workspaceError(error));
      }
      finally { finishWorkspaceOperation(operation); }
    })();
  }, [ownsOperation, scheduleOwnedFrame, beginWorkspaceOperation, finishWorkspaceOperation, transcript]);

  const sendTurn = useCallback(async () => {
    const selected = conversationRef.current.selected;
    const draft = turnSubmissionText(conversationRef.current);
    const selectedProject = projectRef.current;
    const session = state.session;
    if (selected === null || selectedProject === null || session === null || draft.trim().length === 0 ||
        conversationRef.current.activeTurn !== null || conversationRef.current.stopRequest !== null || workspaceOperation.current !== null || inFlight.current ||
        documentBusyRef.current || approvalRef.current.pending !== null || bindingGenerationRef.current !== generationRef.current ||
        selectedProject.projectId !== selected.projectId) return;
    const submission = nextTurnSubmission(conversationRef.current, newLogicalTurnId);
    if (submission.retry && !retrySettingsMatch(conversationRef.current.submittedContext, session.permissionMode, session.thinkingMode)) {
      setReferenceIssue("The saved turn uses different Permission or Thinking settings. Send a new turn with the current settings, or restore those settings explicitly before retrying.");
      return;
    }
    const owner = beginWorkspaceOperation(submission.retry ? "Preparing saved retry" : "Preparing submission");
    if (owner === null) return;
    const generation = owner.generation;
    const isCurrent = () => ownsOperation(owner, turnOwnerRef.current) && sameSelection(conversationRef.current.selected, selected);
    const turnId = submission.turnId;
    const references = structuredClone(conversationRef.current.draftReferences);
    const background = backgroundDocumentContext(documentRef.current);
    let submittedContext = submission.retry ? structuredClone(conversationRef.current.submittedContext) : null;
    let tracked;
    try {
      if (!submission.retry) {
        const inspected = await api.workspaceSelect({ rootPath: selectedProject.rootPath, action: "inspect" });
        if (!ownsOperation(owner, workspaceOperation.current)) return;
        if (inspected.status !== "ready" || inspected.projectId !== selectedProject.projectId ||
            inspected.rootPath !== selectedProject.rootPath || inspected.historyDirectory !== selectedProject.historyDirectory) {
          throw new Error("The project history configuration changed. Reopen the project before sending; your draft is retained.");
        }
        submittedContext = {
          projectId: selected.projectId, rootPath: selectedProject.rootPath,
          permissionMode: session.permissionMode, requestedThinkingMode: session.thinkingMode,
          skillReferences: inlineSkillReferences(draft, session.loadedSkills, selectedSkillNamesRef.current),
          projectRules: { text: inspected.rulesText, fingerprint: inspected.rulesFingerprint },
          ...(background === undefined ? {} : { documentContext: background }),
          references,
        };
      }
      checkSubmissionSize(draft, submittedContext);
      if (!ownsOperation(owner, workspaceOperation.current)) return;
      tracked = api.sessionTurnTracked({
        text: draft, turnId, retry: submission.retry,
        ...(submittedContext === null ? {} : { submittedContext }),
      });
      submittedDocumentRef.current = submittedDocumentSource(submittedContext) ?? null;
      workingDocumentSourcesRef.current = submittedContext === null ? null : structuredClone({
        documentContext: submittedContext.documentContext, references: submittedContext.references,
      });
      setReferenceIssue(null);
    } catch (error) {
      if (ownsOperation(owner, workspaceOperation.current)) {
        setWorkspaceIssue(error instanceof Error && !(error instanceof BackendClientError)
          ? { code: "SUBMISSION_INVALID", message: error.message, retryable: false, source: "protocol" }
          : workspaceError(error));
        focusComposer(owner);
      }
      return;
    } finally { finishWorkspaceOperation(owner); }
    turnOwnerRef.current = owner;
    frameOwnerRef.current = null;
    setPendingUserText(draft);
    setWorkspaceIssue(null);
    applyConversation({ type: "turn-started", generation, projectEpoch: owner.projectEpoch, text: draft, submittedContext, requestId: tracked.requestId, turnId, projectId: selected.projectId, sessionId: selected.sessionId });
    const settlement = tracked.result.then(async (result) => {
      if (!isCurrent()) return;
      workingDocumentSourcesRef.current = null;
      const next = applyConversation({ type: "turn-succeeded", generation, projectEpoch: owner.projectEpoch, requestId: tracked.requestId, projectId: selected.projectId, result });
      const answer = next.latestAnswer;
      if (answer === null || answer.requestId !== tracked.requestId) {
        const active = next.activeTurn;
        if (active === null || active.requestId !== tracked.requestId) return;
        const mismatch = protocolMismatch("The backend returned a mismatched conversation result.").uiError;
        const failed = applyConversation({ type: "turn-failed", generation, projectEpoch: owner.projectEpoch, requestId: tracked.requestId, projectId: selected.projectId, sessionId: selected.sessionId, message: mismatch.message, retryable: mismatch.retryable });
        if (failed.failure?.requestId === tracked.requestId) {
          setPendingUserText(null);
          setWorkspaceIssue(mismatch);
          focusComposer(owner);
        }
        return;
      }
      setLiveTurns((turns) => upsertLiveTurn(turns, {
        sessionId: answer.sessionId,
        turnId: answer.turnId,
        turnNumber: answer.turnNumber,
        userText: draft,
        submittedContext,
        assistantText: answer.text,
        responseKind: answer.responseKind,
      }));
      setPendingUserText(null);
      commitApproval(clearApproval(approvalRef.current));
      if (result.extensionAction === "preview") {
        startExtensions(result.turnId);
      }
      if (state.session !== null) {
        dispatch({
          type: "session-created",
          session: {
            ...state.session,
            turnCount: Math.max(state.session.turnCount, answer.turnNumber),
          },
        });
      }
      setHistoryIssue(null);
      await stopPromiseRef.current;
      if (!isCurrent() || conversationRef.current.stopRequest !== null) return;
      await loadHistory(generation);
      if (!isCurrent()) return;
      scheduleOwnedFrame(owner, () => transcriptEndRef.current?.scrollIntoView({ block: "end" }));
      focusComposer(owner);
    }).catch(async (error: unknown) => {
      if (!isCurrent()) return;
      workingDocumentSourcesRef.current = null;
      const safe = workspaceError(error);
      const next = applyConversation({
        type: "turn-failed",
        cancelled: safe.code === "TURN_CANCELLED",
        generation,
        projectEpoch: owner.projectEpoch,
        requestId: tracked.requestId,
        projectId: selected.projectId,
        sessionId: selected.sessionId,
        message: safe.message,
        retryable: safe.retryable,
        turnLifecycle: safe.turnLifecycle ?? null,
      });
      if (next.failure?.requestId !== tracked.requestId) return;
      commitApproval(clearApproval(approvalRef.current));
      setWorkspaceIssue(safe);
      focusComposer(owner);
      await stopPromiseRef.current;
      if (!isCurrent() || conversationRef.current.stopRequest !== null) return;
      setPendingUserText(null);
      if (!isPersistedTurnFailure(next.failure) && next.submittedTurn?.accepted !== true && safe.source !== "transport") return;
      const operation = beginWorkspaceOperation("Refreshing saved conversation");
      if (operation === null) return;
      // beginWorkspaceOperation clears the banner for user gestures; this refresh is not one.
      setWorkspaceIssue(safe);
      const selectionIsCurrent = () => (
        ownsOperation(operation, workspaceOperation.current) && sameSelection(conversationRef.current.selected, selected)
      );
      await (async () => {
        try {
          await loadHistory(generation);
          const currentSession = state.session;
          if (
            !selectionIsCurrent() ||
            currentSession === null ||
            currentSession.sessionId !== selected.sessionId
          ) return;
          // A new durable failure adds one turn; a same-ID retry updates the last one.
          const data = await fetchTranscriptPage(
            selected.projectId,
            selected.sessionId,
            transcriptTailOffset(currentSession.turnCount + 1),
            TRANSCRIPT_PAGE_SIZE,
            api.sessionTranscript,
          );
          if (!selectionIsCurrent()) return;
          const savedTurn = data.items.find((turn) => turn.turnId === turnId);
          if (savedTurn !== undefined) {
            applyConversation({ type: "turn-acceptance-reconciled", generation, projectEpoch: operation.projectEpoch,
              projectId: selected.projectId, sessionId: selected.sessionId, turnId, state: savedTurn.state });
          }
          dispatch({
            type: "session-created",
            session: { ...currentSession, turnCount: data.total },
          });
          setTranscript(transcriptViewFrom(selected.projectId, selected.sessionId, data));
          setLiveTurns([]);
          setHistoryIssue(null);
          scheduleOwnedFrame(operation, () => transcriptEndRef.current?.scrollIntoView({ block: "end" }));
        } catch (reconciliationError: unknown) {
          if (!selectionIsCurrent()) return;
          const issue = workspaceError(reconciliationError);
          setWorkspaceIssue(safe);
          setHistoryIssue(`${next.submittedTurn?.accepted || isPersistedTurnFailure(next.failure) ? "The prompt is saved, but" : "Delivery is unconfirmed and"} the conversation state could not be refreshed. ${issue.message}`);
        } finally {
          finishWorkspaceOperation(operation);
        }
      })();
    }).finally(() => {
      if (turnSettlementPromiseRef.current === settlement) turnSettlementPromiseRef.current = null;
    });
    turnSettlementPromiseRef.current = settlement;
  }, [captureOwner, ownsOperation, scheduleOwnedFrame, applyConversation, beginWorkspaceOperation, finishWorkspaceOperation, focusComposer, loadHistory, state.session]);

  const sendNewTurn = useCallback(() => {
    applyConversation({ type: "new-turn-requested", generation: generationRef.current, projectEpoch: projectEpochRef.current });
    void sendTurn();
  }, [applyConversation, sendTurn]);

  const previewExtensions = useCallback(() => {
    const flow = extensionFlow;
    if (!canPreviewExtensions(flow)) return;
    const operation = beginWorkspaceOperation("Previewing extensions");
    if (operation === null) return;
    const isCurrent = () => ownsOperation(operation, workspaceOperation.current);
    updateExtensionsFor(flow.triggerTurnId, beginExtensionPreview);
    void api.extensionsPreview().then((preview) => {
      if (!isCurrent()) return;
      updateExtensionsFor(flow.triggerTurnId, (current) => receiveExtensionPreview(current, preview));
    }).catch((error: unknown) => {
      if (!isCurrent()) return;
      const safe = workspaceError(error);
      updateExtensionsFor(flow.triggerTurnId, (current) => failExtensionFlow(current, safe.message));
    }).finally(() => finishWorkspaceOperation(operation));
  }, [ownsOperation, beginWorkspaceOperation, extensionFlow, finishWorkspaceOperation, updateExtensionsFor]);

  const decideBinding = useCallback((
    bindingHash: string,
    decision: Exclude<ExtensionBindingDecision, null>,
  ) => {
    updateExtensions((current) => current === null ? null : decideExtensionBinding(current, bindingHash, decision));
  }, [updateExtensions]);

  const applyExtensions = useCallback(() => {
    const flow = extensionFlow;
    if (flow === null) return;
    const plan = planExtensionApply(flow, state.session?.permissionMode, newLogicalTurnId);
    if (plan === null) return;
    const { submitting, request } = plan;
    const operation = beginWorkspaceOperation("Applying extensions");
    if (operation === null) return;
    const isCurrent = () => ownsOperation(operation, workspaceOperation.current);
    updateExtensionsFor(flow.triggerTurnId, () => submitting);
    void api.extensionsApply(request).then((report) => {
      if (!isCurrent()) return;
      if (report.sessionId !== state.session?.sessionId) {
        throw protocolMismatch("The backend returned an apply result for a different conversation turn.");
      }
      const alreadyVisible =
        (transcript?.sessionId === report.sessionId &&
          transcript.items.some((turn) => turn.turnId === report.turnId)) ||
        liveTurns.some((turn) =>
          turn.sessionId === report.sessionId && turn.turnId === report.turnId
        );
      updateExtensions((current) => settleExtensionApply(
        current,
        flow.triggerTurnId,
        request.turnId,
        report,
        state.session?.extensionRevision ?? -1,
      ));
      if (!alreadyVisible) {
        setLiveTurns((turns) => upsertLiveTurn(turns, {
          sessionId: report.sessionId,
          turnId: report.turnId,
          turnNumber: report.turnNumber,
          userText: report.displayInput,
          assistantText: report.text,
          responseKind: "command",
        }));
      }
      if (state.session !== null && !alreadyVisible) {
        dispatch({
          type: "session-created",
          session: {
            ...state.session,
            turnCount: Math.max(state.session.turnCount, report.turnNumber),
          },
        });
      }
      scheduleOwnedFrame(operation, () => transcriptEndRef.current?.scrollIntoView({ block: "end" }));
    }).catch((error: unknown) => {
      if (!isCurrent()) return;
      const safe = workspaceError(error);
      updateExtensionsFor(flow.triggerTurnId, (current) =>
        failExtensionApply(current, safe.message, safe.turnLifecycle));
    }).finally(() => finishWorkspaceOperation(operation));
  }, [ownsOperation, scheduleOwnedFrame, beginWorkspaceOperation, extensionFlow, finishWorkspaceOperation, liveTurns, state.session, transcript, updateExtensions, updateExtensionsFor]);

  const restartForExtensions = useCallback(() => {
    if (!canRestartForExtensions(extensionFlow)) return;
    runLifecycle("restart");
  }, [extensionFlow, runLifecycle]);

  // Re-read the saved list and transcript after a refresh failed; nothing is resent.
  const refreshSavedConversation = useCallback(() => {
    const selected = conversation.selected;
    if (selected === null || conversation.activeTurn !== null) return;
    const operation = beginWorkspaceOperation("Refreshing saved conversation");
    if (operation === null) return;
    const isCurrent = () => ownsOperation(operation, workspaceOperation.current) && sameSelection(conversationRef.current.selected, selected);
    void (async () => {
      try {
        await loadHistory(operation.generation);
        const currentSession = state.session;
        if (!isCurrent() || currentSession === null || currentSession.sessionId !== selected.sessionId) return;
        const data = await fetchTranscriptPage(selected.projectId, selected.sessionId,
          transcriptTailOffset(currentSession.turnCount + 1), TRANSCRIPT_PAGE_SIZE, api.sessionTranscript);
        if (!isCurrent()) return;
        dispatch({ type: "session-created", session: { ...currentSession, turnCount: data.total } });
        setTranscript(transcriptViewFrom(selected.projectId, selected.sessionId, data));
        setLiveTurns([]);
        setHistoryIssue(null);
      } catch (error: unknown) {
        if (isCurrent()) setHistoryIssue(`The conversation state could not be refreshed. ${workspaceError(error).message}`);
      } finally {
        if (isCurrent()) focusComposer(operation);
        finishWorkspaceOperation(operation);
      }
    })();
  }, [ownsOperation, beginWorkspaceOperation, conversation.activeTurn, conversation.selected, finishWorkspaceOperation, focusComposer, loadHistory, state.session]);

  const updateThinkingMode = useCallback(async (
    mode: "normal" | "extended",
  ) => {
    const selected = conversationRef.current.selected;
    if (selected === null || conversationRef.current.activeTurn !== null) return;
    const operation = beginWorkspaceOperation("Updating session controls");
    if (operation === null) return;
    const isCurrent = () => ownsOperation(operation, workspaceOperation.current);
    try {
      const data = await api.sessionSetThinking({ mode });
      if (!isCurrent()) return;
      if (data.sessionId !== selected.sessionId) {
        throw protocolMismatch("The backend returned controls for a different conversation.");
      }
      dispatch({
        type: "session-created",
        session: state.session === null
          ? data
          : { ...state.session, ...data },
      });
      focusComposer(operation);
    } catch (error) {
      if (isCurrent()) {
        setWorkspaceIssue(workspaceError(error));
        focusComposer(operation);
      }
    }
    finally { finishWorkspaceOperation(operation); }
  }, [ownsOperation, beginWorkspaceOperation, finishWorkspaceOperation, focusComposer, state.session]);

  const updatePermissionMode = useCallback(async (
    mode: PermissionMode,
  ) => {
    const selected = conversationRef.current.selected;
    if (selected === null || conversationRef.current.activeTurn !== null) return;
    const operation = beginWorkspaceOperation("Updating session controls");
    if (operation === null) return;
    const generation = operation.generation;
    const isCurrent = () => ownsOperation(operation, workspaceOperation.current);
    try {
      const data = await api.sessionSetPermission({ permissionMode: mode });
      if (!isCurrent()) return;
      const updatedMode = reconcilePermissionAck(
        generation,
        generationRef.current,
        selected.sessionId,
        data,
      );
      if (updatedMode === null) {
        if (!isCurrent()) return;
        throw protocolMismatch("The backend returned controls for a different conversation.");
      }
      dispatch({
        type: "session-created",
        session: state.session === null
          ? {
              sessionId: selected.sessionId,
              turnCount: 0,
              graphRecursionLimit: 64,
              thinkingMode: "normal",
              permissionMode: updatedMode,
              slashCommands: [],
              loadedSkills: [],
              mcpFamilies: [],
              startupDiagnostics: [],
              extensionRevision: 0,
            }
          : { ...state.session, permissionMode: updatedMode },
      });
      focusComposer(operation);
    } catch (error) {
      if (isCurrent()) {
        setWorkspaceIssue(workspaceError(error));
        focusComposer(operation);
      }
    } finally {
      finishWorkspaceOperation(operation);
    }
  }, [ownsOperation, beginWorkspaceOperation, finishWorkspaceOperation, focusComposer, state.session]);

  useEffect(() => { if (workspaceIssue !== null) focusComposer(); }, [focusComposer, workspaceIssue]);
  useEffect(() => {
    if (pendingUserText !== null) transcriptEndRef.current?.scrollIntoView({ block: "end" });
  }, [liveTurns.length, pendingUserText]);

  // A selected session with a saved prompt is already in the list (or will be after the next refresh).
  const selectedSaved = (state.session?.turnCount ?? 0) > 0;
  const interaction = conversationInteractionState(conversation);
  const idle = state.activeAction === null && !interaction.turnActive && workspaceBusy === null && !documentBusy && pendingApproval === null;
  const annotationControls = useMemo<AnnotationControls>(() => ({
    annotations: conversation.annotations, references: conversation.draftReferences, disabled: !idle || chooserOpen,
    onChange: (referenceId, comment) => applyConversation({ type: "annotation-changed", referenceId, comment,
      generation: conversation.backendGeneration, projectEpoch: conversation.projectEpoch }),
    onToggle: (referenceId, expanded) => applyConversation({ type: "annotation-toggled", referenceId, expanded,
      generation: conversation.backendGeneration, projectEpoch: conversation.projectEpoch }),
    onRemove: (referenceId) => applyConversation({ type: "reference-removed", referenceId,
      generation: conversation.backendGeneration, projectEpoch: conversation.projectEpoch }),
  }), [applyConversation, conversation.annotations, conversation.draftReferences, conversation.backendGeneration, conversation.projectEpoch, idle, chooserOpen]);
  const canStart = idle && (state.snapshot === null || state.snapshot.lifecycle === "stopped");
  const stopScreen = stopScreenState(
    conversation,
    state.activeAction === null && workspaceBusy === null && !documentBusy && pendingApproval === null,
    pendingUserText,
  );
  const { stopRecovery, stopping } = stopScreen;
  const canRestart = (idle || stopRecovery) && (state.phase === "crashed" || state.phase === "degraded" || state.snapshot?.childRunning === true);
  const canShutdown = idle && state.snapshot?.childRunning === true;
  const canCreateSession = idle && workspaceBusy === null && state.snapshot?.lifecycle === "ready" && state.diagnostics !== null && activeProjectId !== null;
  const canManageConversations = idle && !chooserOpen && state.snapshot?.lifecycle === "ready" &&
    state.diagnostics !== null && bindingGenerationRef.current === generationRef.current;
  const menuTargetsRunningConversation = conversationMenu !== null && sameSelection(
    conversation.stopRequest ?? conversation.activeTurn, { projectId: conversationMenu.projectId, sessionId: conversationMenu.session.sessionId },
  );
  const canDeleteConversation = !chooserOpen && state.snapshot?.lifecycle === "ready" &&
    state.diagnostics !== null && bindingGenerationRef.current === generationRef.current &&
    state.activeAction === null && workspaceBusy === null && (idle || menuTargetsRunningConversation);
  const renameTitleTooLong = renameDialog !== null && new TextEncoder().encode(renameDialog.title.trim()).length > 256;
  const shutdownMessage = shutdownSummary(state.snapshot);
  const selectedSummary = useMemo(() => {
    const selected = conversation.selected;
    if (selected === null) return null;
    if (sessionList?.projectId !== selected.projectId) return null;
    return sessionList.items.find((item) => item.sessionId === selected.sessionId) ?? null;
  }, [conversation.selected, sessionList]);
  // The sidebar shows only the opened project's list; a list left over from another project is never drawn.
  const openedList = project !== null && sessionList?.projectId === project.projectId ? sessionList : null;
  const visibleTranscript = selectionPreview?.transcript ?? transcript;
  const visibleTurns = useMemo(() => mergeConversationTurns(
    visibleTranscript === null
      ? []
      : visibleTranscript.items.map((turn) => ({ sessionId: visibleTranscript.sessionId, turn })),
    selectionPreview === null ? liveTurns : [],
    selectionPreview !== null || pendingUserText === null || conversation.activeTurn === null
      ? null
      : {
          sessionId: conversation.activeTurn.sessionId,
          turnId: conversation.activeTurn.turnId,
          userText: pendingUserText,
          submittedContext: conversation.submittedContext,
          activity: conversation.activeTurn.activity,
        },
  ), [conversation.activeTurn, liveTurns, pendingUserText, selectionPreview, visibleTranscript]);
  const renderConversation = activeProjectId !== null && state.phase === "session-ready" && state.session !== null && conversation.selected?.projectId === activeProjectId;
  const retryControlsMatch = retrySettingsMatch(conversation.submittedContext, state.session?.permissionMode ?? "ask", state.session?.thinkingMode ?? "normal");
  const documentDirty = documentValue !== null && documentValue.sourceText !== documentBaselineRef.current?.sourceText;
  const activeSession = renderConversation ? state.session : null;

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-workspace">Skip to main workspace</a>
      <aside className="sidebar" aria-label="Research Agent workspace" inert={deleteDialog !== null}>
        <div className="brand-lockup"><span className="brand-mark" aria-hidden="true">R</span><div><p className="eyebrow">LOCAL WORKSPACE</p><h1>Research Agent</h1></div></div>
        <button className="new-session-button" type="button" title="Creating or selecting a conversation starts its enabled, configured MCP servers." onClick={createSession} disabled={!canCreateSession || interaction.turnActive}><span aria-hidden="true">＋</span> New conversation</button>
        <section className="sidebar-section project-browser" aria-labelledby="workspace-label">
          <h2 id="workspace-label">Project</h2>
          <button type="button" onClick={showProjectChooser} disabled={!idle || state.snapshot?.lifecycle !== "ready" || state.diagnostics === null}>{project === null ? "Open project" : "Switch project"}</button>
          {openedList === null && <p className="sidebar-note">{project === null ? "Choose a project to load its conversations." : historyGeneration === null ? "Loading selected project…" : "Project unavailable"}</p>}
          {project !== null && openedList !== null && (() => {
            const list = openedList;
            const rows = sidebarRowsForProject(list.projectId, list.items, conversation.selected, selectedSaved);
            const name = projectDisplayName(project.rootPath);
            return <div className="project-group">
              <div className="project-heading"><strong tabIndex={0} title={project.rootPath}>{name}</strong><small>{list.total} saved</small></div>
              {list.status === "unavailable" && <p className="sidebar-note">{list.issue ?? "Conversations unavailable"}</p>}
              {rows.length === 0 && list.status !== "unavailable" ? <p className="sidebar-note">No saved conversations</p> : <ul className="session-list">{rows.map((session) => {
                const isSelected = conversation.selected?.sessionId === session.sessionId && conversation.selected.projectId === list.projectId;
                return <li key={session.sessionId} tabIndex={-1} onContextMenu={(event) => {
                  event.preventDefault();
                  const bounds = event.currentTarget.getBoundingClientRect();
                  conversationMenuReturnFocusRef.current = event.currentTarget;
                  setConversationMenu({ projectId: list.projectId, session,
                    left: Math.max(8, Math.min(event.clientX || bounds.left, window.innerWidth - 200)),
                    top: Math.max(8, Math.min(event.clientY || bounds.bottom, window.innerHeight - 110)) });
                }}><button type="button" className="session-link" title={session.title} aria-label={session.title} aria-current={isSelected ? "page" : undefined} disabled={interaction.turnActive || documentBusy || pendingApproval !== null || workspaceBusy !== null || session.status !== "ready"} onClick={() => void selectConversation(list.projectId, session)}><span>{session.title}</span><small>{session.transient ? "Not saved yet" : `${session.turnCount} turns${session.status === "ready" ? "" : ` · ${session.status}`}`}</small></button></li>;
              })}</ul>}
              {list.hasMore && <button className="load-more-sessions" type="button" onClick={loadMoreSessions} disabled={interaction.turnActive || documentBusy || pendingApproval !== null || workspaceBusy !== null}>Load more conversations</button>}
            </div>;
          })()}
        </section>
        <div className="sidebar-spacer" />
        <section className="backend-controls" aria-labelledby="backend-controls-title">
          <div className="sidebar-status" role="status" aria-live="polite"><span className={`status-dot status-${state.phase}`} aria-hidden="true" /><span><strong id="backend-controls-title">{phaseLabels[state.phase]}</strong><small>{state.snapshot === null ? "Desktop process not observed" : `Generation ${state.snapshot.generation} · ${state.snapshot.pendingRequests} pending`}</small></span></div>
          <div className="control-row"><button type="button" onClick={() => runLifecycle("start")} disabled={!canStart}>{state.error !== null && state.phase === "stopped" ? "Retry start" : "Start"}</button><button type="button" title="Restarting reloads enabled, configured MCP servers for the conversation." onClick={() => runLifecycle("restart")} disabled={!canRestart}>Restart</button><button type="button" onClick={() => runLifecycle("shutdown")} disabled={!canShutdown}>Shut down</button></div>
        </section>
      </aside>

      <main id="main-workspace" className="main-workspace" tabIndex={-1} inert={deleteDialog !== null}>
        <header className="workspace-header"><div><p className="eyebrow">CURRENT CONVERSATION</p><h2>{selectionPreview?.title ?? selectedSummary?.title ?? (conversation.selected === null ? "Start a local research conversation" : "New conversation")}</h2></div><span className="header-status" role="status" aria-live="polite">{workspaceBusy ?? phaseLabels[state.phase]}</span></header>
        <div className="writing-workspace">
          <section className="document-pane" aria-label="Source document workspace">
            <DocumentHeader path={documentValue?.path ?? null} dirty={documentDirty} busy={documentBusy}
              openDisabled={activeProjectId === null || workspaceBusy !== null || interaction.turnActive || documentBusy || rootPath.trim() === "" || state.snapshot?.lifecycle !== "ready"}
              saveDisabled={documentValue === null || documentBusy || state.snapshot?.lifecycle !== "ready"}
              undoDisabled={lastDocumentAction === null || documentBusy || interaction.turnActive}
              onOpen={() => void openDocument()}
              onSave={() => void saveDocument()}
              onUndo={() => lastDocumentAction !== null && void applyDocumentOperation({ turnId: lastDocumentAction.turnId, undoOfCallId: lastDocumentAction.callId })}
            />
            {documentNotice !== null && <p className="document-error" role="status">{documentNotice}</p>}
            <DocumentEditor value={documentValue} onChange={updateDocument} annotationControls={annotationControls} onAddReference={renderConversation && idle && !chooserOpen ? addDocumentReference : undefined} onSave={() => void saveDocument()} saveDisabled={documentBusy}
              citationEntries={citationEntries} />
            {documentValue !== null && state.snapshot?.lifecycle === "ready" && <CitationPanel
              document={documentValue}
              refreshToken={citationRefresh}
              api={api}
              contextPayload={documentContextPayload}
              onSelect={updateDocument}
              onEntries={setCitationEntries}
              requestAdd={requestCitationAdd}
              writesDisabled={interaction.turnActive || documentBusy || pendingApproval !== null}
            />}
            {documentConflict !== null && <section className="document-conflict" aria-label="Document version conflict">
              <h3>{documentConflict.result.status === "failed" ? "Save failed" : "Choose a document version"}</h3>
              <p>Keeping the editor or cancelling leaves disk unchanged. Using the candidate replaces this file after checking its version again.</p>
              <div className="conflict-versions">
                <details><summary>Original source</summary><pre>{documentConflict.base.sourceText}</pre></details>
                <details><summary>Current editor</summary><pre>{documentValue?.sourceText}</pre></details>
                <details><summary>Current disk</summary><pre>{documentConflict.result.currentDiskText ?? "Unavailable"}</pre></details>
                <details open><summary>Agent candidate / requested save</summary><pre>{documentConflict.result.candidateText ?? documentValue?.sourceText}</pre></details>
              </div>
              <div className="action-row">
                <button type="button" disabled={documentBusy} onClick={() => void resolveDocumentConflict("keep")}>Keep editor</button>
                <button type="button" disabled={documentBusy || documentConflict.result.expectedSnapshot === undefined} onClick={() => void resolveDocumentConflict("use")}>Use candidate and save</button>
                <button type="button" disabled={documentBusy} onClick={() => void resolveDocumentConflict("cancel")}>Cancel</button>
              </div>
            </section>}
          </section>
        <div className={`workspace-body${(renderConversation || selectionPreview !== null) ? " conversation-workspace-body" : ""}`}>
          {extensionFlow !== null && <ExtensionPanel
            flow={extensionFlow}
            busy={workspaceBusy !== null || state.activeAction !== null || interaction.turnActive}
            canRestart={canRestart}
            permissionMode={state.session?.permissionMode ?? "ask"}
            onPreview={previewExtensions}
            onDecision={decideBinding}
            onApply={applyExtensions}
            onRestart={restartForExtensions}
          />}
          {selectionPreview === null && (state.error !== null || workspaceIssue !== null || conversation.failure !== null) && <section className="notice notice-error" aria-labelledby="recovery-title"><div className="notice-icon" aria-hidden="true">!</div><div><p className="section-kicker">{conversation.failure === null ? (workspaceIssue ?? state.error)?.code : failureLifecycleLabel(conversation.failure)}</p><h3 id="recovery-title">{state.phase === "crashed" ? "The local backend stopped unexpectedly" : conversation.failure?.cancelled ? "Turn stopped" : "Action required"}</h3><p>{conversation.failure?.message ?? (workspaceIssue ?? state.error)?.message}</p><div className="action-row">{conversation.failure?.retryable && (conversation.failure.draftPreserved || conversation.submittedTurn?.turnId === conversation.failure.turnId) && <button type="button" onClick={() => void sendTurn()} disabled={interaction.turnActive || workspaceBusy !== null || !retryControlsMatch}>Retry saved turn</button>}{state.snapshot?.lifecycle === "ready" && state.diagnostics === null && <button type="button" onClick={() => loadDiagnostics(true)} disabled={!idle}>Retry runtime check</button>}{(state.phase === "crashed" || state.phase === "degraded") && <button type="button" onClick={() => runLifecycle("restart")} disabled={!canRestart}>Restart backend</button>}{canStart && <button type="button" onClick={() => runLifecycle("start")}>Retry start</button>}</div></div></section>}
          {stopScreen.showStopFailure && conversation.stopRequest !== null && <section className="notice notice-error" role="alert">
            <div><h3>The turn could not finish stopping</h3><p>{conversation.stopRequest.error}</p>
              {stopScreen.showPendingMessage && pendingUserText !== null && <details><summary>Your message</summary><SafeContent content={pendingUserText} /></details>}
              <div className="action-row"><button type="button" onClick={stopTurn}>Retry Stop</button>
                {stopScreen.showRestartInPanel && <button type="button" disabled={!canRestart} onClick={() => runLifecycle("restart")}>Restart backend</button>}
              </div>
            </div>
          </section>}
          {selectionPreview === null && historyIssue !== null && <section className="notice history-notice" aria-live="polite"><div className="notice-icon" aria-hidden="true">!</div><div><p className="section-kicker">CONVERSATION NOT REFRESHED</p><p>{historyIssue}</p><button type="button" onClick={refreshSavedConversation} disabled={interaction.turnActive || workspaceBusy !== null}>Refresh without resending</button></div></section>}
          {(state.phase === "starting" || (state.snapshot === null && state.error === null)) && <section className="empty-state" role="status"><h3>Preparing your research workspace</h3><p>Connecting to the local backend. Choose a project when it is ready.</p></section>}
          {state.phase === "stopped" && state.snapshot !== null && state.error === null && <section className="empty-state" aria-labelledby="stopped-title"><div className="hero-mark" aria-hidden="true">R</div><h3 id="stopped-title">The local backend is stopped</h3><button className="primary-button" type="button" onClick={() => runLifecycle("start")} disabled={!canStart}>Start local backend</button>{shutdownMessage !== null && <p className="shutdown-summary">{shutdownMessage}</p>}</section>}
          {(state.phase === "starting" || state.phase === "restarting" || state.phase === "shutting-down") && <section className="empty-state" aria-labelledby="transition-title"><div className="spinner" aria-hidden="true" /><p className="section-kicker">DESKTOP BACKEND</p><h3 id="transition-title">{phaseLabels[state.phase]}</h3><p>Please keep this window open while the local process changes state.</p></section>}
          {state.phase === "busy" && <section className="empty-state" aria-labelledby="busy-title"><div className="spinner" aria-hidden="true" /><p className="section-kicker">LOCAL REQUEST</p><h3 id="busy-title">{state.activeAction === "session" ? "Creating your session" : "Checking the local runtime"}</h3><p>This check stays on your device and does not call a model provider.</p></section>}
          {selectionPreview === null && activeProjectId !== null && state.phase === "backend-ready" && state.diagnostics !== null && <section className="setup-card" aria-labelledby="backend-ready-title"><div className="success-mark" aria-hidden="true">✓</div><div><p className="section-kicker">BACKEND READY</p><h3 id="backend-ready-title">Create a conversation to begin</h3><p>The protocol and local runtime are ready. Creating or selecting a conversation starts enabled, configured MCP servers. No model request has been sent.</p><div className="action-row"><button className="primary-button" type="button" onClick={createSession} disabled={!canCreateSession}>Create local conversation</button><button type="button" onClick={() => runLifecycle("shutdown")} disabled={!canShutdown}>Shut down</button></div><RuntimeDetails diagnostics={state.diagnostics} /></div></section>}

          {selectionPreview !== null && <section className="conversation-surface" aria-label="Saved conversation preview" aria-busy="true">
            <p className="control-state" role="status">Preparing this conversation… You can read the saved messages while it loads.</p>
            <Transcript turns={visibleTurns} projectId={visibleTranscript?.projectId ?? activeProjectId ?? undefined} annotationControls={annotationControls}
              transcriptRef={transcriptRef} endRef={transcriptEndRef} />
          </section>}
          {selectionPreview === null && activeSession !== null && <section className="conversation-surface" aria-label="Conversation workspace">
            <Transcript turns={visibleTurns} projectId={visibleTranscript?.projectId ?? activeProjectId ?? undefined} annotationControls={annotationControls}
              transcriptRef={transcriptRef} endRef={transcriptEndRef} empty
              hasOlder={transcript?.hasOlder ?? false} issue={transcript?.issue ?? null}
              loadOlderDisabled={workspaceBusy !== null || interaction.turnActive} onLoadOlder={loadOlder} />
            {(conversation.failure !== null && !conversation.failure.cancelled && conversation.submittedContext !== null || referenceIssue !== null) && <div className="composer-notices">
            {conversation.failure !== null && !conversation.failure.cancelled && conversation.submittedContext !== null && <div className="reference-retry-settings">
              <p>Saved turn: {conversation.submittedContext.permissionMode === "ask" ? "Ask" : "Bypass"} · {conversation.submittedContext.requestedThinkingMode === "normal" ? "Normal" : "Extended"}.
                {!retryControlsMatch && " Current controls differ; the original retry is disabled."}</p>
              {composeTurnText(conversation.draft, conversation.annotations).trim().length > 0 && <button type="button" onClick={sendNewTurn} disabled={!idle}>Send new turn with current settings</button>}
            </div>}
            {referenceIssue !== null && <p className="reference-issue" role="status">{referenceIssue}</p>}
            </div>}
            <SlashComposer
              key={`${state.snapshot?.generation}:${conversation.selected?.projectId}:${conversation.selected?.sessionId}`}
              draft={conversation.draft} textareaRef={composerRef}
              references={conversation.draftReferences}
              annotationControls={annotationControls}
              thinkingMode={activeSession.thinkingMode} permissionMode={activeSession.permissionMode}
              turnActive={interaction.turnActive} stopping={stopping} onStop={stopTurn}
              controlsDisabled={interaction.turnActive || documentBusy || pendingApproval !== null || workspaceBusy !== null}
              onThinkingChange={(mode) => void updateThinkingMode(mode)}
              onPermissionChange={(mode) => void updatePermissionMode(mode)}
              turnHint={conversation.activeTurn !== null && conversation.submittedContext?.documentContext !== undefined &&
                conversation.submittedContext.requestedThinkingMode === "extended" ? "Normal for this document turn; Extended resumes afterward." : undefined}
              onRemoveReference={(referenceId) => applyConversation({ type: "reference-removed", generation: conversation.backendGeneration, projectEpoch: conversation.projectEpoch, referenceId })}
              skills={state.session?.loadedSkills ?? []}
              onSkillPicked={(name) => selectedSkillNamesRef.current.add(name)}
              commands={composerSlashCommands(state.session, conversation.selected, state.snapshot?.generation, slashCatalogOwner,
                state.snapshot?.lifecycle === "ready" && state.phase === "session-ready" && idle)}
              disabled={conversation.selected === null || interaction.turnActive || workspaceBusy !== null}
              sendDisabled={interaction.sendDisabled || documentBusy || pendingApproval !== null || workspaceBusy !== null || (conversation.failure !== null && !conversation.failure.cancelled && !retryControlsMatch)}
              onChange={(draft) => applyConversation({ type: "draft-changed", draft })}
              onSubmit={sendTurn}
            />
            <details className="session-meta"><summary>Session details · {activeSession.turnCount} turns</summary><p>Session {activeSession.sessionId}</p></details>
          </section>}
          {(state.phase === "degraded" || state.phase === "crashed") && state.diagnostics !== null && <RuntimeDetails diagnostics={state.diagnostics} />}
        </div>
        </div>
      </main>
      {conversationMenu !== null && <div className="conversation-menu-backdrop" onClick={() => {
        setConversationMenu(null); conversationMenuReturnFocusRef.current?.focus();
      }} onContextMenu={(event) => { event.preventDefault(); setConversationMenu(null); }}>
        <div className="document-menu-actions conversation-menu" role="menu" aria-label="Conversation actions" tabIndex={-1}
          ref={conversationMenuRef} style={{ left: conversationMenu.left, top: conversationMenu.top }}
          onClick={(event) => event.stopPropagation()} onKeyDown={(event) => {
            if (menuShouldClose(event.key, true, true)) {
              event.preventDefault(); setConversationMenu(null); conversationMenuReturnFocusRef.current?.focus();
              return;
            }
            const items = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("button:not(:disabled)"));
            const next = menuNextIndex(event.key, items.indexOf(document.activeElement as HTMLButtonElement), items.length, false);
            if (next !== null) { event.preventDefault(); items[next]?.focus(); }
          }}>
          <button type="button" role="menuitem"
            disabled={!canManageConversations || conversationMenu.session.transient || conversationMenu.session.status !== "ready"}
            onClick={() => {
              setRenameDialog({ projectId: conversationMenu.projectId, sessionId: conversationMenu.session.sessionId,
                title: conversationMenu.session.title, issue: null, owner: captureOwner("Rename dialog") });
              setConversationMenu(null);
            }}>Rename</button>
          <button type="button" role="menuitem" disabled={!canDeleteConversation} onClick={() => {
            setDeleteDialog({ projectId: conversationMenu.projectId, sessionId: conversationMenu.session.sessionId,
              title: conversationMenu.session.title, status: null, issue: null, owner: captureOwner("Delete dialog") });
            setConversationMenu(null);
          }}>Delete</button>
        </div>
      </div>}
      {renameDialog !== null && <ModalDialog as="form" className="file-open-dialog" labelledBy="rename-conversation-title"
        dismissible={workspaceBusy === null} focusSelector="input:not(:disabled), button:not(:disabled)"
        onDismiss={() => { setRenameDialog(null); conversationMenuReturnFocusRef.current?.focus(); }}
        onSubmit={(event) => { event.preventDefault(); void renameConversation(); }}>
          <h2 id="rename-conversation-title">Rename conversation</h2>
          <label>Name<input autoFocus value={renameDialog.title} disabled={workspaceBusy !== null}
            onFocus={(event) => event.currentTarget.select()}
            onKeyDown={(event) => { if (event.key === "Enter" && (event.nativeEvent.isComposing || event.keyCode === 229)) event.preventDefault(); }}
            onChange={(event) => setRenameDialog({ ...renameDialog, title: event.target.value, issue: null })} /></label>
          {renameTitleTooLong && <p className="extension-error" role="alert">Enter a shorter name.</p>}
          {renameDialog.issue !== null && <p className="extension-error" role="alert">{renameDialog.issue}</p>}
          <div className="action-row">
            <button type="submit" className="primary-button" disabled={!canManageConversations || renameDialog.title.trim() === "" || renameTitleTooLong}>
              {workspaceBusy === "Renaming conversation" ? "Saving…" : "Save name"}
            </button>
            <button type="button" disabled={workspaceBusy !== null} onClick={() => {
              setRenameDialog(null); conversationMenuReturnFocusRef.current?.focus();
            }}>Cancel</button>
          </div>
      </ModalDialog>}
      {deleteDialog !== null && <DeleteConversationDialog title={deleteDialog.title} status={deleteDialog.status} error={deleteDialog.issue}
        onConfirm={() => void deleteConversation()} onCancel={() => {
          setDeleteDialog(null);
          scheduleOwnedFrame(deleteDialog.owner, () => conversationMenuReturnFocusRef.current?.focus());
        }} />}
      {chooserOpen && state.snapshot?.lifecycle === "ready" && state.diagnostics !== null && <ModalDialog labelledBy="project-chooser-title"
        dismissible={workspaceBusy === null} onDismiss={() => setChooserOpen(false)}
        focusSelector="input:not(:disabled), button:not(:disabled), select:not(:disabled)">
          <p className="section-kicker">LOCAL PROJECT</p>
          <h2 id="project-chooser-title">{project === null ? "Open a research project" : "Switch research project"}</h2>
          <p>Choose an existing WSL folder. Its RESEARCH.md defines the project rules and conversation history location.</p>
          <div className="action-row"><button type="button" autoFocus disabled={workspaceBusy !== null}
            onClick={() => void chooseProject("inspect", true)}>Choose project folder…</button></div>
          {candidate !== null && <div className="approval-context">
            <p><strong>Resolved project:</strong> <code>{candidate.rootPath}</code></p>
            {candidate.status === "needs_configuration" ? <>
              <p>{candidate.researchFingerprint === null ? "Create RESEARCH.md with a new empty history." : "Preserve the existing RESEARCH.md and append its history setting."}</p>
              <label>History directory<input aria-label="History directory" value={candidateHistory}
                disabled={workspaceBusy !== null} onChange={(event) => setCandidateHistory(event.target.value)} /></label>
              <p><strong>Resolved history:</strong> <code>{candidate.historyDirectory}</code></p>
              {candidateHistory !== candidate.historyDirectory && <button type="button" disabled={workspaceBusy !== null} onClick={() => void chooseProject("inspect")}>Inspect history location</button>}
            </> : <p><strong>History directory:</strong> <code>{candidate.historyDirectory}</code></p>}
            {candidate.status === "needs_initialization" && <p>This configured history does not exist yet. Initialize an empty history here, or cancel and edit RESEARCH.md to change its location.</p>}
            {candidate.status === "ready" && <p>Open this project and validate its existing conversation history.</p>}
            {documentDirty && <fieldset disabled={workspaceBusy !== null}><legend>The document has unsaved changes</legend>
              <label><input type="radio" name="project-document-choice" checked={dirtyChoice === "save"} onChange={() => setDirtyChoice("save")} /> Save before opening</label>
              <label><input type="radio" name="project-document-choice" checked={dirtyChoice === "discard"} onChange={() => setDirtyChoice("discard")} /> Discard only after the project opens</label>
            </fieldset>}
            {(conversation.draft.length > 0 || conversation.draftReferences.length > 0) && <label><input type="checkbox" checked={discardDraft} disabled={workspaceBusy !== null}
              onChange={(event) => setDiscardDraft(event.target.checked)} /> Discard the unsent draft and references only after the project opens</label>}
            <div className="action-row"><button className="primary-button" type="button"
              disabled={workspaceBusy !== null || ((conversation.draft.length > 0 || conversation.draftReferences.length > 0) && !discardDraft) || candidateHistory.trim() === "" || (candidate.status === "needs_configuration" && candidateHistory !== candidate.historyDirectory)}
              onClick={() => void chooseProject(candidate.status === "ready" ? "open" : "initialize")}>
              {documentDirty && dirtyChoice === "save" ? "Save and " : ""}{candidate.status === "ready" ? "Open project" : "Initialize and open project"}
            </button></div>
          </div>}
          {chooserIssue !== null && <p className="extension-error" role="alert">{chooserIssue}</p>}
          {workspaceBusy !== null && <p role="status">{workspaceBusy}…</p>}
          <button type="button" disabled={workspaceBusy !== null} onClick={() => setChooserOpen(false)}>Cancel</button>
      </ModalDialog>}
      {chatSelection !== null && renderConversation && idle && !chooserOpen && deleteDialog === null && <button type="button" className="chat-reference-action"
        style={{ position: "fixed", top: chatSelection.top, left: chatSelection.left }}
        onPointerDown={(event) => event.preventDefault()} onClick={() => void addChatReference()}>Comment on selection</button>}
      {pendingApproval !== null && deleteDialog === null && <ApprovalDialog
        approval={pendingApproval}
        resolving={approvalResolving || conversation.stopRequest !== null}
        onStop={(conversation.activeTurn?.turnId ?? conversation.stopRequest?.turnId) === pendingApproval.turnId ? stopTurn : undefined}
        stopping={stopping}
        stopError={conversation.stopRequest?.error ?? undefined}
        onResolve={resolvePendingApproval}
        returnFocus={returnApprovalFocus}
        allowDocumentEditing={documentValue !== null}
      />}
    </div>
  );
}
