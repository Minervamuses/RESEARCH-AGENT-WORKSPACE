import assert from "node:assert/strict";
import test from "node:test";
import {
  addErrorOutcome,
  addOutcome,
  buildPanelModel,
  citationFormatForPath,
  completionCandidates,
  completionPrefix,
  describeEntry,
  nextExpanded,
  panelSummaryText,
  problemCount,
  removeConfirmation,
  removeErrorMessage,
  selectUse,
  type BibliographyInspectDto,
} from "../src/citations.ts";

const TEXT = "😀 Claim [@b2020; @ghost] and @a2019 again [@b2020].\n";

function inspect(overrides: Partial<BibliographyInspectDto> = {}): BibliographyInspectDto {
  const at = (key: string, from = 0) => TEXT.indexOf(`@${key}`, from);
  return {
    libraryPath: "/p/references.json",
    libraryStatus: "ok",
    libraryFingerprint: "a".repeat(64),
    libraryErrorCode: null,
    libraryError: null,
    styleId: "apa",
    styleConfigured: false,
    styles: [
      { id: "apa", name: "APA", kind: "author-date", origin: "csl-styles" },
      { id: "ieee", name: "IEEE", kind: "numeric", origin: "csl-styles" },
    ],
    documentFormat: "markdown",
    entries: [
      { key: "a2019", authors: ["Adams"], year: "2019", title: "Alpha", doi: null, type: "article", citedCount: 1 },
      { key: "b2020", authors: ["Brown", "Chen", "Diaz"], year: "2020", title: "Beta", doi: "10.1/x", type: "article-journal", citedCount: 2 },
      { key: "c2021", authors: [], year: null, title: "", doi: "10.1/x", type: "", citedCount: 0 },
    ],
    uses: [
      { key: "b2020", start: at("b2020"), end: at("b2020") + 6, line: 1, group: 0, known: true },
      { key: "ghost", start: at("ghost"), end: at("ghost") + 6, line: 1, group: 0, known: false },
      { key: "a2019", start: at("a2019"), end: at("a2019") + 6, line: 1, group: 1, known: true },
      { key: "b2020", start: at("b2020", at("a2019")), end: at("b2020", at("a2019")) + 6, line: 1, group: 2, known: true },
    ],
    order: ["b2020", "ghost", "a2019"],
    missing: ["ghost"],
    uncited: ["c2021"],
    duplicateDois: [{ doi: "10.1/x", keys: ["b2020", "c2021"] }],
    ...overrides,
  };
}

test("panel lists cited keys in first-use order with counts and issues", () => {
  const model = buildPanelModel(inspect());
  assert.deepEqual(model.cited.map((item) => [item.key, item.count, item.number]), [
    ["b2020", 2, null], ["ghost", 1, null], ["a2019", 1, null],
  ]);
  assert.equal(model.cited[1].entry, null);
  assert.deepEqual(model.missing.map((item) => item.key), ["ghost"]);
  assert.deepEqual(model.duplicates, [{ doi: "10.1/x", keys: ["b2020", "c2021"] }]);
  assert.deepEqual(model.uncited.map((entry) => entry.key), ["c2021"]);
  assert.equal(model.libraryIssue, null);
  assert.equal(model.hasDocument, true);
});

test("numeric styles number only known references in first-use order", () => {
  const model = buildPanelModel(inspect(), "ieee");
  assert.equal(model.numeric, true);
  assert.deepEqual(model.cited.map((item) => item.number), [1, null, 2]);
});

test("library errors become a problem message, not an exception", () => {
  const model = buildPanelModel(inspect({ libraryStatus: "error", libraryErrorCode: "library_malformed",
    libraryError: "references.json is not valid JSON", entries: [], uncited: [] }));
  assert.match(model.libraryIssue ?? "", /library_malformed/);
  assert.deepEqual(model.uncited, []);
});

test("entries are described compactly", () => {
  const entries = inspect().entries;
  assert.equal(describeEntry(entries[0]), "Adams 2019 · Alpha");
  assert.equal(describeEntry(entries[1]), "Brown et al. 2020 · Beta");
  assert.equal(describeEntry(entries[2]), "n.d.");
  assert.equal(describeEntry(null), "Not in the bibliography");
});

test("jumping selects the exact UTF-16 range after an emoji", () => {
  const snapshot: { editorRevision: number; sourceText: string; rangeStartUtf16?: number; rangeEndUtf16?: number } = { editorRevision: 4, sourceText: TEXT };
  const use = inspect().uses[2];
  const selected = selectUse(snapshot, TEXT, use);
  assert.ok(selected);
  assert.equal(selected.editorRevision, 4);
  assert.equal(TEXT.slice(selected.rangeStartUtf16, selected.rangeEndUtf16), "@a2019");
  assert.equal(use.start, 30); // "😀" is two UTF-16 units
  assert.equal(Array.from(TEXT).join("").indexOf("@a2019"), 30);
  assert.equal(Array.from(TEXT).findIndex((_ch, index, chars) => chars.slice(index, index + 6).join("") === "@a2019"), 29);
});

test("stale or invalid positions are not selected", () => {
  const use = inspect().uses[0];
  assert.equal(selectUse({ editorRevision: 5, sourceText: TEXT + "x" }, TEXT, use), null);
  assert.equal(selectUse({ editorRevision: 5, sourceText: TEXT }, TEXT, { start: 3, end: 3, line: 1 }), null);
  assert.equal(selectUse({ editorRevision: 5, sourceText: TEXT }, TEXT, { start: 0, end: TEXT.length + 1, line: 1 }), null);
});


test("the summary bar counts cited keys and problems, including an unreadable bibliography", () => {
  const model = buildPanelModel(inspect());
  assert.equal(problemCount(model), 2, "one unknown key and one shared DOI");
  assert.equal(panelSummaryText(model), "3 cited · 2 problems");
  const clean = buildPanelModel(inspect({ order: ["a2019"], uses: [], missing: [], duplicateDois: [] }));
  assert.equal(panelSummaryText(clean), "1 cited · 0 problems");
  const broken = buildPanelModel(inspect({
    libraryStatus: "error", libraryErrorCode: "json", libraryError: "bad", order: [], uses: [], missing: [], duplicateDois: [],
  }));
  assert.equal(panelSummaryText(broken), "0 cited · 1 problem");
});

test("the panel opens collapsed and expands by itself only for new problems or Preview", () => {
  const checked = (previousProblems: number | null, problems: number) => ({ kind: "checked" as const, previousProblems, problems });
  assert.equal(nextExpanded(false, checked(null, 0)), false, "opened without problems");
  assert.equal(nextExpanded(true, checked(null, 0)), false, "a newly opened document starts collapsed");
  assert.equal(nextExpanded(false, checked(null, 2)), true, "opened with problems");
  assert.equal(nextExpanded(false, checked(0, 1)), true, "problems appeared after a refresh");
  assert.equal(nextExpanded(false, checked(2, 2)), false, "the user collapsed it and the count did not change");
  assert.equal(nextExpanded(false, checked(1, 3)), false, "more problems of an already-seen kind keep the user's choice");
  assert.equal(nextExpanded(true, checked(2, 0)), true, "fixing problems does not collapse it");
  assert.equal(nextExpanded(false, checked(0, 0)), false);
  assert.equal(nextExpanded(false, { kind: "preview" }), true, "Preview shows its result");
  assert.equal(nextExpanded(true, { kind: "preview" }), true);
});

const clientError = (code: string, message = "backend message") => ({ uiError: { code, message } });

test("removal always asks for confirmation naming the key, the file and the unchecked documents", () => {
  const question = removeConfirmation("a2019", "/p/references.json");
  assert.match(question, /Delete “a2019” from the bibliography file \/p\/references\.json\?/);
  assert.match(question, /other documents were not checked/);
  assert.notEqual(removeConfirmation("b2020", "/p/references.json"), question);
});

test("a stale fingerprint asks for a refresh", () => {
  assert.match(removeErrorMessage(clientError("BIBLIOGRAPHY_CONFLICT")), /changed since the last check/);
  assert.equal(removeErrorMessage(clientError("BIBLIOGRAPHY_FAILED", "cannot write")), "cannot write");
});

test("add results map to added, existing, failed and denied", () => {
  assert.deepEqual(addOutcome({ status: "added", key: "k2020x", reasonCode: null, libraryFingerprint: "a".repeat(64) }),
    { kind: "added", key: "k2020x", message: "Verified and added as k2020x." });
  assert.equal(addOutcome({ status: "existing", key: "k2020x", reasonCode: null, libraryFingerprint: null }).kind, "existing");
  assert.deepEqual(addOutcome({ status: "failed", key: null, reasonCode: "exact_doi_not_found", libraryFingerprint: null }),
    { kind: "failed", key: null, message: "Not added (exact_doi_not_found)." });
  assert.equal(addErrorOutcome(clientError("APPROVAL_DENIED")).kind, "denied");
  assert.deepEqual(addErrorOutcome(clientError("PROTOCOL_INVALID", "Enter a DOI or an arXiv ID.")),
    { kind: "failed", key: null, message: "Enter a DOI or an arXiv ID." });
});

test("citation format follows the document type", () => {
  assert.equal(citationFormatForPath("/p/thesis.md"), "markdown");
  assert.equal(citationFormatForPath("/p/thesis.TEX"), "latex");
  assert.equal(citationFormatForPath("/p/notes.txt"), null);
});

test("completion triggers after [@, ; @, \\cite{ and commas", () => {
  assert.equal(completionPrefix("See [@", "markdown"), "");
  assert.equal(completionPrefix("See [@ng20", "markdown"), "ng20");
  assert.equal(completionPrefix("See [@a; @b", "markdown"), "b");
  assert.equal(completionPrefix("See [-@ng", "markdown"), "ng");
  assert.equal(completionPrefix("mail jane@doe", "markdown"), null);
  assert.equal(completionPrefix("in-text @ng", "markdown"), null);
  assert.equal(completionPrefix("\\cite{", "latex"), "");
  assert.equal(completionPrefix("\\citep[see][p. 3]{a2019, b2", "latex"), "b2");
  assert.equal(completionPrefix("\\cite{a2019} done", "latex"), null);
  assert.equal(completionPrefix("[@k", "latex"), null);
});

test("completion candidates rank key prefixes before title matches", () => {
  const entries = inspect().entries;
  assert.deepEqual(completionCandidates(entries, "b").map((c) => c.key), ["b2020"]);
  assert.deepEqual(completionCandidates(entries, "").map((c) => c.key), ["a2019", "b2020", "c2021"]);
  assert.deepEqual(completionCandidates(entries, "alpha"), [{ key: "a2019", detail: "Adams 2019 · Alpha" }]);
  assert.deepEqual(completionCandidates(entries, "zzz"), []);
});
