# Testing Strategy

Freshness: command definitions and test definitions were revalidated on 2026-10-23 at `3f9176a`, with focused updates through `711bf03` after the cleanup commits `c12470f`–`711bf03`. Those cleanup changes were verified on 2026-10-23 with full pytest, `npm test` and `cargo test --locked` (results below). The knowledge maintenance itself ran no application suite, build, native journey, provider call or network request. Each execution record keeps its own date, baseline and provenance. See [audit coverage](README.md#audit-coverage).

## Available verification commands

Use Linux and the Conda environment `app` (`conda activate app`, or `conda run -n app …`). Listing a command does not mean it ran.

| Command | Scope / environment | Definition source | Preconditions / known side effects | Execution and result / not-run reason | Evidence limits |
|---|---|---|---|---|---|
| `cd app && poetry run pytest` | Complete Agent and RAG suite (78 top-level and 7 RAG test modules) | AGENTS.md; root README; `pyproject.toml#tool.pytest.ini_options` | Writes the pytest cache (avoid with `-p no:cacheprovider`), `__pycache__`, temporary stores and archives; spawns real child processes. The fixture and crash tests need a writable `/tmp`. Since `711bf03`, `conftest.py` isolates both `AGENT_LOG_DIR` and `XDG_CACHE_HOME` (FAIL-023) | Executed 2026-10-23 at `711bf03` outside the sandbox with no `XDG_CACHE_HOME` redirect: 1517 passed, and the real `~/.cache/agent-mcp` was unchanged. Inside the sandbox the fixture tests error on the read-only `/tmp` | Offline and fake-provider only |
| `cd app && poetry run pytest tests/test_state.py -q` | One Agent module | AGENTS.md | Cache writes | Not run separately; covered by the 2026-10-23 full run | One module |
| `cd app && poetry run pytest tests/rag/test_config.py -q` | One RAG module | AGENTS.md | Cache writes | Not run separately; covered by the 2026-10-23 full run | No live semantic evidence |
| `cd app && poetry run pytest tests/test_mcp.py tests/test_mcp_stderr_log.py tests/test_extension_mcp.py -q -p no:cacheprovider` | MCP lifecycle with real processes; several budgets are 0.8 s | 2026-10-22 plan build log, F7-S4 | Real child processes. Needs a writable `/tmp` (run outside the sandbox); `conftest.py` isolates the log and cache directories | Not run separately; covered by the 2026-10-23 full run | Timing-sensitive on a loaded host |
| `cd app && poetry run pytest tests/test_citation_skill_activation.py tests/test_tool_access_matrix.py -q` | Citation boundary text and tool binding | Same build log | Temporary state | Not run separately; covered by the 2026-10-23 full run | Checks text presence, not model compliance |
| `poetry run pytest tests/<module> -q` with the focused module sets in the change matrix | Area-focused checks | AGENTS.md focused pattern; the named test files | Temporary files and processes. `test_inline_skills.py` runs Node on `conversations.ts` and is skipped when `node` is absent | Executed for the 2026-10-23 cleanup's affected modules (see historical records) | Those modules only |
| `cd app/desktop && npm test` | `node --test --experimental-strip-types tests/*.test.ts` (8 files) | `app/desktop/package.json#scripts.test` | Conda Node 24. Conversation tests start a Vite SSR server and import React source | Executed 2026-10-23 on `0fabe25`: 260 passed inside the sandbox | Not the native WebKit engine |
| `cd app/desktop && npm run build` | `tsc --noEmit && vite build` | `package.json#scripts.build` | Writes `app/desktop/dist` | Executed 2026-10-23 at `33bc33f`: passed, with the existing Monaco large-chunk warning | Typecheck and bundle only |
| `cd app/desktop/src-tauri && cargo test --locked` | 40 Rust tests (28 in `backend.rs`, 12 in `protocol.rs`) | Root README | Needs an activated env named exactly `app` (`CONDA_PREFIX`, `CONDA_DEFAULT_ENV`). Compiles into `target/`; supervisor tests spawn children and some use `/tmp` | Executed 2026-10-23 on `0fabe25`: 40 passed outside the sandbox. Inside it, `child_crash_fails_pending_and_restart_is_user_driven` fails | One run; child-process tests depend on host process behavior |
| `cd app/vendor/web-search-mcp && npm ci && npx playwright install chromium && npm run build` | Build the Web Search server | Root README; vendored `package.json#scripts.build` | Network downloads; writes `node_modules`, `~/.cache/ms-playwright` and `dist/` | Not run: installs and network | — |
| `cd app/vendor/web-search-mcp && node tests/test-search-result-retention.mjs` (also `test-content-contract.mjs`, `test-browser-lifecycle.mjs`, `test-server-entry.mjs`) | Offline stubs; a local HTTP server; a stub browser with real child processes; spawned `dist/index.js` with stub engines | Plan build log; test files. There is no `npm test` script | Needs a built `dist/`. Real-Chromium checks need a short `TMPDIR` and `PLAYWRIGHT_BROWSERS_PATH` | Not run | No real Google |
| `python main.py` (`--rebuild`, `--dev`) | Build when stale and launch the release GUI | Root README; `main.py` | Writes `src-tauri/target/release`; opens a native window | Not run: GUI launch and build writes | No native evidence this pass |
| `cd app && poetry build` | Wheel and sdist | AGENTS.md | Writes `app/dist` | Not run: no packaging change | — |
| `python3 -B /home/minervamuses/.claude/skills/infrastructure/scripts/manage_for_agents.py preflight --root /home/minervamuses/research-agent-workspace` | Knowledge write boundary and Git policy | Loaded infrastructure helper | Read-only | Executed before every knowledge write this pass: passed each time | Paths and Git policy only |
| `python3 -B /home/minervamuses/.claude/skills/infrastructure/scripts/manage_for_agents.py check --root /home/minervamuses/research-agent-workspace` | Knowledge structure, IDs and required links | Loaded helper | Read-only | Executed after the final edit: Structural validation passed (exit 0) | Proves structure, not claim accuracy |
| `git --no-optional-locks diff --no-ext-diff --no-textconv --check -- for_agents` | Whitespace in the knowledge diff | Git | Read-only | Executed after the final edit: passed (exit 0) | No application claim |

### Historical verification with retrievable provenance

Commit messages are claims by their authors; the build logs are repository records. The 2026-10-23 rows were observed directly in this session.

| Check / date | Baseline and recorded result | Provenance | Evidence limit |
|---|---|---|---|
| Full pytest and build, 2026-10-23 (latest) | `711bf03`: 1517 passed in 65 s, exit 0, with no `XDG_CACHE_HOME` redirect; the `~/.cache/agent-mcp` content and metadata fingerprint was identical before and after. `33bc33f`: `npm run build` passed | 2026-10-23 cleanup run, outside the sandbox with only `TMPDIR` redirected | Offline; the build check proves typecheck and bundle only |
| Full pytest, 2026-10-23 | `73c8db1` (after the Plan-log retirement): 1525 passed. `0fabe25`: 1517 passed in 62 s, exit 0; 8 retirement-guard test cases were removed. `d74065f` changes only docs and one comment | 2026-10-23 cleanup run, outside the sandbox with `TMPDIR`, `XDG_CACHE_HOME` and `AGENT_LOG_DIR` redirected and `-p no:cacheprovider` | Offline and fake-provider only |
| Focused pytest, 2026-10-23 | Plan-log retirement: the 6 affected modules went from 166 passed to 165 passed (one test removed). Guard cleanup: 6 affected modules, 235 passed. Thinking tests after the comment fix: 70 passed | Same cleanup run | Affected modules only |
| npm test and cargo test, 2026-10-23 | `0fabe25`: npm 260 passed inside the sandbox; `cargo test --locked` 40 passed outside it | Same cleanup run | Inside the sandbox one Rust child-crash test fails (see constraints) |
| Full pytest, 2026-10-22 | `1834a85`: 1525 passed in 60 s, exit 0. Run outside the sandbox with `XDG_CACHE_HOME`, `AGENT_LOG_DIR` and `TMPDIR` redirected and `-p no:cacheprovider` | `harness/plans/2026-10-22-web-search-acceptance-fixes/build-log.md`, F7-S4 | Before the vendor-only Bing removal and before `92763e8` |
| Focused checks after the Bing removal, 2026-10-22 | `1bc3bf2`: focused pytest 80 passed; vendor build OK; retention 29/29; content-contract, browser-lifecycle and server-entry 7/7 exit 0 | Same build log, post-delivery section | Offline and stubbed |
| Full pytest, 2026-10-22 | `92763e8`: 1526 passed | Commit message only | Not verified; superseded by the 2026-10-23 runs |
| Mutation re-check, 2026-10-22 | 42/42 must-kill mutations killed; P07b and P07d survived with stated reasons | Plan `evidence/F6-S3/summary.md` | Covers the listed mutants only |
| Real Python→Node entry, 2026-10-22 | 15 local cases through the agent's own MCP path, with real `dist` and real Chromium, all passed with no surviving process | Plan build log, F7-S2; `evidence/F7-S2/results.json` | 127.0.0.1 servers. Public Google was observed separately (4 searches, F7-S3) |
| npm test, 2026-10-19 | 260 passed in 5.6 s | `b4d56f1^:harness/plans/2026-10-18-desktop-interaction/build-log.md` (P6-S1); commit `2bc784a` message | Desktop TS sources and tests are unchanged since `2bc784a` |
| Full pytest, 2026-10-19 | 1458 passed and 3 failed. The three adapted tests then passed individually; the suite was not rerun | Same removed log, P6-S1 | Superseded by the 2026-10-22 runs |
| Rust, 2026-10-12 to 2026-10-19 | Full `cargo test`: 39 passed (3 runs) on 2026-10-12. Later only `cargo test --locked protocol::tests` (12), `cargo test protocol --lib` (14) and `picker_maps_wsl_unc` (1) | Commit `5fc0d74` message; removed desktop log | `backend.rs` changed afterwards (pickers, Stop, rename/delete, permissions). Superseded by the 2026-10-23 full run |
| Native checkpoints, 2026-10-15 to 2026-10-19 | GUI and desktop-interaction plans recorded native checkpoints: picker shown, annotation flow, cancel preserving the draft. One HMR/maximize input stall under WSLg had an unproven root cause | Removed plan logs (`b4d56f1^`, GUI plan history) | Historical accounts, not current reruns |

The 2026-09-13 records (Python 1,138, Node 165, Rust 35 passed / 1 failed followed by one focused pass) are superseded by the records above.

## Change-type verification matrix

| Change type | Minimum focused checks | Broader checks | Manual or environment-specific evidence |
|---|---|---|---|
| Session, graph, finalization, cancellation | `test_session_persistence.py`, `test_graph_skill_loader.py`, `test_turn_finalizer.py`, `test_thinking_session.py`, `test_ingest.py`, `test_bash_tool.py`, `test_observability.py` | Full pytest with isolated environment variables | Stop with real subprocesses; live providers only when authorized |
| Conversation schema, persistence, replay | `test_conversation_repository.py`, `test_session_persistence.py`, `test_desktop_crash_recovery.py`, `test_desktop_conversations.py` | Full pytest; protocol suites in all three languages when DTOs change | Check v1/v2/v3 reads and byte preservation; never use user history as a fixture |
| Project open, catalog, `RESEARCH.md` | `test_desktop_conversations.py`, `test_desktop_fixture.py`, `test_desktop_service.py` | Add direct `inspect_project`/`initialize_project` branch tests (none exist) | A disposable folder with its own `RESEARCH.md` |
| Documents, comments, frozen submissions | `test_desktop_documents.py`, `test_desktop_document_service.py`, `test_inline_skills.py`; Node `documents`, `answer_stream`, `conversations` tests | `npm run build`; shared protocol fixtures | Monaco save in the native window, IME, size limits (ASM-030) |
| Stop | Stop tests in `test_desktop_document_service.py`, `test_session_persistence.py`, `test_bash_tool.py`; `answer_stream.test.ts` | Full pytest | Failed-cleanup and still-pending branches (FAIL-022) |
| Permission and approvals | `test_project_permissions.py`, `test_policy_tool_node.py`, `test_desktop_service.py::test_desktop_bash_*`; `trust.test.ts` | Full pytest | Exercise Ask and Bypass separately; summaries over 8 KiB (FAIL-025) |
| Desktop protocol (any language) | `test_desktop_protocol_contract.py`, `test_desktop_server.py`; `protocol.test.ts`; `cargo test --locked protocol::tests` | All three suites | Add shared fixtures for every new shape (none exist yet for `workspace.select` or `submittedContext`) |
| Rust host, pickers, launcher | `cargo test --locked` (in an activated `app` env); `test_desktop_launcher.py` | `npm run build`; `python main.py --rebuild` when release behavior matters | The picker needs Windows interop; release launch in WSLg |
| MCP client | `test_mcp.py`, `test_mcp_stderr_log.py`, `test_extension_mcp.py` with an isolated `XDG_CACHE_HOME` | Full pytest | Real `dist` entry outside the sandbox |
| Web Search server | `npm run build` plus the four Node test scripts | Focused MCP pytest | Real Chromium needs a short `TMPDIR`; public Google only with explicit authorization and pacing (at least 10 s apart) |
| Citation | `tests/test_citation_*.py`, `test_citation_skill_activation.py`, `test_tool_access_matrix.py` | Full pytest | Live provider probes only when authorized; record the `SKILL.md` version for thesis runs |
| Skills, inline references, installer, extensions | `test_inline_skills.py`, `test_skill_runtime.py`, `test_extension_skill_startup.py`, `test_extension_manager.py`, `test_skill_adherence.py` | Full pytest | Preserve source and backup bytes; Bypass consent behavior |
| RAG | `tests/rag/*`, `test_ingest.py` | Full pytest | Ollama/OpenRouter live only when authorized; FAIL-001/002/003 lack tests |
| Diagnostics, observability, privacy | `test_diagnostics.py`, `test_observability.py`, `test_chat_cli.py` | Full pytest | Prove that tool arguments and provider bodies stay out of logs (INV-028 gap) |
| Rendering and CSS | Node `conversations` and `styles` tests | `npm run build` | Native WebKitGTK, DPI and IME behavior |
| Knowledge only | Helper preflight/check, link and ID checks, scoped diff and index comparison | — | Static evidence is enough; no application suite by default |

## Invariant and failure-mode coverage

These map existing test definitions; none was executed this pass.

| Subject | Anchors / scope | Remaining limitation |
|---|---|---|
| Runtime, text, dependency boundary (INV-001, INV-002, INV-003) | `test_runtime_env.py`; Rust Conda tests; `test_public_import_defers_vector_backends` | Launcher has no Conda check; the `rag/types.py` seam is undocumented |
| Tool admission and finalization (INV-004, INV-005, INV-010; FAIL-010, FAIL-011) | `test_policy_tool_node.py`, `test_tool_access_matrix.py`, `test_turn_finalizer.py`, `test_citation_gate.py` | Duplicate tool IDs are unvalidated; extended errors complete as text |
| Canonical persistence and conversation access (INV-006, INV-016, INV-026; FAIL-017, FAIL-018, FAIL-026) | `test_conversation_repository.py`, `test_session_persistence.py`, crash recovery, `test_desktop_conversations.py`, `test_desktop_document_service.py` | No cross-process test (ASM-016, ASM-022); no limit tests (ASM-024) |
| RAG identity and state (INV-007, INV-008, INV-012; FAIL-001, FAIL-002, FAIL-003) | `tests/rag/test_root_identity.py`, `test_json_store.py`, `test_ingest.py` | No cross-store failure injection or post-Stop store check; FAIL-001/002 unpinned |
| Extension trust and installer (INV-009, INV-013, INV-024; FAIL-005, FAIL-006) | `test_extension_skill_startup.py`, `test_extension_manager.py`, `test_project_permissions.py` | Check-to-read race; Bypass consent pinned as intended |
| Citation (INV-010, INV-014, INV-030; FAIL-007, FAIL-015, FAIL-024, FAIL-028) | `test_citation_*`, `test_inline_skills.py::test_desktop_citation_command_survives_reference_comment_composition` | Prompt-only rules have no compliance test (ASM-035); DataCite cause unknown |
| Desktop wire, topology and trust (INV-011, INV-015, INV-017, INV-018, INV-023) | Protocol suites in three languages, `test_project_permissions.py`, `trust.test.ts`, Rust supervisor tests | Rust trace validation is test-only; the picker entry points are untested; no shared fixtures for new shapes |
| Documents and Stop (INV-025, INV-027; FAIL-022, FAIL-025) | `test_desktop_documents.py`, `test_desktop_document_service.py`, `answer_stream.test.ts` | Approval limits and a second Stop are untested |
| Skills (INV-019) | `test_inline_skills.py`, `test_citation_slash_command.py`, `test_slash_commands.py` | CLI `@name` has no help or tests for accidental selection |
| MCP and Web Search (INV-020, INV-031; FAIL-009, FAIL-023, FAIL-027, FAIL-030) | `test_mcp.py`, `test_chat_cli.py`, vendored Node tests | Non-web_search MCP is unbounded; Google live stability Unknown |
| Typography and keyboard (INV-021, INV-022; FAIL-019, FAIL-020) | `styles.test.ts`, `conversations.test.ts`, `documents.test.ts`, `inline_skills.test.ts` | Fixed-px surfaces; no native IME run |
| Records and hygiene (INV-028, INV-029; FAIL-014, FAIL-021) | `test_diagnostics.py`, `test_observability.py` | No test for log privacy on exception paths; no link or ignore checks in any suite |

## Test-data, fixture, and environment constraints

- **Environment.** Conda `app` owns Python, Node and Rust; Poetry creates no virtualenv. `cargo test` needs `CONDA_DEFAULT_ENV=app` and `<CONDA_PREFIX>/bin/python`.
- **Sandbox.** In the Claude Code Bash sandbox `/tmp` is read-only. `fixture_session.py` (`/tmp/research-agent-desktop-phase02-*`) and several supervisor tests then fail, so run them outside the sandbox. Pointing `TMPDIR` at a temp directory keeps `/tmp` tidy. `conftest.py` isolates `AGENT_LOG_DIR` and, since `711bf03`, `XDG_CACHE_HOME` (FAIL-023). Observed on 2026-10-23 inside the sandbox: 19 fixture errors and 1 failure from the read-only `/tmp`, and the Rust test `child_crash_fails_pending_and_restart_is_user_driven` reporting `BACKEND_OUTPUT_CLOSED` instead of `BACKEND_CRASHED`. All of them pass outside it.
- **Web Search outside the sandbox.** Node children receive only `HOME`, `LOGNAME`, `PATH`, `SHELL`, `TERM`, `USER` plus five forwarded settings: no `TMPDIR`, no proxy. Real Chromium checks need a short writable temp path and, for direct `node` runs, `PLAYWRIGHT_BROWSERS_PATH`.
- **Fixtures.** Never use user stores (`app/store`), real project histories, secrets, extension state, citation bundles or caches as fixtures. The exact `phase02` fixture requires an owned temp root.
- **Scope of offline results.** Fake model and fetch results prove deterministic host behavior only. Real tagging and chat contact OpenRouter; embeddings need Ollama with bge-m3; Web Search contacts Google.
- **Shared fixtures.** `fixtures.json` drives the Python, TypeScript and Rust protocol tests (104 messages, 43 traces), but has no `workspace.select` or `submittedContext` case.
- **No CI and no linters.** No CI workflow, formatter, linter or coverage threshold is configured.

## Known gaps and unreliable checks

- **RAG.** FAIL-001/002/003 have no regression or failure-injection tests (BACKLOG-001, BACKLOG-002, BACKLOG-006). Init/sync exclusions and prefix-search completeness are untested (ASM-020, ASM-021).
- **Desktop.**
  - No tests cover `inspect_project`/`initialize_project` branches, the select-time unavailable conversation, item-count limits, oversized approval summaries, result lines over 2 MiB, or a second Stop after failed cleanup.
  - The native picker, Monaco save in the release build, `window.confirm` and IME were not exercised in any current record.
- **Sandbox-sensitive checks.** The fixture-based pytest modules and the Rust child-crash test fail falsely inside the Claude Code sandbox. Count only results from outside it.
- **Cross-process.** There are no multi-instance tests for conversations, catalog, `RESEARCH.md` or documents.
- **Logs.** No test proves the diagnostic-log privacy contract on exception paths (INV-028), and no test checks log rotation during a long-lived process.
- **Timing.** MCP real-process tests use sub-second budgets and are load-sensitive.
- **Model behavior.** Natural-model behavior (Citation rules, save prose) is evidenced only by a few recorded traces (ASM-014, ASM-035).
- **Structural validation.** It checks Markdown structure, paths and IDs. It cannot establish claim accuracy, runtime correctness, or that future agents will read this folder.
