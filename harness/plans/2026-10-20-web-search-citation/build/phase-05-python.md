# P5 — Python→Node 設定、時間與 MCP 失敗隔離
依據：[目標](../GOALS.md)、[執行契約](../PLANS.md)。相依P4；失敗隔離子步P5-S2只需既有啟動基線，可在P4阻塞時獨立處理。P4只有環境阻塞（PLANS「宿主沙箱與執行環境」）時，P5各步照常進行。涵蓋G5/G6/G8、R09/R10/R11。

## 後置條件
Agent真實載入／呼叫vendored dist，保留的設定改變Node實際行為；任何單一MCP的規格解析／準備／啟動／載入失敗只影響自己，兩條extension情境都有診斷。父層與Node共同滿足300秒總上限。

## P5-S1：設定清單與明確傳遞
主要production範圍app/agent/mcp.py與Node已有設定消費處；若需同步多個消費處，按可驗證的設定群拆步，各步commit，不造設定框架。

以下是本計劃選定的最小設定契約；不是所有現值都已在程式實現。
| 設定 | 目標預設與有效語意 | 來源／處置 |
| --- | --- | --- |
| AGENT_ENABLE_MCP_WEB_SEARCH | 現有true；false優先停用 | 保留Python開關 |
| AGENT_MCP_WEB_SEARCH_COMMAND / ARGS | 未設command使用repo vendored Node入口；有command則取代預設command/args，不混入預設dist參數 | 保留既有解析與缺build診斷 |
| MAX_CONTENT_LENGTH | 10000；部署值只接受1–10000；呼叫顯式1–10000優先，呼叫0或省略採部署預設；超10000明確拒絕 | 既有名稱，修正Node預設；非法值診斷而非silent NaN |
| DEFAULT_TIMEOUT | 300000毫秒；改為一次呼叫總預算，可調小不可超過300000；不是每次重試重新取得的預算 | 舊6秒局部語意停止支援並更新描述；單一操作上限依U13改由程式內具名常數維持；父層／Node皆使用 |
| BROWSER_HEADLESS | true，明確false才關 | 保留；Brave/Bing/extractor一致 |
| MAX_CONCURRENT_PAGES | 2，正整數；每程序活躍page/context上限 | 新的局部設定名稱；以現有pool實作 |
| MAX_CONCURRENT_HTTP | 2，正整數；每程序活躍HTTP讀取上限 | 新的局部設定名稱；用既有能力，不新增worker |
| DEBUG_BROWSER_LIFECYCLE | false；只記必要資源診斷 | 保留如仍有作用 |
| DEBUG_BING_SEARCH | false；只在Bing保留時有意義 | 保留如仍有作用 |
| ENABLE_RELEVANCE_CHECKING / RELEVANCE_THRESHOLD / FORCE_MULTI_ENGINE_SEARCH | 不再支援 | 刪除功能；FORCE不再切回舊批次策略 |
| MAX_BROWSERS / BROWSER_TYPES / BROWSER_FALLBACK_THRESHOLD | 不再支援 | 固定單Chromium、改真實工作上限，刪品質次數fallback |

- Python僅對web_search傳必要allowlist的有效值；不複製全部父程序環境、不帶其他provider秘密。底層stdio必要HOME/PATH等依現有SDK機制，不設通用環境同步器。依U11，不為遷就沙箱把TMPDIR或proxy變數加入allowlist。
- 優先序：停用 > 自訂command選擇或預設vendored > 明確部署env > 內建預設；每次tool的顯式長度再優先於部署長度。自訂command也收到同一allowlist，但其自有CLI參數語意由該程式負責，不假稱能控制任意自訂可執行檔。
- 若保留debug名稱卻已移除消費者，刪除／宣告不支援，不留假開關。
- 依U14，在vendor README新增直接相關設定表（README目前沒有設定表），列出仍支援的設定、預設與優先序。同一步把README中已不成立的內容改為符合新行為：
  - npx playwright install chromium firefox；
  - Chromium／Firefox抓取描述；
  - 評分／門檻相關描述。

  不全面改寫文檔。README是文件，不計入production檔案數。
- 用既有test_mcp加入allowlist、預設／自訂／停用與invalid env案例；在P6沿真實Python→Node（依PLANS「宿主沙箱與執行環境」在沙箱外）用MAX_CONTENT_LENGTH=37讀可控長文，確認輸出與truncated有效值真的改變，再傳顯式71驗覆寫、0驗回到37的部署預設，並測10001明確拒絕。只查spec.env不算AC11。
- missing build／無node要在diagnostics可見，其他tools留存。

focused命令從app（套用PLANS的暫存與日誌隔離）：conda run -n app --no-capture-output poetry run pytest tests/test_mcp.py tests/test_mcp_stderr_log.py -q -p no:cacheprovider；Node設定若改則build與對應回歸。每個設定群記錄並commit，主ID P5-S1，建議fix(mcp): pass supported web search settings explicitly [P5-S1]。

## P5-S2：啟動準備與兩條診斷路徑隔離
主要production範圍app/agent/mcp.py、app/agent/startup.py；沿現有結構。
- 各resolver分別捕捉並記server名稱/失敗階段與必要原因，繼續其他resolver。不能用全列表catch最後返回空工具。
- _spec_to_connection及log準備都放進既有per-server隔離，get_tools既有隔離保留。setup失敗不移除已取得工具。
- startup有／無extension都傳同一diagnostics，保留本機tools與可用MCP，使用者可見不可用原因；不只吞例外。
- paths.py缺app root在web resolver捕捉，不改root尋找框架；既有stderr rotation、權限與stdout filter保留。
- 在既有test_mcp/test_extension_mcp適用案例放入resolver拋錯、connection preparation拋錯、get_tools拋錯；兩種extension情境都驗其他MCP與local tools存在且診斷明確。不要追無關測試故障。

套用PLANS的暫存與日誌隔離，執行受影響pytest模組（test_mcp.py、test_mcp_stderr_log.py，變更extension測試則加test_extension_mcp.py；加 -p no:cacheprovider），記錄並commit：fix(mcp): isolate resolver and connection preparation failures [P5-S2]。

## P5-S3：實際工具呼叫的端到端預算
相依P4及P5-S1。主要production範圍mcp.py；只有證據顯示既有ChatSession dispatch無法涵蓋時才局部改session.py，禁止為限時引入persistent session。

已讀installed adapter的事實：MultiServerMCPClient有tool_interceptors參數；tools.py在interceptor handler內建立stdio session、initialize、call_tool與退出session。因此先在現有mcp.py使用這個既有hook局部包web_search的完整呼叫，不新增adapter層或修改site-packages。discovery get_tools不在此handler內，另在既有loader有界處理。先讀實際安裝版本的hook型別與cleanup行為再寫，不猜不存在的API。

- 每個呼叫起始記單調時間，連程序／初始化／排隊一起扣除，按GOALS A03預留收尾。向Node傳遞或限制剩餘可用時間，不可Python/Node各自重開300秒。
- 配合現有MCP取消與stdio子程序結束；驗證Shell wrapper、Node及其Chromium都屬受管理的子程序，逾時可在總預算內結束。不得用只timeout await而留下真正工作、也不得殺無關程序。
- A1審查已觀察到的收尾行為：
  - 收尾序列：mcp 1.27的stdio_client結束時，先關stdin，等2秒，再送SIGTERM給sh程序群組，再等2秒，再送SIGKILL。
  - Chromium在獨立process group，這個序列打不到它；所以Node必須依P4-S3／A09在stdin end時自行關browser並退出。
  - 外層取消若落在收尾期，會跳過SIGTERM／SIGKILL，可能無界等待。

  因此外層上限要晚於Node工作deadline加Node退出時間，A03的285/15切分就是為此保留。
- timeout/取消區分已知結果與未取得結果；Node已返回的候選不被close錯誤覆寫。若外層在未收到Node結果前強制結束，只能說未取得，不能假造部分候選。
- 用可控本地慢啟動／慢initialize／慢tool／慢close，以及「結果已回、取消落在SDK收尾期」，縮短部署timeout，測真Python呼叫返回耗時及子程序生命週期。這是必要小型整合驗證，可在現有測試加入最小case或一次性命令，不能建立framework。依PLANS「宿主沙箱與執行環境」在沙箱外執行，殘留程序在同一腳本內取證。
- 記錄實際觀測的總時間與設定；計時誤差只作觀測精度說明，不擅自把300秒上限改成較長SLA。

focused tests及真實本地程序驗證後commit：fix(mcp): bound web search calls including startup and cleanup [P5-S3]。若現有SDK無法安全達到，最多兩次最小修正後隔離該必要條件，繼續可做驗收，最後如實列阻塞；不為此自動升依賴或重寫MCP client。
