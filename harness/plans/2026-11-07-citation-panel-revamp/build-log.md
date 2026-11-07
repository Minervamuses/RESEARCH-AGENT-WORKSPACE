# 執行紀錄

本檔是唯一的狀態來源。撰寫計劃時還沒有執行任何實作。

## 目前狀態

| 階段 | 狀態 | 證據 | 阻塞 | 下一步 |
|---|---|---|---|---|
| R1 | Complete | R1-S1：[evidence/R1-S1/preflight.txt](evidence/R1-S1/preflight.txt)；R1-S2：[evidence/R1-S2/](evidence/R1-S2/) | — | — |
| R2 | Complete | R2-S1：[evidence/R2-S1/](evidence/R2-S1/)；R2-S2：[evidence/R2-S2/](evidence/R2-S2/)；R2-S3：[evidence/R2-S3/](evidence/R2-S3/) | — | — |
| R3 | In progress | R3-S1：[evidence/R3-S1/](evidence/R3-S1/) | — | R3-S2 vendor bime_word |
| R4 | Not started | — | — | 等 R2、R3 |
| R5 | Not started | — | — | S2 的前提（R2-S1）已滿足；S1 等 R4-S2 |
| R6 | Not started | — | — | 等 R4、R5 全部完成 |

局部阻塞依 D15 逐項記錄問題、嘗試次數、受影響步驟與恢復條件；完成證據保留。階段內仍有可執行步驟時為 In progress，所有剩餘步驟均被封鎖時才標為 Blocked。此處仍是唯一的狀態來源。

## 目標證據

R6-S2 時逐項填寫每個目標的代理證據與連結。GUI 依 D14 由使用者本人於交付後驗收；尚未回報不阻塞代理完成，也不得記為已實測。歷史測試、沿用證據與本次觀察分開標示。

| 目標 | 代理自動檢查／程式碼證據 | 使用者手動驗收 |
|---|---|---|
| G1–G8 | 尚未執行 | GUI 操作交由使用者，尚無結果 |
| G9 | 尚未執行 | 不適用：README 由代理核對 |

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
