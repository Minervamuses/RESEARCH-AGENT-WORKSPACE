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

`/citation <prompt>` starts one task, which may use multiple tool calls.
The host uses normal thinking for this task and restores the session's mode
afterward. Its source registry is released after finalization or failure.
To continue selecting or saving in a later turn, start another `/citation`
task; visible prior conversation still supplies metadata and authorization.

## Search and present

- `search` is stateless. Pass a natural-language topic/title in `query` and
  optional `year_from`/`year_to`; never pass Crossref, DataCite, or OpenAlex
  query syntax.
- For a selected claim, use the current editor snapshot, including unsaved
  text, its selected UTF-16 range or requested source lines, and only the
  surrounding context needed to understand the claim. Do not replace this
  source with the disk copy, conversation history, or stale RAG chunks.
- Form a concise topic query from the claim's key concepts, relationship,
  and relevant population/context (at most 2048 characters). Do not paste a
  whole paragraph as a supposed known paper title or route it through
  bibliographic `search_work` matching. State the search focus so the user
  can connect the candidates to the selected claim.
- Prefer bibliographic facts from explicit user text or visible tool results;
  do not invent identifiers or silently complete uncertain metadata from
  memory. A DOI/arXiv identifier visible in the conversation or another tool
  result may be passed to save because the workflow will fetch authoritative
  metadata before writing.
- Present each result with full title, authors, year, venue, work type, and
  version label plus its DOI/arXiv identifiers, keeping every identifier next
  to the metadata of its own record. There are no cX/mX identifiers or
  persistent candidate pools; conversational labels such as `1` are yours to
  resolve against visible results.
- Each result reports an actual retrieved abstract and its provider/source
  URL, or explicitly says no abstract was retrieved. Present the candidate's
  identity/link together with that availability and source. Do not invent an
  abstract or substitute a search snippet, title, or DOI metadata for one.
- Use only retrieved abstracts to explain possible relevance and specific
  limitations for the selected claim. Separate what the abstract reports
  from your interpretation; even an abstract-level match does not prove the
  claim. For metadata-only candidates, say that relevance cannot yet be
  assessed from an abstract. Title similarity and verified DOI identity
  establish neither substantive support nor a content summary.
- Describe study design and method limitations only when the retrieved
  abstract states them. Higher/lower activity groups alone do not establish
  extreme-group sampling, non-random assignment, or the absence of an RCT.
  If randomization or control methods are not reported, say that the
  abstract does not specify them and the design cannot be determined.
  Do not turn missing methods into definite design facts or definite
  unaddressed confounders.
- This workflow stops at abstracts. Do not download/read full text or start
  a separate evidence-verification pipeline. Abstracts exist only in this
  turn's discovery results; saving still verifies bibliographic identity
  and BibTeX, without upgrading the result to claim verification.
- If some providers fail, present the remaining results and the incomplete
  search scope. A provider failure or missing abstract is not a zero-hit
  result and is not evidence that relevant literature does not exist.

## Save

- A save call contains one `works` array (1–10 WorkIntent objects).
- DOI first. When the selected record, or the conversation, shows a DOI or
  arXiv identifier, the WorkIntent is `requested_label` plus that one
  identifier in `identifiers`, and nothing else. Copy it from the record the
  user chose. The workflow fetches authoritative doi.org metadata and BibTeX
  for it without searching again, so re-typing title, authors, year, venue,
  or type adds nothing but chances for error.
- Each version (preprint, published article, repository copy) has its own
  DOI. Choose the version by choosing the record whose version label matches
  the request, then pass that record's identifier. Never combine identifiers
  from different records.
- Translate a visible result number such as `2` into that record's
  identifier; never pass a number or legacy candidate ID to the tool.
- Only for a work without any DOI/arXiv identifier, give the known title,
  authors, year, venue, `work_type`, `work_kind`, and `version_kind` facts,
  each in its own field. Never encode authors, years, venues, or provider
  syntax inside `title` or another field; the workflow owns provider query
  construction. It then makes a descriptive best match, verifies it against
  authoritative metadata, and reports an uncertain match as ambiguous or not
  found instead of saving it.
- Save when the visible conversation authorizes it; authorization and target
  choice may come from earlier turns. Do not require the user to repeat a
  version word in the current message. If a reference is genuinely ambiguous,
  ask naturally, but do not add a mandatory clarification ceremony.
- In a descriptive (identifier-free) save, put your selected manifestation
  directly in `version_kind`; the workflow treats it as the requested target
  rather than downgrading it to an untrusted hint. `work_kind=original_research`
  and `version_kind=earliest` likewise mean what you selected.
- Multiple save calls are allowed in one user turn and are serialized. Use
  another search or save when the returned outcome gives a concrete reason to
  correct or retry; never claim success before the tool reports it.
- The workflow already retries transient provider trouble. `provider_failed`
  (reason codes ending in `_timeout`, `_network_error`, `_server_error`, or
  `_rate_limited`) means a provider stayed unavailable; retry that item at
  most once, otherwise say it can be retried later. `internal_error` is an
  unexpected local failure: report it with the batch's `batch_id` instead of
  retrying. Other failures are not fixed by repeating the same request.
- A search result that starts with `Search failed` means no provider
  answered; it is not evidence that the work does not exist.

## Cite and inspect

- Use `[[cite:<source-id>]]` when you want the registry-backed renderer to
  number a saved source, and `[[citation-needed]]` for its placeholder.
  Ordinary DOI links, numeric citations, author-year prose, or a handwritten
  bibliography are allowed, but do not present invented bibliographic facts.
- `sources` lists this task's sources and `source` accepts only a stable
  `source_id`. `explain` gives the public verification/storage contract.
- A later task must save or reuse a bundle through the tool to obtain a
  receipt trusted by its own registry. Historical markers or receipts alone
  do not make a source citable in the new task. Cleanup keeps saved bundles.
- Each save's tool content contains the actual per-item status and any receipt.
  Base your response on that result and preserve ambiguity/failure honestly;
  no finalizer will replace your prose with a deterministic save summary.

Bundles are staged, fsynced, and atomically renamed. DOI identities keep their
stable `src-*`; schema-v1 bundles are validated and reused without rewriting.
