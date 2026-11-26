# D6 P1：LaTeX 語法高亮

- **後置條件**：`.tex` 以 `latex` 語言開啟並有語法高亮；引用補全行為與修改前相同；Markdown 不受影響。
- **涵蓋**：G7。
- **相依**：D5（只為了避免同時修改 `DocumentEditor.tsx`；邏輯上只需要 D1）。
- **輸入**：GOALS G7；PLANS「架構」第 8 點與「基線／編輯器」中補全與 token 的說明；S2 brief touch point 2。

## 範圍

- 新增 `src/lib/latexLanguage.ts` 與測試（可併入 `tests/outline.test.ts` 或另開 `tests/latex_language.test.ts`）；修改 `src/DocumentEditor.tsx` 建立 model 前的語言選擇與註冊。
- 不改 `src/citations.ts` 的 `completionPrefix`；若發現必須改，先確認 `tests/citations.test.ts` 的語意不變並在 build-log 說明原因。
- 不新增依賴；Monarch 定義寫在本地。

## 行為規格

- 註冊：`registerLatexLanguage(monaco)` 以模組層級旗標保證整個 app 只註冊一次（`languages.register` 與 `setMonarchTokensProvider`、`setLanguageConfiguration`）；開第二份 `.tex` 不重複註冊。
- 語言選擇：`.md`／`.markdown` → `markdown`；`.tex` → `latex`；其他維持 `plaintext`。
- Token：指令（`\foo`）、章節指令（`\section` 等）、環境（`\begin{…}`／`\end{…}` 與名稱）、註解（`%` 到行尾，`\%` 不是）、數學（`$…$`、`$$…$$`、`\(…\)`、`\[…\]`、常見數學環境）、引用指令（`\cite` 系列，含 `\citep`、`\citet`、`\textcite`、`\parencite`、`\autocite`）、交叉引用（`\ref`、`\eqref`、`\label`、`\autoref`）、大括號與方括號。
- **引用鍵不得是 `string` 或 `comment` token**：引用指令大括號內的鍵標成 `identifier`（或其他不含這兩個字的名稱）。
- LanguageConfiguration：`%` 為行註解、括號配對與自動關閉（`{}`、`[]`、`()`；`$` 可選）。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| D6-S1 | `latexLanguage.ts`：Monarch 定義、LanguageConfiguration、冪等註冊函式。 | 測試（不需真的 Monaco）：以假的 `monaco.languages` 物件呼叫兩次，`register` 等只被呼叫一次；遍歷 Monarch 規則，確認處理引用指令參數的狀態中沒有任何 token 名稱含 `string` 或 `comment`；規則中的正規表示式都能編譯 |
| D6-S2 | `DocumentEditor.tsx` 在 `createModel` 前註冊並選語言；補全仍以 `model.getLanguageId()` 註冊。 | `npm test`（含 `tests/citations.test.ts`）與 `npm run build` 通過；bundle 大小與 D1 比較並記錄。實際顏色與 `\cite{` 補全（含 Esc 後繼續打字）列入 D8 手動清單 |

## 交付給後續階段

`.tex` 的高亮與補全相容的證據。
