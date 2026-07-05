# citation/ — isolated citation-capture prototype

A standalone experiment that turns a **natural-language request** into a
captured **BibTeX** file. It reuses the host project's configuration, chat
model, and Web Search MCP, but is **not** wired into the agent graph, the skill
system, the capability map, or any slash command.

```
natural-language request  (e.g. "幫我找關於檢索效率的文章")
  → LLM-driven discovery: the agent DECIDES the search queries itself
    (e.g. it searches "BM25", "learned sparse retrieval", "reranking latency"),
    runs the Web Search MCP, and ranks the papers it actually retrieved
  → show candidate papers; you pick one after discussion
  → resolve a trustworthy DOI for that selected paper
  → DOI / Crossref metadata route for BibTeX (title/author/year verified)
  → citation/cite/<normalized_title>.bib
```

The query strategy is **decided at runtime by the model**, not hard-coded — the
request is never just stuffed verbatim into a single search call. Candidates are
always grounded in real tool output; the LLM never invents papers or BibTeX.
BibTeX is produced only after the user selects a paper, and the accepted write
path is DOI → Crossref/DOI BibTeX.

If **no** route yields real BibTeX, the run reports the failure and writes
nothing. The prototype never fabricates BibTeX or saves placeholder data.

## How to run

From the **app repo root** (`research-agent-workspace/app/`), inside the active
`app` conda environment. Poetry is configured with `virtualenvs.create = false`,
so package installs go into that conda environment:

```bash
conda activate app

# interactive: describe what you want in natural language; the agent decides how
# to search, then lists candidates for you to choose one
python -m citation.cli "幫我找關於檢索效率的文章"
python -m citation.cli "papers about RAG citation hallucination evaluation"

# smoke-test / non-interactive: walk the top ranked candidates (up to
# --auto-attempts, default 4) until one yields a verified citation; never
# prompts, and refuses ambiguous Crossref matches instead of guessing
python -m citation.cli "Attention is all you need" --auto
python -m citation.cli "Attention is all you need" --auto --auto-attempts 2

# options
python -m citation.cli --help
python -m citation.cli "<request>" --limit 8 --verbose
```

You can also omit the request and be prompted for it: `python -m citation.cli`.

## What it reuses (read-only) from the host project

| Need              | Source (unmodified)                                   |
|-------------------|-------------------------------------------------------|
| Config            | `agent.config.AgentConfig`                            |
| Chat model        | `agent.llm.get_chat_model` (OpenRouter, `llm_model`)  |
| Web Search MCP    | `agent.mcp.load_mcp_tools_with_families` (family `web_search`) |
| Repo root         | `agent.paths.find_app_root`                           |
| `.env` loading    | `python-dotenv`, same `.env` the agent CLI reads      |

The LLM **drives discovery**: it is given the Web Search MCP tools and decides
which queries to run (and may issue several), then annotates and ranks the
papers it retrieved. It is never used to generate BibTeX, and candidates only
come from real tool output. A working OpenRouter setup is **required**: the
runtime probes the chat model once at startup, and a missing/invalid
`OPENROUTER_API_KEY`, a bad model name, or an OpenRouter rejection aborts the
run with exit code `2` — there is no deterministic fallback query and no
"enrichment-optional" mode. Crossref match decisions are always deterministic
(title similarity + year + author overlap).

## Environment variables

These already live in the host project's `.env` (git-ignored):

- `OPENROUTER_API_KEY` — **required**: the chat model drives search decisions
  and candidate ranking/annotation. A missing or unusable key/model fails fast
  with exit code `2`.
- `AGENT_ENABLE_MCP_WEB_SEARCH=1` — **required**: turns on the Web Search MCP.
- `AGENT_MCP_WEB_SEARCH_COMMAND` / `AGENT_MCP_WEB_SEARCH_ARGS` — how to launch
  `mrkrsl/web-search-mcp`.
- `CROSSREF_MAILTO` — optional; added to the Crossref `User-Agent` for the
  "polite pool". No personal data is hard-coded.

## Output

BibTeX is written to `citation/cite/<normalized_title>.bib`.

Filename rules: lowercase, trimmed, spaces → `_`, unsafe characters removed,
consecutive `_` collapsed, `.bib` extension. Existing files are **never**
overwritten — a numeric suffix is added (`name.bib` → `name_2.bib`).

Example: `Attention Is All You Need` → `attention_is_all_you_need.bib`.

## Web Search MCP tools used

From `mrkrsl/web-search-mcp` (family `web_search`):

| Tool | Use here |
|------|----------|
| `get-web-search-summaries` | the agent's main discovery tool (cheap, snippets only) and DOI lookup helper |
| `get-single-web-page-content` | inspect a chosen paper's source page for a DOI (and the agent may use it during discovery) |
| `full-web-search` | bound and available to the agent, but it's steered toward summaries to avoid bulk crawling |

All three are **bound to the model** during discovery; the prompt steers it
toward `get-web-search-summaries` and a handful of targeted queries.

## Failure handling (every step reports, none fail silently)

Exit codes: `0` success (or nothing selected), `1` capture failed for the
selected paper(s), `2` configuration/API error (OpenRouter or Web Search MCP),
`3` the agentic search completed but produced no parseable candidates.

- OpenRouter model cannot be built or the startup probe fails (missing/invalid
  `OPENROUTER_API_KEY`, bad model name, OpenRouter rejection) → clear error,
  exit code `2`. Never disguised as "no candidates".
- A discovery LLM call fails/times out mid-search → reported as an OpenRouter
  discovery error, exit code `2`.
- Web Search MCP not enabled/loaded → clear error + how to enable, exit code `2`.
- Search completed but no parseable results → "no candidate papers found",
  exit code `3`.
- No DOI on the selected candidate/source page → falls through to Crossref title search and a Scholar-oriented DOI lookup.
- `get-single-web-page-content` tool missing → noted in the trace; capture
  continues with the Crossref title-search route.
- Source-page fetch or Scholar DOI lookup hangs → 30s per-call timeout, noted
  in the trace, capture continues.
- Crossref finds no DOI → reported in the trace.
- Crossref finds several similar candidates → **ambiguous**: interactive mode
  asks you to confirm; `--auto` refuses to guess and aborts.
- Retrieved BibTeX fails DOI verification (see below) → DOI is excluded and an
  alternate DOI is tried; nothing unverified is written.
- Crossref BibTeX retrieval fails → tries to resolve an alternate DOI, then retries the DOI/Crossref route.
- Scholar DOI lookup fails (CAPTCHA / nothing citable) → reported plainly.
- `citation/cite/` missing → created automatically.
- Target `.bib` already exists → safe numeric suffix.

## DOI verification before writing (v1 rules)

Every DOI — from the discovery snippet/URL, the source page, the
Scholar-oriented lookup, a Crossref title search, or an alternate DOI — goes
through the same check after BibTeX retrieval and **before** any write. The
retrieved BibTeX is compared against the selected candidate:

- **Title** carries the decision: similarity (normalized, 0–1) must reach
  **0.70**, or **0.55** when at least one author surname overlaps.
- **Year**: when both the candidate and the BibTeX have a year, a gap larger
  than **1** fails (tolerates preprint/publication drift).
- **Authors**: when both sides list authors, at least one shared surname
  lowers the title bar (see above); zero overlap fails. A missing author list
  on either side is never a failure by itself.
- A failed check records a trace note, excludes that DOI, and moves on to an
  alternate DOI. If no DOI verifies, nothing is written.

Known limitations of these v1 rules: search-result titles can be truncated or
breadcrumb-laden (lowering similarity for the *right* paper), candidate years
often come from snippets and may be wrong, and author lists from discovery are
sparse — so the thresholds are deliberately conservative and may reject a
correct DOI rather than risk writing a wrong one. Tune them in
`citation/capture.py` (`_VERIFY_*` constants) as real-world data accumulates.

## Known limitations / workarounds (kept inside `citation/` by design)

- **Google Scholar is not a stable API and is CAPTCHA-guarded.** Discovery and
  DOI lookup are therefore best-effort and use normal Web Search MCP output. We
  do not solve CAPTCHAs and do not scrape Scholar's Cite popup. BibTeX capture
  must still go through the DOI/Crossref route.
- The Web Search MCP is Playwright-backed and the host loader writes a server
  log under `~/.cache/agent-mcp/`. In a restricted sandbox that path may be
  read-only and the search engines / Crossref / doi.org hosts may be blocked;
  run in an environment with normal network + a writable cache.
- The MCP server returns **formatted text**, not structured JSON, so discovery
  parses its `**N. Title** / URL: / Description:` layout. If that upstream
  format changes, update `citation/discovery.parse_summaries`.
- This prototype intentionally does **not** reuse `agent.session.ChatSession`
  (which would pull in the full graph/skill machinery). It calls the MCP tools
  and the chat model directly — the minimal isolated path.
