# Extended thinking workflow

`thinking` 實作 optional extended mode。Normal mode 由 `agent.graph` 直接處理，不經過這個 workflow。

## Workflow

```text
rewrite request
    → isolated proposer candidates
    → aggregate candidate panel
    → review / revise loop
    → final validation
    → session finalization and recording
```

`FusionOrchestrator` 負責流程協調，但 graph execution、citation gate 與 turn persistence 仍回到 session/turn collaborators。

## Module map

| Module | Responsibility |
|---|---|
| `orchestrator.py` | Proposer panel、aggregation、review/revise 與 final validation |
| `schemas.py` | Candidate、review、route 與 metadata models |
| `prompts.py` | Rewrite、aggregate 與 review message construction |
| `parsers.py` | Structured model-output parsing |
| `review.py` | Review routing、retry limits 與 aggregation helpers |
| `trace.py` | Candidate-scoped evidence/tool trace summarization |

## Boundaries and invariants

- Candidates 必須相互隔離；不可依賴可能重複的 `tool_call_id` 跨 candidate 配對。
- Proposer 只能綁定 `orchestrator.py` 中明確允許的 read-only tools。
- Reviewer/reviser 只看見 session 明確提供的 context 與 evidence summary。
- Citation skill active 時不允許 extended mode，避免在平行 candidates 間分享 source registry。
- 每個完成分支都必須通過 `ChatSession.finalize_and_record()`。
- `thinking.trace` 是 fusion evidence trace，不是通用 turn trace 或 telemetry。

Model IDs、token limits 與 retry defaults 以 `agent.config` 與實作為準，不在此複製。

## Related docs

- [Agent architecture](../README.md)
- [Turn lifecycle](../turns/README.md)
- [Workspace `/thinking` guide](../../../README.md)
- [Skills 與 Extended Thinking](../../SKILLS_GUIDE.md)
