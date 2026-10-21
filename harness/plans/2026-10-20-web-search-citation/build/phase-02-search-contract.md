# P2 — 搜尋候選與參數契約
依據：[目標與 A01–A06](../GOALS.md)、[執行契約](../PLANS.md)。相依：無。涵蓋 G2/G4/G8、R02/R04/R06/R07。

## 後置條件
搜尋先形成不依正文成功與否而改變的候選範圍；逐引擎補足 limit，有正確來源與失敗資料，且兩個搜尋工具（full-web-search、get-web-search-summaries）的 Agent 可見輸出都看得到；參數無模型猜測，兩個讀取入口一致。完整正文忠實性依賴後續 P3。

## P2-S1：搜尋補足與執行事實
主要 production 範圍：src/search-engine.ts、src/types.ts、src/index.ts；若共用格式化函式須放 src/utils.ts（以下 src 均指 app/vendor/web-search-mcp/src）。若因此超過三個 production 檔，依 PLANS 第 3 項拆成 P2-S1a（搜尋補足與執行事實）與 P2-S1b（兩個搜尋工具的輸出文字與斷言），兩步都要可 build，各自檢查、記錄並 commit。

- 刪詞彙相關性評分、品質門檻、勝出批次與提前結束的評分路徑，不以關閉旗標代替刪除責任。
- 用 A05 有限序列：保留引擎排序，逐批附加，完全相同 URL 才去重；首筆 title/snippet/URL 保存，額外來源引擎可附於同一候選。每引擎最多一次策略嘗試；既有必要傳輸重試最多一次，Brave 403/429 不重試。實際重試計數與來源數分開。
- 達 limit、引擎耗盡、取消或 deadline 停止。因 limit 達成而未嘗試的引擎標為策略停止，不說搜尋失敗；耗盡只有兩筆就回兩筆與原因。
- 搜尋候選先固定，不以 includeContent 或 extraction 成功換人。R05 的正文交付在 P3 接通，不保留成功者優先選擇作最終行為。
- 候選 URL 保留觀測值，驗證 http/https；相對 URL 用標準 URL 與頁面 base 解析；不二次 decodeURIComponent、不展開猜出的網站 redirect 辭典。最終 URL 只從真實導覽得到。
- 每個引擎記錄 attempted、parsed_count、錯誤／零解析／完成；HTTP200 + 零解析只能說本次解析為零。全部失敗、全零解析、部分成功不同。診斷可記 HTTP狀態/媒體/parser，不按 captcha 等詞推斷。
- 搜尋 title/snippet 與頁面 title/content 分開；未知留空。停止把搜尋命中預填為已成功讀正文。沿既有 MCP 文字回傳，用最少內部欄位表達，不設大型狀態框架。
- U12：full-web-search 與 get-web-search-summaries（index.ts:151 起的 handler 目前只輸出 title/URL/description）的文字輸出，都要帶出各引擎 attempted／零解析／失敗／策略停止，以及每筆候選的來源引擎。共用的狀態與候選文字格式化放在可單獨匯入、不會啟動 server 的純函式；index.ts 載入即啟動 stdio server，離線測試不能 import 它。兩個 handler 都呼叫這個函式。

最少檢查：
- 改既有 tests/test-search-result-retention.mjs，用 stub「第一引擎2筆、第二引擎含1重複+3新筆、limit5」確認：
  - 補到5筆並維持順序；
  - 足額後第三引擎未呼叫；
  - 後續引擎失敗仍保留前兩筆；
  - 全部失敗與全零解析可區分；
  - 中文/AI/運動/天氣查詢不觸發分數。
- 去除分數勝出的舊斷言，保留 403/429 快失敗與來源保留。
- 輸出文字斷言（AC05「離線＋輸出文字」）：從 build 後的 dist 匯入上述格式化函式，以 stub 搜尋回應確認：
  - 全部失敗、全零解析、部分成功三者的文字不同；
  - 每筆候選列出來源引擎。

  另以靜態檢查（grep src/index.ts）確認 full-web-search 與 get-web-search-summaries 兩個 handler 都呼叫這個函式。實際 Agent 可見文字由 P6-S1 經 Python 入口補充觀察。
- 從 vendor 執行 npm run build（Conda app）與 Node test。

逐步更新紀錄並 commit：fix(web-search): fill candidates across engines without scoring [P2-S1]（拆步時用 P2-S1a／P2-S1b）。

## P2-S2：長度、預設及入口傳遞
相依 P2-S1。主要 production 範圍 index.ts、enhanced-content-extractor.ts、utils.ts；只有真有型別需要時調整 types.ts，先找可獨立且正確的小變更，不為分類而新增模組。
- 移除依數字／字串猜模型並改長度的程式。兩入口保留嚴格可轉換的數字字串與 boolean true/false 字串，拒絕部分 parse 的非法輸入。
- default includeContent=true，limit=5（1–10）；maxContentLength 採 A01/A02。明確0必須依A01解析為有效部署預設；合法正整數沿驗證、擷取、轉換、最後輸出流通，不被不同入口重設。
- 部署 MAX_CONTENT_LENGTH 預設10000。移除「自動最佳化內容長度」宣告；明示有效值、字元單位、0與截斷標記。metadata 不混算。
- 硬上限10000公開且不可由0或環境值繞過；大於10000明確拒絕，不因小上限觸發品質 fallback；P3 會移除內容品質判定本體，這步至少不能新增這種判斷。
- 若尚有舊 utils.cleanText 展平結構，這步只解決長度參數；P3 負責保守轉換，避免重複兩套截斷。

用最少既有/同檔案例測省略、0（採部署預設）、7、'7'、10001（拒絕）、emoji/中文、錯誤值、兩入口一致與設定優先序；不要造 broad matrix。執行受影響 build/targeted test，記錄仍待 P3 的內容政策。commit：fix(web-search): honor explicit content limits consistently [P2-S2]。

## 階段故障邊界
無法靠有限現有引擎取得結果時回報事實，不新增搜尋 API。某引擎未知可用性留待 P6 實機；離線契約先完成。任何測試失敗依 PLANS 處理，不把階段切分當人工審查關卡。
