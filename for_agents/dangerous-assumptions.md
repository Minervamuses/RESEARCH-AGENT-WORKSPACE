# Dangerous Assumptions

Freshness: 2026-09-13 source/contract/test-definition inspection at `a88d44d` covers extension integrity/locking, earliest-year resolution, save reporting, Desktop runtime policy, and resource limits; RAG search/prune anchors received a focused check. Other claims retain the 2026-09-05 (`9745fd1`) or unchanged Desktop 2026-09-06 (`743aaaf`) basis; historical probes were not rerun. See [audit coverage](README.md#audit-coverage).

## Active dangerous assumptions

### ASM-001 — External model and embedding services are available

- Assumption: Configured OpenRouter models, including the current main default `google/gemini-3.8-flash`, Ollama, bge-m3, and optional MCP/citation providers are reachable and compatible when their features run.
- Where relied on: chat, extended thinking, extension preview, folder tagging, ingest/search, web/GitHub tools, citation discovery.
- Failure if false: feature-specific startup/turn/ingest/save failure or missing tool family; no offline semantic fallback.
- Detection or mitigation: fail-fast checks, provider errors, MCP diagnostics, deterministic fake-provider tests, and an offline test of the main-model configuration value. The configured `llm_max_tokens=65_536` is a request setting, not evidence that the provider accepts or emits that many tokens. That test does not establish provider-side model availability.
- Evidence: README.md; `app/agent/config.py`; `app/agent/llm/openrouter.py`; `app/tests/test_openrouter_model.py`; app/agent/startup.py; app/rag/embedder/ollama.py.
- Status: Active
- Confidence: Confirmed dependency; live availability Unknown.

### ASM-002 — Persistent RAG schema and embedding configuration remain compatible

- Assumption: Existing unversioned raw.json/folder_meta.json/Chroma state uses the expected schema and one stable embedding model.
- Where relied on: RAGConfig, cached Chroma clients, all retrieval and sync functions.
- Failure if false: parse errors, stale/missing data, or semantically incompatible vectors.
- Detection or mitigation: local rebuild is documented; there is no migration/version check. Chroma cache keys omit embedding model.
- Evidence: app/rag/config.py; app/rag/store/cache.py; app/rag/README.md.
- Status: Active
- Confidence: Confirmed assumption.

### ASM-003 — RAG writers are serialized and multi-store writes complete

- Assumption: No competing process mutates folder metadata/raw JSON/Chroma during ingest or prune, and failures do not interrupt the ordered multi-store writes.
- Where relied on: ingest_repo, DocumentStore, prune_orphans.
- Failure if false: partial or stale corpus surfaces; see FAIL-001 through FAIL-003.
- Detection or mitigation: raw JSON detects only mtime/size fingerprint changes and replaces atomically. `folder_meta.json` is directly truncated and rewritten, and a read-time JSON/OSError fallback to `{}` can let a later write discard unrelated-root metadata. Rerun ingest is the documented recovery.
- Evidence: app/rag/cli/ingest.py; app/rag/store/document_store.py; app/rag/sync.py.
- Status: Active
- Confidence: Confirmed assumption.

### ASM-004 — RAG roots and implicit single-file IDs remain stable and unique

- Assumption: A repo stays at the same canonical absolute path, sync/prune uses that same root, and default filename-stem PIDs do not collide.
- Where relied on: source_namespace, scoped_source_id, ingest_single, list_diff/prune_orphans.
- Failure if false: old namespaces remain orphaned, sync gives misleading deltas, or same-stem single files replace each other.
- Detection or mitigation: explicit roots/PIDs and rebuild/prune procedures; no automated root-move/collision handling.
- Evidence: app/rag/utils/paths.py; app/rag/cli/ingest.py::ingest_single; app/rag/sync.py.
- Status: Active
- Confidence: Confirmed assumption.

### ASM-005 — Presence-only sync is understood as not detecting edits

- Assumption: Callers know list_diff compares paths, not content hashes or mtimes.
- Where relied on: /sync and prune previews.
- Failure if false: changed files can be mistaken for up-to-date indexed content.
- Detection or mitigation: explicit re-ingest of changed content; module docstring documents the limited primitive.
- Evidence: app/rag/sync.py.
- Status: Active
- Confidence: Confirmed assumption.

### ASM-006 — Indexed filenames and previews are safe to send to OpenRouter

- Assumption: Collected folders contain no secret material in names or first-line previews beyond simple skip/extension policy.
- Where relied on: repo/folder tagging.
- Failure if false: sensitive source fragments leave the local machine.
- Detection or mitigation: skip rules and user discipline; README explicitly warns not to rely on extensions as the only protection.
- Evidence: app/rag/collect.py; app/rag/cli/ingest.py::_tag_folders; README.md.
- Status: Active
- Confidence: Confirmed data boundary.

### ASM-010 — Tool call IDs are unique and later failure needs no rollback

- Assumption: Tool-call IDs are non-empty/unique within an execution, and side effects remain acceptable if finalization or persistence later fails.
- Where relied on: PolicyToolNode merge, trace grouping, all mutating tools.
- Failure if false: result association can overwrite/merge incorrectly, or a failed turn leaves side effects without a recorded explanation.
- Detection or mitigation: candidate IDs isolate extended traces; no general duplicate-ID validation or transaction rollback exists.
- Evidence: app/agent/tools/policy_node.py; app/agent/turns/trace.py; app/agent/thinking/trace.py.
- Status: Active
- Confidence: Inferred risk from current control flow.

### ASM-011 — Instruction-level tool prohibitions are sufficient

- Assumption: A Skill instruction saying not to use bash is equivalent to enforced unavailability.
- Where relied on: README description of academic-paper-writing.
- Failure if false: the model can still call globally bound bash under its configured runtime permission policy (Desktop can explicitly bypass individual prompts).
- Detection or mitigation: runtime availability block exposes the true set; resolve_tool_access keeps base tools global.
- Evidence: README.md; app/agent/tools/access.py; test_tool_access_matrix.py::test_skill_switch_does_not_change_bash_permission_mode.
- Status: Active
- Confidence: Confirmed documentation/runtime mismatch.

### ASM-012 — Desktop remains a valid source checkout, launch environment, and aligned contract set

- Assumption: Rust can derive the repository/app roots from its Cargo manifest, the Conda `app` interpreter remains at `<CONDA_PREFIX>/bin/python`, Python can read `app/desktop/protocol/v1`, and the manually maintained Python/TypeScript/Rust validators remain synchronized. When root `main.py` is used, the caller already has `npm` on `PATH` and installed Desktop dependencies; the launcher does not activate or validate Conda itself.
- Where relied on: every supported desktop startup and protocol request.
- Failure if false: startup degrades, installed-wheel/relocated-binary use fails, or one language rejects/accepts a shape differently.
- Detection or mitigation: strict source/Conda checks, shared contract/fixtures, three-language tests, and explicit source-only README guidance. `pyproject.toml` still does not package the desktop contract and Tauri bundling is disabled.
- Evidence: root `main.py`; `app/desktop/src-tauri/src/backend.rs::source_conda_launch`; `app/agent/desktop/protocol.py`; protocol fixtures; manifests.
- Status: Active
- Confidence: Confirmed source-checkout dependency; any packaged topology Unknown.

### ASM-013 — MCP and extended-thinking stages terminate promptly

- Assumption: MCP get_tools and aggregator/reviewer/reviser provider calls return or raise within acceptable time.
- Where relied on: session startup and extended turns.
- Failure if false: session creation or a turn can hang/bypass finalization.
- Detection or mitigation: proposer candidates have timeouts; MCP startup and later thinking stages lack consistent explicit containment.
- Evidence: app/agent/mcp.py; app/agent/thinking/orchestrator.py.
- Status: Active
- Confidence: Inferred from missing timeout/exception boundaries.

### ASM-016 — Only one desktop backend mutates the project catalog

- Assumption: separate desktop application processes do not register conversations concurrently against the same `desktop-projects.json`.
- Where relied on: `DesktopProjectCatalog.register_session` reads an in-memory snapshot and atomically replaces the file without an interprocess lock or compare-and-swap.
- Failure if false: two successful registrations derived from the same snapshot can overwrite one another, leaving a saved conversation absent from the sidebar.
- Detection or mitigation: one Rust supervisor serializes one child inside one application; catalog reload/status can reveal missing membership. No cross-process guard exists.
- Evidence: `app/agent/desktop/catalog.py`; `app/desktop/src-tauri/src/backend.rs`.
- Status: Active
- Confidence: Confirmed assumption from write ordering; no multiprocessing reproduction run.

### ASM-018 — Production launches do not carry exact fixture-only gates

- Assumption: normal users do not launch Tauri with exact `RESEARCH_AGENT_DESKTOP_FIXTURE=phase02`, a valid owned fixture root, or its crash-checkpoint environment values.
- Where relied on: `agent.desktop.server._build_runtime_service` selects the isolated fake service only from the exact primary gate; `fixture_session.py` additionally requires exact checkpoint and turn fields before crash instrumentation.
- Failure if false: the UI starts against deterministic canonical fixture conversations/providers instead of the real `ChatSession`, or a checkpoint could intentionally block the fixture child.
- Detection or mitigation: fixture-root validation is strict, checkpoint names/turn IDs are allowlisted, and diagnostics/content are recognizable. The fixture does not open or import legacy conversation sources. There is no separate build-time exclusion.
- Evidence: `app/agent/desktop/server.py`; `app/agent/desktop/fixture_session.py`; test_desktop_fixture.py; test_desktop_crash_recovery.py.
- Status: Active
- Confidence: Confirmed test seam and premise.

### ASM-019 — A live desktop request eventually returns or loses its transport

- Assumption: a normal Python backend request eventually produces a terminal result, exits, or closes its protocol channel; elapsed runtime alone is not treated as failure.
- Where relied on: `BackendSupervisor.request` calls `submit_request(..., None)` and waits on the response channel without an absolute or inactivity deadline.
- Failure if false: a live but deadlocked/non-responsive child can leave the request waiting indefinitely until the user explicitly shuts down or restarts the backend.
- Detection or mitigation: process/pipe/protocol failures fail the generation, startup and shutdown remain bounded, and shutdown can fail an in-flight request. There is no automatic heartbeat/inactivity detector.
- Evidence: `app/desktop/src-tauri/src/backend.rs::request`; `progressing_request_can_outlive_the_prior_absolute_deadline`; `shutdown_bounds_an_in_flight_request`; commit `45d446d`.
- Status: Active
- Confidence: Confirmed current liveness premise; an actual indefinite hang was not reproduced.

### ASM-020 — Workspace exclusions survive later sync scans

- Assumption: paths intentionally omitted by `/init`, especially the top-level `app/` directory, remain outside later `/sync` comparison and prune previews for the same host root.
- Where relied on: the documented no-argument `/init` followed by `/sync <host-root>` for the returned host root.
- Failure if false: `/sync` can report intentionally excluded application files as `missing_from_store`, obscuring real drift and inviting unnecessary ingestion.
- Detection or mitigation: none in the current API boundary; `init_workspace` passes `skip_rel_paths={app}` to ingest, while `diff_folder` calls `list_diff` without the same exclusion. Prune still requires confirmation and only deletes stored paths missing from disk.
- Evidence: `app/agent/ingest.py::init_workspace`; `app/agent/ingest.py::diff_folder`; `app/rag/sync.py::list_diff`.
- Status: Active
- Confidence: Inferred from the mismatched call paths; no end-to-end reproduction was run.

### ASM-021 — Three-times oversampling is enough for folder-prefix search

- Assumption: retrieving the global top `3 * k` semantic hits before applying `folder_prefix` always contains the desired prefix-scoped top `k`.
- Where relied on: `rag.search(query, k, folder_prefix=...)` and Agent search scoped to a folder.
- Failure if false: the API returns too few or zero scoped hits even though relevant matching chunks rank below unrelated global hits.
- Detection or mitigation: callers can broaden or retry, but the API does not report truncation and no completeness regression covers this ranking shape.
- Evidence: `app/rag/api.py::search`.
- Status: Active
- Confidence: Inferred algorithmic limitation; no live embedding reproduction was run.

### ASM-022 — One process owns each canonical conversation file

- Assumption: two `ConversationRepository` instances do not write the same conversation concurrently, and a second session does not recover a legitimately active pending turn.
- Where relied on: prompt-first and terminal conversation transitions. Each writer verifies a content fingerprint before `os.replace`, but there is no interprocess lock or atomic filesystem compare-and-swap spanning both operations.
- Failure if false: both writers can pass the precheck and one can overwrite a successful transition; a second opener can convert live pending work to interrupted.
- Detection or mitigation: one session serializes its own turns and Rust owns one child per Desktop process. Conflicts visible before the precheck fail explicitly; no multiprocessing/lease test covers the race window.
- Evidence: `app/agent/conversations/repository.py::save`; `app/agent/session.py::_recover_interrupted_turn`.
- Status: Active
- Confidence: Inferred cross-process race from the write ordering; not reproduced.

### ASM-024 — Canonical turn-count and catalog scan limits need no rollover path

- Assumption: 4,096 turns per conversation and a 4,096-file catalog scan are sufficient for local use, or users can manually start/manage another conversation when either item-count limit is reached.
- Where relied on: canonical turn-list validation and sidebar scanning.
- Failure if false: a later prompt fails before provider execution or additional files are omitted from the bounded scan; there is no automatic rollover/archival workflow.
- Detection or mitigation: validators fail before accepting a prompt beyond the turn-count bound and scan results include a limit issue. The former 8 MiB canonical-document limit is retired and must not be replaced with another arbitrary answer/document/wire/transcript byte ceiling.
- Evidence: `app/agent/conversations/models.py::MAX_TURNS`; `MAX_CONVERSATION_FILES`; `app/agent/conversations/repository.py::scan`.
- Status: Active
- Confidence: Confirmed item-count limits; adequacy for real long-lived stores Unknown.

### ASM-025 — Structural renderer tests approximate native large-content behavior

- Assumption: avoiding variadic React children is sufficient for useful rendering of extremely large Markdown in the native WebView, and the bounded root typography scale remains visually usable across platform DPI and fullscreen states.
- Where relied on: `SafeContent` presentation and responsive Desktop CSS.
- Failure if false: JavaScript no longer throws on argument count, but the native UI can still consume excessive memory, become sluggish, overflow, or look poorly scaled.
- Detection or mitigation: array-valued child construction, 140,000-child server-render regressions, CSS arithmetic checks, and pre-maintenance headless-Chrome observations. No product content ceiling or native-WebKit performance/layout claim is made.
- Evidence: `app/desktop/src/SafeContent.tsx`; `app/desktop/tests/conversations.test.ts`; `app/desktop/src/styles.css`; `app/desktop/tests/styles.test.ts`.
- Status: Active
- Confidence: Source mitigation Confirmed; native resource and visual behavior Unknown.

## Assumptions under investigation

### ASM-014 — Model prose truthfully reflects citation save outcomes

- Assumption: The model follows the Skill and model-visible SaveBatchOutcome when describing saved/reused/failed items.
- Where relied on: final citation response; host intentionally does not replace model prose.
- Failure if false: user-facing prose can claim success after a failed tool outcome even though artifact/telemetry is correct.
- Detection or mitigation: strict tool content/artifact and existing deterministic tests; the accepted scoped characterization now includes strict 11-status tool content/artifact coverage and real-graph fake-model journeys for all-success, all-failure, mixed and retry-success. No independent status-rendering layer was required.
- Evidence: [historical Issue 05](https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/bc2c94d40562e9606a9872bc922a36423b6a10a2/issue/05-citation-save-result-reporting.md); app/skills/citation/tool.py; app/agent/session.py.
- Status: Under investigation
- Confidence: Inferred live-model risk, not a reproduced current incident. Current test definitions and archived Issue05/final-check evidence close the bounded characterization task; they do not guarantee arbitrary model prose. Freshness: 2026-09-13 source/archived evidence at `a88d44d` / `bc2c94d`.

### ASM-015 — Desktop operation gates cover every unsafe overlap

- Assumption: the service's turn, knowledge-mutation, extension, create, and shutdown flags reject every unsafe concurrent request accepted by the concurrent NDJSON server.
- Where relied on: overlapping protocol requests; some read-only knowledge methods do not take the mutation context manager, and guards are process-local booleans on one event loop.
- Failure if false: stale results, RAG read/write races, inconsistent extension/session state, or misleading busy status.
- Detection or mitigation: focused busy/approval/shutdown tests cover major intersections; frontend reducers also disable overlapping user actions. No integrated stress test covers all raw-protocol combinations.
- Evidence: `app/agent/desktop/server.py`; `app/agent/desktop/service.py`; desktop service tests.
- Status: Under investigation
- Confidence: Partially verified; complete intersection safety Unknown.

## Retired assumptions

### ASM-007 — Startup-only managed Skill verification retired

The old premise that startup verification alone protects later activation is retired. Startup now carries `applied_source_hash` and `load_skill_runtime` checks the full bundle before loading; changed instructions/manifest/resources are rejected. A writer changing content between the check and subsequent reads remains outside this precheck guarantee (INV-013, FAIL-005). Evidence: runtime/startup source and `test_runtime_rejects_applied_bundle_changed_after_startup`; Confirmed source at `a88d44d`, no fresh runtime probe. Status: Retired startup-only premise.

### ASM-008 — Process-local-only extension apply serialization retired

`ExtensionManager.apply` retains the in-process guard and adds Linux nonblocking flock on the state-root `.apply.lock` inode, spanning revision reread through registry publication. Cooperating callers receive busy or stale-preview errors. Current multiprocessing tests cover lost-update prevention, fsync lifetime, crash/exception release and separate roots. This assumes a stable cooperating local filesystem; arbitrary writers and other stores are not locked. Evidence: manager source / `test_extension_manager.py` definitions at `a88d44d`; FAIL-006 mitigated. Status: Retired process-local-only premise.

### ASM-009 — Search ranking as proof of earliest-year ties retired

The resolver now reports missing/tied-year ambiguity instead of using rank/relevance; authority fallback preserves that decision. It still chooses a unique minimum known year even with undated alternatives, as `test_earliest_unique_known_minimum_survives_later_ties_and_unknown_years` explicitly asserts. This establishes the accepted year-only rule, not globally proven chronology or sub-year ordering. Evidence: `resolution.py::decide_resolution`, `service.py::save` and tests at `a88d44d`; INV-014 / FAIL-007. Status: Retired tie-ranking premise.

### ASM-017 — Deferred catalog registration through flush is no longer assumed

Canonical JSON is the sole active transcript authority and `ConversationRepository` is its sole writer. Accepted prompts become pending before provider/tool execution, terminal state precedes success exposure, and restart converts leftover pending work to interrupted without automatic replay. Repository, lifecycle, Desktop restart, and subprocess crash-boundary tests cover this offline ordering.

### ASM-023 — Legacy conversation staging is no longer a runtime assumption

- The former assumption covered the resource cost of recursively cloning legacy conversation Chroma for import. The importer and its staging clone have been removed; old `chat_history` and Plan-log sources are now left untouched and are not runtime inputs.

- Repository line endings no longer depend on global Git defaults; `.gitattributes` and commit `3ac4f8b` own the LF policy. The resolved issue record has been removed.
- Separate citation/tool quotas no longer need to align with a smaller graph recursion constant; one `AgentConfig` graph fuse with early finalization governs the current graph. The resolved issue record has been removed; `note/20260820/agent_loop_guardrail_consolidation.md` retains the decision evidence.
- Generic Skill task-mode/persistent-selection assumptions are retired: `task_modes` is rejected and `/skill` unregistered. Citation also runs once through its dedicated CLI/Desktop command. Installer pending clarification is a separately bounded host scope (INV-019, INV-024).
- The former assumption that every Desktop request must finish within 600 seconds is retired. Current Rust code has no normal absolute request deadline; only startup/shutdown and actual transport/process failure paths remain bounded.
