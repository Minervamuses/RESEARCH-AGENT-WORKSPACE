# Research Agent Desktop GUI — Build Log

This file is the sole owner of runtime phase status, the compact resume checkpoint, implementation attempts, blockers, and observed verification evidence. Other plan files describe intended work only.

## Resume Checkpoint

- Execution mode: Autonomous within the launch-message authorization envelope
- Execution authorization: Activated by the user's 2026-08-28 launch message using the complete How to Start envelope; no later narrowing or expansion
- Current phase: 01 — Desktop foundation (In progress)
- Current checkpoint: Phase 01 implementation, integrated focused checks, fake-child matrix, and real Tauri lifecycle/crash-recovery trace pass; scoped staged-diff review and checkpoint commit remain
- Next action: Review and commit only the Phase 01 write set, record the hash, then perform the mandatory durable reload and start Phase 02
- Current attempt/hypothesis: 1 / Existing protocol and Python WIP are sound; the missing Rust/Tauri owner and React lifecycle client are sufficient for the Phase 01 result
- Extended Thinking live GUI trials: 0 / 3
- Blocked branches: None
- Last durable update: 2026-08-28 01:47 Asia/Taipei — real Tauri stopped/start/ready/shutdown/crash/restart trace completed without a session or provider call

## Phase Summary and Status

| Phase | Status | Started | Completed | Evidence | Blocker |
|---|---|---|---|---|---|
| 01 — Desktop foundation | In progress | 2026-08-28 01:23 | — | Runtime/tool identities and dirty-tree ownership preflight recorded below | None |
| 02 — Chat and session | Not started | — | — | — | None |
| 03 — Knowledge slash commands | Not started | — | — | — | None |
| 04 — Extensions and trust boundary | Not started | — | — | — | None |
| 05 — Acceptance and Linux delivery | Not started | — | — | — | None |

Allowed status values are Not started, In progress, Blocked, and Complete. Complete requires observed evidence for every required acceptance item in the phase.

## Recording Rules

- Update Resume Checkpoint at phase start, after a meaningful check or failed attempt, at phase completion, after plan repair, and before stopping.
- Record the exact command or manual procedure, relevant runtime, concise observed result, and evidence path when one exists.
- Distinguish observed evidence, historical/user report, inference, planned command, skipped check, and unavailable check.
- Record the exact in-scope write set and overlap with pre-existing user changes before the first write of each phase.
- Keep secrets, credentials, raw provider payloads, raw tool arguments/results, full tracebacks, and large terminal dumps out of this file.
- A required failed/unavailable check keeps a phase In progress or Blocked. An optional unavailable live check is a limitation, not a fabricated pass.
- Preserve material failures and corrections. Later entries may supersede them explicitly but must not erase useful history.
- After two focused failed attempts against the same causal hypothesis, record the evidence, mark only the affected branch Blocked, and let the selector continue independent eligible work.
- Keep the Extended Thinking live-GUI-trial counter separate from implementation attempts. Reserve and increment it before starting a backend/session specifically for that trial or, if already ready, before dispatching its one GUI turn. Immediately record the trial number, timestamp, operation, paid model set, temporary-data boundary, and whether dispatch was reached.
- If startup prevents dispatch, record `dispatch not reached / startup failure`; success, HTTP 429, timeout, provider error, crash, or any other cause likewise consumes the started trial. Phase changes, repairs, retries, and different failure causes never delete or reset it. Do not begin a fourth trial, and do not start the next one until the prior turn is terminal or its backend is fully stopped. Stop before three when existing live evidence is sufficient.
- The three-trial limit bounds end-to-end GUI trials, not internal logical model invocations, HTTP retries, or provider cost. A failed live Extended Thinking trial is recorded as a limitation with its real reason; it does not block GUI completion when the required fake success/error contract and honest error presentation pass.

## Activity Log and Evidence

No implementation phase has started. The 2026-08-24 authoring and planning audits through the Phase 05 review changed only the plan bundle. The later PROMPTS review also changed the main-model configuration and ran only the focused offline Python checks recorded below; no live provider, TypeScript, Rust, Tauri, store, extension, or Bash integration check has run.

## 2026-08-26 Asia/Taipei — Phase 03 planning review clarification

- **Status:** All phases remain `Not started`; execution authorization remains inactive.
- **Changes:** Corrected Phase 03 to depend on Phases 01 and 02; removed every dependency on the user-deleted legacy design artifacts; clarified one-at-a-time RAG writes, typed progress, partial-write reporting, read-only sync comparison, and one-time prune `previewId` behavior; required cleanup of manually created and generated test artifacts; preserved independent Phase 04 eligibility after Phase 02.
- **Planning verification:** Strict harness validator returned valid with 0 errors and 0 warnings; an exact-text scan found no remaining reference to the deleted design directory.
- **Application verification:** Not run; this was a planning-only revision.
- **Unresolved product decision:** Whether Phase 03 should provide a full Knowledge explorer, only minimal ingest/compare/prune management, or no separate Knowledge UI beyond chat-owned RAG use. The current functional scope remains unchanged until the user decides.
- **Next action:** Record that decision in `GOALS.md`, `PLANS.md`, Phase 03, and Phase 05 before implementation launch.

## 2026-08-26 Asia/Taipei — Phase 03 scope decision recorded

- **Status:** All phases remain `Not started`; execution authorization remains inactive.
- **User decision:** Do not build a standalone Knowledge GUI. Normal questions keep using RAG internally through the Python agent. `/init`, `/ingest`, `/sync`, and `/prune` are entered in the conversation composer and are not represented by separate pages, forms, buttons, search results, document/chunk explorers, or command-specific progress UI.
- **Plan correction:** Phase 02 now owns only the common Python composer-input/slash-command dispatch seam so Phases 03 and 04 remain independently eligible after it. Phase 03 owns the four exact knowledge commands, desktop-only Linux path validation, read-only sync comparison, conversation-local prune preview followed by matching `--yes`, fake/temp verification, and cleanup. No opaque token is exposed to the user.
- **Exact planning write set:** `GOALS.md`, `PLANS.md`, `PROMPTS.md`, `build-log.md`, and `phases/phase-01-desktop-foundation.md` through `phases/phase-05-acceptance-delivery.md`.
- **Planning verification:** Strict harness validation returned `VALID: 0 finding(s)`; stale-positive-requirement and deleted-spec-reference scans returned no matches; the dependency walkthrough confirmed Phase 03 requires completed Phases 01/02 and Phase 04 has no Phase 03 dependency; all nine bundle files have no trailing whitespace.
- **Application verification:** Not run; this is a planning-only correction and no application file was changed.
- **Blockers:** None.
- **Next action:** Await the recommended `PROMPTS.md` launch message; implementation begins at Phase 01.

## 2026-08-26 Asia/Taipei — Phase 04 reviewed-source alignment recorded

- **Status:** All phases remain `Not started`; execution authorization remains inactive.
- **User decision:** `GOALS.md`, `PLANS.md`, and Phases 01–03 are user-reviewed authoritative sources. Every conflicting Phase 04 statement must be corrected to match them.
- **Plan correction:** Restored the existing Python-owned per-command Bash workflow with exactly Approve and Deny, exact-request one-use execution, fail-closed timeout/replay/crash behavior, and terminal CLI compatibility. Narrowed the Tauri restriction to React/WebView generic shell/filesystem grants while preserving the Phase 01 Rust-owned Python-child mechanism, including an official Shell child-process primitive if Phase 01 verifies it. Preserved Phase 03 composer-only matching `/prune <root> --yes` confirmation without a modal or button.
- **Exact planning write set:** `phases/phase-04-extensions-trust.md` and `build-log.md` only.
- **Planning verification:** Strict harness validation returned valid with 0 errors and 0 warnings. Stale-conflict, Bash-alignment, Phase 01 child-alignment, Phase 03 prune-preservation, and trailing-whitespace scans passed.
- **Application verification:** Not run; this was a planning-only revision and no application file was changed.
- **Blockers:** None.
- **Next action:** Await the recommended `PROMPTS.md` launch message; implementation begins at Phase 01.

## 2026-08-27 Asia/Taipei — Phase 05 user-reviewed alignment recorded

- **Status:** All phases remain `Not started`; execution authorization remains inactive.
- **User decision:** Applicable `AGENTS.md`, `GOALS.md`, `PLANS.md`, and Phases 01–04 are user-reviewed authoritative sources. `PROMPTS.md` has not yet been user-reviewed and cannot override those approved sources.
- **Plan correction:** Phase 05 now requires an exact `GOALS.md`/`PLANS.md` Overall Completion/Phase 05/effective earlier-acceptance evidence crosswalk in `build-log.md`; rechecks the minimal A/B restoration and streaming integration plus fake Bash approve/deny behavior; names the exact Conda `app` Python/npm/Cargo/Tauri final commands without duplicating the configured frontend build; and accepts only authorized, managed, evidenced manifest/lockfile changes.
- **Exact planning write set:** `phases/phase-05-acceptance-delivery.md` and `build-log.md` only.
- **Planning verification:** Strict harness validation returned valid with 0 errors and 0 warnings. `git diff --check`, direct trailing-whitespace scans of both written files, and exact-text checks for the authority order, evidence crosswalk, final Tauri command, and managed manifest/lockfile rule passed. A focused fresh-agent walkthrough found Phase 05 resumable from the approved sources; the complete bundle remains intentionally unlaunchable until `PROMPTS.md` is separately reviewed and reconciled.
- **Application verification:** Not run; this is a planning-only correction and no application file was changed.
- **Remaining planning review:** `PROMPTS.md` remains unreviewed and unchanged. It must be reconciled with the approved sources before it is used as implementation authorization.
- **Blockers:** None for this planning correction; implementation authorization remains inactive.
- **Next action:** Await user review of `PROMPTS.md` or another explicit launch message consistent with the approved sources.

## 2026-08-27 Asia/Taipei — PROMPTS review and bounded provider authorization recorded

- **Status:** All phases remain `Not started`; execution authorization remains inactive until the reviewed How to Start block is sent.
- **User decision:** `PROMPTS.md` is now reviewed. Bounded live/paid-provider verification is allowed when materially useful, with fake/temp verification as the default, one user notice before the first such call for the whole plan, secret-safe evidence in this log, no credential-value inspection/disclosure/editing/copying, no real-data mutation, and no second expensive attempt without fresh authority.
- **Plan correction:** Reconciled `GOALS.md`, `PLANS.md`, `PROMPTS.md`, and Phases 02–05 with that decision while retaining the Phase 01 no-live startup baseline, mandatory fake/temp acceptance, and the rule that live-provider success is optional. Phase 01 content required no change.
- **Exact write set:** `app/agent/config.py`; `GOALS.md`, `PLANS.md`, `PROMPTS.md`, `build-log.md`; and `phases/phase-02-chat-session.md` through `phases/phase-05-acceptance-delivery.md`. This set was frozen before edits in the task commentary; Phase 01 was reviewed but not edited.
- **Git boundary:** Main-model configuration was committed separately as `e223906`. Because this new plan directory is wholly untracked, its nine files will be staged atomically as one complete bundle; pre-existing GUI deletions, old-harness deletions, desktop-bridge/test WIP, and other user changes remain excluded.
- **Planning verification:** The strict harness validator passed with 0 errors and 0 warnings while every written harness file was declared in scope. `git diff --check` passed, and per-file `git diff --no-index --check` produced no whitespace finding for any written untracked harness file. A fresh read-only agent review found no other actionable defect and confirmed that the separate `/init`/directory-ingest conflict remains explicit rather than silently resolved.
- **Application verification:** The focused offline OpenRouter factory module passed 6 tests, and a direct Conda `app` configuration assertion returned `google/gemma-4-26b-a4b-it:free`. No live provider, Ollama, citation, MCP, real-store, TypeScript, Rust, Tauri, or full-suite check was run.
- **Separate reviewed-code finding:** The live repository performs paid `z-ai/glm-5` folder tagging once per folder for `/init` and directory `/ingest`, while current GOALS/Phase 03 text says those commands run without a model call. This semantic conflict is intentionally unresolved pending a user decision; the present authorization alignment does not silently redefine those acceptance requirements.
- **Blockers:** None for this planning/configuration checkpoint. The separate `/init`/directory-ingest wording decision may affect Phase 03 implementation but does not prevent this review from completing.
- **Next action:** Await the reviewed How to Start launch block; implementation then begins at Phase 01.

## 2026-08-28 Asia/Taipei — GUI verification scope and Extended Thinking cap recorded

- **Status:** All phases remain `Not started`; execution authorization remains inactive until the reviewed How to Start block is sent. `PROMPTS.md` remains reviewed and complete.
- **User decision:** This plan is centered on the GUI. Do not execute actual `/init` or `/ingest` RAG construction during this plan's focused, integrated, or final verification. Paid-model verification is limited to Extended Thinking and to at most three live GUI trials across the whole plan; every started trial, including one whose startup prevents dispatch, consumes its reserved slot and is recorded honestly regardless of outcome or cause such as HTTP 429.
- **Plan correction:** `/init` and `/ingest` now require real React/Rust/Python routing evidence with injected Python handler spies instead of construction; `/sync` and `/prune` use prebuilt fake/temp state. Phase 02 adds required fake Extended Thinking success/error GUI evidence, Phase 03 and Phase 04 make no paid-model call, and Phase 05 owns the optional 0–3 live-GUI-trial check and the final Python selector that excludes the two tests which actually call `ingest_repo`. A trial is reserved before trial-specific backend/session startup or dispatch, so startup failure records `dispatch not reached` and still counts. This decision supersedes the 2026-08-27 entry's generic paid-provider/second-expensive-attempt wording and its then-unresolved `/init`/directory-ingest decision; those older lines remain only as preserved history.
- **Cost boundary:** One dispatched Extended Thinking GUI turn may invoke several paid models and internal retries. The 3-trial cap is not a 3-request or fixed-cost cap; no hard transport-level cap exists in this planning-only change.
- **Current paid-call inventory:** The main model is the free `google/gemma-4-26b-a4b-it:free`. A clean current Extended Thinking turn has six logical model invocations, five paid: `openai/gpt-5-mini` rewrite, paid `google/gemini-3.1-pro-preview` and `anthropic/claude-haiku-4.5` proposers alongside the free Gemma proposer, `openai/gpt-5.2` aggregation, and `anthropic/claude-haiku-4.5` review. Two revision rounds with both format repairs can reach twelve logical invocations, nine paid, before graph/tool loops or transport retries. The paid `z-ai/glm-5` folder-tagger path for real `/init` and directory `/ingest` is excluded rather than changed.
- **Exact planning write set:** `GOALS.md`, `PLANS.md`, `PROMPTS.md`, `build-log.md`, `phases/phase-02-chat-session.md`, `phases/phase-03-knowledge.md`, `phases/phase-04-extensions-trust.md`, and `phases/phase-05-acceptance-delivery.md`. Phase 01 was reviewed and remains unchanged; no application, test, dependency, or Git state is changed by this correction.
- **Planning verification:** Strict harness validation passed with 0 errors and 0 warnings after all corrections. Scoped `git diff --check` passed, the exact harness diff contains only the eight declared files, and Phase 01 has no diff. A fresh read-only walkthrough found the startup-before-dispatch counting ambiguity; after correction, its follow-up review confirmed the live-GUI-trial semantics are consistent and found no further actionable harness defect.
- **Application verification:** Not run; this is a planning-only correction. No live provider, Ollama, RAG construction, citation, MCP, real-store, TypeScript, Rust, Tauri, or application-test command was run.
- **Blockers:** None for the planning correction. A hard cap on internal paid invocations, HTTP retries, or provider cost would require a separate application/configuration decision and is not implied by the three-live-GUI-trial limit.
- **Next action:** Await the reviewed How to Start launch block; implementation begins at Phase 01.

## 2026-08-28 01:23 Asia/Taipei — Phase 01: authorization and ownership preflight

- **Status:** `Not started` → `In progress`.
- **Authorized scope:** The user's 2026-08-28 launch message explicitly activated the complete reviewed How to Start authorization, including continuous cross-phase execution and scoped local checkpoint commits. No later narrowing or expansion exists. Actual `/init` or `/ingest` construction remains prohibited; the shared Extended Thinking live-GUI-trial counter remains `0 / 3`.
- **Runtime gate (observed):** Repository root `/home/minervamuses/research-agent-workspace`; Linux `6.6.87.1-microsoft-standard-WSL2`; Linux Git 2.43.0; Conda 25.5.1 at `/home/minervamuses/miniconda3/bin/conda`; environment `app`; Python 3.13.14, Poetry 2.4.1, Node 24.18.0, npm 11.16.0, Cargo 1.97.1, and rustc 1.97.1 all resolve under `/home/minervamuses/miniconda3/envs/app`.
- **Exact current write set:** `harness/plans/2026-08-24-desktop-gui-completion/build-log.md`; user-owned `app/agent/desktop/__init__.py`, `app/agent/desktop/protocol.py`, `app/agent/desktop/server.py`, `app/agent/desktop/service.py`, `app/tests/test_desktop_protocol_contract.py`, `app/tests/test_desktop_service.py`, and `app/tests/test_desktop_server.py`; planned `app/desktop/src-tauri/src/backend.rs`, `app/desktop/src-tauri/src/lib.rs`, `app/desktop/src/backend.ts`, `app/desktop/src/App.tsx`, `app/desktop/src/styles.css`, `app/desktop/tests/backend.test.ts`, and `app/desktop/package.json`. Contract/fixture/protocol files are read-only unless a focused check demonstrates a mismatch; any causal expansion will be recorded before editing.
- **Existing overlap:** The four Python desktop files and two focused test files are untracked user WIP; their pre-edit SHA-256 values were recorded in the execution transcript. `app/tests/test_desktop_protocol_contract.py` is user-modified (`45` insertions, `385` deletions) to replace its temporary parser with the production Python protocol. The GUI deletions, old-harness deletions, `.gitignore`, and all other dirty-tree entries remain user-owned and excluded. Generated `app/agent/desktop/__pycache__/` content is excluded.
- **Official process-primitive evaluation (observed):** Tauri's official Shell plugin supports Rust child processes but would add and initialize `tauri-plugin-shell`; its dangerous spawn/stdin/kill commands are capability-scoped when exposed to the WebView. A bundled sidecar also requires an external binary and target-triple packaging, which does not match this Linux source-checkout delivery. Phase 01 will therefore use `std::process::Command` from the Rust owner with an exact validated Conda interpreter path, while retaining official Tauri command/event IPC and no WebView shell/filesystem permission.
- **Hypothesis/attempt:** `0 / baseline characterization`; the demonstrated missing slice is Rust child supervision plus truthful React lifecycle presentation, while the existing Python WIP may already satisfy its focused boundary.
- **Verification:** Not yet run for implementation. Durable-file reload, live source/fixture inspection, runtime identities, Git status, and user-WIP hashes were observed read-only.
- **Limitations:** None at phase start.
- **Blockers:** None.
- **Next action:** Run the exact Phase 01 focused Python selector, `npm test`, TypeScript no-emit check, and current Rust tests as baseline evidence before the first application edit.
- **Evidence references:** Tauri official Shell and external-binary documentation inspected on 2026-08-28; no dependency was installed.

## 2026-08-28 01:24 Asia/Taipei — Phase 01: focused baseline characterization

- **Status:** Phase 01 remains `In progress`.
- **Hypothesis/attempt:** `1 / existing protocol and Python WIP are sound; the missing Rust/Tauri owner and React lifecycle client are sufficient for the Phase 01 result`.
- **Verification (observed, Conda `app`, no live provider):** From `app/`, `poetry run pytest tests/test_desktop_protocol_contract.py tests/test_desktop_service.py tests/test_desktop_server.py -q` passed `95` tests with one existing LangChain deprecation warning in `0.14s`. From `app/desktop/`, `npm test` passed `72` tests; `./node_modules/.bin/tsc --noEmit` exited `0`; `cargo test --manifest-path src-tauri/Cargo.toml` passed `8` library tests plus empty binary/doc targets.
- **Causal conclusion:** No baseline contract mismatch or focused Python service/server defect was demonstrated. Keep the shared contract, fixtures, Python WIP, and three existing protocol implementations unchanged unless the new lifecycle trace exposes a specific incompatibility.
- **Blockers:** None.
- **Next action:** Add the standard-library one-child Rust supervisor and named Tauri command/event bridge, then wire a bounded lifecycle UI and fake-child tests.
- **Evidence references:** Exact command output is in the execution transcript; no generated store, live provider, Ollama, or real-data operation occurred.

## 2026-08-28 01:26 Asia/Taipei — Phase 01: direct Python backend lifecycle trace

- **Status:** Phase 01 remains `In progress`; implementation attempt `1` continues.
- **Verification (observed):** From the repository root, ASCII NDJSON for one `runtime.diagnostics` request followed by `runtime.shutdown` was piped to `conda run --no-capture-output -n app python -m agent.desktop.server` with a `15s` process timeout. The process exited `0`; protocol stdout contained `backend.ready`, ordered `request.started` events, one valid diagnostics result, one `{"status":"stopped"}` shutdown result, and `backend.shutting_down`. Diagnostics reported original working directory `/home/minervamuses/research-agent-workspace`, app working directory `/home/minervamuses/research-agent-workspace/app`, protocol `1`, Python `3.13.14`, Conda environment/prefix `app`, provider-key presence as `false`, and bounded path/MCP fields. A LangChain deprecation warning appeared on stderr only.
- **Causal conclusion:** The exact source-run child command and Python readiness/shutdown semantics needed by the Rust supervisor work without a provider or session. Rust must keep stdout and stderr separate and may safely retain only stderr counts.
- **Blockers:** None.
- **Next action:** Complete the in-progress Rust/Tauri and React lifecycle slices, then integrate their fixed command/event contract.
- **Evidence references:** Exact combined terminal capture is in the execution transcript; no session, provider, RAG, extension, or real-data operation occurred.

## 2026-08-28 01:28 Asia/Taipei — Phase 01: read-only acceptance audit and write-set expansion

- **Status:** Phase 01 remains `In progress`; implementation attempt `1` continues.
- **Confirmed findings:** `app/desktop/src-tauri/capabilities/main.json` lacks the narrow `core:event:default` permission required for the React client to subscribe to Rust-emitted lifecycle events. Successful `runtime.shutdown` currently discards `_shutdown_session()`'s observed `flushed` result and returns only `status`, so Rust/UI cannot report flush truth directly. `backend.ready` is backend readiness only, never session readiness. React StrictMode can remount effects during development, requiring idempotent start/listen handling. Supervisor generation guards, bounded byte reads, exact Conda identity, Python-origin validation, deterministic pending failure, and app-exit shutdown remain required acceptance hazards rather than newly demonstrated defects.
- **Exact write-set expansion before edit:** Add `app/desktop/src-tauri/capabilities/main.json` for `core:event:default` only. The explicit Python shutdown result and its focused regressions remain within the already recorded `app/agent/desktop/service.py`, `app/tests/test_desktop_service.py`, and `app/tests/test_desktop_server.py` write set. No Shell/filesystem permission, dependency, lockfile, protocol version, or persistent format is added.
- **Verification:** Audit was read-only and reused the passing baseline; no application check was rerun.
- **Blockers:** None.
- **Next action:** Apply the two smallest confirmed fixes while the non-overlapping Rust and frontend lifecycle slices complete, then run integrated focused checks.
- **Evidence references:** Audit findings and line references are in the execution transcript; the audit changed no file.

## 2026-08-28 01:29 Asia/Taipei — Phase 01: shutdown truth and event capability checkpoint

- **Status:** Phase 01 remains `In progress`; implementation attempt `1` continues.
- **Changes:** `DesktopService.runtime.shutdown` now preserves `_shutdown_session()`'s explicit `flushed` result and returns it on successful and idempotent graceful shutdown. Focused expectations cover the server wire result and repeated runtime shutdown. The main WebView capability adds only `core:event:default` beside the existing Tauri-version permission so React can subscribe/unsubscribe to the named Rust event; no Shell or filesystem capability exists.
- **Verification (observed, Conda `app`):** From `app/`, `poetry run pytest tests/test_desktop_service.py tests/test_desktop_server.py -q` passed `25` tests with one existing LangChain deprecation warning in `0.14s`.
- **Limitations:** Rust must consume `data.flushed` and keep forced termination distinct; integrated Tauri capability/event behavior remains to be exercised.
- **Blockers:** None.
- **Next action:** Integrate the Rust supervisor and frontend lifecycle client, then run all Phase 01 focused checks and fake-child traces.
- **Evidence references:** Exact focused-test output is in the execution transcript; no provider, RAG, store, extension, or real-data operation occurred.

## 2026-08-28 01:33 Asia/Taipei — Phase 01: event-capability correction

- **Status:** Phase 01 remains `In progress`; implementation attempt `1` continues.
- **Disproved assumption:** The earlier audit treated `core:event:default` as a listen/unlisten-only capability. Direct inspection of Tauri's generated ACL manifest showed that the default set also grants WebView `emit` and `emit_to` commands.
- **Correction:** `app/desktop/src-tauri/capabilities/main.json` now grants only `core:event:allow-listen` and `core:event:allow-unlisten` beside the existing `core:app:allow-tauri-version`. This supersedes the broader permission wording in the 01:28 and 01:29 entries; no Shell, filesystem, event emit, or event emit-to permission is granted.
- **Verification:** Generated ACL inspection is observed evidence; integrated Tauri listen behavior remains in the pending dev trace.
- **Blockers:** None.
- **Next action:** Finish frontend focused tests, review both implementation slices, then run the complete Phase 01 focused command set.
- **Evidence references:** Generated `app/desktop/src-tauri/gen/schemas/acl-manifests.json` documents the exact event permission composition; the generated file was read-only.

## 2026-08-28 01:47 Asia/Taipei — Phase 01: integrated supervisor and desktop lifecycle verification

- **Status:** Phase 01 remains `In progress`; implementation attempt `1` succeeded and only the scoped checkpoint commit remains.
- **Changes:** Added one standard-library Rust supervisor with an exact validated Conda interpreter launch, one bounded serialized writer, byte-bounded stdout parsing, request correlation/timeouts, generation guards, stderr counts, deterministic pending failure, graceful/forced shutdown truth, restart, and Tauri app-exit cleanup. Added the named typed Tauri command/event seam, listen/unlisten-only WebView capability, pure TypeScript lifecycle client/reducer, bounded diagnostics/errors, and the conversation-centered React shell. Python `runtime.shutdown` now returns the observed `flushed` result. No dependency, manifest dependency set, lockfile, protocol version, persistent format, Shell capability, or filesystem capability changed.
- **Review corrections:** Cross-layer review caught and fixed the shutdown-report-versus-snapshot client mismatch, stale startup command responses, restart-after-termination-failure truth, cross-generation stale shutdown reports, and a writer-thread self-retention leak. A stable-tree read-only review then found no remaining confirmed defect. Local Tauri 2.11.5 and tauri-runtime-wry 2.11.4 source confirms `ExitRequested` invokes the callback synchronously before exit advances, so the bounded synchronous cleanup is safe without a prevent/second-exit loop.
- **Focused verification (observed, Conda `app`, no provider):** From `app/`, `poetry run pytest tests/test_desktop_protocol_contract.py tests/test_desktop_service.py tests/test_desktop_server.py -q` passed `95` tests with one existing LangChain deprecation warning in `0.15s`. From `app/desktop/`, `npm test` passed `79` tests; `./node_modules/.bin/tsc --noEmit` exited `0`; `cargo test --manifest-path src-tauri/Cargo.toml` passed `25` library tests plus empty binary/doc targets in `0.19s`; `git diff --check` passed. The Rust matrix includes readiness, timeout, wrong Conda identity, unsupported protocol version, request event/result, duplicate id, malformed/oversized output, bounded stderr, graceful/forced/concurrent shutdown, crash/pending failure, restart/generation isolation, settled command responses, and writer/child release.
- **Real Tauri trace (observed):** `npm run tauri dev` built and opened the WSL/Linux Tauri window. Computer Use visual QA observed stopped, starting, backend-ready, shutting-down, stopped-with-`flushed` confirmation, second-generation start, user-driven restart to generation 3, and bounded runtime details reporting Python `3.13.14`, backend `0.1.0`, protocol `v1`, Conda `app`, both providers not configured, Ollama not checked, and MCP disabled. One exact child, PID `47305` with command `/home/minervamuses/miniconda3/envs/app/bin/python -m agent.desktop.server`, was resolved read-only and sent `SIGKILL` to simulate a crash; the GUI truthfully showed `BACKEND_CRASHED`, exposed `Restart backend`, displayed `Restarting backend`, and recovered to backend-ready generation 4. It then shut down gracefully. The dev harness was ended with Ctrl-C (expected harness exit `1`/`KeyboardInterrupt`), and no backend or Tauri process remained.
- **Safety boundary:** No session was created, no live provider or Extended Thinking trial was started (`0 / 3` remains), no actual `/init` or `/ingest` construction ran, and no RAG/store/extension/real-user data was read or mutated. Fake-child temporary directories were removed.
- **Limitations:** Phase 01 intentionally proves only enough session wiring through focused fake/service tests; conversation behavior begins in Phase 02. The WSLg host exposed only a pane-level accessibility tree, so visual state was verified from fresh screenshots and bounded coordinate actions rather than semantic element indices.
- **Blockers:** None.
- **Next action:** Stage only the declared Phase 01 files, inspect the cached diff/name set, create the authorized local checkpoint commit, record its hash, and reload durable sources for Phase 02.
- **Evidence references:** Exact automated command output, stable-tree review findings, Tauri runtime source excerpts, process identity checks, and Computer Use screenshots are in the execution transcript; no generated evidence file was added.

<!-- Append material runtime entries in this form:

## YYYY-MM-DD HH:MM TZ — Phase NN: event

- Status: previous → current
- Authorized scope: launch message plus phase file
- Exact write set: paths intended or changed
- Existing overlap: user-owned changes preserved
- Hypothesis/attempt: concise cause and attempt number
- Changes: observed summary
- Verification: exact command/procedure and pass/fail/skipped/unavailable result
- Limitations: residual risk or None
- Blockers: exact blocker or None
- Next action: next autonomous checkpoint
- Evidence references: artifact/context/review path or None
-->
