# Known Failure Modes

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
- Root cause: Confirmed — the three stores are updated in order without one transaction; JSON-before-Chroma operations can also fail between writes.
- Current handling / recovery: error propagates; rerun the idempotent ingest, or back up/move the generated store and rebuild.
- Reproduction or detection: code-defined failure semantics; raw JSON rollback tests exist, but no cross-store failure-injection test.
- Related invariants / assumptions: INV-008, INV-012, ASM-002, ASM-003.
- Evidence: app/rag/cli/ingest.py; app/rag/store/document_store.py; app/rag/store/json_store.py::deferred_save.
- Status: Active

### FAIL-004 — Legacy hard-cap history loss (resolved)

- Former symptom: the retired TurnStore could drop the oldest in-memory turn after repeated Chroma history write failures reached its hard cap.
- Resolution: canonical conversation JSON now retains every accepted pending/terminal turn; normal session creation no longer constructs, writes, queries, evicts, or flushes a conversation-history Chroma store.
- Current handling / recovery: canonical compare-and-swap transitions fail explicitly; there is no secondary conversation writer or hard-cap drop path.
- Verification: Phase 06 history-retirement and canonical lifecycle tests, plus the Phase 07 integrated fixture assertion that `store/chat_history` is never created.
- Related invariants / assumptions: INV-005, INV-006.
- Evidence: app/agent/session.py; app/agent/conversations/repository.py; harness/reconstruct/build-log.md.
- Status: Resolved in Phase 06

### FAIL-005 — Post-startup installed Skill tampering is activated

- Symptom: modifying the private installed SKILL.md after startup changes the instructions loaded by a later /skill activation without apply/restart.
- Trigger / preconditions: another same-user process or manual action mutates the managed installed bundle during a live session.
- Affected components or users: Skill instructions, task modes, pinned resources, and requested tool permissions.
- Root cause: Confirmed — startup validates source_hash, but SkillMetadata retains only the path and load_skill_runtime rereads disk without comparing the hash.
- Current handling / recovery: restart will revalidate and skip a bad bundle; the live session has no activation-time guard.
- Reproduction or detection: focused probe observed post_startup_tamper_loaded=True.
- Related invariants / assumptions: INV-009, INV-013, ASM-007.
- Evidence: issue/02-extension-skill-post-startup-integrity.md; app/agent/extensions/startup.py; app/agent/skills/runtime.py.
- Status: Active

### FAIL-006 — Concurrent extension applies can lose an update

- Symptom: two CLI processes both report revision N+1 success, but the later registry replace omits the other process's change.
- Trigger / preconditions: separate processes apply different changes to the same extension state root concurrently.
- Affected components or users: applied Skill/MCP registry and managed-state expectations.
- Root cause: Confirmed from control flow — _APPLY_LOCK is process-local; atomic replace prevents torn JSON but is not interprocess compare-and-swap.
- Current handling / recovery: inspect status and re-apply missing desired state; no cross-process lock or regression test.
- Reproduction or detection: deterministic race sequence documented in issue/04; multiprocessing reproduction not run in this audit.
- Related invariants / assumptions: INV-009, ASM-008.
- Evidence: app/agent/extensions/manager.py::_APPLY_LOCK; app/agent/extensions/registry.py::write_registry; issue/04.
- Status: Active

### FAIL-007 — Same-year earliest citation can select the wrong version

- Symptom: version_kind=earliest returns eligible instead of ambiguous for distinct same-year or undated manifestations.
- Trigger / preconditions: multiple identity-compatible candidates share the minimum year and lack finer temporal/relation evidence.
- Affected components or users: citation version selection and saved bibliography identity.
- Root cause: Confirmed — decide_resolution breaks equal-year ties with score/rank/provider.
- Current handling / recovery: agent/user must inspect alternatives or request a specific version; no fail-closed tie rule exists.
- Reproduction or detection: focused probe observed same_year_earliest=eligible:fixture:pub.
- Related invariants / assumptions: INV-014, ASM-009.
- Evidence: app/skills/citation/resolution.py::decide_resolution; issue/03; test_citation_resolution.py covers only different years.
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

### FAIL-008 — Desktop shell was disconnected from the Python backend

- Symptom: before the current desktop commits, the UI exposed only a disabled shell and Tauri version.
- Trigger / preconditions: checkout at or before the previous audit baseline.
- Affected components or users: historical desktop implementation only.
- Root cause: Confirmed historical absence of Rust supervision/commands and React bridge state.
- Current handling / recovery: tracked Rust supervision, Python service/catalog, React conversations/trust UI, and protocol tests now implement the source-checkout path. Remaining direct-method and source-only limits are tracked separately as FAIL-013 and ASM-012.
- Reproduction or detection: compare `af5b76f` with commits `30f8b18` through `1e22f90`; current build log records integrated journeys and final checks.
- Related invariants / assumptions: INV-011, INV-015, ASM-012.
- Evidence: Git history; `app/desktop`; `app/agent/desktop`; completed GUI build log.
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
- Reproduction or detection: current graph tests; historical issue record.
- Related invariants / assumptions: INV-005.
- Evidence: issue/06-citation-tool-budget-recursion-limit.md; app/agent/config.py; app/agent/graph.py.
- Status: Mitigated

### FAIL-012 — Cross-platform line-ending churn

- Symptom: whole-file diffs, whitespace noise, and merge conflicts from LF/CRLF conversions.
- Trigger / preconditions: Windows and WSL tools using host defaults.
- Affected components or users: repository review/merge hygiene.
- Root cause: Confirmed historical absence of repository-owned attributes.
- Current handling / recovery: .gitattributes enforces LF with batch/cmd exceptions.
- Reproduction or detection: git attributes and issue/05 evidence.
- Related invariants / assumptions: INV-002.
- Evidence: .gitattributes; issue/05-cross-platform-line-endings.md.
- Status: Mitigated

## Diagnostic index

| Symptom | First safe check | Likely item |
|---|---|---|
| Explore shows deleted folder | Compare folder_meta.json inventory with root-scoped raw chunks | FAIL-001 |
| Empty file still appears in search | list_chunks for its namespaced PID after re-ingest | FAIL-002 |
| Search and list/context disagree | Inspect raw.json versus Chroma after the last failed ingest | FAIL-003 |
| Older exact wording is not found | Verify the `/status` conversation root and approved `grep -F` phrase; exact misses do not use semantic fallback | Expected exact-match limitation; FAIL-004 retired |
| Applied Skill content changed mid-session | Hash installed bundle against registry and restart | FAIL-005 |
| Applied extension disappears after concurrent work | Compare desired state, registry revision, and both process reports | FAIL-006 |
| Earliest citation looks arbitrary | Compare candidate year/date/relation evidence, not provider rank | FAIL-007 |
| Raw desktop folder ingest says not enabled | Use the selected conversation's `/init` or `/ingest` route; inspect direct-method caller | FAIL-013 |
| Old checkout shows only a disabled desktop shell | Compare checkout to the current desktop commits and use the current source-run instructions | FAIL-008 |
| Tool family missing | Session /status diagnostics and MCP stderr log | FAIL-009 |
| Safe fallback instead of answer | Redaction-safe recovery reason/telemetry, not model content logs | FAIL-010 |
