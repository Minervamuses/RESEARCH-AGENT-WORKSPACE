# Phase 02 — Desktop Permission Control

## Source Inputs

- `../GOALS.md`
- `../PLANS.md`
- `../build-log.md`
- `phase-01-backend-policy-and-contract.md`
- Phase 01 material context/review, if it actually exists.
- `../../../app/desktop/src/App.tsx`
- `../../../app/desktop/src/conversations.ts`
- `../../../app/desktop/src/protocol.ts`
- `../../../app/desktop/src/backend.ts`
- `../../../app/desktop/src/styles.css`
- `../../../app/desktop/src/trust.tsx`
- `../../../app/desktop/tests/`

## Objective

在既有 conversation controls 中提供清楚、可存取、互斥的 `ask` 與
`ByPassPermission` 選擇；顯示值只來自 valid same-generation/same-session
backend snapshot 或 setter ACK，切換 conversation、backend generation 或 request
失敗時不會顯示 stale 或 optimistic trust state。

## In Scope

- 在現有 `session-controls` 加入一個明確標示 Bash permission 的 settings control
  （button/menu、segmented control 或等價的單選控制），包含兩個互斥選項：
  「逐次詢問（預設）」與「ByPassPermission」。
- UI 必須直接顯示 current mode；bypass 選項需清楚說明 Bash 將不再逐次詢問。
- 以 Phase 01 的 session DTO field 作 controlled value，不建立 localStorage 或
  第二個 independent mode state。
- 以 `updateThinkingMode` 為模式實作新的 ACK-first update：control request 中
  disabled；只有 protocol validation、generation 與 `sessionId` correlation
  成功後才 merge ACK。
- Active turn、workspace operation 或 backend lifecycle transition 時 disabled。
- Setter failure、protocol mismatch、conversation switch 或 generation reset 時
  保留/重建 backend-authoritative value，並使用既有 safe workspace error。
- 增加最小 Node/UI regression，保留 existing approval dialog 與 Extension UI。

## Non-Goals

- 在前端 auto-resolve `approval.required`。
- 重做 `ApprovalDialog`、Extension flow、conversation reducer 或整體視覺系統。
- 新增 UI framework、state library、browser automation framework 或 dependency。
- 在 React、Rust 或 browser storage 持久化 permission mode。
- 執行 Bash、provider 或外部服務作 UI test。

## Dependencies and Prerequisites

- Phase 01 在 `../build-log.md` 為 `Complete`，且 authoritative field、setter ACK
  與三語言 contract 有 evidence。
- WSL/Linux Conda `app` 的 Node/npm 可用。
- 重新核對 `App.tsx` generation reset、session create/select 與
  `updateThinkingMode` pattern；live source 優先於本 phase 的行號假設。
- **Unresolved implementation detail:** 使用現有 select styling 是否足以符合
  使用者要求的 settings button/兩選項與 accessibility。以最小 accessible control
  解決；只有實際 layout/test evidence 要求時才改 `styles.css` 或 `trust.tsx`，
  不需要再詢問產品語意。

## Expected Components Affected

### Required production

- `app/desktop/src/App.tsx`

### Already established by Phase 01

- `app/desktop/src/protocol.ts`

### Conditional production

- `app/desktop/src/styles.css`，僅在 existing session-control rules 不足時。
- `app/desktop/src/trust.tsx`，僅在沿用其 static-render test seam 能以較小變更測試
  control 時；existing `ApprovalDialog` semantics 不得改。

### Tests

- `app/desktop/tests/protocol.test.ts`
- `app/desktop/tests/backend.test.ts`
- `app/desktop/tests/conversations.test.ts`
- `app/desktop/tests/answer_stream.test.ts`
- `app/desktop/tests/trust.test.ts`
- `app/desktop/tests/styles.test.ts` only if styles change.

`app/desktop/src/backend.ts` 預期只供既有 generic client 使用，不應修改；
若 testability 要求改 production transport，停止並先證明較小 seam 不足。

## Authorization and Stop Conditions

- Routine files above由 launch authority 覆蓋。
- Stop if UI 需要新 dependency、generic settings architecture、persistent browser
  state 或 new Tauri command/capability。
- Stop if Phase 01 contract evidence 不完整或 live DTO 與 phase assumptions 不一致；
  先 repair 未開始 plan。
- Stale/mismatched ACK 若無法以現有 generation/session checks 安全拒絕，Phase 02
  維持 `Blocked`；不得以 optimistic update 掩蓋。

## Implementation and Verification Plan

### Preflight

- Confirm Phase 01 completion and reload actual protocol DTO/method names.
- Characterize session create/select replacement、backend generation reset、
  `conversationInteractionState.controlDisabled`、workspace operation guard 與
  thinking-control ACK flow。
- Run focused Node baseline and record any pre-existing failure。
- Check existing `session-controls` at default and narrow viewport through current tests
  or source rules before deciding whether CSS is necessary。

### Red

- Add a failing test/fixture proving the rendered control has exactly two mutually
  exclusive modes, a visible current value and clear bypass warning text。
- Add logic-level/source-boundary checks proving active/busy states disable the control。
- Add ACK cases: valid same-generation/same-session result updates; backend error、
  invalid enum、session mismatch and generation change do not apply the stale mode。
- Preserve existing tests for approval dialog correlation/inert content and Extension
  trust actions。

若 current Node setup 無法 mount `App` without a new dependency，使用既有
`renderToStaticMarkup` seam 或小型 pure helper/component；不要新增 test framework。

### Green

- Add the smallest accessible permission control beside Thinking。
- Bind its value to `activeSession.bashPermissionMode`。
- Implement one callback mirroring existing workspace-operation、generation、
  `sessionId`、protocol-error and focus behavior。
- Do not mutate displayed trust state before the successful ACK。
- Keep existing approval dialog event handling unchanged；bypass absence of dialog comes
  from Phase 01 not emitting the event。

### Refactor

- Reuse existing control styles and callback structure；avoid a generic settings layer。
- Extract only a tiny pure rendering/ACK helper when required for deterministic tests。
- Rerun focused Node checks after any material extraction or CSS change。

### Verification

From `/home/minervamuses/research-agent-workspace/app/desktop`:

- **Focused UI/protocol:**
  `/home/minervamuses/miniconda3/bin/conda run -n app node --test --experimental-strip-types tests/protocol.test.ts tests/backend.test.ts tests/conversations.test.ts tests/answer_stream.test.ts tests/trust.test.ts`
- **Style check, only if CSS changes:**
  `/home/minervamuses/miniconda3/bin/conda run -n app node --test --experimental-strip-types tests/styles.test.ts`
- **TypeScript/Vite build:**
  `/home/minervamuses/miniconda3/bin/conda run -n app npm run build`

- **Manual:** If the existing provider-free local flow can reach session controls without
  credentials or a real Bash command, inspect default/narrow layouts and keyboard/label
  behavior. Otherwise record manual UI as unavailable and rely on deterministic render,
  logic and build evidence; do not obtain credentials or call a provider。
- **Failure behavior:** Any required Node/build failure keeps Phase 02 `In progress`。
  Phase 03 cannot begin。

## Reliability, Security, and Recovery

- Backend response is authoritative；React never stores a permission decision separately。
- Generation and session correlation prevent an old A/before-restart ACK from changing
  B/new-generation UI。
- Disabled state prevents a pending approval from being retroactively converted to
  bypass；backend idle-only rejection remains the final authority。
- Error recovery preserves the last confirmed mode and exposes the existing bounded UI
  error；retry is an explicit user action。
- No data migration/rollback exists。A failed phase stays incomplete；revert or repair
  only the scoped React/CSS diff。

## Acceptance Criteria

- [ ] Session controls expose one clear, accessible two-mode Bash permission control。
- [ ] Fresh/B conversation displays ask；returning to A displays its backend-restored
      bypass；new generation displays ask after a fresh backend snapshot。
- [ ] Valid setter ACK is the only path that changes the displayed mode。
- [ ] Active turn/workspace busy disables the control；pending commands are never
      auto-resolved by React。
- [ ] Error、invalid mode、session mismatch and stale generation ACK do not corrupt UI
      state and surface the existing safe error behavior。
- [ ] Existing one-time approval dialog and Extension trust UI tests remain unchanged in
      meaning。
- [ ] Focused Node tests and `npm run build` pass with observed evidence。

## Evidence to Record

- Exact Node/build commands and concise results in `../build-log.md`。
- Rendered markup or screenshot only when produced without credential/live provider；
  otherwise record the unavailable manual step。
- Material discovery only in
  `../context/phase-02-desktop-permission-control-context.md`。
- Actual review findings only in
  `../code_review/phase-02-desktop-permission-control-review.md` when a review occurs。

## Handoff

- Phase 03 may begin only when Phase 01 and Phase 02 are `Complete`。
- Handoff includes a backend-authoritative mode, validated setter and UI evidence for
  valid/stale/error transitions。
- Continue automatically in autonomous mode；stop only for a recorded gate。
