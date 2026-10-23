# Dangerous Assumptions

Freshness: revalidated 2026-10-23 at `3f9176a` by static inspection. RAG premises ASM-002, ASM-004, ASM-005, ASM-020 and ASM-021 rest on code that has not changed since `5a0fa7c`; their wording comes from earlier passes and was confirmed again at the named anchors. Nothing was executed or reproduced this pass. See [audit coverage](README.md#audit-coverage).

## Active dangerous assumptions

### ASM-001 — External model, embedding and provider services are available

- Assumption: the services each feature needs are reachable and compatible when it runs:
  - OpenRouter models: the main default `google/gemini-3.8-flash`, plus the thinking roles.
  - Ollama with bge-m3.
  - Citation providers, and Google for Web Search.
- Where relied on: chat, extended thinking, the extension preview explanation, folder tagging, ingest and search, Citation discovery and save, web_search.
- Failure if false: the affected turn, ingest, save or tool fails. There is no offline semantic fallback.
- Detection or mitigation:
  - OpenRouter: each HTTP attempt is capped at 600 s, with at most 2 retries for 5xx or network errors and no retry for timeout, 4xx or 429. Failed turns carry an incident reference.
  - Citation: providers report classified failures and use bounded retries; a provider that failed transiently is skipped for the rest of the task.
  - MCP and OpenAlex: MCP failures become diagnostics. OpenAlex runs only with `OPENALEX_API_KEY`, and its absence is not shown to the user.
  - Limits of this evidence: `llm_max_tokens=65_536` is a request setting, not proof the provider accepts it, and no test pins that value.
- Evidence: `app/agent/config.py`; `agent/llm/openrouter.py`; `skills/citation/providers/net.py`; `agent/mcp.py`; `test_openrouter_model.py::test_default_main_model_is_pinned`.
- Status: Active
- Confidence: Confirmed dependency; live availability Unknown.

### ASM-002 — Persistent RAG schema and embedding configuration remain compatible

- Assumption: existing unversioned `raw.json`, `folder_meta.json` and Chroma state use the expected schema and one stable embedding model.
- Where relied on: `RAGConfig`, cached Chroma clients, every retrieval and sync function.
- Failure if false: parse errors, stale or missing data, or semantically incompatible vectors.
- Detection or mitigation: a local rebuild is documented. There is no migration or version check, and Chroma cache keys omit the embedding model.
- Evidence: `app/rag/config.py`; `rag/store/cache.py::get_chroma_store`; `app/rag/README.md`.
- Status: Active
- Confidence: Confirmed assumption.

### ASM-003 — RAG writers are serialized and multi-store writes complete

- Assumption: no competing process or Stop interrupts the ordered writes to folder metadata, raw JSON and Chroma.
- Where relied on: `ingest_repo`, `DocumentStore`, `prune_orphans`.
- Failure if false: the three stores describe different, partial or stale corpora (FAIL-001, FAIL-002, FAIL-003).
- Detection or mitigation:
  - Raw JSON detects only mtime/size fingerprint changes and is replaced atomically.
  - `folder_meta.json` is rewritten directly, and a malformed read falls back to `{}`.
  - A Stop now deterministically discards the raw JSON batch while Chroma keeps its partial writes.
  - Rerunning ingest is the documented recovery.
- Evidence: `app/rag/cli/ingest.py`; `rag/store/document_store.py`; `rag/store/json_store.py::deferred_save`; `agent/ingest.py::LocalWorkScope`.
- Status: Active
- Confidence: Confirmed assumption.

### ASM-004 — RAG roots and implicit single-file IDs remain stable and unique

- Assumption: a repository stays at the same canonical path, sync and prune use that root, and default filename-stem PIDs do not collide.
- Where relied on: `source_namespace`, `scoped_source_id`, `ingest_single`, `list_diff`, `prune_orphans`.
- Failure if false: old namespaces remain orphaned, sync reports misleading deltas, or same-stem single files replace each other.
- Detection or mitigation: explicit roots and PIDs, plus rebuild and prune procedures. Root moves and collisions are not handled automatically.
- Evidence: `app/rag/utils/paths.py`; `rag/cli/ingest.py::ingest_single`; `rag/sync.py`.
- Status: Active
- Confidence: Confirmed assumption.

### ASM-005 — Presence-only sync is understood as not detecting edits

- Assumption: callers know that `list_diff` compares paths, not content hashes or mtimes.
- Where relied on: `/sync` and prune previews.
- Failure if false: changed files are mistaken for up-to-date indexed content.
- Detection or mitigation: explicit re-ingest of changed content; the module docstring documents the limitation.
- Evidence: `app/rag/sync.py::list_diff`.
- Status: Active
- Confidence: Confirmed assumption.

### ASM-006 — Indexed filenames and previews are safe to send to OpenRouter

- Assumption: collected folders contain no secrets in their names or first-line previews beyond what the skip and extension rules exclude.
- Where relied on: repository and folder tagging.
- Failure if false: sensitive source fragments leave the machine.
- Detection or mitigation: skip rules and user discipline. `collect.py` has no secret-name filter, unlike `read_file`'s denylist. The tagger keeps the SDK default retries (`MAX_RETRIES=10`) and timeout.
- Evidence: `app/rag/collect.py::_should_ingest`; `rag/cli/ingest.py::_tag_folders`; `rag/llm/openrouter.py`.
- Status: Active
- Confidence: Confirmed data boundary.

### ASM-010 — Tool-call IDs are unique, and later failure needs no rollback

- Assumption: tool-call IDs are non-empty and unique within an execution, and side effects stay acceptable when finalization, persistence or Stop interrupts the turn.
- Where relied on: `PolicyToolNode` message merge, trace grouping, `TurnTimingTrace._model_by_call`, every mutating tool.
- Failure if false: results are associated with the wrong call, or a failed or stopped turn leaves effects without a recorded explanation.
- Detection or mitigation: Stop deliberately keeps completed effects (root README). There is no duplicate-ID validation and no transaction.
- Evidence: `app/agent/tools/policy_node.py`; `agent/turns/trace.py`; `agent/observability.py`.
- Status: Active
- Confidence: Inferred risk from control flow.

### ASM-011 — Prose-only tool prohibitions are enough

- Assumption: telling the model not to use a bound tool is equivalent to the tool being unavailable.
- Where relied on: the academic-paper-writing restriction is gone; the successor is the desktop document turn. Its prompt and the `document_edit` description say never to use bash, yet bash stays bound, and under Bypass it runs without a prompt. The same prose-only pattern governs Web Search during Citation tasks (INV-030).
- Failure if false: the model edits project files with bash, outside the `DocumentWorkspace` version and conflict checks, or uses the prohibited tool for the task.
- Detection or mitigation: `turn_trace` records tool names, and Ask shows each bash command before it runs. Base tools stay globally available by design.
- Evidence: `app/agent/desktop/service.py` (`document_edit` description and document-turn prompt); `agent/tools/access.py`; `test_tool_access_matrix.py::test_skill_switch_does_not_change_bash_permission_mode`.
- Status: Active
- Confidence: Confirmed prose-versus-binding mismatch; impact Inferred.

### ASM-012 — Desktop runs from a valid source checkout, launch environment and aligned contract set

- Assumption: all of the following hold:
  - The release binary runs from the checkout it was built in; `CARGO_MANIFEST_DIR` is fixed at build time.
  - The Conda `app` interpreter is at `<CONDA_PREFIX>/bin/python`.
  - Python can read `app/desktop/protocol/v1`.
  - The hand-written validators stay synchronized: 13 snapshot shapes, copied in TypeScript and Rust.
  - The launching shell already has `npm`, the Rust toolchain and installed Desktop dependencies.
- Where relied on: every desktop start and protocol request; `main.py`.
- Failure if false:
  - A moved checkout gives `SOURCE_CHECKOUT_INVALID`, which the launcher's mtime check does not notice.
  - A wrong environment degrades startup; Retry start and Restart cannot fix it, because Rust reads its own process environment.
  - A message one language accepts and another rejects either kills the generation (Rust) or flips the UI to degraded (TypeScript).
- Detection or mitigation:
  - Strict Conda and checkout checks.
  - `main.py --rebuild` after moving the checkout.
  - Shared fixtures; they lack `workspace.select` and `submittedContext` cases.
  - Source-only README guidance; bundling is disabled.
- Evidence: `main.py::_release_is_current`; `backend.rs::source_conda_launch`; `app/agent/desktop/protocol.py`; `protocol.test.ts` ("language-neutral manifest matches TypeScript constants"); Rust `manifest_matches_rust_constants`.
- Status: Active
- Confidence: Confirmed source-checkout dependency; moved-checkout failure Inferred (untested).

### ASM-013 — Other MCP servers and extended-thinking stages terminate promptly

- Assumption: GitHub and drop-in MCP `get_tools()` calls and every extended-thinking provider call return or raise within acceptable time.
- Where relied on: session creation (`load_mcp_tools_with_families` loads servers sequentially) and extended turns.
- Failure if false: session creation hangs on a stuck non-web_search server (plan exclusion X10), or an extended turn waits up to the 600 s HTTP cap per attempt.
- Detection or mitigation:
  - web_search discovery is capped at min(15 s, `DEFAULT_TIMEOUT`).
  - Proposers have a 180 s timeout.
  - All roles use the bounded OpenRouter client, and every stage is async and can be cancelled by Stop.
  - A raised aggregator or reviewer error fails the turn rather than hanging.
- Evidence: `app/agent/mcp.py::load_mcp_tools_with_families`; `agent/thinking/orchestrator.py`; `test_mcp.py::test_web_search_startup_is_capped_without_blocking_other_servers`; `test_thinking_session.py::test_extended_model_wait_cancels_and_persists_interrupted`.
- Status: Active
- Confidence: Confirmed missing bound for non-web_search MCP; thinking hang Inferred.

### ASM-016 — One desktop backend uses a history directory at a time

- Assumption: no second desktop process registers, renames or deletes conversations in the same `<historyDirectory>/desktop-projects.json`, or rewrites the same `RESEARCH.md`.
- Where relied on: `DesktopProjectCatalog.register_session` and `unregister_session`, `initialize_project`. Each reads a snapshot and atomically replaces the file without a lock.
- Failure if false: a lost update. A lost registration self-heals at the next open or `session.list`, because the catalog reconciles from JSON. A stale writer that re-registers a deleted ID instead makes the next open fail with "catalog references missing conversations".
- Detection or mitigation: reconcile on every open and list. Tauri has no single-instance plugin, and nothing prevents launching two apps.
- Evidence: `app/agent/desktop/catalog.py::load_project_catalog`, `register_session`, `reconcile_conversations`; `app/desktop/src-tauri/Cargo.toml`.
- Status: Active
- Confidence: Confirmed write ordering; no multiprocess reproduction.

### ASM-018 — Production launches never carry the fixture gates

- Assumption: normal users never launch with exact `RESEARCH_AGENT_DESKTOP_FIXTURE=phase02` and a valid owned fixture root.
- Where relied on: `agent.desktop.server._build_runtime_service`, which selects the fake service only for that exact gate. The root must be a uid-owned direct child of `/tmp` named `research-agent-desktop-phase02-*`.
- Failure if false: the UI runs against deterministic fixture projects and providers instead of the real `ChatSession`.
- Detection or mitigation: strict root validation; allowlisted checkpoint names; recognizable fixture content. There is no build-time exclusion.
- Evidence: `app/agent/desktop/server.py`; `fixture_session.py::require_fixture_root`; `test_desktop_server.py::test_runtime_service_uses_production_for_unset_or_nonexact_fixture_gate`.
- Status: Active
- Confidence: Confirmed test seam and premise.

### ASM-019 — A live desktop request eventually returns, is stopped, or loses its transport

- Assumption: a normal backend request eventually produces a terminal result, is cancelled by Stop (turns only), exits, or closes its channel. Elapsed time alone is never treated as failure.
- Where relied on: `BackendSupervisor.request` uses `submit_request(..., None)` and has no absolute or inactivity deadline. `session.stop` has no deadline either.
- Failure if false: a deadlocked live child leaves a non-turn request, or a Stop that cannot settle, waiting forever. While a Stop is pending, Restart and Shut down are disabled, so closing the window (forced kill, at most about 15 s) is the only way out.
- Detection or mitigation: transport and process failures fail the generation, and startup and shutdown waits are bounded. There is no heartbeat.
- Evidence: `backend.rs::request`; Rust `progressing_request_can_outlive_the_prior_absolute_deadline`, `shutdown_bounds_an_in_flight_request`; `App.tsx::canRestart`, `canShutdown`.
- Status: Active
- Confidence: Confirmed liveness premise; an indefinite hang was not reproduced.

### ASM-020 — Workspace exclusions survive later sync scans

- Assumption: paths `/init` deliberately omits (especially the top-level `app/`) stay outside later `/sync` comparisons and prune previews of the same root.
- Where relied on: the documented no-argument `/init` followed by `/sync <host-root>`.
- Failure if false: `/sync` reports excluded application files as `missing_from_store`, hiding real drift.
- Detection or mitigation: none. `init_workspace` passes `skip_rel_paths={app}`, but `list_diff` has no exclusion parameter at all.
- Evidence: `app/agent/ingest.py::init_workspace`, `diff_folder`; `rag/sync.py::list_diff`; `test_ingest.py::test_init_workspace_uses_app_parent_as_host_root` covers only init.
- Status: Active
- Confidence: Inferred from mismatched call paths; not reproduced.

### ASM-021 — Three-times oversampling is enough for folder-prefix search

- Assumption: the global top `3 * k` semantic hits always contain the best `k` hits under the requested `folder_prefix`.
- Where relied on: `rag.search(query, k, folder_prefix=...)` and folder-scoped agent search.
- Failure if false: too few or zero scoped hits, even though matching chunks exist.
- Detection or mitigation: callers can broaden the search. The API does not report truncation.
- Evidence: `app/rag/api.py::search` (`retrieval_k = k * 3`).
- Status: Active
- Confidence: Inferred algorithmic limitation.

### ASM-022 — One process owns each canonical conversation file

- Assumption: two `ConversationRepository` instances never write the same conversation concurrently, and a second opener never recovers a turn that is still legitimately pending.
- Where relied on: prompt-first and terminal transitions, rename, delete, retry, and the v1/v2→v3 upgrade. Each verifies a fingerprint before `os.replace`, but no lock or compare-and-swap spans both steps.
- Failure if false: one writer overwrites the other's successful transition, or live pending work is converted to interrupted.
- Detection or mitigation: one session serializes its own turns, and one Rust supervisor owns one child per app. Conflicts that are visible before the precheck fail explicitly.
- Evidence: `app/agent/conversations/repository.py::save`; `session.py::_recover_interrupted_turn`, `_reload_and_recover`.
- Status: Active
- Confidence: Inferred race from write ordering; not reproduced.

### ASM-024 — Item-count limits never bind in local use

- Assumption: these limits are never reached: 4,096 turns per conversation, 4,096 conversation files per history directory, 4,096 sessions per catalog.
- Where relied on: canonical validation, `ConversationRepository.scan`, `load_project_catalog`, catalog registration.
- Failure if false:
  - The 4,097th turn fails before execution, surfacing as a misleading `PROTOCOL_INVALID` ("requested session mode or skill is invalid").
  - More than 4,096 files makes the project unopenable.
  - The 4,097th session cannot register.
- Detection or mitigation: explicit validation errors. There is no rollover or archive workflow, and no test covers these limits. Byte ceilings on answers or transcripts stay intentionally absent.
- Evidence: `app/agent/conversations/models.py::MAX_TURNS`, `MAX_CONVERSATION_FILES`; `repository.py::scan`; `desktop/catalog.py`.
- Status: Active
- Confidence: Confirmed limits; adequacy Unknown.

### ASM-025 — Structural renderer tests approximate native large-content behavior

- Assumption: three things transfer to the native WebKitGTK window: array-valued React children, the bounded root type scale, and the new editor and marker layout. Specifically, they must keep large content usable there.
- Where relied on: `SafeContent`, responsive CSS, Monaco (`DocumentEditor.tsx`), and `MessageBody` marker positioning (TreeWalker and ResizeObserver).
- Failure if false: excessive memory use, sluggishness, overflow, or poorly scaled text. The comment and editor fonts are fixed px (INV-021).
- Detection or mitigation: 140,000-child server-render regressions and CSS arithmetic checks. There is no native performance or layout run.
- Evidence: `app/desktop/src/SafeContent.tsx`, `styles.css`, `DocumentEditor.tsx`; `conversations.test.ts`; `styles.test.ts`.
- Status: Active
- Confidence: Source mitigation Confirmed; native behavior Unknown.

### ASM-026 — Native pickers have Windows interop and an existing start folder

- Assumption: `powershell.exe`, `wslpath` and `WSL_DISTRO_NAME` work, and the folder passed as the picker's start path exists.
- Where relied on: `pick_project` and `pick_document`, the only UI routes to choose a project or document (root README).
- Failure if false:
  - Nothing can be selected: there is no manual path entry and no picker timeout.
  - If the open project's folder has been moved or deleted, every chooser route passes that stale root. `showProjectChooser` resets the candidate to the current project root, and `run_windows_picker` fails ("The starting folder is unavailable") instead of falling back to `$HOME`. The deadlock lasts until restart.
- Detection or mitigation: `NATIVE_PICKER_FAILED` is retryable but repeats under the same conditions. Cancelling keeps the current draft and document.
- Evidence: `backend.rs::pick_project`, `run_windows_picker`; `App.tsx::chooseProject`, `showProjectChooser`; only Rust test `picker_maps_wsl_unc_without_changing_unicode_or_spaces` covers mapping.
- Status: Active
- Confidence: Confirmed code path; stale-folder dead end not reproduced.

### ASM-027 — Google keeps accepting automated full-Chromium searches with parseable markup

- Assumption: Google answers `/search` from Playwright full Chromium with a normal UA (AutomationControlled masked), and its result markup stays parseable (`#search`, `a:has(h3)`, snippet selectors).
- Where relied on: `app/vendor/web-search-mcp/src/search-engine.ts`, the only engine since `1bc3bf2`.
- Failure if false: HTTP 4xx or a `/sorry/` redirect becomes an engine error, and markup drift gives `zero_parsed` or empty snippets. There is no fallback engine; DuckDuckGo, Brave and Bing were removed after being blocked or useless from this machine.
- Detection or mitigation: honest engine lines with the HTTP status and final path. The user accepted Google-only and the UA choice (plan FU01–FU03 and the post-delivery decision).
- Evidence: vendored README; plan build log F7-S3 (4 public Google searches unblocked on 2026-10-22) and its post-delivery section; `tests/test-search-result-retention.mjs`.
- Status: Active
- Confidence: Low-to-medium. Short-run evidence only; stability at volume or over time is unverified.

### ASM-028 — Chromium gets a usable launch environment

- Assumption: all of the following hold for the Node child:
  - A short, writable `/tmp`; no `TMPDIR` is forwarded, and a long socket path makes Chromium crash with SIGTRAP.
  - Direct internet access; proxy variables are not forwarded.
  - Playwright Chromium 1181 is installed at the default `~/.cache/ms-playwright`.
  - `dist/` is built.
- Where relied on: `agent/mcp.py::_web_search_env` (five forwarded settings plus a call-id marker); `browser-pool.ts`.
- Failure if false: discovery still succeeds, since it launches no browser, but every search fails at browser launch (HTTP page reads can still work). Behind a proxy, DNS or 407 errors appear.
- Detection or mitigation: engine error text; README setup steps (`npx playwright install chromium`, `npm run build`). In the Claude Code sandbox `/tmp` is read-only, so real-Chromium checks must run outside it.
- Evidence: `app/agent/mcp.py`; vendored README; `test_mcp.py::test_web_search_passes_only_supported_settings_to_both_commands`; plan record OD1 survey.
- Status: Active
- Confidence: Confirmed design; high impact in restricted environments.

### ASM-029 — Per-call web search processes make in-process limits sufficient

- Assumption: the server's in-process `RateLimiter` (10 searches per minute), the page and HTTP concurrency limits (2 each) and the damaged-pool flag protect Google and the machine.
- Where relied on: `rate-limiter.ts`, `browser-pool.ts`, and decision D05 to keep per-call sessions.
- Failure if false: every call is a new process, so the limiter never trips across calls. Parallel tool calls spawn parallel Chromium instances and Google requests, each with about 0.3–0.4 s of process start cost.
- Detection or mitigation: recorded measurements and the decision in commits `b1e3d20` and `3da6a23`. Desktop prompts are serialized, but tool calls within one turn can run concurrently.
- Evidence: `app/agent/mcp.py` interceptor; vendored `src/rate-limiter.ts`; commit `b1e3d20` message.
- Status: Active
- Confidence: Confirmed.

### ASM-030 — Documents and submissions fit the protocol and storage limits

- Assumption: project documents stay small relative to two limits: 1 MiB for turn text plus `submittedContext`, and 2 MiB per protocol line.
- Where relied on: `checkSubmissionSize` (React); `validate_submitted_context` and the 1 MiB checks in `models.py` and `protocol.py`; document results.
- Failure if false:
  - The stored context keeps a full `sourceText` for the editor snapshot and each document reference, so total size is roughly document size × (references + 1). A 100 KB document allows about 9 comments, a 300 KB one about 2.
  - A conflict result carries about three copies, so documents of about 700 KB or more exceed the 2 MiB line and fail as `PROTOCOL_INVALID`.
  - Latest-ten context replays earlier snapshots. `sourceTextSameAs` deduplicates only within one prompt.
- Detection or mitigation: a friendly size error before sending. There is no cross-turn deduplication.
- Evidence: `app/agent/conversations/models.py::MAX_INPUT_BYTES`; `desktop/protocol.py`; `service.py::_model_reference_projection`; commit `2bfdb22`.
- Status: Active
- Confidence: Mechanism Confirmed; thresholds are arithmetic, not measured.

### ASM-031 — Stop drains promptly, and only a user Stop marks the turn stopped

- Assumption: synchronous work under `await_sync_work` and `run_local_work`, the persistence helpers and process-group shutdown all return promptly after Stop. Only the user's Stop sets the turn-wide stop flag.
- Where relied on: `agent/ingest.py::await_sync_work`, which calls `callbacks.request_stop()` on any `CancelledError`; `LocalWorkScope.finish_stop`; `service.py::_finish_turn_work`.
- Failure if false:
  - A stalled filesystem or uninterruptible worker keeps "Stopping…" forever; there is no drain deadline.
  - A process group that will not exit raises, which leaves the service busy (FAIL-022).
  - Any cancellation sets the shared flag, including a proposer `asyncio.wait_for` timeout during a tool call. Sibling candidates then hit `check_cancelled`, and the turn can end as if stopped without the user pressing Stop.
- Detection or mitigation: the UI shows Stopping and Retry Stop. No test covers candidate-timeout interplay.
- Evidence: `app/agent/ingest.py::await_sync_work`, `run_local_work`; `thinking/orchestrator.py` (proposer timeout); `test_ingest.py::test_stopped_ingest_waits_for_started_write_and_does_not_start_next_file`.
- Status: Active
- Confidence: Drain design Confirmed; the candidate-timeout effect is Inferred.

### ASM-032 — Project permission and the project root bound every agent file effect

- Assumption: Ask/Bypass and the opened project root cover everything the agent can read or change on disk.
- Where relied on: the root README's permission description and the document-turn prompt ("use absolute paths").
- Failure if false: several paths escape that boundary.
  - `read_file` passes through the consent hook but is never gated. It has no project-root containment, only a name denylist (`.ssh`, `.env*`, `id_rsa*`, names starting with credentials, token or secret; not `.netrc`, `.npmrc` or `*.pem`).
  - Bash runs with cwd `app/` and is root-contained only by prompt text.
  - RAG reads are ungated.
  - Bypass also skips the installer's update consent.
- Detection or mitigation: Ask shows bash commands. `_validated_path` guards knowledge mutations, and `DocumentWorkspace` guards document edits.
- Evidence: `app/agent/tools/read_file.py`; `tools/bash.py`; `desktop/service.py::_desktop_operation_approval`; `extensions/manager.py` (`bypass_approval`).
- Status: Active
- Confidence: Confirmed.

### ASM-033 — A project's canonical root path stays stable

- Assumption: a project folder is never moved or renamed after initialization.
- Where relied on: projectId = `p-` + sha256(canonical root)[:32] in `catalog.inspect_project`; ownership checks in `load_project_catalog`; `ConversationRepository.save` forbids changing projectId.
- Failure if false: after a move, existing history is foreign to the new projectId, and open fails with "explicit mapping is required". No mapping tool exists. Pre-project global Desktop conversations (projectId `local`) are likewise unreachable.
- Detection or mitigation: an explicit failure with no data change. Re-homing means manually editing the JSON `projectId`.
- Evidence: `app/agent/desktop/catalog.py`; `test_desktop_conversations.py::test_unknown_project_orphan_requires_mapping_without_changing_history`.
- Status: Active
- Confidence: Confirmed.

### ASM-034 — OpenRouter adapter internals stay compatible

- Assumption: the bounded client can keep replacing `ChatOpenRouter.client` with its own SDK client (SDK retries off, custom httpx clients) without breaking.
- Where relied on: `agent/llm/openrouter.py::bounded_sdk_client`, used by the main model, the thinking roles and the extension manager.
- Failure if false: a dependency bump silently restores SDK backoff windows (previously up to 25–60 minutes) or breaks model construction. `openrouter` is only a transitive dependency.
- Detection or mitigation: exact pin `langchain-openrouter==0.2.6`; `test_openrouter_model.py::test_real_chat_openrouter_accepts_factory_kwargs` and the retry tests that drive the real wrapper over a mock transport.
- Evidence: `app/pyproject.toml`; `agent/llm/openrouter.py`; commits `37a448c`, `ccb0c40`.
- Status: Active
- Confidence: Confirmed dependency on internals.

## Assumptions under investigation

### ASM-014 — Model prose truthfully reflects Citation save outcomes

- Assumption: the model describes saved, reused and failed items as the save batch reports them. There are 12 statuses, including `internal_error`, which is to be reported with its `batch_id`.
- Where relied on: the final Citation answer. The host intentionally does not rewrite model prose.
- Failure if false: prose claims success after a failed outcome, even though the artifact and telemetry are correct.
- Detection or mitigation: strict tool content and artifact; the SKILL.md retry-once and reporting rules; scripted-model journeys (all success, all failure, mixed, retry). The retry text in SKILL.md does not list every reason code.
- Evidence: `app/skills/citation/types.py::SaveItemStatus`; `SKILL.md`; `test_citation_e2e.py::test_save_reporting_reaches_model_history_and_cli`.
- Status: Under investigation
- Confidence: Inferred live-model risk; no live-model save evidence was found.

### ASM-015 — Desktop operation gates cover every unsafe overlap

- Assumption: the service flags reject every unsafe concurrent request the concurrent NDJSON server accepts. They cover turns, approval, workspace opening, project operation counts, session creation, the document apply and tool locks, knowledge and extensions.
- Where relied on: overlapping protocol requests. `knowledge.overview`, `list_chunks` and `get_context` remain ungated reads.
- Failure if false: stale results, RAG read/write races, or inconsistent session, document or extension state.
- Detection or mitigation: focused busy-state tests; frontend reducers disable overlapping actions. No provable hole was found statically, and there is no integrated stress test.
- Evidence: `app/agent/desktop/service.py::dispatch` and gate fields; `test_desktop_conversations.py::test_conversation_change_blocks_turn_during_read`; `test_desktop_service.py::test_session_create_is_single_flight_and_blocks_shutdown`.
- Status: Under investigation
- Confidence: Partially verified.

### ASM-035 — The model follows prompt-only Citation rules

- Assumption: during Citation tasks the model follows four prompt-only rules:
  - It avoids Web Search for papers (INV-030).
  - It searches again only for named gaps and stops when searches add nothing.
  - It describes only works with retrieved abstracts.
  - It ends with the searches run and the supported, unsupported and unassessable parts.
- Where relied on: `app/skills/citation/SKILL.md`; only repeat marking (`already returned earlier in this task`) and counts are enforced by the tool.
- Failure if false: unverified references from web results or memory reach the answer without markers, so the gate cannot catch them. This mixes the Citation-workflow and general-agent conditions the user's thesis compares.
- Detection or mitigation: `turn_trace` tool names and Citation counts; text-presence tests for the rules. The user decided to observe violations before adding harder limits (2026-10-20 decision U08).
- Evidence: `SKILL.md`; `test_citation_skill_activation.py::test_citation_runtime_keeps_the_web_search_boundary_once`; `test_citation_e2e.py::test_citation_follow_up_receives_stop_rules_and_repeat_signal`; natural-trace notes in commits `20f1092` and `7c97096`.
- Status: Under investigation
- Confidence: Unknown at scale. A few compliant natural traces are recorded; the 2026-10-19 web-only turn was caused by FAIL-028.

## Retired assumptions

### ASM-007 — Startup-only managed Skill verification

Retired: activation re-hashes each loaded Skill before reading files (INV-013, FAIL-005). The check-to-read race remains outside that guarantee. Evidence: `load_skill_runtime`; `test_runtime_rejects_applied_bundle_changed_after_startup`.

### ASM-008 — Process-local-only extension apply serialization

Retired: apply holds a Linux flock on the state-root `.apply.lock` from the revision re-read through registry publication (FAIL-006). Arbitrary writers and other stores are not covered. Evidence: `ExtensionManager.apply`; `test_extension_manager.py::test_cross_process_apply_preserves_successful_update`.

### ASM-009 — Search rank as proof for earliest-year ties

Retired: missing or tied years return ambiguity, and authority fallback preserves it (INV-014, FAIL-007). Evidence: `resolution.py::decide_resolution`; `CitationService._plan_item`.

### ASM-017 — Deferred catalog registration through flush

Retired: prompt-first canonical persistence registers the catalog only after the durable pending write (INV-006). Evidence: `test_desktop_conversations.py::test_first_prompt_registers_catalog_before_provider_failure`.

### ASM-023 — Legacy conversation staging

Retired with the importer. Old `chat_history` and Plan-log sources are not runtime inputs and are left untouched.
