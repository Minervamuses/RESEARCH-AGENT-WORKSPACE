import assert from "node:assert/strict";
import test from "node:test";

import {
  MAX_ANSWER_CHUNK_BYTES,
  MAX_ACTIVITY_ITEMS,
  conversationInteractionState,
  conversationReducer,
  initialConversationState,
  type AnswerChunkMessage,
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

function chunk(
  chunkIndex: number,
  text: string,
  overrides: Partial<AnswerChunkMessage> & { data?: Partial<AnswerChunkMessage["data"]> } = {},
): AnswerChunkMessage {
  return {
    requestId: overrides.requestId ?? requestId,
    sequence: overrides.sequence ?? chunkIndex + 2,
    data: {
      sessionId: overrides.data?.sessionId ?? sessionId,
      turnId: overrides.data?.turnId ?? turnId,
      chunkIndex: overrides.data?.chunkIndex ?? chunkIndex,
      streamKind: overrides.data?.streamKind ?? "post_finalized",
      text: overrides.data?.text ?? text,
    },
  };
}

function receive(state: ConversationState, event: AnswerChunkMessage): ConversationState {
  return conversationReducer(state, {
    type: "answer-chunk-received",
    generation: 1,
    event,
  });
}

function succeed(
  state: ConversationState,
  text: string,
  chunkCount: number,
): ConversationState {
  return conversationReducer(state, {
    type: "turn-succeeded",
    generation: 1,
    requestId,
    projectId,
    result: {
      sessionId,
      turnId,
      text,
      responseKind: "answer",
      streamKind: "post_finalized",
      chunkCount,
    },
  });
}

test("equal provisional and authoritative text becomes one final answer", () => {
  let state = receive(activeState(), chunk(0, "Hello "));
  state = receive(state, chunk(1, "world"));
  assert.equal(state.activeTurn?.provisionalText, "Hello world");

  state = succeed(state, "Hello world", 2);
  assert.equal(state.activeTurn, null);
  assert.deepEqual(state.latestAnswer, {
    projectId,
    sessionId,
    requestId,
    turnId,
    text: "Hello world",
    responseKind: "answer",
    streamKind: "post_finalized",
    presentation: "final",
  });
  assert.equal(state.draft, "");

  const afterLateChunk = receive(state, chunk(2, "duplicate"));
  assert.equal(afterLateChunk, state);
  assert.equal(afterLateChunk.latestAnswer?.text, "Hello world");
});

test("a differing authoritative result replaces provisional assembly exactly once", () => {
  let state = receive(activeState(), chunk(0, "draft answer"));
  state = succeed(state, "final answer", 1);
  assert.equal(state.latestAnswer?.text, "final answer");
  assert.equal(state.latestAnswer?.presentation, "reconciled");

  const duplicateResult = succeed(state, "second answer", 1);
  assert.equal(duplicateResult, state);
  assert.equal(duplicateResult.latestAnswer?.text, "final answer");
});

test("duplicate, gap, stale, cross-session, mismatched, and malformed chunks are rejected", () => {
  const started = activeState();
  const first = receive(started, chunk(0, "a"));
  assert.notEqual(first, started);

  const rejected = [
    chunk(0, "duplicate", { sequence: 3 }),
    chunk(2, "gap", { sequence: 4 }),
    chunk(1, "stale", { sequence: 2 }),
    chunk(1, "cross", { sequence: 4, data: { sessionId: otherSessionId } }),
    chunk(1, "mismatch", { sequence: 4, data: { turnId: "turn-2" } }),
    chunk(1, "", { sequence: 4 }),
    chunk(1, "x".repeat(MAX_ANSWER_CHUNK_BYTES + 1), { sequence: 4 }),
    chunk(1, "wrong request", {
      sequence: 4,
      requestId: "223e4567-e89b-42d3-a456-426614174000",
    }),
  ];
  for (const event of rejected) {
    assert.equal(receive(first, event), first);
  }
  assert.equal(receive(first, null as unknown as AnswerChunkMessage), first);

  const wrongGeneration = conversationReducer(first, {
    type: "answer-chunk-received",
    generation: 2,
    event: chunk(1, "stale generation", { sequence: 4 }),
  });
  assert.equal(wrongGeneration, first);
});

test("oversized aggregate stream is rejected without altering accepted text", () => {
  const maxChunk = "a".repeat(16_384);
  let state = activeState();
  for (let index = 0; index < 128; index += 1) {
    state = receive(state, chunk(index, maxChunk));
  }
  assert.equal(state.activeTurn?.chunks.length, 128);
  assert.equal(state.activeTurn?.chunkBytes, 2 * 1024 * 1024);
  const full = state;
  assert.equal(receive(full, chunk(127, "extra", { sequence: 131 })), full);
});

test("failure discards provisional text, preserves recoverable draft, and unlocks controls", () => {
  let state = receive(activeState("retry this"), chunk(0, "partial"));
  assert.equal(conversationInteractionState(state).createDisabled, true);
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

test("backend generation change drops stale selection, stream, answer, and failure", () => {
  let state = receive(activeState(), chunk(0, "partial"));
  state = conversationReducer(state, {
    type: "backend-generation-changed",
    generation: 2,
  });
  assert.equal(state.backendGeneration, 2);
  assert.equal(state.selected, null);
  assert.equal(state.activeTurn, null);
  assert.equal(state.latestAnswer, null);
  assert.equal(state.failure, null);
  assert.equal(state.draft, "question");
  assert.equal(receive(state, chunk(1, "late")), state);

  const staleGeneration = conversationReducer(state, {
    type: "backend-generation-changed",
    generation: 1,
  });
  assert.equal(staleGeneration, state);
});

test("activity is correlated, bounded, and global turn lock blocks selection and control", () => {
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
      turnId: null,
      activity: { kind: "stage", label: `stage-${index}`, status: null },
    });
  }
  assert.equal(state.activeTurn?.activity.length, MAX_ACTIVITY_ITEMS);
  assert.equal(state.activeTurn?.activity[0]?.label, "stage-5");
});
