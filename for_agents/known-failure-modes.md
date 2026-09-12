# Known Failure Modes

Freshness: 2026-09-13 source/contract/test-definition inspection at `a88d44d` covers mitigated extension/earliest/Citation failures, stale Skill documentation, and current frontend reconciliation. Other claims retain the 2026-09-05 (`9745fd1`) or unchanged Desktop 2026-09-06 (`743aaaf`) basis; historical probes were not rerun. See [audit coverage](README.md#audit-coverage).

## Active failure modes

### FAIL-001 — Prune leaves stale folder inventory

- Symptom: explore() still lists a folder after prune removed its last indexed file.
- Trigger / preconditions: repo-ingested folder becomes empty on disk and prune_orphans deletes its orphan PID.
- Affected components or users: RAG inventory and any agent/UI using rag_explore.
- Root cause: Confirmed — prune_orphans deletes Chroma/raw entries but never updates folder_meta.json.
- Current handling / recovery: re-ingest/rebuild the root or manually rebuild generated store metadata.
- Reproduction or detection: focused offline probe observed folders_before=[docs] and folders_after=[docs] after one PID was pruned.
- Related invariants / assumptions: INV-012, ASM-003.
- Evidence: app/rag/sync.py::prune_orphans; app/rag/api.py::explore.
- Status: Active

### FAIL-002 — Empty or unreadable re-ingest retains old chunks

- Symptom: ingest reports zero files/chunks, but earlier chunks for that path remain listable/searchable.
- Trigger / preconditions: a previously repo-indexed file becomes empty, non-UTF-8, or permission-denied and the same root is re-ingested.
- Affected components or users: RAG search/context and research answers using stale source text.
- Root cause: Confirmed — only files producing docs enter folder_pids, so the folder-level delete excludes the prior PID.
- Current handling / recovery: delete/prune the old source or rebuild the local store; normal re-ingest is insufficient for this case.
- Reproduction or detection: focused offline probe re-ingested an emptied file, received (0, 0), and observed prior chunks still present.
- Related invariants / assumptions: INV-012, ASM-003.
- Evidence: app/rag/cli/ingest.py::ingest_repo.
- Status: Active

### FAIL-003 — RAG multi-store writes can diverge

- Symptom: folder inventory, raw JSON, and Chroma can describe different partial states after an ingest/prune error.
- Trigger / preconditions: Chroma/Ollama/filesystem failure after folder metadata or some Chroma mutations but before deferred raw JSON commit.
- Affected components or users: semantic search versus list/context/explore results.
- Root cause: Confirmed — the three stores are updated in order without one transaction; JSON-before-Chroma operations can also fail between writes. `ingest_repo` directly truncates/rewrites folder_meta.json and treats a JSON decode or OS read failure as an empty mapping before the next write. Only raw.json uses atomic replacement, with mtime/size conflict detection.
- Current handling / recovery: error propagates; rerun the idempotent ingest, or back up/move the generated store and rebuild. If a malformed/unreadable folder metadata read preceded a write, re-ingest any unrelated roots whose inventory was discarded.
- Reproduction or detection: code-defined failure semantics; raw JSON rollback tests exist, but no cross-store failure-injection test.
- Related invariants / assumptions: INV-008, INV-012, ASM-002, ASM-003.
- Evidence: app/rag/cli/ingest.py; app/rag/store/document_store.py; app/rag/store/json_store.py::deferred_save.
- Status: Active

### FAIL-013 — Raw desktop folder-ingest methods are declared but disabled

- Symptom: direct protocol calls to `knowledge.init_workspace` or `knowledge.ingest_folder` return `RAG_WRITE_FAILED` even though the GUI can run `/init` and directory `/ingest` through the composer.
- Trigger / preconditions: a client uses the raw protocol mutation method instead of `session.turn` with the canonical slash command.
- Affected components or users: alternate protocol clients and future desktop refactors; the current React UI uses the supported composer route.
- Root cause: Confirmed — the direct handlers deliberately raise until they have structured progress, while `_execute_desktop_knowledge_command` invokes the existing Python ingest operations.
- Current handling / recovery: send `/init` or `/ingest <absolute-directory>` through the selected conversation. Do not add a second frontend-owned knowledge path.
- Reproduction or detection: inspect/dispatch the two direct methods; composer routing tests cover the supported path.
- Related invariants / assumptions: INV-015, INV-018.
- Evidence: `app/agent/desktop/service.py::_knowledge_init_workspace`, `_knowledge_ingest_folder`, and `_execute_desktop_knowledge_command`; protocol contract/tests.
- Status: Active compatibility limitation

### FAIL-014 — User-facing Skill documentation retains retired contracts

- Symptom: root README still advertises `/skill`, `task_modes` and persistent `/citation ... off`; `app/SKILLS_GUIDE.md` also retains persistent Citation wording. Its generic one-shot/installer material is useful, but it is not uniformly current.
- Trigger: following those obsolete paragraphs instead of the current Citation Skill and shared command implementation.
- Root cause: Confirmed documentation drift; both pages were inspected at `a88d44d`.
- Current handling: generic `/<skill-name> <prompt>` and `/citation <prompt>` are single-turn; bare/deactivation Citation commands return guidance rather than enabling persistent mode. Installer continuation follows its separate host scope.
- Evidence: root README slash table/Skills; `app/SKILLS_GUIDE.md` Citation paragraph; `app/skills/citation/SKILL.md`; `_handle_citation`; strict manifest and slash tests. This maintenance leaves non-knowledge documentation unchanged.
- Related: INV-019, ASM-011.
- Status: Active documentation conflict.

### FAIL-009 — Provider or MCP failure degrades or aborts the affected path

- Symptom: chat/extended/ingest/search/citation feature errors, or configured MCP tools are absent.
- Trigger / preconditions: missing key/model/service, network failure, server crash, or hung startup.
- Affected components or users: feature-specific operation.
- Root cause: Confirmed operational dependency; MCP startup intentionally degrades to diagnostics, while provider exceptions fail the affected accepted turn.
- Current handling / recovery: configure/restart the dependency. The prompt is canonical pending before provider/tool execution; a provider exception attempts a durable failed transition, but if that transition also fails the original error is preserved and restart converts the leftover pending work to interrupted. Neither state auto-replays. MCP failure does not prevent the base session.
- Reproduction or detection: test_mcp.py::test_session_create_survives_mcp_failure; test_session_lifecycle.py; six test_desktop_crash_recovery.py subprocess boundaries; README troubleshooting. No live provider run.
- Related invariants / assumptions: ASM-001, ASM-013.
- Evidence: app/agent/startup.py; app/agent/mcp.py; app/agent/session.py; app/agent/conversations/repository.py.
- Status: Active operational mode

## Mitigated but still relevant

### FAIL-005 — Post-startup applied Skill tampering is rejected before activation

- Former symptom: the prior startup-only path loaded changed installed instructions without another approval. The 2026-09-05 probe belongs to that older path.
- Resolution: startup retains approved `applied_source_hash`; runtime re-inspects the managed bundle and raises `applied bundle changed; restart or re-apply required` before loading changed files.
- Detection/recovery: activation/startup tests cover instructions, manifest, resources and unsafe paths; restore approved content or re-apply and materialize a fresh session.
- Limits: precheck-to-read TOCTOU remains; neither source inspection nor the tests prove immutable files against a continuous writer.
- Evidence: `app/agent/extensions/startup.py::_load_skill`, `app/agent/skills/runtime.py::load_skill_runtime`, `test_runtime_rejects_applied_bundle_changed_after_startup`. Confirmed current source/test definitions at `a88d44d`; no reproduction run this pass.
- Related: INV-009, INV-013, ASM-007.
- Status: Mitigated for the accepted activation-precheck scope.

### FAIL-006 — Cooperating extension apply writers are serialized across processes

- Former symptom: process-local-only apply could lose a reported successful registry update.
- Resolution: a stable state-root `.apply.lock` receives nonblocking exclusive Linux flock before latest revision read and remains held through `_apply_locked`/durable publication. Busy callers fail visibly; stale previews require regeneration.
- Detection/recovery: `test_cross_process_apply_preserves_successful_update` checks one success, busy rejection, later stale rejection, then fresh-preview success preserving both Skills. Adjacent tests cover fsync lifetime and crash/exception release.
- Limits: local cooperating writers only; installer staging, catalog/conversations, network filesystems, uncooperative writers and power-loss behavior are not covered by this lock.
- Evidence: `ExtensionManager.apply` / `_apply_locked` and `app/tests/test_extension_manager.py`; Confirmed source/definitions at `a88d44d`, not a new multiprocessing run.
- Related: INV-009, ASM-008.
- Status: Mitigated.

### FAIL-007 — Earliest-year ties now fail ambiguous

- Former symptom: same-year or wholly undated eligible versions could be chosen by relevance/rank.
- Resolution: deduplicate canonical identities, reject all-missing years with `earliest_year_missing` and tied known minima with `earliest_year_tie`. `CitationService.save` does not override those decisions with authority fallback.
- Detection/recovery: resolution, resolver, service/authority and tool tests check ambiguity propagation and no save for the ambiguous cases. User can supply a specific target.
- Limits: accepted scope compares years only; unique known minimum selection still tolerates undated alternatives. The historical wrong-selection probe is not current behavior.
- Evidence: `resolution.py::decide_resolution`, `service.py::save`, `test_citation_resolution.py` and authority/work-resolver definitions; Confirmed source at `a88d44d`.
- Related: INV-014, ASM-009.
- Status: Mitigated for year-only ambiguity.

### FAIL-015 — Desktop Citation entry and lifecycle are implemented

- Former symptom: Desktop rejected `/citation` and exposed no Citation entry.
- Resolution: shared CLI/Desktop `/citation <prompt>` runs one Normal task, then releases citation scope and restores prior thinking mode. Desktop's Python catalog includes it only when runtime/tool eligibility holds.
- Detection/recovery: current service/e2e tests cover fresh runtime gating, cleanup and exact completed replay without another model/fetch/save. Failed/interrupted work still needs an eligible runtime.
- Evidence: `_handle_citation`, `ChatSession._run_one_shot_skill_turn`, `DesktopService._desktop_command_eligible`; [archived native final-check](https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/bc2c94d40562e9606a9872bc922a36423b6a10a2/issue/final_check/build-log.md) records menu/tool/final-output and A/B/restart/failure/interruption paths using real session/Citation code with fake model/fetch seams.
- Limits: no fresh native/provider run; no general GUI per-task cancellation entry was established by the archive.
- Related: INV-010, INV-019.
- Status: Mitigated; former deferred Citation decision is resolved, distinct from still-deferred Thinking Effort.

### FAIL-004 — Legacy hard-cap history loss

- Former symptom: the retired TurnStore could drop the oldest in-memory turn after repeated Chroma history write failures reached its hard cap.
- Resolution: canonical conversation JSON now retains every accepted pending/terminal turn; normal session creation no longer constructs, writes, queries, evicts, or flushes a conversation-history Chroma store.
- Current handling / recovery: canonical fingerprint-prechecked atomic replacements fail explicitly; there is no secondary conversation writer or answer/document-size hard-cap data-loss path. Complete answer/document/wire/transcript text has no numeric bytes ceiling; the remaining turn-count and catalog-scan item limits are tracked separately by ASM-024.
- Verification: Phase 06 history-retirement and canonical lifecycle tests, plus the Phase 07 integrated fixture assertion that `store/chat_history` is never created.
- Related invariants / assumptions: INV-005, INV-006.
- Evidence: app/agent/session.py; app/agent/conversations/repository.py; current canonical-conversation tests.
- Status: Resolved in Phase 06

### FAIL-016 — Fixed absolute Desktop request deadline

- Former symptom: the Rust supervisor killed an otherwise healthy normal request after 600 total seconds, regardless of progress.
- Resolution: `BackendSupervisor.request` now submits normal requests with no timeout; response-channel closure, child exit, protocol failure, and bounded startup/shutdown paths still fail visibly.
- Current handling / recovery: user-driven shutdown/restart handles a genuinely stuck live child; there is no replacement normal inactivity detector (ASM-019).
- Verification: `progressing_request_can_outlive_the_prior_absolute_deadline` crosses the old shortened boundary and completes; `stdout_pipe_close_fails_the_pending_request_without_a_deadline` and `shutdown_bounds_an_in_flight_request` preserve terminal failure paths.
- Related invariants / assumptions: INV-011, ASM-019.
- Evidence: commit `45d446d`; `app/desktop/src-tauri/src/backend.rs`; current Rust regression tests.
- Status: Mitigated; obsolete source issue record removed

### FAIL-008 — Desktop shell was disconnected from the Python backend

- Symptom: before the current desktop commits, the UI exposed only a disabled shell and Tauri version.
- Trigger / preconditions: checkout at or before the previous audit baseline.
- Affected components or users: historical desktop implementation only.
- Root cause: Confirmed historical absence of Rust supervision/commands and React bridge state.
- Current handling / recovery: tracked Rust supervision, Python service/catalog, React conversations/trust UI, and protocol tests now implement the source-checkout path. Remaining direct-method and source-only limits are tracked separately as FAIL-013 and ASM-012.
- Reproduction or detection: compare `af5b76f` with commits `30f8b18` through `1e22f90`; fixed-revision final-check evidence records later integrated journeys/checks; see [testing](testing-strategy.md).
- Related invariants / assumptions: INV-011, INV-015, ASM-012.
- Evidence: Git history; `app/desktop`; `app/agent/desktop`; historical Git records; later evidence is scoped in [testing](testing-strategy.md).
- Status: Mitigated

### FAIL-010 — Empty or tool-protocol model output

- Symptom: blank reply, leaked tool syntax, or an unexecuted structured tool call would otherwise reach the user or canonical conversation record.
- Trigger / preconditions: malformed or empty upstream model response.
- Affected components or users: all agent turns.
- Root cause: Confirmed external/model-output failure.
- Current handling / recovery: two empty retries, one tool-free repair for invalid final content, then deterministic honest fallback before persistence.
- Reproduction or detection: test_graph_skill_loader.py and test_turn_finalizer.py.
- Related invariants / assumptions: INV-005.
- Evidence: app/agent/graph.py; app/agent/turns/safety.py.
- Status: Mitigated

### FAIL-011 — Graph tool quota and recursion fuse mismatch

- Symptom: historical citation save action could be generated but not executed before LangGraph recursion failure.
- Trigger / preconditions: old separate tool budgets with recursion limit 32.
- Affected components or users: historical citation/long tool turns.
- Root cause: Confirmed historical configuration mismatch.
- Current handling / recovery: separate quotas removed; one validated graph_recursion_limit defaults to 64 and forces tool-free finalization near the fuse.
- Reproduction or detection: current graph tests; the historical decision and verification are retained in `note/20260820/agent_loop_guardrail_consolidation.md`.
- Related invariants / assumptions: INV-005.
- Evidence: `note/20260820/agent_loop_guardrail_consolidation.md`; app/agent/config.py; app/agent/graph.py.
- Status: Mitigated

### FAIL-012 — Cross-platform line-ending churn

- Symptom: whole-file diffs, whitespace noise, and merge conflicts from LF/CRLF conversions.
- Trigger / preconditions: Windows and WSL tools using host defaults.
- Affected components or users: repository review/merge hygiene.
- Root cause: Confirmed historical absence of repository-owned attributes.
- Current handling / recovery: .gitattributes enforces LF with batch/cmd exceptions.
- Reproduction or detection: Git attributes and commit `3ac4f8b`.
- Related invariants / assumptions: INV-002.
- Evidence: `.gitattributes`; commit `3ac4f8b`.
- Status: Mitigated

### FAIL-017 — Persisted first-turn failure disappeared from the sidebar

- Former symptom: after the first prompt was durably accepted but provider execution failed, creating another conversation could leave the failed conversation absent from the sidebar or unavailable for reselection.
- Root cause: the frontend error path showed the failure but did not refresh the project catalog and selected canonical transcript after Python reported a persisted turn lifecycle.
- Resolution: `isPersistedTurnFailure` and the guarded `sendTurn` error path refreshes catalog and transcript only when lifecycle metadata says the turn was both accepted and persisted, with generation, project, and session guards against stale async results.
- Current handling / recovery: if reconciliation itself fails, the original error remains and an additional saved-but-refresh-failed notice is shown; later reselection/refresh can recover from canonical state.
- Verification: TypeScript regression `durable first-turn failure remains selectable after creating another conversation`; Python `test_first_prompt_registers_catalog_before_provider_failure` covers the durable backend premise.
- Related invariants / assumptions: INV-006, INV-011, ASM-015.
- Evidence: commit `9992913`; `app/desktop/src/App.tsx`; `app/agent/desktop/service.py`; corresponding Python/TypeScript tests.
- Status: Mitigated

### FAIL-018 — A pending retry duplicated its stale failure card

- Former symptom: retrying a restored failed or interrupted turn could render both the old terminal card and a new pending card, temporarily inflating the visible turn count.
- Root cause: pending turns were appended outside the restored/live logical-turn merge.
- Resolution: pending records now participate in `mergeConversationTurns` under `(sessionId, turnId)` identity, overlaying the stale failure until the authoritative terminal result replaces them.
- Current handling / recovery: a genuinely new pending turn receives provisional ordering after the loaded session's current maximum; terminal `turnNumber` remains authoritative.
- Verification: pending failed/interrupted overlay, new-pending append, and unresolved-retry single-prompt TypeScript regressions.
- Related invariants / assumptions: INV-011, ASM-015.
- Evidence: commit `e3dfdbe`; `app/desktop/src/conversations.ts`; `app/desktop/src/App.tsx`; Desktop TypeScript tests.
- Status: Mitigated

### FAIL-019 — Large Markdown exceeded JavaScript's variadic argument capacity

- Former symptom: sufficiently large inline, list, or block Markdown content could fail while React elements were created with spread dynamic children.
- Root cause: content-sized arrays were expanded into function arguments, inheriting the JavaScript engine's finite call-argument capacity.
- Resolution: `SafeContent` passes dynamic child collections as array children.
- Current handling / recovery: structural regressions exercise 140,000 inline, list-item, and paragraph children. This is an evidence point, not a product ceiling or native-WebView performance guarantee.
- Verification: three large-content TypeScript regressions in `conversations.test.ts`.
- Related invariants / assumptions: INV-017, ASM-025.
- Evidence: commit `8dee300`; `app/desktop/src/SafeContent.tsx`; `app/desktop/tests/conversations.test.ts`.
- Status: Mitigated

### FAIL-020 — Maximized Desktop window retained compact typography

- Former symptom: maximizing or using a wide Desktop window increased whitespace while text remained at the same small scale.
- Root cause: the root had no width-responsive font size while component typography used `rem` values, so wider windows did not alter the inherited scale.
- Resolution: the root font uses a bounded viewport-responsive clamp: it preserves the 1rem baseline at the initial 1080px width, grows on wider windows, and caps at 1.3125rem.
- Current handling / recovery: the source contract and representative-width arithmetic are tested; pre-maintenance headless-Chrome observations covered 720, 1080, 1920, and 2560 widths. Native maximized/fullscreen Tauri, DPI, and human visual acceptance remain unverified.
- Verification: `styles.test.ts`, `npm test` (151 passing in the prior 2026-09-06 account at `743aaaf`, not a current-pass run), `npm run build`, and headless layout observations.
- Related invariants / assumptions: INV-021, ASM-025.
- Evidence: commit `743aaaf`; `app/desktop/src/styles.css`; `app/desktop/tests/styles.test.ts`.
- Status: Mitigated; native visual evidence remains a testing gap

## Diagnostic index

| Symptom | First safe check | Likely item |
|---|---|---|
| Explore shows deleted folder | Compare folder_meta.json inventory with root-scoped raw chunks | FAIL-001 |
| Empty file still appears in search | list_chunks for its namespaced PID after re-ingest | FAIL-002 |
| Search and list/context disagree | Inspect raw.json versus Chroma after the last failed ingest | FAIL-003 |
| Older exact wording is not found | Verify the `/status` conversation root and approved `grep -F` phrase; exact misses do not use semantic fallback | Expected exact-match limitation; FAIL-004 retired |
| Applied Skill content changed mid-session | Read activation hash diagnostics; re-apply/restore approved bytes and reload | FAIL-005 |
| Extension apply reports busy or stale preview | Check busy/stale-preview reports and the stable state-root apply lock | FAIL-006 |
| Earliest citation returns ambiguity | Compare candidate year/date/relation evidence, not provider rank | FAIL-007 |
| Raw desktop folder ingest says not enabled | Use the selected conversation's `/init` or `/ingest` route; inspect direct-method caller | FAIL-013 |
| `/skill` is unknown or `task_modes` is rejected | Use `/<skill-name> <prompt>` and the current `app/SKILLS_GUIDE.md` contract | FAIL-014 |
| `/citation` is rejected in Desktop | Check runtime/tool eligibility for the single-turn command; completed replay has separate canonical checks | FAIL-015 |
| A long request is no longer killed at 600 seconds | Confirm current Rust source/test, then use explicit shutdown/restart only if it is actually stuck | FAIL-016 / ASM-019 |
| Old checkout shows only a disabled desktop shell | Compare checkout to the current desktop commits and use the current source-run instructions | FAIL-008 |
| Tool family missing | Session /status diagnostics and MCP stderr log | FAIL-009 |
| Safe fallback instead of answer | Redaction-safe recovery reason/telemetry, not model content logs | FAIL-010 |
| Saved first-turn failure is missing from the sidebar | Check lifecycle `accepted`/`persisted` flags, then catalog/transcript refresh errors | FAIL-017 |
| Retry shows both pending and stale failed cards | Inspect the logical `(sessionId, turnId)` merge across restored/live/pending sources | FAIL-018 |
| Huge Markdown throws or disappears | Inspect `SafeContent` for variadic dynamic-child spreads; distinguish correctness from native performance | FAIL-019 / ASM-025 |
| Text stays tiny after maximizing | Inspect the root typography clamp and computed root size; then perform a native visual check | FAIL-020 / INV-021 |
