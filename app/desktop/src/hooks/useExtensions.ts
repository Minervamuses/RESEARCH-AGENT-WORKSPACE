import { useCallback, useState } from "react";
import type { SnapshotExtensionTransition } from "../backend.ts";
import {
  applyExtensionSnapshotTransition,
  createExtensionFlow,
  interruptExtensionFlow,
  markExtensionRestarting,
  observeExtensionRevision,
  updateExtensionFlowFor,
  type ExtensionFlow,
} from "../lib/extensionFlow.ts";

/**
 * Owns the extension preview/apply flow. All transitions are the pure functions
 * in lib/extensionFlow.ts; this hook only holds the state they act on.
 */
export function useExtensions() {
  const [flow, setFlow] = useState<ExtensionFlow | null>(null);
  const reset = useCallback(() => setFlow(null), []);
  const start = useCallback((turnId: string) => setFlow(createExtensionFlow(turnId)), []);
  const interrupt = useCallback(
    () => setFlow((current) => current === null ? null : interruptExtensionFlow(current)),
    [],
  );
  const markRestarting = useCallback(
    () => setFlow((current) => current === null ? null : markExtensionRestarting(current)),
    [],
  );
  const applyTransition = useCallback(
    (transition: SnapshotExtensionTransition) =>
      setFlow((current) => applyExtensionSnapshotTransition(current, transition)),
    [],
  );
  const observeRevision = useCallback(
    (revision: number) => setFlow((current) => observeExtensionRevision(current, revision)),
    [],
  );
  const update = useCallback(
    (transform: (current: ExtensionFlow | null) => ExtensionFlow | null) => setFlow(transform),
    [],
  );
  const updateFor = useCallback(
    (triggerTurnId: string, transform: (current: ExtensionFlow) => ExtensionFlow) =>
      setFlow((current) => updateExtensionFlowFor(current, triggerTurnId, transform)),
    [],
  );
  return { flow, reset, start, interrupt, markRestarting, applyTransition, observeRevision, update, updateFor };
}
