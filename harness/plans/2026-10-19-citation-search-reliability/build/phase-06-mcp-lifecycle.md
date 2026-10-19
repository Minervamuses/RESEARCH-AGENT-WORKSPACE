# P6 — 依真實程序成本決定 MCP session 重用

目標 G6；前提 P2、P4 完成並取得真正搜尋器程序資料；本階段屬完整啟動範圍，執行者須完成量測、判斷與必要修正，不等使用者挑選。共通 [政策](../PLANS.md)／[目標](../GOALS.md)。

## 要回答的問題

一次真實 Web Search 工具呼叫中，stdio process 建立、MCP initialize、tool call、close 各占多少等待？同一 session 重用是否在既有使用案例中值得其生命週期複雜度？

`app/agent/mcp.py:260–264` 使用 get_tools；已安裝 adapter 0.2.2 的 client.py:152–200／tools.py:366–399 證明無綁定 session 時每 call 建立。echo 三 PID 對一 PID／約 0.623 秒差額只證明該 echo 實驗，不能乘以十四次真搜尋。

## 決策與條件路線

P6-S1：優先重用 P4 同回合資料及有效 launch command；在既有 loader／session 邊界做最小分段計時，區分工具列表初始化與執行、冷／暖啟動。必要真搜尋限相同小案例、查詢與返回品質可比，支出／長耗時按 gate，不能跑 sweep。輸出分段資料與「值得重用／維持現狀／證據不足」的理由，沒有預設節省門檻。

P6-S2（只有選定重用）：先列明資源 owner。現有 `SessionStartup`（startup.py:13–76）只傳工具與 families；必須把 session context 的生命週期放到既有 ChatSession 啟停邊界，不能在 loader 的 async with 退出後留下失效 tool。核對 CLI、GUI shutdown（service.py:_shutdown_session）、取消與初始化失敗；可能涉及 mcp.py／startup.py／session.py／desktop service 超過三 production files，先記錄小方案、每檔必要性與成本，再依計劃內自主範圍實作驗證，不因這些已辨識接點另請示。不改工具 family／權限聯集，不另造 connection pool 或新並行模型。

P6-S3（選定實作）：同一既有 session 的兩次工具呼叫由同一 child process 服務，會話結束後 child 與 stdio 資源關閉；初始化失敗無殭屍；server 崩潰後明確失敗／既有允許的重建路線，不能無界重連。取消不破壞後續可恢復行為，未授權工具仍拒絕。再次量同一代表案例並檢查內容品質；若無有意義改善則記錄，不宣稱性能成功。

現有 `tests/test_mcp.py`、`tests/test_session_lifecycle.py`、`tests/test_extension_mcp.py` 可重用 fake server；依真正受影響範圍選 `poetry run pytest ... -q`。echo 只作 resource/lifecycle check，不能當真搜尋速度驗收。

交付為量測決策；執行者判定需要重用時，須接續完成 patch、清理／失敗實證與同案例前後資料。有足夠實測支持不需重用時，按 PLANS 記錄有證據不需修改；缺資料不能當作完成。MCP 程序重用不等於內部 browser 重用，P7 需獨立證據。
