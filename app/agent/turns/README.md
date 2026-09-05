# Turn lifecycle

`turns` 存放單一 chat turn 的資料物件與可重用 lifecycle helpers。它不是通用 `models` 或 `utils` 目錄。

## Scope and non-goals

Owns:

- graph execution 結果正規化
- user-visible turn result models
- final-response protocol safety helpers
- canonical completed-turn view
- process-local journal observability
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

兩者不可互換；未finalized的`GraphTurnResult.answer`不得寫入canonical completed state或作為terminal outcome回傳。

## Module map

| Module | Responsibility |
|---|---|
| `results.py` | `GraphTurnResult` 與 `TurnOutcome` |
| `execution.py` | Stateless graph streaming、message/call collection 與 recovery metadata |
| `safety.py` | User-visible response 與 tool-protocol artifact checks |
| `memory.py` | Canonical completed-turn view |
| `journal.py` | Process-local tool 與 diagnostic observation state |
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
- `TurnJournal`只擁有turn logs與last tool calls；不持久化transcript。
- Canonical JSON是目前唯一active transcript authority，`ConversationRepository`是唯一writer；normal新回合、context與exact lookup不使用conversation Chroma。
- 模型context只取最新10個completed、context-eligible conversational turns；display-only command turn不進context。
- Accepted prompt 必須在 provider/tool 執行前成為 canonical pending turn。
- Safety/citation finalization 必須在 canonical completed transition 前完成；完成寫入後才可回傳 terminal outcome。
- 重啟會把遺留pending turn恢復成interrupted，且不自動重播provider/tool；failed或interrupted turn只有明確retry才重新執行，completed同ID則回復既有結果。
- Canonical JSON是唯一支援的transcript source；舊Plan logs與conversation Chroma不由turn execution或Desktop selection讀取或匯入，來源保持不變。

## Related docs

- [Agent architecture](../README.md)
- [Workspace operation guide](../../../README.md)
- [Citation subsystem](../../skills/citation/README.md)
