# Known Failure Modes

Freshness: revalidated 2026-10-23 at `3f9176a` by static inspection of source, test definitions, commit records and the plan build logs (current and recoverable from Git history). Nothing was reproduced this pass. The RAG failures FAIL-001 and FAIL-002 keep their original 2026-09-05 offline probes at `9745fd1`; their code is unchanged. FAIL-014 and FAIL-021 received a focused update at `d74065f` after the cleanup commits `c12470f`–`d74065f`. See [audit coverage](README.md#audit-coverage).

## Active failure modes

### FAIL-001 — Prune leaves stale folder inventory

- Symptom: `explore()` still lists a folder after prune removed its last indexed file.
- Trigger / preconditions: a repo-ingested folder becomes empty on disk, and `prune_orphans` deletes its orphan PID.
- Affected components or users: the RAG inventory and anything using `rag_explore`.
- Root cause: Confirmed — `prune_orphans` deletes Chroma and raw entries but never updates `folder_meta.json`.
- Current handling / recovery: re-ingest or rebuild the root.
- Reproduction or detection: the 2026-09-05 offline probe found `folders_before=[docs]` and `folders_after=[docs]`. No test pins this.
- Related invariants / assumptions: INV-012, ASM-003.
- Evidence: `app/rag/sync.py::prune_orphans`; `rag/api.py::explore`. Code unchanged since `5a0fa7c`.
- Status: Active

### FAIL-002 — Empty or unreadable re-ingest retains old chunks

- Symptom: ingest reports zero files and chunks, yet the path's earlier chunks remain listable and searchable.
- Trigger / preconditions: a repo-indexed file becomes empty, non-UTF-8 or unreadable, and the same root is re-ingested.
- Affected components or users: RAG search and context; research answers built from stale text.
- Root cause: Confirmed — only files that produce documents enter the folder-level delete set.
- Current handling / recovery: delete or prune the old source, or rebuild the store.
- Reproduction or detection: the 2026-09-05 offline probe re-ingested an emptied file, got `(0, 0)`, and found the old chunks still present.
- Related invariants / assumptions: INV-012, ASM-003.
- Evidence: `app/rag/cli/ingest.py::ingest_repo` (unchanged logic).
- Status: Active

### FAIL-003 — RAG multi-store writes can diverge

- Symptom: folder inventory, raw JSON and Chroma describe different partial states.
- Trigger / preconditions: either of two events during ingest or prune.
  - A Chroma, Ollama or filesystem failure after folder metadata or some Chroma writes, but before the deferred raw JSON commit.
  - A user Stop at the same point: the JSON batch is discarded while Chroma keeps its partial writes.
- Affected components or users: semantic search versus list, context and explore results.
- Root cause: Confirmed — there is no transaction across the three stores. `folder_meta.json` is rewritten directly, before chunks, and a malformed read falls back to `{}`.
- Current handling / recovery: rerun ingest, or back up and rebuild the store. Re-ingest any unrelated roots whose folder metadata was lost to the `{}` fallback.
- Reproduction or detection: the failure semantics follow from the code. Raw JSON rollback tests exist, but no test injects a cross-store failure or checks the stores after a Stop.
- Related invariants / assumptions: INV-008, INV-012, ASM-003.
- Evidence: `app/rag/cli/ingest.py`; `rag/store/document_store.py`; `rag/store/json_store.py::deferred_save`; `app/agent/ingest.py::LocalWorkScope`.
- Status: Active

### FAIL-009 — Provider or MCP failure degrades or aborts the affected path

- Symptom: a chat, extended, ingest, search or Citation operation fails, or configured MCP tools are missing.
- Trigger / preconditions: a missing key, model or service; a network failure; a server crash; a hung or failed MCP startup.
- Affected components or users: the affected feature only.
- Root cause: Confirmed operational dependency.
- Current handling / recovery:
  - The prompt is persisted as pending before any provider work. A provider exception fails the turn with an incident reference; if that write also fails, the turn becomes interrupted on reload. Neither state replays automatically.
  - OpenRouter retries 5xx and network errors at most twice. An extended rewrite failure is recorded as a completed answer containing the error text.
  - An MCP load failure is logged as `mcp:<server>: applied_but_unavailable: <prepare|load>: <Type>: <msg> [causes: …]; stderr log: <path>` and the base session continues.
- Reproduction or detection:
  - CLI `/status` prints only `mcp_families`.
  - Failure reasons are in `session.extension_startup_diagnostics` (Desktop `runtime.diagnostics.mcpDiagnostics`), the diagnostic log and `$XDG_CACHE_HOME/agent-mcp/<server>.stderr.log`.
  - Tests: `test_mcp.py::test_session_create_survives_mcp_failure`, `test_web_search_load_failure_names_the_cause_and_log`; `test_session_persistence.py::test_failed_turn_records_one_incident_in_log_and_transcript`.
- Related invariants / assumptions: INV-031, ASM-001, ASM-013, ASM-027, ASM-028.
- Evidence: `app/agent/startup.py`; `agent/mcp.py`; `agent/session.py`; `agent/llm/openrouter.py`.
- Status: Active operational mode

### FAIL-013 — Raw desktop folder-ingest methods are declared but disabled

- Symptom: direct `knowledge.init_workspace` or `knowledge.ingest_folder` calls return `RAG_WRITE_FAILED`, although the GUI can run `/init` and `/ingest` through the composer.
- Trigger / preconditions: a client uses the raw protocol method instead of `session.turn` with the slash command.
- Affected components or users: alternate protocol clients and future refactors. React does not use either method.
- Root cause: Confirmed — both handlers deliberately raise until they have structured progress. `knowledge.ingest_file` works and requires approval.
- Current handling / recovery: send `/init` or `/ingest <absolute-directory>` in the selected conversation.
- Reproduction or detection: `test_desktop_service.py::test_folder_ingest_waits_for_structured_progress_step`.
- Related invariants / assumptions: INV-011, INV-015, INV-018.
- Evidence: `app/agent/desktop/service.py::_knowledge_init_workspace`, `_knowledge_ingest_folder`, `_knowledge_ingest_file`.
- Status: Active compatibility limitation

### FAIL-014 — Developer documentation references deleted or retired material

- Symptom: eight relative links point at deleted files, and several strings still describe retired behavior.
- Trigger / preconditions: following the links or wording instead of current code. The cleanup on 2026-10-15 deleted `app/SKILLS_GUIDE.md` (`d497bd9`) and `app/agent/extensions/README.md` (`be9c46e`); `b4d56f1` removed the desktop-interaction plan log.
- Affected components or users: contributors and agents navigating the docs.
- Root cause: Confirmed documentation drift. The broken links are:
  - root `README.md` → `harness/plans/2026-10-18-desktop-interaction/build-log.md`;
  - `app/README.md` → `agent/extensions/README.md` and `SKILLS_GUIDE.md`;
  - `app/agent/README.md` → `extensions/README.md` and `../SKILLS_GUIDE.md`;
  - `app/agent/tools/README.md`, `app/agent/thinking/README.md` and `app/skills/citation/README.md` → `SKILLS_GUIDE.md`.

  The stale strings are:
  - `ChatSession.set_thinking_mode` says "/citation off".
  - `activate_citation_skill` and `SlashCommandResult` docstrings still say "persistent".
  - The `bash.py` docstring and `tools/README.md` say every call prompts, which Bypass contradicts.
  - `agent/README.md` describes `ingest.py` only as a RAG wrapper.

  Corrected on 2026-10-23: the RAG store notes (`d74065f`); the `plan_logs_dir` comment went with the field (`73c8db1`).
- Current handling / recovery: rely on current code, `SKILL.md` files and the root README. The deleted files are recoverable from their parent commits. The earlier stale `/skill`, `task_modes` and persistent Citation wording is gone.
- Reproduction or detection: a relative-link check over tracked Markdown (run read-only this pass). The removed desktop plan log records that its README review saw the `SKILLS_GUIDE` links and deliberately left other historical docs unrepaired.
- Related invariants / assumptions: INV-019.
- Evidence: the files and commits above; `b4d56f1^:harness/plans/2026-10-18-desktop-interaction/build-log.md` (P6-S2 entry).
- Status: Active documentation conflict

### FAIL-022 — Failed Stop cleanup keeps the backend busy until restart

- Symptom: after a Stop, new turns, conversation selection, deletion, project open and backend shutdown all return `BUSY_TURN`. Retry Stop returns the same error each time.
- Trigger / preconditions: the turn's cleanup raises (for example a bash process group that will not exit), or the turn has not reached a saved terminal state.
- Affected components or users: the Desktop session. The root README promises that Retry Stop recovers.
- Root cause: Confirmed — the `finally` block in `_session_turn` leaves `_turn_active = owner.error is not None`. `_session_stop` re-raises the cached `owner.error` and never retries cleanup.
- Current handling / recovery: restart the backend once the turn's terminal result has arrived. Rust shutdown gets `BUSY_TURN`, so the child is killed after the bounded waits and a new generation starts.
- Reproduction or detection: `test_desktop_document_service.py::test_failed_stop_cleanup_keeps_new_turn_blocked` pins the blocked state. No test covers a second Stop or the still-pending branch.
- Related invariants / assumptions: INV-027, ASM-031.
- Evidence: `app/agent/desktop/service.py::_session_turn`, `_session_stop`; `answer_stream.test.ts` ("Stop failure remains blocked…").
- Status: Active

### FAIL-023 — Full pytest appends to the user's real MCP stderr logs

- Symptom: run headers and test-server logs appear in `~/.cache/agent-mcp/*.stderr.log` (alpha, beta, dropin, legacy and others).
- Trigger / preconditions: running the suite without redirecting `XDG_CACHE_HOME`. Tests built on a default `MCPServerSpec` reach `_spec_to_connection`, which calls `prepare_stderr_log` under the real cache.
- Affected components or users: the user's cache directory and later log forensics: those headers are not user turns.
- Root cause: Confirmed — `tests/conftest.py` isolates only `AGENT_LOG_DIR`.
- Current handling / recovery: run the full suite with `XDG_CACHE_HOME`, `AGENT_LOG_DIR` and `TMPDIR` pointing at temporary directories, as the 2026-10-22 plan's full run did. Lines already appended were deliberately not deleted.
- Reproduction or detection: incident I1, recorded 2026-10-19 in `8d38151^:harness/plans/2026-10-19-citation-search-reliability/build-log.md`; static `conftest.py` inspection this pass.
- Related invariants / assumptions: INV-028.
- Evidence: `app/tests/conftest.py`; `app/agent/mcp.py::_spec_to_connection`.
- Status: Active

### FAIL-024 — DataCite search errors with an opaque cause

- Symptom: provider state `datacite:error` with no category during natural `/citation` runs.
- Trigger / preconditions: unknown. A plain `ProviderError` (for example an unparseable payload or a response over 2 MiB) is rendered as a bare `error`. Queries are sent unescaped as Lucene text, so syntax characters may produce HTTP 400.
- Affected components or users: Citation recall. Crossref results still arrive, and the search is marked incomplete.
- Root cause: Unknown.
- Current handling / recovery: reported honestly as an incomplete search. The provider is not skipped for the task, because the failure is not classified as transient.
- Reproduction or detection: incident I4, seen twice on 2026-10-19 and not reproduced with ordinary queries (same removed plan log as FAIL-023). `test_citation_provider_datacite.py::test_search_text_encodes_once_caps_rows_and_uses_cache` pins the raw query.
- Related invariants / assumptions: ASM-001.
- Evidence: `app/skills/citation/providers/datacite.py::_text_query`; `providers/net.py::describe_failure`.
- Status: Monitoring

### FAIL-025 — Ask silently denies oversized or secret-looking approvals

- Symptom: the operation fails with `APPROVAL_DENIED` ("denied or its approval expired") although the user never saw a prompt.
- Trigger / preconditions: Ask mode, and an operation whose JSON parameter summary exceeds 8,192 bytes or whose target, description or summary looks like a credential. Example: `/prune <dir> --yes` with roughly 100 or more orphan paths.
- Affected components or users: Desktop users running large index mutations, MCP calls, installs or Citation saves.
- Root cause: Confirmed — `DesktopService._operation_approval` returns `False` before creating any approval event.
- Current handling / recovery: split the operation, or deliberately switch to Bypass. The UI does not explain the cause.
- Reproduction or detection: source inspection only; no test covers summaries over 8 KiB.
- Related invariants / assumptions: INV-018.
- Evidence: `app/agent/desktop/service.py::_operation_approval`, `_approval_context_is_safe`, `_require_operation_approval`.
- Status: Active

### FAIL-026 — Project open fails closed on unhealthy history

- Symptom: `workspace.select open` returns `PROTOCOL_INVALID` with "project history scan is incomplete…", "history contains conversations with different or unknown project ownership…" or "catalog references missing conversations…", and no conversations are listed.
- Trigger / preconditions: any of these in the history directory:
  - a malformed or unreadable conversation file;
  - more than 4,096 files;
  - a conversation owned by another projectId (after a root move, or legacy global history);
  - a catalog entry whose file is missing;
  - a malformed catalog with no conversations.
- Affected components or users: every Desktop conversation in that project.
- Root cause: Confirmed and intended — `load_project_catalog` never guesses or repairs ownership and never lists partially.
- Current handling / recovery: inspect the history directory read-only, then move or fix the offending file. Alternatively, correct `historyDirectory` in `RESEARCH.md`, or initialize a new empty history. Foreign ownership needs a manual `projectId` edit. Nothing in this path modifies files.
- Reproduction or detection: `test_desktop_conversations.py::test_malformed_conversation_blocks_incomplete_history_scan_without_writes`, `test_catalog_only_missing_json_blocks_open_without_fake_transcript`, `test_unknown_project_orphan_requires_mapping_without_changing_history`.
- Related invariants / assumptions: INV-016, ASM-024, ASM-033.
- Evidence: `app/agent/desktop/catalog.py::load_project_catalog`.
- Status: Active (intended fail-closed behavior)

### FAIL-027 — A killed web search can leave Chromium profile directories

- Symptom: `/tmp/playwright_chromiumdev_profile-*` directories (about 190 KB each) remain.
- Trigger / preconditions: the Python process is killed with SIGKILL while a web search call owns Chromium.
- Affected components or users: `/tmp` clutter only.
- Root cause: Inferred — Playwright's temporary profile is not removed when its owner is killed before cleanup.
- Current handling / recovery: delete the leftover directories manually when no search is running.
- Reproduction or detection: exclusion X03 in `harness/plans/2026-10-22-web-search-acceptance-fixes/context/acceptance-findings.md`, recorded as rare and small and left for later.
- Related invariants / assumptions: INV-031.
- Evidence: the plan record above.
- Status: Active (low impact)

## Mitigated but still relevant

### FAIL-021 — Generated stores and plan logs escaped the ignore policy

- Former symptom: `app/store/` (Desktop conversations with full prompts, answers and frozen document text) showed as untracked instead of ignored, and four generated `app/plan_logs/*.md` stubs were committed.
- Root cause: `4abc132` deleted `app/.gitignore`, the only file ignoring `store/` and `plan_logs/`. The stubs entered in `1cf54d7`, a commit titled "Delete harness/" that also changed `main.py`, launcher tests, lazy RAG imports and `App.tsx`.
- Resolution: on 2026-10-23, with the user's approval, `c12470f` added `/app/store/` to the workspace `.gitignore`, and `73c8db1` removed the stubs together with `AgentConfig.plan_logs_dir`. AGENTS.md no longer lists `app/plan_logs/`.
- Detection/recovery: `git check-ignore -v app/store/x` should report `.gitignore:12:/app/store/`.
- Limits: nothing checks the ignore rules. Deleting or editing `.gitignore` can silently undo this again.
- Related: INV-029.
- Status: Mitigated

### FAIL-028 — Reference comments demoted `/citation` to plain text

- Former symptom: when a passage comment existed, `composeTurnText` produced "Main request:\n/citation …". The backend's leading-slash parser therefore never saw the command, and the turn ran as a normal agent turn without `citation_workflow`. A natural run on 2026-10-19 used Web Search instead.
- Resolution: commit `2bc784a` keeps an explicit `/citation` first. The `off`, `none` and `deactivate` arguments keep the old wrapping, and comments, quoted sources, `@citation` and `/citationfoo` never select the Skill.
- Detection/recovery: `test_inline_skills.py::test_desktop_citation_command_survives_reference_comment_composition` runs the shipped TypeScript composer under Node through the real `DesktopService`, graph and Citation tool. It is documented as failing before the fix.
- Limits: by design, any other slash command is still wrapped as plain text when comments exist (`conversations.test.ts` pins `/status`).
- Related: INV-030, ASM-035.
- Status: Mitigated

### FAIL-029 — Slow OpenRouter gateway errors were not retried

- Former symptom: on 2026-10-19 two `/citation` final-answer calls received HTTP 504 after 32.6 s and 51.5 s. The 20 s retry window introduced by `37a448c` had already closed, so both turns failed after minutes of tool work.
- Resolution: commit `ccb0c40` disables SDK retries and retries any 5xx or network error up to `llm_max_retries` (default 2), regardless of attempt duration. Waits are 1 s and 2 s, capped at 8 s including Retry-After.
- Detection/recovery: `test_openrouter_model.py::test_slow_gateway_failure_is_still_retried`, plus cancellation and timeout tests.
- Limits: timeouts (600 s per attempt), 4xx and 429 are not retried (ASM-034).
- Status: Mitigated

### FAIL-030 — Web search acceptance defects AF01–AF44

- Former symptom: the 2026-10-21 Web Search implementation had verified defects. Content was dropped or duplicated, charsets were wrong and truncation took quadratic time. Local timeouts were not true totals, owned Chromium went unrecognized, statistics were misleading, startup was unbounded and wrapper errors replaced results.
- Resolution: the 2026-10-22 plan fixed or handled all 44 findings, killed all 42 must-kill mutations, and passed real-entry checks in 15 local cases. Bing was removed after delivery (`1bc3bf2`).
- Detection/recovery: vendored Node tests (retention, content contract, browser lifecycle, server entry) and `test_mcp.py`. See [testing strategy](testing-strategy.md).
- Limits:
  - Google stability at volume is unverified (ASM-027).
  - Stack Overflow returned a Cloudflare 403 on both read paths.
  - Mutation survivors P07b and P07d (PID reuse) were accepted.
  - Engine errors store raw `error.message` (`search-engine.ts`), so multi-line Playwright text can reach tool output (static observation).
- Evidence: `harness/plans/2026-10-22-web-search-acceptance-fixes/build-log.md` (F7-S4 reconciliation and post-delivery section).
- Status: Mitigated

### FAIL-015 — Desktop Citation entry and lifecycle

- Former symptom: the Desktop rejected `/citation`.
- Resolution: `/citation <prompt>` and inline `@citation` run one Normal task in CLI and Desktop, then release the Citation scope and restore the mode. The Desktop catalog lists `/citation` only when its runtime and tool are eligible. Under Ask, each Citation save needs approval. Stop gives a per-task cancellation entry.
- Detection/recovery: `test_citation_e2e.py` (fresh runtime gating, cleanup, exact completed replay); `test_project_permissions.py::test_tool_operations_receive_frozen_single_operation_consent`.
- Limits: a cancelled save's late writer may still land a bundle, but it is never registered (`test_cancelled_save_late_writer_cannot_populate_next_citation`). No fresh native or live-provider run.
- Related: INV-010, INV-019.
- Status: Mitigated

### FAIL-017 — A persisted first-turn failure disappeared from the sidebar

- Former symptom: after a durably accepted first prompt failed, creating another conversation could leave the failed one absent from the sidebar or impossible to select.
- Resolution: the Python callback registers the catalog right after the durable pending write. React's `sendTurn` error path refreshes the catalog and transcript under generation, project and session guards when the turn was accepted, or when the error came from the transport.
- Detection/recovery: Python `test_desktop_conversations.py::test_first_prompt_registers_catalog_before_provider_failure` and `test_registration_failure_is_pending_and_retry_does_not_rerun_turn`. The TS test "only an accepted and persisted prompt qualifies for a saved-conversation refresh" checks the predicate only.
- Correction: the previously cited TS journey test "durable first-turn failure remains selectable after creating another conversation" was removed in `971f828` on 2026-09-06, before the previous baseline.
- Status: Mitigated

### FAIL-018 — A pending retry duplicated its stale failure card

- Former symptom: retrying a restored failed or interrupted turn showed both the old card and a new pending card.
- Resolution: pending records join `mergeConversationTurns` under the `(sessionId, turnId)` identity; the terminal `turnNumber` is authoritative.
- Detection/recovery: `answer_stream.test.ts` ("pending failed and interrupted retries replace…", "a pending new turn remains appended…"); `conversations.test.ts` ("an unresolved retry renders one prompt…").
- Status: Mitigated

### FAIL-019 — Large Markdown exceeded JavaScript's variadic argument capacity

- Former symptom: large inline, list or block Markdown failed when content-sized arrays were spread into function arguments.
- Resolution: `SafeContent` passes array children (unchanged since the fix).
- Detection/recovery: three 140,000-child regressions in `conversations.test.ts`; a scan found no remaining variadic spreads of content-sized arrays in `app/desktop/src`.
- Limits: no native memory or performance claim (ASM-025).
- Status: Mitigated

### FAIL-020 — A maximized window kept compact typography

- Former symptom: wide windows added whitespace while text stayed small.
- Resolution: the bounded root clamp (INV-021).
- Limits: the Monaco editor (14px) and comment text (13px) are fixed px and do not scale. Native maximized, DPI and human visual acceptance remain unverified.
- Detection/recovery: `styles.test.ts` checks the root rule only.
- Status: Mitigated for rem-based UI; not for the editor and comment surfaces

### FAIL-016 — Fixed absolute Desktop request deadline

- Former symptom: Rust killed healthy requests after 600 s.
- Resolution: normal requests have no deadline (commit `45d446d`). A live turn can now be ended with Stop; other stuck requests still need a restart (ASM-019).
- Detection/recovery: Rust `progressing_request_can_outlive_the_prior_absolute_deadline`, `stdout_pipe_close_fails_the_pending_request_without_a_deadline`, `shutdown_bounds_an_in_flight_request`.
- Status: Mitigated

### FAIL-005 — Post-startup applied Skill tampering is rejected before activation

- Resolution: activation re-inspects each managed bundle against the approved `applied_source_hash`, including every inline composite member.
- Limits: the precheck-to-read race remains.
- Evidence: `load_skill_runtime`; `test_runtime_rejects_applied_bundle_changed_after_startup`.
- Related: INV-013, ASM-007.
- Status: Mitigated

### FAIL-006 — Cooperating extension-apply writers are serialized

- Resolution: a nonblocking exclusive flock on the stable `.apply.lock` spans the revision read through durable publication.
- Limits: covers local cooperating writers only, not other stores.
- Evidence: `ExtensionManager.apply`; `test_extension_manager.py::test_cross_process_apply_preserves_successful_update` (definitions carried forward).
- Related: INV-009, ASM-008.
- Status: Mitigated

### FAIL-007 — Earliest-year ties fail as ambiguous

- Resolution: missing or tied years return ambiguity, and `CitationService._plan_item` keeps authority fallback from overriding it.
- Limits: year precision only. A unique known minimum still wins alongside undated alternatives.
- Evidence: `resolution.py::decide_resolution`; `test_citation_work_resolver.py::test_earliest_ambiguity_returns_before_doi_refetch`.
- Related: INV-014, ASM-009.
- Status: Mitigated

### FAIL-010 — Empty or tool-protocol model output

- Resolution: two empty-reply retries, one tool-free repair for invalid final content, then a deterministic fallback before persistence.
- Evidence: `graph.py`; `test_graph_skill_loader.py::test_agent_node_reports_persistent_blank_answers_honestly`, `test_agent_node_repairs_dsml_protocol_artifact`.
- Related: INV-005.
- Status: Mitigated

### FAIL-011 — Graph tool quota and recursion fuse mismatch

- Resolution: one validated `graph_recursion_limit` (default 64, minimum 3) forces tool-free finalization near the fuse.
- Evidence: `test_graph_skill_loader.py::test_agent_node_finalizes_before_recursion_limit`; `note/20260820/agent_loop_guardrail_consolidation.md`.
- Related: INV-005.
- Status: Mitigated

### FAIL-012 — Cross-platform line-ending churn

- Resolution: `.gitattributes` enforces LF, with batch/cmd exceptions.
- Evidence: `.gitattributes`; commit `3ac4f8b`.
- Related: INV-002.
- Status: Mitigated

### FAIL-008 — The desktop shell was disconnected from the Python backend

- Former symptom: before commits `30f8b18` through `1e22f90`, the UI was a disabled shell. The backend now starts automatically through `BackendClient.initialize()` and runs as a release binary.
- Remaining limits: FAIL-013 and ASM-012.
- Status: Mitigated (history)

### FAIL-004 — Legacy hard-cap history loss

- Former symptom: the retired TurnStore could drop turns after repeated Chroma history failures.
- Resolution: canonical conversation JSON keeps every accepted turn, and no session path uses conversation Chroma. The remaining item-count limits are tracked in ASM-024.
- Status: Resolved

## Diagnostic index

| Symptom | First safe check | Likely item |
|---|---|---|
| Explore lists a deleted folder | Compare `folder_meta.json` with root-scoped raw chunks | FAIL-001 |
| An emptied file still appears in search | `list_chunks` for its namespaced PID after re-ingest | FAIL-002 |
| Search and list/context disagree, or a Stop interrupted ingest | Compare raw JSON with Chroma after the last failed or stopped ingest | FAIL-003 |
| Tools missing, or a provider call failed | Desktop `runtime.diagnostics` / diagnostic log incident ID / `agent-mcp/*.stderr.log` | FAIL-009 |
| `knowledge.init_workspace` says not enabled | Use `/init` or `/ingest` through `session.turn` | FAIL-013 |
| A README link 404s, or the text mentions `/citation off` | Check whether the target was deleted on 2026-10-15; trust code and `SKILL.md` | FAIL-014 |
| `app/store/` files show up in `git status` again | `git check-ignore -v app/store/x` should name `/app/store/` | FAIL-021 |
| Everything returns `BUSY_TURN` after a Stop | Check the Stop reply error; restart the backend | FAIL-022 |
| Unexpected headers in `~/.cache/agent-mcp` logs | Check whether a test run lacked `XDG_CACHE_HOME` isolation | FAIL-023 |
| `datacite:error` in Citation results | Look up the provider line in the diagnostic log by `batch_id` or time | FAIL-024 |
| `APPROVAL_DENIED` without any prompt | Size and content of the operation parameters under Ask | FAIL-025 |
| A project will not open: "history scan is incomplete" or "ownership" | Inspect `<historyDirectory>/conversations` read-only for malformed or foreign files | FAIL-026 |
| `/tmp/playwright_chromiumdev_profile-*` accumulates | Check for SIGKILLed backends during searches | FAIL-027 |
| A `/citation` turn with comments ran without Citation tools | Confirm the composed text starts with `/citation` | FAIL-028 |
| A turn failed after an OpenRouter 504 | Look for `openrouter request retry` lines in the diagnostic log | FAIL-029 |
| A web search engine line shows `error`, `http_status=429` or `final_path=/sorry/` | Engine facts in the tool output; check Chromium launch prerequisites | FAIL-030, ASM-027, ASM-028 |
| The picker fails with "starting folder is unavailable" | Was the open project folder moved or deleted? Restart the app | ASM-026 |
| An earliest-version save returns ambiguity | Compare candidate years and relations, not rank | FAIL-007 |
| Changed applied Skill rejected mid-session | Activation hash diagnostics; re-apply or restore the approved bytes | FAIL-005 |
| Huge Markdown or editor text renders badly | Distinguish `SafeContent` correctness from native performance; check fixed-px surfaces | FAIL-019, FAIL-020, ASM-025 |
