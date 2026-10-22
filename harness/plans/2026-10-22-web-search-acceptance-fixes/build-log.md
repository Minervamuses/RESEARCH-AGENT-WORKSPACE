# 執行狀態與證據
本文件是唯一的動態狀態擁有者。規劃與驗收的觀察不代表修正已完成；實際結果見下方各步驟事件。每個改動步驟的 commit，都必須同時更新本表與事件紀錄。狀態只用 Not started、In progress、Blocked、Complete。

## 階段狀態
建議的步驟順序：F1-S1 → F1-S2 → F2-S1 → F1-S3 → F1-S4 → F2-S2 → F3 → F4 → F5 → F6（見 PLANS）。
| 階段 | 狀態 | 已完成步驟 | 實際證據 | 阻塞 | 下一動作 |
| --- | --- | --- | --- | --- | --- |
| F1 | Not started | — | — | — | F1-S1 |
| F2 | Not started | — | — | — | F2-S1（F1-S2 之後） |
| F3 | Not started | — | — | 相依 F1 | — |
| F4 | Not started | — | — | 相依 F3 | — |
| F5 | Not started | — | — | 相依 F2、F4 | — |
| F6 | Not started | — | — | 相依 F5 | — |

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
