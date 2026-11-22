import { useEffect, useRef } from "react";

import type { ApprovalRequiredDto } from "../protocol.ts";
import type { PendingApproval } from "../lib/approval.ts";
import { ModalDialog } from "./Modal.tsx";

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

  return (
    <ModalDialog
      as="div"
      backdropClassName={nonModal ? "document-approval-backdrop" : undefined}
      labelledBy="bash-approval-title"
      describedBy="bash-approval-description"
      modal={!nonModal}
      dismissible={!resolving}
      onDismiss={() => onResolve(false)}
      preventEscapeWhenBlocked
      blockEmptyTab
      dismissOnBackdrop
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
            "extension.install": "Install or update extension",
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
    </ModalDialog>
  );
}
