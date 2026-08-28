# Phase 02 — Chat and Conversations

## Objective

Build the Codex-like conversation workspace on the verified Phase 01 bridge. Python owns a small persistent catalog in which each project is an ordered list of existing session IDs; a project is not a filesystem root. The existing session ID is the sole conversation identity across the catalog, history, plan logs, protocol, and UI. A user can create, select, restore, and continue a conversation without changing another one. The selected conversation occupies the main pane and permits at most one active turn across the application. When the current model path can safely identify final-answer text tokens, the UI receives those tokens incrementally before completion; otherwise it uses a bounded post-finalization fallback. In both branches, the Python-finalized result is the sole authoritative answer and persistence owner. The Python desktop boundary also establishes one narrow composer-input dispatch seam that distinguishes normal chat from an allowlisted local slash command before any model call; later phases add their exact command families without a second frontend parser.

## Sources

- Repository-root `AGENTS.md`
- `../GOALS.md`, `../PLANS.md`, `../build-log.md`, and observed Phase 01 evidence
- Live `app/agent/session.py`, `app/agent/turns/`, `app/agent/history_rag/`, `app/agent/cli/slash_commands.py`, `app/agent/desktop/`, `app/desktop/`, protocol fixtures, manifests, and focused tests

Repository-root `AGENTS.md`, `GOALS.md`, and `PLANS.md` are authoritative. Treat the live Phase 01 contract and observed repository behavior as stronger evidence than this phase's file-level expectations.

## Dependencies and Entry Conditions

- Phase 01 is `Complete` in `build-log.md`, with passing evidence for the Python/Rust/React request, event, result, lifecycle, crash, restart, and shutdown path.
- The `PLANS.md` authorization envelope has been activated, and the WSL/Linux Conda `app` runtime and dirty-tree ownership have been revalidated.
- Before the first write, record the exact Phase 02 write set and all overlap with the user's existing desktop/session work.
- Recheck the Phase 01 protocol before choosing method or event names. Preserve protocol version 1 and every existing method/envelope; Phase 02 may add only backward-compatible, bounded project, conversation, transcript, and answer-chunk fields or methods.

## In Scope

- A bounded Python-owned project catalog whose durable meaning is only `project ID -> project name + ordered session ID list`. It does not own transcripts, prompts, plan logs, filesystem roots, or provider state.
- Reusing the existing session ID as the only conversation ID. The current version-4 UUID value is represented as 32 lowercase hexadecimal characters without hyphens; no second conversation identifier is introduced.
- Listing conversation summaries, creating a transient empty conversation, selecting one conversation, restoring its transcript and prompt-visible context, and continuing its turn counter without duplicate persistence. A new session joins the selected project's ordered ID list only after its first successful finalized-and-recorded turn; abandoning an empty conversation creates no restart requirement.
- Keeping one materialized current `ChatSession` and at most one active turn. Conversation creation, selection, session-control mutation, and shutdown must fail safely while a turn or required flush is active.
- Atomically persisting project membership and order through one Python writer while leaving the existing history and plan-log formats and writers unchanged.
- Paginated or otherwise explicitly bounded transcript retrieval; conversation lists and transcript results must not grow to the protocol line limit without an application-level bound.
- Preferred ordered final-answer token events when the model/graph path exposes safely attributable text tokens, plus a bounded post-finalization chunk or final-only fallback when it does not. One full Python-finalized result remains authoritative in every branch.
- The persistent sidebar, selected-conversation workspace, transcript, composer, activity, controls, provisional/final answer states, error/retry states, and safe assistant-content rendering.
- Plan mode, thinking mode, skill/task selection, and citation-skill state returned and enforced by Python for the selected conversation.
- A narrow Python-owned composer-input dispatcher that reuses `parse_slash_command`, the current registry/typed result behavior, and an explicit desktop allowlist. Normal text continues to the agent; a handled slash command returns a bounded conversation-local result without a model call; malformed, unknown, or disallowed commands fail safely without reaching the model. Phase 02 establishes the seam, while Phases 03 and 04 own their command entries and behavior.
- Focused Python, TypeScript, and directly affected Rust tests plus an isolated fake/temp user journey.

## Non-goals

- Concurrent or background turns in several conversations, user-initiated cancellation, attachments, multimodal input, conversation deletion/renaming/moving, or reordering project membership in the UI.
- Giving projects filesystem semantics, arbitrary project discovery, an unrestricted folder picker, or allowing React to submit or explore paths. Path selection is unrelated to the project/session catalog in this phase.
- Streaming fusion candidates, reviewer/rewriter output, chain-of-thought or other raw reasoning, tool arguments/results, tracebacks, or provider payloads. Only text attributable to the final-answer model invocation may enter the provisional answer stream.
- Knowledge command behavior, extension management, Bash approval UI, or a second/generic slash-command parser. Phase 03 and Phase 04 add their exact allowlisted commands on top of this shared Python seam; React never parses them.
- A transcript database, second transcript store, generic project registry, cache, service, or second writer for history and plan logs. The exact bounded project/session-ID catalog described above is the only new persistent index authorized by this phase.
- Changing the existing history or plan-log formats, duplicating transcript content in the catalog, or making React/Rust a persistence owner.
- A global frontend state framework, generic router/RPC layer, broad session refactor, full Python regression suite, final Tauri build, any paid-model verification in this phase, or real-store mutation. Live Extended Thinking trials, if any, are reserved for Phase 05's shared plan-wide budget.
- A blanket dependency prohibition. A directly required dependency follows the manager, manifest, lockfile, and evidence rules already authorized in `PLANS.md`; convenience-only dependencies remain out of scope.

## Expected Components Affected

- Existing Python desktop protocol/service adapters, the existing CLI slash-command parser/typed result, one small Python-owned project/session catalog surface, and the smallest backward-compatible `ChatSession`, turn-journal, history, or plan-log read seams required for list/restore/continue behavior.
- `app/desktop/protocol/v1/contract.json`, fixtures, and the corresponding Python, TypeScript, and Rust protocol representations when the Phase 01 implementation still keeps those surfaces separate.
- Existing React application/state/content-rendering/style files and focused `app/desktop/tests/` files; `app/desktop/package.json` only if its test script must include the added test modules.
- Existing focused Python desktop/history/session tests. Prefer extending them; add a small dedicated test module only when it gives a clearer causal boundary.

These are expected surfaces, not a pre-approved exact diff. Any additional production file must satisfy the causal-scope rule and be recorded before it is edited.

## Authorization and Stop Conditions

- Routine local implementation, focused tests, the exact bounded Python-owned project/session-ID catalog, directly required managed dependencies, scoped local commits, and durable evidence updates are covered by `PLANS.md` once execution is launched. The catalog is a new membership index; it does not alter the existing history or plan-log formats.
- Stop the affected branch and obtain fresh authority if conversation restoration requires changing an existing history/plan-log format or schema, expanding the catalog beyond project name plus ordered opaque session IDs, adding a second transcript store, accepting an arbitrary filesystem root, changing the protocol version/envelope, or weakening Python ownership.
- If existing history or plan-log records cannot be reconstructed unambiguously within their current formats, fail closed with an explicit unavailable/read-only state and record the limitation. Do not guess turn pairs, expose tool blocks, or silently create a replacement history.
- Real-token streaming is a preferred capability, not permission to expose unsafe or unattributable model output. If preflight proves that the current provider/graph path cannot isolate final-answer text tokens, record the evidence and use the bounded post-finalization fallback; do not block the rest of Phase 02 or force a broad graph rewrite.
- Stop the affected branch if the slash seam would require wrapping the interactive CLI loop, changing public terminal CLI behavior, creating a second parser/registry, persisting command-result transcripts in a new format, or letting React/Rust infer command authorization. A small backward-compatible desktop-only result distinction is permitted; a protocol version/envelope change is not.
- A required failed check keeps Phase 02 `In progress` or `Blocked`. Neither Phase 03 nor Phase 04 may start until every required Phase 02 acceptance item has evidence.
- Phase 02 uses fake models for Extended Thinking success and provider-error presentation. An optional normal-thinking metadata check may use a live model only after the resolved main model is confirmed free with no paid fallback; otherwise keep it fake.

## Implementation and Verification Plan

### 1. Preflight and Red — characterize the missing boundaries

- Reload the completed Phase 01 evidence and inspect the live Python, TypeScript, and Rust contract before editing. Confirm whether the current implementation still has one disposable session, no project/session catalog or conversation list/load operation, no ordered answer-text event, and a final-only turn result.
- Characterize the current history and plan-log records using isolated temporary roots. Confirm that their existing session ID is sufficient to identify one conversation, order and pair user/assistant turns, derive a bounded title/updated time, and restore the latest prompt window without invoking semantic search or Ollama. Do not invent a parallel conversation ID.
- Characterize the current graph/provider streaming path before choosing the event source. For an OpenRouter-backed model, verify that the client actually requests streaming and that LangGraph's message stream, or an equally narrow existing callback, delivers text before graph completion; slicing a completed answer does not satisfy this real-token branch. Verify whether final-answer model text can be isolated through message metadata, node identity, model tags, or an equally narrow existing signal. Specifically distinguish final-answer text from planner/reviewer/rewriter calls, reasoning, tool-call chunks, and fusion candidates. Use a fake streaming model/provider by default; that evidence is sufficient for completion. If a live-client or metadata question remains and one bounded normal-thinking call would materially improve verification, it may run only after the resolved main model is confirmed free with no paid fallback and the operation is recorded. Do not use Extended Thinking or any paid model for this Phase 02 check.
- Add the smallest failing tests for:
  - catalog project P1 containing ordered sessions A and B and project P2 containing C, with membership and order unchanged after a normal process restart;
  - the same opaque session ID joining catalog membership, history metadata, plan-log identity, protocol DTOs, and restore selection without translation to another ID;
  - a newly created empty session remaining transient, its first successful finalized-and-recorded turn adding it once to the selected project, and an abandoned empty session leaving no durable catalog entry;
  - atomic catalog replacement, duplicate membership rejection, malformed catalog handling, unknown project/session identifiers, and catalog-write failure followed by registration retry without transcript loss, a false membership update, or rerunning the turn;
  - create, select A, select B, return to A, and continue A without cross-contamination or duplicate history writes;
  - normal shutdown/restart restoration from existing history and a canonical plan log, including malformed or incomplete persisted records;
  - create/select rejection during an active turn and current-conversation retention when a required flush fails;
  - bounded list/transcript pagination;
  - a supported real-token path that emits ordered final-answer text before final completion while dropping other nodes/models, reasoning, tool-call chunks, and provider metadata;
  - final output equal to the provisional stream, final output replacing a differing provisional stream once, provider/finalizer failure discarding provisional text, and the documented post-finalization fallback when safe token attribution is unavailable;
  - duplicate, missing, out-of-order, stale, oversized, cross-session, and mismatched answer events;
  - recoverable provider failure before or during provisional output, duplicate send, and retry without losing the user's draft;
  - a selected Extended Thinking mode completing one scripted fake end-to-end turn through the GUI with bounded stage activity and one authoritative final answer, plus scripted HTTP 429/provider-error outcomes that finalize busy state, preserve an appropriate draft/retry path, and expose no raw provider payload;
  - raw HTML, script/data/file schemes, malformed Markdown, and raw tool/provider data remaining inert or absent.
- Add the smallest dispatcher cases proving that normal text reaches the fake agent exactly once, an allowlisted harmless local command returns a typed bounded result without a model call, and malformed/unknown/disallowed slash input reaches neither a handler nor the model. Use an existing harmless command or an injected test handler; do not enable Phase 03/04 production commands early merely to test the seam.
- Use current history and plan-log formats unchanged. The only new durable fixture is the exact minimal project-name/ordered-session-ID catalog that the production behavior requires.

### 2. Green — make Python own projects, conversations, and restoration

- Keep `ChatSession` as the stateful application facade and `DesktopService` as the desktop coordinator. Materialize one selected `ChatSession` at a time; do not keep several agents executing or build a generic session manager.
- Add one small Python-owned catalog with the bounded semantic model `project ID -> {name, ordered session IDs}`. Bootstrap only the minimum default project needed by the existing local application when no catalog exists. Write the catalog by atomic replacement from Python, validate IDs and bounds on read, and reject a session ID duplicated within or across projects. Never store transcript text, prompt state, paths, or provider payloads in it. A malformed catalog produces an explicit degraded/unavailable project-list state and is not silently overwritten.
- Treat the existing session ID as the canonical conversation ID everywhere. The present constructor generates a random version-4 UUID and renders its 128-bit value as a 32-character lowercase hexadecimal string without hyphens; restoration injects that same opaque value instead of generating or mapping a replacement.
- Return bounded array-shaped project and conversation DTOs from the catalog. Derive each referenced conversation's user-visible summary from existing Python-owned history metadata and canonical plan-log headers. Preserve the catalog's membership order; use deterministic ordering only for fields or views not governed by that list. Missing or malformed referenced records become explicit degraded entries rather than being reassigned to another project.
- Create an empty `ChatSession` in memory with its session ID and selected project ID, but do not add it to the durable catalog yet. After its first turn has been finalized and successfully recorded by the existing owners, append its session ID to the chosen project's list exactly once through the atomic catalog writer. If that append fails, keep the current session and recorded answer, return a bounded retryable catalog-registration state, and retry only registration rather than rerunning or re-persisting the turn. Closing or restarting before a successful append may discard an empty session or leave that failed-registration session unlisted; no fabricated membership or automatic cross-store guessing is allowed.
- Extend `ChatSession` or its journal through backward-compatible construction/restoration seams so Python can reuse a selected session ID, resume the next turn number, load only the configured prompt window, and mark already-persisted restored turns so later eviction/shutdown does not write them twice.
- Before replacing the current materialized session, flush its recent turns. If flush fails, retain the current conversation and return a bounded retryable error. Preserve any transient Python-owned control snapshot in memory while the child remains alive; after a process restart, restore only state represented by current history/plan-log formats and return explicit safe defaults for state those formats do not persist.
- Read canonical plan logs through a bounded Python-owned reader that returns user/assistant transcript content only. Never send their tool arguments/results to React. Treat malformed, ambiguous, oversized, missing, or partially written records as an explicit degraded item instead of guessing.
- Add minimal allowlisted protocol operations for project/conversation listing, creation, selection, catalog-registration retry, and bounded transcript pages. React receives DTOs and sends opaque project/session IDs; Python validates that the requested session belongs to the requested project before materializing it. Keep existing `session.create`, `session.status`, and `session.turn` behavior compatible for Phase 01 callers, with status and control snapshots always referring to the selected conversation.
- At the Python desktop boundary, inspect composer text with the existing slash parser before invoking `ChatSession.turn_outcome`. Dispatch only commands explicitly allowed by the desktop service, use existing typed handler results through the smallest adapter, and return a bounded command/error result that the conversation can present without treating it as an assistant/model answer. Send normal text unchanged to the agent. Do not call CLI `input()`/printing code, expose `/clear` or `/quit`, or add Phase 03/04 command-specific UI here.

### 3. Green — prefer real final-answer token streaming and reconcile once

- When preflight proves that the current graph/provider path can identify the final-answer invocation, enable the provider's real streaming request and consume LangGraph message events alongside the existing stage/update events, or use the smallest equally narrow live-code seam. Emit only non-empty text chunks from the final-answer invocation, filtered by the narrowest verified node/model metadata or tag. Never emit planner, reviewer, rewriter, fusion, tool-call, reasoning, or provider-metadata chunks.
- Treat these model tokens as provisional presentation data because finalization and persistence have not completed. Emit an allowlisted answer-text event correlated by request ID, session ID, turn ID, protocol sequence, and a contiguous chunk index. Bound every event and the total retained provisional text, preserve Unicode text order, and render it through the same inert content boundary as restored answers.
- Keep the existing Python finalizer, citation/policy checks, and persistence path authoritative. If the successful final result equals the assembled provisional text, mark it final without duplicating content. If finalization legitimately changes the text, replace the provisional assembly with the full final result once and expose a bounded reconciliation state. If the turn fails before an authoritative result, discard provisional text from the transcript and leave retry/error behavior to the existing Python result.
- If preflight cannot safely and uniquely attribute real tokens, keep the same event/result contract but emit bounded chunks only after finalization, or return the final result without chunks if that is the smallest compatible fallback. Record which branch was selected and why; do not expose mixed-model output merely to simulate real-time streaming.
- The frontend reducer rejects stale, duplicate, non-contiguous, oversized, cross-session, or mismatched events. The full successful Python result always wins and is displayed exactly once.
- Keep one global active-turn guard in Python/Rust. React disabled states mirror that snapshot for usability but cannot authorize a second turn or a conversation switch.

### 4. Green — build the conversation workspace

- Replace the Phase 01 shell placeholder with the persistent left sidebar and one large selected-conversation pane. Project headings and conversation buttons come from Python DTOs; show explicit loading, empty, selected, unavailable, and degraded states.
- Provide create/select actions, paginated older-turn loading, transcript, composer, send affordance, bounded stage/tool activity, provisional/final/reconciled/fallback answer states, and retryable/non-retryable errors. Preserve the draft on a recoverable send failure and return focus predictably after create/select/send/error actions.
- Send the composer's complete text unchanged across the typed boundary. Render a returned local-command message as a bounded inert conversation/system result, not as streamed assistant content, and do not parse slash syntax, paths, confirmation flags, or human-readable CLI status in React.
- Use a small reducer or equivalent local state boundary keyed by project, session, request, and turn IDs. Treat project and session IDs as opaque values, bound retained activity and streamed text, ignore stale messages after backend restart, and replace local session/control state only with Python results.
- Block duplicate sends and create/select/control actions while a turn is active. Do not imply cancellation exists; normal provider/tool failures remain in the conversation when Python can answer, while lifecycle-fatal failures use the Phase 01 fallback surface.
- Render assistant and restored transcript content with React-created elements only. Support only the needed Markdown subset, keep raw HTML inert, validate `http`/`https` links at activation time, and route external opening through the narrowest verified Tauri mechanism without giving rendered content a general shell or navigation capability.
- Display plan, thinking, skill/task, and citation-skill state from the selected Python snapshot. Send typed intents and accept only the returned state; preserve current mutual exclusion, teardown, and citation-finalization behavior. For Extended Thinking, render only bounded stage/final/error state returned by Python and never raw candidate, reviewer, reasoning, or provider content.

### 5. Refactor — only after the slice is green

- Extract a local reducer, bounded chunk helper, content parser, or conversation DTO only when at least two in-scope callers need it or it makes a tested safety boundary explicit.
- Do not create a generic repository, store, plugin, second command parser/registry, router, or Markdown framework. Repeat the focused checks after any material refactor.

### 6. Verification

- With Conda `app` active, from `app/`, add the two focused companion modules `tests/test_desktop_conversations.py` and `tests/test_desktop_answer_stream.py`, then run `poetry run pytest tests/test_desktop_protocol_contract.py tests/test_desktop_service.py tests/test_slash_commands.py tests/test_desktop_conversations.py tests/test_desktop_answer_stream.py tests/test_history_rag_store.py tests/test_session_eviction.py tests/test_plan_mode.py -q`. The conversation module owns catalog/membership/restart/restore/flush and desktop dispatch cases; the answer-stream module owns real-token attribution/reconciliation/fallback/order cases.
- From `app/desktop/`, add `tests/conversations.test.ts` and `tests/answer_stream.test.ts`, update the existing test script only as needed to include all three focused `tests/*.test.ts` modules, then run `npm test` and `./node_modules/.bin/tsc --noEmit`.
- Because the shared protocol changes, from `app/desktop/` run `cargo test --manifest-path src-tauri/Cargo.toml protocol::tests`. Run additional Rust tests only if Phase 02 changes supervisor behavior beyond forwarding the new bounded methods/events.
- Through the real Phase 01 Rust/React/Python boundaries and an isolated fake/temp backend, seed P1 with ordered sessions A and B and P2 with C; create a transient D in P1; complete D's first turn and confirm one catalog append; stream a turn in A; switch to B and send a different turn; return to A and continue it; restart normally and verify P1/P2 membership and order before reopening persisted A. Exercise both the safely attributed fake-token branch and the forced post-finalization fallback. Select Extended Thinking and exercise one scripted fake success plus one scripted HTTP 429/provider-error result through the same GUI turn route, checking bounded activity, honest error presentation, busy finalization, and draft/retry behavior without dispatching a live model. Then provoke busy, flush-failure, catalog-write failure, malformed-catalog/history, stream-reconciliation, and other recoverable-turn failures before shutdown verifies the reported flush result. If Phase 01 did not establish an exact fake-child launch command, resolve and record it during preflight rather than inventing one in this plan.
- Inspect keyboard-only create/select/send/retry use, transcript scroll/focus behavior, malicious content/link cases, and the sidebar/main-pane layout at the default viewport, the supported minimum, and 200% zoom. Record the exact viewport sizes and observed results in `build-log.md`.
- Do not run the complete Python suite, `npm run build`, the full Cargo suite, or a final Tauri build in this phase unless a focused failure requires it; Phase 05 owns the single planned broader pass.
- Record every exact command/procedure and pass/fail/skipped/unavailable result. A skipped manual or integration case is not a pass.

## Reliability, Security, and Recovery

- Normal selection/replacement must not discard the current session until its required flush succeeds. Backend crash or forced termination remains a possible loss of unflushed recent turns and must never be reported as successful persistence.
- The catalog has one Python writer and atomic replacement. It stores only bounded project names and ordered opaque session IDs; it never becomes a transcript or prompt store. A failed catalog write leaves the previous catalog intact, and malformed catalog data is reported without overwriting history or plan logs.
- An empty newly created session is intentionally ephemeral. Restart recovery begins only after the first successful finalized-and-recorded turn has registered its session ID; no placeholder entry or empty transcript is required.
- Restored history is ordered and paired by Python from existing authoritative metadata; malformed, duplicate, partial, or oversized records degrade explicitly and never cross conversations.
- The full successful final result is authoritative. Real model tokens are provisional bounded presentation updates until that result arrives; reconciliation replaces rather than appends, and no chunk stream becomes a second transcript or persistence owner.
- Project/session IDs are opaque and validated. Streaming filters admit only final-answer text and no DTO or error exposes credentials, raw reasoning, raw plan-log tool blocks, raw provider/tool payloads, tracebacks, or unrelated filesystem contents.
- Temporary history, plan-log, and fake-project roots used by tests are recorded, removed after evidence is captured, and verified absent without touching user data.

## Acceptance

- [ ] The Python catalog and sidebar represent P1 with ordered session IDs A/B and P2 with C; after a normal restart, both project memberships and their order are unchanged and no filesystem path is part of project identity.
- [ ] One opaque session ID is the sole conversation identity in catalog membership, history metadata, plan-log identity, protocol DTOs, selection, and restoration; no translated or parallel conversation ID exists.
- [ ] A newly created empty session remains in memory only. Its first successful finalized-and-recorded turn appends its session ID to the selected project exactly once; abandoning it before that turn leaves no durable entry and requires no restart restoration.
- [ ] A user can switch from A to B, return to A, and continue A with its Python-owned transcript, turn counter, and in-process control state intact; B remains unchanged.
- [ ] After a normal flush/shutdown and restart, registered conversation A reopens from unchanged history/plan-log formats with bounded ordered transcript data and sufficient prompt-visible context to continue without duplicate writes.
- [ ] Duplicate, unknown, malformed, partial, ambiguous, or oversized catalog/conversation records fail closed with a bounded degraded state; catalog-write failure does not claim membership, a registration retry adds the already-recorded session exactly once without rerunning its turn, and flush failure leaves the current conversation selected and recoverable.
- [ ] At most one turn is active across the application, and Python/Rust reject duplicate sends, conversation changes, and incompatible control mutations while it is active.
- [ ] Preflight records whether final-answer model tokens can be safely isolated. When supported, the representative fake-provider flow visibly receives those text tokens before the final result while excluding all other model/node/reasoning/tool chunks; when unsupported, the recorded bounded post-finalization or final-only fallback passes without forcing a broad graph rewrite.
- [ ] Equal provisional/final text becomes one answer; differing text is replaced once by the authoritative Python-finalized result; failed, stale, missing, duplicate, out-of-order, oversized, cross-session, or mismatched events cannot persist or display a second answer.
- [ ] Mode, thinking, skill/task, and citation state round-trip through Python for the selected conversation and preserve existing policy; a fake Extended Thinking GUI turn proves bounded success/finalization and scripted HTTP 429/provider-error presentation, and React/Rust neither infer policy nor expose raw reasoning/provider content.
- [ ] The Phase 02 Python seam sends normal text to the fake agent exactly once, returns an allowlisted local command result without a model call, rejects malformed/unknown/disallowed commands before model execution, and requires no frontend parser or second command registry. Knowledge and extension production commands remain owned by Phases 03 and 04.
- [ ] Restored and live assistant content renders the allowed Markdown/link subset without raw HTML execution, unsafe schemes, desktop-capability acquisition, or raw sensitive payloads.
- [ ] Recoverable send failure preserves the draft and supports explicit retry; keyboard, focus, scroll, default/minimum/200%-zoom layout, empty, busy, degraded, and fatal states have observed evidence.
- [ ] Required focused Python, TypeScript, Rust, fake-boundary, and manual checks pass with exact recorded evidence, and any directly required dependency used the authorized manager/manifest/lockfile path.
- [ ] Existing history/plan-log formats remain unchanged, and no second transcript store, generic/path-based project registry, arbitrary-path access, `AGENTS.md`, real-data, unmanaged-dependency, remote-Git, branch/worktree, deployment, or release change occurred.

## Evidence to Record

- Exact commands, runtime identity, concise observed results, fake/temp root cleanup, and scoped local commit hashes in `../build-log.md`.
- A material restoration, protocol, persistence, or degraded-behavior discovery in `../context/phase-02-chat-session-context.md` only when omitting it could change later implementation or verification.
- Actual review findings in `../code_review/phase-02-chat-session-review.md` only if a real review occurs.

## Handoff

Mark Phase 02 `Complete` only after every required acceptance item maps to observed evidence. Create and record the scoped verified checkpoint commits required by `PLANS.md`, reload the durable sources, and then continue automatically: Phase 03 follows numeric order, while Phase 04 becomes independently eligible from the same completed conversation foundation. If any required Phase 02 branch remains `In progress` or `Blocked`, neither dependent phase may begin.
