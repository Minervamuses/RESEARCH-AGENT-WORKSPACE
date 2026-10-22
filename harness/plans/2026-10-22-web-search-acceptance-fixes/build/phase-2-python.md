# F2：Python 包裝穩健性
依據：[目標 FG5、FG6 與 FA09](../GOALS.md)、[執行契約](../PLANS.md)、[驗收發現](../context/acceptance-findings.md)。相依：無，與 F1 互不相依；建議順序見 PLANS。涵蓋 FG5、FG6、FG8；AF24–AF28、AF31（Python 部分）、AF35、AF36、AF38，突變 P07、P13、P13c、P18、P18b、P26、P27；以及 FU05 的啟動上限。

## 後置條件
- web_search 的 Python 包裝在任何主機程序組合下都能正確追蹤並回收本次呼叫自有的程序樹。
- 觀察者的錯誤不會取代已收到的結果。
- 呼叫端取消時，不留下未取回的例外。
- 逾時、期限後才到的回應、載入失敗，都有可讀且如實的訊息。
- 新增的真實程序測試與執行順序無關。
- web_search 啟動以 15 秒為上限，卡住時不拖住整個 session（FU05）。

五分鐘總上限、285/15 切分、環境 allowlist 與既有隔離行為都不變。

## F2-S1：/proc 解析與程序樹回收
- **production 檔**：app/agent/mcp.py。
- **處理**：AF24、AF35、P07、P27；P07b、P07d 可選。

工作：
1. remember_processes 與 kill_owned 共用一個 stat 解析輔助函式：
   - 取最後一個「)」之後的欄位；
   - 所有 int 轉換與索引都在 try 之內；
   - 解析不了的列直接略過。
2. observe 迴圈中的非預期例外只記錄一次 warning，迴圈繼續運作。
3. `finally` 收尾時，觀察者的例外不得取代已發布的結果，也不得取代原本的例外。
4. 不改變身分判定的規則：直接子程序必須帶呼叫標記，starttime 必須一致，群組 kill 只在 pgid 等於 pid 時才做。
5. 不改變收尾的觸發時機。現行設計只在期限到時才強制收尾；快速失敗路徑上的孤兒程序回收不在本次範圍（acceptance-findings X14）。

最少檢查（tests/test_mcp.py，沿用既有 lifecycle server 寫法）：
- **怪名程序**：把 /bin/sleep 複製到 tmp_path 下，命名為 `a) b c d` 並執行。在它存活期間，discovery 能載入工具，呼叫能回傳 known result。測試在 finally 中只終止自己啟動的 sleeper。
- **觀察者故障**：以 monkeypatch 讓 stat 解析輔助函式在第一次呼叫時拋例外。已發布的結果仍被回傳，並記錄一次 warning。
- **孫程序回收**：lifecycle server 新增一種模式，server 本身保持卡住、不回應工具呼叫。它先產生一個中介子程序；中介子程序再以 setsid 產生忽略 SIGTERM 的孫程序，把 pid 與 starttime 寫入檔案，約 150 ms 後自行結束。呼叫因逾時進入收尾時：
  - 孫程序必須已被收尾；
  - 移除後代展開（P07）時，孫程序會存活；
  - 移除週期性觀察（P27）時，孫程序也會存活，因為中介子程序結束後，孫程序已不在 server 的後代樹中。

  存活與否用 starttime 確認身分；測試結束時只清理自己記錄的程序。
- 既有的 test_mcp 全部仍然通過。

隔離執行 focused pytest（test_mcp.py、test_mcp_stderr_log.py、test_extension_mcp.py），記錄後 commit：`fix(mcp): parse process stats robustly and keep received results [F2-S1]`。

## F2-S2：取消、期限後回應與診斷
- **相依**：F2-S1。
- **production 檔**：app/agent/mcp.py；只有在診斷流程確實需要時才改 app/agent/startup.py。
- **處理**：AF25–AF28、AF31（Python 部分）、AF36、AF38，以及 P13、P13c、P18、P18b、P26。

工作：
1. **呼叫端取消**：settle 之後，若 task 已結束且不是被取消，就取回它的例外（記為 debug），不讓 asyncio 回報「Task exception was never retrieved」。
2. **期限後的回應**：
   - 在 work deadline 時若還沒收到結果，包裝層會取消 task，此時記下這是「逾時取消」。之後 task 不論以何種例外結束，對外一律拋出 TimeoutError，原例外保留在 `__cause__` 並記為 debug，不得以 ExceptionGroup 原樣回給 Agent。
   - 期限前就結束的協定錯誤照舊原樣傳出；既有的 test_web_search_preserves_protocol_error_message 必須仍然通過。
3. **逾時訊息（FA09）**：寫出有效的 DEFAULT_TIMEOUT 毫秒數，並保留既有的「before a result was received (startup, initialization, call and cleanup included)」語意。
4. **載入診斷（FA09）**：
   - load、prepare 階段失敗時，診斷字串要展開 ExceptionGroup，列出最多 3 個葉例外的類型與訊息。
   - 對有 stderr log 的 server（sanitize_stdout 為真的 spec），附上 log 路徑：以 `_mcp_log_dir()` 與 server 名稱另行組出。
   - 不改變 `_spec_to_connection` 的回傳型別，因為測試會 monkeypatch 它。
   - 保留既有格式前綴 `mcp:<name>: applied_but_unavailable: <stage>:`。
5. **測試順序問題**：test_web_search_real_session_budget_and_cleanup 在計時開始前先 import langchain_mcp_adapters.client 與 .sessions，避免第一次 import 的時間被算進預算。

最少檢查（tests/test_mcp.py；startup 兩種 extension 情境沿用既有 parametrize）：
- **取消**：caller 取消時，若 task 在 settle 期間以非取消例外結束，loop exception handler 不會收到「never retrieved」（測試中呼叫 gc.collect()）。
- **期限後的回應**：lifecycle server 新增一種模式，等待 `_meta.web_search_work_ms` 加約 100 ms 後才寫出回應。包裝層已會送出這個值，所以回應必然落在 work deadline 之後、kill deadline 之前（預算 800 ms 時，這段區間約為 0.4–0.6 s）。必須得到含預算數值的 TimeoutError，訊息中不得出現「unhandled errors in a TaskGroup」。
- **載入失敗**：web_search 的 command 指向會立刻 exit 的程式。load_mcp_tools_with_families 回傳空工具，且診斷含 `load:`、葉例外類型與 log 路徑，不只是 ExceptionGroup。
- **startup 診斷**：在有／無 extension 兩種情境下，下列診斷都要出現在 session 的 extension_startup_diagnostics：
  - 某個 server 在 load 階段失敗時的診斷（可殺死 P13）；
  - load_mcp_tools_with_families 本身拋例外時的「MCP loader unavailable」診斷（可殺死 P13c）。
- **預算來源**：
  - 經 load_mcp_tools_with_families 載入 spec.env 為 DEFAULT_TIMEOUT=800 的慢啟動 server。它會吞下例外，所以斷言的是：約 0.8 s 內返回空工具，診斷含逾時訊息與 800 ms 預算，而不是 pytest.raises（可殺死 P18）。
  - `_bounded_web_search(..., 300001)` 會被拒絕（可殺死 P18b）。
- **卡住的取消**：task 被取消後仍有限時間地拒絕結束，例如忽略取消、睡 3 s 後才返回。呼叫端仍在預算內返回。用外層 `asyncio.wait_for(…, 預算 + 2 s)` 偵測卡死；操作本身必須是有限的，避免 asyncio.run 收尾時卡住（可殺死 P26）。
- **順序無關**：以下兩種跑法各連跑 3 次，結果摘要寫入 build-log：
  - 單獨執行 `tests/test_mcp.py::test_web_search_real_session_budget_and_cleanup[startup]` 與 `[initialize]`；
  - 整個模組依序執行。

隔離執行 focused pytest，記錄後 commit：`fix(mcp): report cancellation, late results and load failures plainly [F2-S2]`。

## F2-S3：啟動上限 15 秒
- **相依**：F2-S2。
- **production 檔**：app/agent/mcp.py。
- **處理**：FU05、FA15、X09。

工作：
1. 新增具名常數（例如 `WEB_SEARCH_STARTUP_TIMEOUT_MS = 15000`）。web_search 的 discovery（啟動程序、initialize、列出工具、收尾）以 min(15000, DEFAULT_TIMEOUT) ms 為整體上限。
2. **陷阱**：現行 `_load_web_search_tools(connection, timeout_ms)` 用同一個 `timeout_ms`，同時管 discovery（`_bounded_web_search(connection, discover, timeout_ms)`）和之後每次工具呼叫的 interceptor。所以不能直接把較小的值傳給 timeout_ms，否則每次搜尋都會被限在 15 s 內。
   - 必須另外傳入（或在函式內計算）discovery 專用的上限；interceptor 沿用 DEFAULT_TIMEOUT 的整體預算與 285/15 切分（A03）。
3. 啟動逾時時，web_search 在本 session 標為不可用。診斷沿用 F2-S2 的英文格式，固定含 `startup timeout (<上限> ms)` 這段文字，並附 log 位置；本機工具與其他 MCP 照常載入。
4. **FU06**：這是 MCP client 端的生命週期行為，只依據時間與程序狀態，不得加入任何搜尋相關的判斷，也不新增環境設定。

最少檢查（tests/test_mcp.py；可在測試中以 monkeypatch 縮短常數）：
- 慢啟動的 lifecycle server（啟動後睡 2 s）在常數縮短為 300 ms 時，discovery 約在 0.3 s（加合理餘裕）內返回空工具，診斷含 `startup timeout (300 ms)`。同一測試中，另一個正常的 MCP server 仍載入成功。
- DEFAULT_TIMEOUT 小於常數時，以 DEFAULT_TIMEOUT 為準。
- **呼叫不受啟動上限影響**（能抓到上述陷阱）：常數縮短為 300 ms、DEFAULT_TIMEOUT=4000，經 load_mcp_tools_with_families 以 meta 模式載入。（執行時更正：原寫 2000，但 2000 時清理保留為 1000 ms，工作時間只剩 1000 ms，「大於 1000」不可能成立；見 build-log F2-S3。）
  - 呼叫回報的 `_meta.web_search_work_ms` 必須大於 1000，而不是被限在 300 ms 以內；
  - 另一個工具呼叫刻意花 600 ms（超過常數），仍必須成功返回。
- 既有的 meta 測試仍通過。
- 隔離執行 focused pytest。

記錄後 commit：`fix(mcp): bound web search startup at 15 seconds [F2-S3]`。

## 階段界線
- 不改環境 allowlist、呼叫預算數值、resolver 的分工、stdout 過濾或 log rotation。
- 不為其他 MCP server 加入時間上限（X10）。
- 依 FU06，只改 MCP client 端的行為，不把任何搜尋邏輯放進 app/agent。
