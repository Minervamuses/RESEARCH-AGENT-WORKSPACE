# C5 — Citation 單一儲存與誠實的存檔結果（U4、U9、U13）

- **完成後的狀態**：
  - 驗證過的文獻只存在專案書目庫；`cite/` 不再寫入。
  - **桌面**：只有書目庫裡確實有這筆時，才回報 `saved`／`reused`，也才可引用。寫入失敗是 `storage_failed`，不可引用。同一批次的重複作品不會誤報。
  - **CLI**：不寫檔；驗證成功是 `verified`，只在當次 task 可引用。
  - 存檔計數分開 `new_saved`、`reused`、`verified`、`failed`。
  - BibTeX 鏈與 `pybtex`、`latexcodec` 已移除。
  - 決策紀錄 §5 的保證全部仍由程式負責，且有測試；唯一的例外是 P8 明列的交叉比對。
- **涵蓋**：G3、G7（缺陷 #6）、G8（S029、S108、S110、S118–S120）
- **相依**：C3
- **驗收依據**：[決策紀錄](../../../../note/20261119/citation_storage_unification_decision.md) §4（合併後行為，已依 U13 改寫）與 §5（必須保留的保證）。
  - 本檔與決策紀錄不一致時，以決策紀錄為準，並修訂本檔。
  - 決策紀錄與程式事實不符時，依 GOALS「限制」的例外規則，在決策紀錄末尾追加更正並記在 build-log；不改寫既有段落。
- **輸入**：
  - [GOALS.md](../GOALS.md) 的 U4、U9、U13、P8、P9、P13、A1。
  - [稽核原文](../context/repo-debt-audit-2026-11-19.md)的 S105、S106、S108、S110、S118–S121。

## 存檔語意摘要（U13、P13）

完整規則在決策紀錄 §4.0。這裡列出實作時最容易出錯的順序。

**桌面（`library_path` 不為 None）**

1. 每筆照現在的方式解析與驗證，不寫任何檔案。
2. 驗證成功的每筆，建立 `SourceRef` 與 `SaveReceipt`（沒有 `bundle_path`），但**先不登記**。
3. P13：若 registry 已有同一 source ID 但 identity 不同，該筆是 `identity_conflict`（reason `registry_conflict`），不進入書目庫。
4. 其餘各筆以一次 `_link_library` 合併並寫入書目庫。
5. 依每筆的實際結果決定狀態：
   - 新加入，而且寫入成功：`saved`，登記，可引用。
   - 書目庫原本就有：`reused`，登記，可引用，回傳既有 key。
   - 合併被拒，或整批寫入失敗：`storage_failed`，reason 是書目庫的錯誤碼，**不登記，不可引用**，沒有 receipt。
6. **同一批次的重複作品**：第一筆決定結果。之後同一作品的各筆，在第一筆是 `saved` 時報 `reused` 並共用 key；在第一筆是 `storage_failed` 時同樣是 `storage_failed`。現行 `_link_library` 會把「同批次較早一筆剛加入記憶體」的作品報成 `existing`，即使之後寫入失敗；這是要修的缺陷。

**CLI（`library_path` 為 None）**

1. 每筆照現在的方式解析與驗證，不寫任何檔案。
2. 驗證成功：P13 的 registry 檢查通過後登記，狀態一律是 `verified`，可在當次 task 引用，沒有 bibliography 連結。

**型別與計數**

- `SaveItemOutcome`：有 receipt ⇔ 狀態是 `saved`、`reused` 或 `verified`。bibliography 連結只出現在桌面的 `saved`／`reused`。
- `BibliographyLink` 只剩 `added`／`existing` 兩種狀態，連同 key 與路徑；失敗改由項目本身的 `storage_failed` 與 reason 表達，連結上的 `failed` 與 `reason_code` 移除。
- `SaveItemStatus` 新增 `verified`。`storage_failed` 只代表書目庫寫入或合併失敗。
- `CitationSaveMetrics` 新增 `verified_count`；`new_saved_count` 只算 `saved`；`to_record` 多一個鍵。
- `SAVE_BATCH_SCHEMA_VERSION` 改為 3。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| C5-S1 | **建立保證對照與使用者盤點（探索，不改產品程式）。** 回答以下問題，寫入 `evidence/C5-S1/guarantee-map.md`：<br>1. **A1**：`citation_save_batch` artifact、`SaveReceipt` 或 `CitationSaveMetrics` 是否會寫進對話 JSON 或其他持久化資料？查 `conversations/` 的 repository 與 models、`turns/`、`observability.py`。<br>2. **決策紀錄 §5.3**：列出下列兩條路徑的每個拒絕條件，逐條寫明移除 BibTeX 後由哪段程式負責（resolution、`parse_csl`、`csl_from_authority`、`library.merge` 的驗證），或「無人負責」：<br>　- 權威記錄的 `export_bibtex` 加 `parse_canonical_bibtex`；<br>　- DOI 記錄的 `parse_canonical_bibtex`。<br>　CSL 與 BibTeX 的 DOI 交叉比對（`bibtex_doi_mismatch`）依 P8 不補回，在表中標「P8：移除」。<br>3. 確認現行的 DOI identity 規則：`parse_csl` 取回應中的 `DOI`，沒有時用被要求的 DOI。計劃不改這條規則（決策紀錄 §5.2），這裡只需記錄位置。<br>4. 列出所有讀寫下列名稱的位置：`output_dir`、`resolve_output_dir`、`citation_output_dir`、`CITATION_OUTPUT_DIR`、`bundle_path`、`BIB_FILENAME`、`SIDECAR_FILENAME`、`storage_failed`、`registry_conflict`。<br>5. 確認桌面的 `citation.save` 核准是否仍可能在 `library_path` 為 `None` 時被觸發（決策紀錄 §4.1）。<br>6. **狀態值的使用者**：列出讀取存檔狀態、`BibliographyLink` 或存檔計數的每個位置，包括 `session_policy.py` 的計數、`tool.py` 的格式化、`SKILL.md`、桌面 `bibliography.add` handler（約 2420 行以 `link.key` 判斷成功）、前端（引用面板是否顯示這些狀態）、turn trace 與測試。C5-S3 要逐一更新它們。<br><br>出口：<br>• A1 成立：繼續。<br>• A1 不成立：本階段停在這一步，標為 Blocked 並回報，因為舊回合可能無法讀取。<br>• 第 2 題中「無人負責」的條件，交給 C5-S2 補上。 | 對照表與使用者清單的每一列都附檔案與函式位置。 |
| C5-S2 | **先補保證，再刪 BibTeX。**<br>• 依 C5-S1，把「無人負責」的欄位要求改成對 CSL 項目的檢查。例如權威記錄缺標題時判為 `verification_failed`，並附新的 reason code。<br>• 測試放在既有的 citation 測試模組，例如 `test_citation_save_outcomes.py`、`test_citation_authority.py`：<br>(a) 缺少必要欄位的權威記錄與 DOI 記錄都被拒絕；<br>(b) 正常的 DOI 與 arXiv 存檔照常成功；<br>(c) alias DOI：doi.org 的 CSL 回應帶的 DOI 與被要求的不同時，行為與現在相同，也就是以回應的 DOI 為 identity 存檔成功。<br>• C5-S1 若沒有找到「無人負責」的條件，本步只加測試 (b)、(c)，並在 build-log 註明。 | 新測試在**尚未刪除** BibTeX 的狀態下就通過，證明檢查不依賴 BibTeX。既有的 citation 測試通過。 |
| C5-S3 | **移除 bundle 與 BibTeX 鏈、改存檔語意、桌面端同步切換（U13、P9、P13；單一 commit）。** 下列改動必須在**同一個 commit** 生效：核准畫面改顯示書目庫、解除舊輸出目錄的保護、停止寫入舊目錄、新的存檔語意。否則若停在中間，核准畫面會漏報實際的寫入位置，或者回報的狀態與實際寫入不符。開發時可以分段進行，但中間狀態不單獨提交；全部檢查通過後才 commit 一次。這一步也同時更新所有 import 被刪模組的地方，包括 `agent/desktop/service.py` 與 `tests/test_citation_storage.py`、`test_citation_save_isolation.py`、`test_citation_authority.py`。<br>**核心**<br>• `CitationService` 依上方「存檔語意摘要」與決策紀錄 §4.0 重寫 `save`、`_persist_item` 與 `_link_library`。登記改在書目庫結果確定之後（桌面）或驗證之後（CLI）。<br>• 依 C5-S1 第 6 題，更新每個狀態值的使用者：計數（新增 `verified_count`）、`tool.py` 的工具結果、桌面 `bibliography.add` handler（`storage_failed` 回報為失敗並附 reason）。<br>• 工具結果的文字：<br>　- `storage_failed`：明說沒有存檔、這次不可引用、原因與書目庫路徑，並建議重試。<br>　- `verified`：明說已驗證、只在這次對話可引用、沒有寫到磁碟（CLI 沒有專案書目庫）。<br>　- 不再出現 "the bundle result above is unchanged" 這類句子。<br>• 刪除下列項目：<br>　- `SaveReceipt.bundle_path`；`BibliographyLink` 的 `failed` 狀態與 `reason_code`。<br>　- `storage.py`、`bibtex_canonical.py`。<br>　- `authority.export_bibtex`、`DoiOrgClient.fetch_bibtex` 與 `BIBTEX_ACCEPT`。<br>　- `types.py` 的 bundle schema 常數與只為 v1 bundle 存在的判斷，刪前先 grep 確認。<br>　- `tests/fixtures/legacy_v1_bundle` 與 bundle 測試。<br>　- `AgentConfig.citation_output_dir`，以及 `CITATION_OUTPUT_DIR` 的讀取。<br>• 文字更新：`skills/citation/__init__.py` 的 docstring（約 13–14 行提到 pybtex 與 bundle）改寫；provenance 字串去掉 `bibtex`；`tool.py` 的 `format_explain` 與 `_format_bibliography_links` 改寫。<br>• 順帶處理：<br>　- S108：刪 `csl_render.style_path`、`library.DEFAULT_LIBRARY_FILENAME`、`library.add_item`（約 15 處測試改用正式路徑）、`SourceRegistry.trusted_receipt`、`ProviderState.from_dict`、`PublishedDateFilter.within_years`、`DoiOrgClient.fetch_registration_agency`。<br>　- S110：`render.RenderedTurn.cited_sources` 與 `format_bibliography_entry`。<br>　- S118：`csl_render` 的重複載入。<br>　- S119：重複的小 helper。<br>　- S120：`service.py` 不再存取 `hub._fetch`，改由 hub 提供公開的 fetch；`ProviderError` 不再 inline import。<br>　- 缺陷 #6：`doi_org._encoded` 的回傳型別改為 `tuple[str, str]`。<br>**桌面端**<br>• `citation.save` 的核准 target 改為書目庫路徑（`service.py` 約 2408 行與 2772 行一帶）。依 C5-S1 第 5 題：`library_path` 為 `None` 的分支若走不到就刪除；若走得到，target 寫明不寫入磁碟。<br>• `runtime.diagnostics` 移除 `citationOutputPath`：contract、Python、TS DTO，以及 `App.tsx` 約 506 行與 2931 行的「Citation output」顯示。2931 行的 `cataloged`／`transient` 文字留給 C6。<br>• `_protected_roots` 移除輸出目錄。<br>• 移除 `agent/desktop/service.py` 對 `skills.citation.storage` 的 import（約 107 行）與全部 4 處 `resolve_output_dir` 呼叫（約 850、2408、2774、4251 行）。<br>• S029：bibliography handler 在同一 handler 內共用第一次讀到的書目路徑、書目與樣式清單。<br>• `fixture_session.py` 約 545 行的 `citation_output_dir` 隨 `AgentConfig.citation_output_dir` 一起刪除。 | • `pytest --collect-only -q`（從 `app/`）沒有任何收集錯誤，以此確認沒有殘留的 import。<br>• `pytest tests/test_citation_*.py -q` 與 `tests/test_inline_skills.py` 等引用 citation 的模組通過。<br>• 以 `grep -rnw --include=*.py`（`-w` 整字比對，避免誤中 `agent/extensions/startup.py` 的 `_installed_bundle_path` 這類無關名稱）在 `app/agent`、`app/skills`、`app/tests` 的**程式碼**中搜尋 `storage.py` 的符號、`bundle_path`、`fetch_bibtex`、`export_bibtex`、`bibtex_canonical`、`citation_output_dir`、`CITATION_OUTPUT_DIR`、`pybtex`，結果為 0。文件（`README.md`、`SKILL.md`）中的同名字串由 C5-S4 處理。<br>• **存檔語意測試**（放在既有的 citation 與 desktop 測試模組）：<br>(a) 桌面存檔後，暫存目錄中只有書目庫被改寫，沒有 `cite/`、`reference.bib`、`citation.json`。<br>(b) 桌面書目庫寫入失敗（注入 `LibraryError`）：狀態 `storage_failed`，reason 是書目庫的錯誤碼，沒有 receipt；`[[cite:<sid>]]` 過不了 gate；工具結果明說沒有存檔、不可引用；`failed_count` 加 1，`new_saved_count` 為 0。<br>(c) 書目庫已有同一作品：`reused`，回傳既有 key，可引用。<br>(d) 同一批次兩筆同一作品、寫入成功：第一筆 `saved`、第二筆 `reused`，同一 key；`new_saved_count` 1、`reused_count` 1。<br>(e) 同一批次兩筆同一作品、寫入失敗：兩筆都是 `storage_failed`，第二筆不是 `reused`。<br>(f) 同一批次中一筆合併被拒、一筆正常：被拒的 `storage_failed`，正常的 `saved`；書目庫只寫一次。<br>(g) CLI 存檔：狀態 `verified`，任何目錄都沒有新檔案（比對暫存目錄的檔案清單），`[[cite:…]]` 在同一 task 內可渲染；`verified_count` 1、`new_saved_count` 0。<br>(h) CLI 在同一 task 存同一作品兩次：兩次都是 `verified`，都可引用。<br>(i) P13：registry 衝突時狀態 `identity_conflict`、reason `registry_conflict`；桌面上該筆沒有寫入書目庫。<br>(j) 引用面板以 DOI 加入（`bibliography.add`）：寫入成功回傳 key；寫入失敗回報錯誤並附 reason。<br>• `grep -n "citation.storage\|resolve_output_dir" app/agent/desktop/service.py` 為 0。<br>• `tests/test_desktop_bibliography.py`、`test_desktop_citation_keys.py`、`test_project_permissions.py`、`test_desktop_service.py`、`test_desktop_fixture.py`（沙箱外）、`npm test`（含 DTO 一致性檢查）、`npm run build` 通過。<br>• 測試期間 repo 根目錄的 `cite/` 沒有新增或改變的檔案；以執行前後的檔案清單比對。 |
| C5-S4 | **模型看到的文字。**<br>• 依決策紀錄 §4.5 改寫 `skills/citation/SKILL.md`：description、bundle 相關的段落（約 145–147、157、169 行），以及描述存檔狀態的句子。<br>• 同步修改 `skills/citation/README.md`。`skills/citation/__init__.py` 的 docstring 是程式碼檔，已在 C5-S3 改寫。<br>• 改寫只描述新的事實：<br>　- 桌面：存檔加入專案書目庫；`saved`／`reused` 才可引用；`storage_failed` 表示沒有存檔、不可引用，應告知使用者並可重試。<br>　- CLI：`verified` 只在本次對話可引用，沒有寫到磁碟，不可說成「已存檔」。<br>• 不順便改寫其他指令。 | • `tests/test_skills.py`、`test_skill_runtime.py` 等驗證 skill 內容的測試通過。<br>• `grep -rn "bundle\|bibtex_canonical\|reference.bib\|cite/" app/skills/citation --include=*.md` 只剩描述歷史或明確說明「不再產生」的句子，逐一註明。`README.md` 第 50 行的模組表要刪掉 `bibtex_canonical.py`。<br>• `git diff` 只改了 bundle、BibTeX 與存檔狀態相關的句子。<br>• build-log 註明「模型指令已改變（實驗條件）」。 |
| C5-S5 | **U9：移除 `pybtex`。**<br>• 從 `app/`，在 Conda env `app` 內執行 `poetry remove pybtex`。網路需求見 PLANS「檢查指令」。<br>• `poetry.lock` 不可手改。若 Poetry 無法完成，本步標為 Blocked，程式碼的移除仍然保留。 | • `grep -n "pybtex\|latexcodec" pyproject.toml poetry.lock` 為 0。<br>• `poetry check` 通過。<br>• `python -c "import skills.citation.service, skills.citation.authority"` 成功。<br>• lock 的 diff 只移除 `pybtex` 與 `latexcodec`；若連帶升級或移除其他套件，停下並回報。 |
| C5-S6 | **測試整理與收尾。**<br>• S121：只刪除因 U4 或 U13 而失效的 citation 測試，依測試退役規則記錄。其他重疊不處理。<br>• 執行完整 pytest（沙箱外）、`npm test`、`npm run build`。contract 改過，所以也跑 `cargo test --locked`（沙箱外）。<br>• 在 build-log 記錄「citation 評估分界 commit」：C5-S3 的 commit，若 C5-S2 改變了驗證結果則記 C5-S2。理由見決策紀錄 §6.2。 | • 全部通過。<br>• 選擇性冒煙測試：只用免費的 Crossref、DataCite、doi.org，在 `$TMPDIR` 建一個暫時的專案書目庫，以 `CitationService` 存一個已知 DOI，確認狀態是 `saved` 且書目庫多了這筆。若網路不可用則略過並註明，不算失敗。 |

## 驗收

- 決策紀錄 §4 的每個可觀察結果都有對應的測試或 evidence。
- §5 的每個保證在 `guarantee-map.md` 都有負責的程式位置。
- 上述 grep 都為 0。
- 四套測試通過。
- GUI 清單新增：
  - 在專案中 `/citation` 存檔，書目庫新增 key，且不產生 `cite/`；
  - 以 DOI 加入文獻時，核准對話框顯示書目庫路徑；
  - 把書目庫設為唯讀後存檔：agent 告知沒有存檔，而不是說已存檔；
  - runtime 細節不再顯示「Citation output」。

## 交給後續階段

- citation 子系統沒有 bundle 也沒有 BibTeX。C7 把 bibliography handler 抽成模組時，搬的是縮減後的版本。
- `for_agents/` 的 INV-010、INV-029、INV-032 與 ASM-014 過時，由 C10 列入最終彙報。
