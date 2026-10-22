# 驗收時存活的單點突變
驗收以 155 個單點突變檢查已提交測試的敏感度：Node 114 個，殺死 62 個；Python 41 個，殺死 31 個。下表列出存活且代表真實行為改變的突變，作為 F6-S3 的複驗清單。突變以語意定義，不依賴原行號；修改後應以等效的單點改動重建。

複驗方法：
- 在 repo 外的暫存複本套用一個突變，複本的內容與範圍依 F6-S3：Node 複本含 src、tests、dist；Python 複本不含 app/desktop 與 app/store。
- 對應測試至少一個非零退出，才算「殺死」。
- 「必殺」列必須被已提交測試殺死。「可選」列若無法殺死，要記錄理由；「等效」列不需處理。
- 「不再適用」列的程式已由 F3-S2 刪除，F6-S3 只記錄為 not_applicable 並寫明原因。

## Node（app/vendor/web-search-mcp）
| 突變 | 單點改動 | 應由 | 類別 |
| --- | --- | --- | --- |
| N02b | formatSearchResponse 在零候選時一律印「All attempted engines failed」（刪除零解析分支） | F5-S1 | 必殺 |
| N02c | 引擎行不印 error 原因 | F5-S1 | 必殺 |
| N02d | 輸出文字省略 strategy_stopped 引擎 | F5-S1 | 必殺 |
| N02g | 合併來源的候選只印第一個來源引擎 | F5-S1 | 必殺 |
| N03b | 移除逐筆加入時的 `results.length >= numResults` 防護（一批超量時會回超過 limit） | F5-S1 | 必殺 |
| N04c | Brave URL 清理時多做一次 decode（`%252F` 變成 `%2F`） | F6-S3 | 不再適用（F3-S2 刪除 Brave、DuckDuckGo 與 Bing 首頁流程） |
| N05d | 部署值 MAX_CONTENT_LENGTH=0 被接受 | F6-S1 | 必殺 |
| N06d | originalLength 改以 UTF-16 code unit 計數 | F1-S4 | 必殺 |
| N07c | 重新加入以 class/id 子字串（nav、footer、comment、sidebar、menu、banner、cookie）刪除元素 | F6-S2 | 必殺 |
| N07e | 解析相對連結時忽略頁面實際 final URL（換成錯誤 host） | F1-S1 | 必殺 |
| N07f | 忽略 `<base href>` | F1-S1 | 必殺 |
| N08h | BROWSER_HEADLESS=false 被忽略 | F6-S1 | 必殺 |
| N08i | 不合法的 BROWSER_HEADLESS 被接受 | F6-S1 | 必殺 |
| N09g | withPage 的排隊不受預算約束（排隊中的 page 呼叫在期限後仍等待） | F6-S2 | 必殺 |
| N11b | 移除 stdin end 與 close 的處理 | F6-S1 | 必殺 |
| N11c | 移除 SIGTERM 處理 | F6-S1 | 必殺 |
| N11d | shutdown 時不中止進行中的呼叫預算 | F6-S1 | 必殺 |
| N11e | shutdown 時不關閉 pool | F6-S1 | 必殺 |
| N12 | summaries handler 結束時再次呼叫 closeAll | F6-S1 | 必殺 |
| N13 | full-web-search 忽略 includeContent（永遠讀正文） | F6-S1 | 必殺 |
| N13b | summaries 也去讀正文 | F6-S1 | 必殺 |
| N14 | Node 讀取改名後的 meta 鍵（忽略 web_search_work_ms） | F6-S1 | 必殺 |
| N14b | 取消 min(work, remaining)，只用部署預算 | F6-S1 | 必殺 |
| N14c | withBudget 忽略傳輸層 signal | F6-S1 | 必殺 |
| N14d | 單頁工具忽略呼叫端給的 maxContentLength | F6-S1 | 必殺 |
| N14f | full handler 傳給 formatter 的 includeContent 恆為 false | F6-S1 | 必殺 |
| N14g | summaries 傳給 formatter 的 engines 為空陣列 | F6-S1 | 必殺 |
| N14h | summaries 未把 limit 傳給 search | F6-S1 | 必殺 |
| N14i | handleWebSearch 的結果丟失 engines | F6-S1 | 必殺 |
| N14j | 移除 summaries 對 limit 的 transform。若 F5-S3 之後 limit 仍在 schema 與 handler 兩處重複驗證，此突變為等效，記錄理由；若只剩一處，F6-S1 的無效 limit 案例必須殺死它 | F6-S1 | 必殺（條件等效） |
| N15 | Brave 暫態重試上限放寬為 5 次 | F6-S3 | 不再適用（F3-S2 刪除 Brave、DuckDuckGo 與 Bing 首頁流程） |
| N16b | Brave goto 不帶預算 timeout | F6-S3 | 不再適用（F3-S2 刪除 Brave、DuckDuckGo 與 Bing 首頁流程） |
| N16c | 頁面讀取的 goto 不帶 timeout | F6-S2 | 必殺 |
| N16e | Bing waitForNavigation 不帶 timeout | F6-S3 | 不再適用（F3-S2 刪除 Brave、DuckDuckGo 與 Bing 首頁流程） |
| N16f | Brave selector 等待不帶 timeout | F6-S3 | 不再適用（F3-S2 刪除 Brave、DuckDuckGo 與 Bing 首頁流程） |
| N17 | DDG 請求不帶中止 signal | F6-S3 | 不再適用（F3-S2 刪除 Brave、DuckDuckGo 與 Bing 首頁流程） |
| N20b | extractContentForResults 忽略 targetCount（F5-S2 保留此參數並加測試） | F5-S2 | 必殺 |
| N26 | 頁面 HTTP 請求不帶中止 signal（明確中止時 socket 仍開著） | F6-S2 | 必殺 |
| N28 | killOwnedBrowsers 變成 no-op | F4-S2 | 必殺 |
| N29 | boundedClose 不再與時限競速（close 永不返回時 closeAll 也卡住） | F4-S2 | 必殺 |
| N42 | cleanupReserve 回傳 0 | F6-S1 | 必殺 |
| N43 | Node 接受大於 300000 的 DEFAULT_TIMEOUT | F6-S1 | 必殺 |
| N09b | 子預算 dispose 時不移除父 signal 的 listener | F6-S2 | 可選 |

## Python（app/agent）
| 突變 | 單點改動 | 應由 | 類別 |
| --- | --- | --- | --- |
| P07 | remember_processes 不展開後代程序 | F2-S1 | 必殺 |
| P13 | startup 呼叫 load_mcp_tools_with_families 時不傳 diagnostics | F2-S2 | 必殺 |
| P13c | 移除「MCP loader unavailable」診斷 | F2-S2 | 必殺 |
| P18 | loader 忽略 spec.env 的 DEFAULT_TIMEOUT | F2-S2 | 必殺 |
| P18b | _bounded_web_search 的上限由 300000 放寬為 600000 | F2-S2 | 必殺 |
| P26 | 取消後最後的有界等待改為無界 | F2-S2 | 必殺 |
| P27 | 移除週期性程序觀察 | F2-S1 | 必殺 |
| P07b | kill 時只殺 PID、不殺群組 | F2-S1 | 可選 |
| P07d | kill_owned 不檢查 starttime 身分 | F2-S1 | 可選（PID 重用難以穩定重現） |

## 等效或被縱深防禦遮蔽（不需處理）
- N11：只移除 'end'，'close' 仍會觸發，51 ms 內退出。
- N09d、N09e：佇列內的檢查被外層競速或逐引擎的中止檢查遮蔽。
- N10a、N10c、N45：局部上限的 min 被中止 signal 遮蔽；N27 已證明兩者同時移除時測試會失敗。
- N10d、N10e、N10f：常數值。U13 規定為可調初始值，不釘死。
- P04b：低價值的安全分支。

F4-S1 改用總時間上限後，N26 會被新的總時間上限遮蔽，因此不能只靠「到期」案例殺死；F6-S2 要用「明確中止」案例（期限仍遠時呼叫 budget.abort()）殺死它。N17 所在的 DuckDuckGo 程式已由 F3-S2 刪除。
