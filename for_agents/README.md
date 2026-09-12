# Agent Repository Knowledge

> Managed by `$infrastructure`. Current implementation and scoped observations describe behavior; applicable instructions and explicit contracts govern requirements. This folder grants no implementation authority.

## Current audit

- Latest maintenance: 2026-09-13T00:48:49+08:00; this timestamps the pass, not every retained claim.
- Repository: `/home/minervamuses/research-agent-workspace`; branch `GUI` at `a88d44d35f7e1438f23a6dfd595157248847e382`.
- Runtime verified: Windows-hosted agent delegates commands to Ubuntu-24.04 WSL; Linux Git, Conda `app` Python 3.13.14, Poetry 2.4.1, and Node 24.18.0. Repository instructions expressly permit this setup.
- Working-tree state reviewed: clean at entry, no staged or untracked work; compared changes since the prior audit at `743aaaf`. All nine knowledge files already existed and were read. Initial index SHA-256: `5392745031e4b9b677eab104edf62bca3acbdb94eeb46f61b14be434e4b2c34e`.
- Areas inspected: root instructions/manifests; changed session, Skill, extension, Citation, Desktop protocol/Python/React/Rust paths and relevant regression definitions; selected unchanged RAG anchors; archived final-check outputs/review at `bc2c94d`. No application modules were imported.
- Significant corrections: Citation is single-turn in CLI/Desktop; installer has bounded conversational continuation; extension activation rechecks hashes and apply uses a Linux file lock; earliest-year ties fail ambiguous; Desktop advertises its dispatchable command catalog and supports explicit Bash ask/bypass.
- Evidence gaps: no application tests, builds, native UI, live providers, MCP/Ollama, user stores, or generated artifacts were run/inspected in this pass. Historical native menu/Citation evidence uses fake model/fetch seams; fresh IME across restart and exact geometry/zoom remain unproven. Multi-level Thinking Effort remains deferred.
- Git policy: all nine files tracked; no ignore-rule matches (0/9), no effective ignore (0/9). The old `/for_agents/` ignore statement was stale. Ignore files stay unchanged. Maintenance preserves index bytes until the user's separately authorized commit/push step.
- Historical evidence: [final-check log](https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/bc2c94d40562e9606a9872bc922a36423b6a10a2/issue/final_check/build-log.md) and [check results](https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/bc2c94d40562e9606a9872bc922a36423b6a10a2/issue/final_check/evidence/phase-06-check-results.json) remain readable from local Git despite issue-folder cleanup. Their scope/results are recorded in [testing strategy](testing-strategy.md); removed plans are not active work.

## Audit coverage

| Document | Mode | This pass scope / anchors | Last substantive validation / source baseline | Gaps |
|---|---|---|---|---|
| architecture-map.md | Revalidated | Session/installer, extension and Desktop boundaries; configuration/manifests | 2026-09-13 source at `a88d44d` | No runtime topology launch |
| invariants.md | Revalidated | INV-009/013/014/018/019/022/023/024, completed replay under INV-006/011 | 2026-09-13 source/contracts/tests at `a88d44d` | Test definitions are not fresh runs; activation TOCTOU remains |
| module-responsibilities.md | Revalidated | Session/manager/Citation/desktop ownership and protocol consumers | 2026-09-13 at `a88d44d` | Other subsystem owners retained below |
| data-flow.md | Revalidated | One-shot Citation, installer cleanup/mode, extension lock/hash, desktop menu/permission/replay | 2026-09-13 at `a88d44d` | No effects executed |
| dangerous-assumptions.md | Revalidated | ASM-007/008/009 retired premises; ASM-014 characterization and runtime constraints | 2026-09-13 at `a88d44d` | Continuous writers and live model behavior unproven |
| known-failure-modes.md | Revalidated | FAIL-005/006/007/015 mitigations; FAIL-014 documentation conflict; FAIL-017 source symbol | 2026-09-13 at `a88d44d` | Historical reproductions were not rerun |
| testing-strategy.md | Revalidated | Current definitions, archived 1138/165 results, Rust red then focused green, build/native scope | 2026-09-13 source + records at `bc2c94d` | Only documentation validator executed now |
| future-work-backlog.md | Revalidated | BACKLOG-003/004/005/008/014 resolved; explicit issue09 deferral | 2026-09-13 at `a88d44d` | No new implementation authorized |
| RAG claims across architecture, ownership, flows, assumptions, failures and backlog | Focused check | `prune_orphans` and `rag.search`; unchanged-path comparison | Anchors checked 2026-09-13; broader evidence 2026-09-05 at `9745fd1` | Prior stale-inventory/empty-file probes inherited, not rerun |
| Other Agent/RAG/MCP/thinking claims across subject files | Carried forward | Prior account retained; no changed dependency requiring expanded inspection identified | 2026-09-05 at `9745fd1` | No new enforcement/runtime claims |
| Unchanged canonical history, final-only/large-content/CSS claims | Carried forward | Retained where recent changes did not alter their anchors | 2026-09-06 at `743aaaf` (older history evidence 2026-09-05) | Native resource/geometry, multi-process catalog/conversation safety not revalidated |

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

| Task | Read first |
|---|---|
| Change persistence or replay | [Invariants](invariants.md), [data flow](data-flow.md), [testing](testing-strategy.md) |
| Change Skills, ZIP installation or Citation | [Responsibilities](module-responsibilities.md), [flows](data-flow.md), [invariants](invariants.md) |
| Change Desktop menu or permissions | [Architecture](architecture-map.md), [invariants](invariants.md), [testing](testing-strategy.md) |
| Diagnose a failure / select optional work | [Failures](known-failure-modes.md), [assumptions](dangerous-assumptions.md), [backlog](future-work-backlog.md) |

## Evidence labels

- **Confirmed**: directly supported within the identified source/type/scope; source/test-definition inspection is not execution.
- **Inferred**: supported interpretation, not an established guarantee.
- **Unknown**: material evidence missing or uninspected.
- Confidence, normative authority, and freshness are separate; use the coverage rows and claim-level limits.

## Usage

Read this index and relevant subjects explicitly before broad changes. Check current code for behavior and applicable instructions/contracts for obligations. Invoke `$infrastructure` after structural drift. These files are not automatically loaded by future agents. Backlog entries are candidates, and archived plans do not authorize work.
