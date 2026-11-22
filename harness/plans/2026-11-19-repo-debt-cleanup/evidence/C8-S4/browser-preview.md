# C8-S4 刪除 browser preview（U5、S078）

- **日期**：2026-11-22
- **產品邊界**：桌面 app 只在 Tauri 內執行；不在 Tauri 內時走一般的「後端無法連線」錯誤路徑，不另做橫幅或假資料路徑（R2）。

## 變更

| 位置 | 刪除 |
|---|---|
| `src/backend.ts` | `BackendUiState.browserPreview` 欄位與初始值、`{ type: "browser-preview" }` action、reducer 的 browser-preview 分支（`BROWSER_PREVIEW` 錯誤與 degraded 階段）、`SafeUiError.source` 的 `"preview"` |
| `src/App.tsx` | `isTauriRuntime()`；啟動 effect 開頭「不在 Tauri 內就 dispatch browser-preview」的分支；`canStart`、`canRestart`、`canShutdown`、`canCreateSession`、`canManageConversations`、`canDeleteConversation` 的 `!state.browserPreview &&`（6 處）；「Preparing your research workspace」空狀態條件中的 `&& !state.browserPreview` |

不在 Tauri 內時：啟動 effect 呼叫 Tauri 的 `listen(...)` 會拋錯，該 effect 既有的 `catch` 以 `action-failed` 與 `workspaceError(error)` 顯示一般錯誤；Start 等按鈕依一般的 lifecycle 條件判斷。沒有新增路徑。

C8-S1 的盤點顯示 browser preview 沒有任何測試，所以沒有需要刪除的測試。

## 檢查

- `grep -rn "browserPreview\|isTauri\|__TAURI\|browser-preview\|BROWSER_PREVIEW" app/desktop/src app/desktop/tests`：0（剩下的 `"preview"` 命中都是擴充預覽與引用面板的預覽，與 browser preview 無關）。不需要保留任何建立 backend client 的判斷：backend client 本身不檢查執行環境。
- `npm test` 228 pass、`npm run build` 通過。
- GUI 清單新增：在 Tauri app 中啟動、Start／Restart／Shut down 與 New conversation 按鈕的可用狀態照舊。
