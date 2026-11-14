# K3 舊回合不帶文件全文

- **後置條件**：歷史進入模型時，只有最新一份文件快照保留全文，較舊的快照與凍結引用全文換成佔位；保存的歷史、重試、凍結引用、還原提交狀態都不變；舊版本仍能依佔位從封存取回。
- **涵蓋**：G7。
- **相依**：K2（量測函式與 15 回合測試）。
- **輸入**：PLANS「基線」的文件回合與歷史重播兩節；GOALS 的不變條件與範圍外項目。

## 行為規格

1. **只改組裝，不改保存**。`semantic_input` 照原樣寫進歷史檔；轉換只發生在把歷史做成模型訊息的時候。不改 `LATEST_CONTEXT_TURNS`。
2. **哪一份算最新**：當前回合帶文件快照時，所有歷史回合的快照都換成佔位；當前回合不帶文件時（例如文件關閉後的普通對話），保留歷史中最新一份快照的全文，其餘換成佔位。「當前回合帶不帶快照」以當前回合實際送出的文字中有沒有快照標頭判斷（或由呼叫端明確傳入），不能依 `_document_turn_active`：重試與 `submittedContext` 回合會改用保存的 `semantic_input`，此時文字含快照但旗標可能為假（見 PLANS 基線）。
3. **佔位要留下的東西**：明確寫出「這是較早的版本，不是目前文件」；路徑、`editorRevision`、`diskFingerprint`；當時的選取範圍（行號與 UTF-16 範圍）；選取範圍明顯小於全文時保留選取的文字（上限由執行者訂一個合理值，並在 build-log 記錄這是可逆的選擇）；全文仍在對話封存中、需要還原或比較時可依封存提示取回（指出回合編號或可搜尋的識別資訊）。使用者打的字一律保留。
4. **凍結引用**：保留每個引用的 `referenceId`、種類、引用的段落文字與行號；只拿掉快照的 `sourceText` 全文。
5. **辨識失敗**：無法辨識格式的舊回合（例如本功能之前的格式差異）原樣保留，不丟例外；量測函式的 `document_parse_issue` 可用來發現這種情況。快照 JSON 要從標頭之後用 `json.JSONDecoder().raw_decode` 一類的方式取出，不依賴 JSON 後面的說明文字：K5 會改詰問回合的說明文字，而已保存的回合保留舊文字，兩種都要能辨識。
6. **產生與辨識共用同一組標頭常數**，避免 `service.py` 改了字串而重播端沒跟著改。模組依存方向依現有結構選擇；不要讓 `agent/session.py` 匯入整個 desktop service。
7. 所有把歷史送進模型的地方都走同一套轉換：`_base_prompt_history`（normal 模式，也被 `agent/thinking/orchestrator.py:188` 使用）、`_visible_context_text`（`agent/session.py` 約第 1096 行，由 `orchestrator.py:534` 以純文字送進 extended 模式提示），以及 K1 核對出的其他使用者（例如 `fixture_session.py` 若有自己的組裝，判斷是否需要一致）。`recent_turns` 等對外顯示用途不轉換。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| K3-S1 | 依上方規格實作轉換函式與單元測試 | 單元測試涵蓋：當前回合有／無文件兩種情形；佔位內容（版本標示、路徑、revision、範圍、窄選取的文字、封存指引）；凍結引用保留段落文字；`sourceTextSameAs` 情形；快照後接舊說明文字與詰問唯讀說明文字兩種變體都能辨識；格式無法辨識時原樣保留 |
| K3-S2 | 接上所有歷史組裝處 | 在 K2 的 15 回合測試加入新斷言：沒有凍結引用的回合，最後一次模型呼叫中目前文件的全文只出現一次；文件關閉後的普通對話回合，只有最新一份歷史快照保留全文；歷史檔中各回合的 `semantic_input` 仍含完整快照（與保存內容逐字比對）；重試一個文件回合時，該回合送出的仍是原 `semantic_input`，且歷史中的舊快照照樣被換成佔位；extended 模式的 `_visible_context_text` 也不含舊快照全文。另跑 `tests/test_desktop_document_service.py`、`tests/test_session_persistence.py`、`tests/test_thinking_session.py`、`tests/test_desktop_fixture.py` 與 K1 列出的相關模組 |
| K3-S3 | 量測修改後的數字 | 以 `DOCUMENT_BUDGET_REPORT=<計劃>/evidence/K3-S3/after-history.json` 重跑 15 回合測試，摘要與 `before.json` 對照（第 1、5、10、15 回合），寫進 build-log |

各步驟各自 commit。

## 風險

- 模型可能需要舊版本來回答「改回上一版」：靠佔位中的封存指引；normal 模式可用 bash 取回（需核准），extended 模式不行（既有封存提示已說明）。實際取回行為放進 K8 的手動 GUI 清單，不由執行者宣稱已驗證。
- 若發現某個既有測試斷言舊回合必須含全文，先判斷那是保護「保存」還是「組裝」：保護保存的斷言不能改；只描述舊組裝方式的斷言可改，並在 build-log 說明。

## 交付給後續階段

轉換函式與共用常數、新斷言、`after-history.json`。
