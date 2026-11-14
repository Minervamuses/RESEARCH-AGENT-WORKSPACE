# K4 同回合編輯結果不累積全文

- **後置條件**：已用證據回答「同一回合的下一次編輯需不需要新全文」，依結論縮減 `document_edit` 存檔成功時交給模型的結果；連續編輯（含凍結引用與多 skill 連續編輯）不壞；修改後量測已記錄。
- **涵蓋**：G8；G6 的修改後數字。
- **相依**：K2。修改後的量測（K4-S3）需要 K3 完成，才能和 K3 的數字一起對照。
- **輸入**：PLANS「基線」的編輯結果一節。

## 要回答的問題（K4-S1 的出口）

> 同一回合內，模型要做下一次 `document_edit` 時，需要知道哪些東西才能寫出正確的 `replacement_text`？

已知事實（讀碼）：`replacement_text` 只取代一個範圍；凍結引用的工作範圍由伺服器端 `_advance_document_working_context` 跟著前一次成功編輯移動；多 skill 提示（`agent/skills/runtime.py` 約第 66 行）告訴模型「結果含已存檔的全文與更新後的選取」。

依證據選一個出口，記錄在 build-log：

- **出口 A（縮成狀態＋受影響範圍）**：伺服器端已追蹤範圍，模型只需要知道狀態、路徑、新 `editorRevision`、更新後的範圍（行號、UTF-16）與該範圍更新後的文字。採用時同步修改 `runtime.py` 的多 skill 提示，讓它描述新的結果內容。
- **出口 B（只有最新一次結果帶全文）**：某些情形確實需要範圍外的文字（例如下一個請求針對的是另一段、而模型手上沒有該段最新文字）。則保留最新一次成功結果的全文，較早的同回合結果在送進模型前縮成出口 A 的形式。
- 兩者都不可行時，記為 Blocked 並說明原因；不得為了減少 token 而讓連續編輯出錯。

不論哪個出口，非 `saved` 的結果（`conflict`、`failed`、`cancelled`）原有的診斷資訊（例如 `candidateText`、`currentDiskText`、`issue`）保留，因為模型與使用者需要它們處理衝突。前端或協定看到的結果不改；縮減只發生在 `_run_desktop_document_edit` 交給模型的回傳值，而且兩條回傳路徑（重播 `existing.result` 與一般回傳）都要縮減。`candidate.result`、`document.apply` 等回傳給前端的結果保持完整。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| K4-S1 | **回答問題**：讀 `_run_desktop_document_edit`、`_advance_document_working_context`、凍結引用範圍推進、多 skill 提示與既有測試（例如 `test_same_turn_reference_edits_keep_prior_saved_text_and_utf16_ranges`），列出每種連續編輯情境（同一當前文件連續兩次、兩個凍結引用依序、多 skill「先 A 再 B」）下一次編輯需要的資訊；逐一確認 PLANS 基線列出的測試檔中，哪些斷言解析的是交給模型的工具結果（例如 `tests/test_inline_skills.py` 約第 93 行的 `result["sourceText"]`），哪些解析的是前端結果；選出口並寫理由 | build-log 有情境表、受影響的測試斷言清單與結論；本步不改產品程式碼 |
| K4-S2 | 依出口實作，並補測試 | 新測試：同一回合連續三次編輯，模型看到的工具結果中全文副本數符合出口的預期（A：0 份；B：只有最新一份）；每次編輯後磁碟內容與預期逐位元組相同；第二、三次編輯的範圍正確（含中文與 emoji 的 UTF-16 位移）；`conflict`／`failed` 結果的診斷欄位仍在；重播路徑回傳的結果同樣是縮減後的形式；前端拿到的結果仍有完整 `sourceText`。K4-S1 清單中解析模型工具結果全文的既有斷言（至少 `tests/test_inline_skills.py` 約第 93 行）改寫為：檢查狀態為 `saved`、更新後範圍內的文字含編輯後的段落、`editorRevision` 前進，並在出口 B 時檢查只有最新一次帶全文；改寫理由記入 build-log。其餘既有 `tests/test_desktop_document_service.py`、`tests/test_inline_skills.py`、`tests/test_skill_runtime.py` 測試不改且通過 |
| K4-S3 | 量測修改後的數字 | 以 `DOCUMENT_BUDGET_REPORT=<計劃>/evidence/K4-S3/after.json` 重跑 15 回合測試，把 before、after-history、after 三組數字（含連續兩次編輯那一回合的工具結果字元數）寫成對照表進 build-log |

各步驟各自 commit。

## 交付給後續階段

出口決定與理由、測試、三組量測對照（K8 寫進最終彙報）。
