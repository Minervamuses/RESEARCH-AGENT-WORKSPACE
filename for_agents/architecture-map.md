# Architecture Map

## System summary

This is a student-owned Linux/WSL local research application. One Poetry distribution rooted at `app/` packages three Python namespaces: `agent` for the stateful LangGraph application, `rag` for framework-neutral ingest/retrieval, and `skills` for built-in workflows. Conda owns the Python/Node/Rust runtime; Poetry installs into the active `app` environment without creating a virtual environment. Local stores, citation bundles, extension state, desktop catalog, and MCP logs are runtime artifacts rather than repository source. Old Plan logs may remain on disk but are not read or imported by the current runtime.

The repository-root `main.py` is a source-checkout convenience launcher only: it runs `npm run tauri dev` with `app/desktop` as the working directory and returns that process's exit code. It does not activate Conda, install dependencies, or introduce another backend.

The repository also contains a tracked source-checkout desktop application. React presents projects, conversations, thinking controls, trust prompts, and complete finalized output. Tauri/Rust owns the native window, five allowlisted commands, one supervised Python child, NDJSON correlation, crash/restart state, and graceful-versus-forced shutdown reporting. The Python `agent.desktop` backend owns protocol validation, project/catalog coordination, conversation restoration, slash-command routing, RAG/extension adapters, Bash approval correlation, and all domain writes. Normal answers are exposed only by one terminal `final_only` result after finalization and persistence; progress/tool events never carry answer text.

## Components and boundaries

| Component | Purpose | Entry points / interfaces | Depends on | Evidence | Confidence |
|---|---|---|---|---|---|
| Runtime and packaging | Single Linux application environment and distribution | app/pyproject.toml, app/env/env-app.yml, app/poetry.toml | Conda, Poetry, Python 3.12-3.13, Node, Rust | AGENTS.md; app/pyproject.toml | Confirmed |
| Root desktop launcher | Thin source-checkout delegation to the existing Tauri development path | `python main.py` | `npm` on `PATH`, installed Desktop dependencies, `app/desktop` checkout | `main.py`; source inspection at `743aaaf` | Confirmed source behavior |
| Agent composition core | Session lifecycle, graph construction, configuration, startup, MCP, ingest adapter, telemetry | agent.ChatSession, agent.build_graph, python -m agent.cli.chat | LangGraph, OpenRouter, rag public API, skill runtime | app/agent/README.md; app/agent/session.py::ChatSession; app/agent/startup.py::load_session_startup | Confirmed |
| Turn and thinking lifecycle | Normal and extended execution, finalization, fixed latest-ten canonical context, process-local diagnostics | turns.execution.execute_graph, thinking.orchestrator.FusionOrchestrator | Agent graph, tool policy, conversation repository | app/agent/turns/README.md; app/agent/thinking/README.md | Confirmed |
| Tool and Skill policy | Local tools, global versus Skill-scoped access, runtime denial, one-shot non-Citation Skill commands, and the persistent Citation exception | tools.access.resolve_tool_access, PolicyToolNode, build_default_registry, load_skill_runtime | RAG/file/shell adapters, MCP tools, strict manifests | app/agent/tools/README.md; app/agent/cli/slash_commands.py; app/agent/session.py | Confirmed |
| Extension runtime | Scan, validate, approve, copy, register, and load drop-in Skills/MCPs | /Extension-Management, ExtensionManager, load_extension_startup | Filesystem state, model-assisted preview, MCP loader | app/agent/extensions/README.md; app/agent/extensions | Confirmed |
| Citation engine | Discover, resolve, authority-check, save, register, gate, and render citations | citation_workflow; CitationService; CitationSessionPolicy | Crossref, DataCite, doi.org, optional OpenAlex/arXiv, local cite directory | app/skills/citation/README.md; app/skills/citation | Confirmed |
| RAG subsystem | Collect, tag, chunk, index, retrieve, inspect, sync, and prune research files | rag.search/explore/list_chunks/get_context; rag.cli.ingest | Ollama/Chroma, OpenRouter tagging, JSON filesystem state | app/rag/README.md; app/rag/api.py; app/rag/cli/ingest.py | Confirmed |
| Desktop protocol | Versioned schema-checked request/event/result contract; requests, events, failures, and non-conversation results remain bounded, while validated `session.turn`/`session.transcript` success text has no numeric bytes ceiling | `app/desktop/protocol/v1/contract.json` and `fixtures.json` | Manual language implementations and shared fixtures | Python/TypeScript/Rust protocol sources and tests | Confirmed |
| Python desktop backend | NDJSON server, safe DTO/domain adapter, durable project catalog, canonical conversation restore, dynamic one-shot Skill/composer routing, final-only results, catalog-only unavailable handling, and exact fixture seams | `python -m agent.desktop.server` | Agent/RAG/extension/citation public boundaries and local state | `app/agent/desktop`; `app/tests/test_desktop_*.py` | Confirmed tracked source |
| Rust/Tauri host | Validate source checkout/Conda, supervise one Python child, correlate requests, wait without a normal absolute request deadline, drain stderr, and synthesize lifecycle failures | `backend_start`, `backend_snapshot`, `backend_request`, `backend_shutdown`, `backend_restart` | Tauri, OS pipes/processes, protocol v1 | `app/desktop/src-tauri/src/backend.rs`; `lib.rs` | Confirmed |
| React desktop client | Project/sidebar UI, restored/live/pending transcript projection, persisted-failure reconciliation, composer keyboard policy, thinking control, final-only answer presentation, trust dialogs, safe large-content rendering, and responsive typography | `App`; `BackendClient`; reducers, renderer, and CSS | Five Tauri commands and one event channel | `app/desktop/src`; TypeScript tests; source inspection at `743aaaf` | Confirmed source behavior |
| Test suite | One pytest suite plus desktop TypeScript/Rust tests and isolated fixture journeys | `app/tests`; `npm test`; `cargo test` | Fake providers and temporary roots for most checks | Manifests, current tests, and Git history | Confirmed |
| Issue and note records | Active/deferred problems, decisions, and research context | `issue`, `note` | Live code remains authoritative | Tracked records | Confirmed non-runtime |

## External systems and adapters

| External system | Adapter / use | Failure behavior | Evidence |
|---|---|---|---|
| OpenRouter | Main chat, extended-thinking roles, extension preview explanation, folder tagging | Missing key/model prevents the affected feature; after prompt acceptance, provider errors attempt a durable failed transition, while a failed terminal write leaves pending work to become interrupted on restart | app/agent/llm; app/rag/llm; app/agent/conversations/repository.py; README.md |
| Ollama with bge-m3 | Ingest and semantic search embeddings | Ingest/search fail when service or model is absent; raw JSON inventory/context may still work | app/rag/embedder/ollama.py; README.md |
| ChromaDB | Document knowledge vectors only; old conversation `chat_history` data is not opened or imported | RAG writes are not transactional with raw JSON; no conversation create/turn/restore/recall/flush path initializes or queries Chroma | app/rag/store; test_history_retirement.py |
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

    optional python main.py launcher
      -> npm run tauri dev
      -> Tauri beforeDevCommand starts Vite

    React App
      -> five allowlisted Tauri invoke commands
      -> Rust BackendSupervisor
          -> validates active Conda app + checkout geometry
          -> spawns one <CONDA_PREFIX>/bin/python -m agent.desktop.server
          -> correlates schema-validated NDJSON requests/events/results;
             completed conversation-text results have no numeric bytes ceiling
          -> waits for normal results without a fixed elapsed-time deadline
      -> Python DesktopServer / DesktopService
          -> project catalog + conversation restore
          -> ChatSession / one-shot Skill routing / RAG / extensions / Bash approval
          -> existing Python-owned stores and policies
      -> Rust event bridge
      -> React reducers, safe renderer, trust dialogs

The desktop is source-run only. `tauri.conf.json` has `bundle.active=false`; Python loads the protocol contract from `app/desktop/protocol/v1` through checkout-relative `find_app_root()`. There is no installer, bundled sidecar, remote service, queue, or cloud deployment.

Durable local state is split by owner: `desktop-projects.json` maps projects to session IDs; canonical `conversations/*.json` is the only supported transcript source and carries accepted prompts plus terminal turns, while `ConversationRepository` is its sole writer; old conversation Chroma and Plan logs are left untouched and are not imported; RAG uses `raw.json`, `folder_meta.json`, and document Chroma; citation bundles live under the configured citation root; extension desired/applied state lives under separate drop-in/managed roots.

The session's startup Skill catalog is immutable, but invocation is asymmetric. Every non-Citation Skill is projected into a validated `/<skill-name> <prompt>` command and is active only for that one turn; `/skill` and manifest task modes are retired. Citation remains the sole persistent Skill, is controlled by the CLI-only `/citation` handler, owns session-scoped registry/finalization state, and currently has no Desktop activation path. `app/SKILLS_GUIDE.md` and live code describe this contract; the root README still contains older `/skill` and `task_modes` prose.

MCP startup is deliberately enabled by default in both CLI and Desktop session creation. Either path can explicitly opt out; the React client omits `loadMcp` for ordinary creation so the Python-owned default remains authoritative.

Conversation restore is canonical-only. Selecting a catalog session whose canonical JSON is absent returns conversation unavailable without replacing the current session. Startup, list, selection, and the isolated fixture do not read or import old Plan logs or conversation Chroma; those sources remain untouched.

## Unverified areas

- Unknown: live OpenRouter, Ollama, MCP, citation-provider, and real persistent-store behavior at this commit; no credentials or user data were inspected. The configured main-model default is `google/gemini-3.8-flash`, but its offline configuration test does not prove present OpenRouter availability.
- Unknown: native WebKit layout and resource behavior for the new responsive typography and extremely large Markdown trees. TypeScript structural tests and headless-Chrome layout observations are narrower than a maximized native Tauri visual check.
- Unknown: concurrent use by multiple desktop application processes. The Rust supervisor and Python operation gates are per process, while canonical conversation files, the project catalog, and the extension registry lack a shared cross-process transaction.
- Unknown: resource behavior for very large canonical documents at actual platform exhaustion, and for long-lived stores approaching the remaining turn-count or catalog-scan item limits. Complete answer/document/wire/transcript text has no numeric bytes ceiling.
- Unknown: wheel-installed `agent.desktop` protocol asset lookup and any installer/standalone bundle. Current manifests and README support source checkout only.
- Historical GUI and migration plan bundles were deliberately removed. Their former run counts and plan status are no longer repository evidence; use current source, tests, and fresh verification instead.
- Sampled rather than exhaustive: unchanged agent, RAG, citation, extension, and skill internals. Their high-risk claims were rechecked at named anchors.
- Not inspected: generated stores/bundles/logs, `node_modules`, Rust `target`, Python caches, `app/dist`, and large local artifacts.
