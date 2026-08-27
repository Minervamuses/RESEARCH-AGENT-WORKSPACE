# Phase 01 — Desktop Foundation

## Objective

Use the pre-existing repository foundation—the user-owned Python desktop-bridge WIP, committed protocol-v1 code, and current Rust/Tauri/React shell—as inputs to build the first runnable vertical slice. These files are baseline inputs; Phase 01 implementation and verification have not started. The visible result is a desktop window that truthfully reports backend/session state and can start, stop, restart, and survive child failure without corrupting protocol traffic.

## Sources

- Repository-root AGENTS.md
- GOALS.md, PLANS.md, PROMPTS.md, and build-log.md
- Live app/agent/desktop/, app/tests/test_desktop*, app/desktop/, manifests, lockfiles, and Git status
- Existing session, RAG, citation, and extension APIs reached by DesktopService

Repository-root AGENTS.md, GOALS.md, and PLANS.md are authoritative for this phase. Treat observed live repository behavior as stronger evidence than stale planning assumptions.

## Dependencies and Entry Conditions

- No phase dependency.
- The recommended launch prompt has activated the PLANS.md authorization envelope.
- WSL/Linux, Conda app, Poetry, Node, and Cargo identities are consistent.
- The executing agent has inspected and recorded the live dirty-tree overlap. Existing app/agent/desktop and test work is user-owned input, not a disposable baseline.

## In Scope

- Reconcile and complete the Python protocol, service, and NDJSON stdio-server boundary.
- Keep protocol-v1 envelopes, method names, ordering, size bounds, origin rules, and secret-safe DTO validation aligned across Python, TypeScript, Rust, and fixtures.
- Supervise one Python child from Rust/Tauri with explicit startup/readiness, ordered stdin writes, stdout parsing, bounded pending requests, stderr diagnostics, crash handling, graceful shutdown, and restart.
- Expose a narrow typed Tauri command/event surface to React.
- Replace shell placeholders with truthful lifecycle status and bounded startup, degraded, fatal-error, and recovery surfaces inside the conversation-centered shell.
- Add the smallest focused tests needed to protect these behaviors.

## Non-goals

- Chat page behavior beyond enough wiring to prove a session can be created.
- Knowledge-maintenance or extension-management slash-command behavior beyond enough shared transport to prove the Phase 01 session slice.
- Unrelated or unmanaged dependencies, protocol version/envelope changes, generic RPC abstractions, multiple children, automatic infinite restart, or a frontend shell/filesystem capability.
- Reformatting or rewriting user WIP merely to match a preferred style.

## Implementation Plan

### 1. Reconcile the live contract

- Read the current Python WIP and all three protocol implementations before editing.
- Run the cheapest existing desktop protocol/service/server characterization that is valid in the live tree.
- Resolve only demonstrated mismatches: method/result schemas, request correlation, event ordering, error mapping, size limits, stdout discipline, readiness, and shutdown.
- Preserve existing public callers. Any required result/event addition must be backward-compatible and represented in Python, TypeScript, Rust, and the shared fixture/test surface.
- Keep human-readable logs on stderr. Stdout carries NDJSON protocol messages only.

### 2. Complete the Python application boundary

- Keep one DesktopService as the facade over ChatSession and current domain APIs.
- Make bootstrap, session creation, request dispatch, busy rejection, and shutdown behavior explicit.
- Return bounded safe errors and diagnostic summaries, never raw traceback, secret, tool payload, or provider response.
- Ensure shutdown reports the real recent-turn flush outcome and does not claim success after a crash/forced kill.

### 3. Add the narrow Rust supervisor and IPC

- First evaluate Tauri's official Shell child-process API against the active-Conda source-run contract required by PLANS.md. Prefer std and existing Tauri runtime facilities when they avoid an unnecessary dependency. Add a directly required crate only through Cargo within the PLANS.md authorization envelope; do not add Tokio or an unrelated crate for convenience.
- Spawn the backend without a user-controlled shell string and validate the runtime identity/readiness handshake.
- Use one serialized writer and one reader path so concurrent WebView requests cannot interleave NDJSON.
- Correlate bounded pending requests, apply finite timeouts, reject duplicates, and fail all pending work deterministically on malformed output or child exit.
- Drain bounded stderr into diagnostics without echoing secrets or treating stderr as protocol.
- Make shutdown idempotent: request graceful Python shutdown, wait a bounded interval, then terminate the child if necessary while reporting the distinction.
- Expose only named Tauri commands/events required by the typed frontend client.

### 4. Present lifecycle and bounded recovery surfaces

- Model starting, backend-ready, session-ready, busy, degraded, crashed, restarting, shutting-down, and stopped states explicitly.
- Show safe runtime/configuration/provider/MCP/data-path presence, protocol version, and recovery actions only where startup, degradation, or fatal failure makes them relevant; do not add a permanent top-level Diagnostics area.
- Prevent feature actions until their actual readiness preconditions hold.
- Keep retry/restart user-driven and bounded; do not hide a crash behind an endless automatic loop.
- Establish the Codex-like persistent left-sidebar/main-workspace frame and minimum viewport behavior. Project and conversation population, selection, restoration, and continuation remain Phase 02 work.

## Verification

- From app/, run `poetry run pytest tests/test_desktop_protocol_contract.py tests/test_desktop_service.py tests/test_desktop_server.py -q`; add only missing discriminating cases to those focused surfaces.
- From app/desktop/, run `npm test` and `./node_modules/.bin/tsc --noEmit` using the already resolved dependency tree.
- From app/desktop/, run `cargo test --manifest-path src-tauri/Cargo.toml` so the protocol and new supervisor tests execute in the focused desktop crate.
- Exercise a local fake-child lifecycle trace covering readiness success and timeout, wrong Conda identity, protocol-version mismatch, request/result, request event, bounded stderr, duplicate request id, oversized or malformed output, graceful shutdown, forced termination, crash, pending-request failure, and restart.
- From app/desktop/, run `npm run tauri dev` far enough to observe the conversation-centered shell plus startup, degraded, fatal-error, recovery, and lifecycle transitions without a live provider.
- Record exact commands, runtime, result, and any unavailable item in build-log.md. Do not run the complete Python suite or final Tauri build yet unless required to diagnose this phase.

## Acceptance

- [ ] Existing user WIP is preserved and its reconciled contribution is distinguishable from new edits.
- [ ] Python, TypeScript, Rust, and fixtures accept/reject the same applicable protocol-v1 traces.
- [ ] One child is supervised without shell interpolation, stdout contamination, write interleaving, orphaned pending requests, or secret-bearing general UI errors.
- [ ] Bounded startup, degraded, and fatal-error surfaces show observed runtime/backend/session/capability state and actionable recovery without creating a permanent Diagnostics area.
- [ ] Wrong Conda identity, readiness timeout, protocol-version mismatch, malformed or oversized output, and forced termination produce bounded truthful failure states and do not claim session readiness or successful persistence.
- [ ] Graceful and forced shutdown outcomes are distinguishable.
- [ ] Focused checks and the fake-child lifecycle trace pass with recorded evidence.
- [ ] Any directly required dependency or manifest/lockfile change used the matching package manager within the PLANS.md authorization envelope and has its exact reason and evidence recorded.
- [ ] No unmanaged dependency, AGENTS.md, persistent-format, real-data, remote-Git, branch/worktree, deployment, or release change occurred.

## Handoff

Mark Phase 01 Complete only after all required evidence exists. At each verified checkpoint, create the scoped local commit required by PLANS.md and record its hash in build-log.md without absorbing unrelated dirty-tree work. Reload the durable sources and continue automatically to Phase 02. If Phase 01 is Blocked, record the exact branch and continue only work that is genuinely independent and safe; do not stop merely to announce the checkpoint.
