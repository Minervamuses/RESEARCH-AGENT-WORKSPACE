# Agent Repository Knowledge

> Managed by `$infrastructure`. Verify current behavior against live evidence and requirements against applicable instructions/contracts. This folder grants no authority to change either.

## Current audit

- **Latest maintenance:** 2026-10-23T20:01+08:00, the second focused update after the 2026-10-23 cleanup commits. The first ended at 19:46 and the main pass at 18:32 (+08:00). This timestamps the passes; it does not revalidate every retained claim.
- **Repository baseline:** `/home/minervamuses/research-agent-workspace`, branch `GUI` at `3f9176a75b1759c88898d1db6fbda5d7907d0e8b`. The local `origin/GUI...HEAD` count was `0 0` (no fetch). The previous knowledge baseline was `5a0fa7c` (2026-09-14); 268 commits and 232 changed files lie between the two. The focused updates used `d74065f` and then `711bf03`. The commits involved are:
  - `4366e20`: notes.
  - `c12470f`: ignore `app/store/`.
  - `73c8db1`: Plan-log retirement.
  - `0fabe25`: retirement-guard tests.
  - `d74065f`: stale notes.
  - `fde53e3`: this knowledge refresh.
  - `33bc33f`: doc links and retired wording.
  - `711bf03`: test cache isolation.
- **Provenance:** this pass continues an interrupted OpenCode maintenance session, `ses_e9b3ceaa2ffebUxLDUG3wpfu9L`. That session stopped on a provider quota error before writing any knowledge, and its record is the untracked `infrastructure-mention-handoff.zip`, used here only as a lead. HEAD and index bytes matched that record when this pass began, and current files were re-read instead of trusting its tool outputs.
- **Runtime used:** Claude Code inside WSL Ubuntu-24.04. Every Bash command ran in a bubblewrap sandbox: writes were limited to the working tree and scratch space, and `/tmp` was read-only. Conda `app` at `/home/minervamuses/miniconda3/envs/app` reported Python 3.13.14, Node v24.18.0 and cargo/rustc 1.97.1; Poetry is present (version not queried).
- **Working-tree state reviewed:** no tracked modifications and nothing staged. Untracked items:
  - three files under `app/store/projects/p-c673e2df…/`: user conversation data, not ignored at that time (fixed in `c12470f`; FAIL-021);
  - six files under `note/20261022/session-510d4b09-acceptance-analysis/`: user analysis material;
  - `infrastructure-mention-handoff.zip`.

  Sandbox `/dev/null` mount points (`.bashrc`, `.mcp.json`, `.claude/*`, `.idea` and similar) appear as untracked only inside the sandbox and are not user files. Initial index SHA-256: `f5e487da89f3c745b0b95254332ddb330b21b0770c6aca255b93f370c36ccada`.

  At each focused update only these nine knowledge files were modified. `app/store/` was ignored, `note/20261022/` was committed and the handoff zip had been deleted. Index SHA-256 at the latest update (HEAD `711bf03`): `ac37c2d1cc0158d4486ce20df95b875c35913202d351b98eb6857a4f00d62ac2`.
- **Areas inspected:**
  - AGENTS.md; root, app and subsystem READMEs, including a relative-link check; manifests and ignore rules; `main.py`.
  - Desktop Python backend and conversation store, protocol contract, Rust host and React client.
  - Agent session, graph, tools, Skills, thinking, LLM adapter, diagnostics and observability; RAG changes; Citation; the MCP client; the vendored Web Search server.
  - Test definitions; the completed 2026-10-22 web-search plan, and removed plan logs recoverable from Git.

  Static reading was split across four read-only delegated audits: desktop backend; desktop host, client and launcher; agent core and RAG; Citation, MCP and Web Search. Their findings were spot-checked at named anchors before being recorded. No application module was imported, and no application test, build, native UI, provider or network call ran.
- **Known coverage gaps:**
  - Extension discovery, registry, startup and ZIP-installer internals received a focused check only.
  - RAG tagger, retriever and filters are unchanged and carried forward.
  - `protocol.rs` and `protocol.ts` were read for structure; `App.tsx` and `trust.tsx` were partly skimmed.
  - Native behavior, live providers, cross-process use and current test results are Unknown.
  - User data under `app/store` was not inspected.
- **Git policy:** all nine knowledge files are tracked. Ignore-rule matches: none (0/9). Effective ignore: none (0/9). This pass changed only `for_agents/**`; `.gitignore` and the index bytes were left unchanged (re-verified at the end of the pass).

## Audit coverage

| Document | Mode | This pass scope / anchors | Last substantive validation / source baseline | Gaps |
|---|---|---|---|---|
| architecture-map.md | Revalidated | All component rows, external adapters and topology: launcher; Rust host (7 commands, pickers, stderr log); React client; protocol v1 counts; desktop backend split; conversation store v3; agent core, diagnostics, MCP client, Web Search server, Citation providers and RAG entry points | 2026-10-23 at `3f9176a` (source, manifests, contract, READMEs) | Extension-runtime row is a focused check; nothing was launched |
| invariants.md | Revalidated | INV-001 to INV-031 checked against current contracts and enforcement. INV-015, INV-016, INV-018 and INV-019 were rewritten; INV-025 to INV-031 are new | 2026-10-23 at `3f9176a` | INV-009 and INV-024 internals are a focused check; enforcement evidence is test definitions, not runs |
| module-responsibilities.md | Revalidated | Owners and "must not own" for every listed module, including catalog, documents, service, `ingest.py`, diagnostics, observability, `mcp.py`, the vendored server, the Rust host and React | 2026-10-23 at `3f9176a` | Extension discovery, registry and startup carried forward (2026-09-13 at `a88d44d`) |
| data-flow.md | Revalidated | 13 flows: agent turn, project open, documents, frozen submissions, Stop, rename/delete, permissions, Skills, Citation, Web Search, RAG, desktop launch, diagnostics | 2026-10-23 at `3f9176a` | No flow was executed |
| data-flow.md (extension apply and ZIP install) | Focused check | Bypass, inline-Skill and desktop-gating changes; the `manager.py` diff | Focused anchors 2026-10-23; other steps 2026-09-13 at `a88d44d` | Internal steps not re-read |
| dangerous-assumptions.md | Revalidated | ASM-001, ASM-003, ASM-006, ASM-010 to ASM-016, ASM-018, ASM-019, ASM-022 and ASM-024 to ASM-035 against current code. ASM-026 to ASM-035 are new | 2026-10-23 at `3f9176a` | Nothing reproduced |
| dangerous-assumptions.md (unchanged RAG premises) | Focused check | ASM-002, ASM-004, ASM-005, ASM-020 and ASM-021 confirmed at their anchors | Code unchanged since `5a0fa7c`; wording from 2026-09-05 at `9745fd1` and 2026-09-13 at `a88d44d` | No new RAG evidence |
| known-failure-modes.md | Revalidated | FAIL-009 and FAIL-013 to FAIL-030 against source, tests and plan records. FAIL-014 and FAIL-017 were corrected; FAIL-021 to FAIL-030 are new | 2026-10-23 at `3f9176a` | No reproduction this pass |
| known-failure-modes.md (RAG and older mitigated items) | Focused check | FAIL-001 to FAIL-003 code unchanged; anchors for FAIL-004 to FAIL-008 and FAIL-010 to FAIL-012 still present | Original probes 2026-09-05 at `9745fd1`; mitigations 2026-09-13 at `a88d44d` | Probes not rerun |
| testing-strategy.md | Revalidated | Commands from AGENTS.md, the root README, the two `package.json` files and plan records; per-area test definitions; historical execution records with provenance | Definitions 2026-10-23 at `3f9176a`; each execution record keeps its own date | Only helper and Git checks executed |
| future-work-backlog.md | Revalidated | Every candidate reconsidered. BACKLOG-009, BACKLOG-010 and BACKLOG-013 removed; BACKLOG-011 broadened; BACKLOG-017 blocked; BACKLOG-019 to BACKLOG-025 added | 2026-10-23 at `3f9176a` | No candidate implemented in that pass |
| Cleanup follow-up across invariants, failures, backlog, testing, responsibilities and architecture | Focused check | Checked against the diffs of `c12470f`–`711bf03`: INV-019 and INV-029; FAIL-014, FAIL-021 and FAIL-023 (now mitigated); BACKLOG-019, BACKLOG-020 and BACKLOG-021 (resolved); the Plan-log, `app/store/` and `ingest.py` notes; the 2026-10-23 execution records | 2026-10-23 at `711bf03` | All other claims keep their `3f9176a` validation |

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
| Change persistence, conversation schema or replay | [Invariants](invariants.md), [data flow](data-flow.md), [testing](testing-strategy.md) |
| Change the desktop protocol, a Tauri command or IPC | [Architecture](architecture-map.md), [responsibilities](module-responsibilities.md), [data flow](data-flow.md) |
| Change documents, comments, Stop or permissions | [Invariants](invariants.md), [data flow](data-flow.md), [failures](known-failure-modes.md) |
| Change Skills, Citation, MCP or Web Search | [Responsibilities](module-responsibilities.md), [data flow](data-flow.md), [assumptions](dangerous-assumptions.md) |
| Diagnose a failure or choose optional work | [Failures](known-failure-modes.md), [assumptions](dangerous-assumptions.md), [backlog](future-work-backlog.md) |

## Evidence labels

- **Confirmed**: directly supported within the identified source, type and scope. Source or test-definition inspection is not execution.
- **Inferred**: a supported interpretation, not an established guarantee.
- **Unknown**: material evidence is missing, inaccessible, contradictory or uninspected.
- Confidence, normative authority and freshness are separate. Use the coverage rows and claim-level limits; a Confirmed label does not mean the claim was revalidated in this pass.

## Usage

- Nothing loads these files automatically. Read this index and the relevant subject files explicitly before broad changes.
- Check current code for behavior, and AGENTS.md plus the explicit contracts (root README, `contract.json`, `SKILL.md` files) for obligations.
- Backlog entries are candidates only. Plan records and removed issue cards grant no authority.
- `app/store/` holds user conversations. `/app/store/` ignores it now (FAIL-021, mitigated), but still stage commits explicitly.
- Invoke `$infrastructure` again after structural or contract changes.
