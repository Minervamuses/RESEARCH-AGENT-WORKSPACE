# C8 — 前端邏輯層

- **完成後的狀態**：
  - 純邏輯在 `.ts` 模組，測試直接 import，且 `tsc` 也檢查測試。
  - `api.ts` 是唯一呼叫後端與原生 picker 的地方。
  - `App()` 的 domain state 移進 hooks。
  - browser-preview 降級模式已刪除。
  - 正當的錯誤訊息不再被整句隱藏。
- **涵蓋**：G6、G7（缺陷 #3）
- **相依**：C3、C4、C5、C6，因為 DTO 與方法清單要先穩定。C8 不依賴 C7。
- **輸入**：
  - [GOALS.md](../GOALS.md) 的 U5、P6。
  - [稽核原文](../context/repo-debt-audit-2026-11-19.md)的 S071、S078–S083、S089、S093、S097。

## 限制

- 前端不新增 npm 套件，所以不引入 jsdom 或 testing-library，也就沒有互動式的 DOM 測試。
- 但現有測試已經用 `react-dom/server` 的 `renderToStaticMarkup`，經由 Vite SSR 載入 `.tsx`，對元件做**靜態渲染測試**，例如 `tests/trust.test.ts` 約 250 行渲染 `ApprovalDialog`，`citation_preview`、`documents`、`conversations` 也有。這些測試與它們的 Vite SSR 載入方式**要保留**；C9 新拆出的元件也可以用同一方式加靜態渲染測試。
- 可測的狀態轉移一律抽成純函式，以 `node:test` 直接測試。
- **原始碼比對測試要跟著搬移的程式在同一步改寫（S086）。** 有些測試直接讀 `src/*.tsx` 的原始碼文字做比對，例如：
  - `tests/trust.test.ts` 約 400–409 行比對 `App.tsx` 的 approval 清除程式；
  - `tests/editorZoom.test.ts` 約 64–71 行比對 `DocumentEditor.tsx`。
  搬移被比對的程式時，同一步就把該測試改成對抽出的純函式或常數做行為測試，並寫退役紀錄，否則該步的 `npm test` 會失敗。C9-S4 只處理到那時還沒被改寫的部分。
- 執行者看不到畫面。每個 hook 抽出後，對應的使用者流程都要進 GUI 清單。
- INV-022（IME Enter 不送出等輸入行為）與 INV-017（不可信內容的顯示）的實作只搬移，不改寫。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| C8-S1 | **行為盤點（探索）。** 讀 `App.tsx`、`trust.tsx`、`backend.ts`、`conversations.ts`，列出使用者可見的流程，寫入 `evidence/C8-S1/app-behaviors.md`。流程包括：<br>• 啟動、backend crash 與重啟；<br>• 專案選擇與初始化；<br>• session 的建立、選擇、改名、刪除；<br>• 送出、Stop、Retry；<br>• 核准對話框；<br>• 文件的開啟、存檔與套用；<br>• 引用面板；<br>• thinking 與 permission 控制；<br>• 擴充的預覽與套用；<br>• 斜線選單與 `@` 選單。<br>每個流程寫明觸發方式與預期畫面。這份清單是 C10 GUI 清單的基礎。 | 清單涵蓋 `App()` 內的每個 effect 與每個 backend 呼叫點（`backendClient.`、`invoke(`），數量以 C1-S3 的計數為準；以 grep 對照計數並存證。 |
| C8-S2 | **S083：純邏輯模組化。**<br>• 把 `App.tsx` 約 31 個只為測試匯出的函式，以及 `trust.tsx` 等 `.tsx` 中的純函式，搬到 `.ts` 模組。路徑是提案，例如 `src/lib/`。<br>• 只測純函式的測試改成直接 import `.ts` 模組，不再經由 Vite SSR。<br>• 會渲染 `.tsx` 元件的測試（`renderToStaticMarkup`）保留 Vite SSR 載入，只把手寫的模組型別改成 `typeof import("../src/<模組>.tsx")`，讓 `tsc` 能檢查。<br>• 改動前先列出 5 個 SSR 測試檔中每個 test 屬於「純函式」或「元件渲染」，寫入 evidence。<br>• 讓 `tsc --noEmit` 檢查 `tests/`：把 `tests` 加入 `tsconfig.json` 的 `include`；若會與 Node strip-types 的寫法衝突，改用一個只做型別檢查的 `tsconfig.test.json`，並讓 `npm run build` 也跑它。 | • `npm test`、`npm run build` 通過。<br>• `grep -ln "ssrLoadModule\|createServer" tests/` 只剩含元件渲染測試的檔案，以及 C3-S1 選了 Vite SSR 備案時的 `protocol.test.ts`，逐一註明。<br>• 元件渲染測試的數量與改動前相同，或減少的部分有退役紀錄。<br>• 在測試中故意放一個型別錯誤時 `npm run build` 會失敗；驗證後還原，結果寫入 evidence。 |
| C8-S3 | **S082、S093：`api.ts`。**<br>• 每個用到的方法一個型別化的函式，參數與回傳都用 DTO 型別。U1 的回聲檢查集中在這裡。<br>• 回聲比對依 [C3 的回聲比對規則](phase-03-protocol-single-source.md#回聲比對規則)，比對清單從 contract 推導。<br>• 原生 picker `pick_project`、`pick_document` 也從這裡呼叫。<br>• 移除約 29 處 `as unknown as XDto`、約 19 處就地的回聲檢查，以及 `App.tsx` 中直接的 `invoke("pick_*")`。 | • `npm test`、`npm run build` 通過。<br>• `grep -rnE "invoke\(|backendClient\.|\.request\(|as unknown as" src` 的命中只在 `api.ts` 與 `backend.ts`。目前 `App.tsx` 約 2620 行直接呼叫 `backendClient.request(...)`，也要移走。 |
| C8-S4 | **U5：刪除 browser preview（S078）。**<br>• 刪除 `backend.ts` 與 `App.tsx` 中的降級模式守衛（稽核列出的位置）與它的測試。<br>• 不在 Tauri 內執行時，走一般的「後端無法連線」錯誤路徑，不另做橫幅。 | • `npm test`、`npm run build` 通過。<br>• grep `browserPreview\|isTauri` 的特判（實際名稱以盤點為準）為 0，只剩建立 backend client 時必要的一個判斷。 |
| C8-S5 | **P6：錯誤遮蔽（S089，缺陷 #3）。**<br>1. 盤點 UI 會顯示的錯誤字串來源：Python 業務錯誤、TS 協定錯誤、Rust 的 bridge 與 process 錯誤。<br>2. 確認 Python 的 `_map_exception`（C7 之後在 `errors.py`；若 C7 尚未完成，在 `service.py`）會遮蔽憑證格式的值：API key 樣式、`Authorization`／`Bearer` 標頭值、URL 中的憑證。若不會，就在 Python 這唯一的地方加上以值辨識的遮蔽，可沿用 `service.py` 約 172–178 行既有的 secret 正規式。<br>3. 刪除 TS 的 `sensitiveMessagePattern` 依關鍵字整句隱藏的做法。 | • Python 測試：例外訊息含 `sk-or-v1-…` 樣式的 key 或 `Bearer xyz` 時，送出的錯誤訊息中只有遮蔽後的值。<br>• TS 測試：業務錯誤 `Prompt exceeds the context token limit` 原文顯示。<br>• grep `sensitiveMessagePattern` 為 0。 |
| C8-S6 | **S097 的 hooks、S080、S079（可拆成 C8-S6a、C8-S6b…）。** 一次抽一個 hook，各自一個 commit。提案名稱：<br>• `useBackendEvents`<br>• `useApproval`：S080，11 處 approval 清除收斂成一個實作。同一步改寫 `trust.test.ts` 約 400–409 行對 `App.tsx` 原始碼的比對，改測 `useApproval` 用到的純函式（例如既有的 `approvalHasLiveOwner`），並保留「`bibliography.add` request 也算 approval 擁有者」這個行為斷言。<br>• `useWorkspaceOperations`<br>• `useDocumentWorkspace`<br>• `useTurn`<br>• `useConversationCatalog`：S079，以 store 式 reducer 或 `useSyncExternalStore`，讓 reducer 每個 action 只跑一次<br>• `useExtensions`<br>做法：<br>• 可測的狀態轉移抽成純函式並加測試，放在既有的對應測試檔，例如 `conversations.test.ts`、`trust.test.ts`。<br>• S071 的其餘部分：`DocumentSnapshot`、`DocumentResult` 與 `DocumentContextDto` 統一成一個型別。 | • 每個 commit 都通過 `npm test`、`npm run build`。<br>• 最後 `App()` 函式本體內剩下的每個 `useState`、`useRef`、`useEffect` 都列在 evidence，逐一標明「純 UI」（展開、焦點、捲動），並與 C1-S3 的計數比較。<br>　- 標不出純 UI 的就是 domain state，要移進 hook。<br>　- `App()` 函式本體內不可有 `api.` 以外的後端呼叫。<br>• approval 清除只有一份實作，以 grep 確認。 |
| C8-S7 | **階段收尾。** `npm test`、`npm run build`。<br>重新量測 `App.tsx` 行數，以及 `useState`、`useRef`、`useEffect` 數，與 `evidence/C1-S3` 比較。<br>GUI 清單依 C8-S1 更新。 | 全部通過；量測存證。 |

## 失敗與續作

- 拆 hook 時若某個流程的行為無法從程式碼確定（例如 effect 之間的時序），就保持原本的 effect 順序不變，並在 GUI 清單中標為高風險項目。不要用猜測去改寫。
- 某個 hook 兩次聚焦修正後仍無法通過檢查：保留已完成的 hooks，以 checkpoint 保存，繼續下一個不相依的 hook。

## 交給後續階段

C9 拆元件時，`App()` 只剩組裝與 JSX。元件只要接 hooks 回傳的值。
