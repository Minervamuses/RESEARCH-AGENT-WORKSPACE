import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { useCallback, useEffect, useReducer, useRef } from "react";

import {
  BACKEND_EVENT_NAME,
  BackendClientError,
  type BackendActionName,
  type BackendSnapshot,
  type BoundedRuntimeDiagnostics,
  backendReducer,
  createBackendClient,
  initialBackendState,
  normalizeUiError,
  parseBridgeEvent,
  toBoundedDiagnostics,
} from "./backend.ts";
import type { RuntimeDiagnosticsDto, SessionCreatedDto } from "./protocol.ts";

const backendClient = createBackendClient({
  invoke: <T,>(command: string, args?: Record<string, unknown>) => invoke<T>(command, args),
});

const phaseLabels = {
  starting: "Starting backend",
  "backend-ready": "Backend ready",
  "session-ready": "Session ready",
  busy: "Working",
  degraded: "Needs attention",
  crashed: "Backend crashed",
  restarting: "Restarting backend",
  "shutting-down": "Shutting down",
  stopped: "Backend stopped",
} as const;

function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

function availabilityLabel(value: boolean | null): string {
  if (value === null) return "Not checked";
  return value ? "Available" : "Unavailable";
}

function configuredLabel(value: boolean): string {
  return value ? "Configured" : "Not configured";
}

function RuntimeDetails({ diagnostics }: { diagnostics: BoundedRuntimeDiagnostics }) {
  return (
    <details className="runtime-details">
      <summary>Local runtime details</summary>
      <dl>
        <div><dt>Python</dt><dd>{diagnostics.pythonVersion}</dd></div>
        <div><dt>Backend</dt><dd>{diagnostics.backendVersion}</dd></div>
        <div><dt>Protocol</dt><dd>v{diagnostics.protocolVersion}</dd></div>
        <div><dt>Conda environment</dt><dd>{diagnostics.condaEnvironment ?? "Not detected"}</dd></div>
        <div><dt>OpenRouter</dt><dd>{configuredLabel(diagnostics.openRouterConfigured)}</dd></div>
        <div><dt>OpenAlex</dt><dd>{configuredLabel(diagnostics.openAlexConfigured)}</dd></div>
        <div><dt>Ollama</dt><dd>{availabilityLabel(diagnostics.ollamaReachable)}</dd></div>
        <div><dt>Ollama model</dt><dd>{availabilityLabel(diagnostics.ollamaModelAvailable)}</dd></div>
        <div><dt>MCP</dt><dd>{diagnostics.mcpEnabled ? "Enabled" : "Disabled"}</dd></div>
        <div className="wide-detail">
          <dt>MCP families</dt>
          <dd>{diagnostics.mcpFamilies.length > 0 ? diagnostics.mcpFamilies.join(", ") : "None"}</dd>
        </div>
        <div className="wide-detail"><dt>App root</dt><dd>{diagnostics.appRoot}</dd></div>
        <div className="wide-detail"><dt>Working directory</dt><dd>{diagnostics.workingDirectory}</dd></div>
        <div className="wide-detail"><dt>Conda prefix</dt><dd>{diagnostics.condaPrefix ?? "Not detected"}</dd></div>
        <div className="wide-detail"><dt>Research store</dt><dd>{diagnostics.storePath}</dd></div>
        <div className="wide-detail"><dt>Citation output</dt><dd>{diagnostics.citationOutputPath}</dd></div>
      </dl>
    </details>
  );
}

function shutdownSummary(snapshot: BackendSnapshot | null): string | null {
  const report = snapshot?.lastShutdown;
  if (report === null || report === undefined) return null;
  if (report.kind === "not_running") return "The backend was already stopped.";
  if (report.kind === "forced") return "The backend was forced to stop; session flush is not confirmed.";
  if (report.flushed === true) return "The backend stopped gracefully and recent state was flushed.";
  if (report.flushed === false) return "The backend stopped gracefully, but recent state was not flushed.";
  return "The backend stopped gracefully; flush status is unavailable.";
}

export default function App() {
  const [state, dispatch] = useReducer(backendReducer, initialBackendState);
  const inFlight = useRef(false);
  const diagnosticsAttempt = useRef<number | null>(null);

  useEffect(() => {
    if (!isTauriRuntime()) {
      dispatch({ type: "browser-preview" });
      return;
    }

    let disposed = false;
    let removeListener: (() => void) | undefined;

    void (async () => {
      try {
        const unlisten = await listen<unknown>(BACKEND_EVENT_NAME, ({ payload }) => {
          if (disposed) return;
          try {
            const event = parseBridgeEvent(payload);
            if (event.type === "lifecycle") {
              dispatch({ type: "snapshot", snapshot: event.snapshot });
            } else {
              dispatch({ type: "protocol-event", message: event.message });
            }
          } catch (error) {
            dispatch({ type: "action-failed", error: normalizeUiError(error, "protocol") });
          }
        });
        if (disposed) {
          unlisten();
          return;
        }
        removeListener = unlisten;
        const snapshot = await backendClient.snapshot();
        if (!disposed) dispatch({ type: "snapshot", snapshot });
      } catch (error) {
        if (!disposed) {
          const safeError =
            error instanceof BackendClientError
              ? error.uiError
              : normalizeUiError(error, "transport");
          dispatch({ type: "action-failed", error: safeError });
        }
      }
    })();

    return () => {
      disposed = true;
      removeListener?.();
    };
  }, []);

  const runExclusive = useCallback(
    async (action: BackendActionName, operation: () => Promise<void>) => {
      if (inFlight.current) return;
      inFlight.current = true;
      dispatch({ type: "action-started", action });
      try {
        await operation();
      } catch (error) {
        const safeError =
          error instanceof BackendClientError
            ? error.uiError
            : normalizeUiError(error, "transport");
        dispatch({ type: "action-failed", error: safeError });
      } finally {
        inFlight.current = false;
      }
    },
    [],
  );

  const runLifecycle = useCallback(
    (action: "start" | "restart" | "shutdown") => {
      const operation =
        action === "start"
          ? backendClient.start
          : action === "restart"
            ? backendClient.restart
            : backendClient.shutdown;
      void runExclusive(action, async () => {
        const snapshot = await operation();
        dispatch({ type: "snapshot", snapshot });
        dispatch({ type: "action-completed", action });
      });
    },
    [runExclusive],
  );

  const loadDiagnostics = useCallback(
    (force: boolean) => {
      const generation = state.snapshot?.generation;
      if (generation === undefined || (!force && diagnosticsAttempt.current === generation)) return;
      diagnosticsAttempt.current = generation;
      void runExclusive("diagnostics", async () => {
        const data = await backendClient.request("runtime.diagnostics", {});
        dispatch({
          type: "diagnostics-succeeded",
          diagnostics: toBoundedDiagnostics(data as unknown as RuntimeDiagnosticsDto),
        });
      });
    },
    [runExclusive, state.snapshot?.generation],
  );

  useEffect(() => {
    if (
      state.phase === "backend-ready" &&
      state.snapshot?.lifecycle === "ready" &&
      state.diagnostics === null &&
      state.activeAction === null
    ) {
      loadDiagnostics(false);
    }
  }, [loadDiagnostics, state.activeAction, state.diagnostics, state.phase, state.snapshot?.lifecycle]);

  const createSession = useCallback(() => {
    void runExclusive("session", async () => {
      const data = await backendClient.request("session.create", { loadMcp: false });
      dispatch({ type: "session-created", session: data as unknown as SessionCreatedDto });
    });
  }, [runExclusive]);

  const idle = state.activeAction === null;
  const canStart =
    !state.browserPreview && idle && (state.snapshot === null || state.snapshot.lifecycle === "stopped");
  const canRestart =
    !state.browserPreview &&
    idle &&
    (state.phase === "crashed" || state.phase === "degraded" || state.snapshot?.childRunning === true);
  const canShutdown = !state.browserPreview && idle && state.snapshot?.childRunning === true;
  const canCreateSession =
    !state.browserPreview &&
    idle &&
    state.snapshot?.lifecycle === "ready" &&
    state.diagnostics !== null &&
    state.session === null;
  const shutdownMessage = shutdownSummary(state.snapshot);

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Research Agent workspace">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">R</span>
          <div>
            <p className="eyebrow">LOCAL WORKSPACE</p>
            <h1>Research Agent</h1>
          </div>
        </div>

        <button
          className="new-session-button"
          type="button"
          onClick={createSession}
          disabled={!canCreateSession}
          aria-describedby="session-control-help"
        >
          <span aria-hidden="true">＋</span>
          New session
        </button>
        <p id="session-control-help" className="visually-hidden">
          Available after the backend and local runtime checks are ready.
        </p>

        <section className="sidebar-section" aria-labelledby="workspace-label">
          <h2 id="workspace-label">Workspace</h2>
          <div className="workspace-item" aria-current="page">
            <span className="workspace-icon" aria-hidden="true">⌂</span>
            <span>
              <strong>Local research</strong>
              <small>{state.session === null ? "No active session" : "Current session"}</small>
            </span>
          </div>
        </section>

        <div className="sidebar-spacer" />
        <section className="backend-controls" aria-labelledby="backend-controls-title">
          <div className="sidebar-status" role="status" aria-live="polite">
            <span className={`status-dot status-${state.phase}`} aria-hidden="true" />
            <span>
              <strong id="backend-controls-title">{phaseLabels[state.phase]}</strong>
              <small>
                {state.snapshot === null
                  ? "Desktop process not observed"
                  : `Generation ${state.snapshot.generation} · ${state.snapshot.pendingRequests} pending`}
              </small>
            </span>
          </div>
          <div className="control-row">
            <button type="button" onClick={() => runLifecycle("start")} disabled={!canStart}>
              {state.error !== null && state.phase === "stopped" ? "Retry start" : "Start"}
            </button>
            <button type="button" onClick={() => runLifecycle("restart")} disabled={!canRestart}>
              Restart
            </button>
            <button type="button" onClick={() => runLifecycle("shutdown")} disabled={!canShutdown}>
              Shut down
            </button>
          </div>
        </section>
      </aside>

      <main className="main-workspace">
        <header className="workspace-header">
          <div>
            <p className="eyebrow">CURRENT SESSION</p>
            <h2>{state.session === null ? "Start a local research session" : "Local research session"}</h2>
          </div>
          <span className="header-status" role="status" aria-live="polite">
            {phaseLabels[state.phase]}
          </span>
        </header>

        <div className="workspace-body">
          {state.error !== null && (
            <section className="notice notice-error" aria-labelledby="recovery-title">
              <div className="notice-icon" aria-hidden="true">!</div>
              <div>
                <p className="section-kicker">{state.error.code}</p>
                <h3 id="recovery-title">
                  {state.phase === "crashed" ? "The local backend stopped unexpectedly" : "Action required"}
                </h3>
                <p>{state.error.message}</p>
                <div className="action-row">
                  {state.snapshot?.lifecycle === "ready" && state.diagnostics === null && (
                    <button type="button" onClick={() => loadDiagnostics(true)} disabled={!idle}>
                      Retry runtime check
                    </button>
                  )}
                  {(state.phase === "crashed" || state.phase === "degraded") && (
                    <button type="button" onClick={() => runLifecycle("restart")} disabled={!canRestart}>
                      Restart backend
                    </button>
                  )}
                  {canStart && (
                    <button type="button" onClick={() => runLifecycle("start")}>
                      Retry start
                    </button>
                  )}
                </div>
              </div>
            </section>
          )}

          {state.phase === "stopped" && state.error === null && (
            <section className="empty-state" aria-labelledby="stopped-title">
              <div className="hero-mark" aria-hidden="true">R</div>
              <p className="section-kicker">LOCAL · PRIVATE · ON THIS DEVICE</p>
              <h3 id="stopped-title">Your research workspace is ready to connect</h3>
              <p>
                Start the Linux backend, verify the local runtime, then create a session. No provider
                request is made by the runtime check.
              </p>
              <button className="primary-button" type="button" onClick={() => runLifecycle("start")} disabled={!canStart}>
                Start local backend
              </button>
              {shutdownMessage !== null && <p className="shutdown-summary">{shutdownMessage}</p>}
            </section>
          )}

          {(state.phase === "starting" || state.phase === "restarting" || state.phase === "shutting-down") && (
            <section className="empty-state" aria-labelledby="transition-title">
              <div className="spinner" aria-hidden="true" />
              <p className="section-kicker">DESKTOP BACKEND</p>
              <h3 id="transition-title">{phaseLabels[state.phase]}</h3>
              <p>Please keep this window open while the local process changes state.</p>
            </section>
          )}

          {state.phase === "busy" && (
            <section className="empty-state" aria-labelledby="busy-title">
              <div className="spinner" aria-hidden="true" />
              <p className="section-kicker">LOCAL REQUEST</p>
              <h3 id="busy-title">
                {state.activeAction === "session" ? "Creating your session" : "Checking the local runtime"}
              </h3>
              <p>This check stays on your device and does not call a model provider.</p>
            </section>
          )}

          {state.phase === "backend-ready" && state.diagnostics !== null && (
            <section className="setup-card" aria-labelledby="backend-ready-title">
              <div className="success-mark" aria-hidden="true">✓</div>
              <div>
                <p className="section-kicker">BACKEND READY</p>
                <h3 id="backend-ready-title">Create a session to begin</h3>
                <p>
                  The protocol and local runtime are ready. Provider configuration is reported below;
                  no provider request has been sent.
                </p>
                <div className="action-row">
                  <button className="primary-button" type="button" onClick={createSession} disabled={!canCreateSession}>
                    Create local session
                  </button>
                  <button type="button" onClick={() => runLifecycle("shutdown")} disabled={!canShutdown}>
                    Shut down
                  </button>
                </div>
                <RuntimeDetails diagnostics={state.diagnostics} />
              </div>
            </section>
          )}

          {state.phase === "session-ready" && state.session !== null && (
            <section className="session-surface" aria-labelledby="session-ready-title">
              <div className="session-intro">
                <p className="section-kicker">SESSION READY</p>
                <h3 id="session-ready-title">What would you like to research?</h3>
                <p>
                  The backend session is ready. Conversation controls arrive in the next desktop phase.
                </p>
              </div>
              <div className="composer-preview" aria-label="Conversation composer unavailable in this phase">
                <span>Ask about your research…</span>
                <button type="button" disabled aria-label="Send message unavailable">↑</button>
              </div>
              <p className="session-meta">
                Session {state.session.sessionId} · {state.session.turnCount} turns · Thinking {state.session.thinkingMode}
              </p>
            </section>
          )}

          {(state.phase === "degraded" || state.phase === "crashed") && state.diagnostics !== null && (
            <RuntimeDetails diagnostics={state.diagnostics} />
          )}
        </div>
      </main>
    </div>
  );
}
