# R2 拆除 Insert、限縮 Remove、移除 BibTeX 匯出

- **後置條件**：
  - 面板上沒有任何插入引用的按鈕。
  - Remove 只出現在未引用區，按下時一律先確認。
  - BibTeX 匯出已從前端、協定、後端、測試全部移除。
  - `.tex` 文件不顯示 Export。
- **涵蓋**：G1、G2、G3。決策 D1、D2、D3；假設 A8。
- **相依**：R1。
- **範圍外**：Export 選單的改造（R4）、收合（R5）。這一階段結束時，Markdown 文件仍然有 Word 與 Markdown 兩個獨立按鈕；R4 才把它們合併。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| R2-S1 | **拆除 Insert**。<br>1. `CitationPanel.tsx`：刪除 `insert` callback、`EntryButtons` 中的 Insert，以及新增成功訊息中的「Insert at cursor」。<br>2. 刪除 `cursorOffset` prop。<br>3. `App.tsx`：刪除 `editorCursorRef`，以及傳給 `DocumentEditor` 的 `onCursor`。<br>4. 確認 `DocumentEditor` 的 `onCursor` 是否還有其他使用者；沒有就一併刪除。<br>5. `citations.ts`：刪除 `citationInsertion`、`insertIntoSnapshot`，以及因此不再使用的型別，並刪除 `citations.test.ts` 中對應的測試。<br>6. **保留** `DocumentEditor` 的 key 補全，和 `citationFormatForPath`。 | `grep -rn "citationInsertion\|insertIntoSnapshot\|cursorOffset\|Insert at cursor\|editorCursorRef" app/desktop/src app/desktop/tests` 沒有結果；補全的既有測試仍然通過；`npm test` 與 `npm run build` 通過 |
| R2-S2 | **限縮 Remove**。<br>1. `CitedRow` 不再顯示任何條目按鈕，只保留 Line 跳轉。<br>2. 未引用區每筆顯示 Remove。<br>3. 修改 `removeConfirmation`，讓它一律回傳確認文字。文字必須說明會從書目檔刪除哪一個 key，並註明「其他文件不會檢查」（A8）。<br>4. 使用者取消時不送出 `bibliography.remove`。 | `desktop/tests` 新增或修改測試：確認文字包含 key 與「其他文件不檢查」的說明；面板模型中，本文引用的列沒有刪除動作（以純函式或模型測試）；`npm test` 與 `npm run build` 通過 |
| R2-S3 | **移除 BibTeX 匯出**。<br>1. `contract.json` 兩處 `format` enum 改成 `["docx","markdown"]`，並更新 `fixtures.json`。<br>2. `service.py`：刪除 `_bibliography_export` 的 `bib` 分支，以及只為 bib 存在的「不需要文件」路徑；修改 `_markdown_snapshot` 的錯誤訊息，刪除「Export the bibliography as .bib instead」。<br>3. `csl_render.py`：刪除 `export_bib`、`EXPORT_SUFFIXES["bib"]`，以及 `export_target` 的 bib 分支。<br>4. 前端：`ExportFormat` 刪除 `bib`；`exportFormats` 對 LaTeX 和 `null` 回傳 `[]`；清單為空時不顯示任何 Export 元素。<br>5. 修改相關測試：`test_desktop_bibliography.py`、`test_citation_csl_render.py`、`test_desktop_protocol_contract.py`、`citation_preview.test.ts`、`protocol.test.ts`。<br>6. 不刪除其他功能仍在使用的 BibTeX 程式碼：bundle 的 `reference.bib`、`bibtex_canonical.py`、`authority.export_bibtex` 和 pybtex 依賴。 | 新增負面測試：`bibliography.export` 帶 `format: "bib"` 時被協定驗證拒絕（`PROTOCOL_INVALID`），也不會寫出檔案；`.tex` 文件的 `bibliography.inspect` 結果和改版前相同；`grep -rn "export_bib\|\"bib\"" app/agent app/skills app/desktop/src app/desktop/protocol` 沒有結果；指定的 pytest 通過；`npm test` 與 `npm run build` 通過；因為契約被 `protocol.rs` 使用，**在沙箱外執行 `cargo test --locked`** 必須通過 |

每個步驟各自 commit，例如 `refactor(desktop): remove the citation Insert control [R2-S1]`。

## 失敗與恢復

- 如果 `onCursor` 或 `insertIntoSnapshot` 其實還有其他使用者，就保留它們，只刪除面板中的使用，並在 build-log 記錄原因。
- 如果 cargo 因為契約修改而失敗，修改 Rust 端對 enum 的固定值或測試資料；不得用跳過測試的方式處理。

## 交付給後續階段

`ExportFormat` 只剩 `docx` 與 `markdown`，契約 enum 也一樣。R4 會在這個基礎上加入 `bime_docx`。
