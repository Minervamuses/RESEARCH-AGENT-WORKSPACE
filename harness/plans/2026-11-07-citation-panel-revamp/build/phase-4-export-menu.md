# R4 Export 選單與系上格式 Word 匯出

- **後置條件**：
  - Markdown 文件只有一個 `Export ▾`，選項依序為 Word（一般）、Word（系上格式）、Markdown。
  - 選擇系上格式時，後端以 vendor 的 bime_word 在原稿旁寫出 `<檔名>.bime.docx`，GUI 顯示輸出路徑與稽核摘要。
  - 其他兩種匯出的行為與改版前相同。
- **涵蓋**：G4、G5。決策 D4、D5、D12；假設 A1–A5、A9、A11。
- **相依**：R2（`ExportFormat` 與契約已移除 bib）、R3（依賴與 vendor 已就緒）。

## 介面約定

以下的名稱是提議，執行者可以調整，但要讓三方契約保持一致。

- `bibliography.export` 的 `format` enum 改為 `["docx","bime_docx","markdown"]`。
- 回應保留 `{format, path}`。`bime_docx` 另外回傳 `audit`，內容至少包括：bime_word 稽核摘要中的錯誤數與警告數、`.audit.md` 的路徑，以及 `layoutVerified: false`。
- 協定只允許有界的欄位；字串一律視為不可信。
- 錯誤沿用既有的 `DesktopServiceError` 代碼，例如 `BIBLIOGRAPHY_FAILED`、`PROTOCOL_INVALID`。訊息包含 bime_word 的 stderr，截斷到合理長度。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| R4-S1 | **後端**。<br>1. 修改 `contract.json`、`fixtures.json` 與 `agent/desktop/protocol.py` 的驗證，加入 `bime_docx` 與回應中的 `audit`。<br>2. `bime_docx` 的處理流程如下。<br>&nbsp;&nbsp;a. 必須是有路徑的 Markdown 文件。<br>&nbsp;&nbsp;b. 編輯器文字和磁碟內容不同時，拒絕並提示先存檔（A11）。<br>&nbsp;&nbsp;c. 輸出目標是 `原稿目錄/<stem>.bime.docx`，等於原稿時拒絕。<br>&nbsp;&nbsp;d. 原稿旁有 `bime-<stem>-profile.json` 時傳 `--config`（A2）。<br>&nbsp;&nbsp;e. 一律傳 `--bibliography <專案書目>` 與 `--overwrite`（A4）。<br>&nbsp;&nbsp;f. 透過 `run_local_work` 以子行程執行 `[sys.executable, <vendor>/scripts/bime_word.py, "convert", …]`。工作目錄設為原稿目錄；`PATH` 前面加上 `Path(sys.executable).parent`，讓 bime_word 找得到 Conda 的 Pandoc；設定逾時，例如 180 秒，數值可調整，並記錄在 build-log。<br>&nbsp;&nbsp;g. 依 A3 解讀結束碼；結束碼為 0 或 1 時，解析 stdout 的 JSON。<br>&nbsp;&nbsp;h. vendor 腳本不存在時，回傳清楚的錯誤。<br>3. `bime_docx` 不讀取 `styleId`（A5）。 | 新增 pytest（`tests/test_desktop_bibliography.py` 或同一子系統中的新檔），沒有 Pandoc 時依現有慣例 skip：<br>① 用最小的 Markdown 與 CSL-JSON 夾具實際轉檔，產生 `.bime.docx` 與三份報告，回應中有路徑和稽核摘要<br>② 原稿旁有 `bime-<stem>-profile.json` 時，確實傳了 `--config`<br>③ 編輯器文字和磁碟不同時拒絕，而且不產生檔案<br>④ 未知的 key 讓 bime_word 以結束碼 2 停止時，錯誤訊息包含該 key<br>⑤ 結束碼為 1 時回傳路徑與錯誤數，不視為失敗：可以用替身子行程模擬<br>⑥ LaTeX 文件被拒絕<br>⑦ `docx`、`markdown` 兩種匯出的既有測試不變並通過<br>再執行協定契約的 pytest，以及**沙箱外的 `cargo test --locked`** |
| R4-S2 | **前端選單**。<br>1. 把逐一產生的 Export 按鈕換成一個 `Export ▾`，展開後依 `exportFormats(format)` 列出選項。標籤沿用英文（A9），例如 `Word (.docx)`、`Word – BIME Appendix 17 (bime_word)`，並註明引用格式固定為附件十七、`Markdown (.md)`。<br>2. 選擇後關閉選單；Escape 或點選單外也會關閉。<br>3. `writesDisabled` 或正在處理中時停用。<br>4. 完成訊息：一般匯出顯示路徑；系上格式另外顯示稽核的錯誤數與警告數，以及 `.audit.md` 的路徑，並提醒「版面需在 Word 中更新欄位並人工覆核」。 | `desktop/tests` 測試：Markdown 文件的選項依序是 docx、bime_docx、markdown；LaTeX 和 `null` 沒有選項；系上格式的結果訊息格式化（含錯誤數與報告路徑）；協定測試包含 `bime_docx` 的請求與回應；`npm test` 與 `npm run build` 通過 |
| R4-S3 | **以真實內容做端到端驗證**。以 R3-S3 的 proposal 副本建立一個暫時的桌面專案，或沿用測試夾具的建立方式，透過 `DesktopService.dispatch("bibliography.export", {format: "bime_docx", …})` 匯出。 | 回應的路徑是副本目錄中的 `proposal.bime.docx`；稽核摘要和直接執行 CLI（R3-S3）的結果一致；原稿副本的位元組沒有改變；證據放在 `evidence/R4-S3/`，docx 不提交 |

每個步驟各自 commit。

## 失敗與恢復

- 如果桌面後端的子行程找不到 Pandoc，把搜尋方式改成和 `csl_render` 相同（優先使用 `sys.executable` 旁的 Pandoc），並記錄。
- 如果 bime_word 的 stdout 不是預期的 JSON，回傳錯誤與截斷後的輸出，不要猜測結果。
- 修改後 cargo 失敗時，修正 Rust 端的固定值或夾具，不得跳過。

## 交付給後續階段

`Export ▾` 元件。R5 會把它放進收合後的摘要列。
