# Testing Strategy

## Available verification commands

Run project commands under Ubuntu/WSL from the repository root unless the command changes directory. Conda environment app is mandatory.

| Command | Scope / environment | Definition source | Preconditions / known side effects | Execution and result / not-run reason | Evidence limits |
|---|---|---|---|---|---|
| `cd app && conda run -n app poetry run pytest tests/test_state.py -q` | Focused Agent state smoke; WSL/Linux Conda `app` | `AGENTS.md` | Installed project; temporary/cache writes may occur | Not run during documentation maintenance; unaffected Agent internals carried forward | One module only |
| `cd app && conda run -n app poetry run pytest tests/rag/test_config.py -q` | Focused RAG configuration; WSL/Linux Conda `app` | `AGENTS.md` | Installed project | Not run; RAG was outside the changed Desktop scope | Configuration only, no Ollama integration |
| `cd app && conda run -n app poetry run pytest` | Complete Python Agent/RAG suite | `AGENTS.md`; `app/pyproject.toml` | Broad suite; writes only isolated test artifacts when tests behave as defined | Not run because `$infrastructure` permits only read-only verification outside `for_agents/` | Offline suite does not prove live services |
| `cd app && conda run -n app poetry run pytest tests/test_desktop_crash_recovery.py tests/test_conversation_repository.py tests/test_session_lifecycle.py tests/test_desktop_conversations.py tests/test_desktop_fixture.py tests/test_history_retirement.py -q` | Canonical persistence, crash/restart, selection, and history retirement | Current test modules and canonical contracts | Owned temporary fixture roots; no real provider/store | Not run during maintenance; definitions and affected source anchors inspected | Python boundary only; native UI absent |
| `cd app && conda run -n app poetry run pytest tests/test_desktop_protocol_contract.py tests/test_desktop_service.py tests/test_slash_commands.py tests/test_desktop_answer_stream.py tests/test_conversation_archive_access.py tests/test_session_persistence.py -q` | Desktop protocol, service, final-only, Skill routing, and archive access | Current test modules and protocol contract | Fake/temp state | Not run during maintenance | No Rust/WebView or live provider |
| `cd app && conda run -n app poetry run pytest tests/test_desktop_server.py tests/test_desktop_fixture.py tests/test_bash_tool.py -q` | NDJSON server, exact fixture gate, and Bash approval seam | Current test modules | Isolated roots; no real provider/shell | Not run during maintenance | Does not prove native Tauri interaction |
| `cd app && conda run -n app poetry run pytest tests/test_slash_commands.py tests/test_skills.py tests/test_skill_adherence.py tests/test_extension_skill_startup.py -q` | One-shot non-Citation Skill lifecycle | Current test modules and Skill runtime | Temporary Skill roots | Not run; unchanged scope carried forward | Citation remains a separate lifecycle |
| `cd app && conda run -n app poetry run pytest tests/test_desktop_answer_stream.py tests/test_desktop_service.py tests/test_desktop_fixture.py -q` | Final-only Desktop answers, composer routing, and fixture behavior | Current test modules and protocol contract | Fake/temp state | Not run during maintenance | No React/native presentation |
| `cd app && conda run -n app poetry run pytest tests/test_openrouter_model.py -q` | Default main-model configuration and adapter forwarding | Current focused Python test | No live provider required | Not run during maintenance; test definition and production call site inspected at `743aaaf` | Does not prove `google/gemini-3.8-flash` exists or is reachable on OpenRouter |
| `cd app/desktop && conda run -n app npm test` | TypeScript protocol, bridge/reducer, conversation/retry, safe-content, composer-key, and CSS-contract tests | `app/desktop/package.json#scripts.test`; `tests/*.test.ts` | Conda Node and installed `node_modules`; normal test caches only | Pre-maintenance at the same `743aaaf` HEAD: 151 passed, 0 failed; not rerun during documentation maintenance | Structural/unit/server-render evidence; no native WebKit, DPI, or human visual proof |
| `cd app/desktop && conda run -n app npm run build` | TypeScript check plus Vite production build | `app/desktop/package.json#scripts.build` | Installed `node_modules`; rewrites generated `dist` | Pre-maintenance at the same `743aaaf` HEAD: exit 0; not rerun during documentation maintenance | Build success does not prove runtime/native behavior |
| `cd app/desktop && conda run -n app cargo test --manifest-path src-tauri/Cargo.toml` | Rust protocol/supervisor unit tests | Cargo manifest and Rust tests | Rust toolchain; may compile/update `target` | Not run during maintenance; historical Phase 07 result retained below | No Python provider or WebView presentation |
| `cd app/desktop && conda run -n app npm run tauri -- build --no-bundle` | Supported Linux source-checkout Tauri release build | Root README; `tauri.conf.json#build.beforeBuildCommand` | Conda toolchain and Linux Tauri libraries; writes frontend/Rust build output | Not run during maintenance; historical Phase 07 result retained below | No installer; successful build is not a visual journey |
| `cd app && conda run -n app poetry check --lock` | Manifest/lock consistency | `AGENTS.md`; Poetry metadata | Installed Poetry | Not run; dependency metadata was unchanged | Packaging metadata only |
| `cd app && conda run -n app poetry build` | Wheel and sdist | `AGENTS.md`; Poetry metadata | Writes generated `app/dist` | Not run; documentation-only scope and no packaging change | Desktop contract assets remain source-checkout-only |
| `cd app && conda run -n app python -c "import agent, skills.citation, rag; print('app ok')"` | Distribution import smoke | Root README | Installed project | Not run; no Python implementation change in maintenance | Importability only |
| `/home/minervamuses/miniconda3/bin/conda run -n app python /mnt/c/Users/garyc/.codex/skills/infrastructure/scripts/manage_for_agents.py check --root /home/minervamuses/research-agent-workspace` | `for_agents` structure, paths, links, stable IDs, headings, and ignore state | `$infrastructure` helper | WSL skill path and repository available; read-only | Run during maintenance: initial check exposed 29 errors; post-update check passed | Deterministic structure only, not semantic correctness |

Same-HEAD evidence produced before this documentation-only maintenance pass:

| Check | Result | Evidence limit |
|---|---|---|
| Desktop TypeScript suite | 151 passed, 0 failed at `743aaaf` | Covers current test definitions, including recent GUI regressions; no native WebKit |
| Desktop TypeScript/Vite build | Exit 0 at `743aaaf` | Compile/bundle only |
| Headless-Chrome responsive layout observations | Widths 720, 1080, 1920, and 2560; root font stayed 16px at 1080 and was 18.72px at 1920 | Browser proxy only; not Tauri/WebKit, DPI, 200% zoom, or human acceptance |

Historical GUI and migration plan bundles were deliberately removed. Their former test counts and native-journey observations are no longer repository evidence; rerun the smallest relevant current checks when those claims matter.
| Exact native `720×560` and 200% zoom layout | Unavailable/not passed and blocking | WSLg geometry cannot be set reliably and WebKit ignores zoom; browser/headless substitution is forbidden |
| Live providers, Ollama, and real user stores | Not run | Outside the authorized fixture-only validation scope |

The earlier focused RAG probes recorded in the prior audit reproduced FAIL-001 and FAIL-002 using temporary data and deterministic doubles. Their relevant production paths did not change, but the probes were not repeated now.

The original GUI plan is Complete. The separate corrective plan records Phases 01-06 Complete and Phase 07 Blocked after one older broad Python failure and one older Cargo failure were repaired only by focused checks under a no-rerun rule. Later canonical-conversation Phase 07 evidence above applies to the current application code, but it does not silently change the corrective plan's own status. This infrastructure audit did not run application tests or builds; the three current-HEAD frontend observations above predate the documentation pass.

## Change-type verification matrix

| Change type | Minimum focused checks | Broader checks | Manual or environment-specific evidence |
|---|---|---|---|
| Agent graph/session/turn lifecycle | Relevant test_state, test_graph_skill_loader, test_turn_finalizer, test_session_lifecycle, and test_session_persistence modules | Complete pytest once near completion when inexpensive | No live provider unless explicitly approved |
| Tool access, bash/read_file, MCP | test_tool_access, test_tool_access_matrix, test_policy_tool_node, implementation-specific module | Complete pytest | TTY approval path and MCP logs only when behavior changed |
| Extended thinking | test_thinking, test_thinking_models, test_thinking_session | Complete pytest | Live paid/provider trial only under explicit bounded authorization |
| RAG config/API/store/sync | Relevant app/tests/rag modules plus test_ingest/test_adapter_formatting | Complete pytest | Ollama/OpenRouter only for a concrete live integration need; isolate KMS_STORE_DIR |
| Citation engine/session policy | Relevant test_citation modules and test_turn_finalizer | Complete pytest | Live provider calls only when cached/fake evidence cannot answer the question |
| Skill invocation/manifest | test_slash_commands, test_skills, test_skill_adherence, and test_extension_skill_startup | Complete pytest | Verify one-shot cleanup and legacy-field diagnostics with temporary Skill roots |
| Extension apply/startup | Relevant test_extension modules | Complete pytest | Use temporary drop-in/state roots; never mutate real user extension state |
| Desktop protocol/backend/conversations | Relevant Python Desktop, canonical conversation, catalog-only missing-file, persisted-failure, pending-retry, safe-content, composer-key, and Bash modules plus `npm test` | Cargo test and selected Python regressions; Tauri no-bundle build when native/build surfaces change | Isolated real Tauri/Python journey for lifecycle/UI changes; never use real user stores |
| Desktop React/CSS visual behavior | `npm test` plus `npm run build`; inspect root/rem interaction and overflow-sensitive containers | Relevant Python/Rust checks only when protocol or host boundaries also changed | Compare initial and maximized native Tauri windows at representative DPI; keyboard/IME behavior needs native interaction, and browser screenshots are proxy evidence only |
| Packaging/runtime/dependency change | Runtime tests, import smoke, poetry check --lock | poetry build and complete pytest | Dependency changes require prior user approval |
| Documentation/for_agents only | infrastructure check, marker/search, ignore check, diff check | No application suite by default | Cross-document evidence audit |

## Invariant and failure-mode coverage

| Item | Current verification | Coverage status |
|---|---|---|
| Coverage for INV-001 | test_runtime_env.py; observed Python/Conda paths | Covered |
| Coverage for INV-002 | .gitattributes and Git attribute/diff checks | Covered policy; full corpus not rescanned |
| Coverage for INV-003 | RAG/adapter tests and import search | Covered |
| Coverage for INV-004 | test_policy_tool_node.py; test_tool_access_matrix.py | Covered except duplicate/empty tool-call IDs |
| Coverage for INV-005 and INV-006 | test_turn_finalizer.py, test_thinking_session.py, test_session_lifecycle.py, test_conversation_repository.py, test_desktop_crash_recovery.py | Strong offline coverage for prompt-first, terminal-before-success, latest-ten, interrupted/no-auto-replay, and six kill boundaries; live providers remain unverified |
| Coverage for INV-007 and INV-008 | test_root_identity.py, test_component_flow.py, test_json_store.py | Covered for successful/JSON-conflict paths |
| Coverage for INV-009 | test_extension_registry, manager, MCP, startup, user journey | Covered at apply/startup; FAIL-005/FAIL-006 uncovered |
| Coverage for INV-010 | citation storage/resolution/e2e/gate/finalizer suites | Strong offline coverage; ASM-014 remains model-behavior risk |
| Coverage for INV-011 | Shared fixtures plus Python protocol/server, TypeScript pending/retry/reconciliation tests, and Rust protocol/supervisor tests | Strong offline coverage; same-HEAD TypeScript run passed, while Python/Rust suites were not rerun this pass |
| Coverage for INV-015 | Rust lifecycle/source-launch tests, frontend bridge tests, capability/invoke inspection, isolated real-boundary journeys | Covered for supported source checkout; packaged topology intentionally uncovered |
| Coverage for INV-016 | test_desktop_conversations.py and test_desktop_fixture.py cover A→B→A, restart, canonical restore, catalog-only missing-file rejection, current-session retention, and deterministic canonical fixture data | Strong offline coverage; old Plan/Chroma sources are deliberately unsupported and untouched |
| Coverage for INV-017 | Safe-content/URL tests, three 140,000-child regressions, protocol forbidden-key tests, DTO bounds, and Tauri capability inspection | Covered at tested structural limits; no native browser-engine resource/security audit |
| Coverage for INV-018 | Prune preview, extension preview/binding, approval correlation/replay/timeout/crash tests | Strong per-process coverage; cross-process state remains uncovered |
| Coverage for INV-019 | test_slash_commands.py, test_skills.py, test_skill_adherence.py, test_desktop_service.py, and fixture journey | Strong one-shot success/error/cancel and CLI/Desktop coverage; persistent Citation remains a separate CLI-only contract |
| Coverage for INV-020 | CLI/Desktop service MCP-default tests plus TypeScript creation-parameter test | Covered offline for default-on and explicit opt-out |
| Coverage for INV-021 | `styles.test.ts`, same-HEAD `npm test`, build, and headless representative-width observations | CSS contract and browser proxy covered; native maximized/fullscreen, DPI, zoom, and human acceptance unverified |
| Coverage for INV-022 | `shouldSubmitComposerKey` pure-function test and handler source inspection | Enter/Shift+Enter/IME predicate covered; no native DOM dispatch or IME journey at current HEAD |
| Coverage for FAIL-001 and FAIL-002 | Temporary deterministic probes | Reproduced; no regression tests |
| Coverage for FAIL-003 | Code/docs and JSON rollback tests | Partial; no Chroma mid-failure injection |
| Coverage for FAIL-004 | test_history_retirement.py plus canonical lifecycle and integrated fixture no-`store/chat_history` assertions | Resolved in the supported paths exercised offline; remaining turn-count and catalog-scan limits are ASM-024 |
| Coverage for FAIL-005 | Focused tamper probe and issue reproduction | Reproduced; no regression test |
| Coverage for FAIL-006 | Control-flow proof and issue sequence | No multiprocessing regression |
| Coverage for FAIL-007 | Focused same-year probe | Reproduced; existing test covers different years only |
| Coverage for FAIL-008 | Git history, integrated desktop journeys, Python/TypeScript/Rust tests | Historical disconnected shell is mitigated |
| Coverage for FAIL-009 | MCP/fake-provider tests plus lifecycle/crash-recovery tests | Durable failure/no-auto-replay covered offline; no live dependency verification |
| Coverage for FAIL-010 through FAIL-012 | Focused regression tests, attributes, and current code | Mitigations covered |
| Coverage for FAIL-013 | Direct-handler source/tests plus supported composer routing tests | Limitation confirmed; raw direct folder methods remain intentionally disabled |
| Coverage for FAIL-014 | Retired-command and legacy-manifest tests plus root README comparison | Runtime behavior covered; user-facing root documentation remains stale |
| Coverage for FAIL-015 | Desktop disallowed-command test and App.tsx CLI-only notice | Gap confirmed; Citation lifecycle/product decision remains deferred |
| Coverage for FAIL-016 | Rust long-request, output-close, and shutdown tests | Former deadline mitigated; indefinite liveness remains ASM-019 |
| Coverage for FAIL-017 | Persisted-failure reconciliation TypeScript regression plus Python durable-first-prompt test | Frontend test ran at same HEAD; Python supporting test defined but not rerun in this pass |
| Coverage for FAIL-018 | Pending failed/interrupted retry overlay, new-pending append, and unresolved-retry regressions | Same-HEAD TypeScript suite passed; no native interaction |
| Coverage for FAIL-019 | Three 140,000-child server-render regressions | Avoids variadic-call failure at tested points; no native performance ceiling |
| Coverage for FAIL-020 | CSS-contract test, same-HEAD build, and headless width observations | Mitigation covered as source/browser proxy; native visual acceptance remains open |

## Test-data, fixture, and environment constraints

- Conda environment app owns Python, Node, npm, Rust, and Cargo. Poetry virtualenv creation is disabled.
- Most tests use fake models/providers, monkeypatches, and temporary stores/roots; they do not prove live OpenRouter/Ollama/MCP/provider availability.
- Semantic search and real ingest require Ollama with bge-m3. Folder/repo tagging requires OpenRouter.
- Citation live tests would touch network providers and potentially local citation output; use temporary output and explicit authorization.
- Default app/store, cite, extension state, MCP logs, node_modules, dist, and Rust target are generated/local. Old `plan_logs` and conversation Chroma are unsupported transcript sources; tests must leave them untouched, isolate write roots, and avoid user data.
- `app/agent/desktop`, the React/Tauri implementation, and their tests are tracked. The exact `phase02` fixture gate must use a caller-owned, validated temporary root, deterministic canonical JSON, and fake providers/runners. The gate may not touch user stores or credentials.
- Desktop Python protocol reads `app/desktop/protocol/v1` from the source tree; installed-wheel behavior is unverified and Tauri bundling is disabled.
- Shared protocol fixtures cover Python/TypeScript/Rust source contracts. Exact native `720x560`, 200% zoom, and current native WebKit behavior remain unavailable/not passed.
- No formatter, linter, coverage threshold, or CI configuration is present.

## Known gaps and unreliable checks

- No regression tests exist for stale folder metadata, empty/unreadable re-ingest, post-startup Skill tampering, extension cross-process lost update, or same-year earliest ambiguity.
- No failure-injection test spans RAG folder metadata, raw JSON, and Chroma; no concurrency test covers simultaneous ingest/prune/read.
- No test verifies persistent-store schema migration, embedding-model compatibility, moved roots, default single-file PID collisions, preservation of `/init` exclusions during `/sync`, or prefix-search completeness.
- No explicit timeout test covers MCP get_tools; raised aggregator/reviewer/reviser provider exceptions are not comprehensively tested.
- No multiprocessing test covers desktop catalog lost updates or canonical conversation writers.
- Long-content regressions use values beyond the retired answer/document/transcript thresholds only as evidence points; they do not define a new product ceiling. Real I/O or memory exhaustion behavior remains platform-dependent.
- Safe-content large-child regressions use React server rendering, not native WebKit. They distinguish the variadic-argument failure from correctness but do not prove acceptable native memory or interaction performance.
- Composer keyboard coverage tests the pure predicate; it does not dispatch real textarea events or exercise an IME in the native application.
- Responsive typography coverage checks source arithmetic and headless-Chrome layouts. It does not establish native maximized/fullscreen readability, platform DPI behavior, 200% zoom, or human visual acceptance.
- No integrated stress test enumerates every concurrent raw-protocol RAG read/write intersection. Direct `knowledge.init_workspace` and `knowledge.ingest_folder` remain deliberate failures even though the composer route works.
- Per-conversation thinking snapshots are tested in-process and intentionally reset to safe defaults after backend restart because current durable formats do not store them. Generic Skill selection is one-shot rather than a conversation snapshot.
- Desktop fixture selection remains a runtime environment gate in tracked code; tests prove exact selection, but no build-time mechanism excludes it from ordinary source runs.
- Installer, wheel protocol-asset lookup, bundled sidecar, signing, and cross-platform desktop checks do not exist by design.
- Root README.md still describes retired `/skill`/`task_modes` behavior. Current code/tests and `app/SKILLS_GUIDE.md` govern until that record is updated; the obsolete timeout issue has been removed.
- Desktop has no Citation activation path; `issue/08-citation-skill-flow-deferred.md` defers the required single-turn versus multi-turn lifecycle decision.
- Historical test counts in issue/note files do not establish current checkout health.
- The historical Phase 07 focused checks, final broad Python/npm/Cargo/Tauri checks, release build, and native behavioral journey passed as listed above. Exact native `720×560` and 200% zoom layout remains unavailable/not passed and blocks completion; live providers and real user-state behavior remain unclaimed or Unknown. Retired migration counts do not establish current importer behavior because no importer is supported.
