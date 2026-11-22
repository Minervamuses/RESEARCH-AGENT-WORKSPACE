import type { BoundedRuntimeDiagnostics } from "../backend.ts";
import { SafeContent } from "./messageParts.tsx";
import { RuntimeDetails } from "./RuntimeDetails.tsx";

interface NoticeAction { disabled?: boolean; onClick: () => void }

/** The error card shown for a backend, workspace or turn failure; each present action renders one button. */
export function RecoveryNotice({ kicker, title, message, actions }: {
  kicker: string | undefined; title: string; message: string | undefined;
  actions: { retryTurn?: NoticeAction; retryRuntime?: NoticeAction; restart?: NoticeAction; start?: NoticeAction };
}) {
  return <section className="notice notice-error" aria-labelledby="recovery-title">
    <div className="notice-icon" aria-hidden="true">!</div>
    <div>
      <p className="section-kicker">{kicker}</p>
      <h3 id="recovery-title">{title}</h3>
      <p>{message}</p>
      <div className="action-row">
        {actions.retryTurn && <button type="button" onClick={actions.retryTurn.onClick} disabled={actions.retryTurn.disabled}>Retry saved turn</button>}
        {actions.retryRuntime && <button type="button" onClick={actions.retryRuntime.onClick} disabled={actions.retryRuntime.disabled}>Retry runtime check</button>}
        {actions.restart && <button type="button" onClick={actions.restart.onClick} disabled={actions.restart.disabled}>Restart backend</button>}
        {actions.start && <button type="button" onClick={actions.start.onClick}>Retry start</button>}
      </div>
    </div>
  </section>;
}

export function StopFailureNotice({ error, pendingMessage, restart, onRetryStop }: {
  error: string | null;
  /** The unsent message to show, or `null` when the Stop screen does not offer it. */
  pendingMessage: string | null;
  restart: NoticeAction | null;
  onRetryStop: () => void;
}) {
  return <section className="notice notice-error" role="alert">
    <div>
      <h3>The turn could not finish stopping</h3>
      <p>{error}</p>
      {pendingMessage !== null && <details><summary>Your message</summary><SafeContent content={pendingMessage} /></details>}
      <div className="action-row">
        <button type="button" onClick={onRetryStop}>Retry Stop</button>
        {restart && <button type="button" disabled={restart.disabled} onClick={restart.onClick}>Restart backend</button>}
      </div>
    </div>
  </section>;
}

export function HistoryNotice({ issue, disabled, onRefresh }: { issue: string; disabled: boolean; onRefresh: () => void }) {
  return <section className="notice history-notice" aria-live="polite">
    <div className="notice-icon" aria-hidden="true">!</div>
    <div>
      <p className="section-kicker">CONVERSATION NOT REFRESHED</p>
      <p>{issue}</p>
      <button type="button" onClick={onRefresh} disabled={disabled}>Refresh without resending</button>
    </div>
  </section>;
}

export function PreparingState() {
  return <section className="empty-state" role="status"><h3>Preparing your research workspace</h3><p>Connecting to the local backend. Choose a project when it is ready.</p></section>;
}

export function StoppedState({ canStart, shutdownMessage, onStart }: { canStart: boolean; shutdownMessage: string | null; onStart: () => void }) {
  return <section className="empty-state" aria-labelledby="stopped-title">
    <div className="hero-mark" aria-hidden="true">R</div>
    <h3 id="stopped-title">The local backend is stopped</h3>
    <button className="primary-button" type="button" onClick={onStart} disabled={!canStart}>Start local backend</button>
    {shutdownMessage !== null && <p className="shutdown-summary">{shutdownMessage}</p>}
  </section>;
}

export function TransitionState({ label }: { label: string }) {
  return <section className="empty-state" aria-labelledby="transition-title">
    <div className="spinner" aria-hidden="true" />
    <p className="section-kicker">DESKTOP BACKEND</p>
    <h3 id="transition-title">{label}</h3>
    <p>Please keep this window open while the local process changes state.</p>
  </section>;
}

export function LocalRequestState({ creatingSession }: { creatingSession: boolean }) {
  return <section className="empty-state" aria-labelledby="busy-title">
    <div className="spinner" aria-hidden="true" />
    <p className="section-kicker">LOCAL REQUEST</p>
    <h3 id="busy-title">{creatingSession ? "Creating your session" : "Checking the local runtime"}</h3>
    <p>This check stays on your device and does not call a model provider.</p>
  </section>;
}

export function BackendReadyCard({ diagnostics, canCreate, canShutdown, onCreate, onShutdown }: {
  diagnostics: BoundedRuntimeDiagnostics; canCreate: boolean; canShutdown: boolean; onCreate: () => void; onShutdown: () => void;
}) {
  return <section className="setup-card" aria-labelledby="backend-ready-title">
    <div className="success-mark" aria-hidden="true">✓</div>
    <div>
      <p className="section-kicker">BACKEND READY</p>
      <h3 id="backend-ready-title">Create a conversation to begin</h3>
      <p>The protocol and local runtime are ready. Creating or selecting a conversation starts enabled, configured MCP servers. No model request has been sent.</p>
      <div className="action-row">
        <button className="primary-button" type="button" onClick={onCreate} disabled={!canCreate}>Create local conversation</button>
        <button type="button" onClick={onShutdown} disabled={!canShutdown}>Shut down</button>
      </div>
      <RuntimeDetails diagnostics={diagnostics} />
    </div>
  </section>;
}
