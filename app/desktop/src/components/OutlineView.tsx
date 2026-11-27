import { useEffect, useRef, useSyncExternalStore, type CSSProperties } from "react";
import {
  resolveActiveOutlineDisplay,
  type OutlineDocument,
  type OutlineNode,
  type OutlineTracker,
} from "../lib/outline/index.ts";

export interface OutlineViewProps {
  /** Open document path (relative or absolute), or null when no document is open. */
  documentPath: string | null;
  outline: OutlineDocument;
  collapsedIds: ReadonlySet<string>;
  /** External active-section tracker (subscribes without re-rendering App on scroll). */
  tracker?: OutlineTracker | null;
  /** Static active heading ID override (used when no tracker is attached, e.g. isolated SSR). */
  activeId?: string | null;
  /** Static collapsed ancestor ID override (used when no tracker is attached). */
  activeAncestorId?: string | null;
  onToggleCollapse: (id: string) => void;
  onSelect: (node: OutlineNode) => void;
}

const subscribeNoop = () => () => {};
const getNullSnapshot = () => null;

export function documentBasename(path: string): string {
  const normalized = path.replace(/\\/g, "/");
  const idx = normalized.lastIndexOf("/");
  return idx >= 0 ? normalized.slice(idx + 1) : normalized;
}

function OutlineBranch({
  nodes,
  collapsedIds,
  activeId,
  activeAncestorId,
  onToggleCollapse,
  onSelect,
}: {
  nodes: readonly OutlineNode[];
  collapsedIds: ReadonlySet<string>;
  activeId: string | null;
  activeAncestorId: string | null;
  onToggleCollapse: (id: string) => void;
  onSelect: (node: OutlineNode) => void;
}) {
  return (
    <>
      {nodes.map((node) => {
        const hasChildren = node.children.length > 0;
        const isCollapsed = hasChildren && collapsedIds.has(node.id);
        const isActive = activeId === node.id;
        const isAncestor = !isActive && activeAncestorId === node.id;
        const indentDepth = Math.min(node.depth, 5);
        const rowClass = [
          "outline-row",
          isActive ? "is-active" : "",
          isAncestor ? "is-active-ancestor" : "",
        ].filter(Boolean).join(" ");

        return (
          <li
            key={node.id}
            role="treeitem"
            aria-level={node.depth + 1}
            aria-expanded={hasChildren ? !isCollapsed : undefined}
            aria-current={isActive ? "location" : undefined}
            data-outline-id={node.id}
            className="outline-tree-item"
          >
            <div
              className={rowClass}
              style={{ "--outline-depth": indentDepth } as CSSProperties}
            >
              {hasChildren ? (
                <button
                  type="button"
                  className={`outline-toggle${isCollapsed ? " is-collapsed" : ""}`}
                  aria-label={isCollapsed ? `Expand ${node.title}` : `Collapse ${node.title}`}
                  aria-expanded={!isCollapsed}
                  onClick={() => onToggleCollapse(node.id)}
                >
                  <svg viewBox="0 0 12 12" width="10" height="10" aria-hidden="true">
                    <path d="M3 4.5 6 7.5 9 4.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              ) : (
                <span className="outline-toggle-spacer" aria-hidden="true" />
              )}
              <button
                type="button"
                className="outline-item-button"
                title={node.title}
                onClick={() => onSelect(node)}
              >
                <span className="outline-item-title">{node.title}</span>
              </button>
            </div>
            {hasChildren && !isCollapsed && (
              <ul className="outline-group" role="group">
                <OutlineBranch
                  nodes={node.children}
                  collapsedIds={collapsedIds}
                  activeId={activeId}
                  activeAncestorId={activeAncestorId}
                  onToggleCollapse={onToggleCollapse}
                  onSelect={onSelect}
                />
              </ul>
            )}
          </li>
        );
      })}
    </>
  );
}

/** Hierarchical outline tree for the currently opened Markdown or LaTeX document. */
export function OutlineView({
  documentPath,
  outline,
  collapsedIds,
  tracker = null,
  activeId = null,
  activeAncestorId = null,
  onToggleCollapse,
  onSelect,
}: OutlineViewProps) {
  const treeRef = useRef<HTMLUListElement>(null);
  const trackedId = useSyncExternalStore(
    tracker ? tracker.subscribe : subscribeNoop,
    tracker ? tracker.getSnapshot : getNullSnapshot,
    tracker ? tracker.getSnapshot : getNullSnapshot,
  );

  const display = tracker
    ? resolveActiveOutlineDisplay(outline, trackedId, collapsedIds)
    : { activeId, activeAncestorId };

  const highlightedId = display.activeId ?? display.activeAncestorId;
  useEffect(() => {
    const list = treeRef.current;
    if (!list || highlightedId === null) return;
    const items = list.querySelectorAll<HTMLElement>("[data-outline-id]");
    for (const item of items) {
      if (item.dataset.outlineId === highlightedId) {
        item.querySelector<HTMLElement>(".outline-row")?.scrollIntoView?.({ block: "nearest" });
        break;
      }
    }
  }, [highlightedId]);

  return (
    <section className="sidebar-section outline-panel" aria-labelledby="outline-panel-title">
      <div className="outline-header">
        <h2 id="outline-panel-title">Outline</h2>
        {documentPath !== null && (
          <p className="outline-filename" title={documentPath}>
            {documentBasename(documentPath)}
          </p>
        )}
      </div>

      {documentPath === null ? (
        <p className="sidebar-note outline-empty">Open a document to see its outline.</p>
      ) : outline.roots.length === 0 ? (
        <p className="sidebar-note outline-empty">No headings found</p>
      ) : (
        <ul ref={treeRef} className="outline-tree" role="tree" aria-label="Document outline">
          <OutlineBranch
            nodes={outline.roots}
            collapsedIds={collapsedIds}
            activeId={display.activeId}
            activeAncestorId={display.activeAncestorId}
            onToggleCollapse={onToggleCollapse}
            onSelect={onSelect}
          />
        </ul>
      )}
    </section>
  );
}
