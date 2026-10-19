# P3 — 模型輸入全文去重，保留完整 frozen snapshot

目標 G3；依賴：無其他階段。共通 [目標](../GOALS.md)／[政策](../PLANS.md)。

## 原始碼與最小寫入範圍

讀 `app/agent/desktop/service.py:2803–2839`、`app/desktop/src/App.tsx:768–784` 與 `app/agent/desktop/documents.py:153–208`。優先只改 service.py 的模型輸入組裝，不修改 wire、submittedContext、檔案儲存或 document permission schema。

規劃中的回合內投影：全文存於唯一 snapshot 表示，背景與每個 reference 指向它；reference 各自保留 ID、選取文字、range、行號及來源／權限語義。這是 prompt 的內部文字表示，不是新持久資料格式。保守相同性鍵可用 `(rootPath, path, editorRevision, diskFingerprint, sourceText)`；不把選取 range 放進全文相同性，不只用 path／磁碟 fingerprint。使用 hash 時仍需明確版本與來源邊界；不建立全域 cache 或對原字串正規化。

## 步驟與驗收

| 步驟 | 工作 | 必須結果 |
|---|---|---|
| P3-S1 | 沿用既有未保存文件＋兩個 paragraph reference fixture，捕捉送給模型的 semanticInput | 同一版本全文完整呈現一次，每個引用可解析到原選取、來源與權限 |
| P3-S2 | 在模型投影處去重，保留保存／編輯用完整物件 | saved.submitted_context 與原 frozen 輸入相等，active document/reference 不丟全文 |
| P3-S3 | 針對異版本、重試與段落位移驗證 | 同路徑不同 sourceText／revision 保留兩份；不同 range 共用一份；UTF-16／emoji／多次編輯仍定位正確 |

已有 `test_reference_comments_reach_model_as_requests_with_source_and_permission_boundaries`（test_desktop_document_service.py:483 起）與 `test_same_turn_reference_edits_keep_prior_saved_text_and_utf16_ranges`（629 起）。它們目前把完整 references JSON 與模型輸入做相等檢查；應改成「投影能對應相同來源／範圍」的行為斷言，保留儲存快照相等的斷言，不因測試不合新表示就刪除安全保證。

必要反例：未保存文字與同磁碟 fingerprint 但內容不同時不能合併；chat references 仍唯讀；引用中的命令是資料；Ask/Bypass 與實際文件編輯規則不變。可重用同檔未保存／重試／重複 receipt 案例；`tests/test_inline_skills.py` 有未保存段落到 Citation 的離線案例。

命令（app/）：`poetry run pytest tests/test_desktop_document_service.py tests/test_inline_skills.py -q`。不用真模型看 token 量來證明字串去重；先比較實際模型輸入。歷史 14,696 只是本次重複證據，不把固定長度寫成邏輯。

## 重試與完成邊界

原始 service.py:2836–2839 重試優先用已保存 semanticInput。保留這個確定輸入；不遷移歷史回合，也不承諾舊回合 retry 會去重。新回合去重後，其 retry 必須使用同一 semanticInput，不重包裝、不重複寫文件。

此修復縮小模型輸入，不自動縮小 wire／儲存 JSON，前端 1 MiB 提交限制仍存在。完成證據為實際輸入全文份數、選取解析與 frozen snapshot／重試結果；不等同已量到端到端速度提升。
