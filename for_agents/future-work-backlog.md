# Future-Work Backlog

Freshness: 2026-09-13 source/contract/test-definition inspection at `a88d44d` covers completed extension/earliest/Citation/save-reporting candidates and the explicit Thinking Effort deferral. Other claims retain the 2026-09-05 (`9745fd1`) or unchanged Desktop 2026-09-06 (`743aaaf`) basis; historical probes were not rerun. See [audit coverage](README.md#audit-coverage).

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

### BACKLOG-013 — Align user-facing Skill records with the live runtime

- Priority: P2
- Problem: root README still advertises retired `/skill`/`task_modes` and persistent Citation; `app/SKILLS_GUIDE.md` retains persistent Citation too.
- Evidence: `app/agent/cli/slash_commands.py::_project_skill_commands`; `_RETIRED_SKILL_COMMANDS`; `app/agent/session.py::_run_one_shot_skill_turn`; FAIL-014.
- Why it matters: contributors can implement or troubleshoot against interfaces that the runtime deliberately removed.
- Suggested scope: align the stale README/Skill-guide paragraphs with the current single-turn Citation contract, installer exception and Desktop ask/bypass policy; no runtime change.
- Dependencies / blockers: none; do not change runtime behavior as part of this documentation item.
- Acceptance criteria: user-facing docs describe `/<skill-name> <prompt>` as one-shot, describe Citation as single-turn in CLI/Desktop, explain bounded installer continuation, and omit retired `task_modes`.
- Related items: INV-019, FAIL-014.
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

The unchanged RAG/catalog/conversation candidates below retain their prior evidence dates from [audit coverage](README.md#audit-coverage). A candidate is not authorization to implement it.

## Blocked or research items

The sole retained issue card is [multi-level Thinking Effort](../issue/09-desktop-thinking-effort-control-deferred.md). The user explicitly deferred it: do not infer tiers, mappings, persistence policy or implementation authority. Current Normal/Extended behavior and Citation/installer Normal boundaries stay in place. No new backlog item or plan duplicates that card.

### BACKLOG-009 — Decide whether academic Skill bash prohibition is policy or guidance

- Priority: Research
- Problem: README says academic-paper-writing forbids bash, while runtime keeps every base tool, including bash, globally available under runtime permission policy (Desktop ask/bypass).
- Evidence: app/agent/tools/access.py; test_tool_access_matrix.py::test_skill_switch_does_not_change_bash_permission_mode; README.md.
- Why it matters: users and agents can misread a prose restriction as enforced access control.
- Suggested scope: make one explicit product decision, then align README/Skill manifest/runtime test without changing unrelated tool architecture.
- Dependencies / blockers: user decision on instruction-only versus enforced restriction.
- Acceptance criteria: docs, availability block, actual binding, PolicyToolNode, and tests describe one behavior.
- Related items: ASM-011.
- Status: Blocked

## Recently resolved or removed

### BACKLOG-003 — Resolved in the inspected source

Activation now retains/rechecks the applied hash before loading instructions, manifest and resources. INV-013 / FAIL-005 retain the accepted precheck scope and TOCTOU limit. Evidence: runtime/startup source and current activation tests at `a88d44d`.

Status: Resolved; evidence rechecked 2026-09-13, no new runtime execution.

### BACKLOG-004 — Resolved in the inspected source

Missing/tied-year ambiguity is implemented and preserved through authority fallback. INV-014 / FAIL-007 retain the year-only limit and tested handling of undated alternatives. Evidence: current resolution/service/authority tests and source at `a88d44d`.

Status: Resolved; evidence rechecked 2026-09-13, no new runtime execution.

### BACKLOG-005 — Resolved in the inspected source

Linux state-root flock now covers cooperating apply transactions; busy/stale paths and multiprocessing regressions exist. FAIL-006 records the boundary. Evidence: `ExtensionManager.apply` and current manager tests at `a88d44d`.

Status: Resolved; evidence rechecked 2026-09-13, no new runtime execution.

### BACKLOG-008 — Resolved in the inspected source

The requested save-reporting characterization is complete: strict tool outcomes and real-graph fake-model success/failure/mixed/retry journeys, with archived final-check evidence. No forced host Citation answer layer was required. Arbitrary live-model prose remains ASM-014, not automatic follow-on implementation.

Status: Resolved; evidence rechecked 2026-09-13, no new runtime execution.

### BACKLOG-014 — Resolved in the inspected source

CLI/Desktop Citation now follows one explicit single-turn contract, with Normal-mode execution/restore, registry cleanup, exact completed replay and archived native acceptance. See INV-019 / FAIL-015. The separate Thinking Effort card is still deferred.

Status: Resolved; evidence rechecked 2026-09-13, no new runtime execution.

- The resolved line-ending issue record was removed; repository-owned `.gitattributes` enforces LF and prevents host Git defaults from governing text files.
- The resolved graph-budget issue record was removed; separate tool quotas are gone and one validated graph recursion fuse with early finalization governs turns.

### BACKLOG-007 — Persistent generic Skill selection and task modes removed

Resolved/removed in `78589e9`: legacy manifests containing `task_modes` are rejected, `/skill` is reserved but unregistered, and non-Citation Skills use one-shot commands with focused tests.

### BACKLOG-012 — Canonical prompt-first conversation lifecycle replaced flush repair

Resolved for the supported offline source paths: canonical JSON is the sole active transcript authority and `ConversationRepository` its sole writer. Prompt-first and terminal-before-success ordering remove the former flush window; repository temporary-write tests, catalog/restart tests, six real Python-backend SIGKILL checkpoints, final broad suites/build, and the native Tauri behavioral journey cover interrupted/no-auto-replay recovery. This does not claim live-provider or real-user-state behavior; exact native `720×560` and 200% zoom evidence remains unavailable/not passed.

### BACKLOG-018 — Legacy conversation staging removed with the importer

This item is resolved/removed with the legacy conversation importer itself: no current path clones or stages old `chat_history`, and old Chroma/Plan-log sources are left untouched rather than converted.

- FAIL-008 is resolved for the supported source checkout: commits `30f8b18` through `1e22f90` added Rust supervision, Python conversation/service wiring, React UI, knowledge commands, and trust flows; historical fixed-revision records retain scoped verification; [testing](testing-strategy.md) preserves the later Rust full-suite failure and focused correction.
- Removed GUI/corrective/reconstruction plans are historical evidence, not current execution authority. Source-only packaging and remaining gaps are recorded separately; no stale plan status restarts work.
- Historical July citation research/benchmark proposals are not carried forward automatically; current contracts/code and the retained deferred card govern present work.
