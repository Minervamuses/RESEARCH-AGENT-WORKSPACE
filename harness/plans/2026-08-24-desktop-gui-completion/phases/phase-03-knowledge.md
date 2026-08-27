# Phase 03 — Knowledge Slash Commands

## Objective

Keep knowledge use inside the conversation. Normal questions continue through the existing Python agent and may use its current RAG tools; `/init`, `/ingest`, `/sync`, and `/prune` run as Python-owned local slash commands entered in the same composer. Deliver these flows without a standalone Knowledge page, frontend semantic-search state, document/chunk/context explorer, management buttons, or command-specific progress system.

## Sources

- `../GOALS.md`, `../PLANS.md`, `../PROMPTS.md`, `../build-log.md`, and completed Phase 01/02 evidence
- Repository-root `AGENTS.md`
- Live `app/agent/cli/slash_commands.py`, `app/agent/cli/chat.py`, `app/agent/ingest.py`, `app/rag/`, `app/agent/desktop/`, conversation UI/protocol surfaces, and focused tests

## Dependencies and Entry Conditions

- Phases 01 and 02 are `Complete` in `../build-log.md`.
- The Phase 02 Python-owned composer/slash-command seam is verified across the React/Rust/Python boundary.
- Every mutation check uses an isolated temporary workspace and store; no user store or source tree is an ingest/prune target.
- Phase 04 remains independently eligible after Phase 02 if this phase is blocked.

## In Scope

- Preserve and characterize normal agent-owned RAG use: a normal question may cause the Python agent to call existing RAG search/context tools, and unavailable semantic search is reported through the normal conversation instead of a dedicated explorer.
- Enable exactly `/init`, `/ingest`, `/sync`, and `/prune` through the shared Phase 02 composer route. Python parses, allowlists, validates, executes, and returns a bounded local-command result before any model call.
- Keep `/sync` a read-only comparison: it reports disk-only and store-only paths but writes neither source files nor the RAG store.
- For desktop `/ingest`, `/sync`, and `/prune`, require an explicit Linux absolute path and reject relative paths, `~`, Windows syntax, symlinks, dangerous filesystem roots, application-data overlap, missing paths, and unsupported target types in Python. `/init` keeps its existing workspace-root meaning and accepts no alternate root from React.
- Serialize actual knowledge writes: while `/init`, `/ingest`, or confirmed `/prune` is active, Python rejects another conflicting turn or write. The conversation may use its existing busy/pending presentation; no knowledge-specific progress dashboard or ingest progress callback is added.
- Make prune a two-command conversation flow. `/prune <absolute-directory>` returns the bounded candidate list and stores that exact preview privately for the current backend session. `/prune <same-directory> --yes` is the explicit confirmation, recomputes the orphan set, and deletes only if it still exactly matches the most recent unused preview. No preview token is shown or accepted.
- Report command validation and execution failures honestly. If a write may have partly completed, do not present success; report the bounded failure and current observable outcome, then require the user to rerun the relevant command. Do not build a new recovery engine.
- Focused Python/desktop/conversation tests using fake embeddings/search and temporary data, followed by verified cleanup of every manually created scratch path.

## Non-goals

- A Knowledge navigation item, page, dashboard, overview, document list, manual semantic-search form, search-result view, chunk/context detail, file picker, ingest/sync/prune button, destructive modal, or command-specific progress UI.
- React/Rust command parsing, RAG policy, direct Chroma/JSON/source-file access, broad filesystem capability, or persistence ownership.
- Changing terminal CLI syntax or behavior, including its existing relative-path/default handling. The stricter path and prior-preview rules apply only to the desktop conversation route unless the user separately authorizes a public CLI change.
- New RAG tools, embedding models, document formats, storage/schema changes, multiple roots, attachments, drag/drop, cancellation, a generic command framework, or broad RAG refactoring.
- Ollama installation, model download, unbounded or repeated live/paid-provider use, real-store mutation, generated persistent fixtures, or bulky test data.
- Removing user-owned desktop Knowledge protocol/service WIP merely because this plan does not expose it in the frontend. Leave unused work intact unless a directly required command path must adapt it.

## Expected Components Affected

- Existing `app/agent/cli/slash_commands.py` parser/registry/handlers and `app/agent/ingest.py` domain functions, adapted only through the smallest reusable or desktop-specific seam needed to preserve terminal CLI behavior.
- Existing `app/agent/desktop/` service/protocol adapter and focused desktop/slash/RAG tests.
- Existing conversation composer/result presentation and its focused TypeScript test; no Knowledge page or standalone frontend state module.
- Rust protocol forwarding only if the smallest backward-compatible command-result distinction cannot use the Phase 02 contract unchanged.

These are expected surfaces, not a pre-approved exact diff. Record the live write set before implementation and preserve overlapping user WIP.

## Authorization and Stop Conditions

- Routine local implementation, backward-compatible bounded result additions, focused fake/temp tests, and scoped local checkpoint commits are covered after the launch prompt activates `../PLANS.md`.
- Stop the affected branch for fresh authority if the command route requires a public terminal CLI behavior change, protocol version/envelope change, persistent RAG/history format change, new dependency, broad filesystem capability, or real user-data mutation.
- If the current RAG layer cannot provide a safe operation without one of those changes, leave only that command explicitly unavailable and record the evidence. Do not replace the existing writer or invent a parallel store.
- A required failure keeps Phase 03 `In progress` or `Blocked`; it does not block independently eligible Phase 04 work.

## Implementation and Verification Plan

### 1. Preflight and Red — characterize the current commands

- Re-read the existing CLI parser, registry, handlers, `agent.ingest` functions, RAG tools, desktop service, Phase 02 dispatcher, and focused tests. Record the current difference between the CLI chat loop, which intercepts slash commands, and the desktop `session.turn` path.
- Confirm with existing tests/code that `/init` indexes the workspace, `/ingest` upserts one file/folder, `/sync` only compares disk/store membership, and `/prune` previews unless `--yes` is supplied. Preserve these domain meanings.
- Add the smallest failing cases proving:
  - normal text follows the agent path, and a scripted fake agent can call the existing RAG search/context tool without any frontend Knowledge API;
  - each of the four exact desktop commands bypasses the model and returns a bounded inert conversation result;
  - aliases or other CLI commands are not accidentally enabled by the Phase 03 allowlist;
  - desktop path arguments reject relative/tilde/Windows/symlink/dangerous-root/app-data-overlap/missing/wrong-type inputs before mutation;
  - `/sync` changes neither the temp source tree nor store;
  - a prune preview alone deletes nothing; `--yes` without a matching prior preview, after backend restart, after preview reuse, for another root, or after the orphan set changes deletes nothing and asks for a new preview;
  - a matching preview plus `--yes` deletes only the recomputed matching orphan set;
  - a conflicting second turn/write is rejected and a failed command is never labeled success.
- Reuse existing temp/fake RAG tests and fixtures where they already distinguish the behavior. Do not introduce a new harness or persistent generated fixture.

### 2. Green — route the exact knowledge commands through Python

- Extend the Phase 02 desktop allowlist with only `init`, `ingest`, `sync`, and `prune`. Reuse `parse_slash_command` and existing typed result/handler behavior; do not parse command names, flags, or paths in React or Rust.
- Run a recognized command before `ChatSession.turn_outcome`, so the model/provider is not called. Return a bounded typed local-command outcome for conversation presentation. Normal text remains byte-for-byte the user's agent input after the existing composer transport rules.
- Add a desktop-only validation adapter before the existing handlers where necessary. It validates the raw parsed arguments under the stricter desktop rules while leaving terminal CLI behavior unchanged.
- Keep command output bounded and rendered by the existing inert conversation-content boundary. Do not expose raw Chroma records, embeddings, tracebacks, unbounded paths, or human-readable output that React must reinterpret.

### 3. Green — enforce write and prune safety without new UI

- Use the shared Python busy owner to permit at most one active agent turn or knowledge write. `/sync` remains read-only but still participates in the single foreground conversation operation so results cannot interleave.
- Store at most one bounded prune preview per backend session: canonical root, exact orphan set, and unused/used state. It is private Python state, not a credential or user-visible token.
- On matching `--yes`, recompute under the same validated root and apply through the existing Python writer only when the set is unchanged. Consume the preview on the first apply attempt. Unknown, missing, reused, restarted, root-mismatched, or changed previews return a bounded refusal and perform no deletion.
- Use the existing conversation busy/pending affordance while a command runs and show its final local result or bounded error. Do not add structured ingest progress events, a Knowledge reducer, a destructive dialog, or a separate recovery workflow.

### 4. Refactor — only after the slice is green

- Extract only a small desktop path validator, command-result adapter, or prune-preview record when it makes the tested boundary explicit. Keep command-specific policy near Python and preserve the existing CLI registry as the single parser/definition source.
- Do not delete or redesign unused user-owned Knowledge methods, create a general command bus, or refactor the RAG layer.

### 5. Verification

- With Conda `app` active, from `app/`, run `poetry run pytest tests/test_slash_commands.py tests/test_ingest.py tests/test_desktop_service.py tests/rag/test_component_flow.py tests/rag/test_root_identity.py tests/rag/test_tools_contract.py -q`, extending only the smallest existing modules required for desktop dispatch/path/prune cases.
- From `app/desktop/`, extend the existing conversation test for local command presentation, then run `npm test` and `./node_modules/.bin/tsc --noEmit`.
- Run focused Rust protocol tests only if this phase changes the shared result schema; otherwise record Rust as not affected rather than rerunning it ceremonially.
- Through the real desktop boundary with a fake agent/search/embedder and temporary workspace/store, ask one normal RAG-backed question, run `/init`, `/ingest <absolute-temp-path>`, `/sync <absolute-temp-directory>`, `/prune <absolute-temp-directory>`, and the matching `--yes`; also exercise the refusal cases above. Confirm command paths make no model call.
- Prefer pytest/test-runner temporary directories. For any manually created path, record its exact location, remove it after evidence is captured, verify it is absent, and confirm no generated store or bulky fixture was added to the repository.
- Inspect the existing conversation composer/result presentation with keyboard-only use and at default/minimum/200% zoom. Verify long bounded command output remains reachable without creating a separate Knowledge layout or modal.
- Use fake/temp seams by default. A bounded live/paid-provider call may be used only when materially useful under PLANS.md, after its one-time user notice and exact operation, model, temporary-data, and folder-count boundary are recorded; it does not waive the separate no-model-call acceptance requirements above. Do not install or run Ollama, download a model, touch the real store, run the full Python suite, or perform the final desktop build in this phase.

## Reliability, Security, and Recovery

- Python remains the only RAG writer and path-policy owner. React and Rust relay intent/results only and cannot browse arbitrary paths or directly open Chroma, JSON, or source files.
- The desktop-only validator rejects unsafe paths before a handler runs. Symlink checks and dangerous-root/application-data-overlap checks are performed again at the Python mutation boundary where needed; frontend disabled states are not authorization.
- There is one foreground operation, so chat/command results cannot interleave or produce competing writes. A failure that may follow partial ingest work is reported as failure with the observable state; it is never converted into success or repaired by a second writer.
- Prune preview and apply are linked by private in-memory state and an exact recheck, not by a user-visible token. Backend restart or changed files invalidates the confirmation naturally and deletes nothing.
- Slash-command output is bounded, secret-safe, and inert. No command result becomes assistant-authored content or a second persistent transcript/store.

## Acceptance

- [ ] There is no standalone Knowledge navigation item, page, search/document/chunk/context explorer, management-button surface, destructive modal, or knowledge-specific progress state.
- [ ] A normal fake question can exercise the existing Python RAG tool path and show its answer/degraded outcome through the ordinary conversation, with no frontend search or RAG ownership.
- [ ] `/init`, `/ingest`, `/sync`, and `/prune` entered in the composer are parsed and executed by Python without a model call; React/Rust neither parse them nor write RAG data.
- [ ] `/sync` has observed read-only behavior. Desktop path arguments enforce the approved Linux absolute-path/symlink/dangerous-root/application-data rules without changing terminal CLI behavior.
- [ ] At most one foreground turn/command runs. Failures are not shown as success, and no new progress or recovery subsystem is required.
- [ ] `/prune <root>` previews and deletes nothing; only a following matching `/prune <root> --yes` may delete. Missing, reused, restarted, root-mismatched, or changed previews delete nothing and require a new preview, with no token exposed to the user.
- [ ] Focused Python/TypeScript and affected-contract checks pass against fake/temp data; the user's real store remains untouched and every manual scratch/store path is verified removed.
- [ ] No standalone Knowledge UI, second command parser, generic framework, dependency, persistent-format/schema, public CLI, `AGENTS.md`, remote-Git, branch/worktree, deployment, or release change occurred.

## Evidence to Record

- Exact commands, runtime identity, concise observed results, model-call counters, temporary-path boundaries/cleanup, and scoped local commit hashes in `../build-log.md`.
- A material command/path/prune discovery in `../context/phase-03-knowledge-context.md` only when omission could change later implementation or verification.
- Actual review findings in `../code_review/phase-03-knowledge-review.md` only if a real review occurs.

## Handoff

Mark Phase 03 `Complete` only after every required acceptance item maps to observed evidence. Reload the durable sources and continue the autonomous selector. Normally Phase 04 follows numeric order; if Phase 03 is `Blocked`, Phase 04 remains eligible from completed Phase 02 and proceeds without a user checkpoint.
