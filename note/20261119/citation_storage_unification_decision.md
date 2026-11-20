# 決策紀錄：citation bundle（`cite/`）併入專案書目庫

- 日期：2026-11-19
- 決策者：使用者（本專案擁有者）
- **使用者決定的內容**：
  - 合併成單一儲存；
  - CLI 失去單獨存檔的能力；
  - 移除 `pybtex` 相依。
- **2026-11-20 使用者追加決定的內容**（計劃 GOALS 的 U13）：存檔的成功語意。桌面端「可引用 ⇔ 已寫入書目庫」，寫入失敗回報 `storage_failed` 且不可引用；CLI 回報新狀態 `verified`，不叫 `saved`。見 §4.0 與 §10。
- **計劃提出的內容**：第 4、5 節其餘的行為細節是撰寫計劃時提出的設計，使用者沒有逐項確認。其中會改變行為的部分，在計劃的 GOALS 列為 P8、P9、P13，使用者可以在啟動前否決。
- 狀態：**合併與存檔語意已決定，尚未實作**。實作排在計劃 `harness/plans/2026-11-19-repo-debt-cleanup/` 的 C5 階段。
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
   - **DOI 記錄**：再向 doi.org 取一次 BibTeX（`fetch_bibtex`，`service.py:332`），用 pybtex 解析（`parse_canonical_bibtex`）。BibTeX 沒有 DOI 時補上。
     - BibTeX 的 DOI 與 `record.doi` 不一致時，判為 `verification_failed / bibtex_doi_mismatch`。
     - 注意 `record.doi` 不是被要求的 DOI，而是 doi.org CSL-JSON 回應中的 DOI：`providers/doi_org.py::parse_csl` 取 `canonicalize_doi(payload["DOI"])`，沒有時才沿用被要求的 DOI。
     - 所以這個檢查比的是「doi.org 對同一 DOI 給的兩種格式（CSL 與 BibTeX）是否一致」，不是「回應是否符合被要求的 DOI」。
     - provenance 字串是 `fresh-resolution+doi.org-csl+bibtex`。
   - **權威記錄**（arXiv API、`proceedings.neurips.cc`）：`authority.export_bibtex` 以 pybtex 產生 BibTeX 再解析驗證。失敗判為 `verification_failed / authority_bibtex_invalid`。
3. `write_identity_bundle` 寫出 bundle。若同一 identity 的 bundle 已存在，驗證後重用，狀態是 `reused`。bundle 衝突或寫入失敗判為 `storage_failed`（`bundle_conflict`、`source_id_collision`、`write_failed`）。
4. 建立 `SaveReceipt`，其中 `bundle_path` 是 bundle 目錄，然後 `registry.register(ref, receipt=receipt)`。
5. 只有桌面專案（`library_path` 不為 None）會執行 `_link_library`，把 CSL 項目併入書目庫，結果記在每筆的 `bibliography` 連結（`added`／`existing`／`failed`）。**書目庫失敗不改變 bundle 的 `saved`／`reused` 結果**（INV-032 的一部分）。

### 2.3 bundle 實際被誰用到

- production 唯一讀回 bundle 的地方是 `storage._find_existing`，用來判斷能不能重用（`reused`）。
- 「這個來源在對話中可不可以引用」**不靠 bundle**。可引用性來自記憶體內的 `SourceRegistry`。`CitationSessionPolicy` 每個 Citation task 都重建 service 與 registry，`SKILL.md:145-147` 也寫明後續 task 必須重新存檔或重用才能取得新的信任 receipt。
- 書目庫 `references.json` 的內容由 CSL 產生（`CitationService._csl_item`），與 BibTeX 無關。
- 因此 BibTeX 鏈（第二次 doi.org 請求、pybtex 解析、`reference.bib`）只有兩個作用：
  1. 產出一個沒有人讀的 `reference.bib`；
  2. 附帶做了上面說的「CSL 與 BibTeX 的 DOI 交叉比對」，以及 pybtex 對欄位完整性的解析檢查。
- **更正**：稽核 S105 寫「整條 BibTeX 鏈只為產出 `reference.bib`」，漏了第 2 點。這是撰寫計劃時讀碼發現的。

### 2.4 磁碟上的現況（2026-11-19）

`/home/minervamuses/research-agent-workspace/cite/` 底下只有一個 bundle `Attention_Is_All_You_Need--e0b4220861eb/`（2026-11-07，引用面板驗收時留下）與 `.locks/`。`.gitignore` 有 `/cite/` 規則，所以這些檔案沒有被追蹤。

---

## 3. 決定的內容

**書目庫成為唯一的儲存。receipt 只是記憶體內的信任 token。CLI 不再存檔。**

稽核列出的另一個選項是「維持兩套儲存，只刪 v1 bundle 讀取器」（S106），沒有被採用。

---

## 4. 合併後的行為

這一節是計劃 C5 的驗收依據。「計劃設計」是撰寫計劃時的預定做法：執行者可以調整實作細節，但要達到同樣的可觀察結果，並在 build-log 記錄差異。

### 4.0 存檔的成功語意（使用者決定，GOALS U13；2026-11-20 改寫）

原則：**狀態只描述實際發生的事**。合併前，bundle 寫入失敗回報 `storage_failed`，而且因為登記與 bundle 寫入在同一個 `try` 裡，該筆也不可引用。合併後書目庫是唯一的持久化，所以書目庫寫入失敗必須回到同樣的語意，不可再報 `saved`。

**狀態值**

| 狀態 | 意思 | 可引用 | 出現在 |
|---|---|---|---|
| `saved` | 新加入書目庫，而且寫入成功 | 是 | 桌面 |
| `reused` | 書目庫原本就有同一 identity（DOI、arXiv ID 或 NeurIPS 官方網址），或同一批次較早一筆剛成功加入 | 是，用既有 key | 桌面 |
| `storage_failed` | 書目庫合併被拒或寫入失敗；reason 是書目庫的錯誤碼 | **否** | 桌面 |
| `verified` | 驗證成功，只在這次 task 可引用，沒有寫到磁碟 | 是，只限當次 task | CLI |
| `identity_conflict`（reason `registry_conflict`） | 同一 source ID 已屬於另一個 identity（GOALS P13） | 否 | 兩者 |

其餘失敗狀態（`provider_failed`、`verification_failed` 等）不變。

**桌面的順序**

1. 解析與驗證，不寫任何檔案。
2. 驗證成功的每筆建立 `SourceRef` 與 `SaveReceipt`，**先不登記**；registry 衝突在這裡就判定（P13），該筆不進入書目庫。
3. 其餘各筆以一次 `_link_library` 合併並寫入書目庫。
4. 依每筆的實際結果決定狀態：新加入而且寫入成功是 `saved`；原本就有是 `reused`；合併被拒或寫入失敗是 `storage_failed`。只有 `saved`、`reused` 登記到 registry。
5. **同一批次的重複作品**：第一筆決定結果；之後同一作品的各筆，在第一筆是 `saved` 時報 `reused` 並共用 key，在第一筆是 `storage_failed` 時同樣是 `storage_failed`。現行 `_link_library` 會把「同批次較早一筆剛加入記憶體」的作品報成 `existing`，即使之後整批寫入失敗；合併後不可再這樣回報。

**CLI**：解析與驗證後，registry 檢查通過就登記，狀態一律是 `verified`，沒有 bibliography 連結。同一 task 存同一作品兩次，兩次都是 `verified`。

**計數**：`CitationSaveMetrics` 新增 `verified_count`；`new_saved_count` 只算 `saved`；`reused_count` 只算 `reused`；其餘狀態都算 `failed_count`。

**工具結果**：`storage_failed` 要明說沒有存檔、這次不可引用、原因與書目庫路徑，並建議重試；`verified` 要明說只在這次對話可引用、沒有寫到磁碟。這樣結構化的狀態本身就是誠實的，不必靠附加的提示詞去更正一個寫著 `saved` 的欄位。

### 4.1 桌面專案（有書目庫）

- 存檔唯一的寫入是把 CSL 項目併入 `references.json`。不再建立 `cite/`，也不再寫 `reference.bib` 或 `citation.json`。
- 書目庫的錯誤碼（`LibraryError.code`）改為 `storage_failed` 項目本身的 reason code，不再放在 `bibliography` 連結上。bundle 的 `bundle_conflict`、`source_id_collision`、`write_failed` 消失。
- 引用面板的「以 DOI／arXiv ID 加入」（`bibliography.add`）走同一條路，只是不再產生 bundle。它現在以 `link.key` 判斷成功（`service.py` 約 2420 行）；合併後成功仍回傳 key，`storage_failed` 則回報失敗並附 reason。
- 存檔的核准對話框（operation `citation.save`）目前的 target 是 bundle 輸出目錄（`service.py:2408-2410`、`:2772-2784`），之後改成書目庫路徑。
- 若桌面在沒有書目庫的狀態下仍可能觸發這個核准（`library_path` 為 `None`，現在的程式有處理這個分支），target 要寫明「不寫入磁碟」。C5 要先確認這個分支是否還會被走到；走不到就刪除。

### 4.2 CLI（沒有書目庫）

- `/citation` 的 `search`、`sources`、`source`、`explain` 不變。
- `save` 照常解析、驗證與登記，所以這次對話中可以引用並渲染參考文獻。狀態是 `verified`，不是 `saved`（§4.0）。
- **不寫入任何檔案**，`bibliography` 一律是 `null`，工具結果要明說。
- 以前在 CLI 存過的 bundle 不會被讀回。跨 session 的 `reused` 在 CLI 消失。

### 4.3 型別與資料格式

- `SaveReceipt` 移除 `bundle_path`。持久化位置與 key 由 `BibliographyLink`（status、path、key）表達；它只剩 `added`、`existing` 兩種狀態，`failed` 與 `reason_code` 移除，失敗改由項目的 `storage_failed` 表達。
- `SaveItemStatus` 新增 `verified`。有 receipt ⇔ 狀態是 `saved`、`reused` 或 `verified`。
- `CitationSaveMetrics` 新增 `verified_count`，turn trace 的紀錄多一個鍵。
- 工具 artifact `citation_save_batch` 的 schema 版本從 2 升為 3（`SAVE_BATCH_SCHEMA_VERSION`）。這個 artifact 只在當次回合內被 `CitationSessionPolicy.save_metrics` 與 `observability` 讀取；C5 執行時要確認它沒有被寫進對話 JSON。若有寫入，先停下來記錄，不可讓舊回合無法讀取。
- `types.py` 的 `PERSIST_SCHEMA_VERSION`、`BUNDLE_SCHEMA_V2`、`SUPPORTED_PERSIST_SCHEMA_VERSIONS`，以及只為 v1 bundle 存在的 `identity_verified` 判斷，隨 bundle 一起移除。是否還有其他用途，執行時以 grep 確認。

### 4.4 設定、診斷與保護目錄（GOALS P9）

這些設定與欄位只用來指定或顯示 bundle 目錄，沒有 bundle 之後就沒有用途。

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
2. **DOI identity 照現在的方式決定**：identity 是 doi.org CSL 回應中的 DOI，沒有時用被要求的 DOI（`parse_csl`），alias DOI 因此被正規化成主要 DOI。
   - 計劃**不**新增「回應的 DOI 必須等於被要求的 DOI」的檢查。這個檢查現在不存在，加上去會拒絕合法的 alias DOI。
   - 隨 BibTeX 消失的「CSL 與 BibTeX 的 DOI 交叉比對」也不以其他方式補回（GOALS P8），理由與影響見 6.1。
3. **權威記錄的最低欄位要求**：`export_bibtex` 與 `parse_canonical_bibtex` 會拒絕某些不完整的記錄（例如缺標題）。C5 要列出這些拒絕條件，逐條確認在 resolution、`csl_from_authority` 或書目庫合併中已有對應檢查；沒有的話，把該條件改成對 CSL 項目的檢查，不要直接丟掉。DOI 記錄的 BibTeX 欄位解析檢查也照同樣方式對照。
4. **書目庫合併規則**（INV-032）：保留既有條目、key 與 JSON 排版；拒絕無法重現的排版；寫入前重新比對 fingerprint；只用 atomic replace。INV-032 原本的「書目庫失敗不改變存檔狀態」由 §4.0 取代：桌面端書目庫失敗就是 `storage_failed`，不可引用。
5. **同一 identity 不重複加入**：與現在 `library.merge` 的 `existing` 判斷相同。

---

## 6. 失去或改變的東西

### 6.1 功能

- CLI 不再產生任何存檔，也就是稽核所說的「CLI 失去單獨存檔的能力」。
- 不再產生 `reference.bib`。目前沒有程式或文件流程讀取它。需要 BibTeX 時，之後應從書目庫匯出，而不是恢復 bundle。
- 不再比對「doi.org 給同一 DOI 的 CSL 與 BibTeX 兩種格式是否一致」（GOALS P8）。
  - 這個檢查只會在 doi.org 自己給出前後矛盾的兩份資料時失敗。identity 本來就取自 CSL，書目庫內容也只來自 CSL，所以移除它不影響「存進書目庫的是哪一筆作品」。
  - 但它是驗證管線中一個獨立的第二份證據。若論文要把「交叉比對兩種格式」列為驗證步驟，就不能移除；這時應否決 P8，改以 CSL 之外的另一個來源（例如 Crossref 或 DataCite 的記錄）做比對，而不是恢復 BibTeX。
- bundle 的 `citation.json` 原本保存每次存檔的來龍去脈：agent 當時的 intent、resolution 的記錄來源、provider record ID、版本種類與決策 reason code。**合併後這些不再落地。** 診斷 log 仍保留每筆的 batch ID、index、status 與 reason code（`service.py` 的 `citation save batch … item …` INFO 行），但沒有 intent 與 resolution 細節。

### 6.2 對論文研究的影響

agent 的設計選擇同時是實驗條件。這次合併會改變：

1. **驗證管線**：每筆 DOI 存檔少一個獨立 artifact 的檢查（BibTeX），也少一次 doi.org 請求。CSL 已在 resolution 階段取得並快取 24 小時，所以存檔階段不再發出額外請求。
2. **失敗類別與狀態**：`bibtex_lookup_*`、`bibtex_doi_mismatch`、`authority_bibtex_invalid` 不會再出現。`storage_failed` 的 reason 從 bundle 的錯誤碼改為書目庫的錯誤碼；registry 衝突改報 `identity_conflict`。CLI 的成功狀態從 `saved` 改為 `verified`，存檔計數多了 `verified_count`。C5 若把 BibTeX 的欄位檢查搬到 CSL（見 5.3），被搬過去的檢查會產生自己的 reason code。
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
- **INV-032**：合併規則不變；「書目庫失敗不改變存檔結果」改為「桌面端書目庫失敗即 `storage_failed`、不可引用」（§4.0）。
- **ASM-014**（模型誇大存檔結果）：存檔狀態本身已誠實，風險描述要更新。
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

---

## 10. 修訂紀錄

### 2026-11-20：存檔成功語意（GOALS U13，取代 P7）

- **改了什麼**：§4.0 整節改寫；§4.1、§4.2、§4.3、§5.4、§6.2、§8 中與存檔狀態有關的句子同步修改。
- **原本的設計（P7）**：可引用性只看驗證結果；書目庫寫入失敗時，狀態仍是 `saved`，只有 `bibliography` 連結是 `failed`；CLI 也回報 `saved`；以「書目庫或 registry 原本有沒有這筆」決定 `saved`／`reused`；不新增狀態值，理由是不改變存檔計數的語意。
- **為什麼不成立**：
  - 合併前，`storage_failed` 代表「沒有寫入，而且不可引用」，因為 `registry.register` 與 bundle 寫入在同一個 `try` 裡（`skills/citation/service.py` 約 390–413 行）。INV-032 的「書目庫失敗不改變存檔結果」能成立，前提是 bundle 已經寫入。合併後書目庫是唯一的持久化，P7 等於把「沒有存到任何地方」報成 `saved`。
  - CLI 什麼都沒寫，也報 `saved`。名稱保留了，但 `saved` 與 `new_saved_count` 指的事實已經變了。
  - 桌面的 `document_edit` 本來就拒絕不在書目庫的 key，所以 P7 會造成「聊天裡可引用、插入文件時被拒」的分裂。
  - 依「原本有沒有」決定狀態時，同一批次的重複作品會被報成兩筆 `saved`；而現行 `_link_library` 在整批寫入失敗時，仍把同批次較早加入的作品報成 `existing`。
- **來源**：使用者 2026-11-20 轉來的人工審查討論（「一篇文獻寫入失敗，卻回報 `saved`；同批重複 DOI 也可能誤報｜必修」），以及當天以選項確認「A：不可引用」。另一個選項「B：狀態是 `storage_failed`，但當次對話仍可引用」沒有被採用。
- **對論文評估的影響**：C5 本來就是評估的分界 commit（§6.2）。這次修訂讓分界兩側的差異多了狀態值 `verified`、計數 `verified_count`，以及 `storage_failed` 的 reason 來源改變。
