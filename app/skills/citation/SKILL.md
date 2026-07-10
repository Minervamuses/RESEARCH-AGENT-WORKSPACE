---
name: citation
description: Interactive verified-citation workflow — search academic papers, let the user pick and confirm, save verified BibTeX bundles, and cite them with [[cite:<source-id>]] markers.
---

# Citation Skill

You drive a verified citation workflow through the `citation_workflow` tool.
The user speaks in natural language; you translate their intent into tool
actions and keep them in control of every decision.

## Workflow (strict order)

1. **Search** — `action="search"` with the user's topic as `query`. When the
   user constrains recency ("近5年", "2020–2023"), pass
   `published_within_years` OR `year_from`/`year_to` (never both).
2. **Present** — show the returned candidates to the user and WAIT for their
   choice. Never pick a candidate yourself. Use `action="more"` / `"list"` /
   `"show"` to refine or inspect on request.
3. **Resolve** — after the user picks, `action="select"` with that candidate
   id. Show the confirmable matches and WAIT again.
4. **Confirm** — only after the user explicitly approves a match in a later
   message, `action="confirm"` with the match id. Success saves a verified
   bundle and returns the source's `[[cite:<source-id>]]` marker.
5. **Cite** — cite saved sources only via their `[[cite:<source-id>]]`
   markers; write `[[citation-needed]]` where a claim has no saved source.
   The renderer assigns numbers and builds the bibliography after the
   response passes the citation gate.

## Hard rules

- Never call `confirm` in the same turn as `select`; the tool refuses it.
- Never invent or hand-write DOIs, BibTeX entries, bibliographies,
  reference numbers, or author-year citations.
- Only `[[cite:<source-id>]]` for saved verified sources and
  `[[citation-needed]]` may appear in your answers; nothing else that looks
  like a citation.
- `action="sources"` lists this session's saved sources; `action="source"`
  re-activates one for citing.
- When a search fails or a candidate has no DOI, say so plainly; never
  substitute unverified data.
