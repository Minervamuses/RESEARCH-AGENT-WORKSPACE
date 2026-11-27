# 驗收紀錄（2026-11-27）

- **HEAD**：`45186fe`（分支 `GUI`，未 push）
- **觸發情境**：受支援的正常使用（單一專案、單一文件依序切換），無並行情境。

## 1. 使用者實機 GUI 回報（2026-11-27，使用者轉述）

> 「我自己打開GUI跑過，切換左側、顯示outline都正常，我也有切換檔案，他也有正常跳過去」

對應 `evidence/D8-S3/final-report.md` 第 7 節清單：

| 清單項 | 狀態 | 依據 |
|---|---|---|
| 1 初始畫面與圖示列 | 使用者確認 | 「切換左側」正常 |
| 2 開檔自動切換、換檔換大綱 | 使用者確認 | 「顯示outline都正常」「切換檔案…正常跳過去」 |
| 3 圖示切換與收合 | 使用者確認切換與重複點同一圖示收合；A4（收合時開檔）、收合時主區佔滿未特別回報 | 第二輪 |
| 4 點標題跳轉、文末 Conclusion | 使用者確認點大綱跳到該章節；文末兩行 Conclusion 不跳回、無 `Add comment` 未特別回報 | 第二輪 |
| 5 目前章節追蹤、收合祖先、長標題截斷 | 未回報 | — |
| 6 即時更新、Undo／Agent／衝突、空大綱、未完成語法、同名章節 | 未回報 | — |
| 7 無副作用（Undo 歷史、不變未存檔） | 未回報 | — |
| 8 欄寬拖曳、鍵盤、雙擊重設、重開記憶 | 使用者確認滑鼠拖曳改寬度；鍵盤、雙擊重設、重開記憶未回報 | 第二輪 |
| 9 斷點與視窗夾限 | 未回報 | — |
| 10 LaTeX 高亮、引用補全清單（G7、G11） | 未回報 | — |
| 11 大綱鍵盤操作與中文輸入法 | 未回報 | — |
| 12 長文件與既有功能回歸 | 未回報 | — |

### 第二輪（2026-11-27，使用者轉述）

> 「這次我測試了拖曳(滑鼠拉動改變寬度)、點擊outline跳至該章節、點擊做左側icon在對話/outline間切換、重複點擊相同icon收合、ctrl+f，這些都沒問題」

Ctrl+F 屬計劃外的 `src/monacoFeatures.ts`（GOALS 範圍外項），本計劃只需不破壞它：已確認未破壞。

## 2. 驗收者重跑的自動檢查（本次觀察）

| 檢查 | 結果 |
|---|---|
| `npm test`（`app/desktop/`） | 297 passed, 0 failed |
| `npm run build` | 通過；`dist/assets/suggestController-B_e4S7NY.js` 存在（G11 打包條件） |
| 授權邊界 `git diff --stat bc9f651..HEAD -- app/agent app/desktop/protocol app/desktop/src-tauri app/desktop/package.json app/desktop/package-lock.json for_agents` | 0 bytes |
| `bc9f651..HEAD` 改動路徑 | 只有 `app/desktop/src/`、`app/desktop/tests/`、`README.md`、本計劃目錄 |
| 完整 pytest | 未重跑：後端與協定 0 改動，沿用 D8-S2 的 1,826 passed |

## 3. 驗收者讀碼與解析器探測（本次觀察）

讀過 `App.tsx`、`DocumentEditor.tsx`、`Sidebar.tsx`、`DocumentPane.tsx`、`useDocumentOutline.ts`、`lib/outline/{tracking,state,index}.ts`、`OutlineView.tsx`、`ColumnResizer.tsx`、`ActivityBar.tsx`、`styles.css`／`document.css`／`layout.css`／`outline.css` 的改動。

- 新增 hooks 都在 `App` 的唯一 `return` 之前，沒有條件式 hook。
- `useDocumentOutline` 只依 `[rootPath, path, sourceText]`；換檔立即解析並重設收合，同檔編輯 180 ms debounce；以 `fileKey` 防止換檔首幀顯示舊大綱。
- 編輯器仍只依 `[rootPath, path]` 重建；新增的游標／捲動 listener 與 rAF 在 dispose 時釋放，handle 在卸載時設回 `null`。
- 跳轉序列 `setPosition → revealLineNearTop(Immediate) → focus`，沒有 `setSelection`；外部修改（`incomingRef`）不回報游標行。
- `.app-shell` 與 `.writing-workspace` 的欄只在 `styles.css`／`document.css` 定義，`layout.css`／`outline.css` 未重定義。

以一次性 Node 腳本對 `parseOutline` 跑 29 個邊界輸入（ATX 結尾 `#`、行內格式、Setext、front matter、`~~~` 與較長關閉 fence、3／4 格縮排、多行 HTML 註解、引用／清單、7 個 `#`、未關閉 fence、BOM＋CRLF、lazy continuation；LaTeX 的 `%` 與 `\%`、verbatim／comment 環境、`\verb`／`\verb*`、`\newcommand`／`\def`、未關閉指令、跨行標題、`\sectionmark`、`\section {…}`、part／chapter 層級、`\}` 跳脫、`\section*[短]{完整}`），結果都符合 GOALS〈解析規格〉。

## 4. 發現（皆不阻塞）

1. **LaTeX 標題中的未知指令留下指令名**：`\section{The $\alpha$ case and \cite{x}}` 的大綱標題是 `The $\alpha$ case and \citex`——`\cite` 的大括號被拿掉，但指令名保留並和參數黏在一起。規格只要求常見格式指令（`\textbf`、`\emph`）取文字，所以不算違反規格，只是顯示不好看。位置：`app/desktop/src/lib/outline/latex.ts` 的 `cleanLatexTitle`。
2. **拖曳被系統中斷時仍會記住寬度**：`ColumnResizer` 在 `pointercancel`／`lostpointercapture` 時傳 `cancelled = true`，但 `App` 的 `endSidebarDrag`／`endWorkspaceDrag` 沒看這個參數，照樣寫進 `localStorage`。結果只是保留中斷前的寬度，不會造成錯誤版面。

## 5. 結論

- 自動化部分：通過（測試、打包、邊界都重現）。
- 實機部分（兩輪）：清單第 1、2、3 項（A4 除外）、第 4 項的基本跳轉、第 8 項的滑鼠拖曳由使用者確認通過；Ctrl+F 未被破壞。仍待確認：第 4 項文末 Conclusion、第 5–7 項、第 8 項的鍵盤／雙擊重設／重開記憶、第 9–12 項（含 G7 LaTeX 顏色、G11 引用補全清單、G8 大綱鍵盤）。
- A1–A10 尚未逐項回覆。
