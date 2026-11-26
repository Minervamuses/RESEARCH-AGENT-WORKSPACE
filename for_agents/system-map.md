# System Map

<!-- for_agents: verified=32cf47f date=2026-11-26 -->

> What exists, who owns which behavior, and where to find things.

## Summary

```text
python main.py [--dev | --rebuild]
  └─ Tauri WebKitGTK window (React + Monaco + CitationPanel) [app/desktop/src/App.tsx]
       ├─ pick_project / pick_document ──> powershell.exe + Win32 foreground dialog
       └─ backend_* + research-agent://backend-event [app/desktop/src-tauri/src/backend.rs]
            └─ NDJSON stdin/stdout protocol v1 [app/desktop/protocol/v1/contract.json]
                 └─ python -m agent.desktop.server [app/agent/desktop/server.py]
                      └─ DesktopService (25 RPC methods) [app/agent/desktop/service.py]
                           ├─ project.py (RESEARCH.md + history scan)
                           ├─ DocumentWorkspace (.md / .markdown / .tex)
                           ├─ ChatSession (LangGraph / FusionOrchestrator)
                           │    ├─ ConversationRepository (schema v3 JSON)
                           │    ├─ document_context.py (trimmed model replay)
                           │    ├─ Skills (app/skills/*) + Extensions (app/tool/*)
                           │    ├─ MCP (web_search Chromium per call, github, drop-ins)
                           │    └─ RAG (app/rag/*: Chroma + raw.json + folder_meta.json)
                           └─ skills/citation/* (references.json, Pandoc) + bime_export.py (bime_word)

CLI path: python -m agent.cli.chat ──> ChatSession (task-only citations, no project workspace)
```

This repository is a single-user local Linux/WSL academic research workspace (`AGENTS.md`, `CLAUDE.md`). One Poetry package rooted at `app/pyproject.toml` distributes `agent`, `rag`, and `skills` inside the Conda `app` environment (`app/env/env-app.yml`). The primary surface is the Tauri v2 desktop app (`app/desktop/`), which runs **one opened project, one selected conversation, and one active research turn at a time** (`INV-035`). Verified citations persist only in the project's CSL-JSON bibliography (`references.json`), and conversation lists derive directly from scanning `<historyDirectory>/conversations/*.json` with no separate catalog file.

## Components

| Component | Responsibility | Main anchors | Talks to | Notes |
|---|---|---|---|---|
| Root launcher | Check release binary mtime against desktop inputs, rebuild via Tauri CLI when stale, set WSLg D3D12/WebKit env, launch binary | `main.py::main`, `main.py::_release_is_current` | `npm`, Tauri binary | Skips Conda validation (`INV-001`) |
| Rust/Tauri host | Window shell, 7 Tauri invoke commands, single Python child generation supervisor, 500 ms stdout-EOF crash grace, protocol framing check, Win32 foreground pickers | `app/desktop/src-tauri/src/lib.rs::run`, `app/desktop/src-tauri/src/backend.rs::BackendManager`, `app/desktop/src-tauri/src/protocol.rs::parse_protocol_value` | React WebView, Python `server.py`, `powershell.exe` | `backend.rs` (2,505 LOC) combines supervision, stderr rotation, framing reader, and Windows pickers |
| React desktop UI | Single-workflow state coordinator, Monaco editor + zoom + citekey completion, passage comments, collapsible `CitationPanel`, transcript, modals | `app/desktop/src/App.tsx::App`, `app/desktop/src/api.ts::createApi`, `app/desktop/src/DocumentEditor.tsx::DocumentEditor`, `app/desktop/src/CitationPanel.tsx::CitationPanel` | Rust invoke/event bridge (`app/desktop/src/backend.ts`) | `App.tsx` (1,928 LOC) owns top-level state; `src/components/*` are pure views (`ui-architecture.md`) |
| Protocol v1 layer | Single wire vocabulary (25 methods, 8 request events, 4 process events, 25 error codes), Python schema/exit redaction, TS request check + ID echo | `app/desktop/protocol/v1/contract.json`, `app/agent/desktop/protocol.py::validate_message`, `app/desktop/src/protocol.ts` | Rust `protocol.rs`, `DesktopServer`, `api.ts` | Python is sole runtime result schema validator; `npm test` checks TS DTO parity (`PLAY-001`) |
| Desktop NDJSON server | Async stdin reader, bounded `ProtocolWriter` queue (1,024), per-request event sequencing, single terminal result, incident catch-all | `app/agent/desktop/server.py::DesktopServer`, `app/agent/desktop/server.py::ProtocolWriter`, `app/agent/desktop/server.py::RequestContext` | Rust pipes, `DesktopService`, `diagnostics.py` | 5 s stdin-EOF drain grace (`_DEFAULT_EOF_GRACE_SECONDS`) |
| Desktop service & ops | 25-method RPC router, busy queries, approvals, turn/Stop/Retry Stop, `document_edit` + citekey gate, `bibliography.*`, `/init`/`/ingest`/`/sync`/`/prune`, extensions | `app/agent/desktop/service.py::DesktopService`, `app/agent/desktop/turn_ops.py::_TurnOps`, `app/agent/desktop/document_ops.py::_DocumentOps`, `app/agent/desktop/bibliography_ops.py::_BibliographyOps`, `app/agent/desktop/approvals.py::_ApprovalOps` | `project.py`, `DocumentWorkspace`, `ChatSession`, `skills/citation/*`, `bime_export.py` | Split across `service.py` + 11 mixin modules (`errors.py`, `*_ops.py`, `approvals.py`, `transcript.py`, `turn_context.py`) |
| Project & document workspace | Parse/update `RESEARCH.md` metadata, scan project conversation history, contain `.md`/`.markdown`/`.tex` paths (`<= 1 MiB`), version-check saves/applies/undos | `app/agent/desktop/project.py::inspect_project`, `app/agent/desktop/project.py::open_project_history`, `app/agent/desktop/documents.py::DocumentWorkspace` | `ConversationRepository`, local filesystem | `LEGACY_CATALOG_FILENAME` (`desktop-projects.json`) tolerated on init, never read or written |
| Agent session & graph | Turn lock, `TurnOptions`, prompt-first v3 persistence, Skill activation, `READ_ONLY_DOCUMENT_SKILLS`, LangGraph tool loop, response repair, single finalizer | `app/agent/session.py::ChatSession`, `app/agent/graph.py::build_graph`, `app/agent/document_context.py::replay_history_inputs`, `app/agent/ingest.py::LocalWorkScope` | `ConversationRepository`, `PolicyToolNode`, `FusionOrchestrator`, `TurnTimingTrace` | `ingest.py` owns both RAG wrappers and turn-wide `LocalWorkScope` |
| Conversation store | Strict schema-v3 JSON parse/encode, atomic temp+fsync+link/replace writes, SHA-256 prechecks, history scan, 10-turn context window | `app/agent/conversations/repository.py::ConversationRepository`, `app/agent/conversations/models.py::ConversationDocument` | `<historyDirectory>/conversations/*.json` | Rejects schema v1/v2 as `unsupported_version` (`INV-006`) |
| Tool, Skill & extension runtime | Base tool inventory, global vs skill-scoped tool resolution, `PolicyToolNode` admission/consent, `app/skills/*` loader, drop-in preview/apply + ZIP installer | `app/agent/tools/inventory.py::BASE_TOOL_DOCS`, `app/agent/tools/access.py::resolve_tool_access`, `app/agent/tools/policy_node.py::PolicyToolNode`, `app/agent/skills/runtime.py::SkillRuntime`, `app/agent/extensions/manager.py::ExtensionManager` | Built-in Skills, `app/tool/*`, MCP tools | 6 built-in Skills (`_prompt-master`, `academic-paper-writing`, `citation`, `grill`, `skill-installer`, `writing-genres`) |
| Extended thinking | Multi-stage rewrite, parallel read-only proposers (quorum 2), aggregation, review, and repair | `app/agent/thinking/orchestrator.py::FusionOrchestrator`, `app/agent/llm/openrouter.py::get_chat_model` | OpenRouter, `ChatSession` (`TurnHost`) | Forced off (`normal`) on document, Citation, and installer turns |
| MCP & Web Search | Concurrent MCP server discovery, 15 s startup-bounded and per-call `/proc`-reaped Playwright Chromium Google search | `app/agent/mcp.py::load_mcp_tools_with_families`, `app/agent/mcp.py::_bounded_web_search`, `app/vendor/web-search-mcp/` | Node, Chromium, Google, GitHub/drop-in MCP servers | Vendored server runs as isolated stdio child, never imported by Python |
| Citation & export engine | Provider discovery, authority verification (`doi.org`, arXiv, `proceedings.neurips.cc`), task registry + `[[cite:...]]` gate, CSL-JSON library, citekey parser, Pandoc + `bime_word` export | `app/skills/citation/service.py::CitationService`, `app/skills/citation/library.py::write_atomic`, `app/skills/citation/csl_render.py::render`, `app/agent/desktop/bime_export.py::run_bime_convert`, `app/vendor/bime-word/` | Crossref, DataCite, OpenAlex, `doi.org`, arXiv, NeurIPS, Pandoc, `bime_word.py` | Desktop saves write `references.json` only; CLI saves stay task-only in memory |
| RAG subsystem | Framework-neutral folder collection, LLM folder tagging, tiktoken chunking, Ollama `bge-m3` Chroma indexing, JSON backup, search/explore/sync/prune | `app/rag/api.py::search`, `app/rag/cli/ingest.py::ingest_repo`, `app/rag/sync.py::list_diff`, `app/rag/config.py::RAGConfig` | Ollama, ChromaDB, OpenRouter (`z-ai/glm-5`), `app/store/` | Must never import `agent` or `skills` (`INV-003`) |
| CLI & eval scripts | Terminal chat loop (`--no-mcp`), RAG CLI, offline/live `@grill` evaluation runner | `app/agent/cli/chat.py`, `app/rag/cli/ingest.py`, `app/scripts/grill_eval.py` | `ChatSession`, `DesktopService` | `grill_eval.py` requires explicit `--dry-run` or `--live` |

## Ownership and boundaries

| Concern | Owner | Must not live in | Why / enforcement |
|---|---|---|---|
| Wire vocabulary & result validation | `app/desktop/protocol/v1/contract.json` + `app/agent/desktop/protocol.py` | Hand-copied schema tables in Rust or TS | Python validates outgoing events/results once; Rust checks framing (`protocol.rs`); `app/desktop/tests/protocol_types.test.ts` checks TS DTOs (`INV-011`) |
| Credential redaction & safe UI errors | `app/agent/diagnostics.py::redact_text`, `app/agent/desktop/protocol.py::bounded_error_message` | Keyword-hiding filters in React | Python redacts secrets before truncating to 4,096 B at protocol exit; UI bounds display length (`MAX_UI_ERROR_CHARS = 320`) (`INV-017`, `INV-028`) |
| Persistent domain writes & path containment | Python (`ConversationRepository`, `project.py`, `DocumentWorkspace`, `library.py`, `bime_export.py`) | Rust `backend.rs` or React `app/desktop/src/*` | Rust pickers only map UNC paths; Python resolves symlinks, checks project-root containment, and writes atomically (`INV-015`, `INV-025`) |
| Canonical archive vs model prompt budget | `ConversationRepository` (full archive) vs `app/agent/document_context.py` (trimmed copy) | Mutating `ConversationTurn` or `AgentState["messages"]` in place | `replay_history_inputs` and `compact_edit_results` allocate copies only for LLM calls (`INV-034`) |
| Tool admission & side-effect consent | `app/agent/tools/access.py`, `PolicyToolNode`, `app/agent/desktop/approvals.py` | Individual tool implementations or React components | `ChatSession.tool_access_resolution` computes `effective_tools` (removing `document_edit` on `@grill`); `PolicyToolNode` gates execution (`INV-004`, `INV-018`, `INV-033`) |
| Top-level UI state vs presentation | `app/desktop/src/App.tsx` + pure `app/desktop/src/lib/*.ts` | Direct `api.*` calls or stores inside `app/desktop/src/components/*` | Components receive props/callbacks only (`CitationPanel` receives narrow `BibliographyApi` prop); zero cross-project store (`INV-035`) |
| Framework-neutral retrieval | `app/rag/*` | `app/agent/*` or `app/skills/*` imports inside `app/rag/` | Enforced by package boundary and `app/tests/rag/test_tools_contract.py` (`INV-003`) |
| Vendored tools | `app/vendor/web-search-mcp/`, `app/vendor/bime-word/` | Python imports, Skill discovery, or wheel packaging | Spawned as child processes only; `bime-word` verified against `app/vendor/bime-word/manifest.sha256` (`INV-019`, `INV-029`) |

## Where things live

| Concept or term | Anchor | Notes |
|---|---|---|
| Central model, thinking & extension limits | `app/agent/config.py::AgentConfig` | Subclasses `app/rag/config.py::RAGConfig` |
| System prompt & per-turn writing rules | `app/agent/session.py::SYSTEM_PROMPT` | Appended with project rules in `app/agent/desktop/project_ops.py::_ProjectOps._project_system_prompt` |
| Read-only document skills (`@grill`) | `app/agent/session.py::READ_ONLY_DOCUMENT_SKILLS` | Strips `document_edit` in `ChatSession.tool_access_resolution` |
| Turn cancellation & subprocess reaping | `app/agent/ingest.py::LocalWorkScope` | Paired with `app/agent/tools/bash.py::_stop_process_group` |
| Document snapshot & replay headers | `app/agent/document_context.py::SNAPSHOT_HEADER` | Also `FROZEN_REFERENCES_HEADER`, `HISTORY_SNAPSHOT_HEADER`, `OMITTED_SNAPSHOT_HEADER` |
| Same-turn `document_edit` compaction | `app/agent/document_context.py::compact_edit_results` | Called in `app/agent/graph.py::build_graph` (`_agent_requests`) |
| Desktop RPC dispatch table (25 methods) | `app/agent/desktop/service.py::DesktopService.dispatch` | Delegates to `_ProjectOps`, `_ConversationOps`, `_TurnOps`, `_DocumentOps`, `_BibliographyOps`, `_ExtensionOps`, `_ApprovalOps` |
| Shared busy-state queries | `app/agent/desktop/service.py::DesktopService._turn_or_approval_active` | Also `_document_work_active`, `_other_operation_active`, `_raise_if_knowledge_or_extension_active` |
| Exception-to-wire error mapping | `app/agent/desktop/errors.py::_ErrorMapping._map_exception` | Attaches incident IDs except `_SELF_EXPLANATORY_FAILURE_CODES` |
| `RESEARCH.md` metadata parser & surgical style update | `app/agent/desktop/project.py::_parse_metadata` | `update_project_metadata` splices only `citationStyle` |
| Derived project conversation scan | `app/agent/desktop/project.py::project_conversations` | Wraps `ConversationRepository.scan`, sorted oldest-first |
| Unknown new citation-key gate | `app/agent/desktop/document_ops.py::_DocumentOps._unknown_new_citation_keys` | Compares `Counter(keys_in(...))` before/after `DocumentWorkspace.candidate_text` |
| CSL-JSON bibliography merge & key generator | `app/skills/citation/library.py::merge` | `<surname><year><titleword>[a..zz]`; `write_atomic` preserves JSON indent |
| Markdown/LaTeX citekey parser | `app/skills/citation/citekeys.py::find_citations` | UTF-16 offsets matching Monaco/Pandoc |
| Bundled CSL styles & Appendix 17 preprocessing | `app/skills/citation/styles/styles.json` | `app/skills/citation/csl_render.py::prepare_render_items` |
| NTU BIME Word export & Roman front-matter split | `app/agent/desktop/bime_export.py::run_bime_convert` | `split_front_matter` rewrites `word/document.xml` then re-audits |
| Authoritative arXiv & NeurIPS proceedings lookup | `app/skills/citation/authority.py::AuthorityRegistry` | Live `export.arxiv.org` and `proceedings.neurips.cc` |
| OpenRouter bounded retry client | `app/agent/llm/openrouter.py::bounded_sdk_client` | 600 s per attempt, `<= 2` retries on 5xx/network, 8 s max backoff |
| Redacted rotating logs & `turn_trace` telemetry | `app/agent/diagnostics.py::install_diagnostic_log` | `app/agent/observability.py::TurnTimingTrace`, `measure_document_context` |
| Typed frontend RPC & picker facade | `app/desktop/src/api.ts::createApi` | Enforces `echoedIdFields` (`projectId`, `sessionId`, `turnId`) |
| Approval live-owner state machine | `app/desktop/src/lib/approvalOwner.ts::receiveApprovalEvent` | Tracks turn, `document.apply`, and out-of-turn `bibliography.add` owners |
| Editor font zoom (`10`–`28` px, default `16` px) | `app/desktop/src/editorZoom.ts::editorFontOptions` | Persisted in `localStorage["research-agent.editorFontSize"]` |
| Windows foreground folder/file picker | `app/desktop/src-tauri/src/backend.rs::WINDOWS_PICKER_SCRIPT` | Invoked by `run_windows_picker` (`pick_project`, `pick_document`) |

## External dependencies

| Dependency | Used for | Boundary anchor | Limits / failure notes |
|---|---|---|---|
| OpenRouter HTTP API | Main chat (`google/gemini-3.8-flash`), thinking roles, extension preview summary, RAG folder tagger (`z-ai/glm-5`), optional `grill_eval.py --live` | `app/agent/llm/openrouter.py::bounded_sdk_client`, `app/rag/llm/openrouter.py` | 600 s HTTP phase timeout, `<= 2` retries on 5xx/network; RAG tagger uses OpenAI SDK retries (`ASM-001`, `ASM-006`, `ASM-034`) |
| Ollama (`bge-m3`) & ChromaDB | RAG embeddings and vector storage under `<persist_dir>` | `app/rag/embedder/ollama.py`, `app/rag/store/chroma_store.py` | Required for `/init`, `/ingest`, `rag_search`; not transactional with `raw.json` (`FAIL-003`, `ASM-002`) |
| Bibliographic & authority APIs | Crossref, DataCite, optional OpenAlex, `doi.org` CSL-JSON, `export.arxiv.org`, `proceedings.neurips.cc` | `app/skills/citation/providers/net.py::fetch_with_retries`, `app/skills/citation/authority.py` | 25 s httpx timeout, 15 min search / 24 h DOI cache, 16 MiB NeurIPS index cap (`FAIL-024`, `ASM-001`, `ASM-037`) |
| Pandoc (`>=3,<4`) | Citation preview (`bibliography.render`) and `.docx`/`.md` export | `app/skills/citation/csl_render.py::find_pandoc` | Direct subprocess, `--sandbox` on readers, 60 s timeout, remote images unlinked (`INV-001`, `INV-032`) |
| Vendored `bime_word` 1.1.5 | NTU BIME Appendix 17 `.bime.docx` conversion and OOXML audit | `app/agent/desktop/bime_export.py::run_bime_convert`, `app/vendor/bime-word/scripts/bime_word.py` | 180 s timeout per subprocess; requires `python-docx`, `lxml`, Pandoc, and saved disk match (`ASM-037`) |
| Node + Playwright Chromium (`web_search`) | Per-call Google search & page extraction | `app/agent/mcp.py::_bounded_web_search`, `app/vendor/web-search-mcp/` | 15 s discovery cap, `<= 300 s` call cap, `/proc` SIGKILL reaping; no fallback engine (`FAIL-027`, `ASM-027`, `ASM-028`) |
| Windows WSL interop (`powershell.exe`, `wslpath`) | Native folder/file picker dialogs from WSLg | `app/desktop/src-tauri/src/backend.rs::run_windows_picker` | Uses Win32 `AttachThreadInput` + taskbar button; no timeout or manual path fallback (`ASM-026`) |
