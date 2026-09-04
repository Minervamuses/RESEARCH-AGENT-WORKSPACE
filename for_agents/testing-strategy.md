# Testing Strategy

## Available verification commands

Run project commands under Ubuntu/WSL from the repository root unless the command changes directory. Conda environment app is mandatory.

| Command | Scope | Source of truth | Preconditions | Expected evidence |
|---|---|---|---|---|
| cd app && conda run -n app poetry run pytest tests/test_state.py -q | Focused Agent state smoke | AGENTS.md | Installed app environment | Target module pass/fail |
| cd app && conda run -n app poetry run pytest tests/rag/test_config.py -q | Focused RAG configuration | AGENTS.md | Installed app environment | Target module pass/fail |
| cd app && conda run -n app poetry run pytest | Complete Python Agent/RAG suite | README.md; app/pyproject.toml | No live services should be assumed; may be broader than a focused change needs | One suite result |
| `cd app && conda run -n app poetry run pytest tests/test_desktop_protocol_contract.py tests/test_desktop_service.py tests/test_slash_commands.py tests/test_desktop_conversations.py tests/test_desktop_answer_stream.py tests/test_conversation_migration.py tests/test_history_retirement.py tests/test_conversation_archive_access.py tests/test_session_persistence.py tests/test_plan_mode.py -q` | Desktop protocol, canonical conversation lifecycle, exact archive access, stream, thinking control, and strict legacy migration boundaries | Current canonical conversation and Phase 06 retirement contracts | Installed `app` environment; fake/temp state | Focused cross-subsystem result |
| `cd app && conda run -n app poetry run pytest tests/test_desktop_server.py tests/test_desktop_fixture.py tests/test_bash_tool.py -q` | NDJSON server, exact fixture gate, and Bash approval seam | Current test modules and completed GUI plan | Isolated temporary roots; no real provider/shell | Server/fixture/trust result |
| cd app/desktop && conda run -n app npm test | TypeScript shared protocol fixtures | app/desktop/package.json#scripts.test | Node from Conda app | Node test result |
| cd app/desktop && conda run -n app npm run build | TypeScript check plus Vite build | app/desktop/package.json#scripts.build | Installed node_modules | Typecheck/build result |
| cd app/desktop && conda run -n app cargo test --manifest-path src-tauri/Cargo.toml | Rust protocol/unit tests | Cargo manifest and current test module | Rust 1.97.1; may compile Tauri dependencies | Cargo test result |
| `cd app/desktop && conda run -n app npm run tauri -- build --no-bundle` | Supported Linux source-checkout Tauri build | Root README; `tauri.conf.json#build.beforeBuildCommand` | Conda toolchain and Linux Tauri system dependencies | TypeScript/Vite plus Rust release build; no installer |
| cd app && conda run -n app poetry check --lock | Manifest/lock consistency | README.md | Installed Poetry | Lock validation |
| cd app && conda run -n app poetry build | Wheel and sdist | README.md | Writable generated dist; packaging-only check | Built artifacts in app/dist |
| cd app && conda run -n app python -c "import agent, skills.citation, rag; print('app ok')" | Distribution import smoke | README.md | Installed project | app ok |
| `python3 /mnt/c/Users/garyc/.codex/skills/infrastructure/scripts/manage_for_agents.py check --root /home/minervamuses/research-agent-workspace` | `for_agents` structure and ignore rule | Infrastructure skill | WSL system Python and local skill path | Validator result |

Evidence at the audited HEAD:

| Check | Result | Evidence source |
|---|---|---|
| Selected Python regression excluding the two construction-bearing RAG modules | `879/879` passed in 4.39s with one upstream LangChain pending-deprecation warning | Completed tracked GUI build log; not rerun in this audit |
| Focused optional Bash factory repair selector | `37/37` passed in 0.54s | Completed tracked GUI build log |
| `npm test` | `107/107` passed in 4.46s; non-fatal Vite HMR port messages were recorded | Completed tracked GUI build log |
| Full desktop Cargo unit tests | `25/25` library tests passed plus empty binary/doc targets | Completed tracked GUI build log |
| Tauri source build | TypeScript no-emit, 25-module Vite build, and Rust release build passed in 2m19s; no bundle/installer | Completed tracked GUI build log |
| Source changes after the final tested application commit `a553b06` | None under `app/` or root `README.md` through audited HEAD | Current `git diff --name-only` inspection |
| Infrastructure bootstrap | Preserved all nine files; existing `/for_agents/` ignore rule was effective | This audit |
| Infrastructure final validation | Validator passed; no bootstrap markers, undefined IDs, or duplicate ID definitions; ignore rule and tracked-tree checks passed | This audit |
| Application tests/builds/live services | Not rerun | This documentation-only audit |

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
| INV-005 and INV-006 | test_turn_finalizer.py, test_thinking_session.py, test_session_lifecycle.py, test_conversation_repository.py | Strong offline coverage; raised-provider exception paths remain |
| INV-007 and INV-008 | test_root_identity.py, test_component_flow.py, test_json_store.py | Covered for successful/JSON-conflict paths |
| INV-009 | test_extension_registry, manager, MCP, startup, user journey | Covered at apply/startup; FAIL-005/FAIL-006 uncovered |
| INV-010 | citation storage/resolution/e2e/gate/finalizer suites | Strong offline coverage; ASM-014 remains model-behavior risk |
| INV-011 | Shared fixtures plus Python protocol/server, TypeScript protocol, and Rust protocol/supervisor tests | Strong offline coverage; current build-log baseline passed all three language suites |
| INV-015 | Rust lifecycle/source-launch tests, frontend bridge tests, capability/invoke inspection, isolated real-boundary journeys | Covered for supported source checkout; packaged topology intentionally uncovered |
| INV-016 | Canonical conversation lifecycle and legacy Chroma/Plan migration tests, including A→B→A, restart, crash-boundary, and target validation | Strong offline coverage; legacy inputs remain import-only |
| INV-017 | Safe-content/URL tests, protocol forbidden-key tests, DTO bounds, Tauri capability inspection | Covered for current renderer/contract; no browser-engine security audit |
| INV-018 | Prune preview, extension preview/binding, approval correlation/replay/timeout/crash tests | Strong per-process coverage; cross-process state remains uncovered |
| FAIL-001 and FAIL-002 | Temporary deterministic probes | Reproduced; no regression tests |
| FAIL-003 | Code/docs and JSON rollback tests | Partial; no Chroma mid-failure injection |
| FAIL-004 | test_history_retirement.py plus canonical lifecycle tests | Resolved; no active eviction, flush, or hard-cap path remains |
| FAIL-005 | Focused tamper probe and issue reproduction | Reproduced; no regression test |
| FAIL-006 | Control-flow proof and issue sequence | No multiprocessing regression |
| FAIL-007 | Focused same-year probe | Reproduced; existing test covers different years only |
| FAIL-008 | Git history, integrated desktop journeys, Python/TypeScript/Rust tests | Historical disconnected shell is mitigated |
| FAIL-009 | MCP/fake-provider tests | No live dependency verification |
| FAIL-010 through FAIL-012 | Focused regression tests/attributes/current code | Mitigations covered |
| FAIL-013 | Direct-handler source/tests plus supported composer routing tests | Limitation confirmed; raw direct folder methods remain intentionally disabled |

## Test-data, fixture, and environment constraints

- Conda environment app owns Python, Node, npm, Rust, and Cargo. Poetry virtualenv creation is disabled.
- Most tests use fake models/providers, monkeypatches, and temporary stores/roots; they do not prove live OpenRouter/Ollama/MCP/provider availability.
- Semantic search and real ingest require Ollama with bge-m3. Folder/repo tagging requires OpenRouter.
- Citation live tests would touch network providers and potentially local citation output; use temporary output and explicit authorization.
- Default app/store, cite, extension state, MCP logs, node_modules, dist, and Rust target are generated/local. Legacy `plan_logs` are user migration input and must remain read-only. Tests should isolate write roots and avoid user data.
- `app/agent/desktop`, the React/Tauri implementation, and their tests are tracked. The exact `phase02` fixture gate must use a caller-owned, validated temporary root and fake providers/runners; it must never touch user stores or credentials.
- Desktop Python protocol reads `app/desktop/protocol/v1` from the source tree; installed-wheel behavior is unverified and Tauri bundling is disabled.
- Shared protocol fixtures cover Python/TypeScript/Rust source contracts. Their current passing results come from the completed tracked build log, not a rerun in this audit.
- No formatter, linter, coverage threshold, or CI configuration is present.

## Known gaps and unreliable checks

- No regression tests exist for stale folder metadata, empty/unreadable re-ingest, post-startup Skill tampering, extension cross-process lost update, or same-year earliest ambiguity.
- No failure-injection test spans RAG folder metadata, raw JSON, and Chroma; no concurrency test covers simultaneous ingest/prune/read.
- No test verifies persistent-store schema migration, embedding-model compatibility, moved roots, default single-file PID collisions, or prefix-search completeness.
- No explicit timeout test covers MCP get_tools; raised aggregator/reviewer/reviser provider exceptions are not comprehensively tested.
- No multiprocessing test covers desktop catalog lost updates.
- No integrated stress test enumerates every concurrent raw-protocol RAG read/write intersection. Direct `knowledge.init_workspace` and `knowledge.ingest_folder` remain deliberate failures even though the composer route works.
- Per-conversation thinking/skill snapshots are tested in-process and intentionally reset to safe defaults after backend restart because current durable formats do not store them.
- Desktop fixture selection remains a runtime environment gate in tracked code; tests prove exact selection, but no build-time mechanism excludes it from ordinary source runs.
- Installer, wheel protocol-asset lookup, bundled sidecar, signing, and cross-platform desktop checks do not exist by design.
- Historical test counts in issue/note files do not establish current checkout health.
- This audit did not rerun application tests/builds. The current code baseline has recent tracked passing evidence, but live provider and user-state behavior remains Unknown.
