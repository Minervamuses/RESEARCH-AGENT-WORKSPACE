# C4-S2 移除 `session.status`、`session.shutdown`、`extensions.status` 的 RPC 註冊（P1）

- **日期**：2026-11-22

## 1. 內部函式的呼叫者（刪除前 grep，排除定義行）

| 函式 | 其他引用行 | 處置 |
|---|---|---|
| `_session_status` | 471 | 只有 dispatch 表 → 刪除。 |
| `_session_shutdown` | 480 | 只有 dispatch 表；它只是 `_shutdown_session()` 的包裝 → 刪除。`_shutdown_session` 仍被 `workspace.select`、`session.delete` 與 `runtime.shutdown` 使用，保留。 |
| `_extensions_status` | 481,2078 | 除了 dispatch 表，還被 `/extension-management status` 斜線指令（`_execute_desktop_extension_command`）使用 → 保留，簽名簡化為 `_extensions_status(self)`。 |

`dispatch` 中只為這兩個方法存在的例外條件同步簡化：`_session_closing` 時只放行 `runtime.diagnostics`；`project_operation` 改為所有 `session.*`（原本只排除這兩個方法）；`_workspace_opening` 的放行集合刪除 `session.status`。其他方法的准入結果不變。

## 2. contract、TS、fixtures

- contract：刪除 3 個方法，以及 `session.shutdown`、`extensions.status` 的 `resultDataSchemas`。方法 30 → 27（含 C6 負責的 `project.list`、`session.retry_registration`）。
- TS：`MethodWithoutResultDto` 只剩 `session.set_thinking`；`tests/protocol_types.test.ts` 的 `DTO_EXCEPTIONS` 刪除兩個 method 例外，`METHODS_WITHOUT_RESULT_SCHEMA` 只剩 `session.set_thinking`。
- fixtures：`ordered-request-event-result`、`duplicate-pending-request-id`、`post-terminal-event` 三個 trace 原本拿 `session.status` 當泛用 request，改用仍存在、沒有 result schema 的 `session.set_thinking`（`{"mode": "normal"}`），trace 檢查的排序與關聯規則不變。

## 3. 測試調整（沒有刪除任何測試）

| 位置 | 原本 | 改為 | 理由 |
|---|---|---|---|
| `test_desktop_fixture.py` 7 處、`test_desktop_conversations.py` 1 處、`test_extension_user_journey.py` 1 處 | 以 `session.shutdown` 結束「第一個行程」 | `runtime.shutdown` | 真實 app 結束時送的就是 `runtime.shutdown`，它同樣呼叫 `_shutdown_session()` 並回 `{"status": "stopped"}`。 |
| `test_desktop_service.py` 3 處（取消回合後關閉、關閉時清除 installer、installer 清理衝突的參數化） | `session.shutdown` | `runtime.shutdown` | 同上；衝突時 `runtime.shutdown` 回復 `ready` 並拋出同一個 `SESSION_NOT_READY`。 |
| `test_desktop_conversations.py` 2 處（關閉後重新選取會重建 session） | `session.shutdown` 後繼續使用同一個 service | 直接呼叫保留的內部函式 `_shutdown_session()` | 支援流程中丟棄快取 session 而 service 繼續運作的入口是 `workspace.select` 與 `session.delete`，兩者都呼叫這個函式。 |
| `test_desktop_conversations.py` 回合進行中的忙碌檢查 | 清單含 `session.select`、`session.shutdown`、`runtime.shutdown` | 刪除 `session.shutdown` 一項 | 方法已不存在；另外兩項保留。 |
| `test_desktop_fixture.py` 4 處 `extensions.status` | RPC | `_extensions_status()` | 斷言的 revision、restart 與「不複製 secret」由同一個內部函式產生，也是 `/extension-management status` 的資料來源。 |
| `test_desktop_server.py` 3 個假 service／4 個 request | 以 `session.status` 當廉價方法 | `session.set_thinking`（假 service）或 `runtime.diagnostics`（真 service 的重複 requestId 測試） | 測的是 server 的並行、重複 ID 與晚到 event，與方法無關。 |
| `test_desktop_protocol_contract.py` shutdown schema 測試 | 迴圈檢查 `session.shutdown` 與 `runtime.shutdown` | 只檢查 `runtime.shutdown` | 前者已從 contract 移除。 |

## 4. 檢查結果

- `pytest tests/test_desktop_*.py tests/test_project_permissions.py tests/test_extension_user_journey.py tests/test_extension_*.py`（沙箱外）：628 passed。
- `npm test`：224 pass, 0 fail；`npm run build`：通過。
- `grep -rn '"session.status"\|"session.shutdown"\|"extensions.status"' app/agent app/tests app/desktop/src app/desktop/tests app/desktop/protocol`：0 筆。
