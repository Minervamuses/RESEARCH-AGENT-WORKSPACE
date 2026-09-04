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
  requestId: string;
  turnId: string;
  activity: readonly ConversationActivity[];
}

export interface AuthoritativeTurnResult {
  sessionId: string;
  turnId: string;
  turnNumber?: number;
  state: "completed" | null;
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
  text: string;
  responseKind: "answer" | "command";
  streamKind: AnswerStreamKind;
}

export interface ConversationFailure extends ConversationSelection {
  requestId: string;
  turnId: string;
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
  | ({ type: "turn-started"; generation: number; requestId: string; turnId: string } & ConversationSelection)
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

function sameSelection(
  left: ConversationSelection | null,
  right: ConversationSelection,
): boolean {
  return left !== null && left.projectId === right.projectId && left.sessionId === right.sessionId;
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
  const answerLifecycleIsValid =
    responseKind === "answer" &&
    Number.isSafeInteger(result.turnNumber) &&
    Number(result.turnNumber) >= 1 &&
    Number(result.turnNumber) <= 4_096 &&
    result.state === "completed" &&
    result.accepted === true &&
    result.persisted === true;
  const commandLifecycleIsValid =
    responseKind === "command" &&
    result.turnNumber === undefined &&
    result.state === null &&
    result.accepted === false &&
    result.persisted === false;
  if (
    active === null ||
    action.generation !== state.backendGeneration ||
    action.generation !== active.backendGeneration ||
    action.requestId !== active.requestId ||
    action.projectId !== active.projectId ||
    result.sessionId !== active.sessionId ||
    result.turnId !== active.turnId ||
    (!answerLifecycleIsValid && !commandLifecycleIsValid) ||
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
    activeTurn: null,
    latestAnswer: {
      projectId: active.projectId,
      sessionId: active.sessionId,
      requestId: active.requestId,
      turnId: result.turnId,
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
    return typeof action.draft === "string"
      ? {
          ...state,
          draft: action.draft,
          failure: action.draft === state.draft ? state.failure : null,
        }
      : state;
  }
  if (action.type === "turn-started") {
    if (
      state.activeTurn !== null ||
      action.generation !== state.backendGeneration ||
      !sameSelection(state.selected, action) ||
      !isNonEmptyString(action.requestId) ||
      !isCanonicalTurnId(action.turnId)
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
        turnId: active.turnId,
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
