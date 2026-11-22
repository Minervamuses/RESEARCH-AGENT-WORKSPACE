import { memo, useLayoutEffect, useMemo, useRef, useState } from "react";

import { SafeContent as ContentRenderer } from "../SafeContent.tsx";
import type { Reference } from "../protocol.ts";
import { visibleMessageRange } from "../lib/transcript.ts";
import { AnnotationComment, type AnnotationControls } from "./Annotation.tsx";

// Unchanged history must not be reparsed when the composer or live activity updates.
export const SafeContent = memo(ContentRenderer);

export type MessageKind = "user" | "assistant" | "system" | "tool" | "tool-result";

/** The labelled card every transcript entry is built from. */
export function MessageCard({ kind, label, children }: { kind: MessageKind; label: string; children?: React.ReactNode }) {
  return <div className={`message ${kind}-message`}>
    <p className="message-label">{label}</p>
    {children}
  </div>;
}

export function ReferenceCards({ references, onRemove }: { references: readonly Reference[]; onRemove?: (id: string) => void }) {
  if (references.length === 0) return null;
  return <div className="reference-cards" aria-label={onRemove === undefined ? "Submitted references" : "Draft references"} data-reference-exclude>
    {references.map((reference) => <details className="reference-card" key={reference.referenceId}>
      <summary title={reference.kind === "document" ? reference.document.snapshot.path : undefined}><strong>{reference.kind === "document"
        ? `Document · ${reference.document.snapshot.path.split("/").at(-1)} · lines ${reference.document.startLine}–${reference.document.endLine}`
        : `Chat · ${reference.chat.role} · ${reference.chat.sessionId.slice(0, 8)} / ${reference.chat.turnId.slice(0, 8)}`}</strong>
        <span>{reference.text.replace(/\s+/g, " ").slice(0, 100)}{reference.text.length > 100 ? "…" : ""}</span></summary>
      <pre>{reference.text}</pre>
      <p className="reference-version">{reference.kind === "document"
        ? `Path ${reference.document.snapshot.path} · Root ${reference.document.snapshot.rootPath} · revision ${reference.document.snapshot.editorRevision} · disk ${reference.document.snapshot.diskFingerprint}`
        : `Project ${reference.chat.projectId} · UTF-16 ${reference.chat.startUtf16}–${reference.chat.endUtf16} · message ${reference.chat.messageFingerprint}`}</p>
      {onRemove !== undefined && <button type="button" onClick={() => onRemove(reference.referenceId)}>Remove reference</button>}
    </details>)}
  </div>;
}

export function MessageBody({ text, source, annotationControls }: { text: string; source?: { projectId: string; sessionId: string; turnId: string; role: "user" | "assistant" }; annotationControls?: AnnotationControls }) {
  const bodyRef = useRef<HTMLDivElement>(null);
  const [positions, setPositions] = useState<Record<string, { top: number; left: number }>>({});
  const references = useMemo(() => annotationControls?.references.filter((reference) => reference.kind === "chat" && source !== undefined &&
    reference.chat.projectId === source.projectId && reference.chat.sessionId === source.sessionId &&
    reference.chat.turnId === source.turnId && reference.chat.role === source.role &&
    annotationControls.annotations.some((item) => item.referenceId === reference.referenceId)) ?? [],
  [annotationControls?.references, annotationControls?.annotations, source?.projectId, source?.sessionId, source?.turnId, source?.role]);
  useLayoutEffect(() => {
    const root = bodyRef.current;
    if (root === null || references.length === 0) { setPositions({}); return; }
    const positionMarkers = () => {
      const bounds = root.getBoundingClientRect();
      const nodes: { node: Node; start: number; end: number }[] = [];
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
        const range = visibleMessageRange(root, node, 0, node, node.textContent?.length ?? 0);
        if (range !== null) nodes.push({ node, start: range.startUtf16, end: range.endUtf16 });
      }
      const next: Record<string, { top: number; left: number }> = {};
      for (const reference of references) {
        if (reference.kind !== "chat") continue;
        const end = reference.chat.endUtf16;
        const last = nodes.find((node) => node.start < end && node.end >= end) ?? nodes.filter((node) => node.end <= end).at(-1);
        if (last === undefined) continue;
        const offset = Math.min(end - last.start, last.node.textContent?.length ?? 0);
        const range = document.createRange();
        range.setStart(last.node, Math.max(0, offset - 1));
        range.setEnd(last.node, offset);
        const rect = range.getBoundingClientRect();
        next[reference.referenceId] = { top: rect.bottom - bounds.top,
          left: Math.max(0, Math.min(rect.right - bounds.left, root.clientWidth - 280)) };
      }
      setPositions(next);
    };
    positionMarkers();
    const observer = new ResizeObserver(positionMarkers);
    observer.observe(root);
    return () => observer.disconnect();
  }, [text, references]);
  return <div ref={bodyRef} className="reference-message-body" {...(source === undefined ? {} : {
    "data-reference-message": "", "data-project-id": source.projectId, "data-session-id": source.sessionId,
    "data-turn-id": source.turnId, "data-message-role": source.role,
  })}><SafeContent content={text} />
    {annotationControls && references.map((reference) => {
      const annotation = annotationControls.annotations.find((item) => item.referenceId === reference.referenceId);
      const position = positions[reference.referenceId];
      return annotation && position ? <div key={reference.referenceId} className="chat-annotation-anchor" data-reference-exclude style={position}>
        <AnnotationComment annotation={annotation} controls={annotationControls} />
      </div> : null;
    })}
  </div>;
}
