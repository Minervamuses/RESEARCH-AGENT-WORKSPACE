# Performance

<!-- for_agents: verified=32cf47f date=2026-11-26 -->

> Where time, memory, I/O, and tokens go, what grows, and what has been measured.

## Cost model

| Action | Dominant costs per step | Magnitude | Anchor |
|---|---|---|---|
| Cold desktop launch (`python main.py`) | Mtime walk over `app/desktop/` -> (if stale: `tsc` x2 + `vite build` + `cargo build --release`) -> spawn Tauri + Conda `python -m agent.desktop.server` -> concurrent MCP discovery | Warm binary ~1-3 s (`inferred`); TS/Vite rebuild `4.61 s` (`measured 2026-11-26`) | `main.py::main`, `app/desktop/src-tauri/src/backend.rs::spawn_child`, `app/agent/mcp.py::load_mcp_tools_with_families` |
| Open project (`workspace.select` + `session.list`) | Read `RESEARCH.md` -> `open_project_history` full JSON scan -> `session.list` second full JSON scan (2 scans total) | `0.24 s` at 10 MB / `1.10 s` at 50 MB (`measured 2026-11-26`, `PERF-001`) | `app/agent/desktop/project_ops.py::_ProjectOps._workspace_select`, `app/agent/desktop/project.py::project_conversations` |
| Select conversation (`session.select` + preview) | Tail `session.transcript` read (`<= 20` turns) + `ChatSession.create` (extension check + concurrent MCP `get_tools()`) | ~0.1-2 s locally + MCP child spawn (`inferred`, `PERF-003`) | `app/desktop/src/lib/transcript.ts::selectConversationWithPreview`, `app/agent/desktop/conversation_ops.py::_ConversationOps._session_select` |
| Normal / document turn (`session.turn`) | `RESEARCH.md` inspect -> pending v3 JSON `fsync` -> `replay_history_inputs` + `compact_edit_results` -> OpenRouter HTTP calls (1-2 full doc copies) -> completed v3 JSON `fsync` -> `session.list` scan | Dominated by OpenRouter latency (`44 s` / `8,186` out tokens on 1 `@grill` call `measured 2026-11-22`) | `app/agent/desktop/turn_ops.py::_TurnOps._session_turn`, `app/agent/session.py::ChatSession.turn_outcome` |
| Extended-thinking turn (`FusionOrchestrator`) | Rewrite call -> `>= 2` parallel proposer graphs -> aggregator -> reviewer (+ optional repair) | 5-8+ OpenRouter calls; `<= 180 s` per proposer (`inferred`) | `app/agent/thinking/orchestrator.py::FusionOrchestrator` |
| Web Search tool call (`web_search`) | Spawn `/bin/sh` + Node MCP -> launch Playwright full Chromium -> Google `/search` + page fetch -> `/proc` reap | Seconds to `300 s` cap; ~200+ MB Chromium RSS (`inferred`, `PERF-002`) | `app/agent/mcp.py::_bounded_web_search`, `app/vendor/web-search-mcp/` |
| Citations inspect / Pandoc preview & export | `inspect`: regex/parser scan + `references.json` load; `render`/`.md`/`.docx`: 1-2 `pandoc` subprocesses (60 s cap) | `inspect` <50 ms; Pandoc ~0.2-2 s (`inferred`, `PERF-004`) | `app/agent/desktop/bibliography_ops.py`, `app/skills/citation/csl_render.py` |
| BIME Word export (`bime_docx`) | `bime_word.py convert` -> OOXML `word/document.xml` section split -> `bime_word.py audit` | ~2-10 s (`inferred`, 180 s cap per pass, `PERF-004`) | `app/agent/desktop/bime_export.py::run_bime_convert` |
| RAG folder ingest (`/init` / `/ingest`) | `ThreadPoolExecutor(4)` OpenRouter tagging (`z-ai/glm-5`) -> tiktoken chunking -> Ollama `bge-m3` + Chroma batches (256) -> `raw.json` atomic write | Scales with folder count (network) + chunk count (local GPU/CPU) (`inferred`) | `app/rag/cli/ingest.py::ingest_repo` |

## Scaling dimensions

| What grows | Code that scales with it | Behavior | Ceiling or symptom |
|---|---|---|---|
| Total bytes across `<historyDirectory>/conversations/*.json` | `ConversationRepository.scan` (`app/agent/conversations/repository.py`) | `O(total_bytes)` full UTF-8 decode + schema validation of every file (including archived `sourceText`) on open, `session.list`, and after every turn | ~10.9 ms/MB warm (`0.55 s` at 50 MB); cap `MAX_CONVERSATION_FILES = 4,096` (`PERF-001`) |
| Single conversation file size (`turns` x snapshots) | `ConversationRepository.save` (`_encode_document` + round-trip re-parse + `fsync`) | `O(file_bytes)` serialize + double parse + disk sync on both turn start and turn completion | Slower turn start/finish once one file holds dozens of 250 KB+ snapshots (`MAX_TURNS = 4,096`) |
| Multi-turn & multi-edit document context in prompts | `replay_history_inputs` & `compact_edit_results` (`app/agent/document_context.py`) | Bounded `O(1)` full document copies (`1-2` copies across 10-turn context window) | Eliminated prior `12-13`x token blowup (`measured 2026-11-15`); single submission cap `1 MiB` (`ASM-030`) |
| Open document length in Monaco & `CitationPanel` | `applyDocumentChanges` (`documentSource.ts`), `find_citations` (`citekeys.py`) | Whole-string slice per keystroke; `bibliography.inspect` runs only on open/save/apply/Refresh | Cap `MAX_TEXT_BYTES = 1_048_576`; ~700 KB conflict payloads approach 2 MiB wire limit (`ASM-030`) |
| Rendered transcript length | `Transcript.tsx` (`memo` on `RestoredTurn` and `SafeContent`, lazy `ToolActivity`) | Paged in 20-turn slices (`TRANSCRIPT_PAGE_SIZE = 20`); restored cards skip re-parse while typing | Repeated `Load older turns` keeps DOM nodes mounted without virtualization |
| `raw.json` & Chroma chunk count | `JsonStore` (`app/rag/store/json_store.py`), `rag.sync._stored_file_paths` | `raw.json` rewrites whole corpus JSON after batch ingest; `list_diff` scans all docs in Python | Memory and rewrite time grow `O(total_chunks)` |

## Limits and budgets

| Limit | Value | Anchor | Purpose / effect when hit |
|---|---|---|---|
| Protocol NDJSON line cap | `2,097,152` B (2 MiB) | `app/desktop/protocol/v1/contract.json#maxLineBytes` | Rejects oversized lines (`session.turn` and `session.transcript` success results exempt) |
| Turn submission & document cap | `1,048,576` B (1 MiB) | `app/agent/conversations/models.py::MAX_INPUT_BYTES`, `app/agent/desktop/documents.py::MAX_TEXT_BYTES` | Caps `RESEARCH.md`, editor files, and `text + submittedContext` |
| Replayed context window & placeholder cap | `10` turns / `2,000` chars | `app/agent/conversations/models.py::LATEST_CONTEXT_TURNS`, `app/agent/document_context.py::PLACEHOLDER_SELECTION_MAX_CHARS` | Older turns stay in archive; larger history selections omit `selectedText` |
| OpenRouter timeout, retries & max tokens | `600,000` ms / `2` retries (`<= 8 s`) / `65,536` | `app/agent/config.py::AgentConfig`, `app/agent/llm/openrouter.py::RETRY_MAX_INTERVAL_SECONDS` | Retries 5xx/network only (never timeouts, 4xx, or 429) |
| LangGraph recursion & finalization fuse | `64` steps (`< 3` forces final) / `2` empty retries | `app/agent/config.py::AgentConfig`, `app/agent/graph.py::build_graph` | Forces tool-free answer before `GraphRecursionError` |
| Extended-thinking proposer timeout & quorum | `180.0` s / quorum `2` / `4,096` tokens | `app/agent/config.py::AgentConfig` | Bounds fusion proposers and reviewer/aggregator replies |
| Skill & extension caps | `200,000` skill chars; `512` files / `64 MiB` bundle | `app/agent/config.py::AgentConfig` | Bounds pinned skill references and extension bundles |
| Rust supervisor caps | `64` pending; `15 s` start; `5+5 s` stop; `500 ms` EOF | `app/desktop/src-tauri/src/backend.rs` | Bounds queue depth, hung startups, shutdowns, and crash classification |
| Desktop Ask approval & candidate wait | `60.0` s (`120.0` s candidate); `8,192` B summary | `app/agent/desktop/service.py::DesktopService.__init__`, `approvals.py` | Auto-denies expired prompts; summaries `> 8 KiB` fail closed (`FAIL-025`) |
| `bash` & `web_search` caps | `bash`: `30`/`300 s`, `256 KB`; `web_search`: `15 s`/`300 s` | `app/agent/tools/bash.py`, `app/agent/mcp.py::WEB_SEARCH_STARTUP_TIMEOUT_MS` | Bounds subprocess runtime, output bytes, and Chromium calls |
| Citation cache, Pandoc & `bime_word` caps | `15 min`/`24 h` TTL; `16 MiB` NeurIPS; `60 s` / `180 s` | `app/skills/citation/providers/net.py`, `authority.py`, `csl_render.py`, `bime_export.py` | Bounds bibliographic fetches and export subprocesses |
| Transcript paging & log rotation | `50` sessions / `20` turns; `5 MiB` x `3` logs | `app/desktop/protocol/v1/contract.json`, `app/agent/diagnostics.py::MAX_LOG_BYTES` | Bounds UI page payloads and disk log growth |

## Measurements

- **Conversation scan cost (`measured 2026-11-26` at `32cf47f`):** `PYTHONDONTWRITEBYTECODE=1 python ../harness/plans/2026-11-19-repo-debt-cleanup/evidence/C6-S4/scan_cost.py <tmp>` in Conda `app` on WSL2 ext4 (warm cache, 3 runs, 4 turns x ~250 KB `sourceText` ~= `1.01 MB`/file):
  - **10 files (`10.11 MB`):** `workspace.select(open)` median **`0.1216 s`** (1 scan); `session.list` median **`0.1156 s`** (1 scan).
  - **50 files (`50.56 MB`):** `workspace.select(open)` median **`0.5490 s`** (1 scan); `session.list` median **`0.5510 s`** (1 scan) -> linear **~10.9 ms/MB** (`~1.10 s` combined on project open).
- **15-turn document context budget (`measured 2026-11-15`, `app/tests/test_document_context_budget.py`):** Full document copies in turn-15 prompt dropped from **`12-13`** to **`1-2`**.
- **Live `@grill` turn (`measured 2026-11-22`, `harness/plans/2026-11-19-repo-debt-cleanup/evidence/acceptance-2026-11-22/gui-citation-grill.md`):** 1 model call took **`44 s`** (`8,186` output tokens, `0` tool calls).
- **Test/build wall times (`measured 2026-11-26` at `32cf47f`):** `pytest` (1,826 tests): **`62.76 s`**; `npm test` (253 tests): **`6.90 s`**; `npm run build` (`index` 393 kB + lazy Monaco `editor.api` 2.70 MB): **`4.61 s`**; `cargo test --locked` (35 tests): **`0.60 s`** (`12.42 s` compile).

## Suspected bottlenecks

### PERF-001 - Uncached full-history JSON parsing on project open and after every turn

- **Hypothesis:** Above ~50-100 MB of archived document snapshots, full-file JSON parsing in `ConversationRepository.scan` makes project open (>1-2 s) and post-turn `loadHistory` sluggish, especially on cold cache.
- **Evidence so far:** `scan_cost.py` (`measured 2026-11-26`) takes `0.55 s`/scan at 50 MB warm, and project open runs 2 scans (`workspace.select` + `session.list`).
- **How to confirm:** Run `scan_cost.py` at 100-200 files and check real `app/store/projects/*` sizes.
- **Expected gain:** In-memory `(mtime_ns, size)` summary caching inside `ConversationRepository` would cut repeat `session.list` calls to <5 ms without reintroducing a disk catalog.
- **Risk of fixing:** Must still catch file corruption/ownership mismatches; deferred by user decision (`R3`) until real stores grow large.

### PERF-002 - Per-call Node + Playwright Chromium cold start in `web_search`

- **Hypothesis:** Spawning a fresh Node server and full Chromium on every `web_search` call adds multi-second startup latency and multiplies RAM if a turn emits parallel `web_search` calls (`ASM-029`).
- **Evidence so far:** `app/agent/mcp.py::_load_web_search_tools` opens a fresh `create_session` per call to guarantee `/proc` reaping.
- **How to confirm:** Inspect `tool_end` `duration_ms` for `web_search` in `desktop-backend.log` and `web_search.stderr.log`.
- **Expected gain:** Serializing parallel `web_search` calls or reusing a warm browser saves ~1-3 s/call and caps RAM.
- **Risk of fixing:** High risk of leaked Chromium processes or hung stdio teardown (`INV-031`).

### PERF-003 - Unbounded non-`web_search` MCP discovery and repeated per-turn Skill loads

- **Hypothesis:** One hung `github` or drop-in MCP server stalls `ChatSession.create` indefinitely (`ASM-013`), and desktop skill turns load/hash the same `SKILL.md` 3-4 times (`turn_ops.py` + `session.py`).
- **Evidence so far:** `app/agent/mcp.py::load_mcp_tools_with_families` bounds only `web_search` (`15 s`); `load_skill_runtime` re-reads disk per call.
- **How to confirm:** Test `ChatSession.create` with a sleeping stdio MCP server; count `load_skill_runtime` calls in one `@grill` turn.
- **Expected gain:** Bounding non-`web_search` MCP discovery caps session creation at ~15 s; per-turn runtime reuse saves 2-3 disk/YAML/hash passes.
- **Risk of fixing:** Low if MCP timeout accommodates cold `npx` startups and skill hash precheck (`INV-013`) still runs once per turn.

### PERF-004 - Double subprocess pass on `bime_docx` and `.docx` exports

- **Hypothesis:** `bime_docx` (`convert` + `audit`) and Pandoc `.docx` (`--citeproc -t json` + `-f json -t docx`) pay two subprocess startups and AST serializations on large drafts.
- **Evidence so far:** `bime_export.py::run_bime_convert` re-audits after `split_front_matter`; `csl_render.py::export_docx` unlinks remote images between passes.
- **How to confirm:** Time `run_bime_convert` and `export_docx` on a 50-page Markdown file in `/tmp`.
- **Expected gain:** A few seconds on manual exports.
- **Risk of fixing:** Skipping re-audit desynchronizes `.bime.audit.md` from `.bime.docx`; single-pass Pandoc risks fetching remote image URLs (`INV-032`).

## How to measure

- **Per-turn timing & document token share (`turn_trace`):** `grep -h turn_trace ~/.local/state/research-agent/logs/desktop-backend.log* | grep turn_id=<turnId>` (`app/agent/observability.py::TurnTimingTrace` logs `duration_ms`, `prompt_chars`, `document_chars_*`, `document_full_copies`, and `document_tokens_estimate`).
- **Offline scan benchmark:** `cd app && conda run -n app python -B ../harness/plans/2026-11-19-repo-debt-cleanup/evidence/C6-S4/scan_cost.py /tmp/scan-bench`.
- **CPU profiling:** Run `conda run -n app python -B -m cProfile -s cumtime <script.py>` in `/tmp` against `QueuedModel` / `offline_rag_config` (never paid APIs or `app/store/`).
