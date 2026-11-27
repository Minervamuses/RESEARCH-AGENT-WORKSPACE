// Pure column-width persistence, clamping and drag/keyboard calculation for the
// desktop shell's vertical splitters (sidebar | main, document | conversation).

export const SIDEBAR_WIDTH_KEY = "research-agent.sidebarWidthPx";
export const DOCUMENT_RATIO_KEY = "research-agent.documentSplitRatio";

export const MIN_SIDEBAR_WIDTH = 160;
export const MAX_SIDEBAR_WIDTH = 420;
export const DEFAULT_SIDEBAR_WIDTH = 190;

export const MIN_DOCUMENT_RATIO = 0.2;
export const MAX_DOCUMENT_RATIO = 0.8;
export const DEFAULT_DOCUMENT_RATIO = 1.05 / 2.05;

export const MIN_WORKSPACE_PANE_WIDTH = 300;
export const RESIZER_WIDTH = 6;
export const ACTIVITY_BAR_WIDTH = 44;
export const KEYBOARD_RESIZE_STEP = 16;

export const WIDE_WORKSPACE_BREAKPOINT = 1050;
export const STACKED_SIDEBAR_BREAKPOINT = 760;

export interface LayoutStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem?(key: string): void;
}

export interface SidebarClampOptions {
  activityBarWidth?: number;
  resizerWidth?: number;
}

export interface ResolvedLayoutWidths {
  sidebarPx: number;
  documentPx: number;
  conversationPx: number;
  totalUsedPx: number;
  stackedWorkspace: boolean;
}

function browserStorage(): LayoutStorage | null {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

function roundRatio(value: number): number {
  return Math.round(value * 10000) / 10000;
}

/** Maximum sidebar width allowed for a given container width without causing overflow. */
export function maxSidebarWidthForContainer(
  containerWidth?: number,
  options: SidebarClampOptions = {},
): number {
  if (containerWidth === undefined || !Number.isFinite(containerWidth)) {
    return MAX_SIDEBAR_WIDTH;
  }
  const activityBarWidth = options.activityBarWidth ?? ACTIVITY_BAR_WIDTH;
  const resizerWidth = options.resizerWidth ?? RESIZER_WIDTH;
  const available = containerWidth > WIDE_WORKSPACE_BREAKPOINT
    ? containerWidth - activityBarWidth - resizerWidth * 2 - MIN_WORKSPACE_PANE_WIDTH * 2
    : containerWidth - activityBarWidth - resizerWidth - MIN_WORKSPACE_PANE_WIDTH;
  return Math.max(MIN_SIDEBAR_WIDTH, Math.min(MAX_SIDEBAR_WIDTH, Math.floor(available)));
}

/** Clamp a sidebar width to 160–420 px and to the active viewport's safe maximum. */
export function clampSidebarWidth(
  widthPx: number,
  containerWidth?: number,
  options: SidebarClampOptions = {},
): number {
  const safe = Number.isFinite(widthPx) ? widthPx : DEFAULT_SIDEBAR_WIDTH;
  const maxWidth = maxSidebarWidthForContainer(containerWidth, options);
  return Math.round(Math.min(maxWidth, Math.max(MIN_SIDEBAR_WIDTH, safe)));
}

/** Clamp the document split ratio to 0.2–0.8 and enforce 300 px minimum on both panes. */
export function clampDocumentRatio(
  ratio: number,
  workspaceWidth?: number,
  resizerWidth = RESIZER_WIDTH,
): number {
  const safe = Number.isFinite(ratio) ? ratio : DEFAULT_DOCUMENT_RATIO;
  let minRatio = MIN_DOCUMENT_RATIO;
  let maxRatio = MAX_DOCUMENT_RATIO;
  if (workspaceWidth !== undefined && Number.isFinite(workspaceWidth)) {
    const paneArea = workspaceWidth - resizerWidth;
    if (paneArea <= MIN_WORKSPACE_PANE_WIDTH * 2) {
      return 0.5;
    }
    minRatio = Math.max(MIN_DOCUMENT_RATIO, MIN_WORKSPACE_PANE_WIDTH / paneArea);
    maxRatio = Math.min(MAX_DOCUMENT_RATIO, (paneArea - MIN_WORKSPACE_PANE_WIDTH) / paneArea);
    if (minRatio > maxRatio) return 0.5;
  }
  return roundRatio(Math.min(maxRatio, Math.max(minRatio, safe)));
}

/** Convert a document split ratio into CSS `fr` track values matching the two panes. */
export function documentSplitFrValues(ratio: number): { documentFr: string; conversationFr: string } {
  const clamped = clampDocumentRatio(ratio);
  const conv = roundRatio(1 - clamped);
  return { documentFr: `${clamped}fr`, conversationFr: `${conv}fr` };
}

/** Compute effective pixel column widths for a viewport width without rewriting stored values. */
export function resolveLayoutWidths(
  containerWidth: number,
  stored: { sidebarWidthPx: number | null; documentRatio: number | null },
  options: SidebarClampOptions & { sidebarCollapsed?: boolean } = {},
): ResolvedLayoutWidths {
  const activityBarWidth = options.activityBarWidth ?? ACTIVITY_BAR_WIDTH;
  const resizerWidth = options.resizerWidth ?? RESIZER_WIDTH;
  const sidebarCollapsed = options.sidebarCollapsed ?? false;
  const stackedWorkspace = containerWidth <= WIDE_WORKSPACE_BREAKPOINT;

  const sidebarPx = sidebarCollapsed
    ? 0
    : clampSidebarWidth(stored.sidebarWidthPx ?? DEFAULT_SIDEBAR_WIDTH, containerWidth, { activityBarWidth, resizerWidth });
  const sidebarResizer = sidebarCollapsed ? 0 : resizerWidth;
  const mainWidth = Math.max(0, containerWidth - activityBarWidth - sidebarPx - sidebarResizer);

  if (stackedWorkspace) {
    return {
      sidebarPx,
      documentPx: mainWidth,
      conversationPx: mainWidth,
      totalUsedPx: activityBarWidth + sidebarPx + sidebarResizer + mainWidth,
      stackedWorkspace: true,
    };
  }

  const paneArea = Math.max(0, mainWidth - resizerWidth);
  const ratio = clampDocumentRatio(stored.documentRatio ?? DEFAULT_DOCUMENT_RATIO, mainWidth, resizerWidth);
  const documentPx = Math.round(paneArea * ratio);
  const conversationPx = paneArea - documentPx;
  return {
    sidebarPx,
    documentPx,
    conversationPx,
    totalUsedPx: activityBarWidth + sidebarPx + sidebarResizer + documentPx + resizerWidth + conversationPx,
    stackedWorkspace: false,
  };
}

/** Pure drag/keyboard calculation for the sidebar resizer. */
export function computeDraggedSidebarWidth(
  startWidthPx: number,
  deltaX: number,
  containerWidth?: number,
  options: SidebarClampOptions = {},
): number {
  return clampSidebarWidth(startWidthPx + deltaX, containerWidth, options);
}

/** Pure drag/keyboard calculation for the document | conversation resizer. */
export function computeDraggedDocumentRatio(
  startDocumentWidthPx: number,
  deltaX: number,
  workspaceWidth: number,
  resizerWidth = RESIZER_WIDTH,
): number {
  const paneArea = workspaceWidth - resizerWidth;
  if (!Number.isFinite(paneArea) || paneArea <= 0) return DEFAULT_DOCUMENT_RATIO;
  return clampDocumentRatio((startDocumentWidthPx + deltaX) / paneArea, workspaceWidth, resizerWidth);
}

/** Read a remembered sidebar pixel width, or null for the CSS default. */
export function readSidebarWidth(storage: LayoutStorage | null = browserStorage()): number | null {
  try {
    const raw = storage?.getItem(SIDEBAR_WIDTH_KEY) ?? null;
    if (raw === null || !/^\d{3}$/.test(raw)) return null;
    const width = Number(raw);
    return width >= MIN_SIDEBAR_WIDTH && width <= MAX_SIDEBAR_WIDTH ? width : null;
  } catch {
    return null;
  }
}

/** Persist a clamped sidebar pixel width; storage failures are ignored. */
export function writeSidebarWidth(widthPx: number, storage: LayoutStorage | null = browserStorage()): void {
  try {
    const clamped = clampSidebarWidth(widthPx);
    storage?.setItem(SIDEBAR_WIDTH_KEY, String(clamped));
  } catch {
    // Keep the width for this session only.
  }
}

/** Remove the remembered sidebar width so the shell returns to its CSS default. */
export function clearSidebarWidth(storage: LayoutStorage | null = browserStorage()): void {
  try {
    if (!storage) return;
    if (typeof storage.removeItem === "function") {
      storage.removeItem(SIDEBAR_WIDTH_KEY);
    } else {
      storage.setItem(SIDEBAR_WIDTH_KEY, "");
    }
  } catch {
    // Ignore unavailable storage.
  }
}

/** Read a remembered document split ratio (0.2–0.8), or null for the CSS default. */
export function readDocumentRatio(storage: LayoutStorage | null = browserStorage()): number | null {
  try {
    const raw = storage?.getItem(DOCUMENT_RATIO_KEY) ?? null;
    if (raw === null || !/^0(?:\.\d{1,6})?$/.test(raw)) return null;
    const ratio = Number(raw);
    return ratio >= MIN_DOCUMENT_RATIO && ratio <= MAX_DOCUMENT_RATIO ? roundRatio(ratio) : null;
  } catch {
    return null;
  }
}

/** Persist a clamped document split ratio; storage failures are ignored. */
export function writeDocumentRatio(ratio: number, storage: LayoutStorage | null = browserStorage()): void {
  try {
    const clamped = clampDocumentRatio(ratio);
    storage?.setItem(DOCUMENT_RATIO_KEY, String(clamped));
  } catch {
    // Keep the split for this session only.
  }
}

/** Remove the remembered document split ratio so the workspace returns to its CSS default. */
export function clearDocumentRatio(storage: LayoutStorage | null = browserStorage()): void {
  try {
    if (!storage) return;
    if (typeof storage.removeItem === "function") {
      storage.removeItem(DOCUMENT_RATIO_KEY);
    } else {
      storage.setItem(DOCUMENT_RATIO_KEY, "");
    }
  } catch {
    // Ignore unavailable storage.
  }
}
