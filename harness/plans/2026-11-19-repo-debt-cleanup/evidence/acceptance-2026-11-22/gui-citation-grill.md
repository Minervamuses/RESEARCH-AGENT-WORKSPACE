# 使用者 GUI 試跑後的驗收：citation 與 grill（2026-11-22）

- **觸發**：使用者在 `6c77fb0` 之後自行啟動桌面 app，測試 `@grill` 與 `@citation`，請執行者依本機紀錄驗收。
- **執行者沒有操作 GUI**；以下只根據紀錄與檔案判斷，畫面本身的呈現不在本驗收範圍。
- **資料來源**（唯讀）：`~/.local/state/research-agent/logs/desktop-backend.log` 與 `.stderr.log`（19:45:38 啟動的那一次）、對話檔 `app/store/projects/p-c673e2df…/conversations/40efe7bc….json`、專案書目庫與文件的修改時間、Crossref 公開 API（只送出回答中的 5 個 DOI）。

## 1. 執行狀態

| 檢查 | 結果 |
|---|---|
| 後端 | 一次啟動，log 沒有 ERROR／WARNING／traceback；stderr 只有既有的 LangChain 棄用警告；結束時 `exit status: 0` |
| 對話檔 | schema v3，2 個回合都是 `completed`，沒有 failure；思考模式 normal、Permission bypass |
| 文件與書目庫 | `proposal.md` 與 `references.json` 的修改時間都是 2026-11-07，這次沒有被寫入（兩個回合都沒有 `document_edit`，也沒有 save） |

## 2. grill（回合 1）

- 輸入：`@grill`（skill reference 正確解析），帶一段文件 reference（第 142 行）與留言「check this part」。
- 工具呼叫 0 次，模型呼叫 1 次（44 s，output 8,186 tokens）——符合 grill「唯讀、不修改文件」。
- 格式符合 `skills/grill/SKILL.md` 的 Reply format：`## 還原`（逐句角色與支持關係）→ `## 發現` 的 `### F1｜問題`（原文／理由／請回應）→ `## 判斷` 的 `判斷：待回應`（有未解的「問題」，依規則應為待回應）。
- 引文核對（對照對話檔中凍結的文件快照）：F1 的「原文」逐字存在；理由中引用的後文（「每一題在新的對話中以固定的提示範本送出」「引用 Transformer 的原始論文」、九類測試案例與七種編碼結果）都能在快照中找到。沒有找到的只有它自己的改寫與建議用語，沒有被標成原文。
- 內容是否成立由作者判斷；執行者只確認它的論據有原文依據、落在段落實際宣稱的範圍內。

## 3. citation（回合 2）

- 輸入：`@citation are there any supports?`，帶整份文件快照。
- 工具：`bibliography_lookup` 2 次、`citation_workflow` search 6 次、`rag_search` 1 次，全部 ok；沒有 save——使用者只問有沒有支持文獻，所以只搜尋、不存檔是正確的。
- 回答列出 5 筆候選。向 Crossref 核對：5 個 DOI 都存在，標題、作者、年份、出處都與 Crossref 一致；4 段引用的摘要與 Crossref 原文逐字相同（差異只有 `&lt;` 被解碼成 `<`、Crossref 文字開頭的「Abstract」字樣）；Liu et al. (2023) 在 Crossref 沒有摘要，回答也如實說「abstract was unavailable」。沒有捏造的作品或摘要。
- 引用規則：回答沒有 `[[cite:…]]` 標記（沒有存檔的候選不可引用，正確）；唯一的 Pandoc key `[@liu2023verifiability]` 確實在專案書目庫中。
- 小問題（模型輸出品質，不是程式缺陷）：
  1. 「Searches Executed」列了 5 次搜尋，實際是 6 次 `citation_workflow` search（turn_trace）。
  2. Walters & Wilder (2023)（`10.1038/s41598-023-41032-5`）已經在書目庫裡，回答仍把它當成新候選列出，沒有告訴使用者既有的 key。

## 4. 這次沒有涵蓋的部分

- citation **存檔**路徑（`saved`／`reused`／`storage_failed`、Ask 模式的核准框、書目庫寫入）沒有被觸發；Permission 是 Bypass，存檔也不會出現核准框。若要驗收 C5 的存檔語意，需要在 Ask 模式請 `@citation` 存一筆新文獻與一筆已在書目庫的文獻。
- grill 的第二輪（作者回覆後的 `## 回應檢查`）沒有測。
- 最終彙報第 10 節的 GUI 清單其餘項目（重啟、Stop／Retry Stop、刪除、改名、擴充、對話框焦點等）不在這兩個回合中。

## 結論

這兩個回合的程式行為符合預期：grill 唯讀且格式、引文正確；citation 只搜尋不存檔、候選與摘要都真實、引用標記規則正確；後端沒有錯誤。兩個小問題屬於模型輸出內容，不需改程式。
