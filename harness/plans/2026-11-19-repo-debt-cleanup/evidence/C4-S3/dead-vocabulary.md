# C4-S3 死 event、streaming 殘留與 Ollama 欄位（U7、S006、S009、S010）

- **日期**：2026-11-22

## 1. 移除

| 項目 | Python | contract | TS | fixtures |
|---|---|---|---|---|
| 12 個未發出的 request event（`request.progress`、`knowledge.progress`、`shutdown.progress`、`collecting.started`、`collecting.completed`、`tagging.started`、`tagging.folder_completed`、`metadata.written`、`writing.started`、`writing.file_completed`、`ingest.completed`、`ingest.failed`） | 無 producer（C1 稽核與 `grep` 確認 agent／rag／skills 皆 0） | `requestEvents` 20 → 8；9 個 `eventDataSchemas` 刪除 | `RequestEventWithoutDataDto` 只剩 `request.started`、`stage.changed`、`tool.*` | 刪除 `ingest-progress-safe-dto`、`ingest-progress-rejects-source-text`；`request-event-without-sequence`、3 個 trace（`out-of-order-event`、`post-terminal-event`、`event-without-known-request`）與 raw line `numeric-equivalent-sequence` 原本拿 `request.progress` 當泛用 event，改用仍存在且沒有 data schema 的 `stage.changed`。 |
| `streamKind`、`chunkCount` | `service.py` 3 處 result 與 wire budget 候選中的兩個欄位 | `session.turn` result schema 的兩個欄位 | `TurnCompletedDto` 的兩個欄位；`conversations.ts` 的 `AnswerStreamKind` 型別、`AuthoritativeTurnResult`／`FinalConversationAnswer`／`LiveTurn` 中的欄位與其拒絕條件；`App.tsx` 兩處 | `retired-answer-chunk-is-rejected`（仍因 `answer.chunk` 未知而無效）與 `conversation-protocol-safe-dtos` 中的欄位 |
| `ollamaReachable`、`ollamaModelAvailable` | `runtime.diagnostics` 兩個永遠是 `None` 的欄位 | `runtime.diagnostics` result schema 的兩個欄位 | `RuntimeDiagnosticsDto`、`BoundedRuntimeDiagnostics`、`toBoundedDiagnostics`；`App.tsx` runtime 細節的「Ollama」「Ollama model」兩列與只供它們使用的 `availabilityLabel` | `diagnostics-safe-result-dto`、`diagnostics-rejects-unlisted-result-data` 中的欄位（後者仍因 `providerState` 未列出而無效） |

`tests/protocol_types.test.ts` 的 `DTO_EXCEPTIONS` 現在是空物件。

Rust：`backend.rs` 測試的假 backend 原本送 `request.progress` 與 `streamKind`／`chunkCount`；Rust 已不驗 event 名稱與 result 欄位，但為了讓測試資料代表現行 Python 輸出，改送 `stage.changed`，並刪除大 result 的兩個欄位與對應斷言。

`grep -rn "streamKind\|chunkCount\|ollamaReachable\|ollamaModelAvailable" app/agent app/desktop/src app/desktop/tests app/desktop/protocol`：0 筆。

## 2. 測試改名與合併（S009：併入一般 turn 測試）

- `app/tests/test_desktop_answer_stream.py` → `app/tests/test_desktop_turn_results.py`（docstring 改為一般的 turn result 測試）。其中「答案只出現在 completed、persisted 的 terminal result」「不呼叫 event sink」「失敗與取消不產生答案 event」等斷言保留。改名的測試：`test_final_only_answer_does_not_call_the_event_sink` → `test_answer_does_not_call_the_event_sink`、`test_answer_past_the_old_single_item_limit_is_returned_whole_and_final_only` → `…_returned_whole`。
- `app/desktop/tests/answer_stream.test.ts` → `app/desktop/tests/conversation_turns.test.ts`；測試名稱中的 final-only／nonzero-chunk 字樣刪除。
- 其他改名：`test_real_service_round_trip_registration_restore_and_final_only_answer` → `…_and_complete_answer`、`test_phase07_integrated_final_only_skill_tool_restore_journey` → `test_phase07_integrated_skill_tool_restore_journey`、`test_large_complete_answer_is_written_as_one_final_only_result` → `…_as_one_result`。
- `for_agents/` 仍提到舊檔名（`invariants.md`、`testing-strategy.md`、`known-failure-modes.md`），依限制不修改，列入最終彙報的過時條目。

## 3. 測試退役紀錄

| 被刪的斷言或測試案例 | 它保護的行為（或已刪除的細節） | 留下的證據 |
|---|---|---|
| Python 測試中 36 行 `streamKind == "final_only"`／`chunkCount == 0` 斷言與 result 字面量中的欄位（`test_desktop_turn_results.py` 10、`test_desktop_fixture.py` 16、`test_desktop_server.py` 4、`test_desktop_service.py` 5、`test_skill_adherence.py` 1） | 已刪除的常數欄位 | 同一批測試其餘的「答案完整、只在 terminal result」斷言保留；`test_desktop_protocol_contract.py` 改為斷言兩個欄位不在 `session.turn` result schema。 |
| `conversation_turns.test.ts`「…fail closed」中 `streamKind: "post_finalized"` 與 `chunkCount: 1` 兩個無效輸入 | `conversations.ts` 對兩個已刪除欄位的拒絕條件 | 同測試其餘的跨 session 與格式錯誤輸入保留。 |
| `protocol.test.ts`「normal answers…」中兩個欄位的 schema 斷言 | 已刪除的 schema 欄位 | 改名為「normal answers use only the terminal result」，保留 `answer.chunk` 不存在與 text 無 `maxBytes`；Python 契約測試斷言兩個欄位不存在。 |
| `test_desktop_service.py` 的 `diagnostics["ollamaReachable"] is None` | 永遠是 null 的欄位（已刪除） | 改為斷言兩個欄位不在 diagnostics 中。 |
| fixtures `ingest-progress-safe-dto`、`ingest-progress-rejects-source-text` | 已刪除的 `writing.file_completed` event 的資料規則 | 無；event 已不存在。 |

## 4. fixture 涵蓋（C3-S5 的統計腳本）

```
bibliography.add             valid=  2  invalid=  1
bibliography.export          valid=  6  invalid=  9

methods: 27; lacking a valid or an invalid fixture: 2
  MISSING project.list {'valid': 2, 'invalid': 0}
  MISSING session.retry_registration {'valid': 1, 'invalid': 0}
```

只剩 C6 會移除的 `project.list`（缺非法例）與 `session.retry_registration`。

## 5. 檢查結果

- `pytest tests/test_desktop_*.py tests/test_skill_adherence.py tests/test_project_permissions.py`（沙箱外）：552 passed。
- `npm test`：224 pass, 0 fail；`npm run build`：通過。
- `cargo test --locked`（沙箱外）：35 passed。

## 6. GUI 清單項目

- runtime 細節（Local runtime details）不再顯示「Ollama」與「Ollama model」兩列。
