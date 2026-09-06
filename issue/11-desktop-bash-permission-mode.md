# Desktop Bash 權限模式設定

## Issue 定位

- 類型：Desktop trust UX／Bash execution policy。
- 優先度：高。
- 狀態：Open；實作前仍需由使用者決定 permission mode 的生命週期。
- 範圍：只處理 Bash tool 的逐次批准模式；不改變 Extension apply、MCP binding 或其他信任流程。

## 使用者需求

Desktop 增加一個權限設定 button，至少提供兩個互斥選項：

- **維持現況（預設）**：每一個 Bash command 都顯示 approval dialog，由使用者逐次允許或拒絕。
- **`ByPassPermission`**：使用者明確選取後，所有 Bash command 都自動允許，不再顯示逐次 approval dialog。

## 決策優先權

這是 2026-09-06 的新使用者決策，明確 supersede 舊 Desktop completion plan 中「不提供 always-approve／remembered approval」的歷史 non-goal。舊 plan 可繼續作為當時逐次批准流程的實作證據，但不得用來否決本 issue；新模式實作完成前，現行逐次批准仍是唯一行為。

## 已確認的現況

- `app/agent/tools/bash.py` 的現行契約是每次呼叫都要求批准；非互動環境預設拒絕。
- Desktop backend 會在每個 Bash call 建立一次 `approval.required`，等待 `approval.resolve`，逾時或 context 不符便拒絕。
- React 目前只在收到該 event 時顯示 `ApprovalDialog`；沒有 permission settings button，也沒有自動批准模式。

## 必須保留的邊界

- 新安裝／沒有既有選擇時一律以「維持現況」為預設，不得隱性進入 bypass。
- `ByPassPermission` 只改變 Bash tool 的逐次批准；不得順便批准 Extension apply、MCP binding 或其他信任流程。
- UI 必須讓使用者看得出目前是哪個模式。
- 切換到 `ByPassPermission` 後的 Bash 呼叫不可再卡在等待 approval；切回預設後，下一次 Bash 呼叫立即恢復逐次詢問。

## 實作前必要決策

使用者需另行選定 `ByPassPermission` 的生命週期：只限目前 conversation、只限目前 backend generation（restart 後重設），或作為 app-level setting 持久化。本輪只記錄這個未決選擇，不擅自指定；決定前不得開始會固定 persistence 語意的實作。

## 驗收方向

- Fresh app/session 顯示並使用逐次詢問模式。
- `ByPassPermission` 下連續多個 Bash calls 都直接執行，不產生 `approval.required`；切回預設後再次逐次詢問。
- Extension／MCP approval 行為完全不受影響。
- 在使用者選定生命週期後，conversation switch／backend restart／app restart 的預期值須各自寫成明確測試，且 UI 顯示與 Python 實際模式一致。
- 測試使用 injected fake command runner，不執行破壞性命令。

## 非目標

- 不移除現有逐次 approval 流程；它仍是預設且必須保留。
- 不把 `ByPassPermission` 擴張成全系統無條件信任模式。
- 本 issue 只記錄需求，本輪不修改 GUI、protocol 或 Bash runtime。

## 主要參考檔案

- `app/agent/tools/bash.py`
- `app/agent/desktop/service.py`
- `app/agent/desktop/protocol.py`
- `app/desktop/protocol/v1/contract.json`
- `app/desktop/src/App.tsx`
- `app/desktop/src/trust.tsx`
- `app/tests/test_bash_tool.py`
- `app/tests/test_desktop_service.py`
- `app/tests/test_desktop_protocol_contract.py`
- `app/desktop/tests/`
