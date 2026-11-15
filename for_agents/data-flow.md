# Data Flow

Freshness: revalidated 2026-10-23 at `3f9176a` by static inspection of source and test definitions. The extension-apply and ZIP-installer flow received a focused check only (Bypass, inline-Skill and desktop gating changes); its other steps carry forward 2026-09-13 evidence at `a88d44d`. Nothing was executed. See [audit coverage](README.md#audit-coverage).

## Primary flows

### Flow: Agent turn (CLI and Desktop)

- Trigger / input: user text passed to `ChatSession.turn_outcome` by the CLI loop or by `DesktopService._run_session_turn`. Optional arguments: `turn_id`, `skill_name`, `skill_references`, `retry`, `submitted_context`.
- Output / side effect: one finalized `TurnOutcome`; canonical pending then terminal JSON; `turn_trace` log lines; tool side effects, which are never rolled back.
- Steps:
  1. Caller — the Desktop binds a `LocalWorkScope` (context variables for work callbacks); the CLI binds none.
  2. `ChatSession.turn_outcome` — takes the turn lock, resolves inline `@name` references before any write, and chooses the effective mode (installer or Citation forces Normal).
  3. Persistence — `_begin_turn` reloads and recovers leftover pending work, then creates, appends or retries the pending turn with its submitted context, and fires the prompt-persisted callback. On the Desktop that callback emits `turn.accepted` and registers the catalog entry. A completed same-ID turn returns its stored outcome without a model call. A pending same-ID turn is a conflict. A failed or interrupted turn needs `retry`.
  4. `TurnTimingTrace` — emits `turn_start`. Model calls and admitted tool runs are traced with durations, `query_hash`, Citation counts and `output_chars`.
  5. Graph — `skill_loader`, then `agent`, then `tools`. The `agent` node allows at most two empty-reply retries and one repair, then a deterministic fallback, and forces finalization when fewer than 3 steps remain. The `tools` node runs `PolicyToolNode` admission, asks per-call consent, then executes through `ToolNode` and `run_local_work`. A tool exception becomes a logged `Tool error: <Type>: <text> (incident <id>)` ToolMessage.
  6. `finalize_and_record` — safety check, Citation save metrics, installer result, Citation gate and render, Desktop final-text validator, shielded `complete_turn`, journal.
  7. `finally` — `turn_end` (open runs are closed as `unfinished`), runtime and registry cleanup, thinking-mode restore.
- State or ownership transitions: absent → pending → completed, failed or interrupted, all in one canonical JSON file. The scope goes from bound to stopped (only on Stop) to settled.
- Error / retry / rollback behavior:
  - `CancelledError` → interrupted with `code=cancelled`, then re-raised.
  - `ConversationError` → failed with `persistence_failed`.
  - Any other exception → an incident is attached and its traceback logged, and the turn fails with "The turn could not be completed. (incident <id>; <Type>; details in <log path>)".
  - If the failure write itself fails, the turn stays pending and becomes interrupted on reload.
  - OpenRouter retries happen inside the HTTP client: at most 2, for 5xx or network errors.
  - Nothing replays automatically.
- Invariants involved: INV-004, INV-005, INV-006, INV-019, INV-026, INV-027, INV-028.
- Evidence: `app/agent/session.py::turn_outcome`, `_begin_turn`, `finalize_and_record`; `graph.py`; `observability.py`; `test_session_persistence.py`; `test_observability.py`; `test_turn_finalizer.py`. Source and test definitions.
- Confidence: Confirmed.

### Flow: Desktop project open and initialization

- Trigger / input: the user picks a folder (Rust `pick_project` returns a canonical Linux path), then React sends `workspace.select` with `action` set to `inspect`, `initialize` (with `historyDirectory` and `expectedFingerprint`) or `open`.
- Output / side effect: a `RESEARCH.md` metadata block (initialize only), the history skeleton `<historyDirectory>/{conversations/, desktop-projects.json}`, catalog reconcile writes, and a bound project, repository and document workspace.
- Steps:
  1. Gate — refused while a turn, approval, project operation, session creation, knowledge, extension or document lock is active.
  2. `catalog.inspect_project` — resolves the canonical root and derives projectId `p-` + sha256(root)[:32]. Reads `RESEARCH.md` (at most 1 MiB, UTF-8) and parses exactly one fence-aware block `{"version":1,"historyDirectory":…}`. Returns `needs_configuration`, `needs_initialization` or `ready`, plus the rules text with the block stripped.
  3. `initialize_project` — re-inspects, then refuses a symlinked or changed `RESEARCH.md`. Requires the history to be absent or an empty skeleton. Creates `conversations/` and the catalog, then writes `RESEARCH.md` (temp file, fsync, fingerprint recheck, link or replace). Finally re-inspects, which must report `ready`.
  4. `load_project_catalog` — strict history scan (any issue fails the open), ownership check, catalog create, repair or reconcile.
  5. Service — builds a new `DocumentWorkspace`, shuts down the previous session, binds catalog, repository and project, clears candidates and caches, and returns `opened`.
- State or ownership transitions: no conversation storage is reachable before an open. After it, the project's history directory is the only Desktop conversation root.
- Error / retry / rollback behavior:
  - `CatalogError` becomes `PROTOCOL_INVALID`, with the raw message and no incident. A busy service returns retryable `BUSY_TURN` or `SESSION_NOT_READY`.
  - If writing `RESEARCH.md` fails after the history skeleton exists, the empty history remains; retrying is idempotent.
  - Nothing rolls back: the previous project stays bound until the final binding step.
  - `open` on a project that is not ready returns the inspection result without opening it.
- Invariants involved: INV-016, INV-026, INV-029.
- Evidence: `app/agent/desktop/catalog.py::inspect_project`, `initialize_project`, `load_project_catalog`; `service.py::_workspace_select`; `test_desktop_conversations.py`; `test_desktop_fixture.py`. The `inspect_project` and `initialize_project` branches have no direct tests.
- Confidence: Confirmed source; initialization branches untested.

### Flow: Desktop documents — open, save, conflict, agent edit

- Trigger / input: `pick_document(rootPath)` followed by `document.open{path}`; Ctrl+S or the file menu for `document.save{documentContext}`; model `document_edit` calls during a document turn; `document.apply` or undo from React.
- Output / side effect: document text written in place (temp file, fsync, `os.replace`, mode preserved); JSON receipts to the model; conflict choices in the UI.
- Steps:
  1. Open — `DocumentWorkspace.open` resolves the path strictly inside the root and checks suffix and size. Returns the raw text, a SHA-256 fingerprint and `editorRevision` 0. Monaco edits then bump `editorRevision` and recompute `sourceText`, preserving the BOM and newline style.
  2. Save — compares the editor identity and the last-read disk fingerprint. A mismatch returns `conflict` (candidate, disk text, new `expectedSnapshot`) and writes nothing. Otherwise it writes and returns `saved` with the revision plus one.
  3. Agent edit — `document_edit` is available only in document turns. It needs a `reference_id` when several document references exist, treats chat references as read-only, and requires the target to equal the editor path. It prepares a range-bound candidate, emits `document.proposed`, and waits up to twice the approval timeout for React's `document.apply`. Under Ask an `approval.required` event is sent. `apply` re-checks editor and disk, then writes or returns `conflict`, and the receipt goes back to the model.
  4. Conflict panel — Keep and Cancel never write. "Use candidate and save" re-runs approval and re-checks against `expectedSnapshot`. Undo is a separate, idempotent operation that checks for later versions.
- State or ownership transitions: disk is the truth. React holds editor text and baseline. Python holds candidates, receipts and undo state in memory for the current project open.
- Error / retry / rollback behavior: a timeout returns a `cancelled` receipt and keeps the candidate. Stop marks the turn's candidates `stopped` (undo still allowed) and waits for writes already in flight. A restart discards candidates and never replays them. Manual save needs no approval; agent apply and undo need it under Ask.
- Invariants involved: INV-018, INV-025, INV-027.
- Evidence: `app/agent/desktop/documents.py`; `service.py` document handlers; `test_desktop_documents.py`; `test_desktop_document_service.py::test_same_turn_reference_edits_keep_prior_saved_text_and_utf16_ranges`, `test_stop_waits_started_document_save_and_preserves_saved_effect`.
- Confidence: Confirmed source and test definitions; Monaco and native save were not exercised.

### Flow: Comments, frozen submission, acceptance and retry

- Trigger / input: passage comments on a Monaco selection (widget or Ctrl/Cmd+Alt+Enter) or on a chat selection, plus the main message, which may be empty. Send, or Enter in the main composer.
- Output / side effect: one `session.turn`. Its `text` comes from `composeTurnText`, and its `submittedContext` freezes permission, thinking, Skill references, rules text, the document snapshot and the references. The resulting canonical turn (v3 file) stores that context.
- Steps:
  1. React — runs `workspace.select inspect` to get the current rules, builds `submittedContext`, and checks that text plus context stay within 1 MiB (`checkSubmissionSize`). It keeps an explicit leading `/citation` first; when comments exist, any other slash command becomes plain "Main request" text. Sends through `requestTracked`.
  2. Python protocol — validates the UTF-16 Skill-reference ranges and the context: project, canonical paths, rules text against its SHA-256, snapshot ranges and line numbers, unique reference IDs.
  3. `_submitted_turn_context` — re-reads `RESEARCH.md`, which must still be `ready` with the same root, projectId and history. For an existing `turnId` the stored display text and context are authoritative, and Permission and Thinking must match unless the turn completed.
  4. Prompt assembly — resolves Skill references against the live catalog (stale references give `PROTOCOL_INVALID`) and routes local slash commands to display-only turns. Otherwise it appends the editor snapshot and the frozen-reference JSON, showing each identical document version only once (`sourceTextSameAs`). Document turns force Normal thinking.
  5. Persistence and acceptance — the pending write carries the context and is followed by `turn.accepted`. React clears drafts, references and numbered markers only on that event, or on an accepted terminal, for the current generation, session and turn.
  6. Execution and terminal — as in the agent-turn flow.
- State or ownership transitions: drafts and markers live only in React memory and are lost on restart. After acceptance the submission is immutable canonical data.
- Error / retry / rollback behavior: a failure before the pending write returns `accepted:false` and keeps the draft. Failures after acceptance carry `{turnId,state,accepted,persisted}`. Retry reuses the stored text and context under the same `turnId` and requires matching Permission and Thinking; otherwise the UI offers "Send new turn with current settings". A cancelled turn is not retryable.
- Invariants involved: INV-011, INV-019, INV-026.
- Evidence: `app/desktop/src/conversations.ts::composeTurnText`; `App.tsx::sendTurn`; `protocol.py::validate_message`; `service.py::_submitted_turn_context`, `_model_reference_projection`; `test_desktop_document_service.py::test_model_input_shows_each_frozen_document_version_once`; `answer_stream.test.ts`; commit `2bc784a`.
- Confidence: Confirmed.

### Flow: Stop and settle

- Trigger / input: Stop (the Send button turns into Stop during a turn) sends `session.stop{sessionId, turnId, parentRequestId}` while the `session.turn` request is still outstanding.
- Output / side effect: one `TURN_CANCELLED` terminal for the turn, one Stop reply `{state, accepted, persisted}`, and an interrupted canonical turn (`code=cancelled`).
- Steps:
  1. `_session_stop` — matches the owning turn. `_request_turn_stop` flags it as stopping, sets the `LocalWorkScope` stop, marks document candidates stopped and denies any pending approval. The turn task is then cancelled.
  2. Turn task — catches the cancellation. `_finish_turn_work` awaits document tasks and `scope.finish_stop()`, which sends SIGTERM then SIGKILL (0.5 s each) to bash process groups. `ChatSession` writes the interrupted state.
  3. Results — Stop waits for the turn to settle and returns its result. If the turn completed first, the completed state is returned. A repeated Stop replays the cached result.
  4. React — shows "Stopping…" until both replies arrive, keeping Restart and Shut down disabled meanwhile.
- State or ownership transitions: the accepted user text remains, completed tool and document effects remain, and the next send gets a new `turnId`.
- Error / retry / rollback behavior: if cleanup raises or the turn is still pending, `owner.error` is set and `_turn_active` stays true. New turns, selection, delete, project open and `runtime.shutdown` then return `BUSY_TURN`, and Retry Stop re-raises the cached error. Only a backend restart recovers (FAIL-022). Draining has no deadline (ASM-031).
- Invariants involved: INV-006, INV-027.
- Evidence: `app/agent/desktop/service.py::_session_turn` (finally block), `_session_stop`; `app/agent/ingest.py`; Stop tests in `test_desktop_document_service.py`; `answer_stream.test.ts` ("Stop waits for both replies…", "Stop failure remains blocked…").
- Confidence: Confirmed.

### Flow: Conversation rename and delete

- Trigger / input: the sidebar context menu offers Rename (saved conversations only) and Delete (after a scope confirmation).
- Output / side effect: rename rewrites the v3 JSON with `customTitle` and a new `updatedAt`. Delete unregisters the conversation from the catalog, then unlinks its JSON.
- Steps:
  1. Rename — checks idle gates and membership, strips the title to 1–256 bytes, calls `repository.rename` (turns unchanged). React updates the list only after the acknowledgement.
  2. Delete — React stops a running turn and waits for it to settle and for any `document.apply`. The service requires that no turn or project operation is active and loads the snapshot. If the conversation is selected, the session is shut down, which also resets Permission and control snapshots. Then `unregister_session`, then `repository.delete` (fingerprint precheck, unlink, directory fsync).
- State or ownership transitions: catalog membership and the file are removed. The project and its documents are untouched.
- Error / retry / rollback behavior:
  - A failed rename leaves the file unchanged.
  - A failed delete re-registers the conversation if its file remains.
  - A crash between unregister and unlink resurrects the conversation at the next reconcile.
  - There is no trash or undo.
  - Transient, never-saved conversations can be deleted but not renamed.
- Invariants involved: INV-006, INV-016, INV-023.
- Evidence: `service.py::_session_rename`, `_session_delete`; `conversations/repository.py::rename`, `delete`; `test_desktop_conversations.py::test_rename_survives_selection_restart_and_next_real_session_turn`, `test_delete_unlink_failure_restores_index_and_can_retry_without_changing_selection`.
- Confidence: Confirmed.

### Flow: Permission-gated side effects (Ask/Bypass)

- Trigger / input: an effectful operation, inside or outside a turn.
- Output / side effect: the operation runs, or the caller gets `APPROVAL_DENIED` or a denied ToolMessage.
- Steps:
  1. Mode — the service-wide mode changes only while idle. Each turn freezes it in `_active_turn_permission_mode` and `submittedContext.permissionMode`. Out-of-turn RPC mutators use the live mode.
  2. Gated operations — bash (exact command, checked inside the tool), `document.apply` and undo, `/init`, `/ingest`, `/prune --yes`, RPC `knowledge.ingest_file` and `prune_apply`, Citation save, `skill_install` preview and apply, and MCP calls outside family `desktop_document`. Not gated: manual `document.save`, `/sync`, `prune_preview`, `read_file`, RAG reads.
  3. Ask — sends `approval.required` with a bounded payload. One pending slot sits behind a lock. `approval.resolve` must match the approval, parent request and turn, be unexpired (default 60 s) and is single-use; Stop or the end of the turn denies. A parameter summary over 8 KiB, or text that looks secret, is denied with no prompt (FAIL-025).
  4. Bypass — approves immediately, with no event and no size or secret check. Extension apply approves every binding in the current preview, and the installer's `bypass_approval` skips update consent. Document version checks and `_validated_path` guards still apply.
- State or ownership transitions: approvals are process-local and never persisted.
- Error / retry / rollback behavior: a denial, expiry, event-delivery failure or handler error never executes the operation. An approved operation that later fails is not undone.
- Invariants involved: INV-004, INV-009, INV-018, INV-023, INV-024, INV-025.
- Evidence: `service.py::_single_operation_approval`, `_operation_approval`, `_desktop_operation_approval`, `_desktop_bash_approval`, `_extensions_apply`; `PolicyToolNode`; `test_project_permissions.py`; `app/desktop/tests/trust.test.ts`.
- Confidence: Confirmed.

### Flow: Slash and inline Skill invocation

- Trigger / input: `/<skill-name> <prompt>`, `/citation <prompt>`, an inline `@name` anywhere in the request, or the explicit installer path. Desktop completion offers names from `session.loadedSkills`; the CLI parses `@name` silently.
- Output / side effect: one turn run with a transient, possibly composite, runtime. Citation saves bundles; the installer applies a selected Skill for future sessions.
- Steps:
  1. Selection — the slash Skill comes first, then inline references. References must be exact catalog names with checked boundaries, and client-supplied references must equal the parsed list. A `skill-installer` entry makes the turn an installer turn.
  2. Loading — each Skill is hash-checked, its manifest validated and its required tools resolved. The Desktop validates before acceptance; in the CLI, a load failure after acceptance fails the turn.
  3. Composite — names and instructions are joined, effective tools unioned and `members` recorded. Document turns force `document_edit` into the tools, except turns that include a `READ_ONLY_DOCUMENT_SKILLS` Skill (`grill`), which remove it. Citation in the set forces Normal and a fresh registry.
  4. Cleanup — the runtime is cleared, the Citation registry torn down and the previous thinking mode restored.
- State or ownership transitions: no Skill selection survives the turn. Canonical metadata records the effective mode.
- Error / retry / rollback behavior: the Desktop rejects stale or removed references before acceptance. An exact completed replay returns before any loading. Retrying a failed or interrupted turn needs a currently valid runtime. A rejected runtime never grants tools.
- Invariants involved: INV-013, INV-019, INV-024.
- Evidence: `app/agent/skills/runtime.py::resolve_skill_references`, `combine_skill_runtimes`; `session.py::_run_one_shot_skill_turn`, `_run_installer_turn`; `test_inline_skills.py`; `test_citation_skill_activation.py`.
- Confidence: Confirmed.

### Flow: Citation search, verified save and rendering

- Trigger / input: `citation_workflow` calls during one Citation task, started by `/citation` or `@citation`.
- Output / side effect: numbered record blocks with abstract status; save-batch outcomes (12 statuses); bundles (`reference.bib`, `citation.json`) and registry receipts; rendered markers and a bibliography.
- Steps:
  1. Search — strict schema (query at most 2,048 characters, years 1000–2999, request at most 64 KiB). Crossref, DataCite and, when a key is set, OpenAlex run concurrently through a 15-minute cache and `fetch_with_retries`. A provider that failed transiently earlier in the task is skipped and reported as `<provider>:skipped(...)`.
  2. Merge — deduplicate by DOI, otherwise by provider id; the better rank wins and inherits a real abstract. With a year bound, only records with a known in-range year survive (undated records are dropped), then the list is cut to 10. Repeats within the task are marked, and a counts artifact (`candidate_count`, `abstract_count`, `new_candidate_count` and others) feeds `turn_trace`.
  3. Save resolution — an exact DOI fetches doi.org CSL, with no comparison to model-supplied fields. An arXiv ID goes to the authority path. A descriptive intent runs provider `search_work`, then `decide_resolution`, then a doi.org refetch that requires title similarity of at least 0.88.
  4. Plan and persist — sequential per item. Authority fallback runs only when allowed. doi.org BibTeX goes through strict pybtex (full month-name macros accepted) and DOI injection. `write_identity_bundle` takes a 5 s flock, stages the files, fsyncs and renames; then the receipt is recorded and `registry.register` called.
  5. Finalization — the gate checks `[[cite:...]]` markers against the registry. A violation replaces the draft with a safe message; otherwise markers are numbered and a bibliography appended before `complete_turn`.
- State or ownership transitions: abstracts are shown but not stored. Bundles survive the end of the task; the registry lasts one task.
- Error / retry / rollback behavior:
  - Transient kinds (`rate_limited`, `timeout`, `network_error`, `server_error`) are retried within budget, then reported. The budgets: 429 at most 2 times with Retry-After capped at 30 s; 5xx and transport errors at most 2; timeouts at most 1; backoff 1 s then 2 s, capped at 8 s, plus jitter.
  - Deterministic kinds are not retried.
  - When no provider answered, the tool says "Search failed…" rather than reporting zero records.
  - Save isolates an unexpected error to its item as `internal_error`, with a stage reason and the batch ID logged.
  - Cancellation propagates. Identity and storage conflicts fail closed.
  - Written bundles are never rolled back. A cancelled save's late writer may land a bundle that is never registered.
- Invariants involved: INV-010, INV-014, INV-019, INV-030.
- Evidence: `app/skills/citation/service.py`, `tool.py`, `resolution.py`, `providers/net.py`, `storage.py`, `bibtex_canonical.py`; `test_citation_hub.py`; `test_citation_save_isolation.py`; `test_citation_doi_first_save.py`; `test_citation_workflow_tool.py`; `test_citation_e2e.py`.
- Confidence: Confirmed source and test definitions; no live provider call this pass.

### Flow: Web Search MCP discovery and call

- Trigger / input: session startup (discovery), then each model call to a web_search tool.
- Output / side effect: the tool list. Each call returns a text result: an engine line, candidate blocks with link-resolution lines and per-attempt read facts, and read statistics. Side effects are MCP stderr log lines and short-lived Chromium processes.
- Steps:
  1. Discovery — `_spec_to_connection` prepares the stderr log (rotating at 5 MiB or more, with a header). `_bounded_web_search(discover, min(15000, DEFAULT_TIMEOUT))` spawns the child with the SDK default environment, the five forwarded settings and a call-id marker. It then initializes, lists tools and closes.
  2. Call — the interceptor runs `_bounded_web_search(execute, DEFAULT_TIMEOUT)` in a new process: initialize, `call_tool` with the work budget in `_meta`, publish the result, close stdin. The SDK then waits, sends SIGTERM, then SIGKILL. A 20 ms `/proc` observer records owned descendants and kills them at the kill deadline.
  3. Node server —
     - Creates a `CallBudget` and opens the Google results page through `BrowserPool.withPage`: full Chromium, normal UA, `hl` chosen by whether the query contains Han characters.
     - Parses result links, admits candidates up to the limit, and resolves Google redirect wrappers by navigation (at most 6 s each).
     - Reads each page over HTTP first, with charset decoding and a 10 MiB cap. On failure it falls back to the browser with a bounded wait for client-rendered text.
     - Converts the whole body to Markdown and truncates without breaking links, then formats the output and the statistics scope.
- State or ownership transitions: only the stderr log persists. Each call owns its own browser.
- Error / retry / rollback behavior:
  - A Google 4xx or `/sorry/` redirect becomes an engine error, with no retry or bypass.
  - A response arriving after the work deadline becomes a plain `TimeoutError` naming `DEFAULT_TIMEOUT`.
  - Caller cancellation cancels the call and settles it.
  - A published result survives a cleanup failure.
  - Load failures become diagnostics with leaf causes and the log path.
  - Graph-level tool errors become ToolMessages.
- Invariants involved: INV-020, INV-028, INV-030, INV-031.
- Evidence: `app/agent/mcp.py`; `app/vendor/web-search-mcp/src/{index,search-engine,browser-pool,enhanced-content-extractor,utils}.ts`; `test_mcp.py`; vendored `tests/*.mjs`; F7-S2 and F7-S4 records in the plan build log.
- Confidence: Confirmed source; live Google behavior Unknown.

### Flow: RAG ingest, retrieval, sync and prune

- Trigger / input: CLI or Desktop composer `/init`, `/ingest`, `/sync`, `/prune`; `rag.cli.ingest`; direct retrieval or RPC knowledge methods.
- Output / side effect: `folder_meta.json`, `raw.json`, Chroma vectors, retrieval DTOs, and deletion of root-scoped orphan PIDs.
- Steps:
  1. `ingest_repo` — resolves the canonical root and namespace. `collect_folders` applies skip names and relative exclusions (`/init` excludes the top-level `app/`).
  2. Tagging — `_tag_folders` calls OpenRouter in parallel (4 workers). `folder_meta.json` is merged and rewritten directly, before any chunk is written.
  3. Chunks — inside `json_store.deferred_save()`, each folder's `delete_many` and `add` hit Chroma immediately, while `raw.json` is written once when the batch exits. `check_cancelled` is polled between steps.
  4. Retrieval — `search` embeds the query with Ollama and queries Chroma, oversampling 3×k when `folder_prefix` is set. `list_chunks` and `get_context` read raw JSON; `explore` reads folder metadata.
  5. Sync and prune — `list_diff` compares path presence only and applies no exclusions; prune deletes orphans from Chroma and raw JSON.
- State or ownership transitions: source files stay outside the store; derived chunks are owned by the store across three surfaces.
- Error / retry / rollback behavior:
  - A hard tagger failure aborts before metadata or chunks are written.
  - A malformed `folder_meta.json` read falls back to `{}`.
  - A Chroma failure leaves partial vectors while raw JSON rolls back its batch. Stop has the same effect: the JSON batch is discarded and Chroma keeps its partial writes.
  - Rerunning ingest is the documented recovery.
  - The FAIL-001 and FAIL-002 stale-state bugs persist.
- Invariants involved: INV-003, INV-007, INV-008, INV-012, INV-018.
- Evidence: `app/rag/cli/ingest.py`, `rag/api.py`, `rag/sync.py`, `rag/store/*`, `app/agent/ingest.py`; `tests/rag/*`; `test_ingest.py`.
- Confidence: Confirmed.

### Flow: Drop-in extension apply and ZIP installation

- Trigger / input: drop-in Skill or MCP folders plus `/Extension-Management` status, preview, apply and restart; or `/skill-installer install <ZIP>`, an explicit installer request, or inline `@skill-installer`.
- Output / side effect: managed copies, a new registry revision, and the Skill catalog and MCP specs of future sessions.
- Steps:
  1. Manager — discovery validates and hashes each drop-in. Preview compares desired state with the registry. Apply re-checks, requires binding approval, copies content-addressed bundles and atomically replaces the registry while holding the state-root flock.
  2. Desktop — runs apply as a prompt-first, display-only turn whose input is a sanitized digest, and requires an open project and a selected session. Under Ask it sends the user's explicit binding hashes; under Bypass it approves every binding in the current preview.
  3. Installer — binds the user's source intent, the ZIP hash and the candidate, and prepares bytes with the safe ZIP helper. Bytes are verified before staging, and preview and apply are scoped to the selected Skill. Bypass sets `bypass_approval`. Cleanup restores only staged sources that were never changed.
  4. Restart — loads only validated managed copies, and activation re-checks the applied hash.
- State or ownership transitions: an untrusted drop-in becomes an approved managed copy, then a runtime, but only in a new session.
- Error / retry / rollback behavior: a stale preview or changed source aborts the apply. A completed apply in the same turn replays without reapplying. An apply left pending by a crash becomes a non-retryable interrupted turn. Check-to-read races remain.
- Invariants involved: INV-009, INV-013, INV-018, INV-024.
- Evidence: focused diff of `app/agent/extensions/manager.py`; `service.py::_extensions_apply`; `test_project_permissions.py`; `test_extension_manager.py`. Other internals carry forward 2026-09-13 evidence at `a88d44d`.
- Confidence: Confirmed (focused).

### Flow: Desktop launch, backend startup, requests and shutdown

- Trigger / input: `python main.py`, then the React mount.
- Output / side effect: a release build when stale, the running binary, one Python child generation, correlated protocol traffic, and logs.
- Steps:
  1. Launcher — checks staleness, then builds with `npm run tauri build -- --no-bundle` (`tsc --noEmit && vite build`, then a cargo release build). Runs the binary with WSLg overrides when applicable. A build failure returns its exit code and launches nothing.
  2. React — registers the event listener. `initialize()` calls `backend_snapshot` and, if the backend is stopped with no child, calls `backend_start` once.
  3. Rust — validates Conda and the checkout, increments the generation, spawns the Python server and waits up to 15 s for `backend.ready`. It persists raw stderr with a generation header, and logs protocol rejections, fatal bridge errors and the exit status to the stderr log.
  4. Python server — revalidates the runtime and installs `desktop-backend.log` before bootstrap. It then emits ready and runs one task per request, with ordered events and one terminal result.
  5. Requests — there is no normal request deadline. React runs `runtime.diagnostics` once per generation, then shows the project chooser.
  6. Shutdown — `runtime.shutdown` must be acknowledged within 5 s and the child must exit within another 5 s, otherwise it is killed. Closing the window triggers shutdown. Restart is shutdown plus start, after which React reopens the project and conversation from its refs.
- State or ownership transitions: Rust owns the child, generation, pending map and snapshot. React owns its reducers and refs. Python owns sessions and stores.
- Error / retry / rollback behavior: a wrong Conda environment or checkout, or a start timeout, leaves the backend degraded; the environment errors are not retryable. A spawn failure reports a crash with the log directory. Malformed output, pipe closure or child exit fails the generation. A failed `initialize()` is not retried automatically; the user gets Retry start and Restart.
- Invariants involved: INV-001, INV-011, INV-015, INV-017, INV-020.
- Evidence: `main.py`; `app/desktop/src-tauri/src/backend.rs`; `app/desktop/src/backend.ts::initialize`; `app/agent/desktop/server.py`; Rust lifecycle tests; `backend.test.ts`.
- Confidence: Confirmed source; no release-binary run.

### Flow: Diagnostics, incidents and turn timing

- Trigger / input: entry-point startup, any handled exception, and each turn attempt.
- Output / side effect: `cli.log` or `desktop-backend.log` (mode 0600, 5 MiB with 3 backups), incident references in user-visible errors and transcripts, and `turn_trace` lines.
- Steps:
  1. `install_diagnostic_log(component)` — runs once per process. `agent`, `skills` and `rag` log at INFO, third-party loggers at WARNING. `RedactingFormatter` redacts credential patterns and environment secrets captured at install time. If the file cannot be opened, logging falls back to stderr.
  2. First handling layer — `attach_incident` assigns an 8-hex ID and logs the traceback; outer layers reuse the ID. Desktop `dispatch` appends the reference to exception-derived errors, except self-explanatory codes.
  3. `TurnTimingTrace` — logs turn, model and tool events with IDs, durations, hashes, counts and `output_chars`.
- State or ownership transitions: only log files are written; no content is persisted.
- Error / retry / rollback behavior: an unwritable log directory falls back to stderr. A Rust stderr-log write failure silently disables that generation's log.
- Invariants involved: INV-017, INV-028.
- Evidence: `app/agent/diagnostics.py`, `observability.py`, `graph.py::_tool_error_to_message`, `desktop/service.py::dispatch`; root README; `test_diagnostics.py`; `test_observability.py`.
- Confidence: Confirmed source; privacy gaps Inferred (INV-028).

## State and ownership transitions

| State | Owner while active | Transition | Durable destination |
|---|---|---|---|
| User/model turn | `ChatSession` and graph | Pending before execution, then completed, failed or interrupted | Canonical JSON (project history or CLI store) |
| Submitted context | React draft, then Python | Frozen at acceptance | `submittedContext` in the turn |
| Comment drafts and markers | React memory | Cleared on `turn.accepted` | None |
| Project binding | `DesktopService` | `workspace.select` open | `RESEARCH.md` block and history skeleton |
| Document text | User disk and Monaco | Save or apply with fingerprint checks | The document file |
| Document candidates and undo | `DocumentWorkspace` (memory) | Prepare, then apply, cancel or stop | None; lost on restart |
| Conversation membership and name | Catalog and repository | Registration after pending; rename; delete | `desktop-projects.json`; `customTitle` |
| Permission mode | `DesktopService` | Changed while idle; frozen per turn | Only `submittedContext.permissionMode` |
| RAG source file | User filesystem | Collect, tag, chunk, index | `raw.json`, Chroma, `folder_meta.json` |
| Citation record | Provider hub and task service | Verified save | Bundle plus the task registry |
| Extension drop-in | User drop-in root | Validate, approve, install, restart | Managed copy and registry |
| Web search browser | Per-call Node process | Launch, then close or kill | None (stderr log only) |
| Desktop child and request | Rust supervisor and `RequestContext` | Ordered events, then one result | Wire only |

## Error, retry, and recovery paths

- **Agent graph.** At most two empty-reply retries and one tool-free repair, then a deterministic fallback. OpenRouter retries 5xx and network errors at most twice inside the HTTP client. Tool errors become ToolMessages carrying an incident ID.
- **Extended thinking.**
  - Rewrite and configuration exceptions finalize as a completed answer containing the error text.
  - A raised aggregator or reviewer error fails the turn.
  - A proposer times out after 180 s.
  - Invalid aggregation or an unmet quorum uses the first successful candidate and records a diagnostic.
- **Conversations.** A failed transition falls back to interrupted on reload. Nothing replays automatically; retrying means an explicit retry with the same ID.
- **Desktop project and history.** Open fails closed. Nothing repairs, remaps or partially lists an unhealthy history (FAIL-026).
- **Documents.** A conflict never overwrites. Candidates are lost on restart.
- **Stop.** The turn settles to interrupted, or the service stays busy until a backend restart (FAIL-022).
- **Citation.** Transient failures are classified and retried within budget, and search skips a transiently failed provider for the rest of the task. Save isolates failures per item.
- **MCP and Web Search.** Discovery and calls are bounded, failures become diagnostics, and there is no fallback engine. Other MCP servers are unbounded.
- **RAG.** Rerun ingest. Stop and Chroma failures can leave the three stores diverged.
- **Desktop transport.** A transport fault fails the generation. There is no normal request deadline; the user restarts.
- **Approvals.** Everything defaults to denial; nothing is undone after an approved operation fails.

## Unverified flows

- Live OpenRouter, Google, Ollama and citation-provider paths; a release-binary launch; the PowerShell picker; native Monaco editing and IME.
- Several desktop instances sharing a history directory or documents.
- A Stop while the filesystem is stalled; Ctrl-C in the CLI, which binds no scope.
- Documents and transcripts near the 1 MiB submission limit or the 2 MiB line limit.
- Extended-mode `turn_trace` completeness: rewrite, aggregator, reviewer and repair calls are not traced, and candidate model sequences can collide.
