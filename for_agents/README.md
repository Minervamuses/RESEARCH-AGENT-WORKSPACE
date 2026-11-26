# Agent Atlas

<!-- for_agents: verified=32cf47f date=2026-11-26 -->

> Repository knowledge for coding agents, maintained with the `infrastructure` skill. Verify a claim against code before relying on it; repository instructions outrank this folder.

## System in brief

Single-user Linux/WSL academic-writing workspace (`AGENTS.md`, `CLAUDE.md`) packaged in `app/pyproject.toml` (`agent`, `rag`, `skills`) inside Conda env `app` (`app/env/env-app.yml`).
`main.py` launches a Tauri v2 WebKitGTK app (`app/desktop/src/App.tsx`) whose Rust supervisor (`app/desktop/src-tauri/src/backend.rs`) runs one Python NDJSON server (`app/agent/desktop/server.py`, `app/agent/desktop/service.py`) over protocol v1 (`app/desktop/protocol/v1/contract.json`: 25 methods, 8 request events, 4 process events, 25 error codes).
A CLI (`app/agent/cli/chat.py`) shares `ChatSession` (`app/agent/session.py`), LangGraph (`app/agent/graph.py`), Skills (`app/skills/`), MCP (`app/agent/mcp.py`), and RAG (`app/rag/`).
Three rules newcomers miss:
1. **One active workflow (`INV-035`):** One opened project, conversation, and turn at a time; never add cross-project locks, global stores, or multi-instance coordinators.
2. **Single-store bibliography & scan-derived list (`INV-010`, `INV-016`):** Citations save only to `<project>/references.json` (no `cite/` bundles), and conversation lists come from scanning schema-v3 `<historyDirectory>/conversations/*.json` (no catalog file).
3. **Single-source protocol (`INV-011`):** Python (`app/agent/desktop/protocol.py`) validates result schemas; Rust checks framing and `app/desktop/tests/protocol_types.test.ts` checks TS DTO parity.

## Task router

| I want to... | Read | Open first in code |
|---|---|---|
| Add/change a desktop RPC method or wire field | `PLAY-001` ([playbooks](change-playbooks.md#playbooks)), [contracts](flows.md#contracts-across-boundaries), `INV-011` | `app/desktop/protocol/v1/contract.json` |
| Add a UI button, menu, shortcut, or Ask action | `PLAY-002` ([playbooks](change-playbooks.md#playbooks)), [controls](ui-architecture.md#controls-and-actions), `INV-018` | `app/desktop/src/App.tsx` |
| Change panels, dialogs, Monaco zoom, or CSS | `PLAY-003` ([playbooks](change-playbooks.md#playbooks)), [UI surfaces](ui-architecture.md#surfaces), `INV-021` | `app/desktop/src/styles.css` |
| Add/edit a Skill (`@grill`, `/citation`) or tool | `PLAY-004` ([playbooks](change-playbooks.md#playbooks)), [boundaries](system-map.md#ownership-and-boundaries), `INV-033` | `app/agent/session.py` |
| Change `RESEARCH.md`, v3 JSON, or context trimming | `PLAY-005` ([playbooks](change-playbooks.md#playbooks)), [flows](flows.md#flows), `INV-034` | `app/agent/document_context.py` |
| Touch bibliography, Pandoc preview, or `bime_word` | [flows](flows.md#flows), `INV-032`, `ASM-037` ([assumptions](failure-analysis.md#fragile-assumptions)) | `app/agent/desktop/bibliography_ops.py` |
| Debug Stop / Retry Stop, crashes, or open errors | [failure surface](failure-analysis.md#failure-surface), [defects](failure-analysis.md#active-defects), `INV-027` | `app/agent/desktop/turn_ops.py` |
| Work on RAG ingest, `/sync`, `/prune`, or search | [flows](flows.md#flows), `INV-003`, `FAIL-001` ([defects](failure-analysis.md#active-defects)) | `app/rag/api.py` |
| Investigate slowness, tokens, or scan cost | [cost model](performance.md#cost-model), `PERF-001` ([bottlenecks](performance.md#suspected-bottlenecks)) | `app/agent/observability.py` |
| Change dependencies or vendored tools | `PLAY-006` ([playbooks](change-playbooks.md#playbooks)), [verification](verification.md#commands), `INV-029` | `app/pyproject.toml` |

## Freshness

| File | Verified at | Notes |
|---|---|---|
| `README.md` | `32cf47f` (2026-11-26) | Uncommitted `app/skills/grill/SKILL.md` edits excluded |
| `system-map.md` | `32cf47f` (2026-11-26) | Migrated and updated for C1-C10 cleanup |
| `flows.md` | `32cf47f` (2026-11-26) | Re-verified turn, document, citation, Stop, and scan flows |
| `change-playbooks.md` | `32cf47f` (2026-11-26) | Built fresh (`PLAY-001`..`PLAY-006`) |
| `invariants.md` | `32cf47f` (2026-11-26) | `INV-001`..`INV-035` |
| `failure-analysis.md` | `32cf47f` (2026-11-26) | Open `FAIL-`, `ASM-`, and `Lessons` |
| `verification.md` | `32cf47f` (2026-11-26) | All 4 suites (`pytest` 1826, `npm test` 253, `npm run build`, `cargo` 35) run |
| `performance.md` | `32cf47f` (2026-11-26) | Built fresh with 2026-11-26 `scan_cost.py` run |
| `ui-architecture.md` | `32cf47f` (2026-11-26) | Built fresh across `App.tsx`, components, `lib/*`, and CSS |

## Conventions

- Anchors are repo-relative: `path`, `path::Symbol`, or `path#config.key`. The `check` command fails when a tracked anchor no longer resolves.
- `(unverified: reason)` marks a claim not checked against code. `(measured YYYY-MM-DD)` marks a run result. `(inferred)` marks a reasoned but unconfirmed claim.
- IDs: `INV-` invariants, `FAIL-` open defects, `ASM-` fragile assumptions, `PLAY-` playbooks, `PERF-` suspected bottlenecks. IDs are stable; retired IDs are not reused.
- `briefs/` holds analyses for specific changes. Delete a brief once its change has landed and its corrections are folded into the atlas.
