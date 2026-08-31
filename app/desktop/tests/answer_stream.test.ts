import assert from "node:assert/strict";
import test from "node:test";

import {
  MAX_ACTIVITY_ITEMS,
  conversationInteractionState,
  conversationReducer,
  initialConversationState,
  type AuthoritativeTurnResult,
  type ConversationAction,
  type ConversationState,
} from "../src/conversations.ts";

const projectId = "local";
const sessionId = "123e4567e89b42d3a456426614174000";
const otherSessionId = "223e4567e89b42d3a456426614174000";
const requestId = "123e4567-e89b-42d3-a456-426614174000";
const turnId = "turn-1";

function selectedState(draft = "question"): ConversationState {
  let state = conversationReducer(initialConversationState, {
    type: "backend-generation-changed",
    generation: 1,
  });
  state = conversationReducer(state, {
    type: "conversation-selected",
    generation: 1,
    projectId,
    sessionId,
  });
  return conversationReducer(state, { type: "draft-changed", draft });
}

function activeState(draft = "question"): ConversationState {
  return conversationReducer(selectedState(draft), {
    type: "turn-started",
    generation: 1,
    projectId,
    sessionId,
    requestId,
  });
}

function succeed(
  state: ConversationState,
  overrides: Partial<AuthoritativeTurnResult> = {},
): ConversationState {
  return conversationReducer(state, {
    type: "turn-succeeded",
    generation: 1,
    requestId,
    projectId,
    result: {
      sessionId,
      turnId,
      text: "complete answer",
      responseKind: "answer",
      streamKind: "final_only",
      chunkCount: 0,
      ...overrides,
    },
  });
}

test("one final-only result creates one complete authoritative answer", () => {
  const started = activeState();
  assert.equal(started.latestAnswer, null);

  const state = succeed(started);
  assert.equal(state.activeTurn, null);
  assert.equal(state.draft, "");
  assert.deepEqual(state.latestAnswer, {
    projectId,
    sessionId,
    requestId,
    turnId,
    text: "complete answer",
    responseKind: "answer",
    streamKind: "final_only",
  });

  assert.equal(succeed(state, { text: "duplicate" }), state);
  assert.equal(state.latestAnswer?.text, "complete answer");
});

test("a local slash command is one final-only inert conversation result", () => {
  const state = succeed(activeState("/sync /tmp/research"), {
    text: "Diff against /tmp/research:\n  (none)",
    responseKind: "command",
  });

  assert.deepEqual(state.latestAnswer, {
    projectId,
    sessionId,
    requestId,
    turnId,
    text: "Diff against /tmp/research:\n  (none)",
    responseKind: "command",
    streamKind: "final_only",
  });
});

test("post-finalized, nonzero-chunk, cross-session, and malformed results fail closed", () => {
  const started = activeState();
  const invalidResults = [
    { streamKind: "post_finalized" } as unknown as Partial<AuthoritativeTurnResult>,
    { chunkCount: 1 },
    { sessionId: otherSessionId },
    { turnId: "" },
    { text: null } as unknown as Partial<AuthoritativeTurnResult>,
    { responseKind: "other" } as unknown as Partial<AuthoritativeTurnResult>,
  ];
  for (const invalid of invalidResults) {
    assert.equal(succeed(started, invalid), started);
  }

  const retiredChunkAction = {
    type: "answer-chunk-received",
    generation: 1,
    event: {},
  } as unknown as ConversationAction;
  assert.equal(conversationReducer(started, retiredChunkAction), started);
});

test("failure preserves the recoverable draft and never creates an assistant preview", () => {
  let state = activeState("retry this");
  assert.equal(conversationInteractionState(state).createDisabled, true);
  assert.equal(state.latestAnswer, null);

  state = conversationReducer(state, {
    type: "turn-failed",
    generation: 1,
    requestId,
    projectId,
    sessionId,
    message: "Provider is temporarily unavailable.",
    retryable: true,
  });

  assert.equal(state.activeTurn, null);
  assert.equal(state.latestAnswer, null);
  assert.equal(state.draft, "retry this");
  assert.equal(state.failure?.draftPreserved, true);
  assert.equal(state.failure?.retryable, true);
  assert.equal(conversationInteractionState(state).createDisabled, false);
  assert.equal(conversationInteractionState(state).sendDisabled, false);
});

test("backend generation change drops stale selection, pending turn, answer, and failure", () => {
  const started = activeState();
  const state = conversationReducer(started, {
    type: "backend-generation-changed",
    generation: 2,
  });

  assert.equal(state.backendGeneration, 2);
  assert.equal(state.selected, null);
  assert.equal(state.activeTurn, null);
  assert.equal(state.latestAnswer, null);
  assert.equal(state.failure, null);
  assert.equal(state.draft, "question");
  assert.equal(
    conversationReducer(state, {
      type: "backend-generation-changed",
      generation: 1,
    }),
    state,
  );
});

test("activity is correlated, bounded, and the global turn lock blocks controls", () => {
  let state = activeState();
  const blockedSelection: ConversationAction = {
    type: "conversation-selected",
    generation: 1,
    projectId,
    sessionId: otherSessionId,
  };
  assert.equal(conversationReducer(state, blockedSelection), state);
  assert.deepEqual(conversationInteractionState(state), {
    turnActive: true,
    sendDisabled: true,
    createDisabled: true,
    selectDisabled: true,
    controlDisabled: true,
  });

  for (let index = 0; index < MAX_ACTIVITY_ITEMS + 5; index += 1) {
    state = conversationReducer(state, {
      type: "activity-received",
      generation: 1,
      requestId,
      sessionId,
      activity: { kind: "stage", label: `stage-${index}`, status: null },
    });
  }
  assert.equal(state.activeTurn?.activity.length, MAX_ACTIVITY_ITEMS);
  assert.equal(state.activeTurn?.activity[0]?.label, "stage-5");

  const wrongRequest = conversationReducer(state, {
    type: "activity-received",
    generation: 1,
    requestId: "223e4567-e89b-42d3-a456-426614174000",
    sessionId,
    activity: { kind: "tool", label: "ignored", status: "ok" },
  });
  assert.equal(wrongRequest, state);
});
