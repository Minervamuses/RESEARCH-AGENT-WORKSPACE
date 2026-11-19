# 決策紀錄：citation bundle（`cite/`）併入專案書目庫

- 日期：2026-11-19
- 決策者：使用者（本專案擁有者）
- 狀態：**已決定，尚未實作**。實作排在計劃 `harness/plans/2026-11-19-repo-debt-cleanup/` 的 C5 階段。
- 依據：2026-11-19 的 repo 債務稽核，項目 S105、S106。稽核全文在計劃目錄的 `context/repo-debt-audit-2026-11-19.md`。
- 讀碼基準：branch `GUI`、HEAD `3b6cfd8`。以下行號都以這個 commit 為準。
- 使用者原話：
  - 回覆稽核問題「citation bundle（`cite/`）和專案書目庫要不要合併成一套？這是 citation 子系統最大的減量，但 CLI 會失去單獨存檔的能力。」時答：「同意，但是要在note裡面紀錄這個決定，寫詳細點」。
  - 之後另以勾選核准「移除 pybtex 相依」。

---

## 1. 一句話

驗證過的文獻改成只存在專案的 CSL-JSON 書目庫（預設 `references.json`）。`cite/` 底下的 bundle（`reference.bib`＋`citation.json`）不再寫入，整條 BibTeX 處理鏈與 `pybtex` 相依一併移除。CLI 沒有專案書目庫，因此 CLI 的 `/citation` 仍可搜尋、驗證，並在當次對話中引用，但**不再把任何東西寫到磁碟**。

---

## 2. 決定前的狀況

### 2.1 兩套儲存

| | citation bundle | 專案書目庫 |
|---|---|---|
| 位置 | 依序取 `AgentConfig.citation_output_dir`、環境變數 `CITATION_OUTPUT_DIR`、`<最近的 git workspace>/cite`、平台 user-data 目錄下的 `research-agent/citation`（`skills/citation/storage.py::resolve_output_dir`） | 桌面專案根目錄的 `references.json`，或 `RESEARCH.md` metadata 的 `bibliography` 所指的檔案 |
| 格式 | 每筆一個目錄 `<標題>--<identity hash>/`，內含 `reference.bib`（BibTeX）與 `citation.json`（sidecar：source_ref、建立證據、resolution 紀錄、artifact hash） | 單一 CSL-JSON 陣列。保留使用者手寫條目與 JSON 排版（`library.LAYOUTS`） |
| 寫入者 | `storage.write_identity_bundle`：staging 目錄、0600、fsync、rename，並以 `.locks/` 的 flock 鎖住 source slot | `library.write_atomic`：寫入前比對 fingerprint，再 atomic replace |
| 存在於 | CLI 與桌面都有 | 只有桌面專案 |
| 程式量 | `storage.py` 399 行、`bibtex_canonical.py` 169 行、`authority.export_bibtex`、`providers/doi_org.py::fetch_bibtex`、`types.py` 的 v1/v2 schema 常數、`tests/fixtures/legacy_v1_bundle` 與 bundle 測試 | `library.py` 427 行（合併後保留） |

### 2.2 一次存檔的實際流程（`skills/citation/service.py`）

1. `WorkResolver.resolve` 解析每個 WorkIntent。精確 DOI 會先向 doi.org 取 CSL-JSON（`doi_org.fetch_structured`，`resolution.py:456`、`:600`）。
2. `_persist_item` 依記錄種類分流：
   - **DOI 記錄**：再向 doi.org 取一次 BibTeX（`fetch_bibtex`，`service.py:332`），用 pybtex 解析（`parse_canonical_bibtex`）。BibTeX 沒有 DOI 時補上；DOI 不一致則判為 `verification_failed / bibtex_doi_mismatch`。provenance 字串是 `fresh-resolution+doi.org-csl+bibtex`。
   - **權威記錄**（arXiv API、`proceedings.neurips.cc`）：`authority.export_bibtex` 以 pybtex 產生 BibTeX 再解析驗證。失敗判為 `verification_failed / authority_bibtex_invalid`。
3. `write_identity_bundle` 寫出 bundle。若同一 identity 的 bundle 已存在，驗證後重用，狀態是 `reused`。bundle 衝突或寫入失敗判為 `storage_failed`（`bundle_conflict`、`source_id_collision`、`write_failed`）。
4. 建立 `SaveReceipt`，其中 `bundle_path` 是 bundle 目錄，然後 `registry.register(ref, receipt=receipt)`。
5. 只有桌面專案（`library_path` 不為 None）會執行 `_link_library`，把 CSL 項目併入書目庫，結果記在每筆的 `bibliography` 連結（`added`／`existing`／`failed`）。**書目庫失敗不改變 bundle 的 `saved`／`reused` 結果**（INV-032 的一部分）。

### 2.3 bundle 實際被誰用到

- production 唯一讀回 bundle 的地方是 `storage._find_existing`，用來判斷能不能重用（`reused`）。
- 「這個來源在對話中可不可以引用」**不靠 bundle**。可引用性來自記憶體內的 `SourceRegistry`。`CitationSessionPolicy` 每個 Citation task 都重建 service 與 registry，`SKILL.md:145-147` 也寫明後續 task 必須重新存檔或重用才能取得新的信任 receipt。
- 書目庫 `references.json` 的內容由 CSL 產生（`CitationService._csl_item`），與 BibTeX 無關。
- 因此整條 BibTeX 鏈（第二次 doi.org 請求、pybtex 解析、`reference.bib`）只為了產出一個沒有人讀的檔案。

### 2.4 磁碟上的現況（2026-11-19）

`/home/minervamuses/research-agent-workspace/cite/` 底下只有一個 bundle `Attention_Is_All_You_Need--e0b4220861eb/`（2026-11-07，引用面板驗收時留下）與 `.locks/`。`.gitignore` 有 `/cite/` 規則，所以這些檔案沒有被追蹤。

---

## 3. 決定的內容

**書目庫成為唯一的儲存。receipt 只是記憶體內的信任 token。CLI 不再存檔。**

稽核列出的另一個選項是「維持兩套儲存，只刪 v1 bundle 讀取器」（S106），沒有被採用。

---

## 4. 合併後的行為

這一節是計劃 C5 的驗收依據。「計劃設計」是撰寫計劃時的預定做法：執行者可以調整實作細節，但要達到同樣的可觀察結果，並在 build-log 記錄差異。

### 4.1 桌面專案（有書目庫）

- 存檔的唯一寫入是把 CSL 項目併入 `references.json`。不再建立 `cite/`，也不再寫任何 `reference.bib` 或 `citation.json`。
- 每筆狀態的意義：
  - `saved`：新加入書目庫，並取得新 key。
  - `reused`：同一 identity（DOI、arXiv ID 或 NeurIPS 官方網址）已經在書目庫裡。沒有寫入，回傳既有 key。
  - `storage_failed`：書目庫無法讀取、無法合併（例如排版無法重現），或寫入失敗。**這筆不會被登記為可引用。**
- 這是行為改變：以前 bundle 寫成功而書目庫失敗時，這筆仍是 `saved`、可在聊天中引用，只有 `bibliography` 連結顯示失敗。合併後只有一個儲存，寫不進去就是存檔失敗。
- `storage_failed` 的 reason code 改用書目庫的錯誤碼（`LibraryError.code`），bundle 的 `bundle_conflict`、`source_id_collision`、`write_failed` 消失。
- 引用面板的「以 DOI／arXiv ID 加入」（`bibliography.add`）走同一條路，只是不再產生 bundle。
- 存檔的核准對話框（operation `citation.save`）目前的 target 是 bundle 輸出目錄（`service.py:2408-2410`、`:2772-2784`），之後改成書目庫路徑。

### 4.2 CLI（沒有書目庫）

- `/citation` 的 `search`、`sources`、`source`、`explain` 不變。
- `save` 照常解析與驗證。驗證成功的作品登記到這次 task 的 registry，所以這次對話中可以用 `[[cite:…]]` 引用並渲染參考文獻。
- **不寫入任何檔案。** 工具結果要明確告訴模型「沒有寫到磁碟，只在這次對話中可引用」，避免模型對使用者說「已存檔」。
- 狀態的意義（計劃設計）：
  - `saved`：這次 task 新驗證並登記。
  - `reused`：這次 task 的 registry 已經有同一 identity。
  - 不新增狀態值，避免 `CitationSaveMetrics` 與 turn trace 的計數語意改變。
  - 「是否持久化」只看該筆的 `bibliography` 連結：CLI 一律是 `null`。
- 以前在 CLI 存過的 bundle 不會被讀回。跨 session 的 `reused` 在 CLI 消失。

### 4.3 型別與資料格式

- `SaveReceipt` 移除 `bundle_path`。持久化位置與 key 由既有的 `BibliographyLink`（status、path、key）表達。
- 工具 artifact `citation_save_batch` 的 schema 版本從 2 升為 3（`SAVE_BATCH_SCHEMA_VERSION`）。這個 artifact 只在當次回合內被 `CitationSessionPolicy.save_metrics` 與 `observability` 讀取；C5 執行時要確認它沒有被寫進對話 JSON。若有寫入，先停下來記錄，不可讓舊回合無法讀取。
- `types.py` 的 `PERSIST_SCHEMA_VERSION`、`BUNDLE_SCHEMA_V2`、`SUPPORTED_PERSIST_SCHEMA_VERSIONS`，以及只為 v1 bundle 存在的 `identity_verified` 判斷，隨 bundle 一起移除。是否還有其他用途，執行時以 grep 確認。

### 4.4 設定、診斷與保護目錄

- `AgentConfig.citation_output_dir` 與環境變數 `CITATION_OUTPUT_DIR` 移除。`.env` 若還設著這個變數，之後不會再有作用。
- 桌面 `runtime.diagnostics` 的 `citationOutputPath` 欄位移除，這是協定變更，由 C5 修改 contract、Python 與 TS。GUI 的「Citation output」細節列（`App.tsx:506`、`:2931`）一併移除。
- `DesktopService._protected_roots`（`service.py:4240-4256`）不再把 bundle 輸出目錄列為受保護目錄。

### 4.5 模型看到的文字

- `skills/citation/SKILL.md` 裡關於 bundle 的句子要改寫：第 3 行的 description、第 145-147 行、第 157 行、第 169 行。
- `tool.py::format_explain` 原本說 DOI 走「CSL JSON and BibTeX」驗證、bundle 寫在某個目錄，也要改寫。
- 兩處的 `_format_bibliography_links` 結尾提示（"the bundle result above is unchanged"）也要改。
- **這些是給模型的指令，改動會改變 agent 的行為**，見第 6 節。

---

## 5. 必須保留的保證

合併不能削弱下列保證。C5 要逐條找出現在由哪段程式負責，並在 evidence 記下對照。

1. **只有成功驗證的存檔才能被引用**（INV-010 的主體）：搜尋本身不產生可引用來源；registry 只在驗證成功後登記；聊天中的 `[[cite:…]]` 仍要通過 gate。
2. **DOI identity 檢查**：以前 BibTeX 的 DOI 必須與目標 DOI 一致（`bibtex_doi_mismatch`）。移除 BibTeX 後，必須確認 doi.org 回傳的 CSL-JSON 描述的就是被要求的 DOI。若 `parse_csl` 目前只沿用被要求的 DOI、沒有比對回應內容中的 `DOI` 欄位，就要在 CSL 路徑補上等值檢查，失敗時判為 `verification_failed`。補上的檢查要有測試：doi.org 回傳另一個 DOI 時，存檔失敗且不寫入書目庫。
3. **權威記錄的最低欄位要求**：`export_bibtex` 與 `parse_canonical_bibtex` 會拒絕某些不完整的記錄（例如缺標題）。C5 要列出這些拒絕條件，逐條確認在 resolution、`csl_from_authority` 或書目庫合併中已有對應檢查；沒有的話，把該條件改成對 CSL 項目的檢查，不要直接丟掉。
4. **書目庫合併規則**（INV-032 的其餘部分）：保留既有條目、key 與 JSON 排版；拒絕無法重現的排版；寫入前重新比對 fingerprint；只用 atomic replace。
5. **同一 identity 不重複加入**：與現在 `library.merge` 的 `existing` 判斷相同。

---

## 6. 失去或改變的東西

### 6.1 功能

- CLI 不再產生任何存檔，也就是稽核所說的「CLI 失去單獨存檔的能力」。
- 不再產生 `reference.bib`。目前沒有程式或文件流程讀取它。需要 BibTeX 時，之後應從書目庫匯出，而不是恢復 bundle。
- 桌面書目庫寫入失敗時，該筆不再可引用（見 4.1）。
- bundle 的 `citation.json` 原本保存每次存檔的來龍去脈：agent 當時的 intent、resolution 的記錄來源、provider record ID、版本種類與決策 reason code。**合併後這些不再落地。** 診斷 log 仍保留每筆的 batch ID、index、status 與 reason code（`service.py` 的 `citation save batch … item …` INFO 行），但沒有 intent 與 resolution 細節。

### 6.2 對論文研究的影響

agent 的設計選擇同時是實驗條件。這次合併會改變：

1. **驗證管線**：每筆 DOI 存檔少一個獨立 artifact 的檢查（BibTeX），也少一次 doi.org 請求。CSL 已在 resolution 階段取得並快取 24 小時，所以存檔階段不再發出額外請求。
2. **失敗類別**：`bibtex_lookup_*`、`bibtex_doi_mismatch`、`authority_bibtex_invalid` 不會再出現。`storage_failed` 的 reason code 改用書目庫錯誤碼。新增的 CSL DOI 等值檢查（若需補上，見 5.2）會產生自己的 reason code。
3. **provenance 字串**：`fresh-resolution+doi.org-csl+bibtex` 會改成不含 `bibtex` 的版本。
4. **模型指令**：`SKILL.md` 與 `explain` 的文字改變，見 4.5。
5. **存檔紀錄**：若論文的 citation 驗證評估曾把 `cite/` 的 sidecar 當成每次存檔的紀錄，合併後要改用診斷 log 或回合結果。

因此，以這次變更前後的 commit 為界的評估結果不能直接合併比較。C5 完成時要在 build-log 記下分界 commit。若評估需要逐筆的存檔紀錄，應另外決定記錄位置（例如回合結果或專用的評估 log），不要恢復 bundle。

### 6.3 程式減量（稽核估計，C5 完成後以實測取代）

- 刪除 `storage.py`（399 行）與 `bibtex_canonical.py`（169 行）。
- 刪除 `authority.export_bibtex`、`doi_org.fetch_bibtex` 與 `BIBTEX_ACCEPT`。
- 刪除 `types.py` 的 bundle schema 部分與 v1 bundle 讀取路徑（S106，因此不必另外處理）。
- 刪除 `tests/fixtures/legacy_v1_bundle` 與 bundle 相關測試。
- 刪除 `pyproject.toml` 的 `pybtex`，`poetry.lock` 一併移除 `pybtex` 與 `latexcodec`（`latexcodec` 只被 pybtex 依賴）。用 Poetry 更新 lock，不手改。`pyyaml` 有直接宣告，不受影響。

---

## 7. 既有資料

- `cite/` 現有的 bundle 與 `.locks/` **不遷移、不刪除**，由使用者自行決定是否手動刪除。
- 桌面存過的作品本來就同時寫進了書目庫，不需要遷移。
- 若要保留只在 CLI 存過的作品：每個 bundle 的 `citation.json` 有 DOI，可在桌面引用面板以 DOI 加入書目庫。
- `.gitignore` 的 `/cite/` 規則保留，以免殘留的 bundle 被誤提交。
- `AGENTS.md` 仍把 `cite/` 列為 generated output。這句話對殘留檔案仍然成立；是否修改由使用者決定，計劃不改 `AGENTS.md`。

---

## 8. 需要事後更新的知識文件

`for_agents/` 由 `$infrastructure` skill 維護，計劃不直接修改。C5 完成後，以下內容會過時，需要重新整理：

- **INV-010**：「bundle written」不再成立；驗證 artifact 不再包含 BibTeX。
- **INV-029**：`cite/` 不再產生新內容。
- **INV-032**：「never alter bundle save outcomes」改為「書目庫失敗即存檔失敗」。
- **`data-flow.md`** 的 citation 存檔流程。
- **`module-responsibilities.md`** 的 citation 模組列表。

文件側由 C10 處理：

- **會改寫**：根目錄 `README.md`（「引用與參考文獻」一節第 125 行附近，以及資料位置表第 162 行「已儲存的文獻」列）與 `app/skills/citation/README.md`（第 23、51、65、69 行）。
- **不會改**：`for_agents/`、`AGENTS.md`、`note/` 與既有計劃紀錄。

---

## 9. 不在這個決定範圍內

- 書目庫的檔案格式、key 產生規則與排版保留規則：不變。
- 引用樣式、預覽與匯出（Word、bime_word）：不變。
- 搜尋 provider（Crossref、DataCite、OpenAlex）與 resolution 規則：除了第 5 節第 2、3 點的檢查搬移，其餘不變。
- 是否另外為論文評估保存逐筆存檔紀錄：留待使用者需要時再決定（見 6.2）。
