# Research Agent Desktop GUI — Execution Plan

## Plan Profile

- Plan root: harness/plans/2026-08-24-desktop-gui-completion
- Repository shape: local application; one Poetry Python distribution plus one Tauri/React desktop application.
- Runtime: WSL/Linux, using Conda environment app. Poetry owns Python resolution; existing npm/Cargo manifests own their ecosystem dependency graphs.
- Execution mode: autonomous within a recorded authorization envelope.
- Change risk: medium overall. The process, prune, and capability boundaries need targeted care, but this is a local single-user source-run application rather than a production service.
- Phase directory: phases/ because the repository's ignore rules make build/ unsuitable for durable tracked plans.

## Source-of-Truth Map

- Stable intent, scope, success conditions, defaults, and invariants: GOALS.md
- Phase graph, execution algorithm, authorization envelope, verification cadence, and overall completion: PLANS.md
- Copy-ready entry instructions that keep the durable plan in attention: PROMPTS.md
- Bounded phase work, acceptance, and handoff: phases/phase-*.md
- Current phase, checkpoint, attempt count, blockers, exact commands, and observed results: build-log.md
- Material implementation discoveries, created only when needed: context/
- Actual review findings, created only when a review occurs: code_review/
- Strongest implementation truth: live code, manifests, tests, worktree state, and observed behavior.

No file may duplicate mutable status from build-log.md. Planned commands are not evidence.

## Confirmed Baseline

- Repository root: /home/minervamuses/research-agent-workspace; supported runtime is WSL/Linux.
- Authoring checks observed Conda app with Python 3.13.14, Poetry 2.4.1, Node 24.18.0, and Cargo 1.97.1. Every execution preflight must recheck rather than relying on these dated values.
- app/desktop already has a Tauri 2 + React 19 + TypeScript 6/Vite shell, package-lock.json, Cargo.lock, a protocol-v1 contract in TypeScript and Rust, and protocol tests.
- app/desktop/src/App.tsx is still a shell. app/desktop/src-tauri/src/lib.rs has no complete child supervisor/command bridge.
- Tauri officially supplies commands/channels for React-to-Rust IPC and an official Shell plugin for spawning child processes and receiving output/process events. Tauri's narrower "sidecar" term means a bundled external binary and is not assumed for this Linux source-checkout application. The existing protocol-v1 request, result, event, and error fields are this application's bounded React/Rust/Python contract; extend that contract minimally instead of building a generic RPC framework. See https://v2.tauri.app/concept/inter-process-communication/, https://v2.tauri.app/develop/calling-rust/, https://v2.tauri.app/plugin/shell/, and https://v2.tauri.app/develop/sidecar/.
- The user has uncommitted Python bridge/test work under app/agent/desktop and app/tests/test_desktop*. It may change between plan authoring and execution and must be inspected and preserved in place.
- No application test, build, or live integration was run while authoring this revision.

## Autonomous Execution Contract

The main Start/Resume prompt runs the following loop; a phase boundary is a checkpoint, not a user gate.

1. Reload applicable AGENTS.md, PROMPTS.md, GOALS.md, PLANS.md, build-log.md, the selected phase, and relevant live files.
2. Revalidate runtime and dirty-tree ownership before the first write of the run. At later phase transitions, recheck only what could have changed.
3. Select the first phase that is Not started or In progress and whose dependencies are Complete. Skip Blocked phases while an independent eligible phase exists.
4. Record the phase start, exact current write set, and current checkpoint in build-log.md.
5. Implement only the phase's causal scope. Use the cheapest focused check that can reject the current hypothesis before broad validation.
6. After a coherent in-scope checkpoint passes its focused verification, create a local Git commit containing only that checkpoint and explicitly user-designated pre-existing changes; record the commit hash in build-log.md. Do not sweep unrelated dirty-tree changes into the commit.
7. Record exact results. If acceptance passes, mark the phase Complete and immediately continue the loop.
8. If two focused implementation attempts against the same cause fail, or fresh authority is genuinely required, mark that branch Blocked with evidence and continue another eligible branch.
9. If live evidence invalidates future work, repair the smallest affected part of this plan, record the reason, reload the durable files, and continue.
10. Stop only when all required phases are Complete, or when every meaningful remaining path is Blocked by fresh authority, missing external state, or an unsafe contradiction. Present all blockers in one concise request.

Do not ask for confirmation after a successful file, check, checkpoint, or phase. Do not repeatedly select a Blocked phase.

## Authorization Envelope

### Routine actions after the recommended launch prompt is sent

- Read repository instructions, source, tests, manifests, logs, and Git state.
- Modify in-scope files under app/agent/, app/rag/, app/skills/, app/desktop/, app/tests/, plus an existing minimal README surface when directly required by a phase.
- Touch more than three in-scope production files and add small internal Python, Rust, React, CSS, fixture, or test modules when the phase's listed outcome cannot be achieved cleanly in existing files.
- Use local Linux shell/Bash commands for implementation and verification inside the WSL workspace. This authorizes the Codex instance developing the project; it does not bypass the product agent's end-user Bash approval policy.
- Use a thin Rust owner for one long-lived Python child: start it, relay bounded messages, detect exit, and perform restart/shutdown. Phase 01 must first check whether Tauri's official Shell child-process API fits the active-Conda source-run contract; do not invent a bundled sidecar or generic process-management framework.
- Use Tauri's official command/channel IPC between React and Rust. Keep protocol-v1 as the small application-level contract shared by React, Rust, and Python, not a replacement transport stack.
- Make backward-compatible additions to protocol-v1 method result/event payloads and fixtures, without renaming/removing existing methods or changing the envelope/persistent format.
- Add the smallest bounded Python desktop adapter that reuses the existing slash-command parser and typed results. React sends raw composer text and never parses command syntax or infers command effects; knowledge and extension command families are enabled only by their owning phases.
- Preserve the product agent's existing per-command Bash decision: present the bounded command context with exactly Approve and Deny actions, resolve the pending request as a boolean decision, and execute only the exact approved request. Do not add conversation-wide approval in this plan.
- Add dependencies directly required by the GUI only through the matching existing manager: Conda for Conda-managed runtime requirements, Poetry for Python, npm for TypeScript, and Cargo for Rust. Update the matching manifest and lockfile; do not use direct pip/pipx, global installs, a project .venv, or another package manager.
- Use local fake providers, temporary data roots, fixtures, and repository-native tools by default. A bounded live/paid-provider call is allowed when it materially improves verification: notify the user once before the first such call in this plan, record that notice in build-log.md so resumed agents do not repeat it, and do not expose or retrieve the credential value.
- Remove manually created temporary test stores, data roots, and scratch directories after their evidence is recorded and before the owning phase is complete; verify cleanup without touching user data.
- Run focused checks during phases and one final appropriate Python suite, npm test/build, Cargo test/build or Tauri build pass even if the first such final pass may exceed ten minutes.
- Update this plan bundle with status/evidence and minimal plan repairs.
- Stage and create small local Git commits at verified checkpoints. Local commits are recovery points, not authorization to rewrite history or publish work.

The executing agent must record its exact live write set before editing. The root list above is an outer boundary, not permission for unrelated cleanup.

### Not authorized by the launch prompt

- Changing a persistent data format/schema, public CLI behavior, protocol version/envelope, or removing/renaming a public method.
- Adding a service, database, queue, cache, generic framework, broad compatibility layer, or unrelated concurrency model.
- Reading, displaying, editing, or copying credentials; mutating the user's real store/citation/extension roots; or bypassing the product agent's exact per-command Bash approval.
- Broad full-dataset/GPU/model sweeps, unbounded paid-provider use, a second expensive attempt, or unrelated benchmarks.
- Editing AGENTS.md.
- Pushing, merging, rebasing, rewriting history, switching branches/worktrees, deploying, releasing, publishing, purchasing, or changing a provider subscription.

If a non-authorized action becomes truly necessary, block only the affected branch, continue independent phases, and batch one request describing the exact files/action, why the smaller route failed, and expected time/usage/maintenance cost.

## Phase Roadmap

| Phase | Observable result | Dependencies | File |
|---|---|---|---|
| 01 — Desktop foundation | Existing Python WIP, the minimal application protocol, official Tauri IPC/process primitives where they fit source-run operation, lifecycle, and a startup/fatal-error fallback form one verified runnable vertical slice | None | phases/phase-01-desktop-foundation.md |
| 02 — Chat and conversations | A Codex-like sidebar opens, creates, restores, and continues separate conversations while assistant output streams incrementally in the main pane; its Python boundary owns a narrow reusable slash-command dispatch seam | Phase 01 | phases/phase-02-chat-session.md |
| 03 — Knowledge slash commands | Normal chat keeps agent-owned RAG behavior, while `/init`, `/ingest`, read-only `/sync`, and preview-confirmed `/prune` work in the conversation without a standalone Knowledge UI | Phase 02 | phases/phase-03-knowledge.md |
| 04 — Extensions and Bash approval | Slash-command extension management works with isolated roots, and an existing product Bash request is decided with per-request Approve/Deny buttons without a new approval policy | Phase 02 | phases/phase-04-extensions-trust.md |
| 05 — Acceptance and Linux delivery | Representative integrated journeys, one final broader verification pass, and source-run guidance provide honest completion evidence | Phases 02, 03, and 04 | phases/phase-05-acceptance-delivery.md |

Phases 03 and 04 are logically independent after Phase 02. The default selector follows numeric order, but if one is Blocked it proceeds with the other.

## Phase Boundaries and Verification Cadence

- Phase 01 uses "supervision" only to mean a thin Rust owner for one Python child: start it from the active Conda source-run environment, exchange bounded input/output, notice exit, and shut it down. React talks to Rust through official Tauri commands/channels. Phase 01 evaluates Tauri's official Shell child-process API before adding custom lifecycle glue, but does not bundle a sidecar merely to use that label; the app-specific protocol defines only the agent messages crossing the remaining boundary.
- Normal provider/tool failures such as HTTP 429 are delivered into the conversation so the agent can explain them. The minimal fallback outside chat exists only for failures that prevent the agent from answering at all, such as Python startup failure, child crash, or protocol incompatibility; there is no permanent Diagnostics application area.
- Phase 02 owns the persistent project/conversation sidebar, conversation restoration, ordered streaming answer lifecycle, and the narrow Python-owned composer-input/slash-command dispatch seam rather than a single disposable session. It does not implement Phase 03 or Phase 04 command behavior.
- Phase 03 preserves the agent's existing RAG tool use for normal questions and adds only the four knowledge-maintenance commands to the Phase 02 conversation route. It adds no Knowledge page, frontend semantic-search state, document/chunk explorer, management controls, or command-specific progress system.
- Phase 04 combines slash-command Extensions, the existing two-outcome product Bash decision, and targeted trust-boundary closure; security is also implemented locally in earlier phases and is not deferred to this audit.
- Each phase starts with relevant existing tests/characterization, then the smallest changed-layer checks. Exact test selectors are discovered from live tests and recorded in build-log.md rather than invented here.
- Do not rerun npm build, full Cargo tests, or the complete Python suite at every phase. Run focused tests while iterating and one appropriate broader/final pass in Phase 05.
- Manual UI checks use a fake/temp backend wherever possible. Live provider success is not required for completion, although one-time-noticed bounded calls are authorized when useful.
- A failed required check keeps the phase In progress or Blocked. An unrelated existing failure is recorded separately and is not silently fixed.

## Phase-Specific Write Surfaces

These are expected boundaries, not claims that every file will change:

- Phase 01: app/agent/desktop/, app/tests/test_desktop*, app/desktop/src-tauri/src/, app/desktop/src/protocol.ts, app/desktop/tests/, app/desktop/src/App.tsx, and app/desktop/src/styles.css.
- Phase 02: existing desktop React/state/protocol surfaces, directly required Python desktop/session adapters including the bounded slash-command seam, and focused tests.
- Phase 03: the existing conversation composer/result presentation, directly required Python desktop/slash-command/RAG adapters, and focused tests. Existing user-owned Knowledge protocol WIP is preserved but is not a reason to build or expose a Knowledge UI.
- Phase 04: existing desktop Extensions/UI/error/accessibility surfaces, directly required Python extension adapters, Tauri capability/config surfaces, and focused tests.
- Phase 05: tests/fixtures, existing desktop/source-run documentation, and only defects causally exposed by final acceptance.

Unexpected files outside these surfaces require a causal explanation in build-log.md; they do not automatically require a user stop if still inside the routine envelope.

## Plan Maintenance

- build-log.md alone owns current status and resume state. Update its compact checkpoint at phase start, after a meaningful check/failure, at phase completion, and before any stop.
- Keep stable intent in GOALS.md. A live discovery normally changes PLANS.md or a not-yet-complete phase, not the goal.
- Create context/ only for a discovery too material to explain concisely in build-log.md. Create code_review/ only for an actual review.
- Preserve failed evidence. Correct material entries append-only; do not rewrite history to make a phase look clean.
- After compaction, a new agent, or any phase transition, execute the PROMPTS.md reload sequence before writing.
- A reviewer may be used at final integration when it adds evidence; independent review is not mandatory ceremony after every phase.

## Overall Completion

- [ ] All five phase rows in build-log.md are Complete and no required branch remains Blocked.
- [ ] Every GOALS.md success condition maps to observed test, build, inspection, or user-visible acceptance evidence.
- [ ] Python, TypeScript, and Rust agree on protocol-v1 behavior and preserve the stated ownership/persistence boundaries.
- [ ] React-to-Rust communication uses Tauri's official command/channel IPC, Rust owns one source-run Python child through the narrowest verified process primitive, and the custom application protocol remains bounded to domain messages rather than becoming a generic RPC or supervisor framework.
- [ ] Focused checks and the single final broader verification pass have exact recorded results.
- [ ] Fake/temp representative Chat with agent-owned RAG, knowledge slash commands, Extensions, lifecycle, crash/recovery, and shutdown journeys pass without agent inspection/disclosure of credential values or real-data mutation.
- [ ] Every manually created temporary test root or scratch directory is removed after its evidence is recorded, without deleting user-owned data.
- [ ] Security/privacy/accessibility and the default, minimum, and 200%-zoom layouts have observed evidence.
- [ ] Linux source-run instructions are verified from the Conda app context and do not claim a standalone bundle.
- [ ] Pre-existing user WIP and deletions remain preserved and distinguishable; each plan-created verified checkpoint has a scoped local commit recorded without absorbing unrelated changes.
- [ ] Remaining optional limitations are stated honestly; no unmanaged dependency, credential exposure, Bash-policy bypass, real-data mutation, remote Git, deployment, or release action occurred.
