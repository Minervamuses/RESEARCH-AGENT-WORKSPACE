# Agent Repository Knowledge

> Managed by `$infrastructure`. Current implementation and scoped observations describe behavior; applicable instructions and explicit contracts govern requirements. This folder grants no implementation authority.

## Current audit

- Latest maintenance: 2026-09-14T12:32:05+08:00; this timestamps the pass, not every retained claim.
- Repository: `/home/minervamuses/research-agent-workspace`; branch `GUI` at `5a0fa7c1241fe6932973338b353ec3c37281941b`.
- Runtime verified: Windows-hosted agent delegates commands to Ubuntu-24.04 WSL; Linux Git, Conda `app` Python 3.13.14, Poetry 2.4.1, and Node 24.18.0. Repository instructions expressly permit this setup.
- Working-tree state reviewed: clean at entry, no staged or untracked work. Compared the five source refactors since knowledge commit `5b6a194` (prior audit baseline `a88d44d`); branch was five commits ahead of its local upstream reference. All nine knowledge files were read and considered. Initial index SHA-256: `d4ef06711b85d275b28e4e15d03c5609356efbfa90ecab4b8108cb6403ce2d03`.
- Areas inspected: applicable instructions, manifests/runtime, all eight changed source/test files, and direct callers/consumers for Skill loading, fusion aggregation, deferred JSON writes, OpenAlex records and Desktop safe text rendering. The deferred Thinking Effort card was also read. No application modules were imported.
- Findings: the five refactors preserve the inspected contracts and ownership boundaries. The updated test definitions explicitly cover immediate/deferred JSON rollback, first-seen OpenAlex ordering and inline Markdown formatting. Historical passing counts do not validate these later revisions.
- Evidence gaps: no application tests, builds, native UI, live providers, MCP/Ollama, user stores, or generated artifacts were run/inspected. Older native/fixture results and RAG probes were carried forward, not rerun. No new failure or backlog item was justified by this scope.
- Git policy: all nine files tracked; no ignore-rule matches (0/9), no effective ignore (0/9). Ignore files stay unchanged. Maintenance preserves index bytes until the user's separately authorized commit/push step.
- Historical evidence: [final-check log](https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/bc2c94d40562e9606a9872bc922a36423b6a10a2/issue/final_check/build-log.md) and [check results](https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/bc2c94d40562e9606a9872bc922a36423b6a10a2/issue/final_check/evidence/phase-06-check-results.json) were inspected during the prior pass. Their recorded scope/results remain in [testing strategy](testing-strategy.md); they were not reread this pass and removed plans are not active work.

## Audit coverage

| Document | Mode | This pass scope / anchors | Last substantive validation / source baseline | Gaps |
|---|---|---|---|---|
| architecture-map.md | Focused check | Conda/Poetry/desktop manifests; five changed units and their direct consumers retain existing boundaries | Named anchors: 2026-09-14 at `5a0fa7c`; other claims retain prior dates below | No launch or full dependency audit |
| invariants.md | Focused check | INV-008 JSON conflict/rollback, INV-013 activation precheck, INV-017 rendering, INV-005 fusion malformed-output versus provider-exception boundary | Named anchors: 2026-09-14 at `5a0fa7c`; other claims retain prior dates | No fresh tests; precheck races and raised-stage exceptions remain |
| module-responsibilities.md | Focused check | `load_skill_runtime`/session caller; fusion orchestrator/review; JSONStore/DocumentStore/ingest; OpenAlex/resolver/service; SafeContent/App | Named owners: 2026-09-14 at `5a0fa7c`; others retain prior dates | No ownership or public-interface change found in scoped diff |
| data-flow.md | Revalidated | Skill resource validation, fusion fallback, immediate/deferred raw-JSON save, OpenAlex ordering and Desktop inline rendering | Named source/definition scopes: 2026-09-14 at `5a0fa7c` | Other flows retain prior dates; no effects executed |
| dangerous-assumptions.md | Focused check | ASM-003 multi-store limit, ASM-013 provider exceptions, ASM-025 native rendering limit, retired ASM-007 activation premise | Named anchors: 2026-09-14 at `5a0fa7c`; other premises retain prior dates | No new premise or runtime reproduction |
| known-failure-modes.md | Focused check | FAIL-003 cross-store limit, FAIL-005 activation mitigation, FAIL-019 array-child mitigation remain applicable | Named source anchors: 2026-09-14 at `5a0fa7c`; incidents retain original dates | No failure reproduced or newly resolved |
| testing-strategy.md | Revalidated | Three changed test files; unchanged Skill/fusion regressions; command effects and historical-result scope | Definitions: 2026-09-14 at `5a0fa7c`; execution records retain dates below | Only knowledge helper and Git checks executed |
| future-work-backlog.md | Focused check | BACKLOG-006 still concerns cross-store failure injection; Issue09 remains explicitly deferred; all candidates considered against scoped changes | Named scope: 2026-09-14 at `5a0fa7c`; other candidates retain prior dates | No candidate added or implemented |
| Other Skill/Citation/installer, extension, Desktop menu/permission/replay claims across subjects | Carried forward | Prior account retained; no changed dependency found outside the named scopes | 2026-09-13 source/contracts/tests at `a88d44d`; archived records at `bc2c94d` | Not substantively revalidated this pass |
| Other RAG and Agent/MCP/thinking claims across subjects | Carried forward | Prior account retained outside JSON save and fusion fallback | Broad evidence 2026-09-05 at `9745fd1`; prune/search focused anchors 2026-09-13 at `a88d44d` | Stale-inventory/empty-file probes not rerun |
| Other canonical-history, final-only, large-content and CSS claims | Carried forward | Prior account retained outside SafeContent parser/array-child checks | 2026-09-06 at `743aaaf` (older history evidence 2026-09-05) | Native geometry/zoom, resources and multi-process persistence not revalidated |

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
