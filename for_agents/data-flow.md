# Data Flow

Freshness: current source/contract/test-definition inspection on 2026-09-13 at `a88d44d` covers Skill/Citation/installer execution, extension apply/activation, Desktop controls/menu and completed replay; RAG prune/search anchors received a focused check. Other claims retain 2026-09-05 (`9745fd1`) evidence, or 2026-09-06 (`743aaaf`) for unchanged Desktop/canonical presentation claims. No application checks were rerun; see [audit coverage](README.md#audit-coverage).

## Primary flows

### Flow: Interactive agent turn

- Trigger / input: non-slash user text passed to ChatSession.turn_outcome.
- Output / side effect: one finalized TurnOutcome plus canonical pending/terminal JSON; tools may have side effects before finalization.
- Steps:
  1. CLI/session — validate runtime and serialize the turn with the session async lock.
  2. Session — assemble system, latest canonical completed-turn, current transient-or-Citation Skill, tool-availability, conversation-root, and citation-source context.
  3. Normal graph or extended orchestrator — invoke OpenRouter, bind the effective tools, and execute allowed tool calls.
  4. turns.execution — normalize streamed messages, tool calls, trace events, answer, and recovery reason into GraphTurnResult.
  5. ChatSession.finalize_and_record — reject tool-protocol artifacts, apply citation gate/render, collect safe metrics, commit canonical completed JSON, then update TurnJournal diagnostics.
  6. ConversationRepository — remains the sole transcript writer, with canonical JSON as the sole active authority; the latest ten completed context-eligible turns are supplied automatically.
- State or ownership transitions: accepted input becomes pending before provider/tool work; model draft becomes finalized text before the completed transition and terminal outcome.
- Error / retry / rollback behavior: empty model output retries twice; invalid final output gets one repair then deterministic fallback. Raised graph/provider exceptions first attempt to transition the accepted turn to failed; if that persistence attempt also fails, the original error is preserved and the canonical turn can remain pending until restart exposes it as interrupted. Neither state is replayed automatically, and rerunning requires an explicit same-ID retry. Tool side effects have no rollback.
- Invariants involved: INV-004, INV-005, INV-006.
- Evidence: app/agent/session.py; app/agent/graph.py; app/agent/turns; app/tests/test_turn_finalizer.py.
- Confidence: Confirmed.

### Flow: RAG repository ingest, retrieval, sync, and prune

- Trigger / input: CLI or desktop-composer `/init`, `/ingest`, `/sync`, `/prune`; `rag.cli.ingest`; or direct retrieval/protocol APIs.
- Output / side effect: folder_meta.json, raw.json, Chroma knowledge vectors, retrieval DTOs, or deletion of root-scoped orphan PIDs.
- Steps:
  1. ingest_repo — resolve the canonical root and derive a deterministic root namespace.
  2. collect_folders — enumerate supported files while applying skip names and relative-path exclusions.
  3. _tag_folders — send folder names, filenames, and limited previews to OpenRouter and collect tags/summaries.
  4. ingest_repo — merge namespaced folder metadata, read UTF-8 non-empty files, tokenize chunks, and attach root/path/category metadata.
  5. DocumentStore — delete current non-empty folder PIDs, then write JSON and Chroma in batches; raw JSON is atomically replaced at deferred-batch exit.
  6. search — embed a query with Ollama and use Chroma; list_chunks/get_context use raw JSON; explore uses folder metadata.
  7. list_diff/prune_orphans — compare presence for the same root namespace and delete orphan PIDs from Chroma/raw JSON.
  8. Desktop composer — route the four maintenance commands through injected Python-owned operations with absolute Linux path, protected-root, and preview checks; raw protocol reads remain separate.
- State or ownership transitions: source files remain external and immutable; derived chunks are owned by the local store. raw.json owns full-content enumeration, Chroma owns semantic lookup, and folder_meta.json owns inventory.
- Error / retry / rollback behavior: hard tagger failures abort before metadata/chunks; malformed tag text falls back. `folder_meta.json` is directly truncated/rewritten, and a malformed/unreadable read falls back to `{}` before the next write. Later Chroma failures can leave partial vector state while raw JSON uses atomic replacement and rolls back its local deferred batch. Re-run ingest is documented recovery. Prune and empty re-ingest have confirmed stale-state bugs. Direct `knowledge.init_workspace` and `knowledge.ingest_folder` protocol methods deliberately fail; the supported GUI path is the composer command route (FAIL-013).
- Invariants involved: INV-003, INV-007, INV-008, candidate INV-012, and INV-018 for prune confirmation.
- Evidence: app/rag/cli/ingest.py; app/rag/api.py; app/rag/store; app/rag/sync.py; app/tests/rag.
- Confidence: Confirmed, including focused offline reproductions for FAIL-001 and FAIL-002.

### Flow: One-shot Skill and Citation invocation

- Trigger/input: generic `/<skill-name> <prompt>` or shared static `/citation <prompt>` in CLI/Desktop.
- Steps: shared parser retains original display command and semantic trailing prompt; session turn lock checks canonical identity and writes pending with effective thinking mode; runtime loads from the startup catalog (applied Skills recheck their hash); transient instructions/tools govern the turn; common finalization gates and persists output before returning `final_only`.
- Citation: use Normal and fresh registry for this task, clear registry/runtime on success, error or cancellation, then restore the prior thinking mode. Later citation tasks need a fresh receipt and may reuse the saved bundle; ordinary following turns do not inherit citation authority.
- Installer-to-Skill switch: load the target before cleanup; cleanup conflict yields visible host-derived text plus preserved backup path without executing the target graph. Successful cleanup restores the previous mode before generic execution; Citation still runs Normal.
- Replay/error: completed exact identity returns canonical output before loading/cleanup; Desktop defers Citation availability only for a completed candidate and still calls canonical validation. Failed/interrupted work requires a currently valid runtime and explicit retry. Runtime rejection never grants new tool authority.
- Invariants: INV-004, INV-005, INV-006, INV-013, INV-019, INV-024.
- Evidence: `ChatSession.turn_outcome` / `_run_one_shot_skill_turn`; shared slash handler; `DesktopService._session_turn`; Citation activation/e2e and completed replay test definitions. Confirmed source/contracts at `a88d44d`; not executed this pass.

### Flow: Citation discovery, verified save, and rendering

- Trigger/input: one `/citation <prompt>` task; multiple tool calls may occur within it.
- Steps: Citation policy creates a task registry/service; discovery ranks provider records without registering them; save resolves intents before writes, authority-checks identities/BibTeX, stages and atomically publishes each bundle, then registers receipts; ToolMessage content/artifact expose the same per-item outcome; finalization gates registry-backed markers and renders the final answer before canonical completion.
- Earliest resolution: deduplicate eligible identities, return `earliest_year_missing` if all years are absent and `earliest_year_tie` for tied known minima. Authority fallback does not override these decisions. A unique known minimum still wins with undated alternatives; no finer chronology is proven.
- Errors/ownership: provider/verification/storage failures produce per-item outcomes; batches can partly succeed and tool side effects have no turn-wide rollback. Identity conflict fails closed. Task cleanup releases registry/service; already saved bundles survive. A later task cannot cite merely because an earlier task had a receipt.
- Save reporting: the model receives authoritative outcomes; the host does not replace Citation prose with a forced status answer. Deterministic four-outcome journeys characterize compliance, not arbitrary live-model truthfulness (ASM-014).
- Invariants: INV-005, INV-010, INV-014, INV-019.
- Evidence: `app/skills/citation/SKILL.md`, `resolution.py::decide_resolution`, `service.py::save`, `storage.py`, `CitationSessionPolicy`, `test_citation_e2e.py`/resolution/authority tests. Changed resolution/session boundaries Confirmed by source at `a88d44d`; unchanged provider/storage internals retain earlier evidence.

### Flow: Drop-in extension apply and next-session loading

- Trigger / input: Skill/MCP folders under the drop-in root plus CLI or desktop `/Extension-Management` status/preview/apply/restart flow.
- Output / side effect: validated managed copies, registry revision, status report, and future-session Skill catalog/MCP specs.
- Steps:
  1. discovery — scan regular files, validate metadata/descriptors, enforce limits/containment, and hash the bundle.
  2. manager preview — compare desired state with registry and ask the private management Skill/model for an explanation; host validates the plan.
  3. confirmation/apply — recheck preview/registry/source, require exact MCP binding approvals, copy content-addressed bundles, and atomically replace registry JSON. Desktop performs this inside a prompt-first durable display-only turn whose stored input is a sanitized digest.
  4. restart — load_extension_startup revalidates registry, installed hash, descriptors, and built-in collisions.
  5. session startup — merge built-in/applied Skills, load available MCP tools, and record diagnostics.
  6. invocation — load Skill instructions/manifest/resources from the catalog path and resolve required/optional tools for a later one-shot command; Citation uses the shared one-turn CLI/Desktop lifecycle.
  7. desktop trust UI — require an explicit decision for every exact MCP binding hash, consume the preview once, and restart the Rust-owned child before observing the applied revision.
- State or ownership transitions: untrusted drop-in becomes scanned desired state, then approved managed state, then a loaded runtime only in a new session.
- Error / retry / rollback behavior: invalid/rebound roots disable deletion; stale preview or changed source aborts apply; individual failures are reported. Desktop parses and verifies the durable result, replays a completed same-turn result after restart without reapplying, and restores a crash-pending apply as non-retryable interrupted. A process-local guard plus Linux nonblocking flock on the stable state-root `.apply.lock` covers revision reread through durable registry write; busy/stale callers must preview again. Startup retains the applied hash and activation rechecks the bundle before loading. Check-to-read races remain outside that guarantee.
- Invariants involved: INV-004, INV-006, INV-009, INV-018, INV-013.
- Evidence: app/agent/extensions; app/agent/startup.py; app/agent/skills/runtime.py; `app/agent/desktop/service.py::_extensions_apply`; extension apply/crash tests; [historical Issue 06](https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/bc2c94d40562e9606a9872bc922a36423b6a10a2/issue/06-extension-skill-post-startup-integrity.md) and [historical Issue 07](https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/bc2c94d40562e9606a9872bc922a36423b6a10a2/issue/07-extension-apply-cross-process-race.md).
- Confidence: Confirmed current lock/hash source; former tamper probe is historical and FAIL-005 is mitigated. Current multiprocessing and activation tests are definitions inspected, not runs in this pass.

### Flow: Explicit ZIP Skill installation

- Trigger/input: `/skill-installer install <Linux ZIP>` or the narrowly recognized explicit natural-language installer request; subsequent ordinary replies continue only its host-bound pending request.
- Steps: session writes pending Normal-mode metadata; `SkillInstaller.begin` binds actual user source/update intent, ZIP hash, registry revision and candidate; `skill_install status/preview` returns required choices; ordinary Bash uses the safe ZIP helper to prepare the chosen original bundle; host verifies prepared bytes and update permission before staging; selected-key manager preview/apply excludes other Skill/MCP changes and deletion.
- Output/ownership: registry-confirmed per-item outcome, original ZIP and successful expanded source retained, managed copy available to a newly materialized session. Existing session catalog stays unchanged. Installer final text comes from host results, unlike model-authored Citation prose.
- Error/cleanup: shell denial/error, cancellation, stale binding or apply failure settles host work before cleanup; restore only unchanged unapplied staged source. Later edits/unsafe cleanup preserve the source and backup and report a conflict. Successful installation, cancellation, explicit replacement or no useful host action clears authority and restores prior thinking choice; pending clarification stays in memory only.
- Invariants: INV-006, INV-009, INV-019, INV-024.
- Evidence: `ChatSession._skill_install_action` / `_run_installer_turn` / `clear_skill_installer`; `SkillInstaller`; `zip_bundle.py`; manager/adherence/runtime test definitions. Confirmed source/contract at `a88d44d`; no installation performed.

### Flow: Desktop backend startup, requests, and shutdown

- Trigger / input: a user may run root `python main.py`, which delegates to `npm run tauri dev`; the resulting React client calls one of the five Tauri backend commands.
- Output / side effect: one Rust-managed Python child generation, correlated protocol events/results, and a truthful lifecycle snapshot or shutdown report.
- Steps:
  1. Source launcher — optional root `main.py` changes only the child working directory to `app/desktop` and starts the existing Tauri development command; Tauri's configured development command starts Vite.
  2. React `BackendClient` — validate/build a protocol-v1 request and invoke Tauri.
  3. Rust supervisor — require active Conda environment `app`, resolve the source checkout, and spawn `<CONDA_PREFIX>/bin/python -m agent.desktop.server` with repository cwd and `PYTHONPATH=app`.
  4. Python server — revalidate Linux/Conda, redirect incidental stdout to stderr, emit `backend.ready`, and accept bounded NDJSON lines. New sessions load MCP by default unless the request explicitly opts out; React omits the field to delegate that default.
  5. Rust pipe readers — enforce UTF-8/line size/origin/order, correlate events and one terminal result, and emit bounded Tauri events to React. Normal requests wait on channel completion without a fixed elapsed-time deadline; startup and shutdown retain bounded waits.
  6. Shutdown — Rust sends `runtime.shutdown`; Python refuses while unsafe work is active, closes the session without a transcript-flush lifecycle, emits shutdown state, and exits. Rust reports whether the child exited gracefully or was forced.
- State or ownership transitions: Rust owns child/generation/pending-request state; Python owns session and stores; React owns presentation state and discards stale-generation events.
- Error / retry / rollback behavior: wrong runtime or startup timeout degrades without a child; malformed output, pipe/channel closure, child exit, or bounded shutdown failure clears pending work and stops the generation. A live child that neither responds nor closes its output has no automatic normal-request timeout and requires user-driven shutdown/restart. Stderr content is drained but only counts are retained by Rust.
- Invariants involved: INV-011, INV-015, INV-017, INV-020.
- Evidence: `app/desktop/src-tauri/src/backend.rs`; `app/agent/desktop/server.py`; `app/desktop/src/backend.ts`; lifecycle tests.
- Confidence: Confirmed for source checkout; installer/bundle behavior Unknown.

### Flow: Desktop conversation creation, turn presentation, and restoration

- Trigger / input: project/sidebar selection, new conversation, control change, or composer text. Outside a matching slash menu plain Enter submits; inside the menu it only inserts the selected command. Shift+Enter inserts a newline; IME-composing Enter never submits.
- Output / side effect: selected Python `ChatSession`, schema-validated complete transcript DTOs, a finalized answer/command result, and eventual durable conversation state.
- Steps:
  1. Catalog — `DesktopProjectCatalog` bootstraps one local project, reconciles healthy canonical JSON summaries, and stores only ordered session IDs.
  2. Create/select — selecting a saved session loads canonical JSON. If the catalog entry has no corresponding canonical file, selection returns conversation unavailable; old Chroma/Plan sources are not read or imported.
  3. Switch — validate the canonical target before replacing the current session; no conversation-history flush exists. In-process thinking and Bash permission controls are snapshot-restored while the backend lives; new sessions/restart default to Normal/ask. Session replacement clears installer state before capturing controls; cleanup conflict preserves the existing session/source.
  4. Turn — Python first parses and validates composer routing; after acceptance it writes the original prompt as canonical pending before executing an allowlisted display-only command or starting provider/tool work.
  5. Finalize — Python validates and finalizes the answer, commits the terminal canonical transition, then returns the authoritative result; first-prompt registration follows the durable pending write.
  6. Present — while work is pending, Python may emit bounded stage/tool/trust events without answer text. React merges restored, live, and pending records by logical session/turn identity; a same-ID pending retry replaces a stale failed/interrupted card. After finalization and canonical completion, Python returns one authoritative result with `streamKind=final_only` and `chunkCount=0`; React replaces the pending projection and never assembles an answer preview.
- State or ownership transitions: original input moves from draft to durable pending, then to completed/failed/interrupted in the same canonical JSON. The latest ten completed context-eligible turns are derived at prompt time rather than moved between stores.
- Error / retry / rollback behavior: malformed or missing canonical transcripts block selection and retain the current session; catalog failure returns a pending registration that can be retried without replaying the model turn. When a backend failure reports both `accepted=true` and `persisted=true`, React reloads the catalog and, under project/session/generation guards, the selected transcript so a durable first-turn failure remains visible/selectable. If that refresh fails, the original error remains and the UI adds a saved-but-refresh-failed notice. Unconfirmed persistence does not trigger the refresh. Provider failures require explicit same-ID retry; if a failed transition cannot be published, restart converts the leftover pending turn to interrupted rather than auto-replaying it.
- Invariants involved: INV-005, INV-006, INV-011, INV-016, INV-017, INV-022.
- Evidence: `app/agent/desktop/catalog.py`; `app/agent/desktop/service.py::_with_turn_lifecycle`; `app/agent/conversations`; `app/desktop/src/App.tsx::isPersistedTurnFailure`; `app/desktop/src/conversations.ts::mergeConversationTurns`; conversation/lifecycle/answer-stream tests.
- Confidence: Confirmed.

### Flow: Desktop command menu and Bash permissions

- Input: session create/select returns Python's dispatchable `slashCommands` and effective `bashPermissionMode`. React scopes catalog ownership to generation/project/session; typing a slash prefix opens the menu, insertion changes only the draft, and submission still routes through Python validation.
- Permission transition: idle `session.set_bash_permission` accepts ask/bypass. React displays the acknowledged value only for the current generation/session. Active turn or approval blocks mode changes. Same-process switching retains each conversation choice; new sessions/restart reset ask.
- Bash execution: the existing Python tool invokes `_desktop_bash_approval`. It denies calls without a live active request/turn/event loop; explicit bypass then authorizes execution without events or prompt-text display filtering. Ask stages an exact command/request/turn/expiry approval and requires a one-use affirmative decision before invoking the runner.
- Errors/recovery: unknown/reused/expired/mismatched decisions, crash/shutdown/dismissal and ask-path unsafe display context deny execution. Bypass is intentionally broader for display context; it does not grant frontend shell capability or replace prune/MCP/installer authorization.
- Invariants: INV-004, INV-011, INV-015, INV-018, INV-022, INV-023.
- Evidence: shared JSON/TS/Rust protocol; `DesktopService._session_snapshot` / `_session_set_bash_permission` / `_desktop_bash_approval`; `SlashComposer` and `trust.tsx`; current service/trust/menu tests. Confirmed source/contract; no real shell/native action this pass.

## State and ownership transitions

| State | Owner while active | Transition | Durable destination |
|---|---|---|---|
| User/model turn | ChatSession and graph | pending JSON before execution; completed JSON before success; failed transition attempted before error, with pending→interrupted fallback | canonical conversation JSON |
| RAG source file | User filesystem | collect/tag/chunk/index | raw.json, Chroma, folder_meta.json |
| Citation discovery record | Citation provider hub/tool call | authority verification and canonical save | cite bundle plus session SourceRegistry |
| Extension drop-in | User drop-in root | validate/approve/install/restart | private managed copy and registry |
| Skill/Citation/installer runtime | Startup catalog and session | one-shot load/cleanup; installer may retain host-bound pending clarification | No generic durable Skill selection; original resources remain in bundle |
| Desktop child/request | Rust supervisor and Python `RequestContext` | ordered events then one result | wire only; underlying Python side effects persist separately |
| Desktop conversation membership | `DesktopProjectCatalog` | first durable pending prompt or later reconciliation retry | `desktop-projects.json` |
| Desktop conversation content | Python session/repository | write-through pending and terminal transitions | canonical conversation JSON only; old Chroma/Plan sources are ignored and left untouched |

## Error, retry, and recovery paths

- Agent graph: two identical retries for truly empty upstream output; one tool-free repair for unsafe final content; deterministic fallback after exhaustion.
- Extended thinking: candidate failures/timeouts can be isolated, malformed aggregation falls back, but raised aggregator/reviewer/reviser provider exceptions are not consistently contained.
- Conversations: the canonical repository is the sole active writer, writes accepted prompts before provider/tool execution, and makes completed state durable before success exposure. Provider failures attempt a failed transition; if that write also fails, the pending turn remains recoverable as interrupted on reopen. Neither failed nor interrupted work is replayed automatically; latest context is the fixed latest-ten completed eligible view. Old Chroma/Plan records are not read or imported.
- RAG: raw JSON writes are atomic and fingerprint-changing concurrent rewrites fail loudly; the three RAG persistence surfaces are not transactional. Re-run ingest is the documented recovery for partial writes.
- Citation: network retries/rate limiting live in provider adapters; identity and storage conflicts fail closed; a batch reports each saved/reused/failed item.
- Extensions: startup skips invalid entries and reports diagnostics; apply requires a new preview after stale state. Cooperating extension applies use a Linux file lock; activation detects a changed approved bundle before loading. Neither mechanism protects unrelated stores or closes every concurrent-filesystem window.
- Desktop: malformed child output, pipe/channel closure, or child exit terminates the generation; frontend reducers reject stale-generation state. Normal requests have no elapsed-time deadline, while shutdown retains a bounded acknowledgment/exit path that can fail pending work. Shutdown/EOF make cancellation visible and do not report a forced exit as successful persistence.
- Desktop trust: unknown, reused, expired, cross-turn, unsafe, dismissed, crash/restart, or shutdown Bash decisions default to denial. Prune and extension previews are one-use and rechecked before mutation.

## Unverified flows

- Live provider and real persistent-store paths were not run in this audit.
- Multiple concurrently launched desktop applications sharing `persist_dir`, or canonical conversation files were not exercised.
- A permanently live but non-responsive Python request has no automatic inactivity detector; only explicit shutdown/restart and transport/process failure paths are covered.
- No integrated stress test covers all RAG read/write overlaps accepted by the concurrent protocol server.
- Installer/wheel/bundled desktop asset lookup is unsupported and unverified; only Linux source checkout is documented.
- No failure-injection test covers Chroma mid-batch failure or raised extended-thinking provider exceptions; extension multiprocessing regressions now exist.
- The current subprocess crash checks exercise the real Python NDJSON child with fixture-owned state, but do not prove exact native `720x560`/200% zoom layout or live provider/user-store behavior. The broader native behavioral journey is recorded as passed separately.
