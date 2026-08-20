# Citation 工具額度與 LangGraph Recursion Limit 不相容

## Issue 定位

- 類型：Citation workflow 執行上限不一致。
- 優先度：高。
- 狀態：已解決（2026-08-20）。
- 修正前影響：預設設定宣告可執行 20 次主要工具呼叫，但模型產生第 16 次 action 後、tool 執行前即觸發 `GraphRecursionError`；最後的 citation `save` 可能完全沒有執行。

## 解決結果

本 issue 原先把「提高 recursion 以兌現 20+4 tool quota」視為既定方向；實作前重新追查設定 consumer、歷史證據與真實失效後，改以更小且一致的政策解決：

- 刪除 primary 20、citation-local 4、proposer 2 三套 tool-call quota，以及對應計數、prompt、裁切與 budget telemetry。
- 在 `AgentConfig.graph_recursion_limit` 保留唯一的 per-graph emergency fuse，預設 64、最小 3；programmatic config 與 CLI 共用同一驗證。
- `build_graph(config)` 在 compile 時把該值綁到 graph；normal、citation、proposer、fallback、reviser 與公開 builder 不需另外傳 raw recursion 設定。
- 使用 LangGraph `RemainingSteps` 在剩餘步數少於 3 時禁止新工具並產生 best-effort final answer，避免到達 framework hard error 才丟失既有結果。
- CLI 改為 `--max-graph-steps`，override 仍先寫入 `AgentConfig`；`/status` 顯示同一設定。

完整決策、consumer map、commit 與驗證紀錄見 [`note/20260820/agent_loop_guardrail_consolidation.md`](../note/20260820/agent_loop_guardrail_consolidation.md)。

以下內容保留為修正前的問題描述與重現證據；其中 20、4、32 與 `--max-turns` 不再是現行設定。

## 專案背景

`AgentConfig.agent_max_tool_interactions` 是每回合主要／外部工具呼叫的硬上限。目前預設為 20，這是刻意決策：citation workflow 可能需要多次 discovery，之後才執行最終 `save`。

Citation 的 `explain`、`sources`、`source` 三種 session-local 查閱 action 另有獨立額度 4。它們不消耗主要工具額度，但仍會經過 LangGraph 節點。

同一回合另受 `ChatSession.DEFAULT_RECURSION_LIMIT = 32` 約束。現行 graph 在一次連續工具 round 中通常依序經過 `agent → tools → agent`，而回合開始前還有 `skill_loader`，所以 recursion step 並不等於工具呼叫次數。

## 已確認的問題

目前兩個上限各自正確計數，卻沒有共同保證「允許的工具 action 能在 recursion limit 內完成」。結果是主要額度仍顯示尚有剩餘時，LangGraph 已先終止整個回合。

這不是「20 是否適合」的產品決策問題。20 次主要額度及其較高時間／API／運算成本已被接受；問題是預設 recursion limit 無法兌現該額度。

## 最小重現

使用真實 compiled graph、預設 `agent_max_tool_interactions=20`、預設 `recursion_limit=32`，並啟用 citation skill。讓 deterministic model 依序產生：

1. 15 次 `citation_workflow(search)`。
2. 第 16 次 action 產生 `citation_workflow(save)`。

已觀察結果：

- 15 次 search 均完成。
- 模型有產生第 16 次 save action。
- save tool 沒有執行。
- LangGraph 拋出 `GraphRecursionError`，訊息指出 recursion limit 32 已到達。

因此，使用者可能看到整回合失敗，而且已完成的 discovery 沒有轉成 saved citation bundle。

## 期望行為

- 預設 recursion limit 必須足以完成設定允許的主要額度與本地 citation 額度，並保留產生最終答案所需的 graph steps；或系統必須把有效工具額度限制在 recursion limit 實際可完成的範圍。
- 若任一上限改變，另一上限或其推導規則不得靜默失配。
- Citation workflow 在仍有宣告額度時，不得因預設 recursion limit 提前跳過最後的 `save`。
- 一般 RAG、Web、bash 與其他主要工具仍使用相同的全域主要額度 20；本 issue 不重新討論該產品決策。

## 修正前需要決定

1. `recursion_limit` 是否改成由主要額度、本地額度與固定 graph overhead 推導，而不是維持獨立 magic number。
2. CLI `--max-turns` 是否繼續表示原始 LangGraph recursion depth，或改成使用者可理解的工具 round 上限。
3. 達到使用者自訂的較低 recursion limit 時，是否應回傳最佳可用結果與清楚錯誤，而不是讓 citation save 狀態含糊。

不要只把 32 換成另一個未說明的常數；需用測試證明完整允許序列及最終回答都能完成。

## 驗收條件

- 預設設定下，20 次主要工具 action 可全部執行，之後仍能產生最終回答。
- Citation 測試覆蓋「多次 search，最後一次 save」且確認 save 實際執行。
- 混入最多 4 次本地 citation 查閱 action 時，行為符合明確記載的額度與 recursion 契約。
- 一般非 citation 工具達到主要額度時仍會強制收斂，不形成無限循環。
- CLI 狀態與錯誤訊息能區分工具額度耗盡和 LangGraph recursion limit。
- 額度／recursion 的邊界測試不依賴 live model 或付費 provider。

## 主要參考檔案

- `app/agent/config.py`
- `app/agent/graph.py`
- `app/agent/session.py`
- `app/agent/turns/execution.py`
- `app/agent/cli/chat.py`
- `app/tests/test_graph_skill_loader.py`
- `app/tests/test_citation_workflow_tool.py`
- `app/tests/test_observability.py`
