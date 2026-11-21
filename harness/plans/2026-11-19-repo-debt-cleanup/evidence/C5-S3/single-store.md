# C5-S3 移除 bundle 與 BibTeX 鏈、改存檔語意、桌面端同步切換（U13、U20、P9、P13）

- **日期**：2026-11-22
- **本步是 citation 評估的分界 commit**（決策紀錄 §6.2）。C5-S2 沒有改變驗證結果。

## 1. 存檔語意（`skills/citation/service.py`）

| 情境 | 狀態／reason | 登記與引用 | 書目庫 |
|---|---|---|---|
| 桌面，新作品，寫入成功 | `saved`／`saved_new` | 登記，可引用 | `BibliographyLink("added", path, key)` |
| 桌面，本批開始前已在書目庫 | `reused`／`reused_existing` | 登記，可引用，用既有 key（不受同批新作品寫入失敗影響，U20） | `("existing", …)` |
| 桌面，同批重複，第一筆寫入成功 | 第二筆 `reused`，共用 key | 登記 | `("existing", …)` |
| 桌面，合併被拒、或本批新作品（含其同批重複）寫入失敗、或書目庫無法讀取 | `storage_failed`／書目庫錯誤碼（`library_conflict`、`library_write_failed`、`library_malformed`…） | **不登記，不可引用**，沒有 receipt | 無 |
| CLI（沒有書目庫；桌面專案的 `bibliography` metadata 格式錯誤時亦同） | `verified`／`verified_not_persisted` | 登記，只在當次 task 可引用 | 無；不寫任何檔案 |
| 同一 source ID 已屬於另一個 identity（P13） | `identity_conflict`／`registry_conflict` | 不登記 | 寫入前就判定，**不寫入書目庫** |
| 書目庫寫入時發生非預期例外 | 參與這次寫入的各筆 `internal_error`／`storage_internal_error`（附 traceback log） | 不登記 | 未寫入 |

順序：所有解析與驗證完成後，先做 P13 檢查，再以一次 `_link_library` 合併並寫入；`_link_library` 以「本批新加入的 key」集合區分「批次前已在磁碟」與「本批剛加入記憶體」，所以寫入失敗時只有後者被報成 `storage_failed`。

型別（`types.py`）：`SaveReceipt.bundle_path` 刪除；`BibliographyLink` 只剩 `added`／`existing` 與必填 key；`SaveItemStatus` 新增 `verified`；不變量：有 receipt ⇔ `saved`／`reused`／`verified`，有書目庫連結 ⇔ `saved`／`reused`；artifact 的 `bibliography` 鍵一律存在（值可為 null）；`SAVE_BATCH_SCHEMA_VERSION = 3`。`source_id_for` 以相同公式從 `storage.py` 搬到 `types.py`（`src-` + `sha256(identity.key)[:12]`，測試釘住既有值）。v1 bundle 專用的 `identity_verified` 等級、`SourceRef.schema_version` 與 `to_persisted_dict`、`source_identity` 一併刪除（grep 確認只有 bundle 與測試使用）。

計數：`CitationSaveMetrics` 新增 `verified_count`（`to_record` 多一個鍵）；`new_saved_count` 只算 `saved`；turn trace 的 `_tool_result_counts` 新增 `save_verified`。

工具結果（`tool.py`）：JSON 之後附上每筆的白話說明。`storage_failed`：「NOT saved and not citable in this task (<reason>)… Tell the user nothing was saved; the save can be retried.」並列出書目庫路徑（有連結時）；`verified`：「verified and citable in this conversation only; nothing was written to disk (no project bibliography)」。`TOOL_DESCRIPTION` 與 `format_explain` 不再提到 BibTeX 與 bundle，`explain` 改說明書目庫或「不寫入磁碟」。

## 2. 桌面端（`agent/desktop/service.py` 等）

- `citation.save` 核准的 target 改為書目庫路徑；`library_path` 為 `None`（C5-S1 第 5 題：metadata 格式錯誤時走得到）時 target 是 `(not written to disk)`，說明寫明不寫入磁碟。`bibliography.add` 的核准 target 同為書目庫路徑。
- `bibliography.add`：`saved`→`added`、`reused`→`existing` 回傳 key；其他狀態回報 `failed` 並附 reason（`storage_failed` 是書目庫錯誤碼）。wire 不變。
- `runtime.diagnostics` 移除 `citationOutputPath`（contract、Python、TS DTO、`BoundedRuntimeDiagnostics`、fixtures、`App.tsx` 的「Citation output」列與 session details 中的一段；`cataloged`／`transient` 文字留給 C6）。
- `_protected_roots` 不再包含輸出目錄；移除 `skills.citation.storage` import 與全部 `resolve_output_dir` 呼叫。
- `AgentConfig.citation_output_dir` 刪除；`fixture_session.py` 與 `scripts/grill_eval.py` 同步。`CitationSessionPolicy` 不再需要 `config` 參數。
- **S029**：`bibliography.inspect` 改用 `integrity.inspect` 讀到的同一份書目的 fingerprint（不再重讀一次）；`styles.json` 由 S118 的快取只解析一次。`bibliography.add` 在存檔寫入後讀一次 fingerprint 是取得寫入後的值所必需，保留。三處書目路徑解析位於不同 handler（`_project_bibliography_path`、`_desktop_bibliography_lookup`、`_unknown_new_citation_keys`），錯誤處理各不相同，不屬於「同一 handler 內」的重複，未合併。

## 3. 刪除與順帶處理

- 刪除 `skills/citation/storage.py`（399 行）、`bibtex_canonical.py`（169 行）、`authority.export_bibtex` 與 pybtex import、`DoiOrgClient.fetch_bibtex`、`BIBTEX_ACCEPT`、`DoiOrgClient.fetch_registration_agency` 與 `RA_URL`、`types.py` 的 bundle schema 常數；`tests/fixtures/legacy_v1_bundle`、`test_citation_storage.py`、`test_citation_bibtex_canonical.py`。
- provenance：`fresh-resolution+doi.org-csl+bibtex` → `fresh-resolution+doi.org-csl`。`skills/citation/__init__.py` docstring 改寫。
- **S108**：刪除 `csl_render.style_path`、`library.DEFAULT_LIBRARY_FILENAME`、`library.add_item`（測試改用 load → merge → `write_atomic` 的正式步驟）、`SourceRegistry.trusted_receipt`、`ProviderState.from_dict`、`PublishedDateFilter.within_years`、`DoiOrgClient.fetch_registration_agency`。
- **S110**：`render_citations` 直接回傳文字，刪除 `RenderedTurn`（含 `cited_sources`）；`format_bibliography_entry` 改為模組內私有 `_bibliography_entry`。
- **S118**：`csl_render.render`／`export_markdown`／`export_docx` 只載入書目一次（`_citeproc_ast` 接收已載入的 `Library`）；`styles.json` 以 `functools.lru_cache` 只解析一次。
- **S119**：`user_agent` 搬到 `providers/net.py` 由 Crossref 與 DataCite 共用；arXiv ID 樣式 `ARXIV_ID` 放在 `normalize.py` 由 `library.py` 與 `resolution.py` 共用；renderer 改用 gate 的 `mask_unscanned_regions`，與 gate 遮蔽完全相同的 code 區域，刪除自己的 regex。
- **S120**：hub 的 `_fetch` 改為公開的 `fetch`（`AuthorityRegistry(fetcher=hub.fetch)`），三處 inline `ProviderError` import 移到檔頭。
- **缺陷 #6**：`DoiOrgClient._encoded` 的回傳型別標註改為 `tuple[str, str]`。

規模：`service.py` 523 → 485、`types.py` 381 → 334、`authority.py` 265 → 238、`doi_org.py` 197 → 163、`render.py` 107 → 96、`tool.py` 446 → 456（新增說明文字）、`registry.py` 76 → 78（新增 `conflicts`）；`storage.py`、`bibtex_canonical.py` 刪除。

## 4. 必要檢查

| 檢查 | 結果 |
|---|---|
| `pytest --collect-only -q`（`app/`） | 1762 tests collected，0 錯誤 |
| `pytest tests/test_citation_*.py` | 509 passed（新增測試前）；新增後全部通過 |
| 完整 `pytest`（沙箱外） | 1762 passed |
| `grep -rnw --include=*.py` 於 `app/agent`、`app/skills`、`app/tests`：`write_identity_bundle`、`StorageError`、`identity_bundle_dir_name`、`validate_identity_bundle`、`BIB_FILENAME`、`SIDECAR_FILENAME`、`doi_hash`、`identity_hash`、`resolve_output_dir`、`BundleResult`、`bundle_path`、`fetch_bibtex`、`export_bibtex`、`bibtex_canonical`、`citation_output_dir`、`CITATION_OUTPUT_DIR`、`pybtex` | 全部 0（`agent/extensions/startup.py` 的 `_installed_bundle_path` 不是整字相符，與 citation 無關） |
| `grep -n "citation.storage\|resolve_output_dir" app/agent/desktop/service.py` | 0 |
| `npm test`（含 DTO 一致性檢查）、`npm run build` | 224 pass、通過 |
| repo 根目錄 `cite/` 在完整 pytest 前後的檔案清單（路徑、大小、mtime） | 完全相同 |

存檔語意測試 (a)–(k)：

| 規格 | 測試 |
|---|---|
| (a) 桌面只改寫書目庫 | `test_citation_project_library.py::test_desktop_save_rewrites_only_the_bibliography` |
| (b) 書目庫寫入失敗 | `…::test_bibliography_write_failure_is_storage_failed_and_not_citable`（reason、無 receipt、gate 拒絕、工具文字、`failed_count=1`／`new_saved_count=0`）；`…::test_unreadable_bibliography_is_storage_failed_and_not_citable`；`test_citation_save_isolation.py::test_bibliography_write_failure_cause_is_logged` |
| (c) 書目庫已有同一作品 | `…::test_existing_work_is_reused_with_its_key_and_citable` |
| (d) 同批重複、寫入成功 | `…::test_duplicate_work_in_one_batch_is_saved_once_then_reused` |
| (e) 同批重複、寫入失敗 | `…::test_duplicate_work_in_a_failed_write_is_never_reported_reused` |
| (f) 一筆合併被拒、一筆正常，只寫一次 | `…::test_one_rejected_merge_does_not_stop_the_other_work_and_writes_once`；`test_citation_authority.py::test_mixed_save_keeps_storage_and_registry_failures_per_item` |
| (g) CLI `verified`、不寫檔、同 task 可渲染、計數 | `…::test_cli_save_is_verified_citable_in_the_task_and_writes_no_file`；`…::test_cli_save_is_verified_and_writes_nothing` |
| (h) CLI 同 task 存兩次 | `…::test_cli_saving_the_same_work_twice_in_one_task_stays_verified` |
| (i) P13 registry 衝突 | `…::test_registry_conflict_is_identity_conflict_and_never_written`；`test_citation_authority.py::test_mixed_save_keeps_storage_and_registry_failures_per_item` |
| (j) 引用面板以 DOI 加入 | `test_desktop_bibliography.py::test_add_uses_citation_save_approval_and_merges`（成功回傳 key、核准 target 是書目庫）；`…::test_add_reports_a_bibliography_write_failure_with_its_reason` |
| (k) U20 混合批次 | `…::test_existing_work_stays_reused_when_a_new_work_in_the_batch_fails_to_write` |

## 5. 產品邊界檢查

- registry 衝突提前檢查（P13）→ 觸發情境：同一 citation task 中，某個 source ID 已登記為另一個 identity（例如 hash 碰撞，或測試注入）→ 支援的正常使用（單一回合內的存檔；這是既有 `registry.register` 拒絕條件提前到寫入前，避免書目庫出現不可引用的條目，不是協調機制）。
- 書目庫寫入的非預期例外轉為 `internal_error` → 觸發情境：使用者在支援的單一專案流程中存檔，寫入時發生權限或磁碟錯誤 → 支援的正常使用（循序存檔失敗必須誠實回報，不可讓整個工具呼叫崩潰）。
- 沒有新增任何鎖、排程或跨專案協調。

## 6. 測試退役紀錄

| 被刪或改寫的測試 | 它保護的行為（或已刪除的細節） | 留下的證據 |
|---|---|---|
| `test_citation_storage.py` 全部 24 個（bundle 目錄名、v1／v2 reader、sidecar 驗證、輸出目錄優先序、workspace root、原子寫入、lock） | bundle 儲存（U4 刪除） | 書目庫的原子寫入、fingerprint、排版保留由 `test_citation_library.py` 保留；source ID 穩定性由 `test_citation_types.py::test_source_ids_are_stable_hashes_of_the_canonical_identity` 保留；`verification_level` 與 identity 形狀由 `test_verification_shapes_require_a_matching_canonical_identity` 保留。 |
| `test_citation_bibtex_canonical.py` 全部 13 個 | pybtex 解析與 BibTeX 正規化（BibTeX 鏈刪除） | C5-S1 確認沒有對應的記錄欄位要求；權威記錄欄位由 adapter 測試保留。 |
| `test_citation_provider_doi_org.py::test_fetch_bibtex_returns_raw_text_with_bibtex_accept`、`test_registration_agency_lookup`、`test_registration_agency_tolerates_garbage` | `fetch_bibtex`（刪除）、`fetch_registration_agency`（S108 刪除） | CSL 取回、快取、404 與錯誤的測試保留。 |
| `test_citation_save_isolation.py::test_bibtex_failures_are_classified`（4 例） | BibTeX 請求與解析失敗的分類（刪除） | CSL 取回失敗的分類 `test_exact_doi_lookup_failures_are_classified`（5 例）保留。 |
| `test_citation_save_isolation.py::test_storage_failure_cause_is_logged` | bundle `StorageError` 的 log | 改寫為 `test_bibliography_write_failure_cause_is_logged`（書目庫錯誤碼與訊息進 log）。 |
| `test_citation_save_isolation.py::test_unexpected_storage_exception_isolated_to_its_item` | 逐筆 bundle 寫入的非預期例外只影響該筆 | 改寫為 `test_unexpected_storage_exception_fails_only_the_items_in_that_write`：一次寫入服務本批各筆，非預期例外讓參與寫入的各筆 `internal_error`，未參與的項目保留自己的結果。 |
| `test_citation_types.py::test_provider_state_round_trip`、`test_relative_date_filter_handles_bounds` | `ProviderState.from_dict`、`PublishedDateFilter.within_years`（S108 刪除） | `test_date_filter_is_fail_closed` 保留。 |
| `test_citation_types.py::test_source_identity_and_verification_shapes`、`test_source_ref_model_and_persistence_have_no_bundle_path` | v1 `identity_verified` 推導與 `to_persisted_dict`（刪除） | 改寫為 `test_verification_shapes_require_a_matching_canonical_identity`。 |
| `test_citation_render.py` 中 `cited_sources` 與 `format_bibliography_entry` 的斷言 | `RenderedTurn.cited_sources`、公開的 entry formatter（S110） | 同名測試改以渲染後文字的 `Sources:` 清單斷言順序與欄位，涵蓋相同情況。 |
| `test_citation_authority.py::test_official_arxiv_record_and_deterministic_bibtex`、NeurIPS 測試中的 `export_bibtex` 斷言 | `export_bibtex`（刪除） | 改為斷言權威記錄本身的欄位；NeurIPS 存檔測試改斷言 registry 中的驗證等級與 provenance、書目庫 key。 |
| `test_citation_authority.py::test_mixed_doi_and_authority_save_preserves_metadata_and_reuses_bundles` 中 sidecar（intent、resolution）斷言 | bundle sidecar 的存檔紀錄（決策紀錄 §6.1：不再落地） | 改寫為 `…_reuses_entries`（桌面）：receipt 欄位、provenance、第二次存檔 `reused` 且書目庫位元組不變。 |
| `test_citation_authority.py::test_mixed_save_keeps_storage_and_registry_failures_per_item` | 逐筆 bundle 寫入失敗與 registry 衝突 | 同名測試改為書目庫合併被拒（`storage_failed`）與 P13 衝突（`identity_conflict`、未寫入書目庫）。 |
| `test_citation_e2e.py` 三個 bundle 名稱的測試與 bundle／sidecar 斷言 | CLI 寫 bundle、跨 task 重用 bundle（U4／U13 改變） | 改名並改為 CLI 語意：`verified`、不寫任何檔案、下一個 task 必須重新存檔（`test_later_citation_requires_a_new_save_in_the_next_task`）；存檔回報場景改以 CSL 失敗製造 `verification_failed`／`provider_failed`。延遲寫入取消測試改用專案書目庫的實際寫入。 |
| `test_citation_project_library.py::test_bibliography_failure_keeps_the_bundle_outcome`、`test_cli_save_has_no_bibliography` | 書目庫失敗仍報 `saved`（U13 推翻）、CLI 的 bundle 存檔 | 改寫為 `test_unreadable_bibliography_is_storage_failed_and_not_citable`、`test_cli_save_is_verified_and_writes_nothing`，並新增 (a)–(k)。 |
| `test_turn_finalizer.py::test_registry_mismatch_affects_telemetry_but_not_model_prose[bundle_path-/forged]` | 偽造 `bundle_path` 欄位（欄位刪除） | 同測試其餘三個偽造欄位保留。 |
