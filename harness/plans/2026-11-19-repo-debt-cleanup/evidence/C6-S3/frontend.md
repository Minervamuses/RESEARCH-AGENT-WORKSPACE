# C6-S3 前端：單一專案清單、選取恢復純函式、移除 registration（U3、U19、S070）

- **日期**：2026-11-22
- **產品邊界**：只處理支援的循序流程——開啟一個專案、看它的清單、後端 crash／重啟後選回原本的對話。沒有新增任何跨專案或並行協調。

## 1. 變更

| 位置 | 變更 |
|---|---|
| `src/protocol.ts` | 刪除 `ProjectSummaryDto`、`ProjectListDto`、`RegistrationRetryDto`、`SessionCreatedDto.registered`、`SessionSelectedDto.registered`、`TurnCompletedDto.registrationStatus`／`registrationIssue`、`MethodResults` 的 `project.list` 與 `session.retry_registration`。DTO 一致性檢查（`tests/protocol_types.test.ts`）恢復通過。 |
| `src/conversations.ts` | 新增純函式 `conversationToRestore(openedProjectId, list, resume)`：只有在清單屬於開啟中的專案、`resumeSelectionRef` 擷取的選取也屬於它、且該對話仍在清單時，回傳要選回的 summary；否則 null。 |
| `src/backend.ts` | `planBackendSnapshotTransition` 的 `catalogGeneration`／`resetStaleCatalog` 改名為 `historyGeneration`／`resetStaleHistory`（行為不變）。 |
| `src/App.tsx` | `loadSelectedProjectHistory` 只呼叫一次 `session.list`（不再有 `project.list` 與 `reconcile`），回傳 `SessionListDto`。刪除 `catalog` state；**S070**：`sessionLists: Record<projectId, …>` 改為單一 `sessionList`，rename／delete／load more 都只更新它（projectId 不符時不動）；sidebar 只畫開啟中專案的一組，標題是專案根目錄名稱（`projectDisplayName`），數字用 `session.list` 的 `total`。選取恢復 effect 改為 `conversationToRestore(projectRef.current?.projectId, sessionList, resumeSelectionRef.current)`。`loadCatalog` → `loadHistory`，每次 turn 完成後都重新載入清單（原本只在 `registrationStatus === "registered"` 時，也就是已存檔後的每一回合）。刪除 retry registration 的 state、callback 與按鈕，以及 session meta 的 `cataloged`／`transient` 文字（只留 session ID 與回合數）。sidebar 的「Not saved yet」暫存列保留（C6-S1），判斷改為 `state.session.turnCount > 0`（原本是 `registered`）。 |
| `src/App.tsx`（通知） | 原本的 registration 通知同時承擔「turn 停止／失敗後，已存檔的對話無法重新整理」三種訊息。這些訊息與 registration 無關，所以保留通知，改名為 `historyIssue`，標題改成「CONVERSATION NOT REFRESHED」，按鈕「Refresh without resending」重新讀取清單與 transcript 尾頁（`refreshSavedConversation`，不重送 prompt），取代原本只能重試 registration 的按鈕。CSS class `.registration-notice` → `.history-notice`。 |

## 2. 測試

| 驗收 | 測試（`tests/conversations.test.ts`） |
|---|---|
| (a) 重啟後原本選取且仍在清單的對話被選回 | `restart reselects the conversation that was selected when it is still listed` |
| (b) 原本選取的對話已刪除時不選取、不報錯 | `restart selects nothing when the previously selected conversation was deleted` |
| (c) 沒有可恢復的選取時不選取 | `restart selects nothing without a resumable selection for the opened project`（另含專案不符、清單為 null 的情況） |
| 清單只用 `session.list` | `project history loads with one session.list request for the opened project`（請求恰好一次、參數無 `reconcile`；回傳他專案時拋 protocol mismatch；過期時回 null） |

改名的測試（行為不變）：`sidebar rows expose a transient selected conversation without cataloging it` → `sidebar rows show an unsaved selected conversation without changing the saved list`；`sidebar rows never duplicate a registered or already-listed conversation` → `…a saved or already-listed conversation`；`tests/backend.test.ts` 兩個 snapshot transition 測試的欄位與名稱改為 history。沒有刪除測試。

## 3. 執行指令與結果

```bash
cd app/desktop
PATH=/home/minervamuses/miniconda3/envs/app/bin:$PATH npm_config_cache=$TMPDIR/npm-cache npm run build
PATH=/home/minervamuses/miniconda3/envs/app/bin:$PATH npm_config_cache=$TMPDIR/npm-cache npm test
```

- `npm run build`：第一次失敗（sidebar 的 IIFE 漏了 `()`，TS2322），補上後通過。
- `npm test`：224 pass、0 fail（含 DTO 一致性檢查）。
- grep `registration|Registration|project\.list|ProjectList|cataloged|retry_registration|registrationStatus`（`app/desktop/src`、`tests`、`src-tauri/src`）：0。

## 4. GUI 清單（交給使用者）

1. 開啟已有對話的專案：sidebar 只有這一個專案，標題是專案資料夾名稱，「N saved」與列出的對話數一致，順序由舊到新。
2. 按 New conversation：出現「Not saved yet」列；第一次送出完成後，該列變成一般對話列（顯示回合數），且只出現一次。
3. 右鍵刪除一個對話：它從清單消失，數字減一。
4. 選取一個對話後按 Restart（或在後端 crash 後按重啟）：重新開啟專案後，原本的對話被自動選回；若它已被刪除，則不選取、不顯示錯誤。
5. 畫面上沒有「Retry registration」按鈕，也沒有「CATALOG REGISTRATION PENDING」通知；Session details 只顯示 session ID 與回合數，沒有 cataloged／transient。
6. （選擇性）若 turn 停止或失敗後出現「CONVERSATION NOT REFRESHED」通知，按「Refresh without resending」後清單與對話內容更新、通知消失，且 prompt 沒有被重送。
