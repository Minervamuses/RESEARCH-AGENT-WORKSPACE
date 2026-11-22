import type { PermissionMode } from "../protocol.ts";
import {
  approvedBindingHashes,
  type ExtensionBindingDecision,
  type ExtensionFlow,
} from "../lib/extensionFlow.ts";

interface ExtensionPanelProps {
  flow: ExtensionFlow;
  busy: boolean;
  canRestart: boolean;
  permissionMode?: PermissionMode;
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
