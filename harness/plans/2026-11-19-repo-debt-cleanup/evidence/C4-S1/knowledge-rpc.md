# C4-S1 刪 10 個 `knowledge.*` RPC（U2）

- **日期**：2026-11-22

## 1. 刪除前的 grep（GOALS A3：只刪 RPC 專用的符號）

在刪除前的 `service.py` 副本上 grep 每個符號（排除定義行），並 grep `agent`、`skills`、`rag`、`tests` 其他檔案：

```
_knowledge_overview | service.py lines (non-def): 484 | other files: none
_knowledge_search | service.py lines (non-def): 485 | other files: none
_knowledge_list_chunks | service.py lines (non-def): 486 | other files: none
_knowledge_get_context | service.py lines (non-def): 487 | other files: none
_knowledge_init_workspace | service.py lines (non-def): 488 | other files: none
_knowledge_ingest_file | service.py lines (non-def): 489 | other files: none
_knowledge_ingest_folder | service.py lines (non-def): 490 | other files: none
_knowledge_sync | service.py lines (non-def): 491 | other files: none
_knowledge_prune_preview | service.py lines (non-def): 492 | other files: none
_knowledge_prune_apply | service.py lines (non-def): 493 | other files: none
_hit_dto | service.py lines (non-def): 3693,3712 | other files: none
_prune_previews | service.py lines (non-def): 414,3503,3818,3833,3846,3854 | other files: none
```

- 第 484–493 行是 dispatch 表的 10 個項目；`_hit_dto` 的 3693、3712 行在 `_knowledge_search`／`_knowledge_list_chunks` 內；`_prune_previews` 的 414 行是初始化、3503 行是 `_clear_session_caches` 的 `clear()`、3818–3854 行在 `_knowledge_prune_preview`／`_knowledge_prune_apply` 內。沒有 RPC 以外的呼叫者。
- 刪除 handler 後無人使用而一併刪除的 import：`from rag import explore, get_context, list_chunks, search`、`import math`（只有 `_hit_dto` 使用）。

## 2. 保留（A3）

`_map_exception` 的 knowledge 分支與 `_KNOWLEDGE_MUTATIONS`、錯誤碼 `OLLAMA_UNREACHABLE`／`OLLAMA_MODEL_MISSING`／`BUSY_KNOWLEDGE_MUTATION`、`_knowledge_count`／`_knowledge_string_items`／`_knowledge_diff_paths`、`_knowledge_active`／`_knowledge_operation`、`_PrunePreview` 與 `_composer_prune_preview`、`DesktopKnowledgeOperations`、`_prune_digest`、`_bounded_cache_insert`（extension preview 仍用）、`TEXT_EXTENSIONS`／`_EXTENSIONLESS_INGEST_FILES`（composer `/ingest` 仍用）、`diff_folder`／`prune_folder`／`ingest_file` 的 import（`DesktopKnowledgeOperations` 仍用），以及 contract approval operation enum 中 4 個 `knowledge.*` 值與 `trust.tsx` 的標籤。

## 3. contract、TS、fixtures

- contract：`methods` 從 40 個減為 30 個，沒有 `knowledge.` 開頭的方法；approval enum 仍有 `knowledge.init_workspace`、`knowledge.ingest_file`、`knowledge.ingest_folder`、`knowledge.prune_apply`。contract 以保留原排版的方式逐項刪除（解析位置後刪除該項並驗證語意結果）。
- TS：`MethodWithoutResultDto` 刪除 10 個方法名；`tests/protocol_types.test.ts` 的 `METHODS_WITHOUT_RESULT_SCHEMA` 同步。knowledge 方法沒有 result schema，所以沒有 DTO 要刪。
- fixtures：刪除 `knowledge-search-bounded-filters`、`knowledge-search-k-out-of-range`、`prune-apply-with-server-preview`、`prune-apply-missing-preview`；`unicode-path-with-spaces` 原本以 `knowledge.ingest_file` 測含中文與空白的路徑，改用仍存在的 `document.open`，保留這個輸入分區。

## 4. 測試退役紀錄

| 被刪或改寫的測試 | 它保護的行為（或已刪除的細節） | 留下的證據 |
|---|---|---|
| `test_desktop_service.py::test_knowledge_pagination_drops_raw_metadata` | `knowledge.list_chunks` RPC 的分頁與 `_hit_dto` 丟棄原始 metadata（RPC 與 `_hit_dto` 已刪） | 無對應的保留行為；`rag_*` 工具的輸出合約由 `tests/rag/test_tools_contract.py` 保留。 |
| `test_desktop_service.py::test_desktop_path_guard_rejects_non_linux_paths`（3 例） | `_validated_path` 拒絕相對路徑、Windows 路徑、空字串（經 RPC） | `test_composer_knowledge_paths_fail_closed_before_injected_operations` 的 `/ingest relative.md`、`/ingest ~/paper.md`、`/ingest C:\\Users\\paper.md`、`/ingest`（無參數）。 |
| `test_desktop_service.py::test_desktop_path_guard_rejects_symlinked_parent` | `_validated_path` 拒絕父目錄是 symlink 的檔案（經 RPC） | 同一個 composer 測試新增 `/ingest {linked}/paper.md`（父目錄是 symlink 的檔案）。 |
| `test_desktop_service.py::test_single_file_ingest_rejects_unsupported_and_extension_state` | 不支援的檔案類型與 extension 狀態檔被拒絕 | 改寫為 `test_composer_ingest_rejects_unsupported_and_extension_state`，經 `/ingest` 走同一個 `_validated_path` 與檔案類型檢查，斷言不變。 |
| `test_desktop_service.py::test_single_file_ingest_rejects_zero_chunks_and_maps_ollama_failures` | 0 chunk 為 `RAG_WRITE_FAILED`；Ollama 缺模型為 `OLLAMA_MODEL_MISSING`；provider 錯誤為 `RAG_WRITE_FAILED` | 改寫為 `test_composer_ingest_rejects_zero_chunks_and_maps_ollama_failures`，經 `/ingest` 走同一個 `_map_exception("knowledge.ingest_file", …)` 分支。原本的 `details == {"partialWritePossible": True}` 改為斷言 `retryable is True`：`session.turn` 失敗的 `error.details` 依 contract 只能是 turn lifecycle 四個欄位，所以 composer 路徑本來就看不到 `partialWritePossible`（見第 5 節）。 |
| `test_desktop_service.py::test_folder_ingest_waits_for_structured_progress_step` | `knowledge.ingest_folder` RPC 永遠回「not enabled yet」（RPC 已刪） | 無；composer `/ingest <目錄>` 的成功路徑由 `test_composer_knowledge_commands…`（`ingested 1 files`）覆蓋。 |
| `test_project_permissions.py::test_direct_index_rpc_mutators_have_correlated_approval`（6 例，S036） | `knowledge.ingest_file`／`knowledge.prune_apply` RPC 的核准與 `parentRequestId` 關聯 | 同檔 composer 參數化測試（`/ingest` 檔案與目錄、`/prune`；ask 核准／拒絕、bypass）已覆蓋核准次數與效果；本步在其中新增 `event["parentRequestId"] == sink.request_id`，保留關聯斷言。 |

## 5. 觀察（交給最終彙報）

composer `/ingest` 遇到 Ollama 錯誤時，桌面端收到的 `error.details` 只有 turn lifecycle（contract 的 `turnErrorDetailsSchema` 要求 `session.turn` 失敗只帶這四個欄位），`partialWritePossible` 只存在於已刪除的 RPC 路徑。這是既有行為，不是本步造成；錯誤碼與訊息仍會顯示。若需要讓使用者知道可能已部分寫入，需要另外的設計決定。

## 6. 檢查結果

- `pytest tests/test_desktop_*.py tests/test_project_permissions.py tests/test_slash_commands.py tests/test_chat_cli.py tests/rag/ tests/test_academic_skill_tools.py tests/test_state.py`（沙箱外）：621 passed。包含 `/init /ingest /sync /prune` 斜線指令、核准、錯誤對照與 `rag_*` 工具。
- `npm test`（含 DTO 一致性檢查）：224 pass, 0 fail；`npm run build`：通過。
