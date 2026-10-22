# Web Search MCP server（內附修改版）

這是 agent 的全域 `web_search` MCP server。原始專案為 [mrkrsl/web-search-mcp](https://github.com/mrkrsl/web-search-mcp)（MIT，見 [LICENSE](LICENSE)），以 upstream commit `eeb03f8`（package 0.3.1）為基礎，再加上本專案的修正；修正後以 Node 腳本直接啟動 `dist/index.js`，以單一 Playwright 完整版 Chromium 搜尋 Google，不需要 API key。

## 與 upstream 的差異

- `src/search-engine.ts`：
  - 只搜尋 Google，不做詞彙評分或勝出批次選擇；同一批結果中 URL 完全相同的只保留一筆。Google 回傳不足 limit 時如實回報，不以其他引擎補足。呼叫中途失敗時保留已接納的候選，兩個搜尋工具都列出引擎執行狀態與每筆來源。
  - 介面語言依查詢：查詢含漢字時 `hl=zh-TW`，其他一律 `hl=en`。這是固定規則，其他語言暫歸英文。
  - Google 回 HTTP 4xx 或被導到 `/sorry/` 時，記錄 status 與最終路徑並回報為引擎錯誤，不重試、不繞過；沒有備援引擎。
  - 已移除 DuckDuckGo、Brave 與 Bing。在本機與本 IP 上，DuckDuckGo 與 Brave 一律被擋（202／429）；Bing 在 2026-10-22 的公開觀測中兩次沒有正式結果、一次回傳與查詢無關的結果，依使用者決定移除。
  - 結果連結若是引擎自己的跳轉包裝（host 等於搜尋主機，例如 Google 的 `/goto`），在同一個搜尋頁上以實際導覽解開：referer 為搜尋頁，第一個離開搜尋主機的主框架導覽請求就是目的地，不等目標回應，所以 PDF 與慢速目標也能取得網址。每筆上限 6 秒；不解碼參數，也沒有網址辭典。
- `src/browser-pool.ts`：所有瀏覽器工作使用 Playwright 完整版 Chromium（`channel: 'chromium'`，新 headless 模式），每個 context 用固定格式的一般 Chrome UA，主版號取自實際瀏覽器。自有 Chromium 以 owner flag、process group 與 start time 辨識；Chromium 把 argv 改寫成單一字串時仍可辨識，close 卡住時以 SIGKILL 有界收尾。
- `src/enhanced-content-extractor.ts`：正文轉換與讀取，見下方「正文讀取」。
- `tests/`：離線回歸，見「建置與檢查」。
- `package-lock.json`：補上 `zod` 並對齊 0.3.1 的 lock（MCP SDK 1.15.0、Playwright 1.54.2、TypeScript 5.8.3）。upstream 提交的 lock 停在 0.2.2，而且缺 `zod`。較新的依賴（MCP SDK 1.29、TypeScript 5.9）會讓 `src/index.ts` 的 `server.tool()` 型別檢查出現 TS2589；兩者產生的 `dist` 相同，但為了讓 `npm run build` 乾淨通過，暫不升級。
- 未帶入 upstream 的 README、`docs/`、`mcp.json` 範例、未使用的 `scripts/bundle.js`、舊式 `.eslintrc.json`，以及需要連網的手動測試腳本。
- 已刪除 upstream 中從未被呼叫的程式：舊的 `src/content-extractor.ts`、只有它們使用的工具函式與型別，以及沒有任何讀取者的結果欄位（如 `contentPreview`、`wordCount`、`fetchStatus`）；也移除未使用的依賴 `p-retry` 與 `esbuild`（`tsx` 仍自帶 esbuild）。

`app/agent/mcp.py` 預設以 Conda 環境的 `node` 啟動本目錄的 `dist/index.js`；設定 `AGENT_MCP_WEB_SEARCH_COMMAND`／`AGENT_MCP_WEB_SEARCH_ARGS` 可改用其他啟動方式，`AGENT_ENABLE_MCP_WEB_SEARCH=0` 則停用。Python 端只管 MCP client 的啟動、生命週期與診斷，不含任何搜尋邏輯：web_search 啟動（啟動程序、initialize、列出工具、收尾）以 min(15000 ms, DEFAULT_TIMEOUT) 為上限，逾時時本 session 標為不可用，其他工具照常；每次工具呼叫仍以 DEFAULT_TIMEOUT 為總上限。

## 建置與檢查

在 Conda `app` 環境（提供 Node 與 npm）、本目錄執行：

```bash
npm ci
npx playwright install chromium
npm run build
node tests/test-search-result-retention.mjs
node tests/test-content-contract.mjs
node tests/test-browser-lifecycle.mjs
node tests/test-server-entry.mjs
```

`dist/` 與 `node_modules/` 是本機產物，不進版控。Playwright 瀏覽器版本須符合 lock 中的 Playwright；`npx playwright install chromium` 會安裝完整版 Chromium，已下載過的瀏覽器會沿用。四份測試都不需要網路；只有 `test-server-entry.mjs` 會啟動 `dist/index.js`（以測試專用的 `tests/fixtures/stub-engines.mjs` 取代引擎與瀏覽器啟動）。

完整版 Chromium 會在 TMPDIR 建立 unix socket，路徑必須很短（約 108 字元以內），否則啟動時以 SIGTRAP 崩潰。經 Python 啟動時 Node 拿不到 TMPDIR、使用 `/tmp`，不受影響；在路徑很長的沙箱 TMPDIR 下直接以 node 啟動真實 Chromium 時，請改用短路徑。

## Web Search 設定

Python 只向 web_search 傳下表五個 Node 設定；不複製其他 provider 環境或秘密，也不轉送 TMPDIR/proxy。底層 SDK 的 HOME/PATH 等必要環境沿用既有機制。

| 設定 | 預設 | 有效語意 |
| --- | --- | --- |
| AGENT_ENABLE_MCP_WEB_SEARCH | true | Python 開關，false/0 優先停用 |
| AGENT_MCP_WEB_SEARCH_COMMAND / ARGS | repo dist/index.js | 自訂 command 完全取代預設 command/args；仍收到相同 Node allowlist，自訂程式的 CLI 語意自行負責 |
| MAX_CONTENT_LENGTH | 10000 | 部署正文 Markdown Unicode code points，整數1–10000；工具顯式1–10000優先，省略或0採部署預設。metadata與截斷標記不計，不能超過10000 |
| DEFAULT_TIMEOUT | 300000 ms | 單次呼叫總預算，整數1–300000；包含排隊、啟動、讀取、收尾，不是每個請求的 timeout。預設工作285000／清理15000 ms；短預算保留最多一半供清理 |
| BROWSER_HEADLESS | true | true/false；所有瀏覽器路徑一致 |
| MAX_CONCURRENT_PAGES | 2 | 正整數，每個 Node 程序活躍 context/page 上限 |
| MAX_CONCURRENT_HTTP | 2 | 正整數，每個 Node 程序活躍 HTTP 讀取上限 |

優先序：停用 → 自訂或預設啟動入口 → 明確部署設定 → 內建預設；每次工具顯式正文長度再優先。非法設定明確診斷，不靜默 clamp 或部分 parse。

ENABLE_RELEVANCE_CHECKING、RELEVANCE_THRESHOLD、FORCE_MULTI_ENGINE_SEARCH、MAX_BROWSERS、BROWSER_TYPES、BROWSER_FALLBACK_THRESHOLD、DEBUG_BROWSER_LIFECYCLE、DEBUG_BING_SEARCH 不再支援。引擎、瀏覽器模式、UA 與各操作上限都是程式內的具名常數，不是環境設定。

搜尋候選先固定；includeContent 預設 true，false 不讀正文。成功讀取以保守 Markdown 保留來源文字與實際連結，PDF/失敗仍交付搜尋資料。HTTP200或非空文字不代表目標文章、摘要、相關性或研究支持。論文發現、書目、摘要與引用請用 citation_workflow。

## 正文讀取

- **整頁轉換**：以整個 `<body>` 依原順序轉換，只移除 script、style、noscript、template；不猜主文，也不因 class 或 id 刪除內容。導覽、頁尾等文字保留，由 10000 上限與透明的截斷標記處理長度。
- **表格**：每個表格只輸出自己的列，儲存格內容收成單行，巢狀表格只在其儲存格內出現一次；`<caption>` 在列前輸出一次（`Table caption:`）。
- **區塊分隔**：dl/dt/dd、details/summary、header/footer/nav/aside 等預設區塊元素前後都有分隔，壓縮過的 HTML 不會把相鄰文字黏成一個詞。
- **編碼**：HTTP 讀取依 BOM → Content-Type charset → 前 4096 bytes 的 `<meta charset>`／http-equiv → UTF-8 的順序判定，以 Node 內建 TextDecoder 解碼；輸出的 `Character encoding:` 行列出編碼與來源，不支援的 label 以 UTF-8 解碼並註明。
- **媒體**：PDF 與其他不支援的媒體為 unsupported_media；超過 10 MiB 讀取上限時保留已收到的 status、Content-Type 與網址；瀏覽器導覽變成下載時也是 unsupported_media。
- **晚渲染**：HTTP 讀不到文字、或回 403/429/503／逾時時，以瀏覽器讀取。瀏覽器在 DOMContentLoaded 之後，等到「網路靜止，且頁面已有可見文字」，最多 3000 ms（取 min(上限, 剩餘預算)）；仍沒有文字時維持 empty_text，並寫出已等待的毫秒數。
- **截斷**：以 Unicode code points 計算；切點落在連結或裸網址內時捨棄整個連結或網址，不留下殘缺的開頭；轉換與截斷都是線性時間。

## 時間上限

- 每次呼叫的總上限是 DEFAULT_TIMEOUT 扣掉清理保留額度（預設 285000 ms），由 Python 外層再保證一次。
- 局部上限都是該操作的總時間上限，不只是閒置計時：單頁 HTTP 讀取 6000 ms、導覽後的頁面讀取 6000 ms、搜尋導覽 4000 ms、結果等待 3000 ms、連結解析每筆 6000 ms、晚渲染等待 3000 ms，皆取 min(上限, 剩餘預算)。
- full-web-search 每頁 8000 ms 的讀取視窗，從該頁實際取得第一個 HTTP 讀取 slot 起算，涵蓋 HTTP 與瀏覽器 fallback；排隊只受整次預算限制。逾時原因可區分：`HTTP page read exceeded its <ms> ms operation limit`、`page read window exceeded (<ms> ms)`、`Call deadline exceeded`。

## 輸出中的狀態與統計

- **引擎行**：`- <引擎>: attempted=…; attempts=…; parsed_count=…; status=…`，之後依序可能有 `reason=`、`http_status=`、`final_path=`，最後是 `error=`。
  - status：completed（有解析結果）、zero_parsed（已執行但零解析）、error、not_attempted（沒有開始）。
  - not_attempted 的 reason：deadline（呼叫期限已到）、cancelled（呼叫被取消）、rate_limited（程序內限流拒絕）、queue_expired（在佇列中等待時逾期）。
  - attempts 只計實際開始的嘗試：已取得 page slot、開始啟動瀏覽器或建立 context。
- **零候選**：分別說明引擎失敗、零解析，或沒有開始（附原因）。
- **連結**：解開的包裝顯示 `Link: engine redirect from <host> resolved by navigation in <ms> ms`；解不開時顯示 `Link: engine redirect not resolved (<結果>: <原因>)`，並註明該 URL 是引擎的包裝網址。結果為 stayed_on_engine_host（包裝頁已回應但沒有離開搜尋主機）、timeout、failed 或 not_started。
- **頁面讀取**：摘要描述最後一次已開始的嘗試；每次嘗試另起一行，保留自己的 HTTP status、讀取狀態、Content-Type、final URL、編碼、等待時間、長度與錯誤。只在佇列中等待、從未開始的 fallback 顯示為 `not started` 與原因。
- **Read statistics 口徑**：
  - `source_read_attempts`：實際開始的 HTTP 與瀏覽器讀取次數（已發出請求，或已開始啟動瀏覽器、建立 context）；只在佇列中等待的不計。
  - `candidates_attempted`：至少開始過一次讀取的候選數。
  - 同一次 HTTP 讀取內跟隨的 redirect 不另計。
  - `parsed_count`（引擎行）是引擎回傳、尚未去重與套用 limit 的列數。
  - `engine_redirects_resolved`／`engine_redirects_unresolved`：搜尋連結是引擎包裝網址的候選中，解開與未解開的數量。

  輸出在統計行之後附同樣內容的一行 `Statistics scope:`。
