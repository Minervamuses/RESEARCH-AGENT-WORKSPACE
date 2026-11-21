# C2-S8 前端小項目與 `.error-text` 驗證紀錄

- **日期**：2026-11-21
- **涵蓋項目**：S073、S074、S075、S076、S092、缺陷 #2

## 1. 測試退役與新增紀錄

| 測試 | 處置與保護的行為 | 留下的證據 |
|---|---|---|
| `app/desktop/tests/conversations.test.ts` 的 `"new conversations delegate the MCP default to the backend"` | 退役（S074）：只測試已刪除的 `sessionCreateParams("local")` 回傳 `{ projectId: "local" }` | `session.create` 不傳 `loadMcp` 時由後端採預設值的行為由協定 fixture `session-create-whitelisted-options` 與 Python `tests/test_desktop_conversations.py` 覆蓋 |
| `app/desktop/tests/answer_stream.test.ts` 中對 `conversationInteractionState(state).createDisabled`／`selectDisabled`／`controlDisabled` 的欄位比較 | 改寫（S073）：該三個欄位恆等於 `turnActive`，已隨 S073 移除 | 保留 `turnActive` 與 `sendDisabled` 全部斷言 |
| `app/desktop/tests/backend.test.ts` 新增 2 支 `planBackendSnapshotTransition` 純函式測試 | 新增（S075）：重啟後 generation 改變（保留選取與草稿、重設過期 catalog、拒絕舊 generation）與 crash（清除暫態 UI 但保留當前 generation catalog） | `npm test` 330 passed |

## 2. 產品邊界紀錄

- `planBackendSnapshotTransition`／`applyBackendSnapshot` → 後端意外結束（crash）或使用者觸發重啟（restart）導致 lifecycle／generation 改變 → 支援的正常使用（僅將 `App.tsx` 原有的四處重複處理收斂為單一純函式與單一 callback，未新增任何鎖或並行控制）。

## 3. 加入 C10 GUI 手動檢查清單的項目

- Stop 失敗訊息（核准對話框內 `.error-text`）與 source editor 問題訊息（`DocumentEditor` 內 `.error-text`）以錯誤色（`#843c38`）顯示。
- 後端重啟（Restart）與意外結束（Crash）後的畫面狀態、選取對話與未送出草稿恢復行為與之前相同。
