# Agent architecture

`agent` 是 chat application package。根層保留 composition roots、穩定 facade 與跨子系統契約；屬於同一 lifecycle 或 policy 的實作則放在 subpackages。

## Package map

| Package | Responsibility |
|---|---|
| `adapters/` | 將 framework-neutral RAG API 轉成 LangChain tools |
| `cli/` | Interactive chat、slash command parsing 與 local command handling |
| `conversations/` | Canonical JSON transcript authority（只接受 schema v3）、validation 與 lifecycle transitions |
| `desktop/` | Python desktop protocol/server、`DesktopService`（dispatch 與生命週期，handler 依職責分在 `*_ops.py`、`approvals.py`、`transcript.py`、`turn_*.py`、`errors.py`）、專案 metadata 與歷史目錄（`project.py`）；`bibliography.*` 的邏輯在 `skills/citation`。測試用的 isolated fixture 在 `tests/support/` |
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
| `ingest.py` | App 對 RAG ingest/sync 的 application entrypoint；也提供每回合的本地工作範圍 `LocalWorkScope`，Stop 靠它收束並取消可控制的本地工作 |
| `mcp.py` | MCP specs、logging 與 async tool loading facade |
| `observability.py` | 跨 turn/workflow 的 redaction-safe telemetry |

因此根層 `.py` 不是「尚未分類」；它們是公開入口或 composition layer。

## One-turn flow

```text
ChatSession.turn_outcome()  [session-wide async lock]
    ├─ ChatSession._begin_turn() → ConversationRepository pending JSON
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
- Canonical JSON是唯一active transcript authority，`ConversationRepository`是唯一writer；normal新回合、context與exact lookup不讀寫conversation Chroma，document RAG也不儲存或搜尋對話。
- Package `__init__.py` 應保持輕量，不 eager re-export 可形成 cycle 的 orchestrators/policies。

## Persistence boundary

- Accepted prompt會先以canonical pending JSON提交，才可呼叫provider／tool；finalization完成後再原子轉成completed並回傳terminal outcome。
- Process重啟時遺留的pending turn會成為interrupted，不會自動重播provider或tool；只有使用相同logical turn ID的明確retry才重新執行。已completed的同ID request直接回復既有結果。
- Canonical JSON是唯一支援的transcript source。Desktop的對話清單直接由掃描專案歷史目錄得到（不再有catalog）；選取的對話若沒有對應的JSON，會回報錯誤並保留目前已選取的session。
- 舊Plan logs、conversation Chroma與舊版的 `desktop-projects.json` 不會被讀取、匯入、改寫或刪除；沒有batch migration入口。
- 模型context固定只取canonical JSON中最新10個completed、eligible conversational turns。
- 重播進模型時，`document_context.replay_history_inputs` 縮減歷史中的文件全文：當前回合帶快照時，舊快照與凍結引用都換成佔位；不帶時只保留最後提交的快照（標明可能早於之後的存檔）。`graph._agent_requests` 另以 `compact_edit_results` 讓同回合只有最新一次 saved `document_edit` 結果帶全文。兩者都只改模型輸入副本，canonical JSON、graph state 與前端收據不變。
- 啟用 `READ_ONLY_DOCUMENT_SKILLS`（目前是 `grill`）的回合，`tool_access_resolution` 會移除 `document_edit`；文件快照照常送進模型。

## Tests and related docs

從 `app/` 使用 `conda run -n app poetry run pytest tests/<target>.py -q` 執行對應測試；完整驗證命令見 [workspace README](../../README.md)。

- [Turn lifecycle](turns/README.md)
- [Extended thinking](thinking/README.md)
- [Tool policy](tools/README.md)
- [Citation subsystem](../skills/citation/README.md)
- [RAG API](../rag/docs/API.md)
