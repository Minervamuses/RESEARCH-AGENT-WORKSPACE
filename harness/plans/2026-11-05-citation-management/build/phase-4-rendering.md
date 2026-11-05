# C4 渲染引擎與內建樣式

- **後置條件**：四個內建樣式就位；Pandoc 的渲染結果已與 citeproc-js 參考基準比較並留下證據；後端有一個模組能把 Markdown 正文以指定樣式渲染成「逐筆引用 + 參考文獻」，並能匯出 `.docx`、已排版 Markdown 與 `.bib`。
- **目標**：CG4、CG5、CG7。決策 D1、D2、D4；假設 A6、A7、A8。
- **相依**：C1（Pandoc）。

## 介面（擬定）

- `app/skills/citation/styles/`：`.csl` 檔與一份樣式清單（ID、顯示名稱、`numeric` 或 `author-date`、來源與授權）。
- `app/skills/citation/csl_render.py`：
  - `render(text, library_path, style_id) -> Rendered`：每筆引用的渲染字串（依出現順序，附原始 UTF-16 位置）與參考文獻條目（SafeContent 可顯示的 Markdown：只用 `*斜體*`、`**粗體**`、連結）。
  - `export_docx(text, library_path, style_id) -> bytes`、`export_markdown(...) -> str`（引用已轉成文字、參考文獻附在文末）、`export_bib(library_path) -> str`。
  - 只呼叫 Pandoc 子程序：不經 shell、正文由 stdin 傳入、有逾時、優先使用 `--sandbox`；Pandoc 不存在或逾時回傳明確錯誤。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| C4-S1 | **內建樣式**。從 CSL 官方樣式庫（GitHub citation-style-language/styles）下載 `apa.csl`、`modern-language-association.csl`、`ieee.csl`、`chicago-author-date.csl`，保留檔頭的授權（CC BY-SA 3.0）與作者資訊，在樣式清單記錄來源 commit SHA 與下載日期。確認 Poetry 打包會包含這些檔案 | 對同一小份 fixture，四個樣式各自以 Pandoc 渲染成功且輸出彼此不同；`poetry build` 產生的 wheel 內含 `.csl`（檢查後刪除 `dist/` 產物或確認它被忽略） |
| C4-S2 | **比較測試**。在 `$TMPDIR` 建一個獨立目錄，安裝固定版本的 npm 套件 `citeproc`（citeproc-js；記錄版本），寫一支 Node 腳本：讀合成語料、樣式、en-US locale，輸出每個案例的引用字串與參考文獻。語料至少涵蓋：1、2、3、8、21 位作者；同作者同年（2020a/2020b）；同姓不同名；機構作者（literal）；姓氏前綴（van der）；缺年份；頁碼 locator；省略作者（`-@`）；一次引用多篇；數字制的首次出現編號與連續範圍合併（IEEE 的 [1]–[3]）；標題大小寫轉換。以 Pandoc 跑相同語料與樣式，逐案例比較字串。把腳本、`package.json`、`package-lock.json`、語料、兩邊輸出與比較結果提交到 `evidence/C4-S2/`（不提交 node_modules） | 產出 `evidence/C4-S2/summary.md`：每個樣式、每個案例是否一致；不一致者標類別（作者清單/et al.、消歧、排序/編號、locator、大小寫、標點、其他）。判定：「核心類別」= 作者清單/et al.、消歧、排序/編號、locator；記錄 Pandoc 在核心類別的不一致數 |
| C4-S3 | **條件步驟**（僅當 C4-S2 中 Pandoc 在核心類別有不一致時執行；否則在 build-log 記為「未觸發」並 commit）。`poetry add --group dev citeproc-py`（同步更新 `pyproject.toml` 與 `poetry.lock`，D4），以相同語料跑 citeproc-py，記錄結果；然後 `poetry remove --group dev citeproc-py`，讓 manifest 回到原狀。產品仍用 Pandoc（A8）；若 citeproc-py 在 Pandoc 出錯的案例上正確，寫成最終彙報的決策項 | `evidence/C4-S3/` 有 citeproc-py 版本與結果；步驟結束時 `git diff` 顯示 `pyproject.toml`、`poetry.lock` 與步驟前相同；`poetry check` 通過 |
| C4-S4 | **渲染與匯出模組**。實作上述介面。逐筆引用的渲染取自 Pandoc `--citeproc` 後 JSON AST 中 Cite 節點的內容；參考文獻取自 `#refs` 區塊。匯出 docx 用 `--citeproc --csl --bibliography -o`；匯出 Markdown 用 `-t markdown-citations`；`.bib` 用 `-f csljson -t biblatex`。驗證 `--sandbox` 下仍能讀取 `--csl` 與 `--bibliography`，若不行依 PLANS 風險 R4 改用替代作法並記錄 | 測試：同一正文以 APA 與 IEEE 渲染，引用與參考文獻都不同，輸入字串雜湊不變；數字制的參考文獻順序 = 首次出現順序；作者年制依樣式排序；書目缺某 key 時回報缺漏而非崩潰；docx 可被 `zipfile` 開啟且 `word/document.xml` 含渲染後的引用；Markdown 匯出不含 `[@`；`.bib` 能被 pybtex 解析；Pandoc 不在 PATH 時回傳明確錯誤；含遠端圖片連結的正文匯出時不連網（以 `--sandbox` 或替代旗標保證，測試在無網路假設下通過） |

## 失敗與恢復

- citeproc-js 安裝被拒（網路）：C4-S2 改為只記錄 Pandoc 輸出並人工抽查五個核心案例，記為部分完成；C4-S3 不觸發。
- 下載樣式被拒：記為環境阻塞；C4-S4 以 Pandoc 內建的 Chicago author-date 先完成並測試，其他樣式待補。

## 交付給後續階段

樣式清單、`render`/`export_*` 的輸入輸出格式，以及比較測試的結論（C8 最終彙報引用）。
