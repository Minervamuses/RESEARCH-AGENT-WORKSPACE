# P4 — 最小可持久化執行計時

目標 G4；依賴：無其他階段，與 P1–P3 同批驗收。共通 [政策](../PLANS.md)／[隱私與行為條件](../GOALS.md)。

## 證據與最小接點

`session.py:441–475` 只保存粗工具摘要；`turns/journal.py:9–38` 為 process-local；`turns/execution.py:37–60` 的 updates/progress callback 是 node 結果，不能當每個工具起訖。`graph.py:319–341` 有真正 model invoke/ainvoke；`tools/policy_node.py` 在授權後交給 ToolNode。`diagnostics.py:147–197` 已提供 INFO 以上 rotating file，server.py:454 已安裝。

首選在現有 `observability.py` 定義最小 LangChain callback，從 `turns/execution.py` 的 graph config 傳入，`session.py:_execute_graph` 提供既有 active turn ID。三個 production files 是待驗證的最小方案，不另建 telemetry framework。先用真 graph＋假模型／工具確認 callback 穿過 RunnableLambda／ToolNode，且能取得 call ID；若無法可靠觀察，不把 node completion 假裝工具結束。

## 事件契約（內部 logger，不新增對話 schema）

| 類別 | 必須可觀察資料 |
|---|---|
| turn | turn_id、執行 attempt/run ID、開始／結束、monotonic elapsed、成功／失敗／取消 |
| model | turn_id、attempt、每次真正 invoke 的序號、callback run ID、開始／結束／error；回應既有 token usage 可用則記 |
| tool | turn_id、來源 model 序號／parent run、tool_call_id、工具名、開始／結束／error／cancel；並行個別區間 |
| Citation | allowlist action、原始 query 的不可逆 hash（不記明文）、結果狀態、候選數、真摘要數；不把 save success 與工具成功混為一談 |

時間戳供跨記錄關聯，duration 用 monotonic clock。重試同一 logical turn 要有新的 attempt ID，工具 call ID 不能跨 attempt 誤配。模型 callback 次數包含 outer empty-response/repair 再呼叫；SDK 一次 invoke 內部 HTTP 重試仍在同一 model 區間，未知 attempt 次數不虛構。

候選／摘要數從現有型別／實際結果產生處取得，不以任意 regex 猜模型 prose。首選 callback 在記憶體讀工具結果，只輸出 allowlist 計數；若現有 citation tool 的 content-only 輸出無可靠結構，先列出最小額外插點（例如 citation/tool.py 或 service.py）及文件數，按超過三檔 gate 請核准。不能以把未知記成 0 來假裝滿足；未知應為 null／unavailable，並記錄原因。G4 完整驗收仍需至少一個真 Citation fixture 能產生可靠數量。

## 步驟與驗收

P4-S1：核實 callback 可觀測真正 model 與每個 admitted tool；實作一組 per-execution handler／最小事件串接，不更動並行模型。先核定檔案集合；需要超過三 production files 時先給可審閱方案再取得核准。

P4-S2：沿用 INFO 診斷 log，輸出到既有 component 檔案並確實 flush 到可在重啟後讀取；不可只寫 DEBUG 或記憶體 journal。保留 stdout 作 NDJSON。logger 不可寫入時沿用現有 fallback，應標記追蹤不可用，不能因診斷失敗讓研究回合失敗。

P4-S3：用一個 model 回應同批快／慢兩工具的可控離線案例，讀 log 證明快工具先結束且各自 duration 正確，並有 tool → model → turn 關聯。包含成功、工具例外、模型例外、取消與未獲授權的工具；拒絕不能記為已執行成功，未結束事件需在 turn 收尾標記取消／中斷或保持明確未完成。

P4-S4：沿用 Citation fixture 檢查 search action、同 query hash 可串接、不同 query 可區別，候選／摘要數與 fixture 相符；重試 attempt 分開，model 序號與工具數不同。assert 原 query、全文、DOI、raw args 與 secrets 未出現在新增 log。新 trace 可在關閉原 process 後重讀，GUI 完成時點不能覆寫個別事件。

可重用 `tests/test_observability.py`、`tests/test_diagnostics.py`、`tests/test_policy_tool_node.py`、`tests/test_session_lifecycle.py` 與 `tests/test_citation_workflow_tool.py`。依實際插點選必要 module 跑 `poetry run pytest ... -q`；真 graph／callback 整合案例應放既有相關 module，不能只測手寫 logger 字串。

## 交付與量測出口

交付一段已去內容的實際離線 trace、所用事件語義、精確 log 位置與解析程序（可直接閱讀，不另造分析平台）。用 P1–P3 修好後的一次正常使用 trace 決定 P6–P10；若尚無自然樣本，記錄缺口，不跑付費補查、不報性能改善。總時間與重疊區間要分開；未觀測區段列未知。

若 callback 路線不能以小改動達成，遵循兩次嘗試規則停止並給較小替代接點，不升級成通用 tracing 系統。
