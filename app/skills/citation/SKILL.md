---
name: citation
description: Stateless work-identity citation resolution, verified bundle saving, and [[cite:...]] rendering.
---

# Citation Skill

Use only `citation_workflow` to discover or select a persistent citation
identity. Its actions are `search`, `save`, `sources`, `source`, and `explain`.
Use Web/RAG to read or summarize content when needed, but treat any DOI found
outside this workflow as an untrusted clue; never save it directly.

## Search and present

- `search` is stateless. Pass a natural-language topic/title in `query` and
  optional `year_from`/`year_to`; never pass Crossref, DataCite, or OpenAlex
  query syntax.
- Present each result with full title, authors, year, venue, work type, and
  version label. Search order is never a save identifier; there are no cX/mX
  identifiers or persistent candidate pools.
- Metadata does not ground a content summary. Fetch actual text or explicitly
  label any title-based description as inference.

## Save

- A save call contains one `works` array (1–10 self-contained WorkIntent
  objects). Include `requested_label` plus every known title/author/year/venue/
  type/DOI/arXiv/version fact. Never pass a result position or legacy ID.
- Put each independently known fact in its own WorkIntent field. Never encode
  authors, years, venues, or provider syntax inside `title` or another field.
  The workflow owns provider-specific query construction and escaping.
- Make at most one valid `save` call in a user turn. Put every authorized work
  in that one batch. After any attempted outcome—success, ambiguity, not found,
  provider failure, or insufficient intent—do not silently change the query or
  try a second mutation.
- Save only when the current request authorizes it. Negated, conditional,
  questioning, or unclear intent is not authorization.
- Generic references such as 「這篇」 do not choose published/VoR, preprint,
  repository, or another manifestation. If the visible metadata does not make
  the requested version explicit, ask the user which version they mean.
- `original` never defaults to either original work or earliest manifestation.
  Ask the user to distinguish those meanings, then encode `work_kind` or the
  version request explicitly.
- A hard user constraint or target identifier is a veto when it contradicts a
  provider record. Never trade identity precision for recall and never replace
  an unsupported published/no-DOI record with a similar preprint DOI.
- A provider's first result, relevance score, top-level DOI, or primary
  location is not an identity decision. Preserve ambiguity among aliases,
  preprints, accepted manuscripts, published versions, and reposts.

## Cite and inspect

- Cite saved sources only with `[[cite:<source-id>]]`; use
  `[[citation-needed]]` when no saved source supports a claim. Never hand-write
  DOI citations, reference numbers, author-year citations, BibTeX, or a
  bibliography.
- `sources` lists session sources and `source` accepts only a stable
  `source_id`. `explain` gives the public verification/storage contract.
- Trusted save artifacts, not model prose, determine the final receipt. Report
  every batch item and preserve ambiguity/failure honestly.

Bundles are staged, fsynced, and atomically renamed. DOI identities keep their
stable `src-*`; schema-v1 bundles are validated and reused without rewriting.
