# C8 — 前端邏輯層（U5、U18）

- **完成後的狀態**：
  - 純邏輯在 `.ts` 模組，測試直接 import，且 `tsc` 也檢查測試。
  - `api.ts` 是唯一呼叫後端與原生 picker 的地方，request 參數也受 DTO 一致性檢查。
  - browser-preview 降級模式已刪除。
  - `App()` 依 domain 拆解：可測的判斷在純模組，domain 邊界清楚的 state 與 effect 在 hooks，跨 domain 的協調集中在一處。
  - 後端重啟、Stop、核准與過期回應的既有檢查都保留，而且有純函式測試。
- **涵蓋**：G6
- **相依**：C3、C4、C5、C6，因為 DTO 與方法清單要先穩定。C8 不依賴 C7。
- **輸入**：
  - [GOALS.md](../GOALS.md) 的 U5、U18、R1、R2。
  - [稽核原文](../context/repo-debt-audit-2026-11-19.md)的 S071、S078–S083、S093、S097。

## 拆解原則（U18）

2026-11-20 的討論改變了這一階段的方向。原計劃列了七個提案 hooks；這裡不再要求固定數量，而是以下列原則判斷：

1. **可測性來自純邏輯，不來自 hooks。** 沒有 jsdom 時，custom hook 和 `App()` 一樣無法在 `node:test` 執行。所以每個狀態轉移、守衛與判斷，先抽成 `.ts` 純函式並測試；hook 只是把它接到 React 的薄包裝。
2. **保留 React 原有的狀態管理。** 不引入全域 store、外部 store、controller class 或 `useSyncExternalStore` 式的全域狀態（R1）。
3. **hook 之間不互傳 ref 或 setter。** 要避免的是：拆完之後只是把一個檔案裡的相依關係，變成多個 hooks 互傳十幾個 ref 與 setter。
   - 一個 domain 只有在它的 state、ref 與 effect 都屬於自己，而且參數與回傳能用幾行說清楚時，才抽成 hook。
   - 一個 hook 需要另一個 domain 的資訊時，接收的是值或一個在協調處定義的 callback，不是對方的 ref 或 setter。
   - 做不到時就不抽，留在 `App()`，並在 evidence 寫明原因。
4. **跨 domain 的協調集中在一處。** 開關專案、後端重啟或 generation 改變時要重設多個 domain 的邏輯，集中在 `App()` 或單一的協調 hook，不分散到各 domain 的 hooks。
5. **必要檢查要保留，而且有測試。** 這些守的都是支援的循序使用（GOALS U12）：
   - 後端重啟或 crash 後，舊 generation 的回應與 event 不被套用；
   - Stop 與 Retry Stop 的畫面狀態；
   - 核准的擁有者、逾時與過期清除；
   - 已結束或已被取代的操作晚到的回應（`isCurrent`、`ownsOperation`、`projectEpoch` 的比對）；
   - 文件衝突。
   「專案 A 和 B 同時操作」不是驗收目標，不為它新增檢查或測試。

## 限制

- 前端不新增 npm 套件，所以不引入 jsdom 或 testing-library，也就沒有互動式的 DOM 測試。
- 現有測試已經用 `react-dom/server` 的 `renderToStaticMarkup`，經由 Vite SSR 載入 `.tsx`，對元件做**靜態渲染測試**，例如 `tests/trust.test.ts` 約 250 行渲染 `ApprovalDialog`，`citation_preview`、`documents`、`conversations` 也有。這些測試與它們的 Vite SSR 載入方式**要保留**；C9 新拆出的元件也可以用同一方式加靜態渲染測試。
- **原始碼比對測試要跟著搬移的程式在同一步改寫（S086）。** 有些測試直接讀 `src/*.tsx` 的原始碼文字做比對，例如：
  - `tests/trust.test.ts` 約 400–409 行比對 `App.tsx` 的 approval 清除程式；
  - `tests/editorZoom.test.ts` 約 64–71 行比對 `DocumentEditor.tsx`。
  搬移被比對的程式時，同一步就把該測試改成對抽出的純函式或常數做行為測試，並寫退役紀錄，否則該步的 `npm test` 會失敗。C9-S4 只處理到那時還沒被改寫的部分。
- 執行者看不到畫面。每次抽出後，對應的使用者流程都要進 GUI 清單。
- INV-022（IME Enter 不送出等輸入行為）與 INV-017（不可信內容的顯示）的實作只搬移，不改寫。
- 錯誤遮蔽已在 C2-S11 改到 Python 出口；本階段不再處理。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| C8-S1 | **行為與狀態盤點（探索）。** 讀 `App.tsx`、`trust.tsx`、`backend.ts`、`conversations.ts`，寫入 `evidence/C8-S1/app-behaviors.md`：<br>1. **使用者可見的流程**：啟動、backend crash 與重啟；專案選擇與初始化；session 的建立、選擇、改名、刪除；送出、Stop、Retry；核准對話框；文件的開啟、存檔與套用；引用面板；thinking 與 permission 控制；擴充的預覽與套用；斜線選單與 `@` 選單。每個流程寫明觸發方式與預期畫面。這份清單是 C10 GUI 清單的基礎。<br>2. **每個 `useRef` 的分類**：DOM ref、state 鏡像、操作擁有者、generation 或 epoch 計數、進行中的 promise。2026-11-19 的粗估是約 5 個 DOM、約 7 個鏡像、約 20 個擁有者與計數，以實際盤點為準。<br>3. **必要檢查清單**：上方原則 5 的每一項，對應到程式位置。<br>4. **domain 草圖**：每個候選 domain 擁有哪些 state、ref、effect，以及它會需要其他 domain 的哪些資訊。依原則 3 標出哪些適合抽成 hook、哪些應留在協調處。 | 清單涵蓋 `App()` 內的每個 effect、每個 ref 與每個 backend 呼叫點（`backendClient.`、`invoke(`），數量與 C1-S3 的計數一致；以 grep 對照計數並存證。 |
| C8-S2 | **S083：純邏輯模組化。**<br>• 把 `App.tsx` 約 31 個只為測試匯出的函式，以及 `trust.tsx` 等 `.tsx` 中的純函式，搬到 `.ts` 模組。路徑是提案，例如 `src/lib/`。<br>• 只測純函式的測試改成直接 import `.ts` 模組，不再經由 Vite SSR。<br>• 會渲染 `.tsx` 元件的測試（`renderToStaticMarkup`）保留 Vite SSR 載入，只把手寫的模組型別改成 `typeof import("../src/<模組>.tsx")`，讓 `tsc` 能檢查。<br>• 改動前先列出 5 個 SSR 測試檔中每個 test 屬於「純函式」或「元件渲染」，寫入 evidence。<br>• 讓 `tsc --noEmit` 檢查 `tests/`：把 `tests` 加入 `tsconfig.json` 的 `include`；若會與 Node strip-types 的寫法衝突，改用一個只做型別檢查的 `tsconfig.test.json`，並讓 `npm run build` 也跑它。 | • `npm test`、`npm run build` 通過。<br>• `grep -ln "ssrLoadModule\|createServer" tests/` 只剩含元件渲染測試的檔案，以及 C3-S1 選了 Vite SSR 備案時的 `protocol.test.ts`，逐一註明。<br>• 元件渲染測試的數量與改動前相同，或減少的部分有退役紀錄。<br>• 在測試中故意放一個型別錯誤時 `npm run build` 會失敗；驗證後還原，結果寫入 evidence。 |
| C8-S3 | **S082、S093：`api.ts`。**<br>• 每個用到的方法一個型別化的函式，參數與回傳型別取自 `protocol.ts` 的型別對照。U1 的回聲檢查集中在這裡。<br>• 在 `protocol.ts` 加上 `MethodParams`（方法名稱 → 參數 DTO），由 `api.ts` 使用；C3-S3 的 DTO 一致性檢查擴充到它，沿用同一個比對函式。<br>• 回聲比對依 [C3 的回聲比對規則](phase-03-protocol-single-source.md#回聲比對規則)，比對清單從 contract 推導。<br>• 原生 picker `pick_project`、`pick_document` 也從這裡呼叫。<br>• 移除約 29 處 `as unknown as XDto`、約 19 處就地的回聲檢查，以及 `App.tsx` 中直接的 `invoke("pick_*")`。 | • `npm test`、`npm run build` 通過。<br>• DTO 一致性檢查涵蓋 `MethodParams`；負向演練：暫時讓 contract 某方法多一個必填參數，`npm test` 失敗；還原後寫入 evidence。<br>• `grep -rn "invoke(\|backendClient\.\|\.request(\|as unknown as" src`（GNU grep 的基本正規式，`\|` 是「或」）的命中只在 `api.ts` 與 `backend.ts`。目前 `App.tsx` 約 2620 行直接呼叫 `backendClient.request(...)`，也要移走。 |
| C8-S4 | **U5：刪除 browser preview（S078）。**<br>• 刪除 `backend.ts` 與 `App.tsx` 中的降級模式守衛（稽核列出的位置）與它的測試。<br>• 不在 Tauri 內執行時，走一般的「後端無法連線」錯誤路徑，不另做橫幅，也不建立假資料的替代路徑（R2）。 | • `npm test`、`npm run build` 通過。<br>• grep `browserPreview\|isTauri` 的特判（實際名稱以盤點為準）為 0，只剩建立 backend client 時必要的一個判斷。 |
| C8-S5 | **S079、S080：對話 reducer 與核准擁有者。**<br>• **S079**：`applyConversation` 目前每個 action 跑兩次 reducer（先手動跑一次更新 ref，再 dispatch 一次）。改成每個 action 只計算一次新狀態，再同時更新 ref 與 React state，例如一個只在本 domain 使用的小 helper。不引入外部 store。<br>• **S080**：approval 清除區塊目前重複 11 次，同一概念用了 3 個 ref 與 2 個 state。把 approval 擁有者的追蹤抽成一個純狀態模組，涵蓋三件事：登記與清除擁有者、決定要不要接受某個 `approval.required`、判斷過期清除。React 端只剩一個薄包裝。<br>• 同一步改寫 `trust.test.ts` 約 400–409 行對 `App.tsx` 原始碼的比對。那個原始碼測試除了 `approvalHasLiveOwner` 的呼叫，還守著兩件事：發出 `bibliography.add` 時會登記為 approval 擁有者，以及事件 listener 會接受 `requestId` 等於該 add request 的 `approval.required`。`approvalHasLiveOwner` 本身已有單元測試（約 387 行），只再測它不夠。 | • `npm test`、`npm run build` 通過。<br>• reducer 測試：一個 action 只呼叫 reducer 一次（以計數的 reducer 包裝斷言）。<br>• 核准擁有者模組的完整流程測試：<br>(a) 發出 `bibliography.add` 後，擁有者已登記；<br>(b) 收到 `requestId` 相符的 `approval.required`，會被接受並設為待核准；<br>(c) add request 仍在進行時，過期清除不會關掉核准框；<br>(d) add request 結束後，同一核准被判為過期而清除；<br>(e) `requestId` 不相符的 `approval.required` 不被接受。<br>文件與回合 request 的擁有者也用同樣的流程測至少一條。<br>• approval 清除只有一份實作，以 grep 確認。 |
| C8-S6 | **S097：依 domain 拆解 `App()`（可拆成 C8-S6a、C8-S6b…）。** 依 C8-S1 的 domain 草圖與上方原則，一次處理一個 domain，各自一個 commit：<br>1. 把這個 domain 的判斷與狀態轉移抽成純函式並測試，放在既有的對應測試檔，例如 `conversations.test.ts`、`trust.test.ts`。<br>2. 若它符合原則 3，就把它的 state、ref 與 effect 移進一個 hook；不符合就留在 `App()`。<br>3. 跨 domain 的重設集中在協調處（原則 4）。<br>• 稽核當初的七個提案（`useBackendEvents`、`useApproval`、`useWorkspaceOperations`、`useDocumentWorkspace`、`useTurn`、`useConversationCatalog`、`useExtensions`）只是候選，不是驗收項目。<br>• S071 的其餘部分：`DocumentSnapshot`、`DocumentResult` 與 `DocumentContextDto` 統一成一個型別。<br>• 拆 hook 時若某個流程的行為無法從程式碼確定（例如 effect 之間的時序），就保持原本的 effect 順序不變，並在 GUI 清單中標為高風險項目。不要用猜測去改寫。 | • 每個 commit 都通過 `npm test`、`npm run build`。<br>• `evidence/C8-S6/domains.md` 對每個抽出的 hook 列出：參數、回傳值、擁有的 state、ref、effect。任何參數是另一個 hook 的 ref 或 setter 時，逐項寫明理由；預期沒有。<br>• 原則 5 的每項必要檢查，都有對應的純函式測試，列出測試名稱。<br>• `App()` 函式本體內剩下的每個 `useState`、`useRef`、`useEffect`，在 evidence 逐一標明是「協調」或「純 UI」（展開、焦點、捲動），並與 C1-S3 的計數比較。<br>• `App()` 函式本體內沒有 `api.` 以外的後端呼叫。 |
| C8-S7 | **階段收尾。** `npm test`、`npm run build`。<br>重新量測 `App.tsx` 行數，以及 `useState`、`useRef`、`useEffect`、`useCallback` 數，與 `evidence/C1-S3` 比較。<br>GUI 清單依 C8-S1 更新。 | 全部通過；量測存證。 |

## 失敗與續作

- 某個 domain 兩次聚焦修正後仍無法通過檢查：保留已完成的部分，以 checkpoint 保存，繼續下一個不相依的 domain。
- 某個 domain 的 hook 做不到「不互傳 ref 或 setter」時，不要硬拆：純函式照樣抽出並測試，state 留在 `App()`，在 evidence 記錄。這不算失敗。

## 交給後續階段

C9 拆元件時，元件只接收 hooks 與協調處提供的值與 callback。
