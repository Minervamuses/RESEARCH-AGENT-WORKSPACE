import { useCallback, useEffect, useId, useRef, useState } from "react";
import type { JsonObject } from "./protocol";
import type { DocumentSnapshot } from "./lib/documentSource.ts";
import {
  addErrorOutcome,
  addOutcome,
  buildPanelModel,
  citationFormatForPath,
  describeEntry,
  BIME_LAYOUT_REMINDER,
  EXPORT_LABELS,
  EXPORT_NOTES,
  exportFormats,
  exportSummary,
  nextExpanded,
  panelSummaryText,
  previewEntries,
  problemCount,
  removeConfirmation,
  removeErrorMessage,
  selectUse,
  styleChangeParams,
  type AddOutcome,
  type BibliographyAddDto,
  type BibliographyEntryDto,
  type BibliographyExportDto,
  type BibliographyInspectDto,
  type BibliographyRenderDto,
  type CitedItem,
  type ExportFormat,
  type ExportSummary,
  type UseLocation,
} from "./citations";
import { CitationText } from "./CitationText.tsx";

export type BackendRequest = (
  method: "bibliography.inspect" | "bibliography.remove" | "bibliography.set_style" | "bibliography.render" | "bibliography.export",
  params: JsonObject,
) => Promise<JsonObject>;

export interface CitationPanelProps {
  document: DocumentSnapshot;
  /** Increments when the document is opened, saved or changed by an applied operation. */
  refreshToken: number;
  request: BackendRequest;
  contextPayload: (snapshot: DocumentSnapshot) => JsonObject;
  onSelect: (snapshot: DocumentSnapshot) => void;
  /** Keys and titles for editor completion. */
  onEntries?: (entries: BibliographyInspectDto["entries"]) => void;
  /** bibliography.add, tracked by App so an Ask-mode approval reaches the approval UI. */
  requestAdd: (identifier: string) => Promise<JsonObject>;
  /** Writes are disabled while a turn or document operation runs. */
  writesDisabled: boolean;
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

/** One `Export ▾` button; its options open in the panel's flow so the panel never clips them. */
export function ExportMenu({ formats, disabled, onExport }: {
  formats: ExportFormat[];
  disabled: boolean;
  onExport: (format: ExportFormat) => void;
}) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLUListElement>(null);
  useEffect(() => {
    if (disabled) setOpen(false);
    else if (open) menu.current?.querySelector<HTMLElement>("button")?.focus();
  }, [disabled, open]);
  if (formats.length === 0) return null;
  const close = () => { setOpen(false); trigger.current?.focus(); };
  return (
    <div className="citation-export" onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false);
    }} onKeyDown={(event) => {
      if (event.key === "Escape" && open) { event.preventDefault(); close(); }
    }}>
      <button ref={trigger} type="button" disabled={disabled} aria-haspopup="menu" aria-expanded={open}
        onClick={() => setOpen(!open)}>Export ▾</button>
      {open && <ul ref={menu} className="citation-export-options" role="menu" aria-label="Export">
        {formats.map((format) => (
          <li key={format} role="none">
            <button type="button" role="menuitem" onClick={() => { close(); onExport(format); }}>
              <span className="citation-export-label">{EXPORT_LABELS[format]}</span>
              <span className="citation-export-note">{EXPORT_NOTES[format]}</span>
            </button>
          </li>
        ))}
      </ul>}
    </div>
  );
}

/** A key cited in this document: details and Line jumps only, never a write action. */
export function CitedRow({ item, onJump }: { item: CitedItem; onJump: (use: UseLocation) => void }) {
  return (
    <li className="citation-row">
      <details>
        <summary>
          {item.number !== null && <span className="citation-number">[{item.number}]</span>}
          <code>{item.key}</code>
          <span className="citation-meta">{describeEntry(item.entry)}</span>
          <span className="citation-count">{item.count}×</span>
        </summary>
        <UseButtons item={item} onJump={onJump} />
      </details>
    </li>
  );
}

/** An entry this document does not cite; Remove asks for confirmation first. */
export function UncitedRow({ entry, onRemove, disabled }: {
  entry: BibliographyEntryDto;
  onRemove: (key: string) => void;
  disabled: boolean;
}) {
  return (
    <li className="citation-row">
      <code>{entry.key}</code> <span className="citation-meta">{describeEntry(entry)}</span>
      <span className="citation-actions">
        <button type="button" className="link-button" disabled={disabled} onClick={() => onRemove(entry.key)}>Remove</button>
      </span>
    </li>
  );
}

export function CitationPanel({
  document, refreshToken, request, contextPayload, onSelect, onEntries, requestAdd, writesDisabled,
}: CitationPanelProps) {
  const [inspect, setInspect] = useState<BibliographyInspectDto | null>(null);
  const [inspectedText, setInspectedText] = useState("");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const documentRef = useRef(document);
  documentRef.current = document;
  const sequence = useRef(0);
  const [expanded, setExpanded] = useState(false);
  /** Problems found by the previous check of this document; null until its first check. */
  const problemsRef = useRef<number | null>(null);
  const bodyId = useId();

  // Each opened document starts collapsed; its first check decides whether to expand (A7).
  useEffect(() => {
    setExpanded(false);
    problemsRef.current = null;
  }, [document.path]);

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
      const problems = problemCount(buildPanelModel(data));
      const event = { kind: "checked", previousProblems: problemsRef.current, problems } as const;
      problemsRef.current = problems;
      setExpanded((current) => nextExpanded(current, event));
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

  const [identifier, setIdentifier] = useState("");
  const [adding, setAdding] = useState(false);
  const [added, setAdded] = useState<AddOutcome | null>(null);
  const format = citationFormatForPath(document.path);

  const remove = useCallback(async (key: string) => {
    const fingerprint = inspect?.libraryFingerprint;
    if (inspect === null || fingerprint === null || fingerprint === undefined || writesDisabled) return;
    if (!window.confirm(removeConfirmation(key, inspect.libraryPath))) return;
    try {
      await request("bibliography.remove", { key, libraryFingerprint: fingerprint });
      setNotice(`Removed ${key} from the bibliography.`);
      await refresh();
    } catch (error) {
      setNotice(removeErrorMessage(error));
    }
  }, [inspect, refresh, request, writesDisabled]);

  const add = useCallback(async () => {
    const value = identifier.trim();
    if (value === "" || writesDisabled) return;
    setAdding(true);
    setAdded(null);
    try {
      const outcome = addOutcome(await requestAdd(value) as unknown as BibliographyAddDto);
      setAdded(outcome);
      if (outcome.kind !== "failed") setIdentifier("");
      await refresh();
    } catch (error) {
      setAdded(addErrorOutcome(error));
    } finally {
      setAdding(false);
    }
  }, [identifier, refresh, requestAdd, writesDisabled]);

  const [preview, setPreview] = useState<BibliographyRenderDto | null>(null);
  const [working, setWorking] = useState<string | null>(null);
  const [exported, setExported] = useState<ExportSummary | null>(null);

  const setStyle = useCallback(async (styleId: string) => {
    const params = styleChangeParams(inspect, styleId, writesDisabled);
    if (params === null) return;
    setWorking("Saving style…");
    try {
      await request("bibliography.set_style", params);
      setPreview(null);
      await refresh();
    } catch (error) {
      setNotice(removeErrorMessage(error));
    } finally {
      setWorking(null);
    }
  }, [inspect, refresh, request, writesDisabled]);

  const renderPreview = useCallback(async () => {
    if (inspect === null) return;
    setExpanded((current) => nextExpanded(current, { kind: "preview" }));
    setWorking("Formatting…");
    try {
      const data = await request("bibliography.render", {
        documentContext: contextPayload(documentRef.current), styleId: inspect.styleId,
      }) as unknown as BibliographyRenderDto;
      setPreview(data);
    } catch (error) {
      setNotice(removeErrorMessage(error));
    } finally {
      setWorking(null);
    }
  }, [contextPayload, inspect, request]);

  const runExport = useCallback(async (exportFormat: ExportFormat) => {
    if (inspect === null || writesDisabled) return;
    setWorking("Exporting…");
    setExported(null);
    try {
      const data = await request("bibliography.export", {
        documentContext: contextPayload(documentRef.current), format: exportFormat,
        ...(exportFormat === "bime_docx" ? {} : { styleId: inspect.styleId }),
      }) as unknown as BibliographyExportDto;
      setExported(exportSummary(data));
    } catch (error) {
      setNotice(removeErrorMessage(error));
    } finally {
      setWorking(null);
    }
  }, [contextPayload, inspect, request, writesDisabled]);

  const model = inspect === null ? null : buildPanelModel(inspect);
  const problems = model === null ? 0 : problemCount(model);
  return (
    <section className="citation-panel" aria-label="Citations">
      <header className={problems > 0 ? "citation-summary has-problems" : "citation-summary"}>
        <h3>Citations</h3>
        {model !== null && <span className="citation-counts">{panelSummaryText(model)}</span>}
        {inspect !== null && <label className="citation-style">
          Style
          <select value={inspect.styleId} disabled={writesDisabled || working !== null}
            onChange={(event) => void setStyle(event.target.value)}>
            {inspect.styles.map((style) => <option key={style.id} value={style.id}>{style.name}</option>)}
          </select>
        </label>}
        {inspect !== null && format === "markdown" && <button type="button" disabled={working !== null} onClick={() => void renderPreview()}>Preview</button>}
        {inspect !== null && <ExportMenu formats={exportFormats(format)} disabled={writesDisabled || working !== null}
          onExport={(exportFormat) => void runExport(exportFormat)} />}
        <button type="button" onClick={() => void refresh()} disabled={loading}>{loading ? "Checking…" : "Refresh"}</button>
        <button type="button" className="citation-toggle" aria-expanded={expanded} aria-controls={bodyId}
          onClick={() => setExpanded(!expanded)}>{expanded ? "Collapse ▴" : "Expand ▾"}</button>
      </header>
      {notice !== null && <p className="document-error" role="status">{notice}</p>}
      {model !== null && model.libraryIssue !== null && <p className="document-error" role="alert">{model.libraryIssue}</p>}
      {working !== null && <p role="status">{working}</p>}
      {exported !== null && <p className={exported.hasErrors ? "document-error" : "citation-added"} role="status">
        Exported to <code>{exported.path}</code>. The source document is unchanged.
        {exported.audit !== null && <> {exported.audit} Report: <code>{exported.reportPath}</code>. {BIME_LAYOUT_REMINDER}</>}
      </p>}
      {expanded && model !== null && <div id={bodyId} className="citation-body">
        <p className="citation-library">
          Bibliography: <code>{model.libraryPath}</code>
          {model.libraryStatus === "missing" && " — not created yet. Save a source with /citation or add one below."}
        </p>
        {writesDisabled && <p className="citation-empty">Style changes, edits and exports wait until the current turn or document operation finishes.</p>}
        {preview !== null && <details open className="citation-section citation-preview">
          <summary>Preview ({preview.styleId})</summary>
          <ol className="citation-list">
            {preview.citations.map((citation) => <li key={citation.index}><code>{citation.keys.join("; ")}</code> → {citation.text}</li>)}
          </ol>
          <div className="citation-references">
            {previewEntries(preview).map((entry) => <p key={entry.key}><CitationText segments={entry.segments} /></p>)}
          </div>
        </details>}
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
        <form className="citation-add" onSubmit={(event) => { event.preventDefault(); void add(); }}>
          <label>
            Add by DOI or arXiv ID
            <input value={identifier} onChange={(event) => setIdentifier(event.target.value)} maxLength={2048}
              placeholder="10.1038/… or 2401.01234" disabled={adding || writesDisabled} />
          </label>
          <button type="submit" disabled={adding || writesDisabled || identifier.trim() === ""}>{adding ? "Verifying…" : "Verify and add"}</button>
        </form>
        {added !== null && <p className={added.kind === "added" || added.kind === "existing" ? "citation-added" : "document-error"} role="status">
          {added.message}
        </p>}
        <details className="citation-section">
          <summary>Not cited in this document ({model.uncited.length})</summary>
          <ul className="citation-list">
            {model.uncited.map((entry) => (
              <UncitedRow key={entry.key} entry={entry} disabled={writesDisabled} onRemove={(key) => void remove(key)} />
            ))}
          </ul>
        </details>
      </div>}
    </section>
  );
}
