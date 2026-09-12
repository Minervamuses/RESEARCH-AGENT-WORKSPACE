# Issue 03 — Desktop Bash 權限模式：目標

## Purpose and Background

Desktop 目前只有逐次批准模式：可顯示的 Bash request 會建立
`approval.required`，等待使用者透過 `approval.resolve` 批准或拒絕；不安全或
不完整的 approval context 則直接拒絕。`issue/03-desktop-bash-permission-mode.md`
要求加入使用者可見的 `ByPassPermission` 選項，讓使用者明確選取後，該
conversation 的 Bash 呼叫在目前 backend generation 內不再逐次詢問。

2026-09-06 的使用者決定已固定生命週期，並取代原 issue 中「實作前仍需決定」
的記載：

| 情境 | 權限模式 |
|---|---|
| Fresh conversation | 逐次詢問（`ask`） |
| Conversation A 開啟 bypass | A 自動允許 Bash |
| 從 A 切到 B | B 維持逐次詢問 |
| 從 B 回到 A | 恢復 A 的 bypass |
| Backend 或 App restart | 所有 conversation 回到逐次詢問 |

## Desired Outcomes

- Desktop 使用者能看見並切換目前 conversation 的 Bash permission mode。
- Python Desktop backend 是唯一的 permission-policy owner；React 只顯示
  backend 已確認的狀態。
- `ask` 保留既有逐次批准與 fail-closed 邊界；`bypass` 直接允許有效 active
  turn 內的 Bash 呼叫，不建立 approval event，也不等待 approval resolution。
- Mode 只存在於目前 `DesktopService` generation 的 per-conversation memory；
  不寫入 canonical conversation、app settings 或其他持久格式。

## Success Conditions

- [ ] Fresh backend generation 中建立或首次選取的 conversation 都由 `ask` 開始，
      UI 與 Python snapshot 一致。
- [ ] A 切到 `bypass` 後，至少兩個連續 Bash 呼叫都只經 injected fake runner
      各執行一次，且不產生 `approval.required`、不呼叫 `approval.resolve`。
- [ ] A 切回 `ask` 後，下一個可顯示的 Bash request 立即恢復既有 dialog、
      correlation、timeout、single-use resolve 與拒絕行為。
- [ ] A 設為 `bypass`、切到 fresh B、再回 A 時，B 是 `ask`，A 恢復
      `bypass`。
- [ ] Session/backend shutdown、新 backend generation 及 App restart 後，
      重新建立或選取任何 conversation 都是 `ask`。
- [ ] Active turn 或 pending approval 期間無法切換 mode；已 staged 的 command
      不會被追溯自動批准。
- [ ] UI 只在通過 protocol validation、backend generation 未變且
      `sessionId` 相符的成功 ACK 後更新；失敗或 stale ACK 不改變顯示值。
- [ ] Extension apply、MCP binding approval、CLI/non-Desktop Bash approval
      不讀取這個 mode，既有行為維持不變。
- [ ] Python、JSON contract、TypeScript 與 Rust 對新增 method、enum、snapshot
      field 及 setter result 完全一致。
- [ ] 所有 command-execution 測試使用 injected fake runner，不執行真實或
      破壞性 shell command。

## In Scope

- Desktop Bash 的 `ask`／`bypass` policy、per-conversation in-memory lifecycle
  與 restart reset。
- 最小 additive protocol-v1 control method、session snapshot field、setter result
  與三語言 validation mirror。
- 現有 conversation controls 中清楚、可存取、互斥的兩模式 UI。
- 直接覆蓋 default、toggle、A→B→A、restart、stale ACK、ask/bypass execution
  與 Extension/MCP/CLI 隔離的最小測試。
- 修正 `app/agent/tools/bash.py` 與 `app/agent/tools/inventory.py` 中會因新模式
  變成不實的「EVERY CALL PROMPTS」說明，同時保留 CLI 實際行為。

## Non-Goals

- 不把 mode 持久化到 conversation JSON、catalog、localStorage、app settings
  或其他新舊資料格式。
- 不讓 `ByPassPermission` 影響 Extension apply、MCP binding、knowledge
  operation 或其他 trust flow。
- 不移除或弱化 `ask` 的 safe-display、expiry、request/turn correlation、
  deny、timeout、replay protection 與 fail-closed 行為。
- 不改變 CLI/non-Desktop Bash 的 TTY 逐次詢問與 non-interactive auto-deny。
- 不新增 queue、worker、serialization layer 或其他 concurrency model。
  Ask 模式同一 model response 的多 Bash pending 限制維持現況；本 issue 不重設計它。
- 不新增 production dependency、protocol version、generic settings framework、
  native Windows runtime、deployment 或 release 流程。
- 不使用 live provider、真實 Bash command 或使用者資料來證明功能。

## Preserved Behavior and Invariants

- Default 永遠是 `ask`；缺少、未知或失敗的狀態不得 fallback 成 `bypass`。
- Backend policy state 與 UI 顯示不得有兩個 owner；React 不得在收到
  `approval.required` 後自行 auto-resolve 來模擬 bypass。
- Bypass 仍須確認呼叫屬於目前 active Desktop turn/request；缺少 active
  ownership 時維持拒絕。
- `_approval_context_is_safe` 是送往 approval UI 的 display gate。`ask` 照舊
  使用；`bypass` 因不產生 UI payload 而略過它，才能符合「所有 Bash command
  自動允許」的已定語意。
- Conversation 切換只有在 target materialization 與 lifecycle 檢查成功後，才
  原子提交 target mode；失敗的 select/create 不得污染目前 conversation。
- 新 conversation、無 snapshot 的 conversation、shutdown 及新
  `DesktopService` 一律回到 `ask`。
- 既有 LangGraph scheduling 不因本 issue 改變。若多個 Bash call 已並行，
  bypass 不得因 `_pending_approval` 而拒絕其中一個，但不承諾執行順序。
- 無論 mode 為何，實際 command runner 的 timeout、cwd、stdout/stderr
  truncation 與 result shape 維持不變。

## Constraints

- **Constraint:** 支援的 runtime 是 WSL/Linux；Conda `app` 與 Poetry 管理
  Python 環境。
  - **Authority:** `AGENTS.md` 與 repository README。
  - **Consequence:** 不使用 native Windows Python、Node 或 Cargo 驗證。
- **Constraint:** 這是 planning-only authoring request。
  - **Authority:** `long-horizon-plan-author` skill 與本次使用者要求。
  - **Consequence:** 本 bundle 不授權 implementation；正式啟動仍需明確批准
    protocol/schema change 與超過三個 production files。
- **Constraint:** 不新增 dependency 或 persistent format。
  - **Authority:** `AGENTS.md` 與本目標的最小範圍。
  - **Consequence:** 使用現有 service snapshot、protocol、React control 與 test
    seams；若證據顯示必須新增，停止並取得新授權。
- **Constraint:** Trust-boundary change 必須以 deterministic fake runner 與
  cross-language validation 證明。
  - **Authority:** Issue 驗收方向與 repository test conventions。
  - **Consequence:** Live shell/provider 結果不能取代必要的 focused tests。

## Known Unknowns and User Decisions

- **User decisions:** 目前沒有尚未決定的產品語意。上方 lifecycle、idle-only
  setter、backend-authoritative UI、無 persistence 與不新增 concurrency model
  已固定。
- **Technical prerequisite:** 2026-09-06 initial base-shell preflight 沒有在 `PATH`
  找到 Cargo/rustc；follow-up 已確認 Conda `app` 內有 Linux Cargo 1.97.1 與
  rustc 1.97.1。
  - **Why it matters:** Rust protocol mirror 可使用既定 Conda runtime 驗證；Tauri
    system build prerequisites 是否完整仍須由實際 build check 判定。
  - **Resolution:** Phase 01 preflight 必須從 Conda `app` 重新確認 Linux Rust
    toolchain，再執行 planned check。若缺少 toolchain/system dependency，不得自行
    安裝；取得新授權前保持 `Blocked`，且缺少必要 Rust evidence 時不得宣告完成。
- **Technical verification:** Repository 沒有現成的 provider-free Desktop
  browser/Tauri end-to-end harness。
  - **Why it matters:** 完整 GUI journey 可能需要 credentialed provider。
  - **Resolution:** 以現有 React/Node checks、protocol validation 與 Python fake
    runner journey 作必要 deterministic evidence；只有在不需 credential、付費
    或真 Bash 時才增加手動 UI 檢查，否則如實記為 unavailable。

## Source Inputs

- `AGENTS.md`
- `issue/03-desktop-bash-permission-mode.md`
- 2026-09-06 使用者確認的 lifecycle 決策
- `app/agent/desktop/service.py`
- `app/agent/desktop/protocol.py`
- `app/agent/tools/bash.py`
- `app/agent/tools/inventory.py`
- `app/desktop/protocol/v1/contract.json`
- `app/desktop/protocol/v1/fixtures.json`
- `app/desktop/src/protocol.ts`
- `app/desktop/src-tauri/src/protocol.rs`
- `app/desktop/src/App.tsx`
- `app/tests/test_bash_tool.py`
- `app/tests/test_desktop_service.py`
- `app/tests/test_desktop_conversations.py`
- `app/tests/test_desktop_fixture.py`
- `app/tests/test_desktop_protocol_contract.py`
- `app/desktop/tests/`
