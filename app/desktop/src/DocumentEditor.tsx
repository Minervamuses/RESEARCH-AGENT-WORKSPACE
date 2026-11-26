import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { editor } from "monaco-editor/editor/editor.api";
import { citationFormatForPath, completionCandidates, completionPrefix, type BibliographyEntryDto } from "./citations.ts";
import { AnnotationComment, type AnnotationControls } from "./components/Annotation.tsx";
import {
  captureDocumentSelection,
  documentOffsetAt,
  documentPositionAt,
  applyDocumentChanges,
} from "./lib/documentSource.ts";
import type { DocumentContextDto } from "./protocol.ts";
import {
  editorFontOptions, readEditorFontSize, writeEditorFontSize, zoomedFontSize, zoomKeybindings, type ZoomStep,
} from "./editorZoom.ts";

interface DocumentEditorProps {
  value: DocumentContextDto | null;
  onChange: (snapshot: DocumentContextDto) => void;
  onSave: () => void;
  onAddReference?: (snapshot: DocumentContextDto) => void;
  annotationControls?: AnnotationControls;
  saveDisabled?: boolean;
  /** Bibliography entries offered after `[@`, `; @`, `\cite{` or a comma inside it. */
  citationEntries?: readonly BibliographyEntryDto[];
}

function modelSource(source: string): string {
  return source.startsWith("\uFEFF") ? source.slice(1) : source;
}

export function DocumentEditor({ value, onChange, onSave, onAddReference, annotationControls, saveDisabled = false, citationEntries }: DocumentEditorProps) {
  const surfaceRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const snapshotRef = useRef<DocumentContextDto | null>(value);
  const callbacksRef = useRef({ onChange, onSave, onAddReference, saveDisabled });
  const citationEntriesRef = useRef(citationEntries);
  citationEntriesRef.current = citationEntries;
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
      import("./monacoFeatures.ts"),
    ]).then(([monaco, { default: EditorWorker }]) => {
      if (disposed || !surfaceRef.current || !snapshotRef.current) return;
      globalThis.MonacoEnvironment = { getWorker: () => new EditorWorker() };
      const initial = snapshotRef.current;
      const model = monaco.editor.createModel(
        modelSource(initial.sourceText),
        /\.(md|markdown)$/i.test(initial.path) ? "markdown" : "plaintext",
      );
      let fontSize = readEditorFontSize();
      const instance = monaco.editor.create(surfaceRef.current, {
        model,
        automaticLayout: true,
        ariaLabel: "Document source editor",
        lineNumbers: "on",
        wordWrap: "on",
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        fontFamily: '"Cascadia Code", "Noto Sans Mono", monospace',
        ...editorFontOptions(fontSize),
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
      const citationFormat = citationFormatForPath(initial.path);
      const completion = citationFormat === null ? null : monaco.languages.registerCompletionItemProvider(model.getLanguageId(), {
        triggerCharacters: ["@", "{", ","],
        provideCompletionItems: (target, position) => {
          if (target !== model) return { suggestions: [] };
          const linePrefix = target.getLineContent(position.lineNumber).slice(0, position.column - 1);
          const prefix = completionPrefix(linePrefix, citationFormat);
          if (prefix === null) return { suggestions: [] };
          const range = {
            startLineNumber: position.lineNumber, endLineNumber: position.lineNumber,
            startColumn: position.column - prefix.length, endColumn: position.column,
          };
          return {
            suggestions: completionCandidates(citationEntriesRef.current ?? [], prefix).map((candidate) => ({
              label: candidate.key,
              kind: monaco.languages.CompletionItemKind.Reference,
              insertText: candidate.key,
              detail: candidate.detail,
              range,
            })),
          };
        },
      });
      const saveAction = instance.addAction({
        id: "workspace.document.save",
        label: "Save document",
        keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS],
        run: () => {
          if (!callbacksRef.current.saveDisabled) callbacksRef.current.onSave();
        },
      });
      // Editor-only zoom (A6): active while the editor has focus, remembered for the next start.
      const zoom = (step: ZoomStep) => {
        fontSize = zoomedFontSize(fontSize, step);
        instance.updateOptions(editorFontOptions(fontSize));
        writeEditorFontSize(fontSize);
      };
      const zoomActions = [
        instance.addAction({
          id: "workspace.editor.zoom-in", label: "Increase editor font size",
          keybindings: zoomKeybindings("in", monaco.KeyMod, monaco.KeyCode), run: () => zoom("in"),
        }),
        instance.addAction({
          id: "workspace.editor.zoom-out", label: "Decrease editor font size",
          keybindings: zoomKeybindings("out", monaco.KeyMod, monaco.KeyCode), run: () => zoom("out"),
        }),
        instance.addAction({
          id: "workspace.editor.zoom-reset", label: "Reset editor font size",
          keybindings: zoomKeybindings("reset", monaco.KeyMod, monaco.KeyCode), run: () => zoom("reset"),
        }),
      ];
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
        completion?.dispose();
        saveAction.dispose();
        for (const action of zoomActions) action.dispose();
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
