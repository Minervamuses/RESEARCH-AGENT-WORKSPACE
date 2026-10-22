# OD1 引擎與瀏覽器實測（2026-10-22）
- **目的**：使用者同意「作實測，幫我找出比較穩又真的實用的組合」。本實測只觀察，不修改任何產品程式。
- **環境**：GUI 30004e9 之後的 dist（行為與 f5cf123 相同），WSL Linux，同一台機器與同一個對外 IP。
- **時段**：2026-10-22 18:23–18:37（Asia/Taipei），實際執行約 9 分鐘。

## 方法
- **請求量**：約 93 次搜尋請求與 9 次連結導覽，全部循序執行。同一引擎兩次請求至少間隔 5 秒；同一組合連續被擋 2 次就停止，避免讓這個 IP 更容易被擋。
- **查詢**：六個中性查詢，中英文、技術、新聞、一般各類都有，沒有預設網站。
- **瀏覽器模式**：
  - headless_shell：Playwright 1.54 自帶、產品現用，UA 帶 `HeadlessChrome`；
  - full_chromium：Playwright 的完整版 Chromium 139，新 headless 模式；
  - system_chrome：系統 Google Chrome 145；
  - 部分組合另測「一般 Chrome UA」（不帶 Headless）。
- **環境前提**：完整版 Chromium 與系統 Chrome 會在 TMPDIR 建立 unix socket，路徑必須很短（約 108 字元以內）；路徑太長時，兩者都在啟動時以 SIGTRAP 崩潰。產品經 Python 啟動時 TMPDIR 為空、使用 /tmp，不受影響；但在沙箱內以長 TMPDIR 跑這兩種模式會失敗。
- **腳本與原始資料**：
  - [survey.mjs](survey.mjs)：主實測，產出 results.jsonl、reads.jsonl、summary.json、run.log；
  - [followup.mjs](followup.mjs)：Bing 與 Google 頁面結構診斷；
  - [followup2.mjs](followup2.mjs)：Google 依瀏覽器模式比較，以及 Bing 依語言設定市場；
  - [followup3.mjs](followup3.mjs)：Google 結果連結的實際導覽。

  Bing、Brave 走產品的引擎方法；DuckDuckGo 與探索性引擎用與產品相同的請求，或臨時的解析器。

## 結果
| 引擎 × 方式 | 可用性 | 結果品質 | 連結 |
| --- | --- | --- | --- |
| Google × 完整版 Chromium 或系統 Chrome × 一般 UA | 10/10 成功，搜尋約 0.5–1 s | 中英文技術、新聞、一般查詢都精準（例：Python 官方文件「Coroutines and tasks」、iT 邦幫忙的過擬合文章、氣象署颱風消息） | Google `/goto?url=` 包裝（已編碼，無法直接解碼）。實際導覽 6/6 到達目標頁，各 0.4–2.2 s |
| Google × headless_shell（無論 UA） | 0/6，429 或導到 /sorry/ 驗證頁 | — | — |
| Bing × 任一瀏覽器模式（產品現行流程） | 頁面幾乎都能取得；自身失敗 0 次 | 差。預設市場常沒有正式結果，parser 抓到側欄模組，例如查光合作用卻得到颱風消息。技術長尾偏題 | 全為 ck/a 包裝（真實網址比例 0）。實際導覽 3/3 到達目標頁，各 0.7–4.2 s |
| Bing × 依查詢語言設定市場（setlang/cc） | 6/6 取得頁面 | 不穩：3/6 好（颱風、光合作用、捷運），asyncio 偏題，過擬合只有 2 筆「Google 翻譯」，Playwright 0 筆 | 同上 |
| Brave × 三種瀏覽器、一般 UA | 全部 HTTP 429 | — | — |
| DuckDuckGo × HTTP GET、POST、lite、系統 Chrome | 全部 HTTP 202 異常頁 | — | — |
| Mojeek × HTTP | HTTP 403 | — | — |

## 結論（供使用者決定 OD1）
- **在這台機器與 IP 上**，DuckDuckGo、Brave、Mojeek 目前不論換瀏覽器或 UA 都被擋。Bing 能用，但結果品質不穩，連結也全是中介頁。
- **Google 最穩也最實用**，條件有兩個：用完整瀏覽器（Playwright 完整版 Chromium 即可，不需系統 Chrome），並使用一般 Chrome UA。被擋的主因是 headless shell 的特徵（含 `HeadlessChrome` UA）。
- **兩家都要實際導覽才能取得真實網址**。這屬於 R04「最終網址必須來自實際導覽結果」，不需要網址辭典。
- **限制**：
  - 只有約 9 分鐘的觀測，無法代表長期穩定性；
  - Google 條款禁止自動化查詢，用量增加後可能出現驗證頁；
  - 這些結論只適用於本機與本 IP。
