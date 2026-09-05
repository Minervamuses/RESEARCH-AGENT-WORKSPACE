# Future-Work Backlog

## Active backlog

### BACKLOG-001 — Remove pruned folders from RAG inventory

- Priority: P1
- Problem: prune_orphans removes Chroma/raw chunks but leaves namespaced folder metadata, so explore reports deleted folders.
- Evidence: FAIL-001 focused reproduction; app/rag/sync.py::prune_orphans never writes folder_meta.json.
- Why it matters: agents and future UI can present a stale knowledge inventory.
- Suggested scope: update only the affected namespace/folders during confirmed prune and add one focused regression.
- Dependencies / blockers: define when a folder with zero stored files should be removed while preserving other roots.
- Acceptance criteria: after pruning a root's last file in a folder, explore omits that folder and preserves unrelated roots/folders.
- Related items: INV-012, ASM-003, FAIL-001.
- Status: Not started

### BACKLOG-002 — Delete prior chunks when re-ingested source becomes empty or unreadable

- Priority: P1
- Problem: repo re-ingest skips zero-doc files before adding their PID to the delete set, leaving stale content.
- Evidence: FAIL-002 focused reproduction; app/rag/cli/ingest.py::ingest_repo.
- Why it matters: research answers may quote content that no longer exists.
- Suggested scope: make the folder upsert delete the current path's prior PID even when no replacement chunks are produced; keep source-error reporting explicit.
- Dependencies / blockers: decide whether unreadable/permission-denied files should delete old content or fail the folder update.
- Acceptance criteria: an emptied file cannot be found after re-ingest; the chosen unreadable-file policy is tested and visible.
- Related items: INV-012, ASM-003, FAIL-002.
- Status: Not started

### BACKLOG-003 — Preserve applied Skill integrity for the whole session

- Priority: P1
- Problem: activation rereads mutable managed files after startup verification.
- Evidence: focused probe post_startup_tamper_loaded=True; issue/02 (historical command wording, current trust defect); FAIL-005.
- Why it matters: apply-and-restart is the extension trust boundary.
- Suggested scope: either retain source_hash and revalidate at activation or load an immutable startup snapshot; cover instructions, manifest, and pinned resources once.
- Dependencies / blockers: choose hash-on-activation versus memory snapshot based on existing size/lazy-loading constraints.
- Acceptance criteria: modifying installed content after startup never changes or successfully activates the live-session Skill; normal apply, restart, activate still works.
- Related items: INV-009, INV-013, ASM-007, FAIL-005.
- Status: Not started

### BACKLOG-004 — Make unsupported earliest citation ties ambiguous

- Priority: P2
- Problem: same-year or undated distinct manifestations can be selected by relevance/rank without temporal proof.
- Evidence: focused probe same_year_earliest=eligible:fixture:pub; issue/03; FAIL-007.
- Why it matters: the saved version can contradict the user's earliest request.
- Suggested scope: fail closed for tied minimum year identities unless finer date or explicit relation evidence establishes order.
- Dependencies / blockers: decide comparable date fields/relations if support goes beyond the minimal tie guard.
- Acceptance criteria: different years still choose the older record; same-year/undated unresolved identities return ambiguity with useful alternatives.
- Related items: INV-014, ASM-009, FAIL-007.
- Status: Not started

### BACKLOG-005 — Serialize extension apply across processes

- Priority: P2
- Problem: two processes can commit different revision N+1 registries from the same revision N.
- Evidence: process-local _APPLY_LOCK and atomic replace without interprocess CAS; issue/04; FAIL-006.
- Why it matters: a reported successful extension can disappear.
- Suggested scope: one Linux/WSL file lock or real compare-and-swap around final revision read through durable replace, plus a multiprocessing regression.
- Dependencies / blockers: define timeout/crash behavior without adding a broad concurrency framework.
- Acceptance criteria: at most one concurrent apply commits; the other reports a retryable stale/lock conflict; registry remains valid and no successful update is lost.
- Related items: INV-009, ASM-008, FAIL-006.
- Status: Not started

### BACKLOG-006 — Add focused RAG partial-write failure evidence

- Priority: P2
- Problem: RAG recovery is documented as rerun-based, but no test injects Chroma add/delete failure between folder metadata and raw JSON completion.
- Evidence: FAIL-003; app/rag/cli/ingest.py and DocumentStore write order.
- Why it matters: users need an honest, test-backed recovery signal when store surfaces diverge.
- Suggested scope: one deterministic failure-injection test per materially different add/delete ordering and, only if required, a concise partial-write error.
- Dependencies / blockers: avoid introducing a transaction/migration framework for this local project.
- Acceptance criteria: tests show exact resulting surfaces and prove that the documented rerun or explicit recovery restores consistency.
- Related items: INV-008, INV-012, ASM-003, FAIL-003.
- Status: Not started

### BACKLOG-008 — Verify user-facing citation save reporting against mixed outcomes

- Priority: P2
- Problem: structured ToolMessage outcomes are authoritative, but final prose truthfulness remains model-governed.
- Evidence: issue/01; ASM-014; current finalizer intentionally does not overwrite model prose.
- Why it matters: a mixed/failed batch can be described incorrectly even though artifacts and telemetry are correct.
- Suggested scope: deterministic fake-model journey for all-success, all-failure, mixed, and retry-success; add a separate human-readable status block only if evidence shows it is needed.
- Dependencies / blockers: preserve the decision not to reintroduce a host renderer that replaces the full answer.
- Acceptance criteria: final responses are demonstrably based on prior ToolMessage outcomes, and any independent CLI status derives from the same SaveBatchOutcome.
- Related items: INV-010, ASM-014.
- Status: Not started

### BACKLOG-010 — Prevent desktop catalog lost updates across processes

- Priority: P2
- Problem: `DesktopProjectCatalog` atomically replaces a process-local snapshot but does not lock or compare the current file revision when registering a session.
- Evidence: `app/agent/desktop/catalog.py::register_session` and `_atomic_replace`; ASM-016. The Rust supervisor serializes only one child inside one application process.
- Why it matters: launching two desktop applications against one `persist_dir` can make a successfully saved conversation disappear from project membership.
- Suggested scope: add the smallest Linux/WSL interprocess lock or compare-and-retry boundary around read-modify-replace; do not introduce a database or generic coordination layer.
- Dependencies / blockers: define bounded lock timeout and stale-process behavior; preserve the strict existing file schema.
- Acceptance criteria: a multiprocessing regression proves concurrent registrations either both persist or one reports a retryable conflict, with valid JSON and no lost successful update.
- Related items: INV-016, ASM-016.
- Status: Not started

### BACKLOG-011 — Align advertised desktop knowledge mutations with the supported route

- Priority: P2
- Problem: protocol v1 declares `knowledge.init_workspace` and `knowledge.ingest_folder`, but their direct handlers always fail while the supported React flow sends `/init` and `/ingest` through `session.turn`.
- Evidence: `app/desktop/protocol/v1/contract.json`; `app/agent/desktop/service.py`; FAIL-013.
- Why it matters: an alternate client or future refactor can select a contract-valid method that is guaranteed to fail and accidentally create a second knowledge workflow.
- Suggested scope: preserve protocol-v1 compatibility while making the supported route explicit; either implement the same Python-owned structured-progress behavior behind the direct methods or mark them as intentionally unsupported in the contract/docs and tests.
- Dependencies / blockers: requires a narrow product decision on whether raw protocol clients are supported; must not add a standalone Knowledge UI.
- Acceptance criteria: contract, handlers, README, and tests describe one behavior, and no advertised supported method deterministically fails by design.
- Related items: INV-015, INV-018, FAIL-013.
- Status: Not started

### BACKLOG-013 — Align user-facing Skill and timeout records with the live runtime

- Priority: P2
- Problem: the root README still advertises retired persistent `/skill` selection and `task_modes`, while issue/08 still presents the retired 600-second Desktop request deadline as open/current behavior.
- Evidence: `app/agent/cli/slash_commands.py::_project_skill_commands`; `_RETIRED_SKILL_COMMANDS`; `app/agent/session.py::_run_one_shot_skill_turn`; `app/desktop/src-tauri/src/backend.rs::request`; FAIL-014; FAIL-016.
- Why it matters: contributors can implement or troubleshoot against interfaces that the runtime deliberately removed.
- Suggested scope: update only the stale README Skill sections and issue/08 status/current-behavior summary while retaining their historical evidence.
- Dependencies / blockers: none; do not change runtime behavior as part of this documentation item.
- Acceptance criteria: user-facing docs describe `/<skill-name> <prompt>` as one-shot, identify Citation as the only persistent CLI Skill path, omit `task_modes`, and record that normal Desktop requests have no absolute deadline.
- Related items: INV-019, FAIL-014, FAIL-016.
- Status: Not started

### BACKLOG-015 — Preserve `/init` exclusions in later sync scans

- Priority: P2
- Problem: `init_workspace` excludes the top-level `app/` tree, but `diff_folder` does not pass that exclusion to `list_diff`, so a later `/sync <host-root>` can classify intentionally omitted files as missing from the store.
- Evidence: `app/agent/ingest.py::init_workspace`; `app/agent/ingest.py::diff_folder`; `app/rag/sync.py::list_diff`; ASM-020. This audit did not run a live ingest reproduction.
- Why it matters: noisy sync output can hide actual corpus drift and steer users toward indexing application code that `/init` intentionally excluded.
- Suggested scope: carry the same explicit exclusion into comparison/prune previews, or persist one narrowly defined workspace policy; add one deterministic path-level regression.
- Dependencies / blockers: define whether callers can override the default workspace exclusion without adding a generic policy framework.
- Acceptance criteria: after no-argument `/init`, `/sync <host-root>` for its returned host root omits excluded `app/` paths while still reporting a genuinely new allowed file.
- Related items: ASM-020.
- Status: Not started

### BACKLOG-016 — Make folder-prefix search complete or explicitly bounded

- Priority: P2
- Problem: `rag.search` retrieves only the global top `3 * k` results before applying `folder_prefix`, which can omit qualifying chunks ranked below unrelated global hits.
- Evidence: `app/rag/api.py::search`; ASM-021. No live embedding reproduction was run.
- Why it matters: a scoped search can look authoritative while returning fewer than the best available scoped matches.
- Suggested scope: query within the prefix scope before limiting, or expose and test a deliberate bounded-search contract without redesigning retrieval.
- Dependencies / blockers: confirm the smallest Chroma-supported filter that preserves existing source/folder normalization.
- Acceptance criteria: a focused deterministic test proves the top `k` prefix-matching results are returned despite more than `3 * k` higher-ranked out-of-prefix chunks, or the API explicitly reports its bound.
- Related items: ASM-021.
- Status: Not started

### BACKLOG-017 — Serialize canonical conversation writes across processes

- Priority: P2
- Problem: conversation save verifies a fingerprint and then atomically replaces the file, but no interprocess lock or filesystem compare-and-swap closes the interval between those operations.
- Evidence: `app/agent/conversations/repository.py::save`; `app/agent/session.py::_recover_interrupted_turn`; ASM-022. No multiprocessing reproduction was run.
- Why it matters: two application processes sharing one conversation can lose a successful transition, and a second opener can classify live pending work as interrupted.
- Suggested scope: add one narrow per-conversation Linux/WSL lock or equivalent guarded replace plus a multiprocessing regression; preserve the existing JSON format and single-process lifecycle.
- Dependencies / blockers: define bounded lock/lease behavior for crashed writers without adding a database or generic concurrency framework.
- Acceptance criteria: concurrent transitions cannot both report success while losing one result, and opening a genuinely active pending turn does not recover it prematurely.
- Related items: INV-006, ASM-022.
- Status: Not started

## Blocked or research items

### BACKLOG-009 — Decide whether academic Skill bash prohibition is policy or guidance

- Priority: Research
- Problem: README says academic-paper-writing forbids bash, while runtime keeps every base tool, including bash, globally available with approval.
- Evidence: app/agent/tools/access.py; test_tool_access_matrix.py::test_skill_switch_does_not_change_bash_permission_mode; README.md.
- Why it matters: users and agents can misread a prose restriction as enforced access control.
- Suggested scope: make one explicit product decision, then align README/Skill manifest/runtime test without changing unrelated tool architecture.
- Dependencies / blockers: user decision on instruction-only versus enforced restriction.
- Acceptance criteria: docs, availability block, actual binding, PolicyToolNode, and tests describe one behavior.
- Related items: ASM-011.
- Status: Blocked

### BACKLOG-014 — Define Citation lifecycle consistently across CLI and Desktop

- Priority: Research
- Problem: Citation is the sole persistent Skill lifecycle in the CLI, but Desktop rejects `/citation <prompt>` and exposes no equivalent activation/clear path.
- Evidence: `app/agent/cli/slash_commands.py`; `app/agent/skills/citation/session_policy.py`; `app/agent/desktop/service.py`; issue/09; FAIL-015.
- Why it matters: the same Python session model has different citation capabilities depending on its frontend, and a naïve fix could accidentally create persistent generic Skill state or replay work.
- Suggested scope: make one product decision on persistent versus one-shot Citation semantics, then align Python-owned session state, CLI/Desktop routing, registry finalization, and focused tests.
- Dependencies / blockers: user decision on whether Desktop should support multi-turn Citation sessions or a one-shot citation command.
- Acceptance criteria: CLI and Desktop document and enforce one deliberate Citation contract; activation, terminal cleanup, restart, and thinking interactions are covered without persisting generic Skill selection.
- Related items: INV-010, INV-019, FAIL-015.
- Status: Blocked

## Recently resolved or removed

- issue/05 is resolved: repository-owned .gitattributes enforces LF and prevents host Git defaults from governing text files.
- issue/06 is resolved: separate tool quotas were removed; one validated graph recursion fuse with early finalization now governs turns.
- BACKLOG-007 is resolved/removed: persistent generic Skill selection and task modes were retired in `78589e9`; legacy manifests containing `task_modes` are rejected, `/skill` is reserved but unregistered, and non-Citation Skills use one-shot commands with focused tests.
- BACKLOG-012 is resolved for the supported offline source paths: canonical JSON is the sole active transcript authority and `ConversationRepository` its sole writer; prompt-first and terminal-before-success ordering remove the former flush window; repository temporary-write tests, catalog/restart tests, six real Python-backend SIGKILL checkpoints, final broad suites/build, and the native Tauri behavioral journey cover interrupted/no-auto-replay recovery. This does not claim live provider or real user-state behavior; exact native `720×560` and 200% zoom layout evidence remains unavailable/not passed and blocks Phase 07 completion.
### BACKLOG-018 — Legacy conversation staging removed with the importer

This item is resolved/removed with the legacy conversation importer itself: no current path clones or stages old `chat_history`, and old Chroma/Plan-log sources are left untouched rather than converted.

- FAIL-008 is resolved for the supported source checkout: commits `30f8b18` through `1e22f90` added Rust supervision, Python conversation/service wiring, React UI, knowledge commands, and trust flows; the completed build log records final Python/TypeScript/Rust/build evidence.
- The desktop GUI completion plan is complete at the audited HEAD. It is historical execution evidence, not active backlog; source-only packaging and remaining gaps are recorded separately above.
- Historical July citation research/benchmark proposals are not carried forward automatically; current code/tests and the active citation issues govern present work.
