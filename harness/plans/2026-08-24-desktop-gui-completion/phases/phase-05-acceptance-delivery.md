# Phase 05 — Acceptance and Linux Delivery

## Objective

Validate the integrated GUI on representative fake/temp cases, run one proportionate final regression/build pass, fix only defects causally exposed by that evidence, and leave verified Linux source-run guidance with honest limitations.

## Sources

- Repository-root AGENTS.md, GOALS.md, PLANS.md, and the Phase 01–04 plan files are user-reviewed authoritative sources for this phase.
- build-log.md, completed phase evidence, and material context/review provide runtime truth; a phase status or planning claim alone is not evidence.
- PROMPTS.md is reviewed and reconciled reusable execution text rather than an authoritative source for this phase; it cannot override the approved intent or authorization in the sources above.
- Live diff, tests, manifests, existing documentation, Tauri configuration, current Git status, and the user's recorded decisions

## Dependencies and Entry Conditions

- Phases 02, 03, and 04 are Complete.
- No required earlier acceptance item is represented only by a plan or unverified claim.
- The launch authorization in force is consistent with applicable AGENTS.md and PLANS.md and covers the first appropriate final local regression/build pass even if it runs beyond ten minutes.

## In Scope

- Integrated fake/temp acceptance of startup/lifecycle diagnostics, Chat/controls with agent-owned RAG, knowledge slash commands, Extensions, crash/restart, and graceful/forced shutdown.
- One final broader Python regression pass and one final desktop npm/Cargo/Tauri test/build pass appropriate to the live scripts and runtime.
- Targeted repair of defects directly exposed by these checks, with focused re-verification.
- Minimal existing documentation for Conda/Poetry plus npm/Cargo source-checkout install, dev, test, and build commands.
- Final evidence map, limitations, and read-only/dirty-tree verification.

## Non-goals

- Unbounded or repeated live/paid-provider use, credential-value inspection/disclosure/editing/copying, actual Bash, real stores/extension roots, full datasets, GPU/model sweeps, standalone bundles, installers, Windows-native support, CI, deploy, release, or unrelated cleanup.
- Repeating all expensive commands after every small repair. Rerun the narrow failed check first; repeat a broad check only when the fix could affect its result and the remaining authorization permits it.
- New implementation reports or architecture documents.

## Acceptance Matrix

1. Startup and Diagnostics: correct Conda/Linux identity; protocol, runtime, backend, session, optional-provider, MCP, and data-path diagnostics; readiness; presence-only secret-safe configuration; degraded optional services.
2. Chat and controls: a minimal integrated fake journey creates or opens representative conversations A and B, streams and safely reconciles one authoritative answer in A, switches to B and back without cross-contamination, restarts, reopens and continues A, and observes busy rejection, Python-owned state controls, recoverable error, and safe content.
3. Agent-owned RAG: a normal fake conversation invokes the existing Python RAG tool path when scripted, reports available/degraded semantic behavior honestly, and exposes no standalone Knowledge UI.
4. Knowledge slash commands: composer-entered `/init`, `/ingest`, read-only `/sync`, and preview-then-`--yes` `/prune` bypass the model, enforce desktop Linux path safety, leave the expected temp-store state, and remove all scratch artifacts.
5. Extensions: temp status/no-call, fake preview, exact decisions, apply, restart-required, loaded revision.
6. Lifecycle: child crash with pending request, restart, normal flush result, forced termination distinction.
7. Trust/accessibility/layout: one fake Bash approval executes the exact staged request once through an execution spy, denial executes zero times, and capability/CSP/link, keyboard/focus, and default/minimum/200%-zoom reachability checks pass without executing an arbitrary real command.

## Implementation and Verification Plan

### 1. Reconcile evidence before running broad work

- In build-log.md, create an explicit crosswalk from every GOALS.md success condition, every PLANS.md Overall Completion criterion, every Phase 05 matrix row and acceptance item, and every relied-upon earlier phase acceptance item to an exact observed command, procedure, result, or evidence reference. A phase status, plan text, or unverified narrative is not evidence.
- Run only missing focused cases first. Do not rerun passing expensive checks without a causal reason.
- Confirm fake providers and temporary data roots are the default, record their boundaries and cleanup procedures, and do not retain generated stores or bulky test fixtures in the repository. For any materially useful bounded live/paid-provider check, also record the one-time user notice, exact operation/model, provider seam, temporary-data boundary, and cleanup evidence required by PLANS.md.

### 2. Execute integrated representative journeys

- Reuse the exact fake-child/backend launch seam and temporary-root map recorded by the completed earlier phases; their absence means the prerequisite evidence is incomplete and must not be replaced by an improvised Phase 05 harness.
- Use the real Tauri/Rust/Python/React boundaries where applicable, substituting fake provider/search services, a fake Bash runner/execution spy, and temp stores/roots at their recorded Python domain seams by default. A bounded live/paid-provider call may be substituted only at that same recorded seam under the PLANS.md safeguards; it remains optional and cannot replace required fake/temp evidence.
- Exercise the minimum cross-phase Chat journey in matrix row 2 after the Phase 03/04 integrations, including A/B isolation, restart restoration/continuation, ordered provisional streaming when supported, and one authoritative finalized answer or the verified bounded fallback.
- Observe actual user-visible state rather than relying only on backend status flags.
- Record failures precisely and repair only their direct cause. After two failed focused attempts for the same cause, block and report rather than rewrite broadly.

### 3. Run the final regression/build pass

- Re-read live package scripts, Tauri configuration, and repository instructions immediately before execution. If these exact commands are no longer supported, record the contradictory evidence and repair this unstarted plan rather than substituting a guessed command.
- With Conda `app` active, from `app/`, run `poetry run pytest` once as the complete Python regression.
- With the same Conda `app` environment active, from `app/desktop/`, run `npm test` once and `cargo test --manifest-path src-tauri/Cargo.toml` once.
- From `app/desktop/`, run `npm run tauri -- build --no-bundle` once. Its configured `beforeBuildCommand` runs `npm run build`, so do not run a separate production frontend build unless the live Tauri configuration has changed and the reason is recorded.
- Do not use `cargo check` as a substitute for the required Tauri source build. A required unavailable command keeps the plan Blocked with the exact reason and residual risk.
- If the first authorized broad run exposes a failure, use focused checks for repairs. Do not begin a second expensive broad pass without both a new hypothesis and fresh user authority.

### 4. Verify delivery guidance and boundaries

- Update only an existing minimal README surface with the verified Conda app activation, Poetry Python install/use, npm/Cargo desktop commands, dev launch, tests, build, and known source-run limitations.
- Execute the documented no-live-provider startup path from the supported runtime.
- Confirm the user-deleted legacy design artifacts remain deleted, no standalone Knowledge frontend was introduced, pre-existing user WIP is preserved, the old harness deletion was not restored, and all manually created test artifacts were removed.
- Reconcile every manifest/lockfile change against the initial state and earlier phase evidence. Each change must be directly required, explicitly authorized, made through the matching package manager, and recorded with its reason and evidence; no unauthorized or unmanaged manifest/lockfile change may remain.
- Reconcile final Git status, diff, and recorded scoped checkpoint commit hashes against the initial dirty-tree ownership and each phase write set. No unrelated user change may be absorbed and no unauthorized external or Git action may occur.
- Summarize optional limitations without converting them into hidden requirements.

## Acceptance

- [ ] All seven matrix rows have observed evidence through real application boundaries with fake/temp substitutions where specified.
- [ ] Every GOALS.md success condition, every PLANS.md Overall Completion criterion, every Phase 05 matrix row and acceptance item, and every relied-upon earlier acceptance item maps to exact observed evidence in build-log.md; no mapping relies only on a phase status or plan claim.
- [ ] Required focused checks and the single final broader Python/npm/Cargo/Tauri pass succeed, or the overall plan remains Blocked with an exact consolidated request.
- [ ] Source-run instructions are verified in WSL/Linux from the Conda app context and correctly describe Poetry, npm, and Cargo roles.
- [ ] User-deleted legacy design artifacts, user WIP, persistent data, credential confidentiality, manifests/lockfiles, and Git/external state remain within the authorized boundaries; manually created test artifacts are absent.
- [ ] No critical user-visible defect or unresolved required review finding remains.

## Evidence to Record

- Record the final criterion-to-evidence crosswalk, exact commands/manual procedures, Conda/Linux identity, concise pass/fail/skipped/unavailable results, fake/temp boundaries and cleanup, final dirty-tree reconciliation, and scoped checkpoint commit hashes in build-log.md.
- Create or update context only for a material discovery whose omission could change completion or recovery. Record actual review findings under code_review/ only when a real review occurs.

## Handoff

When acceptance and the complete evidence crosswalk pass, mark Phase 05 and the overall plan Complete, update the final Resume Checkpoint, and return the concise completion report required by applicable AGENTS.md and PLANS.md. PROMPTS.md has been user-reviewed and aligned but remains non-authoritative and cannot change that completion standard. If completion is blocked, issue one consolidated request only after all other authorized work is exhausted.
