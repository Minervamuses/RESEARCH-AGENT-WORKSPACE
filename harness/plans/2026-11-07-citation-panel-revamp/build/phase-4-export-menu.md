# R4 Export 選單與系上格式 Word 匯出

- **後置條件**：
  - Markdown 文件只有一個 `Export ▾`，選項依序為 Word（一般）、Word（系上格式）、Markdown。
  - 選擇系上格式時，後端以 vendor 的 bime_word 在原稿旁寫出 `<檔名>.bime.docx`，GUI 顯示輸出路徑與稽核摘要。
  - 其他兩種匯出的行為與改版前相同。
- **涵蓋**：G4、G5。決策 D4、D5、D12；假設 A1–A5、A9、A11。
- **相依**：R2，以及 R3 的工具環境就緒與試轉結果交接。R4-S1／S2 可在真實案例尚有已記錄問題時進行，S2 在 S1 通過後進行；R4-S3 必須先取得 R3-S3 正負案例通過的證據。最小輸入成功不能使 G5 或 R4 整體完成。

## 介面約定

以下的名稱是提議，執行者可以調整，但要讓三方契約保持一致。

- `bibliography.export` 的 `format` enum 改為 `["docx","bime_docx","markdown"]`。
- 回應保留 `{format, path}`。`bime_docx` 另外回傳 `audit`，內容至少包括：bime_word 稽核摘要中的錯誤數與警告數、`.audit.md` 的路徑，以及 `layoutVerified: false`。
- 協定只允許有界的欄位；字串一律視為不可信。Python、TypeScript、Rust 對請求與回應採相同格式清單；bime_docx 回應必須包含 audit，一般 docx／markdown 維持 format、path。三方一起更新回應欄位清單及 audit 子欄位的型別／界限驗證，不以放寬未知欄位來讓結果通過。
- 錯誤沿用既有的 `DesktopServiceError` 代碼，例如 `BIBLIOGRAPHY_FAILED`、`PROTOCOL_INVALID`。訊息包含 bime_word 的 stderr，截斷到合理長度。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| R4-S1 | **後端與三方協定**。<br>1. 修改 `desktop/protocol/v1/contract.json`、`fixtures.json`，核對／調整 `agent/desktop/protocol.py`，並同步修改 `desktop/src/protocol.ts` 與 `desktop/src-tauri/src/protocol.rs`。三方請求／回應的 enum 都加入 `bime_docx`。TypeScript 回應 schema 要加入 `audit`；Rust `bibliography.export` 回應的 `validate_exact_data_keys` 目前只允許 format、path，必須同步加入 bime_docx 的 audit 與其子欄位驗證，不能只改 enum。<br>2. `bime_docx` 的處理流程如下。<br>&nbsp;&nbsp;a. 必須是有路徑的 Markdown 文件。<br>&nbsp;&nbsp;b. 編輯器文字和磁碟內容不同時，拒絕並提示先存檔（A11）。<br>&nbsp;&nbsp;c. 輸出目標是 `原稿目錄/<stem>.bime.docx`，等於原稿時拒絕。<br>&nbsp;&nbsp;d. 原稿旁有 `bime-<stem>-profile.json` 時傳 `--config`（A2）。<br>&nbsp;&nbsp;e. 一律傳 `--bibliography <專案書目>` 與 `--overwrite`（A4）。<br>&nbsp;&nbsp;f. 透過 `run_local_work` 以子行程執行 `[sys.executable, <vendor>/scripts/bime_word.py, "convert", …]`。工作目錄設為原稿目錄；`PATH` 前面加上 `Path(sys.executable).parent`，讓 bime_word 找得到 Conda 的 Pandoc；設定逾時，例如 180 秒，數值可調整，並記錄在 build-log。<br>&nbsp;&nbsp;g. 依 A3 解讀結束碼；結束碼為 0 或 1 時，解析 stdout 的 JSON。<br>&nbsp;&nbsp;h. vendor 腳本不存在時，回傳清楚的錯誤。<br>3. `bime_docx` 不讀取 `styleId`（A5）。 | 新增 pytest（`tests/test_desktop_bibliography.py` 或同一子系統中的新檔），沒有 Pandoc 時依現有慣例 skip：<br>① 用最小的 Markdown 與 CSL-JSON 夾具實際轉檔，產生 `.bime.docx` 與三份報告，回應中有路徑和稽核摘要<br>② 原稿旁有 `bime-<stem>-profile.json` 時，確實傳了 `--config`<br>③ 編輯器文字和磁碟不同時拒絕，而且不產生檔案<br>④ 未知的 key 讓 bime_word 以結束碼 2 停止時，錯誤訊息包含該 key<br>⑤ 結束碼為 1 時回傳路徑與錯誤數，不視為失敗：可以用替身子行程模擬<br>⑥ LaTeX 文件被拒絕<br>⑦ `docx`、`markdown` 兩種匯出的既有測試不變並通過<br>共享夾具與三方驗證須接受 bime_docx 請求及含合法 audit 的對應回應、拒絕缺少 audit 或 audit 格式錯誤的回應，並保持 docx／markdown 舊回應相容；執行協定契約的 pytest、`desktop/tests/protocol.test.ts` 及 **PLANS 的 Rust 協定局部測試 `protocol::tests`** |
| R4-S2 | **前端選單**。<br>1. 把逐一產生的 Export 按鈕換成一個 `Export ▾`，展開後依 `exportFormats(format)` 列出選項。標籤沿用英文（A9），例如 `Word (.docx)`、`Word – BIME Appendix 17 (bime_word)`，並註明引用格式固定為附件十七、`Markdown (.md)`。<br>2. 選擇後關閉選單；Escape 或點選單外也會關閉。<br>3. `writesDisabled` 或正在處理中時停用。<br>4. 完成訊息：一般匯出顯示路徑；系上格式另外顯示稽核的錯誤數與警告數，以及 `.audit.md` 的路徑，並提醒「版面需在 Word 中更新欄位並人工覆核」。 | `desktop/tests` 測試：Markdown 文件的選項依序是 docx、bime_docx、markdown；LaTeX 和 `null` 沒有選項；系上格式的結果訊息格式化（含錯誤數與報告路徑）；協定測試包含 `bime_docx` 的請求與回應；本步相關的前端測試（依 PLANS 選檔）與 `npm run build` 通過 |
| R4-S3 | **以真實內容做端到端驗證**。先確認 R3-S3 正負案例均達成功標準；未達時只在有新證據與次數／成本允許下修正、重跑失敗案例，否則本步保持 Blocked。從 R3-S3 的乾淨 `positive/` 複製輸入（不複製已產生的 docx／報告）到新的暫時桌面專案；不得使用 `negative/`。透過 `DesktopService.dispatch("bibliography.export", {format: "bime_docx", …})` 匯出。 | 回應路徑是新副本目錄中的 `proposal.bime.docx`；三份報告存在，稽核摘要與使用相同輸入的 R3-S3 正向 CLI 結果一致；原稿副本位元組不變。證據放在 `evidence/R4-S3/`，docx 不提交；此步與其他必要自動檢查通過後，才能完成 G5 的代理驗收。GUI 路徑／摘要顯示由使用者依 D14 手動確認 |

每個步驟各自 commit。

## 失敗與恢復

- 如果桌面後端的子行程找不到 Pandoc，把搜尋方式改成和 `csl_render` 相同（優先使用 `sys.executable` 旁的 Pandoc），並記錄。
- 如果 bime_word 的 stdout 不是預期的 JSON，回傳錯誤與截斷後的輸出，不要猜測結果。
- 修改後 cargo 失敗時，修正 Rust 端的固定值或夾具，不得跳過。

## 交付給後續階段

R4-S2 完成並通過局部檢查後，`Export ▾` 元件即可交給 R5-S1 放入摘要列，不必等待 R4-S3 真實案例通過。R4-S3 受阻不撤銷已完成的 S1／S2；R4 整體與 G5 仍須真實案例驗收。
