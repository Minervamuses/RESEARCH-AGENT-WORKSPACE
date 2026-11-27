import type { ConversationSelection } from "../conversations.ts";
import type { Api } from "../api.ts";
import type { SessionListDto, SessionSummaryDto } from "../protocol.ts";

export interface SidebarSessionRow extends SessionSummaryDto {
  transient: boolean;
}

export type SidebarView = "conversations" | "outline";

export interface SidebarViewState {
  view: SidebarView;
  collapsed: boolean;
}

export const INITIAL_SIDEBAR_VIEW_STATE: SidebarViewState = {
  view: "conversations",
  collapsed: false,
};

/** Clicking the active icon toggles collapse; clicking another icon switches and expands (U6). */
export function selectSidebarView(current: SidebarViewState, target: SidebarView): SidebarViewState {
  if (current.view === target) {
    return { view: current.view, collapsed: !current.collapsed };
  }
  return { view: target, collapsed: false };
}

/** Opening a document selects the outline view without expanding a user-collapsed sidebar (U1, A4). */
export function sidebarStateOnDocumentOpen(current: SidebarViewState): SidebarViewState {
  return { view: "outline", collapsed: current.collapsed };
}

/** Clearing the open document returns the sidebar view to conversations (A5). */
export function sidebarStateOnDocumentCleared(current: SidebarViewState): SidebarViewState {
  return { view: "conversations", collapsed: current.collapsed };
}

export function sidebarRowsForProject(
  projectId: string,
  sessions: readonly SessionSummaryDto[],
  selected: ConversationSelection | null,
  selectedSaved: boolean,
): SidebarSessionRow[] {
  const rows = sessions.map((session) => ({ ...session, transient: false }));
  if (
    selected !== null &&
    selected.projectId === projectId &&
    !selectedSaved &&
    !rows.some((session) => session.sessionId === selected.sessionId)
  ) {
    rows.unshift({
      sessionId: selected.sessionId,
      title: "New conversation",
      turnCount: 0,
      createdAt: null,
      updatedAt: null,
      status: "ready",
      issue: null,
      transient: true,
    });
  }
  return rows;
}

/** The opened project's first page of saved conversations (the backend scans its history). */
export async function loadSelectedProjectHistory(
  projectId: string | null,
  sessionList: Api["sessionList"],
  isCurrent: () => boolean = () => true,
): Promise<SessionListDto | null> {
  if (projectId === null) return null;
  const sessions = await sessionList({ projectId, offset: 0, limit: 50 });
  return isCurrent() ? sessions : null;
}

export function projectDisplayName(rootPath: string): string {
  return rootPath.split(/[\\/]/).filter((part) => part.length > 0).at(-1) ?? rootPath;
}

export function mergeSessionItems(
  current: readonly SessionSummaryDto[],
  next: readonly SessionSummaryDto[],
): SessionSummaryDto[] {
  const bySession = new Map<string, SessionSummaryDto>();
  for (const item of [...current, ...next]) bySession.set(item.sessionId, item);
  return [...bySession.values()];
}
