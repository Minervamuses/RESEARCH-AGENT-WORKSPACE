# C2-S10 桌面後端小項目紀錄

- **日期**：2026-11-21
- **涵蓋項目**：S023、S024、S026

## 處置說明

1. **S023（APPLIED）**：`_execute_desktop_extension_command` 只回傳 `SlashCommandResult`，不再回傳被呼叫端丟棄的第二個值；動作名稱（`"status"`／`"preview"`）與參數檢查收斂至 `_desktop_extension_action(parsed)`，避免兩處重複計算且保留 duplicate replay 的 `extensionAction` 回傳。
2. **S024（APPLIED）**：刪除只呼叫一次且無 await 的 `_apply_controls`，直接 inline 到 `_session_select`。
3. **S026（部分套用，附保留理由）**：
   - `DocumentWorkspace.undo`（`app/agent/desktop/documents.py`）：兩次 `self.validate_snapshot(current_snapshot)` 位於同一個 `with self._lock:` 內，中間只讀記憶體中的 `self._undos` 與 `self._saved`，無重讀磁碟或狀態變化，已移除第二次呼叫。
   - `DocumentWorkspace.prepare`（`app/agent/desktop/documents.py:256`）：`_text(candidate["candidateText"], "candidateText")` **保留**。理由：前面雖然檢查過 `sourceText <= MAX_TEXT_BYTES`（1 MiB）與 `replacementText <= MAX_TEXT_BYTES`，但 `_apply_replacement` 會產生新字串 `source[:left] + replacement + source[right:]`（且可能將 `\n` 展開為 `\r\n`），組合後的 `candidateText` 仍可能超過 `MAX_TEXT_BYTES` 上限（例如 700 KiB 原文插入 700 KiB 替換文字會產生 1.4 MiB 文件，導致寫入後超過 `_disk` 1 MiB 讀取上限與協定 `maxBytes`）。因此該檢查並非重複檢查，依 C2-S10 規則保留。

## 測試結果

- `pytest tests/test_desktop_service.py tests/test_desktop_documents.py tests/test_desktop_document_service.py tests/test_extension_*.py`：`234 passed in 11.60s`。
