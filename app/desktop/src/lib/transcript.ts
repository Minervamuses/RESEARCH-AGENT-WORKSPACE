import type { BackendClient } from "../backend.ts";
import type { ConversationFailure } from "../conversations.ts";
import type {
  SessionSelectedDto,
  SessionSummaryDto,
  SessionTranscriptDto,
  TranscriptTurnDto,
} from "../protocol.ts";
import { protocolMismatch } from "./errors.ts";

// One transcript page: the tail window restored on select and after a durable failure.
export const TRANSCRIPT_PAGE_SIZE = 20;

export interface TranscriptView {
  projectId: string;
  sessionId: string;
  status: SessionTranscriptDto["status"];
  issue: string | null;
  items: TranscriptTurnDto[];
  offset: number;
  total: number;
  hasOlder: boolean;
}

export function mergeTranscriptItems(
  older: readonly TranscriptTurnDto[],
  current: readonly TranscriptTurnDto[],
): TranscriptTurnDto[] {
  const byTurn = new Map<number, TranscriptTurnDto>();
  for (const item of [...older, ...current]) byTurn.set(item.turnNumber, item);
  return [...byTurn.values()].sort((left, right) => left.turnNumber - right.turnNumber);
}

export function failureLifecycleLabel(failure: ConversationFailure): string {
  const lifecycle = failure.turnLifecycle;
  if (lifecycle === null) return "Delivery status unknown";
  if (lifecycle.state === null) return "Prompt was not accepted";
  if (lifecycle.state === "completed") return "Answer saved locally";
  if (lifecycle.state === "pending") return "Prompt saved · completion pending";
  return `Prompt saved · ${lifecycle.state}`;
}

export function isPersistedTurnFailure(failure: ConversationFailure | null): boolean {
  const lifecycle = failure?.turnLifecycle;
  return lifecycle?.accepted === true && lifecycle.persisted === true;
}

export function transcriptTailOffset(total: number): number {
  return Math.max(0, total - TRANSCRIPT_PAGE_SIZE);
}

export async function fetchTranscriptPage(
  projectId: string,
  sessionId: string,
  offset: number,
  limit: number,
  mismatchMessage = "The backend returned a transcript for a different conversation.",
  request: BackendClient["request"],
): Promise<SessionTranscriptDto> {
  const data = await request("session.transcript", {
    projectId,
    sessionId,
    offset,
    limit,
  }) as unknown as SessionTranscriptDto;
  if (data.projectId !== projectId || data.sessionId !== sessionId) {
    throw protocolMismatch(mismatchMessage);
  }
  return data;
}

export async function selectConversationWithPreview(
  projectId: string,
  summary: SessionSummaryDto,
  callbacks: {
    isCurrent: () => boolean;
    onPreview: (data: SessionTranscriptDto) => void;
    onSelected: (selected: SessionSelectedDto) => void;
  },
  request: BackendClient["request"],
): Promise<SessionTranscriptDto | null> {
  let previewing = true;
  const selectedRequest = request("session.select", { projectId, sessionId: summary.sessionId });
  // Handle both outcomes immediately: selection may fail before this read finishes.
  const transcriptRequest = fetchTranscriptPage(
    projectId, summary.sessionId, transcriptTailOffset(summary.turnCount), TRANSCRIPT_PAGE_SIZE,
    undefined, request,
  ).then(
    (data) => {
      if (previewing && callbacks.isCurrent() && data.status === "ready") callbacks.onPreview(data);
      return { data, error: null };
    },
    (error: unknown) => ({ data: null, error }),
  );
  try {
    const selected = await selectedRequest as unknown as SessionSelectedDto;
    if (!callbacks.isCurrent()) return null;
    if (selected.projectId !== projectId || selected.sessionId !== summary.sessionId) {
      throw protocolMismatch("The backend returned a different conversation than requested.");
    }
    callbacks.onSelected(selected);
    const result = await transcriptRequest;
    if (!callbacks.isCurrent()) return null;
    if (result.data === null) throw result.error;
    let data = result.data;
    // Materializing a session recovers pending turns. A stale sidebar count can
    // also select the wrong tail page, so confirm either case after selection.
    if (data.items.some((turn) => turn.state === "pending") ||
        data.total !== selected.turnCount || data.offset !== transcriptTailOffset(selected.turnCount)) {
      data = await fetchTranscriptPage(
        projectId, summary.sessionId, transcriptTailOffset(selected.turnCount), TRANSCRIPT_PAGE_SIZE,
        undefined, request,
      );
    }
    return callbacks.isCurrent() ? data : null;
  } finally {
    previewing = false;
  }
}

export function transcriptViewFrom(
  projectId: string,
  sessionId: string,
  data: SessionTranscriptDto,
): TranscriptView {
  return {
    projectId,
    sessionId,
    status: data.status,
    issue: data.issue,
    items: data.items,
    offset: data.offset,
    total: data.total,
    hasOlder: data.status === "ready" && data.offset > 0,
  };
}

export function visibleMessageRange(root: Node, startNode: Node, startOffset: number, endNode: Node, endOffset: number): { visibleText: string; text: string; startUtf16: number; endUtf16: number } | null {
  let text = "";
  const positions = new Map<Node, { start: number; end: number; boundaries: number[] }>();
  const newline = () => { if (text.length > 0 && !text.endsWith("\n")) text += "\n"; };
  const visit = (node: Node) => {
    const start = text.length;
    if (node.nodeType === 3) {
      text += node.textContent ?? "";
      positions.set(node, { start, end: text.length, boundaries: [] });
      return;
    }
    if (node.nodeType !== 1) return;
    const element = node as Element;
    if (element.hasAttribute("hidden") || element.getAttribute("aria-hidden") === "true" ||
        element.hasAttribute("data-reference-exclude") || ["INPUT", "TEXTAREA", "SELECT", "DETAILS"].includes(element.tagName) ||
        (element.tagName === "BUTTON" && !(element.getAttribute("class") ?? "").split(/\s+/).includes("safe-link"))) return;
    const block = node !== root && /^(P|DIV|PRE|LI|UL|OL|BLOCKQUOTE|H[1-6])$/.test(element.tagName);
    if (block) newline();
    const boundaries = [text.length];
    if (element.tagName === "BR") text += "\n";
    for (const child of Array.from(node.childNodes)) {
      visit(child);
      boundaries.push(text.length);
    }
    positions.set(node, { start, end: text.length, boundaries });
    if (block) newline();
  };
  visit(root);
  const visibleText = text.replace(/\n+$/, "");
  const offset = (node: Node, index: number): number | null => {
    const position = positions.get(node);
    if (position === undefined || !Number.isSafeInteger(index) || index < 0) return null;
    const value = node.nodeType === 3
      ? index <= position.end - position.start ? position.start + index : undefined
      : position.boundaries[index];
    return value === undefined ? null : Math.min(value, visibleText.length);
  };
  const startUtf16 = offset(startNode, startOffset), endUtf16 = offset(endNode, endOffset);
  if (startUtf16 === null || endUtf16 === null || endUtf16 <= startUtf16) return null;
  return { visibleText, text: visibleText.slice(startUtf16, endUtf16), startUtf16, endUtf16 };
}
