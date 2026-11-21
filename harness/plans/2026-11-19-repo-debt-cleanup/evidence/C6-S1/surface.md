# C6-S1 registration、catalog 與 `project.list` 的觸點盤點

- **日期**：2026-11-22
- **基準**：HEAD `c7b9de4`（C5 完成）。行號以此為準。

## 1. 後端 `app/agent/desktop/service.py`

| 觸點 | 位置 | C6 處置 |
|---|---|---|
| import `DesktopProjectCatalog`、`load_project_catalog` | 58、61 | 改 import `open_project_history`（模組改名見 §5） |
| 建構參數 `project_catalog`、`self._catalog`、`self._injected_catalog` | 350、382、384 | 刪除（`_injected_repository` 保留） |
| `self._session_registered`、`self._pending_registration` | 391–392；設定於 983–989、1125–1126、1147–1148、1640–1648、2086–2105、2112–2128、3444–3445、3456–3457 | 刪除 registration；「這個 session 是否已有存檔的 prompt」改用單一旗標 `_session_saved`（`_on_prompt_persisted` 設 True、`session.select` 設 True、`session.create`／關閉設 False），只用於切換時是否保存該 session 的控制快照（原本以 `_session_registered` 判斷）。 |
| dispatch `project.list` → `_project_list` | 462、834–861 | 刪除（U19） |
| dispatch `session.retry_registration` → `_session_retry_registration` | 468、1104–1155 | 刪除（U3） |
| `_workspace_opening` 放行集合中的 `project.list` | 517 | 刪除該項 |
| `_session_list`：`reconcile` 參數、`_reconcile_lagged_catalog_entries()`、`_require_catalog_project` 的 `sessionIds` | 864–895 | 改由 `repository.scan()` 的 summaries 推導，依 `(created_at, conversation_id)` 排序；刪除 `reconcile` |
| `_session_select`／`_session_rename`／`_session_delete` 以 `project["sessionIds"]` 判斷歸屬 | 922、1022、1066–1072 | 改為檢查專案與對話檔（`_load_conversation` 的 project 比對） |
| `_session_delete` 的 `self._catalog.unregister_session`／失敗時 `register_session` | 1089–1099 | 刪除；只刪對話檔 |
| `_reconcile_lagged_catalog_entries` | 1267–1279 | 刪除 |
| `_require_catalog_project` | 1304–1322 | 改為只檢查 `project_id` 是開啟中的專案 |
| `_on_prompt_persisted` 呼叫 `_register_saved_session` | 1520 | 改為設定 `_session_saved = True` |
| `_session_create` 回傳 `"registered": False` | 1653 | 刪除欄位 |
| `_session_select` 回傳 `"registered": True` | 937、999 | 刪除欄位 |
| wire budget 候選中的 `registrationStatus`／`registrationIssue` | 1683–1684 | 刪除 |
| `_register_saved_session`、`_saved_session_registration_result` | 2082–2130 | 刪除 |
| `_workspace_select` 呼叫 `load_project_catalog` 與 injected catalog 置換、`self._catalog = catalog` | 2167–2184 | 改呼叫 `open_project_history`，只保留 repository |
| `session.turn` 兩處結果的 `registrationStatus`／`registrationIssue` | 3191–3206、3290–3305 | 刪除 |

## 2. `app/agent/desktop/catalog.py`

| 觸點 | 位置 | C6 處置 |
|---|---|---|
| `CATALOG_FILENAME`、`CATALOG_MAX_*`、`DEFAULT_PROJECT_ID`、`DEFAULT_PROJECT_NAME`、`_validate_snapshot`、`_encode_snapshot`、`_validate_project_id`、`_validate_project_name`、`is_canonical_session_id`、`_SESSION_ID_RE` | 18–135 | 刪除（`is_canonical_session_id` 先 grep 是否有其他使用者）；保留一個具名常數記錄殘留檔名，供 `initialize_project` 的空目錄檢查容許 |
| `DesktopProjectCatalog`（`snapshot`、`project_for_session`、`register_session`、`unregister_session`、`rebuild_from_conversations`（S018）、`reconcile_conversations`、`_load_or_bootstrap`、`_read_existing`、`_write_temp`、`_create_absent`、`_atomic_replace`） | 144–411 | 刪除 |
| `_scoped_catalog`、`_check_catalog_owner` | 690–702 | 刪除（U11：空目錄歸屬檢查消失） |
| `load_project_catalog` | 705–750 | 改為 `open_project_history(project_id, history_directory) -> ConversationRepository`，只做三項 fail-closed 檢查（目錄存在、scan 無 issue、所有對話的 `project_id` 相符） |
| `initialize_project` 中建立 catalog 檔、讀現有 catalog 檢查擁有者 | 753–840 | 不再建立或讀取；「目錄必須為空」仍容許殘留的 `desktop-projects.json` |
| bootstrap（`_load_or_bootstrap`） | 319–334 | 隨類別刪除 |

## 3. contract、TS 與 `App.tsx`

| 觸點 | 位置 | C6 處置 |
|---|---|---|
| contract `project.list`（方法與 result schema） | contract | 刪除 |
| contract `session.retry_registration`（方法與 result schema） | contract | 刪除 |
| contract `session.turn` result 的 `registrationStatus`、`registrationIssue` | contract | 刪除 |
| contract `session.create`／`session.select` result 的 `registered` | contract | 刪除（只供 registration 狀態與 `cataloged`／`transient` 文字使用） |
| contract `session.list` 參數 `reconcile` | contract | 刪除 |
| TS `ProjectListDto`、`ProjectSummaryDto`、`RegistrationRetryDto`、`SessionCreatedDto.registered`、`SessionSelectedDto.registered`、`TurnCompletedDto.registrationStatus`／`registrationIssue`、`MethodResults` 兩列 | `src/protocol.ts` | 刪除 |
| `loadSelectedProjectHistory`（專案數不等於 1 時 throw） | `App.tsx` 204–219 | 改為只呼叫 `session.list` |
| `catalog` state 與其讀寫 | `App.tsx` 1026、1374、1611、1718、1999–2003、2200–2206、2748–2750 | 刪除；sidebar 改為單一專案清單 |
| 選取恢復 effect | `App.tsx` 2199–2206（以 `catalog.selectedSessionId` 或 `resumeSelectionRef`） | 改讀開啟中專案 ID 與 `resumeSelectionRef`；判斷抽成純函式 |
| retry registration UI 與 state（`registrationIssue`、`retryRegistration`、通知區塊） | `App.tsx` 1047、2385–2392、2580–2590、2839 | 刪除 |
| `cataloged`／`transient` 文字 | `App.tsx` 2891 | 刪除；session meta 只留 session ID 與回合數 |
| `registered: true` 的派送 | `App.tsx` 1936、2380、2454、2588 | 刪除 |
| 多專案 scaffolding（`catalog?.projects.map(...)`） | `App.tsx` 2750 起 | 改為單一專案清單（S070） |
| sidebar 的「Not saved yet」暫存列（`transient` 列屬性） | `App.tsx` 128、151、166、2765、2913 | **保留**：它代表尚未第一次送出的記憶體內 session，與 catalog 無關；計劃要刪的是 session meta 的 `cataloged`／`transient` 文字。 |

## 4. GOALS A7：`project.list` 的 `selectedSessionId`

- 後端（`_project_list` 858–861）只在 `self.session` 不為 None 時回傳非 null，即「後端此刻持有一個 session」。
- 前端只在 `conversation.selected === null` 時才用它（`App.tsx` 2200–2206：先用同專案的 `resumeSelectionRef`，否則才用 `catalog.selectedSessionId`）。
- 前端選取變成 null 的時機：初始狀態、`backend-generation-changed`（`conversations.ts` 462–475：新後端還沒有 session）、開啟專案（`workspace.select` 先 `_shutdown_session()`）、刪除選取中的對話（後端同時關閉 session，前端把 `selectedSessionId` 清成 null，1999–2003）。在這些時機後端都沒有 session，`selectedSessionId` 一律是 null。
- 前端重新載入（WebView reload）時，前端沒有開啟中的專案，必須重新 `workspace.select`，後端也會先關閉 session。
- **結論**：支援的流程中，選取恢復完全依賴 `resumeSelectionRef`（C2-S8 的 `planBackendSnapshotTransition` 在 generation 改變時擷取）；`selectedSessionId` 不需要移到 `session.list`。

## 5. 模組名稱

移除 catalog 類別後，`catalog.py` 只剩專案 metadata（`RESEARCH.md`）、`inspect_project`、`initialize_project`、`project_citation_settings`、`update_project_metadata` 與開啟歷史目錄的函式，所以依步驟規格改名為 `agent/desktop/project.py`，並更新所有 import（`service.py`、`fixture_session.py` 與 8 個測試模組）。例外類別一併改名為 `ProjectError`、`ProjectUnavailableError`、`ProjectMalformedError`、`ProjectConflictError`（約 29 處），避免 `project.py` 中留下 catalog 的名稱。

## 6. 其他觸點

- `app/agent/desktop/fixture_session.py`：seed 時以 `DesktopProjectCatalog.register_session` 寫 catalog（574–585）、檢查 catalog 檔不是 symlink（559）、`FixtureSessionFactory` 以 catalog 的 `project_for_session` 避開已用的 session ID（1397–1430）→ 改為不寫 catalog，以 repository 是否已有該對話檔判斷。
- 測試：`test_desktop_conversations.py`（catalog 類別單元測試 530–758、重啟發現延遲登記 1129、registration 1465–1760 等）、`test_desktop_fixture.py`（144、216、1020、1323）、`test_desktop_service.py`（23、1148）、`test_desktop_server.py`、`test_desktop_crash_recovery.py`、`test_desktop_bibliography.py`、`test_desktop_document_service.py`、`test_citation_project_library.py`、`test_skill_adherence.py`（import 改名）；TS `tests/conversations.test.ts` 等讀 `registered` 的測試在 C6-S3 處理。
