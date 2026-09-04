# Testing Strategy

## Available verification commands

Run project commands under Ubuntu/WSL from the repository root unless the command changes directory. Conda environment app is mandatory.

| Command | Scope | Source of truth | Preconditions | Expected evidence |
|---|---|---|---|---|
| cd app && conda run -n app poetry run pytest tests/test_state.py -q | Focused Agent state smoke | AGENTS.md | Installed app environment | Target module pass/fail |
| cd app && conda run -n app poetry run pytest tests/rag/test_config.py -q | Focused RAG configuration | AGENTS.md | Installed app environment | Target module pass/fail |
| cd app && conda run -n app poetry run pytest | Complete Python Agent/RAG suite | README.md; app/pyproject.toml | No live services should be assumed; may be broader than a focused change needs | One suite result |
| `cd app && conda run -n app poetry run pytest tests/test_conversation_batch_migration.py tests/test_desktop_crash_recovery.py tests/test_conversation_repository.py tests/test_session_lifecycle.py tests/test_desktop_conversations.py tests/test_desktop_fixture.py tests/test_history_retirement.py -q` | Fixture-only catalog batch, six Python-child crash/restart boundaries, prompt/terminal repository ordering, latest-ten context, restart restore, and no active conversation Chroma | Current Phase 03/06/07 canonical contracts | Installed `app` environment; owned temporary fixture roots; no real provider/store | Focused persistence/recovery result |
| `cd app && conda run -n app poetry run pytest tests/test_desktop_protocol_contract.py tests/test_desktop_service.py tests/test_slash_commands.py tests/test_desktop_answer_stream.py tests/test_conversation_migration.py tests/test_conversation_archive_access.py tests/test_session_persistence.py tests/test_plan_mode.py -q` | Desktop protocol, selected-session migration, exact archive access, stream, thinking control, and canonical persistence | Current canonical conversation and Phase 06 retirement contracts | Installed `app` environment; fake/temp state | Focused cross-subsystem result |
| `cd app && conda run -n app poetry run pytest tests/test_desktop_server.py tests/test_desktop_fixture.py tests/test_bash_tool.py -q` | NDJSON server, exact fixture gate, no-chat-history journey, and Bash approval seam | Current test modules and active Phase 07 plan | Isolated temporary roots; no real provider/shell | Server/fixture/trust result |
| cd app/desktop && conda run -n app npm test | TypeScript shared protocol fixtures | app/desktop/package.json#scripts.test | Node from Conda app | Node test result |
| cd app/desktop && conda run -n app npm run build | TypeScript check plus Vite build when run alone | app/desktop/package.json#scripts.build | Installed node_modules | Typecheck/build result; do not run separately when the Tauri build below already invokes it through `beforeBuildCommand` |
| cd app/desktop && conda run -n app cargo test --manifest-path src-tauri/Cargo.toml | Rust protocol/unit tests | Cargo manifest and current test module | Rust 1.97.1; may compile Tauri dependencies | Cargo test result |
| `cd app/desktop && conda run -n app npm run tauri -- build --no-bundle` | Supported Linux source-checkout Tauri build | Root README; `tauri.conf.json#build.beforeBuildCommand` | Conda toolchain and Linux Tauri system dependencies | TypeScript/Vite plus Rust release build; no installer |
| cd app && conda run -n app poetry check --lock | Manifest/lock consistency | README.md | Installed Poetry | Lock validation |
| cd app && conda run -n app poetry build | Wheel and sdist | README.md | Writable generated dist; packaging-only check | Built artifacts in app/dist |
| cd app && conda run -n app python -c "import agent, skills.citation, rag; print('app ok')" | Distribution import smoke | README.md | Installed project | app ok |
| `python3 /mnt/c/Users/garyc/.codex/skills/infrastructure/scripts/manage_for_agents.py check --root /home/minervamuses/research-agent-workspace` | `for_agents` structure and ignore rule | Infrastructure skill | WSL system Python and local skill path | Validator result |

Current focused Phase 07 evidence (broad and native-manual gates remain pending):

| Check | Result | Evidence source |
|---|---|---|
| `test_conversation_batch_migration.py` | `7 passed, 1 warning` | Phase 07 build log; default-off exact fixture gate, ordering/isolation, one shared snapshot, lazy rerun, safe results |
| `test_desktop_crash_recovery.py` | `6 passed, 1 warning` | Phase 07 build log; six real `python -m agent.desktop.server` SIGKILL/restart checkpoints |
| Fixture/repository/server selector | `51 passed, 1 warning` | Phase 07 build log; repository and fixture recovery coverage |
| Repository temp-failure + restart-control + no-chat-history gap selector | `5 passed, 1 warning` | Phase 07 build log; current focused additions |
| Migration + fixture + server + normal-startup history selector | `69 passed, 1 warning` | Phase 07 build log; normal startup remains batch-off and does not load active history |
| Final broad Python/npm/Cargo/Tauri evidence | Pending | Active Phase 07 plan; no current claim |
| Native Tauri keyboard/layout/manual journey | Pending and blocking | Active Phase 07 plan; subprocess/headless checks cannot substitute |
| Live providers, Ollama, user stores, and real migration | Not run | Outside the authorized fixture-only validation scope |

The earlier focused RAG probes recorded in the prior audit reproduced FAIL-001 and FAIL-002 using temporary data and deterministic doubles. Their relevant production paths did not change, but the probes were not repeated now.

## Change-type verification matrix

| Change type | Minimum focused checks | Broader checks | Manual or environment-specific evidence |
|---|---|---|---|
| Agent graph/session/turn lifecycle | Relevant test_state, test_graph_skill_loader, test_turn_finalizer, test_session_lifecycle, and test_session_persistence modules | Complete pytest once near completion when inexpensive | No live provider unless explicitly approved |
| Tool access, bash/read_file, MCP | test_tool_access, test_tool_access_matrix, test_policy_tool_node, implementation-specific module | Complete pytest | TTY approval path and MCP logs only when behavior changed |
| Extended thinking | test_thinking, test_thinking_models, test_thinking_session | Complete pytest | Live paid/provider trial only under explicit bounded authorization |
| RAG config/API/store/sync | Relevant app/tests/rag modules plus test_ingest/test_adapter_formatting | Complete pytest | Ollama/OpenRouter only for a concrete live integration need; isolate KMS_STORE_DIR |
| Citation engine/session policy | Relevant test_citation modules and test_turn_finalizer | Complete pytest | Live provider calls only when cached/fake evidence cannot answer the question |
| Skills/extensions | Relevant test_skill and test_extension modules | Complete pytest | Use temporary drop-in/state roots; never mutate real user extension state |
| Desktop protocol/backend/conversations | Relevant Python Desktop, canonical conversation, legacy migration, and Bash modules plus `npm test` | Cargo test and selected Python regression; Tauri no-bundle build when native/build surfaces change | Isolated real Tauri/Python journey for lifecycle/UI changes; never use real user stores |
| Packaging/runtime/dependency change | Runtime tests, import smoke, poetry check --lock | poetry build and complete pytest | Dependency changes require prior user approval |
| Documentation/for_agents only | infrastructure check, marker/search, ignore check, diff check | No application suite by default | Cross-document evidence audit |

## Invariant and failure-mode coverage

| Item | Current verification | Coverage status |
|---|---|---|
| INV-001 | test_runtime_env.py; observed Python/Conda paths | Covered |
| INV-002 | .gitattributes and Git attribute/diff checks | Covered policy; full corpus not rescanned |
| INV-003 | RAG/adapter tests and import search | Covered |
| INV-004 | test_policy_tool_node.py; test_tool_access_matrix.py | Covered except duplicate/empty tool-call IDs |
| INV-005 and INV-006 | test_turn_finalizer.py, test_thinking_session.py, test_session_lifecycle.py, test_conversation_repository.py, test_desktop_crash_recovery.py | Strong offline coverage for prompt-first, terminal-before-success, latest-ten, interrupted/no-auto-replay, and six kill boundaries; live providers remain unverified |
| INV-007 and INV-008 | test_root_identity.py, test_component_flow.py, test_json_store.py | Covered for successful/JSON-conflict paths |
| INV-009 | test_extension_registry, manager, MCP, startup, user journey | Covered at apply/startup; FAIL-005/FAIL-006 uncovered |
| INV-010 | citation storage/resolution/e2e/gate/finalizer suites | Strong offline coverage; ASM-014 remains model-behavior risk |
| INV-011 | Shared fixtures plus Python protocol/server, TypeScript protocol, and Rust protocol/supervisor tests | Strong offline coverage; current build-log baseline passed all three language suites |
| INV-015 | Rust lifecycle/source-launch tests, frontend bridge tests, capability/invoke inspection, isolated real-boundary journeys | Covered for supported source checkout; packaged topology intentionally uncovered |
| INV-016 | test_desktop_conversations.py, test_conversation_migration.py, and test_conversation_batch_migration.py cover A→B→A, restart, selected-session import, display-only turns, source immutability, default-off doubly gated batch, shared snapshot, and target validation | Strong offline coverage; real user-store migration remains unverified |
| INV-017 | Safe-content/URL tests, protocol forbidden-key tests, DTO bounds, Tauri capability inspection | Covered for current renderer/contract; no browser-engine security audit |
| INV-018 | Prune preview, extension preview/binding, approval correlation/replay/timeout/crash tests | Strong per-process coverage; cross-process state remains uncovered |
| FAIL-001 and FAIL-002 | Temporary deterministic probes | Reproduced; no regression tests |
| FAIL-003 | Code/docs and JSON rollback tests | Partial; no Chroma mid-failure injection |
| FAIL-004 | test_history_retirement.py plus canonical lifecycle and integrated fixture no-`store/chat_history` assertions | Resolved in the supported paths exercised offline; no active recall, eviction, flush, or hard-cap path remains |
| FAIL-005 | Focused tamper probe and issue reproduction | Reproduced; no regression test |
| FAIL-006 | Control-flow proof and issue sequence | No multiprocessing regression |
| FAIL-007 | Focused same-year probe | Reproduced; existing test covers different years only |
| FAIL-008 | Git history, integrated desktop journeys, Python/TypeScript/Rust tests | Historical disconnected shell is mitigated |
| FAIL-009 | MCP/fake-provider tests plus test_session_lifecycle.py and test_desktop_crash_recovery.py | Accepted provider failures are durably terminal and pending restarts do not auto-replay; no live dependency verification |
| FAIL-010 through FAIL-012 | Focused regression tests/attributes/current code | Mitigations covered |
| FAIL-013 | Direct-handler source/tests plus supported composer routing tests | Limitation confirmed; raw direct folder methods remain intentionally disabled |

## Test-data, fixture, and environment constraints

- Conda environment app owns Python, Node, npm, Rust, and Cargo. Poetry virtualenv creation is disabled.
- Most tests use fake models/providers, monkeypatches, and temporary stores/roots; they do not prove live OpenRouter/Ollama/MCP/provider availability.
- Semantic search and real ingest require Ollama with bge-m3. Folder/repo tagging requires OpenRouter.
- Citation live tests would touch network providers and potentially local citation output; use temporary output and explicit authorization.
- Default app/store, cite, extension state, MCP logs, node_modules, dist, and Rust target are generated/local. Legacy `plan_logs` are user migration input and must remain read-only. Tests should isolate write roots and avoid user data.
- `app/agent/desktop`, the React/Tauri implementation, and their tests are tracked. The exact `phase02` fixture gate must use a caller-owned, validated temporary root and fake providers/runners; catalog batch migration additionally requires exact `RESEARCH_AGENT_DESKTOP_FIXTURE_MIGRATE_CATALOG=1`. Neither gate may touch user stores or credentials.
- Desktop Python protocol reads `app/desktop/protocol/v1` from the source tree; installed-wheel behavior is unverified and Tauri bundling is disabled.
- Shared protocol fixtures cover Python/TypeScript/Rust source contracts. Phase 07 final cross-language/build reruns and native manual inspection are not yet claimed here.
- No formatter, linter, coverage threshold, or CI configuration is present.

## Known gaps and unreliable checks

- No regression tests exist for stale folder metadata, empty/unreadable re-ingest, post-startup Skill tampering, extension cross-process lost update, or same-year earliest ambiguity.
- No failure-injection test spans RAG folder metadata, raw JSON, and Chroma; no concurrency test covers simultaneous ingest/prune/read.
- No test verifies persistent-store schema migration, embedding-model compatibility, moved roots, default single-file PID collisions, or prefix-search completeness.
- No explicit timeout test covers MCP get_tools; raised aggregator/reviewer/reviser provider exceptions are not comprehensively tested.
- No multiprocessing test covers desktop catalog lost updates. The fixture-only batch migration assumes its owned offline phase is not concurrently edited; it is not a production startup migration.
- No integrated stress test enumerates every concurrent raw-protocol RAG read/write intersection. Direct `knowledge.init_workspace` and `knowledge.ingest_folder` remain deliberate failures even though the composer route works.
- Per-conversation thinking/skill snapshots are tested in-process and intentionally reset to safe defaults after backend restart because current durable formats do not store them.
- Desktop fixture selection remains a runtime environment gate in tracked code; tests prove exact selection, but no build-time mechanism excludes it from ordinary source runs.
- Installer, wheel protocol-asset lookup, bundled sidecar, signing, and cross-platform desktop checks do not exist by design.
- Historical test counts in issue/note files do not establish current checkout health.
- Current Phase 07 focused Python checks passed as listed above. Final broad Python/npm/Cargo/Tauri evidence, the blocking native Tauri manual journey, live providers, and user-state behavior remain unclaimed or Unknown.
