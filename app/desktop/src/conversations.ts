import type {
  TranscriptTurnDto,
  Reference,
  SubmittedContext,
  TurnLifecycleDetailsDto,
} from "./protocol.ts";

export const MAX_ACTIVITY_ITEMS = 32;

export type AnswerStreamKind = "final_only";

export interface ConversationSelection {
  projectId: string;
  sessionId: string;
}

export interface ConversationActivity {
  kind: "stage" | "tool";
  label: string;
  status: string | null;
}

export interface ActiveConversationTurn extends ConversationSelection {
  backendGeneration: number;
  projectEpoch: number;
  requestId: string;
  turnId: string;
  activity: readonly ConversationActivity[];
}

export interface AuthoritativeTurnResult {
  sessionId: string;
  turnId: string;
  turnNumber: number;
  state: "completed";
  accepted: boolean;
  persisted: boolean;
  text: string;
  responseKind?: "answer" | "command";
  streamKind?: AnswerStreamKind;
  chunkCount?: number;
}

export interface FinalConversationAnswer extends ConversationSelection {
  requestId: string;
  turnId: string;
  turnNumber: number;
  text: string;
  responseKind: "answer" | "command";
  streamKind: AnswerStreamKind;
}

export interface LiveTurn {
  submittedContext?: SubmittedContext | null;
  sessionId: string;
  turnId: string;
  turnNumber: number;
  userText: string;
  assistantText: string;
  responseKind: "answer" | "command";
  streamKind: AnswerStreamKind;
}

export interface RestoredConversationTurn {
  sessionId: string;
  turn: TranscriptTurnDto;
}

export interface PendingConversationTurn {
  submittedContext?: SubmittedContext | null;
  sessionId: string;
  turnId: string;
  userText: string;
  activity: readonly ConversationActivity[];
}

export type VisibleConversationTurn =
  | {
      source: "restored";
      key: string;
      sessionId: string;
      turnId: string;
      turnNumber: number;
      turn: TranscriptTurnDto;
    }
  | {
      source: "live";
      key: string;
      sessionId: string;
      turnId: string;
      turnNumber: number;
      turn: LiveTurn;
    }
  | {
      source: "pending";
      key: string;
      sessionId: string;
      turnId: string;
      turnNumber: number;
      retrying: boolean;
      turn: PendingConversationTurn;
    };

export interface ConversationStop extends ConversationSelection {
  requestId: string;
  turnId: string;
  status: "requesting" | "confirmed" | "failed";
  error: string | null;
}

export interface ConversationFailure extends ConversationSelection {
  cancelled?: boolean;
  requestId: string | null;
  turnId: string;
  message: string;
  retryable: boolean;
  draftPreserved: boolean;
  turnLifecycle: TurnLifecycleDetailsDto | null;
}

export interface DraftAnnotation {
  referenceId: string;
  number: number;
  comment: string;
  expanded: boolean;
}

export interface SubmittedTurn extends ConversationSelection {
  turnId: string;
  text: string;
  accepted: boolean;
}

export interface ConversationState {
  backendGeneration: number;
  projectEpoch: number;
  selected: ConversationSelection | null;
  draft: string;
  draftReferences: Reference[];
  annotations: DraftAnnotation[];
  nextAnnotationNumber: number;
  submittedContext: SubmittedContext | null;
  submittedTurn: SubmittedTurn | null;
  activeTurn: ActiveConversationTurn | null;
  stopRequest: ConversationStop | null;
  latestAnswer: FinalConversationAnswer | null;
  failure: ConversationFailure | null;
}

export type ConversationAction = (
  | { type: "backend-generation-changed"; generation: number }
  | { type: "project-opened"; generation: number; preserveDraft?: boolean }
  | ({ type: "conversation-selected"; generation: number; preserveDraft?: boolean } & ConversationSelection)
  | { type: "draft-changed"; draft: string }
  | { type: "reference-added"; reference: Reference; generation?: number }
  | { type: "reference-removed"; referenceId: string; generation?: number }
  | { type: "annotation-changed"; referenceId: string; comment: string; generation: number }
  | { type: "annotation-toggled"; referenceId: string; expanded: boolean; generation: number }
  | { type: "new-turn-requested"; generation?: number }
  | { type: "stop-requested"; generation: number }
  | ({ type: "stop-succeeded"; generation: number; requestId: string; turnId: string } & ConversationSelection)
  | ({ type: "stop-failed"; generation: number; requestId: string; turnId: string; message: string } & ConversationSelection)
  | ({ type: "turn-started"; generation: number; requestId: string; turnId: string; text?: string; submittedContext?: SubmittedContext | null } & ConversationSelection)
  | ({ type: "turn-accepted"; generation: number; requestId: string; turnId: string } & ConversationSelection)
  | ({ type: "turn-acceptance-reconciled"; generation: number; turnId: string; state: TranscriptTurnDto["state"] } & ConversationSelection)
  | ({
      type: "activity-received";
      generation: number;
      requestId: string;
      sessionId: string;
      activity: ConversationActivity;
    })
  | ({
      type: "turn-succeeded";
      generation: number;
      requestId: string;
      projectId: string;
      result: AuthoritativeTurnResult;
    })
  | ({
      type: "turn-failed";
      cancelled?: boolean;
      generation: number;
      requestId: string;
      projectId: string;
      sessionId: string;
      message: string;
      retryable: boolean;
      turnLifecycle?: TurnLifecycleDetailsDto | null;
    })
  | ({
      type: "retry-target-restored";
      submittedContext?: SubmittedContext | null;
      generation: number;
      turnId: string;
      userText: string;
      state: "failed" | "interrupted";
      message: string;
      retryable: boolean;
    } & ConversationSelection)
  | { type: "failure-cleared" }
) & { projectEpoch?: number };

export interface WorkspaceOperationOwner {
  generation: number;
  projectEpoch: number;
  token: symbol;
}

export function ownsWorkspaceOperation(
  owner: WorkspaceOperationOwner,
  current: WorkspaceOperationOwner | null,
  generation: number,
  projectEpoch: number,
): boolean {
  return current !== null && owner.token === current.token &&
    owner.generation === generation && owner.generation === current.generation &&
    owner.projectEpoch === projectEpoch && owner.projectEpoch === current.projectEpoch;
}

export interface ConversationInteractionState {
  turnActive: boolean;
  sendDisabled: boolean;
  createDisabled: boolean;
  selectDisabled: boolean;
  controlDisabled: boolean;
}

export const initialConversationState: ConversationState = {
  backendGeneration: 0,
  projectEpoch: 0,
  selected: null,
  draft: "",
  draftReferences: [],
  annotations: [],
  nextAnnotationNumber: 1,
  submittedContext: null,
  submittedTurn: null,
  activeTurn: null,
  stopRequest: null,
  latestAnswer: null,
  failure: null,
};

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

function isNonNegativeSafeInteger(value: unknown): value is number {
  return Number.isSafeInteger(value) && Number(value) >= 0;
}

function isCanonicalTurnId(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /^[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{15}$/.test(value)
  );
}

function isValidSelection(value: ConversationSelection): boolean {
  return isNonEmptyString(value.projectId) && isNonEmptyString(value.sessionId);
}

export function sameSelection(
  left: ConversationSelection | null,
  right: ConversationSelection,
): boolean {
  return left !== null && left.projectId === right.projectId && left.sessionId === right.sessionId;
}

function logicalTurnKey(sessionId: string, turnId: string): string {
  return `${sessionId}:${turnId}`;
}

function compareCanonicalTurns(
  left: { sessionId: string; turnId: string; turnNumber: number },
  right: { sessionId: string; turnId: string; turnNumber: number },
): number {
  return (
    left.turnNumber - right.turnNumber ||
    left.sessionId.localeCompare(right.sessionId) ||
    left.turnId.localeCompare(right.turnId)
  );
}

export function upsertLiveTurn(
  current: readonly LiveTurn[],
  next: LiveTurn,
): LiveTurn[] {
  const byLogicalTurn = new Map<string, LiveTurn>();
  for (const turn of current) {
    byLogicalTurn.set(logicalTurnKey(turn.sessionId, turn.turnId), turn);
  }
  byLogicalTurn.set(logicalTurnKey(next.sessionId, next.turnId), next);
  return [...byLogicalTurn.values()].sort(compareCanonicalTurns);
}

export function mergeConversationTurns(
  restored: readonly RestoredConversationTurn[],
  live: readonly LiveTurn[],
  pending: PendingConversationTurn | null = null,
): VisibleConversationTurn[] {
  const byLogicalTurn = new Map<string, VisibleConversationTurn>();
  for (const item of restored) {
    const key = logicalTurnKey(item.sessionId, item.turn.turnId);
    byLogicalTurn.set(key, {
      source: "restored",
      key,
      sessionId: item.sessionId,
      turnId: item.turn.turnId,
      turnNumber: item.turn.turnNumber,
      turn: item.turn,
    });
  }
  for (const turn of live) {
    const key = logicalTurnKey(turn.sessionId, turn.turnId);
    byLogicalTurn.set(key, {
      source: "live",
      key,
      sessionId: turn.sessionId,
      turnId: turn.turnId,
      turnNumber: turn.turnNumber,
      turn,
    });
  }
  if (pending !== null) {
    const key = logicalTurnKey(pending.sessionId, pending.turnId);
    const existing = byLogicalTurn.get(key);
    let turnNumber = existing?.turnNumber;
    if (turnNumber === undefined) {
      let latest = 0;
      for (const item of byLogicalTurn.values()) {
        if (item.sessionId === pending.sessionId) latest = Math.max(latest, item.turnNumber);
      }
      turnNumber = latest + 1;
    }
    byLogicalTurn.set(key, {
      source: "pending",
      key,
      sessionId: pending.sessionId,
      turnId: pending.turnId,
      turnNumber,
      retrying: existing !== undefined,
      turn: pending,
    });
  }
  return [...byLogicalTurn.values()].sort(compareCanonicalTurns);
}

export function reconciledTurnCount(
  current: number,
  returnedTurnNumber: number,
): number {
  return Math.max(current, returnedTurnNumber);
}

function validTurnLifecycle(
  value: TurnLifecycleDetailsDto,
  turnId: string,
): boolean {
  if (value.turnId !== turnId) {
    return false;
  }
  if (value.state === null) {
    return value.accepted === false && value.persisted === false;
  }
  return (
    (value.state === "pending" ||
      value.state === "completed" ||
      value.state === "failed" ||
      value.state === "interrupted") &&
    value.accepted === true &&
    value.persisted === true
  );
}

function boundedActivity(activity: ConversationActivity): ConversationActivity | null {
  if (
    (activity.kind !== "stage" && activity.kind !== "tool") ||
    !isNonEmptyString(activity.label) ||
    (activity.status !== null && typeof activity.status !== "string")
  ) {
    return null;
  }
  return {
    kind: activity.kind,
    label: activity.label.slice(0, 160),
    status: activity.status === null ? null : activity.status.slice(0, 80),
  };
}

function receiveActivity(
  state: ConversationState,
  action: Extract<ConversationAction, { type: "activity-received" }>,
): ConversationState {
  const active = state.activeTurn;
  const activity = boundedActivity(action.activity);
  if (
    active === null ||
    activity === null ||
    action.generation !== state.backendGeneration ||
    action.generation !== active.backendGeneration ||
    action.requestId !== active.requestId ||
    action.sessionId !== active.sessionId
  ) {
    return state;
  }
  return {
    ...state,
    activeTurn: {
      ...active,
      activity: [...active.activity, activity].slice(-MAX_ACTIVITY_ITEMS),
    },
  };
}

function finalizeTurn(
  state: ConversationState,
  action: Extract<ConversationAction, { type: "turn-succeeded" }>,
): ConversationState {
  const active = state.activeTurn;
  const result = action.result;
  const responseKind = result.responseKind ?? "answer";
  const lifecycleIsValid =
    (responseKind === "answer" || responseKind === "command") &&
    Number.isSafeInteger(result.turnNumber) &&
    Number(result.turnNumber) >= 1 &&
    Number(result.turnNumber) <= 4_096 &&
    result.state === "completed" &&
    result.accepted === true &&
    result.persisted === true;
  if (
    active === null ||
    action.generation !== state.backendGeneration ||
    action.generation !== active.backendGeneration ||
    action.requestId !== active.requestId ||
    action.projectId !== active.projectId ||
    result.sessionId !== active.sessionId ||
    result.turnId !== active.turnId ||
    !lifecycleIsValid ||
    typeof result.text !== "string" ||
    (result.responseKind !== undefined &&
      result.responseKind !== "answer" &&
      result.responseKind !== "command") ||
    (result.streamKind !== undefined && result.streamKind !== "final_only") ||
    (result.chunkCount !== undefined && result.chunkCount !== 0)
  ) {
    return state;
  }

  const streamKind = result.streamKind ?? "final_only";
  return {
    ...state,
    draft: "",
    draftReferences: [],
    annotations: [],
    nextAnnotationNumber: 1,
    submittedTurn: null,
    activeTurn: null,
    stopRequest: state.stopRequest?.status === "confirmed" ? null : state.stopRequest,
    latestAnswer: {
      projectId: active.projectId,
      sessionId: active.sessionId,
      requestId: active.requestId,
      turnId: result.turnId,
      turnNumber: result.turnNumber,
      text: result.text,
      responseKind,
      streamKind,
    },
    failure: null,
  };
}

export function conversationReducer(
  state: ConversationState,
  action: ConversationAction,
): ConversationState {
  if (action.type !== "backend-generation-changed" && action.type !== "project-opened" &&
      action.type !== "draft-changed" && action.type !== "failure-cleared" &&
      (action.projectEpoch ?? 0) !== state.projectEpoch) return state;
  if (action.type === "backend-generation-changed") {
    if (!isNonNegativeSafeInteger(action.generation) || action.generation <= state.backendGeneration) {
      return state;
    }
    return {
      ...state,
      backendGeneration: action.generation,
      selected: null,
      activeTurn: null,
      stopRequest: null,
      latestAnswer: null,
      failure: null,
    };
  }
  if (action.type === "stop-requested") {
    if (action.generation !== state.backendGeneration ||
        (state.stopRequest !== null && state.stopRequest.status !== "failed")) return state;
    const target = state.stopRequest ?? state.activeTurn;
    if (target === null) return state;
    return { ...state, stopRequest: {
      projectId: target.projectId, sessionId: target.sessionId,
      requestId: target.requestId, turnId: target.turnId, status: "requesting", error: null,
    } };
  }
  if (action.type === "stop-succeeded" || action.type === "stop-failed") {
    const stop = state.stopRequest;
    if (stop === null || stop.status !== "requesting" || action.generation !== state.backendGeneration ||
        action.requestId !== stop.requestId || action.turnId !== stop.turnId || !sameSelection(stop, action)) return state;
    if (action.type === "stop-failed") {
      return { ...state, stopRequest: { ...stop, status: "failed", error: action.message } };
    }
    return { ...state, stopRequest: state.activeTurn === null ? null : { ...stop, status: "confirmed" } };
  }
  if (action.type === "project-opened") {
    const projectEpoch = action.projectEpoch ?? state.projectEpoch + 1;
    if (action.generation !== state.backendGeneration || state.activeTurn !== null || state.stopRequest !== null || projectEpoch <= state.projectEpoch) return state;
    return { ...initialConversationState, backendGeneration: state.backendGeneration, projectEpoch,
      draft: action.preserveDraft ? state.draft : "",
      draftReferences: action.preserveDraft ? state.draftReferences : [],
      annotations: action.preserveDraft ? state.annotations : [],
      nextAnnotationNumber: action.preserveDraft ? state.nextAnnotationNumber : 1,
      submittedTurn: action.preserveDraft ? state.submittedTurn : null,
      submittedContext: action.preserveDraft ? state.submittedContext : null };
  }
  if (action.type === "conversation-selected") {
    if (
      state.activeTurn !== null || state.stopRequest !== null ||
      action.generation !== state.backendGeneration ||
      !isValidSelection(action)
    ) {
      return state;
    }
    return {
      ...state,
      draft: action.preserveDraft || sameSelection(state.selected, action) ? state.draft : "",
      draftReferences: action.preserveDraft || sameSelection(state.selected, action) ? state.draftReferences : [],
      annotations: action.preserveDraft || sameSelection(state.selected, action) ? state.annotations : [],
      nextAnnotationNumber: action.preserveDraft || sameSelection(state.selected, action) ? state.nextAnnotationNumber : 1,
      submittedContext: action.preserveDraft || sameSelection(state.selected, action) ? state.submittedContext : null,
      submittedTurn: action.preserveDraft || sameSelection(state.selected, action) ? state.submittedTurn : null,
      selected: { projectId: action.projectId, sessionId: action.sessionId },
      latestAnswer: null,
      failure: null,
    };
  }
  if ((action.type === "reference-added" || action.type === "reference-removed" || action.type === "annotation-changed" || action.type === "annotation-toggled" || action.type === "new-turn-requested") &&
      action.generation !== undefined && action.generation !== state.backendGeneration) return state;
  if (action.type === "reference-added") {
    if (state.activeTurn !== null || state.stopRequest !== null || state.selected === null || state.draftReferences.some((item) => item.referenceId === action.reference.referenceId)) return state;
    return { ...state, draftReferences: [...state.draftReferences, structuredClone(action.reference)],
      annotations: [...state.annotations.map((item) => ({ ...item, expanded: false })), {
        referenceId: action.reference.referenceId, number: state.nextAnnotationNumber, comment: "", expanded: true,
      }], nextAnnotationNumber: state.nextAnnotationNumber + 1, submittedTurn: null, failure: null };
  }
  if (action.type === "reference-removed") {
    if (state.activeTurn !== null || state.stopRequest !== null) return state;
    return { ...state, draftReferences: state.draftReferences.filter((item) => item.referenceId !== action.referenceId),
      annotations: state.annotations.filter((item) => item.referenceId !== action.referenceId), submittedTurn: null, failure: null };
  }
  if (action.type === "annotation-changed" || action.type === "annotation-toggled") {
    if (state.activeTurn !== null || state.stopRequest !== null) return state;
    return { ...state, annotations: state.annotations.map((item) => item.referenceId !== action.referenceId
      ? action.type === "annotation-toggled" && action.expanded ? { ...item, expanded: false } : item
      : action.type === "annotation-changed" ? { ...item, comment: action.comment } : { ...item, expanded: action.expanded }),
      submittedTurn: action.type === "annotation-changed" ? null : state.submittedTurn,
      failure: action.type === "annotation-changed" ? null : state.failure };
  }
  if (action.type === "new-turn-requested") return state.activeTurn === null && state.stopRequest === null ? { ...state, submittedTurn: null, failure: null } : state;
  if (action.type === "draft-changed") {
    return typeof action.draft === "string"
      ? {
          ...state,
          draft: action.draft,
          submittedTurn: action.draft === state.draft || state.activeTurn !== null ? state.submittedTurn : null,
          failure: action.draft === state.draft ? state.failure : null,
        }
      : state;
  }
  if (action.type === "turn-started") {
    if (
      state.activeTurn !== null || state.stopRequest !== null ||
      action.generation !== state.backendGeneration ||
      !sameSelection(state.selected, action) ||
      !isNonEmptyString(action.requestId) ||
      !isCanonicalTurnId(action.turnId)
    ) {
      return state;
    }
    return {
      ...state,
      submittedContext: action.submittedContext === undefined ? state.submittedContext : structuredClone(action.submittedContext),
      submittedTurn: { projectId: action.projectId, sessionId: action.sessionId, turnId: action.turnId,
        text: action.text ?? composeTurnText(state.draft, state.annotations),
        accepted: state.submittedTurn?.turnId === action.turnId && state.submittedTurn.accepted },
      activeTurn: {
        backendGeneration: action.generation,
        projectEpoch: state.projectEpoch,
        projectId: action.projectId,
        sessionId: action.sessionId,
        requestId: action.requestId,
        turnId: action.turnId,
        activity: [],
      },
      latestAnswer: null,
      failure: null,
    };
  }
  if (action.type === "activity-received") {
    return receiveActivity(state, action);
  }
  if (action.type === "turn-accepted" || action.type === "turn-acceptance-reconciled") {
    const submitted = state.submittedTurn;
    if (action.generation !== state.backendGeneration || !sameSelection(state.selected, action) ||
        submitted === null || submitted.turnId !== action.turnId || !sameSelection(submitted, action)) return state;
    if (action.type === "turn-accepted") {
      const active = state.activeTurn;
      if (active === null || active.backendGeneration !== action.generation || active.projectEpoch !== state.projectEpoch ||
          active.requestId !== action.requestId || active.turnId !== action.turnId || !sameSelection(active, action)) return state;
    }
    return { ...state, draft: "", draftReferences: [], annotations: [], nextAnnotationNumber: 1,
      failure: action.type === "turn-acceptance-reconciled" && state.failure?.turnId === action.turnId
        ? { ...state.failure, draftPreserved: false, turnLifecycle: { turnId: action.turnId, state: action.state, accepted: true, persisted: true } }
        : state.failure,
      submittedTurn: { ...submitted, accepted: true } };
  }
  if (action.type === "turn-succeeded") {
    return finalizeTurn(state, action);
  }
  if (action.type === "turn-failed") {
    const active = state.activeTurn;
    const turnLifecycle = action.turnLifecycle ?? null;
    if (
      active === null ||
      action.generation !== state.backendGeneration ||
      action.generation !== active.backendGeneration ||
      action.requestId !== active.requestId ||
      action.projectId !== active.projectId ||
      action.sessionId !== active.sessionId ||
      typeof action.message !== "string" ||
      typeof action.retryable !== "boolean" ||
      (turnLifecycle !== null && !validTurnLifecycle(turnLifecycle, active.turnId))
    ) {
      return state;
    }
    const accepted = turnLifecycle?.accepted === true || state.submittedTurn?.accepted === true;
    return {
      ...state,
      activeTurn: null,
      stopRequest: state.stopRequest?.status === "confirmed" ? null : state.stopRequest,
      draft: accepted ? "" : state.draft,
      draftReferences: accepted ? [] : state.draftReferences,
      annotations: accepted ? [] : state.annotations,
      nextAnnotationNumber: accepted ? 1 : state.nextAnnotationNumber,
      submittedTurn: action.cancelled || state.submittedTurn === null ? null : { ...state.submittedTurn, accepted },
      latestAnswer: null,
      failure: {
        ...(action.cancelled ? { cancelled: true } : {}),
        projectId: active.projectId,
        sessionId: active.sessionId,
        requestId: active.requestId,
        turnId: active.turnId,
        message: action.message.slice(0, 320),
        retryable: action.cancelled ? false : action.retryable,
        draftPreserved: !accepted && (state.draft.length > 0 || state.draftReferences.length > 0),
        turnLifecycle,
      },
    };
  }
  if (action.type === "retry-target-restored") {
    if (
      state.activeTurn !== null || state.stopRequest !== null ||
      action.generation !== state.backendGeneration ||
      !sameSelection(state.selected, action) ||
      !isCanonicalTurnId(action.turnId) ||
      typeof action.userText !== "string" ||
      action.userText.length === 0 ||
      (action.state !== "failed" && action.state !== "interrupted") ||
      typeof action.message !== "string" ||
      typeof action.retryable !== "boolean"
    ) {
      return state;
    }
    return {
      ...state,
      draft: "",
      draftReferences: [],
      annotations: [],
      nextAnnotationNumber: 1,
      submittedContext: structuredClone(action.submittedContext ?? null),
      submittedTurn: { projectId: action.projectId, sessionId: action.sessionId, turnId: action.turnId, text: action.userText, accepted: true },
      latestAnswer: null,
      failure: {
        projectId: action.projectId,
        sessionId: action.sessionId,
        requestId: null,
        turnId: action.turnId,
        message: action.message.slice(0, 320),
        retryable: action.retryable,
        draftPreserved: false,
        turnLifecycle: {
          turnId: action.turnId,
          state: action.state,
          accepted: true,
          persisted: true,
        },
      },
    };
  }
  if (action.type === "failure-cleared") {
    return { ...state, failure: null };
  }
  return state;
}

export function nextTurnSubmission(
  state: ConversationState,
  idFactory: () => string,
): { turnId: string; retry: boolean } {
  if (state.failure !== null && !state.failure.cancelled) {
    return { turnId: state.failure.turnId, retry: true };
  }
  if (state.failure === null && state.submittedTurn !== null && !state.submittedTurn.accepted && sameSelection(state.selected, state.submittedTurn)) {
    return { turnId: state.submittedTurn.turnId, retry: true };
  }
  return { turnId: idFactory(), retry: false };
}

export function turnSubmissionText(state: ConversationState): string {
  if (state.submittedTurn !== null && sameSelection(state.selected, state.submittedTurn) &&
      ((state.failure !== null && !state.failure.cancelled && state.failure.turnId === state.submittedTurn.turnId) ||
       (state.failure === null && !state.submittedTurn.accepted))) return state.submittedTurn.text;
  return composeTurnText(state.draft, state.annotations);
}

export function composeTurnText(draft: string, annotations: readonly DraftAnnotation[]): string {
  const requests = annotations.filter((item) => item.comment.trim().length > 0)
    .map((item) => `Reference ${item.referenceId}:\n${item.comment.trim()}`);
  if (requests.length === 0) return draft;
  return `${draft.trim().length > 0 ? `Main request:\n${draft}\n\n` : ""}Requests for frozen references:\n\n${requests.join("\n\n")}`;
}

export function latestRetryableTranscriptTurn(
  items: readonly TranscriptTurnDto[],
): (TranscriptTurnDto & {
  state: "failed" | "interrupted";
  failureRetryable: true;
}) | null {
  return items.reduce<ReturnType<typeof latestRetryableTranscriptTurn>>(
    (latest, item) => {
      if (
        (item.state !== "failed" && item.state !== "interrupted") ||
        item.failureRetryable !== true || item.failureCode === "cancelled"
      ) {
        return latest;
      }
      if (latest !== null && latest.turnNumber > item.turnNumber) {
        return latest;
      }
      return item as TranscriptTurnDto & {
        state: "failed" | "interrupted";
        failureRetryable: true;
      };
    },
    null,
  );
}

export function conversationInteractionState(
  state: ConversationState,
): ConversationInteractionState {
  const turnActive = state.activeTurn !== null || state.stopRequest !== null;
  return {
    turnActive,
    sendDisabled: turnActive || state.selected === null || composeTurnText(state.draft, state.annotations).trim().length === 0,
    createDisabled: turnActive,
    selectDisabled: turnActive,
    controlDisabled: turnActive,
  };
}
