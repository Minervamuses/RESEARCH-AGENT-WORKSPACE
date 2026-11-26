# Flows

<!-- for_agents: verified=32cf47f date=2026-11-26 -->

> What happens, step by step, including what happens when a step fails.

## Flows

### Flow: Desktop agent turn, frozen context, and model-input trimming

- **Trigger:** User clicks `Send` or presses `Enter` in `app/desktop/src/components/Composer.tsx::Composer` (`App.tsx::sendTurn`).
- **Steps:**
  1. `App.tsx::sendTurn` — inspects `RESEARCH.md` via `api.workspaceSelect({action: "inspect"})` (unless retrying), builds `submittedContext` (frozen `permissionMode`, `requestedThinkingMode`, `skillReferences`, `projectRules`, open `documentContext`, and passage `references`), enforces the 1 MiB submission cap (`checkSubmissionSize`), and sends `session.turn` over Tauri IPC -> Rust stdin pipe.
  2. `DesktopService` (`app/agent/desktop/turn_ops.py::_TurnOps._session_turn`) — claims `_turn_active`, binds `_TurnWork` + `LocalWorkScope`, validates `submittedContext` (`turn_context.py::_TurnContextOps._submitted_turn_context`), resolves `/slash` and `@skill` references, appends `SNAPSHOT_HEADER` and deduplicated `FROZEN_REFERENCES_HEADER` blocks (using read-only wording when `@grill` is active), and passes `TurnOptions` (forcing `thinking_mode="normal"` on document turns without altering session state) to `ChatSession.turn_outcome`.
  3. `ChatSession` (`app/agent/session.py::ChatSession._locked_turn_outcome`) — acquires `_turn_execution_lock`, recovers any leftover `pending` turn, writes the new `pending` turn with full untransformed text/context to `<historyDirectory>/conversations/<sessionId>.json` via `ConversationRepository`, and fires `turn.accepted` (`App.tsx` clears comment drafts).
  4. History & edit trimming (`app/agent/document_context.py`) — `ChatSession._replayed_context` calls `replay_history_inputs` on copies of the latest 10 completed turns: if the current turn carries `SNAPSHOT_HEADER`, all earlier snapshots become `OMITTED_SNAPSHOT_HEADER` metadata placeholders; if no file is open, only the latest historical snapshot keeps `sourceText` under `HISTORY_SNAPSHOT_HEADER`; historical frozen references lose `sourceText`. Inside the LangGraph loop (`app/agent/graph.py::build_graph`), `compact_edit_results` shortens non-latest saved `document_edit` tool messages to `rangeText` in the transient model prompt.
  5. Execution & finalization (`ChatSession.finalize_and_record`) — `PolicyToolNode` enforces `effective_tools` and sequential Ask approvals. Finalization runs safety checks, `CitationSessionPolicy.finalize_answer`, Desktop schema pre-validation (`_validate_turn_result_shape`), shielded `ConversationRepository.complete_turn`, and `TurnTimingTrace.finish`, then returns `TurnCompletedDto` and triggers `loadHistory` in React.
- **Data and state:** Canonical v3 JSON (`pending` -> `completed|failed|interrupted`) retains full snapshots; model prompts hold trimmed transient copies; `desktop-backend.log` records `turn_trace` character/token share counts.
- **Errors:** Pre-persist validation errors return `PROTOCOL_INVALID` (`accepted: false`, drafts retained). `CancelledError` marks the turn `interrupted` (`TURN_CANCELLED`). Provider 429/5xx/timeout or graph recursion (`64`) marks the turn `failed` with `turnLifecycle` details and incident ID, surfacing `RecoveryNotice` (`Retry saved turn`). Malformed history document blocks pass through untrimmed (`document_parse_issue` logged).
- **Related IDs:** `INV-004`, `INV-005`, `INV-006`, `INV-011`, `INV-026`, `INV-033`, `INV-034`, `PERF-001`, `PERF-002`.

### Flow: Document open, zoom, citekey completion, save, and gated `document_edit`

- **Trigger:** `DocumentHeader` `Open file…` / `Save` / `Undo`, Monaco keystrokes, or agent `document_edit` tool call.
- **Steps:**
  1. Open — `App.tsx::openDocument` calls Tauri `pick_document` (`backend.rs::run_windows_picker`), confirms discarding dirty edits if needed, and calls `document.open`. `DocumentWorkspace.open` (`app/agent/desktop/documents.py`) enforces project-root containment, `.md`/`.markdown`/`.tex` suffix, and `<= 1 MiB` UTF-8, returning `editorRevision: 0` and SHA-256 `diskFingerprint`. Monaco (`DocumentEditor.tsx`) loads locally bundled workers, applies `readEditorFontSize()` (`16` px default, `10`–`28` px in `localStorage`), and registers `[@` / `; @` / `\cite{` completions from `CitationPanel` entries.
  2. Manual save — `document.save` (`DocumentWorkspace.save`) compares `diskFingerprint` against disk; on match, writes temp+fsync+`os.replace`, advances `editorRevision`, and bumps `citationRefresh`.
  3. Agent `document_edit` (`app/agent/desktop/document_ops.py::_DocumentOps._run_desktop_document_edit`) — unavailable on `@grill` turns (`INV-033`). Resolves range/reference, then runs `_unknown_new_citation_keys`: splices `replacement_text` via `DocumentWorkspace.candidate_text` and compares `Counter(citation_keys_in(...))`. If any key's count increases and is absent from `references.json` (or `references.json` is unreadable), returns `{status: "failed", unknownKeys}` without creating a candidate.
  4. Candidate & apply — `DocumentWorkspace.prepare` stores the candidate in memory; Python emits `document.proposed`; React queues `api.documentApplyTracked` (`App.tsx::applyDocumentOperation`). Under Ask, `_document_operation_approval` emits non-modal `approval.required` (allowing editor inspection) and awaits `approval.resolve`. `DocumentWorkspace.apply` re-checks editor + disk versions, writes atomically, advances working reference offsets (`_advance_document_working_context`), and resolves the awaiting tool future (`2 * approval_timeout_seconds` = 120 s max wait).
- **Data and state:** Disk holds UTF-8 bytes; React holds `documentValue` and `documentBaselineRef`; Python `DocumentWorkspace` holds in-memory `_candidates`, `_saved`, and `_undos`.
- **Errors:** Disk/editor drift returns `status: "conflict"` with `currentDiskText` and `expectedSnapshot`, opening `DocumentConflictPanel` (`Keep editor`, `Use candidate and save`, `Cancel`). Approval denial or 120 s timeout returns `status: "cancelled"` with zero disk write.
- **Related IDs:** `INV-018`, `INV-021`, `INV-025`, `INV-032`, `INV-033`, `ASM-030`.

### Flow: Citation discovery, authoritative verification, and single-store bibliography save

- **Trigger:** `/citation` or `@citation` turn calling `citation_workflow`, or out-of-turn `Verify and add` (`bibliography.add`) in `CitationPanel.tsx`.
- **Steps:**
  1. Search (`app/skills/citation/service.py::CitationService.search`) — queries Crossref, DataCite, and optional OpenAlex concurrently (`net.py::fetch_with_retries`, 15 min TTL cache); providers exhausting transient retries are skipped for the rest of that task.
  2. Consent — `citation_workflow(action="save")` or `bibliography.add` requests `citation.save` approval under Ask (`approvals.py::_ApprovalOps._desktop_operation_approval` / `_bibliography_add`; out-of-turn `bibliography.add` registers `"citation"` owner in `app/desktop/src/lib/approvalOwner.ts`).
  3. Verification (`CitationService.save`, `authority.py::AuthorityRegistry`) — resolves `WorkIntent`s concurrently: exact DOI fetches `doi.org` CSL-JSON (sanitized via `csl.py`, abstract stripped); arXiv ID queries `export.arxiv.org`; no-DOI NeurIPS paper fetches `proceedings.neurips.cc/paper_files/paper/<year>` (`<= 16 MiB`), requires a unique normalized title match, and verifies `citation_*` meta tags on the paper page (`<= 1 MiB`). Pre-checks `SourceRegistry.conflicts` before writing.
  4. Single-store persistence (`CitationService._link_library`, `library.py`) — on Desktop (`library_path` set), loads `references.json`, reuses existing entries matching canonical DOI, arXiv ID, or NeurIPS URL hash (`proceedings.neurips.cc` / `papers.nips.cc`), appends new keyed entries (`<surname><year><titleword>[a..zz]`), and atomically rewrites `references.json` if its indent layout is reproducible and SHA-256 matches. Only items present in `references.json` after the write register in `SourceRegistry` as `saved` or `reused`. On CLI (`library_path=None`), verified items register as `verified` in memory for the current turn only; nothing is written to disk.
  5. Chat gate (`app/agent/skills/citation/session_policy.py::CitationSessionPolicy.finalize_answer`) — checks `[[cite:<id>]]` markers against `SourceRegistry` before `complete_turn`; unverified markers replace the draft with a safe refusal message.
- **Data and state:** `<project>/references.json` (CSL-JSON array, no `cite/` bundles); per-turn `SourceRegistry`; `citation_save_finalized` counts in `desktop-backend.log`.
- **Errors:** Unreproducible layout, concurrent edit, or disk error returns item status `storage_failed` with `library_*` reason code, leaving the item unregistered and uncitable while preserving pre-existing `reused` items in the same batch.
- **Related IDs:** `INV-010`, `INV-014`, `INV-018`, `INV-030`, `INV-032`, `FAIL-024`, `ASM-001`, `ASM-014`, `ASM-037`.

### Flow: Citations panel inspect, Pandoc preview/export, and `bime_word` export

- **Trigger:** Document open/save/apply (`citationRefresh`), or clicking `Refresh`, `Style`, `Preview`, `Export ▾`, or `Remove` in `app/desktop/src/CitationPanel.tsx`.
- **Steps:**
  1. Inspect (`bibliography.inspect` -> `bibliography_ops.py`) — parses Markdown or LaTeX citekeys (`citekeys.py::find_citations`) and checks `references.json` (`integrity.py::inspect`), returning `entries`, `uses`, `order`, `missing`, `uncited`, and `duplicateDois`. Panel starts collapsed per file and auto-expands on initial problems or `0 -> >0` problem transitions.
  2. Style & remove — `bibliography.set_style` splices `"citationStyle"` into `RESEARCH.md` via `project.py::update_project_metadata` (idle required, SHA-256 prechecked). `bibliography.remove` confirms via `window.confirm`, requires idle + matching `libraryFingerprint`, and rewrites `references.json`.
  3. Pandoc preview & `.docx`/`.md` export (Markdown only; `csl_render.py`) — runs `pandoc --sandbox -f markdown -t json --citeproc` (60 s timeout; `bime-appendix17` preprocesses a temp bibliography copy for CJK `language`, initials, `et al.`, and straight apostrophes). Preview returns flat `RenderSegmentDto`s rendered by `CitationText.tsx`. Export unlinks remote `scheme://` images, embeds local images from `document.parent` for `.docx`, and atomically writes `<stem>.<style>.docx` or `.md` beside the source file.
  4. BIME Word export (`format="bime_docx"`, `bime_export.py::run_bime_convert`) — requires `DocumentWorkspace.matches_disk(snapshot)` (refuses unsaved editor buffers). Runs vendored `bime_word.py convert --scope fragment --overwrite` (180 s timeout, optional `bime-<stem>-profile.json`). On exit `0` or `1` with valid JSON stdout, `split_front_matter` splits any `BIMETOCTitle` before the first `Heading1` into its own `lowerRoman` (`start=1`) section and restarts body at `decimal` (`start=1`), re-runs `bime_word.py audit --fail-on none`, updates `<stem>.bime.bime.json`, and returns `{path, audit}`.
- **Data and state:** Source document never mutates; exports write `<stem>.<style>.docx|md` or `<stem>.bime.{docx,audit.json,audit.md,bime.json}`.
- **Errors:** `LIBRARY_CONFLICT` -> retryable `BIBLIOGRAPHY_CONFLICT`. Unsaved buffer on `bime_docx` -> `PROTOCOL_INVALID`. Missing Pandoc, timeout, or `bime_word` exit `2` -> `BIBLIOGRAPHY_FAILED` (nothing written). `bime_word` exit `1` writes draft `.bime.docx` and highlights `audit.errors` in red.
- **Related IDs:** `INV-001`, `INV-017`, `INV-025`, `INV-032`, `ASM-037`, `PERF-004`.

### Flow: Project open, derived conversation list, Stop / Retry Stop, and crash recovery

- **Trigger:** Cold launch (`main.py`), `Open/Switch project`, `Stop` / `Retry Stop`, or backend crash/restart.
- **Steps:**
  1. Startup — React `listenBackendEvents` subscribes to `research-agent://backend-event` and calls `api.initialize` -> `backend_start`. Rust `BackendSupervisor` (`backend.rs`) validates Conda `app` and build-time checkout, spawns `python -m agent.desktop.server`, waits `<= 15 s` for `backend.ready`, and React loads `runtime.diagnostics` then opens `ProjectChooser`.
  2. Project open (`workspace.select` -> `project_ops.py`, `project.py`) — `pick_project` runs `WINDOWS_PICKER_SCRIPT` (Win32 `AttachThreadInput` foreground dialog -> WSL path). `inspect_project` parses `RESEARCH.md` (`<= 1 MiB`, keys `{version, historyDirectory, bibliography, citationStyle}`). `open` runs `open_project_history` -> `project_conversations` (`ConversationRepository.scan`, fail-closed on issues or foreign `projectId`), shuts down any prior session, binds `DocumentWorkspace` and `ConversationRepository`, and React calls `session.list`.
  3. Stop & Retry Stop (`turn_ops.py::_TurnOps._session_stop`, `_retry_stop`) — cancels the turn task, marks candidates stopped, denies pending approvals, awaits `document_tasks`, and runs `LocalWorkScope.finish_stop` (0.5 s `SIGTERM` -> 0.5 s `SIGKILL` per bash process group in `bash.py::_stop_process_group`). If cleanup fails or disk state stays `pending`, `_turn_active` stays `True` and UI shows `StopFailureNotice` (`Retry Stop`). Pressing `Retry Stop` reruns `finish_stop` on remaining unstopped groups, calls `ChatSession.reload_and_recover` if disk state is `pending`, and clears `_turn_active` once disk state is terminal (`completed|failed|interrupted`) or never accepted.
  4. Crash & restart — on child stdout EOF, `backend.rs::stdout_closed` polls `try_wait()` for 500 ms (`STDOUT_CLOSE_EXIT_GRACE`) so crashes report `BACKEND_CRASHED` instead of `BACKEND_OUTPUT_CLOSED`. On `Restart`, `planBackendSnapshotTransition` (`backend.ts`) increments `generation`, captures `resumeSelection` and `resumeDraft`, reopens the project, reloads `session.list`, and reselects the conversation (`conversationToRestore`).
- **Data and state:** `RESEARCH.md`, `<historyDirectory>/conversations/*.json`, Rust `generation` counter.
- **Errors:** Any malformed/v1/v2/foreign conversation file or invalid `RESEARCH.md` metadata blocks opening the project (`FAIL-026`). Unreadable disk state during `Retry Stop` keeps the session blocked until `Restart backend`.
- **Related IDs:** `INV-001`, `INV-006`, `INV-015`, `INV-016`, `INV-027`, `INV-035`, `FAIL-026`, `ASM-012`, `ASM-026`, `ASM-031`, `PERF-001`.

### Flow: Knowledge slash commands (`/init`, `/ingest`, `/sync`, `/prune`) and extensions

- **Trigger:** Composer `/init`, `/ingest <path>`, `/sync <dir>`, `/prune <dir> [--yes]`, `/extension-management`, or `skill-installer`.
- **Steps:**
  1. Knowledge commands (`command_ops.py::_KnowledgeCommandOps`) — run inside `ChatSession.run_display_only_turn` (`context_eligible=False`). Paths are checked by `_validated_path` (absolute Linux, non-symlink, outside `SKIP_DIRS` and protected app roots). Mutations require Ask approval (`knowledge.*` operation enum). `ingest_repo` (`app/rag/cli/ingest.py`) tags folders via OpenRouter (`ThreadPoolExecutor(max_workers=4)`), writes `folder_meta.json`, batches Chroma upserts (`256`), and commits `raw.json` on exit (`deferred_save`). `/prune` stores `_composer_prune_preview` digest and requires `--yes` with unchanged orphan digest (under Bypass, `/prune <dir>` applies immediately in one step).
  2. Extensions (`extension_ops.py::_ExtensionOps`, `app/agent/extensions/manager.py`) — `/extension-management` opens `ExtensionPanel` (`useExtensions.ts`); `extensions.preview` diffs `app/tool/{skill,mcp}` drop-ins (optionally summarizing via OpenRouter); in Ask mode the user approves/denies each MCP `bindingHash`; `extensions.apply` acquires Linux `flock` on `.apply.lock`, writes content-addressed managed copies + registry revision inside `run_display_only_turn`, and prompts `Restart backend` when `restartRequired` is true.
- **Data and state:** `<persist_dir>/{raw.json, folder_meta.json, chroma}`, `app/tool/` managed state, display-only turns in conversation JSON.
- **Errors:** Stop or Chroma error mid-ingest rolls back `raw.json` while leaving `folder_meta.json` / partial Chroma writes until re-ingest (`FAIL-003`). Large `/prune --yes` orphan summaries (`> 8 KiB`) silently fail Ask approval (`FAIL-025`).
- **Related IDs:** `INV-003`, `INV-007`, `INV-008`, `INV-009`, `INV-012`, `INV-013`, `INV-024`, `FAIL-001`, `FAIL-002`, `FAIL-003`, `FAIL-025`, `FAIL-035`.

## State machines

### Canonical conversation turn (`app/agent/conversations/models.py`, `repository.py`)

| From | To | Trigger | Guard / notes |
|---|---|---|---|
| `(absent)` | `pending` | `create` / `append_pending` | At most one `pending` turn per conversation; persisted before model/tool calls (`INV-006`) |
| `pending` | `completed` | `complete_turn` | Requires non-blank `assistantOutput`, `failure=None`; idempotent on identical replay |
| `pending` | `failed` | `fail_turn` | `failure.code` in `{"execution_failed", "persistence_failed"}`; `assistantOutput=None` |
| `pending` | `interrupted` | `fail_turn` / `_recover_interrupted_turn` | On user Stop (`cancelled`) or session reload after crash (`interrupted`) |
| `failed` / `interrupted` | `pending` | `retry_turn` | Explicit `retry=True` with identical `turnId`, text, `thinkingMode`, and `submittedContext` (`INV-026`) |
| `completed` | *(any other)* | **Impossible** | Rejected by `_validate_document_update` (`InvalidTransitionError`) |

### Backend supervisor & UI lifecycle (`app/desktop/src-tauri/src/backend.rs`, `app/desktop/src/backend.ts`)

- **Rust `BackendLifecycle`:** `Stopped` -> `Starting` -> `Ready` (on `backend.ready` within 15 s) | `Degraded` (on `backend.protocol_error` or invalid Conda/checkout) | `Crashed` (unexpected child exit or stdout EOF + reap within 500 ms). From `Ready`/`Degraded`/`Crashed`: `Restarting` -> `Ready`, or `ShuttingDown` (5 s `runtime.shutdown` wait + 5 s exit wait, else SIGKILL `Forced`) -> `Stopped`.
- **React `UiLifecycle`:** Maps `Ready` to `backend-ready` (no `ChatSession`), `session-ready` (session selected), or `busy` (`diagnostics` / `session` action in flight). Every new child increments `generation`; stale generation events/results are dropped.

### Single-slot approval & Extension flow (`app/desktop/src/lib/approvalOwner.ts`, `lib/extensionFlow.ts`)

- **Approval (`_PendingApproval` / `ApprovalOwnerState`):** `idle` -> `pending` (on `approval.required` matching registered `turnRequestId`, `documentRequestId`, or `citationRequestId` while no other approval is open) -> `resolving` (`approval.resolve` or expiry timer at 60 s) -> `idle`. Stop, crash, project switch, or owner completion immediately clears/denies.
- **Extension UI (`ExtensionFlow.phase`):** `ready` -> `previewing` -> `review` (all MCP bindings decided in Ask) -> `applying` -> `applied` -> `restarting` -> `awaiting-load` -> `loaded` (once `session.extensionRevision >= appliedRevision`), with `error` branch offering `Retry preview` or `Recover saved apply result`.

## Contracts across boundaries

| Boundary | Definition | Producers | Consumers | Versioning / compatibility |
|---|---|---|---|---|
| Desktop NDJSON protocol v1 | `app/desktop/protocol/v1/contract.json` | React (`protocol.ts`, `api.ts`), Rust (`backend.rs`), Python (`protocol.py`, `server.py`) | Python `DesktopServer`, Rust `protocol.rs`, React `backend.ts` / `api.ts` | `protocolVersion: 1`, 2 MiB line cap (`session.turn` and `session.transcript` success results exempt); `protocol_types.test.ts` enforces TS DTO match (`PLAY-001`) |
| Tauri bridge commands & event | `app/desktop/src-tauri/src/lib.rs`, `backend.rs::BACKEND_EVENT_NAME` | React `api.ts` (7 commands), Rust `emit_lifecycle` / `emit_protocol` | Rust `BackendManager`, React `parseBridgeEvent` | In-process binary/bundle pair built together by `main.py` |
| Canonical conversation JSON | `app/agent/conversations/models.py::SCHEMA_VERSION` (`3`), `repository.py::_DOCUMENT_KEYS` | `ConversationRepository` | `ConversationRepository` (`ChatSession`, `project.py`, `transcript.py`) | Strict schema v3 only; v1/v2 rejected as `unsupported_version` (`INV-006`, `FAIL-026`) |
| Project `RESEARCH.md` metadata | `app/agent/desktop/project.py::_PROJECT_MARKER`, `_PROJECT_METADATA_KEYS` | `initialize_project`, `update_project_metadata`, user edits | `inspect_project`, `project_citation_settings` | `version: 1`; exact keys `{version, historyDirectory, bibliography?, citationStyle?}` (`FAIL-026`) |
| Project bibliography CSL-JSON | `app/skills/citation/library.py::parse_items`, `csl.py::sanitize_csl` | `CitationService._link_library`, `bibliography.remove`, user edits | `library.py`, `integrity.py`, `csl_render.py`, `bime_export.py` | JSON array of objects with unique string `id`; unknown indentation layouts are read-only (`LIBRARY_FORMAT_UNSUPPORTED`) |
| Embedded prompt document blocks | `app/agent/document_context.py` (`SNAPSHOT_HEADER`, `FROZEN_REFERENCES_HEADER`, replay headers) | `turn_ops.py`, `document_context.py` | `document_context.py`, `observability.py::measure_document_context` | Shared header constants; unparseable blocks pass through untrimmed |
| Vendored `bime_word` CLI JSON | `app/agent/desktop/bime_export.py::_parse_summary`, `_reaudit` | `app/vendor/bime-word/scripts/bime_word.py` (`convert`, `audit`) | `bime_export.py` | Pinned to vendored 1.1.5 (`manifest.sha256`); exit `0`/`1` require JSON stdout |
| Web Search MCP stdio | `app/agent/mcp.py::_load_web_search_tools` | `app/agent/mcp.py` (`meta.web_search_work_ms`, env whitelist) | `app/vendor/web-search-mcp/dist/index.js` | stdout filtered through `grep --line-buffered '^{'`; 5 env vars whitelisted |
