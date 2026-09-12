# Testing Strategy

Freshness: source/definition and fixed-revision record inspection on 2026-09-13 at `a88d44d`. No application suite, build, import smoke, native journey or live provider was executed during this maintenance. Historical observations retain the date and scope below.

## Available verification commands

Use Linux Conda `app`. From the indicated directory, commands below are defined by `AGENTS.md`, current manifests or the named tracked test files. Listing a command does not imply it was run.

| Command | Scope / definition source | Preconditions / effects | Execution this pass and limits |
|---|---|---|---|
| `cd app && poetry run pytest tests/test_state.py -q` | Agent state; AGENTS | Active Conda, installed project; pytest/cache writes | Not run: unchanged state path; one-module evidence only |
| `cd app && poetry run pytest tests/rag/test_config.py -q` | RAG config; AGENTS | Active Conda; possible cache writes | Not run: no config changes; no live semantic evidence |
| `cd app && poetry run pytest` | Complete Agent/RAG; pyproject pytest testpaths | Tests write temporary stores/files, spawn fixtures/processes, and may cache imports | Not run: writes outside maintenance boundary; prior run below |
| `cd app && poetry run pytest tests/test_skill_runtime.py tests/test_extension_skill_startup.py tests/test_extension_manager.py tests/test_skill_adherence.py -q` | Current Skill/installer/extension tests | Temporary bundles/registries, ZIP extraction and multiprocessing | Not run: effectful fixtures outside `for_agents/`; inspected definitions establish intended assertions only |
| `cd app && poetry run pytest tests/test_citation_resolution.py tests/test_citation_authority.py tests/test_citation_e2e.py tests/test_citation_slash_command.py tests/test_citation_skill_activation.py -q` | Current Citation tests | Fake provider/model paths, temporary bundles/canonical JSON | Not run: effectful fixtures; no arbitrary live-model claim |
| `cd app && poetry run pytest tests/test_desktop_service.py tests/test_desktop_conversations.py tests/test_desktop_protocol_contract.py -q` | Current routing/control/replay/contract tests | Temporary canonical/catalog state, fake runners/providers | Not run: fixtures outside boundary; native GUI not covered |
| `cd app && poetry run pytest tests/test_desktop_crash_recovery.py tests/test_conversation_repository.py tests/test_session_lifecycle.py tests/test_history_retirement.py -q` | Canonical lifecycle and real child crash fixtures | Owned temporary state and processes | Not run: unchanged broad lifecycle evidence carried forward |
| `cd app && poetry run pytest tests/test_openrouter_model.py -q` | Main default and max-token forwarding test | Fake client; import/cache effects possible | Not run: definition inspected; model availability/output acceptance unproven |
| `cd app/desktop && npm test` | package.json: Node test runner with TypeScript stripping | Installed Conda Node/dependencies; tests render React and read source/contracts | Not run in documentation scope; historical result below |
| `cd app/desktop && npm run build` | package.json: `tsc --noEmit && vite build` | Writes frontend `dist` | Not run: outside write boundary |
| `cd app/desktop && cargo test --offline --manifest-path src-tauri/Cargo.toml` | Current Cargo/Rust tests; archived exact command | Compiles/writes `target`; supervisor tests spawn child processes | Not run: outside boundary; historical full red and focused green stay distinct |
| `cd app/desktop && npm run tauri -- build --no-bundle` | README; Tauri beforeBuildCommand runs npm build | Frontend and Rust release writes; requires system native libraries | Not run: source-only build, no installer/native interaction proof |
| `cd app && poetry build` | AGENTS/pyproject | Writes `app/dist` | Not run: no packaging change |
| `python -B /mnt/c/Users/garyc/.codex/skills/infrastructure/scripts/manage_for_agents.py preflight --root .` | Loaded infrastructure helper; repo cwd | Read-only paths, permissions and Git tracking/ignore checks | Executed before knowledge writes; passed |
| `python -B /mnt/c/Users/garyc/.codex/skills/infrastructure/scripts/manage_for_agents.py bootstrap --root .` | Loaded helper | Creates missing knowledge files only | Executed; all nine preserved, none created |
| `python -B /mnt/c/Users/garyc/.codex/skills/infrastructure/scripts/manage_for_agents.py check --root .` | Loaded helper | Read-only structural/path/ID checks | Executed: Structural validation passed (exit 0); certifies structure only |
| `git --no-optional-locks diff --no-ext-diff --no-textconv --check` | Git diff validation | Read-only | Executed: passed (exit 0); no application correctness claim |

### Historical verification with retrievable provenance

The [archived results](https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/bc2c94d40562e9606a9872bc922a36423b6a10a2/issue/final_check/evidence/phase-06-check-results.json), [Python/Node output tails](https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/bc2c94d40562e9606a9872bc922a36423b6a10a2/issue/final_check/evidence/phase-06-python-node-results.txt) and [final review](https://github.com/Minervamuses/RESEARCH-AGENT-WORKSPACE/blob/bc2c94d40562e9606a9872bc922a36423b6a10a2/issue/final_check/code_review/phase-06-regression-and-closure-review.md) were read from local Git this pass. They are historical execution evidence, not reruns or independent review.

| Check / execution date | Baseline / actual result | Evidence limit |
|---|---|---|
| Full Python, 2026-09-13 | `ec9175f`: 1,138 passed, 2 warnings; exit 0, wrapper 44.359 s | Fake/offline scope; warnings are LangChain pending default and intentional duplicate ZIP member |
| Node, 2026-09-13 | `ec9175f`: 165 passed, 0 failed; exit 0, wrapper 6.285 s | No fresh browser engine/native interaction |
| Full Rust, 2026-09-13 | `ec9175f`: 35 passed, 1 failed; exit 101 | `a_new_generation_cannot_reuse_the_prior_shutdown_report` observed Degraded instead of Crashed |
| Focused Rust after correction | `cf3183b`: exact shutdown-report target passed, 35 filtered; exit 0, wrapper 5.167 s | Test setup now kill/waits under child mutex; full suite was not rerun or declared green |
| Tauri no-bundle build | `cf3183b`: exit 0, 79.553 s, offline Cargo; includes TypeScript/Vite build | Linux source release only; no installer or additional native journey |
| Native menu and Citation, archived final-check Phase03 | Keyboard/mouse insertion, caret/focus, Linux AT-SPI exposure, zero-request insertion, new catalog, real session/Citation tool/save/output plus A/B/restart/failure/interruption observed | Model/fetch seams were fake; no screen-reader speech claim, IME skipped, no dedicated GUI task-cancel entry |
| Prior typography account, 2026-09-06 | `743aaaf`: 151 Node tests/build and headless Chrome at 720/1080/1920/2560 reported in prior knowledge | Retained historical account, not a new native layout result |

The `ec9175f..a88d44d` app diff contains only the Rust test setup correction; Python/Node production/tests remain the recorded source. No application source changed in this maintenance. A prior failure cannot be rewritten as a full passing run even when its one target later passes.

The older RAG stale-inventory and empty-file probes (FAIL-001/002) remain the 2026-09-05 account at `9745fd1`. Only named current prune/search anchors were checked; no new reproduction was made. Removed plans have no active status here; exact geometry/zoom and restarted IME are evidence gaps, not an instruction to reopen an old blocked plan.

## Change-type verification matrix

| Change type | Minimum relevant checks | Broader / environment evidence |
|---|---|---|
| Graph/session/finalization | State, graph, turn-finalizer, session lifecycle/persistence modules | One reasonably inexpensive full pytest near completion under project rules; live calls require authorization |
| Canonical replay/persistence | Conversation repository, Desktop conversations/service, crash recovery and history retirement | Verify user-visible saved/replayed output and unchanged bytes; do not infer interprocess safety |
| Tool/Bash/MCP | Access/policy-node, Bash, MCP and Desktop trust/service tests | Test ask and bypass separately; injected runner does not prove live shell/provider operation |
| Skill/Citation/installer | Runtime/startup, adherence, manager, Citation activation/e2e/slash/resolution/authority | Cleanup, true effective mode, no extra model/save on completed replay, preserved source/backup bytes |
| Extension apply | Existing manager multiprocessing and scoped preview tests | Use temporary roots; stable local lock inode, not arbitrary shared/network-FS safety |
| RAG ingest/sync/store/search | Relevant `tests/rag` plus ingest/adapters | Small deterministic case first; live Ollama/OpenRouter only for an authorized integration need |
| Desktop catalog/menu/permissions | Python service/protocol, Node conversations/trust, shared JSON/TS/Rust fixtures | Native key/mouse/ARIA checks when affected; stale generation/session and zero-effect insertion |
| Desktop rendering/CSS | Node safe-content/styles tests and frontend build | Native WebKit/DPI/IME evidence is narrower and distinct from headless Chrome |
| Runtime/packaging | Runtime/manifest/import checks; build only as needed | Respect Conda/Poetry, no dependency or environment edits without approval |
| Knowledge only | Helper preflight/check, local links/IDs, diff and scope/index comparison | Static evidence sufficient; no application suite by default |

## Invariant and failure-mode coverage

These are mappings to existing checks, not fresh passing claims.

| Subject | Anchors / scope | Remaining limitation |
|---|---|---|
| Runtime/text/dependency (INV-001/002/003) | Runtime guard/config, .gitattributes, RAG adapter tests; current environment paths verified | Full dependency/import audit carried forward |
| Tools/finalization (INV-004/005/010; FAIL-009/010/011) | Access matrix, policy node, turn finalizer, Citation gate/e2e | Duplicate tool IDs and raised extended-stage exceptions not comprehensively covered; live dependencies unknown |
| Canonical authority (INV-006/016; FAIL-004/017/018) | Repository, lifecycle/crash, catalog restore and frontend logical-turn merge | Multi-process writers/catalog remain ASM-016/022 |
| RAG identity/state (INV-007/008/012; FAIL-001/002/003) | Root identity, JSON conflict/rollback, historical probes and current prune source | No unified Chroma/raw/meta failure-injection proof; stale inventory/empty re-ingest remain |
| Extension trust (INV-009/013; FAIL-005/006) | Changed-bundle startup/activation tests; manager multiprocessing/fsync/crash/exception tests | Activation check-to-read race and noncooperating writers remain |
| Earliest resolution (INV-014; FAIL-007) | Same-year/all-missing ambiguity, DOI dedupe, unique known minimum with undated alternatives; authority/workflow propagation | Year precision only |
| Desktop wire/trust (INV-011/015/017/018/023) | Shared fixtures, Python/TS/Rust validators, ask/bypass busy/ACK/trust tests, safe renderer | Source checkout only; no new native engine or cross-process test |
| Skill lifecycle and installer (INV-019/024; FAIL-015) | Citation terminal cleanup/late save, installer authority/bytes/cancel/cleanup conflict/mode and completed replay tests | Fake model quality not a live-model guarantee; host pending state is not durable |
| MCP defaults (INV-020) | CLI/Desktop default-on/opt-out tests | Live MCP availability not checked |
| Typography/composer (INV-021/022; FAIL-019/020) | Source CSS tests, array-child regressions, current menu key predicate and archived native menu | Exact native geometry/zoom, fresh IME and resource exhaustion unproven |
| Save reporting (ASM-014) | Strict ToolMessage statuses and four outcome journeys; archived scoped characterization | Model prose remains model-governed; no automatic new backlog |
| Documentation drift (FAIL-014) | Root README / Skill-guide comparison against shared handler/current Citation Skill | Still outside this maintenance's write scope |

## Test-data, fixture, and environment constraints

- Conda `app` owns Python/Node/Rust; Poetry creates no separate virtualenv. Use repository LF policy.
- Application tests visibly create temporary archives, stores, registries and child processes. They were inspected statically; none was run to evade the knowledge-only write boundary.
- Do not use user stores, secrets, extension state, generated citation bundles or caches as fresh fixtures. The exact Desktop `phase02` fixture gate requires an owned root; it is not the production Citation model path.
- Offline fake model/fetch results prove deterministic host behavior only. Real tagging/chat may contact OpenRouter; embedding requires Ollama/bge-m3.
- Protocol assets are source-checkout-relative and Tauri bundling is disabled. The active protocol requires matching command catalog/permission fields across JSON/Python/TS/Rust.
- New sessions/restart default to Normal/ask; same-process conversation controls are memory snapshots. Canonical historical thinking metadata is not a persisted next-turn preference.
- No formatter/linter/coverage threshold or CI workflow was identified in the prior account; no new CI execution was inspected.

## Known gaps and unreliable checks

- RAG partial-store writes, empty/unreadable re-ingest and stale folder metadata lack the targeted regression/failure-injection evidence described in the retained backlog.
- Broader unversioned-store/embedding compatibility, root moves, filename-stem PID collisions, init/sync exclusions and prefix search completeness remain carried-forward gaps.
- Desktop catalog and canonical conversation interprocess writes remain unproven; extension apply tests do not cover those stores.
- Managed Skill activation validation is a precheck, not a lock/snapshot for all subsequent reads.
- The Rust full-suite result is still 35 passed / 1 failed historically, followed by one focused pass after its test-only fix. No new full-suite run occurred.
- Native menu/Citation acceptance does not prove screen-reader speech, live-model quality, exact 720x560/200% zoom, all DPI configurations, or restarted IME. The user accepted skipping restart-dependent IME work; do not turn that evidence gap into new scope.
- Multi-level Thinking Effort remains explicitly [deferred](../issue/09-desktop-thinking-effort-control-deferred.md), not implemented by current Normal/Extended tests.
- Structural validation can check Markdown/paths/IDs; it cannot establish claim accuracy, runtime correctness, or automatic future-agent loading.
