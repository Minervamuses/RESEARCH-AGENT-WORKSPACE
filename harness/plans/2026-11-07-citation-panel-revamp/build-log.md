# 執行紀錄

本檔是唯一的狀態來源。撰寫計劃時還沒有執行任何實作。

## 目前狀態

| 階段 | 狀態 | 證據 | 阻塞 | 下一步 |
|---|---|---|---|---|
| R1 | Complete | R1-S1：[evidence/R1-S1/preflight.txt](evidence/R1-S1/preflight.txt)；R1-S2：[evidence/R1-S2/](evidence/R1-S2/) | — | — |
| R2 | Complete | R2-S1：[evidence/R2-S1/](evidence/R2-S1/)；R2-S2：[evidence/R2-S2/](evidence/R2-S2/)；R2-S3：[evidence/R2-S3/](evidence/R2-S3/) | — | — |
| R3 | Complete | R3-S1：[evidence/R3-S1/](evidence/R3-S1/)；R3-S2：[evidence/R3-S2/](evidence/R3-S2/)；R3-S3：[evidence/R3-S3/](evidence/R3-S3/) | — | — |
| R4 | Complete | R4-S1：[evidence/R4-S1/](evidence/R4-S1/)；R4-S2：[evidence/R4-S2/](evidence/R4-S2/)；R4-S3：[evidence/R4-S3/](evidence/R4-S3/)；R4-F1（使用者驗收後修正）：[evidence/R4-F1/](evidence/R4-F1/) | — | — |
| R5 | Complete | R5-S1：[evidence/R5-S1/](evidence/R5-S1/)；R5-S2：[evidence/R5-S2/](evidence/R5-S2/) | — | — |
| R6 | Complete | R6-S1：[evidence/R6-S1/](evidence/R6-S1/)；R6-S2：[evidence/R6-S2/](evidence/R6-S2/) | — | GUI 由使用者驗收（D14） |

局部阻塞依 D15 逐項記錄問題、嘗試次數、受影響步驟與恢復條件；完成證據保留。階段內仍有可執行步驟時為 In progress，所有剩餘步驟均被封鎖時才標為 Blocked。此處仍是唯一的狀態來源。

## 目標證據

R6-S2 時逐項填寫每個目標的代理證據與連結。GUI 依 D14 由使用者本人於交付後驗收；尚未回報不阻塞代理完成，也不得記為已實測。歷史測試、沿用證據與本次觀察分開標示。

| 目標 | 代理自動檢查／程式碼證據（本次觀察，除非另註） | 使用者手動驗收 |
|---|---|---|
| G1 | R2-S1：移除 grep 無結果（R6-S2 再查一次，含 `onCursor`，exit 1）；補全的 `registerCompletionItemProvider`／`completionPrefix` 保留，補全測試通過 | 交由使用者，尚無結果 |
| G2 | R2-S2：`CitedRow` 只有 Line、`UncitedRow` 有 Remove 的 SSR 測試（突變確認）；`removeConfirmation` 文字含 key、書目檔與「other documents were not checked」；取消在送出前 return（程式碼核對） | 交由使用者，尚無結果 |
| G3 | R2-S3：三方協定／共享夾具拒絕 bib 請求與回應；dispatch bib 不寫檔；`export_bib` 不存在；`.tex` 無 Export（`exportFormats` 為空、`ExportMenu` 不渲染）；`.tex` 的 inspect 斷言不變；保留的 BibTeX 功能仍在（R6-S2 [final-static-checks.txt](evidence/R6-S2/final-static-checks.txt)） | 交由使用者，尚無結果 |
| G4 | R4-S2：選項順序與標籤測試、單一 `Export ▾` 的 SSR 測試；docx／markdown 既有匯出測試（檔名、原稿不變）未修改並通過 | 交由使用者，尚無結果 |
| G5 | R3-S3 正負 CLI 試轉；R4-S1 六項後端測試（真實轉檔、profile、未存檔、缺 key、結束碼 1、失敗訊息）與三方 audit 驗證；**R4-S3 真實 proposal 副本端到端通過**（8 項檢查）；R6-S2 確認 a171a62 之後後端、vendor、依賴與協定未改，證據沿用；vendor manifest 仍全部 OK | GUI 中的路徑與稽核摘要顯示：交由使用者，尚無結果 |
| G6 | R5-S1：`nextExpanded` 10 種情況、摘要文字與問題數測試、初始渲染只有摘要列的 SSR 測試 | 交由使用者，尚無結果 |
| G7 | R5-S2：`editorZoom` 5 項測試（含 storage 例外與重開讀回）；`lineHeight: 0` 在 create 與 updateOptions 兩處（`DocumentEditor.tsx:185`、`:328`）；Tauri 縮放熱鍵預設關閉；面板 font-size grep 全部 ≥ .9rem | 交由使用者（含 28px 多行不重疊），尚無結果 |
| G8 | R6-S2 完整套件各一次全部通過：pytest **1756**、npm test **329**、npm run build、cargo **41**（歷史基線 1736／307／41） | 保留功能的 GUI 操作：交由使用者，尚無結果 |
| G9 | R6-S1：README 與 G1–G7 逐條對照、20 個相對連結存在、`git diff --check` 通過 | 不適用：README 由代理核對 |

## 紀錄

### RA0 撰寫計劃（2026-11-07）

- 依 2026-11-07 對話中使用者的決策 D1–D13 撰寫本計劃。D10–D12 是撰寫期間以選擇題確認的。
- 撰寫時觀察的事實記錄在 [PLANS.md](PLANS.md)「基線」一節，包括 HEAD `5aea53c`、zip 的 SHA-256 與 manifest 檢查結果，以及 app 環境缺少 python-docx 與 lxml。
- 撰寫時做的檢查：以 skill 附帶的 `validate_plan.py` 做結構檢查，並自行做一次需求追蹤與新執行者的推演（不是獨立審查）。結果寫在撰寫者給使用者的回覆中。
- 尚未執行任何測試，也還沒有修改任何產品程式碼。


### RA1 依審核與使用者回覆修訂計劃（2026-11-07）

- 使用者要求：「其餘的我同意，你動手改計劃，改完後回報」；GUI 依「這個我不同意，GUI驗收留給我本人操作就好」新增 D14。代理交付不等待本人 GUI 驗收，原有實際行為目標保留。
- 限縮 BibTeX 移除搜尋，保留其他功能的 export_bibtex；統一既有測試失敗不能自動降低完成標準。
- R3-S3 正負試轉使用隔離且可重建的副本，R4 只沿用乾淨正向輸入。R3 的後置條件改為工具就緒與試轉結果交接，G5 的正負案例／真實 proposal 成功條件保留於 R4-S3；不以最小輸入替代。
- 字體縮放加入自動行高與 28px 多行檢查；前期沿用基線、開發中做局部檢查、完整套件留至 R6 各一次；補上兩次聚焦修正／一次昂貴失敗的停止界線。
- 保留原有 G1–G9、R1–R6 與階段依賴圖；plan-index.json 不增加狀態或另一份完成規則。
- 本次只修改計劃，未執行 R1–R6、未修改產品程式碼或依賴、未 commit；上方所有實作階段仍為 Not started。
- 本次驗證：技能的唯讀結構檢查涵蓋 11 檔，0 errors、0 warnings；git diff --check 通過，計劃檔均保持 LF。獨立 reviewer 讀取最新計劃與使用者修訂要求後，未發現新的阻塞或誤導性缺口；未執行產品測試或轉檔。


### RA2 補正三方協定、局部阻塞與行高檢查（2026-11-07）

- 依使用者本輪核對指出的 A、B、C 修訂；D14 的本人 GUI 驗收分工保留，新增 D15 記錄本次採用的局部阻塞規則。
- 已唯讀核對實際程式碼：Rust 參數／回應 enum 與 exact data keys、TypeScript 參數／回應 schema 均須同步修改。R2-S3、R4-S1 明列檔案與三方驗收，包含 bime_docx 的 audit 欄位。
- 本次 D15 取代 RA1「兩次局部修正失敗即停止整次」的規則：只封鎖該問題與相依步驟，獨立工作繼續；昂貴失敗／無改善或沒有可執行的獨立工作時才停止整次。
- R5-S2 在 R2-S1 完成後可先做，不等待 R2-S2／S3，R5-S1 另等 R4-S2；R6 同時依賴 R4、R5 全部完成。同步調整 PLANS、階段檔、PROMPTS、上方下一步與 plan-index.json；不新增階段或平行執行。
- 行高驗收簡化為核對初始化與縮放更新的 lineHeight: 0；實際多行文字是否重疊仍由使用者操作 GUI 驗收。
- 本次只修訂計劃，未修改產品程式碼／依賴、未執行產品測試或轉檔、未 commit；R1–R6 仍為 Not started。

### RA3 定義昂貴嘗試並提交 RA1–RA3（2026-11-07）

- 核對 RA2 時，代理指出「昂貴嘗試」沒有定義。使用者回覆：「昂貴嘗試的定義就是付費API(基本上這邊應該只有openrouter的付費)」，記為 D16，並寫進 PLANS 的問題處理規則與 PROMPTS。
- 結果：本計劃本來就不授權付費 API，所以 D15 的整次停止條件，實際上只剩「沒有可執行的獨立步驟」這一項；完整測試、`poetry add`、編譯仍受兩次修正上限與十分鐘規則約束。
- 補充 RA2 的出處：A–C 是代理在核對時提出的，使用者採用後自行修訂計劃。
- 結構檢查與 `git diff --check` 的結果記錄在這次提交的訊息中。RA1–RA3 的計劃修訂一起本地提交；R1–R6 仍為 Not started。

### R1-S1 唯讀前置核對（2026-11-07，觀察）

證據：[evidence/R1-S1/preflight.txt](evidence/R1-S1/preflight.txt)（指令輸出原文）。

1. 分支：`git branch --show-current` → `GUI`；HEAD `83eb38ecb3e0187ecfea09997eba4eeab0c1a478`（RA3）。PLANS 的基線寫 `5aea53c`，之後只有計劃 commit（05df764、665cabe、83eb38e），沒有產品程式碼變更。
2. 計劃檔：`git ls-files harness/plans/2026-11-07-citation-panel-revamp` 列出 11 檔（含 `build/` 的 6 個 phase 檔），工作樹沒有對應修改，不需補 commit。
3. 與本計劃無關的未追蹤項目，只記錄、不動：`note/20261106/`（使用者的筆記）；根目錄的 `.bash_profile`、`.bashrc`、`.claude/`、`.gitconfig`、`.gitmodules`、`.idea`、`.mcp.json`、`.profile`、`.ripgreprc`、`.vscode`、`.zprofile`、`.zshrc` 是沙箱掛載的 `/dev/null` 字元裝置（`crw-rw-rw- 1,3`，nobody:nogroup），不是使用者檔案，一律不 stage。
4. 程式位置（`grep -n`，行號相對 `app/`）：與 PLANS 基線一致。差異只有行號：`CitationPanel.tsx` Insert callback 第 145 行、成功訊息「Insert at cursor」第 304 行、Export 按鈕第 257 行；`citations.ts` 的 `citationInsertion`／`insertIntoSnapshot` 第 214／219 行、`ExportFormat` 第 272 行、`removeConfirmation` 第 152 行；`App.tsx` `editorCursorRef` 第 1089 行、`onCursor` 第 2833 行、`cursorOffset` 第 2842 行；`DocumentEditor.tsx` `fontSize: 14`／`lineHeight: 23` 第 183–184 行、`onCursor` 第 276 行、補全第 295 行；`styles.css` `.citation-panel` 第 1266 行（`.78rem`）、`.citation-badge` 第 1276 行（`.68rem`）；`desktop/src` 沒有 `localStorage`；`service.py` `_bibliography_export` 第 2372 行、bib 分支第 2389 行、`_markdown_snapshot` 的 `.bib instead` 第 2266 行；`csl_render.py` `EXPORT_SUFFIXES` 第 511 行、`export_bib` 第 529 行、Pandoc 搜尋第 68–71 行；`contract.json` 第 789／1201 行、`fixtures.json` 第 2210／2252 行、`protocol.ts` 第 995／1169 行、`protocol.rs` 第 999／2454–2455 行；`agent/skills/metadata.py:48` 為 `skills_dir.glob("*/SKILL.md")`；README 第 37、100、101、132 行，citation README 第 41、55 行。
5. zip：`sha256sum` = `66052fb91d5f9fbccff4b7eb98c3ea56779ec55192360e1772f8179e26303ab2`，與 PLANS 相同。解壓到 `$TMPDIR/bimezip.UTdf/`，頂層 `bime-word/`、約 512K；`sha256sum -c manifest.sha256` 結束碼 0，39 行全部 OK；`scripts/bime/__init__.py:2` 為 `__version__ = '1.1.5'`；`requirements.txt` 與 PLANS 相同。
6. Conda `app` 工具：Poetry 2.4.1、npm 11.16.0（node v24.18.0）、cargo 1.97.1、pandoc 3.13、Python 3.13.14 都可執行；`import docx`、`import lxml` 都是 `ModuleNotFoundError`，與基線相同（由 R3-S1 處理）。
7. 另記 `/home/minervamuses/論文/`（唯讀）的 HEAD `59e9dc1d5096f5f0b7767a4654ca4753ca88012f` 與 `git status --short`：` M CLAUDE.md`、` M proposal.docx`、` M references.json`、`?? 076aca99-…docx`、`?? RESEARCH.md`、`?? proposal.pdf`。R3-S3 與 R6-S2 以此比對。

結論：所有項目符合，不需修改後續階段檔。

### R1-S2 核對既有測試基線（2026-11-07）

**沿用的歷史基線**（未在本次重跑）：

- 來源：已刪除的 `harness/plans/2026-11-05-citation-management/build-log.md` 的 C8-F4 一節，以 `git show 05df764:harness/plans/2026-11-05-citation-management/build-log.md` 唯讀讀取（第 442–446 行）。
- 當時結果（2026-11-06）：完整 pytest（沙箱外，TMPDIR 等導向 `/tmp/cm-f4.*`）**1736 passed**、exit 0；`npm test` **307/307**；`npm run build` 成功（既有 chunk 大小警告）；`cargo test --locked`（沙箱外）**41 passed**，連跑 5 次全過。
- 程式版本：C8-F4 commit `5aea53c` 只改計劃檔，量測的程式碼即 `8c34c9a`。`git diff --stat 8c34c9a HEAD -- app` 只有 `app/skills/citation/README.md` 一行文件連結（665cabe），所以程式碼與目前 HEAD 相同。
- 環境：同一個 Conda `app`（Python 3.13.14、pandoc 3.13）；當時同樣沒有 python-docx／lxml。
- 可沿用範圍：作為 R2–R5 判斷回歸的比較對象，以及 R6 完整套件的對照數字。限制：這是歷史紀錄，不是本次觀察；R6 必須實際各跑一次，驗收標準是全部通過，不是固定數字。已知既有失敗：無（C8-F3 已修正 Rust 的崩潰判斷競態；記憶中提到兩個 `complete_large_*` 測試在人為 2 倍 CPU 超載下可能變成 Forced，一般執行未見）。

**本次局部檢查（觀察，不冒充完整基線）**：

- `python -m pytest -q -p no:cacheprovider tests/test_desktop_bibliography.py tests/test_citation_csl_render.py tests/test_desktop_protocol_contract.py`（`app`，沙箱內）：**229 passed**、1 個 langgraph 的 PendingDeprecationWarning，exit 0，約 4 秒。輸出：[evidence/R1-S2/pytest-focused.txt](evidence/R1-S2/pytest-focused.txt)。
- `node --test --experimental-strip-types tests/citations.test.ts tests/citation_preview.test.ts tests/protocol.test.ts tests/documents.test.ts`（`app/desktop`，沙箱內）：**222/222 pass**，exit 0，約 4 秒。輸出：[evidence/R1-S2/node-focused.txt](evidence/R1-S2/node-focused.txt)。
- R1 未跑完整 pytest、npm、cargo 套件（依 PLANS，留至 R6 各一次）。

### R2-S1 拆除 Insert（2026-11-07）

- 修改：`CitationPanel.tsx` 刪除 `insert` callback、`EntryButtons` 的 Insert 按鈕、`EntryActions.onInsert`、`cursorOffset` prop，以及新增成功訊息中的「Insert at cursor」；`citations.ts` 刪除 `citationInsertion`、`insertIntoSnapshot`（`SelectableSnapshot` 仍被 `selectUse` 使用，保留）；`App.tsx` 刪除 `editorCursorRef`、傳給 `DocumentEditor` 的 `onCursor` 與傳給面板的 `cursorOffset`；`DocumentEditor.tsx` 的 `onCursor` 沒有其他使用者（`grep -rn onCursor app/desktop/src app/desktop/tests` 只剩它自己），一併刪除 prop、callbacksRef 欄位與 `publishSelection` 中的呼叫。`citations.test.ts` 刪除插入測試，`citationFormatForPath` 的斷言保留並改名為「citation format follows the document type」。
- 保留：`DocumentEditor` 的 `[@`／`; @`／`\cite{` 補全（`completionPrefix`、`completionCandidates`）、`citationFormatForPath`。
- 檢查（觀察）：
  - `grep -rn "citationInsertion\|insertIntoSnapshot\|cursorOffset\|Insert at cursor\|editorCursorRef" app/desktop/src app/desktop/tests` → 無結果，exit 1；另查 `onCursor\|>Insert<` 也是 exit 1。
  - `node --test --experimental-strip-types tests/citations.test.ts tests/documents.test.ts` → 20/20 pass，含兩項補全測試（[evidence/R2-S1/node-focused.txt](evidence/R2-S1/node-focused.txt)）。
  - `npm run build`（`tsc --noEmit && vite build`）→ exit 0，只有既有的 chunk 大小警告（[evidence/R2-S1/npm-build.txt](evidence/R2-S1/npm-build.txt)）。
- 此時 Remove 仍出現在本文引用列（R2-S2 處理）。

### R2-S2 限縮 Remove（2026-11-07）

- 修改：`CitationPanel.tsx` 刪除 `EntryActions`／`EntryButtons`；`CitedRow`（改為 export）只保留 Line 跳轉；新增 export 的 `UncitedRow`，每筆有 Remove，`writesDisabled` 時停用。`remove(key)` 一律先 `window.confirm(removeConfirmation(key, inspect.libraryPath))`，取消就在送出 `bibliography.remove` 之前 return（程式碼核對：`CitationPanel.tsx` 的 `remove` callback）。`citations.ts` 的 `removeConfirmation(key, libraryPath)` 一律回傳文字：「Delete “<key>” from the bibliography file <path>? This document does not cite it, but other documents were not checked and may still cite it.」
- 檢查（觀察）：
  - `citations.test.ts`：確認文字含 key、書目檔路徑與「other documents were not checked」。
  - `citation_preview.test.ts` 新增 SSR 測試（沿用該檔的 Vite `ssrLoadModule`）：`CitedRow` 的 markup 只有一個 `Line 3` 按鈕，沒有 Remove／Insert；`UncitedRow` 有 Remove，disabled 時帶 `disabled=""`。
  - **突變確認**：暫時在 `CitedRow` 加入 Remove 按鈕，新測試失敗（1 fail）；還原後通過，`CitationPanel.tsx` 與 commit 內容相同。
  - `node --test --experimental-strip-types tests/citations.test.ts tests/citation_preview.test.ts` → 17/17 pass（[evidence/R2-S2/node-focused.txt](evidence/R2-S2/node-focused.txt)）；`npm run build` → exit 0（[evidence/R2-S2/npm-build.txt](evidence/R2-S2/npm-build.txt)）。
- 取消後書目不變屬 GUI 行為，列入使用者手動清單；自動證據只有上述程式碼核對。

### R2-S3 移除 BibTeX 匯出（2026-11-07）

- 三方協定：`contract.json` 的 `bibliography.export` 參數與 `resultDataSchemas` 的 `format` enum 改為 `["docx","markdown"]`；`protocol.ts` 參數／回應 schema、`protocol.rs` 參數（`validate_enum(format, "params.format", …)`）與回應（`validate_enum(&data["format"], …)`）同步。`agent/desktop/protocol.py` 直接從 contract 載入，不需另改。`documentContext` 在契約中仍是 `required: false`（未改 `requiredParams`，避免額外的三方變更）；後端對所有格式一律要求文件（`_markdown_snapshot(required=True)`，缺少時 `PROTOCOL_INVALID`「Open a document first.」）。
- 共享夾具：原本有效的 `bibliography-export-bib-request` 改為無效的 `bibliography-export-rejects-bib-request`（帶 Markdown 文件的 bib 請求，`PROTOCOL_INVALID`）；新增有效的 `bibliography-export-markdown-request`；`bibliography-export-rejects-unknown-param` 的 format 改為 docx，讓拒絕原因只剩 `outputPath`。traces 新增 `bibliography-export-docx-trace`、`bibliography-export-markdown-trace`（有效）與 `bibliography-export-rejects-bib-result`（docx 請求配 `format: "bib"` 回應，無效）；Python、TypeScript、Rust 三方都讀同一份 messages／traces。
- 後端：`service.py` `_bibliography_export` 刪除 bib 分支與「不需要文件」的路徑；格式不在 `csl_render.EXPORT_SUFFIXES` 時直接 `PROTOCOL_INVALID`（防禦：協定層之外的呼叫也不會寫檔）；`_markdown_snapshot` 的錯誤訊息刪除「Export the bibliography as .bib instead」。`csl_render.py` 刪除 `export_bib`、`EXPORT_SUFFIXES["bib"]` 與 `export_target` 的 bib 分支；`export_target` 不再需要 `library_path`，`document_path` 改為必填。
- 前端：`ExportFormat = "docx" | "markdown"`；`exportFormats` 對 LaTeX 與 `null` 回傳 `[]`；面板以 `.map` 產生按鈕，所以清單為空時沒有任何 Export 元素（R4 換成選單時沿用「空清單不顯示」）。
- 測試：
  - `test_desktop_bibliography.py`：新增 `test_bibtex_export_is_rejected_without_writing`——三種帶 `format: "bib"` 的 dispatch（無文件、Markdown、`.tex`）都是 `PROTOCOL_INVALID`，目錄內容不變且沒有 `*.bib`；`validate_message` 拒絕 bib 請求、`validate_result_data` 拒絕 bib 回應並接受 markdown。既有匯出測試刪除 bib 部分，`.tex` 的 docx 與 markdown 匯出都被拒絕；`.tex` render 錯誤訊息改為檢查「Markdown documents」且不含 `.bib`；`.tex` 的 `bibliography.inspect`（`documentFormat == "latex"`、`order`）斷言不變並通過。損壞書目的錯誤型別測試改用 markdown 匯出。
  - `test_citation_csl_render.py`：以 `test_export_targets_sit_beside_the_document_and_exclude_bibtex` 取代 pybtex 的 bib 匯出測試（`EXPORT_SUFFIXES` 只有 docx／markdown、沒有 `export_bib`、`export_target("bib")` 拋 KeyError）。
  - `test_desktop_protocol_contract.py`：新增 enum 斷言。`citation_preview.test.ts`：`exportFormats` 的新期望。
- 檢查（觀察）：
  - `pytest tests/test_desktop_bibliography.py tests/test_citation_csl_render.py tests/test_desktop_protocol_contract.py` → **235 passed**，無 skip（Pandoc 存在）（[pytest-focused.txt](evidence/R2-S3/pytest-focused.txt)）。
  - `node --test … citations citation_preview protocol` → **219/219**，含上述 3 個 message 與 3 個 trace 夾具（[node-focused.txt](evidence/R2-S3/node-focused.txt)）。
  - `npm run build` → exit 0（[npm-build.txt](evidence/R2-S3/npm-build.txt)）。
  - Rust `cargo test --locked … protocol::tests`（沙箱外）→ **12 passed**、29 filtered out，exit 0，約 6 秒；含 `shared_message_fixtures`、`shared_ordering_and_correlation_traces` 與由 contract 產生樣本的 `rust_result_data_rules_match_manifest`（[cargo-protocol-tests.txt](evidence/R2-S3/cargo-protocol-tests.txt)）。
  - 限定範圍的 grep（[grep-checks.txt](evidence/R2-S3/grep-checks.txt)）：`grep -nw export_bib service.py csl_render.py` exit 1；contract／protocol.ts／protocol.rs／citations.ts／csl_render.py 沒有 `"bib"`；fixtures 只剩兩個拒絕案例。保留的 BibTeX 功能仍在：`authority.export_bibtex` 及 `skills/citation/service.py:307` 的呼叫、`storage.py` 的 `reference.bib`、`bibtex_canonical`、`pyproject.toml` 的 pybtex。

### R3-S1 加入 python-docx 與 lxml（2026-11-07）

- 執行前：`pyproject.toml` 沒有這兩個依賴；`pyproject.toml` sha256 `775901d5…`、`poetry.lock` `6207f1ab…`；Conda `app` 的 `pip list --format=freeze` 161 個套件（[pip-freeze-before.txt](evidence/R3-S1/pip-freeze-before.txt)）。
- 指令（`app/`）：`PATH=$P/bin:$PATH CONDA_PREFIX=$P CONDA_DEFAULT_ENV=app $P/bin/poetry add "python-docx>=1.2.0,<2.0" "lxml>=5.2,<7.0"`。直接在沙箱外執行：安裝目標是 `$P/lib/python3.13/site-packages`，不在沙箱可寫範圍，沙箱內必然被擋（PLANS 允許此情況在沙箱外執行）。exit 0，約 3 秒：「2 installs, 0 updates, 0 removals」，安裝 lxml 6.1.3、python-docx 1.2.0（[poetry-add.txt](evidence/R3-S1/poetry-add.txt)）。
- 檢查（觀察）：
  - `$P/bin/python -c "import docx, lxml"` 成功：python-docx 1.2.0、lxml 6.1.3（[import-check.txt](evidence/R3-S1/import-check.txt)）。
  - 環境差異只有新增 `lxml==6.1.3`、`python-docx==1.2.0`（[pip-freeze-diff.txt](evidence/R3-S1/pip-freeze-diff.txt)）；其他套件的版本沒有變化。
  - `poetry check` → 「All set!」，exit 0。
  - `git status`：只修改 `app/pyproject.toml`（dependencies 新增兩行）與 `app/poetry.lock`（新增 lxml、python-docx 兩個 package 區塊；唯一刪除的行是 `content-hash`），沒有改到其他鎖定版本；未修改 `env-app.yml`。
  - 引用相關 pytest：`tests/test_citation*.py`（33 個模組）+ `test_desktop_bibliography.py` + `test_desktop_protocol_contract.py` → **772 passed**，exit 0，約 7 秒（[pytest-citation.txt](evidence/R3-S1/pytest-citation.txt)）。

### R3-S2 vendor bime_word 1.1.5（2026-11-07）

- 來源：`/home/minervamuses/論文/bime_word-1.1.5.zip`（唯讀），SHA-256 `66052fb91d5f9fbccff4b7eb98c3ea56779ec55192360e1772f8179e26303ab2`，與 PLANS 相同。解壓到新建的空目錄 `$TMPDIR/bime-vendor.CUbh/`，`sha256sum -c manifest.sha256` 全部 OK（39 筆），40 個檔案（含 manifest），沒有 `__pycache__`／`*.pyc`。
- 以 `cp -a` 把 `bime-word/` 整個複製到 `app/vendor/bime-word/`（目標原本不存在）。
- 檢查（觀察，[vendor-check.txt](evidence/R3-S2/vendor-check.txt)）：
  - 在 `app/vendor/bime-word` 執行 `sha256sum -c manifest.sha256`：39 筆全部 OK，exit 0。
  - `diff -r --exclude=__pycache__ <解壓目錄>/bime-word app/vendor/bime-word`：無差異，exit 0。
  - CRLF：`grep -rlI $'\r'` 無結果，沒有 CRLF 檔；`.gitattributes` 的 `* text=auto eol=lf` 不會改動內容，manifest 不受影響。唯一的二進位檔 `references/source/bime-format-original.docx` 由 git 自動判定為 binary。
  - `git add --dry-run app/vendor/bime-word`：40 個檔案全部列入。vendor 內的 `.gitignore` 只忽略 `__pycache__/`、`*.py[cod]`、`.pytest_cache/`、`.venv/`、`preview/`、`*.audit.json`、`*.audit.md`、`*.bime.json`，原始檔沒有符合這些規則的。
  - `PYTHONDONTWRITEBYTECODE=1 $P/bin/python app/vendor/bime-word/scripts/bime_word.py doctor` → exit 0：python-docx 1.2.0、lxml 6.1.3、pandoc `/home/minervamuses/miniconda3/envs/app/bin/pandoc`（3.13）；`readiness.convert_and_insert: true`（[doctor.txt](evidence/R3-S2/doctor.txt)）。字型 DFKai-SB、MingLiU 以 DejaVu Sans 代替、Times New Roman 以 Liberation Serif 代替；`soffice` 不存在，所以 `png_preview: false`。依計劃只記錄，不安裝字型：只影響在 Word 中的顯示，不影響轉檔。
  - 技能探索：`agent/skills/metadata.py:48` 只掃描 `resolve_skills_dir()`（預設 `app/skills`）下的 `*/SKILL.md`；`agent/` 中沒有任何地方遞迴搜尋 `SKILL.md` 或掃描 `vendor`。以專案的 `discover_skills()` 實際載入：`['_prompt-master', 'academic-paper-writing', 'citation', 'skill-installer']`，沒有 `bime-word`（[skill-discovery.txt](evidence/R3-S2/skill-discovery.txt)）。
  - A10：`pyproject.toml` 的 `packages` 只有 agent、rag、skills，vendor 不進 wheel；`testpaths = ["tests"]`，vendor 內的測試不會被 app 的 pytest 收集。

### R3-S3 以隔離副本試轉（2026-11-07）

- 論文 repo（唯讀）HEAD 固定為 `59e9dc1d5096f5f0b7767a4654ca4753ca88012f`。以 `git -C /home/minervamuses/論文 show 59e9dc1:<檔名>` 讀出 `proposal.md`、`references.json`、`bime-proposal-profile.json`，分別寫入新的暫存根目錄 `$TMPDIR/bime-trial.nWo3/positive/` 與 `negative/`（`/tmp/claude-1000/bime-trial.nWo3/`，不提交）。`proposal.md` 沒有任何圖片（`grep` 無 `![`／`<img`），不需複製圖片。
- 輸入：正向的 `references.json` 是 HEAD 版本，69 筆，含 `yao2023react`（使用者工作樹目前只有 68 筆，本步不依賴它）。負向只刪除 `yao2023react` 這一筆：`json.loads` → 過濾 → `json.dumps(indent=1, ensure_ascii=False)` 加換行；正向檔以同樣方式 dump 後位元組相同，所以兩者差異只有該筆（`diff` 45 行，[negative/references-diff.txt](evidence/R3-S3/negative/references-diff.txt)）。其他兩個輸入相同。各檔 SHA-256 記在 [inputs.txt](evidence/R3-S3/inputs.txt)，R4-S3 可用來核對或從同一 commit 重建。
- 指令：在 repo 根目錄設 `bime_vendor_script="$PWD/app/vendor/bime-word/scripts/bime_word.py"`，分別以 `positive/`、`negative/` 為工作目錄執行 `PYTHONDONTWRITEBYTECODE=1 PATH=$P/bin:$PATH $P/bin/python "$bime_vendor_script" convert proposal.md -o proposal.bime.docx --config bime-proposal-profile.json --bibliography references.json --scope fragment`。執行前兩處都沒有 `proposal.bime.docx`。
- **正向結果（觀察）**：exit **0**，約 1 秒；stderr 空白。stdout JSON：`{"output": "proposal.bime.docx", "language": "zh", "audit": {"error": 0, "warning": 0, "conflict": 0, "unknown": 0, "manual": 11}, "reports": ["proposal.bime.audit.json", "proposal.bime.audit.md"], "operation_report": "proposal.bime.bime.json", "layout_verified": false}`。產生 `proposal.bime.docx` 與三份報告 `proposal.bime.audit.json`、`proposal.bime.audit.md`、`proposal.bime.bime.json`（報告與 stdout／stderr／exit 存於 [evidence/R3-S3/positive/](evidence/R3-S3/positive/)；docx 不提交，SHA-256 與大小記在 inputs.txt）。python-docx 讀取：175 段；封面含「國立臺灣大學生物資源暨農學院生物機電工程學系」「碩士論文」、中文題目「學術寫作研究輔助AI代理系統之設計與評估」與英文題目；最後一個「參考文獻」標題之後有 42 段參考文獻（第一筆 Anthropic 2024，最後一筆 Zhang 2025），含 Yao 的條目（[positive/docx-read.txt](evidence/R3-S3/positive/docx-read.txt)）。
- **負向結果（觀察）**：exit **2**，stdout 空白，stderr：`bime_word: Citation keys not found in the bibliography (nothing is invented): yao2023react`；不是 `Output exists`，也沒有產生 docx 或報告（[evidence/R3-S3/negative/](evidence/R3-S3/negative/)）。
- 兩個案例都達到成功標準，沒有 G5／R4-S3 的未解驗收項目。
- 論文 repo：`git status --short` 與開始前、也與 R1-S1 記錄相同；HEAD 不變。
- **交接給 R4**：vendor 腳本 `app/vendor/bime-word/scripts/bime_word.py`；stdout 欄位 `output`、`language`、`audit.{error,warning,conflict,unknown,manual}`、`reports`（audit.json、audit.md）、`operation_report`、`layout_verified`；報告路徑相對於 `-o` 的位置。R4-S3 從 `positive/` 只複製三個輸入（不含 docx 與報告）；暫存目錄若已消失，就以同一 commit 重建，並用 inputs.txt 的 SHA-256 核對。

### R4-S1 後端與三方協定：`bime_docx`（2026-11-07）

- 協定（三方一致）：
  - `contract.json`：`bibliography.export` 參數與回應的 `format` enum 為 `["docx","bime_docx","markdown"]`；回應新增可選的 `audit` 物件，子欄位 `errors`、`warnings`、`manualChecks`（integer 0–1,000,000）、`reportPath`（string ≤ 8192 bytes）、`layoutVerified`（boolean），全部必填，不允許額外欄位。
  - 條件規則「`audit` 恰好只出現在 `bime_docx`」：契約語法無法表達，三方各自實作——`agent/desktop/protocol.py` `validate_result_data`、`desktop/src/protocol.ts` `validateResultData`、`protocol.rs` `validate_bibliography_result`（`validate_data_keys` 允許 format／path／audit、必填 format／path，再驗 audit 子欄位的型別與界限）。`protocol.ts` 新增 `BIME_AUDIT_SCHEMA`，`RESULT_DATA_SCHEMAS` 仍與 contract 完全相同（既有 deepEqual 測試）。
  - Rust 由 contract 產生樣本的通用測試 `rust_result_data_rules_match_manifest`：樣本含 audit，所以此方法的樣本 format 改為 `bime_docx`；`audit` 缺少時依條件規則應被拒絕，加入與既有 `rangeStartUtf16`／`rangeEndUtf16` 相同形式的例外。
  - 共享夾具：新增有效的 `bibliography-export-bime-docx-request` 與 `bibliography-export-bime-docx-trace`；無效 traces：`…-bime-docx-rejects-missing-audit`、`…-docx-rejects-audit`、`…-bime-docx-rejects-negative-count`、`…-bime-docx-rejects-extra-audit-field`、`…-bime-docx-rejects-string-layout`。R2-S3 的 docx／markdown 夾具不變。
- 後端：
  - 新模組 `agent/desktop/bime_export.py`：`vendor_script()`（`find_app_root()/vendor/bime-word/scripts/bime_word.py`）、`bime_target()`（`<stem>.bime.docx`）、`profile_for()`（`bime-<stem>-profile.json` 存在才用）、`convert_command()`、`run_bime_convert()`。子行程：`[sys.executable, <vendor script>, "convert", <原稿>, "-o", <stem>.bime.docx, (--config <profile>), "--bibliography", <專案書目>, "--scope", "fragment", "--overwrite"]`，工作目錄為原稿目錄，`PATH` 前面加上 `Path(sys.executable).parent`（Conda 的 Pandoc），**逾時 180 秒**（`BIME_TIMEOUT_SECONDS`）。結束碼依 A3：0／1 需解析出 stdout JSON（`audit.error/warning/manual`、`reports` 中的 `.audit.md`、`layout_verified`）並確認 docx 已寫出；1 仍回傳路徑與錯誤數。其他結束碼回傳 stderr（保留最後 1,000 字元）。補充：bime_word 缺少依賴時以 `SystemExit` 的訊息結束，結束碼也是 1、沒有 JSON，因此 0／1 都必須解析成功，否則回傳「unexpected output (exit code N)」與截斷的 stderr／stdout，不猜測結果。逾時、無法啟動、vendor 腳本不存在都有明確訊息。
  - `service.py`：`bime_docx` 走 `_bime_export`，不讀 `styleId`（A5）；必須是 Markdown 文件（沿用 `_markdown_snapshot`，LaTeX 為 `PROTOCOL_INVALID`）；以新的 `DocumentWorkspace.matches_disk(snapshot)`（`documents.py`，讀取磁碟位元組並與編輯器文字比較）確認已存檔，否則 `PROTOCOL_INVALID`「Save the document first (Ctrl+S): the BIME Word export converts the saved file.」（A11）；輸出等於原稿時拒絕；子行程以 `run_local_work` 執行；bime_word 失敗為 `BIBLIOGRAPHY_FAILED`。
- 新增 pytest（`tests/test_desktop_bibliography.py`，真實轉檔標 `needs_pandoc`）：
  - ① `test_bime_export_writes_the_docx_and_reports_beside_the_saved_file`：最小 Markdown＋CSL-JSON 實際轉檔，產生 `.bime.docx` 與三份報告；回應的 audit 與 `.bime.audit.json` 的 summary 相同；docx 內含 Ng；原稿位元組不變；`styleId: "ieee"` 不產生 `.ieee.*`；第二次匯出覆蓋同一路徑（A4）。
  - ② `test_bime_export_passes_the_profile_bibliography_and_overwrite`（替身子行程）：沒有 profile 時沒有 `--config`，有 `bime-稿件-profile.json` 時傳入；`--bibliography <書目>`、`--scope fragment`、`--overwrite`、工作目錄、逾時與 PATH 前綴都核對。
  - ③／⑥ `test_bime_export_refuses_unsaved_text_and_latex`：未存檔的文字與 `.tex` 文件都拒絕，子行程未被呼叫，沒有任何 `*.bime.*`。
  - ④ `test_bime_export_stops_on_a_key_missing_from_the_bibliography`：實際轉檔，結束碼 2 的錯誤訊息含 `ghost1999`，沒有 docx。
  - ⑤ `test_bime_export_with_audit_errors_still_returns_the_file`：替身結束碼 1、errors 2，回傳路徑與完整 audit。
  - 失敗訊息：結束碼 2 的 stderr（未知設定 key）、缺依賴（結束碼 1、無 JSON）、非 JSON（結束碼 0）、逾時、vendor 腳本不存在。
  - ⑦ docx／markdown 的既有匯出測試未修改並通過。`test_desktop_protocol_contract.py` 新增 audit 條件規則的正反案例（含上界 1,000,001、缺 reportPath、非 boolean 的 layoutVerified）。
- 檢查（觀察）：
  - pytest `test_desktop_bibliography.py test_citation_csl_render.py test_desktop_protocol_contract.py test_desktop_document_service.py`：沙箱內 268 passed、1 failed——失敗的是 `test_isolated_desktop_fixture_calls_real_document_coordinator`，原因是沙箱的 `/tmp` 唯讀（`OSError: [Errno 30] … /tmp/research-agent-desktop-phase02-…`，已知的 fixture 限制，見 [pytest-focused-sandbox.txt](evidence/R4-S1/pytest-focused-sandbox.txt)）；因本步修改了 `documents.py`，在沙箱外以 TMPDIR／XDG_CACHE_HOME／AGENT_LOG_DIR 導向新的 `/tmp/r4s1.*` 重跑同一組：**269 passed**，exit 0（[pytest-focused.txt](evidence/R4-S1/pytest-focused.txt)）。
  - `node --test … protocol citations citation_preview` → **226/226**，含新增的 1 個 message 與 6 個 trace 夾具（[node-focused.txt](evidence/R4-S1/node-focused.txt)）。
  - `npm run build` → exit 0（[npm-build.txt](evidence/R4-S1/npm-build.txt)）。
  - Rust `protocol::tests`（沙箱外）→ **12 passed**，exit 0，約 7 秒（[cargo-protocol-tests.txt](evidence/R4-S1/cargo-protocol-tests.txt)）。
- （R4-S2 更正：原句「子行程會產生 `__pycache__`」是推測。觀察結果：本機 shell 設有 `PYTHONDONTWRITEBYTECODE=1`，子行程繼承後沒有產生；在其他環境即使產生，也會被根目錄與 vendor 的 `.gitignore` 忽略，不影響 manifest 檢查。）

### R4-S2 前端 Export 選單（2026-11-07）

- `citations.ts`：`ExportFormat = "docx" | "bime_docx" | "markdown"`；`exportFormats("markdown")` 依序回傳 docx、bime_docx、markdown，LaTeX／`null` 為空。標籤（A9 英文）：`Word (.docx)`、`Word – BIME Appendix 17 (bime_word)`、`Markdown (.md)`；每個選項下方有一行說明，系上格式為「Citation format fixed to Appendix 17; converts the saved file.」（A5、A11）。新增 `BibliographyExportDto`、`BimeAuditDto` 與純函式 `exportSummary()`：一般匯出只有路徑；系上格式另有「bime_word audit: N errors, N warnings, N manual checks.」、報告路徑，以及 `BIME_LAYOUT_REMINDER`（「Open it in Word, update all fields, and review the layout by hand; bime_word does not verify the layout.」）；錯誤數大於 0 時 `hasErrors` 讓訊息改用錯誤樣式（A3：仍顯示路徑，不算失敗）。
- `CitationPanel.tsx`：逐一產生的 Export 按鈕換成 export 的 `ExportMenu`：一個 `Export ▾`（`aria-haspopup="menu"`），清單為空時不渲染任何元素；打開時焦點移到第一個選項；選擇後關閉；Escape 或焦點離開（點選單外）時關閉——沿用 `trust.tsx` `ThinkingControl` 既有的 onBlur／Escape 作法；`writesDisabled` 或處理中（`working !== null`）時停用並關閉。`bime_docx` 請求不送 `styleId`。結果訊息中的路徑以 React 文字節點顯示（既有的安全顯示方式）。
- `styles.css`：選項清單在摘要列的版面流中另起一行（`.citation-export { display: contents }`、`.citation-export-options { order: 1; flex-basis: 100% }`），不用絕對定位：面板是 `overflow: auto`，浮動選單會被裁切，R5 收合成一列後更明顯。說明文字 `.9rem`。
- 測試（`citation_preview.test.ts`）：選項順序與標籤、BIME 說明；`exportSummary` 的一般／系上格式／單複數與 `hasErrors`；SSR：Markdown 只有一個收合的 `Export ▾` 按鈕（`aria-expanded="false"`、未渲染 menu）、停用時帶 `disabled`、LaTeX 渲染為空字串。協定的 bime_docx 請求與回應由 R4-S1 的共享夾具涵蓋（本次 node 執行中通過）。
- 檢查（觀察）：`node --test … citations citation_preview protocol` → **228/228**（[node-focused.txt](evidence/R4-S2/node-focused.txt)）；`npm run build` → exit 0（[npm-build.txt](evidence/R4-S2/npm-build.txt)）。
- 交由使用者 GUI 驗收：選單展開、Escape／點外部關閉、處理中停用、完成訊息的顯示。

### R4-S3 以真實內容做端到端驗證（2026-11-07）

- 前提：R3-S3 正負案例都達到成功標準（見 R3-S3）。
- 輸入：只從 R3-S3 的 `positive/`（`/tmp/claude-1000/bime-trial.nWo3/positive/`，仍存在）複製 `proposal.md`、`references.json`、`bime-proposal-profile.json`，複製前以 [R3-S3/inputs.txt](evidence/R3-S3/inputs.txt) 的 SHA-256 核對；不複製已產生的 docx／報告，不使用 `negative/`。新的暫時桌面專案：`/tmp/claude-1000/bime-e2e.xvcL/project/`（runtime 目錄另外放在 `…/runtime/`，AGENT_LOG_DIR 與 XDG_* 導向 `$TMPDIR/bime-e2e-rt.*`）。
- 程序（[run_e2e.py](evidence/R4-S3/run_e2e.py)，在 `app/` 以 `PYTHONPATH=. $P/bin/python` 執行，沙箱內）：`workspace.select` inspect／initialize → `document.open proposal.md` → `bibliography.inspect`（書目為專案的 `references.json`，69 筆，`missing` 為空）→ `DesktopService.dispatch("bibliography.export", {"documentContext": …, "format": "bime_docx"})`，回應再以 `validate_result_data` 驗證。約 2 秒，exit 0。
- 結果（觀察，[result.json](evidence/R4-S3/result.json)）：
  - 回應：`{"format": "bime_docx", "path": ".../project/proposal.bime.docx", "audit": {"errors": 0, "warnings": 0, "manualChecks": 11, "reportPath": ".../project/proposal.bime.audit.md", "layoutVerified": false}}`。
  - 三份報告 `proposal.bime.audit.json`、`.audit.md`、`.bime.bime.json` 都在新副本目錄中（複製到 [evidence/R4-S3/](evidence/R4-S3/)）；docx 51,180 bytes，不提交，SHA-256 記在 result.json。
  - 稽核摘要 `{"error": 0, "warning": 0, "conflict": 0, "unknown": 0, "manual": 11}`，與 R3-S3 正向 CLI 的 stdout 相同；`.audit.json` 除 `source`／`source_sha256` 與 `bibliography` 路徑外與 R3-S3 相同；`.audit.md` 只有檔案路徑與 docx SHA-256 兩行不同（docx 內含產生時間等，位元組不同屬預期）。
  - 原稿副本 `proposal.md` 的位元組在匯出前後相同。
  - 8 項檢查全部為 true（[stdout.txt](evidence/R4-S3/stdout.txt)）。
- 論文 repo 的 `git status --short` 仍與 R1-S1 相同。
- 結論：G5 的代理端自動驗收（真實 proposal 副本、正負案例）通過；GUI 中的路徑與摘要顯示依 D14 交由使用者確認。

### R5-S1 收合摘要列（2026-11-07）

- 依 PLANS 的正常順序先做 S1（前提 R4-S2 已完成），S2 接著做。
- `citations.ts` 新增純函式：`problemCount(model)`＝未知 key＋重複 DOI＋（書目無法讀取時 1），與 README 對「問題」的定義一致；`panelSummaryText(model)` → 「3 cited · 2 problems」（單數 problem）；`nextExpanded(expanded, event)`（A7）：`{kind: "checked", previousProblems, problems}` 中 `previousProblems === null` 表示開啟後的第一次檢查，此時有問題才展開、否則收合；0→N 展開；其他（N→N、N→M、N→0、0→0）保留目前狀態；`{kind: "preview"}` 一律展開。
- `CitationPanel.tsx`：面板分為摘要列與內容區。摘要列（`<header class="citation-summary">`）依序為 `Citations`、計數、Style、Preview（只限 Markdown）、`Export ▾`、Refresh、展開／收合切換（`aria-expanded`、`aria-controls`）；問題數大於 0 時加上 `has-problems`（紅底、紅框、計數加粗變紅）。內容區（書目路徑、寫入停用說明、Preview、本文引用、Problems、Verify and add、未引用區）只在展開時渲染。`document.path` 改變時重設為收合、`problemsRef = null`；每次 inspect 成功後依 `nextExpanded` 更新；按 Preview 時展開。
  - 規則 6：通知（`notice`）、書目錯誤（`libraryIssue`）、處理中狀態與匯出結果都放在摘要列下方，收合時也看得到；書目錯誤同時計入問題數，所以會標紅並自動展開。
  - 展開後高度上限仍由 `.citation-panel { max-height: 40vh; overflow: auto }` 控制（未改）。
  - 收合狀態不保存（A7）。
- `styles.css`：新增 `.citation-summary`、`.citation-counts`、`.has-problems`、`.citation-toggle` 規則；刪除已無使用者的 `.citation-panel-header`、`.citation-format-row`。新規則的字級都 ≥ .9rem（全面字級調整在 R5-S2）。
- 測試：`citations.test.ts` 新增計數／摘要文字（含書目錯誤）與 `nextExpanded` 的 10 種情況（開啟時有／無問題、新文件從展開重設為收合、0→N、N→N 使用者已收合、N→M、N→0、0→0、Preview）；`citation_preview.test.ts` 新增 SSR：初始渲染只有摘要列，切換鈕 `aria-expanded="false"`、文字「Expand ▾」，沒有 `citation-body` 與「Verify and add」。
- 檢查（觀察）：`node --test … citations citation_preview` → **22/22**（[node-focused.txt](evidence/R5-S1/node-focused.txt)）；`npm run build` → exit 0（[npm-build.txt](evidence/R5-S1/npm-build.txt)）。
- 交由使用者 GUI 驗收：開啟沒有問題的文件時收合、有問題時自動展開與標紅、輸入 `[@notakey` 存檔後標紅並展開、Preview 展開、手動切換。

### R5-S2 字體與縮放（2026-11-07）

- 新模組 `app/desktop/src/editorZoom.ts`（A6）：預設 16、範圍 10–28、每次 ±1；`readEditorFontSize()` 只接受 `localStorage` 中 1–2 位數、範圍內的整數字串，其餘（含 `"16.5"`、`" 20"`、`"1e1"`）回到 16；`getItem` 拋例外或沒有 storage 時回到 16；`writeEditorFontSize()` 的例外被吞掉（只是不記住）；`zoomedFontSize(current, "in"|"out"|"reset")`。鍵名 `research-agent.editorFontSize`。
- `DocumentEditor.tsx`：`monaco.editor.create` 以 `readEditorFontSize()` 初始化 `fontSize`，原本的 `fontSize: 14`、`lineHeight: 23` 改為 `fontSize`、`lineHeight: 0`（第 183、185 行）；新增三個只在編輯器取得焦點時生效的 Monaco action：放大 `CtrlCmd+Equal`、`CtrlCmd+Shift+Equal`、`CtrlCmd+NumpadAdd`，縮小 `CtrlCmd+Minus`、`CtrlCmd+NumpadSubtract`，重設 `CtrlCmd+Digit0`、`CtrlCmd+Numpad0`；觸發時 `instance.updateOptions({ fontSize, lineHeight: 0 })`（第 328 行）並寫入 storage；編輯器釋放時一併 dispose。重開時再從 storage 讀取，所以初始化與縮放都使用自動行高。
- Tauri：`tauri.conf.json` 沒有設定 `zoomHotkeysEnabled`；Cargo.lock 使用的 tauri-utils 2.9.3 預設 `zoom_hotkeys_enabled: false`（`config.rs:2342`），webview 不會自己處理 Ctrl+=／Ctrl+−，不會重複縮放。未改用其他按鍵。
- `styles.css`（面板文字 ≥ .9rem）：`.citation-panel` `.78rem` → `.95rem`（padding 微調）；`.citation-badge` `.68rem` → `.9rem`；`.citation-summary h3` `1rem`；`.citation-export-note` `.9rem`；新增 `.citation-panel select { font: inherit }`（全域的 `font: inherit` 只涵蓋 button、input、textarea，select 原本用瀏覽器預設字級）與 `.citation-panel .document-error { font-size: inherit }`（`.document-error` 全域為 `.75rem`，面板內的通知改為繼承 `.95rem`）。`.link-button`、按鈕、輸入框都是 `font: inherit`。摘要列按鈕與 select 改為 `min-height: 2rem`、較小的 padding，`flex-wrap: wrap` 讓窄視窗換行。grep 結果見 [static-checks.txt](evidence/R5-S2/static-checks.txt)：面板相關的 font-size 只有 .95rem、inherit、1rem、.9rem、.9rem。
- 測試：新 `tests/editorZoom.test.ts`（5 項）：預設值與範圍、有效／無效的儲存值、storage 拋例外、步進／上下限／重設與「重開後讀到縮放後的大小」；另以原始碼核對 `lineHeight: 0` 恰好出現在 create 與 updateOptions 兩處、沒有固定行高或 `fontSize: 14`、三組快捷鍵都已註冊。實際畫面與 28px 多行文字是否重疊不在 Node 測試範圍，列入使用者的 GUI 清單。
- 檢查（觀察）：`node --test … editorZoom documents citations citation_preview` → **35/35**（[node-focused.txt](evidence/R5-S2/node-focused.txt)）；`npm run build` → exit 0（[npm-build.txt](evidence/R5-S2/npm-build.txt)）。

### R6-S1 更新 README（2026-11-07）

- `/README.md`：
  - 環境一節（原第 37 行 web-search-mcp 段落之後）新增 bime_word：來源 `bime_word-1.1.5.zip`、版本 1.1.5、完整 SHA-256、原樣放在 `app/vendor/bime-word/` 且不當成 agent 技能、依賴 python-docx 與 lxml（`pyproject.toml`）與 Pandoc、`doctor` 檢查指令，以及更新方式（新 zip 解壓到空目錄並 `sha256sum -c manifest.sha256`，整個取代後在 vendor 目錄再檢查一次）。
  - 「開啟專案、文件與對話」第 3 點：編輯器 16px、Ctrl+= ／ Ctrl+-（減號）／ Ctrl+0、每次 1px、10–28px、縮放會記住；只在游標位於編輯器時生效。
  - 「引用面板」：預設收合的摘要列與其內容、有問題時標紅、三種自動展開條件與「其他時候維持你的選擇、不保存」、收合時仍顯示的訊息；刪除 Insert；Remove 只在 Not cited 區、一律確認、書目檔共用且其他文件不檢查；面板沒有插入按鈕，保留 `[@` 補全說明。
  - 「格式與匯出」：`Export ▾` 的三個選項與檔名（`<檔名>.<樣式>.docx`、`<檔名>.bime.docx` 加三份報告、`<檔名>.<樣式>.md`），同名覆蓋、原稿不變；系上格式要先存檔、不使用 Style、`bime-<檔名>-profile.json`、專案書目、`fragment`、稽核摘要與「有錯誤仍寫出」、不驗證版面需在 Word 更新欄位、缺 key／設定錯誤時顯示 bime_word 的訊息；`.tex` 沒有匯出。
  - 「附件十七的細節」最後一句補上 Export 選單的對應選項。
  - 輸出位置表的「引用匯出」列：刪除 `<書目檔名>.bib`，加入 `.bime.docx` 與三份報告。
- `app/README.md`：`vendor/` 一列原本只寫 web-search-mcp，補上 `bime-word/`（子行程執行、不進 wheel、不是 agent 技能）。這列與本次改版直接相關且已過時。
- `app/skills/citation/README.md`：第 41 行資料流刪除 `export_bib`；第 55 行刪除 BibTeX 匯出，並註明系上格式 Word 由 `agent/desktop/bime_export.py` 執行 vendor 的 bime_word、不經過 `csl_render`。
- `grep -rn -i "insert\|bibtex\|\.bib\b\|export" README.md app/README.md app/skills/citation/README.md` 剩下的命中：README 第 50 行是 shell 的 `export OPENROUTER_API_KEY`；citation README 第 22、50 行是 bundle 的 canonical BibTeX（保留的功能）；其餘都是本次改寫的內容（[readme-checks.txt](evidence/R6-S1/readme-checks.txt)；該檔以 `cut -c1-220` 截斷長行，有一處中文字被切成亂碼，不影響判讀）。
- **README 與程式行為逐條對照（程式碼核對）**：
  - G1：README 寫「面板沒有插入引用的按鈕」與 `[@`／`; @`／`\cite{` 補全——對應 R2-S1 的移除（grep 無結果）與保留的 `completionPrefix`。
  - G2：「Remove 只出現在 Not cited 區、一律先確認、其他文件不檢查」——對應 `UncitedRow`、`CitedRow` 只有 Line、`removeConfirmation` 的文字。
  - G3：「`.tex` 文件沒有匯出」——對應 `exportFormats("latex") = []`，`ExportMenu` 空清單不渲染；README 不再提 BibTeX 匯出。
  - G4：三個選項的名稱與順序、`<檔名>.<樣式>.docx|md`、同名覆蓋——對應 `EXPORT_LABELS`、`exportFormats`、`csl_render.export_target`、`write_bytes_atomic`。
  - G5：`<檔名>.bime.docx` 與三份報告名稱、先存檔、不用 Style、profile 命名、專案書目、`fragment`、稽核摘要、錯誤仍寫出、失敗顯示 bime_word 訊息——對應 `bime_export.convert_command`／`run_bime_convert`、`service._bime_export`、`exportSummary`／`BIME_LAYOUT_REMINDER`，以及 R4-S3 實測的報告檔名。
  - G6：預設收合、摘要列項目、標紅、自動展開三條件、不保存、收合時仍顯示的訊息——對應 `CitationPanel` 的摘要列、`problemCount`、`nextExpanded`、`document.path` 重設。
  - G7：16px、Ctrl+= ／ Ctrl+- ／ Ctrl+0、1px、10–28px、記住大小、只在編輯器焦點時生效——對應 `editorZoom.ts` 與 `DocumentEditor` 的 Monaco action。README 未另寫面板字級（≥ .9rem 屬視覺調整）。
- 檢查（觀察）：三份 README 的 20 個相對連結全部指向存在的檔案（含新的 `app/vendor/bime-word/README.md`）；`git diff --check` exit 0。

### R6-S2 代理最終驗收與交接（2026-11-07）

- **完整套件（各一次，觀察）**：
  - 完整 pytest（`app/`，沙箱外；TMPDIR／XDG_CACHE_HOME／AGENT_LOG_DIR 導向新的 `/tmp/r6s2-pytest.YaYr/` 子目錄）：**1756 passed**、2 warnings，exit 0，約 65 秒（[pytest-full.txt](evidence/R6-S2/pytest-full.txt)）。基線 1736；新增的 20 項都是本計劃的測試與夾具參數（R2-S3、R4-S1 的 Python 測試與 messages／traces 夾具）。兩個 warning：langgraph 的 PendingDeprecationWarning（R1 已見），以及 `tests/test_skill_runtime.py::test_installer_zip_rejects_unsafe_members_without_extracting` 故意建立重複成員 zip 的 `UserWarning: Duplicate name`——該檔本計劃未修改，與改版無關。
  - `npm test`（`app/desktop`，沙箱內）：**329/329**，0 fail／skip，exit 0，約 7 秒（[npm-test.txt](evidence/R6-S2/npm-test.txt)）。基線 307；新增 `editorZoom.test.ts` 與面板、選單、協定夾具的測試。
  - `npm run build`：exit 0，只有既有的 chunk 大小警告（[npm-build.txt](evidence/R6-S2/npm-build.txt)）。
  - 完整 `cargo test --locked`（沙箱外）：**41 passed**，exit 0（編譯已快取，約 3 秒）（[cargo-test-full.txt](evidence/R6-S2/cargo-test-full.txt)）。與基線 41 相同；協定的新規則由 `protocol::tests` 內既有的共享夾具與 contract 樣本測試涵蓋。
  - 沒有失敗，所以沒有重跑。
- **G1／G3 限定範圍檢查**（[final-static-checks.txt](evidence/R6-S2/final-static-checks.txt)）：Insert／游標管線 grep exit 1；補全保留；`export_bib` exit 1；contract／protocol.ts／protocol.rs／citations.ts／csl_render.py／protocol.py／service.py 都沒有 `"bib"`；fixtures 只剩兩個拒絕案例；export enum 為 `["docx","bime_docx","markdown"]`；`authority.export_bibtex`、其呼叫、`storage.py` 的 `reference.bib`、pybtex 依賴都保留。未恢復全域「bib 零命中」搜尋。
- **R4-S3 證據沿用**：`git diff --stat a171a62 HEAD -- app/agent app/skills app/vendor app/pyproject.toml app/poetry.lock app/desktop/protocol` 只有 `app/skills/citation/README.md`（文件），程式、vendor、依賴、協定與輸入都未改，不重跑真實案例。vendor 的 `sha256sum -c manifest.sha256` 仍全部 OK。
- **論文 repo**：HEAD `59e9dc1…`，`git status --short` 與 R1-S1 相同（` M CLAUDE.md`、` M proposal.docx`、` M references.json`、三個未追蹤檔）。
- **GUI**：依 D14 由使用者本人驗收，清單見下方「最終彙報」；以上都是自動檢查與程式碼核對，沒有任何 GUI 實測。

### 使用者驗收回報（2026-11-07 晚間）

- 使用者已自行還原 `yao2023react`，在 GUI 匯出一次系上格式 Word，並請 Agent 在第 191 行插入一筆引用。
- 代理唯讀核對後回報兩個問題：
  - **匯出的頁碼**：GUI 匯出與論文 repo 已提交的 `proposal.docx` 不同。已提交版是 bime_word 輸出再經兩步人工後處理（論文 commit `7853b51`、`0a42403`）：換入計劃書封面，並把目錄獨立成小寫羅馬數字一節。本文經逐段比對，格式相同。
  - **新引用顯示 unverified**：Agent 新增的 NeurIPS 條目 `vaswani2017attention` 顯示 unverified；同一篇再存一次還會多出一筆 `vaswani2017attentiona`（只在記憶體中重現，沒有寫入）。
- 使用者決定：
  - 封面維持 bime_word 產生的學位論文封面（「轉成論文才是正確的」）。
  - 頁碼「這個要處理」→ R4-F1。
  - 另在 side chat 發現 citation skill 的 NeurIPS「查證」其實只比對一筆寫死的資料，要求真的去查；若官方不支援，就移除支援 NeurIPS 的宣稱 → R7。
- 代理的疏漏：R4-S3 只比對了稽核數字，沒有和使用者提交過的檔案比對，因此沒有發現頁碼差異。

### R4-F1 系上格式匯出：目錄獨立一節、本文從 1 起算（2026-11-07）

- **診斷**：bime_word 1.1.5 的 `fragment` 範圍會把封面之後全部從 1 編頁（`convert.py` 的 cover 分支）。目錄因此與本文同一節，稽核只列為人工項 PAGE_FORMAT「Front matter and body share a section」——這就是第 11 個人工項，先前提交的版本只有 10 個。附件十七 二.4 規定前頁用小寫羅馬數字、本文從 1 起算。
- **修正**：只改 `app/agent/desktop/bime_export.py`，vendor 不動。
  - **`split_front_matter`**：適用條件是 TOC 標題（`BIMETOCTitle`）與第一個 `Heading1` 在同一節。
    - 在 `Heading1` 前插入一個空段落，帶有複製自本文節的 `sectPr`：`pgNumType lowerRoman start=1`，同樣的頁面設定與頁尾。這個段落位於 TOC 欄位之外，在 Word 更新欄位後仍會保留。
    - 本文節設為 `decimal start=1`，並移除該 `Heading1` 的 `pageBreakBefore`。
    - 其他 package part 逐位元組保留，以原子取代寫回並保留檔案權限。
    - 沒有目錄或已經分節的文件不變。
  - **重跑稽核**：分節後執行 `bime_word.py audit <docx> [--config profile] --scope fragment --report <stem>.bime.audit --fail-on none`，覆寫兩份稽核報告，面板數字改用這次的結果。
  - **operation report**：`<stem>.bime.bime.json` 加一筆 `front_matter_section` 決定（含轉檔時的 SHA-256），`output_sha256` 改為最終檔。
  - 失敗（讀不到 docx、稽核非 0 結束、輸出不是 JSON）一律回 `BIBLIOGRAPHY_FAILED` 並顯示訊息。
- **測試**（`app/tests/test_desktop_bibliography.py`）：
  - 真實轉檔含 `{{TOC}}`：節為 `[lowerRoman 1, decimal 1]`；章前是分節段落；稽核沒有 share-a-section；回應數字等於 `.audit.json`；`.audit.md` 與 operation report 的 SHA-256 等於最終檔。
  - 真實轉檔不含目錄時只有一節，也沒有 `front_matter_section`。
  - stand-in 子程序改寫出真正的最小 docx：檢查 convert→audit 兩次呼叫的參數、稽核失敗與非 JSON 的訊息。
  - `split_front_matter` 單元測試：只改 `document.xml`、`pgNumType` 依 schema 排在 `cols` 之前、權限保留、第二次呼叫不變、壞檔回錯誤。
  - 突變（停用分節）使兩項新測試失敗。
  - focused：`test_desktop_bibliography.py` + `test_desktop_protocol_contract.py` 237 passed（[pytest-focused.txt](evidence/R4-F1/pytest-focused.txt)）。
- **真實副本**（[real-copy.txt](evidence/R4-F1/real-copy.txt)）：從論文資料夾唯讀複製目前的 `proposal.md`、`references.json`、profile 到 `$TMPDIR/bimereal/`，以 `run_bime_convert` 匯出。
  - 結果：節結構與已提交的 `proposal.docx` 相同（封面無頁碼 → 目錄 i… → 本文 1…）。
  - 稽核 0／0／10，share-a-section 0 項。
  - `.audit.md` 與 operation report 的 SHA-256 等於最終檔。
  - 與已提交版的段落文字差異只有：封面（使用者決定保留論文封面）；Pandoc 版本造成的兩個樣式名稱（格式相同）；`proposal.md` 新增的 vaswani 引用。
  - 論文資料夾沒有寫入。
- **README**：根目錄 README 的 BIME 匯出段落說明分節與重跑稽核。

## 步驟與 commit

| 步驟 | commit |
|---|---|
| R1-S1 | `483fc46` |
| R1-S2 | `804c212` |
| R2-S1 | `3b366bd` |
| R2-S2 | `de2f8a6` |
| R2-S3 | `c7e645e` |
| R3-S1 | `a91eab6` |
| R3-S2 | `f3b18a4` |
| R3-S3 | `3b94810` |
| R4-S1 | `2442b1d` |
| R4-S2 | `1d3f409`（含 R4-S1 build-log 一句更正） |
| R4-S3 | `a171a62` |
| R5-S1 | `79bfeda` |
| R5-S2 | `a9689e1` |
| R6-S1 | `d4ed203` |
| R6-S2 | `38f7662` |
| R4-F1 | 本 commit（主旨含 `[R4-F1]`） |

R6-S2 之前：沒有 Blocked 項目、沒有修正步驟（F）、沒有 checkpoint commit、沒有任何付費 API 呼叫。使用者驗收後新增 R4-F1 與 R7（見紀錄），同樣沒有付費 API 呼叫。

## 最終彙報

1. **完成的改變**（`483fc46`..R6-S2，全部在 GUI 分支本地，未 push）：拆除 Insert 與游標管線；Remove 只在未引用區且一律確認；BibTeX 匯出從前端、三方協定到後端移除；`Export ▾` 選單（Word、Word – BIME Appendix 17、Markdown）；以 Poetry 加入 python-docx 1.2.0、lxml 6.1.3；vendor bime_word 1.1.5；`bime_docx` 匯出（`<檔名>.bime.docx` 與三份報告、稽核摘要）；面板預設收合成摘要列；編輯器 16px 與可記住的縮放；面板文字 ≥ .9rem；README 更新。測試：pytest 1756（基線 1736）、npm 329（基線 307）、build 成功、cargo 41（基線 41），全部通過。
2. **手動 GUI 檢查清單**（D14，由使用者本人操作；代理沒有實測，以下都尚無結果）：
   - 開啟沒有 Problems 的 `proposal.md` 副本時面板收合；若開啟時已有 Problems，應自動展開並標紅。
   - 展開後本文引用沒有 Insert，也沒有 Remove。
   - 未引用區的 Remove 會先確認，取消後沒有任何變化。
   - `Export ▾` 有三個選項；選擇後選單關閉；Escape 或點選單外會關閉；回合進行中停用。
   - 開啟 `.tex` 文件時沒有 Export。
   - 有未存檔的修改時，系上格式匯出會被拒絕並提示先 Ctrl+S。
   - 匯出後 `proposal.bime.docx` 與三份報告出現在原稿旁，面板顯示路徑、稽核數字、`.audit.md` 路徑與「在 Word 更新欄位並人工覆核」的提醒。
   - 輸入 `[@notakey` 並存檔後，摘要列變紅並自動展開。
   - Ctrl+= ／ Ctrl+- ／ Ctrl+0 能縮放編輯器字體；重開 GUI 後保留縮放的大小；放大至 28px 時，多行中英文不重疊。
   - 面板文字的大小可以接受；窄視窗時摘要列換行正常。
   - 保留的功能都還正常：Style 選單、Preview（會自動展開）、verified／unverified 標籤、Line 跳轉、Verify and add、`[@` 補全。
3. **需要使用者決定或注意的事**：
   - `/home/minervamuses/論文/references.json` 中被誤刪的 `yao2023react` 仍未還原（本計劃不寫入論文資料夾）。還原指令：`git -C /home/minervamuses/論文 checkout -- references.json`。還原前，系上格式匯出會因為這個未知的 key 停止（R3-S3 負向案例即此情況）。
   - 可逆假設 A1–A11 照計劃實作。執行中另做的可逆選擇：audit 欄位為 errors／warnings／manualChecks／reportPath／layoutVerified；「問題數」包含書目無法讀取；問題數 N→M（都大於 0）時不自動展開（A7 字面）；`Export ▾` 的選項在摘要列中另起一行而非浮動選單（避免被面板裁切）；未存檔時的錯誤代碼沿用 `PROTOCOL_INVALID`；bime_word 逾時 180 秒；契約中 `documentContext` 仍是選填，由後端要求。
   - `for_agents/` 可能已過時（面板、協定、vendor、依賴都有變動），需要用 infrastructure skill 更新。
   - 已知既有失敗：無。沙箱內跑 `test_desktop_document_service.py` 的 phase02 fixture 會因 `/tmp` 唯讀失敗（已知限制，沙箱外通過）。
