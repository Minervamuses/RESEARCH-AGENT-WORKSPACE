# Issue 03 — Desktop Bash 權限模式：Build Log

本檔是 runtime phase status 與 observed implementation/verification evidence 的
唯一 source of truth。Plan 描述預定工作；本檔只記錄實際發生的結果。

## Phase Summary

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Backend policy and contract | Complete | 2026-09-07T00:15:51+08:00 | 2026-09-07T00:31:23+08:00 | Python service, contract, conversation, fixture, TS & Rust tests pass | None |
| 02 — Desktop permission control | Complete | 2026-09-07T00:31:23+08:00 | 2026-09-07T00:36:06+08:00 | Desktop UI control rendered, ACK reconciliation tested, build clean | None |
| 03 — Integration and trust verification | Complete | 2026-09-07T00:36:06+08:00 | 2026-09-07T00:41:25+08:00 | Full Python suite (957), Node (155), Rust (36), Tauri build, review sign-off | None |

允許的 status：

- `Not started`
- `In progress`
- `Blocked`
- `Complete`

只有所有 required acceptance 與 verification 都有 observed evidence 時，才能把
phase 標為 `Complete`。

## Evidence Rules

- 記錄 exact command 或 procedure、WSL/Linux target、concise result 與
  pass/fail/skipped/unavailable。
- Planned commands、歷史報告、source inspection 與 builder assertion 不是 passing
  implementation evidence。
- 記錄 skipped/unavailable check 的原因、residual risk 與是否阻止 completion。
- 大型 output 以安全的 local artifact/reference 連結，不複製全部內容。
- 不記錄 credential、secret、完整 diff、真實 command content 或 routine
  narration。
- Evidence 衝突時保留兩者並讓 phase 維持 `Blocked`，直到修正或取得授權決定。
- Material correction 採 append-only；更新上方 summary，但不抹除影響後續理解的
  failed attempts。

## Activity Log

## 2026-09-07T00:15:51+08:00 — Phase 01: Preflight and baseline verification

- **Status:** Not started → In progress
- **Authorized scope:** `phase-01-backend-policy-and-contract.md` and user end-to-end execution instruction
- **Exact write set:** `issue/issue_03/build-log.md`
- **Changes:** Preflight environment checks confirmed Linux/WSL runtime with Conda `app` (Python 3.13.14, Poetry 2.4.1, Node 24.18.0, npm 11.16.0, Cargo 1.97.1, rustc 1.97.1). Baseline service, Python contract, TypeScript contract, and Rust protocol tests all executed and passed.
- **Verification:**
  - `conda run -n app poetry run pytest tests/test_desktop_service.py -k "desktop_bash or conversation_replacement_or_shutdown_denies_pending_bash" -q`: pass (5 passed, 49 deselected)
  - `conda run -n app poetry run pytest tests/test_desktop_protocol_contract.py -q`: pass (105 passed)
  - `conda run -n app node --test --experimental-strip-types tests/protocol.test.ts`: pass (100 passed)
  - `conda run -n app cargo test --manifest-path src-tauri/Cargo.toml protocol::tests`: pass (12 passed)
- **Blockers:** None
- **Next action:** Implement Red test cases and schema updates across Python, contract JSON, TypeScript, and Rust.

## 2026-09-07T00:31:23+08:00 — Phase 01: Implementation and verification complete

- **Status:** In progress → Complete
- **Authorized scope:** `phase-01-backend-policy-and-contract.md`
- **Exact write set:**
  - `app/desktop/protocol/v1/contract.json`
  - `app/desktop/protocol/v1/fixtures.json`
  - `app/desktop/src/protocol.ts`
  - `app/desktop/src-tauri/src/protocol.rs`
  - `app/agent/tools/bash.py`
  - `app/agent/tools/inventory.py`
  - `app/agent/desktop/service.py`
  - `app/tests/test_desktop_protocol_contract.py`
  - `app/tests/test_desktop_service.py`
  - `app/tests/test_desktop_conversations.py`
  - `app/tests/test_desktop_fixture.py`
- **Changes:**
  - Implemented `session.set_bash_permission` method with required `mode: "ask" | "bypass"`.
  - Added `bashPermissionMode` to session snapshots for `session.create` and `session.select`.
  - Added per-conversation in-memory lifecycle with `_ConversationControlSnapshot` preserving A→B→A and resetting to `ask` on shutdown/restart.
  - Implemented idle check (`BUSY_TURN` on active turn or pending approval) and mode validation (`PROTOCOL_INVALID`).
  - Implemented bypass routing in `_desktop_bash_approval` with active ownership check and zero approval event emission.
  - Updated model-facing prompt copy in `bash.py` and `inventory.py`.
  - Synchronized JSON contract, fixtures, TypeScript definitions, and Rust mirrors.
- **Verification:**
  - `conda run -n app poetry run pytest tests/test_desktop_service.py -k "desktop_bash or bash_permission or conversation_replacement_or_shutdown_denies_pending_bash" -q`: pass (9 passed, 49 deselected)
  - `conda run -n app poetry run pytest tests/test_desktop_conversations.py -k "select_a_b_a or bash_permission" -q`: pass (2 passed, 30 deselected)
  - `conda run -n app poetry run pytest tests/test_desktop_fixture.py -k "bash_permission or thinking_mode_resets or fixture_bash" -q`: pass (3 passed, 17 deselected)
  - `conda run -n app poetry run pytest tests/test_desktop_protocol_contract.py -q`: pass (108 passed)
  - `conda run -n app poetry run pytest tests/test_bash_tool.py tests/test_tool_inventory.py -q`: pass (23 passed)
  - `conda run -n app node --test --experimental-strip-types tests/protocol.test.ts`: pass (102 passed)
  - `conda run -n app cargo test --manifest-path src-tauri/Cargo.toml protocol::tests`: pass (12 passed)
- **Blockers:** None
- **Next action:** Proceed immediately to Phase 02 — Desktop permission control.

## 2026-09-07T00:36:06+08:00 — Phase 02: Implementation and verification complete

- **Status:** In progress → Complete
- **Authorized scope:** `phase-02-desktop-permission-control.md`
- **Exact write set:**
  - `app/desktop/src/App.tsx`
  - `app/desktop/src/trust.tsx`
  - `app/desktop/tests/trust.test.ts`
- **Changes:**
  - Implemented `BashPermissionControl` component in `trust.tsx` with two mutually exclusive options ("逐次詢問（預設）" and "ByPassPermission（不再逐次詢問）").
  - Implemented `reconcileBashPermissionAck` helper ensuring same-generation, same-session, valid-enum merge.
  - Added `updateBashPermissionMode` callback in `App.tsx` with workspace operation wrapping, generation correlation, and error handling.
  - Mounted `BashPermissionControl` in `.session-controls` bound to `activeSession.bashPermissionMode` and disabled during busy/turn states.
  - Verified responsive styling without needing `.session-controls` CSS modifications.
- **Verification:**
  - `conda run -n app node --test --experimental-strip-types tests/trust.test.ts`: pass (8 passed)
  - `conda run -n app node --test --experimental-strip-types tests/protocol.test.ts tests/backend.test.ts tests/conversations.test.ts tests/answer_stream.test.ts tests/trust.test.ts`: pass (154 passed)
  - `conda run -n app node --test --experimental-strip-types tests/styles.test.ts`: pass (1 passed)
  - `conda run -n app npm run build`: pass (`tsc --noEmit && vite build` built in 128ms)
- **Blockers:** None
- **Next action:** Proceed immediately to Phase 03 — Integration and trust verification.

## 2026-09-07T00:41:25+08:00 — Phase 03: Integration, build, and trust review complete

- **Status:** In progress → Complete
- **Authorized scope:** `phase-03-integration-and-trust-verification.md`
- **Exact write set:**
  - `issue/issue_03/code_review/phase-03-integration-and-trust-verification-review.md`
  - `issue/issue_03/build-log.md`
- **Changes:**
  - Executed full cross-subsystem integration regressions and the complete repository pytest suite.
  - Executed all Node unit/integration tests and production Vite build.
  - Executed all Rust desktop tests and Linux Tauri source build (`tauri build --no-bundle`).
  - Completed independent trust-boundary code review against `GOALS.md` invariants.
- **Verification:**
  - `conda run -n app poetry run pytest tests/test_bash_tool.py tests/test_tool_inventory.py tests/test_tool_access_matrix.py tests/test_desktop_protocol_contract.py tests/test_desktop_service.py tests/test_desktop_conversations.py tests/test_desktop_fixture.py tests/test_desktop_server.py tests/test_extension_mcp.py -q`: pass (272 passed in 4.93s)
  - `conda run -n app poetry run pytest`: pass (957 passed in 24.30s)
  - `conda run -n app npm test`: pass (155 passed in 4.43s)
  - `conda run -n app npm run build`: pass (`tsc --noEmit && vite build` built in 106ms)
  - `conda run -n app cargo test --manifest-path src-tauri/Cargo.toml`: pass (36 passed in 0.22s)
  - `conda run -n app npm run tauri -- build --no-bundle`: pass (built binary at `app/desktop/src-tauri/target/release/research-agent-desktop` in 1m 14s)
  - `git diff --check`: pass (clean, 0 errors)
- **Review:** Independent sign-off recorded in `issue/issue_03/code_review/phase-03-integration-and-trust-verification-review.md`.
- **Limitations:** Interactive live-model GUI runs are mocked/deterministic by design; automated tests cover all states.
- **Blockers:** None
- **Next action:** All phases complete. Deliver final report to user.

<!-- 實作時僅 append material event，格式如下：

## <timestamp with timezone> — Phase <NN>: <event>

- **Status:** <previous> → <new>
- **Authorized scope:** <phase file and current user authority>
- **Exact write set:** <paths actually owned by this phase>
- **Changes:** <concise observed change>
- **Verification:** <exact commands/procedures and pass/fail/unavailable results>
- **Review:** <findings or sign-off when applicable>
- **Limitations:** <untested or explicitly accepted limitations>
- **Blockers:** <current blockers or None>
- **Next action:** <next eligible action under PLANS.md>
- **Evidence references:** <context, review, logs, artifacts, or commits>
-->
