# Agent loop guardrail 統一與 tool quota 清理事件紀錄

日期：2026-08-20

分支：`clean`

起點：`131875d docs(citations): record recursion budget mismatch`

狀態：已完成；production code、回歸測試與 issue 狀態均已更新

## 摘要

本次事件起於 citation 工作流的 tool budget 與 LangGraph recursion limit 失配：`clean` 宣告 primary tools 可用 20 次、citation-local actions 另有 4 次，但 session recursion 固定為 32 supersteps；真實 graph 在第 16 次串行 action 前後就可能先拋出 `GraphRecursionError`。

進一步盤點發現，問題不應以「把 32 換成另一個 magic number」處理。Primary 20、citation-local 4、extended proposer 2 與 proposer-derived recursion 12 都在限制同一類 agent/tool loop，卻使用不同單位、不同 scope，且沒有目前模型的 representative evidence 支持這些 tight 數字。相反地，既有 live-test 紀錄顯示 cap 4 曾截斷合法 citation 流程。

最後採用的政策是：**不再限制 exact tool-call 數；只在 `AgentConfig` 保留一個明確、共用、較寬鬆的 graph superstep emergency fuse，並在碰到 hard limit 前做 no-tool finalization。**

## 修改前的重疊控制

| 控制 | 修改前值 | 實際 scope | 問題 |
|---|---:|---|---|
| `agent_max_tool_interactions` | 20（`main` 為 4） | 每次 graph invocation 的 primary ToolMessage | Citation 合法流程曾被 cap 4 截斷；20 沒有 live adequacy evidence。 |
| `agent_max_local_tool_interactions` | 4 | Citation `explain/sources/source` 的獨立帳戶 | 沒有 local-action runaway incident 支持數值 4。 |
| `thinking_fusion_proposer_tool_interactions` | 2 | 每個 proposer candidate 各自重置 | 預設三個 proposer 的實際 panel 上限是 6，不是整個使用者 turn 的 2。 |
| `DEFAULT_RECURSION_LIMIT` | 32 | 每次 LangGraph invocation 的 supersteps | 和 tool call 使用不同單位；只能完成約 14 次串行工具操作再正常回答。 |
| `_proposer_recursion_limit()` | 預設 12 | 每個 proposer graph | 從 proposer quota 2 另外推導，形成第二套 recursion policy。 |

原註解稱 tool quota 是 per-turn，但 extended proposer、base fallback 與每次 reviser 都建立或執行新的 graph invocation，計數會重置；因此它也不是整個使用者回合的可靠成本上限。一個 citation tool call 內部又可能 fan out 到多個 provider request，ToolMessage 數並不等於外部 request、token、時間或金額。

## 修改後的唯一資料流

唯一設定位於 `app/agent/config.py`：

```text
AgentConfig.graph_recursion_limit = 64
    └─ build_graph(config)
        └─ graph.compile().with_config({"recursion_limit": 64})
            ├─ ChatSession normal/citation/fallback/reviser
            ├─ extended proposer graphs
            └─ public agent.build_graph(config) callers
```

實際 consumers：

- Normal 與 citation：`ChatSession._run_graph_turn()`。
- Extended zero-success base fallback 與每次 reviser：同樣走 `_run_graph_turn()`。
- 每個 proposer：只 clone `llm_model`；`build_graph(cloned_config)` 自動綁定同一 limit。
- 公開 `agent.build_graph(config)`：compiled graph 自帶 config limit，不依賴 ChatSession caller 再傳 raw recursion config。
- CLI `--max-graph-steps`：建立 `AgentConfig` 時覆寫該欄位，不再把第二份 recursion 值傳給 `ChatSession`。
- `/status` 與 CLI recursion error：讀同一個 config 欄位。

`AgentConfig` 以同一個 validator 要求 `graph_recursion_limit` 是整數且至少為 3；CLI parser 直接重用該 validator，在建立 session 前拒絕無法走到 finalization node 的 1 或 2。

Citation skill 沒有自己的 graph limit；它啟用時仍使用 normal thinking graph。Aggregator、reviewer 與 prompt rewrite 是直接 model invocation，不是 LangGraph consumer，也不偽裝成 recursion 設定。

## 刪除與保留

已刪除：

- 三個 tool quota config fields、primary/local 分類與 completed-call 計數。
- 每回合注入模型的 `[Tool budgets]` prompt。
- 平行 tool call quota 裁切、primary/local remaining telemetry。
- Proposer config override與 derived recursion formula。
- Base workflow 的「最多 1–3 次 `rag_search`」數字；保留依結果足夠、空白、重複或無關而停止的 evidence-based 規則。

刻意保留：

- `_strip_tool_calls()`：只用於 recursion finalization 與 response repair 等明確要求 no-tool 的 stage；`dropped_tool_calls` 現在代表模型違反 no-tool 契約，不再代表 quota。
- `MAX_REVIEW_ATTEMPTS`：限制外層 review/revise 演算法，LangGraph recursion 無法取代。
- Empty-response retry、OpenRouter/provider retry、candidate/Bash/HTTP/lock timeout：它們處理 transport、上游空回應或資源卡住，不是 agent loop quota。
- Tool access policy、proposer read-only allowlist、bash approval、citation validation/final gate：它們是權限與 correctness boundary。

## Recursion 邊界與 graceful finalization

`AgentState.remaining_steps` 使用 LangGraph `RemainingSteps` managed value，由 framework 注入，呼叫端不保存第二份數字。

目前拓撲為 `skill_loader → agent ↔ tools`。實測邊界：

```text
limit 4: loader rem3 → agent rem2 → 必須直接 final
limit 5: loader rem4 → agent rem3 → tools rem2 → agent rem1 → final
```

因此 `remaining_steps < 3` 時，agent 改用未綁 tools 的 model，注入 no-tool finalization instruction，並機械移除模型仍可能回傳的 structured tool call。有效回答帶有 `finalized:graph_recursion_limit` recovery metadata；不合格回答仍走既有 one-shot repair 與 deterministic fallback。

預設 64 可容納最多約 30 個串行 tool rounds 後再 final。這是依舊工作流至少需要 51 supersteps 所選的 compatibility margin，不是經 live model 證明的最佳 runaway 閾值。多個平行 calls 共用一個 tools superstep，因此這個 fuse 不限制單輪 parallel fan-out，也不是整個 extended user turn 的總成本上限。

## Commit 紀錄

1. `9e1f384 refactor(agent): centralize graph recursion configuration`
   - 將預設 64 寫入 `AgentConfig`；移除 session constant、constructor/create override與 proposer-derived recursion；更新 CLI、status、README及 normal/proposer consumer tests。
2. `347eaf5 refactor(agent): remove per-mode tool call budgets`
   - 刪除三套 quota、graph budget machinery、budget telemetry與 numeric RAG soft cap；保留專用 no-tool strip；新增超過舊 20/4 界線的 deterministic tests。
3. `563b069 fix(agent): finalize before graph recursion limit`
   - 加入 `RemainingSteps`、`<3` graceful cutoff、graph-steps telemetry與 boundary/defiant-model tests。
4. `4a8838c fix(agent): bind graph limit at compilation`
   - 讓公開 `build_graph(config)` 自動綁定 limit；刪除 ChatSession／`execute_graph()` 的 raw recursion plumbing；新增無 invoke override 的回歸測試。
5. `f17b2ed fix(agent): validate graph recursion limit`
   - 在 `config.py` 驗證 limit 至少為 3；CLI parser 重用同一 validator；涵蓋 programmatic config、CLI 與 minimum boundary。

## 驗證結果

修改前 focused baseline：

```bash
cd app
conda run -n app poetry run pytest \
  tests/test_chat_cli.py \
  tests/test_citation_slash_command.py \
  tests/test_thinking_session.py \
  tests/test_graph_skill_loader.py \
  tests/test_observability.py \
  tests/test_tool_inventory.py -q
# 81 passed, 1 warning
```

Single-config focused tests：

```bash
conda run -n app poetry run pytest \
  tests/test_chat_cli.py \
  tests/test_citation_slash_command.py \
  tests/test_thinking_session.py \
  tests/test_turn_finalizer.py \
  tests/test_mcp.py -q
# 98 passed, 1 warning
```

Quota-removal focused tests（第一次與修正 assertion 後使用同一命令）：

```bash
conda run -n app poetry run pytest \
  tests/test_graph_skill_loader.py \
  tests/test_observability.py \
  tests/test_thinking_session.py \
  tests/test_tool_inventory.py \
  tests/test_tool_access_matrix.py -q
# first:     66 passed, 1 failed, 1 warning
# corrected: 67 passed, 1 warning
```

Graceful-cutoff focused tests：

```bash
conda run -n app poetry run pytest \
  tests/test_graph_skill_loader.py \
  tests/test_observability.py \
  tests/test_state.py \
  tests/test_tool_access_matrix.py -q
# 42 passed, 1 warning
```

Compiled-graph binding focused tests：

```bash
conda run -n app poetry run pytest \
  tests/test_graph_skill_loader.py \
  tests/test_thinking_session.py \
  tests/test_turn_finalizer.py \
  tests/test_citation_e2e.py \
  tests/test_history_recall_scenario.py -q
# 85 passed, 1 warning
```

Config/CLI validation focused tests：

```bash
conda run -n app poetry run pytest \
  tests/test_chat_cli.py \
  tests/test_smoke.py \
  tests/test_graph_skill_loader.py -q
# 40 passed, 1 warning
```

各步結果摘要：

```text
baseline focused tests:       81 passed, 1 warning
central config focused tests: 98 passed, 1 warning
quota removal first run:      66 passed, 1 failed, 1 warning
quota removal corrected run:  67 passed, 1 warning
graceful cutoff tests:         42 passed, 1 warning
compiled graph binding tests:  85 passed, 1 warning
config/CLI validation tests:   40 passed, 1 warning
```

Quota removal 第一次失敗是新 test 沿用舊 fallback 英文句子；runtime 已正確回傳 `repair:dropped_tool_calls` 且沒有執行工具。Assertion 改為穩定的 recovery metadata 後，同一組測試全過；production code 不需第二次修正。

最終完整驗證：

```bash
# from repository root
cd app
conda run -n app poetry run pytest
# 694 passed, 1 warning in 5.24s

conda run -n app poetry run python -m agent.cli.chat --help
# --max-graph-steps MAX_GRAPH_STEPS
# Max LangGraph supersteps per graph invocation (default: 64)

cd ..
git diff --check 131875d..f17b2ed
# passed (no output)
```

唯一 warning 是 installed LangGraph cache serializer 的 pending deprecation，與本次變更無關。

全域 tracked-file 搜尋確認 production/tests 已無舊三個 quota、`DEFAULT_RECURSION_LIMIT`、`--max-turns`、primary/local budget telemetry 或 budget prompt。`app/rag/docs/API.md` 的 `HostConfig.max_turns = 12` 是 framework-neutral subclass 文件範例，沒有 production reader，因此未修改。

## 限制與後續判讀

- 本次沒有執行 live paid-model trial，也沒有宣稱現行 GLM 5.2 永遠不會 loop。
- Repository 從初始 commit 起就有 tool cap，沒有可比較的 no-cap live baseline；歷史 C1「8 次 RAG runaway」只剩不可重驗的 code comment。
- `graph_recursion_limit=64` 是 deterministic emergency policy；未來只有在真實 trace 顯示過低或過高時才應調整。
- 直接呼叫 LangGraph runnable 並顯式傳入 invoke-time `recursion_limit` 仍可覆寫 bound config；現行 production/session/CLI 沒有這條第二設定路徑，測試只用它驗證 4／5 邊界。
- 若之後出現成本問題，應量測整個 user turn 的 provider requests、tokens、duration或金額，再設相符的 run-level policy；不要重新用 ToolMessage 數當成本代理。

## 結論

本次修正不再讓 normal、citation 與 proposer 各自維護一套 tight budget。Agent 的工具選擇由模型、skill 指令與既有權限邊界決定；所有 LangGraph invocation 共用 `config.py` 的單一 emergency fuse，並在 hard recursion error 前保留已完成工具結果、產生最佳可用回答。
