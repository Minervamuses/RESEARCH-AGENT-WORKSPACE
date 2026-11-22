# C8-S6 依 domain 拆解 `App()`

基準：C8-S5 結束的 HEAD `8043ea6`；範圍遵循單一工作流（一個專案、一個對話、一個回合），不為「專案 A、B 同時操作」新增檢查。

## 一、抽出的 hook

### `useExtensions`（`src/hooks/useExtensions.ts`，C8-S6a）

- **參數**：無。
- **回傳**：`flow`、`reset()`、`start(turnId)`、`interrupt()`、`markRestarting()`、`applyTransition(transition)`、`observeRevision(revision)`、`update(fn)`、`updateFor(triggerTurnId, fn)`。
- **擁有**：state `extensionFlow`（1 個）；沒有 ref、沒有 effect（所以不涉及 effect 順序）。所有轉移都是 `src/lib/extensionFlow.ts` 的純函式；hook 只是 `useState` 加上穩定的 `useCallback` 包裝。
- **新增的純函式**：`applyExtensionSnapshotTransition`、`updateExtensionFlowFor`、`canPreviewExtensions`、`canRestartForExtensions`、`planExtensionApply`（含 Bypass 全部核准與重試的規劃）、`settleExtensionApply`。
- **參數是別的 hook 的 ref 或 setter**：無（沒有參數）。
- App 端仍負責：開始/結束 workspace operation、`api.extensionsPreview/Apply` 呼叫、結果落地到 transcript／liveTurns／session（它們是別的 domain 的 state，所以留在協調處）。

## 二、保留在 `App()` 的 domain 與理由

| domain | 理由 |
|---|---|
| 協調核心（generation／epoch／workspace operation） | 每個 domain 都用；`invalidateOperations` 重設別人的 ref。純函式（`ownsWorkspaceOperation`）本來在 `conversations.ts`，這次補了測試。 |
| 後端事件與生命週期（listener、`applyBackendSnapshot`、`runLifecycle`） | 是跨 domain 重設的集中點（原則 4）；純決策在 `planBackendSnapshotTransition`，這次再抽出 `turnEventIsStale`、`lifecycleResultIsStale`。 |
| 核准 | **評估後不抽 hook**：它的兩個 effect（逾時、過期清除）在 `App()` 中排在 5 個其他 effect 之後（歷史載入、選取還原等），而這些 effect 的守衛讀 `approvalRef.current.pending`；hook 必須宣告在最前面（`commitApproval` 被 12 處使用），effect 會被提前，同一次 commit 內的相對順序無法從程式碼確定。依「不確定時保持原 effect 順序」留在 `App()`。另需 6 個來自別的 domain 的 callback／值。純狀態模組 `approvalOwner.ts`（C8-S5）已在，這次再抽 `approvalExpiry` 並補逾時測試。**GUI 清單標為高風險的是 C8-S5 已列的 1、3、5。** |
| 文件工作區 | 8 個 ref 與 6 個 state 被 turn、project、approval 讀寫；hook 會變成互傳 ref。抽出 `planDocumentResult`、`planConflictResolution`（衝突狀態轉移）並補測試；`receiveDocumentResult`、`resolveDocumentConflict` 變成「規劃 → 套用」的薄接線。 |
| 回合（送出、Stop、Retry） | `sendTurn` 動到 10 個以上 domain 的 state。抽出 `stopScreenState`（Stopping、Retry Stop 面板、Restart 可用）與既有的 reducer 守衛。 |
| 對話清單與 transcript、專案選擇與綁定、控制（thinking／permission）、引用面板、輸入與 UI 輔助 | 同 C8-S1 草圖：自己擁有的 state 太薄或被多個流程寫入，拆出去只會互傳 setter。 |
| 對話選單與改名／刪除對話框 | C8-S1 列為「可選」。動作需要 begin/finish operation、`stopTurn`、兩個 promise ref；只剩 UI state 與 1 個焦點 effect，收益小，**不抽**。 |

## 三、原則 5 必要檢查 → 測試

| 檢查 | 純函式 | 測試（檔案：名稱） |
|---|---|---|
| 後端重啟或 crash 後舊 generation 的回應與 event 不套用 | `planBackendSnapshotTransition`、`conversationReducer`、`turnEventIsStale`、`lifecycleResultIsStale` | `backend.test.ts`「snapshot transition on restart generation change…」；`conversation_turns.test.ts`「backend generation change drops stale selection…」；**新**`conversation_turns.test.ts`「stale generation: turn events and lifecycle results from before a restart or reopen are dropped」 |
| Stop 與 Retry Stop 的畫面狀態 | `stopScreenState`、reducer `stop-*` | **新**`conversation_turns.test.ts`「Stop screen: Stopping, Retry Stop panel and Restart offer…」；既有「Stop waits for both replies…」「Stop failure remains blocked…」 |
| 核准擁有者、逾時、過期清除 | `approvalOwner.ts`、`approvalExpiry`、`approvalHasLiveOwner` | `approvalOwner.test.ts` 流程 (a)–(e)；`trust.test.ts`「a pending approval stays while…」；**新**`trust.test.ts`「approval timeout: an expired approval is denied at once…」 |
| 晚到回應（`ownsWorkspaceOperation`、`isCurrent`、`projectEpoch`） | `ownsWorkspaceOperation`、`selectConversationWithPreview`、`loadSelectedProjectHistory` | **新**`conversation_turns.test.ts`「late results: an operation owner only applies while its token, generation and project epoch are still current」；既有 `conversations.test.ts`「a replaced backend generation discards preview and selection responses」；reducer 的 `projectEpoch` mismatch 迴圈 |
| 文件衝突 | `planDocumentResult`、`planConflictResolution`、`advanceWorkingDocumentSources` | **新**`documents.test.ts`：「document result: a result for another open file or a different source is not applied」「…saved reconciles an unchanged editor…」「…conflict and failure keep the editor and pick the right base…」「conflict resolution: agent operations resend, a manual save needs the editor unchanged…」 |
| 擴充流程 | `extensionFlow.ts` | **新**`trust.test.ts`「extension planning: Bypass approves every binding…」「backend snapshot transitions interrupt, restart and await-load the extension flow」 |

測試數：237 → 247（+10）。

## 四、S071 型別統一

`DocumentSnapshot`（`lib/documentSource.ts`）與 `DocumentContextDto`（`protocol.ts`）欄位完全相同，已刪除前者，全部改用 `DocumentContextDto`（`documents.ts`、`documentSource.ts`、`DocumentEditor.tsx`、`CitationPanel.tsx`、`App.tsx`）。沒有名為 `DocumentResult` 的型別：`DocumentResultDto` 是 `document.save/apply` 的結果，欄位與上下文不同，不是同一件事，所以保留。`DocumentConflict` 是新的具名型別，取代 `App.tsx` 內的行內型別。DTO 一致性測試通過。

## 五、`App()` 後端呼叫

`App()` 本體不再有 `api.` 以外的後端／原生呼叫：原本的 `listen<unknown>(BACKEND_EVENT_NAME, …)` 搬進 `api.ts` 的 `listenBackendEvents`。`grep -rn "invoke(\|invoke<\|backendClient\.\|\.request(\|as unknown as\|listen<" src` 只命中 `api.ts`、`backend.ts` 與 `protocol.ts` 的一個已註明的 contract 轉型（C8-S3 已記錄）。

## 六、`App()` 本體剩餘的 hook（`awk '/^export default function App\(/,0'`）

| | C1-S3 | C8-S1 | 現在 |
|---|---|---|---|
| useState | 35 | 34 | 33 |
| useRef | 35 | 36 | 33 |
| useEffect | 14 | 13 | 11 |
| useCallback | 42 | 44 | 46 |

（`useCallback` 增加來自 C8-S5 與本步新增的 `listenBackendEvents` 之外的 callback 重新分配；`useRef`、`useEffect` 的下降主要來自 C8-S5。行數 2484 → 2462。）

### useState（33）

- **純UI（5）**：`conversationMenu`（展開）、`candidateRoot`、`candidateHistory`、`discardDraft`、`dirtyChoice`（專案選擇表單輸入）。
- **協調（28）**：`conversation`、`project`、`referenceIssue`、`chatSelection`、`chooserOpen`、`candidate`、`chooserIssue`、`sessionList`、`renameDialog`、`deleteDialog`、`slashCatalogOwner`、`historyGeneration`、`workspaceBusy`、`workspaceIssue`、`transcript`、`selectionPreview`、`liveTurns`、`pendingUserText`、`historyIssue`、`approval`、`documentValue`、`rootPath`、`documentBusy`、`documentNotice`、`documentConflict`、`lastDocumentAction`、`citationRefresh`、`citationEntries`。

### useRef（33）

- **純UI（5）**：`conversationMenuRef`、`composerRef`、`transcriptRef`、`transcriptEndRef`（DOM）、`conversationMenuReturnFocusRef`（焦點）。
- **協調（28）**：`projectRef`、`bindingGenerationRef`、`projectEpochRef`、`resumeSelectionRef`、`resumeDraftRef`、`documentBaselineRef`、`deleteOwnerRef`、`historyGenerationRef`、`documentRef`、`documentBusyRef`、`documentRequestRef`、`documentApplyPromiseRef`、`workingDocumentSourcesRef`、`submittedDocumentRef`、`selectedSkillNamesRef`、`inFlight`、`exclusiveOwnerRef`、`historyLoading`、`diagnosticsAttempt`、`generationRef`、`conversationRef`、`workspaceOperation`、`documentOperationRef`、`frameOwnerRef`、`turnOwnerRef`、`stopPromiseRef`、`turnSettlementPromiseRef`、`approvalRef`。

### useEffect（11）

- **純UI（3）**：選單開啟後聚焦；有 workspaceIssue 時聚焦輸入框；pending 訊息出現時捲到底。
- **協調（8）**：切換對話時清 `selectedSkillNamesRef`；backend 事件 listener 與啟動；ready 後自動 runtime 檢查；ready 後載入歷史／重新開啟專案；`selectionchange` 監聽（餵 `chatSelection`）；核准逾時；核准過期清除；重啟後自動重選對話。

## 七、GUI 清單新增

1. 擴充預覽 → 檢視 → Apply（Ask 與 Bypass 各一次）；Bypass 不出現逐項核准。
2. 擴充 Apply 中 backend 崩潰：面板顯示可重試；重試（Retry apply）使用同一個 request。
3. 擴充 Apply 需要重啟：Restart 後面板依序顯示 restarting → awaiting load → loaded。**高風險**（snapshot 轉移與 revision 觀察的時序）。
4. 文件存檔衝突：衝突面板顯示；Use / Keep / Cancel；衝突後再編輯再按「use」會顯示「editor changed again」。
5. 文件 agent 操作衝突：選擇後同一個操作以選擇重送；失敗時顯示 issue；取消顯示「Operation cancelled」。
6. Stop 失敗：出現「The turn could not finish stopping」+ Retry Stop；回合結束後出現「Your message」與 Restart backend；Retry Stop 後回到「Stopping…」。
7. 核准逾時：到期自動 Deny；已過期的核准一出現就 Deny（C8-S5 的高風險項目同樣適用）。
8. 後端事件（回合進行中重啟後）：舊 generation 的事件不影響新畫面（**高風險**，沿用 C8-S1 F3/F4）。

## 八、commit

- `300a62f` refactor(desktop-ui): move the extension flow into useExtensions with pure planning functions [C8-S6a]
- `cda3d2b` refactor(desktop-ui): plan document results and conflict resolution as pure functions, unify DocumentSnapshot with DocumentContextDto [C8-S6b]
- `f1e0e2b` refactor(desktop-ui): extract stop screen, stale-event and approval-expiry decisions with tests [C8-S6c]
- 最後一個 commit：`listenBackendEvents` 搬入 `api.ts`，加上本檔與 build-log。
