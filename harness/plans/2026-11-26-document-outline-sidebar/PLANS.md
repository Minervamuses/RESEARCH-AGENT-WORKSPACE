# 文件大綱側欄與可拖曳欄寬：路線與執行契約

- **計劃根目錄**：`harness/plans/2026-11-26-document-outline-sidebar/`（相對於 repo 根目錄 `/home/minervamuses/research-agent-workspace`）
- **目標與決策**：[GOALS.md](GOALS.md)
- **目前狀態與證據**：[build-log.md](build-log.md)，這是唯一的狀態來源
- **啟動入口**：[PROMPTS.md](PROMPTS.md)

## 任務規模

功能實作限於桌面前端（`app/desktop/`：React 19 + TypeScript + Monaco `0.57.0` + 純 CSS）。涉及 Python 後端、協定或 Rust 的回歸修復依下方執行契約。

風險集中在三處：

1. **狀態跨元件**：大綱在左側欄（`App` → `Sidebar`），編輯器在文件欄（`App` → `DocumentPane` → `DocumentEditor`），兩者是兄弟。需要一條不經過 `App` 重繪的通道傳遞「目前章節」，否則每次捲動都會重繪整個 `App.tsx`（1,928 行）。
2. **跳轉與追蹤的事件順序**：程式跳轉本身會觸發游標與捲動事件；處理不好就出現「點最後一章，高亮跳回前一章」或迴圈。
3. **版面格線**：`.app-shell` 多一條圖示列與一條拖曳邊界，`.writing-workspace` 多一條拖曳邊界；三個斷點（> 1050、761–1050、≤ 760 px）與 CSS 載入順序都要對。

## 基線（2026-11-26 撰寫時讀碼，HEAD `78cd9ac`，分支 `GUI`）

路徑相對於 `app/desktop/`。行號是撰寫時的位置，D1 重新核對。以下都是讀碼結論，撰寫時沒有執行測試或 GUI。

**版面**

- `src-tauri/tauri.conf.json`：視窗預設 `1080x720`，最小 `720x560`。
- `src/styles.css` 第 109–116 行 `.app-shell`：`grid-template-columns: minmax(10.15rem, 11.9rem) minmax(0, 1fr)`；第 118 行 `.sidebar` 是直向 flex、`overflow: auto`。根字級 `clamp(1rem, calc(0.75rem + 0.35vw), 1.3125rem)`，1080 px 寬時是 16 px，側欄約 190 px。
- `src/styles/document.css` 第 2 行 `.writing-workspace`：`minmax(0, 1.05fr) minmax(0, 1fr)`；第 3 行 `.document-pane`；第 26–33 行在 ≤ 1050 px 變單欄（文件與對話上下堆疊）、≤ 760 px 再調整高度。
- `src/styles/responsive.css`：≤ 760 px 時 `.app-shell` 單欄、側欄堆疊在上方並改成格線。
- `src/main.tsx` 第 5–11 行依序 import：`styles.css`、`workspace.css`、`sidebar.css`、`conversation.css`、`dialogs.css`、`responsive.css`、`document.css`（`responsive.css` 早於 `document.css`；同權重時後載入者勝）。
- 1080 px 寬時文件欄約 456 px；加上圖示列（約 44 px）後約 433 px。

**側欄與 App**

- `src/components/Sidebar.tsx`（92 行）：`<aside className="sidebar">` 依序是品牌 `brand-lockup`、`New conversation` 按鈕、`project-browser` 區（Switch project 與對話清單 `ProjectGroup`）、`sidebar-spacer`、`backend-controls`。所有狀態由 `App` 傳入。
- `src/App.tsx` 第 1760–1776 行：`<div className="app-shell">` 內是 skip link、`<Sidebar … inert={deleteDialog !== null}>`、`<main className="main-workspace">`；第 1778 行 `<div className="writing-workspace">` 內是 `DocumentPane` 與 `workspace-body`（對話）。
- `src/App.tsx` 第 217 行 `updateDocument`（`documentRef.current = value; setDocumentValue(value)`）。呼叫處：第 354 行（存檔／Agent 結果）、第 423 行（`openDocument` 成功開檔）、第 465 行（只更新 fingerprint）、第 804 行（切換專案等重設時設為 `null`）。只有第 423 行會換成另一份文件。
- `src/App.tsx` 第 408 行 `openDocument`：`api.pickDocument` → `api.documentOpen` → `updateDocument(snapshot)`。

**編輯器**（細節見 S2 brief「Current state」）

- `src/DocumentEditor.tsx` 第 49 行起的 effect 只依 `[value?.rootPath, value?.path]` 建立 model；第 66–69 行語言：`.md`/`.markdown` 用 `markdown`，其他（`.tex`）用 `plaintext`；第 73、78 行 `automaticLayout: true`、`scrollBeyondLastLine: false`。
- 第 160 行 `publishSelection`（掛在 `onDidChangeCursorSelection`）每次游標移動都呼叫 `onChange` → `App.updateDocument`，所以每次游標移動本來就會重繪 `App`；捲動不會。
- **既有缺陷（G11）**：第 57–61 行只動態載入 `monaco-editor/editor/editor.api`、worker 與 markdown 語言定義。從這兩個入口追 import 圖（約 704 個檔案）完全沒有 `editor/contrib/` 的編輯器功能：補全清單 `suggestController`、右鍵選單、搜尋、懸停、摺疊、括號配對等都沒載入；`dist/assets/` 沒有 `editor.contrib.suggestController`、`editor.contrib.contextmenu`、`editor.contrib.findController`。使用者 2026-11-26 實機確認文件編輯器打 `@`、`/` 不會跳出任何清單，Ctrl+F 沒反應。已載入的 `editor/browser/services/editorWorkerService.js` 含字詞建議提供者，所以補上清單後必須關掉字詞建議。`suggestController.js` 沒有 `.d.ts`。
- Monaco 內建 Markdown 語法把任何 `[...]` 標成 `string.link`（`markdown.js` 第 131 行），預設主題塗成暗紅色；所以 `[@key]`、`[TODO: …]` 顯示為紅字只是語法上色，與引用是否有效無關。Markdown 的 `[` 會自動補 `]`。
- 第 190 行引用補全以 `model.getLanguageId()` 註冊，`triggerCharacters: ["@", "{", ","]`。Monaco 的觸發字元補全不看 token 類型；打字時的 quick suggestions 在 `string`／`comment` token 內預設關閉（`node_modules/monaco-editor/esm/vs/editor/contrib/suggest/browser/suggestModel.js`）。
- 第 274 行起的第二個 effect：外部修改以 `executeEdits` 套用（保留 Undo）；只有範圍兩端都有值時才設定選取並捲動（`CitationPanel` 跳轉用這條，會叫出 `Add comment`）。
- `src/lib/documentSource.ts`：`documentPositionAt`／`documentOffsetAt` 以原始 `sourceText`（含 BOM、CRLF）的 UTF-16 單位換算；`modelSource` 會去掉 model 開頭的 BOM。
- `node_modules/monaco-editor/esm/vs/languages/definitions/` 有 81 種語言，沒有 LaTeX。

**儲存與測試**

- `src/editorZoom.ts`：`localStorage` 鍵 `research-agent.editorFontSize`，讀寫都包在 `try/catch`，可注入假的 storage 做測試。新的寬度儲存照這個模式。
- `package.json`：`npm test` = `node --test --experimental-strip-types tests/*.test.ts`；`npm run build` = 兩次 `tsc --noEmit`（含 `tsconfig.test.json`）+ `vite build`。依賴只有 `@tauri-apps/*`、`monaco-editor`、`react`、`react-dom`。
- `tests/documents.test.ts` 以 Vite `createServer` + `ssrLoadModule` 做 `.tsx` 的 SSR 渲染測試；沒有瀏覽器排版引擎，也跑不了 Monaco worker（ASM-025）。
- `tests/styles.test.ts` 只檢查 `:root` 的 `clamp(...)`。
- `src/hooks/` 已有 `useDisclosureMenu.ts`、`useExtensions.ts`。

**環境**（使用者機器的既有紀錄）

- npm、cargo 在 Conda 環境 `app`：先 `export PATH=/home/minervamuses/miniconda3/envs/app/bin:$PATH`。沙箱內 `~/.npm` 唯讀，npm 指令加 `npm_config_cache=$TMPDIR/npm-cache`。
- 完整 pytest 需要可寫的 `/tmp`，要在沙箱外跑：在 `app/` 下 `/home/minervamuses/miniconda3/envs/app/bin/python -m pytest -q -p no:cacheprovider`，`TMPDIR`、`XDG_CACHE_HOME`、`AGENT_LOG_DIR` 指到暫存目錄。接管道時檢查 `${PIPESTATUS[0]}`。
- 歷史基線（未重跑）：2026-11-22 `6c77fb0` pytest 1827、npm 253、cargo 35。驗收標準是「全部通過」，不是固定數字。

**工作樹**

- 撰寫時有與本計劃無關的修改與未追蹤檔：`app/skills/grill/SKILL.md`（已修改）、`.agents/`、`.opencode/`、`NOTES-grill-skill-and-document-context.md`、`note/20261106/`，以及 repo 根目錄的 `.bashrc`、`.claude/` 等點檔（沙箱掛載產生）。一律不動、不提交；commit 只 `git add` 明確路徑。

## 架構

以下是本計劃採用的設計。檔名是提議，執行者可依實際情況調整，但介面與行為要符合 GOALS。

```text
App
├─ useDocumentOutline(documentValue)  → outline（樹＋扁平清單＋sourceText 戳記）、collapsedIds
├─ outlineTracker（useRef，非 React state）← DocumentEditor 回報游標行／可視頂行；Outline 檢視訂閱
├─ editorHandleRef ← DocumentEditor 註冊 { jumpToOffset }
├─ sidebarView: "conversations" | "outline"、sidebarCollapsed
├─ ActivityBar（圖示列）
├─ Sidebar：品牌｜(對話管理 或 OutlineView)｜backend 控制
├─ ColumnResizer（側欄｜主區）
└─ main → writing-workspace：DocumentPane｜ColumnResizer｜對話
```

1. **純邏輯模組 `src/lib/outline/`**：`types.ts`、`markdown.ts`、`latex.ts`、`tree.ts`、`tracking.ts`、`index.ts`（`parseOutline(path, sourceText)` 依副檔名分派）。不依賴 React 或 Monaco，Node 直接 import 測試；不用 TS `enum`／`namespace`（`--experimental-strip-types` 不支援）。
2. **目前章節通道**：`tracking.ts` 提供 `createOutlineTracker()`，內含純狀態機與 `subscribe`／`getSnapshot`。`DocumentEditor` 回報游標行與可視範圍（頂行＋`scrollTop`）；`OutlineView` 以 `useSyncExternalStore` 讀目前章節 ID。捲動只重繪大綱檢視，不重繪 `App`。游標移動本來就會重繪 `App`，不另外處理。tracker 保留最後的游標行、可視頂行與哪一個較新；大綱重新解析後用它們重算目前章節；換檔或文件變 `null` 時整個重設。
3. **跳轉保護**：點標題時先在 tracker 設定「跳轉中（目標 ID）」，再 `setPosition` → `revealLineNearTop(line, ScrollType.Immediate)`（預設是 Smooth，必須明確指定）→ `focus`，並記下跳轉後的 `getScrollTop()`。跳轉造成的游標事件與 `scrollTop` 等於記錄值的捲動事件，不論同步到達或經 rAF 延後，都不能解除保護；之後 `scrollTop` 不同的捲動或游標移到其他行才解除。點擊時若大綱戳記與目前 `sourceText` 不同，先同步重新解析，依 D5 確認原章節才跳轉；同名節點或祖先造成歧義時只刷新大綱；編輯器 handle 尚未註冊（Monaco 載入中或換檔中）時安靜略過。跳轉序列寫成可注入假編輯器的純函式，以測試驗證呼叫順序。
4. **解析時機**：`useDocumentOutline` 只依 `[rootPath, path, sourceText]`，絕不依整個 `documentValue`（游標移動會產生新物件）。換檔立即解析並重設收合；同檔內容變動約 180 ms debounce（A9）。
5. **側欄檢視**：`Sidebar` 保持只顯示、不持有狀態；中間區塊依 `view` 顯示對話管理或 `OutlineView`。`App` 在 `openDocument` 成功後設為大綱（A4：收合時不自動展開），在第 804 行的重設處設回對話管理（A5）。
6. **欄寬**：`src/lib/layout.ts` 負責讀寫與夾限（照 `editorZoom.ts` 的模式，鍵名用 `research-agent.` 前綴）；`ColumnResizer` 是 `role="separator"`、`aria-orientation="vertical"` 的元件，拖曳期間直接改 CSS 變數（例如 `--sidebar-width`、`--document-fr`、`--conversation-fr`），放開時才寫入 React 狀態與儲存，避免拖曳時每幀重繪。沒有儲存值時 CSS 回到現在的預設格線。儲存的是使用者要的寬度；實際寬度另由 CSS `min()`／`minmax()` 依目前視窗夾限，所以在大視窗存的寬度縮小視窗後也不會溢出。
7. **樣式與格線位置**：`grid-template-columns` 只在原檔修改——`.app-shell` 在 `src/styles.css`、`.writing-workspace` 在 `src/styles/document.css`——以 `var(--…, 現在的預設值)` 帶入變數，讓 `responsive.css`（≤ 760 px）與 `document.css`（≤ 1050 px）既有的單欄規則照舊生效。`.app-shell` 的每個直接子元素都明確指定 `grid-column`，側欄收合時以 modifier class 換成另一組欄定義，避免元素被自動排進錯誤的欄。桌面多欄定位與收合欄型只在 > 760 px 套用；≤ 760 px 時圖示列、可見側欄與主區都在第一欄。新增 `src/styles/layout.css`（圖示列、拖曳邊界的元件樣式，以及只針對新元素的 `@media`）與 `src/styles/outline.css`，在 `main.tsx` 依序 import 在 `document.css` 之後；這兩個檔案不得重新定義 `.app-shell` 或 `.writing-workspace` 的欄（它們最後載入，會蓋掉窄版規則）。
8. **補全清單（D1A）**：編輯器建立前與既有動態 import 一起載入 `suggestController`，以本地 `declare module` 宣告型別，並設 `wordBasedSuggestions: "off"`、`quickSuggestions.strings: "on"`。
9. **P1 語法高亮**：`src/lib/latexLanguage.ts` 用 Monarch 定義 `latex`；以模組層級旗標保證語言只註冊一次；引用指令大括號內的鍵標成 `identifier`，任何 token 名稱都不含 `string`／`comment`。

## 路線

| 階段 | 後置條件 | 相依 | 涵蓋 | 細節 |
|---|---|---|---|---|
| D1 | 分支、HEAD、工具、基線位置已核對；修改前的 npm／build 基線已記錄；計劃已提交 | 無 | G9 | [phase-1-preflight.md](build/phase-1-preflight.md) |
| D1A | 修復既有缺陷：文件編輯器載入補全清單，引用補全可見、一般文字不跳建議 | D1 | G11 | [phase-1a-citation-suggest.md](build/phase-1a-citation-suggest.md) |
| D2 | 大綱解析核心與單元測試完成，含 offset 一致性與效能量測 | D1 | G1 | [phase-2-outline-core.md](build/phase-2-outline-core.md) |
| D3 | 兩條直立邊界可拖曳、鍵盤調整、雙擊重設、寬度記憶 | D1 | G6 | [phase-3-resizable-columns.md](build/phase-3-resizable-columns.md) |
| D4 | 圖示列、側欄檢視切換、收合、自動切換與大綱檢視呈現完成 | D2、D3 | G2、G3 | [phase-4-sidebar-outline.md](build/phase-4-sidebar-outline.md) |
| D5 | 點標題跳轉、目前章節追蹤、即時更新完成 | D4 | G4、G5 | [phase-5-navigation-tracking.md](build/phase-5-navigation-tracking.md) |
| D6 | P1：`.tex` 語法高亮且引用補全清單照樣出現 | D1A、D5 | G7 | [phase-6-latex-highlighting.md](build/phase-6-latex-highlighting.md) |
| D7 | P1：大綱鍵盤操作 | D5 | G8 | [phase-7-outline-keyboard.md](build/phase-7-outline-keyboard.md) |
| D8 | README、完整回歸、手動 GUI 清單與最終彙報 | D1A、D2–D7 | G9、G10 | [phase-8-delivery.md](build/phase-8-delivery.md) |

D1A、D2、D3 彼此互不相依；建議 D1 之後先做 D1A，讓 Markdown 的引用補全不必等到 P1。D2 與 D3 可任意先後。D6 與 D7 互不相依；D6 排在 D5 之後只是為了避免同時修改 `DocumentEditor.tsx`。每個階段結束時 `npm test` 與 `npm run build` 都要通過，產品維持可用（D4 完成時大綱已可看、D5 完成時已可跳轉）。

## 檢查範圍

| 檢查 | 指令（在 `app/desktop/`） | 何時必要 |
|---|---|---|
| 前端單元／SSR 測試 | `npm_config_cache=$TMPDIR/npm-cache npm test` | 每個修改程式的步驟 |
| 型別與打包 | `npm_config_cache=$TMPDIR/npm-cache npm run build` | 每個階段結束；D8 |
| 完整 pytest | 見「基線／環境」，在 `app/`、沙箱外 | D8 一次 |
| cargo test | `cargo test --locked --manifest-path src-tauri/Cargo.toml`，沙箱外 | 只有改到 `src-tauri/` 時（預期不會） |
| 解析效能量測 | 暫存目錄中的一次性 Node 腳本，結果存 `evidence/D2-S4/` | D2 |
| 手動 GUI 驗收 | 使用者依 D8 清單操作 | 交付後由使用者執行；執行者不宣稱已驗證 |

## 執行契約

本文件規定工作內容，本身不授權實作。只要求撰寫計劃時，交付經檢查的計劃檔即結束。使用者明確啟動此計劃後，執行者在已授權範圍內跨階段連續執行，包括一般實作選擇、修復、檢查與計劃維護；交接時保留這份授權，遵守宿主與工具的權限控制及使用者之後的變更。不從一般計劃文字推定付費服務、遠端寫入、發佈、破壞性操作或更大的範圍。已授權的事不重複請求確認。

**授權範圍**（使用者以 PROMPTS 的啟動提示啟動時）：GOALS 範圍內 `app/desktop/src/`、`app/desktop/tests/`、`README.md` 的修改；本計劃目錄內的檔案；「檢查範圍」所列的檢查；本地 commit。**不授權**：新增或升級依賴（`package.json`／`package-lock.json`）、修改後端／協定／`src-tauri`（除非為修復本計劃造成的問題且最終彙報列明）、修改 `for_agents/`、付費 API 呼叫、push、建立或切換 branch。

**每一步**：先讀適用的專案說明（`AGENTS.md`、`CLAUDE.md`）、GOALS、本檔、build-log 與相關的現行程式。保留無關的既有修改。完成一個有界步驟 → 跑該步驟的必要檢查 → 在 build-log 記錄實際觀察到的結果與限制 → 本地 commit（subject 帶步驟 ID，例如 `feat(desktop-ui): … [D2-S1]`；只 `git add` 明確路徑；計劃 `build/` 下的檔案用 `git add -f`）→ 才進入相依的下一步。檢查失敗而保留證據時也要 commit 一個 checkpoint。

**失敗與阻塞**：先診斷並在範圍內修復。同一問題兩次聚焦修正仍失敗，只封鎖該問題與相依步驟，在 build-log 標 `Blocked` 並寫明恢復需要什麼，繼續其他前提已滿足的工作；全部剩餘工作都被阻塞時才停止並彙報。不得把必要檢查的失敗改成通過，不得刪除或弱化既有測試來換取通過。

**改變路線**：證據顯示路線需要改變時，先修訂受影響的未開始／進行中階段與 plan-index.json（並 commit），再繼續。不得自行改變 GOALS 的目標、範圍外項目或驗收；需要時停止相應部分，列入最終彙報。

**不停下來等使用者**：需要使用者決定或驗證的事（含 GUI 驗收、A1–A10 的確認）一律寫進最終彙報，不中途等待。

**完成判定**：只依實際觀察到的驗收結果判定階段完成，不依程式寫完、結構 lint 通過或 commit 存在。跳過或無法執行的必要檢查不算通過。證據要分清楚是本次觀察、沿用、歷史紀錄或提議。中斷後先比對 build-log、`git log`（以步驟 ID）與工作樹，再決定從哪裡續作；同一問題的嘗試次數不因重新啟動而歸零。

## 整體完成條件

1. D1、D1A、D2–D8 在 build-log 都是 `Complete`，或少數步驟 `Blocked` 且原因、影響、恢復需求寫明。
2. G1–G11 的每個成功條件都有自動測試證據，或明確列為使用者手動 GUI 驗收項目。
3. D8 的 `npm test`、`npm run build`、完整 pytest 全部通過（改到 `src-tauri` 時加 cargo）。
4. 最終彙報 `evidence/D8-S3/final-report.md` 已提交，內容包含：手動 GUI 清單、已知限制、A1–A10 待確認、`for_agents/` 需要 `$infrastructure` 更新之處、測試數字。
5. 工作樹中本計劃的修改都已提交，無關檔案保持原狀。
