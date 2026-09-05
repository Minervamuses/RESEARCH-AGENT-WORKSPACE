# Agent Repository Knowledge

> Managed by $infrastructure. Live repository code, tests, configuration, and authoritative documentation override this folder when they disagree.

## Current audit

- Last audited: 2026-09-05T13:03:47+08:00
- Repository baseline: branch `GUI` at `9745fd1e22f2ee78dac19194a7df2f2bc311a607`, aligned with `origin/GUI` at audit start.
- Working-tree state reviewed: tracked worktree and index were clean at audit start. The changed-path history from the prior documented baseline (`f47fb2f` to current HEAD: 99 commits and 140 paths) was reviewed, with current implementation/tests rechecked at the affected boundaries. All nine `for_agents/` files are tracked even though root `.gitignore:21` also matches `/for_agents/`; this audit did not alter the ignore rule or index before the requested final commit.
- Areas inspected: root instructions and current/stale user docs; Poetry, Conda, npm, Cargo, Tauri, protocol, Git, ignore, and line-ending configuration; canonical conversation/session/turn/history retirement; one-shot Skill projection and the Citation exception; tool/extension/citation/RAG risk anchors; Python desktop service/catalog/fixture; Rust supervision and long-request liveness; React final-only conversation/trust/safe-content surfaces; focused Python/TypeScript/Rust tests; issues 01-09; and the original GUI, corrective, and canonical-conversation plan/build logs.
- Known coverage gaps: no application suite, build, live provider, Ollama, MCP, real citation-provider, real user-store, migration, or native GUI run was repeated during this documentation-only audit. Current pass results cited here come from tracked build logs and current tests, not a rerun. The canonical-conversation plan still lacks exact native `720x560` and 200% zoom evidence; the corrective plan separately remains blocked under its own broad-rerun authority. Generated stores, citation bundles, extension state, node modules, Rust target output, caches, and large artifacts were not inspected. RAG, citation, and extension internals were sampled at unchanged high-risk anchors rather than exhaustively reread.

## Documents

- [Architecture map](architecture-map.md)
- [Invariants](invariants.md)
- [Module responsibilities](module-responsibilities.md)
- [Data flow](data-flow.md)
- [Dangerous assumptions](dangerous-assumptions.md)
- [Known failure modes](known-failure-modes.md)
- [Testing strategy](testing-strategy.md)
- [Future-work backlog](future-work-backlog.md)

## Evidence labels

- **Confirmed**: directly supported by current code, tests, configuration, authoritative docs, or observed command output.
- **Inferred**: strongly suggested by current evidence but not guaranteed or fully enforced.
- **Unknown**: material evidence is missing, contradictory, inaccessible, or not inspected.

## Usage

Read this index and the relevant subject files before broad changes. Verify claims against live code and tests before acting. Invoke $infrastructure again after structural or contract changes. Ordinary or ignored Markdown is not automatically loaded by future agents; explicitly read this directory.
