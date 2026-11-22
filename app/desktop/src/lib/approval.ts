import type { ApprovalRequiredDto, PermissionMode } from "../protocol.ts";

export interface PendingApproval extends ApprovalRequiredDto {
  generation: number;
}

export function acceptApprovalEvent(
  generation: number,
  requestId: string,
  activeRequestId: string | null,
  data: ApprovalRequiredDto,
  now = Date.now(),
): PendingApproval | null {
  const createdAt = Date.parse(data.createdAt);
  const expiresAt = Date.parse(data.expiresAt);
  if (
    activeRequestId === null ||
    requestId !== activeRequestId ||
    data.parentRequestId !== requestId ||
    !Number.isFinite(createdAt) ||
    !Number.isFinite(expiresAt) ||
    createdAt > expiresAt ||
    now >= expiresAt
  ) {
    return null;
  }
  return { ...data, generation };
}

/** Requests that may own a pending approval: the active turn, a document operation,
 * and an out-of-turn bibliography.add (its citation.save approval). */
export interface ApprovalOwnerRequests {
  turnRequestId: string | null;
  documentRequestId: string | null;
  citationRequestId: string | null;
}

/** True while the request that raised this approval is still in flight. */
export function approvalHasLiveOwner(parentRequestId: string, owners: ApprovalOwnerRequests): boolean {
  return parentRequestId === owners.turnRequestId
    || parentRequestId === owners.documentRequestId
    || parentRequestId === owners.citationRequestId;
}

export type ApprovalExpiry = { kind: "expired" } | { kind: "wait"; delayMs: number };

/** Whether a pending approval is already past its deadline (deny now) or how long to wait before denying. */
export function approvalExpiry(expiresAt: string, now: number): ApprovalExpiry {
  const remaining = Date.parse(expiresAt) - now;
  return remaining <= 0 ? { kind: "expired" } : { kind: "wait", delayMs: remaining };
}

export function reconcilePermissionAck(
  generation: number,
  activeGeneration: number,
  selectedSessionId: string,
  ack: { sessionId: string; permissionMode: PermissionMode },
): PermissionMode | null {
  if (generation !== activeGeneration) return null;
  if (ack.sessionId !== selectedSessionId) return null;
  if (ack.permissionMode !== "ask" && ack.permissionMode !== "bypass") return null;
  return ack.permissionMode;
}
