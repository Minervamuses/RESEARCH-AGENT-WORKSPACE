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
| C7-S4 | **S052（desktop 這一側）。**<br>• 稽核 S052 列出的 desktop 私有存取都改成公開方法或屬性，包括：<br>　- final-text validator 與 prompt persisted callback 的設定；<br>　- citation policy 的讀取；<br>　- installer context 與 bypass；<br>　- skill runtime 預載；<br>　- conversation snapshot；<br>　- system prompt 的設定。<br>• `_document_turn_active` 改成 `turn_outcome(..., document_turn=True)` 這類每回合參數，`service.py` 不再在回合前後設定與還原它。<br>• `tests/support/fixture_session.py` 隨之更新。 | • desktop 測試全部通過。<br>• grep `session\._[a-z]`（排除 `self._session` 這類 service 自己的屬性；正規式寫在 evidence）在 `agent/desktop/` 為 0。<br>• 回歸測試：一個文件回合在中途拋錯後，下一個一般回合的有效工具不含強制加入的 `document_edit`。既有測試沒有涵蓋時，在 `test_desktop_document_service.py` 加一個。 |
| C7-S5 | **S028 與 P4（FAIL-022）。**<br>1. 先把 8 處忙碌判斷各自的條件、錯誤碼與訊息寫成對照表，存成 `evidence/C7-S5/busy-matrix.md`。8 處是：`_session_select`、`_session_rename`、`_session_delete`、`_session_create`、`_workspace_select`、`_runtime_shutdown`、`_shutdown_session`、`_require_idle_session`。<br>2. 建立一個 operation-state 物件，例如放在 `agent/desktop/operation_state.py`。它擁有回合、文件、工作區、專案讀取、擴充、關機等 flag、計數與 lock，提供 `require_idle(…)` 與進入、離開操作的方法。8 處都改用它，對照表中的每一列行為不變。<br>3. P4：`_session_stop` 在快取的清理錯誤存在時，重新執行清理，不再重播快取錯誤。成功就清除忙碌狀態；失敗就回報這次的錯誤，繼續封鎖。 | • desktop 測試全部通過，`test_failed_stop_cleanup_keeps_new_turn_blocked` 不修改也通過。<br>• 新測試（放在既有模組）：第一次清理失敗、第二次 Stop 時清理成功，接著新回合被接受。<br>• 另一個測試：兩次清理都失敗，第二次回報的是新的錯誤（以不同訊息區分），且新回合仍被拒。<br>• 對照表每一列都有既有或新增的測試覆蓋；沒有覆蓋的列在 evidence 註明。 |
| C7-S6 | **`service.py` 模組化（可拆成 C7-S6a、C7-S6b…）。** 依職責把程式搬出，`DesktopService` 只留 dispatch 表、生命週期與接線。提案模組：<br>• `errors.py`：`_map_exception` 一族與 `DesktopServiceError`（S034、S035）<br>• `bibliography_ops.py`：bibliography handler（S123 的一部分）<br>• `extension_ops.py`<br>• `command_ops.py`：桌面斜線指令 `/init /ingest /sync /prune`<br>• `document_ops.py`<br>• `approvals.py`<br>• `transcript.py`<br>• `turn_context.py`<br>原則：<br>• 每個 commit 搬一到兩組職責，只搬移、不改行為。<br>• 測試中 monkeypatch 的路徑（`agent.desktop.service.X`）跟著更新。 | • 每個 commit 都讓 desktop 測試通過。<br>• 最後 `service.py` 的行數與各模組行數寫入 evidence。<br>• grep 確認各模組之間沒有循環 import；以 `python -c "import agent.desktop.server"` 加上 desktop 測試確認。 |
| C7-S7 | **階段收尾。** 完整 pytest（沙箱外）。 | 全部通過；G5 的 grep 檢查（私有存取、fixture 開關、`inspect.signature`）都為 0。 |

## 失敗與續作

C7-S4 與 C7-S5 改到回合生命週期。若 desktop 測試的失敗無法在兩次聚焦修正內解決：

- 以 checkpoint 保存；
- C7-S6 可以在 C7-S5 之前先做。兩者彼此獨立，但模組化時要搬的是當下的版本。

## 交給後續階段

- C10 的文件可以如實寫「Retry Stop 可以恢復」。
- 之後新增後端功能時，改的是對應的模組，不再改 4,000 行的單一檔案。
