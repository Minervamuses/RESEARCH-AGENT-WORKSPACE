# F7-S3 公開引擎觀測（2026-10-22 22:06–22:08，Asia/Taipei）

- **腳本**：observe.py（組別驅動、預算與紀錄）、observe.mjs（只觀察的 preload，包住兩個解析器，記錄同一份結果頁的結構計數，不另發請求）、group4.mjs（dist adapter 逐引擎觀測）、bing_probe.mjs（只送 Bing 的結構探測）。
- **原始紀錄**：groups.jsonl。每組開始前寫 start、結束後寫 end。外部頁面正文每頁 ≤2000 code points（第 1 組 maxContentLength 1500；第 3 組的 10000 已裁成 2000 並註明）；Stack Overflow 的 Cloudflare 挑戰 token 已遮蔽為 `<redacted>`；沒有 cookie 或憑證。
- **執行環境**：沙箱外；第 1–3、5 組經 Python 入口（resolve_mcp_specs + load_mcp_tools_with_families），以產品的自訂 command 加 observe.mjs 載入 repo 的 dist，loader、wrapper 與環境 allowlist 都是產品的；第 4、6 組經 dist adapter，**不等同 Python 全鏈路**。
- **預算**：六組全部使用，組別時間合計 23.0 s（上限 480 s）。各組 DEFAULT_TIMEOUT 設為 60000–90000 ms。

## 各組
| 組 | 入口 | 查詢與理由 | 事實 |
| --- | --- | --- | --- |
| 1 | Python，full-web-search，limit 5，maxContentLength 1500 | `python asyncio TaskGroup exception handling`：一般技術問題，有穩定文件 | Google 200，結構 5／解析 5；5 個 `/goto` 包裝全部解開（26–31 ms），Bing 為 strategy_stopped。正文 4/5 讀自目標頁（docs.python.org、reddit、realpython、geeksforgeeks）；Stack Overflow 的 HTTP 與瀏覽器都得到 403（Cloudflare 挑戰），如實為 http_error |
| 2 | Python，get-web-search-summaries，limit 5 | `台股 今日 收盤 行情`：中文時事，檢查 zh-TW 市場 | Google 200，結構 5／解析 5，標題為「Google 搜尋」；5 個包裝全部解開（28–31 ms），目標為 tw.stock.yahoo.com、twse.com.tw 等；Bing 為 strategy_stopped。第 1 組解析過包裝之後，這次搜尋沒有被擋 |
| 3 | Python，get-single-web-page-content | 第 1 組第一個解開的網址 `https://docs.python.org/3/library/asyncio-task.html` | 200，`Character encoding: utf-8 (meta charset)`，text，原文 71104、交付 10000 code points 並有截斷標記 |
| 4 | dist adapter，逐引擎 | `how does TCP congestion control work` | Google 200，結構 4／解析 4，4 個包裝全部解開（28–90 ms，目標含 en.wikipedia.org、book.systemsapproach.org）。Bing 200，頁面網址帶 setlang、cc（及 Bing 自加的 rdr、rdrig），`#b_results` 存在但 `li.b_algo` 為 0，解析 0 |
| 5 | Python，get-web-search-summaries，limit 10 | `Playwright channel chromium new headless mode`：觀察 Google 不足額時 Bing 是否補足 | Google 200，結構 9／解析 9，9 個包裝全部解開（25–31 ms）；Google 不足 10，Bing 確實被呼叫（attempted=true），200，`li.b_algo` 為 0，zero_parsed，所以沒有補到任何候選 |
| 6 | dist adapter，只送 Bing | `how does photosynthesis work`：OD1 曾在 setlang=en&cc=US 下得到正式結果 | Bing 200，`#b_results` 子項為 li.b_algo 10、li.b_ans 1、li.b_pag 1；解析 10。但 10 個標題全是「test」相關（Jest、GoogleTest、CDC 的 chair stand test），與查詢無關，頁面標題仍是原查詢 |

## FG9 判定
- **Google 被擋**：沒有。4 次搜尋（第 1、2、4、5 組）都是 HTTP 200、最終路徑 `/search`，沒有 429 或 `/sorry/`；連結解析之後的下一次搜尋也沒有被擋。
- **轉接器缺陷**：沒有。Google 的結構計數與解析數在 4 次都相等（5/5、5/5、4/4、9/9）；Bing 在第 6 組結構 10、解析 10，解析器與實際結構一致。
- **零結果事實**：Bing 在第 4、5 組結構計數為 0 且沒有被擋，依規則記為零解析，不算缺陷。
- **連結解析**：Google 包裝 23/23 解開（100%，25–90 ms），沒有 stayed_on_engine_host、timeout 或 failed。Bing 包裝的真實解析**沒有被觀測到**：第 4、5 組沒有正式結果；第 6 組只呼叫 tryBingSearch 觀察結構，沒有經過接納與解析，也沒有記錄 href。Bing 的解析只有 F3-S3 與 F7-S2 案例 10 的本機證據。
- **Bing 補足**：策略 B 在第 5 組確實執行（Google 9 < 10 → 呼叫 Bing），但 Bing 沒有正式結果，未補到候選。Bing 依市場參數的正式結果數：英文市場 0、0、10（第 6 組結果與查詢無關）；中文市場未觀測到（第 2 組 Google 已補滿）。
- **相關性**：依計劃不當成缺陷；Bing 回傳無關結果的事實列入最終彙報的後續選項。

## 偏離紀錄
- **Google 請求間隔**：PLANS 要求 Google 兩次請求至少間隔 10 秒。observe.py 以「組別開始」間隔 10 秒來控制，但每組實際送出 Google 搜尋的時點會因程序啟動而不同（dist adapter 的第 4 組比 Python 入口快）。以同一份結果頁的解析時點計算，第 1→2 組相隔 9.9 s、第 2→4 組相隔 8.7 s，都**少於 10 秒**；第 4→5 組相隔 69.7 s。另外第 2、4 組的開始紀錄只相隔 9.3 s，低於腳本的 sleep 應保證的 10 s，原因未查明（可能是 WSL 時鐘調整）。這次 Google 沒有被擋，但規則沒有達成，不寫成已遵守。日後同類觀測應以實際請求時點控制間隔，並留更大的餘裕。
