# Research Agent Desktop GUI — Reusable Prompts

## How to Start

PROMPTS.md is not auto-loaded like AGENTS.md. To place it and the rest of the durable plan in the agent's attention, start or resume implementation by copying the complete block below into the Codex task. The short reference is intentional; the referenced section contains the durable reload loop and must be read before any write.

PROMPTS.md is reusable entry text, not an independent owner of scope, phase status, or evidence. Apply the latest user message and every applicable AGENTS.md. Within this user-reviewed bundle, GOALS.md owns stable intent, PLANS.md owns the execution contract, each phase file owns its bounded work, and build-log.md owns runtime truth. This file cannot override those sources.

    Read and follow the complete “Autonomous Start/Resume” section in harness/plans/2026-08-24-desktop-gui-completion/PROMPTS.md.

    I authorize the in-scope implementation described by that section, PLANS.md, and the selected phase across app/agent/, app/rag/, app/skills/, app/desktop/, app/tests/, and an existing minimal README surface. This explicitly includes more than three directly required production files; small internal Python/Rust/React/CSS/test modules; the single-child Rust/Tauri supervision model; backward-compatible protocol-v1 result/event additions; the exact bounded Python-owned project-name/ordered-session-ID catalog in Phase 02; the Python-owned conversation slash-command adapter in Phases 02–04; and the bounded GUI presentation and resolution of the existing Python-owned per-command Bash approval flow.

    I explicitly authorize directly required dependency or Conda-environment changes only through the matching existing Conda, Poetry, npm, or Cargo manager, with the matching environment definition, manifest, and lockfile updates where applicable and the recorded evidence required by PLANS.md. I also authorize the scoped local checkpoint commits required by PLANS.md, containing only the verified phase write set, its plan evidence, and the pre-existing desktop-bridge/test WIP actually reconciled by that checkpoint. Do not absorb unrelated dirty-tree changes, amend or rewrite history, switch branches/worktrees, or perform remote Git actions.

    I authorize the listed focused local checks and the first Phase 05 final set exactly as specified there: one `poetry run pytest` from app/; one `npm test`, one `cargo test --manifest-path src-tauri/Cargo.toml`, and one `npm run tauri -- build --no-bundle` from app/desktop/. This includes the Tauri command's configured frontend build and remains authorized if that first final set exceeds ten minutes. Use fake providers and temporary data by default. A bounded live/paid-provider verification call is authorized only when it materially improves verification under PLANS.md: notify me once before the first such call for the whole plan, record that notice and the exact operation, model, and temporary-data boundary in build-log.md, and never inspect, disclose, edit, or copy credential values or mutate real user data. A second expensive broad pass or expensive attempt requires fresh authority. Do not execute an arbitrary real GUI Bash command as verification; change existing persistent formats/schemas or expand the approved Phase 02 catalog; restore user-deleted legacy artifacts; edit AGENTS.md; deploy; publish; or release.

    Continue autonomously across phase boundaries until the entire plan is complete or every meaningful remaining path has a genuine fresh-authority/external-state blocker. Do not stop after a successful phase. Skip a Blocked phase when another independent phase is eligible, and batch any final authority requests into one message.

Sending only “work on the next phase” is not equivalent to the bounded authorization above. When a later request intentionally narrows or expands it, the latest user message wins and must be recorded in build-log.md.

## Autonomous Start/Resume

Work on the long-horizon plan at harness/plans/2026-08-24-desktop-gui-completion as one continuous autonomous run.

### Durable Reload

Before the first write, read items 1–7 completely where they exist, then inspect the affected live surfaces and current diffs or metadata for item 8:

1. Every applicable AGENTS.md from repository root to the target files.
2. This PROMPTS.md file, including the authorization text in How to Start.
3. GOALS.md.
4. PLANS.md.
5. build-log.md.
6. The phase selected by the algorithm below.
7. Relevant existing context/ and code_review/ files, if they actually exist.
8. The current live source, tests, manifests, lockfiles, runtime evidence, and Git status for the selected work. Read complete lockfiles only when a proposed or observed dependency change makes that necessary.

Repeat the complete durable-file reload at every phase transition, after context compaction, after a new agent takes over, after a plan repair, and whenever those durable sources may have changed. At later transitions, re-inspect only the live files, diffs, manifests, tool identities, and other evidence that could have changed. Do not rely on remembered summaries when the durable files are available.

### Runtime and Ownership Gate

Confirm that the active root is /home/minervamuses/research-agent-workspace and that commands target WSL/Linux. Activate Conda environment app or use `conda run -n app`; verify that Python, Poetry, Node, npm, Cargo, and rustc belong to that environment, and do not infer runtime from the Windows UNC storage view or a default login shell. If the gate does not pass, perform only read-only discovery, stop all edits, installs, builds, tests, and mutating Git operations, and report the required environment switch or restart. Do not continue implementation on another phase.

Inspect the dirty worktree before editing. Treat every pre-existing modification, deletion, and untracked file as user-owned unless durable evidence proves otherwise, including the desktop bridge/test WIP, user-deleted legacy design artifacts, and requested deletion of the older harness bundle. Record the exact in-scope write set and overlapping files in build-log.md; do not reset, restore, stash, absorb unrelated changes into a checkpoint commit, or overwrite user work wholesale.

### Continuous Selection Loop

1. Read the compact Resume Checkpoint and phase table in build-log.md.
2. Reconcile the latest user launch message with the recorded execution-authorization state. Before starting a phase, record whether the complete How to Start authorization was activated and any later narrowing or expansion.
3. Select the lowest-numbered phase that is Not started or In progress and whose dependencies in PLANS.md are Complete.
4. Never select a Blocked phase while another independent eligible phase exists.
5. Set the selected phase In progress, update the checkpoint, perform its read-only preflight, and execute only its plan.
6. Use existing tests or characterization first, implement the smallest causal slice, and run the cheapest relevant check.
7. Record the exact command/procedure and observed result. A planned command, code inspection alone, or builder narrative is not a passing result.
8. After a coherent in-scope checkpoint passes its focused verification, stage and create the scoped local commit required by PLANS.md, then record its hash. Include only the exact checkpoint write set, its plan evidence, and explicitly authorized pre-existing WIP; never absorb unrelated dirty-tree changes.
9. When all phase acceptance criteria have evidence, mark it Complete, reload the durable sources, and immediately select the next eligible phase.
10. If a check fails, diagnose one causal hypothesis at a time. After two focused implementation attempts fail for the same cause, mark only that branch Blocked and continue independent eligible work.
11. If live evidence invalidates future plan text, preserve stable GOALS.md intent unless a fresh explicit user decision changes it. Make the smallest evidence-driven correction to build-log.md, PLANS.md, PROMPTS.md, or affected not-yet-complete phase files, record why, reload, and continue.
12. End the run only when every required phase is Complete or every meaningful remaining path is Blocked by authority, missing external state, or an unsafe contradiction.

A completed source file, check, page, or phase is not a stopping condition. Do not ask the user to approve routine phase transitions.

### Authorization Rules

Treat every applicable AGENTS.md, the user's latest launch message, PLANS.md Authorization Envelope, and the selected phase's narrower scope and stop conditions together as the active authority. PROMPTS.md cannot broaden them. When the complete How to Start block is sent, proceed without repeated questions on the explicitly listed multi-file work, directly required internal modules and managed dependencies, scoped child-supervisor concurrency, backward-compatible protocol result/event additions, the exact Phase 02 catalog, the Python-owned conversation slash-command and Bash-decision adapters, isolated fake/temp tests, one-time-noticed bounded live/paid-provider verification under the recorded PLANS.md safeguards, scoped local checkpoint commits, and the first Phase 05 final command set.

Do not interpret plan text alone as authorization for:

- unmanaged, convenience-only, or out-of-scope dependency/environment changes, or any manager/manifest/lockfile change not directly required and evidenced under PLANS.md;
- changes to existing persistent formats/schemas, expansion of the exact Phase 02 catalog, or protocol-version/envelope changes;
- credential-value inspection, disclosure, editing, or copying; unbounded or repeated live/paid-provider use outside the recorded PLANS.md envelope; real user stores/roots; or arbitrary real GUI Bash execution as verification;
- unrelated architecture, full-dataset/model/GPU work, or a second expensive attempt;
- user-deleted legacy design artifacts, AGENTS.md, unrelated commits, commit amendment/history rewriting, branches/worktrees, push, merge, rebase, deploy, publish, or release.

Apply GOALS.md stable scope, non-goals, preserved invariants, and recorded user decisions, then the selected phase's specific stop conditions. If a prohibited action is still essential, document the exact need and block that branch. Continue all independent work except when the Runtime and Ownership Gate itself has failed. Only after no meaningful authorized work remains, ask once with the accumulated blockers, exact proposed files/actions, why the smaller alternative failed, and estimated time/usage/maintenance cost.

### Implementation and Verification Discipline

- Keep each change causally tied to the selected phase; do not clean up nearby defects.
- Preserve Python as policy/data owner, Rust as process/IPC owner, and React as presentation/interaction owner.
- Add only the smallest tests that distinguish the intended behavior. Reuse current fixtures and temp roots.
- Use repository or test-runner temporary directories for generated stores and files. Remove every manually created test root, scratch file, fake-provider output, and generated store after recording evidence; verify cleanup before completing the owning phase. Do not add large or persistent generated test data to the repository.
- Run focused checks during phases. Reserve the complete Python suite and the Phase 05 npm/Cargo/Tauri final commands for Phase 05 unless a narrower build is the cheapest way to reject the current change.
- Do not repeat an expensive command without a new hypothesis; a second expensive broad pass also requires fresh user authority.
- Never claim success from status flags when the representative user-visible result is wrong.
- Record secret-safe evidence in build-log.md at phase start, meaningful failures/checkpoints, completion, and before any stop.
- Create context/ only for a material discovery and code_review/ only after a real review.

### Completion Report

When all phases are Complete, report the user-visible outcome first, then exact changed files grouped by subsystem, scoped local checkpoint commit hashes, checks actually run and their results, preserved constraints, and any optional limitations. Do not continue polishing, create an extra completion-only commit, package artifacts, or release.

When all remaining paths are Blocked, provide one consolidated request. Include what was completed, each blocker and evidence, the smallest proposed authority expansion, and what can remain intentionally unavailable.

## Execute One Phase — Explicit Diagnostic Override Only

This is not the default implementation entry and must never be selected merely because a phase completed. Use it only when the user's current message explicitly asks to isolate one named phase for diagnosis, review, or repair.

Read the same durable sources and runtime/ownership gate as Autonomous Start/Resume, then perform only the named bounded task. Preserve build-log.md status truth and do not mark unrelated work Complete. Once the explicitly bounded diagnosis, review, or repair is finished, return its evidence without silently expanding into application work the user excluded. A later normal Start/Resume invocation returns to the continuous cross-phase selector.

## Repair the Plan After Contradictory Evidence

Use this prompt only when the active execution loop cannot repair the plan safely:

    Read all applicable AGENTS.md and the complete PROMPTS.md, GOALS.md, PLANS.md, build-log.md, affected phase files, material context/review, and live repository evidence. Identify exactly which assumption was disproved. Preserve stable user intent and change GOALS.md only when the latest user message explicitly changes it; otherwise update only the affected roadmap, prompt, log checkpoint, and not-yet-complete phase text. Do not implement application code in this repair task. Run the plan validator and provide the changed plan files plus the evidence that required the repair.

## Final Evidence Review

Use this prompt for a separate final review when desired:

    Read all applicable AGENTS.md and the complete plan bundle. Compare GOALS.md and PLANS.md directly with the live diff, build-log.md evidence, focused/final check outputs, preserved user deletions, and representative fake/temp user journeys. Challenge every completion claim, especially process lifecycle, persistence ownership, prune confirmation, extension approvals, untrusted content, crash/shutdown reporting, accessibility, and Linux source-run instructions. Record only actionable findings in code_review/ and do not edit application code unless the user separately requests fixes.
