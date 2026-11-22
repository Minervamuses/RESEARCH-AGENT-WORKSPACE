import type { ApprovalRequiredDto } from "../protocol.ts";
import { acceptApprovalEvent, approvalHasLiveOwner, type PendingApproval } from "./approval.ts";

/**
 * Pure state for the single pending approval: which approval is shown, whether it is being
 * resolved, which operation owner may resolve it, and which out-of-turn requests (a document
 * operation, a bibliography.add) may still raise one. The turn request id lives in the
 * conversation reducer, so callers pass it in where it matters. Every transition returns the
 * same object when nothing changed, so the React wrapper can skip redundant renders.
 */
export interface ApprovalOwnerState<Owner> {
  pending: PendingApproval | null;
  resolving: boolean;
  owner: Owner | null;
  documentRequestId: string | null;
  citationRequestId: string | null;
}

export type ApprovalRequestKind = "document" | "citation";

export function initialApprovalOwnerState<Owner>(): ApprovalOwnerState<Owner> {
  return { pending: null, resolving: false, owner: null, documentRequestId: null, citationRequestId: null };
}

const requestField = {
  document: "documentRequestId",
  citation: "citationRequestId",
} as const;

/** Register a request that may raise an approval (issuing bibliography.add, starting a document operation). */
export function registerApprovalRequest<Owner>(
  state: ApprovalOwnerState<Owner>,
  kind: ApprovalRequestKind,
  requestId: string,
): ApprovalOwnerState<Owner> {
  return state[requestField[kind]] === requestId ? state : { ...state, [requestField[kind]]: requestId };
}

/**
 * Forget a finished request and close any approval it raised, releasing the owner.
 * A missing id (the registration was already invalidated) changes nothing.
 */
export function finishApprovalRequest<Owner>(
  state: ApprovalOwnerState<Owner>,
  kind: ApprovalRequestKind,
  requestId: string | null | undefined,
): ApprovalOwnerState<Owner> {
  if (requestId === null || requestId === undefined) return state;
  const field = requestField[kind];
  const forgotten = state[field] === requestId ? { ...state, [field]: null } : state;
  return forgotten.pending?.parentRequestId === requestId ? clearApproval(forgotten, true) : forgotten;
}

/** Forget a request registration without touching the approval (workspace invalidation). */
export function forgetApprovalRequest<Owner>(
  state: ApprovalOwnerState<Owner>,
  kind: ApprovalRequestKind,
): ApprovalOwnerState<Owner> {
  return state[requestField[kind]] === null ? state : { ...state, [requestField[kind]]: null };
}

/** Release the owner so the shown approval can no longer be resolved. */
export function dropApprovalOwner<Owner>(state: ApprovalOwnerState<Owner>): ApprovalOwnerState<Owner> {
  return state.owner === null ? state : { ...state, owner: null };
}

/**
 * The one place an approval is closed. Callers that end the approval by resolving it or by
 * finishing its request also release the owner; other callers keep it, which is what lets the
 * dialog return focus to the composer when it unmounts.
 */
export function clearApproval<Owner>(state: ApprovalOwnerState<Owner>, dropOwner = false): ApprovalOwnerState<Owner> {
  const keepOwner = !dropOwner || state.owner === null;
  if (state.pending === null && !state.resolving && keepOwner) return state;
  return { ...state, pending: null, resolving: false, owner: keepOwner ? state.owner : null };
}

export interface ApprovalEventInput<Owner> {
  generation: number;
  requestId: string;
  /** Request id of the active turn, or null when no turn is running. */
  turnRequestId: string | null;
  data: ApprovalRequiredDto;
  now: number;
  /** Becomes the owner when the event is accepted. */
  owner: Owner;
}

export interface ApprovalEventResult<Owner> {
  state: ApprovalOwnerState<Owner>;
  accepted: boolean;
}

/**
 * Accept an `approval.required` only when it comes from the request that owns it (the
 * bibliography.add, the document operation, or else the active turn), is unexpired, and no
 * other approval is already shown.
 */
export function receiveApprovalEvent<Owner>(
  state: ApprovalOwnerState<Owner>,
  input: ApprovalEventInput<Owner>,
): ApprovalEventResult<Owner> {
  if (state.pending !== null) return { state, accepted: false };
  const expectedRequestId = input.requestId === state.citationRequestId ? state.citationRequestId
    : input.requestId === state.documentRequestId ? state.documentRequestId
    : input.turnRequestId;
  const pending = acceptApprovalEvent(input.generation, input.requestId, expectedRequestId, input.data, input.now);
  if (pending === null) return { state, accepted: false };
  return { state: { ...state, pending, owner: input.owner }, accepted: true };
}

/** Clear a shown approval when no request that can raise one is still in flight. */
export function clearStaleApproval<Owner>(
  state: ApprovalOwnerState<Owner>,
  turnRequestId: string | null,
): ApprovalOwnerState<Owner> {
  if (state.pending === null) return state;
  return approvalHasLiveOwner(state.pending.parentRequestId, {
    turnRequestId,
    documentRequestId: state.documentRequestId,
    citationRequestId: state.citationRequestId,
  }) ? state : clearApproval(state);
}

export interface ApprovalResolveTarget<Owner> {
  approval: PendingApproval;
  owner: Owner;
}

/** The approval a Deny/Approve click may resolve now, or null (no owner, already resolving, Stop pending, other id). */
export function approvalToResolve<Owner>(
  state: ApprovalOwnerState<Owner>,
  stopPending: boolean,
  expectedApprovalId?: string,
): ApprovalResolveTarget<Owner> | null {
  const { pending, owner } = state;
  if (pending === null || owner === null || state.resolving || stopPending ||
      (expectedApprovalId !== undefined && pending.approvalId !== expectedApprovalId)) return null;
  return { approval: pending, owner };
}

export function beginApprovalResolve<Owner>(state: ApprovalOwnerState<Owner>): ApprovalOwnerState<Owner> {
  return state.resolving ? state : { ...state, resolving: true };
}
