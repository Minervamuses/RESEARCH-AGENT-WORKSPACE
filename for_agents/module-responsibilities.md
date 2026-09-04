# Module Responsibilities

## Responsibility map

| Module / component | Owns | Must not own | Public boundary | Evidence | Confidence |
|---|---|---|---|---|---|
| app/pyproject.toml, poetry.toml, env | Package composition and Linux toolchain | Feature policy or generated state | One distribution with agent, rag, skills | app/pyproject.toml; app/env/env-app.yml | Confirmed |
| app/agent root modules | Cross-subsystem configuration, graph/state contracts, session facade, startup, MCP, paths, ingest adapter, telemetry | RAG internals or citation domain rules | ChatSession, build_graph, AgentConfig | app/agent/README.md | Confirmed |
| app/agent/cli | Interactive loop, local slash parsing/dispatch, prompts, runtime guard | Graph execution, RAG internals, extension registry mutation logic | python -m agent.cli.chat | app/agent/cli; app/tests/test_chat_cli.py | Confirmed |
| app/agent/turns | Graph result normalization, final-response safety helpers, journal ordering, recent memory, plan log, history spill | Session lock, active skill, thinking mode, citation domain logic | GraphTurnResult, TurnOutcome, TurnJournal | app/agent/turns/README.md | Confirmed |
| app/agent/thinking | Optional rewrite/proposer/aggregate/review/revise workflow and candidate evidence | Final persistence, citation registry, general tool policy | FusionOrchestrator | app/agent/thinking/README.md | Confirmed |
| app/agent/tools | Local tool implementations, inventory, access resolution, execution-time enforcement | Session policy selection or tool business-domain rules | resolve_tool_access, PolicyToolNode | app/agent/tools/README.md | Confirmed |
| app/agent/skills | Skill discovery, metadata, manifest validation, context loading, task mode, tool brokerage | Built-in skill domain behavior | SkillMetadata, SkillRuntime | app/SKILLS_GUIDE.md; app/agent/skills | Confirmed |
| app/agent/extensions | Drop-in scan/validation, managed copies, registry, preview/apply/status, startup conversion | Installing/building dependencies, hot-reloading current sessions, executing source drop-ins | ExtensionManager, ExtensionStartup | app/agent/extensions/README.md | Confirmed |
| app/agent/history_rag | Long-term evicted-turn persistence and recall | Recent-turn ordering or plan logs | ChatHistoryStore, recall_history tool | app/agent/history_rag | Confirmed |
| app/rag | Framework-neutral collection, tagging, chunking, storage, retrieval, sync/prune, tool schemas | Agent, CLI-session, skill, or desktop policy | rag public functions and dispatch | app/rag/README.md; app/rag/docs/API.md | Confirmed |
| app/skills/citation | Citation provider, identity, resolution, persistence, registry, gate, renderer | Session lifecycle or generic tool access | CitationService and citation_workflow domain | app/skills/citation/README.md | Confirmed |
| app/agent/skills/citation | Session-scoped citation integration and finalization policy | Provider/resolution/storage implementations | CitationSessionPolicy | app/agent/skills/citation/session_policy.py | Confirmed |
| `app/agent/desktop/catalog.py` | Strict project-to-session catalog schema and atomic single-process mutations | Conversation text, model state, or project discovery | `DesktopProjectCatalog` | Catalog source/tests | Confirmed |
| `app/agent/desktop/protocol.py` and `server.py` | Python contract validation, bounded NDJSON input/output, per-request ordering, exactly one terminal result, EOF cleanup | Domain policy or native process supervision | `python -m agent.desktop.server` | Server/protocol sources/tests | Confirmed |
| `app/agent/desktop/service.py` | Safe desktop DTOs, operation gates, conversation coordination, slash routing, RAG/extension adapters, Bash approval correlation | Native child lifecycle, React presentation, provider internals | Protocol method dispatcher | Service source/tests | Confirmed |
| `app/agent/desktop/fixture_session.py` | Exact opt-in isolated acceptance fixture | Normal production session semantics or real provider/store use | `RESEARCH_AGENT_DESKTOP_FIXTURE=phase02` plus validated fixture root | Server gate; fixture tests | Confirmed test-only seam |
| `app/desktop/protocol/v1` | Language-neutral method/event/result vocabulary, limits, schemas, shared fixtures | Runtime transport or business logic | `contract.json`, `fixtures.json` | Three language implementations/tests | Confirmed |
| `app/desktop/src-tauri/src/backend.rs` | One child generation, pipe threads, request correlation, bounded stderr counts, lifecycle/restart/shutdown truth | Agent/RAG/extension business rules | Five Tauri commands and one event channel | Rust source/tests | Confirmed |
| `app/desktop/src-tauri/src/protocol.rs` | Rust-side protocol-v1 validation and trace enforcement | Python domain behavior | Rust protocol parser/validator | Contract fixtures/tests | Confirmed |
| `app/desktop/src/backend.ts`, `protocol.ts`, `conversations.ts` | Browser-side validation, bridge client, lifecycle/conversation reducers, authoritative result reconciliation | Persistence or domain authorization | Typed frontend state/client functions | TypeScript sources/tests | Confirmed |
| `app/desktop/src/App.tsx`, `trust.tsx`, `SafeContent.tsx` | UI composition, exact trust decisions, bounded safe content and URL activation | Parsing domain commands, executing shell, or writing stores | React application | Frontend sources/tests; capabilities | Confirmed |
| app/tests and app/desktop/tests | Regression evidence using fake providers/temp roots; shared protocol checks | Runtime truth by themselves | pytest, node test, Rust unit tests | app/pyproject.toml; app/desktop/package.json | Confirmed |
| issue, note, harness/plans | Decisions, incidents, research, and planned work | Current runtime authority | Human/agent records | Repository guidance; individual records | Confirmed |

## Boundary rules

- agent may import rag public boundaries; rag must not import agent or skill/application code. Current import search found no reverse dependency.
- ChatSession coordinates order and owns the session lock; it delegates graph execution, thinking, citation policy, canonical repository transitions, and journal observability rather than duplicating those implementations.
- Tool existence and tool authorization are separate. tools.access resolves the set, graph binding exposes it, and PolicyToolNode rechecks it at execution.
- app/skills/citation owns citation truth; app/agent/skills/citation owns session integration only.
- Extension source drop-ins are untrusted desired state. Only validated, approved managed copies may reach a future session.
- raw.json is the full-content RAG read surface; Chroma is the semantic index; folder_meta.json is inventory metadata. None is independently a complete transactional store.
- React gathers intent and renders bounded state; Rust owns native process/transport lifetime; Python owns policy and persistent writes. Frontend disabled controls are not authorization.
- The desktop protocol owns cross-language shapes, limits, origin rules, and request ordering. All three implementations reject incompatible messages instead of adapting them silently.
- Conversation project membership is catalog-owned, while conversation text is canonical JSON under the conversation repository. The catalog is not the transcript store.
- Desktop composer commands are parsed and executed in Python. React sends the original text and does not infer knowledge or extension side effects.
- Untrusted assistant/tool text is rendered through `SafeContent`; only credential-free absolute HTTP(S) URLs may reach the native opener. Tauri capabilities grant the WebView no shell or filesystem access.
- Generated store, cite, dist, node_modules, Rust target, caches, and user extension state are not source modules. Legacy `plan_logs` are preserved user migration input, not active runtime output.

## Ambiguous or overloaded ownership

- ChatSession is intentionally a broad composition facade. Changes must preserve delegation boundaries because it touches graph, tools, skills, citation, thinking, and persistence.
- `DesktopService` is a large composition adapter spanning sessions, transcripts, knowledge commands, extensions, approvals, and DTO limits. Its current breadth is real; future edits should preserve the underlying Python owners rather than move domain logic into the adapter.
- The desktop contract is manually represented in JSON, Python, TypeScript, and Rust. Shared fixtures and tests reduce drift, but the JSON contract is not generated into the language implementations.
- Conversation durability is split among recent in-memory turns, Chroma role pairs, plan logs, and a separate project catalog. In-process control snapshots are intentionally not durable across backend restart; only existing history/plan formats restore.
- The contract still advertises direct `knowledge.init_workspace` and `knowledge.ingest_folder` methods, while current Python handlers fail them deliberately. The supported GUI route uses canonical slash commands through `session.turn`.
- `fixture_session.py` is tracked production-package code selected by an exact environment gate. It is an acceptance seam, not an alternate product core, and must never become an implicit fallback.
- The desktop catalog uses atomic replacement but has no interprocess lock. Rust serializes one backend process, not multiple concurrently launched desktop applications.
- RAG corpus state is split across three persistence surfaces. DocumentStore orders JSON before Chroma, while repo ingest writes folder metadata before chunks; failure recovery is rerun-based rather than transactional.
- Skill tool policy says base tools are global, but README.md describes academic-paper-writing as forbidding bash. Runtime access and prose instructions currently express different meanings.
- `app/agent/README.md` does not list the tracked `desktop/` package in its package table. Root README and live code are the current evidence for that component.
- The completed desktop plan contains historical baseline prose and unchecked intent checkboxes; `build-log.md` owns completion status, while live source/tests remain stronger evidence.
