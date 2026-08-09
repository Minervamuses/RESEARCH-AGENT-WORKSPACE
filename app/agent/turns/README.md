# Turn lifecycle

`turns` 存放單一 chat turn 的資料物件與可重用 lifecycle helpers。它不是通用 `models` 或 `utils` 目錄。

## Scope and non-goals

Owns:

- graph execution 結果正規化
- user-visible turn result models
- final-response protocol safety helpers
- recent-turn records 與 prompt assembly
- plan/recent/history journal ordering
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
| `journal.py` | Mutable turn/plan/log state owner 與 recording transaction ordering |
| `store.py` | Recent-window overflow 與 shutdown flush coordination |
| `plan_log.py` | Plan-mode markdown rendering 與 append IO |
| `trace.py` | Tool-call extraction、grouping 與 count formatting |

`trace.py` 是一般 turn tool trace；`thinking/trace.py` 處理 candidate/fusion evidence，`observability.py` 則是 telemetry。

## Lifecycle and persistence

```text
graph/thinking execution
    → GraphTurnResult
    → session finalization and citation policy
    → TurnJournal.record_turn()
         ├─ plan mode: markdown only, never Chroma
         └─ normal mode: recent window → TurnStore overflow → history_rag
    → TurnOutcome
```

## Invariants

- `ChatSession` 擁有整個 turn lock 與呼叫順序。
- `execute_graph()` 無長期 mutable state，不 import `ChatSession`。
- `TurnJournal` 是 counter、recent turns、turn logs、last tool calls 與 plan state 的唯一 owner。
- `TurnStore` 使用 Journal 建立的同一個 recent-turn list，不複製第二份狀態。
- Plan markdown 寫入失敗時，counter、recent turns 與 history 都不得前進。
- Safety/citation finalization 必須在 `record_turn()` 前完成。

## Related docs

- [Agent architecture](../README.md)
- [Workspace operation guide](../../../README.md)
- [Citation subsystem](../../skills/citation/README.md)
