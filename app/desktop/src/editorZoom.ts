// Editor font zoom (A6): 16px by default, 10–28px in 1px steps, remembered in
// this webview's localStorage. Storage may be missing or throw (private
// windows, blocked site data); the editor then simply uses 16px.

export const DEFAULT_EDITOR_FONT_SIZE = 16;
export const MIN_EDITOR_FONT_SIZE = 10;
export const MAX_EDITOR_FONT_SIZE = 28;
export const EDITOR_FONT_SIZE_KEY = "research-agent.editorFontSize";

export type ZoomStep = "in" | "out" | "reset";

export interface ZoomStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

function browserStorage(): ZoomStorage | null {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

/** The remembered size, or 16 when nothing valid is stored or storage fails. */
export function readEditorFontSize(storage: ZoomStorage | null = browserStorage()): number {
  try {
    const raw = storage?.getItem(EDITOR_FONT_SIZE_KEY) ?? null;
    if (raw === null || !/^\d{1,2}$/.test(raw)) return DEFAULT_EDITOR_FONT_SIZE;
    const size = Number(raw);
    return size >= MIN_EDITOR_FONT_SIZE && size <= MAX_EDITOR_FONT_SIZE ? size : DEFAULT_EDITOR_FONT_SIZE;
  } catch {
    return DEFAULT_EDITOR_FONT_SIZE;
  }
}

/** Remember a size; a failing storage only means it is not remembered. */
export function writeEditorFontSize(size: number, storage: ZoomStorage | null = browserStorage()): void {
  try {
    storage?.setItem(EDITOR_FONT_SIZE_KEY, String(size));
  } catch {
    // Keep the size for this editor only.
  }
}

/** Ctrl+= / Ctrl+− move one pixel within 10–28; Ctrl+0 returns to 16. */
export function zoomedFontSize(current: number, step: ZoomStep): number {
  if (step === "reset") return DEFAULT_EDITOR_FONT_SIZE;
  const next = current + (step === "in" ? 1 : -1);
  return Math.min(MAX_EDITOR_FONT_SIZE, Math.max(MIN_EDITOR_FONT_SIZE, next));
}
