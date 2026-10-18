import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type MouseEvent,
} from "react";

import type {
  ApprovalRequiredDto,
  BashPermissionMode,
  ExtensionApplyDto,
  ExtensionPreviewDto,
  JsonObject,
  TurnLifecycleDetailsDto,
} from "./protocol.ts";

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

interface ExtensionApplyRequest extends JsonObject {
  previewId: string;
  approvedBindingHashes: string[];
  turnId: string;
  retry: boolean;
}

export interface PendingApproval extends ApprovalRequiredDto {
  generation: number;
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

export function acceptApprovalEvent(
  generation: number,
  requestId: string,
  activeRequestId: string | null,
  data: ApprovalRequiredDto,
  now = Date.now(),
  activeTurnId?: string,
): PendingApproval | null {
  const createdAt = Date.parse(data.createdAt);
  const expiresAt = Date.parse(data.expiresAt);
  if (
    activeRequestId === null ||
    requestId !== activeRequestId ||
    data.parentRequestId !== requestId ||
    (activeTurnId !== undefined && data.turnId !== activeTurnId) ||
    !Number.isFinite(createdAt) ||
    !Number.isFinite(expiresAt) ||
    createdAt > expiresAt ||
    now >= expiresAt
  ) {
    return null;
  }
  return { ...data, generation };
}

interface ApprovalDialogProps {
  approval: PendingApproval | ApprovalRequiredDto;
  resolving: boolean;
  onResolve: (approved: boolean) => void;
  returnFocus: () => void;
  allowDocumentEditing?: boolean;
  onStop?: () => void;
  stopping?: boolean;
  stopError?: string;
}

export function ApprovalDialog({
  approval,
  resolving,
  onResolve,
  returnFocus,
  allowDocumentEditing = false,
  onStop,
  stopping = false,
  stopError,
}: ApprovalDialogProps) {
  const nonModal = allowDocumentEditing || approval.operation !== undefined;
  const denyRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    denyRef.current?.focus();
    return returnFocus;
  }, [returnFocus]);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      if (!resolving) onResolve(false);
      return;
    }
    if (event.key !== "Tab" || nonModal) return;
    const controls = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("button:not(:disabled)"));
    const first = controls[0], last = controls.at(-1);
    if (first === undefined || last === undefined) { event.preventDefault(); return; }
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  const onBackdropMouseDown = (event: MouseEvent<HTMLDivElement>) => {
    if (!nonModal && event.target === event.currentTarget && !resolving) onResolve(false);
  };

  return (
    <div className={nonModal ? "approval-backdrop document-approval-backdrop" : "approval-backdrop"} onMouseDown={onBackdropMouseDown}>
      <div
        className="approval-dialog"
        role="dialog"
        aria-modal={!nonModal}
        aria-labelledby="bash-approval-title"
        aria-describedby="bash-approval-description"
        onKeyDown={onKeyDown}
      >
        <p className="section-kicker">ONE-TIME OPERATION</p>
        <h2 id="bash-approval-title">{approval.operation === undefined ? "Allow this Bash command?" : "Allow this operation?"}</h2>
        <p id="bash-approval-description">{approval.description}</p>
        <dl className="approval-context">
          {approval.operation === undefined ? <>
            <div><dt>Exact command</dt><dd><code>{approval.command}</code></dd></div>
            <div><dt>Execution timeout</dt><dd>{approval.executionTimeoutSeconds} seconds</dd></div>
          </> : <>
            <div><dt>Action</dt><dd>{{
              "document.apply": "Save document edit", "document.undo": "Undo document edit",
              "citation.save": "Save citation batch", "knowledge.init_workspace": "Initialize index",
              "knowledge.ingest_file": "Import file", "knowledge.ingest_folder": "Import folder",
              "knowledge.prune_apply": "Prune index", "mcp.call": "Call MCP tool",
              "extension.install": "Install or update extension", "extensions.apply": "Apply extension changes",
            }[approval.operation]}</dd></div>
            <div><dt>Target</dt><dd><code>{approval.targetPath}</code></dd></div>
            {approval.parametersSummary !== undefined && <div><dt>Parameters</dt><dd><pre>{approval.parametersSummary}</pre></dd></div>}
          </>}
          <div>
            <dt>Approval expires</dt>
            <dd>{approval.expiresAt}</dd>
          </div>
        </dl>
        <p className="approval-note">This decision applies once to this exact pending request. Closing or leaving this conversation denies it.</p>
        {stopError !== undefined && <p className="error-text" role="alert">{stopError}</p>}
        <div className="approval-actions">
          <button
            ref={denyRef}
            type="button"
            autoFocus
            disabled={resolving}
            onClick={() => onResolve(false)}
          >
            Deny
          </button>
          <button
            className="primary-button"
            type="button"
            disabled={resolving}
            onClick={() => onResolve(true)}
          >
            Approve
          </button>
          {onStop !== undefined && <button type="button" disabled={stopping} onClick={onStop}>
            {stopping ? "Stopping…" : "Stop"}
          </button>}
        </div>
      </div>
    </div>
  );
}

export interface BashPermissionControlProps {
  mode: BashPermissionMode;
  disabled: boolean;
  onChange: (mode: BashPermissionMode) => void;
}

export function BashPermissionControl({
  mode,
  disabled,
  onChange,
}: BashPermissionControlProps) {
  return (
    <label className="bash-permission-control">
      Permission
      <select
        aria-label="Permission"
        title={disabled ? "The current turn keeps its starting mode. Change the mode after it finishes." : "Applies to document edits, Bash, citation saves, indexing, MCP and extensions."}
        value={mode}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value as BashPermissionMode)}
      >
        <option value="ask">Ask</option>
        <option value="bypass">Bypass</option>
      </select>
    </label>
  );
}

export function ThinkingControl({ mode, disabled, onChange }: {
  mode: "normal" | "extended"; disabled: boolean; onChange: (mode: "normal" | "extended") => void;
}) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const label = mode === "normal" ? "Normal" : "Extended";
  useEffect(() => {
    if (disabled) setOpen(false);
    else if (open) menu.current?.querySelector<HTMLElement>('[aria-checked="true"]')?.focus();
  }, [disabled, open]);
  const close = () => { setOpen(false); trigger.current?.focus(); };
  return <div className="thinking-control" onBlur={(event) => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false);
  }} onKeyDown={(event) => {
    if (event.key === "Escape" && open) { event.preventDefault(); close(); }
  }}>
    <button ref={trigger} className="thinking-trigger" type="button" disabled={disabled}
      aria-label={"Thinking: " + label} aria-haspopup="menu" aria-expanded={open}
      title={"Thinking: " + label + (disabled ? ". The current turn keeps its starting mode." : ". Document and citation tasks use Normal when required.")}
      onClick={() => setOpen(!open)}
      onKeyDown={(event) => {
        if (event.key === "ArrowDown" && !disabled) { event.preventDefault(); setOpen(true); }
      }}>
      <svg aria-hidden="true" viewBox="0 0 20 20" width="18" height="18"><path d="m10 2 2.1 5.9L18 10l-5.9 2.1L10 18l-2.1-5.9L2 10l5.9-2.1Z" fill="none" stroke="currentColor" strokeWidth="1.5" /></svg>
      <span>{label}</span>
    </button>
    <div ref={menu} className="thinking-options" role="menu" aria-label="Thinking mode" hidden={!open}
      onKeyDown={(event) => {
        if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        const options = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("button"));
        const current = options.indexOf(document.activeElement as HTMLButtonElement);
        const next = event.key === "Home" ? 0 : event.key === "End" ? options.length - 1
          : (current + (event.key === "ArrowDown" ? 1 : -1) + options.length) % options.length;
        options[next]?.focus();
      }}>
      {(["normal", "extended"] as const).map((value) => <button type="button" role="menuitemradio"
        aria-checked={mode === value} tabIndex={mode === value ? 0 : -1} disabled={disabled} key={value}
        onClick={() => { close(); onChange(value); }}>{value === "normal" ? "Normal" : "Extended"}</button>)}
    </div>
  </div>;
}

export function reconcileBashPermissionAck(
  generation: number,
  activeGeneration: number,
  selectedSessionId: string,
  ack: { sessionId: string; bashPermissionMode: BashPermissionMode },
): BashPermissionMode | null {
  if (generation !== activeGeneration) return null;
  if (ack.sessionId !== selectedSessionId) return null;
  if (ack.bashPermissionMode !== "ask" && ack.bashPermissionMode !== "bypass") return null;
  return ack.bashPermissionMode;
}

interface ExtensionPanelProps {
  flow: ExtensionFlow;
  busy: boolean;
  canRestart: boolean;
  permissionMode?: BashPermissionMode;
  onPreview: () => void;
  onDecision: (
    bindingHash: string,
    decision: Exclude<ExtensionBindingDecision, null>,
  ) => void;
  onApply: () => void;
  onRestart: () => void;
}

export function ExtensionPanel({
  flow,
  busy,
  canRestart,
  permissionMode = "ask",
  onPreview,
  onDecision,
  onApply,
  onRestart,
}: ExtensionPanelProps) {
  const approvedHashes = permissionMode === "bypass" && flow.preview !== null
    ? flow.preview.bindings.map((binding) => binding.bindingHash) : approvedBindingHashes(flow);
  const preview = flow.preview;

  return (
    <section className="extension-card" aria-labelledby="extension-flow-title">
      <p className="section-kicker">EXTENSION MANAGEMENT</p>
      <h3 id="extension-flow-title">Review local extension changes</h3>

      {flow.phase === "ready" && <>
        <p>Previewing may contact the configured model provider. Apply uses this preview. Ask requires a decision for each exact MCP binding; Bypass skips those consent choices.</p>
        <button className="primary-button" type="button" disabled={busy} onClick={onPreview}>Preview proposed extensions</button>
      </>}

      {flow.phase === "previewing" && <p role="status" aria-live="polite">Preparing a bounded extension preview…</p>}

      {flow.phase === "review" && preview !== null && <>
        <p>{preview.summary}</p>
        <div className="extension-summary">
          <strong>Proposed skills</strong>
          <span>{preview.proposedSkills.length > 0 ? preview.proposedSkills.join(", ") : "None"}</span>
        </div>
        {preview.bindings.length === 0
          ? <p className="extension-empty-bindings">This preview contains no MCP command bindings.</p>
          : <div className="extension-bindings">{preview.bindings.map((binding) => <fieldset className="extension-binding" key={binding.bindingHash}>
            <legend>{binding.name} · {binding.server}</legend>
            <dl>
              <div><dt>Command</dt><dd><code>{binding.command}</code></dd></div>
              <div><dt>Arguments</dt><dd>{binding.arguments.length > 0 ? binding.arguments.map((argument, index) => <code key={`${binding.bindingHash}-argument-${index}`}>{argument}</code>) : "None"}</dd></div>
              <div><dt>Working directory</dt><dd><code>{binding.workingDirectory}</code></dd></div>
              <div><dt>Environment names</dt><dd>{binding.environmentNames.length > 0 ? binding.environmentNames.join(", ") : "None"}</dd></div>
              <div><dt>Binding hash</dt><dd><code>{binding.bindingHash}</code></dd></div>
            </dl>
            {permissionMode === "ask" && <div className="binding-decision" role="radiogroup" aria-label={`Decision for ${binding.name}`}>
              <label><input type="radio" name={`extension-${binding.bindingHash}`} checked={flow.decisions[binding.bindingHash] === "deny"} disabled={busy} onChange={() => onDecision(binding.bindingHash, "deny")} /> Deny</label>
              <label><input type="radio" name={`extension-${binding.bindingHash}`} checked={flow.decisions[binding.bindingHash] === "approve"} disabled={busy} onChange={() => onDecision(binding.bindingHash, "approve")} /> Approve</label>
            </div>}
          </fieldset>)}</div>}
        <button className="primary-button" type="button" disabled={busy || approvedHashes === null} onClick={onApply}>{permissionMode === "bypass" ? "Apply changes" : "Apply reviewed changes"}</button>
        {approvedHashes === null && <p className="extension-decision-note">Choose Approve or Deny for every binding before applying.</p>}
      </>}

      {flow.phase === "applying" && <p role="status" aria-live="polite">Applying the current valid preview…</p>}

      {(flow.phase === "applied" || flow.phase === "restarting" || flow.phase === "awaiting-load" || flow.phase === "loaded") && flow.report !== null && <>
        <p role="status" aria-live="polite">
          {flow.phase === "loaded"
            ? `Extension revision ${flow.report.appliedRevision} is loaded.`
            : flow.phase === "restarting"
              ? `Restarting the backend to load extension revision ${flow.report.appliedRevision}…`
              : flow.phase === "awaiting-load"
                ? `The backend restarted. Create or select a conversation to verify extension revision ${flow.report.appliedRevision}.`
                : `Extension revision ${flow.report.appliedRevision} was applied${flow.report.restartRequired ? " and requires a backend restart" : ""}.`}
        </p>
        <ul className="extension-outcomes">{flow.report.items.map((item, index) => <li key={`${item.key}-${index}`}><strong>{item.key} · {item.outcome}</strong><span>{item.detail}</span></li>)}</ul>
        {flow.report.diagnostics.length > 0 && <details className="extension-diagnostics"><summary>Apply diagnostics</summary><ul>{flow.report.diagnostics.map((item, index) => <li key={index}>{item}</li>)}</ul></details>}
        {flow.report.restartRequired && flow.phase === "applied" && <button className="primary-button" type="button" disabled={busy || !canRestart} onClick={onRestart}>Restart backend and load revision</button>}
      </>}

      {flow.phase === "error" && <>
        <p className="extension-error" role="alert">{flow.error ?? "The extension operation could not be completed."}</p>
        {flow.applyRequest === null
          ? <button type="button" disabled={busy} onClick={onPreview}>Retry preview</button>
          : <>
            <p>The saved result was not delivered. Nothing will replay unless you choose recovery.</p>
            <button type="button" disabled={busy} onClick={onApply}>Recover saved apply result</button>
          </>}
      </>}
    </section>
  );
}
