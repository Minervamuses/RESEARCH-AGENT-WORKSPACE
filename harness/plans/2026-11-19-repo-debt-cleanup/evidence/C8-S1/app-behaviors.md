# C8-S1 前端行為與狀態盤點（唯讀探索）

- 量測基準：工作樹 `GUI` 分支，`app/desktop/src/App.tsx` 共 3000 行，`export default function App()` 在第 1002 行，函式本體到檔尾（1002–3000，約 2000 行）。
- 讀過：`App.tsx`、`trust.tsx`（547 行）、`backend.ts`（626 行）、`conversations.ts`（790 行）、`tests/*.test.ts`。
- 本檔所有行號都是 `App.tsx`，除非另標檔名。範圍遵循單一工作流（一個專案、一個對話、一個執行中的回合）；「專案 A、B 同時操作」不在驗收範圍。

## 1. 使用者可見的流程（GUI 驗收清單基礎）

「畫面」欄是預期看到的東西；`高風險` 表示行為取決於 effect 之間的時序，C8-S6 拆 hook 時要保持 effect 順序不變。

| # | 流程 | 觸發 | 預期畫面 |
|---|---|---|---|
| F1 | 啟動 | 開啟桌面程式（effect 1407：先註冊 listener，再 `backendClient.initialize`） | 先出現「Preparing your research workspace」(2821)；backend 啟動時側欄狀態「Starting backend」+ spinner 卡片 (2823)；ready 後自動跑 runtime 檢查 (effect 1593)，卡片「Checking the local runtime」(2824)；診斷完成後自動彈出專案選擇對話框「Open a research project」(2942，`chooserOpen` 預設 true)。側欄「Choose a project to load its conversations.」。**高風險**：1407 → 1593 → 1791 → 2182 的串接。 |
| F2 | 啟動失敗 | backend 起不來 | 紅色通知「Action required」+ 錯誤訊息 (2811)；側欄 Start 按鈕改為「Retry start」，通知內也有「Retry start」。 |
| F3 | Backend crash | 收到 `backend.crashed` 事件或 lifecycle snapshot 變 crashed | 側欄狀態「Backend crashed」；通知「The local backend stopped unexpectedly」+「Restart backend」按鈕 (2811)；核准對話框消失、進行中的回合畫面清掉（generation 改變）；擴充面板轉為錯誤或 restarting；診斷區 `RuntimeDetails` 顯示 (2874)。 |
| F4 | 重啟 | 按側欄 Restart / 通知內「Restart backend」 | 「Restarting backend」+ spinner (2823)；新 generation ready 後：「Reopening selected project」（effect 1791，`workspace.select open`）→ 重新載入對話清單 → effect 2182 自動重選重啟前的對話並還原草稿；若該對話已被刪除則不選任何對話。**高風險**。 |
| F5 | 關閉 backend | 按 Shut down | 「The local backend is stopped」+「Start local backend」按鈕 + shutdown 摘要（graceful / forced / already stopped）(2822)。 |
| F6 | 選擇專案 | 側欄「Open project / Switch project」→ 「Choose project folder…」（原生 picker `pick_project`） | 對話框顯示 Resolved project；依狀態：`needs_configuration`（History directory 輸入框 + 編輯後出現「Inspect history location」）、`needs_initialization`（說明將建立空歷史）、`ready`（說明將驗證既有歷史）。有未存文件時出現「Save before opening / Discard only after the project opens」單選；有草稿時出現「Discard the unsent draft…」勾選，未勾則主按鈕停用。錯誤以 `role=alert` 顯示。Esc 與 Cancel 在忙碌時停用。 |
| F7 | 開啟或初始化專案 | 主按鈕「Open project」/「Initialize and open project」（有未存文件且選 save 時前綴「Save and 」） | 標頭狀態「Opening project」；成功後對話框關閉，側欄顯示專案名稱與「N saved」；文件、草稿、transcript、擴充流程、核准全部重置 (1703–1738)；之後載入對話清單（「Loading selected project…」）。存檔失敗時留在對話框：「The document was not saved. Resolve the save issue before switching.」；文件有 conflict 時不能切換專案（側欄提示「Resolve or cancel the document conflict before switching projects.」）。 |
| F8 | 建立對話 | 側欄「＋ New conversation」或 backend-ready 卡片「Create local conversation」 | 有草稿時先跳 `window.confirm`；標頭狀態「Creating conversation」；新對話被選取，空 transcript 顯示「What would you like to research?」；側欄該列顯示「Not saved yet」（transient）。 |
| F9 | 選擇對話 | 點側欄對話列 | 有草稿時 `window.confirm`（重啟還原時不問）；「Selecting conversation」；先顯示已存訊息預覽（`aria-busy`，「Preparing this conversation…」），選取完成後換成正式 transcript 並捲到底、焦點回輸入框；若最後一回合 failed/interrupted，還原「Retry saved turn」。選取失敗時 transcript 顯示錯誤並回復 slash 目錄。 |
| F10 | 改名 | 對話列右鍵 → 選單 Rename（方向鍵移動；Esc/Tab 關閉並還原焦點） | 「Rename conversation」對話框；超過 256 bytes 顯示「Enter a shorter name.」；「Save name」忙碌時顯示「Saving…」；成功後側欄列標題更新、焦點回該列；transient 或非 ready 的列 Rename 停用。 |
| F11 | 刪除 | 右鍵 → Delete | `DeleteConversationDialog` 說明刪除範圍；若該對話正在執行，狀態先「stopping」再「deleting」；失敗在對話框內顯示錯誤、可重試；成功後對話框關閉、焦點到 `#main-workspace`；若刪的是目前對話，草稿、transcript、擴充流程清空。刪別的對話正在執行時：「Wait for the current conversation to finish…」。 |
| F12 | 載入更多 | 「Load more conversations」/「Load older turns」 | 標頭狀態「Loading more conversations」/「Loading older turns」；older turns 載入後捲動位置保持。 |
| F13 | 送出 | 輸入框 Enter（Shift+Enter 換行；IME 組字中不送出）或 Send | 標頭「Preparing submission」瞬間，接著出現使用者訊息 + 「Assistant · working」spinner；活動列表 Stage/Tool；Send 變 Stop；Permission/Thinking 控制、側欄對話列、文件開啟全部停用。完成後出現 assistant 回答、捲到底、焦點回輸入框。 |
| F14 | 送出失敗與 Retry | 回合失敗或傳輸錯誤 | 紅色通知（`failureLifecycleLabel`：Delivery status unknown / Prompt was not accepted / Answer saved locally / Prompt saved…）；草稿保留；可重試時有「Retry saved turn」(沿用同一 turnId)；Permission/Thinking 與原本不同時，重試停用並顯示「Saved turn: Ask · Normal. Current controls differ…」+「Send new turn with current settings」。已存但未刷新時出現「CONVERSATION NOT REFRESHED」+「Refresh without resending」。 |
| F15 | Stop | 回合進行中按 Stop（輸入框或核准對話框內皆有） | 按鈕變「Stopping…」且停用；成功後 composer 解鎖，通知「Turn stopped」；已存回合會重新整理。 |
| F16 | Retry Stop | Stop 失敗 | 區塊 `role=alert`「The turn could not finish stopping」+ 錯誤訊息 +「Retry Stop」；回合已結束時另顯示「Your message」摺疊與「Restart backend」；composer 仍鎖住；Retry 成功後「Refreshing saved conversation」並更新 transcript。 |
| F17 | 核准對話框 | 當前 request 發出 `approval.required`（回合、document.apply、bibliography.add 的 citation.save） | 模態對話框顯示動作、目標、參數與 Deny/Approve；處理中按鈕停用；回合 request 的核准對話框內含 Stop；到 `expiresAt` 自動 Deny；結束後對話框關閉、焦點回輸入框；刪除對話框開著時不顯示；backend crash／重啟／回合結束時消失。 |
| F18 | 開啟文件 | 文件標頭 Open（原生 picker `pick_document`） | 有未存變更時 `window.confirm`「Discard unsaved document changes and open another file?」；開啟後編輯器顯示內容，標頭顯示路徑，引用面板重新檢查；失敗在文件提示列顯示。回合進行中、核准中、忙碌時 Open 停用。 |
| F19 | 存檔 | 標頭 Save 或編輯器存檔快捷鍵 | `saved`：dirty 標記消失、引用面板刷新；`conflict`：出現衝突面板；`failed`：衝突面板標題「Save failed」，提示「Save failed. The editor and candidate are retained.」；`cancelled`：「Operation cancelled. Your current text is retained.」。 |
| F20 | Agent 套用文件變更 | 回合中收到 `document.proposed` | 自動送 `document.apply`（可能先出現核准對話框，編輯器仍可操作）；成功後編輯器取代選取範圍、「Undo」可用；Undo 送 `undoOfCallId`；Stop 期間忽略新提案。 |
| F21 | 文件衝突 | `document.apply` 或 `document.save` 回 conflict/failed | 「Document version conflict」面板：Original source / Current editor / Current disk / Agent candidate（預設展開）；按鈕 Keep editor、Use candidate and save（無 `expectedSnapshot` 時停用）、Cancel；提示「The editor or disk changed. Choose which version to keep.」；Use 時若編輯器又變動：「The editor changed again. Save again to review the current conflict.」。衝突存在時側欄不能切專案。 |
| F22 | 引用面板 | 開啟文件且 backend ready 時顯示摺疊摘要列 | 展開看條目；加入條目（`bibliography.add`，可能出現 citation.save 核准）；改 style（只在 idle 且不同樣式時送）；Markdown 文件才有 Export（Word、BIME Word、Markdown）；已引用列有 Line 跳轉，未引用列有 Remove；回合進行中、文件忙碌、核准中時寫入停用；文件開啟、存檔、套用後重新檢查。 |
| F23 | Thinking 控制 | 輸入框下方 Normal/Extended | 標頭「Updating session controls」；成功後選項更新；回合/文件忙碌/核准中停用；文件回合的提示「Normal for this document turn; Extended resumes afterward.」。 |
| F24 | Permission 控制 | Ask/Bypass | 同上；ACK 的 generation 或 session 不符時顯示「The backend returned controls for a different conversation.」；Bypass 時擴充預覽不再逐項詢問。 |
| F25 | 擴充預覽與套用 | 回合結果 `extensionAction === "preview"` 後出現 ExtensionPanel | Preview →「Previewing extensions」→ 顯示摘要、proposed skills、MCP bindings（Ask 模式每個 binding 要選 Approve/Deny，全部決定前 Apply 停用；Bypass 自動核准）；Apply →「Applying the current valid preview…」→ 結果；`restartRequired` 時出現 Restart；重啟後等待新對話確認 revision（awaiting load）；backend 中斷時顯示「The backend stopped before the saved extension result was delivered.」並提供 apply recovery。 |
| F26 | 斜線選單 | 草稿僅有 `/prefix`、游標在結尾、輸入框聚焦、目錄屬於目前 session 與 generation | 列出符合的命令（`/name` + 描述，純文字）；狀態列「N commands · ↑↓ to move · Enter to insert · Esc to close」或「No matching commands」；↑↓ 移動，Enter 插入 `/name `（不送出），Esc 關閉；IME 組字中不處理；目錄在切換對話或重啟後未驗證時不顯示。 |
| F27 | `@` skill 選單 | 游標前是 `@token`（前一字元不是 email/網域字元） | 列出 `loadedSkills`（`@name` + 描述）；Enter 插入 `@name`（結尾才補空格）並記入已選 skill；無符合時「No matching Skill. Unselected @ text is sent literally.」；送出時帶 `skillReferences`；已選的 skill 已不存在時送出失敗並顯示 `SUBMISSION_INVALID`（Selected Skill is no longer available）。 |
| F28 | 文件與對話選取引用 | 編輯器選取文字加入引用；對話中選取文字出現浮動「Comment on selection」 | 引用卡片出現在輸入框上方；跨訊息選取顯示「Select text within one message at a time.」；選取計算排除編號與註解 UI；回合進行中、核准中、對話框開啟時不顯示浮動按鈕。 |

## 2. `App()` 內每個 `useRef`（36 個，行號為宣告行）

| 行 | 名稱 | 分類 | 說明 |
|---|---|---|---|
| 1011 | `projectRef` | state mirror | 鏡像 `project` state |
| 1012 | `bindingGenerationRef` | generation/epoch 計數 | 目前專案綁定在哪個 backend generation；`null` 表示重啟後需重新綁定 |
| 1013 | `projectEpochRef` | generation/epoch 計數 | 每次開啟專案 +1 |
| 1014 | `resumeSelectionRef` | other | 重啟前選取的對話（還原用） |
| 1015 | `resumeDraftRef` | other | 重啟前的草稿 |
| 1023 | `documentBaselineRef` | other | 磁碟基準快照，判斷文件 dirty |
| 1028 | `deleteOwnerRef` | operation owner | 刪除對話操作 |
| 1029 | `conversationMenuRef` | DOM ref | 右鍵選單容器 |
| 1030 | `conversationMenuReturnFocusRef` | DOM ref | 選單關閉後要還原焦點的元素 |
| 1033 | `historyGenerationRef` | state mirror | 鏡像 `historyGeneration` state（經 `setHistoryGeneration` 同步） |
| 1049 | `documentRef` | state mirror | 鏡像 `documentValue`（經 `updateDocument`） |
| 1052 | `documentBusyRef` | state mirror | 鏡像 `documentBusy`（手動同步） |
| 1056 | `documentRequestRef` | other（進行中 request 的 id/上下文） | document.apply 的 requestId、turnId、context |
| 1057 | `documentApplyPromiseRef` | in-flight promise | 進行中的 document.apply |
| 1058 | `workingDocumentSourcesRef` | other | 回合進行中的文件來源快照 |
| 1059 | `submittedDocumentRef` | other | 送出時的文件快照 |
| 1060 | `selectedSkillNamesRef` | other | 使用者從 `@` 選單選過的 skill 名稱集合 |
| 1069 | `citationRequestRef` | other（進行中 request 的 id） | bibliography.add 的 requestId，也是核准擁有者之一 |
| 1070 | `inFlight` | other（互斥旗標） | lifecycle/diagnostics 的獨占鎖 |
| 1071 | `exclusiveOwnerRef` | operation owner | `runExclusive` 的擁有者 |
| 1072 | `historyLoading` | operation owner | `loadHistory` 的擁有者 |
| 1073 | `diagnosticsAttempt` | generation/epoch 計數 | 最後一次嘗試診斷的 generation |
| 1074 | `generationRef` | generation/epoch 計數 | 目前接受的 backend generation |
| 1075 | `conversationRef` | state mirror | 鏡像 `conversation` reducer 狀態（effect 1089 + `applyConversation`） |
| 1076 | `composerRef` | DOM ref | 輸入框 |
| 1077 | `transcriptRef` | DOM ref | transcript 容器（兩個互斥區塊共用） |
| 1078 | `transcriptEndRef` | DOM ref | 捲到底錨點 |
| 1079 | `workspaceOperation` | operation owner | 工作區獨占操作（`beginWorkspaceOperation`） |
| 1080 | `documentOperationRef` | operation owner | 文件 open/save/apply |
| 1081 | `approvalOwnerRef` | operation owner | 核准的擁有者 |
| 1082 | `frameOwnerRef` | operation owner | `requestAnimationFrame` 排程 |
| 1083 | `turnOwnerRef` | operation owner | 回合 |
| 1084 | `stopPromiseRef` | in-flight promise | Stop request |
| 1085 | `turnSettlementPromiseRef` | in-flight promise | 回合結算 |
| 1086 | `pendingApprovalRef` | state mirror | 鏡像 `pendingApproval`（effect 1090） |
| 1087 | `approvalResolvingRef` | state mirror | 鏡像 `approvalResolving` |

分類合計：DOM 5（1029、1030、1076、1077、1078）、state mirror 7（1011、1033、1049、1052、1075、1086、1087）、operation owner 8（1028、1071、1072、1079、1080、1081、1082、1083）、generation/epoch 4（1012、1013、1073、1074）、in-flight promise 3（1057、1084、1085）、其他 9（1014、1015、1023、1056、1058、1059、1060、1069、1070；其中 1056、1069 是進行中 request id）。5+7+8+4+3+9 = 36。

App 以外還有三個 ref：`composingRef` 370、`insertion` 371（`SlashComposer`，皆 DOM/IME 輸入狀態）、`bodyRef` 841（`MessageBody`，DOM）。

## 3. 必要檢查對應程式位置與既有測試

測試欄「純」＝純函式／reducer 測試；「源碼」＝讀 `.tsx` 文字比對；「無」＝沒有任何測試。

### (a) 後端重啟或 crash 後，舊 generation 的回應與 event 不被套用

| 位置 | 作用 | 既有測試 |
|---|---|---|
| `backend.ts:586 planBackendSnapshotTransition`（`snapshot.generation < currentGeneration` → `accepted:false`；`resetStaleHistory`、`clearTransientUi`、`invalidateOperations`） | 快照轉移的純決策 | 純：`backend.test.ts:567`「snapshot transition on restart generation change…」（含 596 的舊 generation 被拒）、`backend.test.ts:609`「…on crash clears transient UI…」 |
| `App.tsx:1337 applyBackendSnapshot`（1352 拒絕；1353 `invalidateOperations`；1399 更新 `generationRef`；1400 `backend-generation-changed`） | 把決策接到 refs/state | 無（接線無測試） |
| `App.tsx:1134 invalidateOperations` | 清掉所有擁有者，使晚到結果的 `ownsOperation` 為 false | 無 |
| `App.tsx:1576–1577 runLifecycle`（`owner.projectEpoch` 與 `snapshot.generation < generationRef`） | 舊的 start/restart 結果不套用 | 無 |
| `App.tsx:1416–1436` listener（`disposed` 守衛、`backend.crashed` / `backend.shutting_down` 清核准與擴充流程） | 事件入口 | 無 |
| `App.tsx:1461` | event 的 `active.backendGeneration`、`active.projectEpoch` 與目前值不符則丟棄 | 無（內嵌判斷） |
| `conversations.ts:472–479, 485` conversationReducer（`projectEpoch` 不符整個丟棄；`backend-generation-changed` 清 selected/activeTurn/stopRequest/failure；各 action 比對 `generation`） | reducer 守衛 | 純：`conversation_turns.test.ts:540`「backend generation change drops stale selection, pending turn, answer, and failure」、`:562`、`:602`、`:623`（`{generation:0}`、`{projectEpoch:1}` 的 mismatch 迴圈在 632–634、654、700） |
| `backend.ts` `backendReducer` snapshot 分支（generation 改變時清 diagnostics 與 session） | UI 狀態 | 純：`backend.test.ts:120`「lifecycle reducer keeps backend readiness, session readiness, and recovery distinct」 |
| `App.tsx:1597–1599 loadHistory`、`1791–1825` effect | 歷史只在綁定 generation 載入 | 無 |
| `App.tsx:231 composerSlashCommands` | slash 目錄需屬於目前 generation 與 session | 純：`conversations.test.ts:234` |
| `trust.tsx:441 reconcilePermissionAck` | Permission ACK 需同 generation、同 session | 純：`trust.test.ts:289` |
| `App.tsx:573 selectConversationWithPreview` | 取代後的 generation 丟棄預覽與選取回應 | 純：`conversations.test.ts:801`「a replaced backend generation discards preview and selection responses」（另 755、779、820） |

### (b) Stop 與 Retry Stop 的畫面狀態

| 位置 | 作用 | 既有測試 |
|---|---|---|
| `conversations.ts:493–510` reducer `stop-requested` / `stop-succeeded` / `stop-failed`；`:782 conversationInteractionState`（`turnActive = activeTurn ∨ stopRequest`） | Stop 狀態機 | 純：`conversation_turns.test.ts:602`「Stop waits for both replies in either order and ignores duplicate clicks」、`:623`「Stop failure remains blocked after the turn ends and can retry only its own target」、`:642`、`:662` |
| `App.tsx:1895–1941 stopTurn`（含 1914–1934 的 Retry 成功後「Refreshing saved conversation」） | 送 `session.stop`、核對回聲、重試後重新整理 | 回聲純：`backend.test.ts:468`「echo: session.stop…」；其餘無 |
| `App.tsx:2675–2679` `stopRecovery`、`stopping`、`canRestart`；`1563–1565` runLifecycle 的 stopRecovery 例外 | Stop 失敗後可重啟 | 無 |
| `App.tsx:2812–2819`「The turn could not finish stopping」+ Retry Stop | 畫面 | 無（JSX 在 App 內） |
| `App.tsx:340 ComposerFooter`（Stop / Stopping…） | 畫面 | 渲染：`conversations.test.ts:852` |
| `trust.tsx:266 ApprovalDialog` 的 Stop 與 stopError | 畫面 | 渲染：`trust.test.ts:363` |
| `App.tsx:1469–1470`（Stop 期間忽略 `document.proposed`／`approval.required`）、`2023`（Stop 期間不可 resolve）、`2365、2394`（sendTurn 等待 `stopPromiseRef`）、`1954–1964`（delete 先 stop） | Stop 與其他流程的互動 | 無 |

### (c) 核准的擁有者、逾時與過期清除

| 位置 | 作用 | 既有測試 |
|---|---|---|
| `trust.tsx:217 acceptApprovalEvent`（requestId 需等於 active、`parentRequestId` 相符、未過期；generation 只被蓋章，沒有比較） | 是否接受 `approval.required` | 純：`trust.test.ts:205`「approval events must correlate to the active request and remain unexpired」 |
| `trust.tsx:249 approvalHasLiveOwner`（turn／document／citation 三種 request） | 過期清除判斷 | 純：`trust.test.ts:382`；另 `trust.test.ts:395` 以**讀 App.tsx 原始碼**比對清除程式（C8-S5 要改寫） |
| `App.tsx:1442–1458`（citation 路徑接受並登記擁有者）、`1489–1505`（turn/document 路徑） | 登記 `pendingApprovalRef` + `approvalOwnerRef` | 無（源碼測試只守 citation 傳入） |
| `App.tsx:2062–2071` effect（逾時自動 Deny；已過期則立即 Deny） | 逾時 | 無（過期判斷在 `acceptApprovalEvent` 有測試） |
| `App.tsx:2073–2087` effect（無擁有者時清除） | 過期清除 | 純部分有（`approvalHasLiveOwner`），effect 本身無 |
| `App.tsx:2020–2055 resolvePendingApproval`（`isCurrent` = `ownsOperation(owner, approvalOwnerRef)` 且核准 id 相同；回聲核對 2041） | 結案 | 回聲純：`backend.test.ts:459`；其餘無 |
| 清除區塊重複位置（`approvalResolvingRef.current = false` 共 10 處）：1230、1251、1363、1378、1432、1722、2051、2083、2349、2389 | 其中有清 `approvalOwnerRef` 的只有 1229、1250、2049（另 1138 的 `invalidateOperations`） | 無 |

### (d) 已結束或被取代的操作晚到的回應（`isCurrent`、`ownsOperation`、`projectEpoch`）

| 位置 | 作用 | 既有測試 |
|---|---|---|
| `conversations.ts:215–230 ownsWorkspaceOperation`；`App.tsx:1099 captureOwner`、`1103 ownsOperation` | 擁有者比對（token + generation + projectEpoch） | **無**（`tests/` 內沒有任何對 `ownsWorkspaceOperation` 或 `WorkspaceOperationOwner` 的引用） |
| `isCurrent` 閉包：1602（loadHistory）、1630（rename）、1657（chooseProject）、1769（loadMore）、1802（reopen）、1950（delete）、2026（resolve）、2105（select）、2198（create）、2236（loadOlder）、2272（sendTurn，另比 `sameSelection`）、2402（`selectionIsCurrent`）、2460（preview ext）、2493（apply ext）、2554（refresh）、2583、2614（controls）；文件：1217–1221、1268–1272、1302–1309；獨占：1552、1588 | 各操作晚到回應守衛 | 只有被抽出的函式有測：`selectConversationWithPreview`（`conversations.test.ts:755、779、801、820`）、`loadSelectedProjectHistory` 的 `isCurrent`（`:433`）；其餘內嵌，無 |
| `projectEpoch` 比較：1100、1104、1461、1576、1832、1875、1899、2451；reducer 側 `conversations.ts:476–479` | epoch 不符就丟棄 | reducer 側純：`conversation_turns.test.ts:632–634、654、700` 的 mismatch 迴圈；App 側無 |
| 自我比較：`ownsOperation(x, x)` 於 1462、1464、1621、1794、1945 | 只檢查該擁有者的 generation/epoch 是否仍是目前值（沒有比對別的 ref） | 無 |

### (e) 文件衝突

| 位置 | 作用 | 既有測試 |
|---|---|---|
| `App.tsx:1160–1196 receiveDocumentResult`（saved 1166；conflict 1186；failed 1189；cancelled 1192；來源不符丟 `protocolMismatch` 1163） | 結果分派到 state | 無（內嵌 setState） |
| `App.tsx:1317–1335 resolveDocumentConflict`（keep/use/cancel；1325 的「編輯器又變動」檢查） | 解決衝突 | 無 |
| `App.tsx:1198–1239 applyDocumentOperation`（帶 `resolution`、`expectedSnapshot`） | 送出解決選擇 | 無 |
| `App.tsx:1269–1270`、`1673–1680`、`1750–1753`、`1653` | 未存變更確認、切專案前存檔、衝突時禁止切專案 | 無 |
| `App.tsx:939 reconcileSavedDocument` | 存檔後與編輯器合併 | 純：`documents.test.ts:80`、`:91`（SSR 載 App.tsx） |
| `App.tsx:977 advanceWorkingDocumentSources`（非 saved 狀態不前進，conflict/failed/cancelled） | 範圍前進 | 純：`documents.test.ts:139`（158 行的 status 迴圈） |
| `App.tsx:972 documentOperationContext`、`965 submittedDocumentSource`、`930 documentContextPayload` | 文件上下文 | 純：`documents.test.ts:100`、`:139` |
| `App.tsx:2784–2798` 衝突面板 | 畫面 | 無 |

## 4. Domain 草圖

原則：state、ref、effect 都屬於該 domain、參數與回傳幾行說得清，才抽 hook；hook 之間不互傳 ref 或 setter；需要別人的資訊就收「值」或「在協調處定義的 callback」。

| Domain | 擁有的 state / ref / effect | 需要其他 domain 的 | 判斷與理由 |
|---|---|---|---|
| 協調核心（owner/epoch 與 workspace operation） | ref：`generationRef`、`projectEpochRef`、`workspaceOperation`、`frameOwnerRef`；`captureOwner`、`ownsOperation`、`begin/finishWorkspaceOperation`、`scheduleOwnedFrame`、`invalidateOperations`；state `workspaceBusy`、`workspaceIssue` | `beginWorkspaceOperation` 要讀 `inFlight`、`documentBusyRef`、`pendingApprovalRef`、`conversationRef`；`invalidateOperations` 重設 12 個 ref 與 4 個 state | **留在 App() 協調**：每個 domain 都用它，且它重設別人的 ref。可抽的只有純函式（`ownsWorkspaceOperation` 已在 `conversations.ts`，補測試）。 |
| 後端事件與生命週期 | state `state`（`backendReducer`）；ref `inFlight`、`exclusiveOwnerRef`、`diagnosticsAttempt`；effect 1407、1593；`applyBackendSnapshot`、`runExclusive`、`runLifecycle`、`loadDiagnostics` | `applyBackendSnapshot` 讀寫 project、resume、history、approval、extension、conversation；listener 分派到 approval/document/turn/citation | **留在 App() 協調**：listener 與 snapshot 套用是跨 domain 重設的集中點（原則 4）。純決策已在 `planBackendSnapshotTransition`。`runExclusive`+`diagnostics`（3 個 ref、1 個 effect）可作為窄 hook，但 `runLifecycle` 需讀 5 個其他 domain 的守衛，只能收一個 `canRun()` callback，收益低。 |
| 核准 | state `pendingApproval`、`approvalResolving`；ref `pendingApprovalRef`、`approvalResolvingRef`、`approvalOwnerRef`；effect 1090、2062、2073；`resolvePendingApproval`、`returnApprovalFocus` | 擁有者 request id（turn、document、citation 三個，來自別的 domain）、`stopRequest`、`focusComposer`、`captureOwner/ownsOperation`、document 的 context（resolve payload） | **hook 候選（有條件）**：先在 C8-S5 把擁有者追蹤做成純狀態模組；hook 對外只有 `clear()`、`accept(event, owners)`、`resolve()`；三個擁有者 id 由協調處提供的 `getOwnerRequests()` callback 取得，其他 domain 結束時呼叫 `clear()`（不接觸 ref）。目前 10 處清除是它被切碎的症狀。 |
| 文件工作區 | state `documentValue`、`documentBusy`、`documentNotice`、`documentConflict`、`lastDocumentAction`、`rootPath`；ref `documentRef`、`documentBusyRef`、`documentBaselineRef`、`documentOperationRef`、`documentRequestRef`、`documentApplyPromiseRef`、`workingDocumentSourcesRef`、`submittedDocumentRef`；`openDocument`、`saveDocument`、`applyDocumentOperation`、`resolveDocumentConflict`、`receiveDocumentResult` | 綁定 generation 是否有效（`bindingGenerationRef`）、project rootPath、conversation 是否忙碌、`pendingApproval`、workspace operation 是否進行、approval 清除；turn 需要讀 `documentRef`、寫 `submittedDocumentRef`/`workingDocumentSourcesRef`；project open/delete 需重設 | **先抽純函式、hook 暫不抽**：`receiveDocumentResult`、`resolveDocumentConflict` 的分派可抽成純規劃函式並補測（目前 (e) 幾乎沒測）。state/ref 與 turn、approval、project 開啟都交纏（`submittedDocumentRef` 與 `workingDocumentSourcesRef` 實為 turn 與 document 共用）；除非把這兩個 ref 的歸屬釐清，否則留在 App()。 |
| 回合（送出、Stop、Retry） | state `liveTurns`、`pendingUserText`；ref `turnOwnerRef`、`stopPromiseRef`、`turnSettlementPromiseRef`；`sendTurn`、`sendNewTurn`、`stopTurn`；conversation reducer（`conversation`、`conversationRef`、`applyConversation`、effect 1089） | workspace operation、`loadHistory`、transcript 與 history 的 setter、`state.session` 與 `dispatch(session-created)`、extension flow 建立、approval 清除、document refs、焦點與捲動、project/generation | **留在 App() 協調**：`sendTurn` 一次動到 10 個以上 domain 的 state，拆出去只會變成互傳 setter。可抽純函式：送出守衛、Stop 目標與 correlation、失敗後是否需要刷新（`isPersistedTurnFailure` 已有）。 |
| 對話清單與 transcript | state `sessionList`、`transcript`、`selectionPreview`、`slashCatalogOwner`、`historyGeneration`、`historyIssue`；ref `historyLoading`、`historyGenerationRef`、`resumeSelectionRef`、`resumeDraftRef`；effect 1791、2182；`loadHistory`、`selectConversation`、`createSession`、`loadMoreSessions`、`loadOlder`、`refreshSavedConversation` | 幾乎全部：project、generation、conversation reducer、approval/document 守衛、draft、extension、focus | **留在 App() 協調**：`selectConversation` 與 `createSession` 會重設 draft、extension、chat selection。可抽純函式：`mergeSessionItems`、`selectConversationWithPreview`（已抽，需搬到 `.ts`）。 |
| 對話選單與改名/刪除對話框 | state `conversationMenu`、`renameDialog`、`deleteDialog`；ref `conversationMenuRef`、`conversationMenuReturnFocusRef`、`deleteOwnerRef`；effect 1156 | 動作需要 begin/finish operation、`stopTurn`、兩個 promise ref、`loadHistory`、session list setter | **部分 hook 候選**：對話框的 UI state、DOM ref 與 effect 1156 屬於自己，可成 hook，對外 `openMenu/openRename/openDelete/close`；`renameConversation`、`deleteConversation` 的動作留在 App()（要讀其他 domain 的 ref），以 callback 形式連接。收益小，視 C8-S6 時間決定。 |
| 專案選擇與綁定 | state `project`、`chooserOpen`、`candidate*`、`chooserIssue`、`discardDraft`、`dirtyChoice`；ref `projectRef`、`projectEpochRef`、`bindingGenerationRef`；`chooseProject`、`showProjectChooser` | `chooseProject` 開啟成功後重設 20 個 state/ref（1703–1738）；需要 draft、document dirty、`saveDocument` | **留在 App() 協調**：它就是原則 4 要集中的「開關專案重設」。表單 state 太薄，單獨抽成 hook 只會再回傳 setter。 |
| 擴充 | state `extensionFlow`；無 ref；`previewExtensions`、`decideBinding`、`applyExtensions`、`restartForExtensions`；純函式全在 `trust.tsx` | `begin/finishWorkspaceOperation`、`ownsOperation`、`state.session`（revision、permissionMode、sessionId）、transcript/liveTurns（`alreadyVisible`）、`setLiveTurns`、`dispatch(session-created)`、`runLifecycle("restart")`；外部寫入點：1383–1398（snapshot）、1435、1571、2117、2209、2353、1719、2001 | **hook 候選（最合適）**：state 與純轉移都是自己的；對外 `reset()`、`interrupt()`、`markRestarting()`、`observeRevision()`、`start(turnId)`；`applyExtensions` 的結果落地用協調處的 `onApplied(report)` callback；不接收他人的 ref 或 setter。 |
| 引用面板 | state `citationRefresh`、`citationEntries`；ref `citationRequestRef`；`requestCitationAdd`；`CitationPanel` 本身已是獨立元件 | 文件 open/save/apply 要 bump `citationRefresh`；approval 要讀 `citationRequestRef`；核准清除 | **留在 App()**：只有 2 個 state、1 個 ref、1 個 callback，且 `citationRequestRef` 與 approval 擁有者纏在一起；等 approval 擁有者模組完成後再看。 |
| 控制（thinking / permission） | 無自己的 state/ref/effect（session 在 `backendReducer`）；`updateThinkingMode`、`updatePermissionMode` | begin/finish operation、`focusComposer`、`state.session`、`dispatch` | **留在 App()**：沒有自己擁有的東西；純判斷 `reconcilePermissionAck` 已在 `trust.tsx` 並有測試。 |
| 輸入、選取引用與 UI 輔助 | state `chatSelection`、`referenceIssue`；ref `composerRef`、`transcriptRef`、`transcriptEndRef`、`selectedSkillNamesRef`；effect 1061、1866、2656、2657；`captureChatSelection`、`addChatReference`、`addDocumentReference`、`focusComposer` | `referenceIssue` 被送出、選取、建立、刪除、引用等七個流程寫入；`addChatReference` 需 begin/finish operation 與 conversation | **留在 App()**：1866 的選取監聽可獨立，但整體被多 domain 寫入；2656、2657 是純 UI（焦點、捲動）。 |

總結：值得抽成 hook 的只有「擴充」「核准（有條件）」，「對話選單/對話框」可選；其餘留在協調處並把可測判斷抽成純函式。若不遵守「不互傳 ref/setter」，其他 domain 都會退化成互傳十幾個 ref。

## 5. 覆蓋計數與指令

指令與 C1-S3 相同（自 `app/desktop/src/App.tsx` 所在的 repo 根目錄執行）：

```bash
awk '/^export default function App\(/,0' app/desktop/src/App.tsx | { grep -oE '\buseState\b' || true; } | wc -l      # 34
awk '/^export default function App\(/,0' app/desktop/src/App.tsx | { grep -oE '\buseRef\b' || true; } | wc -l        # 36
awk '/^export default function App\(/,0' app/desktop/src/App.tsx | { grep -oE '\buseEffect\b' || true; } | wc -l     # 13
awk '/^export default function App\(/,0' app/desktop/src/App.tsx | { grep -oE '\buseCallback\b' || true; } | wc -l   # 44
{ grep -oE '\buseState\b' app/desktop/src/App.tsx || true; } | wc -l      # 42
{ grep -oE '\buseRef\b' app/desktop/src/App.tsx || true; } | wc -l        # 40
{ grep -oE '\buseEffect\b' app/desktop/src/App.tsx || true; } | wc -l     # 15
{ grep -oE '\buseCallback\b' app/desktop/src/App.tsx || true; } | wc -l   # 45
```

| Hook | `App()` 本體（現在） | C1-S3 基準 | 整檔（含 import 1 次） | C1-S3 基準 |
|---|---:|---:|---:|---:|
| `useState` | 34 | 35 | 42 | 43 |
| `useRef` | 36 | 35 | 40 | 39 |
| `useEffect` | 13 | 14 | 15 | 16 |
| `useCallback` | 44 | 42 | 45 | 43 |

整檔與本體的差額：`useState` 8 = import 1 + `SlashComposer` 5（366–369、372）+ `RestoredToolActivity` 1（651）+ `MessageBody` 1（842）；`useRef` 4 = import 1 + `SlashComposer` 2 + `MessageBody` 1；`useEffect` 2 = import 1 + `SlashComposer` 395；`useCallback` 1 = import。另有 `useLayoutEffect` 在 386（`SlashComposer`）與 848（`MessageBody`），皆不在 `App()`。`App()` 本體另有 `useReducer` 2、`useMemo` 3。行數：`App.tsx` 3000（基準 3059），`App()` 起點 1002（基準 1026）。

### 5.1 後端呼叫點（`grep -n "backendClient\.\|invoke(" src/App.tsx` 的輸出行，共 26 行）

```
205:  request: ... = backendClient.request,                     (loadSelectedProjectHistory 預設參數，模組層)
559:  request = backendClient.request,                           (fetchTranscriptPage 預設參數，模組層)
581:  request = backendClient.request,                           (selectConversationWithPreview 預設參數，模組層)
1211:        const tracked = backendClient.requestTracked("document.apply", {
1242:    const tracked = backendClient.requestTracked("bibliography.add", { identifier });
1271:      const opened = await backendClient.request("document.open", { path })
1301:      const result = await backendClient.request("document.save", { documentContext: ...
1531:        const snapshot = await backendClient.initialize(() => {
1573:    const operation = action === "start" ? backendClient.start : action === "restart" ? backendClient.restart : backendClient.shutdown;
1587:      const data = await backendClient.request("runtime.diagnostics", {});
1605:      const loaded = await loadSelectedProjectHistory(currentProject.projectId, backendClient.request, isCurrent);
1633:      const result = await backendClient.request("session.rename", { ...
1687:      const data = await backendClient.request("workspace.select", {
1773:        const data = await backendClient.request("session.list", { projectId, offset, limit: 50 })
1803:    void backendClient.request("workspace.select", { rootPath: project.rootPath, action: "open" })
1906:    const pending = Promise.resolve().then(() => backendClient.request("session.stop", {
1975:      const result = await backendClient.request("session.delete", { ...
2030:    void backendClient.request("approval.resolve", {
2201:        const data = await backendClient.request("session.create", { projectId: activeProjectId });
2280:        const inspected = await backendClient.request("workspace.select", { rootPath: selectedProject.rootPath, action: "inspect" })
2297:      tracked = backendClient.requestTracked("session.turn", {
2462:    void backendClient.request("extensions.preview", {}).then((data) => {
2495:    void backendClient.request("extensions.apply", request).then((data) => {
2585:      const data = await backendClient.request("session.set_thinking", { mode });
2616:      const data = (await backendClient.request("session.set_permission", { permissionMode: mode }))
2777:              request={backendClient.request}                (傳給 CitationPanel)
```

- `App()` 本體內共 23 行（1211–2777）：直接 `request(` 16（1271、1301、1587、1633、1687、1773、1803、1906、1975、2030、2201、2280、2462、2495、2585、2616）、`requestTracked(` 3（1211、1242、2297）、生命週期 `initialize` 1（1531）+ `start/restart/shutdown` 1（1573）、把 `request` 當值傳遞 2（1605、2777）。
- 模組層 3 行（205、559、581）是預設參數；另有 `fetchTranscriptPage` 的間接呼叫 `session.transcript`（1922、2244、2415、2560 與 `selectConversationWithPreview` 內）、`selectConversationWithPreview` 內的 `session.select`，這兩個方法在 `App.tsx` 中沒有直接的 `backendClient.request("session.transcript"|"session.select")` 字面。
- **`grep -n "invoke("` 在 `App.tsx` 命中 0 行**（字面 `invoke(` 不存在）。原生呼叫是 `invoke<`：`107`（`createBackendClient` 的 transport 包裝，模組層）、`1267`（`invoke<string | null>("pick_document", …)`）、`1662`（`invoke<string | null>("pick_project", …)`）。驗證用的 grep 請改成 `invoke[<(]`。
- 另有 Tauri 事件 API：`1416 listen<unknown>(BACKEND_EVENT_NAME, …)`（effect 1407 內）。C8-S3 若要「唯一呼叫後端與原生」，`listen` 也應算在內。

### 5.2 每個 `useEffect`（`App()` 內 13 個，全部列出）

| 行 | 用途 | 類型 |
|---|---|---|
| 1061 | 對話選取改變時清空 `selectedSkillNamesRef` | 輸入 |
| 1089 | 把 `conversation` 同步到 `conversationRef` | state mirror |
| 1090 | 把 `pendingApproval` 同步到 `pendingApprovalRef` | state mirror |
| 1156 | 對話選單開啟時把焦點移到選單 | 純 UI |
| 1407 | 註冊 backend 事件 listener、`initialize`；事件路由（lifecycle、crash、approval、document.proposed、turn.accepted、stage/tool 活動）；含 browser-preview 分支（1408–1411） | 協調（含後端呼叫 1531） |
| 1593 | backend ready 且無診斷時自動 `loadDiagnostics` | 協調（呼叫 1587） |
| 1791 | generation 改變後載入歷史或重新綁定專案（`workspace.select open`） | 協調（呼叫 1803） |
| 1866 | 註冊 `selectionchange` → `captureChatSelection` | 輸入 |
| 2062 | 核准到期計時自動 Deny | 核准 |
| 2073 | 核准失去擁有者時清除 | 核准 |
| 2182 | 重啟後依 `conversationToRestore` 自動重選對話 | 協調（呼叫 `selectConversation`） |
| 2656 | `workspaceIssue` 出現時把焦點回輸入框 | 純 UI |
| 2657 | `pendingUserText` 或 `liveTurns` 變動時捲到底 | 純 UI |

`SlashComposer` 的 `useEffect`（395）在 `App()` 之外，其餘 effect 都在上表。第 2、3 節的 refs 清單 36 個、本節 13 個 effect、5.1 節 23 個 `App()` 內後端呼叫行（含 `initialize`、生命週期、傳值）逐項涵蓋 `App()` 內全部的 effect、ref 與後端呼叫點；無遺漏。

## 6. 只為測試而匯出的函式、`trust.tsx` 純 helper、SSR 測試分類

### 6.1 `App.tsx` 的具名 export（共 33，另有 default export）

本檔所有具名 export 在 `src/` 其他檔案都沒有引用，也都在 `App.tsx` 內自用；`export` 只為測試（或根本沒測）。

| 類別 | 項目（行號） |
|---|---|
| 純函式（25，不含 JSX） | `sidebarRowsForProject` 143、`loadSelectedProjectHistory` 203（預設參數是 `backendClient.request`）、`projectDisplayName` 215、`shouldSubmitComposerKey` 219、`composerSlashCommands` 231、`slashPrefix` 246、`filterSlashCommands` 251、`insertSlashCommand` 255、`inlineSkillToken` 261、`insertInlineSkill` 274、`inlineSkillReferences` 279、`handleComposerKey` 296、`isPersistedTurnFailure` 544、`selectConversationWithPreview` 573（預設參數是 `backendClient.request`）、`mergeSessionItems` 639、`documentReference` 747、`backgroundDocumentContext` 764、`checkSubmissionSize` 770、`retrySettingsMatch` 777、`visibleMessageRange` 781、`documentContextPayload` 930、`reconcileSavedDocument` 939、`submittedDocumentSource` 965、`documentOperationContext` 972、`advanceWorkingDocumentSources` 977 |
| 型別（1） | `InlineSkillReference` 259 |
| 元件（7，含 JSX） | `DeleteConversationDialog` 170、`SlashCommandList` 327、`ComposerFooter` 340、`RestoredTurn` 676、`ConversationTurns` 718、`ReferenceCards` 823、`DocumentHeader` 894 |

- 完全沒有任何測試引用的 export：`documentReference`、`backgroundDocumentContext`、`checkSubmissionSize`、`retrySettingsMatch`、`ReferenceCards`、`DocumentHeader`、`InlineSkillReference`（型別）。
- 純函式但**未 export**、搬移時一併處理的：`mergeTranscriptItems` 526、`failureLifecycleLabel` 535、`transcriptTailOffset` 549、`transcriptViewFrom` 622、`shutdownSummary` 499、`newLogicalTurnId` 507、`workspaceError` 511、`protocolMismatch` 517、`isTauriRuntime` 469（C8-S4 刪）；`fetchTranscriptPage` 553 預設參數也是 `backendClient.request`，搬到 `.ts` 時需改成注入或移到 `api.ts`。
- 型別與常數：`SidebarSessionRow` 125、`TranscriptView` 132、`TRANSCRIPT_PAGE_SIZE` 130、`SlashCatalogOwner` 228、`DocumentAction` 955、`WorkingDocumentSources` 963、`phaseLabels` 113。

### 6.2 `trust.tsx`（547 行）

| 類別 | 項目（行號） |
|---|---|
| 純 helper（不含 JSX） | 型別 18–47、`createExtensionFlow` 51、`beginExtensionPreview` 63、`receiveExtensionPreview` 75、`decideExtensionBinding` 92、`approvedBindingHashes` 110、`beginExtensionApply` 123、`beginExtensionApplyRecovery` 139、`extensionApplyRequest` 149、`receiveExtensionApply` 157、`markExtensionRestarting` 165、`markExtensionAwaitingLoad` 170、`observeExtensionRevision` 175、`failExtensionFlow` 184、`failExtensionApply` 188、`interruptExtensionFlow` 207、`acceptApprovalEvent` 217、`ApprovalOwnerRequests`（interface）242、`approvalHasLiveOwner` 249、`reconcilePermissionAck` 441 |
| 元件（JSX） | `ApprovalDialog` 266、`PermissionControl` 375、`ThinkingControl` 397、`ExtensionPanel` 467 |

沒有測試引用的 helper：`beginExtensionPreview`、`failExtensionFlow`；`ThinkingControl` 沒有渲染測試。

### 6.3 經 Vite SSR 載入 `.tsx` 的測試（5 個檔，`grep -ln "ssrLoadModule\|createServer" tests/`）

載入對象：`trust.test.ts`→`trust.tsx`；`conversations.test.ts`→`App.tsx`、`SafeContent.tsx`；`documents.test.ts`→`DocumentEditor.tsx`、`App.tsx`；`inline_skills.test.ts`→`App.tsx`；`citation_preview.test.ts`→`CitationPanel.tsx`、`CitationText.tsx`。不是 SSR 但讀 `.tsx` 原始碼文字的：`trust.test.ts:395`（讀 `App.tsx`）、`editorZoom.test.ts:65`（讀 `DocumentEditor.tsx`）。

「純」＝只呼叫純函式；「渲染」＝`renderToStaticMarkup`。

| 檔案 | test（行號） | 分類 |
|---|---|---|
| `trust.test.ts`（13） | 114、128、137、177 extension flow 轉移；205 `acceptApprovalEvent`；289 `reconcilePermissionAck`；382 `approvalHasLiveOwner` | 純（7） |
| | 233、261、330、349、363 ApprovalDialog / PermissionControl / ExtensionPanel | 渲染（5） |
| | 395 讀 `App.tsx` 原始碼比對清除程式 | 原始碼比對（1，C8-S5 改寫） |
| `conversations.test.ts`（33） | 176、195、234、381、433、453、462、493、713、755、779、801、820、912 | 純，載 `App.tsx`（14） |
| | 269 `safeExternalUrl` | 純，載 `SafeContent.tsx`（1） |
| | 411、417、423、868 | 純，不經 SSR（4） |
| | 149 `DeleteConversationDialog`、254 `SlashCommandList`、516 `ConversationTurns`、559/595/651 `RestoredTurn`、852 `ComposerFooter` | 渲染，載 `App.tsx`（7） |
| | 626 `RestoredTurn` + slash 篩選（混合）| 渲染（1） |
| | 286、298、314、326、343 SafeContent 渲染；359 連結啟用（渲染 + `openSafeExternalUrl`） | 渲染，載 `SafeContent.tsx`（6） |
| `documents.test.ts`（8） | 35、49、63 | 純，載 `DocumentEditor.tsx`（3） |
| | 80、91、100、139 | 純，載 `App.tsx`（4） |
| | 111 `handleAnnotationKey` + `AnnotationComment` | 混合（渲染）（1） |
| `inline_skills.test.ts`（4） | 21、36、47、56 | 純，載 `App.tsx`（4） |
| `citation_preview.test.ts`（8） | 33、42、51、89 | 純，不經 SSR（4） |
| | 69 `ExportMenu`、107 `CitedRow/UncitedRow`、130 `CitationPanel`、144 `CitationText` | 渲染，載 `CitationPanel.tsx` / `CitationText.tsx`（4） |

渲染測試共 5 + 14（conversations：7 + 1 + 6）+ 1 + 4 = 24 個（`trust` 5、`conversations` 14、`documents` 1、`citation_preview` 4）；只測純函式、卻經 SSR 載入的有 7（trust）+ 15（conversations：14 + 1）+ 7（documents）+ 4（inline_skills）= 33 個，是 C8-S2 要改成直接 import 的對象。

## 7. browser-preview 降級模式的所有位置

`grep -rn "browserPreview\|isTauri\|__TAURI\|browser-preview\|BROWSER_PREVIEW" src tests`：

| 檔案:行 | 內容 |
|---|---|
| `backend.ts:53` | `SafeUiError.source` 聯集含 `"preview"` |
| `backend.ts:93` | `BackendUiState.browserPreview: boolean` |
| `backend.ts:103` | `initialBackendState.browserPreview: false` |
| `backend.ts:107` | `BackendUiAction` 的 `{ type: "browser-preview" }` |
| `backend.ts:210–222` | reducer 分支：phase `degraded`、`browserPreview: true`、錯誤 `BROWSER_PREVIEW`、source `"preview"` |
| `App.tsx:469–471` | `isTauriRuntime()`（檢查 `__TAURI_INTERNALS__`） |
| `App.tsx:1408–1411` | effect 1407 開頭：非 Tauri 時 `dispatch({ type: "browser-preview" })` 並 return |
| `App.tsx:2674、2678、2679、2680、2681、2686` | `canStart`、`canRestart`、`canShutdown`、`canCreateSession`、`canManageConversations`、`canDeleteConversation` 各含 `!state.browserPreview` |
| `App.tsx:2821` | 「Preparing your research workspace」條件含 `!state.browserPreview` |

- `tests/` 與 `index.html`、`vite.config.*`、`package.json` 中**沒有任何** `browserPreview`、`isTauri`、`__TAURI`、`browser-preview`、`BROWSER_PREVIEW` 引用：C8-S4 沒有現成的測試要刪；若要驗證刪除後行為，需新增 reducer 層級以外的覆蓋（非 Tauri 時 `listen`/`invoke` 丟錯 → 走一般 `action-failed` 路徑）。
- `backend.ts:53` 的 `"preview"` source 只被 `backend.ts:219` 使用，刪除模式時可一併刪掉；`citations.ts:164、172` 與 `CitationPanel.tsx:252` 的 `kind: "preview"` 是引用預覽，與此無關。

## 8. 給 C8-S2 至 C8-S6 的注意事項（探索中發現）

1. `grep "invoke("` 命中 0 行，原生呼叫是 `invoke<`；`listen<` 也是需要收進 `api.ts` 的原生邊界（見 5.1）。
2. 核准清除區塊是 10 處 `approvalResolvingRef.current = false`（C1 的稽核寫 11 次，以現況為準），而且只有 3 處（1229、1250、2049）同時清 `approvalOwnerRef`；其他 7 處留下舊擁有者。C8-S5 設計擁有者模組時要決定這是刻意還是遺漏。
3. `invalidateOperations`（1134）沒有重設 `citationRequestRef`、`exclusiveOwnerRef`/`inFlight`、`diagnosticsAttempt`、`selectedSkillNamesRef`、`resumeSelectionRef`、`resumeDraftRef`；是否刻意要在拆 hook 前確認，否則「集中重設」會改變行為。
4. citation 路徑的 listener（1442–1458）先於 1461 的 generation/epoch 守衛 return；`acceptApprovalEvent` 只蓋章 generation，不比對。目前靠 `invalidateOperations`/`clearTransientUi` 清除，沒有測試。
5. `ownsOperation(x, x)` 自我比較出現 5 處（1462、1464、1621、1794、1945），語意是「只看 generation/epoch 是否仍是目前值」；`ownsWorkspaceOperation` 本身沒有任何測試。
6. 多個 callback 以 `state.session` 閉包取值，而不是 ref（`stopTurn` 1920/1925、`sendTurn` 2355、2408、`applyExtensions` 2498/2511、`updateThinkingMode` 2592）；抽 hook 時依賴陣列改動會改變閉包時機，這些要保持原樣或加測試。
7. render 期間讀 ref：`activeProjectId`（2188）、`canManageConversations`（2682）、`canDeleteConversation`（2687）、`documentDirty`（2717，讀 `documentBaselineRef`）；`documentBaselineRef` 不是 state，所以 dirty 判斷靠別的 state 改變才會重算。拆分時要保留這個重算時機。
8. `loadSelectedProjectHistory`（205）、`fetchTranscriptPage`（559）、`selectConversationWithPreview`（581）的預設參數直接綁 `backendClient.request`，搬進 `.ts` 時要改成注入，否則 `.ts` 模組會 import `App.tsx` 的模組層 client。
9. 使用者可見的「Retry Stop」與衝突面板、核准的逾時與清除都在 JSX 或 effect 內，沒有任何測試；C8-S6 抽出純函式時優先處理 (e) 的 `receiveDocumentResult` 與 `resolveDocumentConflict`。
