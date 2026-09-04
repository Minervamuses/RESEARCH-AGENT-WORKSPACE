# Dangerous Assumptions

## Active dangerous assumptions

### ASM-001 — External model and embedding services are available

- Assumption: Configured OpenRouter models, Ollama, bge-m3, and optional MCP/citation providers are reachable and compatible when their features run.
- Where relied on: chat, extended thinking, extension preview, folder tagging, ingest/search, web/GitHub tools, citation discovery.
- Failure if false: feature-specific startup/turn/ingest/save failure or missing tool family; no offline semantic fallback.
- Detection or mitigation: fail-fast checks, provider errors, MCP diagnostics, deterministic fake-provider tests.
- Evidence: README.md; app/agent/startup.py; app/rag/embedder/ollama.py.
- Status: Active
- Confidence: Confirmed dependency; live availability Unknown.

### ASM-002 — Persistent RAG schema and embedding configuration remain compatible

- Assumption: Existing unversioned raw.json/folder_meta.json/Chroma state uses the expected schema and one stable embedding model.
- Where relied on: RAGConfig, cached Chroma clients, all retrieval and sync functions.
- Failure if false: parse errors, stale/missing data, or semantically incompatible vectors.
- Detection or mitigation: local rebuild is documented; there is no migration/version check. Chroma cache keys omit embedding model.
- Evidence: app/rag/config.py; app/rag/store/cache.py; app/rag/README.md.
- Status: Active
- Confidence: Confirmed assumption.

### ASM-003 — RAG writers are serialized and multi-store writes complete

- Assumption: No competing process mutates folder metadata/raw JSON/Chroma during ingest or prune, and failures do not interrupt the ordered multi-store writes.
- Where relied on: ingest_repo, DocumentStore, prune_orphans.
- Failure if false: partial or stale corpus surfaces; see FAIL-001 through FAIL-003.
- Detection or mitigation: raw JSON fingerprint detects only one class of concurrent rewrite; rerun ingest is the recovery.
- Evidence: app/rag/cli/ingest.py; app/rag/store/document_store.py; app/rag/sync.py.
- Status: Active
- Confidence: Confirmed assumption.

### ASM-004 — RAG roots and implicit single-file IDs remain stable and unique

- Assumption: A repo stays at the same canonical absolute path, sync/prune uses that same root, and default filename-stem PIDs do not collide.
- Where relied on: source_namespace, scoped_source_id, ingest_single, list_diff/prune_orphans.
- Failure if false: old namespaces remain orphaned, sync gives misleading deltas, or same-stem single files replace each other.
- Detection or mitigation: explicit roots/PIDs and rebuild/prune procedures; no automated root-move/collision handling.
- Evidence: app/rag/utils/paths.py; app/rag/cli/ingest.py::ingest_single; app/rag/sync.py.
- Status: Active
- Confidence: Confirmed assumption.

### ASM-005 — Presence-only sync is understood as not detecting edits

- Assumption: Callers know list_diff compares paths, not content hashes or mtimes.
- Where relied on: /sync and prune previews.
- Failure if false: changed files can be mistaken for up-to-date indexed content.
- Detection or mitigation: explicit re-ingest of changed content; module docstring documents the limited primitive.
- Evidence: app/rag/sync.py.
- Status: Active
- Confidence: Confirmed assumption.

### ASM-006 — Indexed filenames and previews are safe to send to OpenRouter

- Assumption: Collected folders contain no secret material in names or first-line previews beyond simple skip/extension policy.
- Where relied on: repo/folder tagging.
- Failure if false: sensitive source fragments leave the local machine.
- Detection or mitigation: skip rules and user discipline; README explicitly warns not to rely on extensions as the only protection.
- Evidence: app/rag/collect.py; app/rag/cli/ingest.py::_tag_folders; README.md.
- Status: Active
- Confidence: Confirmed data boundary.

### ASM-007 — Managed Skill files cannot change after startup

- Assumption: Private installed copies remain immutable for the lifetime of a session.
- Where relied on: SkillMetadata path catalog and later load_skill_runtime activation.
- Failure if false: unapproved instructions, manifest permissions, or pinned resources can become active without apply/restart.
- Detection or mitigation: startup hash validation only; focused probe reproduced FAIL-005.
- Evidence: app/agent/extensions/startup.py; app/agent/skills/runtime.py; issue/02.
- Status: Active
- Confidence: Confirmed false premise under same-user mutation.

### ASM-008 — Only one process applies extensions to a state root

- Assumption: The process-local apply lock covers every writer.
- Where relied on: registry revision check and atomic replacement.
- Failure if false: two successful N-to-N+1 updates can overwrite one another; see FAIL-006.
- Detection or mitigation: none across processes; status/restart may reveal missing entries.
- Evidence: app/agent/extensions/manager.py::_APPLY_LOCK; app/agent/extensions/registry.py; issue/04.
- Status: Active
- Confidence: Confirmed assumption.

### ASM-009 — Year and search rank can prove the earliest citation version

- Assumption: For earliest, a minimum year plus score/rank/provider ordering is sufficient when finer dates are absent.
- Where relied on: citation resolution tie-breaking.
- Failure if false: a published version may be selected over an earlier preprint from the same year.
- Detection or mitigation: no same-year ambiguity test; focused probe reproduced FAIL-007.
- Evidence: app/skills/citation/resolution.py::decide_resolution; issue/03.
- Status: Active
- Confidence: Confirmed unsafe assumption.

### ASM-010 — Tool call IDs are unique and later failure needs no rollback

- Assumption: Tool-call IDs are non-empty/unique within an execution, and side effects remain acceptable if finalization or persistence later fails.
- Where relied on: PolicyToolNode merge, trace grouping, all mutating tools.
- Failure if false: result association can overwrite/merge incorrectly, or a failed turn leaves side effects without a recorded explanation.
- Detection or mitigation: candidate IDs isolate extended traces; no general duplicate-ID validation or transaction rollback exists.
- Evidence: app/agent/tools/policy_node.py; app/agent/turns/trace.py; app/agent/thinking/trace.py.
- Status: Active
- Confidence: Inferred risk from current control flow.

### ASM-011 — Instruction-level tool prohibitions are sufficient

- Assumption: A Skill instruction saying not to use bash is equivalent to enforced unavailability.
- Where relied on: README description of academic-paper-writing.
- Failure if false: the model can still call globally bound bash after its normal approval gate.
- Detection or mitigation: runtime availability block exposes the true set; resolve_tool_access keeps base tools global.
- Evidence: README.md; app/agent/tools/access.py; test_tool_access_matrix.py::test_skill_switch_does_not_change_bash_permission_mode.
- Status: Active
- Confidence: Confirmed documentation/runtime mismatch.

### ASM-012 — Desktop remains a valid source checkout and contract copies stay aligned

- Assumption: Rust can derive the repository/app roots from its Cargo manifest, the Conda `app` interpreter remains at `<CONDA_PREFIX>/bin/python`, Python can read `app/desktop/protocol/v1`, and the manually maintained Python/TypeScript/Rust validators remain synchronized.
- Where relied on: every supported desktop startup and protocol request.
- Failure if false: startup degrades, installed-wheel/relocated-binary use fails, or one language rejects/accepts a shape differently.
- Detection or mitigation: strict source/Conda checks, shared contract/fixtures, three-language tests, and explicit source-only README guidance. `pyproject.toml` still does not package the desktop contract and Tauri bundling is disabled.
- Evidence: `app/desktop/src-tauri/src/backend.rs::source_conda_launch`; `app/agent/desktop/protocol.py`; protocol fixtures; manifests.
- Status: Active
- Confidence: Confirmed source-checkout dependency; any packaged topology Unknown.

### ASM-013 — MCP and extended-thinking stages terminate promptly

- Assumption: MCP get_tools and aggregator/reviewer/reviser provider calls return or raise within acceptable time.
- Where relied on: session startup and extended turns.
- Failure if false: session creation or a turn can hang/bypass finalization.
- Detection or mitigation: proposer candidates have timeouts; MCP startup and later thinking stages lack consistent explicit containment.
- Evidence: app/agent/mcp.py; app/agent/thinking/orchestrator.py.
- Status: Active
- Confidence: Inferred from missing timeout/exception boundaries.

### ASM-016 — Only one desktop backend mutates the project catalog

- Assumption: separate desktop application processes do not register conversations concurrently against the same `desktop-projects.json`.
- Where relied on: `DesktopProjectCatalog.register_session` reads an in-memory snapshot and atomically replaces the file without an interprocess lock or compare-and-swap.
- Failure if false: two successful registrations derived from the same snapshot can overwrite one another, leaving a saved conversation absent from the sidebar.
- Detection or mitigation: one Rust supervisor serializes one child inside one application; catalog reload/status can reveal missing membership. No cross-process guard exists.
- Evidence: `app/agent/desktop/catalog.py`; `app/desktop/src-tauri/src/backend.rs`.
- Status: Active
- Confidence: Confirmed assumption from write ordering; no multiprocessing reproduction run.

### ASM-018 — Production launches do not carry the exact fixture gate

- Assumption: normal users do not launch Tauri with both `RESEARCH_AGENT_DESKTOP_FIXTURE=phase02` and a valid fixture root.
- Where relied on: `agent.desktop.server._build_runtime_service` selects the isolated fake service solely from that exact environment value.
- Failure if false: the UI starts against deterministic fixture conversations/providers instead of the real `ChatSession`, while still using the real protocol/service shell.
- Detection or mitigation: fixture root validation is strict and diagnostics/content are recognizable; all other gate values select production. There is no separate build-time exclusion.
- Evidence: `app/agent/desktop/server.py`; `app/agent/desktop/fixture_session.py`; fixture tests.
- Status: Active
- Confidence: Confirmed test seam and premise.

## Assumptions under investigation

### ASM-014 — Model prose truthfully reflects citation save outcomes

- Assumption: The model follows the Skill and model-visible SaveBatchOutcome when describing saved/reused/failed items.
- Where relied on: final citation response; host intentionally does not replace model prose.
- Failure if false: user-facing prose can claim success after a failed tool outcome even though artifact/telemetry is correct.
- Detection or mitigation: strict tool content/artifact and existing deterministic tests; optional separate human status block remains future work.
- Evidence: issue/01-citation-save-result-reporting.md; app/skills/citation/tool.py; app/agent/session.py.
- Status: Under investigation
- Confidence: Inferred model-behavior risk, not a reproduced current incident.

### ASM-015 — Desktop operation gates cover every unsafe overlap

- Assumption: the service's turn, knowledge-mutation, extension, create, and shutdown flags reject every unsafe concurrent request accepted by the concurrent NDJSON server.
- Where relied on: overlapping protocol requests; some read-only knowledge methods do not take the mutation context manager, and guards are process-local booleans on one event loop.
- Failure if false: stale results, RAG read/write races, inconsistent extension/session state, or misleading busy status.
- Detection or mitigation: focused busy/approval/shutdown tests cover major intersections; frontend reducers also disable overlapping user actions. No integrated stress test covers all raw-protocol combinations.
- Evidence: `app/agent/desktop/server.py`; `app/agent/desktop/service.py`; desktop service tests.
- Status: Under investigation
- Confidence: Partially verified; complete intersection safety Unknown.

## Retired assumptions

- issue/05: repository line endings no longer depend on global Git defaults; .gitattributes now owns LF policy.
- issue/06: separate citation/tool quotas no longer need to align with a smaller graph recursion constant; one AgentConfig graph fuse with early finalization governs the current graph.
- ASM-017: catalog registration no longer depends on a later eviction or shutdown flush. The canonical repository writes an accepted prompt as `pending` before provider/tool execution and writes the terminal state directly; lifecycle, crash-boundary, restart, and Desktop conversation tests cover the ordering.
