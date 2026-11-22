import assert from "node:assert/strict";
import test from "node:test";
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
} from "../src/lib/approvalOwner.ts";
import { applyReducerOnce } from "../src/lib/reducerOnce.ts";
import type { ApprovalRequiredDto } from "../src/protocol.ts";

type State = ApprovalOwnerState<string>;

const NOW = Date.parse("2026-08-28T04:00:30.000Z");

function approvalFor(parentRequestId: string): ApprovalRequiredDto {
  return {
    approvalId: `approval-${parentRequestId}`,
    parentRequestId,
    turnId: "turn-1",
    command: "printf safe",
    description: "Return deterministic output.",
    executionTimeoutSeconds: 5,
    createdAt: "2026-08-28T04:00:00.000Z",
    expiresAt: "2026-08-28T04:01:00.000Z",
  };
}

function receive(state: State, requestId: string, parentRequestId: string, turnRequestId: string | null = null) {
  return receiveApprovalEvent(state, {
    generation: 3, requestId, turnRequestId, data: approvalFor(parentRequestId), now: NOW, owner: "owner-1",
  });
}

test("bibliography.add approval: owner registered, accepted, kept while running, cleared once finished", () => {
  const idle: State = initialApprovalOwnerState();
  // (a) issuing the request registers it as an approval owner.
  const issued = registerApprovalRequest(idle, "citation", "req-add");
  assert.equal(issued.citationRequestId, "req-add");
  // (b) an approval.required carrying that request id is accepted and becomes pending.
  const received = receive(issued, "req-add", "req-add");
  assert.equal(received.accepted, true);
  assert.equal(received.state.pending?.approvalId, "approval-req-add");
  assert.equal(received.state.pending?.generation, 3);
  assert.equal(received.state.owner, "owner-1");
  // (c) while the add request is still running, stale clearing leaves the dialog open.
  assert.equal(clearStaleApproval(received.state, null), received.state);
  // (d) after the add request finished (no approval resolve), the same approval is stale and cleared.
  const forgotten = forgetApprovalRequest(received.state, "citation");
  const cleared = clearStaleApproval(forgotten, null);
  assert.equal(cleared.pending, null);
  assert.equal(cleared.resolving, false);
});

test("finishing the bibliography.add request closes the approval it raised and releases the owner", () => {
  const issued = registerApprovalRequest(initialApprovalOwnerState<string>(), "citation", "req-add");
  const shown = receive(issued, "req-add", "req-add").state;
  const finished = finishApprovalRequest(shown, "citation", "req-add");
  assert.equal(finished.pending, null);
  assert.equal(finished.owner, null);
  assert.equal(finished.citationRequestId, null);
});

test("(e) approval.required with a non-matching requestId is not accepted", () => {
  const issued = registerApprovalRequest(initialApprovalOwnerState<string>(), "citation", "req-add");
  const wrongRequest = receive(issued, "req-other", "req-other");
  assert.equal(wrongRequest.accepted, false);
  assert.equal(wrongRequest.state, issued);
  const wrongParent = receive(issued, "req-add", "req-other");
  assert.equal(wrongParent.accepted, false);
  const noOwnerAtAll = receive(initialApprovalOwnerState<string>(), "req-add", "req-add");
  assert.equal(noOwnerAtAll.accepted, false);
});

test("a second approval is ignored while one is already shown", () => {
  const issued = registerApprovalRequest(initialApprovalOwnerState<string>(), "citation", "req-add");
  const shown = receive(issued, "req-add", "req-add").state;
  const second = receive(shown, "req-add", "req-add");
  assert.equal(second.accepted, false);
  assert.equal(second.state, shown);
});

test("document request owner: accepted, kept while running, cleared when the operation finishes", () => {
  const issued = registerApprovalRequest(initialApprovalOwnerState<string>(), "document", "req-doc");
  assert.equal(receive(issued, "req-other", "req-other").accepted, false);
  const received = receive(issued, "req-doc", "req-doc");
  assert.equal(received.accepted, true);
  assert.equal(clearStaleApproval(received.state, null), received.state);
  const finished = finishApprovalRequest(received.state, "document", "req-doc");
  assert.equal(finished.pending, null);
  assert.equal(finished.owner, null);
  assert.equal(finished.documentRequestId, null);
  // A finished request that never raised the approval leaves the shown approval alone.
  const unrelated = finishApprovalRequest(received.state, "document", "req-else");
  assert.equal(unrelated.pending, received.state.pending);
});

test("turn request owner: accepted for the active turn only, stale once the turn ends", () => {
  const idle: State = initialApprovalOwnerState();
  assert.equal(receive(idle, "req-turn", "req-turn", "req-active").accepted, false);
  assert.equal(receive(idle, "req-turn", "req-turn", null).accepted, false);
  const received = receive(idle, "req-turn", "req-turn", "req-turn");
  assert.equal(received.accepted, true);
  assert.equal(clearStaleApproval(received.state, "req-turn"), received.state);
  const stale = clearStaleApproval(received.state, null);
  assert.equal(stale.pending, null);
  assert.equal(stale.owner, "owner-1", "stale clearing keeps the owner so the dialog can return focus");
  assert.equal(clearStaleApproval(received.state, "req-next").pending, null);
});

test("an unexpired check still applies through the owner module", () => {
  const issued = registerApprovalRequest(initialApprovalOwnerState<string>(), "citation", "req-add");
  const expired = receiveApprovalEvent(issued, {
    generation: 3, requestId: "req-add", turnRequestId: null, data: approvalFor("req-add"),
    now: Date.parse("2026-08-28T04:01:00.000Z"), owner: "owner-1",
  });
  assert.equal(expired.accepted, false);
});

test("resolve target requires owner, no resolve in flight, no Stop, and the expected id", () => {
  const issued = registerApprovalRequest(initialApprovalOwnerState<string>(), "citation", "req-add");
  const shown = receive(issued, "req-add", "req-add").state;
  assert.equal(approvalToResolve(shown, false)?.owner, "owner-1");
  assert.equal(approvalToResolve(shown, false, "approval-req-add")?.approval.approvalId, "approval-req-add");
  assert.equal(approvalToResolve(shown, false, "approval-old"), null);
  assert.equal(approvalToResolve(shown, true), null, "Stop pending");
  assert.equal(approvalToResolve(dropApprovalOwner(shown), false), null, "owner released");
  assert.equal(approvalToResolve(initialApprovalOwnerState<string>(), false), null);
  const resolving = beginApprovalResolve(shown);
  assert.equal(resolving.resolving, true);
  assert.equal(approvalToResolve(resolving, false), null, "already resolving");
  assert.equal(beginApprovalResolve(resolving), resolving);
});

test("clearApproval is the single close: it always resets resolving and optionally releases the owner", () => {
  const issued = registerApprovalRequest(initialApprovalOwnerState<string>(), "citation", "req-add");
  const resolving = beginApprovalResolve(receive(issued, "req-add", "req-add").state);
  const keep = clearApproval(resolving);
  assert.deepEqual([keep.pending, keep.resolving, keep.owner], [null, false, "owner-1"]);
  const drop = clearApproval(resolving, true);
  assert.deepEqual([drop.pending, drop.resolving, drop.owner], [null, false, null]);
  assert.equal(clearApproval(drop), drop, "clearing an idle state changes nothing");
  assert.equal(clearApproval(issued, true), issued);
});

test("a reducer runs exactly once per action and its single result feeds the ref and React state", () => {
  let calls = 0;
  const reducer = (state: number, action: { add: number }): number => { calls += 1; return state + action.add; };
  const ref = { current: 0 };
  const published: number[] = [];
  const publish = (next: number) => { published.push(next); };
  assert.equal(applyReducerOnce(reducer, ref, publish, { add: 2 }), 2);
  assert.equal(calls, 1);
  assert.equal(applyReducerOnce(reducer, ref, publish, { add: 3 }), 5);
  assert.equal(calls, 2);
  assert.equal(ref.current, 5);
  assert.deepEqual(published, [2, 5]);
  // An ignored action (same state back) is still one call and publishes nothing.
  const ignored = applyReducerOnce((state: number) => { calls += 1; return state; }, ref, publish, { add: 0 });
  assert.equal(ignored, 5);
  assert.equal(calls, 3);
  assert.deepEqual(published, [2, 5]);
});
