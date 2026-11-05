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
