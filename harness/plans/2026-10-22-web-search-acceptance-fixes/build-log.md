# 執行狀態與證據
本文件是唯一的動態狀態擁有者。規劃與驗收的觀察不代表修正已完成；實際結果見下方各步驟事件。每一步都強制 commit（見 PLANS 執行契約第 4 項），每個 commit 都必須同時更新本表與事件紀錄。狀態只用 Not started、In progress、Blocked、Complete。

## 階段狀態
建議的步驟順序：F1-S1 → F1-S2 → F2-S1 → F3-S1 → F3-S2 → F3-S3 → F3-S4 → F1-S3 → F1-S4 → F2-S2 → F2-S3 → F4 → F5 → F6 → F7（見 PLANS）。
| 階段 | 狀態 | 已完成步驟 | 實際證據 | 阻塞 | 下一動作 |
| --- | --- | --- | --- | --- | --- |
| F1 | Complete | F1-S1、F1-S2、F1-S3、F1-S4 | evidence/F1-S1/…F1-S4/、evidence/F7-S2/ | — | — |
| F2 | Complete | F2-S1、F2-S2、F2-S3 | evidence/F2-S1/…F2-S3/ | — | — |
| F3 | Complete | F3-S1、F3-S2、F3-S3、F3-S4 | evidence/F3-S1/、evidence/F3-S3/ | 真實 Google／Bing 的觀測留給 F7-S3（FG9 閘門） | — |
| F4 | Complete | F4-S1、F4-S2 | evidence/F4-S2/ | — | — |
| F5 | Complete | F5-S0、F5-S1、F5-S2、F5-S3 | evidence/F5-S1/、evidence/F5-S2/ | — | — |
| F6 | Complete | F6-S1、F6-S2、F6-S3 | evidence/F6-S3/ | — | — |
| F7 | In progress | F7-S1、F7-S2、F7-S3 | evidence/F7-S2/、evidence/F7-S3/ | Google 請求間隔偏離（見 F7-S3） | F7-S4 |

## 事件格式
每個實際的 F?-S? 事件記錄以下內容：
- 改動，以及對應的 FG、AF 與突變；
- 實際檔案；
- 命令、退出碼與輸出摘要；
- 證據路徑（evidence/步驟ID/）；
- 未解決的限制；
- 下一步。

commit 之前更新；commit subject 包含步驟 ID。需要 hash 時從 git log 反查，不為記錄自己的 hash 再 commit。取消、未執行或逾時都不是通過；保留失敗的歷史，不得覆寫成沒有發生。

## Authoring FA0（2026-10-22，Asia/Taipei）
- 依使用者「撰寫修正計劃」建立本計劃，來源是同日的驗收結果。驗收以多個獨立覆核維度、對抗式驗證與完整性審查完成；結論與重現方式整理在 context/acceptance-findings.md 與 context/mutation-survivors.md。驗收 session 的紀錄與 `/tmp` 證據都不在 repository 內。
- 規劃時的唯讀基線（摘要；完整清單見 PLANS「觀察到的基線」）：
  - GUI 分支，HEAD f5cf123；tracked 與 index 乾淨，未追蹤的只有 app/store/ 與 note/20261022/。
  - Conda app 的 Node v24.18.0 已確認支援 TextDecoder(big5/shift_jis/euc-jp/gbk/gb18030/euc-kr/windows-1252)、AbortSignal.any 與 AbortSignal.timeout。
  - 子程序設定 process.title 後，cmdline 變成單一字串：以 NUL 切分找不到 owner flag，以空白切分可以。
- 本次只寫計劃目錄，產品檔案未修改。

### FA0-R1 獨立審查與修復
- 三個 fresh-context 審查者唯讀檢查初稿，角度分別是需求忠實與追蹤、新執行者走查、對照 HEAD 程式碼的技術可行性。結果：沒有 critical；major 合計 10 項（三方有重疊）、minor 若干。撰寫者對照程式碼與小型探測逐項核實後修復：
  - **測試無法分辨對錯**：
    - N11d：只看連線是否關閉，與程序結束時作業系統自行關閉連線無法區分。改為讓 closeAll 延遲返回，並記錄 abort 的時間點。
    - N14j：只有在 limit 驗證剩一處時才殺得死，改列為「條件等效」。
    - P27：原本的「server 自行結束」情境在 HEAD 必定失敗，改為「中介子程序產生孫程序後結束、server 保持卡住」。
    - AF13：補上斷言。
  - **事實錯誤**：
    - 只有 retention 測試接受 dist 參數，突變複驗改在含 src、tests、dist 的暫存複本中執行。
    - Python 複本排除 app/desktop（約 16 GB）與 app/store。
  - **機制**：
    - 晚渲染等待改由 Node 端輪詢，不用 waitForFunction（CSP 禁止 eval 時會失效），並加入 CSP 測試頁。
    - axios 會丟棄中止原因，改為以區域變數判斷是否為操作上限逾時。
    - SDK client 必須用 process.execPath；只關 stdin 的案例改用原始 spawn。
    - preload 的設定經 Python 入口時不能用環境變數傳入。
  - **一致性**：
    - FA03 改為 BOM 優先；FA04 改為「網路靜止且已有可見文字」。
    - 引擎與頁面讀取採同一個「開始」定義；保留 targetCount 並加測試。
    - 必殺突變允許「等效／不再適用」並記錄理由。
  - **流程**：
    - phase 檔在 FA0 以 -f 追蹤，修訂時用 `git add -f`；第一個動作檢查計劃已被追蹤。
    - 續作時，以 results.jsonl 與 groups.jsonl 避免重複；殘留程序只終止命令列含本計劃暫存根目錄者。
    - 定義狀態用語與 checkpoint 的 subject 格式。
  - **順序**：晚渲染從 F3 移到 F1-S2，建議順序為 F1-S1 → F1-S2 → F2-S1，讓使用者的優先項先完成。
- 未採納：在快速失敗路徑主動回收後代程序。這不在驗收發現內，產品路徑中也未觀察到殘留，列為 X14。

### FA0-V1 結構與格式檢查
- 修復後以 long-horizon-plan-author 的 validate_plan.py --json 檢查：exit 0，ok=true，13 檔，0 errors。3 個 BOUNDARY_LINK warning 是刻意連到舊計劃的連結；GOALS 已註明舊計劃若被移除時，從 git 歷史讀取的方式。
- 人工核對：
  - 18 個步驟章節與所有被引用的步驟 ID 一致；AF01–AF44 都有處置；plan-index 的目標覆蓋與 GOALS 一致。
  - 13 檔都是 UTF-8／LF，沒有 CR 與行尾空白。
- 計劃準備狀態：可啟動。所有實作階段為 Not started。提交使用 [FA0]，可由 git log 查得實際 commit。

## 規劃後的清理（2026-10-22，使用者指示）
- 使用者對 OD3 的回覆：「舊的用不到的就可以清理了」，並要求除了清理以外，其他部分先不要動手（OD1 Bing、OD2 啟動上限都不變）。這次清理不屬於 F1–F6 的任何步驟，也沒有開始執行本計劃。
- `refactor(web-search): remove dead code from the vendored server`（commit 由 git log 查得），行為不變：
  - 刪除舊 src/content-extractor.ts、Google parser（parseSearchResults、cleanGoogleUrl）；
  - 刪除未使用的工具函式與型別，以及只寫不讀的結果欄位（fullContent、contentPreview、wordCount、timestamp、fetchStatus、result.error、engine、total_results、search_time_ms）與只服務它們的函式；
  - 刪除兩個 closeAll 轉呼叫與 RateLimiter.getStatus，內聯 validateAndConvertArgs；
  - 測試改讀 read.status 與 read.content。
- 該 commit 的檢查：
  - npm run build exit 0；dist 的 .js、.d.ts 與乾淨重建一致；
  - retention 15/15、content-contract 3 組、browser-lifecycle 通過；
  - focused pytest 67 passed；
  - 經真實 Python→Node 入口讀本機頁面成功（沙箱內，HTTP 路徑）。
- `chore(plan): retire the completed web search citation plan`：
  - 移除 harness/plans/2026-10-20-web-search-citation/；
  - 需求基準以凍結快照保存為 context/baseline-2026-10-20-goals.md 與 context/baseline-2026-10-20-source-spec.md（內容逐字保留，只把指向舊計劃其他檔案的連結改為純文字）；
  - 同步更新 GOALS（S3、OD3、不變條件）、PLANS（基線、檔案範圍）、phase-1 階段界線、acceptance-findings（連結、X12）。
- 對執行的影響：
  - acceptance-findings 的行號以 f5cf123 為準，請用 `git show f5cf123:<路徑>` 對照；
  - 舊 content-extractor.ts 的型別相容條款已不再適用；
  - 孤兒依賴 p-retry、esbuild 經使用者同意後移除（見下）。
- `chore(web-search): drop unused p-retry and esbuild dependencies`：
  - 使用者回覆：「確定沒有的話我同意你刪」。
  - 刪除前確認：沒有任何程式、npm script 或設定使用兩者；lockfile 中 p-retry 只有根目錄依賴；esbuild 另由 tsx 依賴，所以仍以 tsx 依賴的身分保留，版本 0.25.5 不變。
  - 以 `npm uninstall --offline --no-audit --no-fund p-retry esbuild` 移除，lockfile 只刪除 p-retry、retry、@types/retry、is-network-error 與兩個根目錄宣告，沒有升級。
  - 檢查：`npm ls --all` exit 0；`npm ci --dry-run --offline` exit 0；build exit 0；三份 Node 測試通過；沙箱外 tsx 4.20.3 可轉譯執行 TypeScript。
  - 本計劃執行時「不新增或升級依賴、不改 lock」的不變條件照舊。

## OD1 引擎與瀏覽器實測（2026-10-22，使用者同意）
- 使用者：「我同意你作實測，幫我找出比較穩又真的實用的組合」。只觀察，不改產品程式。
- 方法與原始資料見 evidence/OD1-engine-survey/（README.md、survey.mjs、followup*.mjs 與其輸出）。
  - 量：約 93 次搜尋請求、9 次連結導覽，循序執行；同一引擎至少間隔 5 秒；連續被擋 2 次即停止該組合。實際執行約 9 分鐘，沒有殘留程序。
  - 環境前提：完整版 Chromium 與系統 Chrome 需要很短的 TMPDIR，否則以 SIGTRAP 崩潰（unix socket 路徑上限）。產品經 Python 啟動時使用 /tmp，不受影響。
- 結果：
  - Google 以完整版 Chromium 或系統 Chrome 加一般 UA，10/10 成功，品質最好；headless shell 0/6。
  - Google `/goto` 與 Bing `ck/a` 都能經實際導覽到達目標頁（6/6、3/3）。
  - Bing 依語言設定市場後只有 3/6 可用。
  - DuckDuckGo（202）、Brave（429）、Mojeek（403）不論方式全被擋。
- 下一步：等使用者決定 OD1 是否採用與採用範圍，再修訂本計劃，例如新增一個引擎與瀏覽器階段。目前所有階段仍為 Not started。

## Revision FA1（2026-10-22，使用者對 OD1／OD2 的決定）
- 依使用者的逐項回覆（GOALS S7，歸納為 FU01–FU06）修訂本計劃；只改計劃，不執行產品修改：
  - Google 主力、Bing 依查詢語言為備援，刪除 DuckDuckGo 與 Brave；
  - 改用完整版 Chromium 與一般 Chrome UA；
  - 搜尋時以實際導覽取得真實網址；
  - 啟動上限 15 秒；
  - web search 維持獨立 MCP，不與主專案交叉汙染。
- **結構變更**：新增 F3「搜尋引擎與瀏覽器」（F3-S1–F3-S4），原 F3–F6 順延為 F4–F7；新增 F2-S3（啟動上限）。
  - 新舊編號對照：舊 F3-S1／S2 → 新 F4-S1／S2；舊 F4-S1／S2／S3 → 新 F5-S1／S2／S3；舊 F5-S1／S2／S3 → 新 F6-S1／S2／S3；舊 F6-S1／S2／S3／S4 → 新 F7-S1／S2／S3／S4。
  - phase 檔改名為 phase-4-timeouts、phase-5-status、phase-6-regression、phase-7-delivery，新增 phase-3-engines。
  - 上方 Authoring FA0 等歷史紀錄仍沿用當時的編號，沒有改寫。
- **內容變更**：
  - GOALS：新增 S7、FU01–FU06、FG9、FA13–FA15；OD1、OD2 標為已決定；不變條件改為 Google→Bing、只限 UA 的擬態、FU06 的 MCP 邊界。
  - PLANS：加入實測基線、七個階段的路線與建議順序、FU06 檔案範圍、完整版 Chromium 的短 TMPDIR 規則、Google 請求間隔。
  - F4–F7：移除只對 DuckDuckGo、Brave 有意義的工作與測試。
  - F6、F7：加入瀏覽器模式、UA、引擎備援與連結解析的入口測試與真實驗收。
  - acceptance-findings：AF19、AF37、AF41、X09、X13 的處置。
  - mutation-survivors：N04c、N15、N16b、N16e、N16f、N17 改為「不再適用」。
- **獨立審查**：新 context 的審查者沒有發現 critical，提出 3 項 major、8 項 minor，全部已在本次修訂中修正：
  - F2-S3：discovery 的上限與每次工具呼叫的預算分開；加入能抓到「呼叫被限在啟動上限內」的檢查；逾時診斷改用固定英文字串 `startup timeout (<上限> ms)`。
  - F3-S3：解析改在引擎自己的 withPage 內、用同一個 page 依序進行，不巢狀占用 page 閘門（A04）；以主框架導覽請求認定網址，涵蓋 PDF 下載與慢速目標；新增 stayed on engine host 結果；搜尋主機改為精確主機，搜尋網址基底與搜尋主機改為可覆寫成員。
  - FG9：PLANS 完成判準改為 FG1–FG9；F7-S3 加入被擋、轉接器缺陷、零結果的判定與 80% 解析成功率門檻；F7-S4 加入 FU01–FU06 與 FG9 的證據表；F7-S2 案例 9、10 改以真實完整版 Chromium 與本機假引擎，執行真實的引擎方法與連結解析。
  - 其餘：第一個動作改為逐檔核對 plan-index 列出的 phase 檔；AutomationControlled 啟動參數列為保留的基線行為；列出 F3-S1、F3-S2 必須更新的既有斷言；Google 相對 href 依 R04 以頁面基底解析；F6-S1 案例 13 改用會記錄 newContext 選項的 fake browser；FU06 改為具體的 Git 與 grep 檢查；F3-S1 以完整版 Chromium 重跑 F1-S2 的晚渲染矩陣。
- **Git**：新的五份 phase 檔（phase-3-engines 到 phase-7-delivery）以 `git add -f` 逐檔追蹤；舊檔名 phase-3-timeouts、phase-4-status、phase-5-regression、phase-6-delivery 在同一個 commit 中移除。
- 所有階段仍為 Not started。

## Revision FA2（2026-10-22，執行方式）
- 依使用者要求（GOALS S8）：「修改一下prompt，不要停下來等我驗證，一次執行到底，有問題記錄下來就好，每一步皆強制commit，不準切換/創造branch」。只改計劃，不執行。
- PROMPTS：重寫啟動提示，逐條寫明不等使用者驗證、問題記錄後繼續、每一步強制 commit、只在 GUI 分支上工作；使用者端前提補充「執行者本身不會停下來等你」。
- GOALS：新增 S8，優先序改為 S8 > S7 > …；改寫 FG8 與 Git 的不變條件。
- PLANS：
  - 授權邊界：不停下等待使用者驗證；需要使用者決定的事項只列入最終彙報；
  - 第一個動作的唯讀核對紀錄，併入下一個步驟的 commit；
  - 每一步強制 commit，沒有例外；失敗、隔離或阻塞的步驟也要提交 checkpoint；
  - 刪除「phase 檔修訂可以不提交」的選項；
  - branch 限制擴充為不建立、切換、刪除、重新命名，不切到 detached HEAD，不建立 worktree；
  - 問題處理：任何問題都不停下來等待；
  - 完成判準同步改寫。
- F3-S3、F7-S3：引擎被擋時「交給使用者決定」改為列入最終彙報的後續選項，執行中不等待。F7-S4：確認沒有未提交的計劃檔，並確認每一步都有對應的 commit。
- 所有階段仍為 Not started。

## 執行（2026-10-22 起，Asia/Taipei）

### 啟動核對（唯讀，併入 F1-S1 的 commit）
- 使用者以 PROMPTS 的啟動提示啟動本計劃，授權範圍照該提示。
- pwd `/home/minervamuses/research-agent-workspace`；branch GUI；HEAD eaee132（[FA2]）；`git diff --cached --name-only` 為空。
- 原有未追蹤項目：app/store/、note/20261022/（使用者資料，不動），以及宿主沙箱的掛載佔位項目（.bash_profile、.bashrc、.claude/、.gitconfig、.gitmodules、.idea、.mcp.json、.profile、.ripgreprc、.vscode、.zprofile、.zshrc；不是 repository 內容，絕不 stage）。
- 計劃檔 16 份（GOALS、PLANS、PROMPTS、build-log、plan-index.json、context/ 四份、build/phase-1…7）都通過 `git ls-files --error-unmatch`。
- 工具鏈：conda `/home/minervamuses/miniconda3/condabin/conda`；env app 的 Python 3.13.14、Poetry 2.4.1、Node v24.18.0、npm 11.16.0。
- 基線（vendor 目錄，沙箱內）：`npm run build` exit 0；retention 15/15 exit 0；content-contract 3 組 exit 0；browser-lifecycle exit 0（stderr 的 Resource cleanup 堆疊是既有的注入失敗案例）。
- 以步驟 ID 對帳：git log 沒有任何 F?-S? commit，build-log 沒有執行事件；從 F1-S1 開始。

### F1-S1 整頁轉換與結構修正
- **改動**（FG1；AF01、AF02、AF04、AF05、AF07；突變 N07e、N07f）：src/enhanced-content-extractor.ts。
  - 以 `<body>`（沒有時用整份文件）為根，依原順序轉換；移除 `main, article, [role="main"]` 的縮窄邏輯。只移除 script、style、noscript、template 照舊。
  - 表格只取自己的 tr（直接子項，或 thead/tbody/tfoot 底下的 tr）；儲存格內容收成單行，巢狀表格只在該儲存格內輸出一次；`<caption>` 以 `Table caption:` 在列前輸出一次；保留「span structure simplified」說明。
  - 區塊分隔清單改為具名常數 BLOCK_TAGS，加入 address、aside、dd、details、dialog、dl、dt、fieldset、footer、form、header、hgroup、hr、legend、menu、nav、optgroup、option、search、summary。
  - HTTP 路徑標題取 `head > title`，沒有時取不在 svg 之內的第一個 title，否則 unknown；兩條路徑都把空白收成單一空格。
  - 連結 label 的換行與連續空白收成單一空格。
- **測試**：tests/test-content-contract.mjs 新增一組「whole-page conversion, tables once, block separators, base and title」：巢狀表格 1–6 層每段文字恰好一次、8→16 層長度線性、多篇 article 依序、aside+main、工作第 3 項全部元素不黏連（含 TermDef）、caption 一次且含兩個 `<p>` 的儲存格不斷行、`<base href="/docs/sub/">` 與無 base 兩個案例（final host 為 final.example）、svg title 不當頁面標題、標題空白正規化。既有 AC02 斷言未改。
- **檢查**（vendor 目錄，沙箱內）：
  - `npm run build` exit 0；retention 15/15 exit 0；content-contract 4 組 exit 0；browser-lifecycle exit 0；`git diff --check` exit 0。
  - 判別力：evidence/F1-S1/discriminate.mjs 逐項對 eaee132 的乾淨重建（old-eaee132.json）與本步 dist（new.json）執行：舊碼 10/12 失敗（16 層巢狀 7034→1802361 字元），本步 12/12 通過；兩個 base 案例在舊碼也通過，因為它們守護的是突變而非舊缺陷。
  - 突變（evidence/F1-S1/mutations.jsonl，在 `$TMPDIR` 暫存複本套用）：N07e（final URL 換成錯誤 host）被 content-contract 殺死（exit 1）；N07f（忽略 `<base href>`）被新的 `/docs/sub/next` 案例殺死（exit 1）。F6-S3 仍會依清單正式複驗。
- **限制**：儲存格收成單行後，巢狀表格的多列在該儲存格內以空格相連；`<pre>` 在儲存格內也會收成單行。這是 FA02 的退化。parseContent 結尾的 `/[ \t]+\n/g` 留給 F1-S4。
- **下一步**：F1-S2。

### F1-S2 晚渲染等待
- **改動**（FG2；AF03）：
  - src/browser-pool.ts：OPERATION_TIMEOUTS 新增 renderSettle: 3000。
  - src/enhanced-content-extractor.ts：瀏覽器讀取 HTML 時，在 `goto(domcontentloaded)` 與媒體檢查之後、讀取標題與內容之前，呼叫新的 settleRendering：等到「networkidle 且 body 有可見文字」或 min(renderSettle, 剩餘預算)。由 Node 端每約 100 ms 以 `page.evaluate` 讀 `document.body.innerText`（每次 evaluate 受剩餘等待時間約束），networkidle 以 `page.waitForLoadState` 加同一上限；不用 waitForFunction。每個等待都經 `budget.wait`，取消或期限到時立即結束。text/plain 與 HTTP 路徑不等待。
  - 等滿仍沒有文字時維持 empty_text，該次 browser 嘗試的 error 與 Read error 寫出 `No visible text after waiting <實際> ms for client rendering (limit <上限> ms)`。
  - extractWithBrowser 多一個 event 參數以寫入這個事實；沒有新增 PageRead 欄位（types.ts 未改，F5-S2 會整理每次嘗試的欄位）。
- **測試**：tests/test-browser-lifecycle.mjs 新增 stub page 案例：上限 120 ms 時等待約 120 ms 且 waitForLoadState 收到 120、可見資訊含等待時間；上限 5000、預算 200 ms 時等待上限 ≤200 且 1 s 內返回（狀態為 empty_text 或 timeout，兩者都是預算邊界上的正確結果）；50 ms 時 abort 則 1 s 內以 cancelled 返回；文字出現且網路靜止時立即以 text 返回。
- **檢查**（vendor 目錄，沙箱內）：`npm run build` exit 0；retention 15/15、content-contract 4 組、browser-lifecycle（連跑 3 次）全部 exit 0。
- **真實 Chromium**（evidence/F1-S2/late-render.mjs，沙箱內直接以 node 匯入 dist、PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/ms-playwright；F3-S1 之前產品仍是 headless shell；本機 HTTP 伺服器，HTML 回應本身沒有文字以觸發 fallback）：
  - 本步 dist（after.json）：計時器 0/100/300/700/1500 ms、fetch 200 ms、DCL 時已有導覽列且主要內容 fetch 300 ms 後插入、CSP `script-src 'unsafe-inline'` 加計時器 300 ms，全部以 text 取得目標文字（550–1584 ms）；5000 ms 才插入者在 3047 ms 以 empty_text 返回並附 `waiting 3002 ms … (limit 3000 ms)`；持續輪詢的頁面在 3037 ms 以 text 返回。
  - eaee132 乾淨重建（before-eaee132.json）：同一矩陣只有計時器 0 ms 與持續輪詢（文字在 0 ms 插入）取得目標文字；導覽列案例只得到導覽列文字。
  - 額外延遲：靜態頁直接走瀏覽器路徑 32 ms → 561 ms（約 +530 ms，即 networkidle 的 500 ms 靜止窗）；HTTP 已有文字的靜態頁 1–3 ms，不進瀏覽器，不受影響。
  - 驅動腳本在結尾 closeAll 並關閉伺服器；每條沙箱指令有自己的 PID namespace，本次沒有另外的殘留程序取證（真實程序生命週期屬 F4、F7）。
- **限制**：F3-S1 改用完整版 Chromium 後要在沙箱外以短 TMPDIR 重跑這個矩陣（phase-3 已列）。每次瀏覽器讀取 HTML 至少多等約 500 ms 的 networkidle 窗。
- **下一步**：依建議順序做 F2-S1。

### F2-S1 /proc 解析與程序樹回收
- **改動**（FG5、FG6；AF24、AF35；突變 P07、P27）：app/agent/mcp.py。
  - 新增模組層級 `_proc_stat(path)`：從最後一個「)」之後取欄位，回傳 (state, ppid, pgrp, starttime)；讀檔、int 轉換與索引都在 try 之內，解析不了就回 None（該列略過）。remember_processes 與 kill_owned 共用它；/proc 目錄名不是純數字就略過。
  - observe 迴圈與 kill_owned 經 observe_once 呼叫 remember_processes：非預期例外只記一次 warning（`Web Search process observation failed; continuing`），迴圈繼續。kill_owned 的逐程序收尾任何例外都略過該程序。
  - `finally` 中 `await watcher` 的例外只記 warning，不會取代已發布的結果或原本的例外。
  - 身分判定規則與收尾時機都沒變：直接子程序帶呼叫標記、starttime 一致、只在 pgid 等於 pid 時群組 kill；仍只在期限到時強制收尾（X14 不在範圍）。
- **測試**（app/tests/test_mcp.py）：
  - lifecycle server 新增 `plain`（回 known result）與 `grandchild` 模式：server 收到 tools/call 後卡住；中介子程序以 start_new_session 產生忽略 SIGTERM 的 `/bin/sleep` 孫程序，寫下 pid 與 starttime，150 ms 後自行結束。`_assert_lifecycle_pid_gone` 改用 `_proc_stat` 的 `_alive`。
  - `test_web_search_survives_host_process_names_with_parentheses`：把 /bin/sleep 複製為 `a) b c d` 執行，其存活期間 discovery 與呼叫都回 known result；finally 只終止自己的 sleeper。
  - `test_web_search_observer_failure_keeps_received_result`：monkeypatch `_proc_stat` 第一次呼叫拋例外；結果仍為 known result，warning 恰好一次，之後的觀察繼續。
  - `test_web_search_reaps_detached_grandchild_after_intermediate_exits`：逾時收尾後孫程序（以 starttime 確認身分）已不存活，呼叫 0.8 s 內返回；finally 只清理自己記錄的孫程序。
- **檢查**（app 目錄，沙箱內，XDG_CACHE_HOME、AGENT_LOG_DIR、TMPDIR 指到 `$TMPDIR` 子目錄，PYTHONDONTWRITEBYTECODE=1）：
  - 三個新測試 3 passed。
  - focused `pytest tests/test_mcp.py tests/test_mcp_stderr_log.py tests/test_extension_mcp.py -q -p no:cacheprovider`：49 passed。
  - 判別力（evidence/F2-S1/mutate.py 在 `$TMPDIR` 複本套用，複本不含 app/desktop 與 app/store，以 PYTHONPATH 指向複本並確認 import 的是複本）：
    - HEAD 邏輯（只多了測試用的 `_proc_stat`）：怪名程序測試失敗（`ValueError: invalid literal for int() with base 10: 'c'`，即 AF24），觀察者故障測試失敗；孫程序測試通過（HEAD 本來就有展開與週期觀察）。
    - P07（不展開後代）：孫程序測試失敗，孫程序存活。
    - P27（移除週期觀察）：孫程序測試失敗；觀察者故障測試也失敗。
    - 結果在 evidence/F2-S1/variant-{old,P07,P27}.txt。
- **限制**：P07b、P07d（可選）未另加測試；PID 重用難以穩定重現。快速失敗路徑的後代回收仍不在範圍（X14）。
- **下一步**：依建議順序做 F3-S1。

### F3-S1 完整版 Chromium 與一般 UA
- **改動**（FG9；FU02、FU03）：src/browser-pool.ts。
  - chromium.launch 加 `channel: 'chromium'`（Playwright 完整版 Chromium，新 headless 模式）；BROWSER_HEADLESS=false 的語意、launch 參數（含既有的 AutomationControlled）、單一 browser、併發上限、owner flag 與收尾都不變。
  - 新增 `normalUserAgent(version)`：固定格式 `Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/<主版號>.0.0.0 Safari/537.36`，主版號取自 browser.version()；每個 newContext 都帶這個 UA。不隨機，不做其他擬態。
- **測試**：browser-lifecycle 的 stub browser 加 `version()`='777.0.0.0' 並記錄 launch 與 newContext 選項，斷言 `channel: 'chromium'`、7 個 context 都收到 `Chrome/777.0.0.0` 且不含 Headless；brokenPool stub 與 retention 的 fakeBrowser 也加 `version()`（phase-3 列出的預期更新）。
- **檢查**：
  - 沙箱內：`npm run build` exit 0；retention 15/15、content-contract 4 組、browser-lifecycle 全部 exit 0。
  - 沙箱外、短 TMPDIR（`mktemp -d /tmp/ws.XXXX`，用完刪除）、PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/ms-playwright：evidence/F3-S1/full-chromium.mjs 經 BrowserPool 開本機頁面（full-chromium.json）：
    - browser.version() 139.0.7258.5；`navigator.userAgent` 與伺服器收到的 User-Agent 都是 `… Chrome/139.0.0.0 Safari/537.36`，不含 Headless；
    - 自有 browser 程序（node 的直接子程序，pgid=pid）的 `/proc/<pid>/exe` 是 `~/.cache/ms-playwright/chromium-1181/chrome-linux/chrome`，呼叫期間 7 個後代都不是 headless_shell；
    - closeAll 後同一腳本以 starttime 檢查：沒有存活的後代。
  - 晚渲染矩陣以完整版 Chromium 重跑（同一個 evidence/F1-S2/late-render.mjs，結果在 evidence/F3-S1/late-render-full-chromium.json）：與 F1-S2 相同，前八個案例都以 text 取得目標文字（575–1604 ms），5000 ms 者在 3068 ms 以 empty_text 返回並附等待時間，持續輪詢者在 3068 ms 以 text 返回；靜態頁直接走瀏覽器 585 ms，HTTP 已有文字 2 ms。結果相同，不需回到 F1。
- **發現（屬 F4-S2，不在本步修正）**：沙箱外環境含 DBUS_SESSION_BUS_ADDRESS 時，pool 的 owned 記錄是空的：browser 根程序的 cmdline 只剩 1 個 NUL 欄位，owner flag 只能以空白切分找到（full-chromium.json 的 browserRoot.argv）。這直接重現 AF22；收尾仍無殘留，因為 Playwright 的 close 成功。
- **下一步**：F3-S2。

### F3-S2 Google 主力、Bing 備援，移除 DuckDuckGo 與 Brave
- **改動**（FG9；FU01、AF41；FA13）：src/search-engine.ts，另從 src/browser-pool.ts 刪除只服務 Bing 首頁流程、已無使用者的 formSelector 常數。
  - 引擎順序改為 `Google` → `Bing`；策略 B 與 URL 合併邏輯不變。
  - 刪除 DuckDuckGo（axios 請求、解析器、uddg 清理）、Brave（方法、解析器、403/429 與暫態重試）、Bing 首頁輸入框流程與隨機 cvid；search-engine.ts 不再 import axios。
  - 新增 `queryMarket(query)`：含漢字（`\p{Script=Han}`）→ Google hl=zh-TW、Bing setlang=zh-Hant&cc=TW；否則 hl=en、setlang=en&cc=US。
  - SearchEngine 的 static 成員 googleSearchUrl、googleHost、bingSearchUrl、bingHost 可覆寫（不是環境設定）。
  - tryGoogleSearch：導覽 `<googleSearchUrl>?q=&hl=&num=<limit>`；HTTP ≥400 → `Google returned HTTP <status>`；最終路徑以 `/sorry/` 開頭 → `Google redirected to <path> (HTTP <status>)`；兩者都不重試、不換方式。否則以 searchSelector 上限等待 `#search a h3, #rso a h3`，解析 `#search`（沒有時 `#rso`）內的 `a:has(h3)`：title 取 h3，url 以搜尋頁實際網址（含 `<base href>`）解成絕對網址，observedUrl 保存原始 href，snippet 取「只含這一個結果連結的最大祖先區塊」內的 `[data-sncf], .VwiC3b`，沒有就留空。
  - tryBingSearch：直接導覽 `<bingSearchUrl>?q=&count=&setlang=&cc=`；HTTP ≥400 為錯誤；只解析 `#b_results > li.b_algo`，沒有正式結果就是零解析。
  - 兩個方法 attempts 都是 1；每次解析在 stderr 留一行計數。
- **測試**：
  - retention 改寫為兩引擎（20 項）：Google 滿 5 筆時 Bing 不被呼叫；Google 2 筆 + Bing 1 筆重複 3 筆新 → 恰好 5 筆、合併來源 `Google, Bing`；Google 429 與 `/sorry/` 兩種錯誤由 Bing 補足且引擎行保留錯誤；後續失敗保留先前候選；全失敗與全零解析可區分；無語意評分；URL scheme 與編碼保留；fake browser 驗證 Google 429、`/sorry/` 都只有 launch→goto→context-close（不等待、不重試、不開第二個 browser），200 時等待並解析主結果區（相對 `/goto?url=` 包裝、直接 href、缺 snippet、缺 title，側欄 `#rhs` 不計）；經 `search()` 確認相對包裝 href 成為絕對候選且 observedUrl 為原始 href；中英文查詢的 hl、num、setlang、cc、count 與無 cvid；覆寫搜尋網址後兩個方法都導覽覆寫後的網址；呼叫期限保留先前候選，Google 卡住時 Bing 不再開始；Bing 只取 `#b_results > li.b_algo`（含 `<base>` 相對解析），只有側欄模組（`#b_context` 的 `.b_card`、`.b_result`）與 `li.b_ans` 時為零解析；Google 的 `<base href>` 解析與只有側欄時為零。
  - browser-lifecycle 的 selector 上限案例改為 Google 等待結果卡住、由 stub 的 Bing 接手，斷言等待為 `[20]`。
  - 刪除 DuckDuckGo、Brave 的測試與斷言；`grep -rni 'duckduckgo\|brave\|ddg\|uddg' src tests` 沒有結果。app/agent 沒有改動（FU06）。
- **檢查**（vendor 目錄，沙箱內）：`npm run build` exit 0；retention 20/20、content-contract 4 組、browser-lifecycle 全部 exit 0。
- **限制**：Google 的 snippet 選擇器（`[data-sncf]`、`.VwiC3b`）與結果區（`#search`／`#rso`）依頁面現況，日後結構變動時 snippet 會留空、或成為零解析；真實頁面由 F7-S3 觀測（FG9 閘門）。其他語言的查詢暫時歸為英文（FA13 已知限制）。
- **下一步**：F3-S3。

### F3-S3 以實際導覽解析結果網址
- **改動**（FG9；FU04、X13；FA14）：
  - src/types.ts：新增 LinkResolution（wrapperUrl、outcome：resolved／stayed_on_engine_host／timeout／failed／not_started、ms、reason），SearchResult 新增 resolution。
  - src/browser-pool.ts：OPERATION_TIMEOUTS 新增 linkResolve: 6000。
  - src/search-engine.ts：
    - 候選的接納移到 admitBatch，由 Google、Bing 方法在自己的 withPage 回呼內、解析完結果後以同一個 page 呼叫（不巢狀 withPage，不開新分頁）。
    - 第一輪立即依原順序把候選補到 limit；包裝網址（host 等於該引擎的可覆寫搜尋主機）先記為 not_started。所以呼叫期限到時，候選不會遺失。
    - 第二輪依序解析包裝：referer 為解析前的搜尋頁網址，`goto(waitUntil: 'commit')`，監聽 page 的 request 事件。第一個主框架、host 不是搜尋主機的導覽請求網址就是結果，不等目標回應。上限 min(linkResolve, 剩餘預算)；監聽器與 timer 在 finally 移除，被中斷的 goto promise 都有處理。
    - 解析出的網址若已存在，合併來源、移除這一筆並補入下一筆；去重以解析後的網址進行。
    - 結果：committed 但到上限仍未離開搜尋主機 → stayed_on_engine_host；未 committed → timeout；goto 出錯 → failed（錯誤第一行，去掉 ANSI）；期限已到 → 剩餘的保留 not_started。未解析者 url 保留絕對包裝網址。
    - search() 在每個引擎結束時關閉 admit（open 旗標），在呼叫期限後才結束的方法不能再改動結果。
    - 解析器不再在 limit 截斷（parsedCount 是頁面上的結果數），由接納套用 limit，重複時才能由下一筆補上。
- **測試**：
  - retention（25 項）：engineWith 的 stub 改為呼叫 admit；fake browser 加入 on/off/mainFrame 與包裝行為。新增案例：
    - 相對 `/goto` 包裝被替換為解析出的網址，observedUrl 為原始 href，resolution 有 wrapperUrl、resolved 與整數 ms；support.google.com 與直接連結不導覽；包裝導覽帶 referer＝搜尋頁網址、waitUntil commit；
    - linkResolve 縮為 60 ms 時，stayed_on_engine_host、timeout、failed（只留第一行）、resolved 四種各自正確，未解析者保留包裝網址；
    - 預算 150 ms、包裝都卡住時，4 筆候選都保留包裝網址，第一筆 timeout、最後一筆 not_started（原因含 deadline），1 s 內返回，包裝導覽 ≤2 次；
    - Google 8 筆、limit 5、第 3 筆解析後與第 1 筆重複 → 只導覽前 6 筆，回傳 t1、t2、t4、t5、t6；
    - Google 與 Bing 包裝解析到同一網址 → 一筆、來源 `Google, Bing`；
    - MAX_CONCURRENT_PAGES=1 時搜尋與解析在 900 ms 內完成，不死鎖。
    - 連跑 8 次全部 exit 0。
  - browser-lifecycle 的 stub Bing 改為呼叫 admit。
- **檢查**：
  - 沙箱內：`npm run build` exit 0；retention 25/25、content-contract 4 組、browser-lifecycle 全部 exit 0。
  - 真實完整版 Chromium（沙箱外、短 TMPDIR，用完刪除；evidence/F3-S3/resolve-real.mjs → resolve-real.json）：本機伺服器只綁 127.0.0.1，以 `localhost:<port>` 為搜尋主機、linkResolve 縮為 2000 ms，經 `SearchEngine.search()`：
    - JavaScript 跳轉 13 ms、HTTP 302 7 ms、302 到 application/pdf 10 ms、302 到永不回應的目標 8 ms，全部 resolved 為 `127.0.0.1` 上的目標網址；PDF 與永不回應兩種遠低於上限；
    - 不跳轉的包裝在 2001 ms 記為 stayed_on_engine_host，url 保留包裝網址；
    - 伺服器紀錄：每個包裝請求的 Referer 都是搜尋頁網址；
    - Google completed、Bing strategy_stopped；closeAll 後同一腳本以 starttime 檢查，7 個後代都沒有存活；stderr 沒有 unhandled rejection。
- **限制**：
  - 依 FA14，第一個離開搜尋主機的導覽就是結果；若引擎先導到同家的其他主機（例如 consent 頁），會被當成結果。本機（台灣 IP）在 OD1 沒有觀察到。
  - 對搜尋主機的額外請求是否讓 Google 改為封鎖，由 F7-S3 觀測。
  - 可見文字留給 F3-S4。
- **下一步**：F3-S4。

### F3-S4 可見的解析事實
- **改動**（FG9；FU04）：src/utils.ts 的 formatSearchResponse（兩個搜尋工具共用，U12）。
  - 每筆候選的 `URL:` 是解析後的網址；解析失敗時是包裝網址。
  - 有解析紀錄時，`URL:` 之後加一行：
    - resolved：`Link: engine redirect from <包裝網址的 host> resolved by navigation in <ms> ms`；
    - 其他：`Link: engine redirect not resolved (<結果種類>: <原因>); this URL is the engine's redirect wrapper, not the source page`。
  - Read statistics 行尾加 `engine_redirects_resolved=<n>; engine_redirects_unresolved=<n>`；既有欄位與順序不變（F5-S2 再整理口徑）。
- **測試**：retention 新增 formatter 案例：resolved、timeout、stayed_on_engine_host 與非包裝四筆候選的文字互不相同，各自的 Link 行正確，非包裝者沒有 Link 行；統計為 resolved=1、unresolved=2；沒有包裝時兩者都是 0。
- **檢查**（vendor 目錄，沙箱內）：`npm run build` exit 0；retention 26/26、content-contract 4 組（既有統計 regex 仍符合）、browser-lifecycle 全部 exit 0。
- **F3 階段結論**：FG9 的離線與本機真實 Chromium 證據齊備（F3-S1 完整版 Chromium 與 UA、F3-S2 引擎順序與移除、F3-S3 解析、F3-S4 可見事實）。真實 Google／Bing 頁面由 F7-S3 觀測，未觀測前不寫成已驗證。
- **下一步**：依建議順序做 F1-S3。

### F1-S3 字元編碼與媒體事實
- **改動**（FG1；AF06、AF10）：
  - src/enhanced-content-extractor.ts：
    - **編碼**：新增 decodeBody（FA03）：BOM（UTF-8、UTF-16BE/LE）→ Content-Type charset → HTML 前 4096 bytes 的 `<meta charset>`／http-equiv（以 latin1 掃描）→ UTF-8，用 Node 內建 TextDecoder 解碼；text/plain 只看 BOM 與 header。不支援的 label 以 UTF-8 解碼並記下說明。
    - **過大回應**：axios 超過 10 MiB（`ERR_BAD_RESPONSE`、maxContentLength）時，從 `error.request.res` 取回 statusCode、Content-Type 與 responseUrl。媒體不受支援（含 PDF）→ unsupported_media，錯誤 `Unsupported media: <type> (response body exceeds 10 MiB read limit)`；否則 http_error，錯誤 `response body exceeds 10 MiB read limit`。
    - **瀏覽器下載**：goto 之前註冊 response（只記主框架導覽回應）與 download（立即 cancel）監聽，goto 後移除。goto 拋錯時，若主框架回應是不支援的媒體，或已開始下載，標為 unsupported_media；有回應就保留 status、Content-Type 與 URL，沒有回應時標頭維持 unknown 並註明 `(download started)`；兩者都沒有就照舊拋錯。
    - **轉換失敗**：converting() 讓兩條路徑的 parseContent 與截斷例外一律成為 conversion_error。
    - 每次嘗試開始時清除 encoding；catch 中若本次已判定為 unsupported_media，就保留該狀態。
  - src/types.ts：PageRead 新增 encoding（name、source、note）。
  - src/utils.ts：
    - 新增 sanitizeErrorMessage：去 ANSI、去 Playwright `Call log:` 區塊、只留第一行、上限 300 code points；用於所有 transport 的嘗試錯誤。
    - formatPageRead 在 HTTP 行之後輸出 `Character encoding: <name> (<來源>[; <說明>])`。
- **測試**：
  - content-contract 新增一組（本機 node:http 伺服器）：
    - 寫死 byte 的 Big5「中文」（header charset）、Shift_JIS「日本」（`<meta charset>`）、windows-1252「café」（http-equiv）、UTF-8 BOM「中文」（header 宣稱 iso-8859-1），四者都解碼正確，且輸出含編碼與來源；
    - 未知 charset 有明示說明；
    - 約 11 MiB application/pdf → unsupported_media，200 與 Content-Type 保留；約 11 MiB text/html → http_error，附讀取上限原因與已知標頭；
    - 錯誤淨化為單行並保留第一行原因；
    - stub 瀏覽器：主框架回應 application/pdf 加 ERR_ABORTED、下載但沒有回應，兩者都是 unsupported_media；沒有下載也沒有回應的 ERR_ABORTED 仍是 http_error，錯誤已淨化；
    - parseContent 拋例外時，HTTP 與 browser 兩條路徑都是 conversion_error。
  - browser-lifecycle 的晚渲染 stub page 補上 on/off/mainFrame。
- **檢查**：
  - 沙箱內：`npm run build` exit 0；retention 26/26、content-contract 5 組、browser-lifecycle 全部 exit 0。
  - 判別力：新的 content-contract 在上一個 commit（2e40b1a）的乾淨重建上失敗於第一個編碼案例，Big5 得到 `����`（AF06 重現）。
  - 真實完整版 Chromium 的提前探測（沙箱外、短 TMPDIR；evidence/F1-S3/download-real.mjs → download-real.json）：HTTP 讀取得到 403 後，瀏覽器讀到 application/pdf 或 attachment 的 application/octet-stream，兩者都是 unsupported_media，保留 200 與 Content-Type。依 phase-1，AF10(b) 仍要等 F7-S2 案例 7 經真實入口通過才記為已修正。
- **限制**：瀏覽器路徑不記錄編碼（由瀏覽器自行解碼）。HTML 標準中 meta 宣告 UTF-16 時改用 UTF-8 的細則沒有實作；本步只處理 FA03 列出的順序。
- **下一步**：F1-S4。

### F1-S4 線性截斷與完整連結
- **改動**（FG1；AF08、AF09、AF23；突變 N06d）：
  - src/utils.ts：truncateMarkdown 改用 safeCut：在 code point 陣列上，從切點往前、往後各做一次有界局部掃描（LINK_SCAN = 10000 code points，不小於內容上限），不對全文跑 regex。
    - 切點落在 `[label](<url>)` 或 `[label](http…)` 內（含 label 內有 `]`、巢狀 `[[1]]`、label 跨行）時，以括號配對找到 label 的 `[`，捨棄整個連結；
    - 切點落在裸 http(s) 網址 token 內（以空白、`<`、`>` 為界，所以 `Foo_(bar)_baz` 這種含括號的網址算同一 token）時，從 scheme 起捨棄；
    - 不補造目的地；沒有截斷時原樣返回；originalLength 與 returnedLength 都以 code points 計。
  - src/enhanced-content-extractor.ts：parseContent 結尾的 `/[ \t]+\n/g` 改為 trimLineEnds，逐行以迴圈去掉行尾空白與 tab。
- **測試**（content-contract 第一組）：
  - `😀中文abc` 截為 4 時 originalLength=6、returnedLength=4；
  - `[[1]](<https://example.org/a>)`、label 內有換行的連結、text/plain 的 `https://en.wikipedia.org/wiki/Foo_(bar)_baz`、`[x](https://example.org/c)` 四種輸入，前後加文字，每一個可能的切點都只交付完整連結或完全不交付，不留殘缺開頭；
  - 150 KiB 未閉合 `[` 的截斷，以及 `<pre>` 內 150 KiB 空白的轉換，各在 1 s 內完成；
  - `<pre>` 行尾空白與 tab 被去掉。既有截斷斷言照舊通過。
- **檢查**：
  - 沙箱內：`npm run build` exit 0；retention 26/26、content-contract 5 組、browser-lifecycle 全部 exit 0。
  - 判別力：新的 content-contract 在 aa971aa 的乾淨重建上失敗於 `[[1]]` 在第 7 點的切點（得到 `Intro [`，AF08 重現）。
  - 突變 N06d（originalLength 改以 UTF-16 code unit 計）被 content-contract 殺死（`7 !== 6`；evidence/F1-S4/mutations.jsonl）。
  - 倍增量測（evidence/F1-S4/measure.mjs → measure.jsonl，每項一次）：
    | 項目 | 版本 | 128 KiB | 256 KiB | 512 KiB | 1 MiB |
    | --- | --- | --- | --- | --- | --- |
    | 截斷 | aa971aa | 3835 ms | 15519 ms | — | — |
    | 截斷 | F1-S4 | 2 ms | 3 ms | 5 ms | 11 ms |
    | 轉換 | aa971aa | 3864 ms | 15524 ms | — | — |
    | 轉換 | F1-S4 | 8 ms | 12 ms | 16 ms | 94 ms |

    舊版每倍增約 4 倍（二次方），所以只量到 256 KiB；新版約為線性（1 MiB 轉換以 cheerio 解析為主）。
- **限制**：連結或網址長於 10000 code points、橫跨切點時不受保護（掃描有界）；正文上限本身是 10000，實務上不會遇到。
- **F1 階段結論**：FG1、FG2 的離線、本機與真實 Chromium 證據齊備；AF10(b) 依 phase-1 待 F7-S2 案例 7 經真實入口確認。
- **下一步**：F2-S2。

### F2-S2 取消、期限後回應與診斷
- **改動**（FG5、FG6；AF25–AF28、AF31 Python 部分、AF36、AF38；突變 P13、P13c、P18、P18b、P26）：app/agent/mcp.py（startup.py 不需改）。
  - **取消**：新增 settled_error()：task 已結束且不是被取消時取回其例外。呼叫端取消路徑在 settle 之後取回並記 debug，不再出現「Task exception was never retrieved」（AF25）。
  - **期限後回應**：work deadline 時沒有結果而取消 task，記為 timed_out。之後 task 不論以何種例外結束（例如遲到回應造成的 TaskGroup／BrokenResourceError），對外一律是 TimeoutError，原例外放在 `__cause__` 並記 debug（AF27）。期限前結束的協定錯誤照舊原樣傳出。
  - **逾時訊息（FA09、AF28）**：`Web Search timed out before a result was received (startup, initialization, call and cleanup included; DEFAULT_TIMEOUT=<ms> ms)`。
  - **載入診斷（FA09、AF26）**：新增 _describe_failure：保留 `<類型>: <訊息>`，ExceptionGroup 逐層展開，附 `[causes: …]`，最多 3 個葉例外，多的寫 `(+N more)`。sanitize_stdout 為真的 server 附 `; stderr log: <路徑>`。路徑由 `_mcp_log_dir(create=False)` 與 server 名稱組出，新增的 create 參數讓診斷不建立目錄。前綴 `mcp:<name>: applied_but_unavailable: <stage>:` 與 _spec_to_connection 的型別不變。
- **測試**（app/tests/test_mcp.py）：
  - lifecycle server 新增 `late` 模式：等 `_meta.web_search_work_ms` + 100 ms 才回應；
  - test_web_search_real_session_budget_and_cleanup 在計時前先 import langchain_mcp_adapters.client 與 .sessions（AF38）；
  - 新測試：
    - 遲到回應得到含 `DEFAULT_TIMEOUT=800 ms` 的 TimeoutError，訊息不含「unhandled errors in a TaskGroup」，0.8 s 內返回且無殘留；
    - 呼叫端取消後 task 以 RuntimeError 結束，gc.collect() 後 loop exception handler 沒有「never retrieved」；
    - task 忽略取消 3 s 時，呼叫端在 1.0 s 內以 TimeoutError 返回（外層 wait_for 0.8+2 s 偵測卡死）；
    - 經 load_mcp_tools_with_families 載入 spec.env DEFAULT_TIMEOUT=800 的慢啟動 server：1.2 s 內回空工具，診斷含 TimeoutError 與 800 ms；`_bounded_web_search(…, 300001)` 被拒；
    - web_search 指向立刻 exit 的程式：空工具，診斷為 `…: load: ExceptionGroup: … [causes: McpError: Connection closed]; stderr log: <XDG_CACHE_HOME>/agent-mcp/web_search.stderr.log`；
    - 有／無 extension 兩種 session 啟動：load 失敗的診斷出現在 extension_startup_diagnostics，load_mcp_tools_with_families 拋例外時出現「MCP loader unavailable: RuntimeError」。
  - 新測試都把 XDG_CACHE_HOME 設到 tmp_path。
- **檢查**（app 目錄，沙箱內，XDG_CACHE_HOME、AGENT_LOG_DIR、TMPDIR 隔離）：
  - focused `pytest tests/test_mcp.py tests/test_mcp_stderr_log.py tests/test_extension_mcp.py -q -p no:cacheprovider`：56 passed。
  - 判別力與突變（evidence/F2-S2/mutate.py 在 `$TMPDIR` 複本套用，複本不含 app/desktop、app/store；results.jsonl）：
    - F2-S1 版 mcp.py 失敗 5 個新測試。其中遲到回應為 `ExceptionGroup … anyio.BrokenResourceError`（AF27 重現），取消為 `Task exception was never retrieved`（AF25 重現）。
    - P13、P13c 被 startup 診斷測試殺死（兩個參數各失敗）；P18、P18b 被預算來源測試殺死；P26 被卡住的取消測試殺死。
  - 順序無關：單獨執行 `[startup]` 與 `[initialize]` 各連跑 3 次全部 1 passed（約 1.03 s）；整個 test_mcp.py 連跑 3 次全部 41 passed。
- **下一步**：F2-S3。

### F2-S3 啟動上限 15 秒
- **改動**（FG5；FU05、FA15、X09）：app/agent/mcp.py。
  - 新增具名常數 `WEB_SEARCH_STARTUP_TIMEOUT_MS = 15000`。
  - `_load_web_search_tools` 的 discovery（啟動程序、initialize、列出工具、收尾）改以 `min(15000, DEFAULT_TIMEOUT)` 為 `_bounded_web_search` 的整體上限；intercept 中每次工具呼叫仍用 DEFAULT_TIMEOUT 與既有切分（A03 不變）。
  - 啟動逾時改拋 `Web Search startup timeout (<上限> ms) before a result was received (startup, initialization, tool listing and cleanup included; limit is min(15000 ms, DEFAULT_TIMEOUT=<ms> ms))`。經 F2-S2 的診斷格式，web_search 在本 session 標為 applied_but_unavailable（sanitize_stdout 時附 log 位置），其他 MCP 照常載入。
  - 只依時間與程序狀態，沒有搜尋判斷，沒有新增環境設定（FU06）。
- **測試**（app/tests/test_mcp.py）：
  - lifecycle server 新增 `slow_meta` 模式（呼叫花 600 ms 後回傳 `_meta`）；
  - `test_web_search_startup_is_capped_without_blocking_other_servers`：常數縮為 300 ms、DEFAULT_TIMEOUT=300000，啟動卡 2 s 的 server 在 0.6 s 內以 `startup timeout (300 ms)` 結束且無殘留；同一次 load_mcp_tools_with_families 中，另一個正常 MCP server 的 local_probe 仍載入成功，總時間 < 2 s；
  - F2-S2 的預算來源測試加上斷言：DEFAULT_TIMEOUT=800 小於常數時，診斷為 `startup timeout (800 ms)`；
  - `test_web_search_calls_keep_the_full_budget_after_a_short_startup_cap`：常數 300 ms 時，呼叫回報的 `web_search_work_ms` > 1000，且花 600 ms 的呼叫成功返回；既有 meta 測試照舊通過。
- **計劃更正**：phase-2 原寫 DEFAULT_TIMEOUT=2000。2000 ms 時 `reserve = min(15, max(1.5, 0.1), 1.0) = 1.0 s`，工作時間只有 1000 ms，`web_search_work_ms` 一定小於 1000，「大於 1000」不可能成立。改用 4000（工作時間 2500 ms），測試仍能分辨「被限在 300 ms 啟動上限」（約 150 ms 以內）。phase-2 該行已同步更正。
- **檢查**（app 目錄，沙箱內，XDG_CACHE_HOME、AGENT_LOG_DIR、TMPDIR 隔離）：
  - 量測：本機 lifecycle server 的 discovery 約 18–27 ms（8 次），300 ms 上限的 150 ms 工作窗足夠；
  - focused `pytest tests/test_mcp.py tests/test_mcp_stderr_log.py tests/test_extension_mcp.py -q -p no:cacheprovider`：58 passed；
  - 判別力（evidence/F2-S3/mutate.py、results.jsonl）：呼叫改用啟動上限的「陷阱」變體被完整預算測試殺死；discovery 不套上限的變體被啟動上限測試殺死。
- **F2 階段結論**：FG5 的 AF24–AF28、AF35、AF36、AF38、FU05 都有離線真實程序證據；P07、P13、P13c、P18、P18b、P26、P27 已被殺死，F6-S3 會依清單正式複驗。
- **下一步**：F4-S1（F1、F3 已完成）。

### F4-S1 總時間上限與每頁視窗
- **改動**（FG3；AF19、AF20、AF21）：
  - src/browser-pool.ts：
    - OPERATION_TIMEOUTS 新增 pageRead: 6000（FA06）；
    - CallBudget 新增 expiry 訊息參數；`child(cap, expiry)` 只有在子上限早於父預算時才使用自己的 expiry，否則沿用「Call deadline exceeded」；
    - 新增 `boundedRead(read, budget, what)`：以 min(pageRead, 剩餘預算) 約束導覽後的一次讀取，到期拋 `<what> exceeded its <ms> ms page read limit`（ETIMEDOUT）；呼叫端的 withPage 隨即以既有的有界收尾關閉 context，被放棄的讀取也一併結束，且其 rejection 已處理。
  - src/enhanced-content-extractor.ts：
    - **HTTP 總時間上限**：單頁 HTTP 以 `AbortSignal.any([呼叫預算, 操作計時])` 交給 axios，閒置 timeout 照舊。操作計時在區域變數；操作計時觸發而呼叫預算未中止時，改拋 `HTTP page read exceeded its <ms> ms operation limit`（ETIMEDOUT → timeout），照既有規則進 fallback。
    - **每頁視窗**：8 s 視窗改在該頁取得第一個 HTTP slot 時才開（extractContent 的 windowMs，由 extractContentForResults 傳入 pageTotal），涵蓋該頁的 HTTP 與 fallback；排隊只受整次預算約束。視窗到期的原因為 `page read window exceeded (<ms> ms)`。嘗試錯誤改用實際生效的預算原因，所以能和 Call deadline 區分。
    - page.title、page.content 與 text/plain 的 body innerText 都經 boundedRead。
    - 單頁工具（get-single-web-page-content）不帶 windowMs，行為不變。
  - src/search-engine.ts：Google、Bing 解析前的 page.content 經 boundedRead。連結解析沿用自己的 linkResolve。
  - **同一上限**：nominal 上限不小於剩餘預算時，不另設操作計時，由呼叫期限本身結束並說明原因。第一版沒有這條規則，既有的「35 ms 預算、伺服器不回應」案例因此不穩定：操作計時比呼叫期限早不到 1 ms 觸發，被當成操作逾時而進了 fallback。這是本步自己引入的問題，已在提交前以這條規則修正，連跑 5 次通過。
- **測試**（tests/test-browser-lifecycle.mjs，本機伺服器與 stub）：
  - 慢送：伺服器每 100 ms 送 1 byte，pageRequest 縮為 600 ms。讀取在 550–1500 ms 內結束，錯誤為 `HTTP page read exceeded its 600 ms operation limit`；讀取期間 HTTP slot 為 1，結束後 0；stub fallback 恰好 1 次。
  - 讀取卡住：pageRead 縮為 80 ms，經真實 BrowserPool（stub chromium）：
    - title()、content()、text/plain 的 innerText 各自永不返回 → 1 s 內 timeout，錯誤為 `<what> exceeded its 80 ms page read limit`，context 關閉 1 次；
    - Google、Bing 結果頁的 content() 永不返回 → 方法以 `<engine> results page.content() exceeded its 80 ms page read limit` 拒絕，context 關閉。
  - 每頁視窗：pageTotal 縮為 400 ms。
    - 10 頁、每頁 HTTP 200 ms、2 個 slot：10 頁全部 text；
    - HTTP 250 ms 回空、fallback 250 ms：該頁 timeout，錯誤為 `page read window exceeded (400 ms)`，HTTP 那次嘗試沒有錯誤。
  - 既有的 selector 卡住、短期限、取消後不 fallback 等案例全部通過。
- **檢查**（vendor 目錄，沙箱內）：
  - `npm run build` exit 0；retention 26/26、content-contract 5 組、browser-lifecycle（連跑 5 次）全部 exit 0。
  - 判別力（958ce37 的乾淨重建，在 `$TMPDIR` 複本中把測試切成三段執行）：
    - 慢送讀取跑到整次預算 5001 ms，結束後 HTTP slot 仍占用（AF19 重現）；
    - 去掉慢送段後，卡住的 page.title() 超過 1 s（AF20 重現）；
    - 只留視窗段時，10 頁中排在後面的頁面為 timeout（AF21 重現）。
- **下一步**：F4-S2。

### F4-S2 自有 Chromium 辨識與有界收尾
- **改動**（FG3；AF22、AF34；突變 N28、N29；FA10）：src/browser-pool.ts。
  - 新增 identity(pid)：stat 從最後一個「)」之後解析，取 pgid 與 starttime；owner flag 在 cmdline 以 NUL 或空白切分後比對。讀不到或欄位不合就回 undefined。
  - rememberBrowserProcesses 與 killOwnedBrowsers 共用它。只記錄帶 flag 且 pgid 等於 pid 的直接子程序；kill 前要求 starttime 一致、pgid 等於 pid、仍帶 flag。讀不到或身分不符一律不 kill。
- **測試**（tests/test-browser-lifecycle.mjs，真實子程序，不需 Chromium）：
  - 以 `process.execPath -e` 加 detached 產生三個直接子程序，各自設定 process.title：
    - 帶 owner flag 的 `a) b c d --web-search-owner=<pid>`：情境本身也有斷言，cmdline 只剩 1 個字串，comm 為 `a) b c d --web-`；
    - 不帶 flag 的 `a) b c d unrelated`；
    - 另一個帶 flag 的。
  - 經 stub chromium launch 後，pool 認得帶 flag 者、不認不帶 flag 者。
  - 另一個 pool 把第三個子程序記成錯誤的 starttime，killOwnedBrowsers 不殺它。
  - browser.close 永不返回、cleanup 縮為 100 ms 時：closeAll 在 1 s 內返回（2 s 上限偵測卡住），close 只呼叫一次；兩個帶 flag 的群組以 SIGKILL 結束，不帶 flag 者存活。closeAll 會重新讀取身分，所以第三個子程序此時被正確視為自有程序。
  - finally 只清理自己產生的程序。連跑 5 次通過。
- **檢查**：
  - 沙箱內：`npm run build` exit 0；retention 26/26、content-contract 5 組、browser-lifecycle 全部 exit 0。
  - 突變與判別力（evidence/F4-S2/mutate.py、results.jsonl）：
    - N28（killOwnedBrowsers 不 kill）被殺死（帶 flag 的子程序沒有收到 SIGKILL）；
    - N29（boundedClose 不與時限競速）被殺死（closeAll 卡住，回 'hung'）；
    - 9f3867b 的乾淨重建失敗於「rewritten owner process recognised」（AF22 重現）。
  - 真實完整版 Chromium（沙箱外、短 TMPDIR、環境含 DBUS_SESSION_BUS_ADDRESS；同一個 evidence/F3-S1/full-chromium.mjs → evidence/F4-S2/full-chromium-owned.json）：browser 根程序的 cmdline 仍只有 1 個 NUL 欄位，但 poolOwned 已記錄該 pid（exe 在 chromium-1181/，pgid=pid，starttime 相符）；收尾後沒有存活程序。F3-S1 時同一腳本的 poolOwned 是空的。
- **F4 階段結論**：FG3 的四項（HTTP 總時間、讀取上限、每頁視窗、自有 Chromium 辨識與有界收尾）都有離線與本機證據；真實 Agent 入口的觀測留給 F7-S2。
- **下一步**：F5-S1。

### F5-S0 BrowserPool 的開始通知（執行中新增的步驟）
- **新增原因**：F5-S1（引擎 attempts）與 F5-S2（瀏覽器 fallback 在取得 page 之前失敗也要計數）都要用 FA07 的「開始」定義。這個時點只有 BrowserPool.withPage 知道，但兩步都已各有 3 個 production 檔，所以把介面獨立成一步。phase-5 已補上本步的說明。
- **改動**：src/browser-pool.ts 的 withPage 新增可選的第三個參數 onStart。取得 page slot 並通過 `budget.remaining()` 之後、getBrowser 與建立 context 之前呼叫一次；在佇列中逾期的 lease 不呼叫。既有呼叫端不受影響。
- **測試**：tests/test-browser-lifecycle.mjs：launch 失敗時 onStart 為 1 次；兩個 slot 被占住時，第三個 lease 在 30 ms 期限內逾期，onStart 為 0 次。
- **檢查**（vendor 目錄，沙箱內）：`npm run build` exit 0；browser-lifecycle 連跑 3 次 exit 0；retention 26/26、content-contract 5 組 exit 0。
- **下一步**：F5-S1。

### F5-S1 引擎執行事實
- **改動**（FG4；AF11、AF12、AF13、AF32、AF37；突變 N02b、N02c、N02d、N02g、N03b）：
  - src/types.ts：SearchEngineState 新增 not_attempted 狀態、reason（deadline／cancelled／rate_limited／queue_expired）、httpStatus 與 finalPath；attempted 改為「已有 page lease 開始」。
  - src/search-engine.ts：
    - 引擎初始為 not_attempted。前面引擎已達 limit 才標 strategy_stopped。
    - 迴圈開始一個引擎前若預算已到，標 not_attempted／deadline。
    - 方法在取得 page slot 之前就因預算中止 → not_attempted／queue_expired；取消一律為 cancelled。
    - rate limiter 拒絕 → rate_limited；在 rate limiter 佇列中逾期 → queue_expired；進入時就已逾期 → deadline。原本的錯誤文字保留在 error。
    - attempts 由 F5-S0 的 onStart 計數，移除 `Math.max(1, …)`。
    - Google 與 Bing 記錄搜尋導覽的 HTTP status；Google 被導到 `/sorry/` 時另記 finalPath。
  - src/utils.ts：
    - 引擎行在 `status=` 之後依序加 `reason=`、`http_status=`、`final_path=`，error 維持在最後；
    - 零候選時分四句：全部失敗、全部零解析、沒有引擎嘗試（附原因）、混合；
    - strategy_stopped 與 not_attempted 的引擎都列出，合併來源照舊全列。
  - 逐筆加入的 limit 防護不變（F3-S3 的 fill），本步補上測試。
- **測試**（retention，31 項）：
  - engineWith 與期限案例的 stub 改為自己記錄已開始的嘗試（phase-5 列出的預期更新）；期限案例另斷言 Bing 為 not_attempted／deadline／attempts=0。
  - 新增：
    - 四種零候選的文字互不相同，且各含對應句子；
    - 引擎行含 error、含 strategy_stopped 的 Bing、含 reason=deadline，合併來源列出 `Google, Bing`；
    - 經 fake browser 的真實方法：零解析時 `http_status=200`；Google 429 時 `http_status=429`；`/sorry/` 時 `http_status=200; final_path=/sorry/index`；
    - rate limit 拒絕、rate limiter 佇列逾期、page slot 佇列逾期三種情形的原因、attempts=0，以及標題不是「No candidates parsed」；
    - limit 5、Google 2 筆加 Bing 4 筆 → 恰為 5 筆。
- **檢查**（vendor 目錄，沙箱內）：
  - `npm run build` exit 0；retention 31/31、content-contract 5 組、browser-lifecycle 全部 exit 0。
  - 突變（evidence/F5-S1/mutate.py、results.jsonl）：N02b、N02c、N02d、N02g、N03b 全部被 retention 殺死。
  - 判別力：0f2f25d 的乾淨重建跑新的 retention，5 項失敗（evidence/F5-S1/previous-build-0f2f25d.txt）。
- **下一步**：F5-S2。

### F5-S2 頁面讀取事實與統計口徑
- **改動**（FG4；AF16、AF17、AF18；突變 N20b）：
  - src/types.ts：
    - 新增 PageReadAttempt：status（HTTP）、outcome、contentType、finalUrl、encoding、renderWaitMs、originalLength、returnedLength、truncated、error；
    - PageRead.attempts 只收已開始的嘗試；
    - 新增 notStarted（只在佇列中等待、從未開始的 fallback 及其原因）。
  - src/enhanced-content-extractor.ts：
    - **每次嘗試用新紀錄**：嘗試在 started() 時才清空摘要欄位（HTTP status、Content-Type、final URL、標題、編碼、錯誤、長度、truncated、狀態）並加入清單；結束時以 record() 把該次事實寫進自己的紀錄。摘要因此一律是最後一次已開始的嘗試，不沿用前一次的欄位（AF16）；HTTP 的事實在 fallback 之後仍留在清單（AF17）。
    - **瀏覽器開始**：瀏覽器嘗試改經 withPage 的 onStart 開始（F5-S0），launch 或 context 失敗也計數並列出原因（AF17）。在佇列中逾期的 fallback 不計數，摘要維持 HTTP 那次，原因寫入 notStarted。
    - 晚渲染等待的毫秒數改記在該次紀錄的 renderWaitMs；沒有文字時的說明仍寫在 Read error。
    - **targetCount**：extractContentForResults 保留 targetCount。超過的候選原樣保留、不讀（以前會被 slice 掉，R05）。
  - src/utils.ts：
    - formatPageRead 的每次嘗試行以 `status=<HTTP>` 開頭，之後依序列出 read_status、content_type、final_url、encoding、render_wait_ms、markdown_length、truncated，error 在最後；notStarted 顯示為 `- browser: not started (<原因>)`。
    - formatSearchResponse 移除恆為 0 的 transport_retries，Read statistics 之後加一行 `Statistics scope: …`，說明 source_read_attempts、candidates_attempted、redirect 不另計、parsed_count 與 engine_redirects 的口徑（FA08、AF18）。
- **測試**：
  - content-contract 新增一組：
    - HTTP 空文字後 browser 失敗：摘要沒有 HTTP 的長度與 status，兩次嘗試各帶自己的事實，也沒有 Markdown length 行；
    - HTTP 403 後 browser 為空：摘要沒有 Read error，403 留在 http 那次的紀錄；
    - 真實 BrowserPool 的 launch 失敗：browser 嘗試被計數、帶 launch 錯誤，source_read_attempts=2；
    - 兩個 page slot 被占住時 fallback 在佇列中逾期：attempts 只有 http，notStarted 為 `Call deadline exceeded` 且看得到；
    - targetCount=2、5 個候選：只讀前 2 個，回傳全部 5 個，其餘為 not_attempted，統計等於 spy 計數；
    - 統計行沒有 transport_retries，且有口徑說明。
  - 預期更新：既有統計 regex 去掉 transport_retries；所有 fake pool 的 withPage 改為呼叫 onStart；F1-S2 的晚渲染斷言改為新的嘗試行格式。
- **檢查**（vendor 目錄，沙箱內）：
  - `npm run build` exit 0；retention 31/31、content-contract 6 組、browser-lifecycle 全部 exit 0。
  - 突變 N20b（忽略 targetCount）被 content-contract 殺死（evidence/F5-S2/mutations.jsonl）。
  - 11514e4 的乾淨重建跑新的 content-contract，失敗於更新後的統計斷言。
- **下一步**：F5-S3。

### F5-S3 工具入口一致性與文案
- **改動**（FG4；AF14、AF15）：
  - src/utils.ts：新增 validateSearchQuery（query 去空白後不可為空、limit 1–10），validateSearchInput 改為以它為基礎。
  - src/index.ts：
    - get-web-search-summaries 的 handler 改用 validateSearchQuery，純空白 query 也會被拒（AF14）；
    - 移除 full-web-search query 描述的「recommended for comprehensive research」（AF15）；
    - summaries 的描述改為 `Search the web and return search result titles, URLs and snippets without reading the linked pages.`，去掉「extract full page content」與「lightweight alternative」字樣；
    - 兩段註冊註解改寫，不再寫「comprehensive」；
    - 三個工具的 Citation 分流句逐字不變。逐一檢查三個工具與其參數的描述，沒有承諾完整全文、已驗證摘要、來源品質或研究支持。
- **limit 驗證位置（供 F6-S3 判定 N14j）**：兩個搜尋工具的 limit 都在兩處驗證。
  - schema：`z.union(...).transform(val => parseInteger(val, 'limit', 1, 10))`；
  - handler：full-web-search 經 validateSearchInput，summaries 直接用 validateSearchQuery，兩者都呼叫 `parseInteger(..., 'limit', 1, 10)`。
  - 所以 N14j（移除 summaries 的 schema transform）對外行為等效：handler 仍會拒絕無效 limit。
- **測試**：retention 的入口靜態斷言加入：
  - full-web-search 用 `validateSearchInput(args)`，summaries 用 `validateSearchQuery(args)`；
  - index.ts 不含 comprehensive、complete information、full page content、verified summar、high-quality source；
  - Citation 分流句恰好 3 處；
  - validateSearchQuery 拒絕空字串與純空白 query，以及 limit 11，並接受字串 limit '3'。
  - 實際的 handler 行為由 F6-S1 的入口測試驗證。
- **檢查**（vendor 目錄，沙箱內）：`npm run build` exit 0；retention 31/31、content-contract 6 組、browser-lifecycle 全部 exit 0。
- **F5 階段結論**：FG4 的引擎事實、頁面事實、統計口徑與入口一致性都有離線證據；README 口徑由 F7-S1 同步。
- **下一步**：F6-S1。

### F6-S1 Server 入口測試
- **新檔**：
  - tests/fixtures/stub-engines.mjs：測試專用 preload，以 `node --import` 載入；dist 位置由 `process.argv[1]` 推得，所以複本也適用。
    - Google（3 筆）與 Bing（1 筆）方法換成回傳本機直接網址，記錄呼叫並經 admit 接納；
    - 包裝 BrowserPool.prototype.closeAll（可延遲）與 CallBudget.prototype.abort 並記錄；
    - chromium.launch 先記錄 channel 與 headless，預設拋例外，STUB_FAKE_BROWSER=1 時回傳 version 777.0.0.0 的 fake browser，並記錄 newContext 的 UA；
    - 封鎖非 loopback 連線；以 JSON lines 寫入 STUB_LOG。
    - 設定只用測試的 STUB_* 變數，不是產品設定。
  - tests/test-server-entry.mjs：經真實的 dist/index.js，7 組：
    1. 呼叫類（SDK 1.15 client，command 為 process.execPath）：
       - includeContent=false 時本機頁面請求 0 次，4 筆都是 not_attempted；true 時同樣的 URL 與順序、讀 4 次（AF29、N13、N14f）；
       - summaries 頁面請求 0 次，limit=2 恰為 2 筆，兩工具都有引擎行（N13b、N14g、N14h、N14i）；
       - limit 11（兩工具）與純空白 query（summaries）都失敗，且引擎沒有被呼叫（AF14）；
       - 單頁 maxContentLength=7 → returned=7（N14d）；
       - tools/list 三個工具的描述與參數說明不含承諾性字樣，且都含 citation 分流句（AF39 Node 部分）；
       - handler 期間不呼叫 closeAll，shutdown 時恰好一次（N12、N11e）。
    2. 部署值 MAX_CONTENT_LENGTH=9 且省略參數 → returned=9。
    3. 卡住的頁面：
       - `_meta.web_search_work_ms=300` 時 1 s 內回 timeout（N14、N14b）；
       - client 以 AbortSignal 取消後，伺服器端連線在 500 ms 內關閉（N14c）；
       - DEFAULT_TIMEOUT=2000 時在 800–1500 ms 之間返回（保留額度 1000 ms；N42 會接近 2000）。
    4. fake browser：BROWSER_HEADLESS=false 時 launch 為 `{channel: 'chromium', headless: false}`，未設定時 headless 為 true（N08h、FU02）；newContext 的 UA 含 `Chrome/777.0.0.0` 且不含 Headless（FU03）。
    5–6. 自行 spawn、以換行 JSON-RPC 收發：讀取卡住時關閉 stdin 或送 SIGTERM，preload 讓 closeAll 延遲 1500 ms。
       - 讀取連線在 300 ms 內關閉；
       - abort 早於 closeAll 返回；
       - 程序在 closeAll 之後以 0 結束（N11b、N11d、N11c）。
    7. DEFAULT_TIMEOUT=300001、MAX_CONTENT_LENGTH=0、BROWSER_HEADLESS=maybe 都在啟動時以非 0 結束（N43、N05d、N08i）。
- **修改**：app/tests/test_citation_skill_activation.py 新增 test_citation_runtime_keeps_the_web_search_boundary_once。載入的 citation runtime instructions 中，「Do not use Web Search or browse other websites to find papers」、「honestly report the returned failure, uncertainty, or missing information」與「This instruction applies even when Web Search tools remain available.」各恰好出現 1 次（AF39）。
- **檢查**：
  - vendor 目錄，沙箱內：`node tests/test-server-entry.mjs` 連跑 3 次 7/7 exit 0（約 13 s，不需 Chromium 與網路）；retention、content-contract、browser-lifecycle exit 0。
  - app 目錄，沙箱內，隔離：`pytest tests/test_citation_skill_activation.py tests/test_tool_access_matrix.py -q -p no:cacheprovider`：22 passed。
  - 判別力：在 `$TMPDIR` 複本刪掉 SKILL.md 的整段邊界文字後，新的 Python 測試失敗（1 failed, 15 passed）。
  - 各突變由 F6-S3 正式複驗。
- **下一步**：F6-S2。

### F6-S2 生命週期聚焦案例
- **改動**（FG6；AF29、AF33；突變 N16c、N09g、N26、N07c、N09b）：只改測試。
  - tests/test-browser-lifecycle.mjs 新增一組舊 P4-S2 聚焦案例（另加 waitUntil 輔助函式）：
    1. 導覽卡住：stub 的 goto／waitForSelector 只有帶 timeout 才會逾時，否則永不返回。操作上限縮為 50 ms、呼叫預算 2000 ms 時，下列各在 500 ms 內結束：
       - 頁面讀取的 goto（timeout，錯誤含 `Timeout 50ms exceeded`）；
       - Google 與 Bing 的 goto（拒絕）；
       - Google 與 Bing 的結果等待（回空批次）；
       - 連結解析導覽（timeout）。
    2. page 排隊逾期：MAX_CONCURRENT_PAGES=1，第一個 lease 占住 page，第二個以 50 ms 預算排隊，在 300 ms 內以 deadline 拒絕；釋放後它的回呼從未執行、newPage 只開過 1 次，pages 的 active／pending 歸零。
    3. 明確中止：本機伺服器卡住，預算 5000 ms 時呼叫 budget.abort()，socket 在 250 ms 內關閉，狀態 cancelled；http 與 pages 的 active／pending 都是 0。
    4. 子預算 dispose 後，父 signal 的 abort listener 數回到原值（以 events.getEventListeners 計）。
    5. 既有的最後一條斷言（沒有殘留 Timeout）照舊通過。
  - tests/test-content-contract.mjs：
    - class 或 id 含 nav、footer、comment、sidebar、menu、banner、cookie 的元素，文字全部保留；
    - 移除 includeContent=false 的恆真斷言（events 計數與 source_read_attempts=0），註解指向 test-server-entry 案例 1（AF29）。formatter 層級的 URL 一致斷言保留。
- **檢查**（vendor 目錄，沙箱內）：browser-lifecycle 連跑 3 次 exit 0；retention 31/31、content-contract 6 組、test-server-entry 7/7 exit 0。突變由 F6-S3 正式複驗。
- **下一步**：F6-S3。

### F6-S3 突變複驗
- **作法**（FG6；FA12；context/mutation-survivors.md 全部項目）：
  - evidence/F6-S3/run_mutations.py 以語意定義每個突變，用精確文字替換重建單點改動（每段原文必須恰好出現一次）。
  - 暫存複本在 repository 外（`$TMPDIR/f6s3`）：
    - Node 複本含 src、tests、package.json、tsconfig.json，node_modules 為 symlink，以複本自己的 tsc 編出 dist；
    - Python 複本含 app/agent、skills、rag、tests、pyproject.toml、poetry.toml，app/vendor 為 symlink，不含 app/desktop 與 app/store。
  - 每個突變前重建複本。對照組：Node 四份測試、Python focused pytest 都全綠。
  - 至少一個測試非 0 退出（含逾時）即為殺死；結果逐筆追加到 results.jsonl。整個過程沒有修改 repo 的 dist 或 production 檔（`git status` 只有本步的 evidence）。
  - 執行時間約 25 分鐘，沙箱內。
- **結果**（evidence/F6-S3/summary.md）：
  - 必殺 42 項全部被殺死：N02b、N02c、N02d、N02g、N03b、N05d、N06d、N07c、N07e、N07f、N08h、N08i、N09g、N11b、N11c、N11d、N11e、N12、N13、N13b、N14、N14b、N14c、N14d、N14f、N14g、N14h、N14i、N16c、N20b、N26、N28、N29、N42、N43、P07、P27、P13、P13c、P18、P18b、P26。
  - N14j（條件必殺）存活，判為**等效**：F5-S3 之後兩個搜尋工具的 limit 都在 schema transform 與 handler（validateSearchQuery）兩處驗證，移除 summaries 的 schema transform 後，handler 仍在任何引擎執行前拒絕 limit 11（test-server-entry 案例 3 在該突變上通過）。
  - 可選 3 項：
    - N09b 被殺死；
    - P07b 存活：測試回收的程序都自成 process group，只殺 PID 也會結束；
    - P07d 存活：只有 PID 重用時才有差別，無法穩定重現。
  - 不再適用 6 項：N04c、N15、N16b、N16e、N16f、N17，它們的程式已在 F3-S2 隨 DuckDuckGo、Brave 與 Bing 首頁流程刪除，理由逐項寫在 results.jsonl。
- **原因紀錄的修正**：runner 的 first_failure 是啟發式的「第一行像錯誤的輸出」。lifecycle 測試既有的注入失敗日誌（`Resource cleanup: Error: injected context close failure`）與 pytest 印出的原始碼行，讓 N16c、N26、N28、N29、N09b、N09g、P13c、P26 等的原因文字不準確，但判定（非 0 退出）不受影響。
  - 以 `--reasons` 模式只對這些 id 重跑一次，記錄真正失敗的斷言（reasons.jsonl），例如：
    - N16c：`page goto ended after 2005 ms`；
    - N29：`'hung' !== 'closed'`；
    - N09g：content-contract 的佇列案例 150 s 逾時；
    - N26：explicit-abort 案例 `condition not reached`（中止後 1 s 內 socket 沒有關閉，手動在複本中確認）。
  - results.jsonl 保留原始紀錄；N14j、P07b、P07d 的判定理由另以追加行記錄。
- **測試缺口**：沒有。必殺項全部被既有或本計劃新增的測試殺死，本步沒有新增測試。
- **下一步**：F7-S1。

### F7-S1 文件同步
- **改動**（FG7；AF40、AF18）：
  - README.md（root）：安裝步驟改為 `npx playwright install chromium`，移除 firefox（AF40）。
  - app/vendor/web-search-mcp/README.md：
    - 開頭與「與 upstream 的差異」改為 Google 主力、Bing 依語言市場備援、已移除 DuckDuckGo 與 Brave，並說明連結以實際導覽解析；
    - 新增完整版 Chromium 與一般 UA、自有程序辨識、Python 端只管 client 生命週期與 15 秒啟動上限；
    - 建置與檢查列出四份測試，並寫入短 TMPDIR 的前提；
    - 新增「正文讀取」（整頁、表格、區塊分隔、編碼、媒體、晚渲染、截斷）、「時間上限」（總時間上限、每頁視窗起算點、三種逾時原因）與「輸出中的狀態與統計」（引擎 status 與 not_attempted 原因、零候選四句、Link 行、每次嘗試行、Read statistics 口徑）。
    - 既有的設定表與政策段落保留，只把 BROWSER_HEADLESS 的「三條瀏覽器路徑」改為「所有瀏覽器路徑」，並註明引擎、瀏覽器模式、UA 與上限是具名常數、不是環境設定。沒有新增或改名任何設定。
- **檢查**：
  - `git ls-files '*.md'`（不含 harness/plans 與 note）中，Firefox、DuckDuckGo、Brave 只剩 vendor README 的「已移除 DuckDuckGo 與 Brave」一句；兩份測試裡的 firefox 只是「Firefox 絕不可啟動」的守護 stub。
  - README 的設定名稱與 src 實際讀取的 `process.env` 一致：MAX_CONTENT_LENGTH、DEFAULT_TIMEOUT、BROWSER_HEADLESS、MAX_CONCURRENT_PAGES、MAX_CONCURRENT_HTTP。
  - README 寫出的上限與 OPERATION_TIMEOUTS 一致（pageRequest 6000、pageRead 6000、searchRequest 4000、searchSelector 3000、linkResolve 6000、renderSettle 3000、pageTotal 8000）。
  - README 的 source_read_attempts、candidates_attempted、redirect 不另計、parsed_count、engine_redirects 定義與輸出中的 `Statistics scope:` 行逐項對應（AF18）。
  - `git diff --check` 乾淨。
- **下一步**：F7-S2（沙箱外，真實 Python→Node 入口）。

### F7-S2 真實 Python→Node 入口驗收（本機）
- **作法**（FG7；evidence/F7-S2/drive.py、preload.mjs、mcp_helper.py → results.json）：
  - **執行環境**：沙箱外，短暫存目錄 `mktemp -d /tmp/ws.XXXX`。XDG_CACHE_HOME 與 AGENT_LOG_DIR 指到該目錄；PATH 以 conda app 的 bin 優先。執行前 `npm run build`（dist 與 src 一致）。
  - **載入路徑**：與 Agent 相同，`agent.mcp.resolve_mcp_specs` 加 `load_mcp_tools_with_families`，預設載入 repo 的 dist。
  - **需要固定候選或假引擎的案例**（8、9、10），改用產品既有的 AGENT_MCP_WEB_SEARCH_COMMAND／ARGS：`node --import preload.mjs?<query> <dist>/index.js`。仍經過產品的 loader、wrapper 與環境 allowlist。preload 只由自己 URL 的 query string 設定，因為 allowlist 不會轉送測試變數；這點在 results.json 各案例的 note 註明。
  - 案例 9、10 不取代引擎方法，只把 F3-S2 的可覆寫搜尋網址與主機指向本機假引擎，所以真實的 Google、Bing 方法、解析器與連結解析都在真實完整版 Chromium 上執行。
  - 案例 13、14 的自訂 command 用 mcp_helper.py（hang_call、healthy）、`python -c 'sys.exit(3)'` 與 `/bin/sleep 120`。
  - 本機伺服器只綁 127.0.0.1，結束時關閉；假引擎以 `localhost:<port>` 為搜尋主機，目標在 `127.0.0.1:<port>`。
  - 每個案例在同一腳本內每 50 ms 取樣自己的後代程序（pid、pgid、starttime、comm），結束後 0.5 s 以 starttime 檢查存活；只終止自己記錄的程序。
- **結果**：driver exit 0，15 個案例全部通過，各案例都沒有存活程序。
  1. 巢狀表格 3 層與 20 層：每段文字恰好一次；20 層 387 ms（含 Node 啟動）。AF01、AF23。
  2. 多篇 article 加 aside/main：Intro、Story 1、Story 2、Related、Main、Tail 依原順序。AF02。
  3. Big5（`Character encoding: big5 (Content-Type charset)`）與 Shift_JIS（`shift_jis (meta charset)`）文字正確。AF06。
  4. 晚渲染（真實完整版 Chromium）：計時器 300 ms 與「導覽列先、fetch 300 ms 後主要內容」都是 text（約 1.6 s）；5000 ms 才插入者為 empty_text，附 `waiting 3001 ms … (limit 3000 ms)`。AF03。
  5. 經 browser fallback 回顯的 UA 為 `… Chrome/139.0.0.0 Safari/537.36`，不含 Headless。FU03。
  6. 慢送：HTTP 在 `HTTP page read exceeded its 6000 ms operation limit` 結束後進 fallback，瀏覽器 goto 6000 ms 逾時，共 12.6 s，遠低於 285 s。AF19。
  7. 媒體與下載：
     - 11 MiB PDF 為 unsupported_media，`HTTP status: 200; Content-Type: application/pdf`，錯誤附 10 MiB 讀取上限；
     - 11 MiB HTML 為 http_error，`response body exceeds 10 MiB read limit`；
     - HTTP 403 之後瀏覽器遇到 PDF，為 unsupported_media，保留 200 與 application/pdf，403 留在 http 那次的紀錄；
     - 錯誤都是單行。
     - **AF10(b) 依 phase-1 至此記為已修正。**
  8. full-web-search（stub 候選），limit 10、每頁 2 s：10 頁全部 text，沒有視窗逾時，10.6 s。`source_read_attempts=10; http_attempts=10; browser_attempts=0` 等於伺服器實際收到的 10 次讀取；Google completed、Bing strategy_stopped；有口徑說明行。AF11、AF18、AF21。
  9. 引擎備援（真實方法、假引擎）：
     - 假 Google 429 → `status=error; http_status=429`，由 Bing 補足 3 筆；
     - 導到 `/sorry/` → `http_status=200; final_path=/sorry/index`，同樣由 Bing 補足；
     - 中文查詢送出 hl=zh-TW、setlang=zh-Hant、cc=TW，英文為 en、en、US。FU01、FA13。
  10. 連結解析（真實完整版 Chromium，linkResolve 縮為 2000 ms）：
      - Google 相對 `/goto` 的 JavaScript 跳轉 14 ms、302 到 PDF 5 ms，Bing 絕對包裝 302 到永不回應的目標 4 ms、302 到一般目標 4 ms，全部 resolved；
      - 不跳轉的包裝在上限記為 stayed_on_engine_host，候選保留；
      - 正文讀取的請求都打到解析後的網址，只有 stayed 那筆讀自己的包裝網址；
      - 統計 `engine_redirects_resolved=4; engine_redirects_unresolved=1`。FU04、X13。
  11. 主機上有 comm 為 `a) b c d` 的程序時，discovery（364 ms、無診斷）與呼叫都正常。AF24。
  12. 有真實 Chromium 時呼叫端取消：取消時 chrome 程序正在執行，取消後沒有「never retrieved」，沒有存活程序。AF25。
  13. 預算與診斷：
      - 卡住的自訂 server（DEFAULT_TIMEOUT=3000）在 2503 ms 以 `… (…; DEFAULT_TIMEOUT=3000 ms)` 的 TimeoutError 返回；
      - 立即結束的自訂 command，診斷為 `… [causes: McpError: Connection closed]; stderr log: <scratch>/cache/agent-mcp/web_search.stderr.log`。AF26、AF28。
  14. 啟動上限（實際常數 15000 ms）：啟動後卡住的 web_search 在 14523 ms 放棄，診斷含 `startup timeout (15000 ms)` 與 log 位置，另一個 MCP server 的 local_probe 照常載入。FU05。
  15. 約 1 MiB、大量未閉合 `[` 的 text/plain：386 ms 返回 text，`returned=10000; original=1048581`。AF09。
- **限制**：
  - 本步只用本機頁面與假引擎，真實 Google／Bing 由 F7-S3 觀測；
  - driver 的 stderr 有本機伺服器在客戶端中途斷線時的 BrokenPipeError，屬於測試伺服器本身，與產品無關。
- **下一步**：F7-S3（公開請求，最多六組、八分鐘）。

### F7-S3 公開引擎觀測
- **作法**（FG7、FG9；AF41）：
  - evidence/F7-S3/observe.py 依序執行組別，每組前後各在 groups.jsonl 追加 start／end 紀錄；
  - 預算六組、八分鐘；各組 DEFAULT_TIMEOUT 60000–90000 ms；
  - observe.mjs 包住兩個解析器，記錄同一份結果頁的結構計數，不另發請求；
  - 第 1–3、5 組經 Python 入口（產品自訂 command 加 observe.mjs，產品的 loader、wrapper 與 allowlist）；第 4、6 組經 dist adapter，不等同 Python 全鏈路；
  - 沙箱外執行。
  - 正式執行前，以本機假引擎乾跑 group4.mjs 與 observe.mjs（不連網）：包裝可解開，結構計數正確，preload 可正常啟動與結束。
- **結果**（evidence/F7-S3/README.md、groups.jsonl）：六組用完，組別時間合計 23.0 s。
  - **Google**：4 次搜尋都是 200、`/search`，沒有 429 或 `/sorry/`，連結解析之後的下一次搜尋也沒有被擋。結構計數等於解析數（5/5、5/5、4/4、9/9），包裝解開 23/23（100%，25–90 ms）。
  - **正文**：第 1 組 4/5 讀自目標頁；Stack Overflow 兩條路徑都是 Cloudflare 403。第 3 組讀 docs.python.org，utf-8（meta），交付 10000／71104 code points。
  - **Bing**：
    - 第 4、5 組為 200，`#b_results` 存在但沒有 `li.b_algo`，依規則記為零結果事實；
    - 第 5 組 Google 只有 9 < 10，策略 B 確實呼叫了 Bing，但沒有補到候選；
    - 第 6 組（只送 Bing）有 10 個 `li.b_algo`、解析 10，但標題全是「test」相關，與查詢無關。
    - 中文市場沒有被觀測到（第 2 組 Google 已補滿）；Bing 包裝的真實解析沒有被觀測到。
- **FG9 判定**：沒有被擋，沒有轉接器缺陷，沒有需要新增的 F3 修正步驟。
  - 真實 Google 的引擎、完整版 Chromium、一般 UA、連結解析：**已驗證**。
  - 真實 Bing 的備援已執行但沒有提供候選；Bing 包裝的真實解析：**未觀測**，只有本機證據（F3-S3、F7-S2 案例 10）。
- **偏離（如實記錄）**：PLANS 要求 Google 兩次請求至少間隔 10 秒。腳本以「組別開始」間隔 10 秒控制，但實際送出搜尋的時點隨程序啟動而變。以結果頁的解析時點計算：
  - 第 1→2 組 9.9 s、第 2→4 組 8.7 s，未達 10 秒；第 4→5 組 69.7 s；
  - 第 2、4 組的開始紀錄只差 9.3 s，低於 sleep 應保證的 10 s，原因未查明（可能是 WSL 時鐘調整）。
  - Google 沒有被擋，但這條規則沒有達成。不重做，因為六組預算已用完。
- **另作的補充組別**：第 5、6 組依 phase-7「預算尚有剩餘時」的用途，用於觀察 Bing 補足與 Bing 的實際結構；目的與查詢都寫在 groups.jsonl 與 README。
- **下一步**：F7-S4（完整 suite、對帳與結案）。
