# C6 — 對話清單由掃描推導（U3、U19）

- **完成後的狀態**：
  - 沒有程式讀寫 `desktop-projects.json`。
  - 專案的對話清單來自 `ConversationRepository.scan()`。
  - `project.list`、`session.retry_registration`、registration 狀態與 UI 分支已移除。
  - 前端只有單一專案的路徑；後端重啟後原本選取的對話照常恢復。
  - 專案擁有權與歷史健康檢查照舊 fail closed。
  - 掃描成本已量測，交給使用者決定是否需要快取（R3）。
- **涵蓋**：G4、G2
- **相依**：C3
- **輸入**：
  - [GOALS.md](../GOALS.md) 的 U3、U11、U19、R3、A7。
  - [稽核原文](../context/repo-debt-audit-2026-11-19.md)的 S018、S019、S027、S070。
  - [PLANS.md](../PLANS.md)「基線」對 catalog 與 `project.list` 的描述。

## 必須保留的行為

- **INV-016 與 FAIL-026 的 fail-closed 檢查**：
  - 歷史目錄不存在或不是目錄時拒絕開啟；
  - scan 有 issue（例如 C2 之後的 v1/v2 檔案、壞檔）時拒絕開啟；
  - 任何對話的 `project_id` 與專案不符時拒絕開啟。
- `RESEARCH.md` metadata 的解析、`inspect_project`、`initialize_project`、`project_citation_settings`、`update_project_metadata` 的對外行為不變。只有 `initialize_project` 不再建立 catalog 檔。
- 第一次送出 prompt 前，新 session 不出現在清單中；送出後出現（prompt-first 持久化，INV-006）。
- 刪除對話後，它從清單消失。
- **對話選取恢復**（U19）：後端 crash 或重啟後，前端以 `resumeSelectionRef` 重新選取原本的對話；若它已不在清單，就不選取，也不報錯。

## 隨 U3 消失的行為

1. **遺失對話的檢查**：「catalog 列出、但對話檔不存在時，拒絕開啟專案」這個檢查消失，遺失的對話只是不出現在清單。它的測試依退役規則刪除。
2. **空歷史目錄的歸屬檢查**（GOALS U11）：
   - 現在即使沒有任何對話，`_check_catalog_owner` 也會拒絕另一個專案開啟或初始化同一個 `historyDirectory`。
   - 這個保證消失；目錄裡有對話之後的歸屬檢查照舊。
   - 只為空目錄歸屬存在的測試，依退役規則刪除。不實作擁有者標記檔。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| C6-S1 | **盤點（探索）。** 列出 registration、catalog 與 `project.list` 的所有觸點，寫入 `evidence/C6-S1/surface.md`：<br>• `service.py`：`_project_list`、`_session_registered`、`_pending_registration`、`_session_retry_registration`、`_saved_session_registration_result`、`registrationStatus`／`registrationIssue`、`_reconcile_lagged_catalog_entries`、`_injected_catalog`、`self._catalog` 的每個用法，以及 `session.list` 的 `reconcile` 參數。<br>• `catalog.py`：`DesktopProjectCatalog`、`_scoped_catalog`、`_check_catalog_owner`、`load_project_catalog`、`rebuild_from_conversations`（S018）、`reconcile_conversations`、bootstrap。<br>• contract、TS 與 `App.tsx`：`loadSelectedProjectHistory`（約 207–222 行，專案數不等於 1 時 throw）、`catalog` state 的每個讀寫、選取恢復的 effect（約 2237 行）、retry UI（約 2419–2431 行）、`cataloged`／`transient`（約 2931 行）、多專案 scaffolding（約 1049、1625、1784–1813、2790–2808 行）。<br>• **GOALS A7**：找出 `project.list` 回傳非 null `selectedSessionId` 的所有情況，判斷是否屬於支援的流程，以及前端在該流程是否依賴它恢復選取。<br>• 測試。<br>同時決定模組名稱：若移除 catalog 類別後 `catalog.py` 只剩專案 metadata 與歷史目錄函式，就改名為 `project.py`，並更新所有 import。 | 盤點表完整，每列附位置；A7 有結論與證據。 |
| C6-S2 | **後端。**<br>• `load_project_catalog` 改成只做上方三項 fail-closed 檢查並回傳 repository 的函式，例如 `open_project_history`。<br>• `session.list` 的清單來自 scan 的 summaries，依 `created_at` 與 `conversation_id` 排序，與現行 bootstrap 相同。移除 `reconcile` 參數。<br>• 刪除 `project.list`、registration 機制、`session.retry_registration`、`registrationStatus`、`registrationIssue`，以及 contract、DTO、fixtures 中的對應項目。若 A7 的結論是某個支援的流程需要 `selectedSessionId`，就把它加到 `session.list` 的 result。<br>• `initialize_project` 不再建立 catalog 檔。它的「目錄必須為空」檢查要繼續容許殘留的 `desktop-projects.json`：用一個具名常數，註明「C6 之前留下的檔案，永不讀取」。<br>• 測試：catalog 測試改寫為推導行為；S027 的掃描次數斷言更新為新數字；registration、retry 與 `project.list` 的測試刪除，並寫退役紀錄。 | • `tests/test_desktop_conversations.py`、`test_desktop_service.py`、`test_desktop_fixture.py`（沙箱外）、`test_desktop_server.py`、Python 協定測試通過。<br>• 新增或保留的測試涵蓋：<br>(a) 專案歷史中已有 3 個對話，開啟後清單列出 3 個；<br>(b) 新 session 在第一次送出前不在清單、送出後在清單；<br>(c) 刪除後不在清單；<br>(d) 混入他專案對話時拒絕開啟；<br>(e) 歷史目錄含殘留的 `desktop-projects.json` 時照常開啟，且該檔內容未被讀取或改寫（比對 mtime 與內容）；<br>(f) 歷史中有一個壞掉的對話檔時拒絕開啟（scan issue）；<br>(g) 歷史目錄或其 `conversations/` 不存在時拒絕開啟。<br>• grep `desktop-projects\|CATALOG_FILENAME\|register_session\|retry_registration\|registrationStatus\|project\.list\|_project_list` 只剩 (e) 的具名常數與它的測試。 |
| C6-S3 | **前端。**<br>• `loadSelectedProjectHistory` 改為只呼叫 `session.list`，專案 ID 用前端已知的開啟中專案；刪除 `catalog` state 與 `ProjectListDto`。<br>• 選取恢復的 effect 改讀前端已知的專案 ID 與 `resumeSelectionRef`（以及 A7 若保留的 `selectedSessionId`）。「要恢復哪個對話」的判斷抽成純函式，放在 `.ts` 模組並測試。<br>• 刪除 retry registration 的 UI 與 state，以及 `cataloged`／`transient` 文字。session meta 行只留 session ID 與回合數。<br>• S070：移除多專案 scaffolding，改成單一專案清單。 | • `npm test`（含 DTO 一致性檢查）、`npm run build` 通過。<br>• 選取恢復的純函式測試：<br>(a) 後端重啟後，原本選取且仍在清單的對話被選回；<br>(b) 原本選取的對話已被刪除時，不選取，也不報錯；<br>(c) 沒有可恢復的選取時，不選取。<br>• GUI 清單新增：<br>　- 開啟有既有對話的專案時，清單正確；<br>　- 新對話第一次送出後出現；<br>　- 刪除後消失；<br>　- 後端 crash 後按重啟，原本的對話被選回；<br>　- 沒有 retry registration 按鈕。 |
| C6-S4 | **掃描量測（R3，只量測，不加快取）。**<br>• 在 `$TMPDIR` 以 repository 自己的寫入函式產生合法的 v3 對話檔，量測兩種規模：<br>　- 10 個對話與 50 個對話；<br>　- 每個對話的檔案約 1 MiB（以文件回合的 `submittedContext` 撐大，接近實際長文件對話）。<br>• 量測「開啟專案」與「一次 `session.list`」各自的耗時與 scan 次數，各跑 3 次取中位數。<br>• 腳本與結果寫入 `evidence/C6-S4/scan-cost.md`，註明機器與條件。不訂門檻，不加快取。 | 結果存在；最終彙報引用它，並把「是否加快取」列為使用者決定。 |
| C6-S5 | **階段收尾。**<br>• 完整 pytest（沙箱外）、`npm test`、`npm run build`、`cargo test --locked`（沙箱外）。<br>• 確認 contract 中已沒有 `project.list`、`session.retry_registration`、`registrationStatus`、`registrationIssue`。 | • 全部通過。<br>• 本階段只驗收自己負責移除的項目。完整方法清單與錯誤碼的跨階段複查在 C10-S0。 |

## 交給後續階段

- C7 拆 `service.py` 時，registration、catalog 與 `project.list` 的程式已經不存在。
- 掃描量測交給 C10 的最終彙報。
