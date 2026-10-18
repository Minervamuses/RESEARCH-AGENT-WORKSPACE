import assert from "node:assert/strict";
import test from "node:test";

import * as conversationModule from "../src/conversations.ts";
import {
  MAX_ACTIVITY_ITEMS,
  conversationInteractionState,
  conversationReducer,
  initialConversationState,
  latestRetryableTranscriptTurn,
  mergeConversationTurns,
  reconciledTurnCount,
  upsertLiveTurn,
  composeTurnText,
  turnSubmissionText,
  type AuthoritativeTurnResult,
  type ConversationAction,
  type ConversationState,
  type LiveTurn,
} from "../src/conversations.ts";
import type { TranscriptTurnDto } from "../src/protocol.ts";

const projectId = "local";
const sessionId = "123e4567e89b42d3a456426614174000";
const otherSessionId = "223e4567e89b42d3a456426614174000";
const requestId = "123e4567-e89b-42d3-a456-426614174000";
const retryRequestId = "223e4567-e89b-42d3-a456-426614174000";
const turnId = "123e4567e89b42d3a456426614174001";
const otherTurnId = "223e4567e89b42d3a456426614174001";

interface TurnLifecycleDetails {
  turnId: string;
  state: "pending" | "completed" | "failed" | "interrupted" | null;
  accepted: boolean;
  persisted: boolean;
}

const nextTurnSubmission = (
  conversationModule as unknown as {
    nextTurnSubmission: (
      state: ConversationState,
      idFactory: () => string,
    ) => { turnId: string; retry: boolean };
  }
).nextTurnSubmission;

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
    turnId,
  });
}

function succeed(
  state: ConversationState,
  overrides: Partial<AuthoritativeTurnResult> = {},
  correlatedRequestId = requestId,
): ConversationState {
  return conversationReducer(state, {
    type: "turn-succeeded",
    generation: 1,
    requestId: correlatedRequestId,
    projectId,
    result: {
      sessionId,
      turnId,
      text: "complete answer",
      turnNumber: 1,
      state: "completed",
      accepted: true,
      persisted: true,
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
  assert.equal(started.activeTurn?.turnId, turnId);

  const state = succeed(started);
  assert.equal(state.activeTurn, null);
  assert.equal(state.draft, "");
  assert.deepEqual(state.latestAnswer, {
    projectId,
    sessionId,
    requestId,
    turnId,
    turnNumber: 1,
    text: "complete answer",
    responseKind: "answer",
    streamKind: "final_only",
  });

  assert.equal(succeed(state, { text: "duplicate" }), state);
  assert.equal(state.latestAnswer?.text, "complete answer");
});

test("a result for a different logical turn is rejected", () => {
  const started = activeState();
  assert.equal(succeed(started, { turnId: otherTurnId }), started);
});

test("a local slash command is one durable final-only display result", () => {
  const state = succeed(activeState("/sync /tmp/research"), {
    text: "Diff against /tmp/research:\n  (none)",
    responseKind: "command",
  });

  assert.deepEqual(state.latestAnswer, {
    projectId,
    sessionId,
    requestId,
    turnId,
    turnNumber: 1,
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
    { turnNumber: undefined } as unknown as Partial<AuthoritativeTurnResult>,
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
  assert.equal(state.failure?.turnId, turnId);
  assert.equal(conversationInteractionState(state).createDisabled, false);
  assert.equal(conversationInteractionState(state).sendDisabled, false);

  const edited = conversationReducer(state, {
    type: "draft-changed",
    draft: "retry this with changes",
  });
  assert.equal(edited.failure, null);
});

test("failure lifecycle distinguishes not accepted from durable terminal records", () => {
  const cases: Array<{ name: string; lifecycle: TurnLifecycleDetails }> = [
    {
      name: "not accepted",
      lifecycle: { turnId, state: null, accepted: false, persisted: false },
    },
    {
      name: "durable failed",
      lifecycle: { turnId, state: "failed", accepted: true, persisted: true },
    },
    {
      name: "durable interrupted",
      lifecycle: { turnId, state: "interrupted", accepted: true, persisted: true },
    },
    {
      name: "completed before acknowledgement",
      lifecycle: { turnId, state: "completed", accepted: true, persisted: true },
    },
  ];

  for (const { name, lifecycle } of cases) {
    const failed = conversationReducer(activeState(name), {
      type: "turn-failed",
      generation: 1,
      requestId,
      projectId,
      sessionId,
      message: `${name} failure`,
      retryable: true,
      turnLifecycle: lifecycle,
    } as unknown as ConversationAction);
    assert.deepEqual(failed.failure?.turnLifecycle, lifecycle, name);
    assert.equal(failed.failure?.turnId, turnId, name);
    assert.equal(failed.draft, lifecycle.accepted ? "" : name, name);
    assert.equal(turnSubmissionText(failed), name, "explicit retry retains the original request");
    assert.equal(failed.latestAnswer, null, name);
  }

  const started = activeState("invalid lifecycle");
  assert.equal(conversationReducer(started, {
    type: "turn-failed",
    generation: 1,
    requestId,
    projectId,
    sessionId,
    message: "invalid",
    retryable: true,
    turnLifecycle: { turnId, state: "failed", accepted: false, persisted: false },
  } as unknown as ConversationAction), started);
});

test("first send is not a retry and an explicit transport retry keeps the logical ID", () => {
  let generated = 0;
  const first = nextTurnSubmission(selectedState("question"), () => {
    generated += 1;
    return turnId;
  });
  assert.deepEqual(first, { turnId, retry: false });
  assert.equal(generated, 1);

  const started = conversationReducer(selectedState("question"), {
    type: "turn-started",
    generation: 1,
    projectId,
    sessionId,
    requestId,
    turnId: first.turnId,
  });
  const timedOut = conversationReducer(started, {
    type: "turn-failed",
    generation: 1,
    requestId,
    projectId,
    sessionId,
    message: "The backend response timed out.",
    retryable: true,
  });
  const retry = nextTurnSubmission(timedOut, () => {
    throw new Error("retry must not allocate another logical turn ID");
  });
  assert.deepEqual(retry, { turnId, retry: true });
});

test("completed-before-ack retry replays the same logical turn", () => {
  const deliveryFailed = conversationReducer(activeState("question"), {
    type: "turn-failed",
    generation: 1,
    requestId,
    projectId,
    sessionId,
    message: "The saved result was not acknowledged.",
    retryable: true,
    turnLifecycle: { turnId, state: "completed", accepted: true, persisted: true },
  } as unknown as ConversationAction);
  const submission = nextTurnSubmission(deliveryFailed, () => otherTurnId);
  assert.deepEqual(submission, { turnId, retry: true });

  const replayStarted = conversationReducer(deliveryFailed, {
    type: "turn-started",
    generation: 1,
    projectId,
    sessionId,
    requestId: retryRequestId,
    turnId: submission.turnId,
  });
  const replayed = succeed(replayStarted, { turnId, text: "saved answer" }, retryRequestId);
  assert.equal(replayed.activeTurn, null);
  assert.equal(replayed.failure, null);
  assert.equal(replayed.latestAnswer?.turnId, turnId);
  assert.equal(replayed.latestAnswer?.requestId, retryRequestId);
});

test("restart transcript can restore an interrupted same-ID retry target", () => {
  let state = conversationReducer(activeState("question"), {
    type: "backend-generation-changed",
    generation: 2,
  });
  state = conversationReducer(state, {
    type: "conversation-selected",
    generation: 2,
    projectId,
    sessionId,
  });
  state = conversationReducer(state, {
    type: "retry-target-restored",
    generation: 2,
    projectId,
    sessionId,
    turnId,
    userText: "question",
    state: "interrupted",
    message: "The previous process stopped before completion.",
    retryable: true,
  } as unknown as ConversationAction);

  assert.equal(state.failure?.requestId, null);
  assert.deepEqual(state.failure?.turnLifecycle, {
    turnId,
    state: "interrupted",
    accepted: true,
    persisted: true,
  });
  assert.equal(state.draft, "");
  assert.equal(turnSubmissionText(state), "question");
  assert.deepEqual(nextTurnSubmission(state, () => otherTurnId), { turnId, retry: true });
});

test("a later completed display-only turn does not hide a retryable restored turn", () => {
  const retryTarget = latestRetryableTranscriptTurn([
    {
      turnId,
      turnNumber: 1,
      kind: "conversational",
      state: "failed",
      timestamp: "2026-09-04T00:00:00Z",
      userText: "question",
      assistantText: null,
      failureCode: "execution_failed",
      failureMessage: "failed",
      failureRetryable: true,
      toolActivities: [],
    },
    {
      turnId: otherTurnId,
      turnNumber: 2,
      kind: "display-only",
      state: "completed",
      timestamp: "2026-09-04T00:00:01Z",
      userText: "/help",
      assistantText: "help",
      failureCode: null,
      failureMessage: null,
      failureRetryable: null,
      toolActivities: [],
    },
  ]);

  assert.equal(retryTarget?.turnId, turnId);
  assert.equal(retryTarget?.state, "failed");
});

function transcriptTurn(
  number: number,
  id: string,
  state: TranscriptTurnDto["state"],
): TranscriptTurnDto {
  return {
    turnId: id,
    turnNumber: number,
    kind: "conversational",
    state,
    timestamp: `2026-09-04T00:00:0${number}Z`,
    userText: `question ${number}`,
    assistantText: state === "completed" ? `answer ${number}` : null,
    failureCode: state === "failed" ? "execution_failed" : state === "interrupted" ? "interrupted" : null,
    failureMessage: state === "completed" || state === "pending" ? null : `${state} turn`,
    failureRetryable: state === "failed" || state === "interrupted" ? true : null,
    toolActivities: [],
  };
}

function liveTurn(
  targetSessionId: string,
  number: number,
  id: string,
  text = `retried answer ${number}`,
): LiveTurn {
  return {
    sessionId: targetSessionId,
    turnId: id,
    turnNumber: number,
    userText: `question ${number}`,
    assistantText: text,
    responseKind: "answer",
    streamKind: "final_only",
  };
}

test("failed and interrupted retries replace one restored card without inflating the count", () => {
  for (const state of ["failed", "interrupted"] as const) {
    const visible = mergeConversationTurns(
      [{ sessionId, turn: transcriptTurn(4, turnId, state) }],
      [liveTurn(sessionId, 4, turnId)],
    );

    assert.equal(visible.length, 1, state);
    assert.equal(visible[0]?.source, "live", state);
    assert.equal(visible[0]?.turnId, turnId, state);
    assert.equal(reconciledTurnCount(4, 4), 4, state);
  }
});

test("pending failed and interrupted retries replace the restored card before completion", () => {
  for (const state of ["failed", "interrupted"] as const) {
    const visible = mergeConversationTurns(
      [{ sessionId, turn: transcriptTurn(4, turnId, state) }],
      [],
      {
        sessionId,
        turnId,
        userText: "question 4",
        activity: [{ kind: "stage", label: "Researching", status: null }],
      },
    );

    assert.equal(visible.length, 1, state);
    assert.equal(visible[0]?.source, "pending", state);
    if (visible[0]?.source !== "pending") assert.fail(state);
    assert.equal(visible[0].retrying, true, state);
    assert.equal(visible[0].turnNumber, 4, state);
    assert.equal(visible[0].turn.userText, "question 4", state);
  }
});

test("a pending new turn remains appended after restored turns", () => {
  const visible = mergeConversationTurns(
    [{ sessionId, turn: transcriptTurn(4, turnId, "completed") }],
    [],
    {
      sessionId,
      turnId: otherTurnId,
      userText: "question 5",
      activity: [],
    },
  );

  assert.deepEqual(
    visible.map(({ source, turnNumber }) => ({ source, turnNumber })),
    [
      { source: "restored", turnNumber: 4 },
      { source: "pending", turnNumber: 5 },
    ],
  );
  assert.equal(visible[1]?.source === "pending" && visible[1].retrying, false);
});

test("completed duplicate replay upserts one final-only live card", () => {
  let live: LiveTurn[] = [];
  live = upsertLiveTurn(live, liveTurn(sessionId, 4, turnId, "saved answer"));
  live = upsertLiveTurn(live, liveTurn(sessionId, 4, turnId, "replayed saved answer"));
  const visible = mergeConversationTurns(
    [{ sessionId, turn: transcriptTurn(4, turnId, "completed") }],
    live,
  );

  assert.equal(live.length, 1);
  assert.equal(visible.length, 1);
  assert.equal(visible[0]?.source, "live");
  assert.equal(visible[0]?.turn.streamKind, "final_only");
  assert.equal(visible[0]?.turn.assistantText, "replayed saved answer");
  assert.equal(reconciledTurnCount(4, 4), 4);
});

test("a new turn increases the canonical count", () => {
  const live = upsertLiveTurn([], liveTurn(sessionId, 5, otherTurnId));

  assert.equal(live[0]?.turnNumber, 5);
  assert.equal(reconciledTurnCount(4, 5), 5);
});

test("logical turn identity includes the session and older retries keep canonical order", () => {
  const sameIdOtherSession = liveTurn(otherSessionId, 1, turnId, "other session");
  const crossSession = mergeConversationTurns(
    [{ sessionId, turn: transcriptTurn(1, turnId, "failed") }],
    [sameIdOtherSession],
  );
  assert.equal(crossSession.length, 2);

  const pendingOtherSession = mergeConversationTurns(
    [
      { sessionId, turn: transcriptTurn(99, turnId, "completed") },
      { sessionId: otherSessionId, turn: transcriptTurn(2, otherTurnId, "completed") },
    ],
    [],
    {
      sessionId: otherSessionId,
      turnId: "323e4567e89b42d3a456426614174001",
      userText: "other session question 3",
      activity: [],
    },
  );
  assert.equal(
    pendingOtherSession.find(({ source }) => source === "pending")?.turnNumber,
    3,
  );

  const ordered = mergeConversationTurns(
    [
      { sessionId, turn: transcriptTurn(1, turnId, "failed") },
      { sessionId, turn: transcriptTurn(2, otherTurnId, "completed") },
    ],
    [liveTurn(sessionId, 1, turnId)],
  );
  assert.deepEqual(
    ordered.map(({ source, turnNumber }) => ({ source, turnNumber })),
    [
      { source: "live", turnNumber: 1 },
      { source: "restored", turnNumber: 2 },
    ],
  );
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


test("Stop waits for both replies in either order and ignores duplicate clicks", () => {
  const stop = { type: "stop-requested", generation: 1 } as const;
  const stopped = { type: "stop-succeeded", generation: 1, projectId, sessionId, requestId, turnId } as const;
  for (const first of ["turn", "stop"]) {
    let state = conversationReducer(activeState(), stop);
    assert.equal(conversationReducer(state, stop), state);
    state = first === "turn" ? succeed(state) : conversationReducer(state, stopped);
    assert.deepEqual(conversationInteractionState(state), {
      turnActive: true, sendDisabled: true, createDisabled: true, selectDisabled: true, controlDisabled: true,
    });
    assert.equal(conversationReducer(state, {
      type: "turn-started", generation: 1, projectId, sessionId, requestId: retryRequestId, turnId: otherTurnId,
    }), state);
    state = first === "turn" ? conversationReducer(state, stopped) : succeed(state);
    assert.equal(state.activeTurn, null);
    assert.equal(state.stopRequest, null);
    assert.equal(conversationInteractionState(state).turnActive, false);
    assert.equal(state.latestAnswer?.text, "complete answer");
  }
});

test("Stop failure remains blocked after the turn ends and can retry only its own target", () => {
  let state = conversationReducer(activeState(), { type: "stop-requested", generation: 1 });
  state = conversationReducer(state, {
    type: "stop-failed", generation: 1, projectId, sessionId, requestId, turnId, message: "Local work is still stopping.",
  });
  assert.equal(state.stopRequest?.error, "Local work is still stopping.");
  state = succeed(state);
  assert.equal(conversationInteractionState(state).turnActive, true);
  state = conversationReducer(state, { type: "stop-requested", generation: 1 });
  const action = { type: "stop-succeeded", generation: 1, projectId, sessionId, requestId, turnId } as const;
  for (const stale of [
    { ...action, generation: 0 }, { ...action, projectEpoch: 1 },
    { ...action, requestId: retryRequestId }, { ...action, sessionId: otherSessionId }, { ...action, turnId: otherTurnId },
  ]) assert.equal(conversationReducer(state, stale), state);
  state = conversationReducer(state, action);
  assert.equal(state.stopRequest, null);
  assert.equal(conversationInteractionState(state).turnActive, false);
});

test("deleting the selected idle conversation clears its draft and retry state only", () => {
  const action = { type: "conversation-deleted", generation: 1, projectId, sessionId } as const;
  const running = activeState();
  assert.equal(conversationReducer(running, action), running);
  const waiting = conversationReducer(running, { type: "stop-requested", generation: 1 });
  assert.equal(conversationReducer(succeed(waiting), action).selected?.sessionId, sessionId);
  const failed = conversationReducer(running, { type: "turn-failed", generation: 1, projectId, sessionId, requestId,
    message: "Try again", retryable: true });
  const ready = { ...failed, draftReferences: [{ referenceId: "reference", kind: "chat" as const, text: "source",
    chat: { projectId, sessionId, turnId, role: "assistant" as const, messageFingerprint: "a".repeat(64), startUtf16: 0, endUtf16: 6 } }],
    annotations: [{ referenceId: "reference", number: 1, comment: "Rewrite this", expanded: false }], nextAnnotationNumber: 2 };
  assert.notEqual(ready.submittedTurn, null);
  for (const mismatch of [{ sessionId: otherSessionId }, { projectId: "other" }, { generation: 0 }, { projectEpoch: 1 }]) {
    assert.equal(conversationReducer(ready, { ...action, ...mismatch }), ready);
  }
  const deleted = conversationReducer(ready, action);
  assert.deepEqual(deleted, { ...initialConversationState, backendGeneration: 1 });
  assert.equal(conversationInteractionState(deleted).createDisabled, false);
  assert.equal(conversationInteractionState(deleted).selectDisabled, false);
});

test("explicit cancellation preserves saved history but starts the next prompt with a new ID", () => {
  for (const accepted of [false, true]) {
    let state = conversationReducer(activeState("cancel this"), { type: "stop-requested", generation: 1 });
    state = conversationReducer(state, {
      type: "turn-failed", generation: 1, projectId, sessionId, requestId, cancelled: true,
      message: "The turn was stopped.", retryable: false,
      turnLifecycle: { turnId, state: accepted ? "interrupted" : null, accepted, persisted: accepted },
    });
    assert.equal(state.stopRequest?.status, "requesting");
    assert.equal(state.failure?.turnLifecycle?.accepted, accepted);
    assert.equal(state.failure?.retryable, false);
    assert.equal(state.draft, accepted ? "" : "cancel this");
    assert.deepEqual(nextTurnSubmission(state, () => otherTurnId), { turnId: otherTurnId, retry: false });
    state = conversationReducer(state, { type: "backend-generation-changed", generation: 2 });
    state = conversationReducer(state, { type: "conversation-selected", generation: 2, projectId, sessionId, preserveDraft: true });
    assert.deepEqual(nextTurnSubmission(state, () => otherTurnId), { turnId: otherTurnId, retry: false }, "restart does not revive an explicitly cancelled ID");
  }
  const cancelled = { ...transcriptTurn(2, otherTurnId, "interrupted"), failureCode: "cancelled" as const };
  assert.equal(latestRetryableTranscriptTurn([cancelled]), null);
  assert.equal(latestRetryableTranscriptTurn([transcriptTurn(1, turnId, "failed"), cancelled])?.turnId, turnId);
});

test("only the current accepted event clears annotation drafts while the model remains active", () => {
  const reference = { referenceId: "reference", kind: "chat" as const, text: "source text",
    chat: { projectId, sessionId, turnId: otherTurnId, role: "assistant" as const,
      messageFingerprint: "a".repeat(64), startUtf16: 0, endUtf16: 11 } };
  let draft = conversationReducer(selectedState(""), { type: "reference-added", generation: 1, reference });
  draft = conversationReducer(draft, { type: "annotation-changed", generation: 1, referenceId: "reference", comment: "Explain this claim." });
  const sentText = composeTurnText(draft.draft, draft.annotations);
  const context = { projectId, rootPath: "/tmp/project", permissionMode: "ask" as const, requestedThinkingMode: "normal" as const,
    skillReferences: [], projectRules: { text: "rules", fingerprint: "b".repeat(64) }, references: [reference] };
  const started = conversationReducer(draft, { type: "turn-started", generation: 1, requestId, projectId, sessionId, turnId, text: sentText, submittedContext: context });
  assert.equal(started.annotations.length, 1, "request dispatch does not mean acceptance");
  const rejected = conversationReducer(started, { type: "turn-failed", generation: 1, requestId, projectId, sessionId,
    message: "pending write rejected", retryable: true, turnLifecycle: { turnId, state: null, accepted: false, persisted: false } });
  assert.deepEqual(rejected.annotations, draft.annotations);
  assert.deepEqual(rejected.draftReferences, [reference]);
  const accepted = { type: "turn-accepted" as const, generation: 1, projectEpoch: 0, requestId, projectId, sessionId, turnId };
  for (const mismatch of [{ generation: 0 }, { projectEpoch: 1 }, { requestId: retryRequestId }, { sessionId: otherSessionId }, { turnId: otherTurnId }, { projectId: "other" }]) {
    assert.equal(conversationReducer(started, { ...accepted, ...mismatch }), started);
  }
  const running = conversationReducer(started, accepted);
  assert.notEqual(running.activeTurn, null, "acceptance does not finish the turn");
  assert.equal(running.draft, "");
  assert.deepEqual(running.draftReferences, []);
  assert.deepEqual(running.annotations, []);
  assert.deepEqual(running.submittedContext, context, "saved source context is not cleared");
  const failed = conversationReducer(running, { type: "turn-failed", generation: 1, requestId, projectId, sessionId,
    message: "model failed", retryable: true, turnLifecycle: { turnId, state: "failed", accepted: true, persisted: true } });
  assert.equal(failed.failure?.draftPreserved, false);
  assert.equal(turnSubmissionText(failed), sentText);
  assert.deepEqual(nextTurnSubmission(failed, () => otherTurnId), { turnId, retry: true });
  const retry = conversationReducer(failed, { type: "turn-started", generation: 1, requestId: retryRequestId, projectId, sessionId, turnId,
    text: turnSubmissionText(failed), submittedContext: failed.submittedContext });
  assert.deepEqual(retry.annotations, []);
  assert.deepEqual(retry.submittedContext, context);
});

test("an uncertain send reconciles its durable turn ID after reconnect without restoring history annotations", () => {
  let state = activeState("original composite request");
  state = conversationReducer(state, { type: "backend-generation-changed", generation: 2 });
  state = conversationReducer(state, { type: "project-opened", generation: 2, projectEpoch: 1, preserveDraft: true });
  state = conversationReducer(state, { type: "conversation-selected", generation: 2, projectEpoch: 1, projectId, sessionId, preserveDraft: true });
  assert.deepEqual(nextTurnSubmission(state, () => otherTurnId), { turnId, retry: true }, "no matching transcript record is not permission to duplicate the turn");
  assert.equal(conversationReducer(state, { type: "turn-acceptance-reconciled", generation: 2, projectEpoch: 1, projectId, sessionId,
    turnId: otherTurnId, state: "interrupted" }), state);
  state = conversationReducer(state, { type: "turn-acceptance-reconciled", generation: 2, projectEpoch: 1, projectId, sessionId, turnId, state: "interrupted" });
  assert.equal(state.draft, "");
  assert.equal(state.submittedTurn?.accepted, true);
  state = conversationReducer(state, { type: "retry-target-restored", generation: 2, projectEpoch: 1, projectId, sessionId, turnId,
    userText: "original composite request", state: "interrupted", message: "interrupted", retryable: true,
    submittedContext: { projectId, rootPath: "/tmp/project", permissionMode: "ask", requestedThinkingMode: "normal", skillReferences: [],
      projectRules: { text: "rules", fingerprint: "b".repeat(64) }, references: [{ referenceId: "saved", kind: "chat", text: "saved source",
        chat: { projectId, sessionId, turnId: otherTurnId, role: "assistant", messageFingerprint: "a".repeat(64), startUtf16: 0, endUtf16: 12 } }] } });
  assert.equal(state.draft, "");
  assert.deepEqual(state.draftReferences, []);
  assert.deepEqual(state.annotations, []);
  assert.equal(state.submittedContext?.references.length, 1);
  assert.equal(turnSubmissionText(state), "original composite request");
  state = conversationReducer(state, { type: "draft-changed", draft: "new question" });
  assert.deepEqual(nextTurnSubmission(state, () => otherTurnId), { turnId: otherTurnId, retry: false });
  assert.equal(turnSubmissionText(state), "new question");
});
