# Phase 06 — 退役 conversation-history Chroma

Status: In progress

## Objective

移除對話歷史專用的 Chroma store、`recall_history` tool、eviction/flush/cap 路徑與其 active prompts/allowlists，同時完整保留 document RAG 的 Chroma/Ollama dependencies、tools、tests，以及 Bash approval 中需要的 `grep`/`read_file` 能力。

Legacy Chroma conversation reader 只留給非破壞 migration；舊 `<persist_dir>/chat_history` 不刪除。

## In Scope

1. 移除 normal runtime 的 `ChatHistoryStore` construction/injection/query/persist/flush。
2. 移除 `recall_history` tool registration、prompt instructions、schemas、allowlists 與 tests。
3. 刪除不再有責任的 `TurnStore` eviction/flush/hard-cap drop 行為和相關錯誤/telemetry。
4. 將 conversation legacy Chroma reader 收斂在 migration-only boundary。
5. 以 import/residue/representative tests 證明 document RAG 仍使用其原有 Chroma/Ollama stack，conversation create 不依賴 Ollama。
6. 在Python產生的session/tool system guidance與既有`/status`輸出中顯示經驗證、bounded的canonical conversation root，讓使用者與agent知道可在何處做approval-gated exact-text grep；此資訊本身不得繞過Bash approval。

## Non-goals

- 不移除 `app/rag/`、document ingestion/retrieval、`chromadb`, `langchain-chroma` 或 `langchain-ollama` dependencies。
- 不移除一般 Bash tool、approval workflow、`grep` 或 `read_file`。
- 不刪除使用者 legacy Chroma directory。
- 不建立 semantic conversation search 的 replacement。
- 不修改 canonical JSON schema 或 migration policy。

## Dependencies and prerequisites

- Phase 03/04 已證明 canonical transcript write/read/restore authority 都使用 JSON；Phase 05 已移除 Plan runtime。
- 先用 imports、constructors、tool inventory、prompt text 與 tests 建立 conversation-Chroma 和 document-RAG 的精確邊界圖。
- 特別檢查 dependency ownership：同一 package 仍被 document RAG 使用時，不得從 manifest/lock 移除。
- 檢查 Bash allowlist/read tool tests，避免用廣泛字串刪除誤傷研究能力。

## Expected components

預期變更：

- `app/agent/history_rag/` 的 runtime modules，保留或搬移最小 migration reader
- `app/agent/turns/store.py`, `journal.py`, memory/session 中殘餘 legacy caller
- `app/agent/tools/` inventory 與 prompt/access policy 中的 `recall_history`
- history recall、eviction、flush 相關 tests；strict legacy reader coverage 移至 `test_conversation_migration.py`
- `app/rag/` production code與 dependency manifests 不在本階段變更範圍；若無法在不修改它們的情況下保留行為，停止並取得新授權

## Authorization and stop conditions

本階段沒有 dependency-change 授權。若 package manifest 看似可移除 Chroma/Ollama，但仍被 document RAG 使用，必須保留。若 conversation legacy reader 與 document RAG 無法在不重構 shared layer 的情況下分離，先停下提供實際 import graph 與最小選項。

不得以刪除 `chat_history` directory 驗證成功；所有使用者資料保留。

## Implementation and verification plan

### Preflight

1. 以`git grep --untracked`搜尋 `ChatHistoryStore`, `recall_history`, `chat_history`, `flush_recent_turns`, eviction/cap error codes，以及 Chroma/Ollama imports，確保未stage的新檔也納入。
2. 將結果分類為 active conversation runtime、migration-only、document RAG、historical docs/tests。
3. 執行最小 document RAG offline baseline tests，記錄移除前結果。

### Red

先建立/更新測試以證明：

- 新 Session/Desktop conversation 即使沒有 Ollama/chat-history collection 也能 create 與處理 stubbed turn。
- Tool inventory、help/prompt 與 access policy 不再含 `recall_history`。
- A→B→A 與 shutdown 不呼叫 legacy flush，也沒有 flush failure error contract。
- Legacy Chroma fixture 仍可由 migration importer 讀取。
- Document RAG 的 config/store/retrieval offline tests 仍使用原有 backend contract。
- System guidance與`/status`可見實際canonical root；使用fake approval flow的journey能由exact-text grep找到fixture prompt，再以`read_file`讀取，而paraphrase miss不呼叫RAG/embedding fallback。

### Green

1. 先移除 leaf consumers（prompt/tool registration/UI error mapping），再移除 runtime store injection 與 flush/cap branches。
2. 將 importer 所需的 strict read code放在 migration-only namespace；normal runtime 不得 import。
3. 刪除只為 history recall 存在的 schemas/tests/config，但保留同名 dependency 的 document RAG用途。
4. 更新 active user/help text，明確以最近 10 個 JSON completed turns 提供 context，不宣稱 semantic chat recall。
5. 從同一validated config path把canonical root加入session/tool guidance與`/status`文字；保持bounded/SafeContent輸出，不新增silent filesystem tool或permission bypass。

### Refactor

- 移除 dead imports、dead error codes 與本次退役造成的空 wrapper。
- 不重構 document RAG，不改 embeddings、collection 或 ingestion behavior。
- 不引入 replacement search/index/cache。

### Verification

從 `app/` 執行精確的 agent safety 與小型 RAG regression 集合：

```bash
conda run -n app poetry run pytest tests/test_conversation_migration.py tests/test_tool_inventory.py tests/test_tool_access.py tests/test_tool_access_matrix.py tests/test_bash_tool.py tests/test_read_file_tool.py tests/test_skill_runtime.py tests/test_citation_gate.py tests/test_thinking_session.py tests/test_desktop_conversations.py tests/rag/test_config.py tests/rag/test_component_flow.py tests/rag/test_tools_contract.py -q
```

若測試在本階段被搬移或重新命名，build log 必須列出 replacement selector 與保留的行為覆蓋。使用 `git grep --untracked` 做 residue audit；禁止啟動 Ollama、下載 model 或做 live embeddings。

## Reliability, security, and recovery

- Legacy Chroma 是只讀 recovery source，永不由 cleanup code刪除。
- Active runtime 不再有 bounded-memory eviction 後 silent drop 的 durable風險；JSON 是唯一 authority。
- Tool removal 不能擴大 Bash permission；`grep`/`read_file` 仍受原 approval/policy 約束。
- Document RAG regression 需用現有 offline fixtures/mocks 驗證，不能以 dependency import 成功代替實際代表測試。

## Acceptance Criteria

- [ ] Active agent/desktop runtime 不 construct、write、query 或 flush conversation-history Chroma。
- [ ] `recall_history` 不在 tool inventory、prompt、help、policy 或 protocol 中。
- [ ] Legacy Chroma strict reader 僅由 migration boundary 使用，來源資料保留。
- [ ] Document RAG 的 Chroma/Ollama code、dependencies 與代表 tests 保持可用。
- [ ] Bash approval、`grep`、`read_file` 與 Citation/Skills 沒有退化。
- [ ] Conversation create/restore 在 Ollama 不可用時仍可於 stubbed/offline test 工作。
- [ ] Agent與使用者能從system guidance/`/status`得知validated canonical root；exact-text grep→`read_file`有approval-gated journey，paraphrase miss不fallback到embedding/RAG。
- [ ] Residue search 的剩餘 chat-history references 全部是 migration/historical/harness 用途。

## Evidence to record

在 build log 記錄 import/residue 分類、移除的 runtime call chain、保留的 RAG dependency理由、移除前後 focused test 命令與 exit code。若任一 document RAG test 因本階段失敗，Phase 06 不得標 Completed。

## Handoff

Phase 07 只做 migration wiring、fault/journey驗證與 active docs 收尾。若 active runtime 還有任何 conversation Chroma write/query/flush，先完成 Phase 06，不要用最終 residue allowlist 掩蓋。
