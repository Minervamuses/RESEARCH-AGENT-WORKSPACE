# Research Agent Desktop GUI — Goals

## Purpose

Implement a usable Codex-like local desktop GUI for the existing research-agent-workspace with TypeScript, React, and Tauri 2. A persistent left sidebar exposes project and conversation entries; selecting an entry opens its conversation in the large primary pane. Extension management is reached through slash-command-driven conversation flows rather than a permanent top-level application area.

The application must run in the repository's supported WSL/Linux environment and reuse the current Python research-agent, RAG, citation, session, Bash approval, and extension behavior instead of creating a second application core.

The repository already contains a Tauri/React shell and protocol-v1 work, plus uncommitted Python desktop-bridge work owned by the user. Execution must preserve and reconcile that work before extending it.

## Outcomes

- A Codex-like desktop shell presents projects and conversations in a persistent left sidebar and the selected conversation in the main workspace.
- Prior conversations can be reopened from the sidebar and continued with their Python-owned history and session state; creating or switching conversations does not overwrite another conversation.
- Tauri owns the desktop window, narrow WebView capability boundary, Python child lifecycle, request correlation, and transport.
- Python remains the sole owner of agent/session policy and all persistent RAG, citation, history, plan-log, Bash approval, and extension data.
- Conversation workflows expose the existing plan, thinking, skill/task, citation, and Bash approval controls without the frontend reimplementing Python rules.
- Assistant responses appear incrementally through bounded streaming updates while Python remains the owner of the finalized answer and conversation state.
- Normal questions continue to use the existing Python-owned RAG tools inside the agent turn. Knowledge maintenance is exposed only through `/init`, `/ingest`, `/sync`, and `/prune` entered in the conversation composer; there is no standalone Knowledge area.
- Extension status, preview, exact binding approval, apply, and restart-required behavior are available through slash-command-driven conversation workflows.
- Startup, busy, degraded, crash, restart, approval-required, and graceful-shutdown states are visible and recoverable without exposing secrets or unbounded internal payloads.
- The result has verified source-checkout development and build instructions for the supported Linux runtime.

## Success Conditions

- [ ] Starting from the Conda `app` environment launches the Tauri UI and its intended Python backend; the UI exposes protocol, runtime, backend, session, optional-provider, MCP, and data-path diagnostics without revealing secret values.
- [ ] The left sidebar lists representative projects and conversations; selecting an earlier conversation restores its history and resumable state, while creating a new conversation preserves existing ones.
- [ ] A representative fake/local chat flow prevents unintended overlapping turns, streams assistant content in ordered token-sized or small text chunks, finalizes one authoritative answer safely, and reflects mode, thinking, skill, citation, and approval state returned by Python.
- [ ] A representative fake conversation proves that a normal question can use the existing Python RAG search/context tools without a frontend search, document, chunk, or context explorer and degrades honestly when the semantic backend is unavailable.
- [ ] `/init` and `/ingest` traverse the real React/Rust/Python slash-command route to injected Python handler spies, proving dispatch, arguments, busy/error handling, and bounded presentation without executing their underlying RAG construction, model, Ollama, or store-write paths. Read-only `/sync` and preview-confirmed `/prune` use a prebuilt fake/temporary store; desktop path arguments obey the Linux absolute-path safety rules, prune requires an immediately preceding matching preview plus explicit `--yes`, and isolated tests leave no generated store or scratch data behind.
- [ ] An extension-management slash-command flow demonstrates status without a model call, preview/apply semantics, exact MCP binding decisions, and restart-required state using isolated temporary roots.
- [ ] When the existing Python Bash policy requests a decision, the GUI presents the bounded information required for an informed staged approval or denial; frontend and Tauri cannot bypass that policy or obtain an unrestricted shell capability.
- [ ] Required focused Python, TypeScript, and Rust checks pass as phases are built; one appropriate final broader regression/build pass succeeds near completion.
- [ ] Keyboard navigation, focus, dialogs, error recovery, untrusted text/links, and the default/minimum/200%-zoom layouts have observed acceptance evidence.
- [ ] Normal shutdown reports the recent-turn flush outcome; child crash and forced termination are not represented as successful persistence.
- [ ] The pre-existing dirty worktree and user-owned desktop-bridge work are preserved, and no plan command or historical claim is misreported as implementation evidence.

## In Scope

- `app/agent/desktop/` and the smallest directly required seams in existing agent, RAG, citation, session, Bash approval, and extension code.
- `app/desktop/` Tauri/Rust, TypeScript/React, CSS, protocol contracts, tests, and minimal source-run documentation.
- Project and conversation navigation, persistence, selection, restoration, and continuation required by the Codex-like sidebar workflow.
- Ordered response-stream events and incremental rendering required to display an in-progress assistant answer without creating a second frontend-owned transcript.
- Conversation-centered slash-command presentation for knowledge maintenance and extension management, plus the existing Bash approval workflow.
- Focused tests beside affected subsystems and isolated fake/temp acceptance fixtures.
- Backward-compatible protocol-v1 result/event additions and backward-compatible application seams directly required by the GUI.
- Directly required dependency changes made through the repository's existing package managers and recorded in their matching manifests and lockfiles.
- Internal Rust child-supervisor concurrency required to keep one Python process responsive.

## Non-goals

- Modifying `AGENTS.md`.
- Windows-native or macOS support, installers, AppImage/deb publishing, signing, updater, CI matrices, deployment, or release automation.
- Multiple users, remote access, cloud sync, telemetry, high availability, multiple windows, or simultaneous background execution in several conversations.
- Attachment/multimodal ingestion or multiple ingest roots.
- A standalone Knowledge page/dashboard, manual semantic-search form, document/chunk/context browser, knowledge-management buttons, or command-specific progress dashboard.
- User-initiated cancellation of an in-progress model/tool turn in this version.
- New database, service, queue, cache, generic RPC/framework/plugin layer, or a second writer for existing persistent formats.
- GUI credential editing, unrestricted filesystem access, bypassing or replacing the existing Bash approval policy, extension hot reload, or frontend access to unbounded raw tool/provider payloads.
- Actual `/init` or `/ingest` RAG construction during this plan, any paid-model verification outside Extended Thinking, a fourth live Extended Thinking GUI trial, real user-store mutation, broad performance work, or unrelated cleanup.

## Preserved Invariants

- Linux is the supported runtime. Conda environment `app` supplies the runtime/toolchain context; Poetry resolves Python packages; npm and Cargo manage the existing TypeScript and Rust dependency graphs.
- A dependency directly required by the GUI may be added only through the matching existing manager: Conda for Conda-managed runtime requirements, Poetry for Python, npm for TypeScript, and Cargo for Rust. Do not use direct `pip`/`pipx`, global installs, a project `.venv`, or an alternate package manager.
- React presents state and gathers intent; Rust supervises transport and process lifetime; Python enforces domain policy and owns persistent writes.
- ChatSession remains the stateful application facade. React sends composer text unchanged; a bounded Python desktop adapter reuses the existing typed slash-command parser/handlers before a normal agent turn. The GUI does not wrap the CLI loop, simulate input(), parse human-readable status text, or infer slash-command side effects.
- Frontend disabled states are usability aids, not authorization. Python/Rust boundaries recheck busy, path, destructive-action, Bash approval, and extension decisions.
- The GUI may display only the bounded command and policy context needed for an informed Bash decision. It must not expose secrets, raw provider data, unbounded stderr, tracebacks, or unrelated raw tool arguments/results.
- Untrusted assistant, tool, document, and link content is rendered without raw HTML injection and cannot silently acquire desktop capabilities.
- Existing raw.json, folder_meta.json, Chroma, history, plan logs, citation bundles, and extension registries keep their current authoritative writers and formats.
- Existing user changes are never reset, overwritten wholesale, or claimed as work performed by the executing agent.
- Verification uses fake providers and isolated temporary stores/roots by default. Paid-model verification is permitted only for Extended Thinking and is limited to at most three live GUI trials across the whole plan. A trial begins when the executor starts a backend/session specifically for that live Extended Thinking check or, when one is already ready, prepares to dispatch its one `session.turn`; reserve, increment, and record the shared counter before either action. If startup prevents dispatch, record `dispatch not reached / startup failure`; success, HTTP 429, timeout, provider error, crash, or absence of a terminal result likewise consumes the trial, and phase changes or repairs never reset it. Do not start another trial until the previous turn has reached a terminal state or its backend has been fully stopped; stop early when existing live evidence is sufficient, and never begin a fourth trial. This bounds end-to-end GUI trials, not the number of internal model invocations, HTTP retries, or provider cost within one dispatched turn. Before the first trial, give one user notice and record the notice, exact operation, paid model set, and temporary-data boundary in build-log.md. Normal-chat or extension-preview live checks may run only after the resolved model is confirmed free and unable to fall back to a paid model; otherwise use a fake. The executing agent must never read, display, edit, copy, or otherwise retrieve credential values or mutate real user stores/roots.

## Known Unknowns and User Decisions

None currently identified.

## Source Inputs

- User decisions through 2026-08-28, including the Codex-like sidebar and conversation layout, resumable conversations, streaming assistant responses, no standalone Knowledge UI, chat-owned RAG use, `/init`/`/ingest`/`/sync`/`/prune` in the conversation composer, exclusion of actual `/init`/`/ingest` construction tests, slash-command extension management, preservation of the existing Bash approval workflow, Linux-only source delivery, managed dependency changes, uninterrupted long-running execution, and at most three one-time-noticed live Extended Thinking GUI trials with every outcome counted and recorded even when startup prevents dispatch.
- `AGENTS.md` at repository root.
- Live `app/env/env-app.yml`, `app/pyproject.toml`, `app/desktop/package.json`, `app/desktop/src-tauri/Cargo.toml`, lockfiles, source, and tests.
- Live Git status, including the user's existing `app/agent/desktop/` and `app/tests/test_desktop*` work.
