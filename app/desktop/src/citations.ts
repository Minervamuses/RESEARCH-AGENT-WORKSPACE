// Pure view logic for the citation panel. The backend owns parsing,
// validation and every write; this module only shapes bounded DTOs for display.

export type CitationFormat = "markdown" | "latex";
export type StyleKind = "author-date" | "author" | "numeric";

export interface CitationStyleDto {
  id: string;
  name: string;
  kind: StyleKind;
  origin: "csl-styles" | "custom";
}

export interface BibliographyEntryDto {
  key: string;
  authors: string[];
  year: string | null;
  title: string;
  doi: string | null;
  type: string;
  verification: "verified" | "unverified";
  citedCount: number;
}

export interface CitationUseDto {
  key: string;
  start: number;
  end: number;
  line: number;
  group: number;
  known: boolean | null;
}

export interface BibliographyInspectDto {
  libraryPath: string;
  libraryStatus: "ok" | "missing" | "error";
  libraryFingerprint: string | null;
  libraryErrorCode: string | null;
  libraryError: string | null;
  styleId: string;
  styleConfigured: boolean;
  styles: CitationStyleDto[];
  documentFormat: CitationFormat | null;
  entries: BibliographyEntryDto[];
  uses: CitationUseDto[];
  order: string[];
  missing: string[];
  uncited: string[];
  duplicateDois: { doi: string; keys: string[] }[];
}

export interface UseLocation {
  start: number;
  end: number;
  line: number;
}

export interface CitedItem {
  key: string;
  number: number | null;
  entry: BibliographyEntryDto | null;
  count: number;
  uses: UseLocation[];
}

export interface PanelModel {
  libraryPath: string;
  libraryStatus: BibliographyInspectDto["libraryStatus"];
  numeric: boolean;
  cited: CitedItem[];
  missing: { key: string; uses: UseLocation[] }[];
  duplicates: { doi: string; keys: string[] }[];
  libraryIssue: string | null;
  uncited: BibliographyEntryDto[];
  hasDocument: boolean;
}

export function styleKind(inspect: BibliographyInspectDto, styleId = inspect.styleId): StyleKind | null {
  return inspect.styles.find((style) => style.id === styleId)?.kind ?? null;
}

/** Inspect result -> what the panel shows (first-appearance order, numbers, issues). */
export function buildPanelModel(inspect: BibliographyInspectDto, styleId = inspect.styleId): PanelModel {
  const numeric = styleKind(inspect, styleId) === "numeric";
  const entries = new Map(inspect.entries.map((entry) => [entry.key, entry]));
  const usesByKey = new Map<string, UseLocation[]>();
  for (const use of inspect.uses) {
    const list = usesByKey.get(use.key) ?? [];
    list.push({ start: use.start, end: use.end, line: use.line });
    usesByKey.set(use.key, list);
  }
  let next = 1;
  const cited = inspect.order.map((key): CitedItem => {
    const entry = entries.get(key) ?? null;
    const uses = usesByKey.get(key) ?? [];
    // Numeric styles number only references that exist, in first-use order.
    const number = numeric && entry !== null ? next++ : null;
    return { key, number, entry, count: uses.length, uses };
  });
  const missing = new Set(inspect.missing);
  let libraryIssue: string | null = null;
  if (inspect.libraryStatus === "error") {
    libraryIssue = `The bibliography cannot be read (${inspect.libraryErrorCode ?? "error"}): ${inspect.libraryError ?? ""}`.trim();
  }
  return {
    libraryPath: inspect.libraryPath,
    libraryStatus: inspect.libraryStatus,
    numeric,
    cited,
    missing: cited.filter((item) => missing.has(item.key)).map((item) => ({ key: item.key, uses: item.uses })),
    duplicates: inspect.duplicateDois,
    libraryIssue,
    uncited: inspect.uncited.map((key) => entries.get(key)).filter((entry): entry is BibliographyEntryDto => entry !== undefined),
    hasDocument: inspect.documentFormat !== null,
  };
}

/** "Author Year · Title" for one entry, or a note for an unknown key. */
export function describeEntry(entry: BibliographyEntryDto | null): string {
  if (entry === null) return "Not in the bibliography";
  const authors = entry.authors.length === 0 ? "" : entry.authors.length > 2
    ? `${entry.authors[0]} et al.` : entry.authors.join(" and ");
  const head = [authors, entry.year ?? "n.d."].filter(Boolean).join(" ");
  return entry.title ? `${head} · ${entry.title}` : head;
}

export interface SelectableSnapshot {
  editorRevision: number;
  sourceText: string;
  rangeStartUtf16?: number;
  rangeEndUtf16?: number;
}

/**
 * Select one citation use in the editor. Positions come from the inspected
 * text, so they apply only while the editor still has that exact text.
 */
export function selectUse<T extends SelectableSnapshot>(
  snapshot: T,
  inspectedText: string,
  use: UseLocation,
): T | null {
  if (snapshot.sourceText !== inspectedText) return null;
  if (!Number.isInteger(use.start) || !Number.isInteger(use.end) || use.start < 0 || use.end <= use.start ||
      use.end > snapshot.sourceText.length) return null;
  return { ...snapshot, rangeStartUtf16: use.start, rangeEndUtf16: use.end };
}

// --- remove, add, insert, complete -------------------------------------------

/** Confirmation text before removing an entry, or null when no confirmation is needed. */
export function removeConfirmation(key: string, citedCount: number): string | null {
  if (citedCount <= 0) return null;
  const times = citedCount === 1 ? "once" : `${citedCount} times`;
  return `“${key}” is cited ${times} in this document. Other documents were not checked. ` +
    "Remove it from the project bibliography anyway? The citation keys in the text stay as they are.";
}

/** The backend error code carried by a rejected request, if any. */
export function errorCode(error: unknown): string | null {
  const code = (error as { uiError?: { code?: unknown } } | null)?.uiError?.code;
  return typeof code === "string" ? code : null;
}

export function errorMessage(error: unknown): string {
  const message = (error as { uiError?: { message?: unknown } } | null)?.uiError?.message;
  if (typeof message === "string") return message;
  return error instanceof Error ? error.message : "The request failed.";
}

export function removeErrorMessage(error: unknown): string {
  return errorCode(error) === "BIBLIOGRAPHY_CONFLICT"
    ? "The bibliography changed since the last check. Refresh and try again."
    : errorMessage(error);
}

export interface BibliographyAddDto {
  status: "added" | "existing" | "failed";
  key: string | null;
  reasonCode: string | null;
  libraryFingerprint: string | null;
}

export type AddOutcome =
  | { kind: "added" | "existing"; key: string; message: string }
  | { kind: "failed" | "denied"; key: null; message: string };

export function addOutcome(result: BibliographyAddDto): AddOutcome {
  if (result.status !== "failed" && result.key !== null) {
    return {
      kind: result.status,
      key: result.key,
      message: result.status === "added"
        ? `Verified and added as ${result.key}.`
        : `Already in the bibliography as ${result.key}.`,
    };
  }
  return { kind: "failed", key: null, message: `Not added (${result.reasonCode ?? "unknown reason"}).` };
}

export function addErrorOutcome(error: unknown): AddOutcome {
  if (errorCode(error) === "APPROVAL_DENIED") {
    return { kind: "denied", key: null, message: "Not added: the save was not approved. Nothing was written." };
  }
  return { kind: "failed", key: null, message: errorMessage(error) };
}

export function citationFormatForPath(path: string): CitationFormat | null {
  if (/\.(md|markdown)$/i.test(path)) return "markdown";
  if (/\.tex$/i.test(path)) return "latex";
  return null;
}

export function citationInsertion(key: string, format: CitationFormat): string {
  return format === "latex" ? `\\cite{${key}}` : `[@${key}]`;
}

/** Insert text into the unsaved editor text at a UTF-16 offset (a new local revision). */
export function insertIntoSnapshot<T extends SelectableSnapshot>(snapshot: T, offset: number, text: string): T {
  const at = Math.max(0, Math.min(snapshot.sourceText.length, Math.trunc(offset)));
  const { rangeStartUtf16: _start, rangeEndUtf16: _end, ...rest } = snapshot;
  return {
    ...rest,
    editorRevision: snapshot.editorRevision + 1,
    sourceText: snapshot.sourceText.slice(0, at) + text + snapshot.sourceText.slice(at),
  } as T;
}

const LATEX_CITE = /\\(?:cite|citep|citet|parencite|textcite|autocite|nocite|Cite|Citep|Citet|Parencite|Textcite|Autocite|citealp|citealt|citeauthor|citeyear|footcite|smartcite|supercite)\*?(?:\[[^\]]*\]){0,2}\{([^{}]*)$/;
const MARKDOWN_CITE = /(?:\[|;\s*)-?@([\p{L}\p{N}_:.#$%&+?<>~/-]*)$/u;

/**
 * The key fragment being typed when the cursor follows `[@`, `; @`,
 * `\cite{` or a comma inside `\cite{...}`; null elsewhere.
 */
export function completionPrefix(linePrefix: string, format: CitationFormat): string | null {
  if (format === "latex") {
    const match = LATEX_CITE.exec(linePrefix);
    if (match === null) return null;
    const parts = match[1].split(",");
    return parts[parts.length - 1].trimStart();
  }
  const match = MARKDOWN_CITE.exec(linePrefix);
  return match === null ? null : match[1];
}

export interface CompletionCandidate {
  key: string;
  detail: string;
}

export function completionCandidates(
  entries: readonly BibliographyEntryDto[],
  prefix: string,
  limit = 200,
): CompletionCandidate[] {
  const needle = prefix.toLowerCase();
  const scored = entries
    .map((entry) => {
      const key = entry.key.toLowerCase();
      const haystack = `${entry.title} ${entry.authors.join(" ")} ${entry.year ?? ""}`.toLowerCase();
      const rank = key.startsWith(needle) ? 0 : key.includes(needle) ? 1 : needle !== "" && haystack.includes(needle) ? 2 : -1;
      return { entry, rank };
    })
    .filter(({ rank }) => rank >= 0)
    .sort((left, right) => left.rank - right.rank || left.entry.key.localeCompare(right.entry.key));
  return scored.slice(0, limit).map(({ entry }) => ({ key: entry.key, detail: describeEntry(entry) }));
}

// --- styles, preview, export ---------------------------------------------------

export type ExportFormat = "docx" | "markdown" | "bib";

/** LaTeX formats its own references, so only the bibliography exports for .tex. */
export function exportFormats(format: CitationFormat | null): ExportFormat[] {
  return format === "markdown" ? ["docx", "markdown", "bib"] : ["bib"];
}

export const EXPORT_LABELS: Record<ExportFormat, string> = {
  docx: "Word (.docx)",
  markdown: "Formatted Markdown",
  bib: "BibTeX (.bib)",
};

export interface RenderSegmentDto {
  entry: number;
  text: string;
  italic: boolean;
  bold: boolean;
  url: string | null;
}

export interface BibliographyRenderDto {
  styleId: string;
  citations: { index: number; keys: string[]; start?: number; end?: number; text: string }[];
  entries: { key: string; text: string }[];
  segments: RenderSegmentDto[];
  missing: string[];
}

export interface PreviewEntry {
  key: string;
  segments: RenderSegmentDto[];
}

/** Group the flat segment list back into one list per bibliography entry. */
export function previewEntries(render: BibliographyRenderDto): PreviewEntry[] {
  const grouped: PreviewEntry[] = render.entries.map((entry) => ({ key: entry.key, segments: [] }));
  for (const segment of render.segments) {
    const target = grouped[segment.entry];
    if (target !== undefined) target.segments.push(segment);
  }
  return grouped.map((entry, index) => entry.segments.length > 0 ? entry
    : { ...entry, segments: [{ entry: index, text: render.entries[index].text, italic: false, bold: false, url: null }] });
}

/** The bibliography.set_style params for a selection, or null when nothing should be sent. */
export function styleChangeParams(
  inspect: Pick<BibliographyInspectDto, "styleId" | "styles"> | null,
  nextStyleId: string,
  writesDisabled: boolean,
): { styleId: string } | null {
  if (inspect === null || writesDisabled || nextStyleId === inspect.styleId) return null;
  if (!inspect.styles.some((style) => style.id === nextStyleId)) return null;
  return { styleId: nextStyleId };
}
