import type { DocumentContextDto, DocumentResultDto, Reference, SubmittedContext } from "../protocol.ts";

export function documentReference(snapshot: DocumentContextDto, referenceId: string): Reference {
  const { rangeStartUtf16: start, rangeEndUtf16: end, sourceText } = snapshot;
  if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start! < 0 || end! <= start! || end! > sourceText.length) {
    throw new Error("Select document text before adding a reference.");
  }
  let startLine = 1, endLine = 1;
  for (const newline of sourceText.matchAll(/\r\n|\r|\n/g)) {
    const boundary = newline.index + newline[0].length;
    if (boundary <= start!) startLine += 1;
    if (boundary < end!) endLine += 1;
  }
  return { referenceId, kind: "document", text: sourceText.slice(start, end), document: {
    snapshot: { ...structuredClone(snapshot), rangeStartUtf16: start!, rangeEndUtf16: end! },
    startLine, endLine,
  } };
}

export function backgroundDocumentContext(snapshot: DocumentContextDto | null): DocumentContextDto | undefined {
  if (snapshot === null) return undefined;
  const { rangeStartUtf16: _start, rangeEndUtf16: _end, ...background } = snapshot;
  return { ...background };
}

export function documentContextPayload(value: DocumentContextDto): DocumentContextDto {
  const { rangeStartUtf16, rangeEndUtf16, ...context } = value;
  return {
    ...context,
    ...(typeof rangeStartUtf16 === "number" && typeof rangeEndUtf16 === "number"
      ? { rangeStartUtf16, rangeEndUtf16 } : {}),
  };
}

export function reconcileSavedDocument(
  current: DocumentContextDto,
  captured: DocumentContextDto,
  saved: { sourceText: string; diskFingerprint: string; editorRevision?: number; rangeStartUtf16?: number; rangeEndUtf16?: number },
  agentOperation: boolean,
): DocumentContextDto {
  if (current.editorRevision !== captured.editorRevision || current.sourceText !== captured.sourceText) {
    return { ...current, diskFingerprint: saved.diskFingerprint };
  }
  return {
    ...current, sourceText: saved.sourceText, diskFingerprint: saved.diskFingerprint,
    editorRevision: saved.editorRevision ?? current.editorRevision + Number(saved.sourceText !== current.sourceText),
    ...(agentOperation ? { rangeStartUtf16: saved.rangeStartUtf16, rangeEndUtf16: saved.rangeEndUtf16 } : {}),
  };
}

export interface DocumentAction {
  turnId: string;
  callId?: string;
  undoOfCallId?: string;
  parentRequestId?: string;
  sourceSnapshot?: DocumentContextDto;
}

export type WorkingDocumentSources = Pick<SubmittedContext, "documentContext" | "references">;

export function submittedDocumentSource(context: WorkingDocumentSources | null, referenceId?: string): DocumentContextDto | undefined {
  if (referenceId === undefined) return context?.documentContext;
  const reference = context?.references.find((item) => item.referenceId === referenceId);
  if (reference?.kind !== "document") throw new Error("The document proposal names an unavailable document reference.");
  return reference.document.snapshot;
}

export function documentOperationContext(current: DocumentContextDto, source?: DocumentContextDto): DocumentContextDto {
  if (source === undefined) return current;
  return { ...current, rangeStartUtf16: source.rangeStartUtf16, rangeEndUtf16: source.rangeEndUtf16 };
}

export function advanceWorkingDocumentSources(
  working: WorkingDocumentSources | null, before: DocumentContextDto, result: DocumentResultDto,
): WorkingDocumentSources | null {
  if (working === null || result.status !== "saved" || result.path !== before.path ||
      result.rootPath !== before.rootPath || result.sourceText === undefined || result.editorRevision === undefined ||
      result.diskFingerprint === undefined || result.rangeEndUtf16 === undefined) return working;
  const start = before.rangeStartUtf16 ?? 0, end = before.rangeEndUtf16 ?? before.sourceText.length;
  const newEnd = result.rangeEndUtf16, delta = newEnd - end;
  const advance = (snapshot: DocumentContextDto, activeDocument = false): DocumentContextDto => {
    if (snapshot.path !== before.path || snapshot.rootPath !== before.rootPath || snapshot.sourceText !== before.sourceText ||
        snapshot.editorRevision !== before.editorRevision || snapshot.diskFingerprint !== before.diskFingerprint) return snapshot;
    let left = activeDocument ? result.rangeStartUtf16 : snapshot.rangeStartUtf16;
    let right = activeDocument ? result.rangeEndUtf16 : snapshot.rangeEndUtf16;
    if (!activeDocument && left !== undefined && right !== undefined && right > start) {
      if (left >= end) { left += delta; right += delta; }
      else { left = Math.min(left, start); right = Math.max(newEnd, right + delta); }
    }
    return { ...snapshot, sourceText: result.sourceText!, editorRevision: result.editorRevision!, diskFingerprint: result.diskFingerprint!,
      rangeStartUtf16: left, rangeEndUtf16: right };
  };
  return { documentContext: working.documentContext === undefined ? undefined : advance(working.documentContext, true),
    references: working.references.map((reference) => reference.kind === "document"
      ? { ...reference, document: { ...reference.document, snapshot: advance(reference.document.snapshot) as typeof reference.document.snapshot } } : reference) };
}

export interface DocumentConflict {
  action: DocumentAction | null;
  result: DocumentResultDto;
  base: DocumentContextDto;
}

export type DocumentResultPlan =
  /** The editor now shows a different file: apply nothing. */
  | { kind: "ignore" }
  /** The backend answered for a different source than the one submitted. */
  | { kind: "mismatch" }
  | {
    kind: "saved";
    advanceSources: boolean;
    baseline: DocumentContextDto;
    document: DocumentContextDto;
    /** `set` replaces the last action (undo clears it); `null` leaves it alone. */
    lastAction: { set: DocumentAction | null } | null;
  }
  | { kind: "conflict" | "failed"; conflict: DocumentConflict; notice: string }
  | { kind: "cancelled"; notice: string };

/** Decides how a document.save / document.apply result changes the editor, baseline and conflict state. */
export function planDocumentResult(
  result: DocumentResultDto,
  captured: DocumentContextDto,
  current: DocumentContextDto | null,
  action: DocumentAction | null,
  submitted: DocumentContextDto | null,
): DocumentResultPlan {
  if (current === null || current.path !== captured.path || current.rootPath !== captured.rootPath) {
    return { kind: "ignore" };
  }
  if (result.path !== captured.path || (result.rootPath !== undefined && result.rootPath !== captured.rootPath)) {
    return { kind: "mismatch" };
  }
  if (result.status === "saved" && result.sourceText !== undefined && result.diskFingerprint !== undefined) {
    const unchangedSinceSubmit = current.editorRevision === captured.editorRevision &&
      current.sourceText === captured.sourceText;
    return {
      kind: "saved",
      advanceSources: action?.callId !== undefined && action.sourceSnapshot !== undefined,
      baseline: { ...captured, sourceText: result.sourceText, diskFingerprint: result.diskFingerprint },
      document: unchangedSinceSubmit
        ? reconcileSavedDocument(current, captured, {
          sourceText: result.sourceText, diskFingerprint: result.diskFingerprint,
          editorRevision: result.editorRevision,
          rangeStartUtf16: result.rangeStartUtf16, rangeEndUtf16: result.rangeEndUtf16,
        }, action !== null)
        : { ...current, diskFingerprint: result.diskFingerprint },
      lastAction: action?.undoOfCallId !== undefined ? { set: null }
        : action?.callId !== undefined ? { set: action } : null,
    };
  }
  if (result.status === "conflict" || result.status === "failed") {
    const base = action?.sourceSnapshot ?? (action !== null ? submitted : null) ?? captured;
    return {
      kind: result.status,
      conflict: { result, action, base },
      notice: result.status === "conflict"
        ? "The editor or disk changed. Choose which version to keep."
        : result.issue ?? "Save failed. The editor and candidate are retained.",
    };
  }
  return { kind: "cancelled", notice: result.issue ?? "Operation cancelled. Your current text is retained." };
}

export type ConflictResolutionPlan =
  /** Re-send the agent operation with the user's choice. */
  | { kind: "apply"; action: DocumentAction; expectedSnapshot: DocumentContextDto | undefined }
  /** Adopt the disk fingerprint the backend expected, then save again. */
  | { kind: "save-again"; diskFingerprint: string }
  | { kind: "editor-changed"; notice: string }
  | { kind: "dismiss" }
  | { kind: "no-document" };

export function planConflictResolution(
  conflict: DocumentConflict,
  resolution: "keep" | "use" | "cancel",
  current: DocumentContextDto | null,
): ConflictResolutionPlan {
  const { action, result } = conflict;
  if (action !== null) return { kind: "apply", action, expectedSnapshot: result.expectedSnapshot };
  if (resolution === "use" && result.expectedSnapshot !== undefined) {
    if (current === null) return { kind: "no-document" };
    if (current.editorRevision !== result.expectedSnapshot.editorRevision ||
        current.sourceText !== result.expectedSnapshot.sourceText) {
      return { kind: "editor-changed", notice: "The editor changed again. Save again to review the current conflict." };
    }
    return { kind: "save-again", diskFingerprint: result.expectedSnapshot.diskFingerprint };
  }
  return { kind: "dismiss" };
}
