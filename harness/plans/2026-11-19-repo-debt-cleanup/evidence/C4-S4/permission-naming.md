# C4-S4 權限命名（U8＋P2、S016）

- **日期**：2026-11-22

## 1. 改名對照

| 層 | 原本 | 改為 |
|---|---|---|
| 方法 | `session.set_bash_permission` | `session.set_permission` |
| 參數 | `mode` | `permissionMode` |
| 線上欄位（`session.create`、`session.select`、`session.set_permission` 的 result） | `bashPermissionMode` | `permissionMode` |
| Python handler | `_session_set_bash_permission` | `_session_set_permission`（錯誤訊息改為 `Unknown permission mode`） |
| `DesktopService` 欄位／唯讀屬性 | `_bash_permission_mode`／`bash_permission_mode` | `_permission_mode`／`permission_mode` |
| 對話控制快照（記憶體內的 `_ConversationControlSnapshot`） | `bash_permission_mode` | `permission_mode` |
| TS 型別 | `BashPermissionMode`、`SessionBashPermissionSetDto` | `PermissionMode`、`SessionPermissionSetDto` |
| TS 元件與函式 | `BashPermissionControl`（含 props 型別）、`reconcileBashPermissionAck`、`updateBashPermissionMode` | `PermissionControl`、`reconcilePermissionAck`、`updatePermissionMode` |
| fixtures | `session-set-bash-permission-bypass`、`session-set-bash-permission-invalid-mode` 與其中的方法、參數、欄位 | `session-set-permission-bypass`、`session-set-permission-invalid-mode` |
| 測試名稱 | `test_*bash_permission_mode*`（desktop 測試 7 個） | `test_*permission_mode*` |

不變：

- 持久化的 `permissionMode`（`agent/conversations/models.py`、`submittedContext.permissionMode`）未改動，`git diff --stat -- app/agent/conversations` 為空。
- `agent/tools/bash.py` 與 `tests/test_tool_access_matrix.py::test_skill_switch_does_not_change_bash_permission_mode`（測 bash 工具本身的核准閘）屬於 bash 工具的命名，不在範圍內。
- 線上值（`ask`、`bypass`）與行為不變。

`grep -rn "bashPermission\|set_bash_permission\|BashPermissionControl" app/agent app/desktop/src app/desktop/tests app/desktop/protocol`：0 筆。

## 2. 檢查結果

- `pytest tests/test_desktop_*.py tests/test_project_permissions.py tests/test_inline_skills.py tests/test_tool_access_matrix.py tests/test_conversation_repository.py tests/test_session_persistence.py tests/test_conversation_archive_access.py`（沙箱外）：599 passed。其中讀取既有對話檔的測試照常通過。
- `npm test`：224 pass, 0 fail（含 DTO 一致性檢查）；`npm run build`：通過。
- 沒有刪除測試。

## 3. GUI 清單項目

- 權限控制項的名稱與行為不變：切換 Ask／Bypass 後送出回合，核准行為與切換前一致；切換對話後權限設定照常保存在記憶體中。
