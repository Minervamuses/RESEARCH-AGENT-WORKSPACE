# Agent architecture

`agent` 是 chat application package。根層保留 composition roots、穩定 facade 與跨子系統契約；屬於同一 lifecycle 或 policy 的實作則放在 subpackages。

## Package map

| Package | Responsibility |
|---|---|
| `adapters/` | 將 framework-neutral RAG API 轉成 LangChain tools |
| `cli/` | Interactive chat、slash command parsing 與 local command handling |
| `conversations/` | Canonical JSON persistence、catalog-independent validation 與唯讀 legacy migration |
| `extensions/` | Drop-in discovery、validation、registry、apply 與 startup loading |
| `llm/` | App-layer model construction 與 text normalization |
| `skills/` | Skill metadata、runtime、tool broker 與 agent integration policy |
| `thinking/` | Optional extended-thinking workflow |
| `tools/` | Tool implementation、inventory、access resolution 與 execution enforcement |
| `turns/` | 單回合 results、execution、safety、journal 與 persistence helpers |

## Why modules remain at the package root

| Module | Why it stays here |
|---|---|
| `config.py` | 整個 application runtime 的中央設定 |
| `graph.py` / `state.py` | LangGraph 組裝與 graph state contract |
| `session.py` | Stateful public facade、turn lock 與跨子系統呼叫順序 |
| `startup.py` | 整合 built-in skills、verified extensions 與 MCP 的 session bootstrap |
| `paths.py` | 跨 extensions、tools、skills 的路徑解析 |
| `ingest.py` | App 對 RAG ingest/sync 的 application entrypoint |
| `mcp.py` | MCP specs、logging 與 async tool loading facade |
| `observability.py` | 跨 turn/workflow 的 redaction-safe telemetry |

因此根層 `.py` 不是「尚未分類」；它們是公開入口或 composition layer。

## One-turn flow

```text
ChatSession.turn_outcome()  [session-wide async lock]
    ├─ ConversationRepository.begin_turn() → pending JSON
    ├─ normal → graph → turns.execution.execute_graph()
    └─ extended → thinking.orchestrator.FusionOrchestrator
                         ↓
              GraphTurnResult
                         ↓
       ChatSession.finalize_and_record()
          ├─ generic response safety
          ├─ CitationSessionPolicy gate/render
          ├─ ConversationRepository.complete_turn()
          └─ TurnJournal.observe_turn()
                         ↓
                    TurnOutcome
```

## Dependency rules

- `session.py` 協調順序，不重新實作 graph execution、citation policy 或 turn persistence。
- `turns/` 不擁有 session lock、thinking mode 或 active skill。
- `thinking/` 只負責 extended mode，完成後仍回到 session 的單一 finalization path。
- `tools/` 定義能力與強制 policy；tool implementation 不決定 session access。
- `conversations/` 是對話durability與legacy import的唯一authority；document RAG不儲存或搜尋對話。
- Package `__init__.py` 應保持輕量，不 eager re-export 可形成 cycle 的 orchestrators/policies。

## Tests and related docs

從 `app/` 使用 `conda run -n app poetry run pytest tests/<target>.py -q` 執行對應測試；完整驗證命令見 [workspace README](../../README.md)。

- [Turn lifecycle](turns/README.md)
- [Extended thinking](thinking/README.md)
- [Tool policy](tools/README.md)
- [Extensions](extensions/README.md)
- [Citation subsystem](../skills/citation/README.md)
- [Skills 規範](../SKILLS_GUIDE.md)
- [RAG API](../rag/docs/API.md)
