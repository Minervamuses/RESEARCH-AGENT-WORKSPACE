# C5-S1 保證對照與使用者盤點（探索，未改產品程式）

- **日期**：2026-11-22
- **讀碼基準**：HEAD `c76db7b`（C4 完成）。行號以此為準。

## 1. A1：存檔 artifact 是否被持久化

**結論：A1 成立。** `citation_save_batch` artifact、`SaveReceipt`、`CitationSaveMetrics` 都不會寫進對話 JSON 或其他持久化資料。

| 查證點 | 結果 |
|---|---|
| `agent/conversations/models.py`、`repository.py` | 對話只持久化 `ToolActivitySummary`（`call_id`、`name`、`status`、`summary`）。`summary` 由 `agent/session.py::_tool_activity_summaries`（約 452–486 行）只填固定字串「Tool execution completed./failed.」；`ToolMessage.artifact` 與內容都不寫入。`grep -n artifact agent/conversations/*.py` 為 0。 |
| `agent/turns/` | 只有 `safety.py` 的 tool-protocol 文字檢查（與 artifact 無關）。 |
| `agent/observability.py` | `CitationSaveMetrics.to_record()`（約 75–81 行）與 `_tool_result_counts`（約 286–292 行）只寫進 log 行（`citation_save_finalized`、turn trace），不落地成對話資料。 |
| LangGraph checkpointer | `grep -rn "checkpointer\|SqliteSaver\|MemorySaver" agent` 為 0，沒有持久化的訊息歷史。 |
| `app/store/` 現有資料（唯讀） | `grep -rln "citation_save_batch\|bundle_path\|\"artifact\"" app/store` 為 0。 |
| 桌面 transcript 的 tool activity | `service.py` 約 1354 行回 `"arguments": "(not retained)"`、`"result": activity.summary`，沒有 artifact。 |

因此 `SAVE_BATCH_SCHEMA_VERSION` 升為 3 不會讓舊回合無法讀取。

## 2. 決策紀錄 §5.3：BibTeX 拒絕條件的負責程式

以實際呼叫確認（`export_bibtex`／`parse_canonical_bibtex` 對各種輸入的結果，2026-11-22 在 Conda `app` 執行）：

**權威記錄路徑**（`service.py::_persist_item` 中的 `authority.export_bibtex`，其內再 `parse_canonical_bibtex`）

| 條件 | 現行結果 | 移除 BibTeX 後的負責程式 |
|---|---|---|
| 缺標題（`title=""`） | **不拒絕**（產生 `title = ""` 的合法 BibTeX） | 權威 adapter：arXiv `_arxiv` 在 `not title or not authors or not year` 時回 `None`（`authority.py:236`）；NeurIPS `_neurips` 要求頁面標題正規化後等於要求的標題（`authority.py:184`）。 |
| 沒有作者（`authors=()` 或空字串作者） | `IndexError` → `except Exception` → `internal_error`（`verification_internal_error`），不是驗證失敗 | 權威 adapter：arXiv 同上（`not authors`）；NeurIPS 要求 `names` 非空且每個 family 非空（`authority.py:185`）。 |
| 年份缺漏或為 0 | **不拒絕**（寫成 `year = "None"`／`"0"`） | 權威 adapter：arXiv `not year`；NeurIPS 要求 `citation_publication_date` 的年份等於要求的年份（`authority.py:184`）。 |
| 缺 venue（NeurIPS） | 不拒絕 | NeurIPS adapter 要求 `venue` 非空（`authority.py:186`）。 |
| 標題或作者含不成對的大括號、作者姓名逗號過多 | pybtex 拋出 `BibTeXError`／`InvalidNameString` → `internal_error` | **BibTeX 語法限制，不是記錄完整性要求**；CSL-JSON 原樣保存字串，`library.merge` 不需要這個限制。隨 BibTeX 消失，不補。 |
| payload 超過 1 MiB | `payload_too_large` | 權威頁面本身已受 `MAX_AUTHORITY_BYTES`（1 MiB）限制（`authority.py` `_get`）。 |

**DOI 記錄路徑**（`service.py::_persist_item` 中的 `doi_org.fetch_bibtex` 加 `parse_canonical_bibtex`）

| 條件 | 現行結果 | 移除 BibTeX 後 |
|---|---|---|
| BibTeX 請求失敗（暫時性或永久） | `provider_failed / bibtex_lookup_<kind>` 或 `verification_failed / bibtex_lookup_failed` | 隨第二次 doi.org 請求一起消失。CSL 請求失敗仍由 resolution 回報（`resolution.py:456`、`:600` 的 `fetch_structured`）。 |
| 空 payload、無法解析、不是恰好一筆、帶 `@preamble`、超過 1 MiB | `verification_failed / parse_failed`、`not_exactly_one_entry`、`nonempty_preamble`、`payload_too_large` | 這些都是 BibTeX payload 自身格式的檢查，隨 BibTeX artifact 消失；不對應 CSL 記錄的欄位要求。 |
| CSL 與 BibTeX 的 DOI 不一致 | `verification_failed / bibtex_doi_mismatch` | **P8：移除**，不補回。 |
| BibTeX 缺標題、作者 | **不拒絕**（`parse_canonical_bibtex` 只抽取欄位） | 現行只把 BibTeX 的 title／authors／year／venue 當作 CSL 缺欄位時的備援值（`service.py:361–364`）。精確 DOI 的 intent 不比較標題（`resolution.py` `evaluate_record` 只在 `not intent.identifiers` 時比對 title／author／year），這個行為在 BibTeX 前後都相同：CSL 與 BibTeX 都缺標題時，今天也存成空標題。 |

**結論**：沒有「無人負責」的欄位要求。決策紀錄 §5.3 舉的「例如缺標題」與程式事實不符：`export_bibtex`／`parse_canonical_bibtex` 不拒絕缺標題的記錄，最低欄位要求其實由權威 adapter 負責。這項更正依 GOALS「限制」追加在決策紀錄末尾（C5-S2 提交）。C5-S2 因此只加測試 (b)、(c)。

## 3. DOI identity 規則（決策紀錄 §5.2）

- `skills/citation/providers/doi_org.py::parse_csl`（83 行起）：`record_doi = canonicalize_doi(payload.get("DOI")) or doi`（93 行），並寫回 `csl["DOI"]`（95 行）。
- `skills/citation/service.py::_persist_item`：`identity = CanonicalIdentity("doi", record.doi)`（358 行）。
- 計劃不改這條規則；C5-S2 的測試 (c) 固定 alias DOI 的現行行為。

## 4. 名稱的讀寫位置

| 名稱 | 位置 |
|---|---|
| `output_dir` | `skills/citation/service.py:49,52,392`；`skills/citation/tool.py:320,333,438`（`format_explain`）；`agent/desktop/service.py:2375,2377`（`bibliography.add` 核准 target）、`2739–2741,2751`（`citation.save` 核准 target） |
| `resolve_output_dir` | 定義在 `skills/citation/storage.py:86`；呼叫：`skills/citation/service.py:52`、`agent/desktop/service.py:831`（diagnostics `citationOutputPath`）、`2375`、`2741`、`3984`（`_protected_roots`）；import：`agent/desktop/service.py:105`、`skills/citation/service.py:33` |
| `citation_output_dir` | `agent/config.py:63`；`agent/desktop/fixture_session.py:545`；`storage.resolve_output_dir` |
| `CITATION_OUTPUT_DIR` | `storage.resolve_output_dir`（環境變數讀取）；測試 |
| `bundle_path` | `skills/citation/types.py`（`SaveReceipt` 欄位、`to_artifact`、`from_artifact`、驗證）；`skills/citation/service.py:400`；測試與 `tests/fixtures/legacy_v1_bundle` |
| `BIB_FILENAME`、`SIDECAR_FILENAME` | 只在 `skills/citation/storage.py:51–52` 與 `tests/test_citation_storage.py` |
| `storage_failed` | `skills/citation/types.py`（`SaveItemStatus`）；`skills/citation/service.py:413`；`SKILL.md`；測試 |
| `registry_conflict` | `skills/citation/service.py:405`（`ValueError` 的預設 reason）；測試 |
| `source_id_for`（隨 `storage.py` 刪除時必須搬家） | `skills/citation/service.py:320,359`；`storage.py:144` 定義（`src-` + `sha256(identity.key)[:12]`，DOI 的 key 就是 DOI 值），測試 |

## 5. 桌面 `citation.save` 核准在 `library_path` 為 `None` 時是否可能觸發（決策紀錄 §4.1）

**走得到。** `agent/desktop/service.py::_project_bibliography_path`（1285 行起）在專案 `RESEARCH.md` 的 `bibliography` metadata 格式錯誤（`CatalogError`）時回 `None`，`CitationSessionPolicy` 就以 `library_path=None` 建 service（`session_policy.py` `service` property）；`_desktop_operation_approval`（約 2731–2754 行）在 `library_path` 為 `None` 時仍會要求 `citation.save` 核准。觸發情境：使用者在支援的單一專案流程中把 metadata 寫錯，然後在 `/citation` 存檔，屬於支援的正常使用。C5-S3 保留這個分支，核准的 target 寫明「不寫入磁碟」（CLI 語意，狀態 `verified`）。`bibliography.add` 走 `_citation_settings()`，必定有書目庫路徑。

## 6. 狀態值、`BibliographyLink` 與計數的使用者（C5-S3 逐一更新）

| 位置 | 用法 |
|---|---|
| `skills/citation/types.py` | `SaveItemStatus`、`SaveReceipt`（含 `bundle_path`）、`BibliographyLink`（`added`／`existing`／`failed`＋`reason_code`）、`SaveItemOutcome` 的 receipt／status 不變量、`SaveBatchOutcome` 與 `SAVE_BATCH_SCHEMA_VERSION = 2` |
| `skills/citation/service.py` | `save`（173 行以 `saved`／`reused` 決定是否進入書目庫）、`_persist_item`、`_link_library` |
| `skills/citation/registry.py` | `register`（同一 source ID 不同 identity 時拋 `ValueError`）、`trusted_receipt`（S108 刪除）、`receipt_is_trusted` |
| `agent/skills/citation/session_policy.py::save_metrics`（110–167 行） | 依 `saved`／`reused`／其他計算 `CitationSaveMetrics`；receipt 必須在 registry 且可引用 |
| `agent/observability.py` | `CitationSaveMetrics`（55–81 行，`to_record` 四個鍵）；`_tool_result_counts`（286–292 行，`save_saved`／`save_reused`） |
| `skills/citation/tool.py` | `TOOL_DESCRIPTION`（提到「doi.org metadata and BibTeX」）、`_format_bibliography_links`（294–317 行，含 "the bundle result above is unchanged"）、`format_explain(output_dir)`（320–334 行）、`explain` action（438 行） |
| `skills/citation/SKILL.md` | 第 3 行 description（verified bundle saving）、145–147、154–157（書目庫失敗不改變 bundle 結果）、169 行（schema-v1 bundles） |
| `agent/desktop/service.py::_bibliography_add`（約 2361–2391 行） | 以 `item.status in {"saved","reused"}` 與 `link.key` 判斷成功，失敗時用 `link.reason_code` |
| 前端 `app/desktop/src/citations.ts`（約 209–234 行） | 只讀 `bibliography.add` 的 wire 結果（`added`／`existing`／`failed`＋`reasonCode`）；wire 不變，不需修改。引用面板不顯示 `/citation` 存檔狀態。 |
| `agent/document_context.py:314,352` | 讀的是文件存檔結果的 `"saved"`（`document.save`），與 citation 無關。 |
| turn trace | `observability._tool_result_counts` 與 `log_citation_save_metrics` |
| 測試 | `test_citation_authority.py`、`test_citation_doi_first_save.py`、`test_citation_e2e.py`、`test_citation_project_library.py`、`test_citation_provider_routing.py`、`test_citation_save_isolation.py`、`test_citation_save_outcomes.py`、`test_citation_storage.py`、`test_citation_types.py`、`test_citation_workflow_tool.py`、`test_citation_bibtex_canonical.py`、`test_turn_finalizer.py`、`test_inline_skills.py`、`test_desktop_bibliography.py` 等，以及 `tests/fixtures/legacy_v1_bundle` |

## 7. 決策紀錄 §5 的保證與負責程式（C5 前後）

| 保證 | 現在的負責程式 | C5 之後 |
|---|---|---|
| 1. 只有成功驗證的存檔可被引用（INV-010） | 搜尋只回 `ProviderRecord`，不登記（`service.search`）；`registry.register` 只在 `_persist_item` 驗證與 bundle 寫入成功後呼叫（`service.py:403`）；`is_citable_source`（`types.py:138`）；聊天的 `[[cite:…]]` 經 `gate.check_citations`（`gate.py:54`）與 `CitationSessionPolicy.finalize_answer`（`session_policy.py:169`） | 同上；登記移到書目庫結果確定之後（桌面）或驗證之後（CLI），桌面另要求已在書目庫（U13）。 |
| 2. DOI identity | `doi_org.parse_csl:93`；`service._persist_item:358` | 不變。 |
| 3. 權威記錄最低欄位 | 權威 adapter（`authority.py:184–186,236`），見第 2 節 | 不變；BibTeX 只帶來語法限制，不是欄位要求。 |
| 4. 書目庫合併規則（INV-032 未改部分） | `library.load` 偵測並保留排版（`LAYOUTS`，`library.py:33,115,135`）、拒絕無法重現的排版；`merge` 不修改既有條目（299 行）；`write_atomic` 寫入前比對 fingerprint、`os.replace`（350–391 行） | 不變。 |
| 5. 同一 identity 不重複加入 | `library.find_existing`（280 行）與 `merge` 的 `existing` | 不變；本批新作品寫入失敗時的 `existing` 判讀依 U13／U20 修正。 |
