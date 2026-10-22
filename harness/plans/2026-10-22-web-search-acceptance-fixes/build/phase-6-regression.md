# F6：入口、生命週期與契約的回歸守護
依據：[目標 FG6 與 FA12](../GOALS.md)、[執行契約](../PLANS.md)、[驗收發現](../context/acceptance-findings.md)、[突變清單](../context/mutation-survivors.md)。相依：F2、F5。涵蓋 FG6、FG8；AF29、AF30、AF31（Node 部分）、AF33、AF39，以及突變清單中歸 F6 的「必殺」項。

以下 tests 指 app/vendor/web-search-mcp/tests。本階段只新增或修改測試與測試輔助檔；不得為了好測而改動 production 行為。若測試揭露 production 缺陷，依執行契約回到對應階段，新增一個有穩定 ID 的修正步驟（例如 F5-S4），單獨檢查並 commit。

## 後置條件
以下項目都有已提交、而且在行為被破壞時會失敗的測試：
- Node server 入口的生命週期；
- 三個工具的 handler 接線；
- Node 與 Python 兩端的預算與設定契約，包括 F3 的瀏覽器模式與 UA；
- 舊 P4-S2 的聚焦案例；
- Citation 段落與工具文案。

mutation-survivors 的必殺項全部被殺死，或依 FA12 記錄等效／不再適用的理由。結果存於 evidence/F6-S3/。

## F6-S1：Server 入口測試
- **新檔**：tests/test-server-entry.mjs、tests/fixtures/stub-engines.mjs。
- **修改**：app/tests/test_citation_skill_activation.py。

### 啟動方式
- **呼叫類案例**：用 vendor node_modules 內既有的 MCP SDK 1.15 client（StdioClientTransport 與 Client）。
  - command 必須用 `process.execPath`：transport 一旦給了 env 就會整個取代環境，PATH 不存在時 `node` 會解析成系統的 /usr/bin/node（v18）。
  - args 為 `--import`、preload 的 file URL（或 `./tests/fixtures/stub-engines.mjs`，不能寫成不帶 `./` 的路徑）、dist/index.js 的路徑。
  - env 只放案例需要的值。
- **生命週期案例（stdin 結束、SIGTERM）**：改用 node:child_process 自行 spawn，以換行分隔的 JSON-RPC 收發訊息。SDK 的 `close()` 會同時中止並送 SIGTERM，無法只關 stdin。
- index.ts 會在 stdout 印出非 JSON 的文字。自行 spawn 時要略過這些行；用 SDK 時，它們會出現在 transport.onerror，不得因此判定測試失敗。
- dist 目錄由一個參數或環境變數決定，預設是 tests 旁的 ../dist。preload 依同一來源匯入 dist 模組，例如由 `process.argv[1]` 推得，供 F6-S3 在暫存複本中使用。

### preload 的職責（測試專用）
- 把 Google 與 Bing 兩個引擎方法換成回傳固定候選，至少 3 筆，讓 limit=2 時可以分辨。候選指向本機 HTTP 伺服器的直接網址；整個引擎方法都被取代，所以不會發出連結解析的導覽。連結解析的入口驗證在 F7-S2，以真實 Chromium 與本機假引擎進行。
- 包裝 BrowserPool.prototype.closeAll，記錄呼叫，並可依測試設定延遲返回；包裝 CallBudget.prototype.abort，記錄呼叫。
- 把 chromium.launch 換成先記錄選項：預設接著拋例外；案例 13 改為回傳 fake browser，它的 `version()` 回傳固定值（例如 `777.0.0.0`），newContext 記錄收到的選項，page 回傳空白內容。
- 封鎖非 loopback 的連線。
- 記錄寫到 stderr 或測試指定的檔案。preload 的設定只透過測試設定的環境變數傳入，不新增產品設定。

測試不需 Chromium，也不需網路。

### 最少案例（每案例說明它保護的 AF 或突變）
1. **includeContent=false**：full-web-search 的本機伺服器收到 0 個頁面請求，輸出各候選為 not_attempted。includeContent=true 時，URL 與順序相同，且確實有讀取（N13、N14f、AF29）。
2. **summaries 不讀正文**：本機伺服器收到 0 個頁面請求；輸出含引擎行；limit=2 時恰為 2 筆（N13b、N14g、N14h）。full-web-search 的輸出也含引擎行（N14i）。
3. **無效 limit**：兩個搜尋工具在 limit 為 11 時都失敗（JSON-RPC 錯誤或 isError 都算），而且引擎沒有被呼叫。
   - 若 F5-S3 之後 limit 驗證只剩一處，這個案例可殺死 N14j；若仍有兩處重複驗證，F6-S3 把 N14j 記為等效。
4. **空白 query**：summaries 對純空白 query 回錯誤，引擎沒有被呼叫（AF14）。
5. **單頁長度**：顯式 maxContentLength=7 時交付 7 個 code points；部署值 MAX_CONTENT_LENGTH=9 且省略參數時，交付 9 個（N14d）。
6. **closeAll 時機**：任何 handler 執行期間都不呼叫 closeAll，只在 shutdown 時呼叫一次（N12、N11e）。
7. **stdin 結束**：一個呼叫正在讀取卡住的本機頁面；preload 讓 closeAll 延遲約 1500 ms 才返回。關閉 stdin 後：
   - 本機伺服器在約 300 ms 內看到該讀取連線被關閉，preload 記錄到 abort，而且早於 closeAll 返回；
   - 程序在 closeAll 返回後以 0 結束，總時間有界。

   缺少 stdin 處理（N11b）時程序不會結束；缺少 abort（N11d）時，連線要到程序結束才會關閉。
8. **SIGTERM**：同上情境改送 SIGTERM，程序在有界時間內結束，abort 與 closeAll 都有被呼叫（N11c）。
9. **meta 預算**：呼叫帶 `_meta.web_search_work_ms=300`，DEFAULT_TIMEOUT 維持大值，頁面卡住。約 1 s 內回 timeout（N14、N14b）。
10. **傳輸層取消**：client 以 AbortSignal 取消呼叫，伺服器端的讀取被中止，連線關閉（N14c）。
11. **啟動時拒絕不合法設定**：DEFAULT_TIMEOUT=300001、MAX_CONTENT_LENGTH=0、BROWSER_HEADLESS=maybe 時，server 都以錯誤結束（N43、N05d、N08i）。
12. **cleanupReserve**：DEFAULT_TIMEOUT=2000，頁面卡住。依現行公式，保留額度是 1000 ms，回應約在 1000 ms 到達；保留額度為 0 的實作會接近 2000 ms。斷言回應在 1500 ms 內，以區分兩者（N42）。
13. **瀏覽器設定**：HTTP 回空文字以觸發 fallback，preload 回傳上述 fake browser。
    - launch 選項：BROWSER_HEADLESS=false 時 headless 為 false（N08h）；一律帶 `channel: 'chromium'`（FU02）。
    - newContext 收到的 UA 含 `Chrome/777.0.0.0`，而且不含 Headless（FU03）。
14. **工具文案**：從 tools/list 取得三個工具的描述與參數說明，不含「comprehensive」「complete full text」「verified」等承諾性字樣，且都含 citation_workflow 的分流句（AF39 Node 部分）。

Python：在 test_citation_skill_activation.py 斷言：載入的 citation runtime instructions 含新段落的關鍵句，例如「Do not use Web Search or browse other websites to find papers」與「honestly report」，而且只出現一次（AF39）。

執行新測試、三份既有 Node 測試，以及隔離的 citation focused pytest，記錄後 commit：`test(web-search): cover server entry wiring and lifecycle [F6-S1]`。

## F6-S2：生命週期聚焦案例
- **修改**：tests/test-browser-lifecycle.mjs、tests/test-content-contract.mjs。

最少案例：
1. **導覽卡住**：stub page 的 goto 與 waitForSelector 只有在帶 timeout 時才會逾時，否則永不返回。在操作上限調小（例如 50 ms）、呼叫預算遠大於上限（例如 2000 ms）的情況下，下列各自在接近操作上限時結束，而不是等到呼叫預算用完：
   - 頁面讀取的 goto（N16c）；
   - Google 搜尋的 goto 與結果等待；
   - Bing 搜尋的 goto 與結果等待；
   - F3-S3 的連結解析導覽。
2. **page 排隊逾期**：MAX_CONCURRENT_PAGES=1。第一個呼叫占住 page，第二個呼叫以短預算排隊，必須在期限附近拒絕，而且從未開啟 page（N09g）。
3. **明確中止進行中的 HTTP**：本機伺服器卡住，預算仍遠。呼叫 budget.abort() 後，socket 在 250 ms 內關閉，狀態為 cancelled（N26）。F4-S1 加上操作總時間上限後，只有這種明確中止案例能殺死它。
4. **lease 歸零**：上述中止與逾時情境之後，page 與 HTTP 的 active 計數都回到 0，沒有殘留 timer。
5. **class/id 不刪內容**：content-contract 加入 class 或 id 含 nav、footer、comment、sidebar、menu、banner、cookie 的元素，其文字都必須保留（N07c）。
6. **移除恆真斷言**：移除或改寫 content-contract 中那個不可能失敗的 includeContent=false 斷言（AF29），改由 F6-S1 案例 1 守護，並在註解中指向它。
7. **可選**：子預算 dispose 後，父 signal 的 abort listener 數量回到原值（N09b）。

執行 Node 測試，記錄後 commit：`test(web-search): cover hung navigation, queue expiry and explicit aborts [F6-S2]`。

## F6-S3：突變複驗
- **相依**：F6-S1、F6-S2。
- **證據**：evidence/F6-S3/。

### 準備暫存複本（在 repository 外，本次專用的暫存根目錄下）
- **Node**：
  - 複製 app/vendor/web-search-mcp 的 src/、tests/、package.json、tsconfig.json；node_modules 用 symlink。
  - 在複本內以 node_modules/typescript/bin/tsc 編譯出複本自己的 dist/。
  - 測試在複本內執行，例如 `node tests/test-content-contract.mjs`。content-contract 與 browser-lifecycle 是靜態 import ../dist，retention 也會讀取 dist 旁的 src/index.ts，所以不能把 repo 的測試指向暫存 dist。
- **Python**：
  - 只複製 app/agent、app/skills、app/rag、app/tests、app/pyproject.toml、app/poetry.toml；app/vendor 用 symlink。
  - 不得複製 app/desktop（約 16 GB）或 app/store（使用者資料）。
  - 在複本根目錄以 PYTHONPATH 指向複本，執行 focused pytest。
- **對照組**：每個複本在套用突變前先跑一次對照，全綠才開始計數；對照不綠就修正複本，不得把結果記為「殺死」。

### 判定與紀錄
- 依 [突變清單](../context/mutation-survivors.md) 逐一套用單點突變。至少一個測試非零退出，即為「殺死」；套用下一個之前先還原。
- 每個突變的結果立即以一行 JSON 追加到 evidence/F6-S3/results.jsonl，內容為 id、類別、結果（killed、survived、equivalent、not_applicable）、失敗的測試或理由。續作時略過已記錄的 id。
- 因 F3-S2 刪除 DuckDuckGo、Brave 與 Bing 首頁流程而已不存在的突變，記為 not_applicable 並寫明原因。
- 處理規則：
  - 必殺項若存活，先判斷是測試缺口還是等效突變：
    - 測試缺口：補上斷言（屬於本步的測試改動），再重驗；
    - 等效突變，或因修正已不存在對應程式：寫明理由。
  - 可選項存活時，記錄理由即可。
- 整個過程不得修改 repo 的 dist 或 production 檔。

把突變定義腳本、results.jsonl 與彙總，連同補上的測試一起 commit：`test(web-search): record mutation re-check [F6-S3]`。

## 階段界線
- 不引入測試框架或新依賴，只用 node:assert、node:http、node:child_process 與既有 SDK client。
- 新測試不得依賴公開網路或真實 Chromium。
- 時間門檻要放在「正確行為」與「被保護的錯誤行為」兩個預期值之間。效能類門檻（例如線性時間）至少保留 5 倍餘裕。
- 若出現不穩定的測試，先修正測試設計，不放寬產品行為。
