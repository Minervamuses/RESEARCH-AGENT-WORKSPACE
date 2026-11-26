# Verification

<!-- for_agents: verified=32cf47f date=2026-11-26 -->

> How to prove a change safe, what each check costs, and what it does not cover.

## Commands

Run all commands on Linux/WSL inside the Conda `app` environment (`conda activate app` or `conda run -n app ...`).

| Command | Covers | Runtime | Side effects / caveats | Last run |
|---|---|---|---|---|
| `cd app && poetry run pytest -q -p no:cacheprovider` | Full Python suite: Agent, Desktop service/protocol, Citation, Skills, Extensions, MCP, and RAG (99 test modules) | ~63 s (`measured 2026-11-26`) | Spawns local Node, Pandoc, and `bime_word` subprocesses; writes temp dirs (`AGENT_LOG_DIR` and `XDG_CACHE_HOME` isolated in `app/tests/conftest.py`); needs writable `/tmp` | 2026-11-26 at `32cf47f`: `1826 passed, 2 warnings in 62.76s` |
| `cd app && poetry run pytest tests/<module>.py -q` | Focused subsystem regression (e.g. `tests/test_state.py`, `tests/rag/test_config.py`) | 0.2–8 s | Same as above; `test_inline_skills.py` spawns `node`, Pandoc/BIME tests invoke Conda `pandoc` | 2026-11-26 at `32cf47f` (covered by full run) |
| `cd app/desktop && npm test` | 15 Node test files (`node --test --experimental-strip-types`): TS/contract DTO parity (`protocol_types.test.ts`), `api.ts`, reducers, `approvalOwner`, Vite SSR component renders, CSS checks | ~7 s (`measured 2026-11-26`) | Starts in-process Vite SSR loader; does not exercise native WebKitGTK or Monaco workers | 2026-11-26 at `32cf47f`: `253 pass, 0 fail` in 6.90 s |
| `cd app/desktop && npm run build` | `tsc --noEmit && tsc --noEmit -p tsconfig.test.json && vite build` (app + test typecheck + bundle) | ~5 s (`measured 2026-11-26`) | Overwrites git-ignored `app/desktop/dist/` (`index` 393 kB + lazy `editor.api` 2.70 MB) | 2026-11-26 at `32cf47f`: passed in 4.61 s |
| `cd app/desktop/src-tauri && cargo test --locked` | 35 Rust `#[test]` functions (`backend::tests` supervision/EOF/picker + `protocol::tests` framing/forbidden keys) | ~0.6 s warm / ~13 s compile (`measured 2026-11-26`) | Requires active Conda `app` (`CONDA_DEFAULT_ENV=app`); writes `app/desktop/src-tauri/target/`; spawns test Python children | 2026-11-26 at `32cf47f`: `35 passed` in 0.60 s (12.42 s compile) |
| `cd app/vendor/bime-word && sha256sum -c manifest.sha256` | Verifies all 39 vendored `bime_word` 1.1.5 files are byte-identical (`INV-029`) | <0.1 s (`measured 2026-11-26`) | Read-only | 2026-11-26 at `32cf47f`: `39/39 OK` |
| `PYTHONDONTWRITEBYTECODE=1 python app/vendor/bime-word/scripts/bime_word.py doctor` | Checks `python-docx`, `lxml`, `pandoc`, and font readiness for BIME Word export | ~1 s | Pass `PYTHONDONTWRITEBYTECODE=1` to avoid `__pycache__` inside vendor tree | 2026-11-07 (`R3-S2`): `convert_and_insert: true` (`not run` 2026-11-26) |
| `cd app && python scripts/grill_eval.py --cases tests/fixtures/grill/cases.example.json --out /tmp/grill-dry --dry-run` | Offline `@grill` harness smoke check (`DryRunModel`) | ~2 s | Writes reports to `--out`; **never** pass `--live` without explicit user approval (paid OpenRouter calls) | 2026-11-15 (`K6-S3`): `5/5` reports (`not run` 2026-11-26) |
| `cd app/vendor/web-search-mcp && node tests/test-search-result-retention.mjs` | Vendored Web Search MCP offline/local-HTTP checks (`tests/*.mjs`) | ~2 s | Needs built `app/vendor/web-search-mcp/dist/`; Chromium lifecycle test needs short writable `/tmp` | 2026-10-22 (`1bc3bf2`): passed (`not run` 2026-11-26) |
| `cd app && poetry build` | Builds wheel and sdist in `app/dist/` | ~3 s | Writes git-ignored `app/dist/` | `not run` |

## Change-type matrix

| Change | Minimum checks | Before merge | Manual / GUI checks |
|---|---|---|---|
| Protocol v1 method or DTO (`PLAY-001`) | `pytest tests/test_desktop_protocol_contract.py -q`, `npm test` (`protocol_types.test.ts`, `api.test.ts`) | Full `pytest`, `npm run build`, `cargo test --locked` | Exercise the action in the Tauri window if UI-visible |
| Desktop UI control, menu, or approval owner (`PLAY-002`) | `npm test` (`interaction.test.ts`, `approvalOwner.test.ts`, `conversations.test.ts`) | `npm run build`, `pytest tests/test_project_permissions.py -q` | Tab focus loop, `Escape` dismiss, IME Enter, Ask modal/non-modal behavior in WSLg |
| Desktop panel, dialog, zoom, or CSS (`PLAY-003`) | `npm test` (`styles.test.ts`, `editorZoom.test.ts`, `citation_preview.test.ts`) | `npm run build` | WSLg visual check at narrow (`<=760px`) and wide viewports, Monaco 28px CJK/English line height |
| Built-in Skill or agent tool (`PLAY-004`) | `pytest tests/test_skills.py tests/test_tool_inventory.py tests/test_tool_access_matrix.py tests/test_inline_skills.py -q` | Full `pytest` (plus `grill_eval.py --dry-run` if touching `grill`) | Live model check only with user approval |
| Project metadata, conversation schema, or context trimming (`PLAY-005`) | `pytest tests/test_conversation_repository.py tests/test_desktop_conversations.py tests/test_document_history_replay.py tests/test_document_edit_compaction.py tests/test_document_measure.py -q` | Full `pytest`, `npm test` | Open existing project, run multi-edit turn, close file and send follow-up turn |
| Bibliography, CSL preview, Pandoc, or `bime_word` export | `pytest tests/test_citation_library.py tests/test_citation_project_library.py tests/test_citation_csl_render.py tests/test_citation_appendix17.py tests/test_desktop_bibliography.py tests/test_desktop_citation_keys.py -q`, `npm test` | Full `pytest`, `sha256sum -c manifest.sha256` | Open `.bime.docx` in Microsoft Word, update all fields (TOC Roman `i, ii` vs body `1`), check pagination |
| Stop, Retry Stop, session lifecycle, or MCP | `pytest tests/test_desktop_document_service.py tests/test_bash_tool.py tests/test_mcp.py tests/test_session_persistence.py -q` | Full `pytest`, `cargo test --locked` | Stop an active turn and verify immediate follow-up turn |
| RAG ingest, sync, prune, or search | `pytest tests/rag/ -q` | Full `pytest` | Live Ollama `bge-m3` query if retrieval logic changed |
| Dependencies or vendored code (`PLAY-006`) | `poetry check`, `pytest tests/test_extension_packaging.py -q`, `sha256sum -c manifest.sha256` | All 4 suites (`pytest`, `npm test`, `npm run build`, `cargo test --locked`) | Launch `python main.py --rebuild` |

## Coverage gaps

- **Native WSLg WebKitGTK & Microsoft Word rendering (`ASM-025`, `ASM-037`).** Automated UI tests run in Node + Vite SSR without a browser DOM layout engine or real Monaco worker. 56 of the 58 items in `harness/plans/2026-11-19-repo-debt-cleanup/evidence/C10-S3/final-report.md` §10 (dialogs/menus Tab loops, restart resume, conflict chooser, 28px editor zoom) and Word TOC field updates are manual-only (`acceptance-2026-11-22/gui-citation-grill.md` covered 1 `@grill` read-only turn and 1 `@citation` search turn).
- **Live `@grill` argument-checking quality (`ASM-036`).** `test_grill_skill.py` and `test_grill_eval.py` test tool masking and report schema with `DryRunModel`; live reconstruction fidelity, false-positive rate on sound passages, and multi-turn sycophancy await user-authorized `grill_eval.py --live` runs on real passages outside the repo.
- **RAG multi-store failure & sync exclusions (`INV-012`, `FAIL-001`, `FAIL-002`, `FAIL-003`, `FAIL-035`).** No automated test pins `prune_orphans` stale `folder_meta.json`, emptied-file re-ingest chunk retention, Stop/error divergence between Chroma and `raw.json`, or `/init` -> `/sync` `app/` exclusion drift.
- **Exception-path log redaction & thinking telemetry (`INV-028`, `FAIL-036`).** No test drives `ToolInvocationError` kwargs or large OpenRouter error payloads through `desktop-backend.log` to prove zero leakage, and extended-thinking rewrite/aggregator/reviewer/repair calls are not wrapped by `TurnTimingTrace`.
- **Boundary & limit edges (`FAIL-025`, `ASM-013`, `ASM-024`, `ASM-030`).** Ask silent denials `> 8 KiB`, non-`web_search` MCP hung startup, `4,096`-turn / `10,000`-entry limits, `> 2 MiB` document conflict lines, and `.gitignore` / relative-link hygiene (`INV-029`) have no automated regression tests.

## Environment notes

- **Conda + Poetry (`INV-001`).** Always run inside Conda env `app` (`/home/minervamuses/miniconda3/envs/app`); `app/poetry.toml` sets `virtualenvs.create = false`. Never run `pip install`, `python -m venv`, or system `python3` for `app/` packages.
- **No linter, formatter, or CI.** None is configured (`AGENTS.md`); `npm run build` runs `tsc` on both `tsconfig.json` and `tsconfig.test.json`.
- **Sandbox `/tmp` requirement.** `app/tests/support/fixture_session.py` (`test_desktop_fixture.py`, `test_desktop_server.py`) and `web-search-mcp` Chromium tests require a writable `/tmp` (`phase02` fixture directories check UID ownership under `/tmp`). Read-only `/tmp` sandboxes fail those tests.
- **User data & paid APIs.** Never point tests at `app/store/`, `cite/`, or real research folders, and never invoke OpenRouter (`grill_eval.py --live`) without explicit user consent.
