# C7-S6 Busy 判斷的現況對照與共用（S028、U21）

- **日期**：2026-11-22
- **性質**：這是現況對照，不是新的衝突規格。沒有新增拒絕條件、沒有統一 `retryable`、沒有衝突表、鎖階層或全域控制器（R1），沒有回合開始時的待核准檢查（R6）。
- **觸發情境**：這些判斷保護的都是支援的單一工作流程中的循序操作（回合進行或等待核准時切換／改名／刪除對話、開啟專案、關閉）。

## 1. 現況對照（改動前 `01fe7c1`；依各處檢查順序）

`P` = `_project_operation_count`（dispatch 已把本次請求算進去），`R` = `_project_read_count`。「其他工作」= knowledge／extension 進行中、文件 apply 或 tool lock 被持有。

| 檢查點 | 條件 → 錯誤碼／訊息／retryable |
|---|---|
| `_session_create` | 1. `_session_creating` → SESSION_NOT_READY「A desktop session is already being created.」True<br>2. 回合或核准 → BUSY_TURN「A session turn is still active.」**False**<br>3. 其他工作或 `P−R > 1` → SESSION_NOT_READY「A new conversation cannot be created during another operation.」True |
| `_session_select` | 1. 回合或核准 → BUSY_TURN「A conversation cannot be changed during an active turn.」True<br>2. `_session_creating` → SESSION_NOT_READY「A desktop session is already being materialized.」True<br>3. 其他工作或 `P−R > 1` → SESSION_NOT_READY「The selected conversation cannot change during another operation.」True |
| `_session_rename` | 1. 回合或核准 → BUSY_TURN「Wait for the active turn before renaming a conversation.」True<br>2. `_session_creating`、其他工作或 `P−R > 1` → SESSION_NOT_READY「Wait for the current conversation operation before renaming.」True |
| `_session_delete` | 1. 回合或核准 → BUSY_TURN「Stop the active turn and wait for it to finish before deleting.」True<br>2. `_session_creating`、其他工作或 **`P > 1`**（讀取也算） → SESSION_NOT_READY「Wait for the current conversation operation before deleting.」True |
| `_workspace_select` | 1. 回合或核准 → BUSY_TURN「Wait for the active turn before changing project.」**False**<br>2. `_workspace_opening`、`P`（任何 project 請求）、`_session_creating`、`_session_closing`、其他工作 → SESSION_NOT_READY「Wait for the current operation before changing project.」True |
| `_runtime_shutdown` | 0. 已 stopped → 直接回傳<br>1. `_session_creating` → SESSION_NOT_READY「A desktop session is still being created.」True<br>2. 回合或核准 → BUSY_TURN「A session turn is still active.」True<br>3. knowledge → BUSY_KNOWLEDGE_MUTATION「A knowledge mutation is still active.」True<br>4. extension → BUSY_EXTENSION_OPERATION「An extension operation is still active.」True<br>（之後呼叫 `_shutdown_session`） |
| `_shutdown_session` | 1. `_session_creating` → 同上 1<br>2. 回合或核准 → 同上 2<br>3. `_session_closing` → SESSION_NOT_READY「The desktop session is already shutting down.」True<br>4–5. knowledge／extension → 同上 3、4<br>6. 文件 lock 或 `P > allow_current_project_operation` → SESSION_NOT_READY「Wait for the current document or conversation operation.」True |
| `_require_idle_session` | 1. 回合或核准 → BUSY_TURN「A session turn is still active.」True<br>2. knowledge → BUSY_KNOWLEDGE_MUTATION「A knowledge **operation** is still active.」True（與關閉時的 mutation 用字不同，保留）<br>3. extension → BUSY_EXTENSION_OPERATION「An extension operation is still active.」True |

dispatch 層另有 `_workspace_opening`、`_session_closing`、lifecycle 的前置閘門；它們不屬於這 8 處，未改動。因此 handler 內的 `_workspace_opening`、`_session_closing` 條件只能直接呼叫 handler 觸發，測試也這樣做。

## 2. 共用與保留

| 共用 | 用於 | 理由 |
|---|---|---|
| `_turn_or_approval_active`（`_turn_active or _pending_approval is not None`） | 全部 8 處 | 完全相同的條件；各處的訊息與 `retryable` 不同，raise 留在原處 |
| `_document_work_active`（兩個文件 lock） | create、select、rename、delete（經下一列）、workspace、shutdown_session | 完全相同 |
| `_other_operation_active(ignore_reads=...)`（其他工作或另一個 project 請求） | create、select、rename（`ignore_reads=True`）、delete（`False`，註明讀取也算） | 四處只差在是否扣除讀取，參數化後保留差異 |
| `_raise_if_knowledge_or_extension_active(knowledge_message=...)` | runtime_shutdown、shutdown_session、require_idle_session | 三處的兩個 raise 相同，只有 knowledge 訊息在 require_idle 不同，以參數保留 |

保留不共用：`_session_creating`、`_session_closing`、`_workspace_opening` 的單一條件與各自訊息；`_shutdown_session` 的 `P > int(allow_current_project_operation)`；`_workspace_select` 的 `P`（任何 project 請求都擋）。

**所有權**：沒有搬移任何 flag、計數或 lock，擁有者仍是 `DesktopService`；共用的只是查詢。

## 3. 測試覆蓋

新增 `tests/test_desktop_service.py::test_busy_checkpoints_keep_their_codes_messages_and_retryable`（61 個參數）：上表每一列的每個條件各一案，直接呼叫 handler（或 `_require_idle_session`），一次只設一個條件，斷言錯誤碼、訊息與 `retryable` 三者完全相同。先在改動前的程式上通過，再重構後重跑通過。另加 `test_conversation_select_ignores_concurrent_reads_but_delete_counts_them`：同一個「另一個讀取請求」狀態下，select 越過忙碌檢查（落到「專案未開啟」），delete 被擋。

未以參數化涵蓋：`_runtime_shutdown` 進入 `_shutdown_session` 後的條件（已由 `shutdown_session` 參數涵蓋）、`allow_current_project_operation=True` 的放行路徑（既有的刪除選取中對話測試涵蓋）。

## 4. 檢查

- 新測試在改動前 62 passed；改動後沙箱外完整 pytest 1821 passed。
- `grep -n "self._turn_active or self._pending_approval is not None\|_document_apply_lock.locked() or self._document_tool_lock.locked()" app/agent/desktop/service.py` 只剩兩個共用查詢的定義。
