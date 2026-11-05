import { useCallback, useEffect, useRef, useState } from "react";
import type { JsonObject } from "./protocol";
import type { DocumentSnapshot } from "./DocumentEditor";
import {
  buildPanelModel,
  describeEntry,
  selectUse,
  type BibliographyInspectDto,
  type CitedItem,
  type UseLocation,
} from "./citations";

export type BackendRequest = (method: "bibliography.inspect", params: JsonObject) => Promise<JsonObject>;

export interface CitationPanelProps {
  document: DocumentSnapshot;
  /** Increments when the document is opened, saved or changed by an applied operation. */
  refreshToken: number;
  request: BackendRequest;
  contextPayload: (snapshot: DocumentSnapshot) => JsonObject;
  onSelect: (snapshot: DocumentSnapshot) => void;
  /** Keys and titles for editor completion. */
  onEntries?: (entries: BibliographyInspectDto["entries"]) => void;
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "The citation check failed.";
}

function UseButtons({ item, onJump }: { item: { key: string; uses: UseLocation[] }; onJump: (use: UseLocation) => void }) {
  return (
    <ul className="citation-uses">
      {item.uses.map((use, index) => (
        <li key={`${use.start}-${index}`}>
          <button type="button" className="link-button" onClick={() => onJump(use)}>Line {use.line}</button>
        </li>
      ))}
    </ul>
  );
}

function CitedRow({ item, onJump }: { item: CitedItem; onJump: (use: UseLocation) => void }) {
  return (
    <li className="citation-row">
      <details>
        <summary>
          {item.number !== null && <span className="citation-number">[{item.number}]</span>}
          <code>{item.key}</code>
          <span className="citation-meta">{describeEntry(item.entry)}</span>
          <span className="citation-count">{item.count}×</span>
          {item.entry !== null && <span className={`citation-badge ${item.entry.verification}`}>{item.entry.verification}</span>}
        </summary>
        <UseButtons item={item} onJump={onJump} />
      </details>
    </li>
  );
}

export function CitationPanel({ document, refreshToken, request, contextPayload, onSelect, onEntries }: CitationPanelProps) {
  const [inspect, setInspect] = useState<BibliographyInspectDto | null>(null);
  const [inspectedText, setInspectedText] = useState("");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const documentRef = useRef(document);
  documentRef.current = document;
  const sequence = useRef(0);

  const refresh = useCallback(async () => {
    const snapshot = documentRef.current;
    const ticket = ++sequence.current;
    setLoading(true);
    try {
      const data = await request("bibliography.inspect", { documentContext: contextPayload(snapshot) }) as unknown as BibliographyInspectDto;
      if (ticket !== sequence.current) return;
      setInspect(data);
      setInspectedText(snapshot.sourceText);
      setNotice(null);
      onEntries?.(data.entries);
    } catch (error) {
      if (ticket === sequence.current) setNotice(errorText(error));
    } finally {
      if (ticket === sequence.current) setLoading(false);
    }
  }, [request, contextPayload, onEntries]);

  useEffect(() => { void refresh(); }, [refresh, refreshToken, document.path]);

  const jump = useCallback((use: UseLocation) => {
    const selected = selectUse(documentRef.current, inspectedText, use);
    if (selected === null) {
      setNotice("The text changed since the last check. Refresh to update citation positions.");
      return;
    }
    onSelect(selected);
  }, [inspectedText, onSelect]);

  const model = inspect === null ? null : buildPanelModel(inspect);
  return (
    <section className="citation-panel" aria-label="Citations">
      <header className="citation-panel-header">
        <h3>Citations</h3>
        <button type="button" onClick={() => void refresh()} disabled={loading}>{loading ? "Checking…" : "Refresh"}</button>
      </header>
      {notice !== null && <p className="document-error" role="status">{notice}</p>}
      {model !== null && <>
        <p className="citation-library">
          Bibliography: <code>{model.libraryPath}</code>
          {model.libraryStatus === "missing" && " — not created yet. Save a source with /citation or add one below."}
        </p>
        {model.libraryIssue !== null && <p className="document-error" role="alert">{model.libraryIssue}</p>}
        <details open className="citation-section">
          <summary>Cited in this document ({model.cited.length})</summary>
          {model.cited.length === 0
            ? <p className="citation-empty">No citation keys in this document yet.</p>
            : <ol className="citation-list">{model.cited.map((item) => <CitedRow key={item.key} item={item} onJump={jump} />)}</ol>}
        </details>
        {(model.missing.length > 0 || model.duplicates.length > 0) && <details open className="citation-section citation-problems">
          <summary>Problems ({model.missing.length + model.duplicates.length})</summary>
          <ul className="citation-list">
            {model.missing.map((item) => (
              <li key={`missing-${item.key}`}>
                Unknown key <code>{item.key}</code> — not in the bibliography.
                <UseButtons item={item} onJump={jump} />
              </li>
            ))}
            {model.duplicates.map((group) => (
              <li key={`doi-${group.doi}`}>Same DOI <code>{group.doi}</code> in {group.keys.map((key) => <code key={key}>{key}</code>)}</li>
            ))}
          </ul>
        </details>}
        <details className="citation-section">
          <summary>Not cited in this document ({model.uncited.length})</summary>
          <ul className="citation-list">
            {model.uncited.map((entry) => (
              <li key={entry.key} className="citation-row"><code>{entry.key}</code> <span className="citation-meta">{describeEntry(entry)}</span></li>
            ))}
          </ul>
        </details>
      </>}
    </section>
  );
}
