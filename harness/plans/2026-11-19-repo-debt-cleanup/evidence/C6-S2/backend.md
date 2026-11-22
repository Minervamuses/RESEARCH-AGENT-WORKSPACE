# C6-S2 後端：對話清單由掃描推導（U3、U11、U19）

- **日期**：2026-11-22
- **產品邊界**：所有新增或保留的檢查都對應**支援的循序使用**——開啟一個專案、列出、選取、改名、刪除它的對話；後端重啟或 crash 後重新開啟。沒有為同時操作新增任何協調。

## 1. 程式變更

| 位置 | 變更 |
|---|---|
| `agent/desktop/catalog.py` → `agent/desktop/project.py` | 刪除 `DesktopProjectCatalog`、`_scoped_catalog`、`_check_catalog_owner`、`load_project_catalog`、`rebuild_from_conversations`、`reconcile_conversations`、bootstrap、`CATALOG_FILENAME`／`CATALOG_MAX_BYTES`、`is_canonical_session_id`。例外改名為 `ProjectError`、`ProjectUnavailableError`、`ProjectMalformedError`、`ProjectConflictError`。新增 `project_conversations(project_id, repository)`（一次 scan；有 issue → `ProjectUnavailableError`；有他專案對話 → `ProjectConflictError`；依 `created_at`、`conversation_id` 排序）與 `open_project_history(project_id, history_directory)`（歷史目錄或 `conversations/` 不是目錄 → `ProjectUnavailableError`，再呼叫 `project_conversations`）。`initialize_project` 不再建立 catalog 檔；「目錄必須為空」容許 `conversations` 與具名常數 `LEGACY_CATALOG_FILENAME`（註明「C6 之前留下的檔案，永不讀取或寫入」）。 |
| `agent/desktop/service.py` | 刪除 `project_catalog` 參數、`_catalog`、`_injected_catalog`、`_session_registered`、`_pending_registration`、`project.list` 與 `session.retry_registration` 的 dispatch 與 handler、`_reconcile_lagged_catalog_entries`、`registrationStatus`／`registrationIssue`（turn result 與 wire 預算）、create／select 的 `registered`。`session.list` 以 `project_conversations`（`asyncio.to_thread`）推導，移除 `reconcile`。新增 `_require_opened_project` 與 `_require_saved_conversation`：後者只在事件迴圈做一次 `path_for(...).is_file()`（不合法的 ID 也回 `PROTOCOL_INVALID`），擁有權仍由各 handler 原本在 thread 中的讀取（`ConversationConflictError`）把關。`_session_registered` 原本兼管「切換時是否保存控制快照」，改由 `_session_saved`（第一個 prompt 存檔後為 true）承擔。開啟專案改用 `open_project_history`。刪除只刪對話檔。 |
| `agent/desktop/fixture_session.py` | 不再種 catalog，也不檢查 catalog symlink；`FixtureSessionFactory` 不收 catalog。 |
| `desktop/protocol/v1/contract.json` | 刪除 `project.list`、`session.retry_registration` 方法與 schema、`session.turn` 的 `registrationStatus`／`registrationIssue`、create／select 的 `registered`、`session.list` 的 `reconcile`。方法數 27 → 25。 |
| `desktop/protocol/v1/fixtures.json` | 刪除 `project-list-request`、三個 `session.list` reconcile fixtures；trace `conversation-protocol-safe-dtos` 去掉 `project.list`、retry 步驟與 registration 欄位。覆蓋腳本：25 個方法皆有 fixture。 |

**A7**：C6-S1 結論是 `selectedSessionId` 不需要，所以 `session.list` 的 result 沒有加它。

**GOALS U11 的後果**（已接受）：空歷史目錄不再有歸屬保護，不實作擁有者標記檔；目錄有對話之後的歸屬檢查照舊（測試 (d)）。

**一處先修後改**：第一版 `_require_saved_conversation` 直接呼叫 `_load_conversation`，在事件迴圈上同步讀整個對話檔。`test_conversation_change_blocks_turn_during_read[select|rename]` 抓到這點（被 patch 成會等待的讀取把事件迴圈卡住 5 秒）。改成只做存在檢查後通過；選取、改名、transcript 的讀取仍在 thread 中，且在 `_session_creating` 關閉 gate 之後。

## 2. 驗收測試對照

| 項目 | 測試 |
|---|---|
| (a) 歷史已有 3 個對話，開啟後列出 3 個 | `test_desktop_service.py::test_restart_lists_conversations_already_saved_in_project_history` |
| (b) 新 session 第一次送出前不在清單、送出後在 | `test_desktop_conversations.py::test_new_session_is_listed_only_after_its_first_saved_prompt`、`test_first_prompt_is_listed_before_provider_failure`（provider 失敗前就已在 scan 中）、`test_desktop_fixture.py::test_real_service_round_trip_listing_restore_and_complete_answer` |
| (c) 刪除後不在清單 | `test_delete_stopped_conversation_does_not_revive_or_remove_other_files`、`test_delete_unlink_failure_restores_index_and_can_retry_without_changing_selection`（刪除失敗時仍列出，重試後消失） |
| (d) 混入他專案對話時拒絕開啟 | `test_unknown_project_orphan_requires_mapping_without_changing_history`（服務層）、`test_open_project_history_refuses_foreign_conversations`（函式層，檔案未改寫） |
| (e) 殘留 `desktop-projects.json` 時照常開啟，內容與 mtime 不變 | `test_desktop_fixture.py::test_legacy_catalog_file_is_left_untouched_when_project_opens`（開啟、列出、新增對話後比對 bytes 與 `st_mtime_ns`）、`test_initialize_accepts_history_holding_only_a_legacy_catalog_and_never_touches_it`（初始化）、`test_service_lists_saved_history_in_creation_order_and_ignores_legacy_catalog`、`test_unknown_degraded_unavailable_and_busy_coordinator_states` 末段 |
| (f) 有壞掉的對話檔時拒絕開啟 | `test_malformed_conversation_blocks_incomplete_history_scan_without_writes` |
| (g) 歷史目錄或 `conversations/` 不存在時拒絕開啟 | `test_missing_history_or_conversations_directory_refuses_open[history|conversations|history_is_file]`：缺目錄時回 `needs_initialization`（只提供明確初始化，不開啟）；路徑是檔案時 `PROTOCOL_INVALID`；三種情況 `_conversation_repository` 都是 None、沒有建立 session，`open_project_history` 直接呼叫也拒絕 |
| S027 掃描次數 | `test_desktop_service.py::test_session_list_scans_history_once_per_call`：每次 `session.list` 恰好 1 次 scan，scan 讀 2 個檔各一次（原本有 reconcile 時是 2 次 scan、6 次 load，第二次 1 次 scan、4 次 load），兩次結果相同 |

## 3. 退役紀錄

被刪的測試 → 它保護的行為（或已刪除的細節） → 留下的證據

- `test_catalog_bootstraps_only_the_exact_default_schema` → catalog 檔的預設內容（U3 刪除 catalog） → 無需替代；(e) 確認不再建立 catalog 檔。
- `test_catalog_registration_is_ordered_and_idempotent` → catalog 登記順序與冪等（已刪除） → 清單順序改由 scan 排序，`test_service_lists_saved_history_in_creation_order_and_ignores_legacy_catalog`、`test_restart_lists_completed_json_saved_after_seed_without_replay`（同時間依 ID）。
- `test_catalog_malformed_existing_file_is_not_overwritten` → 壞掉的 catalog 不被覆寫（已刪除；catalog 不再讀寫） → (e) 的 bytes／mtime 比對。
- `test_catalog_rejects_an_oversized_existing_file` → catalog 大小上限（已刪除） → 無；檔案不再被讀取。
- `test_catalog_duplicate_session_across_projects_fails_closed` → 同一 session 在 catalog 中屬於兩個專案（已刪除） → 擁有權由對話檔的 `project_id` 決定：(d) 兩個測試。
- `test_catalog_failed_replace_keeps_memory_and_durable_file` → catalog 原子寫入失敗（已刪除） → 無；沒有 catalog 寫入。
- `test_catalog_rejects_noncanonical_uuid4_session_ids`（4 個參數） → catalog 拒絕非正規 session ID → 新增 `test_conversation_methods_reject_noncanonical_session_ids`（5 個參數，含 `../` 路徑；select／rename／delete／transcript 都回 `PROTOCOL_INVALID`，歷史目錄不變）。
- `test_catalog_only_missing_json_blocks_open_without_fake_transcript` → 「catalog 有、對話檔不在」時拒絕開啟（phase-06「隨 U3 消失的行為」第 1 項） → 遺失的對話只是不在清單：(c)。
- `test_registration_failure_is_pending_and_retry_does_not_rerun_turn` → registration 失敗為 pending 與 `session.retry_registration`（已刪除） → 無；對話存檔即在清單，(b)。
- `test_acceptance_and_catalog_registration_fail_independently[catalog]` → catalog 寫入失敗時 turn 仍完成且 registration 為 pending（已刪除） → `[event_delivery]` 參數保留並改名為 `test_turn_acceptance_survives_event_delivery_failure`。
- `test_malformed_existing_catalog_is_rebuilt_from_canonical_conversations` → 壞 catalog 由對話重建（S018 的 rebuild，已刪除） → 改寫為 (e) `test_legacy_catalog_file_is_left_untouched_when_project_opens`。

改寫（行為改變，保留名稱以外的斷言）：`test_restart_discovers_pending_json_when_catalog_registration_lagged` → (a)；`test_session_list_reconciles_json_created_after_service_start` → `test_session_list_shows_json_created_after_project_open`；`test_sidebar_refresh_skips_repeat_scans_without_changing_session_dtos` → S027；`test_seed_is_deterministic_and_restart_preserves_catalog_order` → `..._lists_conversations_in_creation_order`；`test_coordinator_preserves_scoped_membership_order_across_restart` → `test_coordinator_lists_only_the_opened_project_across_restart`（多加：開啟 project-two 後 project-one 的 `session.list` 被拒）；`test_restart_discovers_completed_json_missing_from_catalog_without_replay` → `test_restart_lists_completed_json_saved_after_seed_without_replay`；`test_transient_d_registers_once_after_first_durable_turn` → (b)；`test_first_prompt_registers_catalog_before_provider_failure` → `test_first_prompt_is_listed_before_provider_failure`；`test_catalog_follows_materialized_session_and_same_session_select` → `test_select_reuses_materialized_session_and_same_session_select`（只改名）。其他測試只拿掉 `project.list`、`project_catalog=`、registration 欄位的斷言，或把 `catalog.project_for_session` 換成 `session.list`。`test_desktop_crash_recovery.py` 的重啟後讀取由 `project.list` 改成 `session.list`。

## 4. 執行指令與結果

```bash
# 沙箱外（fixture 測試需要 /tmp 根目錄）
cd app && /home/minervamuses/miniconda3/envs/app/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_desktop_*.py tests/test_citation_project_library.py tests/test_skill_adherence.py
```

- 結果：`542 passed`（含 `test_desktop_conversations.py`、`test_desktop_service.py`、`test_desktop_fixture.py`、`test_desktop_server.py`、`test_desktop_protocol_contract.py`）；之後新增的 `test_conversation_methods_reject_noncanonical_session_ids` 5 個參數另跑通過。
- `npm test`：219 pass、1 fail，失敗的只有 `TS protocol DTOs, method names, and event names follow contract.json`——TS 仍宣告 `project.list`、`session.retry_registration` 與 `registrationStatus`，由 C6-S3 處理（預期）。
- grep `desktop-projects\|CATALOG_FILENAME\|register_session\|retry_registration\|registrationStatus\|project\.list\|_project_list`（`app/`，排除 `node_modules`、`for_agents`）：Python 只剩 `project.py` 的 `LEGACY_CATALOG_FILENAME` 與它在 `initialize_project` 的使用，以及 (e) 的測試；其餘命中都在 `desktop/src/protocol.ts` 與 `App.tsx`，屬於 C6-S3。
- `for_agents/` 仍描述 `catalog.py`、`DesktopProjectCatalog`、`load_project_catalog`、`CatalogConflictError`（`module-responsibilities.md`、`README.md`、`dangerous-assumptions.md`）；依限制不修改，交給 C10 最終彙報。
