# F3：搜尋引擎與瀏覽器
- **依據**：[目標 FG9 與使用者決策 FU01–FU04、FU06](../GOALS.md)、[執行契約](../PLANS.md)、[OD1 實測](../evidence/OD1-engine-survey/README.md)。
- **相依**：無。F3 與 F1、F2 互不相依，但與 F1、F4、F5 修改同一組 Node 檔案，必須依序進行。建議順序見 PLANS。
- **涵蓋**：FG9、FG6、FG8；AF41、X13。

以下 src 指 app/vendor/web-search-mcp/src，tests 指 app/vendor/web-search-mcp/tests。

## 後置條件
- web_search MCP 先以 Google 搜尋；Google 不足 limit 時，以依查詢語言設定市場的 Bing 補足。DuckDuckGo 與 Brave 的程式全部移除。
- 所有瀏覽器工作都使用 Playwright 完整版 Chromium（新 headless 模式）。每個 context 使用由實際瀏覽器版本產生的一般 Chrome UA。
- 回傳的候選網址，是經實際瀏覽器導覽解開引擎跳轉包裝後的真實網址；解不開時保留包裝網址，並如實標示原因。
- 全部變更只在 app/vendor/web-search-mcp（FU06）。Python 主專案不需要任何修改，也不新增環境設定。

## F3-S1：完整版 Chromium 與一般 UA
- **production 檔**：src/browser-pool.ts。
- **處理**：FU02、FU03。

工作：
1. BrowserPool 啟動 Chromium 時加上 `channel: 'chromium'`，使用 Playwright 完整版 Chromium 的新 headless 模式。它由既有的 `npx playwright install chromium` 安裝，不新增依賴。BROWSER_HEADLESS=false 的語意不變。
2. 每個 context 的 userAgent 設為一般 Chrome UA，主版號取自實際啟動的 browser.version()，例如 `Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/<主版號>.0.0.0 Safari/537.36`。格式固定，不隨機，也不偽造其他指紋（FU03）。
3. 既有的 launch 參數、單一 browser、併發上限、owner flag 與收尾邏輯都不變。
4. **環境前提**：完整版 Chromium 會在 TMPDIR 建立 unix socket，路徑必須很短（約 108 字元以內），否則啟動時會以 SIGTRAP 崩潰。
   - 產品經 Python 啟動時 TMPDIR 為空、使用 /tmp，不受影響。
   - 在沙箱內以很長的 TMPDIR 啟動真實 Chromium 時，屬於環境阻塞，依 PLANS 改到沙箱外、以短路徑重跑。

最少檢查：
- **離線**（browser-lifecycle 測試，stub chromium.launch 與 newContext）：
  - launch 選項含 `channel: 'chromium'`；
  - 每個 newContext 都帶不含 "Headless" 的 UA，主版號取自 browser.version()。
- **真實 Chromium**（沙箱外，設定短 TMPDIR 與 PLAYWRIGHT_BROWSERS_PATH）：經 BrowserPool 開一個本機頁面，確認：
  - `navigator.userAgent` 不含 Headless；
  - 使用的是完整版 Chromium：自有瀏覽器程序的 `/proc/<pid>/exe` 位於 `chromium-<rev>/`，而不是 `chromium_headless_shell-<rev>/`；
  - 收尾後沒有殘留程序（同一腳本取證）。
- **晚渲染矩陣重跑**：用 F1-S2 留在 evidence/F1-S2/ 的驅動腳本，改以完整版 Chromium 再跑一次，包括 CSP 與持續輪詢兩頁。結果與 F1-S2 不同時，回到 F1 新增修正步驟。
- 腳本與結果存 evidence/F3-S1/。
- 三份既有 Node 測試仍然通過。

預期必須更新的既有斷言：browser-lifecycle 與 retention 的 stub browser 都沒有 `version()`，加入 F3-S1 後，經 withPage 建立 context 的案例都會失敗。
- 給這些 stub 一個有辨識度的 `version()`，例如 `'777.0.0.0'`；
- 斷言 context 收到的 UA 含 `Chrome/777.0.0.0`。

commit：`feat(web-search): browse with full Chromium and a normal UA [F3-S1]`。

## F3-S2：Google 主力、Bing 備援，移除 DuckDuckGo 與 Brave
- **相依**：F3-S1。
- **production 檔**：src/search-engine.ts，必要時加 src/types.ts。
- **處理**：FU01、AF41。

工作：
1. **刪除 DuckDuckGo 與 Brave**：
   - 刪除兩者的搜尋方法、解析器、URL 清理函式，以及 Brave 專屬的 403/429 處理。
   - 搜尋順序改為 Google → Bing，引擎名稱分別為 `Google` 與 `Bing`。
   - 策略 B（U02）不變：Google 不足 limit 時才由 Bing 補足；完全相同的 URL 合併來源。
2. **新增 Google 方法**（瀏覽器）：
   - 導覽 `https://www.google.com/search?q=<查詢>&hl=<語言>&num=<limit>`，等待結果出現。等待時間以 searchSelector 為上限，取 min(上限, 剩餘預算)。
   - 回應為 HTTP 4xx，或被導到 `/sorry/` 路徑時，視為引擎錯誤，記錄已知事實（HTTP status 與最終路徑），不重試、不換方式繞過。這是對觀測到的 HTTP 結果做判斷，不加入挑戰頁詞彙辭典（R06）。
   - 解析主結果區中含 h3 的連結：
     - title 取 h3 文字；
     - url 依 R04，以搜尋頁的實際網址為基準解成絕對網址，例如 `new URL(href, page.url()).href`。Google 的包裝 href 是相對的 `/goto?url=…`；不先解成絕對網址，`search()` 中的 `new URL(item.url)` 會失敗，候選就被丟掉；
     - observedUrl 維持既有語意，保存原始 href；
     - snippet 取同一結果區塊內的摘要。

     未知的欄位留空。包裝網址由 F3-S3 解析。
3. **Bing 改用直接搜尋網址並帶市場參數**：
   - 網址為 `https://www.bing.com/search?q=<查詢>&count=<limit>&setlang=<…>&cc=<…>`，移除首頁輸入框流程與隨機 cvid。
   - 只解析正式結果（`#b_results > li.b_algo`）。沒有正式結果時，如實回報零解析，不以側欄模組湊數。實測時，側欄模組曾被當成結果，例如查光合作用卻得到颱風消息。
4. **查詢語言判定（FA13）**：
   - 查詢含漢字時，Google 用 hl=zh-TW，Bing 用 setlang=zh-Hant&cc=TW；
   - 否則 Google 用 hl=en，Bing 用 setlang=en&cc=US。

   這是固定規則，不做語意判斷。其他語言暫時歸為英文，記錄為已知限制。
5. **可覆寫的搜尋位址**：兩個引擎的搜尋網址基底與搜尋主機（`www.google.com`、`www.bing.com`）是 SearchEngine 上可覆寫的成員，不是環境設定。
   - 用 static 成員或 prototype 上的屬性，不用 class field，讓 preload 不必修改 index.ts 就能覆寫。
   - 測試與 F7-S2 的 preload 用它們把引擎指向本機的假引擎頁。

最少檢查（tests/test-search-result-retention.mjs：把既有的三引擎 stub 改寫為兩引擎）：
- **策略 B**：
  - Google 回 5 筆時，Bing 不被呼叫；
  - Google 回 2 筆、Bing 一批含 1 筆重複與 3 筆新結果時，恰好補到 5 筆並合併來源；
  - Google 被擋（429 或 `/sorry/`）時由 Bing 補足，Google 的錯誤事實保留在引擎行。
- **Google 解析器**：inline fixture 涵蓋相對的 `/goto?url=` 包裝 href、直接 href、缺 snippet、缺 title。要經由 `search()` 驗證：相對的包裝 href 解成絕對網址後沒有被丟棄，observedUrl 仍是原始 href。
- **Google 方法**（fake page，不只測解析器）：
  - HTTP 429 時為錯誤，並帶 status；
  - 最終網址為 `/sorry/` 路徑時為錯誤，並帶路徑；
  - HTTP 200 時取得解析結果；
  - 被擋時沒有重試，也沒有開第二個 browser。
- **Bing 解析器**：fixture 同時有正式結果與側欄模組時，只取正式結果；只有側欄模組時為零解析。
- **市場參數**：中文查詢與英文查詢，各自產生正確的 hl 與 setlang／cc。
- **可覆寫**：覆寫搜尋網址基底後，Google 與 Bing 方法導覽的是覆寫後的網址。
- **移除乾淨**：原本 DuckDuckGo、Brave 的測試與斷言一併移除；以 grep 確認 src 與 tests 中不再出現 duckduckgo、brave（README 由 F7-S1 處理）。
- build 與三份 Node 測試通過。

預期必須更新的既有斷言：
- browser-lifecycle 的 selector 上限案例：Bing 首頁流程會先後等待 formSelector 與 searchSelector（斷言 `[20, 20]`），並以 DuckDuckGo 方法當作下一個引擎。改寫為 Google 等待結果時卡住、由 stub 的 Bing 接手，斷言 Google 的等待以上限為準。
- retention 的 Bing fixture 只有 `li.b_algo`，沒有外層的 `#b_results`；改用 `<ol id="b_results">` 包住正式結果。
- retention 中以 fake browser 驗證 Brave 被擋的區塊，改為上面的 Google 方法案例。
- retention 中 DuckDuckGo 網址清理、Brave 與 DuckDuckGo 解析器的斷言，以及引擎行中 `Axios DuckDuckGo` 等引擎名稱，隨引擎刪除而移除或改寫。

commit：`feat(web-search): search Google first with Bing as fallback [F3-S2]`。

## F3-S3：以實際導覽解析結果網址
- **相依**：F3-S2。
- **production 檔**：src/search-engine.ts、src/browser-pool.ts（新增具名常數）、src/types.ts。
- **處理**：FU04、X13。

工作：
1. **包裝判定（FA14）**：結果網址的 host 等於產生它的引擎的搜尋主機（`www.google.com`、`www.bing.com`）時，就是該引擎的跳轉包裝。
   - 這是結構判斷，不是網址辭典，也不解碼任何參數（R04）。
   - support.google.com、docs.google.com 這類一般結果的 host 不是搜尋主機，不導覽。
   - 搜尋主機取自 F3-S2 的可覆寫成員。
2. **在哪裡解析**：在該引擎自己的 withPage 回呼內、解析完搜尋結果之後進行，使用同一個 page 與 context，帶著搜尋時的 cookie。
   - 不另外呼叫 withPage，也不開新分頁。這樣不會巢狀占住 page 閘門而死鎖，也不超過 A04 的 2 個活躍 page。
   - 與 OD1 的差別：OD1 在同一個 context 開新分頁，並等到目標頁載入完成；本步改用同一個 page，並以導覽請求認定網址（見下一項）。context、cookie 與 referer 都與 OD1 相同；差異由本步的真實 Chromium 檢查驗證。
3. **怎麼解析**：
   - 依候選的原始順序逐筆導覽包裝網址，referer 設為該次搜尋頁的網址。
   - 觀察主框架的導覽請求，包括 HTTP 跳轉的每一跳。第一個 host 不是搜尋主機的請求網址，就是解析結果，也就是引擎實際送出的目的地；目標網站自己的後續跳轉，由讀取正文時的 final URL 記錄（R04）。
   - 認定後立即處理下一筆，不等待目標回應。所以目標很慢、不回應，或是下載（例如 PDF），都不影響取得網址。
   - 只解析需要的數量：補到 limit 為止。解析後若與已有候選重複，就繼續解析下一筆。
   - 每筆的上限是新具名常數 linkResolve，初始值與 pageRequest 相同（6000 ms），取 min(上限, 剩餘預算)。到期就放棄該筆、記錄原因，接著處理下一筆；呼叫期限已到時，剩餘的候選不再開始解析。
   - 每筆結束時移除監聽器與 timer；被中斷的導覽 promise 也要接住，不得留下未處理的 rejection。最後由 withPage 既有的有界收尾關閉 context。
4. **記錄事實**：
   - observedUrl 維持既有語意，保存標記中的原始 href。另以一個解析紀錄欄位保存絕對的包裝網址、結果、耗時與原因。
   - 結果分為五種：
     - resolved：url 改為解析出的網址；
     - stayed on engine host：包裝頁已回應，但到上限時仍沒有離開搜尋主機的導覽請求，例如需要點擊的中介頁。這是事實，不算程式錯誤；
     - timeout（包裝頁本身沒有在上限內回應）、failed（導覽出錯）、not started（期限已到）：url 保留絕對的包裝網址，並記錄原因。
   - 不猜測、不解碼。
5. **去重**：跨引擎去重改以解析後的網址進行。A05 的「完全相同 URL 才合併」套用在解析後的網址上，所以 Google 與 Bing 指向同一目標的結果會合併來源。
6. **使用範圍**：兩個搜尋工具都輸出解析後的網址；includeContent=true 時，正文直接讀解析後的網址。
7. **已知風險**：解析會對搜尋主機送出額外的請求。F7-S3 記錄解析之後的 Google 搜尋是否被擋。被擋時如實記錄，列入最終彙報的後續選項，由使用者事後決定；執行中不停下來等待，也不自行加入延遲或改變流程。

最少檢查（stub page，放在 browser-lifecycle 或 retention 測試）：
- 包裝網址被替換為解析出的網址，observedUrl 與解析紀錄都在，耗時有紀錄；非包裝網址（包括 support.google.com）不導覽。
- 導覽包裝網址時帶 referer，值為該次搜尋頁的網址。
- 包裝頁已回應、但沒有離開搜尋主機的導覽請求時，記為 stayed on engine host，候選仍保留。
- 導覽逾時與呼叫期限將到時，候選保留包裝網址並附原因；期限到時，剩餘的候選不再開始解析。
- Google 回 8 筆、limit=5：只解析前 5 筆。其中一筆解析後與前面重複時，再解析第 6 筆；回傳恰為 5 筆，依原始順序。
- Google 包裝與 Bing 包裝解析到同一網址時，合併為一筆並列出兩個來源引擎。
- MAX_CONCURRENT_PAGES=1 時，搜尋與解析能完成，不會死鎖。
- **真實 Chromium**（沙箱外、短 TMPDIR）：本機伺服器只綁 127.0.0.1，以 `localhost:<port>` 當作測試用的搜尋主機，目標都在 `127.0.0.1:<port>`。包裝頁有五種：
  1. JavaScript 跳轉；
  2. HTTP 302 跳轉；
  3. 跳到 Content-Type 為 application/pdf 的目標；
  4. 跳到永不回應的目標；
  5. 不跳轉（測試中調小 linkResolve）。

  前四種都要解析成目標網址並記錄耗時，第 3、4 種的耗時不得接近 linkResolve；第 5 種記為 stayed on engine host。收尾後沒有殘留程序。腳本與結果存 evidence/F3-S3/。

commit：`feat(web-search): resolve engine redirect links by real navigation [F3-S3]`。

## F3-S4：可見的解析事實
- **相依**：F3-S3。
- **production 檔**：src/utils.ts。

工作：
- formatSearchResponse 對每筆候選顯示 url：解析成功時是解析出的網址，否則是包裝網址。
- 有解析紀錄時另起一行：
  - resolved：列出包裝網址的網域與解析耗時；
  - 其他結果：標示「engine redirect not resolved」、結果種類與原因，並說明這個 URL 是引擎的包裝網址。
- 統計行加上 resolved 與 unresolved 的數量。
- 兩個搜尋工具共用同一個 formatter（U12）。

最少檢查：formatter 的輸出文字斷言。resolved、timeout、stayed on engine host 與非包裝四種候選的文字互不相同，統計數字正確。

commit：`fix(web-search): show resolved and unresolved result links [F3-S4]`。

## 階段界線
- 只修改 app/vendor/web-search-mcp（FU06）。不改 app/agent，不新增 Python 依賴，不新增環境設定。
- 不加入其他搜尋引擎、付費 API、跨引擎融合或排序；不解碼任何引擎的包裝參數。
- Google 被擋時不重試，也不處理驗證頁，如實回報並交給 Bing。
- 操作的總時間上限語意（F4）、引擎未嘗試的原因與統計口徑（F5）在後續階段完成。本階段新增的 Google、Bing 方法要使用既有的預算與具名常數。
