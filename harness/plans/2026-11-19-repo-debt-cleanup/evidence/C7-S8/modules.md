# C7-S8 `service.py` 模組化（S034、S123 一部分）

- **日期**：2026-11-22，commit `845a1d8`（S8a）至 `4fb187e`（S8f）。
- **做法**：只搬移、不改行為。每組 handler 原封不動搬到 `agent/desktop/<模組>.py` 的一個類別（`_XxxOps`），`DesktopService` 繼承這些類別；方法內的 `self` 仍是 `DesktopService`，所以 handler 之間的呼叫、測試對 `service._x` 的 monkeypatch 都不變。被搬走的方法用到的模組層級常數、dataclass 與函式一起搬到第一個使用它的模組，其他模組再從那裡 import。搬移以 AST 切片工具完成（同目錄的 [`split_service.py`](split_service.py) 與 [`fixup_imports.py`](fixup_imports.py)：前者搬文字，後者補上缺少的 desktop 模組 import、刪除未用的 import；不從 `service.py` import，以免循環）。
- **為什麼用繼承的類別**：phase-07 只允許「搬移程式」。把方法改成接收 service 的函式，需要改寫每個 `self.` 呼叫與上百處測試的 monkeypatch；保留 `self` 是唯一不改方法本體的搬法。這些類別沒有狀態、沒有 `__init__`，也不被單獨使用，不是新的抽象層。

## 1. 模組與行數

| 模組 | 行數 | 內容 |
|---|---|---|
| `service.py` | 4157 → **461** | `DesktopService`：dispatch 表、生命週期、接線 |
| `errors.py`（S8a） | 258 | `DesktopServiceError`（S035）、`EventSink`、logger（名稱固定為 `agent.desktop.service`，log 與測試不變）、`_with_turn_lifecycle`、`_map_exception` 一族（S034）、`_KNOWLEDGE_MUTATIONS` |
| `approvals.py`（S8b） | 325 | 單次核准、工具／文件／Bash 核准、核准回應、`_PendingApproval`、secret 判斷 regex |
| `bibliography_ops.py`（S8b） | 301 | `bibliography.*` handler 與 lookup（S123 的一部分） |
| `document_ops.py`（S8c） | 317 | `document.open/save/apply`、`document_edit` 工具、候選與 working context、`_DocumentCandidate` |
| `extension_ops.py`（S8c） | 607 | `extensions.*` handler、`/extension-management`、DTO 與 apply report |
| `command_ops.py`（S8d） | 501 | `/init /ingest /sync /prune`、路徑檢查、`DesktopKnowledgeOperations`、`_PrunePreview` |
| `transcript.py`（S8d） | 214 | `session.transcript` 與 summary／transcript DTO |
| `turn_context.py`（S8e） | 152 | `_submitted_turn_context`、reference 投影與 snapshot／reference 說明文字 |
| `turn_ops.py`（S8e） | 680 | `session.turn`、Stop／Retry Stop、進度事件、結果檢查、`_TurnWork` |
| `conversation_ops.py`（S8f） | 486 | `session.list/create/select/rename/delete/set_thinking/set_permission`、控制快照、session snapshot |
| `project_ops.py`（S8f） | 121 | `workspace.select`、專案守衛、專案規則與 system prompt |

模組名稱與提案的差異：多了 `turn_ops.py`（回合 handler 本體）、`conversation_ops.py`、`project_ops.py`、`transcript.py` 以外的 `turn_context.py` 只放凍結 context；提案的 `command_ops.py` 只放知識指令，`/extension-management` 跟著 extension handler 放在 `extension_ops.py`。

## 2. `service.py` 剩下的方法

| 方法 | 分類 | 說明 |
|---|---|---|
| `__init__` | 接線 | 建立狀態、注入依賴與 dispatch 表 |
| `permission_mode`（property） | 接線 | 對外唯讀的 Permission |
| `dispatch` | dispatch | 生命週期閘門、project 請求計數、錯誤對照 |
| `_runtime_diagnostics` | 生命週期 | `runtime.diagnostics`：後端程序與執行環境狀態 |
| `_runtime_shutdown`、`_shutdown_session`、`_clear_session_caches` | 生命週期 | 關閉後端與目前 session |
| `_require_session`、`_require_idle_session` | 接線（共用守衛） | 多個模組的 handler 都經由 `self` 使用 |
| `_turn_or_approval_active`、`_document_work_active`、`_other_operation_active`、`_raise_if_knowledge_or_extension_active` | 接線（共用忙碌查詢，C7-S6） | 8 個檢查點分散在 conversation／project／生命週期，放在這裡讓各模組不互相 import |
| `_utc_timestamp`、`_bounded_text`、`_bounded_cache_insert` | 留下的理由：共用小工具 | 被幾乎所有模組經由 `self` 使用；搬到任一模組都會讓其他模組依賴它，留在組合它們的類別最單純 |

沒有任何 handler 本體留在 `service.py`。

## 3. 唯一的非純搬移修改

- `errors.py` 的 logger 由 `logging.getLogger(__name__)` 改成 `logging.getLogger("agent.desktop.service")`，保留原本的 logger 名稱。
- `transcript.py` 的 `DesktopService._tool_activity_payload(activity)`（staticmethod 呼叫）改成 `_TranscriptOps._tool_activity_payload(activity)`，避免反向 import `service.py`。
- `tests/test_grill_skill.py` 改從 `agent.desktop.turn_context` import 三個說明文字常數。其他測試 import 的 `DesktopService`、`DesktopServiceError`、`DesktopKnowledgeOperations`、`_TurnWork` 仍可從 `agent.desktop.service` 取得（再匯出）。

模組間 import（皆無循環）：各模組都只依賴 `errors`、`documents`、`project`、`protocol` 等底層模組；另有 `command_ops`、`turn_ops` 從 `extension_ops` 取 `_MAX_LOCAL_COMMAND_BYTES`，`extension_ops` 從 `approvals` 取 secret regex，`conversation_ops` 從 `turn_ops` 取桌面指令名稱集合，`turn_ops` 從 `turn_context` 取說明文字。

## 4. 檢查

- 每個 commit 後：`python -c "import agent.desktop.server"` 通過，desktop 相關測試（600／653／775／775／803／803 個）全部通過。
- 最後：沙箱外完整 pytest 1827 passed。
