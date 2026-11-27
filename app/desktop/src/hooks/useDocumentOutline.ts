import { useCallback, useEffect, useRef, useState } from "react";
import {
  emptyOutlineDocument,
  OUTLINE_DEBOUNCE_MS,
  parseOutline,
  planOutlineUpdate,
  pruneCollapsedIds,
  toggleCollapsedId,
  type OutlineDocument,
  type OutlineSourceInput,
} from "../lib/outline/index.ts";
import type { DocumentContextDto } from "../protocol.ts";

export interface UseDocumentOutlineResult {
  outline: OutlineDocument;
  collapsedIds: ReadonlySet<string>;
  toggleCollapsed: (id: string) => void;
  setCollapsed: (id: string, collapsed: boolean) => void;
  /** Synchronously re-parse the current file (cancelling any pending debounce) and return the fresh outline. */
  refreshNow: (path: string, sourceText: string) => OutlineDocument;
}

export function useDocumentOutline(documentValue: DocumentContextDto | null): UseDocumentOutlineResult {
  const rootPath = documentValue?.rootPath ?? null;
  const path = documentValue?.path ?? null;
  const sourceText = documentValue?.sourceText ?? null;
  const currentFileKey = rootPath !== null && path !== null ? `${rootPath}\0${path}` : null;

  const initialInput: OutlineSourceInput | null = rootPath !== null && path !== null && sourceText !== null
    ? { rootPath, path, sourceText }
    : null;

  const [outlineState, setOutlineState] = useState<{ fileKey: string | null; outline: OutlineDocument }>(() => ({
    fileKey: currentFileKey,
    outline: initialInput ? parseOutline(initialInput.path, initialInput.sourceText) : emptyOutlineDocument(),
  }));
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(() => new Set());
  const prevInputRef = useRef<OutlineSourceInput | null>(initialInput);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cancelTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  // Depend ONLY on [rootPath, path, sourceText] so cursor/selection updates never re-parse.
  useEffect(() => {
    const nextInput: OutlineSourceInput | null = rootPath !== null && path !== null && sourceText !== null
      ? { rootPath, path, sourceText }
      : null;
    const plan = planOutlineUpdate(prevInputRef.current, nextInput);

    if (plan === "noop") {
      cancelTimer();
      return;
    }

    if (plan === "clear") {
      cancelTimer();
      prevInputRef.current = null;
      setOutlineState({ fileKey: null, outline: emptyOutlineDocument() });
      setCollapsedIds(new Set());
      return;
    }

    if (plan === "immediate" && nextInput !== null) {
      cancelTimer();
      prevInputRef.current = nextInput;
      setOutlineState({
        fileKey: `${nextInput.rootPath}\0${nextInput.path}`,
        outline: parseOutline(nextInput.path, nextInput.sourceText),
      });
      setCollapsedIds(new Set());
      return;
    }

    if (plan === "debounce" && nextInput !== null) {
      cancelTimer();
      timerRef.current = setTimeout(() => {
        timerRef.current = null;
        prevInputRef.current = nextInput;
        const parsed = parseOutline(nextInput.path, nextInput.sourceText);
        setOutlineState({ fileKey: `${nextInput.rootPath}\0${nextInput.path}`, outline: parsed });
        setCollapsedIds((prev) => pruneCollapsedIds(prev, parsed));
      }, OUTLINE_DEBOUNCE_MS);
    }
  }, [rootPath, path, sourceText, cancelTimer]);

  useEffect(() => cancelTimer, [cancelTimer]);

  const toggleCollapsed = useCallback((id: string) => {
    setCollapsedIds((prev) => toggleCollapsedId(prev, id));
  }, []);

  const setCollapsed = useCallback((id: string, collapsed: boolean) => {
    setCollapsedIds((prev) => {
      if (collapsed === prev.has(id)) return prev;
      const next = new Set(prev);
      if (collapsed) next.add(id);
      else next.delete(id);
      return next;
    });
  }, []);

  const refreshNow = useCallback((currentPath: string, currentSourceText: string): OutlineDocument => {
    cancelTimer();
    const parsed = parseOutline(currentPath, currentSourceText);
    const activeRoot = prevInputRef.current?.rootPath ?? rootPath ?? "";
    if (prevInputRef.current) {
      prevInputRef.current = { ...prevInputRef.current, path: currentPath, sourceText: currentSourceText };
    }
    setOutlineState({ fileKey: `${activeRoot}\0${currentPath}`, outline: parsed });
    setCollapsedIds((prev) => pruneCollapsedIds(prev, parsed));
    return parsed;
  }, [cancelTimer, rootPath]);

  const outline = outlineState.fileKey === currentFileKey ? outlineState.outline : emptyOutlineDocument();
  return { outline, collapsedIds, toggleCollapsed, setCollapsed, refreshNow };
}
