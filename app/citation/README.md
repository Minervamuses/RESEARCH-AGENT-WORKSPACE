# citation/ — verified citation workflow

The search → select → verify → save pipeline behind chat's `/citation`
slash command and the standalone `python -m citation` REPL. Both entries
drive the same session-scoped `CitationCoordinator` (`coordinator.py`)
over one process-scoped `CitationProviderHub` (`hub.py`) that owns the
shared provider clients, TTL cache, and rate limiters.

```
query ──► discovery (Crossref ∥ OpenAlex; ≤2 lazy LLM query expansions)
              │  RRF fusion k=60, identity-only merge, related-version groups
              │  web MCP only as empty/failed fallback or /citation more
              ▼
        candidates ──select──► doi.org CSL lookups ──► confirmable matches
                                                            │
                                              confirm (the only writer)
                                                            ▼
                     doi.org CSL re-fetch + BibTeX (pybtex canonical)
                     DOI equality: match == structured == BibTeX
                                                            ▼
                <output>/<title>--<doi-hash>/reference.bib + citation.json
```

## Invariants

- **Only `/citation` (or the REPL) can create formal citations.** The
  Coordinator's mutating methods are never bound into the model tool graph;
  ordinary chat may keep plain web links but can never promote them to
  SourceRefs, numbering, or the bibliography.
- **Interactive only.** There is no `--auto`, no auto-selection, and no
  non-interactive save path. Confirming without an explicit select is
  `invalid_state`.
- **`identity_verified` means identity, nothing more**: the DOI and the
  bibliographic pipeline agree on the record. It never claims the source
  supports any particular statement.
- **Fail closed, write nothing**: no-DOI candidates are viewable but not
  saveable; DOI mismatches, invalid BibTeX, and bundle conflicts end with
  `accepted_doi = null` and zero bundle output.
- **Atomic bundles**: staging dir + single rename; a visible bundle always
  holds both `reference.bib` and a `citation.json` sidecar whose artifact
  hash matches the BibTeX on disk. Same-DOI re-confirms validate and reuse;
  mismatching bundles are never overwritten. Stale staging is reclaimed
  only after 24 h.

## Running the standalone REPL

```bash
conda activate app
cd app

python -m citation "attention is all you need"   # initial search, then REPL
python -m citation --no-mcp                      # skip Web Search MCP
```

REPL commands match the chat slash command (the `/citation` prefix is
optional): `search <query>`, `list [page]`, `show <candidate-id>`,
`more [query]`, `select <candidate-id>`, `confirm <match-id>`, `status`,
`cancel`, `sources [page]`, `source <source-id>`, `help`, `quit`.
A DOI-shaped query resolves directly through doi.org — no LLM, no web.

## Module map

| Module | Role |
|---|---|
| `types.py` | `CitationCandidate` / `CitationMatch` / `CitationResult` / `SourceRef`; persisted formats carry `schema_version=1` |
| `doi.py` | context-aware DOI canonicalizer; regex extracts candidates only, resolvers decide existence |
| `normalize.py` | NFKC/casefold/HTML/LaTeX title normalization (comparison only; empty never matches) |
| `bibtex_canonical.py` | pybtex validation: ≤1 MiB, exactly one entry, empty preamble, canonical re-serialization only |
| `providers/` | Crossref, OpenAlex (key redacted everywhere), doi.org (CSL/BibTeX/RA), web MCP adapter, shared cache/limiter/Retry-After |
| `ranking.py` | deterministic RRF (k=60); metadata precedence structured→crossref→openalex→web; conflicts preserved, never resolved destructively |
| `expansion.py` | lazy LLM query expansion, ≤2 plain strings, degrades to nothing |
| `storage.py` | atomic bundle writer + output-dir precedence |
| `hub.py` / `coordinator.py` | process hub / session workflow state machine |
| `cli.py` | interactive REPL sharing the chat command dispatcher |

## Output location

Precedence: `AgentConfig.citation_output_dir` → `CITATION_OUTPUT_DIR` →
`app/citation/cite/` in a source checkout → the platform user-data
directory for wheel installs. There is no upward `pyproject.toml` search.
Bundle directory names are capped at 180 UTF-8 bytes; the suffix is the
first 12 hex chars of the canonical DOI's SHA-256 (lengthened to 20/64
only on true collisions).

## Environment

| Variable | Effect |
|---|---|
| `OPENALEX_API_KEY` | enables the OpenAlex provider (absent = shown as *disabled*); sent only as a query parameter and redacted from traces/logs |
| `CROSSREF_MAILTO` | Crossref polite-pool User-Agent |
| `CITATION_OUTPUT_DIR` | overrides the bundle output directory |
| `OPENROUTER_API_KEY` | optional; only powers lazy query expansion (no startup probe) |
| `AGENT_ENABLE_MCP_WEB_SEARCH` etc. | web fallback / `/citation more`; see workspace README §8 for the pinned web-search-mcp v0.3.2 build |

## Notes

- The web MCP (`mrkrsl/web-search-mcp` v0.3.2, commit
  `e694d8d5da11d1509b9bf0976d380035f648d6f9`, built externally and launched
  as `node /absolute/path/dist/index.js`) returns formatted text, not JSON;
  `providers/web.py` parses its `**N. Title** / URL: / Description:` layout
  and test fixtures mirror real output.
- Provider failure, empty result, HTTP 429, timeout, and disabled are five
  distinct states — an empty search is never reported as an error, and an
  error is never cached.
