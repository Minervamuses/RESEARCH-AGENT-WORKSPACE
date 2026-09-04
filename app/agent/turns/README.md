# Turn lifecycle

`turns` 存放單一 chat turn 的資料物件與可重用 lifecycle helpers。它不是通用 `models` 或 `utils` 目錄。

## Scope and non-goals

Owns:

- graph execution 結果正規化
- user-visible turn result models
- final-response protocol safety helpers
- recent-turn records 與 prompt assembly
- process-local journal observability 與 legacy recent-history compatibility
- tool-call trace normalization

Does not own:

- session lock、thinking mode 或 active skill
- graph construction
- extended-thinking orchestration
- citation domain logic
- Chroma/JSON store implementation

## Result levels

- `GraphTurnResult` 是 graph 或 extended execution 產生的內部結果；它可含 tool trace、recovery metadata 與 candidate traces。
- `TurnOutcome` 是 response safety、citation gate/render 與 recording 完成後的 user-visible 結果。

兩者不可互換；未 finalized 的 `GraphTurnResult.answer` 不得直接寫入 recent memory 或 persistence。

## Module map

| Module | Responsibility |
|---|---|
| `results.py` | `GraphTurnResult` 與 `TurnOutcome` |
| `execution.py` | Stateless graph streaming、message/call collection 與 recovery metadata |
| `safety.py` | User-visible response 與 tool-protocol artifact checks |
| `memory.py` | `TurnRecord` 與 recent prompt history assembly |
| `journal.py` | Process-local recent-turn、tool 與 diagnostic observation state |
| `store.py` | Legacy recent-window overflow 與 shutdown flush compatibility |
| `trace.py` | Tool-call extraction、grouping 與 count formatting |

`trace.py` 是一般 turn tool trace；`thinking/trace.py` 處理 candidate/fusion evidence，`observability.py` 則是 telemetry。

## Lifecycle and persistence

```text
ChatSession._begin_turn()
    → ConversationRepository pending JSON
    → graph/thinking execution
    → GraphTurnResult
    → session finalization and citation policy
    → ConversationRepository completed JSON
    → TurnJournal.observe_turn() process-local diagnostics
    → TurnOutcome
```

## Invariants

- `ChatSession` 擁有整個 turn lock 與呼叫順序。
- `execute_graph()` 無長期 mutable state，不 import `ChatSession`。
- `TurnJournal` 是 recent turns、turn logs 與 last tool calls 的 process-local owner。
- `TurnStore` 使用 Journal 建立的同一個 recent-turn list，不複製第二份狀態。
- Accepted prompt 必須在 provider/tool 執行前成為 canonical pending turn。
- Safety/citation finalization 必須在 canonical completed transition 前完成；完成寫入後才可回傳 terminal outcome。
- Legacy Plan v1/v2 parser 位於 `agent.conversations` migration boundary，不由一般 turn execution import，且不寫回來源檔。

## Related docs

- [Agent architecture](../README.md)
- [Workspace operation guide](../../../README.md)
- [Citation subsystem](../../skills/citation/README.md)
