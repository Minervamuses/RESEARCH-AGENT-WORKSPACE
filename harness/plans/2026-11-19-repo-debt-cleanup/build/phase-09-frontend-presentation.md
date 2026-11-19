# C9 — 前端呈現層

- **完成後的狀態**：
  - 主要畫面區塊各是一個元件，`App()` 只做組裝。
  - 所有 dialog 共用同一個 Modal，所有 popup menu 共用同一個 Menu。
  - 顏色經由 CSS 變數。
  - 樣式依元件分檔，media query 已整併。
  - grep 原始碼與釘住 class name 的測試已改為行為斷言。
- **涵蓋**：G6
- **相依**：C8
- **輸入**：[稽核原文](../context/repo-debt-audit-2026-11-19.md)的 S081、S086–S088、S096、S097。

## 限制

- **INV-021 的數值不變**：根字級 `clamp(1rem, calc(0.75rem + 0.35vw), 1.3125rem)`、`CitationPanel` 文字 `>= 0.9rem`、Monaco 的預設值與縮放範圍。`styles.test.ts` 不修改也要通過；它屬於 S084，不納入本計劃。
- **`styles.test.ts` 讀檔的位置不能動**：它讀 `src/styles.css`，並取檔案中**第一個** `:root { … }` 規則裡的 `font-size: clamp(…)`。所以：
  - `src/styles.css` 必須保留；
  - 它的第一個 `:root` 規則必須繼續包含這個 `font-size` 宣告；
  - 該規則內不能出現 `{` 或 `}`。
  - `tokens.css` 的變數可以放在另一個檔案的 `:root`，或放在同一規則內。
- **`index.html` 的 `lang` 與 `color-scheme` 不動**（S094，不納入）。
- **不重新設計畫面。** 只有一個例外（GOALS P10）：近似重複的顏色合併成同一個變數，例如 `#66716d`、`#68716e`、`#626a68`、`#626b67`。這會造成肉眼幾乎看不出的差異。每組合併都要記入 evidence，並列進 GUI 清單。
- 不新增 npm 套件。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| C9-S1 | **S081：共用 Modal 與 Menu。**<br>• focus trap 目前有 4 份：`App.tsx` 約 185–193、2969–2978、3003–3010 行，以及 `trust.tsx` 約 286–303 行。收成一個 Modal。<br>• 四個選單（`DocumentHeader`、對話選單、`ThinkingControl`、`ExportMenu`）各自處理 Esc 與 blur，收成一個 Menu。<br>• focus 與 Esc 的判斷邏輯若是純函式，加測試。 | • `npm test`、`npm run build` 通過。<br>• 加入 GUI 清單：每個 dialog 的 Tab 循環、Esc 關閉、焦點還原；每個選單的 Esc、點外部關閉、鍵盤操作。 |
| C9-S2 | **S097 的元件（可拆成 C9-S2a、C9-S2b…）。**<br>• 抽出 `Composer`、`Transcript`、`Sidebar`、`DocumentPane`、`ProjectChooser`、`RuntimeDetails`。<br>• `Transcript` 把三套 turn 渲染（`RestoredTurn`、live 分支、pending 分支）收成一個元件，以 variant 區分。<br>• `trust.tsx` 依職責拆開：ApprovalDialog、composer 控制項、擴充流程。<br>• annotation UI 從 `DocumentEditor` 移出，因為 chat 也在用。<br>• `App()` 只剩 hooks 呼叫與組裝用的 JSX；超過約 1,000 字元的單行 JSX 拆開。 | • 每個 commit 都通過 `npm test`、`npm run build`。<br>• 最後量測 `App.tsx` 行數並存證。<br>• `App.tsx` 中沒有 `.message`、`.tool-*` 的渲染分支。 |
| C9-S3 | **S096：CSS 地基。**<br>• 建立 `src/styles/tokens.css`（提案路徑）。至少包含顏色，間距與圓角視實際重複程度決定，約 15 個變數。<br>• 把 hex 與 rgba 顏色換成變數。<br>• 樣式依元件分檔，由各元件 import；全域樣式只留 reset、tokens 與版面骨架。<br>• 分散在 4 處的 media query 依斷點整併。<br>• 被借用的 class 名稱（`approval-dialog`、`extension-error`）改成依角色命名。 | • `npm test`（含不修改的 `styles.test.ts`）、`npm run build` 通過。<br>• `grep -rnoE "#[0-9a-fA-F]{3,8}\b|rgba?\(" src --include=*.css` 只出現在 `tokens.css`；例外逐一註明理由。<br>• 近似色合併表存證（GOALS P10）。 |
| C9-S4 | **S086–S088：測試改為行為斷言。**<br>• `editorZoom.test.ts` 約 64–71 行 grep `DocumentEditor.tsx` 的按鍵綁定；`trust.test.ts` 約 400–409 行對 `App.tsx` 原始碼做 regex。兩者都改測抽出的純函式或常數。<br>• `citation_preview.test.ts` 與 `conversations.test.ts` 中對 class name 的斷言，改斷言 role、文字或 aria。<br>• `conversations.test.ts` 約 308–352、551 行與 `protocol.test.ts` 約 217 行的三個大型合成資料測試，合併成一個。<br>• 每個被改或被刪的測試都寫退役紀錄。 | • `npm test` 通過。<br>• grep 讀取 `src/*.tsx` 原始碼的測試為 0：`readFile` 加上 `src/` 路徑的組合。若 `styles.test.ts` 讀 CSS，它屬於 S084，保留並註明。 |
| C9-S5 | **階段收尾。** `npm test`、`npm run build`。<br>量測 `styles.css` 與 tokens 檔、各元件檔的行數，以及 hex 色數，存證。 | 全部通過。 |

## 交給後續階段

之後重新設計 UI 時：

- 改顏色只改 `tokens.css`；
- 改一個區塊只改它的元件與樣式檔；
- 測試不會因 class name 或版面調整而失敗。
