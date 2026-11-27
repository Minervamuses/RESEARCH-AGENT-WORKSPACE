# 執行紀錄

本檔是本計劃唯一的狀態來源。撰寫時尚未執行任何實作。

## 目前狀態

| 階段 | 狀態 | 證據 | 阻塞 | 下一步 |
|---|---|---|---|---|
| D1 | Complete | D1-S1 唯讀核對、D1-S2 修改前基線通過（npm test 256/256、build 通過） | — | D1A-S1（或 D2、D3） |
| D1A | Complete | D1A-S1 補全清單打包與測試通過（258/258）、D1A-S2 程式審查完成（實機行為留待 D8 手動驗收） | — | — |
| D2 | Complete | D2-S1–S4 完成（npm test 268/268、build 通過；1 MiB 中位數 MD 5.19 ms / LaTeX 3.56 ms，`evidence/D2-S4/`） | — | — |
| D3 | Complete | D3-S1–S3 完成（npm test 276/276、build 通過；實機拖曳列入 D8 手動清單） | — | — |
| D4 | Complete | D4-S1–S3 完成（npm test 281/281、build 通過；ActivityBar、Sidebar 切換／收合、自動切換、OutlineView SSR 與 CSS 斷言皆過） | — | — |
| D5 | Complete | D5-S1–S3 完成（npm test 290/290、build 通過；Monaco 實機跳轉／Undo／Agent 修改／衝突列入 D8 手動清單） | — | — |
| D6 | Complete | D6-S1、D6-S2 完成（npm test 294/294、build 通過、suggestController 仍存在；實機語法上色與四種引用補全列入 D8 手動清單） | — | — |
| D7 | In progress | D7-S1 大綱鍵盤導覽純邏輯完成（npm test 296/296） | — | D7-S2 OutlineView roving tabindex、ARIA 與鍵盤接線 |
| D8 | Not started | — | — | 等 D1A、D2–D7 |

## 撰寫紀錄

### DA0 撰寫計劃（2026-11-26）

- 依 GOALS 的來源 S1–S4 撰寫：使用者在 Claude Code 對話中貼上的需求書（未存進 repo，U9）、`for_agents/briefs/2026-11-26-document-outline.md`（`78cd9ac`）、使用者 2026-11-26 的決策 U1–U9。
- 撰寫時只讀碼（HEAD `78cd9ac`），沒有執行任何測試、建置或 GUI；PLANS「基線」的行號與行為由 D1 重新核對。
- 撰寫時的檢查（只檢查計劃本身，與產品行為無關）：
  - 長程計劃 skill 附的結構 lint `validate_plan.py --json`：修正前後皆 `ok: true`，0 錯誤、0 警告，檢查 13 個檔案。
  - 一次獨立的新手執行者走查（另一個 agent，只拿計劃、使用者原話與選項回答、S2 brief 與現行程式）：U1–U9 都有對應，沒有遺漏或多加的需求；基線行號與事實相符。找到 8 項會誤導執行的缺口，已全部修正：跳轉保護需要 `scrollTop` 且捲動回報經 rAF 延後、`revealLineNearTop` 必須指定 `Immediate`；tracker 在重新解析後重算與換檔重設；側欄收合時的格線排位；格線規則只在原檔修改、D3 只有一種格線做法；寬度依目前視窗夾限；INV-029 誤標；編輯器 handle 尚未註冊時的點擊；收合時 backend 控制一起隱藏的後果。另依建議把跳轉序列改成可注入假編輯器的純函式測試。

### DA1 計劃審核修訂（2026-11-26）

- 依使用者確認更新引用補全載入與四種指令驗收、窄視窗收合、同名章節過期點擊與文末跳轉；啟動提示及交付檢查沿用 PLANS 的回歸修復例外。D1–D8 仍待執行。

### DA2 補全清單缺陷拆成獨立階段（2026-11-26）

- 授權來源：使用者對 Claude 審核 Codex 修訂的三點回覆「同意」（GOALS U10），並在 GUI 實測確認文件編輯器打 `@`、`/` 沒有清單、Ctrl+F 沒反應。
- 撰寫時讀碼確認：`editor.api` 與 markdown 語言定義的 import 圖（約 704 個檔案）不含任何 `editor/contrib/` 功能；`dist/assets/` 沒有 `editor.contrib.suggestController`、`contextmenu`、`findController`；`suggestController.js` 沒有 `.d.ts`；已載入的 `editorWorkerService.js` 含字詞建議提供者；Markdown 的 `[...]` 是 `string.link` token 且 `[` 會自動補 `]`。
- 修訂：新增 D1A（G11）載入補全清單、本地型別宣告、`wordBasedSuggestions: "off"`、`quickSuggestions.strings: "on"`；D6 改為依賴 D1A、不再處理清單控制器；G7 與 PLANS 基線改寫為既有缺陷；其他缺漏的 Monaco 功能列入範圍外並由最終彙報提出。同時提交 DA1（Codex 的五項修訂）尚未提交的改動。
- 檢查（只檢查計劃本身）：結構 lint `validate_plan.py --json` 為 `ok: true`，0 錯誤、0 警告，檢查 14 個檔案；`git diff --check` 通過。D1、D1A、D2–D8 仍未開始。

### DA3 其他 Monaco 功能改由計劃外工作處理（2026-11-27）

- 使用者 2026-11-27 決定補回文件編輯器的右鍵選單（Monaco 選單加剪貼簿）、搜尋／取代、編輯輔助（括號配對、註解切換、行操作、多游標、字詞移動等）、懸停、摺疊與相同字詞標示，以 Monaco 附 `.d.ts` 的 `features/<名稱>/register` 逐項匯入。已在本計劃之外完成：`src/monacoFeatures.ts`、`tests/monacoFeatures.test.ts`。
- 修訂：GOALS「範圍外」、PLANS「基線／編輯器」、D1A 背景（`suggestController` 不放進該檔；`features/suggest/register` 不含清單控制器；bundle 基準改為含該檔的建置）、D8-S3 不再列出缺漏功能。D1、D1A、D2–D8 仍未開始。

## 執行事件

### D1-S1 唯讀核對（2026-11-27，本次觀察）

- **Git 分支與 HEAD**：分支 `GUI`，HEAD `bc9f651`。與撰寫基線 `78cd9ac` 之間的 4 筆 commit：
  - `208acc6` `docs(plan): plan the document outline sidebar and resizable columns [DA0]`
  - `a4ca515` `docs(plan): fix the editor completion list as an early phase [DA1, DA2]`
  - `5be1978` `feat(desktop-ui): load Monaco find, context menu and editing contributions`（新增 `src/monacoFeatures.ts`、`tests/monacoFeatures.test.ts`，在 `DocumentEditor.tsx:62` 加入 `import("./monacoFeatures.ts")`，行號整體後移 1 行，對後續階段設計無衝突，已在 DA3 納入說明）
  - `bc9f651` `docs(plan): hand the other Monaco features to separate work [DA3]`
- **計劃檔案提交狀態**：`git ls-files harness/plans/2026-11-26-document-outline-sidebar/` 列出全部 14 個計劃檔，`git status --short -- harness/plans/2026-11-26-document-outline-sidebar/` 為空，不需補交。
- **無關的既有工作樹狀態（保留不動）**：`M app/skills/grill/SKILL.md`、`?? .agents/`、`?? .claude/`、`?? .opencode/`、`?? NOTES-grill-skill-and-document-context.md`、`?? note/20261106/`。
- **基線程式位置核對（`grep`／讀碼，本次觀察）**：
  - `app/desktop/src/styles.css:111`：`.app-shell` 的 `grid-template-columns: minmax(10.15rem, 11.9rem) minmax(0, 1fr);`
  - `app/desktop/src/styles/document.css:2,27`：`.writing-workspace` 的 `grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr)` 與 `<= 1050px` 單欄規則
  - `app/desktop/src/main.tsx:5-11`：CSS import 順序 `styles.css` → `workspace.css` → `sidebar.css` → `conversation.css` → `dialogs.css` → `responsive.css` → `document.css`
  - `app/desktop/src/App.tsx`：`updateDocument` 定義於 L217，呼叫於 L354、L423（`openDocument` L408 內）、L465、L804（重設為 `null`），並於 L1790 傳給 `DocumentPane`
  - `app/desktop/src/DocumentEditor.tsx`：`.tex` 用 `plaintext`（L69）、`scrollBeyondLastLine: false`（L79）、`publishSelection`（L161，掛載於 L187／L189）、補全 `triggerCharacters: ["@", "{", ","]`（L192）、第二個 effect（L275）
  - `app/desktop/src/lib/documentSource.ts:25-27`：`documentPositionAt` 以 `source.startsWith("\uFEFF") ? 1 : 0` 處理 BOM
  - `app/desktop/src/editorZoom.ts:8,17-44`：`research-agent.editorFontSize`、`try/catch` 包裝與可注入 storage
  - `app/desktop/src/components/Sidebar.tsx`（92 行）、`app/desktop/src/styles/responsive.css`（110 行）均與基線一致
- **工具環境（Conda `app`）**：`/home/minervamuses/miniconda3/envs/app/bin` 下 `node v24.18.0`、`npm 11.16.0`、`cargo`、`python` 均可用。
- **結論**：所有基線條件成立，無需修訂後續階段檔。

### D1-S2 修改前基線（2026-11-27，本次觀察）

- **`npm test`**（`app/desktop/`）：`256 passed, 0 failed`（node test runner 6,469 ms，wall 5.93 s），無既有失敗。
- **`npm run build`**（`app/desktop/`）：`tsc --noEmit && tsc --noEmit -p tsconfig.test.json && vite build` 通過（wall 4.49 s，vite build 580 ms，940 modules）。
- **`dist/assets/` 基線大小**（含 `5be1978` 的 `monacoFeatures` 拆包）：
  - `index-DXhwvsi3.js`: `393.42 kB`（393,428 B，gzip 112.00 kB）
  - `editor.api-BKMlSWig.js`: `547.91 kB`（547,913 B，gzip 142.70 kB）
  - `monacoFeatures-DMQ4CnLk.js`: `581.49 kB`（581,499 B，gzip 142.69 kB）
  - `editorState-CjudPH6-.js`: `2,175.96 kB`（2,175,962 B，gzip 560.96 kB）
  - Monaco JS 合計：3,305,374 B；CSS：`index` 25.33 kB、`editor` 51.94 kB、`monacoFeatures` 48.29 kB、`editorState` 47.14 kB；字型：`codicon` 153.22 kB。
  - `grep -c editor.contrib.suggestController dist/assets/*.js`：全為 0（確認 D1A 既有缺陷基線）。
- 未跑完整 pytest（排於 D8）。D1 完成。

### D1A-S1 載入補全清單控制器與補全選項（2026-11-27，本次觀察）

- **變更檔案**：
  - 新增 `app/desktop/src/monaco-contrib.d.ts`：宣告 `monaco-editor/editor/contrib/suggest/browser/suggestController`（`tsconfig.json` 與 `tsconfig.test.json` 均涵蓋 `src`）。
  - 修改 `app/desktop/src/editorZoom.ts`：新增 `editorSuggestionOptions()`，回傳 `{ wordBasedSuggestions: "off", quickSuggestions: { other: "on", comments: "off", strings: "on" } }`。
  - 修改 `app/desktop/src/DocumentEditor.tsx`：在既有的 `Promise.all` 中（`import("./monacoFeatures.ts")` 之前）載入 `monaco-editor/editor/contrib/suggest/browser/suggestController`，並在 `monaco.editor.create` 套用 `...editorSuggestionOptions()`。未更動 `src/monacoFeatures.ts` 與 `src/citations.ts`。
  - 修改 `app/desktop/tests/editorZoom.test.ts`：新增 2 個測試，驗證補全選項設定與 `DocumentEditor.tsx` 在 `create` 前等待 `suggestController`。
- **必要檢查結果**：
  - `npm test`：`258 passed, 0 failed`（含 `tests/citations.test.ts`、`tests/monacoFeatures.test.ts` 與新增 2 項）。
  - `npm run build`：通過，無 TS7016（964 modules，vite build 566 ms）。
  - `grep -c editor.contrib.suggestController dist/assets/*.js`：`dist/assets/suggestController-Dlku74Rc.js:1`（其他 JS 皆為 0）。
  - Bundle 變化（與 D1-S2 含 `monacoFeatures` 基線比較）：`index-Dxv-VZyw.js` 393.84 kB（+0.42 kB）；延遲載入的 Monaco JS 合計 3,425,229 B（相對基線 3,305,374 B 增加 +119.86 kB，含 `suggestController-Dlku74Rc.js` 114.89 kB）；延遲載入的 Monaco CSS 合計 159.58 kB（增加 +12.21 kB，含 `suggestController-DJ6Lv6Yp.css` 12.22 kB）。

### D1A-S2 補全清單程式審查（2026-11-27，本次觀察）

- 讀碼核對 `app/desktop/src/DocumentEditor.tsx` L49–90、L249–273：
  - `import("monaco-editor/editor/contrib/suggest/browser/suggestController")`（L62）在既有 `Promise.all`（L58–64）內等待完成，確保早於 `monaco.editor.create`（L73）。
  - `if (disposed || !surfaceRef.current || !snapshotRef.current) return;`（L65）維持於 `.then(...)` 第一行，換檔或卸載時不會建立孤兒實例。
  - 未新增任何 listener 或可釋放資源；既有的 `completion?.dispose()`（L259）與 `instance.dispose()`（L262）已涵蓋釋放。
- 未驗收實機 GUI 行為；`.md` 輸入 `[@`、一般文字不跳字詞建議、Esc 後續打重現、Ctrl+Space 手動叫出已記為 D8 手動 GUI 驗收項目。D1A 完成。

### D2-S1 大綱型別與樹建構（2026-11-27，本次觀察）

- **新增檔案**：
  - `app/desktop/src/lib/outline/types.ts`：`OutlineFormat`、`RawHeading`、`OutlineNode`（含 `id`、`title`、`level`、`depth`、`lineNumber`、`startOffsetUtf16`、`headingEndOffsetUtf16`、`sectionEndOffsetUtf16`、`parentId`、`children`）、`OutlineDocument`（`format`、`sourceText`、`roots`、`flat`）。
  - `app/desktop/src/lib/outline/tree.ts`：`buildOutlineTree`、`normalizeOutlineTitle`（相對層級堆疊、路徑式穩定 ID、同父同級同名兄弟序號、`sectionEndOffsetUtf16` 計算）。
  - `app/desktop/tests/outline.test.ts`：新增 3 項樹建構與 ID 穩定性測試（不連續層級、無 H1 開頭、同名兄弟 ID、無關增刪穩定性、唯一標題改名影響範圍、刪除第一個同名兄弟序號遞補、`sectionEndOffsetUtf16`）。
- **必要檢查**：`npm test` 通過（`261 passed, 0 failed`）。

### D2-S2 Markdown 掃描器（2026-11-27，本次觀察）

- **變更檔案**：
  - 新增 `app/desktop/src/lib/outline/markdown.ts`：`scanMarkdownHeadings`、`parseMarkdownOutline`、`stripMarkdownInline`（線性掃描 ATX H1–H6 含結尾 `#`、Setext 一二級、行內格式去除；排除 fenced code 含未關閉、indented code、HTML 註解含未關閉、YAML front matter、`#標題` 無空白、引用區塊與清單項含縮排續行）。
  - 修改 `app/desktop/tests/outline.test.ts`：新增 3 項 Markdown 測試，涵蓋所有語法、行內標記、中英混合／emoji、全部排除項與空文件。
- **必要檢查**：`npm test` 通過（`264 passed, 0 failed`）。

### D2-S3 LaTeX 掃描器與格式分派（2026-11-27，本次觀察）

- **變更檔案**：
  - 新增 `app/desktop/src/lib/outline/latex.ts`：`scanLatexHeadings`、`parseLatexOutline`、`cleanLatexTitle`（線性掃描 7 級章節指令、星號版、`[短標題]{完整標題}` 顯示完整標題、跨行與巢狀大括號、常見行內格式與 `\label` 清理；排除 `%` 註解含 `\%`／`\\%` 區分、5 種 verbatim 類環境、`\verb`／`\verb*`、`\newcommand`/`\renewcommand`/`\providecommand`/`\def` 定義內容、未閉合尾端指令）。
  - 新增 `app/desktop/src/lib/outline/index.ts`：`outlineFormatForPath`、`parseOutline(path, sourceText)` 與型別／掃描函式匯出。
  - 修改 `app/desktop/tests/outline.test.ts`：新增 3 項 LaTeX 與分派測試。
- **必要檢查**：`npm test` 通過（`267 passed, 0 failed`）。

### D2-S4 offset 一致性與效能量測（2026-11-27，本次觀察）

- **變更檔案**：
  - 修改 `app/desktop/tests/outline.test.ts`：新增 BOM + CRLF + emoji + CJK 的 Markdown 與 LaTeX offset 一致性測試，逐節驗證 `documentPositionAt(sourceText, startOffsetUtf16)` 之行號等於 `lineNumber`、欄位為 1，且原文該 offset 起點即標題起頭。
  - 新增 `harness/plans/2026-11-26-document-outline-sidebar/evidence/D2-S4/bench-outline.ts` 與 `results.txt`。
- **必要檢查**：
  - `npm test`：`268 passed, 0 failed`。
  - `npm run build`：通過（`tsc --noEmit`、`tsc --noEmit -p tsconfig.test.json`、`vite build` 504 ms）。
  - 效能量測（Node v24.18.0，Linux WSL2 x64，Intel Core Ultra 9 285H 16 cores，各 1,000 標題、20 次取中位數）：
    - Markdown ~100 KiB（82,688 B）：中位數 **1.77 ms**（A10 目標 ≤ 15 ms）
    - Markdown ~1 MiB（1,032,688 B）：中位數 **5.19 ms**（A10 目標 ≤ 50 ms）
    - LaTeX ~100 KiB（88,630 B）：中位數 **1.47 ms**（A10 目標 ≤ 15 ms）
    - LaTeX ~1 MiB（1,031,630 B）：中位數 **3.56 ms**（A10 目標 ≤ 50 ms）
- D2 完成。

### D3-S1 欄寬儲存與視窗夾限邏輯（2026-11-27，本次觀察）

- **新增檔案**：
  - `app/desktop/src/lib/layout.ts`：`SIDEBAR_WIDTH_KEY`（`research-agent.sidebarWidthPx`）、`DOCUMENT_RATIO_KEY`（`research-agent.documentSplitRatio`）、`read/write/clear`（`try/catch` 包裝與可注入 storage）、`clampSidebarWidth`、`clampDocumentRatio`、`resolveLayoutWidths`、`computeDraggedSidebarWidth`、`computeDraggedDocumentRatio`、`documentSplitFrValues`。
  - `app/desktop/tests/layout.test.ts`：新增 5 項單元測試，驗證合法值往返、超界夾限、非法字串回預設、storage 例外不拋出、清除回預設，以及 420 px 側欄＋0.8 比例於 1051 px、800 px、761 px 容器皆不溢出且文件／對話欄 ≥ 300 px。
- **必要檢查**：`npm test` 通過（`273 passed, 0 failed`）。

### D3-S2 ColumnResizer、格線變數與版面樣式（2026-11-27，本次觀察）

- **變更檔案**：
  - 新增 `app/desktop/src/components/ColumnResizer.tsx`：`role="separator"`、`aria-orientation="vertical"`、`aria-valuenow/min/max`、`aria-label`、`tabIndex`、`inert`、pointer capture 拖曳、`pointercancel`/`lostpointercapture` 清理 `is-resizing-columns` class、鍵盤與雙擊重設事件介面。
  - 新增 `app/desktop/src/styles/layout.css`：邊界元件樣式、拖曳中 `user-select: none`、`<= 1050px` 與 `<= 760px` 邊界隱藏規則（未重定義 `.app-shell` 或 `.writing-workspace` 的 `grid-template-columns`）。
  - 修改 `app/desktop/src/styles.css`：`.app-shell` 改為三欄（`var(--sidebar-track, minmax(10.15rem, 11.9rem)) var(--resizer-width) minmax(0, 1fr)`），加入 `--sidebar-viewport-max`（> 1050 px 與 761–1050 px 兩段計算）並於 `@media (min-width: 761px)` 明確指定子元素 `grid-column`。
  - 修改 `app/desktop/src/styles/document.css`：`.writing-workspace` 改為三欄（`minmax(300px, var(--document-fr, 1.05fr)) var(--resizer-width, 6px) minmax(300px, var(--conversation-fr, 1fr))`）並於 `@media (min-width: 1051px)` 明確指定子元素 `grid-column`；保留既有 `<= 1050px` 單欄規則。
  - 修改 `app/desktop/src/main.tsx`：在 `document.css` 之後 import `layout.css`。
  - 修改 `app/desktop/src/App.tsx`：掛載側欄與工作區兩條 `ColumnResizer`（刪除對話框開啟時設為 `inert`）並以 CSS 變數帶入寬度。
  - 修改 `app/desktop/tests/styles.test.ts` 與 `app/desktop/tests/layout.test.ts`：新增 CSS 載入順序／預設值／斷點／定位斷言與 `ColumnResizer` SSR 測試。
- **必要檢查**：`npm test` 通過（`275 passed, 0 failed`）；`npm run build` 通過（565 ms）。

### D3-S3 鍵盤調整、雙擊重設與拖曳純函式（2026-11-27，本次觀察）

- **變更檔案**：
  - 修改 `app/desktop/src/lib/layout.ts`：抽出 `keyboardActionForResizerKey`、`computeKeyboardSidebarWidth`、`computeKeyboardDocumentRatio`（16 px 步進、Home/End 邊界、Enter 不做事、容器夾限）。
  - 修改 `app/desktop/src/components/ColumnResizer.tsx` 與 `app/desktop/src/App.tsx`：改用上述純函式；`ColumnResizer` 在 `pointerup`/`pointercancel`/`lostpointercapture`/卸載皆清除 `is-dragging` 與 `body.is-resizing-columns`。
  - 修改 `app/desktop/tests/layout.test.ts`：新增鍵盤映射（含 Enter 不動作）、16 px 步進夾限、Home/End 與邊界條件測試。
- **必要檢查**：`npm test` 通過（`276 passed, 0 failed`）；`npm run build` 通過（604 ms）。實機滑鼠拖曳與雙擊重設列入 D8 手動驗收清單。D3 完成。

### D4-S1 useDocumentOutline 排程與收合狀態純邏輯（2026-11-27，本次觀察）

- **變更檔案**：
  - 新增 `app/desktop/src/lib/outline/state.ts`：`OUTLINE_DEBOUNCE_MS`（180 ms）、`planOutlineUpdate`（換檔立即、同檔 debounce、`null` 清空、純游標移動 noop）、`pruneCollapsedIds`、`toggleCollapsedId`、`recomputeOutline`、`emptyOutlineDocument`。
  - 修改 `app/desktop/src/lib/outline/index.ts`：匯出排程與收合輔助函式。
  - 新增 `app/desktop/src/hooks/useDocumentOutline.ts`：僅依賴 `[rootPath, path, sourceText]` 的薄包裝 hook，另提供 `refreshNow` 供 D5 過期點擊同步重算。
  - 修改 `app/desktop/tests/outline.test.ts`：新增排程與收合狀態單元測試。
- **必要檢查**：`npm test` 通過（`277 passed, 0 failed`）。

### D4-S2 OutlineView 元件與樣式（2026-11-27，本次觀察）

- **新增檔案**：
  - `app/desktop/src/components/OutlineView.tsx`：依層級縮排（`min(depth, 5) * 0.7rem`）、`role="tree"`／`treeitem`、`aria-level`、`aria-expanded`、`aria-current`、展開／收合鈕（內嵌 SVG）、`No headings found` 與未開檔提示、純文字渲染標題與 `title` 提示、預留 `activeId`／`activeAncestorId` 與 `onSelect(node)` 介面。
  - `app/desktop/src/styles/outline.css`：獨立捲動、長標題省略號截斷（`min-width: 0`）、目前章節與已收合祖先樣式（未改動 `.app-shell`／`.writing-workspace` 欄定義）。
  - `app/desktop/tests/outline_view.test.ts`：2 項 SSR 測試，驗證層級縮排與 `aria-level`、收合不渲染子孫、`No headings found`、未開檔提示及 `<script>`／`&` 純文字跳脫。
- **必要檢查**：`npm test` 通過（`279 passed, 0 failed`）。

### D4-S3 ActivityBar、側欄切換／收合與自動切換（2026-11-27，本次觀察）

- **變更檔案**：
  - 修改 `app/desktop/src/lib/sidebar.ts`：新增純狀態轉換函式 `INITIAL_SIDEBAR_VIEW_STATE`、`selectSidebarView`、`sidebarStateOnDocumentOpen`、`sidebarStateOnDocumentCleared`。
  - 新增 `app/desktop/src/components/ActivityBar.tsx`：內嵌 SVG 雙按鈕（Conversations／Outline），含 `aria-pressed`、`aria-expanded`、`inert`、收合標記。
  - 修改 `app/desktop/src/components/Sidebar.tsx`：維持品牌與 backend 控制在兩種檢視固定呈現，中間區依 `view` 顯示既有對話管理或 `outlineContent`。
  - 修改 `app/desktop/src/App.tsx`：掛載 `ActivityBar`、`useDocumentOutline`、`OutlineView`；於 `openDocument` 成功後自動切到大綱（收合時保持收合，A4）、於專案切換清空文件時切回對話管理（A5）；收合時隱藏側欄與側欄拖曳邊界並加上 `.sidebar-collapsed`。
  - 修改 `app/desktop/src/styles.css`、`app/desktop/src/styles/layout.css`、`app/desktop/src/styles/outline.css`、`app/desktop/src/main.tsx`：加入 44 px 圖示列欄位與 `@media (min-width: 761px)` 收合雙欄規則、≤ 760 px 橫向圖示列與單欄堆疊、`outline.css` 匯入於 `layout.css` 之後。
  - 修改 `app/desktop/tests/outline_view.test.ts` 與 `app/desktop/tests/styles.test.ts`：新增狀態轉換測試、`ActivityBar`/`Sidebar` SSR 測試、CSS 載入順序與收合斷點斷言。
- **必要檢查**：`npm test` 通過（`281 passed, 0 failed`）；`npm run build` 通過（681 ms）。D4 完成。

### D5-S1 目前章節追蹤與跳轉保護狀態機（2026-11-27，本次觀察）

- **變更檔案**：
  - 新增 `app/desktop/src/lib/outline/tracking.ts`：`findActiveHeadingId`（二分搜尋最內層標題）、`resolveActiveOutlineDisplay`（收合祖先標示）、`createOutlineTracker`（`useSyncExternalStore` 相容介面、跳轉保護阻擋同步與 rAF 延後的目標行／相同 `scrollTop` 事件、重算與重設）、`resolveOutlineJumpTarget`（過期點擊歧義檢查）、`jumpEditorToOffset` 與 `performOutlineClick`。
  - 修改 `app/desktop/src/lib/outline/index.ts`：匯出追蹤與跳轉輔助函式。
  - 新增 `app/desktop/tests/outline_tracking.test.ts`：4 項單元測試，覆蓋二分搜尋、最內層與收合祖先標示、跳轉保護重播（同步與延後捲動、不同 `scrollTop` 與游標移動解除）、重解析重算、重設清除、訂閱通知去重。
- **必要檢查**：`npm test` 通過（`285 passed, 0 failed`）。

### D5-S2 編輯器接線、跳轉序列與過期點擊處理（2026-11-27，本次觀察）

- **變更檔案**：
  - 修改 `app/desktop/src/DocumentEditor.tsx`：新增可選 props `onCursorLine`（`onDidChangeCursorPosition` 並於 model 建立後回報初始行）、`onViewport`（`onDidScrollChange` 且 `scrollTopChanged` 時經 `requestAnimationFrame` 合併）、`onHandle`（註冊 `{ jumpToOffset }` 並於釋放／換檔時傳 `null`）；未改動 `publishSelection`、第二個 effect、`CitationPanel` 路徑與 `scrollBeyondLastLine: false`。
  - 修改 `app/desktop/src/components/DocumentPane.tsx`：透傳 `onCursorLine`、`onViewport`、`onHandle`。
  - 修改 `app/desktop/src/components/OutlineView.tsx`：以 `useSyncExternalStore` 訂閱 `tracker`（捲動不重繪 `App`），套用目前章節與收合祖先標示，並以 `scrollIntoView({ block: "nearest" })` 捲入可視範圍而不搶焦點。
  - 修改 `app/desktop/src/hooks/useDocumentOutline.ts`：加入 `fileKey` 保護，換檔首幀絕不殘留前一份文件節點。
  - 修改 `app/desktop/src/App.tsx`：接線 `outlineTrackerRef`、`editorOutlineHandleRef`、換檔重設與點擊跳轉處理。
  - 修改 `app/desktop/tests/outline_tracking.test.ts` 與 `app/desktop/tests/outline_view.test.ts`：新增跳轉序列順序與不改選取／文件斷言、4 種過期點擊與 null handle 測試、生命週期依賴與釋放檢查、`OutlineView` SSR 追蹤標示測試。
- **程式審查結果**：`DocumentEditor.tsx` 建立 model 的 `useEffect` 依賴仍為 `[value?.rootPath, value?.path]`；`cursorListener.dispose()`、`scrollListener.dispose()`、`cancelAnimationFrame(scrollFrameId)`、`onHandle(null)` 皆於 `disposeEditor`（及 effect cleanup）釋放。
- **必要檢查**：`npm test` 通過（`289 passed, 0 failed`，含既有 `documents.test.ts` 等全部通過）；`npm run build` 通過（575 ms）。

### D5-S3 即時更新情境自動化覆蓋（2026-11-27，本次觀察）

- **變更檔案**：
  - 修改 `app/desktop/tests/outline_tracking.test.ts`：新增完整情境模擬測試，依序覆蓋開檔、新增標題、刪除標題、改名、改層級、大量貼上（40 章節）、Agent 修改 `sourceText`、Undo 回到舊版本、切換至 `.tex` 檔，驗證排程（`immediate`/`debounce`）、大綱樹、收合保留／修剪／重設及追蹤器重算／重設。
- **必要檢查**：`npm test` 通過（`290 passed, 0 failed`）；`npm run build` 通過（678 ms）。Monaco 內實機 Undo／Agent 修改／衝突處理列入 D8 手動驗收清單。D5 完成。

### D6-S1 LaTeX Monarch 語法定義與冪等註冊（2026-11-27，本次觀察）

- **新增檔案**：
  - `app/desktop/src/lib/latexLanguage.ts`：`LATEX_LANGUAGE_ID`、`editorLanguageForPath`、`LATEX_MONARCH_LANGUAGE`（涵蓋指令、章節指令、環境、註解與 `\%`、數學 `$`/`$$`/`\(...\)`/`\[...\]`/常見數學環境、引用指令與鍵、交叉引用、括號；所有引用參數狀態絕不使用含 `string`/`comment` 的 token 名稱）、`LATEX_LANGUAGE_CONFIGURATION`（`%` 行註解與括號配對）、`registerLatexLanguage`（以 `WeakSet` 冪等註冊）。
  - `app/desktop/tests/latex_language.test.ts`：3 項測試，驗證副檔名語言對應、重複呼叫僅註冊一次、所有規則正規表示式可編譯、引用狀態無 `string`/`comment` token 且支援 `\cite{`／`\citep{`／`\citet{`／`\textcite{`。
- **必要檢查**：`npm test` 通過（`293 passed, 0 failed`）。

### D6-S2 編輯器整合 LaTeX 語法高亮與語言選擇（2026-11-27，本次觀察）

- **變更檔案**：
  - 修改 `app/desktop/src/DocumentEditor.tsx`：於 `monaco.editor.createModel` 之前呼叫 `registerLatexLanguage(monaco)` 並以 `editorLanguageForPath(initial.path)` 選語言；維持 `registerCompletionItemProvider(model.getLanguageId(), ...)` 與 D1A 補全設定；未修改 `src/citations.ts`。
  - 修改 `app/desktop/tests/latex_language.test.ts`：新增檢查驗證註冊早於 `createModel` 且補全仍綁定 `model.getLanguageId()`。
- **必要檢查**：
  - `npm test` 通過（`294 passed, 0 failed`，含 `tests/citations.test.ts`）。
  - `npm run build` 通過（600 ms，978 modules）。
  - Bundle 比較：`index-M2oharq-.js` 為 `428.36 kB`（相對 D5 結束的 `424.90 kB` 增加 `+3.46 kB`；相對 D1A 的 `393.84 kB` 累計增加 `+34.52 kB`）；Monaco 延遲載入 chunks 維持不變；`grep -c editor.contrib.suggestController dist/assets/*.js` 仍為 `dist/assets/suggestController-B8cGBtPE.js:1`。
- `\cite{`、`\citep{`、`\citet{`、`\textcite{` 實機補全清單、Esc 後續打重現與語法顏色列入 D8 手動驗收清單。D6 完成。

### D7-S1 大綱鍵盤導覽純邏輯（2026-11-27，本次觀察）

- **變更檔案**：
  - 新增 `app/desktop/src/lib/outline/keyboard.ts`：`visibleOutlineNodes`、`resolveRovingFocusId`、`handleOutlineTreeKey`（Up/Down/Home/End/Left/Right/Enter、組字中 `isComposing`/`keyCode === 229` 與修飾鍵忽略）。
  - 修改 `app/desktop/src/lib/outline/index.ts`：匯出鍵盤導覽函式。
  - 新增 `app/desktop/tests/outline_keyboard.test.ts`：2 項測試，驗證葉節點／展開／收合／首尾邊界、組字中與非目標按鍵略過。
- **必要檢查**：`npm test` 通過（`296 passed, 0 failed`）。
