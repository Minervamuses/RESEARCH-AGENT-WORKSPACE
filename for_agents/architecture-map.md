# Architecture Map

Freshness: revalidated 2026-10-23 at `3f9176a` by static inspection of source, manifests, the protocol contract and current READMEs, with a focused update at `d74065f` for the ignore-rule and Plan-log commits. Extension-runtime and ZIP-installer internals received only a focused check; their other claims rest on 2026-09-13 evidence at `a88d44d`. No application, build, native UI or provider run occurred. See [audit coverage](README.md#audit-coverage).

## System summary

This is a student-owned, local Linux/WSL research workspace. One Poetry distribution rooted at `app/` packages three namespaces:
- `agent`: the LangGraph application, the desktop backend and the CLI.
- `rag`: framework-neutral ingest and retrieval.
- `skills`: built-in Skills, including the Citation engine.

Conda environment `app` owns Python 3.13, Poetry, Node and Rust. Poetry installs into it without creating a virtual environment (AGENTS.md, `app/poetry.toml`).

The desktop application is the primary user surface.
- **Launch.** `python main.py` builds a release Tauri binary when its inputs are newer, then runs it.
- **Process layout.** React, with a Monaco editor, talks to a Rust supervisor. The supervisor runs one Python backend child over newline-delimited JSON protocol v1.
- **Project.** The user explicitly opens a project folder. Its `RESEARCH.md` holds the research rules and the conversation `historyDirectory`.
- **Documents and comments.** The user edits `.md`, `.markdown` and `.tex` files inside the project. They comment on document or chat passages, then send the main message plus every comment as one turn with frozen references.
- **Controls.** Ask/Bypass permission governs side effects. Stop cancels and settles the active turn. Conversations can be renamed or deleted.
- **No auto-restore.** Nothing reopens the last project, document or conversation (root `README.md`).

The CLI (`python -m agent.cli.chat`) shares `ChatSession`, tools, Skills and Citation with the desktop. It has no project workspace, document editor, approval UI or Stop scope.

Web search is a vendored Node/TypeScript MCP server in `app/vendor/web-search-mcp`, derived from mrkrsl/web-search-mcp. It is built locally into a git-ignored `dist/`, searches Google only through Playwright's full Chromium, and starts as a fresh process for every tool call.

Every record stays on the local machine: diagnostic logs, the backend stderr log, conversation JSON, MCP stderr logs and saved citation bundles. Full prompts, intermediate model replies and tool outputs exist only in memory (root `README.md`, section 記錄了哪些資訊).

Repository records:
- AGENTS.md is the only tracked instruction file. `CLAUDE.md`, `app/SKILLS_GUIDE.md` and `app/agent/extensions/README.md` were deleted on 2026-10-15.
- `issue/` no longer exists.
- `note/` holds research notes.
- `harness/plans/2026-10-22-web-search-acceptance-fixes/` is a completed plan record, not active work.

## Components and boundaries

| Component | Purpose | Entry points / interfaces | Depends on | Evidence (source / type / proves / scope) | Confidence |
|---|---|---|---|---|---|
| Runtime and packaging | One Linux environment and one distribution | `app/pyproject.toml` (Python `>=3.12,<3.14`; packages `agent`, `rag`, `skills`), `app/poetry.toml` (no venv), `app/env/env-app.yml` (python 3.13, poetry, nodejs `>=20,<25`, rust 1.97.1) | Conda, Poetry | Manifest inspection. On 2026-10-23 the Conda `app` binaries reported Python 3.13.14, Node v24.18.0 and cargo/rustc 1.97.1 | Confirmed |
| Root launcher | Build the release GUI when stale, then run it | `python main.py [--dev] [--rebuild]`. `--dev` runs `npm run tauri dev`. By default it runs `npm run tauri build -- --no-bundle` when a listed desktop input is newer than the binary, then `src-tauri/target/release/research-agent-desktop` (or under `$CARGO_TARGET_DIR`) | npm, Tauri CLI, cargo, system WebKitGTK libraries | `main.py::main`, `_release_is_current`, `_desktop_environment`; `app/tests/test_desktop_launcher.py` definitions | Confirmed source |
| Rust/Tauri host | Native window, one supervised Python child, native pickers | Seven invoke handlers: `backend_start`, `backend_snapshot`, `backend_request`, `backend_shutdown`, `backend_restart`, `pick_project`, `pick_document`. One event channel, `research-agent://backend-event` | Tauri 2, OS pipes, protocol v1, Conda `app`, `powershell.exe` and `wslpath` | `app/desktop/src-tauri/src/lib.rs::run`; `backend.rs::BackendSupervisor`, `run_windows_picker`; `capabilities/main.json` | Confirmed source |
| React client | Workspace UI, editor, comments, transcript, trust panels | `App.tsx`; `backend.ts::createBackendClient` (auto-start through `initialize()`); `conversations.ts` reducers and `composeTurnText`; `DocumentEditor.tsx` (Monaco 0.57.0); `trust.tsx`; `SafeContent.tsx` | The seven Tauri commands and one event channel; uses 20 of the 34 protocol methods | Source inspection of `app/desktop/src` | Confirmed source |
| Desktop protocol v1 | Shared vocabulary and limits | `app/desktop/protocol/v1/contract.json` (34 methods, 20 request events, 4 process events, 23 error codes) and `fixtures.json`. `protocolVersion` is still 1; growth has been additive | Hand-written validators in Python, TypeScript and Rust | Contract and validator inspection | Confirmed |
| Python desktop server | NDJSON loop, one task per request, exactly one terminal result, cancellation mapped to `TURN_CANCELLED`, incident catch-all, fixture gate | `python -m agent.desktop.server`; `DesktopServer`, `RequestContext` | `protocol.py`, `service.py`, `agent.diagnostics` | `app/agent/desktop/server.py::_handle_request`, `_build_runtime_service` | Confirmed |
| Desktop service | All desktop domain adaptation | `DesktopService.dispatch`: 34 handlers, 1:1 with the contract | `ChatSession`, conversations, catalog, documents, `LocalWorkScope`, extensions, RAG | `app/agent/desktop/service.py` (4,229 lines) | Confirmed |
| Project catalog | Project inspection and initialization through `RESEARCH.md`, projectId, history ownership, per-project catalog | `inspect_project`, `initialize_project`, `load_project_catalog`, `DesktopProjectCatalog` | conversations | `app/agent/desktop/catalog.py` | Confirmed |
| Document workspace | Versioned in-memory editing state for project documents | `DocumentWorkspace` methods `select_root`, `open`, `validate_snapshot`, `resolve_range`, `prepare`, `apply`, `save`, `undo` | stdlib filesystem | `app/agent/desktop/documents.py` | Confirmed |
| Conversation store | Canonical transcript persistence | `ConversationRepository` operations create, load, save, rename, delete, append_pending, complete_turn, fail_turn, retry_turn, latest_context, scan. Writes schema v3; reads v1 to v3 | stdlib | `app/agent/conversations/{models,repository}.py` | Confirmed |
| Agent session core | Turn lock, prompt-first persistence, slash and inline Skills, thinking dispatch, finalization, incidents, cancellation | `agent.ChatSession`, `agent.build_graph`, `agent.ingest.LocalWorkScope` | graph, tools, Skills, Citation policy, conversations, observability | `app/agent/session.py`, `graph.py`, `ingest.py` | Confirmed |
| Tool and Skill policy | Tool access, execution-time admission with a consent hook, inline and composite Skill runtimes | `tools.access.resolve_tool_access`, `PolicyToolNode`, `skills.runtime.resolve_skill_references`, `combine_skill_runtimes`, `load_skill_runtime` | MCP tools, RAG/file/shell adapters | `app/agent/tools/*`, `app/agent/skills/runtime.py` | Confirmed |
| Extended thinking | Rewrite, proposers, aggregation, review, repair | `FusionOrchestrator` | Bounded OpenRouter roles; read-only proposer allowlist | `app/agent/thinking/orchestrator.py` | Confirmed (focused) |
| LLM adapter | Bounded OpenRouter client | `agent/llm/openrouter.py::get_chat_model`, `bounded_sdk_client` | `langchain-openrouter==0.2.6` and the transitive `openrouter` SDK | Source inspection | Confirmed |
| Diagnostics and observability | Redacted rotating log, incident IDs, per-turn timing | `agent.diagnostics.install_diagnostic_log`, `attach_incident`; `agent.observability.TurnTimingTrace` | `agent/paths.py` | Source and root README | Confirmed |
| MCP client | MCP spec resolution and loading; web_search per-call lifecycle | `agent/mcp.py::resolve_mcp_specs`, `load_mcp_tools_with_families`, `_bounded_web_search` | `mcp` 1.27.0, `langchain-mcp-adapters` 0.2.x, Linux `/proc` | Source inspection | Confirmed |
| Web Search MCP server | Search, page reading, output formatting | Tools `full-web-search`, `get-web-search-summaries`, `get-single-web-page-content`; entry `dist/index.js` | Node, Playwright full Chromium, axios, cheerio | `app/vendor/web-search-mcp/src/*.ts`, vendored `README.md` | Confirmed source |
| Citation engine | Discovery, resolution, verification, storage, registry, gate, rendering | `citation_workflow` tool; `CitationService` (one per Citation task); `CitationSessionPolicy` | Crossref, DataCite, optional OpenAlex, doi.org, arXiv, local bundle directory | `app/skills/citation/*`, `app/agent/skills/citation/session_policy.py` | Confirmed |
| RAG subsystem | Collect, tag, chunk, index, retrieve, sync, prune | `rag.search`, `explore`, `list_chunks`, `get_context`; `rag.cli.ingest`; host seam `rag/types.py::work_callbacks` | Ollama and Chroma (imported lazily), OpenRouter tagger, JSON files | `app/rag/*` | Confirmed |
| Extension runtime | Managed Skill/MCP preview and apply; ZIP installer | `ExtensionManager`, `SkillInstaller` (now with `bypass_approval`) | Managed copies, registry, Linux flock | `app/agent/extensions/manager.py` focused check | Confirmed (focused; internals carried forward) |
| Test suites | Regression evidence | `app/tests` (pytest), `app/desktop/tests` (node --test), Rust `#[test]` functions, `app/vendor/web-search-mcp/tests/*.mjs` | Fakes, temporary roots, stub engines | Manifests and test definitions | Confirmed |
| Records | Research notes and one completed plan record | `note/`, `harness/plans/2026-10-22-web-search-acceptance-fixes/` | Nothing at runtime | Tracked files | Confirmed non-runtime |

## External systems and adapters

| External system | Adapter / use | Failure behavior | Evidence |
|---|---|---|---|
| OpenRouter | Main chat, thinking roles and the extension preview explanation. RAG folder tagging uses a separate client | Main path: 600 s per HTTP attempt. At most 2 retries for 5xx or network errors; no retry for timeout, 4xx or 429. The accepted turn becomes failed with an incident reference. The tagger keeps SDK defaults (`MAX_RETRIES=10`) | `agent/llm/openrouter.py`; `rag/llm/openrouter.py`; `app/tests/test_openrouter_model.py` |
| Ollama with bge-m3 | Ingest and semantic-search embeddings | Ingest and search fail without the service or model; raw JSON reads may still work | `rag/embedder/ollama.py` |
| ChromaDB | Document vectors only | Not transactional with raw JSON or folder metadata (FAIL-003) | `rag/store` |
| Google, via local Chromium | The only Web Search engine | HTTP ≥400 or a `/sorry/` redirect becomes an engine error. There is no fallback engine; a short batch is reported as is | `app/vendor/web-search-mcp/src/search-engine.ts`; vendored README |
| Web Search process | `agent/mcp.py` spawns `/bin/sh -c` running `node dist/index.js`, with stderr appended to a log and stdout filtered to JSON lines, once per call | Discovery is bounded by min(15 s, `DEFAULT_TIMEOUT`); each call by `DEFAULT_TIMEOUT` (default and maximum 300 s). A missing build or missing `node` yields a warning, a diagnostic and no tools | `agent/mcp.py`; `app/tests/test_mcp.py` |
| GitHub MCP (opt-in, off by default) and drop-in MCP servers | Additional MCP tools | Loaded sequentially; `get_tools()` has no timeout (ASM-013); failures become diagnostics | `agent/mcp.py::load_mcp_tools_with_families` |
| Citation providers | Crossref and DataCite discovery; OpenAlex only with `OPENALEX_API_KEY`; doi.org CSL/BibTeX verification; arXiv API plus one hard-coded NeurIPS-2017 entry as authority | 25 s httpx timeout per phase, classified failures, bounded retries. Search skips a transiently failed provider for the rest of the task. Save reports a per-item outcome | `skills/citation/hub.py`, `providers/net.py`, `service.py` |
| Windows interop | Native folder and file pickers via `powershell.exe`, `wslpath` and `WSL_DISTRO_NAME` | `NATIVE_PICKER_FAILED`. There is no manual path entry and no picker timeout (ASM-026) | `backend.rs::run_windows_picker` |
| Local filesystem | Stores, `RESEARCH.md`, project documents, logs | Conversations, catalog, `RESEARCH.md` and documents are replaced atomically from a temp file after a fingerprint precheck. The only interprocess lock is extension apply's flock | conversations repository, catalog, documents |
| Linux, WebKitGTK, WSLg | Native window | The release build needs system libraries. WSLg D3D12 overrides apply only when none of five GPU variables is set and the driver files exist | root `README.md`; `main.py::_desktop_environment` |

## Runtime and deployment topology

CLI path (local Linux/WSL):

```text
terminal -> agent.cli.chat (Conda guard, cli.log) -> load_session_startup -> ChatSession
  -> LangGraph normal turn or extended-thinking orchestrator
  -> local tools, RAG, MCP (web_search started per call), Citation
  -> one finalization chokepoint -> canonical JSON under <persist_dir>/conversations
```

Desktop path (source checkout only):

```text
python main.py [--dev | --rebuild]
  -> when stale: npm run tauri build -- --no-bundle   (tsc + vite build, cargo release)
  -> src-tauri/target/release/research-agent-desktop  (cwd app/desktop)
React App -> 7 Tauri commands
  pick_project / pick_document -> powershell.exe dialog -> wslpath or distro mapping -> canonical Linux path
  backend_* -> Rust BackendSupervisor
     validates Conda app and the checkout (CARGO_MANIFEST_DIR fixed at build time)
     spawns <CONDA_PREFIX>/bin/python -m agent.desktop.server (cwd repo root, PYTHONPATH=app)
     NDJSON protocol v1; child stderr -> desktop-backend.stderr.log (only counts reach React)
  Python DesktopServer / DesktopService
     workspace.select -> RESEARCH.md -> <historyDirectory>/{conversations/, desktop-projects.json}
     ChatSession -> graph, tools, Skills, Citation, MCP, RAG
     DocumentWorkspace -> project documents (.md, .markdown, .tex)
     desktop-backend.log (diagnostics, turn_trace)
```

- `tauri.conf.json` has `bundle.active=false`. There is no installer, bundled sidecar, remote service, queue or cloud deployment.
- The release binary stays bound to the checkout path it was built from. The launcher's mtime check does not detect a moved checkout (ASM-012).

Durable local state, by owner:
- **User project.** `RESEARCH.md` holds one metadata block plus the rules text. Documents are edited in place.
- **Desktop history.** `<historyDirectory>/conversations/*.json`, written only by `ConversationRepository`, and the one-project catalog `<historyDirectory>/desktop-projects.json`. The default history is `<persist_dir>/projects/<projectId>`, where projectId = `p-` + sha256(canonical root)[:32].
- **CLI history.** `<persist_dir>/conversations/`.
- **RAG.** `raw.json`, `folder_meta.json` and document Chroma under `persist_dir` (`KMS_STORE_DIR`, default `app/store`). The workspace `.gitignore` ignores `/app/store/` (`c12470f`).
- **Citations.** Bundles under `cite/`, `CITATION_OUTPUT_DIR` or `AgentConfig.citation_output_dir`.
- **Extensions.** Drop-in and managed roots under `app/tool`.
- **Logs.** Diagnostics under `$AGENT_LOG_DIR` or `$XDG_STATE_HOME/research-agent/logs`; MCP stderr logs under `$XDG_CACHE_HOME/agent-mcp/`.

Several operational facts follow from this layout:
- **MCP startup.** It is on by default for CLI and Desktop. CLI `--no-mcp` and Desktop `loadMcp:false` opt out. It takes effect only when `dist/index.js` exists and `node` is on `PATH`.
- **Legacy history.** Desktop conversations created before project scoping (global store, projectId `local`) cannot be reached from the GUI. No current code reads old Plan logs or conversation Chroma; the last Plan-log support, `AgentConfig.plan_logs_dir`, was removed in `73c8db1`.

## Unverified areas

- **Live services and native UI.** Unknown: live OpenRouter, Ollama, Google, citation-provider and doi.org behavior; native WebKitGTK rendering of Monaco, comment markers and fixed-px text; IME; `window.confirm`; the PowerShell picker; a release-binary run. No credentials or user stores were inspected.
- **Concurrency.** Unknown: several desktop instances sharing a history directory or documents. Only extension apply has an interprocess lock.
- **Size limits.** Unknown: resource behavior for documents and transcripts near the 1 MiB submission limit or the 2 MiB line limit (ASM-030).
- **Validator depth.** Rust `protocol.rs` and TypeScript `protocol.ts` were read for structure, limits and new message kinds, not line by line.
- **Not inspected.** `app/store` contents (user data), `node_modules`, Rust `target`, `dist`, caches, and evidence data under `harness/plans/*/evidence/`.
