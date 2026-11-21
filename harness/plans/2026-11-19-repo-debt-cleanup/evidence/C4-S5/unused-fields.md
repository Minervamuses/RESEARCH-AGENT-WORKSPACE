# C4-S5 無用欄位（S008）

- **日期**：2026-11-22

## 1. 「無 producer／無讀者」證據

以 `grep -rn` 搜尋 `app/agent`、`app/skills`、`app/rag`、`app/desktop/src`、`app/desktop/src-tauri/src`、`app/tests`、`app/desktop/tests`（排除 contract 本身）：

| 欄位 | 讀者／producer | 處置 |
|---|---|---|
| contract 頂層 `messageTypes` | 0 筆 | 刪除。 |
| contract 頂層 `documentContextSchema` | 0 筆（三端都不讀；`submittedContextSchema` 與各方法 params 內有自己的 document context 規則） | 刪除。 |
| `session.turn.documentOperations` | 只有 `protocol.py` 的驗證迴圈與 TS `TurnCompletedDto`／`DocumentOperationDto`；`service.py` 從不產生這個欄位 | 刪除 contract 欄位、Python 驗證、TS 欄位與 `DocumentOperationDto`。 |
| `methods[].requiredParams` | 只有測試讀；Python 解譯器讀 `params[].required`（`_validate_object_schema`），TS 自 C3-S2 起讀 `params[].required`，Rust 自 C3-S4 起不讀 params | 刪除 27 個方法的這個欄位；測試改用由 `params[].required` 推導的 `_required_params()`。 |
| `methods[].operation` | 只有測試讀（「destructive 必須帶 `previewId`」） | 刪除欄位與只為它存在的兩個斷言（Python、TS）。 |
| approval operation enum 的 `extensions.apply` | 沒有 producer；extension 安裝核准實際送出 `extension.install`（`service.py` `_require_operation_approval("extension.install", …)`），enum 已有這個值 | 從 contract enum、TS `ApprovalRequiredDto.operation` 聯集與 `trust.tsx` 的標籤表刪除 `extensions.apply`。 |
| `candidateId`（tool event data 與 `toolSummaries` 項目） | 沒有 producer（agent 中只有 `protocol.py` 的驗證） | 從 `toolEventDataKeys`、`session.turn.toolSummaries.items`、Python 驗證與 TS `ToolSummaryDto` 刪除；fixture `tool-finished-event` 的 `candidateId` 一併刪除（仍是合法的 tool event）。 |

## 2. 測試退役紀錄

| 被刪的斷言 | 它保護的行為（或已刪除的細節） | 留下的證據 |
|---|---|---|
| `test_desktop_protocol_contract.py::test_protocol_manifest_safety_invariants` 中 `requiredParams == params[].required` 與 destructive 帶 `previewId` | 兩個已刪除的重複欄位 | 必填參數只剩 `params[].required` 一個來源；同測試其餘安全不變量保留。 |
| `protocol.test.ts`「contract method names are unique…」中 destructive 帶 `previewId` 的迴圈 | 已刪除的 `operation` 欄位 | 同測試的唯一性與禁止方法斷言保留。 |
| 三個測試中 `method["requiredParams"] == [...]` | 已刪除的欄位 | 改為 `_required_params(...)`，斷言的必填清單不變。 |

## 3. 錯誤碼

見 `error-codes.md`：25 個都有 producer，未移除。

## 4. 檢查結果

- `pytest tests/test_desktop_*.py tests/test_project_permissions.py tests/test_inline_skills.py tests/test_extension_user_journey.py`（沙箱外）：548 passed。
- `npx tsc --noEmit`、`npm test`（224 pass）、`npm run build`（通過）。Rust 在 C4-S6 重跑。
