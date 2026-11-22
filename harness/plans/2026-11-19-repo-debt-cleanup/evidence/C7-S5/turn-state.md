# C7-S5 U17：每回合參數

- **日期**：2026-11-22
- **觸發情境**：「一個回合中途失敗或結束後，下一個回合在同一對話開始」——支援的正常使用。不新增鎖、排程或拒絕條件（R1），也不在回合開始時檢查待核准項目（R6）。

## 1. 盤點（改動前，`bcaf6da`）

### desktop 寫進 `ChatSession` 的回合狀態

| 狀態 | 寫入 | 讀取者 | 還原 |
|---|---|---|---|
| `session._document_turn_active` | `_run_session_turn` 有 documentContext 時設 True | `ChatSession.tool_access_resolution`（強制加 `document_edit`、`bibliography_lookup`）、`_build_tool_availability_hint`、`run_graph_turn`（effective tools 寫入 skill state）；fixture 的文件 seam | `_session_turn` 的 `finally`：只在 `_active_document_context is not None` 時設 False |
| 文件回合強制的 thinking mode | 同上，`session.set_thinking_mode("normal")` | `turn_outcome` 的 `effective_mode`、`_run_turn`（extended 走 fusion）、prompt history | 同一個 `finally`：`session.set_thinking_mode(previous_mode)`（會再驗證，可能拋錯） |
| `session._skill_installer.bypass_approval` | `_session_turn` 開始時設為 `permission == "bypass"`（所有回合） | `SkillInstaller` 的更新確認（`manager.py` 952、1013） | `finally` 設回 False |

### `DesktopService` 自己的 10 個回合欄位

| 欄位 | 設定 | 主要讀取者 | 原本的還原 |
|---|---|---|---|
| `_turn_event_sink` | `_run_session_turn` 開頭 | prompt-persisted callback、文件編輯、單次核准、進度事件、bash 核准 | `finally` 設 None；開專案時不動 |
| `_turn_loop` | 同上 | bash 核准（另一執行緒）| `finally` 設 None |
| `_active_parent_request_id` | 同上（非字串時 None） | 文件編輯、單次核准、工具核准、`document.apply`、bash 核准 | `finally` 設 None |
| `_active_turn_id` | 同上 | 同上，另有核准擁有者比對 | `finally` 設 None |
| `_active_turn_permission_mode` | 同上 | prune 確認、文件候選、單次與一般核准、bash 核准 | `finally` 設 None；開專案時設 None |
| `_active_document_context` | resolve 出 documentContext 後 | 文件編輯、儲存後推進 working context、reference 投影 | `finally` 設 None；開專案時設 None |
| `_active_references` | submittedContext 的 references | 文件編輯、儲存後推進 reference ranges、prompt 投影 | `finally` 設 `[]` |
| `_active_editor_path` | 同 documentContext | 文件編輯的 reference 路徑比對 | `finally` 設 None |
| `_tool_names` | 開頭設 `{}` | 進度事件補工具名稱 | `finally` 設 `{}`；開專案時 clear |
| `_tool_summaries` | 開頭設 `{}` | 進度事件、final-text 驗證、turn result | `finally` 設 `{}`；開專案時 clear |

## 2. 變更

- **`agent/session.py`**：新增 frozen dataclass `TurnOptions(document_turn=False, thinking_mode=None, permission_mode="ask")`。`turn_outcome(..., options=None)` 在取得回合鎖後設定 `_document_turn_active`、`_skill_installer.bypass_approval` 與（有指定時）這一回合的 thinking mode，於同一方法的 `try/finally` 還原；原本的回合本體移到 `_locked_turn_outcome`，內容不變。使用者以 `session.set_thinking` 選的 mode 只被暫時覆寫，回合結束一定還原（直接還原屬性，不再經過可能拋錯的 `set_thinking_mode` 驗證）。CLI 不傳 `options`，等同「一般回合、Ask」，與原本相同。
- **`agent/desktop/service.py`**：10 個欄位移進 `_TurnWork`（`event_sink`、`loop`、`permission_mode`、`document_context`、`references`、`editor_path`、`tool_names`、`tool_summaries`，加上原有的 `turn_id`、`parent_request_id`），在回合開始時建立。讀取者一律經由 `_running_turn`：回合結束時 `_session_turn` 把 `owner.finished` 設為 True，`_running_turn` 就回傳 None——即使 Stop 清理失敗、`_turn_work` 仍需保留給 Retry Stop，舊回合的值也讀不到。刪除 `finally` 裡逐欄還原的 14 行、開專案時清欄位的 4 行，以及對 session 的 `_document_turn_active`、`set_thinking_mode`、`bypass_approval` 寫入；改為把 `TurnOptions(document_turn, "normal" if document_turn else None, owner.permission_mode)` 傳給 `turn_outcome`。
- **fixture 與假 session**：`turn_outcome` 接受 `options`；fixture 的文件 seam 改讀 `options.document_turn`。`test_project_permissions.py` 的 `ToolSession` 改記錄 `options.permission_mode`，另一個測試改為建立 `_TurnWork` 紀錄，不再逐欄設定 service 私有欄位。

## 3. 測試

| 驗收 | 測試（`tests/test_desktop_document_service.py`） |
|---|---|
| (a) 文件回合中途拋錯後，下一個一般回合沒有強制的 `document_edit`，thinking mode 是使用者選的值 | `test_failed_document_turn_leaves_no_document_tools_or_forced_thinking`：使用者選 extended，文件回合在模型呼叫時看到 normal 與 `document_edit`，拋錯後 mode 回到 extended、有效工具不含 `document_edit`、`_running_turn` 為 None；接著的一般回合看不到 `document_edit` |
| (b) Bypass 回合之後改回 Ask，installer 不略過核准 | `test_installer_bypass_follows_each_turns_permission`：兩個回合在模型呼叫時看到的 `bypass_approval` 依序是 True、False，結束後為 False |
| (c) 帶文件與 references 的回合結束後，下一回合看不到上一回合的文件 context、references、editor path | `test_document_and_references_do_not_carry_into_the_next_turn`：第一回合的 prompt 有 snapshot 與 frozen references 區塊，第二回合的 `_running_turn` 三個值都是空的，prompt 沒有這兩個區塊，工具也沒有 `document_edit` |

既有的 `assert service._active_references == [] and service._active_document_context is None`（2 處）改為 `service._running_turn is None`。

## 4. 檢查

- 沙箱外完整 pytest：1759 passed（+3）；改名 helper 後 desktop 模組 525 passed。
- `grep -nE "bypass_approval|_document_turn_active" app/agent/desktop/`：0。
- `set_thinking_mode` 在 `agent/desktop/service.py` 只剩兩處：選取對話時套用該對話的控制快照（`target.set_thinking_mode(control_snapshot.thinking_mode)`），與 `session.set_thinking` 的處理（`session.set_thinking_mode(params["mode"])`）。
- 10 個舊欄位名稱在 `service.py` 的 grep：0（每回合值只出現在 `_TurnWork` 的定義與經由 `_running_turn` 的讀取）。
