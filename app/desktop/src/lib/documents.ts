import type { DocumentContextDto, DocumentResultDto, Reference, SubmittedContext } from "../protocol.ts";
import type { DocumentSnapshot } from "./documentSource.ts";

export function documentReference(snapshot: DocumentSnapshot, referenceId: string): Reference {
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

export function backgroundDocumentContext(snapshot: DocumentSnapshot | null): DocumentSnapshot | undefined {
  if (snapshot === null) return undefined;
  const { rangeStartUtf16: _start, rangeEndUtf16: _end, ...background } = snapshot;
  return { ...background };
}

export function documentContextPayload(value: DocumentSnapshot): DocumentContextDto {
  const { rangeStartUtf16, rangeEndUtf16, ...context } = value;
  return {
    ...context,
    ...(typeof rangeStartUtf16 === "number" && typeof rangeEndUtf16 === "number"
      ? { rangeStartUtf16, rangeEndUtf16 } : {}),
  };
}

export function reconcileSavedDocument(
  current: DocumentSnapshot,
  captured: DocumentSnapshot,
  saved: { sourceText: string; diskFingerprint: string; editorRevision?: number; rangeStartUtf16?: number; rangeEndUtf16?: number },
  agentOperation: boolean,
): DocumentSnapshot {
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
  sourceSnapshot?: DocumentSnapshot;
}

export type WorkingDocumentSources = Pick<SubmittedContext, "documentContext" | "references">;

export function submittedDocumentSource(context: WorkingDocumentSources | null, referenceId?: string): DocumentSnapshot | undefined {
  if (referenceId === undefined) return context?.documentContext;
  const reference = context?.references.find((item) => item.referenceId === referenceId);
  if (reference?.kind !== "document") throw new Error("The document proposal names an unavailable document reference.");
  return reference.document.snapshot;
}

export function documentOperationContext(current: DocumentSnapshot, source?: DocumentSnapshot): DocumentSnapshot {
  if (source === undefined) return current;
  return { ...current, rangeStartUtf16: source.rangeStartUtf16, rangeEndUtf16: source.rangeEndUtf16 };
}

export function advanceWorkingDocumentSources(
  working: WorkingDocumentSources | null, before: DocumentSnapshot, result: DocumentResultDto,
): WorkingDocumentSources | null {
  if (working === null || result.status !== "saved" || result.path !== before.path ||
      result.rootPath !== before.rootPath || result.sourceText === undefined || result.editorRevision === undefined ||
      result.diskFingerprint === undefined || result.rangeEndUtf16 === undefined) return working;
  const start = before.rangeStartUtf16 ?? 0, end = before.rangeEndUtf16 ?? before.sourceText.length;
  const newEnd = result.rangeEndUtf16, delta = newEnd - end;
  const advance = (snapshot: DocumentSnapshot, activeDocument = false): DocumentSnapshot => {
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
