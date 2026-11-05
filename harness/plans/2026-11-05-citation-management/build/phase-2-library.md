# C2 專案書目庫

- **後置條件**：有一個與框架無關的 CSL-JSON 書目庫模組；桌面專案中的 `/citation` 存檔成功時，作品會併入專案書目並取得 key，工具結果回報 key；CLI 行為不變。
- **目標**：CG1。決策 D2、假設 A1、A2、A3；不變條件見 [GOALS](../GOALS.md)。
- **相依**：C1。

## 介面（擬定，執行者可調整名稱，但要在 build-log 記錄最終名稱）

- `app/skills/citation/csl.py`：CSL-JSON 清理與建構。
- `app/skills/citation/library.py`：`load`、`fingerprint`、`generate_key`、`merge`、`write_atomic`，以及書目錯誤類型（`library_malformed`、`library_format_unsupported`、`library_conflict`、`library_write_failed`）。
- `CitationService` 增加可選的書目庫參數；沒有書目庫時行為與現在完全相同。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| C2-S1 | **保留 CSL-JSON**。`fetch_structured` 解析時同時保留清理過的 CSL 物件（快取也存它）：只留 CSL 1.0.2 的書目變數（type、title、container-title、container-title-short、author、editor、issued、volume、issue、page、number、publisher、publisher-place、DOI、URL、ISSN、ISBN、edition、collection-title、version、genre、event-title 等）；人名只留 family、given、literal、suffix、non-dropping-particle、dropping-particle；**一律去掉 abstract**、reference、license、link、funder、assertion、ORCID、affiliation 等。非標準 type 以固定對應表轉成 CSL 1.0.2 type（例如 posted-content → article），對應表寫在程式裡並有測試。arXiv 授權路徑（`authority.py`）以相同欄位建出 CSL 物件（type `article`、URL、`number` 放 arXiv ID）。CSL 物件不寫進 bundle；bundle 格式不變 | 新測試：一份模擬 Crossref 的 payload（含 abstract、reference 清單、ORCID、`<i>` 標題、posted-content type）清理後只剩白名單欄位、沒有 abstract、type 已對應；arXiv 記錄能建出 CSL；既有的 `test_citation_provider_doi_org.py`、`test_citation_authority.py`、`test_citation_storage.py`、`test_citation_save_outcomes.py` 全部通過 |
| C2-S2 | **書目庫模組**。`load` 只接受「物件陣列、每個物件有唯一的字串 `id`」，否則 `library_malformed`，不寫入。排版偵測：依序嘗試 `indent=1`、`2`、`4`、`"\t"`（`ensure_ascii=False`，結尾換行）重新序列化，與原檔逐位元組相同者即為該檔的排版；都不同就 `library_format_unsupported`，不寫入。新檔用 `indent=1`。`generate_key` 依 A3。`merge`：先以正規化 DOI（不分大小寫）找既有條目，再以 arXiv ID 找；找到就重用其 `id`，**完全不改動**既有條目；找不到才在陣列尾端加新條目（`id` = 新 key）。`write_atomic`：讀取時記指紋，寫入前重讀比對，不同就 `library_conflict`；同目錄暫存檔、fsync、`os.replace`、保留權限、fsync 目錄 | 以合成的 fixture（模仿使用者格式：1 空格縮排、含 `–` 等非 ASCII 字元、含手寫的 webpage 與 literal 作者條目）測試：新增一筆後 `git diff --no-index` 式比較只多出尾端一筆；同 DOI 大小寫不同仍重用；撞名得到 `…a`；中文姓得到 `ref…`；格式不明時不寫入；寫入前檔案被改動回 `library_conflict` 且檔案不變；檔案不存在時建立新檔 |
| C2-S3 | **接上存檔流程與桌面專案**。`CitationService` 對 saved/reused 的每一項呼叫 `merge`，在該項結果中加上書目結果（`added`/`existing` 加 key，或失敗代碼）；工具輸出文字顯示 key 與書目路徑，提示 Agent 用 `[@key]`（Markdown）或 `\cite{key}`（LaTeX）。書目寫入失敗不改變 bundle 的 saved/reused 狀態，只回報書目失敗。桌面：`catalog.py` 的 metadata 驗證接受可選鍵 `bibliography`（專案內相對路徑、副檔名 `.json`、不得跳出根目錄）與 `citationStyle`（非空字串，格式在 C6 驗證）；其他未知鍵仍判 malformed；`initialize_project` 不變（新專案仍只寫兩個鍵）。桌面建立 session 時把專案書目路徑傳給 citation 服務：服務是在 `app/agent/skills/citation/session_policy.py:41` 延遲建立的，路徑經由 `CitationSessionPolicy`（建構參數或設定）傳入；`app/agent/session.py` 若必須改，只做傳遞，不放書目邏輯；`citation.save` 的批准內容加上書目路徑。CLI 不傳書目，行為不變 | 新測試：桌面專案（暫存目錄，含 `RESEARCH.md` 與合成書目）以假的 provider 存一個 DOI → 書目多一筆、工具輸出含 key；再存一次 → 書目不變、同 key；`bibliography` 指到根目錄外 → malformed；含未知鍵 → 仍 malformed；CLI 路徑存檔不產生任何書目檔；批准內容含書目路徑。focused：所有 `test_citation_*.py`、`test_desktop_*.py` |

每一步各自 commit，例如 `feat(citation): keep sanitized CSL-JSON from verification [C2-S1]`。

## 失敗與恢復

- 若存檔流程中有路徑拿不到 CSL（例如某種描述式存檔），就以該路徑已驗證的欄位建出最小 CSL 物件，並在測試中涵蓋；不得從搜尋結果或模型提供的欄位補資料。
- 若 metadata 新鍵與既有 `submittedContext` 的規則雜湊互相影響，記錄並在 C6-S2 處理（PLANS 風險 R5）。

## 交付給後續階段

書目庫 API、key 規則、書目結果的欄位名稱，以及 metadata 新鍵的驗證規則。
