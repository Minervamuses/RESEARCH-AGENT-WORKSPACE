# C2-S11 錯誤訊息來源盤點與出口遮蔽紀錄（U15、S089、缺陷 #3）

- **日期**：2026-11-21
- **涵蓋項目**：U15、S089、缺陷 #3

## 1. UI 可見錯誤字串來源盤點

### Python（桌面協定後端）

所有經協定送往宿主的錯誤訊息皆經過 `app/agent/desktop/protocol.py::bounded_error_message`：

| 出口位置 | 協定訊息類型 | 字串來源 |
|---|---|---|
| `app/agent/desktop/protocol.py::failure_result` | `result`（`ok: False` 的 `error.message`） | 1. `_map_exception` 回傳的固定分類字串（必要時附加 `incident_reference`，僅含 incident ID、例外型別名與本地 log 路徑）。<br>2. `service.py::dispatch` 直接將 `str(exc)` 轉為 `DesktopServiceError` 的動態例外：`DocumentError`、`SkillSelectionError`、`CatalogError`、`SlashCommandError`。<br>3. `service.py::_bibliography_error` 轉出的 `LibraryError`、Pandoc／`bime_word` 匯出錯誤等動態字串。<br>4. `DesktopService` 各處明確建立的 `DesktopServiceError` 固定提示文字。<br>5. `server.py::_handle_request` 未捕捉例外轉為固定 `"The desktop backend encountered an internal error. "` 加 `incident_reference`。 |
| `app/agent/desktop/server.py::_protocol_failure` | process event `backend.protocol_error`（`data.message`） | `ProtocolError`（解析失敗、框架不符、重複 `requestId` 等）的 `str(error)`。 |
| `app/agent/desktop/server.py::_best_effort_close` | process event `backend.shutting_down`（`status="shutdown_failed"` 的 `data.message`） | EOF 關閉時 `runtime.shutdown` 拋出 `ProtocolError` 的 `str(exc)`（其他未預期例外使用固定字串）。 |

### Rust（`app/desktop/src-tauri/src/backend.rs`）

- 盤點全檔所有 `BridgeError::new`、`BridgeError::protocol()`、`BridgeError::stopped()` 與 `picker_error(...)`：全部皆為固定常數字串（唯一帶入的動態值是 `child_exited` 中本地診斷目錄路徑 `directory.display()`，與 Python `incident_reference` 同屬本地日誌路徑提示）。
- 子行程的 `stderr` 只寫入本地 owner-only 日誌檔並把行數／位元組計數放入 snapshot，**絕不轉送**文字內容到 WebView；無效 `stdout` 行亦只映射為固定 `BridgeError::protocol()` 或固定環境錯誤字串。
- 結論：Rust 不轉送未經 Python 的動態輸出，不需修改 Rust 端。

### TypeScript（`app/desktop/src/backend.ts`）

- `normalizeBusinessError`（協定 `ok: false` 業務錯誤）與 `asClientError`（transport／protocol／lifecycle 錯誤）都進入 `normalizeUiError`。
- 原本 `normalizeUiError` 以 `sensitiveMessagePattern = /api[ _-]?key|authorization|bearer|secret|token|traceback/i` 檢查整句訊息，只要命中單字（如 `token`、`secret`）就把整句換成 `"Sensitive backend details were withheld..."`，造成正當錯誤訊息被吞沒。
- 已刪除 `sensitiveMessagePattern` 與整句隱藏分支，只保留控制字元壓縮與 `MAX_UI_ERROR_CHARS` 長度上限。

## 2. 遮蔽規則統一（`agent/diagnostics.py::redact_text`）

- 不另建第二套規則：直接擴充 `agent/diagnostics.py::_SECRET_PATTERNS` 並讓 `install_diagnostic_log` 保存當次已知環境變數憑證清單（`configured_secrets()`），由診斷日誌與 `bounded_error_message` 共用同一份樣式與同一份已知 secret 清單。
- 涵蓋樣式：`api_key=`／`token=`／`secret=`／`password=` 鍵值、`Authorization: Bearer/Basic/Token/...` 標頭值、獨立 `Bearer ...`、`scheme://user:pass@host` URL 帳密、`sk-...`／`ghp_...`／`github_pat_...` 獨立金鑰格式，以及 `mailto:`。
- `bounded_error_message` **先呼叫 `redact_text`，再依 `errorMessageMaxBytes`（4096 UTF-8 bytes）截斷**，確保跨截斷邊界的憑證不會殘留前半段。

## 3. 測試退役與改寫紀錄

| 原測試 | 保護的行為（或已刪除的細節） | 留下的證據 |
|---|---|---|
| `app/desktop/tests/backend.test.ts` `"backend client maps protocol business failures into safe UI errors"` 中的 `assert.doesNotMatch(error.uiError.message, /token/i)` | 測試已依 U15／S089 刪除的 TS 關鍵字整句隱藏行為 | 同測試改名為 `"backend client maps protocol business failures into safe UI errors without hiding legitimate keywords"`，驗證含 `token`、`secret` 的正當業務錯誤原文保留；憑證遮蔽改由 `tests/test_diagnostics.py` 與 `tests/test_desktop_server.py`（真實 `DocumentError` 動態路徑、跨 4096-byte 截斷邊界與 `server.py` 框架錯誤）覆蓋 |

## 4. 加入 C10 GUI 手動檢查清單的項目

- 觸發一個會失敗的文件操作（例如開啟不存在或超界範圍的文件）或書目匯出失敗，確認錯誤訊息完整顯示原文、不被整句替換為 withheld。

## 5. 執行中斷與修正紀錄（續作，2026-11-21）

- **現象**：前一個執行 session 跑 `tests/test_desktop_server.py` 時卡住 40 分鐘以上，session 中止後沒有殘留的測試行程。
- **定位**：以 `timeout` 逐一重跑，確認卡住的是 `test_server_framework_errors_redact_credentials_at_protocol_exit`（`test_diagnostics.py` 8 passed in 0.25 s；該測試 90 s 逾時）。
- **根因（測試缺陷，非產品缺陷）**：測試在 `server.run()` 之前直接呼叫 `server._protocol_failure(...)`，此時 `ProtocolWriter` 的 consumer task 尚未由 `run()` 啟動，`send_line` 永遠等不到 flush 確認。
- **修正（第 1 次聚焦修正，成功）**：測試先呼叫 `writer.start()`（冪等，`run()` 沿用同一個 task）。
- **第二個問題**：`test_dynamic_service_error_redacts_credentials_and_truncates_safely` 的截斷邊界輸入把 key 直接黏在 `xxx…` 後面。`sk-` 樣式的 `\b` 是刻意的，避免把 `risk-assessment`、`desk-top` 這類正常字詞遮蔽，所以黏連的字串不是「獨立金鑰」。改為以空白分隔（`"x" * 4087 + " sk-or-v1-…"`，key 自第 4088 byte 起、跨越 4096 byte 上限）。測試仍驗證「先遮蔽再截斷，不留半段 secret」，斷言未放寬。
- **其他**：`protocol.py` 中段的 `from agent.diagnostics import redact_text` 移到檔頭（`agent.diagnostics` 只依賴 `agent.paths`，無循環 import）。

## 6. 產品邊界檢查

- 錯誤出口遮蔽 → 任何支援流程中的錯誤（文件操作失敗、書目匯出失敗、框架錯誤）送往 WebView 時 → 支援的正常使用（循序使用中的一般錯誤顯示；不是協調或狀態機制，不新增拒絕條件）。

## 7. 檢查結果

- `pytest tests/test_desktop_*.py tests/test_diagnostics.py`（沙箱外）：509 passed in 21.62 s。
- `npm test`：330 passed，0 failed。
- `npm run build`：通過（built in 813 ms）。
- `grep -rn "sensitiveMessagePattern" app/desktop`（排除 `node_modules`、`dist`、`target`）：0 筆。
- 未改 Rust（第 1 節盤點結論），C2-S12 不需重跑 cargo。
