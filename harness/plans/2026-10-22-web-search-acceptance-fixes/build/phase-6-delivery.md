# F6：文件、真實入口驗收與交付
依據：[目標 FG7、FG8 與 FA11](../GOALS.md)、[執行契約與檢查成本](../PLANS.md)、[驗收發現](../context/acceptance-findings.md)。相依：F5。涵蓋 FG7、FG8；AF23、AF40–AF44，以及所有 AF 的最終對帳。

本階段所有真實入口、Chromium、公開網路與殘留程序的檢查，都依 PLANS「宿主沙箱與執行環境」在沙箱外執行，並套用暫存與日誌隔離。

## 後置條件
- 文件與修正後的行為一致。
- 實際主 Agent 使用的 Python→wrapper→dist 路徑，逐項重現 F1–F4 的修正。
- 公開引擎在 P2-S3 與本計劃的修改之後，至少重新觀測一次。
- 完整 suite 通過。
- 每個 AF 都有最終處置與證據路徑。
- 一次統一彙報。

## F6-S1：文件同步
- **修改**：README.md（root）、app/vendor/web-search-mcp/README.md。文件不計入 production 檔數。

工作：
1. 刪除 root README 安裝步驟中的 `firefox`，只保留 `npx playwright install chromium`（AF40）。
2. vendor README 在既有段落中增補以下內容：
   - 正文轉換政策：整頁、表格、編碼判定；
   - 瀏覽器讀取的晚渲染等待與上限；
   - 局部上限都是總時間上限，每頁視窗的起算點；
   - 引擎狀態與未嘗試原因的意義；
   - Read statistics 的口徑（FA08）。
3. 不全面改寫文件；不新增或改名環境設定。

檢查：
- 以 grep 確認 repo 內現行說明文件不再指示安裝 Firefox；舊計劃目錄與 context 快照中的歷史描述不在此限。
- README 中的設定名稱與 src 實際讀取的一致。
- README 寫出 source_read_attempts、candidates_attempted 的定義，以及 redirect 不另計；輸出中的口徑說明行與 README 一致（AF18）。

記錄後 commit：`docs(web-search): describe conversion, waits and statistics [F6-S1]`。

## F6-S2：真實 Python→Node 入口驗收（本機）
- **證據**：evidence/F6-S2/，含驅動腳本、結果 JSON 與程序取證。

作法：
- 經 agent.mcp 的 resolve_mcp_specs 與 load_mcp_tools_with_families（與 Agent 相同的路徑），載入實際 build 出的 dist。
- 需要固定候選的案例，以既有的 AGENT_MCP_WEB_SEARCH_COMMAND／ARGS 自訂啟動：`node --import <evidence 內 stub preload 的 file URL> <dist/index.js>`。這仍然經過產品的 loader、wrapper 與環境 allowlist，但必須在證據中註明。
  - web_search 的環境只會帶 allowlist 內的設定，所以 preload 的設定（本機伺服器位址、候選）不能用環境變數傳入。改用 preload file URL 的 query string、ARGS 中的參數，或每個案例一個 wrapper script。
- 單頁工具直接讀本機頁面。
- 本機 HTTP 伺服器只綁 127.0.0.1，結束時關閉。
- 每個案例都在同一腳本內做程序取證，只清理自己記錄的程序。

最少案例：
1. 巢狀表格 3 層與 20 層：文字各出現一次；20 層的耗時記錄下來，作為線性證據（AF01、AF23）。
2. 多個 article 加上 aside/main 的頁面：全部文字依原順序出現（AF02）。
3. Big5（header charset）與 Shift_JIS（meta）頁面：文字正確，編碼來源可見（AF06）。
4. 晚渲染（真實 Chromium，HTTP 回空文字以觸發 fallback）：
   - 計時器 300 ms；
   - DOMContentLoaded 時有導覽列、主要內容經 fetch 300 ms 才插入；
   - 5000 ms 才插入（超過上限，應回 empty_text 並附等待時間）（AF03）。
5. 單頁 HTTP 慢送：在操作上限附近結束並進 fallback，總耗時記錄下來，不得接近 285 s（AF19）。
6. 媒體與下載：
   - 約 11 MiB 的 PDF 與 HTML；
   - HTTP 403 之後，瀏覽器遇到 PDF 下載。

   狀態與已知標頭正確，錯誤訊息為單行。下載案例通過後，才把 AF10(b) 記為已修正；若 Chromium 在下載時不發出回應事件，記錄實際得到的事實（AF10）。
7. full-web-search（stub 候選），limit=10、每頁約 2 s：全部讀到；引擎狀態、口徑說明與統計數字等於伺服器觀察到的事件（AF11、AF18、AF21）。
8. 主機上有名為 `a) b c d` 的程序時，discovery 與呼叫都正常（AF24）。
9. 有真實 Chromium 時，呼叫端取消：沒有「never retrieved」日誌，也沒有殘留（AF25）。
10. 逾時訊息含預算；自訂 command 立即結束時，診斷含葉例外與 log 路徑（AF26、AF28）。
11. 約 1 MB 的對抗性 text/plain（大量未閉合 `[`）：在線性時間內返回，耗時記錄下來（AF09）。

記錄結果，任一失敗都依執行契約處理，回到所屬階段補一個修正步驟。commit：`test(web-search): record real entry behaviour after fixes [F6-S2]`。

## F6-S3：公開引擎觀測
- **預算**：最多六組、累計八分鐘。
- **證據**：evidence/F6-S3/。
- **防止重複請求**：每組開始前，先把組號、查詢與開始時間追加到 evidence/F6-S3/groups.jsonl；結束後追加耗時與結果。中斷後依這份紀錄計算剩餘預算，不重複已發出的組。

案例依 U01，在執行當日自選，不預設網站；查詢與選擇理由記錄在證據中，不寫入產品規則：
1. **full-web-search**（Python 入口）：一般技術問題，limit 5，includeContent true，maxContentLength 1500。
2. **get-web-search-summaries**（Python 入口）：時事類查詢，limit 5。
3. **get-single-web-page-content**（Python 入口）：從前兩組結果中，選一個實際目的頁（不是 bing.com/ck/a）。若沒有符合的候選，改由執行者自選一個穩定的公開頁面並記錄理由；仍無法取得時，記為未驗證，不算失敗。
4. **三個引擎各自的可用性**：經 dist adapter 觀測，必須註明這不等同 Python 全鏈路。記錄 HTTP status、parsed 數、標題、snippet、URL 是否齊全，以及是否使用 Chromium。
5. **第 5、6 組**：只在預算尚有剩餘時使用，用於重試一次環境失敗的組別，或觀察 Bing 不足額時的多引擎補足。

記錄下列事實：
- 各引擎狀態；
- Bing 候選中 ck/a 中介頁所占的比例；
- DDG 零解析時的已知事實；
- Brave 的 status；
- 是否實際發生多引擎補足。

不把搜尋相關性當成缺陷。若引擎的失敗屬於引擎自身（HTTP 狀態、挑戰頁、解析），如實記錄，不停用引擎（停用需另經決策）。環境失敗依 PLANS 歸類。

外部頁面每頁只保存 ≤2000 code points 的摘錄，以 JSON 字串保存，避免尾端空白讓 `git diff --cached --check` 失敗；不保存 cookie 或 nonce。commit：`test(web-search): record public engine observations [F6-S3]`。

## F6-S4：完整 suite、對帳與結案
1. **最終程式改動穩定後的檢查**：
   - 四份 Node 測試；
   - 兩組 focused pytest；
   - 在沙箱外以 timeout 600 執行完整 suite。發現 regression 或環境設定錯誤並修正後可再跑一次，全計劃最多兩次。
   - 在跑完整 suite 的同一條命令中，前後比對 app/store 的 metadata 指紋，只讀 path、type、size、mtime、mode，不讀內容。
2. **Git 檢查**：
   - 分支仍為 GUI，沒有 push。
   - 以 `git log --grep='\[FA0\]' -1 --format=%H` 找到撰寫 commit，對它之後的全部 diff 執行 `git diff --check`。
   - 變更檔案都是 LF。
   - 沒有依賴、lock、環境定義或 AGENTS.md 變更，舊計劃目錄也沒有改動。
   - 列出 .gitignore 涵蓋而未提交的修改，例如 dist，以及未以 -f 提交的 phase 檔修訂。
3. **最終對帳**：在 build-log 寫入每個 AF 的處置表，欄位為結果、證據路徑與 commit 步驟；以及突變複驗的彙總。結果分為：已修正、隔離並說明、環境阻塞未驗證。
4. 若有可用的計劃結構檢查工具，執行並記錄；沒有就人工核對 index、相依與連結。
5. **最終彙報（一次）**：
   - 已完成的行為與檔案；
   - 實際執行的測試與失敗；
   - 公開觀測的事實；
   - 未驗證項與恢復條件；
   - commit 對照；
   - OD1–OD3 這三項待使用者決策；
   - 最多三個具體的後續選項。

   明說沒有 push、沒有建立或切換 branch、執行中沒有停下要求授權或 review。

commit：`docs(plan): close web search acceptance fixes [F6-S4]`。
