import type { ReactNode } from "react";
import type { BackendSnapshot } from "../backend.ts";
import type { ConversationSelection } from "../conversations.ts";
import type { ProjectWorkspaceDto, SessionListDto } from "../protocol.ts";
import { projectDisplayName, sidebarRowsForProject, type SidebarSessionRow, type SidebarView } from "../lib/sidebar.ts";
import { phaseLabels } from "./phaseLabels.ts";

export interface ConversationMenuRequest { projectId: string; session: SidebarSessionRow; left: number; top: number }

/** Project browser, conversation list (or document outline) and backend controls. State and actions come from `App()`. */
export function Sidebar({
  inert, phase, snapshot, hasError, project, list, selected, selectedSaved, historyLoaded,
  newConversationDisabled, chooserDisabled, selectionDisabled, canStart, canRestart, canShutdown,
  onCreateConversation, onShowChooser, onSelectConversation, onLoadMore, onOpenMenu, onLifecycle,
  view = "conversations", outlineContent,
}: {
  inert: boolean;
  phase: keyof typeof phaseLabels;
  snapshot: BackendSnapshot | null;
  /** A backend error exists; a stopped backend then offers "Retry start". */
  hasError: boolean;
  project: ProjectWorkspaceDto | null;
  /** The opened project's list; a list left over from another project is never passed. */
  list: SessionListDto | null;
  selected: ConversationSelection | null;
  selectedSaved: boolean;
  /** The project's history generation is known (distinguishes "Loading" from "unavailable"). */
  historyLoaded: boolean;
  newConversationDisabled: boolean;
  chooserDisabled: boolean;
  /** A turn, document operation, approval or workspace operation blocks switching or paging. */
  selectionDisabled: boolean;
  canStart: boolean; canRestart: boolean; canShutdown: boolean;
  onCreateConversation: () => void;
  onShowChooser: () => void;
  onSelectConversation: (projectId: string, session: SidebarSessionRow) => void;
  onLoadMore: () => void;
  /** `returnFocus` is the row to focus when the menu closes. */
  onOpenMenu: (menu: ConversationMenuRequest, returnFocus: HTMLElement) => void;
  onLifecycle: (action: "start" | "restart" | "shutdown") => void;
  view?: SidebarView;
  outlineContent?: ReactNode;
}) {
  return <aside className="sidebar" aria-label="Research Agent workspace" inert={inert}>
    <div className="brand-lockup"><span className="brand-mark" aria-hidden="true">R</span><div><p className="eyebrow">LOCAL WORKSPACE</p><h1>Research Agent</h1></div></div>
    {view === "outline" ? (
      outlineContent ?? null
    ) : (
      <>
        <button className="new-session-button" type="button" title="Creating or selecting a conversation starts its enabled, configured MCP servers." onClick={onCreateConversation} disabled={newConversationDisabled}><span aria-hidden="true">＋</span> New conversation</button>
        <section className="sidebar-section project-browser" aria-labelledby="workspace-label">
          <h2 id="workspace-label">Project</h2>
          <button type="button" onClick={onShowChooser} disabled={chooserDisabled}>{project === null ? "Open project" : "Switch project"}</button>
          {list === null && <p className="sidebar-note">{project === null ? "Choose a project to load its conversations." : !historyLoaded ? "Loading selected project…" : "Project unavailable"}</p>}
          {project !== null && list !== null && <ProjectGroup project={project} list={list} selected={selected} selectedSaved={selectedSaved}
            selectionDisabled={selectionDisabled} onSelectConversation={onSelectConversation} onLoadMore={onLoadMore} onOpenMenu={onOpenMenu} />}
        </section>
        <div className="sidebar-spacer" />
      </>
    )}
    <section className="backend-controls" aria-labelledby="backend-controls-title">
      <div className="sidebar-status" role="status" aria-live="polite"><span className={`status-dot status-${phase}`} aria-hidden="true" /><span><strong id="backend-controls-title">{phaseLabels[phase]}</strong><small>{snapshot === null ? "Desktop process not observed" : `Generation ${snapshot.generation} · ${snapshot.pendingRequests} pending`}</small></span></div>
      <div className="control-row">
        <button type="button" onClick={() => onLifecycle("start")} disabled={!canStart}>{hasError && phase === "stopped" ? "Retry start" : "Start"}</button>
        <button type="button" title="Restarting reloads enabled, configured MCP servers for the conversation." onClick={() => onLifecycle("restart")} disabled={!canRestart}>Restart</button>
        <button type="button" onClick={() => onLifecycle("shutdown")} disabled={!canShutdown}>Shut down</button>
      </div>
    </section>
  </aside>;
}

function ProjectGroup({ project, list, selected, selectedSaved, selectionDisabled, onSelectConversation, onLoadMore, onOpenMenu }: {
  project: ProjectWorkspaceDto; list: SessionListDto; selected: ConversationSelection | null; selectedSaved: boolean;
  selectionDisabled: boolean;
  onSelectConversation: (projectId: string, session: SidebarSessionRow) => void;
  onLoadMore: () => void;
  onOpenMenu: (menu: ConversationMenuRequest, returnFocus: HTMLElement) => void;
}) {
  const rows = sidebarRowsForProject(list.projectId, list.items, selected, selectedSaved);
  const name = projectDisplayName(project.rootPath);
  return <div className="project-group">
    <div className="project-heading"><strong tabIndex={0} title={project.rootPath}>{name}</strong><small>{list.total} saved</small></div>
    {list.status === "unavailable" && <p className="sidebar-note">{list.issue ?? "Conversations unavailable"}</p>}
    {rows.length === 0 && list.status !== "unavailable" ? <p className="sidebar-note">No saved conversations</p> : <ul className="session-list">{rows.map((session) => {
      const isSelected = selected?.sessionId === session.sessionId && selected.projectId === list.projectId;
      return <li key={session.sessionId} tabIndex={-1} onContextMenu={(event) => {
        event.preventDefault();
        const bounds = event.currentTarget.getBoundingClientRect();
        onOpenMenu({ projectId: list.projectId, session,
          left: Math.max(8, Math.min(event.clientX || bounds.left, window.innerWidth - 200)),
          top: Math.max(8, Math.min(event.clientY || bounds.bottom, window.innerHeight - 110)) }, event.currentTarget);
      }}>
        <button type="button" className="session-link" title={session.title} aria-label={session.title} aria-current={isSelected ? "page" : undefined}
          disabled={selectionDisabled || session.status !== "ready"} onClick={() => onSelectConversation(list.projectId, session)}>
          <span>{session.title}</span>
          <small>{session.transient ? "Not saved yet" : `${session.turnCount} turns${session.status === "ready" ? "" : ` · ${session.status}`}`}</small>
        </button>
      </li>;
    })}</ul>}
    {list.hasMore && <button className="load-more-sessions" type="button" onClick={onLoadMore} disabled={selectionDisabled}>Load more conversations</button>}
  </div>;
}
