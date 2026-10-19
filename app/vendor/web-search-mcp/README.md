# Web Search MCP server（內附修改版）

這是 agent 的全域 `web_search` MCP server。原始專案為 [mrkrsl/web-search-mcp](https://github.com/mrkrsl/web-search-mcp)（MIT，見 [LICENSE](LICENSE)），以 upstream commit `eeb03f8`（package 0.3.1）為基礎，再加上本專案的修正；修正後以 Node 腳本直接啟動 `dist/index.js`，由 Playwright 的 Chromium／Firefox 抓取 Bing、DuckDuckGo、Brave 結果，不需要 API key。

## 與 upstream 的差異

- `src/search-engine.ts`：
  - 任何結束路徑都回傳已取得的最佳結果與其引擎名稱。後續引擎空結果或失敗、較低分的 Brave 達門檻、分數 0 的非空結果、錯誤處理本身失敗，都不再丟掉先前的 Bing 結果。
  - 備援順序改為 Bing → DuckDuckGo → Brave。
  - Brave 回 4xx（限流或驗證頁）時立即放棄，不再等待結果 selector，也不另開瀏覽器重試。
- `tests/test-search-result-retention.mjs`：上述行為的離線回歸。封鎖網路、fetch、TLS 與瀏覽器啟動，並以假 Playwright browser 驗證 Brave 被阻擋的情境。
- `package-lock.json`：補上 `zod` 並對齊 0.3.1 的 lock（MCP SDK 1.15.0、Playwright 1.54.2、TypeScript 5.8.3）。upstream 提交的 lock 停在 0.2.2，而且缺 `zod`。較新的依賴（MCP SDK 1.29、TypeScript 5.9）會讓 `src/index.ts` 的 `server.tool()` 型別檢查出現 TS2589；兩者產生的 `dist` 相同，但為了讓 `npm run build` 乾淨通過，暫不升級。
- 未帶入 upstream 的 README、`docs/`、`mcp.json` 範例、未使用的 `scripts/bundle.js`、舊式 `.eslintrc.json`，以及需要連網的手動測試腳本。

## 建置與檢查

在 Conda `app` 環境（提供 Node 與 npm）、本目錄執行：

```bash
npm ci
npx playwright install chromium firefox
npm run build
node tests/test-search-result-retention.mjs
```

`dist/` 與 `node_modules/` 是本機產物，不進版控。Playwright 瀏覽器版本須符合 lock 中的 Playwright；已下載過的瀏覽器會沿用。
