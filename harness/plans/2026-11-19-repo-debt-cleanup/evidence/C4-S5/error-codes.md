# C4-S5 錯誤碼 producer 盤點（P3）

- **日期**：2026-11-22
- **方法**：對 contract 的每個錯誤碼，以 `grep -rn '"<CODE>"'` 搜尋 `app/agent`、`app/skills`、`app/rag`（`*.py`）與 `app/desktop/src-tauri/src`（Rust），列出 producer 位置。只出現在集合常數（例如 `_SELF_EXPLANATORY_FAILURE_CODES`）的引用不算 producer；下表的「producer 例」都是實際建立 `DesktopServiceError`／`ProtocolError`／`BridgeError` 或 `_map_exception` 回傳值的位置。
- **結論**：25 個錯誤碼都有 producer，**本步沒有移除任何錯誤碼**。`OLLAMA_*`、`BUSY_KNOWLEDGE_MUTATION`、`RAG_*`、`PRUNE_PREVIEW_STALE` 經由斜線指令 `/init /ingest /sync /prune` 與 `_map_exception` 的 knowledge 分支產生（GOALS A3）。C5、C6 完成後由 C10-S0 複查。

| 錯誤碼 | Python 引用數 | Rust 引用數 | producer 例 |
|---|---:|---:|---|
| `PROTOCOL_INVALID` | 60 | 18 | `agent/desktop/server.py:138` |
| `PROTOCOL_VERSION_UNSUPPORTED` | 1 | 5 | `agent/desktop/protocol.py:443` |
| `RUNTIME_WRONG_CONDA_ENV` | 1 | 9 | `agent/desktop/server.py:467` |
| `SESSION_NOT_READY` | 29 | 0 | `agent/desktop/service.py:497` |
| `OPENROUTER_NOT_CONFIGURED` | 2 | 0 | `agent/desktop/service.py:635` |
| `OLLAMA_UNREACHABLE` | 1 | 0 | `agent/desktop/service.py:700` |
| `OLLAMA_MODEL_MISSING` | 1 | 0 | `agent/desktop/service.py:683` |
| `GRAPH_LIMIT_REACHED` | 2 | 0 | `agent/desktop/service.py:629` |
| `BUSY_TURN` | 12 | 0 | `agent/desktop/service.py:873` |
| `TURN_CANCELLED` | 4 | 0 | `agent/desktop/server.py:316` |
| `BUSY_KNOWLEDGE_MUTATION` | 5 | 0 | `agent/desktop/service.py:2928` |
| `BUSY_EXTENSION_OPERATION` | 8 | 0 | `agent/desktop/service.py:663` |
| `INVALID_PATH` | 12 | 0 | `agent/desktop/service.py:676` |
| `RAG_READ_FAILED` | 7 | 0 | `agent/desktop/service.py:720` |
| `RAG_WRITE_FAILED` | 7 | 0 | `agent/desktop/service.py:712` |
| `RAG_PARTIAL_WRITE_POSSIBLE` | 1 | 0 | `agent/desktop/service.py:707` |
| `PRUNE_PREVIEW_STALE` | 2 | 0 | `agent/desktop/service.py:1915` |
| `EXTENSION_PREVIEW_FAILED` | 2 | 0 | `agent/desktop/service.py:660` |
| `EXTENSION_APPLY_FAILED` | 9 | 0 | `agent/desktop/service.py:658` |
| `APPROVAL_DENIED` | 4 | 0 | `agent/desktop/service.py:2724` |
| `PROVIDER_RATE_LIMITED` | 1 | 0 | `agent/desktop/service.py:642` |
| `PROVIDER_REQUEST_FAILED` | 1 | 0 | `agent/desktop/service.py:652` |
| `BIBLIOGRAPHY_CONFLICT` | 1 | 0 | `agent/desktop/service.py:2243` |
| `BIBLIOGRAPHY_FAILED` | 3 | 0 | `agent/desktop/service.py:2244` |
| `INTERNAL_ERROR` | 24 | 3 | `agent/desktop/server.py:72` |

## C10-S0 複查（2026-11-22，`6e97400`）

C5、C6 完成、C7 拆分 `service.py` 之後重做 producer 檢查：25 個錯誤碼仍都有 producer，沒有新的死錯誤碼，不移除任何錯誤碼。producer 位置因 C7-S8 模組化而移到 `errors.py`、`project_ops.py`、`command_ops.py`、`approvals.py`、`bibliography_ops.py` 等，完整輸出見 `evidence/C10-S0/vocabulary.md`。
