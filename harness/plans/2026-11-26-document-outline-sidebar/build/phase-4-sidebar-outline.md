# D4 圖示列、側欄切換與大綱檢視

- **後置條件**：最左邊有圖示列，可在「對話管理」與「大綱」間切換、點目前圖示收合側欄；開檔自動切到大綱；大綱檢視依層級顯示目前文件的標題、可展開收合、有各種空狀態。此階段點標題還不跳轉（D5 接上），但必須不會出錯。
- **涵蓋**：G2、G3。
- **相依**：D2（`parseOutline`）、D3（`.app-shell` 格線與側欄邊界）。
- **輸入**：GOALS U1、U2、U4、U6、A4–A6、A9；PLANS「架構」第 4、5、7 點；PLANS「基線／側欄與 App」。

## 範圍

- 新增 `src/components/ActivityBar.tsx`、`src/components/OutlineView.tsx`、`src/hooks/useDocumentOutline.ts`、`src/styles/outline.css`；修改 `src/components/Sidebar.tsx`、`src/App.tsx`、`src/styles/layout.css`、`src/main.tsx`（`outline.css` 在 `layout.css` 之後）、`tests/styles.test.ts`；新增 SSR 測試（可放 `tests/outline_view.test.ts`，照 `tests/documents.test.ts` 的 Vite SSR 寫法）。
- 對話管理的內容、按鈕、停用條件與行為完全不變，只是搬進「對話管理檢視」。
- 圖示用內嵌 SVG 或文字符號，不新增圖示套件（INV-029）。

## 行為規格

- **圖示列**：兩個按鈕「Conversations」「Outline」（`aria-label` 與 `title`），以 `aria-pressed` 或 tab 語意標示目前檢視。點非目前的圖示：切換檢視，若側欄收合則展開。點目前的圖示：切換收合（U6）。收合時側欄與側欄邊界都不顯示，圖示列保留；收合狀態也要讓螢幕閱讀器知道（例如 `aria-expanded`）。刪除對話框開啟時圖示列 `inert`。
- **格線**：`.app-shell` 加入圖示列那一欄（在 `styles.css` 原處修改，子元素明確 `grid-column`）；收合時以 modifier class（例如 `.app-shell.sidebar-collapsed`）換成「圖示列｜主區」的欄定義，主區佔滿其餘寬度，不會被自動排進側欄的欄位。≤ 760 px 時圖示列是側欄上方的橫列（A8），收合同樣有效。
- **收合的已知後果**（U6）：收合期間品牌與 backend 控制隨側欄隱藏，這是預期行為。
- **側欄結構**（U4）：品牌與 backend 控制在兩種檢視都顯示；中間區塊依檢視顯示原本的 New conversation＋Project＋對話清單，或大綱。中間區塊自己捲動，品牌與 backend 控制固定。
- **自動切換**：`openDocument` 成功並 `updateDocument(snapshot)` 後設為大綱（再開另一份也一樣；A4：收合時只切換選中的圖示，不展開）。第 804 行重設文件為 `null` 時設回對話管理（A5）。存檔、Agent 修改、Undo、衝突處理不改變檢視。啟動時是展開的對話管理（A6）。
- **大綱資料**：`useDocumentOutline(documentValue)` 依 `[rootPath, path, sourceText]`；換檔立即解析並清空收合狀態，同檔約 180 ms debounce（A9）；`null` 時立即清空；卸載與換檔時取消計時器。收合狀態以節點 ID 記錄，重新解析後保留仍存在的 ID。
- **大綱檢視**：上方顯示檔名；樹狀清單依深度縮排（縮排上限約 `min(depth, 5) * 0.7rem`）；有子節點者顯示展開／收合鈕；標題以純文字呈現，過長以省略號截斷並以 `title` 顯示全文，`min-width: 0` 防止撐開；沒有標題顯示 `No headings found`；沒開文件顯示提示（例如 `Open a document to see its outline`）；換檔後絕不殘留前一份文件的節點。
- **重繪範圍**：檢視切換、收合是少見事件，可以放 `App` 狀態；但不要讓大綱解析結果在游標移動時重新計算（依賴只用上面三個欄位）。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| D4-S1 | `useDocumentOutline` 的純邏輯部分（決定何時立即解析、何時 debounce、何時清空、收合 ID 保留）抽成可測函式並測試；hook 本身是薄包裝。 | 測試：換檔立即解析並清空收合；同檔變動走 debounce；`null` 立即清空；游標移動（只有範圍欄位改變的新物件）不觸發解析；重新解析後保留仍存在的收合 ID、丟棄已不存在的 |
| D4-S2 | `OutlineView`、`outline.css`：渲染樹、縮排、展開收合、空狀態、長標題；點標題先呼叫一個 `onSelect(node)` callback（D5 接跳轉）。 | SSR 測試：巢狀樹的層級與 `aria-level`／縮排、收合節點不渲染子節點、`No headings found`、沒開文件的提示、含 `<script>` 與 `&` 的標題被跳脫成文字 |
| D4-S3 | `ActivityBar`、`Sidebar` 拆成固定區＋中間檢視、`App` 的檢視與收合狀態、自動切換、收合時隱藏側欄邊界、`layout.css` 的圖示列欄位與 ≤ 760 px 橫列（A8）、`main.tsx` import。 | SSR 測試：兩種檢視都有品牌與 backend 控制；對話管理檢視的按鈕與文字與修改前相同；收合時只剩圖示列；圖示 `aria` 狀態正確。檢視切換的狀態轉換（開檔→大綱、重設→對話管理、點目前圖示→收合、點另一圖示→展開並切換、收合時開檔→仍收合但切到大綱）抽成純函式測試。`styles.test.ts` 斷言 import 順序、收合 modifier 的欄定義存在、`.app-shell` 每個直接子元素的 class 都有 `grid-column`。`npm run build` 通過 |

## 交付給後續階段

`OutlineView` 的 `onSelect` 與「目前章節 ID」入口（D5 接上）；`useDocumentOutline` 的結果與戳記。
