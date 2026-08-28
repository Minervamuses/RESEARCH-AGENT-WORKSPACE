# Phase 04 — Extensions, Bash Approval, and Trust Boundary

## Objective

Complete the Extensions user journey, present the existing Python-owned per-command Bash decision through the conversation GUI with exactly Approve and Deny actions, and close the cross-page trust, recovery, privacy, and accessibility boundaries. Python remains the policy and execution owner; React and Rust relay only bounded presentation and intent and never gain an unrestricted shell or filesystem capability.

## Sources

- GOALS.md, PLANS.md, PROMPTS.md, build-log.md, and completed Phase 01/02 evidence
- Live extension manager/registry/CLI seams, Bash tool and approval seams, desktop bridge, Tauri configuration/capabilities, React UI/styles, and focused tests

## Dependencies and Entry Conditions

- Phases 01 and 02 are Complete.
- The Phase 02 Python-owned composer/slash-command seam is verified. Phase 04 adds only the exact extension command route and does not depend on Phase 03.
- The Phase 01 Rust-owned Python-child mechanism, protocol-v1 compatibility boundary, and crash/restart path are verified and recorded. This phase preserves that mechanism whether it uses standard process facilities or Tauri's official Shell child-process API.
- Temp extension roots, fake preview/provider seams, and a fake Bash command runner can be used without credentials, arbitrary real command execution, or external writes.
- Current capability/CSP configuration and exact planned file overlap are recorded.

## In Scope

- Extension status, explicit preview, exact MCP binding decision UI, apply, restart-required state, and post-restart verification with isolated roots.
- The existing per-command Bash policy presented in the conversation with bounded command/description/timeout context, exactly Approve and Deny actions, and one Python-owned decision for the exact pending request.
- Shared error/degraded/recovery presentation and bounded diagnostic logging.
- Tauri/WebView capability review, untrusted content/link handling, secret-safe UI, extension/Bash confirmations, keyboard/focus/accessibility, and responsive layout. Phase 03 prune confirmation remains the composer-only matching `/prune <root> --yes` flow and gains no modal or button path here.
- Approval correlation, one-use resolution, timeout/deny behavior, busy-state enforcement, and crash/restart cleanup at the Python, protocol/service, Rust transport, and React presentation layers.

## Non-goals

- Extension discovery marketplace, generic plugin framework, hot reload, any paid-model verification in this phase, real user extension roots, or background auto-apply. Live Extended Thinking trials, if any, remain Phase 05 work under the shared plan-wide budget.
- Replacing the existing Bash policy, adding conversation-wide/session-wide/remembered approval, editing the pending command, accepting arbitrary user-submitted shell commands, or executing commands in React or Rust.
- Replacing or removing the Phase 01 verified Rust-owned Python-child mechanism merely because it uses Tauri's official Shell child-process API, or granting React/WebView a generic Tauri shell/filesystem permission or API.
- Changing Phase 03 knowledge commands or adding a prune modal, broad WCAG certification, design-system rewrite, telemetry, new logging service, or convenience-only dependency changes.

## Implementation Plan

### 1. Adapt the existing extension lifecycle

- Reuse the current manager/registry behavior and Phase 02 Python slash-command seam instead of parsing CLI text or command syntax in React/Rust. Preserve terminal CLI behavior and do not call CLI `input()` or printing code from the desktop route.
- Enable the existing `/extension-management` command family through the desktop allowlist: status returns the read-only state, while preview/apply remain an explicit conversation-owned flow whose typed actions refer to one opaque Python-owned preview. React does not infer command effects from rendered text.
- Make status read-only and free of model/provider calls.
- Require an explicit user action for preview and clearly label that the operation may contact a provider. Fake preview evidence is required. An optional live preview may run only after the resolved main model is confirmed free with no paid fallback and under the shared temporary-root, credential-confidentiality, and evidence rules; otherwise keep it fake.
- Present bounded, secret-safe details sufficient to identify each exact requested MCP command binding and collect a separate decision for each item. Apply only the same approved preview/revision through Python.
- Report partial failures and restart-required state. Verify the loaded revision only after the controlled Phase 01 restart flow.

### 2. Bridge the existing Bash decision into the desktop conversation

- Characterize the current Bash policy, terminal TTY approval behavior, and live protocol-v1 approval event/resolve seams before editing. Preserve public terminal CLI behavior and use only backward-compatible protocol-v1 additions when the completed Phase 01 contract still needs them.
- Add the smallest desktop-only Python decision seam needed for the existing Bash tool to stage one exact command request, emit bounded approval context correlated to the active request/turn, and await a boolean decision without transferring policy or execution ownership to React or Rust.
- Present exactly Approve and Deny. Approval executes the staged command once through the existing Python Bash execution path; denial returns the existing denied tool outcome without starting a subprocess. Do not add command editing, an always-approve option, or remembered approval.
- Reject unknown, expired, reused, stale, cross-request, cross-turn, or mismatched decisions. Deny without execution on timeout, UI dismissal, conversation replacement, backend crash/restart, or shutdown, and clear pending state deterministically.
- If Python cannot provide bounded secret-safe context sufficient for an informed decision, deny the request without execution rather than exposing a secret or approving an undisclosed command.

### 3. Keep tests isolated and deterministic

- Route extension status/preview/apply verification to temporary config, registry, skill, and MCP roots.
- Use a fake preview/provider response for required evidence and never inspect, disclose, edit, or copy credential values. One optional live preview may be used only when materially useful and the resolved main model is confirmed free with no paid fallback; it is not an Extended Thinking live GUI trial. Status and apply remain no-call operations, and this phase makes no paid-model call.
- Use a fake/stubbed Bash runner and execution spy for approval verification; never execute an arbitrary real shell command as test evidence.
- Confirm that status alone produces no provider request and that stale/mismatched preview/apply is rejected.

### 4. Close trust boundaries

- Review Tauri commands, capabilities, CSP, navigation, external-link handling, child command construction, and payload bounds against actual live configuration.
- Remove or narrow only demonstrated excess WebView capability. Preserve the Phase 01 Rust-owned fixed Python-child primitive and its verified start/restart/shutdown behavior; React never receives a generic shell or filesystem API.
- Keep approval policy and subprocess execution in Python. Rust forwards only the bounded correlated event/decision, and React displays context and sends only the selected boolean intent.
- Preserve existing protocol-v1 method/event compatibility. Do not remove or rename an approval surface established by Phase 01; reject invalid decisions through the bounded error path.
- Keep secrets as presence-only indicators and sanitize provider/MCP/tool/extension/error text as untrusted display content.
- Recheck the conversation-owned extension and Bash confirmation flows, busy-state enforcement, crash/restart cleanup, and error classification without depending on or changing Phase 03.

### 5. Close accessibility and layout gaps

- Ensure semantic names, visible focus, keyboard order, skip/navigation behavior, live-status announcements, modal focus trap/return, and non-color status cues.
- Check the sidebar/conversation workspace, inline extension command results, extension/Bash approval and fallback surfaces, and lifecycle diagnostics at default size, configured minimum size, and 200% zoom for reachable actions and no page-level horizontal overflow.
- Fix only issues in the requested journeys; do not initiate a visual redesign.

## Verification

- Run focused existing/new Python extension tests for status, preview, exact approvals, apply, stale revision, partial failure, restart state, temp-root isolation, and no-call status.
- Run focused Python Bash/desktop tests proving exact-command approval executes once, denial/timeout/dismissal/stale/replay/mismatch/crash/shutdown execute zero times, pending state is cleared, and terminal CLI approval behavior is preserved.
- Run focused TypeScript tests for extension state, explicit preview/apply, exact decision mapping, the two-action Bash approval surface, untrusted text/link handling, modal focus, and error recovery.
- Run focused Rust/Tauri checks for command allowlisting, bounded approval event/decision forwarding, child invocation, payload bounds, capability/CSP behavior, and the absence of a WebView shell/filesystem grant.
- Exercise the full fake/temp extension journey and one fake Bash approve plus deny journey through the real desktop boundary, including extension restart/loaded revision and Bash crash/restart cleanup without executing an arbitrary real command.
- Perform keyboard-only and layout/zoom inspection across the conversation and fallback surfaces, recording the actual procedure and findings.

## Acceptance

- [ ] `/extension-management` status, preview, per-binding decisions, apply, and restart-required behavior work through the Phase 02 Python-owned conversation route with isolated data and no React/Rust command parser.
- [ ] Status makes no provider call; preview is explicit and passes with the required fake provider; any optional live preview used only a confirmed-free resolved main model with no paid fallback; stale or mismatched apply is rejected.
- [ ] One existing Python Bash request presents bounded informed context with exactly Approve and Deny; Approve executes that exact staged request once, while Deny executes nothing, and React/Rust cannot bypass or replace the Python policy.
- [ ] Unknown, expired, reused, stale, mismatched, timed-out, dismissed, crashed, restarted, or shutdown approval requests execute nothing and leave no reusable pending approval; terminal CLI Bash approval behavior remains compatible.
- [ ] The Phase 01 Rust-owned Python-child mechanism and protocol-v1 compatibility remain intact, while React/WebView has no generic shell/filesystem permission or API.
- [ ] Phase 03 knowledge behavior remains unchanged: prune confirmation still requires the matching composer `/prune <root> --yes` command and no prune modal or button exists.
- [ ] Secrets/raw payloads are absent from general DTO/UI/log surfaces and untrusted content/links remain inert or validated.
- [ ] Extension/Bash error, recovery, confirmation, keyboard/focus, non-color state, and layout checks have observed evidence.
- [ ] Focused Python/TypeScript/Rust/Tauri checks pass without dependency or real-root changes.

## Handoff

Mark Phase 04 Complete only after every required acceptance item maps to observed evidence, update the compact checkpoint, reload the plan, and continue automatically to Phase 05 once Phase 03 is also Complete. A required failed or unavailable check keeps Phase 04 In progress or Blocked. Do not pause for a routine security/a11y sign-off.
