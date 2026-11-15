---
name: writing-genres
description: Use when the user wants to write or reformat a piece as one of seven genres - thesis or paper (論文), teaching material (教材), notes (筆記), proposal (計劃書), abstract (Abstract), poster (Poster) or slides (投影片) - and needs that genre's structure, length conventions, default file format and extension, how to write the file, and how to convert it. Not for argument checking (use @grill) or detailed academic writing advice (use @academic-paper-writing).
---

# Writing Genres

Pick the genre first, then write to that genre's conventions. The user's own
instructions, a template they supply, or a venue's or department's rules
always override the defaults below.

## Rules for every genre

1. **Identify the genre and reader.** If the request does not make the genre
   clear, ask one short question before writing a whole file.
2. **Prefer an editable source.** The desktop editor opens only `.md`,
   `.markdown` and `.tex` (up to 1 MiB), and only an open file can be selected
   and edited there. Write the source as `.md` unless the genre below says
   otherwise. Other outputs (`.docx`, `.pptx`, `.pdf`, `.html`) are converted
   from that source and cannot be selected and edited in the editor; say so
   before producing one.
3. **Write files with bash.** Write to the path the user gives, or to a
   sensible path inside the project (for example `drafts/<name>.md`). Write
   each file in one bash call so the user approves it once (under Ask, every
   bash call needs approval), use `set -o noclobber` so an existing file is
   never overwritten without the user saying so, and tell the user the exact
   path afterwards. A newly written file is not open in the editor: the user
   opens it there to select and edit it.
4. **Citations are bibliography keys.** Write `[@key]` or `[@a; @b]` in
   Markdown and `\cite{key}` in LaTeX, using keys from the project
   bibliography; never type author-year or numbered references yourself and
   never invent a key. The rendered reference list appears at export time.
5. **Mark what is missing instead of inventing it:** `[TODO: …]` for missing
   text, data or a step, `[CITE: …]` for a source still to be found,
   `[FIGURE: …]` for a figure or table to be made. The BIME Word export drops
   `[TODO: …]`; `[CITE: …]` and `[FIGURE: …]` stay visible until replaced.
6. **Converting.** Pandoc is available in the project environment. From a
   Markdown document with citations, the Citation panel's Export menu writes
   Word (`.docx`), Word in the NTU BIME Appendix 17 thesis format, or Markdown
   with rendered references. `.tex` sources format their own references and
   have no Export entry; compiling LaTeX needs a TeX installation, which may
   not exist on this machine - check with `command -v latexmk` and never
   install software without the user's approval.
7. **Division of labour.** For scholarly argument, section-level academic
   writing and journal fit in papers and proposals, the user can add
   `@academic-paper-writing`. To check whether a passage's argument holds, use
   `@grill`, which never edits. This skill covers form: structure, format and
   files.

## The seven genres

### 論文 (thesis chapter or paper)

- Reader: examiners, reviewers, researchers in the field.
- Structure: title, abstract and keywords, introduction (problem, gap, aim),
  related work or background, methods, results, discussion (meaning,
  limitations), conclusion, references. Theses may add front matter
  (acknowledgements, table of contents) per the department's rules.
- Length: set by the venue or department; ask when unknown.
- Default file: `.md`, one file per chapter for a thesis (`ch1-introduction.md`)
  or one file for a paper. Use `.tex` only when the venue requires a LaTeX
  template the user supplies.
- Output: Citation panel Export → Word, or Word (BIME Appendix 17) for an NTU
  BIME thesis.

### 教材 (teaching material)

- Reader: learners at a stated level; say who it is for at the top.
- Structure: learning objectives, prerequisites, sections that each explain
  one idea with a worked example, exercises, answers or hints, a short
  summary. Use headings learners can scan.
- Default file: `.md`.
- Output: Export → Word, or `pandoc material.md -o material.html` for a web
  page (not editable in the editor).

### 筆記 (notes)

- Reader: the user later, or close collaborators.
- Structure: header with date, topic and sources (bibliography keys);
  key points as bullets; direct quotes marked as quotes with their key;
  the user's own thoughts kept in a separate section from what sources say;
  open questions and `[TODO: …]` items at the end.
- Default file: `.md`, one file per topic or meeting.
- Output: usually none; keep it as Markdown.

### 計劃書 (proposal)

- Reader: reviewers, an advisor, or a funding committee.
- Structure: title, summary, background and problem, research questions or
  aims, methods (design, data, analysis) matched to each aim, expected
  results and contribution, risks and alternatives, timeline, budget when the
  call asks for one, references.
- Length: follow the call or department form; ask when unknown.
- Default file: `.md` (`.tex` only for a supplied LaTeX form).
- Output: Export → Word when a form must be filled in Word.

### Abstract

- Reader: someone deciding whether to read the full work.
- Structure: one paragraph (or the venue's structured headings): background,
  objective, method, main result with its key number, conclusion and its
  limit; then keywords. No citations unless the venue allows them.
- Length: the venue's limit; commonly 150–300 English words or 300–500
  Chinese characters. State the count in the reply.
- Default file: `.md`, the abstract alone (`abstract.md`), so it can be
  selected and edited on its own.

### Poster

- Reader: people walking past at a conference; readable from about two
  metres.
- Structure: title and authors, a one-sentence take-home message, then
  blocks: question, method (a diagram rather than prose), key results (one or
  two figures), conclusion, references and contact. Keep text short: roughly
  300–800 words in total.
- Default file: `.md` with one `##` heading per block and `[FIGURE: …]`
  markers, as the content draft; the user lays it out in their poster tool.
  If the user has TeX and wants a LaTeX poster, write `.tex` with the
  `tikzposter` class instead (check `command -v latexmk` first).
- Output: the layout tool's PDF; it cannot be edited in the editor.

### 投影片 (slides)

- Reader: an audience listening to a talk; one idea per slide.
- Structure: title slide, outline, one slide per point with at most about six
  short lines, figures as `[FIGURE: …]`, a summary slide, a references slide.
  Plan about one slide per minute of talk.
- Default file: `.md` in Pandoc slide form: `# Section` for section slides,
  `## Title` for each slide, speaker notes in `::: notes` blocks.
- Output: `pandoc slides.md -o slides.pptx` for PowerPoint (no TeX needed),
  or `pandoc -t revealjs -s slides.md -o slides.html`. The `.pptx` and
  `.html` cannot be edited in the editor; edit the `.md` and convert again.
