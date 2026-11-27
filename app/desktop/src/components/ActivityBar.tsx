import type { SidebarView } from "../lib/sidebar.ts";

export interface ActivityBarProps {
  view: SidebarView;
  collapsed: boolean;
  inert?: boolean;
  onSelectView: (view: SidebarView) => void;
}

/** VS Code-style vertical icon rail to switch sidebar views and collapse/expand the sidebar. */
export function ActivityBar({ view, collapsed, inert = false, onSelectView }: ActivityBarProps) {
  const conversationsOpen = view === "conversations" && !collapsed;
  const outlineOpen = view === "outline" && !collapsed;

  return (
    <nav className="activity-bar" aria-label="Sidebar views" inert={inert}>
      <button
        type="button"
        className={`activity-bar-button${conversationsOpen ? " is-active" : view === "conversations" ? " is-selected-collapsed" : ""}`}
        aria-label="Conversations"
        title={conversationsOpen ? "Conversations (click to hide sidebar)" : "Conversations"}
        aria-pressed={conversationsOpen}
        aria-expanded={conversationsOpen}
        onClick={() => onSelectView("conversations")}
      >
        <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
          <path
            d="M3.5 4.75A1.75 1.75 0 0 1 5.25 3h9.5a1.75 1.75 0 0 1 1.75 1.75v6.5A1.75 1.75 0 0 1 14.75 13H8.2l-3.25 2.75A.5.5 0 0 1 4.1 15.37V13h-.6A1.75 1.75 0 0 1 3.5 11.25v-6.5Z"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      <button
        type="button"
        className={`activity-bar-button${outlineOpen ? " is-active" : view === "outline" ? " is-selected-collapsed" : ""}`}
        aria-label="Outline"
        title={outlineOpen ? "Outline (click to hide sidebar)" : "Outline"}
        aria-pressed={outlineOpen}
        aria-expanded={outlineOpen}
        onClick={() => onSelectView("outline")}
      >
        <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
          <path
            d="M3.5 5h13M3.5 9h9.5M6.5 13h10M6.5 16.5h7.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </svg>
      </button>
    </nav>
  );
}
