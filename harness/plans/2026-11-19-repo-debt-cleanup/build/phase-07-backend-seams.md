# C7 — 後端接縫

- **完成後的狀態**：
  - `fixture_session.py` 位於 `app/tests/support/`，`server.py` 沒有 fixture 環境變數開關。
  - 假物件集中管理，production 不再為了配合假物件而探測參數。
  - `ChatSession` 有公開介面，`agent/desktop` 與 `agent/thinking` 不再存取它的私有屬性。
  - 文件回合旗標改為每回合的參數。
  - 所有忙碌判斷都經由同一個 operation-state 物件。
  - Retry Stop 可以恢復（FAIL-022）。
  - `service.py` 依職責拆成模組。
- **涵蓋**：G5、G7（缺陷 #1）
- **相依**：C2、C4、C5、C6。這樣 `service.py` 已移除 knowledge、registration、bundle 等程式，不會搬移死碼。
- **輸入**：
  - [GOALS.md](../GOALS.md) 的 P4、P5、A5。
  - [稽核原文](../context/repo-debt-audit-2026-11-19.md)的 S020–S022、S028、S031、S034、S037、S043、S052、S066、S123。
  - `for_agents/known-failure-modes.md` 的 FAIL-022 與 `future-work-backlog.md` 的 BACKLOG-022（唯讀參考）。
  - `agent/ingest.py::LocalWorkScope.finish_stop`：C7-S5 的修正範圍包含它。

## 設計約束

- **不新增抽象層**。只允許：
  - 搬移程式；
  - 把既有的私有方法改成公開，必要時改名；
  - 一個 operation-state 物件；
  - 給 fusion orchestrator 用的一個 `typing.Protocol`。
- **模組名稱是提案**，執行者可依實際內容調整，並記錄在 build-log。
- **每個忙碌檢查點的現行錯誤碼與訊息都要保留**，包括細節差異，例如 `-self._project_read_count`。先做對照表，再改程式。
- 測試若原本存取被改名或刪除的私有屬性，就改走新的公開介面（S066 的這一部分）。其他私有存取不在本階段範圍。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| C7-S1 | **P5：fixture 移到測試（S020、S021、S022）。**<br>• `agent/desktop/fixture_session.py` 移到 `app/tests/support/fixture_session.py`（提案路徑），更新 5 個測試模組的 import。<br>• `server.py` 約 419–430 行的環境變數開關，改成 `server.py` 的主函式接受一個可選的 service 建構函式；production 呼叫時不傳。<br>• `tests/test_desktop_crash_recovery.py` 改用測試自有的入口啟動子程序，例如 `tests/support/fixture_server.py`：它把 `app/tests` 加入 `sys.path`，再以 fixture builder 呼叫 server 主函式。<br>• 刪除只剩 fixture 使用的 `documents.selected_text`（S021）與 `DesktopKnowledgeOperations.workspace_root`（S022），連同 `test_desktop_documents.py:84` 等引用。 | • 那 5 個模組在沙箱外通過。<br>• `grep -rn "RESEARCH_AGENT_DESKTOP_FIXTURE\|fixture_session" app/agent` 為 0。<br>• `app/agent/desktop/` 內沒有 fixture 程式。 |
| C7-S2 | **S031、S037：假物件。**<br>• `_materialize_session` 一律以完整 kwargs 呼叫 session factory。刪除約 5 處 `inspect.signature` 探測、`_session_factory_accepts_bash`，以及稽核列出的假物件用 `getattr`／`hasattr`／`isinstance` 分支。<br>• 測試 factory 改成接受 `**_kwargs`。<br>• 跨模組重複的假 session 與假 service 集中到 `app/tests/desktop_support.py`：只集中重複的部分，不建立新框架。 | desktop 測試通過；grep `inspect.signature` 在 `agent/desktop/service.py` 為 0。 |
| C7-S3 | **S052（orchestrator 這一側）與 S043。**<br>1. 先驗證 A5：grep 列出 `agent/` 中所有在 `session.py` 以外存取 `ChatSession` 私有成員的地方，寫入 `evidence/C7-S3/private-access.md`。<br>2. `agent/thinking/orchestrator.py` 用到的成員改成公開名稱，例如 `run_graph_turn`、`execute_graph`、`base_prompt_history`，並以一個 `TurnHost` Protocol 列出這些需求。<br>3. S043：`_active_skill_context_block` 只是轉手，inline 到唯一的呼叫者。 | `test_thinking_session.py` 等受影響模組通過；grep `session\._[a-z]` 在 `agent/thinking/` 為 0。 |
| C7-S4 | **S052（desktop 這一側）。**<br>• 稽核 S052 列出的 desktop 私有存取都改成公開方法或屬性，包括：<br>　- final-text validator 與 prompt persisted callback 的設定；<br>　- citation policy 的讀取；<br>　- installer context 與 bypass；<br>　- skill runtime 預載；<br>　- conversation snapshot；<br>　- system prompt 的設定。<br>• `_document_turn_active` 改成 `turn_outcome(..., document_turn=True)` 這類每回合參數，`service.py` 不再在回合前後設定與還原它。<br>• `tests/support/fixture_session.py` 隨之更新。 | • desktop 測試全部通過。<br>• 在 `agent/desktop/` 中兩種 grep 都為 0：<br>　- 屬性存取：`session\._[a-z]`，排除 `self._session` 這類 service 自己的屬性；<br>　- 字串形式的存取：`(getattr|hasattr|setattr)\([^)]*"_[a-z]`，例如目前的 `getattr(session, "_conversation_snapshot")`。<br>　兩個正規式與結果都寫在 evidence；只有存取非 `ChatSession` 物件的命中可保留，並逐一註明。<br>• 回歸測試：一個文件回合在中途拋錯後，下一個一般回合的有效工具不含強制加入的 `document_edit`。既有測試沒有涵蓋時，在 `test_desktop_document_service.py` 加一個。 |
| C7-S5 | **S028 與 P4（FAIL-022）。**<br>1. 先把 8 處忙碌判斷各自的條件、錯誤碼與訊息寫成對照表，存成 `evidence/C7-S5/busy-matrix.md`。8 處是：`_session_select`、`_session_rename`、`_session_delete`、`_session_create`、`_workspace_select`、`_runtime_shutdown`、`_shutdown_session`、`_require_idle_session`。<br>2. 建立一個 operation-state 物件，例如放在 `agent/desktop/operation_state.py`。它擁有回合、文件、工作區、專案讀取、knowledge（斜線指令的 `_knowledge_active` 與 `_knowledge_operation`）、擴充、session 建立、關機等 flag、計數與 lock。實際清單以對照表為準，不可遺漏任何現有 flag。物件提供 `require_idle(…)` 與進入、離開操作的方法。8 處都改用它，對照表中的每一列行為不變。<br>3. P4：清理錯誤有兩層快取，兩層都要改，只改桌面端不夠：<br>　(a) `agent/ingest.py::LocalWorkScope.finish_stop`（約 64–80 行）把清理工作存在 `self._bash_cleanup`。失敗後再呼叫，只會對同一個已失敗的 task 再取一次 `.result()`，永遠重拋舊例外。要改成：失敗後清掉這個 task，下次呼叫重新對還沒停下的 process group 執行清理；已成功停下的不重複處理。<br>　(b) `_session_stop` 在快取的清理錯誤（`owner.error`）存在時，重新呼叫 (a)，不再重播快取錯誤。成功就清除忙碌狀態；失敗就回報這次的錯誤，繼續封鎖。<br>　(c) `owner.error` 有兩個來源（`service.py` 約 3000–3021 行）：清理失敗，或回合的持久化狀態仍是 `pending`（"The turn has not reached a saved terminal state."）。所以 Retry Stop **不可只因清理成功就解除忙碌**。<br>　- 重試時要重新讀取該回合的狀態。只有在清理成功，**而且**屬於下列兩種情況之一時，才解除忙碌：<br>　　1. 回合已持久化為 terminal 狀態；<br>　　2. 已確認回合**未被受理、也未落盤**，即 `state=null`、`accepted=false`、`persisted=false`。這是使用者在回合受理前就按 Stop 的合法結果（`fixtures.json` 的 `session-stop-before-prompt-acceptance`），沒有任何終止紀錄可等。<br>　- 讀取狀態失敗、狀態無法判定，或回合仍是 `pending` 時，維持封鎖。<br>　- 若回合仍是 `pending`，可以沿用現有的恢復路徑，也就是重新載入時把殘留的 pending 標成 interrupted（INV-006、`_recover_interrupted_turn`），把它結束後再解除；做不到就維持封鎖並回報。<br>　- 採用哪一種寫入 evidence。不新增其他結束 pending 的方式。 | • desktop 測試全部通過，`test_failed_stop_cleanup_keeps_new_turn_blocked` 不修改也通過。<br>• 新測試（放在既有模組）。失敗要注入在**底層的清理動作**：monkeypatch `agent.tools.bash._stop_process_group`，或 `LocalWorkScope` 實際呼叫的清理函式。不可以整個替換 `finish_stop`，因為那樣測不到 (a) 的快取問題；既有的 `test_failed_stop_cleanup_keeps_new_turn_blocked` 正是整個替換，所以它不能當作這個修正的證據。測試走真正的 `LocalWorkScope.finish_stop`：<br>　- 第一次清理拋錯，第二次 Stop 時清理成功，接著新回合被接受。<br>　- 兩次清理都失敗時，第二次回報的是新的錯誤（以不同訊息區分），且新回合仍被拒。<br>　- **受理前就 Stop、第一次清理失敗、重試清理成功**（`state=null`、`accepted=false`、`persisted=false`）：解除忙碌，新回合被接受。<br>　- **清理成功、但讀取回合狀態失敗**：維持封鎖。<br>　- **清理成功、但回合仍是 `pending`**：Retry Stop 之後不可放行新回合；或者依 (c) 經由現有恢復路徑先把回合標成 interrupted（測試讀取對話 JSON 確認），之後才放行。<br>• `LocalWorkScope` 的單元測試（放在 `tests/test_bash_tool.py` 或既有的 ingest 或 scope 測試）：`finish_stop` 第一次失敗後，第二次呼叫會重新執行清理，而不是重拋同一個例外物件。<br>• 對照表每一列都有既有或新增的測試覆蓋；沒有覆蓋的列在 evidence 註明。 |
| C7-S6 | **`service.py` 模組化（可拆成 C7-S6a、C7-S6b…）。** 依職責把程式搬出，`DesktopService` 只留 dispatch 表、生命週期與接線。提案模組：<br>• `errors.py`：`_map_exception` 一族與 `DesktopServiceError`（S034、S035）<br>• `bibliography_ops.py`：bibliography handler（S123 的一部分）<br>• `extension_ops.py`<br>• `command_ops.py`：桌面斜線指令 `/init /ingest /sync /prune`<br>• `document_ops.py`<br>• `approvals.py`<br>• `transcript.py`<br>• `turn_context.py`<br>原則：<br>• 每個 commit 搬一到兩組職責，只搬移、不改行為。<br>• 測試中 monkeypatch 的路徑（`agent.desktop.service.X`）跟著更新。 | • 每個 commit 都讓 desktop 測試通過。<br>• 最後列出 `service.py` 剩下的每個方法，逐一分類為 dispatch、生命週期或接線，寫入 evidence。<br>　- 無法歸入這三類的方法，要嘛搬走，要嘛在 evidence 寫明留下的理由。<br>　- 被搬出的 handler 本體不可留在 `service.py`。<br>• `service.py` 與各模組的行數寫入 evidence。<br>• 確認各模組之間沒有循環 import：執行 `python -c "import agent.desktop.server"`，並跑 desktop 測試。 |
| C7-S7 | **階段收尾。** 完整 pytest（沙箱外）。 | 全部通過；G5 的 grep 檢查（私有存取、fixture 開關、`inspect.signature`）都為 0。 |

## 失敗與續作

C7-S4 與 C7-S5 改到回合生命週期。若 desktop 測試的失敗無法在兩次聚焦修正內解決：

- 以 checkpoint 保存；
- C7-S6 可以在 C7-S5 之前先做。兩者彼此獨立，但模組化時要搬的是當下的版本。

## 交給後續階段

- C10 的文件可以如實寫「Retry Stop 可以恢復」。
- 之後新增後端功能時，改的是對應的模組，不再改 4,000 行的單一檔案。
