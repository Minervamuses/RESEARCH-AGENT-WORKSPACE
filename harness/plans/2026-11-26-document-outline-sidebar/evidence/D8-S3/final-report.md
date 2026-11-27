# 文件大綱側欄與可拖曳欄寬：最終彙報（D8-S3）

- **日期**：2026-11-27
- **分支**：`GUI`（未切換／新建分支，未 push）
- **起點基線 HEAD**：`bc9f651`
- **階段狀態**：D1、D1A、D2、D3、D4、D5、D6、D7、D8 全部完成（`Complete`），**無任何阻塞項目**。
- **重要聲明**：本彙報的所有通過紀錄皆為**自動單元測試、SSR 渲染測試、CSS 靜態檢查、TypeScript 檢查、Vite 打包、Node 效能基準與 Python `pytest`** 之實測結果。**尚未啟動桌面 GUI 或進行任何實機瀏覽器／WebView 互動驗證**；所有實機互動與視覺驗收均列於下方〈手動 GUI 驗收清單〉由使用者親自操作確認。

---

## 1. 目標對照與證據總覽（G1–G11）

| 目標 | 自動化驗證證據（本次觀察） | 留待使用者手動 GUI 驗收項目 |
|---|---|---|
| **G1** Markdown 與 LaTeX 共用大綱樹、UTF-16 offset 與穩定 ID | `app/desktop/tests/outline.test.ts`（樹建構、不連續層級、無 H1 開頭、同名兄弟與無關增刪穩定性、`sectionEndOffsetUtf16`；Markdown ATX/Setext/行內標記去除與全部排除項；LaTeX 7 級指令、`*`、`[短]{完整}`、跨行／巢狀大括號與全部排除項；BOM+CRLF+emoji+CJK offset 與 `documentPositionAt` 一致性）；`evidence/D2-S4/results.txt` 效能量測 | 清單第 2、12 項（以範例檔 01–07 實機開啟檢查大綱樹） |
| **G2** 圖示列切換、自動切換、點目前圖示收合與保留固定區 | `app/desktop/tests/outline_view.test.ts`（純狀態轉換測試：啟動對話管理、開檔切大綱、重設回對話管理、點目前圖示收合／再點展開、點另一圖示展開切換、收合時開檔維持收合；`ActivityBar`／`Sidebar` SSR 驗證品牌與 backend 控制雙檢視皆保留、ARIA 狀態與 `inert`）；`app/desktop/tests/styles.test.ts`（格線與斷點） | 清單第 1、2、3、9 項 |
| **G3** 大綱檢視呈現（層級、收合、空狀態、長標題、防 XSS） | `app/desktop/tests/outline_view.test.ts`（SSR 測試層級 `aria-level` 與 `--outline-depth`、收合不渲染子節點、`No headings found`、未開檔提示、`<script>` 與 `&` 跳脫為純文字）；`useDocumentOutline.ts` 以 `fileKey` 確保換檔首幀不殘留舊節點 | 清單第 2、3、5 項（含 `03-bilingual-cjk-english.md` 長標題截斷與 `title` 提示、`06-no-headings.md`） |
| **G4** 點大綱標題跳轉、不改文件／選取／Undo、文末不跳回 | `app/desktop/tests/outline_tracking.test.ts`（純函式跳轉序列驗證 `armJump` → `setPosition` → `revealLineNearTop(…, Immediate)` → `focus`，從未呼叫 `setSelection` 或帶範圍 `onChange`；過期點擊歧義判斷與 null handle 靜默略過；`DocumentEditor.tsx` 依賴陣列維持 `[value?.rootPath, value?.path]`） | 清單第 4、7 項（含文末 2 行 Conclusion 跳轉與 Undo 歷史保留） |
| **G5** 目前章節追蹤與即時更新 | `app/desktop/tests/outline_tracking.test.ts`（二分搜尋、最內層、收合祖先標示、同步與 rAF 延後跳轉保護重播、重解析重算與換檔重設、新增／刪除／改名／改層級／貼上 40 節／Agent 修改／Undo／換檔模擬）；`OutlineView` 透過 `useSyncExternalStore` 訂閱 tracker（捲動不重繪 `App`）；SSR 驗證 `.is-active` 與 `.is-active-ancestor` | 清單第 5、6、12 項（實機捲動、Monaco Undo、Agent 編輯與版本衝突處理） |
| **G6** 可左右拖曳欄寬、鍵盤調整、雙擊重設、寬度記憶與視窗夾限 | `app/desktop/tests/layout.test.ts`（`localStorage` 讀寫／清除／例外不拋出、160–420 px 與 0.2–0.8／300 px 夾限、420 px＋0.8 於 1051/800/761 px 容器皆不溢出且文件／對話 ≥ 300 px、拖曳與鍵盤 16 px 步進／Home／End／Enter 不動作純函式、`ColumnResizer` SSR ARIA）；`app/desktop/tests/styles.test.ts`（預設值與斷點規則） | 清單第 8、9 項（實機滑鼠拖曳、雙擊重設、重開記憶、視窗縮放至 1060／1000／900／740 px） |
| **G7** P1：`.tex` 語法高亮與引用補全相容 | `app/desktop/tests/latex_language.test.ts`（冪等註冊、Monarch 規則編譯、所有引用參數狀態不含 `string`/`comment` token、`\cite{`/`\citep{`/`\citet{`/`\textcite{` 規則覆蓋、`DocumentEditor` 於 `createModel` 前註冊並以 `model.getLanguageId()` 註冊補全）；`tests/citations.test.ts` 通過 | 清單第 10 項（`.tex` 實機顏色與四種引用指令補全／Esc 後續打） |
| **G8** P1：大綱鍵盤操作（範圍限定且不干擾輸入法） | `app/desktop/tests/outline_keyboard.test.ts`（Up/Down/Home/End/Left/Right/Enter 覆蓋葉節點、展開、收合與首尾邊界，IME `isComposing`/`keyCode === 229`、修飾鍵與其他鍵不攔截）；`app/desktop/tests/outline_view.test.ts`（SSR 斷言整棵樹僅有一個 `tabIndex=0` 與正確 tree ARIA） | 清單第 11 項（實機 Tab 進出大綱與 Composer 中文輸入法 Enter） |
| **G9** 既有行為、離線打包與邊界約束 | `npm test` 297/297、`npm run build` 通過、`pytest` 1,826/1,826；`evidence/D8-S2/boundary-diff.txt` 為 **0 bytes**（未動 `app/agent`、`app/desktop/protocol`、`app/desktop/src-tauri`、`package.json`、`package-lock.json`、`for_agents/`）；零新增依賴、零 CDN、不耗 LLM token | 清單第 7、12 項（既有引用面板、批註、核准與存檔實機流程） |
| **G11** 修復既有缺陷：文件編輯器引用補全清單 | `app/desktop/tests/editorZoom.test.ts`（`wordBasedSuggestions: "off"`、`quickSuggestions: { other: "on", comments: "off", strings: "on" }`、`suggestController` 於 `create` 前載入）；`app/desktop/src/monaco-contrib.d.ts` 無 TS7016；`evidence/D8-S2/suggest-check.txt` 確認 `dist/assets/suggestController-B_e4S7NY.js:1`（D1 基線為 0） | 清單第 10 項（`.md` 輸入 `[@`、`.tex` 四種引用指令、Esc 後續打、Ctrl+Space、一般內文不跳字詞建議） |
| **G10** 交付文件、完整回歸與彙報 | `README.md` 已更新並通過 `git diff --check`；`evidence/D8-S2/` 完整回歸紀錄；本報告與 `evidence/D8-S3/fixtures/` 7 類範例檔已提交 | 使用者執行下方清單並確認 A1–A10 |

---

## 2. 各階段 Commit 清單（`GUI` 分支）

| 階段 | 步驟 | Commit | 摘要 |
|---|---|---|---|
| D1 | D1-S1 | `b19d62e` | 唯讀基線與工具環境核對 |
| D1 | D1-S2 | `6139043` | 修改前 `npm test`（256）與 `npm run build` 基線 |
| D1A | D1A-S1 | `63dc2e6` | 載入 Monaco `suggestController`、本地型別宣告與補全選項 |
| D1A | D1A-S2 | `db90738` | `DocumentEditor.tsx` 補全清單生命週期審查 |
| D2 | D2-S1 | `61bd2ec` | 大綱節點型別、相對層級樹建構與路徑穩定 ID |
| D2 | D2-S2 | `54a76ae` | 線性時間 Markdown 標題掃描器與行內格式去除 |
| D2 | D2-S3 | `1824fc1` | 線性時間 LaTeX 章節掃描器與副檔名分派 |
| D2 | D2-S4 | `eac578f` | BOM／CRLF／emoji／CJK offset 一致性測試與 100 KiB／1 MiB 效能量測 |
| D3 | D3-S1 | `694b2f7` | 欄寬儲存、比例換算與視窗夾限純邏輯 |
| D3 | D3-S2 | `4d4bbd0` | `ColumnResizer` 元件、`layout.css` 與雙容器三欄格線 |
| D3 | D3-S3 | `ed6fd06` | 抽出鍵盤調整純函式、邊界測試與拖曳狀態清理 |
| D4 | D4-S1 | `581114d` | `useDocumentOutline` 排程／收合純邏輯與 hook |
| D4 | D4-S2 | `91b8be6` | `OutlineView` 元件、`outline.css` 與 SSR 測試 |
| D4 | D4-S3 | `87580e0` | `ActivityBar`、`Sidebar` 雙檢視、自動切換、收合與四欄／收合雙欄格線 |
| D5 | D5-S1 | `578a9d4` | `OutlineTracker`、二分搜尋、收合祖先與跳轉保護狀態機 |
| D5 | D5-S2 | `0e00048` | `DocumentEditor`／`DocumentPane`／`App`／`OutlineView` 跳轉與追蹤接線 |
| D5 | D5-S3 | `020c824` | 新增／刪除／改名／改層級／大量貼上／Agent 修改／Undo／換檔自動化覆蓋 |
| D6 | D6-S1 | `ce18925` | 本地 LaTeX Monarch 語法規則、語言設定與冪等註冊 |
| D6 | D6-S2 | `26e194e` | `DocumentEditor` 啟用 `.tex` 語法高亮與語言選擇 |
| D7 | D7-S1 | `f521c6b` | 大綱樹鍵盤導覽純邏輯與測試 |
| D7 | D7-S2 | `1dfc4d1` | `OutlineView` roving tabindex、焦點樣式與鍵盤接線 |
| D8 | D8-S1 | `6ec5855` | `README.md` 新增功能與限制說明 |
| D8 | D8-S2 | `7480f5b` | 完整回歸（`npm test`、`npm run build`、`pytest`）與授權邊界查核 |
| D8 | D8-S3 | （本次 commit） | 最終彙報、7 類手動 GUI 驗收範例檔與 `build-log.md` 結案 |

---

## 3. 測試、效能與 Bundle 數字

### 3.1 測試結果（修改前後比較）

| 套件 | D1-S2 修改前 | D8-S2 修改後 | 說明 |
|---|---|---|---|
| `app/desktop` `npm test` | 256 passed, 0 failed（6.47 s） | **297 passed, 0 failed**（8.95 s wall） | 新增 +41 項單元／SSR／CSS 測試 |
| `app/desktop` `npm run build` | 通過（4.49 s，940 modules） | **通過**（5.41 s，979 modules） | `tsc --noEmit` 與 `tsconfig.test.json` 皆 0 錯誤 |
| `app` 完整 `pytest`（沙箱外，Conda `app`） | （D1 未跑；歷史參考 1,827） | **1,826 passed, 0 failed**, 2 warnings（57.49 s） | 全部通過；詳見 `evidence/D8-S2/pytest.log` |
| `src-tauri` `cargo test` | 未跑（未改動） | 未跑（`src-tauri/` diff 為 0 bytes） | — |

### 3.2 大綱解析效能量測（D2-S4，`evidence/D2-S4/results.txt`）

測試環境：Node `v24.18.0`，Linux WSL2 x64，Intel Core Ultra 9 285H（16 cores），各 1,000 個標題、暖身後執行 20 次取中位數：

| 測試項目 | 檔案大小 | 標題數 | 中位數 | 最小 / 最大 | A10 參考目標 |
|---|---|---|---|---|---|
| Markdown ~100 KiB | 80.8 KiB（82,688 B） | 1,000 | **1.77 ms** | 1.29 / 2.87 ms | ≤ 15 ms |
| Markdown ~1 MiB | 1,008.5 KiB（1,032,688 B） | 1,000 | **5.19 ms** | 4.56 / 9.81 ms | ≤ 50 ms |
| LaTeX ~100 KiB | 86.6 KiB（88,630 B） | 1,000 | **1.47 ms** | 1.17 / 2.20 ms | ≤ 15 ms |
| LaTeX ~1 MiB | 1,007.5 KiB（1,031,630 B） | 1,000 | **3.56 ms** | 3.25 / 5.46 ms | ≤ 50 ms |

### 3.3 Bundle 大小比較（D1-S2 含 `monacoFeatures` 基線 vs D8-S2 最終）

| 產物 | D1-S2 基線 | D8-S2 最終 | 變化 |
|---|---|---|---|
| `dist/assets/index-*.js` | 393.42 kB（gzip 112.00 kB） | 430.98 kB（gzip 123.92 kB） | +37.56 kB（gzip +11.92 kB） |
| `dist/assets/index-*.css` | 25.33 kB（gzip 6.14 kB） | 30.16 kB（gzip 7.17 kB） | +4.83 kB（gzip +1.03 kB） |
| 延遲載入 Monaco JS 合計 | 3,305,374 B | 3,425,229 B | +119,855 B（全來自 D1A `suggestController`） |
| 延遲載入 Monaco CSS 合計 | 147,388 B | 159,613 B | +12,225 B（全來自 D1A `suggestController`） |
| `editor.contrib.suggestController` | 0 | **1**（`suggestController-B_e4S7NY.js`） | 修復 G11 |

---

## 4. 邊界查核、偏離紀錄與已知限制

- **授權邊界**：`git diff --stat bc9f651 -- app/agent app/desktop/protocol app/desktop/src-tauri app/desktop/package.json app/desktop/package-lock.json for_agents` 輸出 **0 bytes**。沒有任何後端／協定／Rust 回歸修復例外，也無新增或升級依賴。
- **阻塞與偏離**：無任何步驟被阻塞，無偏離 GOALS 或路線之改動。額外防護：`useDocumentOutline.ts` 以 `fileKey` 保護渲染回傳值，確保換檔首幀也不殘留前一份文件節點。
- **既有工作樹檔案**：啟動前已存在的無關修改／未追蹤檔（`app/skills/grill/SKILL.md`、`.agents/`、`.claude/`、`.opencode/`、`NOTES-grill-skill-and-document-context.md`、`note/20261106/`）全程保留原狀、未改動也未提交。
- **已知限制**：
  1. 一次只開啟一份文件，大綱只解析目前開啟的單一檔案；不遞迴展開 `\input{}`／`\include{}` 或自訂巨集。
  2. 不提供 LaTeX 編譯或 PDF 預覽，不提供上下方向邊界拖曳。
  3. **U6 預期行為提醒**：點選圖示列目前已選中的圖示收合側欄時，上方的品牌區與下方的 Backend 狀態及 **Start／Restart／Shut down** 控制會隨側欄一併隱藏；要查看或操作後端控制時，先點任一圖示展開側欄即可。
  4. 本計劃依 U8 不引入瀏覽器自動化框架，所有實機 GUI、滑鼠拖曳、Monaco 捲動／顏色／補全與中文輸入法行為尚未於真實 WebView 驗證，須由使用者依下方清單確認。

---

## 5. 待使用者確認的假設（A1–A10）

以下假設皆已依計劃實作且可輕易調整，請於實機試用後確認是否維持：

| ID | 目前實作選擇 | 調整方式（若不同意） |
|---|---|---|
| A1 | Markdown／LaTeX 解析器皆為零依賴自寫線性掃描器 | 若需換第三方套件須另行授權 |
| A2 | 點選或 Enter 跳轉標題後，焦點移至編輯器 | 改留在大綱只需調整 `jumpEditorToOffset` 一處 |
| A3 | 跳轉以 `revealLineNearTop(line, Immediate)` 捲近頂端；文末受 `scrollBeyondLastLine: false` 限制時維持游標抵達、標題可見且高亮不跳回 | 可改為 `revealLineInCenter` |
| A4 | 側欄收合時開啟文件：圖示列選中改為「大綱」，但側欄維持收合 | 可改為自動展開 |
| A5 | 切換專案清空文件時，檢視回到「對話管理」 | 可改為停留在「大綱」 |
| A6 | 僅記憶欄寬（`localStorage`），不記憶檢視與收合狀態（每次啟動皆為展開的對話管理） | 可改為記憶檢視與收合狀態 |
| A7 | 側欄 160–420 px；文件與對話欄各至少 300 px；鍵盤每次 16 px；窄視窗優先保住文件／對話最小寬度且不覆寫儲存值 | 調整 `src/lib/layout.ts` 與 `styles.css` 常數 |
| A8 | ≤ 760 px 隱藏兩條邊界且圖示列改為頂端橫列；761–1050 px 僅保留側欄邊界 | 調整 `styles.css`／`layout.css` 斷點 |
| A9 | 換檔立即解析，同檔編輯採 180 ms debounce（Agent 修改與 Undo 走同路徑） | 調整 `OUTLINE_DEBOUNCE_MS` |
| A10 | 解析時間目標（100 KiB ≤ 15 ms、1 MiB ≤ 50 ms）實測皆 < 6 ms，已遠優於門檻 | 可另訂門檻 |

---

## 6. 需要由 `$infrastructure` 更新的 `for_agents/` 段落

依授權契約，本計劃未修改 `for_agents/`。建議後續執行 `$infrastructure` 時更新以下位置：

1. **`for_agents/ui-architecture.md`**：
   - 更新左側欄 surfaces 與 controls：新增最左側 `ActivityBar`（Conversations／Outline 雙檢視切換與收合）、`Sidebar` 中間區塊可切換為 `OutlineView`（固定品牌與 backend 控制；收合時側欄與邊界一併卸載）。
   - 更新兩條直立 `ColumnResizer`（`sidebar | main`、`document | conversation`）、`localStorage` 鍵 `research-agent.sidebarWidthPx` 與 `research-agent.documentSplitRatio`，以及 `.app-shell` 四欄／收合雙欄與 `.writing-workspace` 三欄格線。
   - 記錄 `useDocumentOutline`（依賴 `[rootPath, path, sourceText]`）與 `createOutlineTracker`（`useSyncExternalStore` 通道避免捲動重繪 `App`）及 `EditorOutlineHandle` 跳轉介面。
2. **`for_agents/change-playbooks.md`**：
   - 更新桌面樣式檔案與 `app/desktop/src/main.tsx` 匯入順序：`styles.css` → `workspace.css` → `sidebar.css` → `conversation.css` → `dialogs.css` → `responsive.css` → `document.css` → `layout.css` → `outline.css`。
   - 註明格線欄定義歸屬不變條件：`.app-shell` 與 `.writing-workspace` 的 `grid-template-columns` 只在 `styles.css` 與 `document.css` 修改，`layout.css` 與 `outline.css` 不得重定義，且多欄定位與收合欄型僅套用於對應桌機斷點（`> 760px`、`> 1050px`）。
3. **`for_agents/briefs/2026-11-26-document-outline.md`**：
   - 標註已被使用者決策 U1–U6 取代的段落（「大綱放在 `DocumentPane` 內」「`DocumentHeader` Outline 開關」「Option 2 面板位置」「大綱狀態全留 `DocumentPane`」已改為 `ActivityBar`＋`Sidebar` 檢視）。
   - 更正誤標：該 brief 將「離線打包不載入 CDN」標成 `INV-029`；實際上 `INV-029` 是「產生的 store、secrets、`.env` 不提交」。
4. **`for_agents/system-map.md`（若列出前端模組地圖）**：
   - 補入新增模組：`app/desktop/src/lib/outline/{types,tree,markdown,latex,state,tracking,keyboard,index}.ts`、`src/lib/layout.ts`、`src/lib/latexLanguage.ts`、`src/hooks/useDocumentOutline.ts`、`src/components/{ActivityBar,ColumnResizer,OutlineView}.tsx`、`src/monaco-contrib.d.ts`。

---

## 7. 手動 GUI 驗收清單（交付給使用者）

### 範例檔位置

`harness/plans/2026-11-26-document-outline-sidebar/evidence/D8-S3/fixtures/`（請複製到你的測試專案資料夾後於桌面 GUI 開啟）：

1. `01-multilevel-paper.md` — 多層章節 Markdown 論文（含 YAML、ATX/Setext、排除項、文末兩行 Conclusion）
2. `02-multilevel-paper.tex` — 多層章節 LaTeX 論文（含 7 級指令、`*`、`[短]{完整}`、跨行／巢狀大括號、數學、排除項、四種引用位置與文末兩行 Conclusion）
3. `03-bilingual-cjk-english.md` — 中英混合與超長標題、emoji
4. `04-long-many-sections.md` — 60 個章節的長文件（獨立捲動與打字流暢度）
5. `05-duplicate-headings.md` — 同名兄弟章節（重複 `Results`／`Setup`）
6. `06-no-headings.md` — 沒有合法標題的文件（僅有排除語法）
7. `07-in-progress-incomplete.md` 與 `07b-in-progress-incomplete.tex` — 編輯中未完成語法

### 逐項驗收步驟

- [ ] **1. 初始畫面**：啟動桌面 app 後左側是展開的對話管理，內容與先前相同；最左側出現圖示列（Conversations／Outline）。
- [ ] **2. 開檔自動切換**：開啟 `01-multilevel-paper.md`，側欄自動換成大綱且層級正確（無 YAML／程式碼／註解／引用／清單中的假標題）；改開 `02-multilevel-paper.tex`，大綱立即換成 LaTeX 章節，絕無前一份文件殘留。
- [ ] **3. 圖示切換與收合**：點圖示列切換兩種檢視；點目前已選圖示收合側欄、再點展開；收合時開啟另一份文件，確認圖示切到 Outline 但側欄維持收合（A4）。確認展開時雙檢視皆看得到品牌與 Backend 狀態及 Start／Restart／Shut down；收合時它們隨側欄隱藏（U6），主區佔滿寬度且無空欄。
- [ ] **4. 點選跳轉與文末穩定**：點各章節確認游標移到該標題行、焦點在編輯器、不出現 `Add comment`、有空間時標題靠近頂端。於 `01-multilevel-paper.md` 與 `02-multilevel-paper.tex` 點文末只有兩行的 **Conclusion**，確認游標抵達、標題可見，停止捲動後大綱仍持續標出 Conclusion 而不跳回前一章。
- [ ] **5. 目前章節追蹤與收合祖先**：在編輯器捲動與移動游標時，大綱正確標出最內層章節；收合某父節點後移動至其子節點內文，確認該收合父節點出現不同的祖先標示（且不自動展開）。檢查 `03-bilingual-cjk-english.md` 的超長標題以省略號截斷並有完整 `title` 提示。
- [ ] **6. 即時更新與來源覆蓋**：在編輯器新增、刪除、改名、改層級、貼上大段內容，確認大綱即時更新且未受影響的收合狀態保留；測試 `Ctrl+Z`／`Ctrl+Shift+Z` Undo／Redo、讓 Agent 修改文件、觸發並處理版本衝突後大綱皆與最新內容一致。開啟 `06-no-headings.md` 確認顯示 `No headings found`；開啟 `07-in-progress-incomplete.md`／`07b-in-progress-incomplete.tex` 確認前面章節照常顯示；用 `05-duplicate-headings.md` 確認同名章節各自可跳轉與獨立展開收合。
- [ ] **7. 無副作用**：跳轉、捲動、收合大綱後，確認 Undo 歷史仍在、文件不會變成未存檔（除非有編輯）、不會觸發存檔或 Agent 回合。
- [ ] **8. 欄寬拖曳、鍵盤與記憶**：左右拖曳「側欄｜主區」與「文件｜對話」兩條邊界，確認 Monaco 跟著重排、拖曳過程不誤選文字；雙擊邊界恢復預設；重新拖曳後重開 app 確認寬度保留；Tab 聚焦邊界後以左右鍵／Home／End 調整正常、Enter 不動作。
- [ ] **9. 斷點與視窗夾限**：視窗縮到約 `1000 px` 與 `740 px`：前者只剩側欄邊界、後者兩條邊界皆隱藏且橫向圖示列／側欄／主區由上到下排成單欄；在 `740 px` 收合再展開確認無空欄、重疊或水平捲軸。全螢幕把側欄與文件欄拉到最寬，再縮小視窗至約 `1060 px` 與 `900 px`，確認無水平捲軸且文件與對話欄皆可見，放回全螢幕後恢復原本拉寬的寬度。
- [ ] **10. LaTeX 高亮與引用補全清單（G7、G11）**：開啟 `02-multilevel-paper.tex` 確認指令、章節、環境、註解、數學、引用、交叉引用與括號有顏色區分。在已載入 `references.json` 的專案中，於 `.tex` 依序輸入 `\cite{`、`\citep{`、`\citet{`、`\textcite{`，每次皆確認書目鍵清單出現 → 按 `Esc` 關閉 → 續打鍵值開頭確認清單再次出現；於 `.md` 輸入 `[@` 確認清單出現、`Esc` 後續打重現、`Ctrl+Space` 手動叫出；於 `.md` 與 `.tex` 打一般論文文字確認不跳出任何字詞建議。
- [ ] **11. 大綱鍵盤操作與輸入法（G8）**：Tab 進入大綱樹，驗證 `↑`/`↓`、`←`/`→`、`Home`/`End`、`Enter` 皆符合預期且有清楚的焦點外框；切到對話 Composer 以中文輸入法組字按 Enter，確認不受影響。
- [ ] **12. 長文件與既有功能回歸**：開啟 `04-long-many-sections.md` 驗證大綱獨立捲動與編輯打字流暢不卡頓；驗證 Citations 面板、段落引用、批註、核准對話框與存檔一切照常。
