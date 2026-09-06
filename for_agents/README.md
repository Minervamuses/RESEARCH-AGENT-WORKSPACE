# Agent Repository Knowledge

> Managed by `$infrastructure`. Verify current behavior against live evidence and requirements against applicable instructions and contracts. This folder grants no authority to change either.

## Current audit

- Latest maintenance: 2026-09-06T16:30:41+08:00; scope is recorded below, not a blanket revalidation date.
- Repository baseline: branch `GUI` at `743aaaf1b57cde12e7b5c179226233df523ee1e2`; the existing local tracking ref `origin/GUI` was `88d137c` at audit start. No network fetch was performed during maintenance.
- Working-tree state reviewed: tracked worktree and index were clean at audit start. The index fingerprint was retained for the final comparison. All nine required files were tracked.
- Areas inspected: root `AGENTS.md`; the complete prior `for_agents/` set; changed-path history from the previous knowledge baseline `9745fd1` through current HEAD; root desktop launcher; main-model configuration and adapter call site; canonical conversation removal and reconstruction boundaries; React persisted-failure reconciliation, pending-retry merge, safe-content rendering, composer keyboard behavior, and responsive CSS; relevant Python and TypeScript test definitions; npm and Tauri manifests; Git tracking and ignore policy.
- Known coverage gaps: RAG, Citation, Extension, MCP, extended-thinking, and unchanged Agent internals retain their 2026-09-05 evidence unless a scoped row says otherwise. No Python, Cargo, Tauri, live-provider, Ollama, MCP, citation-provider, real-user-store, or native-WebKit run was executed during this documentation pass. Pre-maintenance verification at the same HEAD recorded `npm test` with 151 passing tests, `npm run build` exit 0, and headless-Chrome layout checks; those observations do not prove native Tauri geometry, 200% zoom, or live dependencies. Generated stores, bundles, logs, `node_modules`, `dist`, Rust `target`, caches, and large artifacts were not inspected.
- Git policy: all nine required files match the root `/for_agents/` ignore rule when tracking is disregarded, but all are already tracked, so none is effectively ignored. Maintenance did not change `.gitignore` or tracked state.

## Audit coverage

| Document | Mode | This pass scope and anchors | Last substantive validation or source baseline | Gaps |
|---|---|---|---|---|
| `architecture-map.md` | Revalidated | Root launcher, desktop source topology, React presentation, current model configuration, and changed entry points | 2026-09-06 at `743aaaf` | Native Tauri and packaged topology plus unchanged non-Desktop internals were not rerun |
| `invariants.md` | Revalidated and carried forward | Desktop protocol, presentation, conversation, keyboard, and wide-window typography contracts; other invariants checked only for changed dependencies | Desktop scope: 2026-09-06 at `743aaaf`; other claims: 2026-09-05 at `9745fd1` | No current Python, Cargo, or native execution; RAG, Citation, and Extension enforcement was not re-probed |
| `module-responsibilities.md` | Revalidated | Root launcher, Agent model-configuration boundary, canonical conversation ownership, and React, Tauri, and Python desktop ownership | 2026-09-06 at `743aaaf` | Unchanged modules retain 2026-09-05 source evidence |
| `data-flow.md` | Revalidated and carried forward | Desktop launch plus failed, pending, retry, keyboard, and terminal presentation flow | Desktop scope: 2026-09-06 at `743aaaf`; non-Desktop flows: 2026-09-05 at `9745fd1` | No live backend, provider, or native-UI journey in this pass |
| `dangerous-assumptions.md` | Focused check | External default-model availability, source-checkout launcher and runtime inheritance, large-content rendering, and Desktop conversation-concurrency assumptions | 2026-09-06 at `743aaaf`; untouched assumptions retain 2026-09-05 evidence | No live model lookup, multi-process test, native stress test, or packaged launch |
| `known-failure-modes.md` | Revalidated and carried forward | Recent Desktop reconstruction, persisted-failure refresh, retry, renderer, and maximized-window typography fixes | Desktop scope: 2026-09-06 at `743aaaf`; other failures: 2026-09-05 at `9745fd1` | No reproduction of active RAG, Citation, or Extension failures this pass |
| `testing-strategy.md` | Revalidated | Current manifests, changed test definitions, pre-maintenance frontend results, side effects, and structural-validator requirements | 2026-09-06 at `743aaaf` | Application suites were not executed during maintenance; native WebKit visual automation is absent |
| `future-work-backlog.md` | Focused check | Existing Desktop-related candidates and recently resolved canonical and GUI work | 2026-09-06 at `743aaaf`; unrelated candidates retain 2026-09-05 evidence | No backlog implementation or external issue refresh |

## Documents

- [Architecture map](architecture-map.md)
- [Invariants](invariants.md)
- [Module responsibilities](module-responsibilities.md)
- [Data flow](data-flow.md)
- [Dangerous assumptions](dangerous-assumptions.md)
- [Known failure modes](known-failure-modes.md)
- [Testing strategy](testing-strategy.md)
- [Future-work backlog](future-work-backlog.md)

## Task navigation

| Task | Start here | Then verify |
|---|---|---|
| Change canonical conversation persistence or reconstruction | `invariants.md` (`INV-006`, `INV-011`, `INV-016`), `data-flow.md` | `module-responsibilities.md`, `testing-strategy.md`, `known-failure-modes.md` |
| Adjust Desktop GUI behavior, rendering, or typography | `invariants.md` (`INV-017`, `INV-021`, `INV-022`), `module-responsibilities.md` | `data-flow.md`, `testing-strategy.md`, `known-failure-modes.md` |
| Diagnose startup, provider, or external-service behavior | `architecture-map.md`, `dangerous-assumptions.md` | `known-failure-modes.md`, `testing-strategy.md` |
| Change RAG, Citation, Skill, or Extension behavior | `architecture-map.md`, `invariants.md` | `data-flow.md`, `module-responsibilities.md`, `dangerous-assumptions.md` |

## Evidence labels

- **Confirmed**: directly supported by current code, tests, configuration, authoritative docs, or observed command output.
- **Inferred**: strongly suggested by current evidence but not guaranteed or fully enforced.
- **Unknown**: material evidence is missing, contradictory, inaccessible, or not inspected.

## Usage

Read this index and the relevant subject files before broad changes. Verify claims against live code and tests before acting. Invoke `$infrastructure` again after structural or contract changes. Ordinary or ignored Markdown is not automatically loaded by future agents; explicitly read this directory.
