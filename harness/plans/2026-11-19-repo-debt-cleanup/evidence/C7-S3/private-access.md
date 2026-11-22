# C7-S3 ChatSession 私有存取盤點（A5）與 orchestrator 公開介面（S052、S043）

- **日期**：2026-11-22，盤點於 `a741327`（C7-S2 之後）。
- **產品邊界**：純改名與 inline，行為不變。

## 1. A5 盤點：`agent/` 中 `session.py` 以外存取 `ChatSession` 私有成員之處

指令：`grep -rnE "session\._[a-z]|getattr\([a-z_.]*session[a-z_]*, \"_[a-z]" agent --include=*.py | grep -v "^agent/session.py"`，另以 `grep -noE "(self\._session|session)\._[a-z_]+" agent/thinking/*.py` 補抓 `self._session._x` 形式。

| 位置 | 成員 | 處理 |
|---|---|---|
| `thinking/orchestrator.py` | `_tool_availability_block()` | C7-S3 → `tool_availability_block()` |
| 同上 | `_base_prompt_history()` | C7-S3 → `base_prompt_history()` |
| 同上 | `_operation_approval_handler`（屬性，2 處） | C7-S3 → `operation_approval_handler` |
| 同上 | `_execute_graph(...)` | C7-S3 → `execute_graph(...)` |
| 同上 | `_run_graph_turn(...)`（2 處） | C7-S3 → `run_graph_turn(...)` |
| 同上 | `_prompt_master_skill_text()` | C7-S3 → `prompt_master_skill_text()` |
| 同上 | `_visible_context_text()` | C7-S3 → `visible_context_text()` |
| 同上 | `_active_skill_context_block()` | C7-S3（S043）inline 到這個唯一呼叫者後刪除 |
| `desktop/service.py` | `getattr(session, "_conversation_snapshot")` | C7-S4 |
| 同上 | `_set_final_text_validator`、`_set_prompt_persisted_callback` | C7-S4 |
| 同上 | `getattr(self.session, "_citation_policy")` | C7-S4 |
| 同上 | `getattr(self.session, "_installer_context")`、`getattr(self.session, "_skill_installer")`（2 處） | C7-S4（installer context）／C7-S5（installer bypass） |
| 同上 | `session._document_turn_active = ...`（2 處） | C7-S5 |
| 同上 | `session._load_skill_runtime(name)`、`getattr(session, "_load_skill_runtime")` | C7-S4 |

其他命中不是 `ChatSession`：`desktop/server.py` 的 `context._terminal`（server 自己的 request context）、`DesktopService._tool_activity_payload`（類別自己的 staticmethod）。A5 的假設（私有存取集中在 orchestrator 與 desktop service）成立。

## 2. 變更

- `agent/session.py`：上述 7 個成員改為公開名稱（定義與 session 內部呼叫同步）；刪除 `_active_skill_context_block`。
- `agent/thinking/orchestrator.py`：改用公開名稱；新增 `TurnHost(Protocol)`，列出 orchestrator 用到的全部 session 成員（`config`、`conversation_repository`、`active_skill_runtime`、`extra_tools`、`operation_approval_handler`、`tool_access_resolution`、`tool_availability_block`、`base_prompt_history`、`visible_context_text`、`prompt_master_skill_text`、`execute_graph`、`run_graph_turn`、`finalize_and_record`），`FusionOrchestrator.__init__` 的 `session` 型別改為 `TurnHost`，不再 import `ChatSession`。skill context 在原呼叫處直接取 `active_skill_runtime.context_block()`。
- 測試改走新名稱：`test_history_retirement.py`、`test_document_context_budget.py`、`test_tool_access_matrix.py`、`test_citation_skill_activation.py`（原本呼叫已刪除的 `_active_skill_context_block()`，改為對 `active_skill_runtime.context_block()` 做相同斷言）。`_prompt_master_skill_text_cache` 沒有改名，測試對它的設定不在本步範圍。

## 3. 檢查

- 沙箱外完整 pytest：1756 passed（含 `test_thinking_session.py`）。
- `grep -rnE "session\._[a-z]" app/agent/thinking/`：0。
