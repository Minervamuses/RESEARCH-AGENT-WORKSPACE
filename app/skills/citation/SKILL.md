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
   `published_within_years` OR `year_from`/`year_to` (never both).
2. **Present** — show the returned shortlist to the user and WAIT for their
   choice. Never pick a candidate yourself. When the user changes or narrows
   conditions, use `action="refine"` with structured keyword/year/venue/work
   type filters over the existing pool. Do not scan candidate pages to infer
   a refinement. Use `action="list"` only when the user explicitly asks to
   browse more, and `action="show"` to inspect a specific candidate.
3. **Resolve** — after the user picks, `action="select"` with that candidate
   id. Show the confirmable matches and WAIT again.
4. **Confirm** — only after the user explicitly approves a match in a later
   message, `action="confirm"` with the match id. Clear approvals include
   `儲存`, `保存`, `確認`, `可以`, `要這篇`, `就這篇`, `OK`/`okay`, `yes`,
   `confirm`, and `save`/`save it`. With one pending match, a generic approval
   refers to that match; with multiple pending matches, require one explicit
   `mX` id and ask when it is missing. Success saves a verified bundle and the
   finalizer returns a deterministic receipt with source id, DOI, bundle path,
   verification level, and the source's `[[cite:<source-id>]]` marker.
5. **Cite** — cite saved sources only via their `[[cite:<source-id>]]`
   markers; write `[[citation-needed]]` where a claim has no saved source.
   The renderer assigns numbers and builds the bibliography after the
   response passes the citation gate.

## Hard rules

- Never call `confirm` in the same turn as `select`; the tool refuses it.
- Never call `confirm` for negated, conditional, or questioning language such
  as `不要儲存`, `先別確認`, `取消`, `可以嗎?`, `no`, or `don't save`.
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
