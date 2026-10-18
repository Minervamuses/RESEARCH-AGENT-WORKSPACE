import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import {
  memo,
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
  BACKEND_EVENT_NAME,
  BackendClientError,
  type BackendActionName,
  type BackendSnapshot,
  type BoundedRuntimeDiagnostics,
  type SafeUiError,
  backendReducer,
  createBackendClient,
  initialBackendState,
  normalizeUiError,
  parseBridgeEvent,
  toBoundedDiagnostics,
} from "./backend.ts";
import {
  conversationInteractionState,
  composeTurnText,
  conversationReducer,
  initialConversationState,
  latestRetryableTranscriptTurn,
  mergeConversationTurns,
  nextTurnSubmission,
  turnSubmissionText,
  ownsWorkspaceOperation,
  type WorkspaceOperationOwner,
  reconciledTurnCount,
  sameSelection,
  upsertLiveTurn,
  type ConversationAction,
  type ConversationFailure,
  type ConversationSelection,
  type LiveTurn,
  type VisibleConversationTurn,
} from "./conversations.ts";
import type {
  ApprovalRequiredDto,
  ApprovalResolvedDto,
  BashPermissionMode,
  ExtensionApplyDto,
  ExtensionPreviewDto,
  JsonObject,
  ProjectListDto,
  ProjectSummaryDto,
  ProjectWorkspaceDto,
  Reference,
  SubmittedContext,
  RegistrationRetryDto,
  RuntimeDiagnosticsDto,
  SessionBashPermissionSetDto,
  SessionCreatedDto,
  SessionListDto,
  SessionSelectedDto,
  SessionSummaryDto,
  SessionTranscriptDto,
  TranscriptTurnDto,
  TurnCompletedDto,
  TurnStoppedDto,
} from "./protocol.ts";
import { SafeContent as ContentRenderer } from "./SafeContent.tsx";
import { AnnotationComment, DocumentEditor, type AnnotationControls, type DocumentSnapshot } from "./DocumentEditor.tsx";
import {
  ApprovalDialog,
  BashPermissionControl,
  ThinkingControl,
  ExtensionPanel,
  acceptApprovalEvent,
  beginExtensionApply,
  beginExtensionApplyRecovery,
  beginExtensionPreview,
  createExtensionFlow,
  decideExtensionBinding,
  extensionApplyRequest,
  failExtensionApply,
  failExtensionFlow,
  interruptExtensionFlow,
  markExtensionAwaitingLoad,
  markExtensionRestarting,
  observeExtensionRevision,
  receiveExtensionApply,
  receiveExtensionPreview,
  reconcileBashPermissionAck,
  type ExtensionBindingDecision,
  type ExtensionFlow,
  type PendingApproval,
} from "./trust.tsx";

const backendClient = createBackendClient({
  invoke: <T,>(command: string, args?: Record<string, unknown>) => invoke<T>(command, args),
});

// Unchanged history must not be reparsed when the composer or live activity updates.
const SafeContent = memo(ContentRenderer);

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

interface SidebarSessionRow extends SessionSummaryDto {
  transient: boolean;
}

// One transcript page: the tail window restored on select and after a durable failure.
const TRANSCRIPT_PAGE_SIZE = 20;

interface TranscriptView {
  projectId: string;
  sessionId: string;
  status: SessionTranscriptDto["status"];
  issue: string | null;
  items: TranscriptTurnDto[];
  offset: number;
  total: number;
  hasOlder: boolean;
}

export function sidebarRowsForProject(
  projectId: string,
  sessions: readonly SessionSummaryDto[],
  selected: ConversationSelection | null,
  selectedRegistered: boolean,
): SidebarSessionRow[] {
  const rows = sessions.map((session) => ({ ...session, transient: false }));
  if (
    selected !== null &&
    selected.projectId === projectId &&
    !selectedRegistered &&
    !rows.some((session) => session.sessionId === selected.sessionId)
  ) {
    rows.unshift({
      sessionId: selected.sessionId,
      title: "New conversation",
      turnCount: 0,
      createdAt: null,
      updatedAt: null,
      status: "ready",
      issue: null,
      transient: true,
    });
  }
  return rows;
}

export function sessionCreateParams(projectId: string): JsonObject {
  return { projectId };
}

export async function loadSelectedProjectHistory(
  projectId: string | null,
  request: (method: "project.list" | "session.list", params: JsonObject) => Promise<JsonObject> = backendClient.request,
  isCurrent: () => boolean = () => true,
): Promise<{ catalog: ProjectListDto; sessions: SessionListDto } | null> {
  if (projectId === null) return null;
  const catalog = await request("project.list", {}) as unknown as ProjectListDto;
  if (!isCurrent()) return null;
  if (catalog.projects.length !== 1 || catalog.projects[0].projectId !== projectId || catalog.selectedProjectId !== projectId) {
    throw protocolMismatch("The backend returned history for a different project.");
  }
  const sessions = await request("session.list", { projectId, offset: 0, limit: 50, reconcile: false }) as unknown as SessionListDto;
  if (!isCurrent()) return null;
  if (sessions.projectId !== projectId) throw protocolMismatch("The backend returned conversations for a different project.");
  return { catalog, sessions };
}

export function shouldSubmitComposerKey(
  key: string,
  shiftKey: boolean,
  isComposing: boolean,
): boolean {
  return key === "Enter" && !shiftKey && !isComposing;
}

type SlashCommands = SessionCreatedDto["slashCommands"];
type SlashCatalogOwner = ConversationSelection & { generation: number };
const NO_SLASH_COMMANDS: SlashCommands = [];

export function composerSlashCommands(
  session: SessionCreatedDto | null,
  selected: ConversationSelection | null,
  generation: number | undefined,
  owner: SlashCatalogOwner | null,
  interactive: boolean,
): SlashCommands {
  if (!interactive || owner === null || selected === null || owner.generation !== generation ||
      !sameSelection(owner, selected) || session?.sessionId !== owner.sessionId ||
      (session.projectId !== undefined && session.projectId !== owner.projectId)) {
    return NO_SLASH_COMMANDS;
  }
  return session.slashCommands;
}

export function slashPrefix(draft: string, start: number, end: number): string | null {
  if (start !== end || end !== draft.length) return null;
  return /^[^\S\r\n]*\/([^\s/]*)$/.exec(draft)?.[1] ?? null;
}

export function filterSlashCommands(commands: SlashCommands, prefix: string): SlashCommands {
  return commands.filter((command) => command.name.toLowerCase().startsWith(prefix.toLowerCase()));
}

export function insertSlashCommand(draft: string, name: string): string {
  return `${/^[^\S\r\n]*/.exec(draft)?.[0] ?? ""}/${name} `;
}

export interface InlineSkillReference { name: string; startUtf16: number; endUtf16: number }

export function inlineSkillToken(draft: string, start: number, end: number): { start: number; end: number; prefix: string } | null {
  if (start !== end) return null;
  let tokenStart = start;
  while (tokenStart > 0 && /[A-Za-z0-9_-]/.test(draft[tokenStart - 1])) tokenStart -= 1;
  if (tokenStart === 0 || draft[tokenStart - 1] !== "@") return null;
  const at = tokenStart - 1;
  if (at > 0 && /[A-Za-z0-9_.@+-]/.test(draft[at - 1])) return null;
  let tokenEnd = start;
  while (tokenEnd < draft.length && /[A-Za-z0-9_-]/.test(draft[tokenEnd])) tokenEnd += 1;
  if (draft[tokenEnd] === "." && /[A-Za-z0-9]/.test(draft[tokenEnd + 1] ?? "")) return null;
  return { start: at, end: tokenEnd, prefix: draft.slice(tokenStart, start) };
}

export function insertInlineSkill(draft: string, token: { start: number; end: number }, name: string): { text: string; caret: number } {
  const replacement = "@" + name + (token.end === draft.length ? " " : "");
  return { text: draft.slice(0, token.start) + replacement + draft.slice(token.end), caret: token.start + replacement.length };
}

export function inlineSkillReferences(draft: string, skills: readonly string[], selectedNames: ReadonlySet<string> = new Set()): InlineSkillReference[] {
  const available = new Set(skills);
  const references: InlineSkillReference[] = [];
  for (const match of draft.matchAll(/@([A-Za-z0-9][A-Za-z0-9_-]*)/g)) {
    const start = match.index!;
    const end = start + match[0].length;
    const token = inlineSkillToken(draft, end, end);
    if (token === null || token.start !== start) continue;
    if (!available.has(match[1])) {
      if (selectedNames.has(match[1])) throw new Error("Selected Skill is no longer available: " + match[1]);
      continue;
    }
    references.push({ name: match[1], startUtf16: start, endUtf16: end });
  }
  return references;
}

export function handleComposerKey(
  event: { key: string; shiftKey: boolean; isComposing: boolean; preventDefault: () => void },
  menu: { open: boolean; count: number; active: number },
  actions: { select: (index: number) => void; move: (index: number) => void; close: () => void; submit: () => void },
): void {
  if (event.isComposing) return;
  if (menu.open) {
    if (event.key === "Escape") {
      event.preventDefault();
      actions.close();
      return;
    }
    if (menu.count > 0) {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        actions.move((menu.active + (event.key === "ArrowDown" ? 1 : menu.count - 1)) % menu.count);
        return;
      }
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        actions.select(menu.active);
        return;
      }
    }
  }
  if (shouldSubmitComposerKey(event.key, event.shiftKey, event.isComposing)) {
    event.preventDefault();
    actions.submit();
  }
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
  thinkingMode: "normal" | "extended"; permissionMode: BashPermissionMode;
  controlsDisabled: boolean; sendDisabled: boolean;
  turnActive?: boolean; stopping?: boolean; onStop?: () => void;
  onThinkingChange: (mode: "normal" | "extended") => void; onPermissionChange: (mode: BashPermissionMode) => void;
}) {
  return <div className="composer-footer">
    <div className="composer-controls" aria-label="Conversation settings">
      <ThinkingControl mode={thinkingMode} disabled={controlsDisabled} onChange={onThinkingChange} />
      <BashPermissionControl mode={permissionMode} disabled={controlsDisabled} onChange={onPermissionChange} />
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
  thinkingMode: "normal" | "extended"; permissionMode: BashPermissionMode; controlsDisabled: boolean; turnHint?: string;
  onThinkingChange: (mode: "normal" | "extended") => void; onPermissionChange: (mode: BashPermissionMode) => void;
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

function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

function availabilityLabel(value: boolean | null): string {
  if (value === null) return "Not checked";
  return value ? "Available" : "Unavailable";
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
        <div><dt>Ollama</dt><dd>{availabilityLabel(diagnostics.ollamaReachable)}</dd></div>
        <div><dt>Ollama model</dt><dd>{availabilityLabel(diagnostics.ollamaModelAvailable)}</dd></div>
        <div><dt>MCP</dt><dd>{diagnostics.mcpEnabled ? "Enabled" : "Disabled"}</dd></div>
        <div className="wide-detail"><dt>MCP families</dt><dd>{diagnostics.mcpFamilies.length > 0 ? diagnostics.mcpFamilies.join(", ") : "None"}</dd></div>
        <div className="wide-detail"><dt>App root</dt><dd>{diagnostics.appRoot}</dd></div>
        <div className="wide-detail"><dt>Working directory</dt><dd>{diagnostics.workingDirectory}</dd></div>
        <div className="wide-detail"><dt>Conda prefix</dt><dd>{diagnostics.condaPrefix ?? "Not detected"}</dd></div>
        <div className="wide-detail"><dt>Research store</dt><dd>{diagnostics.storePath}</dd></div>
        <div className="wide-detail"><dt>Citation output</dt><dd>{diagnostics.citationOutputPath}</dd></div>
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

function workspaceError(error: unknown): SafeUiError {
  return error instanceof BackendClientError
    ? error.uiError
    : normalizeUiError(error, "transport");
}

function protocolMismatch(message: string): BackendClientError {
  return new BackendClientError({
    code: "PROTOCOL_INVALID",
    message,
    retryable: true,
    source: "protocol",
  });
}

function mergeTranscriptItems(
  older: readonly TranscriptTurnDto[],
  current: readonly TranscriptTurnDto[],
): TranscriptTurnDto[] {
  const byTurn = new Map<number, TranscriptTurnDto>();
  for (const item of [...older, ...current]) byTurn.set(item.turnNumber, item);
  return [...byTurn.values()].sort((left, right) => left.turnNumber - right.turnNumber);
}

function failureLifecycleLabel(failure: ConversationFailure): string {
  const lifecycle = failure.turnLifecycle;
  if (lifecycle === null) return "Delivery status unknown";
  if (lifecycle.state === null) return "Prompt was not accepted";
  if (lifecycle.state === "completed") return "Answer saved locally";
  if (lifecycle.state === "pending") return "Prompt saved · completion pending";
  return `Prompt saved · ${lifecycle.state}`;
}

export function isPersistedTurnFailure(failure: ConversationFailure | null): boolean {
  const lifecycle = failure?.turnLifecycle;
  return lifecycle?.accepted === true && lifecycle.persisted === true;
}

function transcriptTailOffset(total: number): number {
  return Math.max(0, total - TRANSCRIPT_PAGE_SIZE);
}

async function fetchTranscriptPage(
  projectId: string,
  sessionId: string,
  offset: number,
  limit: number,
  mismatchMessage = "The backend returned a transcript for a different conversation.",
  request = backendClient.request,
): Promise<SessionTranscriptDto> {
  const data = await request("session.transcript", {
    projectId,
    sessionId,
    offset,
    limit,
  }) as unknown as SessionTranscriptDto;
  if (data.projectId !== projectId || data.sessionId !== sessionId) {
    throw protocolMismatch(mismatchMessage);
  }
  return data;
}

export async function selectConversationWithPreview(
  projectId: string,
  summary: SessionSummaryDto,
  callbacks: {
    isCurrent: () => boolean;
    onPreview: (data: SessionTranscriptDto) => void;
    onSelected: (selected: SessionSelectedDto) => void;
  },
  request = backendClient.request,
): Promise<SessionTranscriptDto | null> {
  let previewing = true;
  const selectedRequest = request("session.select", { projectId, sessionId: summary.sessionId });
  // Handle both outcomes immediately: selection may fail before this read finishes.
  const transcriptRequest = fetchTranscriptPage(
    projectId, summary.sessionId, transcriptTailOffset(summary.turnCount), TRANSCRIPT_PAGE_SIZE,
    undefined, request,
  ).then(
    (data) => {
      if (previewing && callbacks.isCurrent() && data.status === "ready") callbacks.onPreview(data);
      return { data, error: null };
    },
    (error: unknown) => ({ data: null, error }),
  );
  try {
    const selected = await selectedRequest as unknown as SessionSelectedDto;
    if (!callbacks.isCurrent()) return null;
    if (selected.projectId !== projectId || selected.sessionId !== summary.sessionId) {
      throw protocolMismatch("The backend returned a different conversation than requested.");
    }
    callbacks.onSelected(selected);
    const result = await transcriptRequest;
    if (!callbacks.isCurrent()) return null;
    if (result.data === null) throw result.error;
    let data = result.data;
    // Materializing a session recovers pending turns. A stale sidebar count can
    // also select the wrong tail page, so confirm either case after selection.
    if (data.items.some((turn) => turn.state === "pending") ||
        data.total !== selected.turnCount || data.offset !== transcriptTailOffset(selected.turnCount)) {
      data = await fetchTranscriptPage(
        projectId, summary.sessionId, transcriptTailOffset(selected.turnCount), TRANSCRIPT_PAGE_SIZE,
        undefined, request,
      );
    }
    return callbacks.isCurrent() ? data : null;
  } finally {
    previewing = false;
  }
}

function transcriptViewFrom(
  projectId: string,
  sessionId: string,
  data: SessionTranscriptDto,
): TranscriptView {
  return {
    projectId,
    sessionId,
    status: data.status,
    issue: data.issue,
    items: data.items,
    offset: data.offset,
    total: data.total,
    hasOlder: data.status === "ready" && data.offset > 0,
  };
}

export function mergeSessionItems(
  current: readonly SessionSummaryDto[],
  next: readonly SessionSummaryDto[],
): SessionSummaryDto[] {
  const bySession = new Map<string, SessionSummaryDto>();
  for (const item of [...current, ...next]) bySession.set(item.sessionId, item);
  return [...bySession.values()];
}

function RestoredToolActivity({ activity }: {
  activity: TranscriptTurnDto["toolActivities"][number];
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <details
      className="tool-activity"
      aria-label={`Tool activity ${activity.name}`}
      onToggle={(event) => setExpanded(event.currentTarget.open)}
    >
      <summary className="message-label">
        Tool activity · {activity.name} · {activity.status}
        {activity.promptEligible ? " · restored context" : " · display only"}
      </summary>
      {expanded && <div className="tool-activity-content">
        <div className="message tool-message">
          <p className="message-label">Tool arguments · {activity.name}</p>
          <SafeContent content={activity.arguments} />
        </div>
        <div className="message tool-result-message">
          <p className="message-label">Tool result · {activity.name}</p>
          <SafeContent content={activity.result} />
        </div>
      </div>}
    </details>
  );
}

export const RestoredTurn = memo(function RestoredTurn({ turn, projectId, sessionId, annotationControls }: { turn: TranscriptTurnDto; projectId?: string; sessionId?: string; annotationControls?: AnnotationControls }) {
  const source = projectId === undefined || sessionId === undefined ? undefined : { projectId, sessionId, turnId: turn.turnId };
  const displayOnly = turn.kind === "display-only";
  return (
    <article className="turn-group">
      <div className="message user-message">
        <p className="message-label">
          You · restored turn {turn.turnNumber}{displayOnly ? " · display-only" : ""}
        </p>
        <MessageBody text={turn.userText} source={source === undefined ? undefined : { ...source, role: "user" }} annotationControls={annotationControls} />
        <ReferenceCards references={turn.submittedContext?.references ?? []} />
      </div>
      {turn.toolActivities.map((activity, index) => (
        <RestoredToolActivity
          activity={activity}
          key={`${activity.callId ?? "legacy"}-${activity.name}-${index}`}
        />
      ))}
      {turn.state === "completed" && turn.assistantText !== null ? (
        <div className={`message ${displayOnly ? "system-message" : "assistant-message"}`}>
          <p className="message-label">
            {displayOnly ? "Local command output · restored · display-only" : "Assistant · restored"}
          </p>
          <MessageBody text={turn.assistantText} source={displayOnly || source === undefined ? undefined : { ...source, role: "assistant" }} annotationControls={annotationControls} />
        </div>
      ) : turn.state === "pending" ? (
        <div className="message system-message">
          <p className="message-label">Pending · saved locally</p>
          <p>This turn has not reached a terminal state and will not replay automatically.</p>
        </div>
      ) : (
        <div className="message system-message">
          <p className="message-label">
            {turn.state === "failed" ? "Failed" : "Interrupted"} · saved locally
          </p>
          <SafeContent content={turn.failureMessage ?? "This turn did not complete."} />
        </div>
      )}
    </article>
  );
});

export const ConversationTurns = memo(function ConversationTurns({ turns, projectId, annotationControls }: { turns: readonly VisibleConversationTurn[]; projectId?: string; annotationControls?: AnnotationControls }) {
  return turns.map((item) => {
    const source = projectId === undefined ? undefined : { projectId, sessionId: item.sessionId, turnId: item.turnId };
    if (item.source === "restored") {
      return <RestoredTurn turn={item.turn} projectId={projectId} sessionId={item.sessionId} annotationControls={annotationControls} key={item.key} />;
    }
    if (item.source === "live") {
      return <article className="turn-group" key={item.key}>
        <div className="message user-message"><p className="message-label">You</p>
          <MessageBody text={item.turn.userText} source={source === undefined ? undefined : { ...source, role: "user" }} annotationControls={annotationControls} />
          <ReferenceCards references={item.turn.submittedContext?.references ?? []} />
        </div>
        <div className={`message ${item.turn.responseKind === "command" ? "system-message" : "assistant-message"}`}>
          <p className="message-label">{item.turn.responseKind === "command" ? "Local command output" : "Assistant"} · complete</p>
          <MessageBody text={item.turn.assistantText} source={item.turn.responseKind === "command" || source === undefined ? undefined : { ...source, role: "assistant" }} annotationControls={annotationControls} />
        </div>
      </article>;
    }
    return <article className="turn-group pending-turn" key={item.key}>
      <div className="message user-message"><p className="message-label">You · {item.retrying ? "retrying" : "pending"}</p>
        <MessageBody text={item.turn.userText} source={source === undefined ? undefined : { ...source, role: "user" }} />
        <ReferenceCards references={item.turn.submittedContext?.references ?? []} />
      </div>
      <div className="message assistant-message"><p className="message-label">Assistant · working</p><div className="inline-spinner" aria-label="Waiting for answer" /></div>
      {item.turn.activity.length > 0 && <ul className="activity-list">{item.turn.activity.map((activity, index) => <li key={`${activity.kind}-${index}`}><strong>{activity.kind === "stage" ? "Stage" : "Tool"}:</strong> {activity.label}{activity.status === null ? "" : ` · ${activity.status}`}</li>)}</ul>}
    </article>;
  });
});

export function documentReference(snapshot: DocumentSnapshot, referenceId: string): Reference {
  const { rangeStartUtf16: start, rangeEndUtf16: end, sourceText } = snapshot;
  if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start! < 0 || end! <= start! || end! > sourceText.length) {
    throw new Error("Select document text before adding a reference.");
  }
  let startLine = 1, endLine = 1;
  for (const newline of sourceText.matchAll(/\r\n|\r|\n/g)) {
    const boundary = newline.index + newline[0].length;
    if (boundary <= start!) startLine += 1;
    if (boundary < end!) endLine += 1;
  }
  return { referenceId, kind: "document", text: sourceText.slice(start, end), document: {
    snapshot: { ...structuredClone(snapshot), rangeStartUtf16: start!, rangeEndUtf16: end! },
    startLine, endLine,
  } };
}

export function backgroundDocumentContext(snapshot: DocumentSnapshot | null): DocumentSnapshot | undefined {
  if (snapshot === null) return undefined;
  const { rangeStartUtf16: _start, rangeEndUtf16: _end, ...background } = snapshot;
  return { ...background };
}

export function checkSubmissionSize(text: string, submittedContext: SubmittedContext | null): void {
  const input = submittedContext === null ? text : JSON.stringify({ text, submittedContext });
  if (new TextEncoder().encode(input).byteLength > 1024 * 1024) {
    throw new Error("This submission exceeds the 1 MiB input limit. Remove references or use a smaller source document; your draft is retained.");
  }
}

export function retrySettingsMatch(context: SubmittedContext | null, permission: BashPermissionMode, thinking: "normal" | "extended"): boolean {
  return context === null || (context.permissionMode === permission && context.requestedThinkingMode === thinking);
}

export function visibleMessageRange(root: Node, startNode: Node, startOffset: number, endNode: Node, endOffset: number): { visibleText: string; text: string; startUtf16: number; endUtf16: number } | null {
  let text = "";
  const positions = new Map<Node, { start: number; end: number; boundaries: number[] }>();
  const newline = () => { if (text.length > 0 && !text.endsWith("\n")) text += "\n"; };
  const visit = (node: Node) => {
    const start = text.length;
    if (node.nodeType === 3) {
      text += node.textContent ?? "";
      positions.set(node, { start, end: text.length, boundaries: [] });
      return;
    }
    if (node.nodeType !== 1) return;
    const element = node as Element;
    if (element.hasAttribute("hidden") || element.getAttribute("aria-hidden") === "true" ||
        element.hasAttribute("data-reference-exclude") || ["INPUT", "TEXTAREA", "SELECT", "DETAILS"].includes(element.tagName) ||
        (element.tagName === "BUTTON" && !(element.getAttribute("class") ?? "").split(/\s+/).includes("safe-link"))) return;
    const block = node !== root && /^(P|DIV|PRE|LI|UL|OL|BLOCKQUOTE|H[1-6])$/.test(element.tagName);
    if (block) newline();
    const boundaries = [text.length];
    if (element.tagName === "BR") text += "\n";
    for (const child of Array.from(node.childNodes)) {
      visit(child);
      boundaries.push(text.length);
    }
    positions.set(node, { start, end: text.length, boundaries });
    if (block) newline();
  };
  visit(root);
  const visibleText = text.replace(/\n+$/, "");
  const offset = (node: Node, index: number): number | null => {
    const position = positions.get(node);
    if (position === undefined || !Number.isSafeInteger(index) || index < 0) return null;
    const value = node.nodeType === 3
      ? index <= position.end - position.start ? position.start + index : undefined
      : position.boundaries[index];
    return value === undefined ? null : Math.min(value, visibleText.length);
  };
  const startUtf16 = offset(startNode, startOffset), endUtf16 = offset(endNode, endOffset);
  if (startUtf16 === null || endUtf16 === null || endUtf16 <= startUtf16) return null;
  return { visibleText, text: visibleText.slice(startUtf16, endUtf16), startUtf16, endUtf16 };
}

export function ReferenceCards({ references, onRemove }: { references: readonly Reference[]; onRemove?: (id: string) => void }) {
  if (references.length === 0) return null;
  return <div className="reference-cards" aria-label={onRemove === undefined ? "Submitted references" : "Draft references"} data-reference-exclude>
    {references.map((reference) => <details className="reference-card" key={reference.referenceId}>
      <summary title={reference.kind === "document" ? reference.document.snapshot.path : undefined}><strong>{reference.kind === "document"
        ? `Document · ${reference.document.snapshot.path.split("/").at(-1)} · lines ${reference.document.startLine}–${reference.document.endLine}`
        : `Chat · ${reference.chat.role} · ${reference.chat.sessionId.slice(0, 8)} / ${reference.chat.turnId.slice(0, 8)}`}</strong>
        <span>{reference.text.replace(/\s+/g, " ").slice(0, 100)}{reference.text.length > 100 ? "…" : ""}</span></summary>
      <pre>{reference.text}</pre>
      <p className="reference-version">{reference.kind === "document"
        ? `Path ${reference.document.snapshot.path} · Root ${reference.document.snapshot.rootPath} · revision ${reference.document.snapshot.editorRevision} · disk ${reference.document.snapshot.diskFingerprint}`
        : `Project ${reference.chat.projectId} · UTF-16 ${reference.chat.startUtf16}–${reference.chat.endUtf16} · message ${reference.chat.messageFingerprint}`}</p>
      {onRemove !== undefined && <button type="button" onClick={() => onRemove(reference.referenceId)}>Remove reference</button>}
    </details>)}
  </div>;
}

function MessageBody({ text, source, annotationControls }: { text: string; source?: { projectId: string; sessionId: string; turnId: string; role: "user" | "assistant" }; annotationControls?: AnnotationControls }) {
  const bodyRef = useRef<HTMLDivElement>(null);
  const [positions, setPositions] = useState<Record<string, { top: number; left: number }>>({});
  const references = useMemo(() => annotationControls?.references.filter((reference) => reference.kind === "chat" && source !== undefined &&
    reference.chat.projectId === source.projectId && reference.chat.sessionId === source.sessionId &&
    reference.chat.turnId === source.turnId && reference.chat.role === source.role &&
    annotationControls.annotations.some((item) => item.referenceId === reference.referenceId)) ?? [],
  [annotationControls?.references, annotationControls?.annotations, source?.projectId, source?.sessionId, source?.turnId, source?.role]);
  useLayoutEffect(() => {
    const root = bodyRef.current;
    if (root === null || references.length === 0) { setPositions({}); return; }
    const positionMarkers = () => {
      const bounds = root.getBoundingClientRect();
      const nodes: { node: Node; start: number; end: number }[] = [];
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
        const range = visibleMessageRange(root, node, 0, node, node.textContent?.length ?? 0);
        if (range !== null) nodes.push({ node, start: range.startUtf16, end: range.endUtf16 });
      }
      const next: Record<string, { top: number; left: number }> = {};
      for (const reference of references) {
        if (reference.kind !== "chat") continue;
        const end = reference.chat.endUtf16;
        const last = nodes.find((node) => node.start < end && node.end >= end) ?? nodes.filter((node) => node.end <= end).at(-1);
        if (last === undefined) continue;
        const offset = Math.min(end - last.start, last.node.textContent?.length ?? 0);
        const range = document.createRange();
        range.setStart(last.node, Math.max(0, offset - 1));
        range.setEnd(last.node, offset);
        const rect = range.getBoundingClientRect();
        next[reference.referenceId] = { top: rect.bottom - bounds.top,
          left: Math.max(0, Math.min(rect.right - bounds.left, root.clientWidth - 280)) };
      }
      setPositions(next);
    };
    positionMarkers();
    const observer = new ResizeObserver(positionMarkers);
    observer.observe(root);
    return () => observer.disconnect();
  }, [text, references]);
  return <div ref={bodyRef} className="reference-message-body" {...(source === undefined ? {} : {
    "data-reference-message": "", "data-project-id": source.projectId, "data-session-id": source.sessionId,
    "data-turn-id": source.turnId, "data-message-role": source.role,
  })}><SafeContent content={text} />
    {annotationControls && references.map((reference) => {
      const annotation = annotationControls.annotations.find((item) => item.referenceId === reference.referenceId);
      const position = positions[reference.referenceId];
      return annotation && position ? <div key={reference.referenceId} className="chat-annotation-anchor" data-reference-exclude style={position}>
        <AnnotationComment annotation={annotation} controls={annotationControls} />
      </div> : null;
    })}
  </div>;
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
    <details className="document-menu" data-document-menu onKeyDown={(event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.currentTarget.open = false;
        event.currentTarget.querySelector("summary")?.focus();
      }
    }} onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget as Node | null)) event.currentTarget.open = false;
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

interface DocumentResult extends Partial<DocumentSnapshot> {
  path: string;
  status: "saved" | "conflict" | "failed" | "cancelled";
  callId?: string;
  savedFingerprint?: string;
  candidateText?: string;
  currentDiskText?: string;
  issue?: string;
  expectedSnapshot?: DocumentSnapshot;
}

export function documentContextPayload(value: DocumentSnapshot): JsonObject {
  const { rangeStartUtf16, rangeEndUtf16, ...context } = value;
  return {
    ...context,
    ...(typeof rangeStartUtf16 === "number" && typeof rangeEndUtf16 === "number"
      ? { rangeStartUtf16, rangeEndUtf16 } : {}),
  };
}

export function reconcileSavedDocument(
  current: DocumentSnapshot,
  captured: DocumentSnapshot,
  saved: { sourceText: string; diskFingerprint: string; editorRevision?: number; rangeStartUtf16?: number; rangeEndUtf16?: number },
  agentOperation: boolean,
): DocumentSnapshot {
  if (current.editorRevision !== captured.editorRevision || current.sourceText !== captured.sourceText) {
    return { ...current, diskFingerprint: saved.diskFingerprint };
  }
  return {
    ...current, sourceText: saved.sourceText, diskFingerprint: saved.diskFingerprint,
    editorRevision: saved.editorRevision ?? current.editorRevision + Number(saved.sourceText !== current.sourceText),
    ...(agentOperation ? { rangeStartUtf16: saved.rangeStartUtf16, rangeEndUtf16: saved.rangeEndUtf16 } : {}),
  };
}

interface DocumentAction {
  turnId: string;
  callId?: string;
  undoOfCallId?: string;
  parentRequestId?: string;
  sourceSnapshot?: DocumentSnapshot;
}

type WorkingDocumentSources = Pick<SubmittedContext, "documentContext" | "references">;

export function submittedDocumentSource(context: WorkingDocumentSources | null, referenceId?: string): DocumentSnapshot | undefined {
  if (referenceId === undefined) return context?.documentContext;
  const reference = context?.references.find((item) => item.referenceId === referenceId);
  if (reference?.kind !== "document") throw new Error("The document proposal names an unavailable document reference.");
  return reference.document.snapshot;
}

export function documentOperationContext(current: DocumentSnapshot, source?: DocumentSnapshot): DocumentSnapshot {
  if (source === undefined) return current;
  return { ...current, rangeStartUtf16: source.rangeStartUtf16, rangeEndUtf16: source.rangeEndUtf16 };
}

export function advanceWorkingDocumentSources(
  working: WorkingDocumentSources | null, before: DocumentSnapshot, result: DocumentResult,
): WorkingDocumentSources | null {
  if (working === null || result.status !== "saved" || result.path !== before.path ||
      result.rootPath !== before.rootPath || result.sourceText === undefined || result.editorRevision === undefined ||
      result.diskFingerprint === undefined || result.rangeEndUtf16 === undefined) return working;
  const start = before.rangeStartUtf16 ?? 0, end = before.rangeEndUtf16 ?? before.sourceText.length;
  const newEnd = result.rangeEndUtf16, delta = newEnd - end;
  const advance = (snapshot: DocumentSnapshot, activeDocument = false): DocumentSnapshot => {
    if (snapshot.path !== before.path || snapshot.rootPath !== before.rootPath || snapshot.sourceText !== before.sourceText ||
        snapshot.editorRevision !== before.editorRevision || snapshot.diskFingerprint !== before.diskFingerprint) return snapshot;
    let left = activeDocument ? result.rangeStartUtf16 : snapshot.rangeStartUtf16;
    let right = activeDocument ? result.rangeEndUtf16 : snapshot.rangeEndUtf16;
    if (!activeDocument && left !== undefined && right !== undefined && right > start) {
      if (left >= end) { left += delta; right += delta; }
      else { left = Math.min(left, start); right = Math.max(newEnd, right + delta); }
    }
    return { ...snapshot, sourceText: result.sourceText!, editorRevision: result.editorRevision!, diskFingerprint: result.diskFingerprint!,
      rangeStartUtf16: left, rangeEndUtf16: right };
  };
  return { documentContext: working.documentContext === undefined ? undefined : advance(working.documentContext, true),
    references: working.references.map((reference) => reference.kind === "document"
      ? { ...reference, document: { ...reference.document, snapshot: advance(reference.document.snapshot) as typeof reference.document.snapshot } } : reference) };
}

export default function App() {
  const [state, dispatch] = useReducer(backendReducer, initialBackendState);
  const [conversation, conversationDispatch] = useReducer(conversationReducer, initialConversationState);
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
  const documentBaselineRef = useRef<DocumentSnapshot | null>(null);
  const [catalog, setCatalog] = useState<ProjectListDto | null>(null);
  const [sessionLists, setSessionLists] = useState<Record<string, SessionListDto>>({});
  const [slashCatalogOwner, setSlashCatalogOwner] = useState<SlashCatalogOwner | null>(null);
  const [catalogGeneration, setCatalogGeneration] = useState<number | null>(null);
  const [workspaceBusy, setWorkspaceBusy] = useState<string | null>(null);
  const [workspaceIssue, setWorkspaceIssue] = useState<SafeUiError | null>(null);
  const [transcript, setTranscript] = useState<TranscriptView | null>(null);
  const [selectionPreview, setSelectionPreview] = useState<{ title: string; transcript: TranscriptView } | null>(null);
  const [liveTurns, setLiveTurns] = useState<LiveTurn[]>([]);
  const [pendingUserText, setPendingUserText] = useState<string | null>(null);
  const [registrationIssue, setRegistrationIssue] = useState<string | null>(null);
  const [extensionFlow, setExtensionFlow] = useState<ExtensionFlow | null>(null);
  const [pendingApproval, setPendingApproval] = useState<PendingApproval | null>(null);
  const [approvalResolving, setApprovalResolving] = useState(false);
  const [documentValue, setDocumentValue] = useState<DocumentSnapshot | null>(null);
  const documentRef = useRef<DocumentSnapshot | null>(null);
  const [rootPath, setRootPath] = useState("");
  const [documentBusy, setDocumentBusy] = useState(false);
  const documentBusyRef = useRef(false);
  const [documentNotice, setDocumentNotice] = useState<string | null>(null);
  const [documentConflict, setDocumentConflict] = useState<{ action: DocumentAction | null; result: DocumentResult; base: DocumentSnapshot } | null>(null);
  const [lastDocumentAction, setLastDocumentAction] = useState<DocumentAction | null>(null);
  const documentRequestRef = useRef<{ requestId: string; turnId: string; context: DocumentSnapshot } | null>(null);
  const documentApplyPromiseRef = useRef<Promise<void> | null>(null);
  const workingDocumentSourcesRef = useRef<WorkingDocumentSources | null>(null);
  const submittedDocumentRef = useRef<DocumentSnapshot | null>(null);
  const selectedSkillNamesRef = useRef(new Set<string>());
  useEffect(() => { selectedSkillNamesRef.current.clear(); }, [conversation.selected?.projectId, conversation.selected?.sessionId]);
  const updateDocument = useCallback((value: DocumentSnapshot | null) => {
    documentRef.current = value;
    setDocumentValue(value);
  }, []);
  const inFlight = useRef(false);
  const exclusiveOwnerRef = useRef<WorkspaceOperationOwner | null>(null);
  const catalogLoading = useRef<WorkspaceOperationOwner | null>(null);
  const diagnosticsAttempt = useRef<number | null>(null);
  const generationRef = useRef(0);
  const conversationRef = useRef(conversation);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const transcriptRef = useRef<HTMLDivElement>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const workspaceOperation = useRef<WorkspaceOperationOwner | null>(null);
  const documentOperationRef = useRef<WorkspaceOperationOwner | null>(null);
  const approvalOwnerRef = useRef<WorkspaceOperationOwner | null>(null);
  const frameOwnerRef = useRef<WorkspaceOperationOwner | null>(null);
  const turnOwnerRef = useRef<WorkspaceOperationOwner | null>(null);
  const stopPromiseRef = useRef<Promise<void> | null>(null);
  const pendingApprovalRef = useRef<PendingApproval | null>(null);
  const approvalResolvingRef = useRef(false);

  useEffect(() => { conversationRef.current = conversation; }, [conversation]);
  useEffect(() => { pendingApprovalRef.current = pendingApproval; }, [pendingApproval]);

  const applyConversation = useCallback((action: ConversationAction) => {
    const next = conversationReducer(conversationRef.current, action);
    conversationRef.current = next;
    conversationDispatch(action);
    return next;
  }, []);

  const captureOwner = useCallback((label: string): WorkspaceOperationOwner => ({
    generation: generationRef.current, projectEpoch: projectEpochRef.current, token: Symbol(label),
  }), []);

  const ownsOperation = useCallback((owner: WorkspaceOperationOwner, current: WorkspaceOperationOwner | null) =>
    ownsWorkspaceOperation(owner, current, generationRef.current, projectEpochRef.current), []);

  const beginWorkspaceOperation = useCallback((label: string): WorkspaceOperationOwner | null => {
    if (workspaceOperation.current !== null || inFlight.current || documentBusyRef.current ||
        pendingApprovalRef.current !== null || conversationRef.current.activeTurn !== null ||
        conversationRef.current.stopRequest !== null) return null;
    const owner = captureOwner(label);
    workspaceOperation.current = owner;
    turnOwnerRef.current = null;
    frameOwnerRef.current = null;
    setWorkspaceBusy(label);
    setWorkspaceIssue(null);
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
    catalogLoading.current = null;
    approvalOwnerRef.current = null;
    frameOwnerRef.current = null;
    turnOwnerRef.current = null;
    documentRequestRef.current = null;
    documentApplyPromiseRef.current = null;
    workingDocumentSourcesRef.current = null;
    submittedDocumentRef.current = null;
    stopPromiseRef.current = null;
    documentBusyRef.current = false;
    setDocumentBusy(false);
    setWorkspaceBusy(null);
  }, []);

  const receiveDocumentResult = useCallback((result: DocumentResult, captured: DocumentSnapshot, action: DocumentAction | null) => {
    const current = documentRef.current;
    if (current === null || current.path !== captured.path || current.rootPath !== captured.rootPath) return;
    if (result.path !== captured.path || (result.rootPath !== undefined && result.rootPath !== captured.rootPath)) {
      throw protocolMismatch("The backend returned a document result for a different source.");
    }
    if (result.status === "saved" && result.sourceText !== undefined && result.diskFingerprint !== undefined) {
      if (action?.callId !== undefined && action.sourceSnapshot !== undefined) {
        workingDocumentSourcesRef.current = advanceWorkingDocumentSources(workingDocumentSourcesRef.current, action.sourceSnapshot, result);
      }
      documentBaselineRef.current = { ...captured, sourceText: result.sourceText, diskFingerprint: result.diskFingerprint };
      if (current.editorRevision === captured.editorRevision && current.sourceText === captured.sourceText) {
        updateDocument(reconcileSavedDocument(current, captured, {
          sourceText: result.sourceText, diskFingerprint: result.diskFingerprint,
          editorRevision: result.editorRevision,
          rangeStartUtf16: result.rangeStartUtf16, rangeEndUtf16: result.rangeEndUtf16,
        }, action !== null));
        setDocumentNotice(null);
      } else {
        updateDocument({ ...current, diskFingerprint: result.diskFingerprint });
        setDocumentNotice(null);
      }
      setDocumentConflict(null);
      if (action?.callId !== undefined) setLastDocumentAction(action);
      if (action?.undoOfCallId !== undefined) setLastDocumentAction(null);
    } else if (result.status === "conflict") {
      setDocumentConflict({ result, action, base: action?.sourceSnapshot ?? (action !== null ? submittedDocumentRef.current : null) ?? captured });
      setDocumentNotice("The editor or disk changed. Choose which version to keep.");
    } else if (result.status === "failed") {
      setDocumentConflict({ result, action, base: action?.sourceSnapshot ?? (action !== null ? submittedDocumentRef.current : null) ?? captured });
      setDocumentNotice(result.issue ?? "Save failed. The editor and candidate are retained.");
    } else {
      setDocumentNotice(result.issue ?? "Operation cancelled. Your current text is retained.");
      setDocumentConflict(null);
    }
  }, [updateDocument]);

  const applyDocumentOperation = useCallback((action: DocumentAction, resolution?: "keep" | "use" | "cancel", expectedSnapshot?: DocumentSnapshot): Promise<void> => {
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
        const tracked = backendClient.requestTracked("document.apply", {
          ...requestAction, documentContext: documentContextPayload(captured), ...(resolution === undefined ? {} : { resolution }),
          ...(expectedSnapshot === undefined ? {} : { expectedSnapshot }),
        } as unknown as JsonObject);
        documentRequestRef.current = { requestId: tracked.requestId, turnId: action.turnId, context: captured };
        const result = await tracked.result as unknown as DocumentResult;
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
          if (pendingApprovalRef.current?.parentRequestId === requestId) {
            pendingApprovalRef.current = null;
            approvalOwnerRef.current = null;
            approvalResolvingRef.current = false;
            setPendingApproval(null);
            setApprovalResolving(false);
          }
        }
      }
    })().finally(() => { if (documentApplyPromiseRef.current === pending) documentApplyPromiseRef.current = null; });
    documentApplyPromiseRef.current = pending;
    return pending;
  }, [captureOwner, ownsOperation, receiveDocumentResult]);

  const openDocument = useCallback(async () => {
    if (projectRef.current === null || bindingGenerationRef.current !== generationRef.current || workspaceOperation.current !== null ||
        conversationRef.current.activeTurn !== null || conversationRef.current.stopRequest !== null || documentBusyRef.current || pendingApprovalRef.current !== null) return;
    const owner = captureOwner("document.open");
    documentOperationRef.current = owner;
    frameOwnerRef.current = null;
    documentBusyRef.current = true;
    setDocumentBusy(true);
    try {
      const path = await invoke<string | null>("pick_document", { rootPath: projectRef.current.rootPath });
      if (path === null || !ownsOperation(owner, documentOperationRef.current)) return;
      if (documentRef.current !== null && documentRef.current.sourceText !== documentBaselineRef.current?.sourceText &&
          !window.confirm("Discard unsaved document changes and open another file?")) return;
      const opened = await backendClient.request("document.open", { path }) as unknown as DocumentSnapshot;
      if (!ownsOperation(owner, documentOperationRef.current)) return;
      if (opened.rootPath !== projectRef.current?.rootPath) throw protocolMismatch("The backend opened a document from a different project.");
      documentBaselineRef.current = { ...opened };
      updateDocument({ ...opened, editorRevision: opened.editorRevision ?? 0 });
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
      const result = await backendClient.request("document.save", { documentContext: documentContextPayload(captured) }) as unknown as DocumentResult;
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
    const { action, result } = documentConflict;
    if (action !== null) {
      await applyDocumentOperation(action, resolution, result.expectedSnapshot);
    } else if (resolution === "use" && result.expectedSnapshot !== undefined) {
      const current = documentRef.current;
      if (current === null) return;
      if (current.editorRevision !== result.expectedSnapshot.editorRevision || current.sourceText !== result.expectedSnapshot.sourceText) {
        setDocumentNotice("The editor changed again. Save again to review the current conflict.");
        return;
      }
      updateDocument({ ...current, diskFingerprint: result.expectedSnapshot.diskFingerprint });
      await saveDocument();
    } else {
      setDocumentConflict(null);
      setDocumentNotice(null);
    }
  }, [documentConflict, applyDocumentOperation, saveDocument, updateDocument]);

  useEffect(() => {
    if (!isTauriRuntime()) {
      dispatch({ type: "browser-preview" });
      return;
    }
    let disposed = false;
    let removeListener: (() => void) | undefined;
    void (async () => {
      try {
        const unlisten = await listen<unknown>(BACKEND_EVENT_NAME, ({ payload }) => {
          if (disposed) return;
          try {
            const event = parseBridgeEvent(payload);
            if (event.type === "lifecycle") {
              if (event.snapshot.generation < generationRef.current) return;
              const generationChanged = generationRef.current !== event.snapshot.generation;
              if (generationChanged) {
                invalidateOperations();
                resumeSelectionRef.current = conversationRef.current.selected ?? resumeSelectionRef.current;
                resumeDraftRef.current = conversationRef.current.draft;
                bindingGenerationRef.current = null;
              }
              if (generationChanged || event.snapshot.lifecycle !== "ready") {
                setSlashCatalogOwner(null);
                setSelectionPreview(null);
                pendingApprovalRef.current = null;
                approvalResolvingRef.current = false;
                setPendingApproval(null);
                setApprovalResolving(false);
                setExtensionFlow((current) => {
                  if (current === null) return null;
                  const recoverable = interruptExtensionFlow(current);
                  if (recoverable === null) return null;
                  if (recoverable.report === null) return recoverable;
                  if (event.snapshot.lifecycle === "restarting") {
                    return markExtensionRestarting(recoverable);
                  }
                  if (event.snapshot.lifecycle === "ready" && generationChanged) {
                    return markExtensionAwaitingLoad(markExtensionRestarting(recoverable));
                  }
                  return recoverable;
                });
              }
              generationRef.current = event.snapshot.generation;
              applyConversation({ type: "backend-generation-changed", generation: event.snapshot.generation });
              dispatch({ type: "snapshot", snapshot: event.snapshot });
              return;
            }
            dispatch({ type: "protocol-event", message: event.message });
            const message = event.message;
            if (
              message.messageType === "event" &&
              !("requestId" in message) &&
              (message.event === "backend.crashed" || message.event === "backend.shutting_down")
            ) {
              pendingApprovalRef.current = null;
              approvalResolvingRef.current = false;
              setPendingApproval(null);
              setApprovalResolving(false);
              setExtensionFlow((current) => current === null ? null : interruptExtensionFlow(current));
            }
            if (message.messageType !== "event" || !("requestId" in message)) return;
            const active = conversationRef.current.activeTurn;
            const documentRequest = documentRequestRef.current;
            if (active === null && documentRequest === null) return;
            const generation = generationRef.current;
            if (active !== null && (active.backendGeneration !== generation || active.projectEpoch !== projectEpochRef.current)) return;
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
              const accepted = acceptApprovalEvent(
                generation,
                message.requestId,
                message.requestId === documentRequest?.requestId ? documentRequest.requestId : active?.requestId ?? null,
                message.data as unknown as ApprovalRequiredDto,
                Date.now(),
              );
              if (accepted !== null) {
                setPendingApproval((current) => {
                  if (current !== null) return current;
                  pendingApprovalRef.current = accepted;
                  approvalOwnerRef.current = captureOwner("approval");
                  frameOwnerRef.current = null;
                  return accepted;
                });
              }
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
        const snapshot = await backendClient.initialize(() => {
          if (!disposed) dispatch({ type: "action-started", action: "start" });
        });
        if (!disposed && snapshot.generation >= generationRef.current) {
          const generationChanged = generationRef.current !== snapshot.generation;
          if (generationChanged) invalidateOperations();
          if (generationChanged && projectRef.current !== null) {
            resumeSelectionRef.current = conversationRef.current.selected ?? resumeSelectionRef.current;
            resumeDraftRef.current = conversationRef.current.draft;
            bindingGenerationRef.current = null;
          }
          if (generationChanged || snapshot.lifecycle !== "ready") {
            setSlashCatalogOwner(null);
            pendingApprovalRef.current = null;
            approvalResolvingRef.current = false;
            setPendingApproval(null);
            setApprovalResolving(false);
            setExtensionFlow((current) => {
              if (current === null) return null;
              const recoverable = interruptExtensionFlow(current);
              if (recoverable === null) return null;
              if (recoverable.report === null) return recoverable;
              if (snapshot.lifecycle === "restarting") {
                return markExtensionRestarting(recoverable);
              }
              if (snapshot.lifecycle === "ready" && generationChanged) {
                return markExtensionAwaitingLoad(markExtensionRestarting(recoverable));
              }
              return recoverable;
            });
          }
          generationRef.current = snapshot.generation;
          applyConversation({ type: "backend-generation-changed", generation: snapshot.generation });
          dispatch({ type: "snapshot", snapshot });
          dispatch({ type: "action-completed", action: "start" });
        }
      } catch (error) {
        if (!disposed) dispatch({ type: "action-failed", error: workspaceError(error) });
      }
    })();
    return () => { disposed = true; removeListener?.(); };
  }, [applyConversation, applyDocumentOperation, captureOwner, invalidateOperations, ownsOperation]);

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
    if (workspaceOperation.current !== null || documentBusyRef.current || pendingApprovalRef.current !== null ||
        current.activeTurn !== null || (current.stopRequest !== null && !stopRecovery)) return;
    setSlashCatalogOwner(null);
    if (action === "restart") {
      resumeSelectionRef.current = conversationRef.current.selected;
      resumeDraftRef.current = conversationRef.current.draft;
      bindingGenerationRef.current = null;
      setExtensionFlow((current) => current === null ? null : markExtensionRestarting(current));
    }
    const operation = action === "start" ? backendClient.start : action === "restart" ? backendClient.restart : backendClient.shutdown;
    void runExclusive(action, async (owner) => {
      const snapshot = await operation();
      if (exclusiveOwnerRef.current?.token !== owner.token || owner.projectEpoch !== projectEpochRef.current ||
          snapshot.generation < generationRef.current) return;
      generationRef.current = snapshot.generation;
      applyConversation({ type: "backend-generation-changed", generation: snapshot.generation });
      dispatch({ type: "snapshot", snapshot });
      if (action === "restart" && snapshot.lifecycle === "ready") {
        setExtensionFlow((current) => current === null ? null : markExtensionAwaitingLoad(current));
      }
      dispatch({ type: "action-completed", action });
    });
  }, [applyConversation, runExclusive]);

  const loadDiagnostics = useCallback((force: boolean) => {
    const generation = state.snapshot?.generation;
    if (generation === undefined || (!force && diagnosticsAttempt.current === generation)) return;
    diagnosticsAttempt.current = generation;
    void runExclusive("diagnostics", async (owner) => {
      const data = await backendClient.request("runtime.diagnostics", {});
      if (!ownsOperation(owner, exclusiveOwnerRef.current)) return;
      dispatch({ type: "diagnostics-succeeded", diagnostics: toBoundedDiagnostics(data as unknown as RuntimeDiagnosticsDto) });
    });
  }, [ownsOperation, runExclusive, state.snapshot?.generation]);

  useEffect(() => {
    if (state.phase === "backend-ready" && state.snapshot?.lifecycle === "ready" && state.diagnostics === null && state.activeAction === null) loadDiagnostics(false);
  }, [loadDiagnostics, state.activeAction, state.diagnostics, state.phase, state.snapshot?.lifecycle]);

  const loadCatalog = useCallback(async (generation: number) => {
    const currentProject = projectRef.current;
    if (currentProject === null || bindingGenerationRef.current !== generation || generation !== generationRef.current) return;
    const owner = captureOwner("project history");
    catalogLoading.current = owner;
    const isCurrent = () => ownsOperation(owner, catalogLoading.current);
    setWorkspaceIssue(null);
    try {
      const loaded = await loadSelectedProjectHistory(currentProject.projectId, backendClient.request, isCurrent);
      if (!isCurrent() || loaded === null) return;
      setCatalog(loaded.catalog);
      setSessionLists({ [currentProject.projectId]: loaded.sessions });
      setCatalogGeneration(generation);
    } catch (error) {
      if (isCurrent()) {
        setCatalogGeneration(generation);
        setWorkspaceIssue(workspaceError(error));
      }
    } finally {
      if (isCurrent()) catalogLoading.current = null;
    }
  }, [captureOwner, ownsOperation]);

  const chooseProject = useCallback(async (action: "inspect" | "open" | "initialize", browse = false) => {
    if (conversationRef.current.activeTurn !== null || pendingApprovalRef.current !== null ||
        documentBusyRef.current || documentConflict !== null) return;
    const operation = beginWorkspaceOperation(action === "inspect" ? "Inspecting project" : "Opening project");
    if (operation === null) return;
    const generation = operation.generation;
    const isCurrent = () => ownsOperation(operation, workspaceOperation.current);
    setChooserIssue(null);
    try {
      let selectedRoot = candidate?.rootPath ?? candidateRoot;
      if (browse) {
        const picked = await invoke<string | null>("pick_project", { initialPath: selectedRoot || null });
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
      const data = await backendClient.request("workspace.select", {
        rootPath: selectedRoot,
        action,
        ...(action === "inspect" && !browse && candidate?.status === "needs_configuration" ? { historyDirectory: candidateHistory } : {}),
        ...(action === "initialize" ? {
          historyDirectory: candidateHistory,
          expectedFingerprint: candidate?.researchFingerprint ?? null,
        } : {}),
      }) as unknown as ProjectWorkspaceDto;
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
      setCatalog(null);
      setCatalogGeneration(null);
      setSessionLists({});
      setSlashCatalogOwner(null);
      setTranscript(null);
      setSelectionPreview(null);
      setLiveTurns([]);
      setPendingUserText(null);
      setRegistrationIssue(null);
      setExtensionFlow(null);
      setPendingApproval(null);
      pendingApprovalRef.current = null;
      approvalResolvingRef.current = false;
      setApprovalResolving(false);
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
      await loadCatalog(generation);
    } catch (error) {
      if (isCurrent()) {
        setChooserIssue(workspaceError(error).message);
      }
    } finally { finishWorkspaceOperation(operation); }
  }, [applyConversation, beginWorkspaceOperation, candidate, candidateHistory, candidateRoot, dirtyChoice, discardDraft, documentConflict, finishWorkspaceOperation, loadCatalog, ownsOperation, saveDocument, updateDocument]);

  const showProjectChooser = useCallback(() => {
    if (conversationRef.current.activeTurn !== null || conversationRef.current.stopRequest !== null || pendingApprovalRef.current !== null ||
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

  const loadMoreSessions = useCallback((projectId: string) => {
    const current = sessionLists[projectId];
    if (current === undefined || !current.hasMore) return;
    const operation = beginWorkspaceOperation("Loading more conversations");
    if (operation === null) return;
    const isCurrent = () => ownsOperation(operation, workspaceOperation.current);
    const offset = current.items.length;
    void (async () => {
      try {
        const data = await backendClient.request("session.list", { projectId, offset, limit: 50 }) as unknown as SessionListDto;
        if (!isCurrent()) return;
        if (data.projectId !== projectId || data.offset !== offset) {
          throw protocolMismatch("The backend returned a mismatched conversation page.");
        }
        setSessionLists((lists) => {
          const existing = lists[projectId];
          if (existing === undefined || existing.items.length !== offset) return lists;
          const items = mergeSessionItems(existing.items, data.items);
          return {
            ...lists,
            [projectId]: { ...data, items, offset: 0, limit: items.length },
          };
        });
      } catch (error) {
        if (isCurrent()) setWorkspaceIssue(workspaceError(error));
      } finally {
        finishWorkspaceOperation(operation);
      }
    })();
  }, [ownsOperation, beginWorkspaceOperation, finishWorkspaceOperation, sessionLists]);

  useEffect(() => {
    const generation = state.snapshot?.generation;
    if (generation === undefined) return;
    generationRef.current = generation;
    applyConversation({ type: "backend-generation-changed", generation });
    if (catalogGeneration !== null && catalogGeneration !== generation) {
      workspaceOperation.current = null;
      setWorkspaceBusy(null);
      setWorkspaceIssue(null);
      setCatalog(null);
      setSessionLists({});
      setTranscript(null);
      setSelectionPreview(null);
      setLiveTurns([]);
      setPendingUserText(null);
      setRegistrationIssue(null);
      pendingApprovalRef.current = null;
      approvalResolvingRef.current = false;
      setPendingApproval(null);
      setApprovalResolving(false);
      setExtensionFlow((current) => current === null ? null : interruptExtensionFlow(current));
      setCatalogGeneration(null);
    }
  }, [applyConversation, catalogGeneration, state.snapshot?.generation]);

  useEffect(() => {
    const generation = state.snapshot?.generation;
    if (generation === undefined || state.snapshot?.lifecycle !== "ready" || state.diagnostics === null ||
        project === null || catalogGeneration === generation || (catalogLoading.current !== null && ownsOperation(catalogLoading.current, catalogLoading.current)) ||
        workspaceOperation.current !== null) return;
    if (bindingGenerationRef.current === generation) {
      void loadCatalog(generation);
      return;
    }
    const operation = beginWorkspaceOperation("Reopening selected project");
    if (operation === null) return;
    const isCurrent = () => ownsOperation(operation, workspaceOperation.current);
    void backendClient.request("workspace.select", { rootPath: project.rootPath, action: "open" }).then(async (data) => {
      if (!isCurrent()) return;
      const opened = data as unknown as ProjectWorkspaceDto;
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
      await loadCatalog(generation);
    }).catch((error: unknown) => {
      if (!isCurrent()) return;
      setCatalogGeneration(generation);
      setChooserIssue(workspaceError(error).message);
      setCandidate(null);
      setCandidateRoot(project.rootPath);
      setChooserOpen(true);
    }).finally(() => finishWorkspaceOperation(operation));
  }, [applyConversation, beginWorkspaceOperation, catalogGeneration, finishWorkspaceOperation, loadCatalog, ownsOperation, project, state.diagnostics, state.snapshot?.generation, state.snapshot?.lifecycle]);

  const focusComposer = useCallback((owner: WorkspaceOperationOwner = captureOwner("composer focus")) => {
    scheduleOwnedFrame(owner, () => composerRef.current?.focus());
  }, [captureOwner, scheduleOwnedFrame]);

  const addDocumentReference = useCallback((snapshot: DocumentSnapshot) => {
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
    const pending = Promise.resolve().then(() => backendClient.request("session.stop", {
      sessionId: target.sessionId, turnId: target.turnId, parentRequestId: target.requestId,
    })).then(async (data) => {
      const result = data as unknown as TurnStoppedDto;
      if (result.sessionId !== target.sessionId || result.turnId !== target.turnId) {
        throw protocolMismatch("The backend stopped a different turn.");
      }
      const next = applyConversation({ type: "stop-succeeded", ...correlation });
      if (!retryingStop || next.stopRequest !== null || next.activeTurn !== null ||
          generation !== generationRef.current || projectEpoch !== projectEpochRef.current || !sameSelection(next.selected, target)) return;
      const operation = beginWorkspaceOperation("Refreshing saved conversation");
      if (operation === null) return;
      try {
        await loadCatalog(generation);
        if (!ownsOperation(operation, workspaceOperation.current) || state.session?.sessionId !== target.sessionId) return;
        if (next.failure?.turnLifecycle?.accepted) {
          const data = await fetchTranscriptPage(target.projectId, target.sessionId,
            transcriptTailOffset(state.session.turnCount + 1), TRANSCRIPT_PAGE_SIZE);
          if (!ownsOperation(operation, workspaceOperation.current)) return;
          dispatch({ type: "session-created", session: { ...state.session, registered: true, turnCount: data.total } });
          setTranscript(transcriptViewFrom(target.projectId, target.sessionId, data));
          setLiveTurns([]);
        }
        setPendingUserText(null);
      } catch (error: unknown) {
        if (ownsOperation(operation, workspaceOperation.current)) {
          setRegistrationIssue(`The turn stopped, but its saved conversation could not be refreshed. ${workspaceError(error).message}`);
        }
      } finally { finishWorkspaceOperation(operation); }
    }).catch((error: unknown) => {
      applyConversation({ type: "stop-failed", ...correlation, message: workspaceError(error).message });
    }).finally(() => {
      if (stopPromiseRef.current === pending) stopPromiseRef.current = null;
    });
    stopPromiseRef.current = pending;
  }, [applyConversation, beginWorkspaceOperation, finishWorkspaceOperation, loadCatalog, ownsOperation, state.session]);

  const resolvePendingApproval = useCallback((approved: boolean, expectedApprovalId?: string) => {
    const approval = pendingApprovalRef.current;
    const owner = approvalOwnerRef.current;
    if (approval === null || owner === null || approvalResolvingRef.current || conversationRef.current.stopRequest !== null ||
        (expectedApprovalId !== undefined && approval.approvalId !== expectedApprovalId) ||
        !ownsOperation(owner, approvalOwnerRef.current)) return;
    const isCurrent = () => ownsOperation(owner, approvalOwnerRef.current) &&
      pendingApprovalRef.current?.approvalId === approval.approvalId;
    approvalResolvingRef.current = true;
    setApprovalResolving(true);
    void backendClient.request("approval.resolve", {
      approvalId: approval.approvalId,
      parentRequestId: approval.parentRequestId,
      turnId: approval.turnId,
      approved,
      ...(approval.operation?.startsWith("document.") && documentRef.current !== null ? { documentContext: documentContextPayload(
        documentOperationContext(documentRef.current, documentRequestRef.current?.turnId === approval.turnId ? documentRequestRef.current.context : undefined),
      ) } : {}),
    }).then((data) => {
      if (!isCurrent()) return;
      const result = data as unknown as ApprovalResolvedDto;
      if (result.approvalId !== approval.approvalId) {
        throw protocolMismatch("The backend resolved a different approval request.");
      }
    }).catch((error: unknown) => {
      if (isCurrent()) setWorkspaceIssue(workspaceError(error));
    }).finally(() => {
      if (!isCurrent()) return;
      pendingApprovalRef.current = null;
      approvalOwnerRef.current = null;
      setPendingApproval(null);
      approvalResolvingRef.current = false;
      setApprovalResolving(false);
      focusComposer(owner);
    });
  }, [focusComposer, ownsOperation]);

  const returnApprovalFocus = useCallback(() => {
    const owner = approvalOwnerRef.current;
    if (pendingApprovalRef.current === null && owner !== null && ownsOperation(owner, approvalOwnerRef.current)) focusComposer(owner);
  }, [focusComposer, ownsOperation]);

  useEffect(() => {
    if (pendingApproval === null) return;
    const remaining = Date.parse(pendingApproval.expiresAt) - Date.now();
    if (remaining <= 0) {
      resolvePendingApproval(false, pendingApproval.approvalId);
      return;
    }
    const timeout = window.setTimeout(() => resolvePendingApproval(false, pendingApproval.approvalId), remaining);
    return () => window.clearTimeout(timeout);
  }, [pendingApproval, resolvePendingApproval]);

  useEffect(() => {
    if (pendingApproval === null) return;
    const active = conversation.activeTurn;
    if (
      active?.requestId !== pendingApproval.parentRequestId &&
      documentRequestRef.current?.requestId !== pendingApproval.parentRequestId
    ) {
      pendingApprovalRef.current = null;
      approvalResolvingRef.current = false;
      setPendingApproval(null);
      setApprovalResolving(false);
    }
  }, [conversation.activeTurn, pendingApproval]);

  const selectConversation = useCallback(async (projectId: string, session: SessionSummaryDto) => {
    if (conversationRef.current.activeTurn !== null || projectRef.current?.projectId !== projectId ||
        bindingGenerationRef.current !== generationRef.current || documentBusyRef.current || pendingApprovalRef.current !== null) return;
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
          setExtensionFlow((current) => observeExtensionRevision(current, selected.extensionRevision));
          applyConversation({ type: "conversation-selected", generation, projectEpoch: operation.projectEpoch, preserveDraft: restoringSelection, projectId, sessionId: session.sessionId });
          selectionApplied = true;
          setChatSelection(null);
          setReferenceIssue(null);
          if (!restoringSelection) {
            resumeDraftRef.current = null;
            resumeSelectionRef.current = null;
          }
          setRegistrationIssue(null);
          setLiveTurns([]);
          setPendingUserText(null);
          setTranscript({ projectId, sessionId: session.sessionId, status: "unavailable", issue: "Loading saved transcript…", items: [], offset: 0, total: selected.turnCount, hasOlder: false });
        },
      });
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
    if (catalog === null || catalog.selectedProjectId === null || conversation.selected !== null || workspaceBusy !== null) return;
    const projectId = catalog.selectedProjectId;
    const sessionId = resumeSelectionRef.current?.projectId === projectId ? resumeSelectionRef.current.sessionId : catalog.selectedSessionId;
    if (sessionId === null) return;
    const summary = sessionLists[projectId]?.items.find((item) => item.sessionId === sessionId);
    if (summary !== undefined) void selectConversation(projectId, summary);
  }, [catalog, conversation.selected, selectConversation, sessionLists, workspaceBusy]);

  const activeProjectId = bindingGenerationRef.current === state.snapshot?.generation ? project?.projectId ?? null : null;

  const createSession = useCallback(() => {
    if (activeProjectId === null || conversationRef.current.activeTurn !== null || documentBusyRef.current || pendingApprovalRef.current !== null) return;
    if (resumeDraftRef.current === null && (conversationRef.current.draft.length > 0 || conversationRef.current.draftReferences.length > 0) &&
        !window.confirm("Discard the unsent draft and references and create a new conversation?")) return;
    const operation = beginWorkspaceOperation("Creating conversation");
    if (operation === null) return;
    setSlashCatalogOwner(null);
    const generation = operation.generation;
    const isCurrent = () => ownsOperation(operation, workspaceOperation.current);
    void (async () => {
      try {
        const data = await backendClient.request("session.create", sessionCreateParams(activeProjectId));
        const session = data as unknown as SessionCreatedDto;
        if (!isCurrent()) return;
        if (session.projectId !== undefined && session.projectId !== activeProjectId) {
          throw protocolMismatch("The backend created a conversation in a different project.");
        }
        setSlashCatalogOwner({ generation, projectId: activeProjectId, sessionId: session.sessionId });
        dispatch({ type: "session-created", session });
        setExtensionFlow((current) => observeExtensionRevision(current, session.extensionRevision));
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
        setRegistrationIssue(null);
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
        const data = await fetchTranscriptPage(current.projectId, current.sessionId, offset, limit, "The backend returned older turns for a different conversation.");
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
        documentBusyRef.current || pendingApprovalRef.current !== null || bindingGenerationRef.current !== generationRef.current ||
        selectedProject.projectId !== selected.projectId) return;
    const submission = nextTurnSubmission(conversationRef.current, newLogicalTurnId);
    if (submission.retry && !retrySettingsMatch(conversationRef.current.submittedContext, session.bashPermissionMode, session.thinkingMode)) {
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
        const inspected = await backendClient.request("workspace.select", { rootPath: selectedProject.rootPath, action: "inspect" }) as unknown as ProjectWorkspaceDto;
        if (!ownsOperation(owner, workspaceOperation.current)) return;
        if (inspected.status !== "ready" || inspected.projectId !== selectedProject.projectId ||
            inspected.rootPath !== selectedProject.rootPath || inspected.historyDirectory !== selectedProject.historyDirectory) {
          throw new Error("The project history configuration changed. Reopen the project before sending; your draft is retained.");
        }
        submittedContext = {
          projectId: selected.projectId, rootPath: selectedProject.rootPath,
          permissionMode: session.bashPermissionMode, requestedThinkingMode: session.thinkingMode,
          skillReferences: inlineSkillReferences(draft, session.loadedSkills, selectedSkillNamesRef.current),
          projectRules: { text: inspected.rulesText, fingerprint: inspected.rulesFingerprint },
          ...(background === undefined ? {} : { documentContext: background }),
          references,
        };
      }
      checkSubmissionSize(draft, submittedContext);
      if (!ownsOperation(owner, workspaceOperation.current)) return;
      tracked = backendClient.requestTracked("session.turn", {
        text: draft, turnId, retry: submission.retry,
        ...(submittedContext === null ? {} : { submittedContext: submittedContext as unknown as JsonObject }),
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
    void tracked.result.then(async (data) => {
      if (!isCurrent()) return;
      workingDocumentSourcesRef.current = null;
      const result = data as unknown as TurnCompletedDto;
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
        streamKind: answer.streamKind,
      }));
      setPendingUserText(null);
      pendingApprovalRef.current = null;
      approvalResolvingRef.current = false;
      setPendingApproval(null);
      setApprovalResolving(false);
      if (result.extensionAction === "preview") {
        setExtensionFlow(createExtensionFlow(result.turnId));
      }
      if (state.session !== null) {
        dispatch({
          type: "session-created",
          session: {
            ...state.session,
            registered: result.registrationStatus === "registered" ? true : state.session.registered,
            turnCount: reconciledTurnCount(state.session.turnCount, answer.turnNumber),
          },
        });
      }
      if (result.registrationStatus === "pending") {
        setRegistrationIssue(result.registrationIssue ?? "The saved conversation is awaiting catalog registration.");
      } else if (result.registrationStatus === "registered") {
        setRegistrationIssue(null);
      }
      await stopPromiseRef.current;
      if (!isCurrent() || conversationRef.current.stopRequest !== null) return;
      if (result.registrationStatus === "registered") await loadCatalog(generation);
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
      pendingApprovalRef.current = null;
      approvalResolvingRef.current = false;
      setPendingApproval(null);
      setApprovalResolving(false);
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
      void (async () => {
        try {
          await loadCatalog(generation);
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
          );
          if (!selectionIsCurrent()) return;
          const savedTurn = data.items.find((turn) => turn.turnId === turnId);
          if (savedTurn !== undefined) {
            applyConversation({ type: "turn-acceptance-reconciled", generation, projectEpoch: operation.projectEpoch,
              projectId: selected.projectId, sessionId: selected.sessionId, turnId, state: savedTurn.state });
          }
          dispatch({
            type: "session-created",
            session: { ...currentSession, registered: true, turnCount: data.total },
          });
          setTranscript(transcriptViewFrom(selected.projectId, selected.sessionId, data));
          setLiveTurns([]);
          setRegistrationIssue(null);
          scheduleOwnedFrame(operation, () => transcriptEndRef.current?.scrollIntoView({ block: "end" }));
        } catch (reconciliationError: unknown) {
          if (!selectionIsCurrent()) return;
          const issue = workspaceError(reconciliationError);
          setWorkspaceIssue(safe);
          setRegistrationIssue(`${next.submittedTurn?.accepted || isPersistedTurnFailure(next.failure) ? "The prompt is saved, but" : "Delivery is unconfirmed and"} the conversation state could not be refreshed. ${issue.message}`);
        } finally {
          finishWorkspaceOperation(operation);
        }
      })();
    });
  }, [captureOwner, ownsOperation, scheduleOwnedFrame, applyConversation, beginWorkspaceOperation, finishWorkspaceOperation, focusComposer, loadCatalog, state.session]);

  const sendNewTurn = useCallback(() => {
    applyConversation({ type: "new-turn-requested", generation: generationRef.current, projectEpoch: projectEpochRef.current });
    void sendTurn();
  }, [applyConversation, sendTurn]);

  const previewExtensions = useCallback(() => {
    const flow = extensionFlow;
    if (flow === null || (flow.phase !== "ready" && flow.phase !== "error")) return;
    const operation = beginWorkspaceOperation("Previewing extensions");
    if (operation === null) return;
    const isCurrent = () => ownsOperation(operation, workspaceOperation.current);
    setExtensionFlow((current) => current?.triggerTurnId === flow.triggerTurnId ? beginExtensionPreview(current) : current);
    void backendClient.request("extensions.preview", {}).then((data) => {
      if (!isCurrent()) return;
      const preview = data as unknown as ExtensionPreviewDto;
      setExtensionFlow((current) => current?.triggerTurnId === flow.triggerTurnId ? receiveExtensionPreview(current, preview) : current);
    }).catch((error: unknown) => {
      if (!isCurrent()) return;
      const safe = workspaceError(error);
      setExtensionFlow((current) => current?.triggerTurnId === flow.triggerTurnId ? failExtensionFlow(current, safe.message) : current);
    }).finally(() => finishWorkspaceOperation(operation));
  }, [ownsOperation, beginWorkspaceOperation, extensionFlow, finishWorkspaceOperation]);

  const decideBinding = useCallback((
    bindingHash: string,
    decision: Exclude<ExtensionBindingDecision, null>,
  ) => {
    setExtensionFlow((current) => current === null ? null : decideExtensionBinding(current, bindingHash, decision));
  }, []);

  const applyExtensions = useCallback(() => {
    const flow = extensionFlow;
    if (flow === null) return;
    const effectiveFlow = state.session?.bashPermissionMode === "bypass" && flow.preview !== null
      ? { ...flow, decisions: Object.fromEntries(flow.preview.bindings.map((binding) => [binding.bindingHash, "approve" as const])) }
      : flow;
    const submitting = effectiveFlow.phase === "error" && effectiveFlow.applyRequest !== null
      ? beginExtensionApplyRecovery(effectiveFlow)
      : beginExtensionApply(effectiveFlow, newLogicalTurnId());
    const request = extensionApplyRequest(submitting);
    if (request === null) return;
    const operation = beginWorkspaceOperation("Applying extensions");
    if (operation === null) return;
    const isCurrent = () => ownsOperation(operation, workspaceOperation.current);
    setExtensionFlow((current) => current?.triggerTurnId === flow.triggerTurnId ? submitting : current);
    void backendClient.request("extensions.apply", request).then((data) => {
      if (!isCurrent()) return;
      const report = data as unknown as ExtensionApplyDto;
      if (report.sessionId !== state.session?.sessionId || report.turnId !== request.turnId) {
        throw protocolMismatch("The backend returned an apply result for a different conversation turn.");
      }
      const alreadyVisible =
        (transcript?.sessionId === report.sessionId &&
          transcript.items.some((turn) => turn.turnId === report.turnId)) ||
        liveTurns.some((turn) =>
          turn.sessionId === report.sessionId && turn.turnId === report.turnId
        );
      setExtensionFlow((current) => {
        if (current?.triggerTurnId !== flow.triggerTurnId || current.applyRequest?.turnId !== request.turnId) return current;
        return observeExtensionRevision(
          receiveExtensionApply(current, report),
          state.session?.extensionRevision ?? -1,
        );
      });
      if (!alreadyVisible) {
        setLiveTurns((turns) => upsertLiveTurn(turns, {
          sessionId: report.sessionId,
          turnId: report.turnId,
          turnNumber: report.turnNumber,
          userText: report.displayInput,
          assistantText: report.text,
          responseKind: "command",
          streamKind: "final_only",
        }));
      }
      if (state.session !== null && !alreadyVisible) {
        dispatch({
          type: "session-created",
          session: {
            ...state.session,
            turnCount: reconciledTurnCount(state.session.turnCount, report.turnNumber),
          },
        });
      }
      scheduleOwnedFrame(operation, () => transcriptEndRef.current?.scrollIntoView({ block: "end" }));
    }).catch((error: unknown) => {
      if (!isCurrent()) return;
      const safe = workspaceError(error);
      setExtensionFlow((current) => current?.triggerTurnId === flow.triggerTurnId
        ? failExtensionApply(current, safe.message, safe.turnLifecycle)
        : current);
    }).finally(() => finishWorkspaceOperation(operation));
  }, [ownsOperation, scheduleOwnedFrame, beginWorkspaceOperation, extensionFlow, finishWorkspaceOperation, liveTurns, state.session, transcript]);

  const restartForExtensions = useCallback(() => {
    if (extensionFlow?.phase !== "applied" || extensionFlow.report?.restartRequired !== true) return;
    runLifecycle("restart");
  }, [extensionFlow, runLifecycle]);

  const retryRegistration = useCallback(() => {
    const selected = conversation.selected;
    if (selected === null || conversation.activeTurn !== null) return;
    const operation = beginWorkspaceOperation("Retrying registration");
    if (operation === null) return;
    const generation = operation.generation;
    const isCurrent = () => ownsOperation(operation, workspaceOperation.current);
    void backendClient.request("session.retry_registration", selected as unknown as JsonObject).then(async (data) => {
      const result = data as unknown as RegistrationRetryDto;
      if (!isCurrent()) return;
      if (result.projectId !== selected.projectId || result.sessionId !== selected.sessionId) {
        throw protocolMismatch("The backend returned registration state for a different conversation.");
      }
      if (result.status === "registered") {
        setRegistrationIssue(null);
        if (state.session !== null) dispatch({ type: "session-created", session: { ...state.session, registered: true } });
        await loadCatalog(generation);
      } else setRegistrationIssue(result.issue ?? "Catalog registration is still pending.");
    }).catch((error: unknown) => {
      if (isCurrent()) setWorkspaceIssue(workspaceError(error));
    }).finally(() => {
      if (isCurrent()) focusComposer(operation);
      finishWorkspaceOperation(operation);
    });
  }, [ownsOperation, beginWorkspaceOperation, conversation.activeTurn, conversation.selected, finishWorkspaceOperation, focusComposer, loadCatalog, state.session]);

  const updateThinkingMode = useCallback(async (
    mode: "normal" | "extended",
  ) => {
    const selected = conversationRef.current.selected;
    if (selected === null || conversationRef.current.activeTurn !== null) return;
    const operation = beginWorkspaceOperation("Updating session controls");
    if (operation === null) return;
    const isCurrent = () => ownsOperation(operation, workspaceOperation.current);
    try {
      const data = await backendClient.request("session.set_thinking", { mode });
      if (!isCurrent()) return;
      if (data.sessionId !== selected.sessionId) {
        throw protocolMismatch("The backend returned controls for a different conversation.");
      }
      dispatch({
        type: "session-created",
        session: state.session === null
          ? data as unknown as SessionCreatedDto
          : { ...state.session, ...data as unknown as SessionCreatedDto },
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

  const updateBashPermissionMode = useCallback(async (
    mode: BashPermissionMode,
  ) => {
    const selected = conversationRef.current.selected;
    if (selected === null || conversationRef.current.activeTurn !== null) return;
    const operation = beginWorkspaceOperation("Updating session controls");
    if (operation === null) return;
    const generation = operation.generation;
    const isCurrent = () => ownsOperation(operation, workspaceOperation.current);
    try {
      const data = (await backendClient.request("session.set_bash_permission", { mode })) as unknown as SessionBashPermissionSetDto;
      if (!isCurrent()) return;
      const updatedMode = reconcileBashPermissionAck(
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
              bashPermissionMode: updatedMode,
              slashCommands: [],
              loadedSkills: [],
              mcpFamilies: [],
              startupDiagnostics: [],
              extensionRevision: 0,
            }
          : { ...state.session, bashPermissionMode: updatedMode },
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

  const selectedRegistered = state.session?.registered === true;
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
  const canStart = !state.browserPreview && idle && (state.snapshot === null || state.snapshot.lifecycle === "stopped");
  const stopRecovery = conversation.stopRequest?.status === "failed" && conversation.activeTurn === null &&
    state.activeAction === null && workspaceBusy === null && !documentBusy && pendingApproval === null;
  const stopping = conversation.stopRequest !== null && conversation.stopRequest.status !== "failed";
  const canRestart = !state.browserPreview && (idle || stopRecovery) && (state.phase === "crashed" || state.phase === "degraded" || state.snapshot?.childRunning === true);
  const canShutdown = !state.browserPreview && idle && state.snapshot?.childRunning === true;
  const canCreateSession = !state.browserPreview && idle && workspaceBusy === null && state.snapshot?.lifecycle === "ready" && state.diagnostics !== null && activeProjectId !== null;
  const shutdownMessage = shutdownSummary(state.snapshot);
  const selectedSummary = useMemo(() => {
    const selected = conversation.selected;
    if (selected === null) return null;
    return sessionLists[selected.projectId]?.items.find((item) => item.sessionId === selected.sessionId) ?? null;
  }, [conversation.selected, sessionLists]);
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
  const retryControlsMatch = retrySettingsMatch(conversation.submittedContext, state.session?.bashPermissionMode ?? "ask", state.session?.thinkingMode ?? "normal");
  const documentDirty = documentValue !== null && documentValue.sourceText !== documentBaselineRef.current?.sourceText;
  const activeSession = renderConversation ? state.session : null;

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-workspace">Skip to main workspace</a>
      <aside className="sidebar" aria-label="Research Agent workspace">
        <div className="brand-lockup"><span className="brand-mark" aria-hidden="true">R</span><div><p className="eyebrow">LOCAL WORKSPACE</p><h1>Research Agent</h1></div></div>
        <button className="new-session-button" type="button" title="Creating or selecting a conversation starts its enabled, configured MCP servers." onClick={createSession} disabled={!canCreateSession || interaction.createDisabled}><span aria-hidden="true">＋</span> New conversation</button>
        <section className="sidebar-section project-browser" aria-labelledby="workspace-label">
          <h2 id="workspace-label">Project</h2>
          <button type="button" onClick={showProjectChooser} disabled={!idle || state.snapshot?.lifecycle !== "ready" || state.diagnostics === null}>{project === null ? "Open project" : "Switch project"}</button>
          {catalog === null && <p className="sidebar-note">{project === null ? "Choose a project to load its conversations." : catalogGeneration === null ? "Loading selected project…" : "Project unavailable"}</p>}
          {catalog?.issue !== null && catalog?.issue !== undefined && <p className="sidebar-note">{catalog.issue}</p>}
          {catalog?.projects.map((project: ProjectSummaryDto) => {
            const list = sessionLists[project.projectId];
            const rows = sidebarRowsForProject(project.projectId, list?.items ?? [], conversation.selected, selectedRegistered);
            return <div className="project-group" key={project.projectId}>
              <div className="project-heading"><strong tabIndex={0} title={project.name}>{project.name}</strong><small>{project.sessionCount} saved</small></div>
              {list?.status === "unavailable" && <p className="sidebar-note">{list.issue ?? "Conversations unavailable"}</p>}
              {rows.length === 0 && list?.status !== "unavailable" ? <p className="sidebar-note">No saved conversations</p> : <ul className="session-list">{rows.map((session) => {
                const isSelected = conversation.selected?.sessionId === session.sessionId && conversation.selected.projectId === project.projectId;
                return <li key={session.sessionId}><button type="button" className="session-link" title={session.title} aria-label={session.title} aria-current={isSelected ? "page" : undefined} disabled={interaction.selectDisabled || documentBusy || pendingApproval !== null || workspaceBusy !== null || session.status !== "ready"} onClick={() => void selectConversation(project.projectId, session)}><span>{session.title}</span><small>{session.transient ? "Not saved yet" : `${session.turnCount} turns${session.status === "ready" ? "" : ` · ${session.status}`}`}</small></button></li>;
              })}</ul>}
              {list?.hasMore && <button className="load-more-sessions" type="button" onClick={() => loadMoreSessions(project.projectId)} disabled={interaction.selectDisabled || documentBusy || pendingApproval !== null || workspaceBusy !== null}>Load more conversations</button>}
            </div>;
          })}
        </section>
        <div className="sidebar-spacer" />
        <section className="backend-controls" aria-labelledby="backend-controls-title">
          <div className="sidebar-status" role="status" aria-live="polite"><span className={`status-dot status-${state.phase}`} aria-hidden="true" /><span><strong id="backend-controls-title">{phaseLabels[state.phase]}</strong><small>{state.snapshot === null ? "Desktop process not observed" : `Generation ${state.snapshot.generation} · ${state.snapshot.pendingRequests} pending`}</small></span></div>
          <div className="control-row"><button type="button" onClick={() => runLifecycle("start")} disabled={!canStart}>{state.error !== null && state.phase === "stopped" ? "Retry start" : "Start"}</button><button type="button" title="Restarting reloads enabled, configured MCP servers for the conversation." onClick={() => runLifecycle("restart")} disabled={!canRestart}>Restart</button><button type="button" onClick={() => runLifecycle("shutdown")} disabled={!canShutdown}>Shut down</button></div>
        </section>
      </aside>

      <main id="main-workspace" className="main-workspace" tabIndex={-1}>
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
            <DocumentEditor value={documentValue} onChange={updateDocument} annotationControls={annotationControls} onAddReference={renderConversation && idle && !chooserOpen ? addDocumentReference : undefined} onSave={() => void saveDocument()} saveDisabled={documentBusy} />
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
            permissionMode={state.session?.bashPermissionMode ?? "ask"}
            onPreview={previewExtensions}
            onDecision={decideBinding}
            onApply={applyExtensions}
            onRestart={restartForExtensions}
          />}
          {selectionPreview === null && (state.error !== null || workspaceIssue !== null || conversation.failure !== null) && <section className="notice notice-error" aria-labelledby="recovery-title"><div className="notice-icon" aria-hidden="true">!</div><div><p className="section-kicker">{conversation.failure === null ? (workspaceIssue ?? state.error)?.code : failureLifecycleLabel(conversation.failure)}</p><h3 id="recovery-title">{state.phase === "crashed" ? "The local backend stopped unexpectedly" : conversation.failure?.cancelled ? "Turn stopped" : "Action required"}</h3><p>{conversation.failure?.message ?? (workspaceIssue ?? state.error)?.message}</p><div className="action-row">{conversation.failure?.retryable && (conversation.failure.draftPreserved || conversation.submittedTurn?.turnId === conversation.failure.turnId) && <button type="button" onClick={() => void sendTurn()} disabled={interaction.turnActive || workspaceBusy !== null || !retryControlsMatch}>Retry saved turn</button>}{state.snapshot?.lifecycle === "ready" && state.diagnostics === null && <button type="button" onClick={() => loadDiagnostics(true)} disabled={!idle}>Retry runtime check</button>}{(state.phase === "crashed" || state.phase === "degraded") && <button type="button" onClick={() => runLifecycle("restart")} disabled={!canRestart}>Restart backend</button>}{canStart && <button type="button" onClick={() => runLifecycle("start")}>Retry start</button>}</div></div></section>}
          {conversation.stopRequest?.status === "failed" && <section className="notice notice-error" role="alert">
            <div><h3>The turn could not finish stopping</h3><p>{conversation.stopRequest.error}</p>
              {conversation.activeTurn === null && pendingUserText !== null && <details><summary>Your message</summary><SafeContent content={pendingUserText} /></details>}
              <div className="action-row"><button type="button" onClick={stopTurn}>Retry Stop</button>
                {conversation.activeTurn === null && <button type="button" disabled={!canRestart} onClick={() => runLifecycle("restart")}>Restart backend</button>}
              </div>
            </div>
          </section>}
          {selectionPreview === null && registrationIssue !== null && <section className="notice registration-notice" aria-live="polite"><div className="notice-icon" aria-hidden="true">!</div><div><p className="section-kicker">CATALOG REGISTRATION PENDING</p><p>{registrationIssue}</p><button type="button" onClick={retryRegistration} disabled={interaction.turnActive || workspaceBusy !== null}>Retry registration without resending</button></div></section>}
          {(state.phase === "starting" || (state.snapshot === null && state.error === null && !state.browserPreview)) && <section className="empty-state" role="status"><h3>Preparing your research workspace</h3><p>Connecting to the local backend. Choose a project when it is ready.</p></section>}
          {state.phase === "stopped" && state.snapshot !== null && state.error === null && <section className="empty-state" aria-labelledby="stopped-title"><div className="hero-mark" aria-hidden="true">R</div><h3 id="stopped-title">The local backend is stopped</h3><button className="primary-button" type="button" onClick={() => runLifecycle("start")} disabled={!canStart}>Start local backend</button>{shutdownMessage !== null && <p className="shutdown-summary">{shutdownMessage}</p>}</section>}
          {(state.phase === "starting" || state.phase === "restarting" || state.phase === "shutting-down") && <section className="empty-state" aria-labelledby="transition-title"><div className="spinner" aria-hidden="true" /><p className="section-kicker">DESKTOP BACKEND</p><h3 id="transition-title">{phaseLabels[state.phase]}</h3><p>Please keep this window open while the local process changes state.</p></section>}
          {state.phase === "busy" && <section className="empty-state" aria-labelledby="busy-title"><div className="spinner" aria-hidden="true" /><p className="section-kicker">LOCAL REQUEST</p><h3 id="busy-title">{state.activeAction === "session" ? "Creating your session" : "Checking the local runtime"}</h3><p>This check stays on your device and does not call a model provider.</p></section>}
          {selectionPreview === null && activeProjectId !== null && state.phase === "backend-ready" && state.diagnostics !== null && <section className="setup-card" aria-labelledby="backend-ready-title"><div className="success-mark" aria-hidden="true">✓</div><div><p className="section-kicker">BACKEND READY</p><h3 id="backend-ready-title">Create a conversation to begin</h3><p>The protocol and local runtime are ready. Creating or selecting a conversation starts enabled, configured MCP servers. No model request has been sent.</p><div className="action-row"><button className="primary-button" type="button" onClick={createSession} disabled={!canCreateSession}>Create local conversation</button><button type="button" onClick={() => runLifecycle("shutdown")} disabled={!canShutdown}>Shut down</button></div><RuntimeDetails diagnostics={state.diagnostics} /></div></section>}

          {selectionPreview !== null && <section className="conversation-surface" aria-label="Saved conversation preview" aria-busy="true">
            <p className="control-state" role="status">Preparing this conversation… You can read the saved messages while it loads.</p>
            <div className="transcript" ref={transcriptRef} aria-label="Conversation transcript" aria-live="polite">
              <ConversationTurns turns={visibleTurns} projectId={visibleTranscript?.projectId ?? activeProjectId ?? undefined} annotationControls={annotationControls} />
              <div ref={transcriptEndRef} />
            </div>
          </section>}
          {selectionPreview === null && activeSession !== null && <section className="conversation-surface" aria-label="Conversation workspace">
            <div className="transcript" ref={transcriptRef} aria-label="Conversation transcript" aria-live="polite">
              {transcript?.hasOlder && <button className="load-older" type="button" onClick={loadOlder} disabled={workspaceBusy !== null || interaction.turnActive}>Load older turns</button>}
              {transcript?.issue !== null && transcript?.issue !== undefined && <p className="transcript-issue">{transcript.issue}</p>}
              {visibleTurns.length === 0 && <div className="conversation-empty"><div className="hero-mark" aria-hidden="true">R</div><h3>What would you like to research?</h3><p>Enter sends. Shift+Enter adds a new line.</p></div>}
              <ConversationTurns turns={visibleTurns} projectId={visibleTranscript?.projectId ?? activeProjectId ?? undefined} annotationControls={annotationControls} />
              <div ref={transcriptEndRef} />
            </div>
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
              thinkingMode={activeSession.thinkingMode} permissionMode={activeSession.bashPermissionMode}
              turnActive={interaction.turnActive} stopping={stopping} onStop={stopTurn}
              controlsDisabled={interaction.controlDisabled || documentBusy || pendingApproval !== null || workspaceBusy !== null}
              onThinkingChange={(mode) => void updateThinkingMode(mode)}
              onPermissionChange={(mode) => void updateBashPermissionMode(mode)}
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
            <details className="session-meta"><summary>Session details · {activeSession.turnCount} turns</summary><p>Session {activeSession.sessionId} · {selectedRegistered ? "cataloged" : "transient"} · Citation output {state.diagnostics?.citationOutputPath ?? "unavailable"}</p></details>
          </section>}
          {(state.phase === "degraded" || state.phase === "crashed") && state.diagnostics !== null && <RuntimeDetails diagnostics={state.diagnostics} />}
        </div>
        </div>
      </main>
      {chooserOpen && state.snapshot?.lifecycle === "ready" && state.diagnostics !== null && <div className="approval-backdrop">
        <section className="approval-dialog" role="dialog" aria-modal="true" aria-labelledby="project-chooser-title"
          onKeyDown={(event) => {
            if (event.key === "Escape" && workspaceBusy === null) { event.preventDefault(); setChooserOpen(false); }
            if (event.key !== "Tab") return;
            const controls = Array.from(event.currentTarget.querySelectorAll<HTMLElement>("input:not(:disabled), button:not(:disabled), select:not(:disabled)"));
            const first = controls[0], last = controls.at(-1);
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
          }}>
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
        </section>
      </div>}
      {chatSelection !== null && renderConversation && idle && !chooserOpen && <button type="button" className="chat-reference-action"
        style={{ position: "fixed", top: chatSelection.top, left: chatSelection.left }}
        onPointerDown={(event) => event.preventDefault()} onClick={() => void addChatReference()}>Comment on selection</button>}
      {pendingApproval !== null && <ApprovalDialog
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
