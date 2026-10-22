# 驗收發現（2026-10-22）
本文件是 2026-10-20 web search／citation 計劃驗收結果的持久紀錄，也是本修正計劃的工作清單。驗收當時的覆核紀錄與 `/tmp` 證據不在 repository 內，主機重開機後也已清除。執行者只依本文件與 repository 現況工作。

- **驗收對象**：GUI 分支 3225a90..f5cf123 的 20 個執行 commit（舊計劃 harness/plans/2026-10-20-web-search-citation/，已於 2026-10-22 移除；需求基準見 [baseline-2026-10-20-goals.md](baseline-2026-10-20-goals.md) 與 [baseline-2026-10-20-source-spec.md](baseline-2026-10-20-source-spec.md)，其他檔案以 `git show f5cf123:<路徑>` 讀取）。
- **驗收方式**：唯讀。重建 dist 並與 repo dist 逐位元組比對，重跑 Node 測試、focused pytest 與完整 suite；在沙箱外以真實 Python→Node→Chromium 路徑重現；用 155 個單點突變檢查測試敏感度；每個發現至少經一次獨立重現。
- **結論**：有條件通過。核心目標與流程紀律成立（下節）；下列缺陷沒有一項讓計劃規定的 AC 以其證據類型判為不通過，但多數未記錄在舊 build-log，部分 build-log 敘述與程式不符。
- **嚴重度**：已依需求校正。minor 表示偏離需求或使用者會遇到的缺陷，但未讓整個目標失效；note 表示觀察。

## 已確認成立（不需修正，作為回歸基準）
- HEAD f5cf123 的 src 重新編譯後與 repo dist 逐位元組相同。
- Node 測試全過：retention 15/15、content-contract 3 組、browser-lifecycle。focused pytest 67 passed，沙箱外完整 suite 1512 passed。
- 真實 Python→Node 入口：
  - MAX_CONTENT_LENGTH=37 時，省略→37、71→71、0→37、10001 明確拒絕。
  - 環境 allowlist 只含五個設定與呼叫標記，不含 TMPDIR、proxy 或秘密。
  - 所有真實程序檢查都沒有殘留，五分鐘總上限由 Python 外層保證成立。
- Citation 段落與計劃原文逐字相同，執行期確實載入，沒有 runtime 硬封鎖。
- 策略 B、來源引擎、全失敗／零解析／部分成功三者可區分。src 沒有語意評分與 Firefox。
- 流程：20 個 commit 都帶步驟 ID；GUI 分支；沒有 push（origin/GUI 停在 49d7048）；沒有依賴、lock、環境或 AGENTS.md 變更。

## 發現與處置
「位置」指 f5cf123 的檔案與行號；修改後行號會移動，以描述為準。src 指 app/vendor/web-search-mcp/src。

### 正文轉換（對應 R03／R05／AC02／AC04）
| ID | 嚴重度 | 位置 | 觀察與重現 | 處置 |
| --- | --- | --- | --- | --- |
| AF01 | minor | src/enhanced-content-extractor.ts:175–180 | 表格分支用 `element.find('tr')`，會連巢狀表格的列一起取，而每個儲存格又以 `children(cell)` 再渲染一次巢狀表格。結果是每多一層，內容就加倍。重現：把 LEAF 包進 n 層 `<table><tr><td>`，輸出 LEAF 次數為 2^(n-1)：3 層 4 次；16 層 147 萬字元、0.34 s；18 層 590 萬字元、1.2 s。經 stdio server，22 層要 21 s、約 2 GB RSS。重複內容會吃掉 10000 上限，同步運算也無法被 Node 預算中斷。此問題由 cbae2aa [P3-S1] 引入，基線用 `.text()` 不重複 | F1-S1 |
| AF02 | minor | src/enhanced-content-extractor.ts:202–203 | 只轉換第一個 `main, article, [role="main"]`，其餘靜默丟棄，輸出仍顯示 status=text，也沒有任何標記。重現：`<p>Intro</p><article><h2>Story 1</h2></article><article><h2>Story 2</h2></article><p>Tail</p>` 只得到 `## Story 1`；`<aside><article>Related</article></aside><main>Main</main>` 只得到 `Related`。舊 build-log P3-S1 寫「只移除 script/style/noscript/template」，與實作不符 | F1-S1（整頁轉換，見 FA01） |
| AF04 | minor | src/enhanced-content-extractor.ts:197 | 區塊元素清單漏了 dl/dt/dd、details/summary、header/footer/nav/aside/address、form/fieldset/legend/option、hr 等。在壓縮 HTML 上，相鄰文字會黏在一起，例如 `<dl><dt>Term</dt><dd>Def</dd></dl>` 變成 `TermDef` | F1-S1 |
| AF05 | minor | src/enhanced-content-extractor.ts:175–180 | 表格的 `<caption>` 文字遺失；儲存格內若有多個區塊，會插入空行，使該列斷成數行 | F1-S1 |
| AF06 | note（納入） | src/enhanced-content-extractor.ts:89 | HTTP 路徑一律以 UTF-8 解碼。Big5、Shift_JIS、ISO-8859-1 頁面變成亂碼，仍標為 text。基線同樣如此（既有問題），但違反 R03「保留來源文字」 | F1-S3 |
| AF07 | note（納入） | src/enhanced-content-extractor.ts:92、117 | 頁面標題取文件中第一個 `title`（可能是 inline SVG 的 `<title>`），也沒有正規化空白 | F1-S1 |
| AF08 | minor | src/utils.ts:145 | 截斷時的連結保護只認得標籤內沒有 `]` 與換行的 `[label](dest)`。標籤像 `[1]`，或 `<a>` 內含區塊元素時，切在目的地中會留下 `[[1]](<` 這種殘缺開頭。text/plain 內含括號的 URL 也可能在中途被切斷 | F1-S4 |
| AF09 | minor | src/utils.ts:145–151、src/enhanced-content-extractor.ts:204 | 截斷用的連結 regex 遇到大量未閉合 `[` 時是二次方：約 40 KB 耗 1 s，130–150 KB 耗 5 s，340–400 KB 耗 30 s。`.replace(/[ \t]+\n/g)` 遇到長空白串也是二次方。兩者都是同步執行，Node 預算無法中斷，只能靠 Python 外層強制結束；若在 Node 工作期限與 Python 強制結束之間才完成，會變成 AF27 | F1-S4 |
| AF10 | minor | src/enhanced-content-extractor.ts:36–53、67–79、99–121 | 三種情形分類錯誤：(a) 超過 10 MiB 的回應被標為 http_error，HTTP status 與 Content-Type 都顯示 unknown，即使已收到標頭；12 MiB 的 application/pdf 因此無法辨識為不支援的 PDF。(b) HTTP 403/429/503 或逾時後，若瀏覽器遇到 PDF/octet-stream 下載，`page.goto` 會拋 net::ERR_ABORTED，結果成了 http_error，Read error 裡還夾著含 ANSI 跳脫碼的 Playwright call log。(c) 瀏覽器路徑的 parseContent 錯誤，以及 truncate 的 RangeError，都被歸為 http_error，而非 conversion_error。候選本身仍保留 | F1-S3 |

### 瀏覽器 fallback 與局部時間上限（對應 G3／U13／AC10；AF03 屬 F1，其餘屬 F4）
| ID | 嚴重度 | 位置 | 觀察與重現 | 處置 |
| --- | --- | --- | --- | --- |
| AF03 | minor | src/enhanced-content-extractor.ts:99–121 | 瀏覽器讀取在 `goto(domcontentloaded)` 之後立刻 `page.content()`，只讀得到 DOMContentLoaded 當下已存在的 DOM。用真實 Chromium 量測：計時器延遲 ≥5 ms，或 fetch 延遲 ≥20 ms 後才插入的文字，一律回 empty_text；計時器 100/300/700/1500/3000 ms、fetch 200 ms 全部遺失。基線 7026a70 會先等 0.5–1.5 s，再等 `article, main, …` selector 最多 2 s，可取得 50/300/1200 ms 插入的文字。這個等待在 9d16963 [P3-S2a] 被移除，舊 build-log 沒有記錄。舊 AC14 的動態 DOM 證據是同步插入，偵測不到這個問題 | F1-S2 |
| AF19 | minor | src/enhanced-content-extractor.ts:70、src/search-engine.ts:179 | axios 的 `timeout` 是 socket 閒置計時，不是總時間。伺服器若持續慢慢送資料，單頁 HTTP 讀取（上限 6 s）或 DDG 請求（上限 4 s）會一路跑到整次呼叫預算 285 s，期間占住 2 個 HTTP slot 之一，也不會進 fallback。舊 build-log P4-S2b 寫的「HTTP ≤6s/4s」不成立 | F4-S1（單頁 HTTP 部分）；DDG 部分因 F3-S2 刪除 DuckDuckGo 而不再適用 |
| AF20 | minor | src/enhanced-content-extractor.ts:117–119、src/search-engine.ts:102、143、156 | 只有導覽本身有上限。之後的 `page.title()`、`page.content()`、`locator.innerText()`（Playwright 預設 30 s）都沒有局部上限，只受整次預算限制 | F4-S1 |
| AF21 | minor | src/enhanced-content-extractor.ts:128–132 | 每頁 8 s 視窗是在所有候選排隊進 2 個 HTTP slot 之前就同時開始計時，所以排隊時間也計入。頁面需 2–3 s、limit=10 時，尾端候選會變成 timeout 或 not_attempted，原因卻寫「Call deadline exceeded」，即使還剩約 285 s | F4-S1（見 FA05） |
| AF22 | minor | src/browser-pool.ts:180–206 | 自有 Chromium 的辨識靠 `/proc/PID/cmdline.split('\0').includes(ownerFlag)`。Chromium 會把 argv 改寫成一個空白相連的字串（環境含 DBUS_SESSION_BUS_ADDRESS 時已觀察到），於是比對失效，`killOwnedBrowsers()` 什麼都不做。stat 解析用 `split(') ')[1]`，也同樣脆弱。實際上仍無殘留，因為 Playwright 的結束處理與 Python 外層會收尾；經 Python 入口時環境沒有 DBUS，比對可以成立。但舊 build-log P4-S3 宣稱的「僅對仍符合原身分的自有程序群組收尾」從未被真正驗證過 | F4-S2 |
| AF23 | note | — | 同步轉換期間，Node 的呼叫預算無法中斷，只能靠 Python 外層強制結束。這是 AF01／AF09 的後果，修好之後只剩對 ≤10 MiB 輸入的線性轉換 | 由 F1 根除；F7-S2 量測線性 |

### 可見狀態與統計（對應 R06／AC05／AC06／U12）
| ID | 嚴重度 | 位置 | 觀察與重現 | 處置 |
| --- | --- | --- | --- | --- |
| AF11 | minor | src/search-engine.ts:25–35、69–77；src/utils.ts:72–76 | 因 deadline、取消、rate limit 或排隊逾期而沒有嘗試的引擎，仍標為 strategy_stopped，與「已達 limit 而停止」無法區分。若完全沒有引擎執行，標題卻寫「No candidates parsed in this call」 | F5-S1 |
| AF12 | minor | src/search-engine.ts:66 | `state.attempts = Math.max(1, state.attempts)`：即使沒有任何傳輸開始，也記為 1 次 | F5-S1 |
| AF13 | note（納入） | src/search-engine.ts、src/types.ts:99–106 | 零解析的引擎只有計數，沒有已知事實（HTTP status 等）。R06 要求回報「已知事實與必要診斷」 | F5-S1 |
| AF16 | minor | src/enhanced-content-extractor.ts:17–53 | 每次嘗試只重設 httpStatus、contentType、finalUrl、pageTitle，error、長度與 truncated 會沿用前一次嘗試。因此摘要行會混雜兩次嘗試的資料，例如顯示「http_error」卻帶著前一次 HTTP 的 Markdown 長度，或顯示「empty_text」卻帶著已被取代的 403 Read error | F5-S2 |
| AF17 | minor | src/enhanced-content-extractor.ts:19、99–101 | `started()` 在 withPage 回呼內才呼叫，所以瀏覽器 fallback 若在建立 page 之前就失敗（launch 逾時、pool 損壞），既不計數也不列出；前一次 HTTP 的事實也在新嘗試開始時被刪掉 | F5-S2 |
| AF18 | minor | src/utils.ts:85–99；README | Read statistics 的口徑沒有定義：candidates_attempted 與 source_read_attempts 的差別、redirect 是否計入；transport_retries 在結構上恆為 0。R06 要求明確區分「按來源計數」與「按重試次數計數」 | F5-S2、F7-S1 |
| AF14 | note（納入） | src/index.ts:96–105 | get-web-search-summaries 只檢查 `!obj.query`，所以純空白 query 會以空字串送到各引擎；full-web-search 則會拒絕 | F5-S3 |
| AF15 | minor | src/index.ts:41 | full-web-search 的 query 參數描述仍保留「recommended for comprehensive research」，與 R01「不承諾最完整資訊」不符 | F5-S3 |

### Python 包裝（對應 G6／AC10／AC12）
| ID | 嚴重度 | 位置 | 觀察與重現 | 處置 |
| --- | --- | --- | --- | --- |
| AF24 | minor | app/agent/mcp.py:303、310、322、328、334 | `/proc/<pid>/stat` 以 `split(") ", 1)` 解析，之後的 `int(fields[1])` 在 try 之外，而且掃描的是整台主機的程序。只要任一程序的 comm 含「) 」就會拋 ValueError：discovery 失敗時 web_search 成為 applied_but_unavailable；呼叫中失敗時，`finally: await watcher`（:395）會把已收到的結果換成 ValueError。重現：把 /bin/sleep 複製為 `a) b c d` 並執行，再經 agent.mcp 載入 web_search | F2-S1 |
| AF25 | minor | app/agent/mcp.py:358–368、386–392 | 呼叫端取消後，task 若在 settle 期間自行以非取消例外結束，沒有人取回該例外，日誌會出現帶 traceback 的「Task exception was never retrieved」。有真實 Chromium 時 8/8 次重現 | F2-S2 |
| AF26 | minor | app/agent/mcp.py:428–433、478–484 | Node 啟動失敗、缺模組或環境錯誤時，診斷只顯示「load: ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)」。真正原因（例如 McpError: Connection closed）與 stderr log 位置都沒有出現，違反 R11「工具缺失不能只留在不易察覺的內部例外裡」 | F2-S2 |
| AF27 | minor | app/agent/mcp.py:369–385 | Node 若在 Python 工作期限之後、強制結束之前才寫出遲到的回應，已取消的 session 會在 TaskGroup 內拋 BrokenResourceError。Agent 看到的是「Tool error: ExceptionGroup…」，而不是「timed out before a result was received」。總時間上限仍成立，但違反舊 P5-S3「未取得結果時只能說未取得」 | F2-S2 |
| AF28 | note（納入） | app/agent/mcp.py:382–385 | 逾時訊息沒有說明等了多久，也沒說是哪個設定（DEFAULT_TIMEOUT）造成的 | F2-S2 |

### 測試守護（突變存活清單見 [mutation-survivors.md](mutation-survivors.md)）
| ID | 嚴重度 | 位置 | 觀察 | 處置 |
| --- | --- | --- | --- | --- |
| AF29 | minor | tests/test-content-contract.mjs:76–81；src/index.ts:215–217 | AC06「includeContent=false 讀取 0 次」的離線斷言是恆真的：它只格式化預先建好的候選，formatter 本來就不會發請求，所以不可能失敗。index.ts 真正的切換點沒有任何測試 | F6-S1、F6-S2 |
| AF30 | minor | src/index.ts:188–258 | 沒有任何已提交測試會 import 或啟動 index.ts。以下行為都沒有回歸保護：stdin end/close、SIGTERM、shutdown 時中止預算並關閉 pool、summaries 不再呼叫 closeAll、handler 的參數接線 | F6-S1 |
| AF31 | minor | src/index.ts:188–201；src/browser-pool.ts:11–21、102–107；app/agent/mcp.py:281、473 | Node 端的契約都沒有斷言：`_meta.web_search_work_ms`、cleanupReserve、DEFAULT_TIMEOUT 上限、BROWSER_HEADLESS、部署值 MAX_CONTENT_LENGTH=0。Python 端也沒有斷言 loader 會使用 spec.env 的 DEFAULT_TIMEOUT，以及 300000 的上限 | F6-S1（Node）、F2-S2（Python） |
| AF32 | minor | tests/test-search-result-retention.mjs:135–152 | U12 的輸出文字斷言不完整：沒有檢查零解析說明句、失敗原因、strategy_stopped 行、合併多個來源引擎的候選 | F5-S1 |
| AF33 | minor | tests/test-browser-lifecycle.mjs:84 等 | 舊 P4-S2 要求的聚焦案例缺漏：沒有卡住的 goto（stub 的 goto 立即回傳）、沒有 withPage 排隊逾期、沒有明確中止進行中的 HTTP 讀取、中止情境後沒有檢查 lease 歸零 | F6-S2 |
| AF34 | minor | src/browser-pool.ts:74–88、195–206 | 沒有測試涵蓋「browser.close 永不返回」時的有界收尾，以及以 owned PID 強制收尾的路徑 | F4-S2 |
| AF35 | minor | app/agent/mcp.py:298–342 | 測試用的 lifecycle server 是直接子程序，所以後代程序展開、群組 kill、身分檢查與週期觀察這幾個分支都沒被測到。實測：拿掉後代展開後，自成 session 的孫程序會存活 | F2-S1 |
| AF36 | minor | app/agent/startup.py:54–63 | startup 測試只模擬 resolver 失敗；load 階段的診斷與「MCP loader unavailable」診斷都沒有斷言 | F2-S2 |
| AF37 | minor | 多處 | 單點缺口：每筆結果的 limit 防護（一批超量時會回 6 筆）、`<base href>` 測試資料與 final URL 解析結果相同而無法分辨、Brave 百分比編碼保留、targetCount、originalLength 的 code point 計算、Brave 暫態重試只一次的上限 | F1、F5（見突變清單）；Brave 相關部分因 F3-S2 刪除 Brave 而不再適用 |
| AF38 | minor | app/tests/test_mcp.py:627–651 | startup/initialize 兩個模式在第一次 import adapter（約 0.2 s）之前就開始計時。測試單獨執行時量到 0.82–0.84 s，超過 0.8 s 的門檻而失敗；在模組內依序執行才會通過 | F2-S2 |
| AF39 | note（納入） | app/tests/test_citation_skill_activation.py、src/index.ts | 新 Citation 段落與三個工具描述都沒有測試守護：刪掉段落，suite 仍然全綠 | F6-S1 |

### 文件、證據與流程
| ID | 嚴重度 | 位置 | 觀察 | 處置 |
| --- | --- | --- | --- | --- |
| AF40 | minor | README.md:24 | 根目錄 README 仍寫 `npx playwright install chromium firefox` | F7-S1 |
| AF41 | minor | — | P2-S3 改了三個引擎的 parser 之後，沒有再經真實入口或公開引擎觀測。實際上幾乎只有 Bing 在運作：DDG 零解析而原因不明，Brave 回 429。Bing 候選全是 `bing.com/ck/a` 中介頁，舊 build-log 卻寫「部分」 | F3（FU01：引擎改為 Google→Bing）；F7-S3 重新觀測 |
| AF42 | minor | — | 舊計劃的證據放在 `/tmp`，主機重開機後已全部消失；多數真實程序檢查只有文字敘述 | PLANS 證據規則；F7 |
| AF43 | note | — | 舊 build-log 的階段狀態表，在中間的 commit 落後於實際進度 | PLANS 執行契約第 4 項 |
| AF44 | minor | 舊 build-log | 幾項宣稱與實作不符：P3-S1「只移除 script/style」、P4-S2b「HTTP ≤6s/4s」、P4-S3「自有程序群組收尾」，以及 AC 表 16 列都標為無保留 Pass | 以本文件為更正紀錄；舊計劃目錄不修改（見 GOALS） |

## 不納入本次修正的觀察
這些項目在驗收中確認為設計取捨、影響可忽略或屬於其他決策。它們不是本計劃的必要工作；需要時由使用者另行決定。
| ID | 觀察 | 不納入理由／後續 |
| --- | --- | --- |
| X01 | BrowserPool.damaged 在同一程序內不會自行恢復 | 屬 fail-closed 設計；每次呼叫都是獨立的 Node 程序，影響只到該次呼叫結束 |
| X02 | launch 完成並自動關閉的空窗期，新呼叫可能拿到正在關閉的 browser | 理論情境，未觀察到 |
| X03 | Python 以 SIGKILL 強制結束後，`/tmp/playwright_chromiumdev_profile-*`（約 190 KB）會殘留 | 罕見且體積小；可列為後續 |
| X04 | 啟動過 Chromium 的 Node 收到 SIGHUP 後仍存活 | Python 父程序結束時會關閉 stdin，實際沒有影響 |
| X05 | SIGTERM/SIGINT 由 Playwright 自己的 handler 先收尾 | 結果有界且正確 |
| X06 | Python 每 20 ms 掃描 /proc 的成本 | 實測 48 個程序時每次 0.70 ms，佔 3.4% |
| X07 | CLI `/status` 不顯示 web_search 的不可用原因 | stderr 回顯、cli.log 與 extension 管理介面都會顯示 |
| X08 | 缺 dist 或 node 時的診斷文字較籠統 | note，維持現狀 |
| X09 | web_search 卡住時，session 啟動要等整個 DEFAULT_TIMEOUT（discovery 用的是整次呼叫預算） | 已決定（FU05）：F2-S3 設定 15 秒啟動上限 |
| X10 | 非 web_search 的 MCP 卡住時，啟動無上限 | 既有問題；舊計劃的時間上限只涵蓋 web_search |
| X11 | Agent 看到的 URL 是 WHATWG 序列化後的形式，原始觀測值不顯示 | note |
| X12 | 未被呼叫的 Google parser 死碼，以及舊 content-extractor.ts | 已於 2026-10-22 依使用者指示清理（OD3），連同其他死碼與只寫不讀的欄位 |
| X13 | Bing ck/a 中介頁讓 full-web-search 的正文讀取實際上拿不到目標頁 | 已決定（FU01、FU04）：F3 改用 Google 為主，並以實際導覽解開 Google 與 Bing 的跳轉包裝 |
| X14 | 呼叫快速失敗時（server 自行結束、連線關閉），包裝層不會主動回收已自成 session 的後代程序；只有期限到時才強制收尾 | 規劃審查時發現。實際產品路徑中，Chromium 在 Node 結束、DevTools pipe 關閉時會自行退出，未觀察到殘留。屬於 R09 的強化，可列為後續 |
