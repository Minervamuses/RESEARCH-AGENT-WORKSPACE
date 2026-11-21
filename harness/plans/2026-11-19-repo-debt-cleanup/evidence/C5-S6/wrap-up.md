# C5-S6 測試整理與收尾、C5 驗收

- **日期**：2026-11-22

## 1. S121

只刪除因 U4 或 U13 而失效的 citation 測試，逐項記在 `evidence/C5-S3/single-store.md` §6（bundle 儲存、BibTeX 鏈、v1 identity、`RenderedTurn` 與 S108 的測試專用 API）。稽核 S121 列出的其他重疊（workflow tool／save isolation、三個啟用 contract 模組、e2e 與 doi-first-save 的同一流程）不在範圍內，未處理。

## 2. 完整檢查（最後程式狀態）

| 檢查 | 結果 |
|---|---|
| `pytest`（`app/`，沙箱外） | 1762 passed, 2 warnings in 53.72 s |
| `npm test` | 224 pass, 0 fail |
| `npm run build` | 通過 |
| `cargo test --locked`（沙箱外，contract 已改） | 35 passed |
| repo 根目錄 `cite/` 的檔案清單（C5-S3 執行前後與本步） | 未改變 |

## 3. citation 評估分界 commit

**`9068f87`**（`refactor(citation): keep verified works only in the project bibliography and report saves truthfully [C5-S3]`）。C5-S2 只新增不依賴 BibTeX 的測試，沒有改變驗證結果。分界兩側的差異見決策紀錄 §6.2 與 §10：失去 `bibtex_lookup_*`、`bibtex_doi_mismatch`、`authority_bibtex_invalid`；`storage_failed` 的 reason 改為書目庫錯誤碼；registry 衝突為 `identity_conflict`；CLI 成功狀態為 `verified`；計數多 `verified_count`；provenance 不含 `bibtex`；`SKILL.md` 與工具文字改變（C5-S4 起）。

## 4. 選擇性冒煙測試（免費 provider）

在 `$TMPDIR/c5s6-smoke/references.json` 建暫時書目庫，以真實的 `CitationProviderHub` 與 `CitationService` 存 DOI `10.1038/s41586-021-03819-2`（只連 doi.org 的 CSL content negotiation，沒有付費 API、沒有 OpenRouter）：

```
status: saved saved_new
link: BibliographyLink(status='added', path='…/c5s6-smoke/references.json', key='jumper2021highly')
entries: 1 ['10.1038/s41586-021-03819-2'] ['jumper2021highly']
```

## 5. C5 驗收

| 驗收項目 | 證據 |
|---|---|
| 決策紀錄 §4 的每個可觀察結果有測試或 evidence | §4.0 狀態與計數：C5-S3 (a)–(k)；§4.1 桌面（書目庫唯一寫入、核准 target、`bibliography.add`）：(a)、(j)、`test_tool_operations_receive_frozen_single_operation_consent`（無書目庫時 target 不寫入）；§4.2 CLI：(g)、(h)、e2e；§4.3 型別：`test_save_item_status_receipt_and_bibliography_invariants`、schema 3 往返；§4.4：P9 移除與 grep；§4.5：C5-S4。 |
| §5 每個保證在 `guarantee-map.md` 有負責程式 | `evidence/C5-S1/guarantee-map.md` §7；§5.3 的更正見決策紀錄末尾。 |
| grep 都為 0 | C5-S3 evidence §4。 |
| 四套測試通過 | 本檔 §2。 |

## 6. GUI 手動檢查清單（交給 C10 彙整）

- 在專案中以 `/citation` 存檔：書目庫（預設 `references.json`）新增 key，專案或 repo 中不產生 `cite/`。
- 在引用面板以 DOI 加入文獻：核准對話框的目標顯示書目庫路徑。
- 把書目庫設為唯讀後存檔：agent 告知沒有存檔（不可引用），而不是說已存檔。
- runtime 細節不再顯示「Citation output」；session details 不再顯示 citation output 路徑。
