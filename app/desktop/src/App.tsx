import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  type KeyboardEvent,
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
  conversationReducer,
  initialConversationState,
  latestRetryableTranscriptTurn,
  mergeConversationTurns,
  nextTurnSubmission,
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
  ExtensionApplyDto,
  ExtensionPreviewDto,
  JsonObject,
  ProjectListDto,
  ProjectSummaryDto,
  RegistrationRetryDto,
  RuntimeDiagnosticsDto,
  SessionCreatedDto,
  SessionListDto,
  SessionSelectedDto,
  SessionSummaryDto,
  SessionTranscriptDto,
  TranscriptTurnDto,
  TurnCompletedDto,
} from "./protocol.ts";
import { SafeContent } from "./SafeContent.tsx";
import {
  ApprovalDialog,
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
  type ExtensionBindingDecision,
  type ExtensionFlow,
  type PendingApproval,
} from "./trust.tsx";

const backendClient = createBackendClient({
  invoke: <T,>(command: string, args?: Record<string, unknown>) => invoke<T>(command, args),
});

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

export function shouldSubmitComposerKey(
  key: string,
  shiftKey: boolean,
  isComposing: boolean,
): boolean {
  return key === "Enter" && !shiftKey && !isComposing;
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
): Promise<SessionTranscriptDto> {
  const data = await backendClient.request("session.transcript", {
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

export function RestoredTurn({ turn }: { turn: TranscriptTurnDto }) {
  const displayOnly = turn.kind === "display-only";
  return (
    <article className="turn-group">
      <div className="message user-message">
        <p className="message-label">
          You · restored turn {turn.turnNumber}{displayOnly ? " · display-only" : ""}
        </p>
        <SafeContent content={turn.userText} />
      </div>
      {turn.toolActivities.map((activity, index) => (
        <section
          className="tool-activity"
          aria-label={`Tool activity ${activity.name}`}
          key={`${activity.callId ?? "legacy"}-${activity.name}-${index}`}
        >
          <div className="message tool-message">
            <p className="message-label">
              Tool activity · {activity.name} · {activity.status}
              {activity.promptEligible ? " · restored context" : " · display only"}
            </p>
            <SafeContent content={activity.arguments} />
          </div>
          <div className="message tool-result-message">
            <p className="message-label">Tool result · {activity.name}</p>
            <SafeContent content={activity.result} />
          </div>
        </section>
      ))}
      {turn.state === "completed" && turn.assistantText !== null ? (
        <div className={`message ${displayOnly ? "system-message" : "assistant-message"}`}>
          <p className="message-label">
            {displayOnly ? "Local command output · restored · display-only" : "Assistant · restored"}
          </p>
          <SafeContent content={turn.assistantText} />
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
}

export function ConversationTurns({ turns }: { turns: readonly VisibleConversationTurn[] }) {
  return turns.map((item) => {
    if (item.source === "restored") {
      return <RestoredTurn turn={item.turn} key={item.key} />;
    }
    if (item.source === "live") {
      return <article className="turn-group" key={item.key}><div className="message user-message"><p className="message-label">You</p><SafeContent content={item.turn.userText} /></div><div className={`message ${item.turn.responseKind === "command" ? "system-message" : "assistant-message"}`}><p className="message-label">{item.turn.responseKind === "command" ? "Local command output" : "Assistant"} · complete</p><SafeContent content={item.turn.assistantText} /></div></article>;
    }
    return <article className="turn-group pending-turn" key={item.key}><div className="message user-message"><p className="message-label">You · {item.retrying ? "retrying" : "pending"}</p><SafeContent content={item.turn.userText} /></div><div className="message assistant-message"><p className="message-label">Assistant · working</p><div className="inline-spinner" aria-label="Waiting for answer" /></div>{item.turn.activity.length > 0 && <ul className="activity-list">{item.turn.activity.map((activity, index) => <li key={`${activity.kind}-${index}`}><strong>{activity.kind === "stage" ? "Stage" : "Tool"}:</strong> {activity.label}{activity.status === null ? "" : ` · ${activity.status}`}</li>)}</ul>}</article>;
  });
}

export default function App() {
  const [state, dispatch] = useReducer(backendReducer, initialBackendState);
  const [conversation, conversationDispatch] = useReducer(conversationReducer, initialConversationState);
  const [catalog, setCatalog] = useState<ProjectListDto | null>(null);
  const [sessionLists, setSessionLists] = useState<Record<string, SessionListDto>>({});
  const [catalogGeneration, setCatalogGeneration] = useState<number | null>(null);
  const [workspaceBusy, setWorkspaceBusy] = useState<string | null>(null);
  const [workspaceIssue, setWorkspaceIssue] = useState<SafeUiError | null>(null);
  const [transcript, setTranscript] = useState<TranscriptView | null>(null);
  const [liveTurns, setLiveTurns] = useState<LiveTurn[]>([]);
  const [pendingUserText, setPendingUserText] = useState<string | null>(null);
  const [registrationIssue, setRegistrationIssue] = useState<string | null>(null);
  const [extensionFlow, setExtensionFlow] = useState<ExtensionFlow | null>(null);
  const [pendingApproval, setPendingApproval] = useState<PendingApproval | null>(null);
  const [approvalResolving, setApprovalResolving] = useState(false);
  const inFlight = useRef(false);
  const catalogLoading = useRef<number | null>(null);
  const diagnosticsAttempt = useRef<number | null>(null);
  const generationRef = useRef(0);
  const conversationRef = useRef(conversation);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const transcriptRef = useRef<HTMLDivElement>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const workspaceOperation = useRef<symbol | null>(null);
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

  const beginWorkspaceOperation = useCallback((label: string): symbol | null => {
    if (workspaceOperation.current !== null || inFlight.current) return null;
    const token = Symbol(label);
    workspaceOperation.current = token;
    setWorkspaceBusy(label);
    setWorkspaceIssue(null);
    return token;
  }, []);

  const finishWorkspaceOperation = useCallback((token: symbol) => {
    if (workspaceOperation.current !== token) return;
    workspaceOperation.current = null;
    setWorkspaceBusy(null);
  }, []);

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
              const generationChanged = generationRef.current !== event.snapshot.generation;
              if (generationChanged || event.snapshot.lifecycle !== "ready") {
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
            if (active === null) return;
            const generation = generationRef.current;
            if (message.event === "approval.required") {
              const accepted = acceptApprovalEvent(
                generation,
                message.requestId,
                active.requestId,
                message.data as unknown as ApprovalRequiredDto,
                Date.now(),
              );
              if (accepted !== null) {
                setPendingApproval((current) => {
                  if (current !== null) return current;
                  pendingApprovalRef.current = accepted;
                  return accepted;
                });
              }
            } else if (message.event === "stage.changed" && typeof message.data.stage === "string") {
              applyConversation({
                type: "activity-received",
                generation,
                requestId: message.requestId,
                sessionId: active.sessionId,
                activity: { kind: "stage", label: message.data.stage, status: null },
              });
            } else if (message.event.startsWith("tool.") && typeof message.data.name === "string" && typeof message.data.status === "string") {
              applyConversation({
                type: "activity-received",
                generation,
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
        const snapshot = await backendClient.snapshot();
        if (!disposed) {
          const generationChanged = generationRef.current !== snapshot.generation;
          if (generationChanged || snapshot.lifecycle !== "ready") {
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
        }
      } catch (error) {
        if (!disposed) dispatch({ type: "action-failed", error: workspaceError(error) });
      }
    })();
    return () => { disposed = true; removeListener?.(); };
  }, [applyConversation]);

  const runExclusive = useCallback(async (action: BackendActionName, operation: () => Promise<void>) => {
    if (inFlight.current) return;
    inFlight.current = true;
    dispatch({ type: "action-started", action });
    try { await operation(); }
    catch (error) { dispatch({ type: "action-failed", error: workspaceError(error) }); }
    finally { inFlight.current = false; }
  }, []);

  const runLifecycle = useCallback((action: "start" | "restart" | "shutdown") => {
    if (workspaceOperation.current !== null) return;
    if (action === "restart") {
      setExtensionFlow((current) => current === null ? null : markExtensionRestarting(current));
    }
    const operation = action === "start" ? backendClient.start : action === "restart" ? backendClient.restart : backendClient.shutdown;
    void runExclusive(action, async () => {
      const snapshot = await operation();
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
    void runExclusive("diagnostics", async () => {
      const data = await backendClient.request("runtime.diagnostics", {});
      dispatch({ type: "diagnostics-succeeded", diagnostics: toBoundedDiagnostics(data as unknown as RuntimeDiagnosticsDto) });
    });
  }, [runExclusive, state.snapshot?.generation]);

  useEffect(() => {
    if (state.phase === "backend-ready" && state.snapshot?.lifecycle === "ready" && state.diagnostics === null && state.activeAction === null) loadDiagnostics(false);
  }, [loadDiagnostics, state.activeAction, state.diagnostics, state.phase, state.snapshot?.lifecycle]);

  const loadCatalog = useCallback(async (generation: number) => {
    if (catalogLoading.current === generation) return;
    catalogLoading.current = generation;
    setWorkspaceIssue(null);
    try {
      const projectData = await backendClient.request("project.list", {});
      const nextCatalog = projectData as unknown as ProjectListDto;
      const entries = await Promise.all(nextCatalog.projects.map(async (project) => {
        const data = await backendClient.request("session.list", { projectId: project.projectId, offset: 0, limit: 50 });
        return [project.projectId, data as unknown as SessionListDto] as const;
      }));
      if (generationRef.current !== generation) return;
      setCatalog(nextCatalog);
      setSessionLists(Object.fromEntries(entries));
      setCatalogGeneration(generation);
    } catch (error) {
      if (generationRef.current === generation) {
        setCatalogGeneration(generation);
        setWorkspaceIssue(workspaceError(error));
      }
    } finally {
      if (catalogLoading.current === generation) catalogLoading.current = null;
    }
  }, []);

  const loadMoreSessions = useCallback((projectId: string) => {
    const current = sessionLists[projectId];
    if (current === undefined || !current.hasMore) return;
    const operation = beginWorkspaceOperation("Loading more conversations");
    if (operation === null) return;
    const generation = generationRef.current;
    const offset = current.items.length;
    void (async () => {
      try {
        const data = await backendClient.request("session.list", { projectId, offset, limit: 50 }) as unknown as SessionListDto;
        if (generationRef.current !== generation) return;
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
        if (generationRef.current === generation) setWorkspaceIssue(workspaceError(error));
      } finally {
        finishWorkspaceOperation(operation);
      }
    })();
  }, [beginWorkspaceOperation, finishWorkspaceOperation, sessionLists]);

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
    if (generation !== undefined && state.snapshot?.lifecycle === "ready" && state.diagnostics !== null && catalogGeneration !== generation && catalogLoading.current !== generation) void loadCatalog(generation);
  }, [catalogGeneration, loadCatalog, state.diagnostics, state.snapshot?.generation, state.snapshot?.lifecycle]);

  const focusComposer = useCallback(() => { requestAnimationFrame(() => composerRef.current?.focus()); }, []);

  const resolvePendingApproval = useCallback((approved: boolean) => {
    const approval = pendingApprovalRef.current;
    if (approval === null || approvalResolvingRef.current) return;
    approvalResolvingRef.current = true;
    setApprovalResolving(true);
    void backendClient.request("approval.resolve", {
      approvalId: approval.approvalId,
      parentRequestId: approval.parentRequestId,
      turnId: approval.turnId,
      approved,
    }).then((data) => {
      const result = data as unknown as ApprovalResolvedDto;
      if (result.approvalId !== approval.approvalId) {
        throw protocolMismatch("The backend resolved a different approval request.");
      }
    }).catch((error: unknown) => {
      if (generationRef.current === approval.generation) {
        setWorkspaceIssue(workspaceError(error));
      }
    }).finally(() => {
      if (pendingApprovalRef.current?.approvalId === approval.approvalId) {
        pendingApprovalRef.current = null;
        setPendingApproval(null);
      }
      approvalResolvingRef.current = false;
      setApprovalResolving(false);
    });
  }, []);

  useEffect(() => {
    if (pendingApproval === null) return;
    const remaining = Date.parse(pendingApproval.expiresAt) - Date.now();
    if (remaining <= 0) {
      resolvePendingApproval(false);
      return;
    }
    const timeout = window.setTimeout(() => resolvePendingApproval(false), remaining);
    return () => window.clearTimeout(timeout);
  }, [pendingApproval, resolvePendingApproval]);

  useEffect(() => {
    if (pendingApproval === null) return;
    const active = conversation.activeTurn;
    if (
      active === null ||
      active.requestId !== pendingApproval.parentRequestId
    ) {
      pendingApprovalRef.current = null;
      approvalResolvingRef.current = false;
      setPendingApproval(null);
      setApprovalResolving(false);
    }
  }, [conversation.activeTurn, pendingApproval]);

  const selectConversation = useCallback(async (projectId: string, session: SessionSummaryDto) => {
    if (conversationRef.current.activeTurn !== null) return;
    const operation = beginWorkspaceOperation("Selecting conversation");
    if (operation === null) return;
    const generation = generationRef.current;
    let selectionApplied = false;
    try {
      const data = await backendClient.request("session.select", { projectId, sessionId: session.sessionId });
      const selected = data as unknown as SessionSelectedDto;
      if (generationRef.current !== generation) return;
      if (selected.projectId !== projectId || selected.sessionId !== session.sessionId) {
        throw protocolMismatch("The backend returned a different conversation than requested.");
      }
      dispatch({ type: "session-created", session: selected });
      setExtensionFlow((current) => observeExtensionRevision(current, selected.extensionRevision));
      applyConversation({ type: "conversation-selected", generation: generationRef.current, projectId, sessionId: session.sessionId });
      selectionApplied = true;
      setRegistrationIssue(null);
      setLiveTurns([]);
      setPendingUserText(null);
      setTranscript({ projectId, sessionId: session.sessionId, status: "unavailable", issue: "Loading saved transcript…", items: [], offset: 0, total: selected.turnCount, hasOlder: false });
      const transcriptData = await fetchTranscriptPage(projectId, session.sessionId, transcriptTailOffset(selected.turnCount), TRANSCRIPT_PAGE_SIZE);
      if (generationRef.current !== generation) return;
      setTranscript(transcriptViewFrom(projectId, session.sessionId, transcriptData));
      const retryTarget = latestRetryableTranscriptTurn(transcriptData.items);
      if (retryTarget !== null) {
        applyConversation({
          type: "retry-target-restored",
          generation,
          projectId,
          sessionId: session.sessionId,
          turnId: retryTarget.turnId,
          userText: retryTarget.userText,
          state: retryTarget.state,
          message: retryTarget.failureMessage ?? "The saved turn did not complete.",
          retryable: true,
        });
      }
      requestAnimationFrame(() => transcriptEndRef.current?.scrollIntoView({ block: "end" }));
      focusComposer();
    } catch (error) {
      if (generationRef.current !== generation) return;
      const safe = workspaceError(error);
      if (selectionApplied) {
        setTranscript({ projectId, sessionId: session.sessionId, status: "unavailable", issue: safe.message, items: [], offset: 0, total: 0, hasOlder: false });
      }
      setWorkspaceIssue(safe);
      focusComposer();
    } finally { finishWorkspaceOperation(operation); }
  }, [applyConversation, beginWorkspaceOperation, finishWorkspaceOperation, focusComposer]);

  useEffect(() => {
    if (catalog === null || catalog.selectedProjectId === null || catalog.selectedSessionId === null || conversation.selected !== null || workspaceBusy !== null) return;
    const projectId = catalog.selectedProjectId;
    const sessionId = catalog.selectedSessionId;
    const summary = sessionLists[projectId]?.items.find((item) => item.sessionId === sessionId);
    if (summary !== undefined) void selectConversation(projectId, summary);
  }, [catalog, conversation.selected, selectConversation, sessionLists, workspaceBusy]);

  const activeProjectId = conversation.selected?.projectId ?? catalog?.selectedProjectId ?? catalog?.projects[0]?.projectId ?? null;

  const createSession = useCallback(() => {
    if (activeProjectId === null || conversationRef.current.activeTurn !== null) return;
    const operation = beginWorkspaceOperation("Creating conversation");
    if (operation === null) return;
    const generation = generationRef.current;
    void (async () => {
      try {
        const data = await backendClient.request("session.create", sessionCreateParams(activeProjectId));
        const session = data as unknown as SessionCreatedDto;
        if (generationRef.current !== generation) return;
        if (session.projectId !== undefined && session.projectId !== activeProjectId) {
          throw protocolMismatch("The backend created a conversation in a different project.");
        }
        dispatch({ type: "session-created", session });
        setExtensionFlow((current) => observeExtensionRevision(current, session.extensionRevision));
        applyConversation({ type: "conversation-selected", generation, projectId: activeProjectId, sessionId: session.sessionId });
        setTranscript({ projectId: activeProjectId, sessionId: session.sessionId, status: "ready", issue: null, items: [], offset: 0, total: 0, hasOlder: false });
        setLiveTurns([]);
        setPendingUserText(null);
        setRegistrationIssue(null);
        focusComposer();
      } catch (error) {
        if (generationRef.current !== generation) return;
        setWorkspaceIssue(workspaceError(error));
        focusComposer();
      } finally { finishWorkspaceOperation(operation); }
    })();
  }, [activeProjectId, applyConversation, beginWorkspaceOperation, finishWorkspaceOperation, focusComposer]);

  const loadOlder = useCallback(() => {
    const current = transcript;
    if (current === null || current.offset <= 0) return;
    const operation = beginWorkspaceOperation("Loading older turns");
    if (operation === null) return;
    const generation = generationRef.current;
    const container = transcriptRef.current;
    const previousHeight = container?.scrollHeight ?? 0;
    const previousTop = container?.scrollTop ?? 0;
    const limit = Math.min(TRANSCRIPT_PAGE_SIZE, current.offset);
    const offset = current.offset - limit;
    void (async () => {
      try {
        const data = await fetchTranscriptPage(current.projectId, current.sessionId, offset, limit, "The backend returned older turns for a different conversation.");
        if (generationRef.current !== generation) return;
        setTranscript((value) => value === null || value.projectId !== current.projectId || value.sessionId !== current.sessionId ? value : { ...value, status: data.status, issue: data.issue, items: mergeTranscriptItems(data.items, value.items), offset: data.offset, total: data.total, hasOlder: data.status === "ready" && data.offset > 0 });
        requestAnimationFrame(() => { if (container !== null) container.scrollTop = previousTop + container.scrollHeight - previousHeight; });
      } catch (error) {
        if (generationRef.current === generation) setWorkspaceIssue(workspaceError(error));
      }
      finally { finishWorkspaceOperation(operation); }
    })();
  }, [beginWorkspaceOperation, finishWorkspaceOperation, transcript]);

  const sendTurn = useCallback(() => {
    const selected = conversationRef.current.selected;
    const draft = conversationRef.current.draft;
    if (selected === null || draft.trim().length === 0 || conversationRef.current.activeTurn !== null || workspaceOperation.current !== null || inFlight.current) return;
    let tracked;
    const submission = nextTurnSubmission(conversationRef.current, newLogicalTurnId);
    const turnId = submission.turnId;
    try {
      tracked = backendClient.requestTracked("session.turn", {
        text: draft,
        turnId,
        retry: submission.retry,
      });
    }
    catch (error) { setWorkspaceIssue(workspaceError(error)); focusComposer(); return; }
    const generation = generationRef.current;
    setPendingUserText(draft);
    setWorkspaceIssue(null);
    applyConversation({ type: "turn-started", generation, requestId: tracked.requestId, turnId, projectId: selected.projectId, sessionId: selected.sessionId });
    void tracked.result.then(async (data) => {
      const result = data as unknown as TurnCompletedDto;
      const next = applyConversation({ type: "turn-succeeded", generation, requestId: tracked.requestId, projectId: selected.projectId, result });
      const answer = next.latestAnswer;
      if (answer === null || answer.requestId !== tracked.requestId) {
        const active = next.activeTurn;
        if (active === null || active.requestId !== tracked.requestId) return;
        const mismatch = protocolMismatch("The backend returned a mismatched conversation result.").uiError;
        const failed = applyConversation({ type: "turn-failed", generation, requestId: tracked.requestId, projectId: selected.projectId, sessionId: selected.sessionId, message: mismatch.message, retryable: mismatch.retryable });
        if (failed.failure?.requestId === tracked.requestId) {
          setPendingUserText(null);
          setWorkspaceIssue(mismatch);
          focusComposer();
        }
        return;
      }
      setLiveTurns((turns) => upsertLiveTurn(turns, {
        sessionId: answer.sessionId,
        turnId: answer.turnId,
        turnNumber: answer.turnNumber,
        userText: draft,
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
        await loadCatalog(generation);
      }
      if (generationRef.current !== generation) return;
      requestAnimationFrame(() => transcriptEndRef.current?.scrollIntoView({ block: "end" }));
      focusComposer();
    }).catch((error: unknown) => {
      const safe = workspaceError(error);
      const next = applyConversation({
        type: "turn-failed",
        generation,
        requestId: tracked.requestId,
        projectId: selected.projectId,
        sessionId: selected.sessionId,
        message: safe.message,
        retryable: safe.retryable,
        turnLifecycle: safe.turnLifecycle ?? null,
      });
      if (next.failure?.requestId !== tracked.requestId) return;
      setPendingUserText(null);
      pendingApprovalRef.current = null;
      approvalResolvingRef.current = false;
      setPendingApproval(null);
      setApprovalResolving(false);
      setWorkspaceIssue(safe);
      focusComposer();
      if (!isPersistedTurnFailure(next.failure)) return;
      const operation = beginWorkspaceOperation("Refreshing saved conversation");
      if (operation === null) return;
      // beginWorkspaceOperation clears the banner for user gestures; this refresh is not one.
      setWorkspaceIssue(safe);
      const selectionIsCurrent = () => (
        generationRef.current === generation && sameSelection(conversationRef.current.selected, selected)
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
          dispatch({
            type: "session-created",
            session: { ...currentSession, registered: true, turnCount: data.total },
          });
          setTranscript(transcriptViewFrom(selected.projectId, selected.sessionId, data));
          setLiveTurns([]);
          setRegistrationIssue(null);
          requestAnimationFrame(() => transcriptEndRef.current?.scrollIntoView({ block: "end" }));
        } catch (reconciliationError: unknown) {
          if (!selectionIsCurrent()) return;
          const issue = workspaceError(reconciliationError);
          setWorkspaceIssue(safe);
          setRegistrationIssue(`The prompt is saved, but the conversation state could not be refreshed. ${issue.message}`);
        } finally {
          finishWorkspaceOperation(operation);
        }
      })();
    });
  }, [applyConversation, beginWorkspaceOperation, finishWorkspaceOperation, focusComposer, loadCatalog, state.session]);

  const previewExtensions = useCallback(() => {
    const flow = extensionFlow;
    if (flow === null || (flow.phase !== "ready" && flow.phase !== "error")) return;
    const operation = beginWorkspaceOperation("Previewing extensions");
    if (operation === null) return;
    const generation = generationRef.current;
    setExtensionFlow((current) => current?.triggerTurnId === flow.triggerTurnId ? beginExtensionPreview(current) : current);
    void backendClient.request("extensions.preview", {}).then((data) => {
      if (generationRef.current !== generation) return;
      const preview = data as unknown as ExtensionPreviewDto;
      setExtensionFlow((current) => current?.triggerTurnId === flow.triggerTurnId ? receiveExtensionPreview(current, preview) : current);
    }).catch((error: unknown) => {
      if (generationRef.current !== generation) return;
      const safe = workspaceError(error);
      setExtensionFlow((current) => current?.triggerTurnId === flow.triggerTurnId ? failExtensionFlow(current, safe.message) : current);
    }).finally(() => finishWorkspaceOperation(operation));
  }, [beginWorkspaceOperation, extensionFlow, finishWorkspaceOperation]);

  const decideBinding = useCallback((
    bindingHash: string,
    decision: Exclude<ExtensionBindingDecision, null>,
  ) => {
    setExtensionFlow((current) => current === null ? null : decideExtensionBinding(current, bindingHash, decision));
  }, []);

  const applyExtensions = useCallback(() => {
    const flow = extensionFlow;
    if (flow === null) return;
    const submitting = flow.phase === "error" && flow.applyRequest !== null
      ? beginExtensionApplyRecovery(flow)
      : beginExtensionApply(flow, newLogicalTurnId());
    const request = extensionApplyRequest(submitting);
    if (request === null) return;
    const operation = beginWorkspaceOperation("Applying extensions");
    if (operation === null) return;
    const generation = generationRef.current;
    setExtensionFlow((current) => current?.triggerTurnId === flow.triggerTurnId ? submitting : current);
    void backendClient.request("extensions.apply", request).then((data) => {
      if (generationRef.current !== generation) return;
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
      requestAnimationFrame(() => transcriptEndRef.current?.scrollIntoView({ block: "end" }));
    }).catch((error: unknown) => {
      if (generationRef.current !== generation) return;
      const safe = workspaceError(error);
      setExtensionFlow((current) => current?.triggerTurnId === flow.triggerTurnId
        ? failExtensionApply(current, safe.message, safe.turnLifecycle)
        : current);
    }).finally(() => finishWorkspaceOperation(operation));
  }, [beginWorkspaceOperation, extensionFlow, finishWorkspaceOperation, liveTurns, state.session, transcript]);

  const restartForExtensions = useCallback(() => {
    if (extensionFlow?.phase !== "applied" || extensionFlow.report?.restartRequired !== true) return;
    runLifecycle("restart");
  }, [extensionFlow, runLifecycle]);

  const retryRegistration = useCallback(() => {
    const selected = conversation.selected;
    if (selected === null || conversation.activeTurn !== null) return;
    const operation = beginWorkspaceOperation("Retrying registration");
    if (operation === null) return;
    const generation = generationRef.current;
    void backendClient.request("session.retry_registration", selected as unknown as JsonObject).then(async (data) => {
      const result = data as unknown as RegistrationRetryDto;
      if (generationRef.current !== generation) return;
      if (result.projectId !== selected.projectId || result.sessionId !== selected.sessionId) {
        throw protocolMismatch("The backend returned registration state for a different conversation.");
      }
      if (result.status === "registered") {
        setRegistrationIssue(null);
        if (state.session !== null) dispatch({ type: "session-created", session: { ...state.session, registered: true } });
        await loadCatalog(generationRef.current);
      } else setRegistrationIssue(result.issue ?? "Catalog registration is still pending.");
    }).catch((error: unknown) => {
      if (generationRef.current === generation) setWorkspaceIssue(workspaceError(error));
    }).finally(() => {
      finishWorkspaceOperation(operation);
      if (generationRef.current === generation) focusComposer();
    });
  }, [beginWorkspaceOperation, conversation.activeTurn, conversation.selected, finishWorkspaceOperation, focusComposer, loadCatalog, state.session]);

  const updateThinkingMode = useCallback(async (
    mode: "normal" | "extended",
  ) => {
    const selected = conversationRef.current.selected;
    if (selected === null || conversationRef.current.activeTurn !== null) return;
    const operation = beginWorkspaceOperation("Updating session controls");
    if (operation === null) return;
    const generation = generationRef.current;
    try {
      const data = await backendClient.request("session.set_thinking", { mode });
      if (generationRef.current !== generation) return;
      if (data.sessionId !== selected.sessionId) {
        throw protocolMismatch("The backend returned controls for a different conversation.");
      }
      dispatch({
        type: "session-created",
        session: state.session === null
          ? data as unknown as SessionCreatedDto
          : { ...state.session, ...data as unknown as SessionCreatedDto },
      });
      focusComposer();
    } catch (error) {
      if (generationRef.current === generation) {
        setWorkspaceIssue(workspaceError(error));
        focusComposer();
      }
    }
    finally { finishWorkspaceOperation(operation); }
  }, [beginWorkspaceOperation, finishWorkspaceOperation, focusComposer, state.session]);

  const onComposerKeyDown = useCallback((event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (shouldSubmitComposerKey(event.key, event.shiftKey, event.nativeEvent.isComposing)) {
      event.preventDefault();
      sendTurn();
    }
  }, [sendTurn]);

  useEffect(() => { if (workspaceIssue !== null) focusComposer(); }, [focusComposer, workspaceIssue]);
  useEffect(() => {
    if (pendingUserText !== null) transcriptEndRef.current?.scrollIntoView({ block: "end" });
  }, [liveTurns.length, pendingUserText]);

  const selectedRegistered = state.session?.registered === true;
  const interaction = conversationInteractionState(conversation);
  const idle = state.activeAction === null && !interaction.turnActive && workspaceBusy === null;
  const canStart = !state.browserPreview && idle && (state.snapshot === null || state.snapshot.lifecycle === "stopped");
  const canRestart = !state.browserPreview && idle && (state.phase === "crashed" || state.phase === "degraded" || state.snapshot?.childRunning === true);
  const canShutdown = !state.browserPreview && idle && state.snapshot?.childRunning === true;
  const canCreateSession = !state.browserPreview && idle && workspaceBusy === null && state.snapshot?.lifecycle === "ready" && state.diagnostics !== null && activeProjectId !== null;
  const shutdownMessage = shutdownSummary(state.snapshot);
  const selectedSummary = useMemo(() => {
    const selected = conversation.selected;
    if (selected === null) return null;
    return sessionLists[selected.projectId]?.items.find((item) => item.sessionId === selected.sessionId) ?? null;
  }, [conversation.selected, sessionLists]);
  const visibleTurns = useMemo(() => mergeConversationTurns(
    transcript === null
      ? []
      : transcript.items.map((turn) => ({ sessionId: transcript.sessionId, turn })),
    liveTurns,
    pendingUserText === null || conversation.activeTurn === null
      ? null
      : {
          sessionId: conversation.activeTurn.sessionId,
          turnId: conversation.activeTurn.turnId,
          userText: pendingUserText,
          activity: conversation.activeTurn.activity,
        },
  ), [conversation.activeTurn, liveTurns, pendingUserText, transcript]);
  const renderConversation = state.phase === "session-ready" && state.session !== null && conversation.selected !== null;
  const activeSession = renderConversation ? state.session : null;

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-workspace">Skip to main workspace</a>
      <aside className="sidebar" aria-label="Research Agent workspace">
        <div className="brand-lockup"><span className="brand-mark" aria-hidden="true">R</span><div><p className="eyebrow">LOCAL WORKSPACE</p><h1>Research Agent</h1></div></div>
        <button className="new-session-button" type="button" onClick={createSession} disabled={!canCreateSession || interaction.createDisabled}><span aria-hidden="true">＋</span> New conversation</button>
        <section className="sidebar-section project-browser" aria-labelledby="workspace-label">
          <h2 id="workspace-label">Projects</h2>
          {catalog === null && <p className="sidebar-note">{catalogGeneration === null ? "Loading local projects…" : "Projects unavailable"}</p>}
          {catalog?.issue !== null && catalog?.issue !== undefined && <p className="sidebar-note">{catalog.issue}</p>}
          {catalog?.projects.map((project: ProjectSummaryDto) => {
            const list = sessionLists[project.projectId];
            const rows = sidebarRowsForProject(project.projectId, list?.items ?? [], conversation.selected, selectedRegistered);
            return <div className="project-group" key={project.projectId}>
              <div className="project-heading"><strong>{project.name}</strong><small>{project.sessionCount} saved</small></div>
              {list?.status === "unavailable" && <p className="sidebar-note">{list.issue ?? "Conversations unavailable"}</p>}
              {rows.length === 0 && list?.status !== "unavailable" ? <p className="sidebar-note">No saved conversations</p> : <ul className="session-list">{rows.map((session) => {
                const isSelected = conversation.selected?.sessionId === session.sessionId && conversation.selected.projectId === project.projectId;
                return <li key={session.sessionId}><button type="button" className="session-link" aria-current={isSelected ? "page" : undefined} disabled={interaction.selectDisabled || workspaceBusy !== null || session.status !== "ready"} onClick={() => void selectConversation(project.projectId, session)}><span>{session.title}</span><small>{session.transient ? "Not saved yet" : `${session.turnCount} turns${session.status === "ready" ? "" : ` · ${session.status}`}`}</small></button></li>;
              })}</ul>}
              {list?.hasMore && <button className="load-more-sessions" type="button" onClick={() => loadMoreSessions(project.projectId)} disabled={interaction.selectDisabled || workspaceBusy !== null}>Load more conversations</button>}
            </div>;
          })}
        </section>
        <div className="sidebar-spacer" />
        <section className="backend-controls" aria-labelledby="backend-controls-title">
          <div className="sidebar-status" role="status" aria-live="polite"><span className={`status-dot status-${state.phase}`} aria-hidden="true" /><span><strong id="backend-controls-title">{phaseLabels[state.phase]}</strong><small>{state.snapshot === null ? "Desktop process not observed" : `Generation ${state.snapshot.generation} · ${state.snapshot.pendingRequests} pending`}</small></span></div>
          <div className="control-row"><button type="button" onClick={() => runLifecycle("start")} disabled={!canStart}>{state.error !== null && state.phase === "stopped" ? "Retry start" : "Start"}</button><button type="button" onClick={() => runLifecycle("restart")} disabled={!canRestart}>Restart</button><button type="button" onClick={() => runLifecycle("shutdown")} disabled={!canShutdown}>Shut down</button></div>
        </section>
      </aside>

      <main id="main-workspace" className="main-workspace" tabIndex={-1}>
        <header className="workspace-header"><div><p className="eyebrow">CURRENT CONVERSATION</p><h2>{selectedSummary?.title ?? (conversation.selected === null ? "Start a local research conversation" : "New conversation")}</h2></div><span className="header-status" role="status" aria-live="polite">{workspaceBusy ?? phaseLabels[state.phase]}</span></header>
        <div className={`workspace-body${renderConversation ? " conversation-workspace-body" : ""}`}>
          {extensionFlow !== null && <ExtensionPanel
            flow={extensionFlow}
            busy={workspaceBusy !== null || state.activeAction !== null || interaction.turnActive}
            canRestart={canRestart}
            onPreview={previewExtensions}
            onDecision={decideBinding}
            onApply={applyExtensions}
            onRestart={restartForExtensions}
          />}
          {(state.error !== null || workspaceIssue !== null || conversation.failure !== null) && <section className="notice notice-error" aria-labelledby="recovery-title"><div className="notice-icon" aria-hidden="true">!</div><div><p className="section-kicker">{conversation.failure === null ? (workspaceIssue ?? state.error)?.code : failureLifecycleLabel(conversation.failure)}</p><h3 id="recovery-title">{state.phase === "crashed" ? "The local backend stopped unexpectedly" : "Action required"}</h3><p>{conversation.failure?.message ?? (workspaceIssue ?? state.error)?.message}</p><div className="action-row">{conversation.failure?.retryable && conversation.failure.draftPreserved && <button type="button" onClick={sendTurn} disabled={interaction.turnActive}>Retry saved draft</button>}{state.snapshot?.lifecycle === "ready" && state.diagnostics === null && <button type="button" onClick={() => loadDiagnostics(true)} disabled={!idle}>Retry runtime check</button>}{(state.phase === "crashed" || state.phase === "degraded") && <button type="button" onClick={() => runLifecycle("restart")} disabled={!canRestart}>Restart backend</button>}{canStart && <button type="button" onClick={() => runLifecycle("start")}>Retry start</button>}</div></div></section>}
          {registrationIssue !== null && <section className="notice registration-notice" aria-live="polite"><div className="notice-icon" aria-hidden="true">!</div><div><p className="section-kicker">CATALOG REGISTRATION PENDING</p><p>{registrationIssue}</p><button type="button" onClick={retryRegistration} disabled={interaction.turnActive || workspaceBusy !== null}>Retry registration without resending</button></div></section>}
          {state.phase === "stopped" && state.error === null && <section className="empty-state" aria-labelledby="stopped-title"><div className="hero-mark" aria-hidden="true">R</div><p className="section-kicker">LOCAL · PRIVATE · ON THIS DEVICE</p><h3 id="stopped-title">Your research workspace is ready to connect</h3><p>Start the Linux backend, verify the local runtime, then create a conversation. No provider request is made by the runtime check.</p><button className="primary-button" type="button" onClick={() => runLifecycle("start")} disabled={!canStart}>Start local backend</button>{shutdownMessage !== null && <p className="shutdown-summary">{shutdownMessage}</p>}</section>}
          {(state.phase === "starting" || state.phase === "restarting" || state.phase === "shutting-down") && <section className="empty-state" aria-labelledby="transition-title"><div className="spinner" aria-hidden="true" /><p className="section-kicker">DESKTOP BACKEND</p><h3 id="transition-title">{phaseLabels[state.phase]}</h3><p>Please keep this window open while the local process changes state.</p></section>}
          {state.phase === "busy" && <section className="empty-state" aria-labelledby="busy-title"><div className="spinner" aria-hidden="true" /><p className="section-kicker">LOCAL REQUEST</p><h3 id="busy-title">{state.activeAction === "session" ? "Creating your session" : "Checking the local runtime"}</h3><p>This check stays on your device and does not call a model provider.</p></section>}
          {state.phase === "backend-ready" && state.diagnostics !== null && <section className="setup-card" aria-labelledby="backend-ready-title"><div className="success-mark" aria-hidden="true">✓</div><div><p className="section-kicker">BACKEND READY</p><h3 id="backend-ready-title">Create a conversation to begin</h3><p>The protocol and local runtime are ready. Saved projects are loaded locally; no provider request has been sent.</p><div className="action-row"><button className="primary-button" type="button" onClick={createSession} disabled={!canCreateSession}>Create local conversation</button><button type="button" onClick={() => runLifecycle("shutdown")} disabled={!canShutdown}>Shut down</button></div><RuntimeDetails diagnostics={state.diagnostics} /></div></section>}

          {activeSession !== null && <section className="conversation-surface" aria-label="Conversation workspace">
            <div className="session-controls" aria-label="Session controls">
              <label>Thinking<select value={activeSession.thinkingMode} disabled={interaction.controlDisabled || workspaceBusy !== null} onChange={(event) => void updateThinkingMode(event.target.value as "normal" | "extended")}><option value="normal">Normal</option><option value="extended">Extended</option></select></label>
              <p className="control-state">Skills run once with /&lt;skill-name&gt; &lt;prompt&gt;. Citation mode is currently CLI-only.</p>
            </div>
            <div className="transcript" ref={transcriptRef} aria-label="Conversation transcript" aria-live="polite">
              {transcript?.hasOlder && <button className="load-older" type="button" onClick={loadOlder} disabled={workspaceBusy !== null || interaction.turnActive}>Load older turns</button>}
              {transcript?.issue !== null && transcript?.issue !== undefined && <p className="transcript-issue">{transcript.issue}</p>}
              {visibleTurns.length === 0 && <div className="conversation-empty"><div className="hero-mark" aria-hidden="true">R</div><h3>What would you like to research?</h3><p>Enter sends. Shift+Enter adds a new line.</p></div>}
              <ConversationTurns turns={visibleTurns} />
              <div ref={transcriptEndRef} />
            </div>
            <form className="composer" onSubmit={(event) => { event.preventDefault(); sendTurn(); }}><label htmlFor="conversation-draft">Message</label><textarea id="conversation-draft" ref={composerRef} value={conversation.draft} onChange={(event) => applyConversation({ type: "draft-changed", draft: event.target.value })} onKeyDown={onComposerKeyDown} rows={4} placeholder="Ask about your research…" disabled={conversation.selected === null || interaction.turnActive} /><div className="composer-footer"><span>Enter to send · Shift+Enter for a new line</span><button className="primary-button" type="submit" disabled={interaction.sendDisabled || workspaceBusy !== null}>Send</button></div></form>
            <p className="session-meta">Session {activeSession.sessionId} · {activeSession.turnCount} turns · {selectedRegistered ? "cataloged" : "transient"} · Citation output {state.diagnostics?.citationOutputPath ?? "unavailable"}</p>
          </section>}
          {(state.phase === "degraded" || state.phase === "crashed") && state.diagnostics !== null && <RuntimeDetails diagnostics={state.diagnostics} />}
        </div>
      </main>
      {pendingApproval !== null && <ApprovalDialog
        approval={pendingApproval}
        resolving={approvalResolving}
        onResolve={resolvePendingApproval}
        returnFocus={focusComposer}
      />}
    </div>
  );
}
