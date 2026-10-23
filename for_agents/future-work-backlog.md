# Future-Work Backlog

Freshness: every candidate was reconsidered on 2026-10-23 at `3f9176a` against current code, tests and records. BACKLOG-019 and BACKLOG-020 were updated at `d74065f` after the cleanup commits `c12470f`–`d74065f`. The RAG items BACKLOG-001, BACKLOG-002, BACKLOG-015 and BACKLOG-016 rest on code unchanged since `5a0fa7c`. A candidate is knowledge, not authorization: implementing anything here still needs the user's request, and dependency or ignore-rule changes need explicit approval (AGENTS.md). See [audit coverage](README.md#audit-coverage).

## Active backlog

### BACKLOG-001 — Remove pruned folders from RAG inventory

- Priority: P1
- Problem: `prune_orphans` removes Chroma and raw chunks but leaves namespaced folder metadata, so `explore` reports deleted folders.
- Evidence: FAIL-001 (2026-09-05 offline probe); `app/rag/sync.py::prune_orphans` never writes `folder_meta.json` (unchanged at `3f9176a`).
- Why it matters: agents and the UI present a stale knowledge inventory.
- Suggested scope: during a confirmed prune, update only the affected namespace and folders; add one focused regression.
- Dependencies / blockers: decide when a folder with zero stored files is removed, while preserving other roots.
- Acceptance criteria: after pruning a root's last file in a folder, `explore` omits that folder and keeps unrelated roots and folders.
- Related items: INV-012, ASM-003, FAIL-001.
- Status: Not started

### BACKLOG-002 — Delete prior chunks when re-ingested source becomes empty or unreadable

- Priority: P1
- Problem: repo re-ingest skips zero-document files before adding their PID to the delete set, so stale content stays searchable.
- Evidence: FAIL-002; `app/rag/cli/ingest.py::ingest_repo`.
- Why it matters: research answers can quote text that no longer exists.
- Suggested scope: make the folder upsert delete the current path's prior PID even when no replacement chunks are produced, and keep source-error reporting explicit.
- Dependencies / blockers: decide whether unreadable or permission-denied files delete old content or fail the folder update.
- Acceptance criteria: an emptied file can no longer be found after re-ingest, and the chosen unreadable-file policy is tested and visible.
- Related items: INV-012, ASM-003, FAIL-002.
- Status: Not started

### BACKLOG-006 — Add focused RAG partial-write and Stop evidence

- Priority: P2
- Problem: recovery is documented as rerun-based, but no test injects a Chroma failure, or a user Stop, between the folder-metadata write and the raw JSON commit.
- Evidence: FAIL-003; the `DocumentStore` and `ingest_repo` write order; `json_store.deferred_save` discards the batch on `CancelledError` while Chroma keeps its writes.
- Why it matters: Stop made this divergence user-triggerable; users need an honest, test-backed recovery signal.
- Suggested scope: one deterministic test per materially different add/delete ordering plus one post-Stop store check; add a concise partial-write message only if required.
- Dependencies / blockers: no transaction or migration framework for this local project.
- Acceptance criteria: tests show the exact resulting surfaces and prove that rerun (or the explicit recovery) restores consistency.
- Related items: INV-008, INV-012, ASM-003, FAIL-003.
- Status: Not started

### BACKLOG-011 — Align declared desktop protocol vocabulary with produced behavior

- Priority: P2
- Problem: protocol v1 advertises vocabulary that the Python backend deliberately fails or never produces or consumes:
  - `knowledge.init_workspace` and `knowledge.ingest_folder` always fail (FAIL-013).
  - 12 of 20 request events are never emitted, including `request.progress`, `knowledge.progress`, `collecting.*`, `tagging.*` and `ingest.*`.
  - `session.turn.documentOperations` is validated in all three languages but unused.
  - The approval operation value `extensions.apply` and the top-level `documentContextSchema` have no producer or consumer.
- Evidence: `app/desktop/protocol/v1/contract.json`; a grep of `app/agent` for each name; `service.py::_knowledge_init_workspace`, `_knowledge_ingest_folder`.
- Why it matters: alternate clients or refactors can rely on contract-valid vocabulary that never occurs, and all four hand-maintained copies must keep validating it.
- Suggested scope: keep protocol-v1 compatibility, and either mark the vocabulary as reserved or unsupported in the contract and its tests, or implement the Python-owned behavior behind it. No new frontend-owned knowledge path.
- Dependencies / blockers: a narrow product decision on whether raw protocol clients are supported.
- Acceptance criteria: contract, handlers, fixtures and tests describe one behavior, and no advertised method fails by design without being marked as such.
- Related items: INV-011, INV-015, INV-018, FAIL-013.
- Status: Not started

### BACKLOG-015 — Preserve `/init` exclusions in later sync scans

- Priority: P2
- Problem: `init_workspace` excludes the top-level `app/`, but `diff_folder` calls `list_diff`, which has no exclusion parameter. A later `/sync <host-root>` therefore reports the excluded files as missing from the store.
- Evidence: `app/agent/ingest.py::init_workspace`, `diff_folder`; `app/rag/sync.py::list_diff`; ASM-020. Not reproduced live.
- Why it matters: noisy sync output hides real drift and invites indexing application code.
- Suggested scope: carry the same explicit exclusion into comparison and prune previews; add one deterministic path-level regression.
- Dependencies / blockers: decide whether callers may override the default workspace exclusion, without adding a generic policy framework.
- Acceptance criteria: after a no-argument `/init`, `/sync <host-root>` omits the excluded `app/` paths and still reports a genuinely new allowed file.
- Related items: ASM-020.
- Status: Not started

### BACKLOG-016 — Make folder-prefix search complete or explicitly bounded

- Priority: P2
- Problem: `rag.search` retrieves only the global top `3 * k` hits before applying `folder_prefix`.
- Evidence: `app/rag/api.py::search`; ASM-021.
- Why it matters: a scoped search can look authoritative while missing better scoped matches.
- Suggested scope: filter within the prefix before limiting, or expose and test a deliberate bounded-search contract.
- Dependencies / blockers: confirm the smallest Chroma-supported filter that preserves source and folder normalization.
- Acceptance criteria: a deterministic test returns the top `k` prefix matches despite more than `3 * k` higher-ranked out-of-prefix chunks, or the API reports its bound.
- Related items: ASM-021.
- Status: Not started

### BACKLOG-019 — Repair references to deleted documentation and retired behavior

- Priority: P2
- Problem: eight relative links point at files deleted on 2026-10-15 or later (`SKILLS_GUIDE.md`, `agent/extensions/README.md`, the desktop-interaction build log). Several strings still describe retired behavior:
  - "/citation off" and "persistent" Skill wording;
  - bash prompting every call;
  - `ingest.py` described as a plain RAG wrapper.
- Evidence: FAIL-014 lists each file. The removed desktop plan log records that the stale `SKILLS_GUIDE` links were seen and deliberately left. The RAG store notes were already corrected in `d74065f`.
- Why it matters: contributors and agents follow dead links or troubleshoot against removed interfaces.
- Suggested scope: a documentation-only pass over the listed files. Either drop or redirect each link, or restore the deleted guide content the user still wants. Correct the listed strings without changing behavior.
- Dependencies / blockers: the user removed these documents in an annotated cleanup, so confirm before restoring any of them.
- Acceptance criteria: a relative-link check over tracked Markdown reports no missing targets, and none of the listed retired phrases remain in code comments or docs.
- Related items: INV-019, FAIL-014.
- Status: Not started

### BACKLOG-021 — Isolate the MCP log cache in the pytest suite

- Priority: P2
- Problem: tests that prepare MCP connections write run headers into the user's real `$XDG_CACHE_HOME/agent-mcp/*.stderr.log`.
- Evidence: FAIL-023 (incident I1, 2026-10-19); `app/tests/conftest.py` isolates only `AGENT_LOG_DIR`.
- Why it matters: test noise pollutes the logs used to analyze real turns, and the suite writes outside its temporary roots.
- Suggested scope: an autouse fixture that points `XDG_CACHE_HOME` at a per-session temp directory, mirroring `_isolated_diagnostic_log_dir`.
- Dependencies / blockers: none known; keep the tests that set their own `XDG_CACHE_HOME`.
- Acceptance criteria: a full run leaves the real `~/.cache/agent-mcp` byte-for-byte unchanged, verified by comparing a metadata fingerprint before and after.
- Related items: INV-028, FAIL-023.
- Status: Not started

### BACKLOG-022 — Make a failed Stop recoverable, or say that a restart is required

- Priority: P2
- Problem: after a Stop cleanup error, or a turn still pending, the service stays `BUSY_TURN` and Retry Stop replays the cached error, while the README promises Retry Stop.
- Evidence: FAIL-022; `service.py::_session_turn` finally block and `_session_stop`; `test_failed_stop_cleanup_keeps_new_turn_blocked`.
- Why it matters: the user can be stuck with no working control except restarting the backend.
- Suggested scope: either let a repeated Stop retry the outstanding cleanup and clear the busy state on success, or make the UI and README state that a backend restart is the recovery.
- Dependencies / blockers: a product decision on which recovery to support.
- Acceptance criteria: with an injected cleanup failure, a test shows the chosen recovery working, and the README matches it.
- Related items: INV-027, ASM-031, FAIL-022.
- Status: Not started

### BACKLOG-023 — Explain Ask denials caused by approval limits

- Priority: P2
- Problem: under Ask, operations whose parameter summary exceeds 8 KiB, or looks secret, are denied without a prompt and reported as "denied or expired".
- Evidence: FAIL-025; `service.py::_operation_approval`.
- Why it matters: legitimate large operations (for example `/prune --yes` with many paths) fail confusingly.
- Suggested scope: return a specific, visible reason, or show a bounded summary in the approval, without weakening the secret filter.
- Dependencies / blockers: keep payloads within protocol limits and the secret rules.
- Acceptance criteria: a test with a summary over 8 KiB yields an explicit, distinguishable message or a valid bounded approval prompt, and no unapproved execution.
- Related items: INV-018, FAIL-025.
- Status: Not started

### BACKLOG-024 — Bound startup of non-web_search MCP servers

- Priority: P2
- Problem: GitHub and drop-in MCP servers load sequentially through `client.get_tools()` with no timeout, so one stuck server holds session creation indefinitely.
- Evidence: `app/agent/mcp.py::load_mcp_tools_with_families`; plan exclusion X10 ("existing problem; the old plan's limit only covers web_search").
- Why it matters: an installed drop-in can block every new Desktop session.
- Suggested scope: apply a startup bound analogous to web_search discovery, and report the timed-out server as unavailable.
- Dependencies / blockers: choose a bound that does not reject slow but healthy servers.
- Acceptance criteria: a test with a server that never answers startup shows session creation finishing within the bound, with a diagnostic, while other servers still load.
- Related items: INV-031, ASM-013.
- Status: Not started

### BACKLOG-025 — Prove or enforce the diagnostic-log privacy contract

- Priority: P2
- Problem: the README says logs exclude message content, tool arguments and raw queries. On exception paths, though, logged tracebacks can include `ToolInvocationError` text with tool kwargs and OpenRouter error bodies of up to 10,000 characters.
- Evidence: INV-028 enforcement gap; `graph.py::_tool_error_to_message` (logs with `exc_info`); `agent/diagnostics.py` (pattern-based redaction only). Inferred from source, not reproduced.
- Why it matters: thesis experiments and privacy statements rely on what the logs contain.
- Suggested scope: tests that drive an invalid-argument tool call and a provider error and assert the log content; then either sanitize those paths or narrow the README claim.
- Dependencies / blockers: keep incident references and tracebacks useful for debugging.
- Acceptance criteria: the tests show that no tool-argument value or provider body appears in `desktop-backend.log`/`cli.log`, or the README states exactly what is retained.
- Related items: INV-028.
- Status: Not started

## Blocked or research items

### BACKLOG-017 — Serialize canonical conversation writes across processes

- Priority: Research
- Problem: conversation saves verify a fingerprint and then `os.replace`; there is no lock or compare-and-swap, and nothing prevents two desktop instances on one history directory.
- Evidence: `app/agent/conversations/repository.py::save`; `session.py::_recover_interrupted_turn`; ASM-022; no single-instance plugin in `Cargo.toml`.
- Why it matters: two processes could lose a successful transition, or interrupt live pending work.
- Suggested scope: only if multi-instance use is demonstrated, add one narrow per-conversation Linux lock or guarded replace, plus a multiprocessing regression; alternatively, enforce a single instance.
- Dependencies / blockers: AGENTS.md rejects hardening without a demonstrated problem, and none is recorded.
- Acceptance criteria: concurrent transitions can never both report success while losing one, and opening a genuinely active pending turn never recovers it prematurely.
- Related items: INV-006, ASM-016, ASM-022.
- Status: Blocked

## Recently resolved or removed

IDs stay listed here so they are not reused. Durable lessons live in the referenced items.

| ID | Outcome | Lesson now lives in |
|---|---|---|
| BACKLOG-020 | Resolved 2026-10-23 by user decision: `/app/store/` is ignored in the workspace `.gitignore` (`c12470f`); the plan-log stubs and `AgentConfig.plan_logs_dir` were removed (`73c8db1`) | INV-029, FAIL-021 |
| BACKLOG-009 | Removed 2026-10-23: the README prose about the academic Skill's bash prohibition was deleted | ASM-011 (prose versus binding) |
| BACKLOG-010 | Removed 2026-10-23: the per-project catalog reconciles from JSON on every open and list, so lost registrations self-heal | ASM-016 (residual resurrected-ID failure) |
| BACKLOG-013 | Removed 2026-10-23: the stale Skill paragraphs went with the README rewrite and the deletion of `SKILLS_GUIDE.md` | BACKLOG-019, FAIL-014 |
| BACKLOG-003 | Resolved 2026-09-13: applied-Skill hash precheck before activation | INV-013, FAIL-005 |
| BACKLOG-004 | Resolved 2026-09-13: earliest-year ambiguity | INV-014, FAIL-007 |
| BACKLOG-005 | Resolved 2026-09-13: extension apply flock | FAIL-006 |
| BACKLOG-007 | Resolved: persistent generic Skill selection and task modes removed (`78589e9`) | INV-019 |
| BACKLOG-008 | Resolved 2026-09-13: save-reporting characterization (now 12 statuses) | ASM-014 |
| BACKLOG-012 | Resolved: prompt-first canonical lifecycle | INV-006 |
| BACKLOG-014 | Resolved 2026-09-13: single-turn Citation (now also `@citation` and Stop) | INV-019, FAIL-015 |
| BACKLOG-018 | Resolved: legacy conversation staging removed with the importer | ASM-023 |

The user deleted the deferred multi-level Thinking Effort card (`issue/09-…`) from the tree in `9189f71`. No retained record schedules or authorizes that work; its history is recoverable from `9189f71^`.
