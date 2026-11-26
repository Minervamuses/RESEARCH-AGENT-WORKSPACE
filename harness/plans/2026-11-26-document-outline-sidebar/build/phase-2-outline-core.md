# D2 大綱解析核心

- **後置條件**：`app/desktop/src/lib/outline/` 的純邏輯模組完成，Markdown 與 LaTeX 都輸出同一種大綱樹；GOALS〈解析規格〉每一項都有單元測試且通過；解析效能已量測。此階段不接 UI。
- **涵蓋**：G1。
- **相依**：D1。
- **輸入**：GOALS〈解析規格〉；PLANS「架構」第 1、4 點；`src/lib/documentSource.ts`；可參考 `app/skills/citation/citekeys.py` 對 LaTeX 註解與 verbatim 的處理（本階段要求比它嚴格，另含 `\newcommand` 類定義）。

## 範圍

- 新增 `src/lib/outline/types.ts`、`markdown.ts`、`latex.ts`、`tree.ts`、`index.ts` 與 `tests/outline.test.ts`（檔名可調整）。`tracking.ts` 在 D5 新增。
- 不改任何既有元件。不新增 npm 依賴（A1）。
- 掃描器要線性時間：不用可能回溯爆炸的正規表示式處理整份文件；不完整的語法跳過尾端即可。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| D2-S1 | **型別與樹**：`types.ts` 定義節點與結果（樹、先序扁平清單、`sourceText` 戳記、格式）；`tree.ts` 由「標題清單」建樹：相對層級堆疊、計算 `sectionEndOffsetUtf16`、視覺深度、穩定 ID（GOALS〈解析規格〉的 ID 規則）。 | 測試：不連續層級（H1→H3）、開頭沒有一級標題、同名兄弟 ID 不同、在前面插入／刪除無關標題後其他 ID 不變、改名只改變該節點與其子孫的 ID、`sectionEndOffsetUtf16` 停在下一個同級或更高層標題前或文件結尾 |
| D2-S2 | **Markdown 掃描器** `markdown.ts`：依〈解析規格〉的 Markdown 段落。 | 測試：H1–H6、結尾 `#`、Setext 一二級、行內格式去除、`#標題` 不算、fenced（``` 與 `~~~`，含未關閉）、indented code、HTML 註解（含未關閉）、YAML front matter、引用區塊與清單內的 `#`、中英混合與 emoji、空文件 |
| D2-S3 | **LaTeX 掃描器** `latex.ts`：依〈解析規格〉的 LaTeX 段落；`index.ts` 的 `parseOutline(path, sourceText)` 依副檔名（`.md`、`.markdown`、`.tex`，不分大小寫）分派，其他副檔名回傳空結果。 | 測試：七種指令與相對層級、`*`、`[短]{完整}` 顯示完整、跨行與巢狀大括號、`\textbf{}`／`\emph{}` 取文字、`%` 註解與 `\%`、五種 verbatim 類環境、`\verb|…|` 與 `\verb*`、`\newcommand{\x}{\section{Y}}` 不算、`\section{Intro`（未完成）不影響前面章節 |
| D2-S4 | **offset 一致性與效能**：兩種格式各做含 BOM、CRLF、emoji、CJK 的 fixture，確認每個節點 `documentPositionAt(sourceText, startOffsetUtf16)` 的行號等於 `lineNumber`、欄位是 1，且原文在該 offset 起的字串就是標題起頭。效能：在暫存目錄寫一次性 Node 腳本，產生 100 KB 與 1 MiB 的 Markdown 與 LaTeX 文件（約 1,000 個標題），各解析 20 次取中位數。 | offset 測試通過；效能腳本、輸出與機器資訊存 `evidence/D2-S4/`（腳本本身也放進去，不放 `/tmp`）。對照 A10：超過 100 ms 時先改進再繼續，仍超過則記錄並列入最終彙報 |

每個步驟完成後 `npm test` 通過再 commit；D2 結束時 `npm run build` 通過。

## 交付給後續階段

`parseOutline(path, sourceText)` 與節點型別；ID 規則保證；效能數字。
