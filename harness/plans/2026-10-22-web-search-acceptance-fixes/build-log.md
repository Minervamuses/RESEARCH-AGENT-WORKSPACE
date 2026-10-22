# 執行狀態與證據
本文件是唯一的動態狀態擁有者。規劃與驗收的觀察不代表修正已完成；實際結果見下方各步驟事件。每一步都強制 commit（見 PLANS 執行契約第 4 項），每個 commit 都必須同時更新本表與事件紀錄。狀態只用 Not started、In progress、Blocked、Complete。

## 階段狀態
建議的步驟順序：F1-S1 → F1-S2 → F2-S1 → F3-S1 → F3-S2 → F3-S3 → F3-S4 → F1-S3 → F1-S4 → F2-S2 → F2-S3 → F4 → F5 → F6 → F7（見 PLANS）。
| 階段 | 狀態 | 已完成步驟 | 實際證據 | 阻塞 | 下一動作 |
| --- | --- | --- | --- | --- | --- |
| F1 | In progress | F1-S1 | evidence/F1-S1/ | — | F1-S2 |
| F2 | Not started | — | — | — | F2-S1（F1-S2 之後） |
| F3 | Not started | — | — | — | F3-S1（F2-S1 之後） |
| F4 | Not started | — | — | 相依 F1、F3 | — |
| F5 | Not started | — | — | 相依 F4 | — |
| F6 | Not started | — | — | 相依 F2、F5 | — |
| F7 | Not started | — | — | 相依 F6 | — |

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
