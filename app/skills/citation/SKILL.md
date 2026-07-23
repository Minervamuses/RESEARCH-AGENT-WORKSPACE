---
name: citation
description: Conversational citation selection, verified bundle saving, and [[cite:...]] rendering.
---

# Citation Skill

Use `citation_workflow` to discover and save persistent citation identities.
Its actions are `search`, `save`, `sources`, `source`, and `explain`. You own
the conversational decision about which work/version the user requested and
whether they authorized a write; the tool owns metadata retrieval, BibTeX,
storage, and the factual save outcome.

## Search and present

- `search` is stateless. Pass a natural-language topic/title in `query` and
  optional `year_from`/`year_to`; never pass Crossref, DataCite, or OpenAlex
  query syntax.
- Prefer bibliographic facts from explicit user text or visible tool results;
  do not invent identifiers or silently complete uncertain metadata from
  memory. A DOI/arXiv identifier visible in the conversation or another tool
  result may be passed to save because the workflow will fetch authoritative
  metadata before writing.
- Present each result with full title, authors, year, venue, work type, and
  version label plus its DOI/arXiv identifiers. There are no cX/mX identifiers
  or persistent candidate pools; conversational labels such as `1` are yours
  to resolve against visible results.
- Metadata does not ground a content summary. Fetch actual text or explicitly
  label any title-based description as inference.

## Save

- A save call contains one `works` array (1–10 self-contained WorkIntent
  objects). Include `requested_label` plus useful known title/author/year/venue/
  `work_type`/`work_kind`/DOI/arXiv/`version_kind` facts. Translate a visible
  result position such as `1` into that result's metadata or stable identifier;
  never pass a position or legacy candidate ID to the tool.
- Put each independently known fact in its own WorkIntent field. Never encode
  authors, years, venues, or provider syntax inside `title` or another field.
  The workflow owns provider-specific query construction and escaping.
- Save when the visible conversation authorizes it; authorization and target
  choice may come from earlier turns. Do not require the user to repeat a
  version word in the current message. If a reference is genuinely ambiguous,
  ask naturally, but do not add a mandatory clarification ceremony.
- Put your selected manifestation directly in `version_kind`; the workflow
  treats it as the requested target rather than downgrading it to an untrusted
  hint. `work_kind=original_research` and `version_kind=earliest` likewise mean
  what you selected from the conversation.
- Multiple save calls are allowed in one user turn and are serialized. Use
  another search or save when the returned outcome gives a concrete reason to
  correct or retry; never claim success before the tool reports it.
- Prefer an exact visible DOI/arXiv identifier. Without one, provide enough
  descriptive fields for a best match. The workflow still verifies the chosen
  provider record against authoritative metadata before persistence.

## Cite and inspect

- Use `[[cite:<source-id>]]` when you want the registry-backed renderer to
  number a saved source, and `[[citation-needed]]` for its placeholder.
  Ordinary DOI links, numeric citations, author-year prose, or a handwritten
  bibliography are allowed, but do not present invented bibliographic facts.
- `sources` lists session sources and `source` accepts only a stable
  `source_id`. `explain` gives the public verification/storage contract.
- Each save's tool content contains the actual per-item status and any receipt.
  Base your response on that result and preserve ambiguity/failure honestly;
  no finalizer will replace your prose with a deterministic save summary.

Bundles are staged, fsynced, and atomically renamed. DOI identities keep their
stable `src-*`; schema-v1 bundles are validated and reused without rewriting.
