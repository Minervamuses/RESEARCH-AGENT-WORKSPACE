# D5 跳轉、目前章節追蹤與即時更新

- **後置條件**：點大綱標題跳到文件對應位置且不改動文件；移動游標或捲動時大綱標出目前章節；所有修改來源都會更新大綱。
- **涵蓋**：G4、G5。
- **相依**：D4。
- **輸入**：GOALS G4、G5、A2、A3；PLANS「架構」第 2、3 點；S2 brief 的「Jump guard ordering」「Bottom-of-file active bounce」；PLANS「基線／編輯器」。

## 範圍

- 新增 `src/lib/outline/tracking.ts`（純狀態機＋`createOutlineTracker` 訂閱介面）與其測試；修改 `src/DocumentEditor.tsx`、`src/components/DocumentPane.tsx`（傳遞新 props）、`src/App.tsx`（tracker 與編輯器 handle 的 ref）、`src/components/OutlineView.tsx`、`src/styles/outline.css`。
- 不改 `publishSelection`、第二個 effect 與 `CitationPanel` 的跳轉路徑；不改建立 model 的依賴。

## 行為規格

- **編輯器回報**：`DocumentEditor` 新增可選 props：`onCursorLine(line)`（`onDidChangeCursorPosition`；model 建立後主動回報一次初始游標行）、`onViewport({ topLine, scrollTop })`（`onDidScrollChange` 且 `scrollTopChanged` 時，以 `requestAnimationFrame` 合併，讀 `getVisibleRanges()[0]?.startLineNumber` 與 `getScrollTop()`）、`onHandle(handle | null)`（建立後註冊 `{ jumpToOffset }`，釋放與換檔時傳 `null`）。所有 listener 與 rAF 在 `disposeEditor` 釋放／取消。
- **跳轉**：`jumpToOffset(offset)` 以目前 `snapshotRef` 的 `sourceText` 換算位置，`setPosition`（空選取）→ `revealLineNearTop(line, ScrollType.Immediate)`（A3；預設 Smooth，必須明確指定）→ `focus`（A2），回傳跳轉後的 `getScrollTop()`。這個序列寫成可注入假編輯器的純函式。不呼叫 `setSelection`，不經 `App.updateDocument` 推送帶範圍的快照。跳轉造成的游標事件照常經 `publishSelection` 讓 `App` 重繪一次（這是既有行為），範圍為空，不出現 `Add comment`。
- **handle 不存在**：Monaco 動態載入完成前或換檔途中 handle 是 `null`，此時點擊安靜略過（不拋例外、不改目前章節）。
- **過期點擊**：點擊時若大綱戳記與目前 `sourceText` 不同，先同步重新解析，用新樹中同 ID 的節點；找不到就不跳，並更新大綱。
- **目前章節**：以行號在扁平清單上二分搜尋，取起始行 ≤ 目標行的最後一個標題（最內層）；在第一個標題之前沒有目前章節。游標事件與捲動事件以最後發生者為準。tracker 保存最後的游標行、可視頂行與哪個較新；**大綱重新解析後以保存的行重算目前章節**；**換檔或文件變 `null` 時重設**（清掉目前章節、保存的行與跳轉保護）。
- **跳轉保護**：點擊時先 `armJump(targetId)`（在 `setPosition` 之前），目前章節立即設為目標；記下 `jumpToOffset` 回傳的 `scrollTop`。之後的游標事件若在目標行、捲動事件若 `scrollTop` 等於記錄值，不論同步到達或經 rAF 延後都忽略；捲動到不同 `scrollTop` 或游標移到其他行才解除並恢復正常追蹤。
- **收合中的目前章節**：目前章節的祖先被收合時，最近的可見祖先有不同於「目前章節」的標示；不自動展開。目前章節在大綱外時把它捲進大綱可視範圍（`scrollIntoView({ block: "nearest" })`），但不搶焦點。
- **即時更新**：所有修改都經 `documentValue.sourceText` 進到 D4 的 hook，不另外監聽 Monaco 內容。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| D5-S1 | `tracking.ts`：二分搜尋、最近可見祖先、跳轉保護狀態機、重新解析後重算、重設、訂閱介面。 | 測試：行號落在各節中段、剛好在標題行、第一標題之前、最後一節；巢狀時取最內層；收合祖先的標示對象；**依實際順序重播** `armJump` → 程式游標事件（目標行）→ 程式捲動事件（`scrollTop` 等於記錄值，分別以同步與延後到達各測一次）→ 使用者捲動（不同 `scrollTop`）：前兩個事件不改變目前章節，最後一個恢復追蹤；跳轉後游標移到別行也解除；換上一份行號不同的新大綱後，以保存的游標行重算出正確章節；重設後沒有目前章節也沒有保護；訂閱者只在目前章節 ID 改變時被通知 |
| D5-S2 | `DocumentEditor` 的三個 props 與釋放；`DocumentPane`／`App` 接線；`OutlineView` 以 `useSyncExternalStore` 讀目前章節並呼叫 handle 跳轉；過期點擊與 handle 不存在的處理；`outline.css` 的目前章節與祖先標示。 | `npm test` 全部通過（既有 `documents.test.ts` 等不得退步）；新增測試：**跳轉序列純函式**以假編輯器記錄呼叫，斷言順序為 `armJump` → `setPosition` → `revealLineNearTop(…, Immediate)` → `focus`，且從未呼叫 `setSelection` 或帶範圍的 `onChange`；過期點擊（戳記不同→重新解析→依 ID 找節點→找不到不跳）；handle 為 `null` 時點擊不拋例外、目前章節不變；SSR 測試目前章節與祖先標示的 class／`aria-current`。`npm run build` 通過。程式審查並在 build-log 記錄：建立 model 的 effect 依賴仍只有 `[value?.rootPath, value?.path]`、所有新 listener 在 `disposeEditor` 釋放 |
| D5-S3 | 即時更新的自動化覆蓋：以 `useDocumentOutline` 的純邏輯模擬「新增／刪除／改名／改層級／貼上大量內容／Agent 修改後的 `sourceText`／Undo 回到舊內容／換檔」，確認大綱結果與收合保留符合規格。 | 測試通過；Monaco 內實際的 Undo／Agent 修改／衝突處理列入 D8 手動清單 |

## 交付給後續階段

完整的 P0 功能。D6、D7 只在這之上加功能。
