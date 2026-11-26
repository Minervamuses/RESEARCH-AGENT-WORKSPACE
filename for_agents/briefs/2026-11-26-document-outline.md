# Brief: Document Outline & LaTeX Highlighting

<!-- for_agents: verified=e1ae814 date=2026-11-26 -->

> Pre-change analysis. It informs a plan; it does not authorize or schedule work.

## Intent

Add a client-side **Document Outline** panel left of the Monaco editor in the desktop GUI for `.md`, `.markdown`, and `.tex` files, plus P1 **LaTeX syntax highlighting** (replacing `"plaintext"` mode while preserving `\cite{` completion). Success criteria:

1. Open, edit, save, Undo/Redo, Agent `document_edit`, and conflict resolution all derive one hierarchical outline from `sourceText` (never persisted to disk, `RESEARCH.md`, or Agent context; no LLM tokens or LaTeX compilation).
2. Clicking a heading jumps Monaco to its UTF-16 position without changing `sourceText`/`editorRevision`, starting Save/Agent work, clearing undo history, recreating the editor, or creating a non-empty selection (`Add comment`).
3. Active-section tracking follows cursor (editing) and viewport (reading), keeps collapse state across re-parses, marks collapsed ancestors, clears on file switch/close, and avoids scroll/jump loops.
4. P1 LaTeX highlighting visually distinguishes commands, sections, environments, comments, math, citations, references, and brackets without breaking `\cite{` / `\citep{` / `\citet{` / `\textcite{` completion.

**Baseline note:** Spec cites `816afd9`; verified against `GUI` HEAD `e1ae814` (19 cleanup/atlas commits, no incompatible document/editor/citation changes). Scope is single-file File Outline only (no `\input`/`\include`, TeX macro expansion, PDF preview, drag-reorder, or Agent/RAG changes).

## Current state

See [ui-architecture](../ui-architecture.md#surfaces), [document flow](../flows.md#flow-document-open-zoom-citekey-completion-save-and-gated-document_edit), and [playbooks](../change-playbooks.md#playbooks). Five facts verified at `e1ae814` shape this change:

1. **Monaco lifecycle & modes (`app/desktop/src/DocumentEditor.tsx::DocumentEditor`):** Dynamically loads local `monaco-editor` `0.57.0`, worker, and `markdown` registration inside a `useEffect` keyed on `[value?.rootPath, value?.path]`. Sets `automaticLayout: true` and **`scrollBeyondLastLine: false`**. Uses `"markdown"` for `.md`/`.markdown` and `"plaintext"` for `.tex` (Monaco's `esm/vs/languages/definitions/` ships 81 languages, no LaTeX). Citation completion binds to `model.getLanguageId()` (`triggerCharacters: ["@", "{", ","]`, `app/desktop/src/citations.ts::completionPrefix`).
2. **Selection publishing & external sync (`app/desktop/src/DocumentEditor.tsx`, `app/desktop/src/App.tsx`):** `publishSelection` (on `onDidChangeCursorSelection`) calls `onChange({ ...current, rangeStartUtf16, rangeEndUtf16 })` -> `App.tsx::updateDocument` -> `setDocumentValue` on **every** cursor move (including programmatic `setPosition`), so each one already re-renders `App`; scrolling does not. The second `useEffect` applies external edits via `executeEdits` under `incomingRef` (keeping undo stops) and moves the view only when both range fields are set — the `CitationPanel.tsx::jump` (`citations.ts::selectUse`) path, which pops up `referenceWidget` (`Add comment`).
3. **UTF-16 offsets, BOM & CRLF (`app/desktop/src/lib/documentSource.ts`):** `documentPositionAt` / `documentOffsetAt` index raw `sourceText` in UTF-16 code units (leading `\uFEFF` BOM at offset `0`, `\r\n` = 2 units), whereas `DocumentEditor.tsx::modelSource` strips leading `\uFEFF` from the Monaco model. `app/agent/desktop/documents.py::MAX_TEXT_BYTES` caps files at `1 MiB` (`1,048,576` B) for `.md`, `.markdown`, `.tex`.
4. **Layout & narrow default width (`app/desktop/src-tauri/tauri.conf.json`, `app/desktop/src/styles.css`, `app/desktop/src/styles/document.css`):** Window `1080x720` (min `720x560`); `Sidebar` gets `minmax(10.15rem, 11.9rem)` (190 px at 16 px root); `.writing-workspace` splits ~890 px `1.05fr`/`1fr`, so **`.document-pane` is ~456 px** at launch (1 column at `max-width: 1050px`). `app/desktop/src/main.tsx` imports 7 plain CSS files in fixed order (zero CSS `@import`).
5. **Dependencies & tests (`app/desktop/package.json`):** No direct Markdown parser (`marked` is only a transitive `monaco-editor` dep, no UTF-16 offsets). `npm test` runs `node --test --experimental-strip-types tests/*.test.ts` plus Vite SSR for `.tsx` (`app/desktop/tests/documents.test.ts`); no layout engine or live Monaco worker (`ASM-025`).

## Touch points

Primary playbook: `PLAY-003` (panel + stylesheet) with `PLAY-002` UI conventions, **departing from `PLAY-002`** because all outline state stays inside `DocumentPane` (zero backend RPCs, zero `App.tsx` async admission). `PLAY-006` applies **only** if an external Markdown npm parser is approved (`AGENTS.md`).

1. **Pure outline modules under `app/desktop/src/lib/` (new `lib/outline/{types,markdown,latex,tree,tracking,index}.ts`):**
   - `types.ts`: `OutlineNode` (`id`, `title`, `level`, `depth`, `lineNumber`, `startOffsetUtf16`, `headingEndOffsetUtf16`, `sectionEndOffsetUtf16`, `children`), `OutlineResult` (tree + flat pre-order list + `sourceText` stamp). Avoid TS `enum`/`namespace` so Node `--experimental-strip-types` imports directly.
   - `markdown.ts`: BOM/CRLF-aware UTF-16 scanner for ATX H1-H6 (including optional closing `#`) and Setext `===`/`---`, stripping inline markup; skips YAML front matter, fenced/indented code, HTML comments, blockquotes, and lists.
   - `latex.ts`: Single-pass UTF-16 scanner for `\part`..`\subparagraph` (starred, `[short]`, multiline/nested `{...}`, inline command unwrapping); skips `%` comments (incl. `\\%`), `verbatim`/`lstlisting`/`minted`/`comment` envs, `\verb`, and `\newcommand`/`\renewcommand`/`\providecommand`/`\def` bodies (stricter than `app/skills/citation/citekeys.py::_mask_latex`).
   - `tree.ts`: Relative-hierarchy stack computing `sectionEndOffsetUtf16`, visual `depth`, and **stable structural IDs**: root path of `(level, normalizedTitle, ordinal)` segments, where `ordinal` counts only earlier **same-parent siblings with the same level and title** (not all siblings). Adding/removing an unrelated heading leaves other IDs unchanged; duplicate `Results` stay distinct (`…/2:results:0`, `…/2:results:1`); only renaming a heading or ancestor changes its ID.
   - `tracking.ts`: `O(log H)` binary search for active heading by 1-based line (cursor or viewport top), collapsed-ancestor lookup, and the pure jump-guard state machine (see touch point 3).
2. **P1 LaTeX Monarch grammar under `app/desktop/src/lib/` (new `lib/latexLanguage.ts`):** Monarch tokenizer + `LanguageConfiguration` with idempotent `registerLatexLanguage(monaco)` guard. Tokenize `\cite{...}` keys as `identifier`, never a name containing `string`/`comment`. In `monaco-editor` `0.57.0` (`suggest/browser/suggestModel.js`) trigger-character completion (`@`, `{`, `,`) ignores token type, so only **quick suggestions** (default `strings`/`comments: off`) are at risk: the popup re-opening while typing key letters after Escape or Backspace.
3. **`app/desktop/src/DocumentEditor.tsx::DocumentEditor`:**
   - Expose imperative jump handle (`jumpToOffset(offsetUtf16)`) using `app/desktop/src/lib/documentSource.ts::documentPositionAt` -> `setPosition(pos)` (collapsed cursor, never non-empty selection) + `revealLineNearTop(pos.lineNumber)`. The jump still passes through `publishSelection` -> `App.tsx::updateDocument` like any cursor move (one `App` render, empty range, no `Add comment`); do not mask it with `incomingRef`, since `App` must keep the real cursor snapshot.
   - **Jump guard ordering:** arm the guard (target heading ID) **before** `setPosition`. `setPosition` fires a cursor event and `revealLineNearTop` a scroll event, both synchronously; neither may release the guard, or the reveal scroll recomputes the active section from the viewport top and reproduces the bottom-of-file bounce. Record `getScrollTop()` after the reveal; release only on a later scroll to a different `scrollTop` or a cursor position other than the target.
   - Add `onCursorLineChange` (`onDidChangeCursorPosition`) and rAF-batched `onVisibleTopLineChange` (`onDidScrollChange` gated by `scrollTopChanged`, reading `getVisibleRanges()[0]?.startLineNumber`). Dispose both + cancel rAF in `disposeEditor`.
   - Keep `[value?.rootPath, value?.path]` as sole model-creation dependency; register `"latex"` once before `createModel` for `.tex` (P1).
4. **Presentational outline panel under `app/desktop/src/components/` (new `components/DocumentOutline.tsx`):** Prop-driven tree rendering heading titles as plain React text (`INV-017`), expand/collapse chevrons, active & collapsed-ancestor cues, empty state (`No headings found`), and P1 keyboard arrows/Enter.
5. **`app/desktop/src/components/DocumentPane.tsx::DocumentPane`:**
   - Own outline state locally: ~180 ms debounced parse keyed on `[document?.rootPath, document?.path, document?.sourceText]` (**never `[document]`**), immediate on open, cleared on switch/`null`; `collapsedIds` (reset on file change), `activeSectionId`, `outlineOpen` (P1 `localStorage`, `app/desktop/src/editorZoom.ts` pattern).
   - Add `Outline` toggle in `DocumentHeader` and horizontal `.document-body` wrapper around `DocumentOutline` + `DocumentEditor`, above `CitationPanel` and `DocumentConflictPanel`.
6. **Stylesheets (`app/desktop/src/styles/document.css`, new `styles/outline.css`, `app/desktop/src/main.tsx`):** Add `.document-body` split and `.document-outline` rules, and an explicit `import "./styles/outline.css";` after `document.css` in `app/desktop/src/main.tsx` (Sync point row 10 in [change-playbooks](../change-playbooks.md#sync-points)). **Cascade order:** `main.tsx` loads `responsive.css` *before* `document.css`, so the later `outline.css` overrides same-specificity rules there. Keep the outline's narrow-window rules in `@media` blocks inside `outline.css` (as `document.css` does at `1050px`/`760px`), not in `responsive.css`.
7. **Tests & docs (`app/desktop/tests/`, `README.md`):** Add `tests/outline.test.ts`, extend `app/desktop/tests/styles.test.ts` (assert `main.tsx` imports `outline.css`), and document Outline & LaTeX support in `README.md`.
8. **Conditional (`app/desktop/package.json` + `package-lock.json`):** Edited only if Option B (npm Markdown parser) is approved (`PLAY-006`).

## Blast radius

| Consumer | Needs edit? | Could break if... |
|---|---|---|
| `app/desktop/src/App.tsx::App` | No | Jump sets a non-empty range (reaches `addDocumentReference`/`sendTurn`), or outline/scroll state moves into `App` (render per scroll frame). One render per jump via `publishSelection` is existing cursor behavior |
| `app/desktop/src/DocumentEditor.tsx` (`referenceWidget`, `annotationWidgets`, `completion`, undo) | Yes | Jump creates a selection, model is recreated (undo lost), listeners leak on switch, or LaTeX tokens stop quick suggestions |
| `app/desktop/src/CitationPanel.tsx::CitationPanel` & `app/desktop/src/citations.ts` | No (verify) | `.document-body` flex height starves `.citation-panel`, or `"latex"` registration alters `completionPrefix` |
| `app/desktop/src/lib/documents.ts` | No | Outline alters `editorRevision`, `diskFingerprint`, or `DocumentContextDto` |
| `app/desktop/src/components/ApprovalDialog.tsx::ApprovalDialog` | No | `.document-outline` z-index covers the non-modal `.document-approval-backdrop` |
| `app/desktop/tests/styles.test.ts` | Extend | `:root` clamp changes (`INV-021`) or `main.tsx` drops/reorders the `outline.css` import |
| `app/desktop/src/styles/responsive.css` | No | Outline narrow rules put here lose to later `outline.css` (overflow at `1080x720`/`720x560`) |
| `main.py::_release_is_current` | No | Auto-rebuilds Tauri when `app/desktop/src` or `package.json` changes |
| Backend (`app/desktop/protocol/v1/contract.json`, `app/agent/desktop/documents.py`, `app/agent/document_context.py`, `app/agent/desktop/project.py`) | No | Must stay untouched (no wire fields, `RESEARCH.md` keys, or Agent context) |

## Invariants at stake

| Concern | Invariants | Risk & preservation |
|---|---|---|
| LF line endings | `INV-002` | New files keep LF per `.gitattributes` |
| Wire & backend boundary | `INV-011`, `INV-015`, `INV-035` | Outline is client-derived in `DocumentPane` for the single open file; no `protocol.ts` or backend edits |
| Project metadata | `INV-016` | No outline keys in `RESEARCH.md` (`FAIL-026`); WebView `localStorage` only |
| XSS / safe rendering | `INV-017` | Heading titles as plain React text, never `dangerouslySetInnerHTML` |
| Typography & zoom | `INV-021` | Leave `:root` clamp, `editorZoom.ts` (`16px`/`lineHeight: 0`), and `.citation-panel >= 0.9rem` untouched |
| Keyboard & IME | `INV-022` | P1 arrow/Enter keys only on focused `DocumentOutline` elements |
| Document & citation integrity | `INV-025`, `INV-032` | Jump is read-only (`setPosition` + `revealLineNearTop`); verify completion in `"latex"` mode |
| Frozen turn & prompt budget | `INV-026`, `INV-034` | Never inject outline into `DocumentContextDto`, `SubmittedContext`, or LLM replay |
| Offline bundling & hygiene | `INV-029` | Bundle parser/grammar locally via Vite (no CDN); build outputs git-ignored |

## Failure modes

| Failure | Trigger | Detection | Handling | User sees |
|---|---|---|---|---|
| Bottom-of-file active bounce | Clicking last heading; `scrollBeyondLastLine: false` leaves an earlier section at viewport top | `tracking.ts` test replaying jump cursor -> reveal scroll -> user scroll; GUI test | Jump guard (touch point 3) | Clicked heading stays highlighted |
| Stale jump during debounce | Clicking before the ~180 ms debounce flushes | `outline.sourceText !== document.sourceText` on click | Re-parse synchronously (or clamp offset) | Accurate jump; never throws |
| Malformed syntax stall | Mid-typing `\section{Intro`, `{{{`, unclosed ` ``` ` or `<!--` in 1 MiB file | Adversarial & incomplete-syntax parser tests | Linear state-machine scanners (no backtracking regexes); skip incomplete tail | Valid earlier headings stay usable |
| BOM / CRLF / emoji offset drift | Leading `\uFEFF`, `\r\n`, or emoji before headings | Unit tests pairing parser offsets with `documentPositionAt` | Index raw `sourceText` UTF-16 offsets directly without normalizing newlines | Jump lands on exact line/column |
| Collapse wipe / duplicate collision | Typing or inserting a heading above; two `Results` siblings | Edit-above, insert-above & duplicate-title tests | Same-title-ordinal path IDs (touch point 1); reset only on file switch | Collapsed state persists; duplicates distinct |
| Stale outline or leaked listeners | Switching file or project (`document = null`) mid-debounce | Lifecycle cleanup tests + manual switch | Cancel debounce & rAF on `[rootPath, path]` change; clear on `null`; dispose Monaco listeners | No stale headings or duplicate listeners |
| Re-parse on every arrow key | `publishSelection` emits a new snapshot per cursor move | Parse call-count test | Parse effect keyed on `[rootPath, path, sourceText]`, never `[document]` | Cursor move runs `O(log H)` lookup only |
| LaTeX grammar breaks citekey completion | Cite keys tokenized as `string`/`comment` (quick suggestions stop), or repeated `register()` | Manual WSLg: popup on `\cite{` / `,` and on typing after Escape; idempotent-register test | Register `"latex"` once; keys as `identifier` | Completion as in Markdown mode |
| `localStorage` throws | Restricted WebKitGTK profile | Throwing-storage test (`editorZoom.test.ts` pattern) | `try/catch`, fall back to default | Panel works, state unsaved |
| Narrow-window editor crush | Outline open at `1080x720` (~456 px pane) | Manual WSLg at `1080x720` / `720x560` | Default collapsed or overlay; `.document-editor` `min-width: 0` | Editor readable, no overflow |

## Performance impact

- **Parsing (`O(N)`, cap `1 MiB` per `app/agent/desktop/documents.py::MAX_TEXT_BYTES`):** Single-pass UTF-16 scan with ~180 ms edit debounce targets `< 15 ms` at 100 KB and `< 50 ms` at 1 MiB (`inferred`); immediate on file open / Agent edits.
- **Cursor & scroll (`O(log H)`):** Look up the active heading by Monaco line number against cached `lineNumber`s (no extra `documentOffsetAt` scan beyond the one `publishSelection` already does); rAF-batched `onDidScrollChange` never re-parses.
- **Render isolation:** Local state in `DocumentPane` keeps `App.tsx`, `Sidebar`, `Transcript`, `Composer`, and `CitationPanel` out of **scroll-tracking, collapse, and toggle** re-renders. Cursor moves and jumps still render `App` once each via the existing `publishSelection` path; the outline adds none.
- **Bundle & cost:** Zero LLM tokens, IPC traffic, or subprocesses. Zero-dep parser + Monarch grammar adds ~15-25 kB raw (~5-8 kB gzip) to `app/desktop/dist/` (baseline `index` 393 kB + lazy `editor.api` 2.70 MB, `measured 2026-11-26`).
- **Measurement:** Throwaway Node script timing 100 KB / 1 MiB docs (1,000 headings) + 10,000 lookups; diff `npm run build` sizes.

## UI and UX

- **Surfaces:** `DocumentPane` adds a `.document-body` horizontal split (`DocumentOutline` left of `DocumentEditor`, above `CitationPanel` / `DocumentConflictPanel`) and an `Outline` toggle in `DocumentHeader`. `DocumentEditor` adds P1 LaTeX highlighting.
- **Controls and actions to add** (for [ui-architecture](../ui-architecture.md#controls-and-actions)):

| Control | Location | Handler | Effect / backend call | Enabled when | Busy / error behavior |
|---|---|---|---|---|---|
| `Outline` toggle | `DocumentHeader` | `DocumentPane` local toggle | Show/hide panel (P1: `localStorage`); no RPC | `document !== null` | Enabled during turns/approvals (read-only) |
| Heading row | `DocumentOutline.tsx` | `DocumentPane::jumpToHeading` | `jumpToOffset` + active highlight | Always | Sync re-parse/clamp if stale |
| Collapse chevron | `DocumentOutline.tsx` | `DocumentPane::toggleCollapsed` | Toggle `node.id` in `collapsedIds` | Has children | Kept across re-parses |
| Resize handle (P1) | Outline right edge | `DocumentPane` pointer drag | Width `160`-`320` px | Open on wide layout | Monaco `automaticLayout` reflows |

- **States to design:** *No file open* (hide panel, disable toggle, no prior-file residue); *Empty* (`No headings found`); *Before first heading* (no active item); *Collapsed parent of active* (cue on nearest visible ancestor, no auto-expand); *Long/CJK/deep titles* (ellipsis + `title`, indent capped at `min(depth, 5) * 0.7rem`); *Narrow (`1080x720`, `<= 1050px`, `<= 760px`)* (collapsed or overlay so Monaco is never crushed); *Focus* (updates never steal Monaco focus).
- **Styling:** Reuse the warm light palette (`#fbfbfa`, `#dedfdd`, `#236c55`, `#343942`, `#66716d`) in `styles/outline.css` (touch point 6); keep `INV-021` untouched.

## Verification plan

| Check | Touch point / risk | Command / method |
|---|---|---|
| Markdown & LaTeX parser unit suite (every construct listed in touch point 1, plus duplicates, skipped levels, CJK/emoji/CRLF/BOM, incomplete syntax, empty) | `lib/outline/{markdown,latex,tree}.ts` | `cd app/desktop && npm test` (`tests/outline.test.ts`) |
| UTF-16 offset parity with `documentPositionAt` / `documentOffsetAt` | `app/desktop/src/lib/documentSource.ts` | `tests/outline.test.ts` on BOM+CRLF+emoji fixtures |
| Tracking & navigation logic (cursor vs scroll, collapsed ancestor, bottom-of-file jump guard, stable IDs across edits, file-switch reset, stale click) | `lib/outline/tracking.ts` | `cd app/desktop && npm test` |
| SSR & XSS safety (`DocumentOutline` empty/nested/collapsed/HTML-escaped titles) | `DocumentOutline.tsx`, `INV-017` | `cd app/desktop && npm test` (Vite SSR `renderToStaticMarkup`) |
| LaTeX Monarch config & citation completion regression | `lib/latexLanguage.ts`, `app/desktop/src/citations.ts` | `cd app/desktop && npm test` (`tests/outline.test.ts`, `tests/citations.test.ts`) |
| Typecheck, build, and CSS load-order check | `tsconfig.json`, `tsconfig.test.json`, `main.tsx`, `INV-021` | `cd app/desktop && npm run build` + `tests/styles.test.ts` |
| 100 KB / 1 MiB parse & lookup benchmark | Scaling ceiling (`MAX_TEXT_BYTES`) | Throwaway Node script in temp dir (`< 50 ms` at 1 MiB) |
| Manual WSLg GUI acceptance (`ASM-025`) | Live Monaco worker, `1080x720` & `720x560` layout, 28 px zoom, scroll tracking, bottom-heading jump, `.tex` citekey popup on `\cite{` / `,` and on typing after Escape, Undo/Redo, Agent `document_edit` + Conflict sync, focus retention | `python main.py` on the 7 spec acceptance docs |

## Options

### 1. Markdown heading parser
| Option | Blast radius | Risk | Cost | Reversibility |
|---|---|---|---|---|
| **A. Zero-dependency CommonMark heading scanner (`lib/outline/markdown.ts`)** *(Recommended)* | Local under `app/desktop/src/lib/` | Medium: must cover CommonMark block/inline edge cases with thorough tests | ~250-350 LOC; 0 new deps; ~5-8 kB gzip; native BOM/CRLF UTF-16 offsets | High (isolated behind `OutlineNode`) |
| **B. `mdast-util-from-markdown` + frontmatter extensions** | `PLAY-006` (~25+ transitive pkgs) | Low parse risk; still needs BOM offset wrapper | ~60-100 kB min; needs user dep approval | Medium (lockfile churn) |
| **C. `markdown-it` + frontmatter plugin** | `PLAY-006` | Line ranges only (`token.map`), normalizes newlines | Medium + offset mapping; needs approval | Medium |

**Recommendation:** **Option A** — raw-source UTF-16 offsets, repo's minimal-dependency style, no `PLAY-006` churn, swappable behind `lib/outline/index.ts`.

### 2. Outline panel placement & default visibility at `1080x720`
| Option | Blast radius | Risk | Cost | Reversibility |
|---|---|---|---|---|
| **A. Inside `DocumentPane` left of `DocumentEditor`, collapsed by default (or overlay on narrow panes)** *(Recommended)* | Local to `DocumentPane.tsx` + CSS | Low: protects ~456 px `.document-pane` at `1080x720`; matches `CitationPanel` | Small; zero `App.tsx` state | High |
| **B. Inside `DocumentPane`, open by default (~200 px)** | Same as A | High UX risk at `1080x720`: shrinks Monaco to ~256 px (~25 chars) | Small | High |
| **C. Top-level column in `.writing-workspace` (`App.tsx`)** | Touches `App.tsx` (1,928 LOC) | Adds state/re-renders to `App.tsx` and separates outline from `DocumentHeader` | Medium | Medium |

**Recommendation:** **Option A**, optionally widening `.writing-workspace` left track on wide windows (`>= 1280px`) when open.

### 3. Outline <-> Monaco navigation & tracking channel
- **Single reasonable approach:** Imperative `jumpToOffset` handle + direct `onCursorLineChange` / `onVisibleTopLineChange` callbacks between `DocumentPane` and `DocumentEditor`. The `CitationPanel` path (pushing a ranged `DocumentContextDto` through `App.tsx::updateDocument`) moves the editor only with a non-empty range, which triggers `Add comment`; scroll tracking in `App` would render it every frame.

## Open decisions

1. **Markdown parser dependency (`AGENTS.md` / `PLAY-006`):** Use zero-dependency CommonMark heading scanner *(default)*, or approve adding `mdast-util-from-markdown` + frontmatter packages to `app/desktop/package.json`?
2. **Default Outline visibility on file open:** Collapsed by default with `Outline` toggle in `DocumentHeader` *(default, avoiding a ~256 px Monaco column at `1080x720`)*, or open by default (always / above `1280px`)?
3. **Focus after clicking an outline heading:** Move focus to Monaco editor *(default)*, or keep focus in the Outline panel?
4. **Scroll alignment on jump:** `revealLineNearTop` *(default)* or `revealPositionInCenter`?
5. **P1 delivery split:** Ship LaTeX syntax highlighting + `localStorage` visibility preference with P0 *(default, zero new deps)* and defer drag-resize handle, or ship P0 strictly before P1?

## Atlas corrections

- **`for_agents/change-playbooks.md` (Sync points row 7):** `app/desktop/tests/styles.test.ts` asserts only the `:root` `clamp(...)`; `.citation-panel >= 0.9rem` is manual-only (verified at `e1ae814`, fixed).
