# C7-S7 U14：Retry Stop（FAIL-022，缺陷 #1）

- **日期**：2026-11-22
- **觸發情境**：使用者按 Stop，清理失敗（或回合仍停在 pending），再按一次 Stop——支援的正常使用。沒有新增鎖或拒絕條件；只把「重播舊錯誤」換成「真的重試」。

## 1. 兩層快取與修正

| 層 | 原本 | 現在 |
|---|---|---|
| (a) `agent/ingest.py::LocalWorkScope.finish_stop` | 清理 task 存在 `_bash_cleanup`；失敗後再呼叫只會對同一個失敗的 task 取 `.result()`，永遠重拋同一個例外 | 失敗時清掉 `_bash_cleanup`，下次呼叫重新對**還沒停下**的 process group 執行清理；已停下的記在 `_stopped_processes`，不重複處理。順帶修正：`await asyncio.shield(task)` 在 task 失敗時本身就會拋出 task 的例外，所以重設要包住整個等待迴圈（第一版只包 `.result()`，單元測試抓到第二次呼叫仍重播舊例外，修正後通過） |
| (b) `DesktopService._session_stop` | `owner.error` 存在就直接重拋 | Stop 送達時若回合**已經結束**（`owner.done` 已完成），代表它是被先前失敗的清理或未定的狀態卡住：呼叫 `_retry_stop`。Stop 送達時回合還在跑，則照舊等它結束並回報這次的結果（第一次 Stop 不自動重試兩次；第一版沒有區分，測試發現第一次 Stop 就被重試成功）。 |

清理失敗的錯誤訊息改為附上這次的原因（「The turn's local work could not finish stopping: <reason>」，有長度上限），使第二次失敗能與第一次區分。錯誤碼仍是 `INTERNAL_ERROR`。

## 2. (c) 何時解除忙碌（`_retry_stop`）

1. 重新執行 `_finish_turn_work`（含 (a)）。失敗 → `owner.error` 換成這次的錯誤並回報，維持封鎖。
2. 成功後從**磁碟**重讀該回合（`_saved_turn_state`：`load_optional` 後以 turn ID 與原始 display input 比對，不退回記憶體快照）。讀取失敗 → 回報「The stopped turn's saved state could not be read; the conversation stays blocked.」，維持封鎖，`owner.error` 不變。
3. 狀態為 `pending` → 採用既有恢復路徑 **`ChatSession.reload_and_recover`**（C7-S4 公開；先從磁碟重讀，再把殘留的 pending 標成 interrupted，INV-006），再讀一次。session 不在或不是該對話、或恢復失敗 → 維持封鎖。沒有新增其他結束 pending 的方式，也沒有用只改記憶體的 `_recover_interrupted_turn`。
4. 解除條件：清理成功，而且（狀態為 terminal：completed／failed／interrupted）或（確認未受理也未落盤：磁碟上找不到該回合，且回合結束時記錄的結果就是 `accepted=false`、`persisted=false`）。其他情況（狀態無法判定、仍 pending）維持封鎖並重拋原錯誤。
5. 解除時 `owner.error = None`、`owner.result` 更新為磁碟上的狀態、`_turn_active = False`（只在它仍是目前回合時）。

## 3. 測試

失敗注入在底層：`monkeypatch.setattr("agent.tools.bash._stop_process_group", ...)`，走真正的 `LocalWorkScope.finish_stop`（測試把一個替身 process 註冊進回合的 scope）。`test_failed_stop_cleanup_keeps_new_turn_blocked` 未修改，照舊通過（它整個替換 `finish_stop`，不作為本修正的證據）。

| 驗收 | 測試 |
|---|---|
| 第一次清理拋錯、第二次 Stop 清理成功，新回合被接受 | `test_desktop_document_service.py::test_retry_stop_reruns_failed_cleanup_and_then_accepts_a_new_turn`（第二次 Stop 回傳 `interrupted`，下一回合 completed） |
| 兩次都失敗：第二次回報新的錯誤，新回合仍被拒 | `test_retry_stop_reports_the_new_cleanup_failure_and_stays_blocked` |
| 受理前就 Stop、第一次清理失敗、重試成功（`state=null`、`accepted=false`、`persisted=false`）：解除，新回合被接受 | `test_retry_stop_releases_a_turn_stopped_before_acceptance`（在 `_refresh_project_rules` 停住，磁碟上沒有對話檔） |
| 清理成功但讀取回合狀態失敗：維持封鎖 | `test_retry_stop_stays_blocked_when_the_turn_state_cannot_be_read` |
| 清理成功但回合仍 pending：經 `reload_and_recover` 標成 interrupted（讀對話 JSON 確認）後才放行 | `test_retry_stop_finishes_a_pending_turn_through_recovery_before_releasing`（第一次 Stop 回報「has not reached a saved terminal state」且仍 BUSY_TURN） |
| `LocalWorkScope` 單元測試：第一次失敗後第二次呼叫重新執行清理，而不是重拋同一個例外物件 | `test_bash_tool.py::test_finish_stop_reruns_cleanup_after_a_failure_and_skips_stopped_groups`（兩次失敗是不同的例外物件與訊息；已停下的 group 不再處理） |

## 4. 檢查

- 新測試 7 passed（含未修改的既有測試）；沙箱外完整 pytest 1827 passed。
- 同一問題的修正次數：(a) 的重設位置 1 次、(b) 的「何時重試」1 次，皆在第一次修正後通過。
