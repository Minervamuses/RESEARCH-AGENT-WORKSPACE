# C5 — Citation 單一儲存（U4、U9）

- **完成後的狀態**：
  - 驗證過的文獻只存在專案書目庫。
  - CLI 不寫檔，但在當次對話中可引用。
  - `cite/` 不再寫入。
  - BibTeX 鏈與 `pybtex`、`latexcodec` 已移除。
  - 決策紀錄 §5 的保證全部仍由程式負責，且有測試；唯一的例外是 P8 明列的交叉比對。
- **涵蓋**：G3、G7（缺陷 #6）、G8（S029、S108、S110、S118–S120）
- **相依**：C3
- **驗收依據**：[決策紀錄](../../../../note/20261119/citation_storage_unification_decision.md) §4（合併後行為）與 §5（必須保留的保證）。本檔不重複其內容。
  - 本檔與決策紀錄不一致時，以決策紀錄為準，並修訂本檔。
  - 決策紀錄與程式事實不符時，依 GOALS「限制」的例外規則，在決策紀錄末尾追加更正並記在 build-log；不改寫既有段落。
- **輸入**：
  - [GOALS.md](../GOALS.md) 的 U4、U9、P7、P8、P9、A1。
  - [稽核原文](../context/repo-debt-audit-2026-11-19.md)的 S105、S106、S108、S110、S118–S121。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| C5-S1 | **建立保證對照（探索，不改產品程式）。** 回答以下問題，寫入 `evidence/C5-S1/guarantee-map.md`：<br>1. **A1**：`citation_save_batch` artifact 或 `SaveReceipt` 是否會寫進對話 JSON 或其他持久化資料？查 `conversations/` 的 repository 與 models、`turns/`、`observability.py`。<br>2. **決策紀錄 §5.3**：列出下列兩條路徑的每個拒絕條件，逐條寫明移除 BibTeX 後由哪段程式負責（resolution、`parse_csl`、`csl_from_authority`、`library.merge` 的驗證），或「無人負責」：<br>　- 權威記錄的 `export_bibtex` 加 `parse_canonical_bibtex`；<br>　- DOI 記錄的 `parse_canonical_bibtex`。<br>　CSL 與 BibTeX 的 DOI 交叉比對（`bibtex_doi_mismatch`）依 P8 不補回，在表中標「P8：移除」。<br>3. 確認現行的 DOI identity 規則：`parse_csl` 取回應中的 `DOI`，沒有時用被要求的 DOI。計劃不改這條規則（決策紀錄 §5.2），這裡只需記錄位置。<br>4. 列出所有讀寫下列名稱的位置：`output_dir`、`resolve_output_dir`、`citation_output_dir`、`CITATION_OUTPUT_DIR`、`bundle_path`、`BIB_FILENAME`、`SIDECAR_FILENAME`、`storage_failed`。<br>5. 確認桌面的 `citation.save` 核准是否仍可能在 `library_path` 為 `None` 時被觸發（決策紀錄 §4.1）。<br><br>出口：<br>• A1 成立：繼續。<br>• A1 不成立：本階段停在這一步，標為 Blocked 並回報，因為舊回合可能無法讀取。<br>• 第 2 題中「無人負責」的條件，交給 C5-S2 補上。 | 對照表的每一列都附檔案與函式位置。 |
| C5-S2 | **先補保證，再刪 BibTeX。**<br>• 依 C5-S1，把「無人負責」的欄位要求改成對 CSL 項目的檢查。例如權威記錄缺標題時判為 `verification_failed`，並附新的 reason code。<br>• 測試放在既有的 citation 測試模組，例如 `test_citation_save_outcomes.py`、`test_citation_authority.py`：<br>(a) 缺少必要欄位的權威記錄與 DOI 記錄都被拒絕；<br>(b) 正常的 DOI 與 arXiv 存檔照常成功；<br>(c) alias DOI：doi.org 的 CSL 回應帶的 DOI 與被要求的不同時，行為與現在相同，也就是以回應的 DOI 為 identity 存檔成功。<br>• C5-S1 若沒有找到「無人負責」的條件，本步只加測試 (b)、(c)，並在 build-log 註明。 | 新測試在**尚未刪除** BibTeX 的狀態下就通過，證明檢查不依賴 BibTeX。既有的 citation 測試通過。 |
| C5-S3 | **移除 bundle 與 BibTeX 鏈，桌面端同步切換（P7、P9；單一 commit）。** 核准畫面改顯示書目庫、解除舊輸出目錄的保護、停止寫入舊目錄，這三件事必須在**同一個 commit** 生效。否則若停在中間，核准畫面會漏報實際的寫入位置，或者保護已解除但仍在寫入。開發時可以分段進行，但中間狀態不單獨提交；全部檢查通過後才 commit 一次。這一步也同時更新所有 import 被刪模組的地方，包括 `agent/desktop/service.py` 與 `tests/test_citation_storage.py`、`test_citation_save_isolation.py`、`test_citation_authority.py`。<br>**核心**<br>• `CitationService` 依決策紀錄 §4.0–§4.2 與 P7 重寫存檔：<br>　- 驗證成功就登記到 registry，時機與現在相同，在 `_persist_item` 內，不寫任何檔案。<br>　- 桌面：沿用 `_link_library` 的一次批次寫入。合併後，以 `replace` 同時更新每筆的 `bibliography` 連結與狀態：`added` 為 `saved`，`existing` 為 `reused`；`failed` 時維持驗證時的狀態（新的一筆為 `saved`），只有連結是 `failed`。<br>　- CLI：`bibliography` 為 `null`；registry 已有同一 identity 時為 `reused`。<br>　- `storage_failed`：若已沒有 producer，就從 `SaveItemStatus` 移除。目前 registry 衝突也會產生它，要依 C5-S1 第 4 題的結果判斷。<br>• 刪除下列項目：<br>　- `SaveReceipt.bundle_path`；`SAVE_BATCH_SCHEMA_VERSION` 改為 3。<br>　- `storage.py`、`bibtex_canonical.py`。<br>　- `authority.export_bibtex`、`DoiOrgClient.fetch_bibtex` 與 `BIBTEX_ACCEPT`。<br>　- `types.py` 的 bundle schema 常數與只為 v1 bundle 存在的判斷，刪前先 grep 確認。<br>　- `tests/fixtures/legacy_v1_bundle` 與 bundle 測試。<br>　- `AgentConfig.citation_output_dir`，以及 `CITATION_OUTPUT_DIR` 的讀取。<br>• 文字更新：provenance 字串去掉 `bibtex`；`tool.py` 的 `format_explain` 與 `_format_bibliography_links` 改寫；CLI 存檔的工具結果要明說「沒有寫到磁碟，只在這次對話中可引用」。<br>• 順帶處理：<br>　- S108：刪 `csl_render.style_path`、`library.DEFAULT_LIBRARY_FILENAME`、`library.add_item`（約 15 處測試改用正式路徑）、`SourceRegistry.trusted_receipt`、`ProviderState.from_dict`、`PublishedDateFilter.within_years`、`DoiOrgClient.fetch_registration_agency`。<br>　- S110：`render.RenderedTurn.cited_sources` 與 `format_bibliography_entry`。<br>　- S118：`csl_render` 的重複載入。<br>　- S119：重複的小 helper。<br>　- S120：`service.py` 不再存取 `hub._fetch`，改由 hub 提供公開的 fetch；`ProviderError` 不再 inline import。<br>　- 缺陷 #6：`doi_org._encoded` 的回傳型別改為 `tuple[str, str]`。<br>**桌面端**<br>• `citation.save` 的核准 target 改為書目庫路徑（`service.py` 約 2408 行與 2772 行一帶）。依 C5-S1 第 5 題：`library_path` 為 `None` 的分支若走不到就刪除；若走得到，target 寫明不寫入磁碟。<br>• `runtime.diagnostics` 移除 `citationOutputPath`：contract、Python、TS DTO，以及 `App.tsx` 約 506 行與 2931 行的「Citation output」顯示。2931 行的 `cataloged`／`transient` 文字留給 C6。<br>• `_protected_roots` 移除輸出目錄。<br>• 移除 `agent/desktop/service.py` 對 `skills.citation.storage` 的 import（約 107 行）與全部 4 處 `resolve_output_dir` 呼叫（約 850、2408、2774、4251 行）。<br>• S029：bibliography handler 在同一 handler 內共用第一次讀到的書目路徑、書目與樣式清單。<br>• `fixture_session.py` 約 545 行的 `citation_output_dir` 隨 `AgentConfig.citation_output_dir` 一起刪除。 | • `pytest --collect-only -q`（從 `app/`）沒有任何收集錯誤，以此確認沒有殘留的 import。<br>• `pytest tests/test_citation_*.py -q` 與 `tests/test_inline_skills.py` 等引用 citation 的模組通過。<br>• grep `storage\.py` 的符號、`bundle_path`、`fetch_bibtex`、`export_bibtex`、`bibtex_canonical`、`citation_output_dir`、`CITATION_OUTPUT_DIR`、`pybtex` 在 `app/agent`、`app/skills`、`app/tests` 為 0。fixtures 資料夾名稱已一併刪除。<br>• 測試：<br>(a) 桌面存檔後，暫存目錄中只有書目庫被改寫，沒有 `cite/`、`reference.bib`、`citation.json`；<br>(b) CLI 存檔後不產生任何檔案，`[[cite:…]]` 在同一 task 內可渲染；<br>(c) 書目庫寫入失敗時，狀態仍是 `saved`、連結是 `failed`，該筆在這次 task 內可引用，工具結果明說沒有寫入磁碟；<br>(d) 同一 identity 已在書目庫時是 `reused`，回傳既有 key；<br>(e) CLI 在同一 task 內存同一 identity 兩次，第二次是 `reused`。<br>• `grep -n "citation.storage\|resolve_output_dir" app/agent/desktop/service.py` 為 0。<br>• `tests/test_desktop_bibliography.py`、`test_desktop_citation_keys.py`、`test_project_permissions.py`、`test_desktop_service.py`、`test_desktop_fixture.py`（沙箱外）、`npm test`、`npm run build` 通過。<br>• 測試期間 repo 根目錄的 `cite/` 沒有新增或改變的檔案；以執行前後的檔案清單比對。 |
| C5-S4 | **模型看到的文字。**<br>• 依決策紀錄 §4.5 改寫 `skills/citation/SKILL.md`：description，以及 bundle 相關的段落（約 145–147、157、169 行）。<br>• 同步修改 `skills/citation/README.md` 與 `skills/citation/__init__.py` 的 docstring。<br>• 改寫只描述新的事實：<br>　- 存檔加入專案書目庫；<br>　- CLI 只在本次對話可引用；<br>　- 書目庫寫入失敗時，本次任務仍可引用，並提示未寫入磁碟（與 C5-S3、P7 一致）。<br>• 不順便改寫其他指令。 | • `tests/test_skills.py`、`test_skill_runtime.py` 等驗證 skill 內容的測試通過。<br>• `git diff` 只改了 bundle 相關句子。<br>• build-log 註明「模型指令已改變（實驗條件）」。 |
| C5-S5 | **U9：移除 `pybtex`。**<br>• 從 `app/`，在 Conda env `app` 內執行 `poetry remove pybtex`。網路需求見 PLANS「檢查指令」。<br>• `poetry.lock` 不可手改。若 Poetry 無法完成，本步標為 Blocked，程式碼的移除仍然保留。 | • `grep -n "pybtex\|latexcodec" pyproject.toml poetry.lock` 為 0。<br>• `poetry check` 通過。<br>• `python -c "import skills.citation.service, skills.citation.authority"` 成功。<br>• lock 的 diff 只移除 `pybtex` 與 `latexcodec`；若連帶升級或移除其他套件，停下並回報。 |
| C5-S6 | **測試整理與收尾。**<br>• S121：只刪除因 U4 而失效的 citation 測試，依測試退役規則記錄。其他重疊不處理。<br>• 執行完整 pytest（沙箱外）、`npm test`、`npm run build`。contract 改過，所以也跑 `cargo test --locked`（沙箱外）。<br>• 在 build-log 記錄「citation 評估分界 commit」：C5-S3 的 commit，若 C5-S2 改變了驗證結果則記 C5-S2。理由見決策紀錄 §6.2。 | • 全部通過。<br>• 選擇性冒煙測試：只用免費的 Crossref、DataCite、doi.org，在 `$TMPDIR` 建一個暫時的專案書目庫，以 `CitationService` 存一個已知 DOI。若網路不可用則略過並註明，不算失敗。 |

## 驗收

- 決策紀錄 §4 的每個可觀察結果都有對應的測試或 evidence。
- §5 的每個保證在 `guarantee-map.md` 都有負責的程式位置。
- 上述 grep 都為 0。
- 四套測試通過。
- GUI 清單新增：
  - 在專案中 `/citation` 存檔，書目庫新增 key，且不產生 `cite/`；
  - 以 DOI 加入文獻時，核准對話框顯示書目庫路徑；
  - runtime 細節不再顯示「Citation output」。

## 交給後續階段

- citation 子系統沒有 bundle 也沒有 BibTeX。C7 把 bibliography handler 抽成模組時，搬的是縮減後的版本。
- `for_agents/` 的 INV-010、INV-029、INV-032 過時，由 C10 列入最終彙報。
