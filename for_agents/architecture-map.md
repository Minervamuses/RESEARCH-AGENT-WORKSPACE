# Architecture Map

## System summary

This is a student-owned Linux/WSL local research application. One Poetry distribution rooted at `app/` packages three Python namespaces: `agent` for the stateful LangGraph application, `rag` for framework-neutral ingest/retrieval, and `skills` for built-in workflows. Conda owns the Python/Node/Rust runtime; Poetry installs into the active `app` environment without creating a virtual environment. Local stores, plan logs, citation bundles, extension state, desktop catalog, and MCP logs are runtime artifacts rather than repository source.

The repository also contains a tracked source-checkout desktop application. React presents projects, conversations, controls, trust prompts, and bounded output. Tauri/Rust owns the native window, five allowlisted commands, one supervised Python child, NDJSON correlation, crash/restart state, and graceful-versus-forced shutdown reporting. The Python `agent.desktop` backend owns protocol validation, project/catalog coordination, conversation restoration, slash-command routing, RAG/extension adapters, Bash approval correlation, and all domain writes. This replaces the disconnected shell described by the previous audit.

## Components and boundaries

| Component | Purpose | Entry points / interfaces | Depends on | Evidence | Confidence |
|---|---|---|---|---|---|
| Runtime and packaging | Single Linux application environment and distribution | app/pyproject.toml, app/env/env-app.yml, app/poetry.toml | Conda, Poetry, Python 3.12-3.13, Node, Rust | AGENTS.md; app/pyproject.toml | Confirmed |
| Agent composition core | Session lifecycle, graph construction, configuration, startup, MCP, ingest adapter, telemetry | agent.ChatSession, agent.build_graph, python -m agent.cli.chat | LangGraph, OpenRouter, rag public API, skill runtime | app/agent/README.md; app/agent/session.py::ChatSession; app/agent/startup.py::load_session_startup | Confirmed |
| Turn and thinking lifecycle | Normal and extended execution, finalization, fixed latest-ten canonical context, process-local diagnostics | turns.execution.execute_graph, thinking.orchestrator.FusionOrchestrator | Agent graph, tool policy, conversation repository | app/agent/turns/README.md; app/agent/thinking/README.md | Confirmed |
| Tool and skill policy | Local tools, global versus skill-scoped access, runtime denial, skill context | tools.access.resolve_tool_access, PolicyToolNode, load_skill_runtime | RAG/file/shell adapters, MCP tools, manifests | app/agent/tools/README.md; app/agent/tools/access.py | Confirmed |
| Extension runtime | Scan, validate, approve, copy, register, and load drop-in Skills/MCPs | /Extension-Management, ExtensionManager, load_extension_startup | Filesystem state, model-assisted preview, MCP loader | app/agent/extensions/README.md; app/agent/extensions | Confirmed |
| Citation engine | Discover, resolve, authority-check, save, register, gate, and render citations | citation_workflow; CitationService; CitationSessionPolicy | Crossref, DataCite, doi.org, optional OpenAlex/arXiv, local cite directory | app/skills/citation/README.md; app/skills/citation | Confirmed |
| RAG subsystem | Collect, tag, chunk, index, retrieve, inspect, sync, and prune research files | rag.search/explore/list_chunks/get_context; rag.cli.ingest | Ollama/Chroma, OpenRouter tagging, JSON filesystem state | app/rag/README.md; app/rag/api.py; app/rag/cli/ingest.py | Confirmed |
| Desktop protocol | Versioned bounded request/event/result contract shared by Python, TypeScript, and Rust | `app/desktop/protocol/v1/contract.json` and `fixtures.json` | Manual language implementations and shared fixtures | Python/TypeScript/Rust protocol sources and tests | Confirmed |
| Python desktop backend | NDJSON server, safe DTO/domain adapter, durable project catalog, canonical conversation restore, lazy selected-session legacy import, and exact fixture seams | `python -m agent.desktop.server` | Agent/RAG/extension/citation public boundaries and local state | `app/agent/desktop`; `app/tests/test_desktop_*.py` | Confirmed tracked source |
| Rust/Tauri host | Validate source checkout/Conda, supervise one Python child, correlate requests, drain stderr, synthesize lifecycle failures | `backend_start`, `backend_snapshot`, `backend_request`, `backend_shutdown`, `backend_restart` | Tauri, OS pipes/processes, protocol v1 | `app/desktop/src-tauri/src/backend.rs`; `lib.rs` | Confirmed |
| React desktop client | Project/sidebar UI, transcript/composer, controls, post-finalized answer presentation, trust dialogs, safe rendering | `App`; `BackendClient`; reducers and panels | Five Tauri commands and one event channel | `app/desktop/src`; TypeScript tests | Confirmed |
| Test suite | One pytest suite plus desktop TypeScript/Rust tests and isolated fixture journeys | `app/tests`; `npm test`; `cargo test` | Fake providers and temporary roots for most checks | Manifests; current tests; completed build log | Confirmed |
| Plans and records | Historical evidence, decisions, and completed desktop execution record | `issue`, `note`, `harness/plans` | Live code remains authoritative | Tracked records and final build-log status | Confirmed non-runtime |

## External systems and adapters

| External system | Adapter / use | Failure behavior | Evidence |
|---|---|---|---|
| OpenRouter | Main chat, extended-thinking roles, extension preview explanation, folder tagging | Missing key/model prevents the affected feature; after prompt acceptance, provider errors leave a durable failed turn | app/agent/llm; app/rag/llm; README.md |
| Ollama with bge-m3 | Ingest and semantic search embeddings | Ingest/search fail when service or model is absent; raw JSON inventory/context may still work | app/rag/embedder/ollama.py; README.md |
| ChromaDB | Document knowledge vectors; legacy conversation data is read only from disposable migration clones | RAG writes are not transactional with raw JSON; no active conversation create/turn/recall/flush path initializes or queries Chroma | app/rag/store; app/agent/conversations/legacy.py; test_history_retirement.py |
| Web Search and optional GitHub MCP | External search and remote GitHub state | Missing/crashing servers are omitted with diagnostics; the session continues | app/agent/mcp.py; app/agent/startup.py |
| Citation providers | Bibliographic discovery and authority metadata | Structured partial/all-provider failures; identity conflicts fail closed | app/skills/citation/providers; app/skills/citation/service.py |
| Local filesystem | Stores, plan logs, bundles, extension registry, protocol pipes | Explicit atomic replacement exists for selected JSON/bundle writes, not for every multi-store flow | README.md; app/rag/store/json_store.py; app/skills/citation/storage.py; app/agent/extensions/registry.py |
| Linux/Tauri host | Native window, child process, and source build | Wrong Conda/source identity degrades startup; bundle/install topology is intentionally absent | `app/desktop/src-tauri`; root `README.md` |

## Runtime and deployment topology

The supported CLI topology is local Linux/WSL:

    terminal user
      -> agent.cli.chat
      -> load_session_startup
      -> ChatSession
          -> LangGraph normal turn or extended-thinking orchestrator
          -> local/RAG/MCP/citation tools
          -> one finalization and journal path
      -> terminal output

RAG and citation state are local generated files. No service, database server, worker, queue, or remote deployment topology is defined.

The supported desktop source-checkout topology is:

    React App
      -> five allowlisted Tauri invoke commands
      -> Rust BackendSupervisor
          -> validates active Conda app + checkout geometry
          -> spawns one <CONDA_PREFIX>/bin/python -m agent.desktop.server
          -> correlates bounded NDJSON requests/events/results
      -> Python DesktopServer / DesktopService
          -> project catalog + conversation restore
          -> ChatSession / RAG / extensions / Bash approval
          -> existing Python-owned stores and policies
      -> Rust event bridge
      -> React reducers, safe renderer, trust dialogs

The desktop is source-run only. `tauri.conf.json` has `bundle.active=false`; Python loads the protocol contract from `app/desktop/protocol/v1` through checkout-relative `find_app_root()`. There is no installer, bundled sidecar, remote service, queue, or cloud deployment.

Durable local state is split by owner: `desktop-projects.json` maps projects to session IDs; canonical `conversations/*.json` is the sole active transcript authority and carries accepted prompts plus terminal turns, while `ConversationRepository` is its sole writer; legacy Chroma chat history and Plan logs are read-only migration inputs; RAG uses `raw.json`, `folder_meta.json`, and Chroma; citation bundles live under the configured citation root; extension desired/applied state lives under separate drop-in/managed roots.

Legacy conversation import has two intentionally different entry conditions. Selecting a catalog session whose canonical JSON is absent lazily invokes the existing strict per-session importer. Catalog-wide batch import is an internal offline seam only: exact `RESEARCH_AGENT_DESKTOP_FIXTURE=phase02`, a validated owned fixture root, and `RESEARCH_AGENT_DESKTOP_FIXTURE_MIGRATE_CATALOG=1` are all required. Normal startup/list does not call the batch or open legacy Chroma.

## Unverified areas

- Unknown: live OpenRouter, Ollama, MCP, citation-provider, and real persistent-store behavior at this commit; no credentials or user data were inspected.
- Unknown: concurrent use by multiple desktop application processes. The Rust supervisor and Python operation gates are per process, while catalog and extension registry updates lack a shared cross-process transaction.
- Unknown: wheel-installed `agent.desktop` protocol asset lookup and any installer/standalone bundle. Current manifests and README support source checkout only.
- Confirmed only by current Phase 07 focused offline evidence: batch migration (`7 passed`), six real Python-backend SIGKILL/restart checkpoints (`6 passed`), repository temporary-write faults, restart control reset, and the no-`chat_history` fixture assertion. Final broad Python/npm/Cargo/Tauri checks and the required native Tauri manual journey remain pending; see `testing-strategy.md`.
- Sampled rather than exhaustive: unchanged agent, RAG, citation, extension, and skill internals. Their high-risk claims were rechecked at named anchors.
- Not inspected: generated stores/bundles/logs, `node_modules`, Rust `target`, Python caches, `app/dist`, and large local artifacts.
