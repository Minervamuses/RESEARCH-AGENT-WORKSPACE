import type { SnapshotExtensionTransition } from "../backend.ts";
import type {
  ExtensionApplyDto,
  ExtensionPreviewDto,
  JsonObject,
  PermissionMode,
  TurnLifecycleDetailsDto,
} from "../protocol.ts";

export type ExtensionBindingDecision = "approve" | "deny" | null;

export type ExtensionFlowPhase =
  | "ready"
  | "previewing"
  | "review"
  | "applying"
  | "applied"
  | "restarting"
  | "awaiting-load"
  | "loaded"
  | "error";

export interface ExtensionFlow {
  triggerTurnId: string;
  phase: ExtensionFlowPhase;
  preview: ExtensionPreviewDto | null;
  decisions: Record<string, ExtensionBindingDecision>;
  report: ExtensionApplyDto | null;
  applyRequest: ExtensionApplyRequest | null;
  error: string | null;
}

export interface ExtensionApplyRequest extends JsonObject {
  previewId: string;
  approvedBindingHashes: string[];
  turnId: string;
  retry: boolean;
}

export function createExtensionFlow(turnId: string): ExtensionFlow {
  return {
    triggerTurnId: turnId,
    phase: "ready",
    preview: null,
    decisions: {},
    report: null,
    applyRequest: null,
    error: null,
  };
}

export function beginExtensionPreview(flow: ExtensionFlow): ExtensionFlow {
  return {
    ...flow,
    phase: "previewing",
    preview: null,
    decisions: {},
    report: null,
    applyRequest: null,
    error: null,
  };
}

export function receiveExtensionPreview(
  flow: ExtensionFlow,
  preview: ExtensionPreviewDto,
): ExtensionFlow {
  return {
    ...flow,
    phase: "review",
    preview,
    decisions: Object.fromEntries(
      preview.bindings.map((binding) => [binding.bindingHash, null]),
    ),
    report: null,
    applyRequest: null,
    error: null,
  };
}

export function decideExtensionBinding(
  flow: ExtensionFlow,
  bindingHash: string,
  decision: Exclude<ExtensionBindingDecision, null>,
): ExtensionFlow {
  if (
    flow.phase !== "review" ||
    flow.preview === null ||
    !flow.preview.bindings.some((binding) => binding.bindingHash === bindingHash)
  ) {
    return flow;
  }
  return {
    ...flow,
    decisions: { ...flow.decisions, [bindingHash]: decision },
  };
}

export function approvedBindingHashes(flow: ExtensionFlow): string[] | null {
  if (flow.phase !== "review" || flow.preview === null) return null;
  if (flow.preview.bindings.some((binding) => {
    const decision = flow.decisions[binding.bindingHash];
    return decision !== "approve" && decision !== "deny";
  })) {
    return null;
  }
  return flow.preview.bindings
    .filter((binding) => flow.decisions[binding.bindingHash] === "approve")
    .map((binding) => binding.bindingHash);
}

export function beginExtensionApply(flow: ExtensionFlow, turnId: string): ExtensionFlow {
  const approved = approvedBindingHashes(flow);
  if (approved === null || flow.preview === null) return flow;
  return {
    ...flow,
    phase: "applying",
    applyRequest: {
      previewId: flow.preview.previewId,
      approvedBindingHashes: [...approved],
      turnId,
      retry: false,
    },
    error: null,
  };
}

export function beginExtensionApplyRecovery(flow: ExtensionFlow): ExtensionFlow {
  if (flow.phase !== "error" || flow.applyRequest === null) return flow;
  return {
    ...flow,
    phase: "applying",
    applyRequest: { ...flow.applyRequest, retry: true },
    error: null,
  };
}

export function extensionApplyRequest(flow: ExtensionFlow): ExtensionApplyRequest | null {
  if (flow.phase !== "applying" || flow.applyRequest === null) return null;
  return {
    ...flow.applyRequest,
    approvedBindingHashes: [...flow.applyRequest.approvedBindingHashes],
  };
}

export function receiveExtensionApply(
  flow: ExtensionFlow,
  report: ExtensionApplyDto,
): ExtensionFlow {
  if (flow.applyRequest === null || report.turnId !== flow.applyRequest.turnId) return flow;
  return { ...flow, phase: "applied", report, applyRequest: null, error: null };
}

export function markExtensionRestarting(flow: ExtensionFlow): ExtensionFlow {
  if (flow.report === null || !flow.report.restartRequired) return flow;
  return { ...flow, phase: "restarting", error: null };
}

export function markExtensionAwaitingLoad(flow: ExtensionFlow): ExtensionFlow {
  if (flow.report === null || flow.phase !== "restarting") return flow;
  return { ...flow, phase: "awaiting-load", error: null };
}

export function observeExtensionRevision(
  flow: ExtensionFlow | null,
  revision: number,
): ExtensionFlow | null {
  if (flow === null || flow.report === null) return flow;
  if (flow.report.appliedRevision !== revision) return flow;
  return { ...flow, phase: "loaded", error: null };
}

export function failExtensionFlow(flow: ExtensionFlow, message: string): ExtensionFlow {
  return { ...flow, phase: "error", error: message };
}

export function failExtensionApply(
  flow: ExtensionFlow,
  message: string,
  lifecycle?: TurnLifecycleDetailsDto,
): ExtensionFlow {
  if (lifecycle?.state === "failed" || lifecycle?.state === "interrupted") {
    return {
      ...flow,
      phase: "error",
      preview: null,
      decisions: {},
      report: null,
      applyRequest: null,
      error: message,
    };
  }
  return { ...flow, phase: "error", error: message };
}

export function interruptExtensionFlow(flow: ExtensionFlow): ExtensionFlow | null {
  if (flow.report !== null) return flow;
  if (flow.applyRequest === null) return null;
  return {
    ...flow,
    phase: "error",
    error: "The backend stopped before the saved extension result was delivered.",
  };
}

/** Applies the backend snapshot's extension transition to the flow (null stays null). */
export function applyExtensionSnapshotTransition(
  flow: ExtensionFlow | null,
  transition: SnapshotExtensionTransition,
): ExtensionFlow | null {
  if (flow === null || transition === "none") return flow;
  if (transition === "awaiting-load") return markExtensionAwaitingLoad(flow);
  const recoverable = interruptExtensionFlow(flow);
  if (recoverable === null || recoverable.report === null) return recoverable;
  if (transition === "interrupt-restarting") return markExtensionRestarting(recoverable);
  if (transition === "interrupt-awaiting-load") {
    return markExtensionAwaitingLoad(markExtensionRestarting(recoverable));
  }
  return recoverable;
}

/** A late result may only change the flow it was started for. */
export function updateExtensionFlowFor(
  flow: ExtensionFlow | null,
  triggerTurnId: string,
  update: (flow: ExtensionFlow) => ExtensionFlow,
): ExtensionFlow | null {
  return flow?.triggerTurnId === triggerTurnId ? update(flow) : flow;
}

export function canPreviewExtensions(flow: ExtensionFlow | null): flow is ExtensionFlow {
  return flow !== null && (flow.phase === "ready" || flow.phase === "error");
}

export function canRestartForExtensions(flow: ExtensionFlow | null): boolean {
  return flow?.phase === "applied" && flow.report?.restartRequired === true;
}

/** Builds the submitting flow and exact apply request; Bypass approves every previewed binding. */
export function planExtensionApply(
  flow: ExtensionFlow,
  permissionMode: PermissionMode | undefined,
  newTurnId: () => string,
): { submitting: ExtensionFlow; request: ExtensionApplyRequest } | null {
  const effective = permissionMode === "bypass" && flow.preview !== null
    ? {
      ...flow,
      decisions: Object.fromEntries(
        flow.preview.bindings.map((binding) => [binding.bindingHash, "approve" as const]),
      ),
    }
    : flow;
  const submitting = effective.phase === "error" && effective.applyRequest !== null
    ? beginExtensionApplyRecovery(effective)
    : beginExtensionApply(effective, newTurnId());
  const request = extensionApplyRequest(submitting);
  return request === null ? null : { submitting, request };
}

/** Records a delivered apply report only for the flow and request that sent it. */
export function settleExtensionApply(
  flow: ExtensionFlow | null,
  triggerTurnId: string,
  requestTurnId: string,
  report: ExtensionApplyDto,
  observedRevision: number,
): ExtensionFlow | null {
  if (flow?.triggerTurnId !== triggerTurnId || flow.applyRequest?.turnId !== requestTurnId) return flow;
  return observeExtensionRevision(receiveExtensionApply(flow, report), observedRevision);
}
