# C5-S2 先補保證，再刪 BibTeX

- **日期**：2026-11-22
- **C5-S1 的結論**：沒有「無人負責」的欄位要求（`evidence/C5-S1/guarantee-map.md` 第 2 節），所以本步只加測試 (b)、(c)，不新增產品檢查。

## 新增的測試（`app/tests/test_citation_save_outcomes.py`）

以桌面模式（有專案書目庫）存檔，成功狀態在刪除 BibTeX 前後都是 `saved`，斷言不依賴 bundle、sidecar 或 BibTeX：

| 測試 | 規格 | 斷言 |
|---|---|---|
| `test_normal_doi_and_arxiv_saves_succeed` | (b) 正常的 DOI 與 arXiv 存檔照常成功 | 兩筆 `saved`／`saved_new`；identity 與標題正確；registry 中可引用，`[[cite:…]]` 通過 gate；書目庫各多一筆。 |
| `test_alias_doi_saves_the_doi_org_primary_identity` | (c) doi.org 回應的 DOI 與被要求的不同 | 狀態 `saved`；receipt 的 DOI 與 identity 是回應中的主要 DOI；可引用；書目庫條目的 `DOI` 是主要 DOI。 |

(a)（缺必要欄位的記錄被拒絕）不新增：C5-S1 確認 BibTeX 從未拒絕缺欄位的記錄，權威記錄的欄位要求由 adapter 負責，既有的 `test_citation_authority.py`（`test_neurips_lookup_abstains_unless_the_official_pages_agree`、`test_missing_exact_arxiv_authority_is_not_found` 等）已覆蓋。

## 決策紀錄更正

依 GOALS「限制」的例外規則，在 `note/20261119/citation_storage_unification_decision.md` 末尾追加「執行時更正（2026-11-22、C5-S2）」：§5 第 3 點舉的「例如缺標題」與程式事實不符，最低欄位要求由權威 adapter 負責。既有段落未改寫。

## 檢查結果

- 新測試在**尚未刪除** BibTeX 的狀態下通過：`pytest tests/test_citation_save_outcomes.py`（16 passed）。
- `pytest tests/test_citation_*.py`：557 passed。
