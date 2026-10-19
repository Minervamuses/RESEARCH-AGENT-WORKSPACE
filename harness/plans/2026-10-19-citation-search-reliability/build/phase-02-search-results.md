# P2 — Web Search 不遺失已取得結果

目標 G2；依賴：無其他階段；先通過具名外部 source／安裝授權。共通政策見 [PLANS](../PLANS.md)，不可退讓條件見 [GOALS](../GOALS.md)。

## 輸入與目標

source：`/home/minervamuses/mcp-servers/web-search-mcp/src/search-engine.ts:42–102`，HEAD eeb03f8。標準安裝：`/home/minervamuses/.local/share/mcp-servers/web-search-mcp/dist/search-engine.js`。先核對 MCP 實際有效 command／args 的入口路徑（只輸出路徑，不輸出 env secrets）；目前只確認標準入口與本機檔案，未讀執行中 GUI 的環境覆寫。

外部 checkout 已有 `package-lock.json` 修改，保留且不納入 patch。source 及安裝的 search-engine.js 在規劃時相同，checksum 見 E2；執行前重核。

## 有界修正

P2-S1：先讀既有四情境離線探針，完整保留 mock network／browser 封鎖；改成以下修復後預期。暫存探針若已消失，在外部既有 tests/ 增加一個最小 Node assert regression 檔即可，路徑提議 `tests/test-search-result-retention.mjs`，不新增 framework／dependency。

P2-S2：只修改 `search()` 的 best result 控制流程。每次取得有效非空結果都能初始化 best（品質 0 亦然）；後續比較沿用現有品質分數／門檻，所有正常返回均回同一 best＋其來源。空結果、後續引擎例外／處理其錯誤時的清理失敗不能抹掉已取得 best。完全無有效結果仍遵守現有空／失敗契約；取消不得吞成成功。不改 heuristic、重試次數、瀏覽器所有權或引擎順序。

P2-S3：使用現有 Linux Node/npm 與已安裝 dependencies，在 source checkout 跑 `npm run build`（已存在，內容為 tsc）。build 失敗先報缺件，不自動 install 或改 lock。以修復後測試驗證 source 生成 dist。

P2-S4：有外部安裝授權後，記錄且備份將被更新的確切產物，複製本次 build 必需產物至有效安裝目錄；比對 checksum，將同一離線測試指向實際 runtime dist 再驗證。不只驗 checkout 的 dist。若需讓 running process 重載，先辨識受影響進程並在空閒／已授權時重啟，不能中止使用者正在執行的回合。

## 核心四情境與直接回歸邊界

| 輸入 | 修復後必須結果 |
|---|---|
| Bing 有效非空；Brave 空；DDG 空 | 原 Bing records 與 Browser Bing |
| Bing 有效非空；Brave 例外；DDG 例外 | 原 Bing records 與 Browser Bing |
| Bing 有效非空；Brave 空；DDG 例外 | 原 Bing records 與 Browser Bing |
| Bing 分數較高但尚未 excellent early-return；Brave 達門檻但分數較低 | 保留 Bing，不能因 Brave 達門檻覆蓋 |

最小直接反例：全部空仍空；品質 0 的非空有效結果不遺失；後來真的較佳者可取代；同分採既有穩定順序。必要時檢查引擎錯誤處理自身失敗後仍保留 best。品質停用或 forceMultiEngine 開啟時，任何既有返回分支仍滿足相同保留契約，不另做大矩陣。

舊 `/tmp/web-search-dist-repro-20261019.mjs` 的斷言是「前三空、第四 Brave」以證明故障；通過舊斷言不是修復成功。外部現有 `test-search.js`／引擎 tests 未證實 offline，不直接執行。新回歸檔的 `node tests/test-search-result-retention.mjs` 是提議命令，新增並核對參數後才可用。

## 交付、失敗與恢復

交付需包含 source diff、build 命令結果、source／安裝各自 checksum、四情境實際結果與未變動 lock 的確認。外部修改不會自動進本研究專案 commit；只有得到外部 Git commit 授權才提交外部 repo，否則記錄 diff／檔案 checkpoint。

安裝驗收失敗只還原本次備份的指定產物，保留 source patch 與診斷，不整樹刪除／reset。本階段不宣稱搜尋加速或品質提高。
