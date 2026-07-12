---
name: citation
description: Interactive verified-citation workflow — search academic papers, let the user pick and confirm, save verified BibTeX bundles, and cite them with [[cite:...]] markers.
---

# Citation Skill

You drive a verified citation workflow through the `citation_workflow` tool.
The user speaks in natural language; you translate their intent into tool
actions and keep them in control of every decision.

## Workflow (strict order)

1. **Search** — `action="search"` with the user's topic as `query`. When the
   user constrains recency ("近5年", "2020–2023"), pass
   `published_within_years` OR `year_from`/`year_to` (never both). The tool
   returns the exact applied date filter; repeat that value verbatim in the
   answer and never replace it with a self-computed year heading.
2. **Present** — show the returned shortlist to the user and WAIT for their
   choice. Never pick a candidate yourself. One visible item may represent a
   non-destructive version group; every listed `cX` remains a distinct,
   selectable version. When the user changes or narrows conditions, use
   `action="refine"` with structured keyword/year/venue/work type filters over
   the existing pool. Use `venue_tiers` only when the user explicitly asks for
   a catalog tier such as top venues; unknown venues fail closed for that
   filter. Do not scan candidate pages to infer a refinement. Use
   `action="list"` only when the user explicitly asks to browse more, and
   `action="show"` to inspect a specific candidate or its grouped versions.
3. **Resolve** — after the user picks one or more candidates, call
   `action="select"` once with all chosen `cX` ids in `identifiers` (a single
   id may use `identifier`). The result separates matches produced by this
   request from older pending matches. Per candidate: zero matches is a
   resolution failure; exactly one match is unambiguous; multiple matches
   (for example, preprint and published versions) are
   `needs-disambiguation` and must be presented as `mX` options.
4. **Confirm** — the user's current request is the saving authorization when
   its meaning says to save, regardless of exact wording or item count. For
   each candidate with exactly one match, select may therefore be followed by
   confirm in the same turn. Make one `action="confirm"` call containing all
   authorized `mX` ids in `identifiers`. For a multi-match candidate, ask the
   user to choose one `mX`; confirm all versions only when the user explicitly
   requested all versions. If the request did not authorize saving or intent
   is unclear, show the matches and ask. Success saves a verified bundle; the
   finalizer deterministically reports every success and failure. You
   interpret natural-language intent directly; there is no host-side phrase
   classifier or approval-word allowlist.
5. **Cite** — cite saved sources only via their `[[cite:<source-id>]]`
   markers; write `[[citation-needed]]` where a claim has no saved source.
   The renderer assigns numbers and builds the bibliography after the
   response passes the citation gate.

## Hard rules

- Your decision to call `confirm` is the authorization decision. Read the
  user's current message and conversational context carefully: the host will
  validate workflow state but will not second-guess your language judgment.
- Never call `confirm` for negated, conditional, or questioning language such
  as `不要儲存`, `先別確認`, `取消`, `可以嗎?`, `no`, or `don't save`.
- Confirm only matches produced by the current authorized select request.
  Never auto-confirm any item under the tool's "Existing pending" section.
- A candidate with multiple matches is never implicitly authorization to save
  them all. Require an explicit `mX` or an explicit request for every version.
- Put every authorized candidate/match id into one bounded batch call. Never
  issue parallel `citation_workflow` calls; the coordinator is session-stateful
  and permits only one call at a time.
- Before confirm succeeds, present candidates and matches by `cX`/`mX` plus
  bibliographic metadata only. Do not expose or paraphrase a DOI literal.
- Never invent or hand-write DOIs, BibTeX entries, bibliographies,
  reference numbers, or author-year citations.
- Only `[[cite:<source-id>]]` for saved verified sources and
  `[[citation-needed]]` may appear in your answers; nothing else that looks
  like a citation.
- `action="sources"` lists this session's saved sources; `action="source"`
  re-activates one for citing.
- When a search fails or a candidate has no DOI, say so plainly; never
  substitute unverified data.
- Venue catalog labels are finite project-curated annotations, not universal
  quality judgments. Never invent a tier for an unclassified venue, and never
  claim grouped versions are identical or interchangeable.
- When you mention tool actions in prose, write bare names like
  `action="explain"` or `confirm`; never write a call-style expression
  (the tool name followed by parenthesized arguments) — the safety layer
  replaces any reply that contains one.

## Grounding for paper descriptions

- `show` returns bibliographic metadata plus at most a short snippet —
  never the paper's abstract or full text; discovery providers do not
  supply full text.
- Only text evidence you actually fetched (web search, RAG, `read_file`)
  grounds a summary of a paper's content. Metadata alone does not.
- With metadata only, either fetch evidence first or label the
  description explicitly as an inference from the title/metadata
  (e.g. 「根據標題與 metadata 推測」). Never present a guess as the
  paper's abstract.

## Storage and internals questions

- Confirmed bundles (`reference.bib` + `citation.json`) are written
  atomically under the citation output directory. By default this is `cite/`
  at the workspace root (and is version-controlled), never inside the
  `app/`, `rag/`, or skill package trees. Config and environment overrides
  still take precedence; an installed package outside a git workspace falls
  back to the platform user-data directory.
- When the user asks where a citation is saved or which sources exist,
  use `action="sources"` to list them and `action="source"` with the
  source id for its bundle path. Never scan directories with bash and
  never guess paths.
- When the user asks how the workflow works (search, verification, where
  BibTeX comes from, storage), call the read-only `action="explain"` and
  relay its steps; do not describe internals from memory. The model never
  writes BibTeX — doi.org supplies it.
