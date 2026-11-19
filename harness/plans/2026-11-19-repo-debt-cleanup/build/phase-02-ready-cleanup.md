# C2 — 零風險清理與小缺陷

- **完成後的狀態**：下列項目已套用並通過對應檢查：
  - [PLANS.md](../PLANS.md#s-id-歸屬) 中歸屬 C2 的 READY 項目；
  - U6（刪除對話 schema v1/v2 讀取器）；
  - S047（`turn_logs`）；
  - 缺陷 #2（`.error-text` 無樣式）與 #7（`watch.out`）。
- **涵蓋**：G7、G8
- **相依**：C1
- **輸入**：
  - 每個 S-ID 的位置與證據見[稽核原文](../context/repo-debt-audit-2026-11-19.md) §6。
  - 行號以 `3b6cfd8` 為準，以符號重新定位。

## 範圍

- **納入**：下表各步驟列出的項目。
- **不納入**：
  - 協定（C3、C4）與 citation 儲存（C5）。
  - `ChatSession` 的介面重整（C7）。S043 屬於 C7，本階段不碰。
  - `App()` 的拆解（C8、C9）。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| C2-S1 | **Agent 核心只剩測試在用的 API。**<br>• S038：刪同步版 `rewrite_prompt`、`review_draft`、`aggregate_candidates`、`parse_reviser_output`，以及它們在 `thinking/__init__.py` 的 re-export；測試改測 async 版。<br>• S039：刪 `agent.llm.text.invoke_text` 與 re-export；`test_openrouter_model.py` 改用正式路徑。不要動 `thinking` 裡的 `invoke_text_messages` 別名。<br>• S041：刪 `ChatSession.citation_service` 與只為測試存在的 setter。<br>• S042：刪 `ChatSession.restore`；3 個測試改用 `create(session_id=…)`。<br>• S044：刪 `session.py` 建構時與 `_validate_snapshot_project` 重複的 inline 檢查。 | • `tests/test_thinking.py`、`test_thinking_session.py`、`test_text_normalization.py`、`test_openrouter_model.py`，以及 grep 找到的引用模組都通過。<br>• grep 這些名稱：production 與測試都是 0（`invoke_text_messages` 除外）。 |
| C2-S2 | **S040：刪 `activate_citation_skill`、`deactivate_citation_skill`。** 7 個測試檔約 40 處引用改走 `/citation` 回合的正式路徑。不要另建等價的測試 helper 來取代被刪的方法。 | grep 為 0；那 7 個檔案通過；每處改寫都依測試退役規則確認保護的行為仍在。 |
| C2-S3 | **Skills 與測試整理。**<br>• S061：刪 manifest 的舊欄位友善錯誤，同步更新 `test_skill_runtime.py`；`extra="forbid"` 仍會拒絕。<br>• S062：只把 `test_skill_scan_ignores_only_regular_zip_sources` 移到 `test_extension_registry.py`，刪掉 `tests/test_extension_baseline.py`。<br>• S063：`test_smoke.py` 的 config 驗證測試移到合適模組，保留 `test_graph_builds_without_error`。<br>• S109：刪 gate 的無作用參數 `user_input` 與呼叫端傳值。<br>• S122：`tests/test_ingest.py` 移到 `tests/rag/`。 | 受影響模組通過；被刪測試有退役紀錄；舊欄位的 manifest 仍被拒絕，只是錯誤訊息改為一般的 forbid 訊息。 |
| C2-S4 | **RAG。**<br>• S114：`VectorRetriever` inline 到 `rag/api.py`，刪掉 `rag/retriever/`。若 `rag/__init__.py` 的 lazy `__getattr__` 對照表提到它，一併更新。`tests/rag/test_tools_contract.py:64` 依賴 lazy 行為，不可破壞。<br>• S115：刪 `rag/store/base.py` 的 `BaseStore`。<br>• S117：修正 `rag/llm/__init__.py` 與實際用法矛盾的註解。 | `tests/rag/` 全部通過；`import rag` 仍延遲載入向量後端。 |
| C2-S5 | **U6：刪對話 schema v1/v2 讀取器（S046）。**<br>1. 先唯讀檢查 `app/store/projects/*/conversations/*.json` 與 `app/store/conversations/*.json`（若存在）的 `schemaVersion`，結果寫入 `evidence/C2-S5/store-versions.md`。發現任何非 v3 檔案時，本步標為 Blocked 並回報，不刪讀取器。<br>2. 刪除 `conversations/models.py` 與 `repository.py` 中 v1/v2 的讀取與升版分支，以及 `test_conversation_repository.py` 中對應的升版測試。<br>3. 讀到 v1/v2 時要明確拒絕：成為 scan issue，或回報 unsupported schema。不可靜默升版，也不可當成 v3 解析。若原本沒有這種負向測試，就在既有的 repository 測試模組加一個最小的。 | 存證顯示全為 v3；repository、desktop conversation 測試通過；v2 檔案被拒絕的測試通過。 |
| C2-S6 | **S047（缺陷 #5）：`TurnJournal.turn_logs`。**<br>• 移除每回合累加、從不清除的 `turn_logs`，保留 production 唯一讀取的 `last_tool_calls`。<br>• `_record_turn` 若因此不再需要 async，就改成同步。<br>• `test_turn_finalizer` 與 `test_observability` 改讀它們真正要驗證的公開結果。 | 受影響測試通過；grep `turn_logs` 為 0；連續多回合後 journal 內沒有隨回合數成長的清單（以既有測試斷言，或在其中加一行斷言）。 |
| C2-S7 | **Rust 與啟動器。**<br>• S014：刪 `capabilities/main.json` 的 `core:app:allow-tauri-version`。<br>• S098：PowerShell 腳本只設定一次 `InputEncoding`。<br>• S101：`BackendSupervisor::new` 與 `for_test` 共用一個建構路徑。<br>• S102：`main.py` 刪掉對不存在的 `public/` 目錄的特判。 | `cargo test --locked`（沙箱外）通過，它會經由 tauri-build 驗證 capability；`npm run build` 通過；`python main.py --help` 或等價的語法檢查不出錯。若 `main.py` 沒有無副作用的檢查方式，改用 `python -m py_compile main.py`。 |
| C2-S8 | **前端小項目與缺陷 #2。**<br>• S073：`conversationInteractionState` 的三個欄位都等於 `turnActive`，呼叫端直接用 `turnActive`。<br>• S074：刪只為測試存在的 `sessionCreateParams`。<br>• S075：四份 backend snapshot／lifecycle 處理合成一個 `applyBackendSnapshot()`。<br>• S076：刪死 CSS 規則。<br>• S092：`generation`、`projectEpoch` 改成必填。<br>• 缺陷 #2：為 `.error-text` 加上錯誤樣式，沿用 `styles.css` 既有的錯誤色，不新增顏色。 | `npm test`、`npm run build` 通過；`grep -n "error-text" src/styles.css` 有規則。加入 GUI 清單：Stop 失敗訊息與 source editor 問題訊息以錯誤色顯示；backend 重啟與 crash 後的畫面狀態與之前相同。 |
| C2-S9 | **Repo 整潔。**<br>• S128（缺陷 #7）：先讀 `app/desktop/watch.out`，確認它只是 picker 調查留下的 watch 輸出，再刪除。它沒有被追蹤，刪了無法用 git 復原。evidence 只記「已刪除」與檔案大小，不記內容，因為內容含視窗標題。<br>• S129：刪 repo 根目錄被 ignore 的過期 `__pycache__/` 與空目錄 `harness/plans/.claude/.cc-writes`（含其上層空的 `.claude/`）。 | `git status` 顯示這些項目已不在；沒有任何被追蹤的檔案改變。內容若不符預期（例如 `watch.out` 不是 watch 輸出），就不刪，標為 Blocked 並回報。 |
| C2-S10 | **桌面後端小項目。**<br>• S023：`_execute_desktop_extension_command` 只回傳結果，不再回傳呼叫端會丟掉的第二個值；呼叫端不再重算它。<br>• S024：只呼叫一次的 async 包裝 `_apply_controls` inline 到呼叫端。<br>• S026：`documents.py` 的 `undo` 對 `validate_snapshot` 只呼叫一次；`prepare` 建好 candidate 後不再重複檢查。刪除前先確認兩次檢查之間沒有狀態變化（例如重新讀檔）；有的話就保留，並在 evidence 註明理由。 | `tests/test_desktop_service.py`、`test_desktop_documents.py`、`test_desktop_document_service.py`（沙箱外）、`test_extension_*.py` 通過。 |
| C2-S11 | **階段收尾。** 完整 pytest（沙箱外）、`npm test`、`npm run build`。C2-S7 已跑過 cargo，之後沒有再改 Rust，所以本步不重跑。 | 全部通過，或只剩 C1 記錄的既有失敗。結果寫入 build-log。 |

每一步一個 commit。scope 依子系統，例如 `refactor(thinking): drop sync review helpers [C2-S1]`、`chore(repo): remove stale watch output [C2-S9]`。

## 驗收

- 歸屬 C2 的每個 S-ID 在 build-log 都有結果：APPLIED，或 Blocked 附理由。
- C2-S11 的完整測試在最後狀態上通過。
- `evidence/C2-S5/store-versions.md` 存在。每一步的測試退役紀錄都附在該步的 evidence 或 build-log 事件中。

## 交給後續階段

- `ChatSession` 已沒有 `restore`、`citation_service` 與 `activate_citation_skill` 等測試專用 API。C7 在這個較小的介面上建立公開 API。
- 對話 repository 只讀 v3。
