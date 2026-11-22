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

/**
 * Monaco options that depend on the zoomed size. A line height of 0 lets Monaco
 * derive it from the font size, so zoomed lines never overlap; the editor uses
 * this for both create() and every updateOptions().
 */
export function editorFontOptions(fontSize: number): { fontSize: number; lineHeight: 0 } {
  return { fontSize, lineHeight: 0 };
}

export type ZoomKey = "Equal" | "NumpadAdd" | "Minus" | "NumpadSubtract" | "Digit0" | "Numpad0";

/** The key chords of each zoom step, as Ctrl/Cmd (plus Shift where listed) and one key. */
export const ZOOM_CHORDS: Record<ZoomStep, readonly { shift: boolean; key: ZoomKey }[]> = {
  in: [{ shift: false, key: "Equal" }, { shift: true, key: "Equal" }, { shift: false, key: "NumpadAdd" }],
  out: [{ shift: false, key: "Minus" }, { shift: false, key: "NumpadSubtract" }],
  reset: [{ shift: false, key: "Digit0" }, { shift: false, key: "Numpad0" }],
};

/** Monaco keybindings for a step, built from Monaco's own KeyMod and KeyCode values. */
export function zoomKeybindings(
  step: ZoomStep,
  mod: { CtrlCmd: number; Shift: number },
  code: Record<ZoomKey, number>,
): number[] {
  return ZOOM_CHORDS[step].map(({ shift, key }) => mod.CtrlCmd | (shift ? mod.Shift : 0) | code[key]);
}
