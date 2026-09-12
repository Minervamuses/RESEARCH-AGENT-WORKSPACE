# Phase 01 — Backend Policy and Contract

## Source Inputs

- `../GOALS.md`
- `../PLANS.md`
- `../../03-desktop-bash-permission-mode.md`
- `../../../AGENTS.md`
- `../../../app/agent/desktop/service.py`
- `../../../app/agent/desktop/protocol.py`
- `../../../app/agent/tools/bash.py`
- `../../../app/agent/tools/inventory.py`
- `../../../app/desktop/protocol/v1/contract.json`
- `../../../app/desktop/protocol/v1/fixtures.json`
- `../../../app/desktop/src/protocol.ts`
- `../../../app/desktop/src-tauri/src/protocol.rs`
- Relevant Python and Desktop protocol/Bash tests listed below.

## Objective

完成一個跨 Python、JSON、TypeScript、Rust 一致的 authoritative Bash permission
boundary：fresh/default 為 `ask`，conversation A/B 狀態在目前 backend generation
內隔離與恢復，restart reset；`bypass` 對 valid active Desktop Bash call 直接
允許而不 staging approval，`ask` 則完整保留既有 fail-closed approval flow。

## In Scope

- 以 `bashPermissionMode` 作 session snapshot field，wire enum 固定為
  `"ask" | "bypass"`。
- 新增 `session.set_bash_permission` control method，request param 為 `mode`；
  setter result 固定為且嚴格驗證 `sessionId` 與 `bashPermissionMode` 兩個欄位。
- 在 `session.create`／`session.select` result schema 與 TypeScript DTO 加入必填
  mode；backend status/snapshot 回傳目前 authoritative mode。
- 在 `DesktopService` 使用目前 active mode 加
  `_ConversationControlSnapshot`，支援 A→B→A 與 shutdown/new-service reset。
- Setter 沿用 `_require_idle_session`；active turn/pending approval 時拒絕且不改
  mode。
- Bypass 先驗 active sink/request/turn ownership，再直接允許；不建立
  `_PendingApproval`、future/timestamp/event/wait。Ask 才進 safe-display 與
  existing pending/resolve path。
- 同步 `contract.json`、`fixtures.json`、`protocol.ts` 與 `protocol.rs`。
- 修正 `bash.py` 與 `inventory.py` 的 model-facing prompt copy，使其說明
  command 受 active runtime permission policy 控制；CLI 行為不變。
- 使用現有 injected fake runners、service/session factories 與 protocol fixtures
  增加最小 regression coverage。

## Non-Goals

- React permission control；由 Phase 02 負責。
- Persistent state、settings module、catalog/conversation format change。
- Extension/MCP approval implementation change。
- Queue、serialization 或 ToolNode scheduling redesign。
- 重構現有 approval dialog、backend transport 或 Tauri process lifecycle。
- 修改 `app/agent/desktop/protocol.py`，除非 failing evidence 證明 dynamic contract
  reader 無法處理新增 schema。
- 修改 `app/agent/session.py` 的「approval-gated」字樣，除非 preflight 證明它
  明確承諾每次顯示 dialog，而非描述 policy gate。

## Dependencies and Prerequisites

- 使用者已送出 `../PROMPTS.md` 的完整 launch prompt 或等價明確 authority。
- WSL/Linux runtime gate 通過，Conda `app` 的 Python/Poetry/Node/npm 可用。
- **Verified authoring prerequisite:** Initial base-shell `PATH` 未曝光 Cargo/rustc，
  但 follow-up 已確認 Conda `app` 內有 Linux Cargo 1.97.1 與 rustc 1.97.1。
  Implementation write 前仍須從既定 Conda runtime 重新確認；不得改用 native
  Windows Cargo，若需安裝或修復 toolchain/system package 則需 fresh authority。
- Initial worktree 必須重新檢查；保留所有 pre-existing changes。
- **Technical observation to confirm:** `_ConversationControlSnapshot`、select/create
  atomicity 與 shutdown clearing 仍與 authoring baseline 相同。

## Expected Components Affected

### Production

- `app/agent/desktop/service.py`
- `app/agent/tools/bash.py`
- `app/agent/tools/inventory.py`
- `app/desktop/protocol/v1/contract.json`
- `app/desktop/src/protocol.ts`
- `app/desktop/src-tauri/src/protocol.rs`

### Fixtures and tests

- `app/desktop/protocol/v1/fixtures.json`
- `app/tests/test_desktop_protocol_contract.py`
- `app/tests/test_desktop_service.py`
- `app/tests/test_desktop_conversations.py`
- `app/tests/test_desktop_fixture.py`
- `app/tests/test_bash_tool.py`
- `app/tests/test_tool_inventory.py`
- `app/desktop/tests/protocol.test.ts`
- Existing Rust inline protocol tests in `protocol.rs`.

Do not add a new test framework. Add `test_tool_access_matrix.py` or
`test_desktop_server.py` only if a changed claim/path requires direct regression evidence.

## Authorization and Stop Conditions

- Routine local edits and checks above are covered only after the launch gate。
- Stop if the smallest correct contract requires protocol version/envelope change,
  persistent storage, a new module/dependency, or files outside `PLANS.md` authorization。
- Stop if Linux Cargo is absent; report exact missing tool and do not install it。
- Stop if implementation cannot preserve active ownership before bypass or ask-mode
  fail-closed semantics。
- A failed target materialization must leave the original conversation and its mode
  unchanged; evidence to the contrary blocks completion。

## Implementation and Verification Plan

### Preflight

- Confirm repository root, `GUI` worktree ownership and WSL/Linux tool paths.
- Read current dispatch map, session create/select, snapshot capture/apply/store,
  idle control setter, shutdown, Bash broker and protocol validators.
- Run the smallest existing baseline checks before edits; record failures instead of
  assuming a clean baseline.
- Confirm shared fixtures and JSON/TS/Rust parity loops so one additive method/field is
  represented exactly once in each source.

### Red

- Add protocol cases that reject unknown/missing/extra permission fields and accept only
  `ask`／`bypass` for the new setter and result.
- Add service tests proving: default ask; idle setter ACK; active-turn setter
  `BUSY_TURN`; A bypass/B ask/return A bypass; shutdown/new service reset.
- Add fake-runner tests proving two consecutive bypass calls execute exactly once each
  with zero `approval.required`, while switching back to ask stages the next display-safe
  request.
- Add one fake secret-like/undisplayable context case: ask remains deny/no-event/no-run;
  bypass runs only through the fake runner and sends no context over the event sink.
- Observe these tests fail for the missing mode behavior, not for fixture or environment
  mistakes.

### Green

- Add current mode to `DesktopService` and to per-conversation control snapshots.
- Commit a target conversation's mode only after successful materialization/lifecycle
  checks; default missing/new targets to ask; clear current mode and snapshots on shutdown.
- Add the idle-only setter and minimal strict protocol method/result.
- In the approval handler, verify active Desktop ownership for both modes; branch to
  bypass before pending approval/display-safety staging, and leave ask flow unchanged.
- Mirror the additive contract through JSON, TypeScript and Rust; update only directly
  false model-facing prompt copy.

### Refactor

- No new abstraction is expected. Reuse existing control snapshot, setter, protocol schema
  and test fixture patterns.
- Perform only local naming/deduplication needed to keep one mode normalization path.
- After any structural edit, rerun the focused service and protocol checks.

### Verification

From `/home/minervamuses/research-agent-workspace/app`:

- **Focused Python service:**
  `/home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_desktop_service.py -k "desktop_bash or bash_permission or conversation_replacement_or_shutdown_denies_pending_bash" -q`
- **Focused conversation lifecycle:**
  `/home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_desktop_conversations.py -k "select_a_b_a or bash_permission" -q`
- **Focused restart/fixture lifecycle:**
  `/home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_desktop_fixture.py -k "bash_permission or thinking_mode_resets or fixture_bash" -q`
- **Python contract:**
  `/home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_desktop_protocol_contract.py -q`
- **CLI/tool-copy regression:**
  `/home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest tests/test_bash_tool.py tests/test_tool_inventory.py -q`

From `/home/minervamuses/research-agent-workspace/app/desktop`:

- **TypeScript contract:**
  `/home/minervamuses/miniconda3/bin/conda run -n app node --test --experimental-strip-types tests/protocol.test.ts`
- **Rust protocol:**
  `/home/minervamuses/miniconda3/bin/conda run -n app cargo test --manifest-path src-tauri/Cargo.toml protocol::tests`

- **Manual/external:** None. Do not run a real command or provider call.
- **Failure behavior:** Any required focused failure keeps Phase 01 `In progress`.
  Missing Linux Cargo makes Phase 01 `Blocked` and prevents Phase 02; skipped Rust
  validation is not a pass.

## Reliability, Security, and Recovery

- Bypass is a deliberate trust-boundary change but only after an explicit per-conversation
  selection; unknown state always maps to ask.
- Active sink/request/turn ownership remains mandatory so the approval handler cannot be
  called out of a valid Desktop turn.
- Ask retains safe-display, pending single-flight, expiry, correlation and replay
  protection exactly.
- Bypass emits no command/description payload, so display-safety does not become an
  accidental command-policy denylist.
- Mode switch/select is atomic: failed target loading or invalid ACK cannot partially
  change the active mode.
- Version control makes local edits reversible; no data migration or operational rollback
  exists. On a failed check, keep the phase incomplete and repair or revert only the
  scoped diff.

## Acceptance Criteria

- [ ] Fresh/new/no-snapshot conversation returns `ask` in service and validated snapshots.
- [ ] `session.set_bash_permission` accepts only idle `ask`／`bypass` and returns a
      strictly validated authoritative ACK.
- [ ] A→B→A and shutdown/new-service lifecycle exactly match `GOALS.md`.
- [ ] Bypass fake-runner calls execute exactly once each, emit no approval event and need
      no resolve; ask resumes on the next call after switching back.
- [ ] Ask unsafe/missing/conflicting context behavior, approve/deny/timeout/replay and
      active ownership remain fail closed.
- [ ] Extension/MCP code paths do not read the permission mode, and CLI Bash behavior
      remains TTY-prompt/non-interactive-deny.
- [ ] JSON/Python/TypeScript/Rust contract and fixtures agree on all added fields/methods.
- [ ] Every listed required focused check passes with observed evidence.

## Evidence to Record

- Exact command, WSL/Linux tool path/version and concise result in `../build-log.md`.
- Acceptance criterion → observed check mapping.
- Material select atomicity, concurrency or protocol discovery only in
  `../context/phase-01-backend-policy-and-contract-context.md` when it changes later work.
- Do not create a review file unless an actual independent review occurs.

## Handoff

- Phase 02 may begin only after Phase 01 is `Complete` with Python, TypeScript and Rust
  evidence.
- Handoff supplies one authoritative `bashPermissionMode` in create/select snapshots and
  one validated setter ACK; Phase 02 must not invent another state owner.
- In autonomous mode continue to Phase 02; otherwise stop only if a recorded authorization
  or environment blocker remains.
