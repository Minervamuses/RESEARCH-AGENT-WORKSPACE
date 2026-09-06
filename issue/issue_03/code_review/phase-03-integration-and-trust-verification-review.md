# Phase 03 — Integration and Trust Verification Review

- **Review Date:** 2026-09-07T00:41:25+08:00
- **Target Repository:** `/home/minervamuses/research-agent-workspace` (Branch `GUI`)
- **Reviewer Stance:** Independent Trust Boundary and Regression Review
- **Reference Document:** `issue/issue_03/GOALS.md`, `issue/issue_03/PLANS.md`, `issue/issue_03/phases/phase-03-integration-and-trust-verification.md`

## 1. Executive Summary

This review independently evaluates the changes introduced for Issue 03 (Desktop Bash Permission Mode: `ask` / `bypass`).
All modifications across Python, JSON, TypeScript, and Rust were inspected against the safety invariants, lifecycle requirements, and acceptance criteria in `GOALS.md`.

All required test suites and builds passed with zero errors or regressions. The diff strictly adheres to the bounded scope authorized in `PLANS.md`.

## 2. Verified Invariants and Success Conditions

| Success Condition / Invariant | Evaluation | Observed Evidence |
|---|---|---|
| Fresh conversation defaults to `ask` | Confirmed | `test_desktop_bash_permission_mode_defaults_to_ask_and_rejects_busy_turn` verifies initial snapshot returns `bashPermissionMode: "ask"`. |
| Bypass mode executes without approval events | Confirmed | `test_desktop_bash_permission_mode_idle_setter_and_fake_runner_bypass` proves two consecutive calls execute via injected fake runner with 0 `approval.required` events. |
| Returning to ask restores approval dialog & staging | Confirmed | `test_desktop_bash_permission_mode_switching_back_to_ask_restores_approval` verifies switching back to `ask` stages `approval.required` and enforces resolve. |
| Conversation A -> B -> A in-memory isolation | Confirmed | `test_select_a_b_a_preserves_bash_permission_mode_in_memory_across_conversations` proves conversation B defaults to `ask`, and re-selecting A restores `bypass`. |
| Service restart / shutdown reset | Confirmed | `test_bash_permission_mode_resets_to_ask_after_service_restart_and_select` proves shutdown and new service generation reset all conversations to `ask`. |
| Active turn blocks mode change | Confirmed | `_require_idle_session` blocks setter with `BUSY_TURN` when turn is active or pending approval. |
| Stale / mismatched ACK rejection in UI | Confirmed | `reconcileBashPermissionAck` verified by 8 unit tests in `trust.test.ts`: rejects mismatched generation, mismatched session, and invalid enum. |
| Extension & MCP isolation | Confirmed | `test_extension_mcp.py` and `test_extension_user_journey.py` pass without regression; Extension and MCP approval flows do not read `bashPermissionMode`. |
| CLI / non-Desktop Bash isolation | Confirmed | `test_bash_tool.py` and `test_tool_inventory.py` pass; non-desktop CLI continues prompting via TTY or auto-denying non-interactive execution. |
| Cross-language protocol parity | Confirmed | JSON contract, TypeScript schemas, and Rust mirrors match verbatim; 108 Python, 155 Node, and 36 Rust protocol tests pass. |
| Deterministic fake runner only | Confirmed | All tests run with injected fake runner fixtures; no real shell commands, live credentials, or paid providers invoked. |

## 3. Detailed Verification Results

1. **Python Focused Regression Suite:**
   - Command: `conda run -n app poetry run pytest tests/test_bash_tool.py tests/test_tool_inventory.py tests/test_tool_access_matrix.py tests/test_desktop_protocol_contract.py tests/test_desktop_service.py tests/test_desktop_conversations.py tests/test_desktop_fixture.py tests/test_desktop_server.py tests/test_extension_mcp.py -q`
   - Result: 272 passed in 4.93s.
2. **Full Repository Python Suite:**
   - Command: `conda run -n app poetry run pytest`
   - Result: 957 passed in 24.30s.
3. **Desktop Node Test Suite:**
   - Command: `conda run -n app npm test`
   - Result: 155 passed in 4.43s.
4. **Desktop Rust Test Suite:**
   - Command: `conda run -n app cargo test --manifest-path src-tauri/Cargo.toml`
   - Result: 36 passed in 0.22s.
5. **Desktop Production Frontend Build:**
   - Command: `conda run -n app npm run build`
   - Result: Succeeded (`tsc --noEmit && vite build`).
6. **Linux Tauri Source Build:**
   - Command: `conda run -n app npm run tauri -- build --no-bundle`
   - Result: Succeeded (Built application at `app/desktop/src-tauri/target/release/research-agent-desktop` in 1m 14s).
7. **Whitespace and Formatting Sanity:**
   - Command: `git diff --check`
   - Result: Clean (0 errors).

## 4. Scope and Non-Goals Compliance

- **No persistent data mutations:** `bashPermissionMode` is purely in-memory in `_control_snapshots` and cleared on shutdown. It does not touch conversation JSON files or catalogs.
- **No new external dependencies:** No packages added to Python `pyproject.toml` or Node `package.json`.
- **No auto-resolve in frontend:** React never resolves pending approval events to simulate bypass. Bypass is handled authoritatively in the backend broker before approval staging.
- **Fail-closed security:** Active turn/request ownership is strictly verified before bypass allows execution; ask mode retains full safe-display and correlation gates.

## 5. Limitations

- Manual interactive GUI testing with live models was not conducted as this project intentionally uses deterministic, provider-free mock/fake harnesses. Automated SSR rendering and static tests in Node verify complete component behavior and accessibility.

## 6. Sign-off

Issue 03 implementation meets all criteria specified in `GOALS.md` and `PLANS.md`. Phase 03 is verified and approved.
