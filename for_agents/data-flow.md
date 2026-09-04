# Data Flow

## Primary flows

### Flow: Interactive agent turn

- Trigger / input: non-slash user text passed to ChatSession.turn_outcome.
- Output / side effect: one finalized TurnOutcome plus canonical pending/terminal JSON; tools may have side effects before finalization.
- Steps:
  1. CLI/session — validate runtime and serialize the turn with the session async lock.
  2. Session — assemble system, latest canonical completed-turn, active-skill, tool-availability, conversation-root, and citation-source context.
  3. Normal graph or extended orchestrator — invoke OpenRouter, bind the effective tools, and execute allowed tool calls.
  4. turns.execution — normalize streamed messages, tool calls, trace events, answer, and recovery reason into GraphTurnResult.
  5. ChatSession.finalize_and_record — reject tool-protocol artifacts, apply citation gate/render, collect safe metrics, commit canonical completed JSON, then update TurnJournal diagnostics.
  6. ConversationRepository — remains the sole transcript authority; the latest ten completed context-eligible turns are supplied automatically.
- State or ownership transitions: accepted input becomes pending before provider/tool work; model draft becomes finalized text before the completed transition and terminal outcome.
- Error / retry / rollback behavior: empty model output retries twice; invalid final output gets one repair then deterministic fallback. Raised graph/provider exceptions durably transition the accepted turn to failed; explicit same-ID retry is required. Tool side effects have no rollback.
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
- Error / retry / rollback behavior: hard tagger failures abort before metadata/chunks; malformed tag text falls back. Later Chroma failures can leave partial vector state while raw JSON rolls back and folder metadata remains. Re-run ingest is documented recovery. Prune and empty re-ingest have confirmed stale-state bugs. Direct `knowledge.init_workspace` and `knowledge.ingest_folder` protocol methods deliberately fail; the supported GUI path is the composer command route (FAIL-013).
- Invariants involved: INV-003, INV-007, INV-008, candidate INV-012, and INV-018 for prune confirmation.
- Evidence: app/rag/cli/ingest.py; app/rag/api.py; app/rag/store; app/rag/sync.py; app/tests/rag.
- Confidence: Confirmed, including focused offline reproductions for FAIL-001 and FAIL-002.

### Flow: Citation discovery, verified save, and rendering

- Trigger / input: active citation Skill invokes citation_workflow search/save/sources/source/explain.
- Output / side effect: discovery ToolMessage, per-item SaveBatchOutcome, canonical citation bundle, session SourceRegistry entry, and rendered citations/bibliography.
- Steps:
  1. CitationSessionPolicy — lazily creates a session-scoped service and registry; activation forces normal thinking.
  2. search — concurrently query Crossref/DataCite and optional OpenAlex; normalize/rank records but do not register them.
  3. save — resolve all WorkIntents, exact-lane identifiers or descriptive matches, then authority-refetch DOI records or use allowlisted non-DOI authority metadata.
  4. identity/storage — canonicalize BibTeX/identity, fail on conflicts, lock the source slot, stage/fsync/rename the two-file bundle, then register trusted receipts.
  5. tool — return the strict per-item result in both model-visible content and artifact.
  6. finalization — validate registry-backed markers before persistence and render valid markers/bibliography.
- State or ownership transitions: discovery records are ephemeral; verified bundles persist on disk; citable SourceRefs live only in the active session registry and are cleared on deactivation.
- Error / retry / rollback behavior: provider failures can be partial; all resolution happens before the first batch write, but eligible items are written individually so a batch can partially succeed. Identity conflict, invalid BibTeX, or corrupt existing bundle fails closed. Final prose is not overwritten to force save-result truthfulness.
- Invariants involved: INV-005, INV-010, candidate INV-014.
- Evidence: app/skills/citation/service.py; storage.py; tool.py; app/agent/skills/citation/session_policy.py; app/skills/citation/README.md.
- Confidence: Confirmed, with FAIL-007 for earliest ties.

### Flow: Drop-in extension apply and next-session loading

- Trigger / input: Skill/MCP folders under the drop-in root plus CLI or desktop `/Extension-Management` status/preview/apply/restart flow.
- Output / side effect: validated managed copies, registry revision, status report, and future-session Skill catalog/MCP specs.
- Steps:
  1. discovery — scan regular files, validate metadata/descriptors, enforce limits/containment, and hash the bundle.
  2. manager preview — compare desired state with registry and ask the private management Skill/model for an explanation; host validates the plan.
  3. confirmation/apply — recheck preview/registry/source, require exact MCP binding approvals, copy content-addressed bundles, and atomically replace registry JSON.
  4. restart — load_extension_startup revalidates registry, installed hash, descriptors, and built-in collisions.
  5. session startup — merge built-in/applied Skills, load available MCP tools, and record diagnostics.
  6. activation — load Skill instructions/manifest/resources from the catalog path and resolve required/optional tools.
  7. desktop trust UI — require an explicit decision for every exact MCP binding hash, consume the preview once, and restart the Rust-owned child before observing the applied revision.
- State or ownership transitions: untrusted drop-in becomes scanned desired state, then approved managed state, then a loaded runtime only in a new session.
- Error / retry / rollback behavior: invalid/rebound roots disable deletion; stale preview or changed source aborts apply; individual failures are reported. A process-local lock serializes one process only. Installed Skill content is not re-hashed at activation.
- Invariants involved: INV-004, INV-009, INV-018, candidate INV-013.
- Evidence: app/agent/extensions; app/agent/startup.py; app/agent/skills/runtime.py; issue/02 and issue/04.
- Confidence: Confirmed, including focused tamper reproduction for FAIL-005.

### Flow: Desktop backend startup, requests, and shutdown

- Trigger / input: React calls one of the five Tauri backend commands.
- Output / side effect: one Rust-managed Python child generation, correlated protocol events/results, and a truthful lifecycle snapshot or shutdown report.
- Steps:
  1. React `BackendClient` — validate/build a protocol-v1 request and invoke Tauri.
  2. Rust supervisor — require active Conda environment `app`, resolve the source checkout, and spawn `<CONDA_PREFIX>/bin/python -m agent.desktop.server` with repository cwd and `PYTHONPATH=app`.
  3. Python server — revalidate Linux/Conda, redirect incidental stdout to stderr, emit `backend.ready`, and accept bounded NDJSON lines.
  4. Rust pipe readers — enforce UTF-8/line size/origin/order, correlate events and one terminal result, and emit bounded Tauri events to React.
  5. Shutdown — Rust sends `runtime.shutdown`; Python refuses while unsafe work is active, closes the session without a legacy transcript flush, emits shutdown state, and exits. Rust reports whether the child exited gracefully or was forced.
- State or ownership transitions: Rust owns child/generation/pending-request state; Python owns session and stores; React owns presentation state and discards stale-generation events.
- Error / retry / rollback behavior: wrong runtime degrades without a child; malformed output or timeouts fail pending requests and stop the generation; unexpected exit becomes crashed and requires explicit restart. Stderr content is drained but only counts are retained by Rust.
- Invariants involved: INV-011, INV-015, INV-017.
- Evidence: `app/desktop/src-tauri/src/backend.rs`; `app/agent/desktop/server.py`; `app/desktop/src/backend.ts`; lifecycle tests.
- Confidence: Confirmed for source checkout; installer/bundle behavior Unknown.

### Flow: Desktop conversation creation, turn presentation, and restoration

- Trigger / input: project/sidebar selection, new conversation, control change, or composer text.
- Output / side effect: selected Python `ChatSession`, bounded transcript DTOs, a finalized answer/command result, and eventual durable conversation state.
- Steps:
  1. Catalog — `DesktopProjectCatalog` bootstraps one local project, reconciles healthy canonical JSON summaries, and stores only ordered session IDs.
  2. Create/select — selecting a saved session loads canonical JSON; only when it is absent may the strict legacy Chroma/Plan readers stage a non-destructive canonical import before materializing the session.
  3. Switch — validate or import the target before replacing the current session; no conversation-history flush exists. In-process thinking/skill controls are snapshot-restored only while the backend lives.
  4. Turn — Python writes the accepted original prompt as canonical pending before parsing an allowlisted display-only command or starting provider/tool execution.
  5. Finalize — Python validates and finalizes the answer, commits the terminal canonical transition, then returns the authoritative result; first-prompt registration follows the durable pending write.
  6. Present — Python emits bounded `answer.chunk` events only after finalization (`streamKind=post_finalized`), then one authoritative result. React assembles provisional chunks and reconciles them against the exact final result.
- State or ownership transitions: original input moves from draft to durable pending, then to completed/failed/interrupted in the same canonical JSON. The latest ten completed context-eligible turns are derived at prompt time rather than moved between stores.
- Error / retry / rollback behavior: malformed/unavailable transcripts degrade or block selection; catalog failure returns a pending registration that can be retried without replaying the model turn; provider failures retain a durable failed turn and require explicit same-ID retry. Restart marks leftover pending work interrupted rather than auto-replaying it.
- Invariants involved: INV-005, INV-006, INV-016, INV-017.
- Evidence: `app/agent/desktop/catalog.py`; `app/agent/desktop/service.py`; `app/agent/conversations`; conversation/lifecycle/answer-stream tests.
- Confidence: Confirmed.

### Flow: Desktop Bash approval

- Trigger / input: the existing Python Bash tool requests approval during an active desktop turn.
- Output / side effect: the exact approved command runs once through the Python Bash path, or no command runs.
- Steps:
  1. Bash tool — pass command, description, and clamped timeout to the injected desktop approval handler.
  2. Desktop service — reject unsafe/secret-like or oversized context; bind one approval ID to the parent request, turn, and expiry.
  3. Protocol/UI — emit `approval.required`; React accepts it only for the active generation/request/turn and renders inert text with Approve and Deny.
  4. Resolution — Python requires the same approval, parent request, and turn; consumes the pending future; the Bash tool invokes the configured runner only after approval.
- State or ownership transitions: pending approval is in-process and single-use; conversation replacement, crash/restart, timeout, mismatch, dismissal, or shutdown clears it as denial.
- Error / retry / rollback behavior: denial or approval-handler failure returns a denied tool result; command failure/timeout is reported by the existing Bash tool. There is no conversation-wide approval and no frontend shell capability.
- Invariants involved: INV-004, INV-015, INV-017, INV-018.
- Evidence: `app/agent/tools/bash.py`; `app/agent/desktop/service.py::_stage_bash_approval`; `app/desktop/src/trust.tsx`; Bash/desktop tests.
- Confidence: Confirmed with injected runners; no real shell command was run in the recorded final checks.

## State and ownership transitions

| State | Owner while active | Transition | Durable destination |
|---|---|---|---|
| User/model turn | ChatSession and graph | pending JSON before execution; completed/failed JSON before terminal outcome | canonical conversation JSON |
| RAG source file | User filesystem | collect/tag/chunk/index | raw.json, Chroma, folder_meta.json |
| Citation discovery record | Citation provider hub/tool call | authority verification and canonical save | cite bundle plus session SourceRegistry |
| Extension drop-in | User drop-in root | validate/approve/install/restart | private managed copy and registry |
| Desktop child/request | Rust supervisor and Python `RequestContext` | ordered events then one result | wire only; underlying Python side effects persist separately |
| Desktop conversation membership | `DesktopProjectCatalog` | first durable pending prompt or later reconciliation retry | `desktop-projects.json` |
| Desktop conversation content | Python session/repository | write-through pending and terminal transitions | canonical conversation JSON; legacy Chroma/Plan sources are import-only |

## Error, retry, and recovery paths

- Agent graph: two identical retries for truly empty upstream output; one tool-free repair for unsafe final content; deterministic fallback after exhaustion.
- Extended thinking: candidate failures/timeouts can be isolated, malformed aggregation falls back, but raised aggregator/reviewer/reviser provider exceptions are not consistently contained.
- Conversations: the canonical repository writes accepted prompts before provider/tool execution and writes completed, failed, or interrupted terminal states directly. A leftover `pending` turn is exposed as interrupted on reopen; legacy Chroma and Plan records are read only at migration boundaries.
- RAG: raw JSON writes are atomic and concurrent rewrites fail loudly; the three RAG persistence surfaces are not transactional. Re-run ingest is the documented recovery for partial writes.
- Citation: network retries/rate limiting live in provider adapters; identity and storage conflicts fail closed; a batch reports each saved/reused/failed item.
- Extensions: startup skips invalid entries and reports diagnostics; apply requires a new preview after stale state. Cross-process lost updates and post-startup Skill tampering are not recovered automatically.
- Desktop: malformed child output or request timeout terminates the generation; frontend reducers reject stale-generation state. Shutdown/EOF make cancellation visible and do not report a forced exit as successful persistence.
- Desktop trust: unknown, reused, expired, cross-turn, unsafe, dismissed, crash/restart, or shutdown Bash decisions default to denial. Prune and extension previews are one-use and rechecked before mutation.

## Unverified flows

- Live provider and real persistent-store paths were not run in this audit.
- Multiple concurrently launched desktop applications sharing `persist_dir` or extension state were not exercised.
- No integrated stress test covers all RAG read/write overlaps accepted by the concurrent protocol server.
- Installer/wheel/bundled desktop asset lookup is unsupported and unverified; only Linux source checkout is documented.
- No failure-injection test covers Chroma mid-batch failure, extension multiprocessing, or raised extended-thinking provider exceptions.
