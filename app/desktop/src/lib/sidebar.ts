import type { ConversationSelection } from "../conversations.ts";
import type { Api } from "../api.ts";
import type { SessionListDto, SessionSummaryDto } from "../protocol.ts";

export interface SidebarSessionRow extends SessionSummaryDto {
  transient: boolean;
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
