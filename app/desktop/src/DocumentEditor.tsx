import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { editor, IPosition, IRange } from "monaco-editor/editor/editor.api";
import type { DraftAnnotation } from "./conversations.ts";
import type { Reference } from "./protocol.ts";

export interface AnnotationControls {
  annotations: readonly DraftAnnotation[];
  references: readonly Reference[];
  disabled: boolean;
  onChange: (referenceId: string, comment: string) => void;
  onToggle: (referenceId: string, expanded: boolean) => void;
  onRemove: (referenceId: string) => void;
}

export function handleAnnotationKey(event: {
  key: string; shiftKey: boolean; isComposing: boolean;
  preventDefault: () => void; stopPropagation: () => void;
}, confirm: () => void): void {
  event.stopPropagation();
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  confirm();
}

export function AnnotationComment({ annotation, controls }: { annotation: DraftAnnotation; controls: AnnotationControls }) {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const composingRef = useRef(false);
  useEffect(() => { if (annotation.expanded) inputRef.current?.focus(); }, [annotation.expanded]);
  return <div className="annotation-comment" data-reference-exclude onMouseDown={(event) => event.stopPropagation()}>
    <button className="annotation-number" type="button" aria-label={`Comment ${annotation.number}`}
      aria-expanded={annotation.expanded} disabled={controls.disabled}
      title={annotation.comment || "Add a request for this selection"}
      onClick={() => controls.onToggle(annotation.referenceId, !annotation.expanded)}>{annotation.number}</button>
    {annotation.expanded && <div className="annotation-popup">
      <label>Comment {annotation.number}<textarea ref={inputRef} rows={3} value={annotation.comment} disabled={controls.disabled}
        aria-label={`Comment ${annotation.number}`} placeholder="What should the agent do with this passage?"
        onChange={(event) => controls.onChange(annotation.referenceId, event.target.value)}
        onCompositionStart={() => { composingRef.current = true; }} onCompositionEnd={() => { composingRef.current = false; }}
        onKeyDown={(event) => handleAnnotationKey({ key: event.key, shiftKey: event.shiftKey,
          isComposing: composingRef.current || event.nativeEvent.isComposing || event.nativeEvent.keyCode === 229,
          preventDefault: () => event.preventDefault(), stopPropagation: () => event.stopPropagation(),
        }, () => controls.onToggle(annotation.referenceId, false))} /></label>
      <div className="annotation-actions">
        <button type="button" disabled={controls.disabled} onClick={() => controls.onToggle(annotation.referenceId, false)}>Done</button>
        <button type="button" disabled={controls.disabled} onClick={() => controls.onRemove(annotation.referenceId)}>Remove</button>
      </div>
      <p>Enter to confirm · Shift+Enter for a new line</p>
    </div>}
  </div>;
}

export interface DocumentSnapshot {
  rootPath: string;
  path: string;
  editorRevision: number;
  sourceText: string;
  diskFingerprint: string;
  rangeStartUtf16?: number;
  rangeEndUtf16?: number;
}

interface DocumentEditorProps {
  value: DocumentSnapshot | null;
  onChange: (snapshot: DocumentSnapshot) => void;
  onSave: () => void;
  onAddReference?: (snapshot: DocumentSnapshot) => void;
  annotationControls?: AnnotationControls;
  saveDisabled?: boolean;
}

interface SourceChange {
  range: IRange;
  text: string;
}

// Monaco columns use UTF-16 units, but its model normalizes newlines and hides a
// leading BOM. Resolve against the source so unrelated bytes survive an edit.
export function documentOffsetAt(source: string, position: IPosition): number {
  let start = source.startsWith("\uFEFF") ? 1 : 0;
  const newline = /\r\n|\r|\n/g;
  newline.lastIndex = start;
  for (let line = 1; line < position.lineNumber; line += 1) {
    const match = newline.exec(source);
    if (!match) return source.length;
    start = match.index + match[0].length;
  }
  newline.lastIndex = start;
  const end = newline.exec(source)?.index ?? source.length;
  return Math.min(end, start + Math.max(0, position.column - 1));
}

export function documentPositionAt(source: string, offset: number): IPosition {
  const target = Math.max(source.startsWith("\uFEFF") ? 1 : 0, Math.min(source.length, offset));
  let start = source.startsWith("\uFEFF") ? 1 : 0;
  let lineNumber = 1;
  const newline = /\r\n|\r|\n/g;
  newline.lastIndex = start;
  for (let match = newline.exec(source); match; match = newline.exec(source)) {
    const next = match.index + match[0].length;
    if (next > target) return { lineNumber, column: Math.min(target, match.index) - start + 1 };
    start = next;
    lineNumber += 1;
  }
  return { lineNumber, column: target - start + 1 };
}

export function applyDocumentChanges(source: string, changes: readonly SourceChange[]): string {
  const edits = changes.map(({ range, text }) => ({
    start: documentOffsetAt(source, { lineNumber: range.startLineNumber, column: range.startColumn }),
    end: documentOffsetAt(source, { lineNumber: range.endLineNumber, column: range.endColumn }),
    text,
  })).sort((left, right) => right.start - left.start);
  return edits.reduce((text, change) => text.slice(0, change.start) + change.text + text.slice(change.end), source);
}

export function captureDocumentSelection(snapshot: DocumentSnapshot | null): DocumentSnapshot | null {
  if (!snapshot) return null;
  const start = snapshot.rangeStartUtf16;
  const end = snapshot.rangeEndUtf16;
  if (start === undefined || end === undefined || !Number.isInteger(start) || !Number.isInteger(end)
    || start < 0 || start >= end || end > snapshot.sourceText.length) return null;
  // Every field is a string or number; a frozen copy cannot follow later editor changes.
  return Object.freeze({ ...snapshot, rangeStartUtf16: start, rangeEndUtf16: end });
}

function modelSource(source: string): string {
  return source.startsWith("\uFEFF") ? source.slice(1) : source;
}

export function DocumentEditor({ value, onChange, onSave, onAddReference, annotationControls, saveDisabled = false }: DocumentEditorProps) {
  const surfaceRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const snapshotRef = useRef<DocumentSnapshot | null>(value);
  const callbacksRef = useRef({ onChange, onSave, onAddReference, saveDisabled });
  const refreshReferenceActionRef = useRef<(() => void) | null>(null);
  const annotationControlsRef = useRef(annotationControls);
  const refreshAnnotationsRef = useRef<(() => void) | null>(null);
  const [annotationHosts, setAnnotationHosts] = useState<{ referenceId: string; node: HTMLDivElement }[]>([]);
  const incomingRef = useRef(false);
  const [selectionLabel, setSelectionLabel] = useState("Line 1, column 1");
  const [issue, setIssue] = useState<string | null>(null);
  callbacksRef.current = { onChange, onSave, onAddReference, saveDisabled };
  annotationControlsRef.current = annotationControls;

  useEffect(() => {
    snapshotRef.current = value;
    setIssue(null);
    setSelectionLabel("Line 1, column 1");
    if (!value || !surfaceRef.current) return;
    let disposed = false;
    let disposeEditor: (() => void) | undefined;
    // Keep the browser-only editor out of SSR helper imports. Workers are bundled
    // locally by Vite; opening a document never fetches an editor from a CDN.
    void Promise.all([
      import("monaco-editor/editor/editor.api"),
      import("monaco-editor/editor/editor.worker?worker"),
      import("monaco-editor/languages/definitions/markdown/register"),
    ]).then(([monaco, { default: EditorWorker }]) => {
      if (disposed || !surfaceRef.current || !snapshotRef.current) return;
      globalThis.MonacoEnvironment = { getWorker: () => new EditorWorker() };
      const initial = snapshotRef.current;
      const model = monaco.editor.createModel(
        modelSource(initial.sourceText),
        /\.(md|markdown)$/i.test(initial.path) ? "markdown" : "plaintext",
      );
      const instance = monaco.editor.create(surfaceRef.current, {
        model,
        automaticLayout: true,
        ariaLabel: "Document source editor",
        lineNumbers: "on",
        wordWrap: "on",
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        fontFamily: '"Cascadia Code", "Noto Sans Mono", monospace',
        fontSize: 14,
        lineHeight: 23,
        padding: { top: 12, bottom: 12 },
        tabSize: 4,
      });
      editorRef.current = instance;
      let selectedSnapshot = captureDocumentSelection(initial);
      const canAddReference = instance.createContextKey<boolean>("workspaceCanAddReference", false);
      const addSelection = () => {
        const captured = captureDocumentSelection(selectedSnapshot);
        if (captured) {
          callbacksRef.current.onAddReference?.(captured);
          instance.setPosition(documentPositionAt(captured.sourceText, captured.rangeEndUtf16!));
        }
      };
      const referenceButton = document.createElement("button");
      referenceButton.type = "button";
      referenceButton.className = "document-reference-action";
      referenceButton.textContent = "Add comment";
      referenceButton.title = "Comment on selection (Ctrl/Cmd+Alt+Enter)";
      referenceButton.setAttribute("aria-label", "Comment on selected document text");
      referenceButton.setAttribute("aria-keyshortcuts", "Control+Alt+Enter Meta+Alt+Enter");
      referenceButton.addEventListener("click", addSelection);
      const referenceWidget: editor.IContentWidget = {
        getId: () => "workspace.document.add-reference",
        getDomNode: () => referenceButton,
        suppressMouseDown: true,
        getPosition: () => selectedSnapshot && callbacksRef.current.onAddReference ? {
          position: documentPositionAt(selectedSnapshot.sourceText, selectedSnapshot.rangeEndUtf16!),
          preference: [monaco.editor.ContentWidgetPositionPreference.BELOW, monaco.editor.ContentWidgetPositionPreference.ABOVE],
        } : null,
      };
      instance.addContentWidget(referenceWidget);
      const annotationWidgets = new Map<string, { widget: editor.IContentWidget; node: HTMLDivElement }>();
      const refreshAnnotations = () => {
        const controls = annotationControlsRef.current;
        const references = controls?.references.filter((reference) => reference.kind === "document" &&
          reference.document.snapshot.path === initial.path && reference.document.snapshot.rootPath === initial.rootPath &&
          controls.annotations.some((annotation) => annotation.referenceId === reference.referenceId)) ?? [];
        let changed = false;
        for (const [id, entry] of annotationWidgets) {
          if (references.some((reference) => reference.referenceId === id)) continue;
          instance.removeContentWidget(entry.widget);
          annotationWidgets.delete(id);
          changed = true;
        }
        for (const reference of references) {
          if (reference.kind !== "document" || annotationWidgets.has(reference.referenceId)) continue;
          const node = document.createElement("div");
          node.className = "document-annotation-widget";
          const snapshot = reference.document.snapshot;
          const widget: editor.IContentWidget = {
            getId: () => `workspace.annotation.${reference.referenceId}`, getDomNode: () => node,
            allowEditorOverflow: true,
            getPosition: () => ({ position: documentPositionAt(snapshot.sourceText, snapshot.rangeEndUtf16!),
              preference: [monaco.editor.ContentWidgetPositionPreference.BELOW, monaco.editor.ContentWidgetPositionPreference.ABOVE] }),
          };
          annotationWidgets.set(reference.referenceId, { widget, node });
          instance.addContentWidget(widget);
          changed = true;
        }
        for (const entry of annotationWidgets.values()) instance.layoutContentWidget(entry.widget);
        if (changed) setAnnotationHosts(Array.from(annotationWidgets, ([referenceId, { node }]) => ({ referenceId, node })));
      };
      refreshAnnotationsRef.current = refreshAnnotations;
      refreshAnnotations();
      const refreshReferenceAction = () => {
        selectedSnapshot = captureDocumentSelection(snapshotRef.current);
        canAddReference.set(Boolean(selectedSnapshot && callbacksRef.current.onAddReference));
        instance.layoutContentWidget(referenceWidget);
      };
      refreshReferenceActionRef.current = refreshReferenceAction;
      const referenceAction = instance.addAction({
        id: "workspace.document.add-reference",
        label: "Comment on selection",
        keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyMod.Alt | monaco.KeyCode.Enter],
        precondition: "workspaceCanAddReference",
        contextMenuGroupId: "9_cutcopypaste",
        contextMenuOrder: 4,
        run: addSelection,
      });
      const publishSelection = () => {
        const current = snapshotRef.current;
        const selection = instance.getSelection();
        if (!current || !selection || incomingRef.current) return;
        const start = documentOffsetAt(current.sourceText, selection.getStartPosition());
        const end = documentOffsetAt(current.sourceText, selection.getEndPosition());
        const updated = {
          ...current,
          rangeStartUtf16: selection.isEmpty() ? undefined : start,
          rangeEndUtf16: selection.isEmpty() ? undefined : end,
        };
        snapshotRef.current = updated;
        refreshReferenceAction();
        setSelectionLabel(selection.isEmpty()
          ? `Line ${selection.positionLineNumber}, column ${selection.positionColumn}`
          : `Lines ${selection.startLineNumber}–${selection.endLineNumber} · selected source`);
        callbacksRef.current.onChange(updated);
      };
      const contentListener = model.onDidChangeContent((event) => {
        const current = snapshotRef.current;
        if (!current || incomingRef.current) return;
        snapshotRef.current = {
          ...current,
          editorRevision: current.editorRevision + 1,
          sourceText: applyDocumentChanges(current.sourceText, event.changes),
        };
        publishSelection();
      });
      const selectionListener = instance.onDidChangeCursorSelection(publishSelection);
      const saveAction = instance.addAction({
        id: "workspace.document.save",
        label: "Save document",
        keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS],
        run: () => {
          if (!callbacksRef.current.saveDisabled) callbacksRef.current.onSave();
        },
      });
      if (initial.rangeStartUtf16 !== undefined && initial.rangeEndUtf16 !== undefined) {
        const start = documentPositionAt(initial.sourceText, initial.rangeStartUtf16);
        const end = documentPositionAt(initial.sourceText, initial.rangeEndUtf16);
        instance.setSelection(new monaco.Selection(start.lineNumber, start.column, end.lineNumber, end.column));
      }
      refreshReferenceAction();
      disposeEditor = () => {
        if (refreshAnnotationsRef.current === refreshAnnotations) refreshAnnotationsRef.current = null;
        for (const entry of annotationWidgets.values()) instance.removeContentWidget(entry.widget);
        setAnnotationHosts([]);
        if (refreshReferenceActionRef.current === refreshReferenceAction) refreshReferenceActionRef.current = null;
        referenceButton.removeEventListener("click", addSelection);
        referenceAction.dispose();
        instance.removeContentWidget(referenceWidget);
        contentListener.dispose();
        selectionListener.dispose();
        saveAction.dispose();
        instance.dispose();
        model.dispose();
        if (editorRef.current === instance) editorRef.current = null;
      };
    }).catch((error: unknown) => {
      if (!disposed) setIssue(error instanceof Error ? error.message : "The source editor could not load.");
    });
    return () => {
      disposed = true;
      disposeEditor?.();
    };
    // Recreate only for a different file. Local edits must keep the same model,
    // cursor, focus and undo history while their controlled snapshot changes.
  }, [value?.rootPath, value?.path]);

  useEffect(() => {
    const current = snapshotRef.current;
    if (!value || !current || value.path !== current.path || value.rootPath !== current.rootPath) return;
    if (value.editorRevision < current.editorRevision) return;
    const instance = editorRef.current;
    const model = instance?.getModel();
    const changedSource = value.sourceText !== current.sourceText;
    const changedSelection = value.rangeStartUtf16 !== current.rangeStartUtf16
      || value.rangeEndUtf16 !== current.rangeEndUtf16;
    if (instance && model && (changedSource || changedSelection)) {
      incomingRef.current = true;
      try {
        if (changedSource) {
          instance.pushUndoStop();
          instance.executeEdits("workspace-document-operation", [{
            range: model.getFullModelRange(),
            text: modelSource(value.sourceText),
          }]);
          instance.pushUndoStop();
        }
        if (value.rangeStartUtf16 !== undefined && value.rangeEndUtf16 !== undefined) {
          const start = documentPositionAt(value.sourceText, value.rangeStartUtf16);
          const end = documentPositionAt(value.sourceText, value.rangeEndUtf16);
          const range = {
            startLineNumber: start.lineNumber, startColumn: start.column,
            endLineNumber: end.lineNumber, endColumn: end.column,
          };
          instance.setSelection(range);
          instance.revealRangeInCenterIfOutsideViewport(range);
          setSelectionLabel(`Lines ${start.lineNumber}–${end.lineNumber} · selected source`);
        }
      } finally {
        incomingRef.current = false;
      }
    }
    snapshotRef.current = value;
    refreshReferenceActionRef.current?.();
  }, [value, onAddReference]);

  useEffect(() => { refreshAnnotationsRef.current?.(); }, [annotationControls, annotationHosts]);

  return (
    <div className="document-editor">
      {!value && <p className="document-editor-empty">Choose a research folder and open a Markdown or .tex document.</p>}
      {issue && <p className="error-text" role="alert">Source editor: {issue}</p>}
      <div className="document-editor-surface" ref={surfaceRef} />
      {annotationControls && annotationHosts.map(({ referenceId, node }) => {
        const annotation = annotationControls.annotations.find((item) => item.referenceId === referenceId);
        return annotation ? createPortal(<AnnotationComment annotation={annotation} controls={annotationControls} />, node, referenceId) : null;
      })}
      {value && <div className="document-editor-status">{selectionLabel} · Source lines · Ctrl/Cmd+S to save</div>}
    </div>
  );
}
