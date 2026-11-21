# C9 — 前端呈現層

- **完成後的狀態**：
  - 主要畫面區塊有清楚的元件邊界；`App()` 主要負責 hooks、跨 domain 協調與 JSX 組裝；transcript 三種入口可按語意保留（U22）。
  - dialog／menu 只共用相容的互動原語，不強制不同語意使用同一元件（U22）。
  - CSS 切成依原順序排列的區段檔，打包結果的規則順序不變；被借用的 class 改成依角色命名。顏色值不變。
  - grep 原始碼與釘住 class name 的測試已改為行為斷言。
- **涵蓋**：G6
- **相依**：C8
- **輸入**：
  - [GOALS.md](../GOALS.md) 的 U18、R4、P12。
  - [稽核原文](../context/repo-debt-audit-2026-11-19.md)的 S081、S086–S088、S096、S097。

## 限制

- **INV-021 的數值不變**：根字級 `clamp(1rem, calc(0.75rem + 0.35vw), 1.3125rem)`、`CitationPanel` 文字 `>= 0.9rem`、Monaco 的預設值與縮放範圍。`styles.test.ts` 不修改也要通過；它屬於 S084，不納入本計劃。
- **`styles.test.ts` 讀檔的位置不能動**：它讀 `src/styles.css`，並取檔案中**第一個** `:root { … }` 規則裡的 `font-size: clamp(…)`。所以：
  - `src/styles.css` 必須保留；
  - 它的第一個 `:root` 規則必須繼續包含這個 `font-size` 宣告；
  - 該規則內不能出現 `{` 或 `}`。
- **不重新設計畫面，也不改顏色**（R4）：不建立色彩 token，不合併近似色，不整併 media query（P12）。這些留給 GUI 改版。
- **層疊順序不變**：CSS 分檔後，打包後的規則順序必須與原本的 `styles.css` 相同。所以：
  - 只能切成原檔中**連續的區段**，不可把分散各處的規則搬到一起；
  - `src/styles.css` 保留第一個區段（含第一個 `:root` 規則）；
  - 其餘區段由目前 import `styles.css` 的入口，緊接在它之後依原順序 import；元件不各自 import 樣式。CSS 的 `@import` 必須放在檔案開頭，會把區段排到 `:root` 之前，所以不用它。
  - 因此一個元件的規則可能仍分散在幾個區段，這是預期的。完整的依元件重組留給 GUI 改版（P12）。
- **`index.html` 的 `lang` 與 `color-scheme` 不動**（S094，不納入）。
- 不新增 npm 套件。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| C9-S1 | **S081／U22：共用相容的 Modal／Menu 原語。**<br>• 盤點 4 處 focus trap（`App.tsx` 約 185–193、2969–2978、3003–3010，`trust.tsx` 約 286–303）的 Tab、Esc、焦點還原、關閉條件；相同部分抽成 Modal 原語，差異保留在呼叫端或薄包裝。<br>• 四個選單（`DocumentHeader`、對話選單、`ThinkingControl`、`ExportMenu`）同樣盤點 Esc、blur、點外部與鍵盤互動，僅共用真正相同的部分。focus、Esc 可測的判斷抽成純函式。<br>• 被借用的 `approval-dialog` class 改為按角色命名；CSS 只改選擇器，不改宣告和值。 | • `npm test`、`npm run build` 通過。<br>• evidence 列出共用原語與保留的語意差異，不以最終 Modal／Menu 元件數為門檻。<br>• GUI 清單逐一涵蓋各 dialog 的 Tab／Esc／焦點還原，以及選單的 Esc／點外部／鍵盤操作。 |
| C9-S2 | **S097 的元件（可拆成 C9-S2a、C9-S2b…）。**<br>• 抽出 `Composer`、`Transcript`、`Sidebar`、`DocumentPane`、`ProjectChooser`、`RuntimeDetails`。<br>• `Transcript` 先區分三種渲染（`RestoredTurn`、live、pending）的資料來源、生命週期與互動；共用訊息卡片、工具結果等相同的呈現元件。只有資料與語意相容才合併成單一 `variant` 入口；若造成大量分支或額外耦合，就保留分開入口（U22）。<br>• `trust.tsx` 依職責拆開：ApprovalDialog、composer 控制項、擴充流程。<br>• annotation UI 從 `DocumentEditor` 移出，因為 chat 也在用。<br>• 超過約 1,000 字元的單行 JSX 拆開。<br>• 元件只接收 hooks 與協調處提供的值與 callback（U18）；不在元件內直接呼叫 `api.`。<br>• 拆出的元件中，原本就有靜態渲染測試涵蓋的部分，測試跟著改指向新元件。無論是否合併入口，三種 transcript 情境都要有 restored、live、pending 的靜態渲染測試；沿用現有的 Vite SSR 加 `renderToStaticMarkup` 寫法，不新增相依。 | • 每個 commit 都通過 `npm test`、`npm run build`。<br>• 最後量測 `App.tsx` 行數並存證。<br>• `App.tsx` 不再直接實作 `.message`、`.tool-*` 的呈現細節，由可重用的元件負責；三種入口可保留。<br>• evidence 說明共用／分開的部分與理由。<br>• `grep -rn "api\." src/components`（或實際的元件目錄）為 0，例外逐一註明。 |
| C9-S3 | **S096 的分檔與 class 改名（P12）。**<br>• 先存一份基準：以腳本把 `vite build` 產生的 CSS 正規化（每條規則一行，去除空白差異），存成 `evidence/C9-S3/css-before.txt`。<br>• 依上方「層疊順序不變」，把 `styles.css` 切成連續區段，放到 `src/styles/` 下，以區段的主要畫面區塊命名；第一個區段留在 `src/styles.css`。<br>• 被借用的 `extension-error`（用於非擴充的錯誤）改成依角色的名稱；只改選擇器名稱與對應的 `className`。<br>• 不改任何宣告的值。 | • `npm test`（含不修改的 `styles.test.ts`）、`npm run build` 通過。<br>• 以同一腳本產生 `css-after.txt`，與 `css-before.txt` 比較：除了改名的選擇器，規則內容與順序完全相同。差異逐行寫入 evidence。<br>• `grep -rnoE "#[0-9a-fA-F]{3,8}\b" src --include=*.css` 的不同色值集合與改動前相同。 |
| C9-S4 | **S086–S088：測試改為行為斷言。**<br>• 依 C8 的規則，原始碼比對測試應已在搬移程式的那一步改寫。本步處理剩下的部分，例如 `editorZoom.test.ts` 約 64–71 行 grep `DocumentEditor.tsx` 的按鍵綁定，改測抽出的純函式或常數。C9-S2 若搬動了 `DocumentEditor.tsx` 中被比對的程式，就在 C9-S2 當步改寫。<br>• `citation_preview.test.ts` 與 `conversations.test.ts` 中對 class name 的斷言，改斷言 role、文字或 aria。<br>• `conversations.test.ts` 約 308–352、551 行與 `protocol.test.ts` 約 217 行的三個大型合成資料測試，合併成一個。<br>• 每個被改或被刪的測試都寫退役紀錄。 | • `npm test` 通過。<br>• grep 讀取 `src/*.tsx` 原始碼的測試為 0：`readFile` 加上 `src/` 路徑的組合。`styles.test.ts` 讀 CSS，屬於 S084，保留並註明。 |
| C9-S5 | **階段收尾。** `npm test`、`npm run build`。<br>量測 `styles.css` 與各樣式檔、各元件檔的行數，存證；另複核共用／保留的互動語意與三種 Transcript 渲染測試（U22）。 | 全部通過。 |

## 交給後續階段

之後重新設計 UI 時：

- 改一個區塊只改它的元件與樣式檔；
- 色盤、色彩 token 與 media query 的整併，在改版時一起決定（R4、P12）；
- 測試不會因 class name 或版面調整而失敗。
