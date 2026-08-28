export const MAX_ANSWER_CHUNKS = 128;
export const MAX_ANSWER_CHUNK_BYTES = 16_384;
export const MAX_ANSWER_STREAM_BYTES = 2 * 1024 * 1024;
export const MAX_ACTIVITY_ITEMS = 32;

export type AnswerStreamKind = "post_finalized" | "final_only";

export interface ConversationSelection {
  projectId: string;
  sessionId: string;
}

export interface AnswerChunkData {
  sessionId: string;
  turnId: string;
  chunkIndex: number;
  streamKind: "post_finalized";
  text: string;
}

export interface AnswerChunkMessage {
  requestId: string;
  sequence: number;
  data: AnswerChunkData;
}

export interface ConversationActivity {
  kind: "stage" | "tool";
  label: string;
  status: string | null;
}

export interface ActiveConversationTurn extends ConversationSelection {
  backendGeneration: number;
  requestId: string;
  turnId: string | null;
  nextChunkIndex: number;
  lastAnswerSequence: number;
  chunkBytes: number;
  chunks: readonly string[];
  provisionalText: string;
  activity: readonly ConversationActivity[];
}

export interface AuthoritativeTurnResult {
  sessionId: string;
  turnId: string;
  text: string;
  responseKind?: "answer" | "command";
  streamKind?: AnswerStreamKind;
  chunkCount?: number;
}

export interface FinalConversationAnswer extends ConversationSelection {
  requestId: string;
  turnId: string;
  text: string;
  responseKind: "answer" | "command";
  streamKind: AnswerStreamKind;
  presentation: "final" | "reconciled" | "final_only";
}

export interface ConversationFailure extends ConversationSelection {
  requestId: string;
  message: string;
  retryable: boolean;
  draftPreserved: boolean;
}

export interface ConversationState {
  backendGeneration: number;
  selected: ConversationSelection | null;
  draft: string;
  activeTurn: ActiveConversationTurn | null;
  latestAnswer: FinalConversationAnswer | null;
  failure: ConversationFailure | null;
}

export type ConversationAction =
  | { type: "backend-generation-changed"; generation: number }
  | ({ type: "conversation-selected"; generation: number } & ConversationSelection)
  | { type: "draft-changed"; draft: string }
  | ({ type: "turn-started"; generation: number; requestId: string } & ConversationSelection)
  | { type: "answer-chunk-received"; generation: number; event: AnswerChunkMessage }
  | ({
      type: "activity-received";
      generation: number;
      requestId: string;
      sessionId: string;
      turnId: string | null;
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
      generation: number;
      requestId: string;
      projectId: string;
      sessionId: string;
      message: string;
      retryable: boolean;
    })
  | { type: "failure-cleared" };

export interface ConversationInteractionState {
  turnActive: boolean;
  sendDisabled: boolean;
  createDisabled: boolean;
  selectDisabled: boolean;
  controlDisabled: boolean;
}

export const initialConversationState: ConversationState = {
  backendGeneration: 0,
  selected: null,
  draft: "",
  activeTurn: null,
  latestAnswer: null,
  failure: null,
};

const encoder = new TextEncoder();

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNonNegativeSafeInteger(value: unknown): value is number {
  return Number.isSafeInteger(value) && Number(value) >= 0;
}

function isPositiveSafeInteger(value: unknown): value is number {
  return Number.isSafeInteger(value) && Number(value) > 0;
}

function isValidSelection(value: ConversationSelection): boolean {
  return isNonEmptyString(value.projectId) && isNonEmptyString(value.sessionId);
}

function sameSelection(
  left: ConversationSelection | null,
  right: ConversationSelection,
): boolean {
  return left !== null && left.projectId === right.projectId && left.sessionId === right.sessionId;
}

function validChunkMessage(event: unknown): event is AnswerChunkMessage {
  if (!isRecord(event) || !isRecord(event.data)) {
    return false;
  }
  const data = event.data;
  return (
    isNonEmptyString(event.requestId) &&
    isPositiveSafeInteger(event.sequence) &&
    isNonEmptyString(data.sessionId) &&
    isNonEmptyString(data.turnId) &&
    isNonNegativeSafeInteger(data.chunkIndex) &&
    data.chunkIndex < MAX_ANSWER_CHUNKS &&
    data.streamKind === "post_finalized" &&
    isNonEmptyString(data.text)
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

function receiveAnswerChunk(
  state: ConversationState,
  generation: number,
  event: AnswerChunkMessage,
): ConversationState {
  const active = state.activeTurn;
  if (
    active === null ||
    generation !== state.backendGeneration ||
    generation !== active.backendGeneration ||
    !validChunkMessage(event) ||
    event.requestId !== active.requestId ||
    event.data.sessionId !== active.sessionId ||
    event.data.chunkIndex !== active.nextChunkIndex ||
    event.sequence <= active.lastAnswerSequence ||
    (active.turnId !== null && event.data.turnId !== active.turnId)
  ) {
    return state;
  }

  const chunkBytes = encoder.encode(event.data.text).byteLength;
  if (
    chunkBytes === 0 ||
    chunkBytes > MAX_ANSWER_CHUNK_BYTES ||
    active.chunks.length >= MAX_ANSWER_CHUNKS ||
    active.chunkBytes + chunkBytes > MAX_ANSWER_STREAM_BYTES
  ) {
    return state;
  }

  const chunks = [...active.chunks, event.data.text];
  return {
    ...state,
    activeTurn: {
      ...active,
      turnId: active.turnId ?? event.data.turnId,
      nextChunkIndex: active.nextChunkIndex + 1,
      lastAnswerSequence: event.sequence,
      chunkBytes: active.chunkBytes + chunkBytes,
      chunks,
      provisionalText: chunks.join(""),
    },
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
    action.sessionId !== active.sessionId ||
    (action.turnId !== null && active.turnId !== null && action.turnId !== active.turnId)
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
  if (
    active === null ||
    action.generation !== state.backendGeneration ||
    action.generation !== active.backendGeneration ||
    action.requestId !== active.requestId ||
    action.projectId !== active.projectId ||
    result.sessionId !== active.sessionId ||
    !isNonEmptyString(result.turnId) ||
    typeof result.text !== "string" ||
    (active.turnId !== null && result.turnId !== active.turnId) ||
    (result.responseKind !== undefined &&
      result.responseKind !== "answer" &&
      result.responseKind !== "command") ||
    (result.streamKind !== undefined &&
      result.streamKind !== "post_finalized" &&
      result.streamKind !== "final_only") ||
    (result.chunkCount !== undefined &&
      (!isNonNegativeSafeInteger(result.chunkCount) || result.chunkCount > MAX_ANSWER_CHUNKS))
  ) {
    return state;
  }

  const responseKind = result.responseKind ?? "answer";
  const streamKind = result.streamKind ?? "final_only";
  const completeStream =
    streamKind === "post_finalized" &&
    result.chunkCount === active.chunks.length &&
    active.chunks.length > 0;
  const presentation =
    streamKind === "final_only"
      ? "final_only"
      : completeStream && active.provisionalText === result.text
        ? "final"
        : "reconciled";

  return {
    ...state,
    draft: "",
    activeTurn: null,
    latestAnswer: {
      projectId: active.projectId,
      sessionId: active.sessionId,
      requestId: active.requestId,
      turnId: result.turnId,
      text: result.text,
      responseKind,
      streamKind,
      presentation,
    },
    failure: null,
  };
}

export function conversationReducer(
  state: ConversationState,
  action: ConversationAction,
): ConversationState {
  if (action.type === "backend-generation-changed") {
    if (!isNonNegativeSafeInteger(action.generation) || action.generation <= state.backendGeneration) {
      return state;
    }
    return {
      ...state,
      backendGeneration: action.generation,
      selected: null,
      activeTurn: null,
      latestAnswer: null,
      failure: null,
    };
  }
  if (action.type === "conversation-selected") {
    if (
      state.activeTurn !== null ||
      action.generation !== state.backendGeneration ||
      !isValidSelection(action)
    ) {
      return state;
    }
    return {
      ...state,
      draft: sameSelection(state.selected, action) ? state.draft : "",
      selected: { projectId: action.projectId, sessionId: action.sessionId },
      latestAnswer: null,
      failure: null,
    };
  }
  if (action.type === "draft-changed") {
    return typeof action.draft === "string" ? { ...state, draft: action.draft } : state;
  }
  if (action.type === "turn-started") {
    if (
      state.activeTurn !== null ||
      action.generation !== state.backendGeneration ||
      !sameSelection(state.selected, action) ||
      !isNonEmptyString(action.requestId)
    ) {
      return state;
    }
    return {
      ...state,
      activeTurn: {
        backendGeneration: action.generation,
        projectId: action.projectId,
        sessionId: action.sessionId,
        requestId: action.requestId,
        turnId: null,
        nextChunkIndex: 0,
        lastAnswerSequence: 0,
        chunkBytes: 0,
        chunks: [],
        provisionalText: "",
        activity: [],
      },
      latestAnswer: null,
      failure: null,
    };
  }
  if (action.type === "answer-chunk-received") {
    return receiveAnswerChunk(state, action.generation, action.event);
  }
  if (action.type === "activity-received") {
    return receiveActivity(state, action);
  }
  if (action.type === "turn-succeeded") {
    return finalizeTurn(state, action);
  }
  if (action.type === "turn-failed") {
    const active = state.activeTurn;
    if (
      active === null ||
      action.generation !== state.backendGeneration ||
      action.generation !== active.backendGeneration ||
      action.requestId !== active.requestId ||
      action.projectId !== active.projectId ||
      action.sessionId !== active.sessionId ||
      typeof action.message !== "string" ||
      typeof action.retryable !== "boolean"
    ) {
      return state;
    }
    return {
      ...state,
      activeTurn: null,
      latestAnswer: null,
      failure: {
        projectId: active.projectId,
        sessionId: active.sessionId,
        requestId: active.requestId,
        message: action.message.slice(0, 320),
        retryable: action.retryable,
        draftPreserved: state.draft.length > 0,
      },
    };
  }
  if (action.type === "failure-cleared") {
    return { ...state, failure: null };
  }
  return state;
}

export function conversationInteractionState(
  state: ConversationState,
): ConversationInteractionState {
  const turnActive = state.activeTurn !== null;
  return {
    turnActive,
    sendDisabled: turnActive || state.selected === null || state.draft.trim().length === 0,
    createDisabled: turnActive,
    selectDisabled: turnActive,
    controlDisabled: turnActive,
  };
}
