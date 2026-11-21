# C4-S6 階段收尾：contract 詞彙統計

- **日期**：2026-11-22

## 1. 完整檢查（最後程式狀態）

| 檢查 | 結果 |
|---|---|
| `pytest`（`app/`，沙箱外） | 1798 passed, 2 warnings in 54.23 s |
| `npm test` | 224 pass, 0 fail |
| `npm run build` | 通過 |
| `cargo test --locked`（沙箱外，Conda `app`；contract 以 `include_str!` 編入，變動後重新編譯） | 35 passed, 0 failed |

## 2. contract 統計（以腳本讀 `contract.json`）

- 方法：27 個（PLANS 目標的 25 個，加上 C6 負責的 `project.list`、`session.retry_registration`）：
  `runtime.diagnostics`、`project.list`、`workspace.select`、`document.open`、`document.save`、`document.apply`、`session.create`、`session.list`、`session.select`、`session.delete`、`session.rename`、`session.retry_registration`、`session.transcript`、`session.turn`、`session.set_thinking`、`session.set_permission`、`session.stop`、`extensions.preview`、`extensions.apply`、`approval.resolve`、`runtime.shutdown`、`bibliography.inspect`、`bibliography.render`、`bibliography.set_style`、`bibliography.remove`、`bibliography.add`、`bibliography.export`
- request event：8 個：`request.started`、`turn.accepted`、`stage.changed`、`tool.started`、`tool.finished`、`tool.failed`、`document.proposed`、`approval.required`
- process event：4 個（不變）
- 錯誤碼：25 個（C4-S5 確認都有 producer）

## 3. C4 移除清單比對（腳本）

- C4 負責移除的 14 個方法（10 個 `knowledge.*`、`session.status`、`session.shutdown`、`extensions.status`、改名前的 `session.set_bash_permission`）：仍存在 0 個。
- C4 負責移除的 12 個 event：仍存在 0 個（`requestEvents` 與 `eventDataSchemas` 都不含）。
- C4 負責移除的欄位（`streamKind`、`chunkCount`、`ollamaReachable`、`ollamaModelAvailable`、`bashPermissionMode`、`documentOperations`、`candidateId`、`requiredParams`、`operation`、`messageTypes`、頂層 `documentContextSchema`）：在 contract 中出現 0 次。
- approval enum 不含 `extensions.apply`。

## 4. C4 驗收

- C4-S3、C4-S4 的 grep 都為 0。
- contract 中沒有本階段負責移除的項目；request event 是 8 個。
- 四套測試通過。
- GUI 清單新增：runtime 細節不再顯示 Ollama 兩列（C4-S3）；權限控制項名稱與行為不變（C4-S4）。
