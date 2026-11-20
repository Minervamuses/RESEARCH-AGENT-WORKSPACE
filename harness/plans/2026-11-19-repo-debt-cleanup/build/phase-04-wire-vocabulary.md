# C4 — 縮小線上詞彙（U2、U7、U8、P1–P3）

- **完成後的狀態**：
  - 方法只剩 [PLANS.md](../PLANS.md#目標詞彙) 列出的那些，但還不扣除 C6 負責的 `session.retry_registration` 與 `project.list`。
  - request event 剩 8 個。
  - `streamKind`、`chunkCount`、Ollama 欄位與 S008 的無用欄位都不存在。
  - 權限在線上統一叫 `permissionMode`，方法叫 `session.set_permission`。
  - 沒有 producer 的錯誤碼已移除。
- **涵蓋**：G2
- **相依**：C3
- **輸入**：
  - [GOALS.md](../GOALS.md) 的 U2、U7、U8、P1–P3、A3。
  - [稽核原文](../context/repo-debt-audit-2026-11-19.md)的 S006–S010、S016、S036。

C3 之後，每項移除都只需改 `contract.json`、Python、TS（DTO、型別對照、呼叫端與 UI）、fixtures 與測試。漏改 DTO 時，C3-S3 的 DTO 一致性檢查會失敗。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| C4-S1 | **U2：刪 10 個 `knowledge.*` RPC。** GOALS A3 已確認：斜線指令 `/init /ingest /sync /prune` 仍以 `knowledge.*` 名稱做核准、錯誤對照與部分寫入判斷，所以**只刪 RPC 專用的符號**。<br>• **刪除**（以 `3b6cfd8` 的位置為線索，用符號重新定位）：<br>　- dispatch 表中 10 個 `"knowledge.*"` 項目（約 484–493 行）；<br>　- handler `_knowledge_overview` 到 `_knowledge_prune_apply`（約 3665–3882 行）；<br>　- 只被這些 handler 使用的 `_hit_dto`；<br>　- RPC 專用的 `self._prune_previews` dict 與它在關機時的 `clear()`（約 414、3520 行）；<br>　- contract 的 10 個方法、TS DTO、fixtures；<br>　- `test_desktop_service.py`（8 個）與 `test_project_permissions.py`（3 個，其中 `:168` 是 S036）中只測 RPC 的測試。<br>• **保留**：<br>　- `_map_exception` 的 knowledge 分支與 `_KNOWLEDGE_MUTATIONS`；<br>　- 錯誤碼 `OLLAMA_UNREACHABLE`、`OLLAMA_MODEL_MISSING`、`BUSY_KNOWLEDGE_MUTATION`；<br>　- `_knowledge_count`、`_knowledge_string_items`、`_knowledge_diff_paths`；<br>　- `_knowledge_active`、`_knowledge_operation`；<br>　- `_PrunePreview` 類別與 `_composer_prune_preview`；<br>　- `DesktopKnowledgeOperations`；<br>　- contract approval operation enum 中的 `knowledge.*` 值，以及 `trust.tsx` 約 329–331 行的標籤。<br>• 每個刪除的符號在刪除前 grep 一次，確認沒有 RPC 以外的呼叫者，並把結果存證。 | • desktop 測試通過。<br>• 測試 `/init /ingest /sync /prune` 斜線指令與 `rag_*` 工具的模組照常通過，包括核准與錯誤對照。<br>• contract 的 `methods` 中沒有 `knowledge.` 開頭的方法；approval enum 仍有 4 個 `knowledge.*` 值。<br>• `npm test`（含 DTO 一致性檢查）、`npm run build` 通過。<br>• 被刪測試有退役紀錄。 |
| C4-S2 | **P1：移除 `session.status`、`session.shutdown`、`extensions.status` 的 RPC 註冊。**<br>只刪 RPC 層：dispatch、contract、TS 型別、fixtures 與只測 RPC 的測試。內部函式若仍被 `workspace.select`、`session.delete` 等使用就保留。 | desktop 測試、`npm test` 通過；grep 確認內部函式仍有呼叫者，或已無呼叫者而一併刪除。 |
| C4-S3 | **U7：死 event、streaming 殘留、Ollama 欄位。**<br>• 從 contract 與 TS 刪 12 個 event：`request.progress`、`knowledge.progress`、`shutdown.progress`、`collecting.started`、`collecting.completed`、`tagging.started`、`tagging.folder_completed`、`metadata.written`、`writing.started`、`writing.file_completed`、`ingest.completed`、`ingest.failed`。<br>• fixtures 中的 `ingest-progress-*` 刪除；拿 `request.progress` 當泛用 event 的 3 個 trace fixture 與 1 個 message fixture，改用仍存在的 event，例如 `stage.changed`。<br>• 端到端刪 `streamKind`、`chunkCount`（稽核 S009 列出的位置）。`test_desktop_answer_stream.py` 與 `desktop/tests/answer_stream.test.ts` 中仍有價值的斷言（例如「答案只出現在 completed、persisted result」）併入一般 turn 測試；其餘刪除。<br>• 刪 `ollamaReachable`、`ollamaModelAvailable`（`service.py` 約 852–853 行、contract、TS 與 GUI 的顯示列）。 | • pytest desktop 與 protocol 模組、`npm test`、`npm run build` 通過。<br>• grep `streamKind\|chunkCount\|ollamaReachable\|ollamaModelAvailable` 在 `app/agent`、`app/desktop/src`、`app/desktop/tests`、`app/desktop/protocol` 為 0。<br>• 加入 GUI 清單：runtime 細節不再顯示 Ollama 列。 |
| C4-S4 | **U8＋P2：權限命名。**<br>• 線上欄位 `bashPermissionMode` 與參數 `mode` 改為 `permissionMode`；方法 `session.set_bash_permission` 改為 `session.set_permission`。<br>• Python handler 名稱同步改，TS 元件 `BashPermissionControl` 改為 `PermissionControl`。<br>• 持久化的 `permissionMode`（`conversations/models.py`）不變，對話檔不動。<br>• `agent/tools/bash.py` 內部專指 bash 工具的命名不在範圍內。`DesktopService` 內部的 `_bash_permission_mode` 欄位改名為 `_permission_mode`。 | • 全部相關測試通過。<br>• grep `bashPermission\|set_bash_permission\|BashPermissionControl` 在上述四個目錄為 0。<br>• 讀取既有對話檔的測試照常通過，證明對話檔未受影響。 |
| C4-S5 | **S008＋P3：無用欄位與錯誤碼。**<br>• 刪 `messageTypes`、頂層 `documentContextSchema`（若三端都不讀）、`session.turn.documentOperations` 及其驗證與 `DocumentOperationDto`、`methods[].requiredParams`、只有測試讀的 `methods[].operation`，以及只為這些欄位存在的測試（例如「destructive 必須帶 `previewId`」）。<br>• `methods[].requiredParams` 刪除前，確認 Python 與 TS 的解譯器都改讀 `params[].required`。<br>• 修正 approval operation enum：`extensions.apply` 改為實際送出的 `extension.install`。<br>• `candidateId`：先確認沒有 producer，再從 contract 與 Python（`protocol.py` 約 342 行）刪除。<br>• P3：對每個錯誤碼 grep 它在 `app/agent`、`app/skills`、`app/rag` 與 Rust 的 producer，沒有 producer 的就移除。清單寫入 `evidence/C4-S5/error-codes.md`。C4、C5、C6 都完成後，在 C10-S0 再複查一次。<br>• 經由 `_map_exception` 或斜線指令產生的錯誤碼都算有 producer，例如 `OLLAMA_*` 與 `BUSY_KNOWLEDGE_MUTATION`。 | 三端測試通過；evidence 列出每個被刪欄位與錯誤碼的「無 producer」證據。 |
| C4-S6 | **階段收尾。** 完整 pytest（沙箱外）、`npm test`、`npm run build`、`cargo test --locked`（沙箱外）。<br>Rust 不受詞彙影響，但若 C3 採用 `include_str!` 讀 contract，contract 變動後仍要確認 Rust 編譯與測試正常。<br>重新統計 contract 的方法、event、錯誤碼數並存證。 | 全部通過；contract 中已沒有 C4 負責移除的方法、event 與欄位（以腳本比對本階段的移除清單）；request event 是 8 個。<br>方法總數依 C6 是否已完成而定（27 或 25），本階段不以總數驗收；最終的完整清單比對在 C10-S0。 |

## 驗收

- 上述 grep 都為 0。
- contract 中沒有本階段負責移除的項目；request event 是 8 個。
- 四套測試通過。
- GUI 清單新增 Ollama 列消失、權限控制項名稱與行為不變這兩項。

## 交給後續階段

contract 只剩有人使用的詞彙。C5、C6 各自再移除 `citationOutputPath`、registration 欄位、`session.retry_registration` 與 `project.list`。
