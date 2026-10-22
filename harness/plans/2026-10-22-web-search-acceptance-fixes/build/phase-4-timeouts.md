# F4：局部時間上限與自有 Chromium
依據：[目標 FG3 與 FA05、FA06、FA10](../GOALS.md)、[執行契約](../PLANS.md)、[驗收發現](../context/acceptance-findings.md)。相依：F1、F3（同一組 Node 檔案）。涵蓋 FG3、FG6、FG8；AF19–AF22、AF34，突變 N28、N29。

以下 src 指 app/vendor/web-search-mcp/src，tests 指 app/vendor/web-search-mcp/tests。F3-S2 已移除 DuckDuckGo 與 Brave，本階段只處理仍存在的路徑：單頁 HTTP、Google、Bing、結果連結解析與正文讀取。

## 後置條件
- 每個局部上限都是真正的總時間上限：單頁 HTTP 讀取、導覽後的頁面讀取、每頁 8 秒視窗皆然，逾時原因可分辨。
- 自有 Chromium（F3-S1 之後為完整版 Chromium）在 argv 或 comm 被改寫時仍可辨識，close 卡住時也能在有界時間內收尾。

整次呼叫的五分鐘上限與 A04 的併發數不變。

## F4-S1：總時間上限與每頁視窗
- **production 檔**：src/enhanced-content-extractor.ts、src/search-engine.ts、src/browser-pool.ts。
- **處理**：AF19、AF20、AF21。

工作：
1. **HTTP 總時間上限（FA05）**：
   - 單頁 HTTP（pageRequest 6 s）除了閒置 timeout，還要有總時間上限：用 `AbortSignal.any` 把 `AbortSignal.timeout(min(上限, 剩餘預算))` 與呼叫預算的 signal 合併，交給 axios。
   - axios 1.10 會把任何中止都轉成 `CanceledError`（code ERR_CANCELED，訊息 "canceled"），並丟棄 signal 的原因。因此要把操作計時 signal 保留在區域變數，在 catch 中判斷：若操作計時已觸發而呼叫預算沒有中止，就改拋一個寫明操作名稱與上限毫秒數的 timeout 錯誤。
   - 這個 timeout 錯誤對應 timeout 狀態，並照既有規則進 fallback。原因要能和「Call deadline exceeded」區分。
2. **導覽後讀取的上限（FA06）**：
   - 新增具名常數（初始值與 pageRequest 相同），約束導覽後的 page.title、page.content、locator.innerText，以及 Google、Bing 解析前的 page.content。
   - 到期時以可取消的方式結束：拋出例外，由 withPage 以既有的有界收尾關閉該 context。
   - 不得只讓 Promise.race 返回，卻留下仍在執行的工作。
   - F3-S3 的連結解析使用它自己的 linkResolve 上限，同樣取 min(上限, 剩餘預算)；到期時放棄該筆並記錄原因，不得留下仍在等待的導覽、監聽器或 timer。
3. **每頁 8 s 視窗（FA05）**：
   - 視窗從該頁實際取得第一個讀取 slot 起算，涵蓋該頁的 HTTP 與 fallback；排隊只受整次呼叫預算限制。
   - 視窗到期的原因寫明「page read window」與毫秒數，與整次期限區分。
   - 候選集合、順序與 not_attempted 的語意不變。

最少檢查（離線，tests/test-browser-lifecycle.mjs 或 content-contract，本機伺服器）：
- **單頁 HTTP 慢送**：本機伺服器每 300 ms 送 1 byte。讀取在約 6 s 內（加上合理餘裕）以 timeout 結束，原因寫明是操作上限，之後依規則進 fallback（stub）。期間只占用一個 HTTP slot。
- **頁面讀取卡住**：stub page 的 title()、content()、locator('body').innerText() 分別永不返回，Google 與 Bing 解析前的 content() 也各測一次。每一項都在讀取上限內以例外結束，context 被關閉。
- **每頁視窗**：
  - limit=10、每頁 2 s、HTTP slot 為 2：10 頁全部讀到文字，沒有 not_attempted 或視窗逾時，總時間在呼叫預算內；
  - 另一案例讓某頁的 HTTP 與 fallback 合計超過視窗：該頁為 timeout，原因寫明「page read window」與毫秒數，而不是「Call deadline exceeded」。
- **舊案例仍然成立**：既有的 selector 卡住、短期限、取消後不再 fallback 等案例全部仍然通過。

為了縮短測試時間，可在測試內暫時調小 OPERATION_TIMEOUTS，既有測試已用這個做法。build、Node 測試、記錄後 commit：`fix(web-search): enforce total operation caps and per-page windows [F4-S1]`。

## F4-S2：自有 Chromium 辨識與有界收尾
- **相依**：F4-S1。
- **production 檔**：src/browser-pool.ts。
- **處理**：AF22、AF34，突變 N28、N29。

工作：
1. rememberBrowserProcesses 與 killOwnedBrowsers 的 owner flag 比對，要能涵蓋 NUL 切分與空白切分兩種 cmdline（FA10）。
2. stat 從最後一個「)」之後解析。
3. 仍要求 pgid 等於 pid 且 starttime 一致，才可以 kill 群組。
4. 解析不了或身分不符的程序一律不 kill。
5. 適用於 F3-S1 之後的完整版 Chromium。

最少檢查（tests/test-browser-lifecycle.mjs，真實子程序，不需 Chromium）：
- **被改寫的程序**：測試以 `process.execPath` 和 detached 方式產生一個直接子程序（自成 process group），在子程序內設定 `process.title = 'a) b c d --web-search-owner=<測試程序 pid>'`。
  - Linux 上，這會同時把 cmdline 改成單一字串，並把 comm 改成含「) 」的名稱（規劃時已驗證：comm 為 `a) b c d --web-`，舊的 `split(') ')` 會讀錯欄位）。
  - pool 必須把它認作自有程序。
- **close 卡住**：搭配一個 close 永不返回的 stub browser。closeAll 應在約 cleanup 上限內返回，並以 SIGKILL 終止該群組（可殺死 N28、N29）。
- **不誤殺**：cmdline 不含 flag，或 starttime 不符的另一個子程序不得被 kill。測試結束時只清理自己產生的程序。
- 既有的 launch 合併、併發上限與 close 失敗保留結果等案例全部仍然通過。

build、Node 測試、記錄後 commit：`fix(web-search): recognise owned Chromium after argv rewrites [F4-S2]`。

## 階段界線
- 不改 A04 的併發數、整次預算或 285/15 切分。
- 不新增環境設定，新的上限都是具名常數。
- 不加入跨程序的全域限流。
- 真實 Agent 入口的觀測在 F7-S2 進行。
