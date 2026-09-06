# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Read first

`AGENTS.md` (repo root) is the authoritative contributor contract — scope, style, testing, and commit rules. Read it before changing anything.

`for_agents/` holds agent-maintained repository knowledge (architecture map, invariants, module responsibilities, data flow, dangerous assumptions, known failure modes, testing strategy, backlog). It is gitignored-by-rule but tracked, and it is **not** auto-loaded — read `for_agents/README.md` explicitly before broad or cross-subsystem changes. It is managed by the external `$infrastructure` skill; treat it as evidence with confidence labels, not as authority to change behavior.

Precedence when documents disagree: live code and tests > `AGENTS.md` / `app/SKILLS_GUIDE.md` > `for_agents/` > root `README.md` > `issue/`, `note/`, `harness/` records.

## Project scope

Student-owned, local-use research application. Prioritize correct research workflows, reproducibility, short feedback loops, and debuggability. Do **not** add enterprise hardening, HA/multi-tenancy, compatibility layers, or speculative abstractions unless explicitly requested or a demonstrated problem requires them. Records in `issue/`, `note/`, and `harness/` are context, not implementation scope.

Linux/WSL is the only supported runtime. The tree may be edited from Windows through WSL tooling, but all commands and runtime behavior target Linux. Preserve LF line endings (`.gitattributes`).

## Environment

One Conda environment named `app` owns Python 3.13, Node, and Rust. Poetry installs into that active environment — `app/poetry.toml` sets `virtualenvs.create = false`, so there is no `.venv`. Never use system Python, bare `pip install`, or `python -m venv`. The chat CLI and the Tauri supervisor both validate that the interpreter matches `CONDA_PREFIX` and refuse to start otherwise.

```bash
conda env create -f app/env/env-app.yml   # first time
conda activate app && cd app && poetry install
ollama pull bge-m3                        # required for ingest / semantic search
```

Non-interactive: prefix commands with `conda run -n app ...`.

Dependency changes require explicit user approval. When approved, edit `app/pyproject.toml` + `app/poetry.lock` via Poetry inside the `app` env; touch `app/env/env-app.yml` only for Conda-managed runtime requirements.

Configuration comes from real environment variables only — the code never reads `.env`. Persist settings with `conda env config vars set -n app KEY=value` (re-`activate` to pick them up). See root `README.md` §3 for the full variable table (`OPENROUTER_API_KEY`, `KMS_STORE_DIR`, `CITATION_OUTPUT_DIR`, `AGENT_ENABLE_MCP_*`, …).

## Commands

From `app/`:

```bash
poetry run pytest                              # full Python suite (agent + rag)
poetry run pytest tests/test_state.py -q       # one focused agent module
poetry run pytest tests/rag/test_config.py -q  # one focused rag module
poetry run pytest tests/test_desktop_service.py::test_name -q   # single test
poetry build                                   # wheel + sdist into app/dist/
poetry check --lock                            # manifest/lock consistency
python -c "import agent, skills.citation, rag; print('app ok')"  # import smoke
python -m agent.cli.chat --no-mcp              # chat CLI without MCP servers
python -m rag.cli.ingest README.md             # ingest one file
```

From `app/desktop/`:

```bash
npm install
npm run tauri dev      # dev GUI (root `python main.py` just wraps this)
npm test               # TypeScript protocol/reducer/renderer/CSS tests
npm run build          # tsc --noEmit + vite build
cargo test --manifest-path src-tauri/Cargo.toml
npm run tauri -- build --no-bundle   # supported Linux source build; bundle.active=false
```

No formatter, linter, coverage threshold, or CI is configured. Match nearby style.

## Architecture

### One distribution, three namespaces

`app/` is the single Poetry project. Its one wheel packages `agent`, `rag`, and `skills`.

- `app/agent/` — LangGraph application: session facade, graph, turns, extended thinking, tools, CLI, MCP, extensions, conversations, desktop backend.
- `app/rag/` — framework-neutral ingest → chunk → store → retrieve subsystem.
- `app/skills/` — built-in skill bundles (`SKILL.md` is model-executed instruction text).
- `app/tool/` — user drop-in roots for Skills/MCPs (`skill/`, `mcp/`), plus `_internal/` and a reserved `local/`.
- `app/tests/` — one pytest suite; RAG tests under `app/tests/rag/`.

**Hard dependency rule:** `agent` may import `rag`'s public API; `rag` must never import `agent` or app-specific skill code. Keep agent/session policy out of `app/rag/`.

**Skill domain code vs. session integration** are separate boundaries: `app/skills/citation/` is the citation engine; `app/agent/skills/citation/` holds only session integration policy.

### Turn and persistence contract

`ChatSession` is a deliberately broad composition facade — it owns the turn lock and ordering, and delegates graph execution, thinking, citation policy, persistence, and journaling. Preserve that delegation; do not inline domain logic into it.

Canonical `conversations/*.json` under the store root is the **sole** active transcript authority, and `ConversationRepository` is its **sole** writer. The ordering is invariant: accepted prompt written pending → provider/tool execution → terminal state durable → success exposed to the user. On restart, leftover pending turns become `interrupted` with no automatic replay. Model context is the latest ten completed context-eligible turns.

Legacy `store/chat_history/` (conversation Chroma) and `app/plan_logs/` are unsupported and left byte-untouched — never read, import, create, update, or delete them. There is no migration path; a catalog session whose canonical JSON is missing reports *conversation unavailable* rather than reconstructing anything.

### Tool access

Tool *existence* and tool *authorization* are separate layers. `tools.access.resolve_tool_access` resolves the effective set, graph binding exposes it, and `PolicyToolNode` re-checks at execution time — so a forged call outside the set is denied at execution, not merely hidden from the prompt. Preserve both layers when adding tools.

### Skill invocation (root README is stale here)

`/skill` and manifest `task_modes` are **retired** (`_RETIRED_SKILL_COMMANDS` in `app/agent/cli/slash_commands.py`). The startup skill catalog is immutable and projects each validated non-Citation skill into a one-shot `/<skill-name> <prompt>` command, active for exactly that turn and identity-cleared afterwards. Citation is the sole persistent skill, controlled by the CLI-only `/citation` handler, and currently has no Desktop activation path. `app/SKILLS_GUIDE.md` plus live code govern; root `README.md` §6/§9 still describe the retired behavior.

MCP startup defaults **on** in both CLI and Desktop session creation; only an explicit opt-out (`--no-mcp`, `loadMcp: false`) disables it. The React client omits the field so Python's default stays authoritative.

### Desktop (source-checkout only)

Three owners, strictly separated:

- **React** (`app/desktop/src/`) — gathers intent, renders bounded state, reconciles restored/live/pending turns by `(sessionId, turnId)`. Disabled controls are not authorization.
- **Rust/Tauri** (`app/desktop/src-tauri/`) — owns the native window, exactly five allowlisted commands (`backend_start`, `backend_snapshot`, `backend_request`, `backend_shutdown`, `backend_restart`), one supervised Python child, NDJSON correlation, and lifecycle truth.
- **Python** (`app/agent/desktop/`) — owns protocol validation, project catalog, conversation restore, slash routing, adapters, and *all* domain writes.

`app/desktop/protocol/v1/{contract.json,fixtures.json}` is the language-neutral contract, hand-implemented three times (Python/TypeScript/Rust) and kept honest by shared fixtures. Change all four in one pass. All three implementations reject incompatible messages rather than adapting silently.

Normal answers are **final-only**: a single terminal `final_only` result with `chunkCount=0`, delivered after finalization and persistence. Progress and tool events never carry answer text — do not add answer previews or simulated streaming. Untrusted text renders through `SafeContent`; only credential-free absolute HTTP(S) URLs may reach the native opener; content-sized child collections must stay array-valued (never spread variadically).

There is no installer or bundled sidecar. Python locates the protocol contract through checkout-relative `find_app_root()`; wheel-installed asset lookup is unverified.

### RAG persistence surfaces

Three surfaces, not one transactional store: `raw.json` (full-content read surface), document Chroma (semantic index), `folder_meta.json` (inventory metadata). Writes are ordered, not atomic across surfaces; recovery is rerun-based. Repo-ingest document IDs are namespaced by canonical root so `/sync` and `/prune` ignore other roots and single-file ingests.

### Extensions

Drop-ins under `app/tool/skill/<id>/` and `app/tool/mcp/<id>/` are untrusted *desired* state. `/Extension-Management` scans, validates, and copies approved bundles into managed state plus a registry; raw drop-ins are never executed during apply, and changes only reach the **next** session. MCP binding approval is exact — it covers resolved command, argv, cwd, env sources, family, scope, and binding hash.

## Generated / not-source

`cite/`, `app/store/`, `app/plan_logs/`, `app/dist/`, `app/desktop/dist/`, `node_modules/`, `src-tauri/target/`, `~/.cache/agent-mcp/`, and user extension state. Never commit stores, citation bundles, secrets, or `.env`.

## Testing

pytest 9, `test_*.py` / `test_*` naming. Add the smallest regression test beside the affected subsystem, reusing `app/tests/fixtures/`. Run focused modules first, then the full `app` suite. Most tests use fake providers, monkeypatches, and temporary roots — passing offline proves nothing about live OpenRouter/Ollama/MCP/citation providers.

Tests must isolate write roots (`KMS_STORE_DIR`, temporary citation/extension roots) and must never touch real user stores, credentials, or legacy `plan_logs`/`chat_history`. `app/agent/desktop/fixture_session.py` is an acceptance seam gated on exactly `RESEARCH_AGENT_DESKTOP_FIXTURE=phase02` — it is not an alternate product core and must never become an implicit fallback.

`for_agents/testing-strategy.md` carries a change-type → minimum-checks matrix; consult it for cross-language (Python + npm + cargo) changes.

## Known open gaps

Recorded in `for_agents/known-failure-modes.md` and `dangerous-assumptions.md`. The recurring ones: no cross-store transaction across RAG's three surfaces; no interprocess lock on the desktop catalog, canonical conversations, or the extension registry (concurrent desktop processes can race); post-startup skill tampering is undetected; exact native `720×560` and 200% zoom layout is unverified. Root `README.md` and `issue/08` contain stale prose.

## Commits

Concise Conventional Commit subjects — `type(scope): summary`, imperative, e.g. `fix(desktop): scale typography on wide windows`, `test(extensions): record sandbox user journey`. One logical change per commit. PRs should state the user-visible change, the affected subsystem, any linked issue, and the exact verification commands run.
