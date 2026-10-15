import { useEffect, useRef, useState } from "react";
import type { editor, IPosition, IRange } from "monaco-editor/editor/editor.api";

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

function modelSource(source: string): string {
  return source.startsWith("\uFEFF") ? source.slice(1) : source;
}

export function DocumentEditor({ value, onChange, onSave, saveDisabled = false }: DocumentEditorProps) {
  const surfaceRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const snapshotRef = useRef<DocumentSnapshot | null>(value);
  const callbacksRef = useRef({ onChange, onSave, saveDisabled });
  const incomingRef = useRef(false);
  const [selectionLabel, setSelectionLabel] = useState("Line 1, column 1");
  const [issue, setIssue] = useState<string | null>(null);
  callbacksRef.current = { onChange, onSave, saveDisabled };

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
      disposeEditor = () => {
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
  }, [value]);

  return (
    <div className="document-editor">
      {!value && <p className="document-editor-empty">Choose a research folder and open a Markdown or .tex document.</p>}
      {issue && <p className="error-text" role="alert">Source editor: {issue}</p>}
      <div className="document-editor-surface" ref={surfaceRef} />
      {value && <div className="document-editor-status">{selectionLabel} · Source lines · Ctrl/Cmd+S to save</div>}
    </div>
  );
}
