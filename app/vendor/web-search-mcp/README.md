# Web Search MCP server（內附修改版）

這是 agent 的全域 `web_search` MCP server。原始專案為 [mrkrsl/web-search-mcp](https://github.com/mrkrsl/web-search-mcp)（MIT，見 [LICENSE](LICENSE)），以 upstream commit `eeb03f8`（package 0.3.1）為基礎，再加上本專案的修正；修正後以 Node 腳本直接啟動 `dist/index.js`，以單一 Playwright Chromium 抓取 Bing、Brave，並以 HTTP 讀取 DuckDuckGo，不需要 API key。

## 與 upstream 的差異

- `src/search-engine.ts`：
  - 逐引擎依序補到候選 limit，不做詞彙評分或勝出批次選擇；URL完全相同才合併來源。後續失敗保留既有候選，兩個搜尋工具都列出各引擎執行狀態與每筆來源。
  - 備援順序改為 Bing → DuckDuckGo → Brave。
  - Brave 回 4xx（限流或驗證頁）時立即放棄，不再等待結果 selector，也不另開瀏覽器重試。
- `tests/test-search-result-retention.mjs`：上述行為的離線回歸。封鎖網路、fetch、TLS 與瀏覽器啟動，並以假 Playwright browser 驗證 Brave 被阻擋的情境。
- `package-lock.json`：補上 `zod` 並對齊 0.3.1 的 lock（MCP SDK 1.15.0、Playwright 1.54.2、TypeScript 5.8.3）。upstream 提交的 lock 停在 0.2.2，而且缺 `zod`。較新的依賴（MCP SDK 1.29、TypeScript 5.9）會讓 `src/index.ts` 的 `server.tool()` 型別檢查出現 TS2589；兩者產生的 `dist` 相同，但為了讓 `npm run build` 乾淨通過，暫不升級。
- 未帶入 upstream 的 README、`docs/`、`mcp.json` 範例、未使用的 `scripts/bundle.js`、舊式 `.eslintrc.json`，以及需要連網的手動測試腳本。
- 已刪除 upstream 中從未被呼叫的程式：舊的 `src/content-extractor.ts`、Google 結果解析器、只有它們使用的工具函式與型別，以及沒有任何讀取者的結果欄位（如 `contentPreview`、`wordCount`、`fetchStatus`）；也移除未使用的依賴 `p-retry` 與 `esbuild`（`tsx` 仍自帶 esbuild）。

`app/agent/mcp.py` 預設以 Conda 環境的 `node` 啟動本目錄的 `dist/index.js`；設定 `AGENT_MCP_WEB_SEARCH_COMMAND`／`AGENT_MCP_WEB_SEARCH_ARGS` 可改用其他啟動方式，`AGENT_ENABLE_MCP_WEB_SEARCH=0` 則停用。

## 建置與檢查

在 Conda `app` 環境（提供 Node 與 npm）、本目錄執行：

```bash
npm ci
npx playwright install chromium
npm run build
node tests/test-search-result-retention.mjs
node tests/test-content-contract.mjs
node tests/test-browser-lifecycle.mjs
```

`dist/` 與 `node_modules/` 是本機產物，不進版控。Playwright 瀏覽器版本須符合 lock 中的 Playwright；已下載過的瀏覽器會沿用。

## Web Search 設定

Python 只向 web_search 傳下表五個 Node 設定；不複製其他 provider 環境或秘密，也不轉送 TMPDIR/proxy。底層 SDK 的 HOME/PATH 等必要環境沿用既有機制。

| 設定 | 預設 | 有效語意 |
| --- | --- | --- |
| AGENT_ENABLE_MCP_WEB_SEARCH | true | Python 開關，false/0 優先停用 |
| AGENT_MCP_WEB_SEARCH_COMMAND / ARGS | repo dist/index.js | 自訂 command 完全取代預設 command/args；仍收到相同 Node allowlist，自訂程式的 CLI 語意自行負責 |
| MAX_CONTENT_LENGTH | 10000 | 部署正文 Markdown Unicode code points，整數1–10000；工具顯式1–10000優先，省略或0採部署預設。metadata與截斷標記不計，不能超過10000 |
| DEFAULT_TIMEOUT | 300000 ms | 單次呼叫總預算，整數1–300000；包含排隊、啟動、讀取、收尾，不是每個請求的 timeout。預設工作285000／清理15000 ms；短預算保留最多一半供清理 |
| BROWSER_HEADLESS | true | true/false；三條瀏覽器路徑一致 |
| MAX_CONCURRENT_PAGES | 2 | 正整數，每個 Node 程序活躍 context/page 上限 |
| MAX_CONCURRENT_HTTP | 2 | 正整數，每個 Node 程序活躍 HTTP 讀取上限 |

優先序：停用 → 自訂或預設啟動入口 → 明確部署設定 → 內建預設；每次工具顯式正文長度再優先。非法設定明確診斷，不靜默 clamp 或部分 parse。

ENABLE_RELEVANCE_CHECKING、RELEVANCE_THRESHOLD、FORCE_MULTI_ENGINE_SEARCH、MAX_BROWSERS、BROWSER_TYPES、BROWSER_FALLBACK_THRESHOLD、DEBUG_BROWSER_LIFECYCLE、DEBUG_BING_SEARCH 不再支援。

搜尋候選先固定；includeContent 預設 true，false 不讀正文。成功讀取以保守 Markdown 保留來源文字與實際連結，PDF/失敗仍交付搜尋資料。HTTP200或非空文字不代表目標文章、摘要、相關性或研究支持。論文發現、書目、摘要與引用請用 citation_workflow。
