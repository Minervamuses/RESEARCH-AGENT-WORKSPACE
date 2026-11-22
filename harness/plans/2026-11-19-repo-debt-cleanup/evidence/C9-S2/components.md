# C9-S2 元件拆分（S097、U18、U22）

基準：C9-S1 之後的 HEAD `05575ec`（C8 結束時 `App.tsx` 2,462 行）。元件只收值與 callback，不呼叫 `api.`，沒有全域 store（R1）。

## 一、commit 與元件

| commit | 內容 |
|---|---|
| C9-S2a | `trust.tsx` 依職責拆成 `components/ApprovalDialog.tsx`、`ComposerControls.tsx`（`PermissionControl`、`ThinkingControl`）、`ExtensionPanel.tsx`；`trust.tsx` 刪除 |
| C9-S2b | `Transcript.tsx`、`messageParts.tsx`；annotation UI 從 `DocumentEditor.tsx` 移到 `Annotation.tsx` |
| C9-S2c | `Composer.tsx`（`Composer`＝原 `SlashComposer`、`SlashCommandList`、`ComposerFooter`） |
| C9-S2d | `Sidebar.tsx`、`DocumentPane.tsx`、`ProjectChooser.tsx`、`RuntimeDetails.tsx`、`ConversationDialogs.tsx`、`StatusNotices.tsx`，`Composer.tsx` 加 `ComposerNotices`，`phaseLabels.ts` |

### 元件與 props 摘要（`src/components/`）

| 元件 | props 摘要 |
|---|---|
| `Modal.tsx::ModalDialog` | `as`、`className`、`backdropClassName`、`labelledBy`／`describedBy`、`modal`、`dismissible`＋`onDismiss`、`preventEscapeWhenBlocked`、`blockEmptyTab`、`focusSelector`、`dismissOnBackdrop`、`onSubmit`（見 C9-S1） |
| `Sidebar` | `phase`、`snapshot`、`project`、`list`、`selected`、`selectedSaved`、`historyLoaded`、各 disabled 旗標（`newConversationDisabled`、`chooserDisabled`、`selectionDisabled`、`canStart`／`canRestart`／`canShutdown`）；callback：`onCreateConversation`、`onShowChooser`、`onSelectConversation`、`onLoadMore`、`onOpenMenu(menu, returnFocus)`、`onLifecycle`。內含 `ProjectGroup` |
| `DocumentPane` | `document`、`dirty`、`busy`、`notice`；`header`（3 個 disabled＋`onOpen`／`onSave`／`onUndo`）、`editor`（`onChange`、`annotationControls`、`onAddReference`、`citationEntries`）、`citation`（`CitationPanel` 的 props 或 `null`；`api` 以 prop 傳入）、`conflict`＋`onResolveConflict`。內含 `DocumentHeader`、`DocumentConflictPanel` |
| `Transcript` | `turns`、`projectId`、`annotationControls`、`transcriptRef`／`endRef`、`hasOlder`、`issue`、`empty`、`loadOlderDisabled`、`onLoadOlder`；另匯出 `ConversationTurns`、`RestoredTurn` |
| `Composer` | 原 `SlashComposer` 的 props 不變（`draft`、`references`、`commands`、`skills`、disabled 旗標、`onChange`、`onSubmit`…）；`ComposerNotices`：`savedTurn`、`controlsMatch`、`canSendNew`、`sendNewDisabled`、`onSendNew`、`referenceIssue` |
| `ProjectChooser` | `switching`、`candidate`、`candidateHistory`、`issue`、`busyLabel`、`documentDirty`、`dirtyChoice`、`hasDraft`、`discardDraft`；callback：`onHistoryChange`、`onDirtyChoiceChange`、`onDiscardDraftChange`、`onBrowse`、`onInspectHistory`、`onConfirm(action)`、`onCancel` |
| `RuntimeDetails` | `diagnostics` |
| `ConversationDialogs` | `DeleteConversationDialog`（原樣）、`RenameConversationDialog`（`title`、`issue`、`titleTooLong`、`busy`、`saving`、`canSave`、callbacks）、`ConversationMenu`（位置、`menuRef`、`canRename`／`canDelete`、`onRename`／`onDelete`／`onClose`／`onDismiss`） |
| `StatusNotices` | `RecoveryNotice`（`kicker`、`title`、`message`、`actions`）、`StopFailureNotice`、`HistoryNotice`、`PreparingState`、`StoppedState`、`TransitionState`、`LocalRequestState`、`BackendReadyCard` |
| `ApprovalDialog`、`ComposerControls`、`ExtensionPanel`、`Annotation` | 原 props 不變（搬移） |

`App()` 仍擁有所有 state、ref、effect 與 operation 邏輯；條件渲染的「是否顯示」判斷留在 `App()`，元件只畫。1,000 字元以上的單行 JSX 原有 1 行（1,468 字元的錯誤卡片），現在 `src/*.tsx`、`src/components/*.tsx` 沒有超過 600 字元的行。

## 二、Transcript：三種渲染的分析（U22）

| | RestoredTurn | CompletedTurn（live） | PendingTurn |
|---|---|---|---|
| 資料 | `TranscriptTurnDto`（儲存的歷史，狀態 completed／pending／failed／interrupted，`kind` 含 display-only） | `LiveTurn`（本次已完成，`responseKind` answer／command） | `PendingConversationTurn`（進行中，`activity` 清單） |
| 生命週期 | 載入或重新整理時整批取代；`memo` | 回合完成後加入，與 restored 以 `turnId` 合併 | 送出到完成之間；完成後被 live／restored 取代 |
| 互動 | 使用者與助理文字可 annotation；工具細節 `details` 懶載入 | 使用者與助理文字可 annotation | 使用者文字**不**接 annotation；無助理內容；顯示 spinner 與 stage／tool 活動 |
| 標籤 | `You · restored turn N`、`Assistant · restored`、`Pending/Failed/Interrupted · saved locally` | `You`、`Assistant · complete`／`Local command output · complete` | `You · pending／retrying`、`Assistant · working` |

**共用（`messageParts.tsx`）**：`MessageCard`（`.message` 加 `<kind>-message` 與 `.message-label` 的標記，工具參數與結果卡也用它）、`MessageBody`（`SafeContent`＋annotation 錨點）、`ReferenceCards`、`SafeContent`（`memo`）。`App.tsx` 不再出現 `.message`、`.tool-*` 的任何細節。

**不合併成單一 variant 元件**：三者的資料型別、助理區塊的狀態分支（restored 有 4 種狀態與 display-only、live 只有 2 種、pending 是 spinner 加活動清單）、是否接 annotation 與工具細節都不重疊；合併會得到一個以 `source` 切換的大分支元件，卻沒有共用的邏輯。`ConversationTurns` 已經是以 `item.source` 分派到三個入口的薄 variant 分派器，這就是 U22 要的最小耦合。

## 三、`trust.tsx` 的拆分（依職責）

- `ApprovalDialog`：核准框（Bash 與 operation 的兩種顯示、Stop、非 modal 變體），用 `ModalDialog`。
- `ComposerControls`：`PermissionControl`、`ThinkingControl`（用 `useDisclosureMenu`）。
- `ExtensionPanel`：擴充預覽與套用流程的畫面（邏輯仍在 `lib/extensionFlow.ts`、`hooks/useExtensions.ts`）。

## 四、測試異動與退役

- 沒有刪除任何測試。`tests/trust.test.ts` 與 `tests/documents.test.ts`、`tests/conversations.test.ts` 的 SSR 載入改指向新元件（`ApprovalDialog`／`ComposerControls`／`ExtensionPanel`、`Annotation`、`Transcript`、`Composer`、`ConversationDialogs`）；`conversations.test.ts` 不再 SSR 載入整個 `App.tsx`，單檔 test 時間由約 8 秒降低。
- 新增 2 個靜態渲染測試（`conversations.test.ts`）：「a live turn renders its own cards…」（answer 與 command 兩種）、「a pending turn renders the prompt, a working card with a spinner…」。restored 已有 5 個測試（懶載入工具、巨量答案、citation 保存、終態、retry 不重複顯示）。三種入口各至少 1 個靜態渲染測試。
- `editorZoom.test.ts` 讀 `DocumentEditor.tsx` 的按鍵綁定：搬走的只有 annotation UI，被比對的程式沒動，測試不改（C9-S4 處理）。

## 五、檢查

- `npm test`：256 pass（C9-S1 後 254；+2）。`npm run build`：通過。
- `grep -rn "api\." src/components` → **0**。唯一相關：`DocumentPane` 的 `citation.api` 是 `App` 傳入的物件，由 `CitationPanel`（在 `src/`，非 components）使用；元件目錄內沒有 `api.` 呼叫。
- `grep -n 'className="[^"]*\(message\|tool-\)' src/App.tsx` → 0。
- `App.tsx` 行數：**2,462（C8-S7）→ 1,932**。

## 六、GUI 清單（需人工）

1. Sidebar：選對話、右鍵選單開啟位置（靠近視窗邊緣時被夾住）、Load more、Start／Restart／Shut down、狀態點與文字。
2. DocumentPane：開檔、儲存（Ctrl+S 與選單）、Undo、未儲存圓點、`Working…`、文件衝突三個選項、citation 面板顯示條件。
3. Transcript：restored、live、pending 三種卡片外觀不變；工具活動展開；章節 annotation 標記與彈出視窗位置；Load older 與空對話提示；預覽模式（切換對話時）。
4. Composer：Enter／Shift+Enter／IME；`/`、`@` 清單；Stop；重試設定提示與「Send new turn with current settings」；reference issue 提示。
5. ProjectChooser：選資料夾、history 目錄編輯與 Inspect、未儲存文件選項、丟棄草稿勾選、按鈕狀態文字。
6. 通知：錯誤卡片的 4 個按鈕、Stop 失敗卡片、History 未更新卡片、四種 empty state、Backend ready 卡片與 runtime details。
7. 核准框與 `ThinkingControl`、`PermissionControl`：外觀與 C9-S1 清單。
