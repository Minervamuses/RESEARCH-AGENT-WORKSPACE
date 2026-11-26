# Failure Analysis

<!-- for_agents: verified=32cf47f date=2026-11-26 -->

> How each boundary can fail, what is broken now, and which premises are fragile.

## Failure surface

| Boundary / dependency | Failure | Detection | Handling | User sees | Tested by | Ref |
|---|---|---|---|---|---|---|
| Rust <-> Python child | Crash right at stdout EOF | `stdout_closed` 500 ms `try_wait()` grace | `Crashed` + `backend.crashed` | Crash banner + `Restart` | `backend::tests::crash_seen_first_as_stdout_eof_is_still_reported_as_a_crash` | `INV-015` |
| Rust <-> Python child | Bad Conda/checkout or >15 s start | `source_conda_launch`, `STARTUP_TIMEOUT` | Kills child, sets `Degraded` | `Action required` + `Retry start` | `backend::tests::readiness_timeout_is_bounded_and_stops_child` | `INV-001`, `ASM-012` |
| Protocol v1 pipe | Line >2 MiB, bad JSON, forbidden key | `_read_requests`, `validate_safe_data` | `PROTOCOL_INVALID`; redacts errors | Bounded error (`<= 320` chars) | `test_desktop_server.py`, `protocol::tests` | `INV-011`, `INV-017`, `ASM-030` |
| Rust request wait | Non-turn RPC hangs without EOF | `unhandled` (no timer in `backend.rs`) | Blocks until `Restart` | Busy spinner until restart | `backend::tests::progressing_request_can_outlive_the_prior_absolute_deadline` | `ASM-019` |
| Windows picker | Foreground denied or missing start dir | `WINDOWS_PICKER_SCRIPT`, `wslpath` | Taskbar fallback; `NATIVE_PICKER_FAILED` | Notice; drafts kept | `backend::tests::picker_takes_the_foreground_before_opening_the_dialog` | `ASM-026` |
| OpenRouter HTTP | Missing key, 429, 5xx, or 600 s timeout | `bounded_sdk_client` (`<= 2` retries on 5xx) | Fails v3 turn + incident ID | `PROVIDER_*` + `Retry saved turn` | `test_openrouter_model.py` | `ASM-001`, `ASM-034` |
| LangGraph reply | Blank reply, leaked markup, step limit | `graph.py::_agent_requests` | 2 empty retries, 1 repair, fallback | Safe recovery reply | `test_graph_skill_loader.py` | `INV-005` |
| Stop & bash group | User `Stop` or unkillable bash group | `_session_stop`, `_retry_stop` | `interrupted`; `Retry Stop` reruns cleanup | `Turn stopped` or `StopFailureNotice` | `test_desktop_document_service.py` | `INV-027`, `ASM-031` |
| Ask approval | 60 s expiry, Stop, or summary `> 8 KiB` | `_single_operation_approval`, `_operation_approval` | Denies fail-closed (`> 8 KiB` pre-dialog) | `APPROVAL_DENIED` | `test_project_permissions.py` (`> 8 KiB` `untested`) | `INV-018`, `FAIL-025` |
| Project & v3 JSON | `pending` turn, v1/v2, bad JSON, unknown key | `_recover_interrupted_turn`, `project_conversations` | `pending` -> `interrupted`; scan aborts open | Interrupted card or open error | `test_desktop_conversations.py` | `INV-006`, `INV-016`, `FAIL-026` |
| Document save/edit | Disk drift or unknown new citekey | `DocumentWorkspace._result`, `_unknown_new_citation_keys` | `conflict` or `failed` pre-candidate | Conflict panel; `unknownKeys` | `test_desktop_documents.py`, `test_desktop_citation_keys.py` | `INV-025`, `INV-032` |
| Citation & library | Provider error, conflict, unknown layout | `fetch_with_retries`, `library.py::write_atomic` | Skips provider; write error -> `storage_failed` | Honest failure / `BIBLIOGRAPHY_CONFLICT` | `test_citation_project_library.py` | `INV-010`, `FAIL-024` |
| Pandoc & `bime_word` | Missing tool, timeout, unsaved buffer, exit `1`/`2` | `csl_render.py`, `bime_export.py` | Exit `2`/unsaved writes nothing; exit `1` writes draft | Error notice or red audit count | `test_desktop_bibliography.py` | `INV-025`, `INV-032`, `ASM-037` |
| MCP & `web_search` | >15 s start, >300 s call, `SIGKILL`, hung drop-in | `_bounded_web_search`, `load_mcp_tools_with_families` | Reaps `web_search`; drop-in `get_tools()` `unhandled` | Degraded tools or hung session create | `test_mcp.py` (drop-in `untested`) | `INV-031`, `FAIL-027`, `ASM-013` |
| RAG 3-store state | Ollama down, Stop mid-ingest, prune/empty file | `_map_exception`, `deferred_save` | Rolls back `raw.json`; Chroma/meta diverge | Error turn; stale search/inventory | `tests/rag/test_json_store.py` (`FAIL-001`..`003` `untested`) | `INV-012`, `FAIL-001`..`FAIL-003` |

## Active defects

### FAIL-001 - Prune leaves stale folder metadata in `folder_meta.json`

**Symptom / Trigger:** `rag.explore()` still lists a folder after `/prune --yes` removed its last file. **Root cause:** Confirmed in `app/rag/sync.py::prune_orphans` (deletes Chroma/`raw.json`, skips `folder_meta.json`). **Workaround / Fix:** Re-ingest root; update `folder_meta.json` for the pruned `source_namespace`.

### FAIL-002 - Re-ingesting an emptied or unreadable file retains old chunks

**Symptom / Trigger:** `ingest_repo` reports 0 chunks for an emptied/unreadable file while old chunks remain searchable. **Root cause:** Confirmed in `app/rag/cli/ingest.py::ingest_repo` (only `>= 1`-doc files join the delete set). **Workaround / Fix:** Delete + `/prune`; include zero-doc files in the folder delete set.

### FAIL-003 - Interrupted or failed RAG ingest diverges across the three stores

**Symptom / Trigger:** `explore()`, `rag_search`, and `list_chunks` disagree after an error or `Stop` mid-ingest. **Root cause:** Confirmed in `app/rag/cli/ingest.py::ingest_repo` and `app/rag/store/json_store.py::deferred_save` (`folder_meta.json` and Chroma write before `raw.json` rolls back). **Workaround / Fix:** Rerun `/ingest`; add post-Stop convergence tests.

### FAIL-024 - DataCite text search can fail with opaque `datacite:error`

**Symptom / Trigger:** Citation search reports `datacite:error` on Lucene characters (HTTP 400) or >2 MiB payloads. **Root cause:** Inferred in `app/skills/citation/providers/datacite.py::_text_query`. **Workaround / Fix:** Crossref/OpenAlex still return hits; escape Lucene operators.

### FAIL-025 - Ask silently denies oversized (`> 8 KiB`) or secret-shaped approvals

**Symptom / Trigger:** Returns `APPROVAL_DENIED` with no dialog when `parametersSummary > 8,192` B (large `/prune --yes`) or text matches secret regexes. **Root cause:** Confirmed in `app/agent/desktop/approvals.py::_ApprovalOps._operation_approval`. **Workaround / Fix:** Narrow target or use `Bypass`; truncate summary or return a specific error.

### FAIL-026 - One bad/legacy conversation file or unknown `RESEARCH.md` key blocks project open

**Symptom / Trigger:** `workspace.select` aborts if `<historyDirectory>/conversations/` has a v1/v2, malformed, `> 4,096`, or foreign `projectId` file, or `RESEARCH.md` has an unknown metadata key. **Root cause:** Confirmed fail-closed checks in `app/agent/desktop/project.py::project_conversations` and `_parse_metadata`. **Workaround / Fix:** Fix/move the file or key; include offending filename/code in the error.

### FAIL-027 - `SIGKILL` during `web_search` leaks `/tmp/playwright_chromiumdev_profile-*`

**Symptom / Trigger:** ~190 KB `/tmp/playwright_chromiumdev_profile-*` dirs remain if backend is `SIGKILL`ed mid-search. **Root cause:** Inferred in `app/agent/mcp.py::_bounded_web_search`. **Workaround / Fix:** Delete stale dirs; put profile under a parent dir cleaned by `kill_owned()`.

### FAIL-035 - `/sync` drops `/init`'s top-level `app/` exclusion

**Symptom / Trigger:** `/sync <workspace-root>` after `/init` lists `app/` files as `missing_from_store`. **Root cause:** Confirmed in `app/agent/ingest.py::diff_folder` -> `app/rag/sync.py::list_diff` (no `skip_rel_paths`). **Workaround / Fix:** Sync subdirs; thread `skip_rel_paths` into `list_diff`.

### FAIL-036 - Exception tracebacks in logs can retain tool kwargs or provider payloads

**Symptom / Trigger:** `desktop-backend.log` / `cli.log` tracebacks can include non-secret `ToolInvocationError` kwargs or provider bodies (`INV-028`). **Root cause:** Confirmed in `app/agent/graph.py::build_graph` + pattern-only `app/agent/diagnostics.py::RedactingFormatter`. **Workaround / Fix:** Logs are `0600`; scrub exception args before `exc_info`.

## Fragile assumptions

### ASM-001 - External APIs are reachable

**Premise:** OpenRouter, Ollama (`bge-m3`), Crossref, DataCite, `doi.org`, arXiv, `proceedings.neurips.cc`, and Google are online (`app/agent/llm/openrouter.py`, `app/skills/citation/service.py`). **If false:** Feature fails with no offline fallback. **Detect:** `runtime.diagnostics`, `turn_trace`, incident IDs.

### ASM-002 - Unversioned RAG stores and embedding model stay compatible

**Premise:** `raw.json`, `folder_meta.json`, and Chroma match current schemas and `embed_model` (`app/rag/store/cache.py::get_chroma_store` omits `embed_model`). **If false:** Parse error or bad vectors. **Detect:** Exceptions or poor recall; rebuild `<persist_dir>`.

### ASM-003 - RAG multi-store writes finish uninterrupted

**Premise:** `ingest_repo` and `prune_orphans` finish across all 3 stores (`app/rag/cli/ingest.py`). **If false:** Divergence (`FAIL-001`..`FAIL-003`). **Detect:** Compare `explore()`, `list_chunks()`, `search()`.

### ASM-004 - Canonical RAG roots and single-file PIDs stay stable

**Premise:** Repo paths do not move and `ingest_single` stem PIDs do not collide (`app/rag/utils/paths.py::source_namespace`). **If false:** Orphaned namespace or overwritten chunks. **Detect:** `/sync` delta.

### ASM-005 - `/sync` is understood as path-presence only

**Premise:** Callers know `app/rag/sync.py::list_diff` ignores file content/mtime edits. **If false:** Stale chunks served until `/ingest`. **Detect:** Stale quotes with empty `/sync`.

### ASM-006 - Indexed filenames and first lines contain no secrets

**Premise:** `app/rag/collect.py::collect_folders` previews are safe to send to OpenRouter (`z-ai/glm-5`). **If false:** Sensitive fragments leave the host. **Detect:** Audit folder before `/ingest`.

### ASM-010 - `tool_call_id`s are unique and completed tool effects need no rollback

**Premise:** Providers emit distinct `tool_call_id`s and tool writes stand on later Stop/error (`app/agent/tools/policy_node.py::_merge_tool_messages`). **If false:** Merged tool messages collide. **Detect:** `turn_trace` counts.

### ASM-011 - Prose tool prohibitions hold while `bash` and `web_search` stay bound

**Premise:** Models obey prose forbidding `bash` document edits (`@grill` included) and `web_search` in `/citation` (`app/agent/desktop/turn_context.py`, `app/skills/citation/SKILL.md`). **If false:** `Bypass` `bash` mutates files or `web_search` pollutes `/citation`. **Detect:** `turn_trace`; `grill_eval.py`.

### ASM-012 - Binary runs from build-time checkout with Conda `app` intact

**Premise:** Repo stays at `CARGO_MANIFEST_DIR` with `python`, `pandoc`, and `app/vendor/bime-word/` (`app/desktop/src-tauri/src/backend.rs::source_conda_launch`). **If false:** `SOURCE_CHECKOUT_INVALID` or `BIBLIOGRAPHY_FAILED`. **Detect:** `Degraded` card or `bime_word.py doctor`.

### ASM-013 - Non-`web_search` MCP servers start and respond promptly

**Premise:** `github` and drop-in MCP `get_tools()` calls finish (`app/agent/mcp.py::load_mcp_tools_with_families`). **If false:** `ChatSession.create` hangs (`PERF-003`). **Detect:** Stuck `Creating your session`.

### ASM-014 - Model prose truthfully reports `citation_workflow` save statuses

**Premise:** Replies accurately report `saved`, `reused`, `verified`, and `storage_failed` (`app/skills/citation/tool.py`). **If false:** Misleading prose (`[[cite:...]]` still gated). **Detect:** `citation_save_finalized` log.

### ASM-015 - `writesDisabled` and SHA-256 prechecks prevent bibliography races

**Premise:** UI disabling + fingerprint checks suffice without an async lock (`app/agent/desktop/bibliography_ops.py`). **If false:** `BIBLIOGRAPHY_CONFLICT`. **Detect:** Panel conflict notice.

### ASM-019 - Accepted non-turn desktop requests eventually return or close pipes

**Premise:** Non-turn handlers return or self-timeout (`app/desktop/src-tauri/src/backend.rs::BackendSupervisor` has no timer). **If false:** Request wedges until `Restart`. **Detect:** Stuck `pendingRequests > 0`.

### ASM-021 - `3 * k` Chroma oversampling captures top `k` `folder_prefix` hits

**Premise:** Global top `3 * k` hits include `k` matches in `folder_prefix` (`app/rag/api.py::search`). **If false:** Silent `< k` recall. **Detect:** Compare `list_chunks` vs `search`.

### ASM-024 - Collection caps (`4,096` turns/files, `10,000` entries) never bind

**Premise:** Single-user stores stay below `MAX_TURNS` / `contract.json` caps (`app/agent/conversations/models.py::MAX_TURNS`). **If false:** `PROTOCOL_INVALID` / `scan_limit`. **Detect:** Validation error at cap + 1.

### ASM-025 - Node SSR and CSS tests approximate WSLg WebKitGTK layout

**Premise:** `clamp` font sizing, flow `Export`, and Monaco `10`-`28` px zoom render cleanly in WebKitGTK (`app/desktop/src/DocumentEditor.tsx`). **If false:** Clipping or 28px CJK overlap. **Detect:** Visual check in `python main.py`.

### ASM-026 - Windows picker interop works and opened `rootPath` still exists

**Premise:** `powershell.exe` + `wslpath` + `AttachThreadInput` work and `rootPath` exists (`app/desktop/src-tauri/src/backend.rs::run_windows_picker`). **If false:** Hung dialog or `NATIVE_PICKER_FAILED` with no text fallback. **Detect:** Picker error or hang.

### ASM-027 - Google keeps serving parseable `#search` HTML to Chromium

**Premise:** Google answers `/search` without `/sorry/` blocks (`app/vendor/web-search-mcp/src/search-engine.ts`). **If false:** Engine error / `zero_parsed`. **Detect:** `web_search.stderr.log`.

### ASM-028 - `web_search` gets short writable `/tmp`, direct network, and `dist/`

**Premise:** `/tmp` is writable (`TMPDIR`/proxies stripped), Chromium installed, `dist/index.js` built (`app/agent/mcp.py::_web_search_env`). **If false:** Tool omitted or launch fails. **Detect:** `mcpDiagnostics`.

### ASM-029 - Per-call `web_search` spawning makes in-process rate limits acceptable

**Premise:** Parallel `web_search` calls in one turn are rare (`app/agent/mcp.py::_load_web_search_tools`). **If false:** Concurrent browsers spike RAM (`PERF-002`). **Detect:** `web_search.stderr.log`.

### ASM-030 - Submissions (`<= 1 MiB`) and conflict lines (`<= 2 MiB`) fit wire caps

**Premise:** Multi-reference turns stay `<= 1 MiB` and ~3-copy conflict payloads stay `<= 2 MiB` (`app/desktop/src/lib/composer.ts::checkSubmissionSize`). **If false:** `SUBMISSION_INVALID` or framing error. **Detect:** Send/conflict error banner.

### ASM-031 - `LocalWorkScope` sync workers drain promptly on Stop

**Premise:** Threaded disk/Pandoc/`bime_word`/Chroma calls return quickly (`app/agent/ingest.py::await_sync_work`). **If false:** `Stopping...` waits with no deadline. **Detect:** Stuck `Stopping...`.

### ASM-032 - Users know `read_file`, RAG reads, and `bash` are not root-confined

**Premise:** Local trust permits `read_file` (outside `.env`/`.ssh`/`id_rsa`/`secret*`) across WSL (`app/agent/tools/read_file.py::_is_sensitive_path`). **If false:** Reads outside `<projectRoot>`. **Detect:** Transcript/`turn_trace`.

### ASM-033 - Initialized project folders are never moved or renamed

**Premise:** Canonical `rootPath` stays fixed (`app/agent/desktop/project.py::inspect_project`). **If false:** `project_id` mismatch blocks open (`FAIL-026`). **Detect:** Ownership error on open.

### ASM-034 - `langchain-openrouter==0.2.6` client replacement stays compatible

**Premise:** `model.client = bounded_sdk_client(...)` keeps governing timeouts/retries (`app/agent/llm/openrouter.py::get_openrouter_chat_model`). **If false:** 60-min SDK backoffs return. **Detect:** `app/tests/test_openrouter_model.py`.

### ASM-035 - Models cite via `[@key]` / `\cite{key}` rather than prose author-year

**Premise:** Models obey `_CITATION_KEY_INSTRUCTIONS` (`app/agent/desktop/document_ops.py::_unknown_new_citation_keys`). **If false:** Unverified prose citations bypass gate. **Detect:** `0 cited` in `CitationPanel`.

### ASM-036 - `@grill` reconstructs faithfully and resists sycophancy live

**Premise:** Live models follow `app/skills/grill/SKILL.md` (`## 還原` -> `## 發現` -> `## 判斷`) without nitpicking or caving, and users avoid mixing `@grill` + edit comments. **If false:** False positives or whole-turn read-only surprise. **Detect:** `grill_eval.py --live`.

### ASM-037 - Shared bibliography removal, NeurIPS scraping, and `bime_word` TOC hold

**Premise:** Uncited removal spares sibling files; NeurIPS papers live on `proceedings.neurips.cc` with `citation_*` tags (`app/skills/citation/authority.py::_neurips`); `bime_word` keeps `BIMETOCTitle`/`Heading1` (`app/agent/desktop/bime_export.py::_split_document_xml`) and users update Word fields. **If false:** Broken sibling keys, `not_found`, or stale TOC pages. **Detect:** `CitationPanel` & Word field update.

### ASM-038 - Closed-document `HISTORY_SNAPSHOT_HEADER` is read as pre-edit text

**Premise:** After editing in turn *N* and closing before *N+1*, the model treats `app/agent/document_context.py::HISTORY_SNAPSHOT_HEADER` as pre-edit text. **If false:** Quotes pre-edit text as current disk state. **Detect:** Keep edited file open.

## Lessons

| Lesson | From | Applies when |
|---|---|---|
| Never cache a failed Stop cleanup error; re-stop only remaining groups and clear `_turn_active` once disk state is terminal. | `75222fd` | Editing `LocalWorkScope` or `_session_stop` |
| Poll `try_wait()` for 500 ms on stdout EOF before reporting pipe close, because OS pipe EOF can beat process reap. | `8c34c9a` | Editing `app/desktop/src-tauri/src/backend.rs` |
| WSLg `powershell.exe` pickers need Win32 `AttachThreadInput` + `SetForegroundWindow` and a taskbar fallback. | `7489076` | Editing Windows/WSL pickers |
| Out-of-turn Ask-gated RPCs (`bibliography.add`) must register a live owner in `approvalOwner.ts` or React drops the prompt. | `22ae953` | Adding Ask-gated UI actions (`PLAY-002`) |
| Redact credentials at Python protocol exit (`bounded_error_message`) instead of blanking UI messages mentioning `token`. | `4d831eb` | Mapping wire errors (`INV-017`) |
| Pass per-turn overrides via `TurnOptions` inside `turn_outcome`'s `try/finally` instead of mutating sticky session fields. | `01fe7c1` | Adding per-turn session overrides |
| Validate schemas once in Python, import `contract.json` in TS/Rust, and enforce TS DTO parity in `protocol_types.test.ts`. | `9c98b72` | Changing protocol v1 (`PLAY-001`) |
| Gate `SourceRegistry` registration on `references.json` write success so Desktop never marks unwritten items citable. | `9068f87` | Editing `CitationService.save` (`INV-010`) |
| Pass child arrays to `createElement`, never variadic `createElement(...children)` (`RangeError` above ~100k nodes). | `SafeContent.tsx` | Rendering Markdown or citation previews |
| Isolate `AGENT_LOG_DIR` and `XDG_CACHE_HOME` in `conftest.py` autouse fixtures so pytest never pollutes user logs. | `711bf03` | Adding logs or subprocess tests |
