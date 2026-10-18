# P4：真正停止當前回合

依賴：無；可在 P1 原生視窗整合受阻時進行。覆蓋 G8、G9。政策見 [GOALS](../GOALS.md)、[PLANS](../PLANS.md)。

完成後：Stop 後立即呈現 Stopping，模型／工具／核准不再推進；本地受控工作及保存狀態收束後回到可送出，同一對話下一回合可用。不是隱藏回答，也不是重啟後端。

## P4-S1 單回合取消與實際工作收束

執行細分（2026-10-18，依可獨立驗證邊界；每個改動子步驟各自 commit）：
- P4-S1a：main／extended 模型 await 可取消，保留既有同步入口；以無外網假模型驗證。
- P4-S1b：現有同步本地工具／RAG 的受控等待與停止檢查；以本地 subprocess／provider stub 驗證。
- P4-S1c：Stop protocol、目前回合擁有權、核准／document 等待與保存收束，完成本節整合驗收。S1a/S1b 不代表使用者 Stop 已完成，S1c 依賴兩者。

先沿現有 call graph 有限核對：`desktop/server.py` 分派 request，`service.py::_session_turn`、document.apply 與 approval，`session.py` turn/persistence，模型 await，graph 的 tool dispatch，`tools/bash.py` 與實際由當前回合呼叫的本地工具。只記可達的取消點／阻塞工作及其擁有者，不審計整個 repository。

已知缺口：service 未追目前 turn task／stop request；document candidate 與 approval 將 CancelledError 和 timeout 一起吞掉；bash 同步 subprocess.run 無可供 Stop 終止的 handle。session 已能將取消保存成 interrupted，可沿用。

擬採最小方案：
- 新增關聯目前 session/turn/request 的 stop method，不被一般 busy guard 擋住；標記此回合 stopping，後續節點／新工具／遲到 approval 或 document.apply 不得再開始。
- 追蹤目前 turn task 與它實際衍生的 document/approval 工作；區分 timeout 的一般結果與使用者取消，取消應清理等待並向外傳播，不能回傳正常 ToolMessage 後讓 graph 繼續。
- 非同步模型／MCP await 取消本地等待並清理資源；僅在對方現行介面支援時傳 cancellation，不能宣稱外部結果撤銷。沿目前每次 tool call 的 MCP session context 清理，不關閉整個桌面 session 或重啟後端代替 Stop。已查到本機 MCP stdio context 有關 stdin、等待退出及終止受控 process tree 的清理路徑，優先使用；仍以實測確認取消時清理有被等待。
- Linux bash 沿既有 command_runner 擴充可追蹤的 Popen/process group，終止本回合啟動的 process 及其受控子程序並 wait/reap；不殺其他工作。正常命令、timeout 與 CLI 既有行為保留，不改成新 worker 系統。
- 取消 asyncio.to_thread 不會證明 thread 已結束。對已開始的文件寫入等短同步工作，留住真實完成等待，再決定保存結果與停止終點；工具入口及後續寫入點尊重當回合停止旗標。對現行長本地工具，優先於既有循環加入合作取消／沿現有 subprocess 終止，不為未知工具建通用隔離執行框架。
- 若有限追查發現長同步工作在既有架構無法中止或合理收束，具體列出該工具、它的效果及最小改動；需要新 concurrency model／依賴時先批准。不能以只取消 Task 就當 P4 完成。
- 停止與正常完成交錯時沿既有單回合狀態判定一個 terminal 結果；只有真實工作已收束、pending turn 已被寫成 interrupted/cancelled（或已先正常完成）才回報停止完成。已完成的寫入不回滾，未完成不標 completed。

已確認的同步範圍不可遺漏：`agent/adapters/langchain/rag_tools.py` 的 explore/search/get_context 及 read_file；`agent/ingest.py` 經 to_thread 執行的 init/ingest/sync/prune 是現有回合 slash 路徑；`rag/cli/ingest.py`、`rag/sync.py` 有檔案迴圈。只為這些可達迴圈補停止檢查，RAG 可接受通用取消檢查 callback，不引入 agent 專屬依賴。`session.py` 現有 skill 安裝 shield 後等待工作與 staging 收束的保護須保留。同步 provider 的長等待若無可用取消點，先解決這個具體前提再稱 Stop 完成。

主要路徑：`app/agent/desktop/service.py`、`server.py`、`session.py`、現有 tool dispatch／bash 路徑；若其他現行工具確實有受控工作才局部改該處。stop method/結果沿現有 protocol 三側與 fixtures 更新，受 T3 約束。

最少且有判別力的驗證：既有假模型等待時 Stop，確認不進下一步；Ask approval 待決時 Stop，遲到核准不再寫入；一個可重現、無外部服務的 bash 長命令啟動受控子程序，Stop 後確認 process 已退出且後續效果不發生。對已確認 to_thread ingest 用一個可控 stub 停在中途，確認收束後不再背景寫入、不啟動下一檔；MCP 使用一個無外網的本地 stdio 等待例確認 call context 清理與子程序退出。不每個工具各建一套測試，不跑實際 embedding 或完整資料。讀回 conversation 確認使用者訊息仍在、狀態為 interrupted/cancelled，下一回合成功，已先完成的檔案寫入仍在。通過後 commit `[P4-S1]`。

## P4-S2 Send／Stop 介面與終點

沿 `App.tsx::ComposerFooter`、`conversations.ts`、`backend.ts` 接入上一步狀態。當前 turn 執行或等待核准時同一按鈕位置顯示 Stop；點擊立即 Stopping 且不允許新 send。核准對話開啟時仍必須有可操作的 Stop，不得被 modal 遮住。待真正 terminal 才恢復 Send，保留 stopped/interrupted 的訊息狀態；取消請求本身出錯時呈現真實錯誤，不能假裝已停止。

Stop 作用於目前回合，普通 backend Restart 仍保留給 MCP 管理。重複點擊不多送 destructive 動作，也不把停止回合自動重試。

驗證：接上假模型／本地工具的桌面介面實際點 Stop，檢查按鈕狀態、可停止核准等待、完整收束後下一則訊息可送；覆用 P4-S1 的後端證據，不再重跑全部工具。完成後 commit `[P4-S2]`，P5 可等待此終點再刪除執行中對話。
