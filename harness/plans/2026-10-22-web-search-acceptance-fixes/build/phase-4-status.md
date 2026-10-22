# F4：可見狀態與統計如實
依據：[目標 FG4 與 FA07、FA08](../GOALS.md)、[執行契約](../PLANS.md)、[驗收發現](../context/acceptance-findings.md)。相依：F3（同一組 Node 檔案）。涵蓋 FG4、FG6、FG8；AF11–AF18、AF32、AF37，突變 N02b、N02c、N02d、N02g、N03b、N04c、N15、N20b。

以下 src 指 app/vendor/web-search-mcp/src，tests 指 app/vendor/web-search-mcp/tests。

## 後置條件
兩個搜尋工具與單頁工具的 Agent 可見文字都如實呈現下列事實：
- 每個引擎是完成、零解析、失敗、已達 limit 而策略停止，還是因期限、取消、rate limit 或排隊逾期而未嘗試；
- 實際開始的傳輸次數，以及已知的 HTTP status；
- 每個頁面最後一次嘗試的事實，以及完整的嘗試清單；
- 有定義的統計口徑。

工具文案不承諾完整性。U12 的「兩個搜尋工具都顯示引擎狀態與來源引擎」持續成立。

本階段引擎與頁面採用同一個「開始」定義（FA07、FA08）：已發出 HTTP 請求，或已開始為這次讀取啟動瀏覽器、建立 context，才算開始。只在佇列中等待、從未取得 slot 的，不算開始，改以原因呈現。

## F4-S1：引擎執行事實
- **production 檔**：src/types.ts、src/search-engine.ts、src/utils.ts。
- **處理**：AF11、AF12、AF13、AF32、AF37（N03b、N04c、N15）。

工作：
1. **引擎狀態（FA07）**：
   - SearchEngineState 加入 not_attempted 與原因欄位，原因為 deadline、cancelled、rate_limited、queue_expired 之一。
   - strategy_stopped 只用於「前面的引擎已達 limit」。
   - rate limiter 拒絕或排隊逾期時，尚未嘗試的引擎標記為 not_attempted 並附原因；原本的 error 文字仍保留在 error 欄位。
2. **嘗試次數**：attempts 依上述「開始」定義計算，沒有開始的引擎為 0。移除 `Math.max(1, …)`。
3. **已知事實（AF13）**：引擎取得回應時，記錄 HTTP status（DDG 取自 axios 回應，Bing、Brave 取自主要導覽回應），並列在引擎行。不加入挑戰頁詞彙判斷（R06）。
4. **零候選時的標題**：formatSearchResponse 分四種情形，各有不同句子：
   - 所有已嘗試的引擎都失敗；
   - 有引擎完成但全部零解析；
   - 沒有引擎嘗試（附原因）；
   - 混合。
5. **文字完整**：
   - 引擎行一律顯示 error 原因；strategy_stopped 與 not_attempted 的引擎都要列出；合併來源的候選列出全部來源引擎。
   - 新欄位一律加在既有 `status=` 之後，讓既有的引擎行格式維持相容。
6. 保留逐筆加入時的 limit 防護、Brave 暫態錯誤最多重試一次，以及 URL 只解碼一次；本步只補上缺漏的測試。

最少檢查（tests/test-search-result-retention.mjs）：
- **四種零候選情形**：文字互不相同，且各自含對應句子（可殺死 N02b）。
- **引擎行**：含 error 原因（N02c）、含 strategy_stopped 引擎（N02d）。
- **HTTP status**：零解析引擎行顯示 HTTP status（例如 200），Brave 403/429 的引擎行顯示其 status（AF13）。
- **合併來源**：同一 URL 由 Bing 與 DDG 都回傳時，顯示 `Browser Bing, Axios DuckDuckGo`（N02g）。
- **未嘗試**：deadline 已過、rate limit 拒絕、排隊逾期時，未嘗試的引擎為 not_attempted，原因正確，attempts=0，標題不是「No candidates parsed」。
- **超量防護**：limit=5，Bing 2 筆、DDG 一批 4 筆新結果，結果恰為 5 筆（N03b）。
- **Brave 百分比**：Brave 結果 href 含 `%252F` 時，保留為 `%252F`（N04c）。
- **Brave 重試上限**：暫態錯誤時，實際 attempts 不超過 2（N15）。
- 既有的策略 B、403/429 快速失敗與中文查詢案例全部仍然通過。

預期必須更新的既有斷言：
- 用 stub 取代的引擎方法不會再被自動補成 attempts=1。retention 中預期 `attempts=1` 的斷言（約第 146 行）要改為讓 stub 記錄自己的實際嘗試，或改斷言實際值。
- 期限案例的 `engines[2].error` 仍須能比對 /deadline/（約第 202 行）。

build、Node 測試、記錄後 commit：`fix(web-search): report why engines ran or stopped [F4-S1]`。

## F4-S2：頁面讀取事實與統計口徑
- **相依**：F4-S1。
- **production 檔**：src/enhanced-content-extractor.ts、src/types.ts、src/utils.ts。
- **處理**：AF16、AF17、AF18、N20b。

工作：
1. **每次嘗試用新紀錄**：
   - 每次嘗試開始時建立一筆新的嘗試紀錄，涵蓋 status、HTTP status、Content-Type、final URL、頁面標題、編碼（F1-S3）、等待毫秒（F1-S2）、錯誤、長度與 truncated。
   - PageRead 的摘要欄位由最後一次嘗試的紀錄組成，不沿用前一次嘗試留下的欄位。
   - attempts 清單保留每次嘗試的事實，讓 HTTP 的事實在 fallback 後仍可見。
2. **在建立 page 之前失敗的嘗試**：
   - 依階段開頭的「開始」定義，瀏覽器 fallback 在開始啟動瀏覽器或建立 context 時計為一次 browser 嘗試；即使在取得 page 之前失敗（launch 逾時、pool 損壞），也要列出原因。
   - 只在佇列中等待就逾期的 fallback 不計數，以「not started」與原因呈現。
3. **統計口徑（FA08）**：
   - 移除恆為 0 的 transport_retries。
   - formatSearchResponse 的 Read statistics 後面附一行口徑說明，涵蓋：source_read_attempts、candidates_attempted、redirect 不另計、parsed_count 是引擎回傳、尚未跨引擎去重的列數。
4. **targetCount**：保留 extractContentForResults 的 targetCount 參數（移除它需要改 index.ts，會超出本步的檔案範圍），並新增測試確保它生效（N20b）。

最少檢查（tests/test-content-contract.mjs，stub 與本機伺服器）：
- **HTTP 空文字後 browser 失敗**：摘要為該次 browser 的事實，不帶 HTTP 的長度；attempts 清單兩次都在，各自帶事實。
- **HTTP 403 後 browser 為空**：摘要的 Read error 不是被取代的 403；403 留在 attempts。
- **launch 失敗**：browser 嘗試被計數並列出原因；source_read_attempts 包含它。
- **排隊逾期**：fallback 在佇列中就逾期時不計數，但看得到原因。
- **targetCount**：targetCount=2、給 5 個候選時，只讀前 2 個；回傳仍含全部 5 個候選，其餘維持 not_attempted（R05：候選不得無聲消失）。
- **口徑一致**：統計數字等於 spy 觀察到的實際事件數；說明行存在；沒有 transport_retries。

預期必須更新的既有斷言：
- content-contract 的 stub 會直接呼叫 started()（約第 56 行）。計數時機改變後，要同步調整這個 stub。
- 舊的統計字串斷言（約第 74 行的 `transport_retries=0`）要更新。
- 既有的候選保留、媒體與截斷斷言全部仍然通過。

build、Node 測試、記錄後 commit：`fix(web-search): keep per-attempt page facts and define statistics [F4-S2]`。

## F4-S3：工具入口一致性與文案
- **相依**：F4-S2。
- **production 檔**：src/index.ts，必要時加 src/utils.ts。
- **處理**：AF14、AF15。

工作：
1. get-web-search-summaries 改用與 full-web-search 相同的 query 驗證：去除空白後為空就拒絕。limit 驗證維持一致。在 build-log 記錄：修改後，兩個搜尋工具的 limit 驗證各在幾處進行（schema transform、handler，或共用函式）。F5-S3 判定突變 N14j 時會用到這個資訊。
2. 移除 full-web-search query 參數描述中的「recommended for comprehensive research」。逐一檢查三個工具與其參數的描述，不得承諾完整全文、已驗證摘要、來源品質或研究支持；Citation 分流句維持不變。

最少檢查：
- 實際的 handler 行為，包括 summaries 拒絕空白 query、無效 limit 被拒絕，由 F5-S1 的入口測試驗證。
- 本步至少用靜態斷言確認：描述中不再出現「comprehensive research」，且兩個搜尋 handler 都使用共用的 query 驗證。

build、Node 測試、記錄後 commit：`fix(web-search): validate both search entries alike [F4-S3]`。

## 階段界線
- 不改候選選擇、引擎順序、limit 語意或長度語意。
- 不加入挑戰頁詞彙判斷或站點辭典。
- 輸出仍是既有的 MCP 文字回傳，不新增持久 schema。
- README 的口徑說明在 F6-S1 同步。
