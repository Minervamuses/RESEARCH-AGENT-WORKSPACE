# P4 — Chromium、併發、取消與有界收尾
依據：[目標 A03/A04](../GOALS.md)、[執行契約](../PLANS.md)。相依P3。涵蓋G5/G8、R08/R09、AC08–AC10。

## 後置條件
搜尋、搜尋後正文與單頁讀取都由明確擁有者管理實際 browser/context/page/request/timer；Node 路徑受有限預算控制。Python外層啟動/呼叫/清理的最終300秒保證在P5完成。

## P4-S1：收斂 Chromium 與真實資源
最小共同作用範圍：browser-pool.ts、search-engine.ts、enhanced-content-extractor.ts，若需server注入唯一pool再改index.ts。四檔共同修改僅限「同一程序唯一pool、各真實建立路徑納管」這個不可分後置條件；小於此範圍若留下dedicated browser或兩個互不知情pool，不能滿足需求。這是列明的具體必要範圍，不是全面重構授權。

- 一個程序最多一個Chromium。合併同時到達的launch承諾；launch失敗後能清掉promise並下次正常嘗試。不可用Map型別數冒充資源數、不可在忙碌時任意evict。
- 所有Bing/Brave獨立launch與extractor fallback均納管；Firefox imports/launch/設定移除。Brave改Chromium，不能只改pool預設。
- 每個呼叫有自己的lease/context資訊，不依getLastUsedBrowserType。context/page成功失敗都finally釋放；關閉一個工作不提前關掉另一活躍工作。
- 初始page/context與HTTP各2，等待亦計預算。既有p-limit或簡單既有pool計數即可，不新增worker系統；共享鎖不可巢狀等待造成死鎖。跨程序不是全域保證。
- 移除src內不再適用的MAX_BROWSERS/BROWSER_TYPES與Firefox說明，保持有效headless；vendor README的Firefox／評分說明由P5-S1一併修正。保留一般限流的有限工作性質，若rate-limiter現行排隊會繞過deadline，P4-S2局部調整；不另做全域rate limiter。

新增最小 tests/test-browser-lifecycle.mjs（建議待實作路徑）：stub並行launch只一次、上限峰值、失敗重試後無孤兒、忙碌context不被關閉、Brave不觸發firefox。實際 Chromium 能否啟動於P6少量實機驗證，不能把stub當實機。build＋focused檢查後 commit：fix(web-search): manage Chromium resources through one bounded pool [P4-S1]。

## P4-S2：deadline、取消與停止後續工作
相依P4-S1。核心檔案search-engine.ts、enhanced-content-extractor.ts及browser-pool.ts；必要的index.ts邊界接線與rate-limiter.ts局部修改按可獨立檢查的小步拆成 P4-S2a/P4-S2b，各自檢查並commit，記錄實際檔案，禁止把多個改動步驟最後打包。
- 入口建立單調deadline與取消狀態，傳至queue、launch、navigation、selectorwait、HTTP、有限重試及fallback。依U13，每個局部timeout = min(該操作上限, 剩餘預算)；不能每換引擎重設整段預算，也不能讓單一操作直接取用全部剩餘預算。單一操作逾時後，若仍有預算，繼續下一個引擎或候選。
- 操作上限依現行語意沿用現有值作為可調整初始值（PLANS基線所列）：引擎內單次導覽／HTTP請求4秒、selector等待2–3秒、單頁HTTP／導覽6秒、搜尋後正文單頁整體8秒。4秒不是含launch與重試的整個引擎嘗試上限；整個引擎嘗試只受剩餘預算限制。集中為具名常數，不新增環境設定。
- HTTP使用既有Axios/原生取消能力；瀏覽器取消時停止導覽、關閉自有page/context；不可取消的launch完成後立即納管並關閉，不再開新工作。
- timeout race必須清timer並觸發實際取消與有界收尾。成功後亦清timer；abort之後queued任務不能再導覽。只在明確暫態錯誤、仍有預算時做一次必要重試，不因內容短而重試。
- 在已取得候選時，優先回傳候選與已知內容／取消狀態；P5外層強制終止導致無法取得部分資料時，誠實回報可見限制，不偽造結果。
- 工作預算與清理reserve見A03；數值可縮短供測試。清理耗盡使用既有子程序管理能力收尾，不能殺無關browser或使用者程序。

focused案例用假的單調時鐘／可控延遲與短deadline：
- 排隊逾時、launch慢、導航慢、HTTP慢、fallback前取消；
- 第一個引擎的selector等待卡住時，在其操作上限內放棄並嘗試下一個引擎，不吃掉整段預算；

確認返回後不再產生請求、lease計數歸零、無殘留timer。不做多輪五分鐘等待。每個實際拆步build、測試、log與commit，subject含P4-S2或其子ID。

## P4-S3：MCP程序生命週期
相依P4-S2。主要index.ts與必要pool收尾方法。
- MCP連線結束、可處理的終止訊號、正常完成都由程序擁有者終止未完成工作並有界回收；重複close可安全處理。
- 依A09，「連線結束」以process.stdin的end／close事件判定：中止未完成工作、有界關閉自有browser後退出。不能只依賴server.onclose或extra.signal，因為它們在真實Python stdio路徑上不會觸發。
- 不在每次工具成功時關閉其他活躍呼叫共用browser；只釋放本次lease/context。目前index.ts:230的summaries handler每次呼叫都closeAll()，要改成只釋放本次資源。程序退出時才關全部自有資源。
- close失敗記診斷，不把已取得成功改為搜尋失敗、不覆蓋原始錯誤。
- 停止／訊號處理不能依賴單純process.exit掩蓋孤兒工作；確認實際Node/Chromium子程序結束。

驗證：
- 用stub驗證關閉失敗、連線結束和terminate時結果保留。
- 受控本地真程序驗證：經真實Python stdio關閉stdin後，Node在有界時間內自行結束，而非等client的SIGTERM或舊timer；區分wrapper/Node/browser。依PLANS「宿主沙箱與執行環境」在沙箱外執行，殘留程序在同一腳本內取證。

build與focused檢查後 commit：fix(web-search): bound shutdown without overwriting results [P4-S3]。
