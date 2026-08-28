# Agent Repository Knowledge

> Managed by $infrastructure. Live repository code, tests, configuration, and authoritative documentation override this folder when they disagree.

## Current audit

- Last audited: 2026-08-28T18:25:57+08:00
- Repository baseline: branch `GUI` at `f47fb2f9ff9a6814a0e287a56cde0accec7cc237`, aligned with `origin/GUI`.
- Working-tree state reviewed: tracked worktree and index clean; `for_agents/` is ignored and untracked. The six commits since the previous audit were reviewed, including the completed desktop GUI implementation and record consolidation.
- Areas inspected: root instructions and READMEs; Poetry, Conda, npm, Cargo, Tauri, protocol, Git, ignore, and line-ending configuration; agent session/turn/tool/history/skill/extension boundaries; citation and RAG risk anchors; the tracked Python desktop server/service/catalog and fixture seam; Rust protocol/supervisor; React protocol, conversation, trust, safe-content, and application surfaces; focused Python/TypeScript/Rust tests; current issues; and the completed desktop plan/build log.
- Known coverage gaps: no application test, build, live provider, Ollama, MCP, real citation-provider, real user-store, or native GUI run was repeated during this documentation-only audit. Current test/build results are taken from the completed tracked build log and are distinguished from checks run now. Generated stores, citation bundles, extension state, node modules, Rust target output, caches, and large artifacts were not inspected. Unchanged subsystems were checked through focused anchors rather than exhaustive file-by-file review.

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
