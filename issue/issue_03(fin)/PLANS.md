# Issue 03 — Desktop Bash 權限模式：執行計畫

## Plan Overview

- **Plan root:** `issue/issue_03`
- **Purpose:** 依 `GOALS.md` 實作 conversation-scoped、backend-generation-local 的
  Desktop Bash `ask`／`bypass` 模式，並以 Python 作 policy owner、shared
  protocol 作邊界、React 作 ACK-driven presentation。
- **Execution mode:** 使用者送出 `PROMPTS.md` 的完整 launch prompt 後，在授權
  envelope 內 autonomous；本次 authoring 本身不授權 implementation。
- **Repository shape:** Application；一個 Python/Poetry agent 加一個
  Tauri/React desktop application。
- **Change risk:** High。此功能刻意允許在使用者選取後跳過逐次 shell approval，
  並跨 Python、JSON、TypeScript、Rust 邊界。
- **Phase directory:** `phases/`。根 `.gitignore` 的 `build/` 規則會忽略任何
  深度的 `build/`，而 repository 歷史 plan 慣例使用 `phases/`。

## Source-of-Truth Map

- 穩定目標、生命週期、scope、non-goals 與 invariants：`GOALS.md`
- Phase 順序、dependencies、authorization 與整體完成條件：`PLANS.md`
- 可重用啟動、單 phase、plan repair 與 final review 指令：`PROMPTS.md`
- 每個 phase 的 bounded work 與 planned verification：`phases/phase-*.md`
- 唯一 runtime status 與 observed evidence owner：`build-log.md`
- 實作後才產生的 material discovery：`context/`
- 實際 review 發生後才產生的 finding：`code_review/`
- 最強事實來源：live repository、實際 diff 與實際執行結果。

`context/` 與 `code_review/` 不在 initial authoring write set；不得預先建立空檔
或虛構 evidence。

## Confirmed Repository Baseline

### Runtime and worktree

- Repository root：`/home/minervamuses/research-agent-workspace`。
- 支援 runtime：WSL/Linux（Ubuntu 24.04）；Windows PowerShell 只作 WSL
  orchestration。
- Authoring preflight：Conda `app` 內 Python 3.13.14、Poetry 2.4.1、
  Node 24.18.0、npm 11.16.0；全部解析到
  `/home/minervamuses/miniconda3/envs/app/bin/`。
- Initial base-shell preflight 未在 `PATH` 找到 Cargo/rustc；follow-up 已確認
  Conda `app` 提供 `/home/minervamuses/miniconda3/envs/app/bin/cargo` 1.97.1 與
  `rustc` 1.97.1。Tauri system build prerequisites 尚待實際 build check 證明。
- Initial Git state：branch `GUI`，HEAD
  `ed1875422d7dfab5c3358f8a3c5c01939cfaa986`，相對 `origin/GUI` ahead 2，
  worktree clean。這兩個既有未推送 commits 不是本計畫產物。

### Relevant implementation boundaries

- `app/agent/desktop/service.py` 的 `_ConversationControlSnapshot` 與
  `_control_snapshots` 已為 thinking mode 提供 A→B→A 的 generation-local
  memory；`_shutdown_session` 會清空 snapshots。
- `session.set_thinking` 已提供 idle-only control setter 的直接範例。
- Desktop Bash handler 在 `_desktop_bash_approval`／`_stage_bash_approval`
  建立 pending approval。Ask path 目前對 unsafe/missing/conflicting context
  直接拒絕，不保證每次呼叫都發 event。
- `app/agent/tools/bash.py` 只有 approval handler 回傳 true 才呼叫 runner，
  且現有 injected runner seam 足以測試，不需新 test framework。
- Python `app/agent/desktop/protocol.py` 動態讀
  `desktop/protocol/v1/contract.json`；TypeScript `protocol.ts` 與 Rust
  `protocol.rs` 則是手動 mirror。
- React `App.tsx` 目前只在收到 `approval.required` 時顯示
  `ApprovalDialog`；`updateThinkingMode` 是 generation/session-correlated、
  ACK-first control update 的既有範例。
- `app/desktop/src/backend.ts` 與 Rust backend bridge 已是 generic protocol
  transport；目前沒有證據要求新增 Tauri command、capability 或 process owner。
- Repository 已有 Python, Node, Rust protocol fixtures/tests、Desktop fake Bash
  runner 與 Extension/MCP approval tests；目前沒有 permission-mode tests。

本 authoring run 沒有執行 application tests、build 或 GUI journey；任何歷史或
planned command 都不算 `build-log.md` 的 implementation evidence。

## Execution Authorization

### Launch gate

正式 implementation 前，使用者必須送出 `PROMPTS.md` 的完整
`Start or Resume End-to-End Execution` prompt，或以等價文字明確批准：

- 對 protocol-v1 新增 backward-compatible method、enum、snapshot field 與
  setter result schema；
- 修改超過三個直接必要的 production files；
- 在本計畫的 bounded scope 內持續完成三個 phases。

沒有這項 authority 時，執行代理只能做 read-only preflight，將 Phase 01 標為
`Blocked` 並停止；plan 文件本身不得被解讀為 implementation 授權。

### Routine actions authorized after launch

- 修改 selected phase 明列、且與 `GOALS.md` 有直接因果關係的既有 application
  與 test files。
- 新增或更新最小 protocol fixtures 與 regression tests。
- 在 Conda `app`、WSL/Linux 中執行 phase 明列的 focused tests、Node checks、
  Rust checks、build 與一次 final broader suite。
- 使用 pytest/tmp fixtures 與 injected fake runners；建立並清理不含使用者資料
  的暫存檔。
- 更新本 bundle 的 `build-log.md`、material `context/`、實際
  `code_review/` 與被新證據影響的未開始 phase 文件。
- 在不改變 behavior 的前提下做 phase 內最小 cleanup，並於 material refactor
  後重跑 focused checks。

### Expected production write surface

最小實作預期涉及：

- `app/agent/desktop/service.py`
- `app/agent/tools/bash.py`
- `app/agent/tools/inventory.py`
- `app/desktop/protocol/v1/contract.json`
- `app/desktop/src/protocol.ts`
- `app/desktop/src-tauri/src/protocol.rs`
- `app/desktop/src/App.tsx`

`app/desktop/src/styles.css` 或 `app/desktop/src/trust.tsx` 只有在既有 control
style/test seam 無法滿足清楚且可存取的兩選項 UI 時才可修改；不要為此新增
component framework 或 dependency。`app/agent/desktop/protocol.py`、
`app/desktop/src/backend.ts`、Rust backend/process/capability files 預期不需改，
除非 live evidence 證明既有 generic path 無法承載已批准 contract；先記錄因果
再決定是否需要 fresh authority。

### Stop and obtain fresh authority

- 目標、lifecycle、default、non-goal 或 preserved trust behavior 必須改變。
- 需要 dependency、Conda environment、lockfile、Rust toolchain 或 Tauri system
  package 安裝／升級。
- 需要 persistent setting、conversation schema、catalog 格式、protocol version
  或 envelope change，而非已批准的 additive protocol-v1 field/method。
- 需要 service、database、queue、worker、serialization layer 或新的 concurrency
  model。
- 需要 credentials、live/paid provider、真實 shell command、使用者 store 或
  external system write。
- 需要 destructive operation、commit、push、merge、rebase、branch/worktree
  change、deploy、publish 或 release。
- Required command 預期超過約十分鐘而 launch message 未明確批准，或需要第二次
  expensive broader run。
- Rust/Tauri 或其他 required evidence 無法取得。這會讓目前成功條件保持
  `Blocked`；若要把該 evidence 改為非必要，必須由使用者明確變更目標並先修訂
  本計畫，不能在執行途中以接受 residual risk 直接結案。

### Repository instructions

所有 applicable `AGENTS.md` 持續優先。本計畫不修改或取代 `AGENTS.md`。

## Phase Roadmap

| Phase | Outcome | Depends on | Phase file |
|---|---|---|---|
| 01 — Backend policy and contract | Python authoritative state、ask/bypass broker、per-conversation lifecycle 與 JSON/TS/Rust protocol contract 成為一個可驗證的完整 boundary | None | `phases/phase-01-backend-policy-and-contract.md` |
| 02 — Desktop permission control | 使用者能以清楚的兩模式 control 切換，UI 只顯示 correlated backend ACK 的 mode，conversation/generation 轉換不顯示 stale trust state | Phase 01 | `phases/phase-02-desktop-permission-control.md` |
| 03 — Integration and trust verification | 代表性 fake-runner journey、Extension/MCP/CLI 隔離、跨語言 checks、Linux build 與 independent review 對所有 success conditions 提供 observed evidence | Phases 01 and 02 | `phases/phase-03-integration-and-trust-verification.md` |

## Dependency and Sequencing Notes

- Phase 01 將 backend behavior 與所有 protocol mirrors 放在同一 phase，避免完成
  checkpoint 留下已知的 JSON/TypeScript/Rust 不一致。
- Phase 02 必須依賴已驗證的 authoritative snapshot field 與 setter ACK，不能以
  React local state 或 auto-resolve approval event 暫代。
- Phase 03 不替前兩個 phases 補做它們自己的 focused verification；它只負責
  跨 phase scenario、broader regression、build 與 review。
- 任何 required check failure 都阻止 dependent phase。若 Phase 01 因 Linux
  Cargo prerequisite 而 Blocked，Phase 02 不得先以未驗證 contract 開發。

## Acceptance Coverage

| Goal scenario | Owning phase evidence | Final confirmation |
|---|---|---|
| Fresh/new conversation 為 `ask` | Phase 01 service/contract tests | Phase 03 fake journey |
| A `bypass`、B `ask`、回 A 恢復 bypass | Phase 01 conversation snapshot tests | Phase 03 integrated matrix |
| Restart 後全部 `ask` | Phase 01 fixture/service restart tests | Phase 03 generation reset check |
| Bypass 無 event/wait，ask 恢復 dialog | Phase 01 fake runner/broker tests | Phase 03 representative journey |
| UI ACK-first、stale response 不污染 | Phase 02 Node/UI tests | Phase 03 review/build |
| Extension/MCP/CLI 隔離 | Phase 01/02 focused regressions | Phase 03 explicit isolation test |
| 三語言 contract 一致 | Phase 01 Python/Node/Rust checks | Phase 03 full protocol/build checks |

## Plan Maintenance

- `build-log.md` 是唯一 phase status 與 observed evidence owner。
- Required focused 或 broader check failure 使 phase 維持 `In progress` 或
  `Blocked`；dependent phase 不得開始。
- 一次只診斷一個有證據的 causal hypothesis。相同原因兩次 focused attempt
  失敗後，記錄 evidence 與 blocker；不要堆疊猜測性修補。
- Live evidence 若推翻未開始 phase，先更新本 roadmap 與受影響的 phase files，
  再繼續 implementation。
- 保留 completed evidence 與 material failed attempts；用 append-only correction
  修正 `build-log.md`，不要重寫歷史。
- 穩定目標只在使用者明確改變需求後才更新 `GOALS.md`。
- `context/` 只保存會改變後續實作/驗證的 material discovery；
  `code_review/` 只在 review 真正發生後建立。

## Overall Completion Criteria

- [ ] 三個 phase 在 `build-log.md` 都是 `Complete`，且每項 required check 有
      exact observed evidence。
- [ ] `GOALS.md` 的每個 success condition 都能對應到 test、build、review 或
      representative acceptance evidence。
- [ ] Default ask、A→B→A、ask↔bypass、idle-only、restart reset、stale ACK 與
      invalid mode 情境全部通過。
- [ ] Ask path 的 safe-display/correlation/timeout/replay 行為與
      CLI/non-interactive Bash 行為沒有 regression。
- [ ] Bypass 只影響 active Desktop Bash；Extension apply 與 MCP exact-binding
      approval 有直接隔離證據。
- [ ] JSON、Python、TypeScript、Rust contract checks 與 Linux desktop build 有
      observed result；缺少 Rust/Tauri evidence 時維持 `Blocked`。若使用者日後要
      改變這項成功條件，先明確變更目標並 repair plan，再繼續執行。
- [ ] 沒有新增 dependency、persistent format、queue/concurrency system、
      real-data mutation 或 out-of-scope trust bypass。
- [ ] High-risk trust-boundary diff 經 fresh context 或等價 independent
      deterministic review，findings 已修正或由使用者明確接受。
- [ ] `git diff --check` 通過，實際 diff 只包含直接必要 scope；未進行 commit、
      remote Git、deploy 或 release。
