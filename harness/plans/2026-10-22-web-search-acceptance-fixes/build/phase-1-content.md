# F1：正文讀取忠實度
依據：[目標 FG1、FG2 與 FA01–FA04](../GOALS.md)、[執行契約](../PLANS.md)、[驗收發現](../context/acceptance-findings.md)。相依：無。涵蓋 FG1、FG2、FG8；AF01–AF10，突變 N06d、N07e、N07f。

以下 src 指 app/vendor/web-search-mcp/src，tests 指 app/vendor/web-search-mcp/tests。

## 後置條件
正文讀取做到五件事：
- 依原順序轉換整頁可見文字，只移除 script、style、noscript、template；
- 每段來源文字只出現一次，區塊之間不黏連；
- 瀏覽器讀取能在有界的等待內取得晚渲染的文字；
- 依實際編碼解碼；
- 轉換與截斷都在線性時間內完成，截斷後不會留下殘缺的連結或網址。

PDF、過大回應、下載與轉換失敗，都分類正確並保留已知事實。候選集合與截斷語意（A01/A02）不變。

## F1-S1：整頁轉換與結構修正
- **production 檔**：src/enhanced-content-extractor.ts，必要時加 src/utils.ts。
- **處理**：AF01、AF02、AF04、AF05、AF07。

工作：
1. **整頁轉換（FA01）**：
   - 移除依 `main, article, [role="main"]` 縮窄根節點的邏輯，改以 `<body>`（沒有 body 時用整份文件）為根，依原順序轉換。
   - 不新增任何以 tag 名稱、class、id 或文字長度刪除內容的規則。
2. **表格（FA02）**：
   - 每個表格只輸出直接屬於自己的列（thead/tbody/tfoot 底下的 tr 也算），不得用會取到巢狀表格列的後代查詢。
   - 儲存格內的巢狀表格只在該儲存格內輸出一次；儲存格內容收成單行，讓外層每列維持一行。
   - `<caption>` 在列前輸出一次。
   - 保留既有的「span structure simplified」一致說明。
3. **區塊分隔**：
   - 預設為區塊顯示的元素前後都要有分隔，至少包括：address、aside、dd、details、dialog、dl、dt、fieldset、footer、form、header、hgroup、hr、legend、menu、nav、optgroup、option、search、summary，以及既有清單。
   - 只輸出分隔，不刪除內容。壓縮過的 HTML 不得讓相鄰文字黏成一個詞。
4. **頁面標題**：
   - HTTP 路徑取 `head > title`；沒有時，取不在 svg 之內的第一個 title；都沒有就是 unknown。
   - 兩條路徑都把空白正規化為單一空格。
   - 不得從 URL 補造標題。
5. **連結標籤**：
   - 輸出 `[label](<url>)` 時，label 內的換行與連續空白收成單一空格。
   - 不改寫可見文字，只做空白整理。

最少檢查，加在 tests/test-content-contract.mjs，使用 inline HTML 與 node:assert：
- 巢狀表格 1–6 層：每個葉節點文字恰好出現 1 次。16 層時，輸出長度與層數呈線性關係，不是 2^n。
- 多個 `<article>` 前後夾段落的頁面：intro、每篇 story、tail 全部依原順序出現。
- `<aside><article>Related</article></aside><main>Main</main>`：兩段都要出現。
- 壓縮 HTML 的區塊元素：一個 fixture 涵蓋工作第 3 項列出的每個元素，各帶相鄰文字，斷言沒有黏連的詞（例如不得出現 `TermDef`）。
- caption 恰好出現 1 次；含兩個 `<p>` 的儲存格不讓該列斷行。
- 連結 base 分兩個案例，必須能分辨突變 N07e 與 N07f：
  - `<base href="/docs/sub/">` 加上 `next`，結果必須是 `/docs/sub/next`，而不是依 final URL 解析；
  - 沒有 base 時，結果必須依實際 final URL（含其 host）解析。
- 標題：
  - head 沒有 title 但 body 內有 svg title 時，頁面標題為 unknown；
  - `<title>  A\n  B </title>` 的標題為 `A B`。
- 既有的 AC02 斷言（來源詞、shadow、metadata、figcaption、href、百分比參數）全部仍然通過。

執行 build、三份既有 Node 測試與上述新增檢查，記錄後 commit：`fix(web-search): convert whole pages and each table once [F1-S1]`。

## F1-S2：晚渲染等待
- **相依**：F1-S1。
- **production 檔**：src/enhanced-content-extractor.ts、src/browser-pool.ts（新增具名常數），必要時加 src/types.ts（記錄等待時間）。
- **處理**：AF03。

工作：
1. 在 OPERATION_TIMEOUTS 新增 renderSettle，初始值 3000 ms（FA04）。
2. extractWithBrowser 在 `goto(domcontentloaded)` 之後、讀取內容之前，等到「網路靜止，且頁面已有可見文字」，或等滿 min(renderSettle, 剩餘預算)。
3. 判斷方式：
   - 由 Node 端輪詢，例如每約 100 ms 以 `page.evaluate` 或 `locator.innerText` 讀取 body 的可見文字；
   - 網路靜止可用 `page.waitForLoadState('networkidle')`，並受同一上限約束；
   - 不得依賴 `page.waitForFunction`：它在頁內以 eval 執行，遇到 CSP 不允許 unsafe-eval 的頁面會失敗，而錯誤可能被吞掉。
4. 等待只涵蓋瀏覽器讀取；HTTP 已取得文字的頁面不受影響。靜態頁不需等滿上限。取消或呼叫期限到時，等待立即結束。
5. 等滿上限後仍沒有文字時，維持 empty_text，並在該次嘗試的可見資訊中寫出已等待的毫秒數。這是給 Agent 的事實，不是「低品質」判定。
6. 不使用隨機延遲。UA 依 FU03 由 F3-S1 統一設定，本步不另做擬態。不以特定站點的 selector 作為等待條件。

最少檢查：
- **離線**：在 tests/test-browser-lifecycle.mjs 用 stub page 驗證：等待受 min(上限, 剩餘預算) 約束；呼叫被取消時等待立即結束；等滿上限仍無文字時，可見資訊含等待時間。
- **真實 Chromium**（直接以 node 匯入 dist 的 extractor；設 PLAYWRIGHT_BROWSERS_PATH。F3-S1 之前產品用 headless shell，沙箱內只要 TMPDIR 可寫即可；F3-S1 之後是完整版 Chromium，必須在沙箱外以短 TMPDIR 執行，見 PLANS）。用本機 HTTP 伺服器，讓 HTTP 回應本身沒有文字，以觸發 fallback，測試以下頁面：
  - 計時器在 0、100、300、700、1500 ms 插入文字；
  - fetch 經 200 ms 延遲後渲染；
  - DOMContentLoaded 時已有導覽列文字、主要內容經 fetch 300 ms 後才插入；
  - 帶 `Content-Security-Policy: script-src 'unsafe-inline'`、計時器 300 ms 插入；
  - 5000 ms 才插入（超過上限）；
  - 持續輪詢、網路永不靜止。

  預期：前四類都取得目標文字；超過上限者約在上限時間返回 empty_text，並附等待時間；持續輪詢者在上限內返回。

  靜態頁與 HTTP 已有文字的頁面，額外延遲的實測值記錄下來。驅動腳本與結果存在 evidence/F1-S2/。

build、三份 Node 測試、記錄後 commit：`fix(web-search): wait boundedly for client-rendered text [F1-S2]`。

## F1-S3：字元編碼與媒體事實
- **相依**：F1-S2。
- **production 檔**：src/enhanced-content-extractor.ts、src/types.ts、src/utils.ts。
- **處理**：AF06、AF10。

工作：
1. **編碼（FA03）**：
   - HTTP 回應依序以 BOM、Content-Type charset、前 4096 bytes 內的 `<meta charset>` 或 http-equiv、預設 UTF-8 判定編碼，再用 TextDecoder 解碼。text/plain 一樣適用。
   - PageRead 記錄實際使用的編碼與判定來源，formatPageRead 輸出一行。
   - 遇到不支援的 label 時以 UTF-8 解碼，並在該行說明。
2. **過大回應**：
   - 超過 10 MiB 讀取上限時，從 axios 錯誤物件的 `error.request.res` 取回已收到的 HTTP status、Content-Type 與 final URL（驗證時已確認這些資訊存在，不需改用 stream）。
   - 若媒體類型不受支援（含 PDF），標為 unsupported_media；否則標為 http_error，錯誤寫明「response body exceeds 10 MiB read limit」。
   - 不得把已知的標頭顯示為 unknown。
3. **瀏覽器下載**：
   - 瀏覽器 fallback 在 goto 之前註冊 `page.on('response')`，只記錄主框架的導覽回應，取得 status 與 Content-Type。
   - 回應為 PDF、octet-stream 或其他不支援的類型，或 goto 因下載而拋 net::ERR_ABORTED 時，標為 unsupported_media。
   - 若下載時沒有任何回應事件，標頭維持 unknown，並註明「download started」。
   - 必須等 F7-S2 案例 7 以真實 Chromium 通過後，才能把 AF10(b) 記為已修正。
4. **錯誤淨化**：Agent 看得到的錯誤訊息要去掉 ANSI 跳脫碼與 Playwright 的「Call log」區塊，成為單行簡短文字。這套用在所有 transport 的錯誤。
5. **轉換失敗分類**：parseContent（兩條路徑）與截斷時的例外一律歸為 conversion_error，不得落成 http_error。

最少檢查（content-contract，本機 node:http 伺服器）：
- 編碼：用寫死的 byte 序列，涵蓋四種判定來源：
  - Big5 的「中文」（a4 a4 a4 e5），經 header charset；
  - Shift_JIS 的「日本」（93 fa 96 7b），經 `<meta charset>`；
  - windows-1252 的「café」（63 61 66 e9），經 http-equiv；
  - UTF-8 BOM 加「中文」（ef bb bf e4 b8 ad e6 96 87），header 卻宣稱 latin-1，結果仍須是 UTF-8 的「中文」。

  四者都正確解碼，輸出看得到編碼來源。
- 未知 charset 的案例有明示說明。
- 約 11 MiB 的 application/pdf 回應為 unsupported_media，status 200 與 Content-Type 皆保留。約 11 MiB 的 text/html 回應為 http_error，附讀取上限原因與已知標頭。
- 錯誤淨化：含 ANSI 與 Call log 的字串淨化後為單行，且保留第一行原因。
- 下載分類：以 stub 驗證「主框架回應為 application/pdf」與「ERR_ABORTED 但沒有回應」兩種情形都得到 unsupported_media。
- 讓 parseContent 拋例外的 stub，在 HTTP 與 browser 兩條路徑都得到 conversion_error。

build、Node 測試、記錄後 commit：`fix(web-search): decode declared charsets and keep media facts [F1-S3]`。

## F1-S4：線性截斷與完整連結
- **相依**：F1-S3。
- **production 檔**：src/utils.ts、src/enhanced-content-extractor.ts。
- **處理**：AF08、AF09、N06d。

工作：
1. truncateMarkdown 改為線性時間：從切點向前做有界的局部掃描，判斷切點是否落在連結或裸網址之內。不得對全文重複執行可能回溯的 regex。
   - 轉換時記下的連結區段不可靠：後處理會改變位移，text/plain 與直接呼叫 truncateMarkdown 時也沒有這些區段。
2. **連結保護規則**：
   - 切點落在 `[label](<url>)` 內時，捨棄整個連結（label 含 `]` 時也一樣），不留下 `[label](<` 之類的殘缺開頭。
   - 切點落在裸網址內時，捨棄整個網址 token；text/plain 中含括號的網址也一樣。
   - 不補造任何目的地。
3. parseContent 結尾整理行尾空白的步驟改為逐行線性處理，取代 `/[ \t]+\n/g`。
4. originalLength 與 returnedLength 以 Unicode code points 計算（A02）。

最少檢查：
- 邊界案例：`[[1]](<https://example.org/a>)`、label 內有換行的輸入、text/plain 的 `https://en.wikipedia.org/wiki/Foo_(bar)_baz`，在每個可能的切點都不交付網址的嚴格前綴，也不留下殘缺的開頭。
- 線性：
  - 截斷：用至少 150 KB 的大量未閉合 `[`（舊實作需 ≥5 s 的大小），斷言在 1 s 內完成；
  - 轉換：長空白串必須放在 `<pre>` 內（一般文字節點的空白已先收合），同樣斷言在 1 s 內完成。

  128 KB/256 KB/512 KB/1 MB 的倍增量測腳本與結果存在 evidence/F1-S4/。
- `😀中文` 這類非 BMP 字元的 originalLength 是 code point 數（可殺死 N06d）。
- 既有的截斷斷言（標記、remainder not delivered、Unicode）仍然通過。

build、Node 測試、記錄後 commit：`fix(web-search): truncate Markdown in linear time without broken links [F1-S4]`。

## 階段界線
- 不加入主文辨識、品質分數或任何刪除規則；不改候選選擇、長度上限或 includeContent 語意。
- 操作總時間上限與每頁視窗屬於 F4，可見狀態欄位的整理屬於 F5。本階段只新增實作需要的 PageRead 欄位（編碼、等待時間）。
