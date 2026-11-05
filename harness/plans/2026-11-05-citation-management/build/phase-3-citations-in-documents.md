# C3 正文引用：解析、檢查與 Agent 接線

- **後置條件**：Python 能從 Markdown 與 LaTeX 文字中找出所有引用 key 及其位置；能對「目前文件 + 書目」產生完整性報告；Agent 在桌面專案中能唯讀查詢書目；`document_edit` 拒絕新引入的未知 key。
- **目標**：CG2。決策 D1、D6；假設 A4、A9。
- **相依**：C2（書目庫 API）。C3-S1 的 Pandoc 交叉比對需要 C1 的 Pandoc。

## 介面（擬定）

- `app/skills/citation/citekeys.py`：`find_citations(text, fmt) -> list[CitationUse]`，每筆含 key、UTF-16 起訖、行號、所屬引用群組。`fmt` 為 `markdown` 或 `latex`，由副檔名決定。
- `app/skills/citation/integrity.py`：`inspect(text, fmt, library, bundle_lookup) -> Report`。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| C3-S1 | **解析器**。Markdown 依 Pandoc 引用語法：`[@a]`、`[@a; @b]`、`[see @a, p. 33]`、`[-@a]`、行文中的 `@a`、`@{a.b}`；key 規則依 Pandoc（開頭為字母、數字或 `_`，中間可含 `:.#$%&-+?<>~/`，結尾標點不算 key）；`@` 前面是英數字時不是引用（例如 email）；略過 code fence 與行內 code。LaTeX：`\cite`、`\citep`、`\citet`、`\parencite`、`\textcite`、`\autocite`、`\nocite` 及星號版本，可有一到兩個 `[...]` 選項，`{a,b}` 多 key；略過 `%` 註解。位置用 UTF-16，與文件編輯器一致 | 單元測試涵蓋上列每種語法、email、code、註解、全形標點與中文前後文、emoji 造成的 UTF-16 位移。**交叉比對**：對合成語料與論文 `proposal.md` 的 `$TMPDIR` 複本（`git -C /home/minervamuses/論文 show HEAD:proposal.md`），以 `pandoc -f markdown -t json` 取出所有 Cite 節點的 key 序列，必須與解析器的 key 序列完全相同；結果（數量與差異，不含正文）存 `evidence/C3-S1/` |
| C3-S2 | **完整性報告**。輸出：書目條目清單（key、作者、年份、標題、DOI、驗證狀態）；每個 key 的使用位置與次數；首次出現順序；找不到的 key（含位置）；本文件未引用的條目；DOI 重複的條目組；書目本身的錯誤（malformed、格式不明）。驗證狀態：書目條目的 DOI 或 arXiv ID 在 citation 輸出目錄有有效 bundle（重用 `storage.py` 的既有 bundle 查找）為 `verified`，否則為 `unverified`（手寫條目即屬此類） | 單元測試：缺 key、重複 DOI、手寫條目為 unverified、有 bundle 者為 verified、順序以首次出現為準、書目 malformed 時報告書目錯誤而不拋例外；以論文 `references.json` 與 `proposal.md` 的複本跑一次，記錄條目數、引用數、缺漏數、未引用數於 `evidence/C3-S2/`（只記數量與 key） |
| C3-S3 | **Agent 接線**。新增唯讀工具 `bibliography_lookup`（以文字或 key 查詢，回傳 key、作者、年份、標題、DOI、驗證狀態，最多 20 筆），在桌面專案的 session 中可用。接線要比照 `document_edit` 的三個特例處理，否則工具不是看不到，就是每次呼叫都要求批准：(1) `app/agent/session.py:149-150` 依名稱把 `document_edit` 歸入 family `desktop_document`，`bibliography_lookup` 也要歸入；(2) `session.py:661-663` 在文件回合把 `document_edit` 強制加入 effective tools，`bibliography_lookup` 至少要在文件回合與 `/citation` 回合有效；(3) `app/agent/desktop/service.py:2347` 只對 family `desktop_document` 免批准，其他 family 會走 MCP 批准。實作放在桌面的額外工具清單（`service.py:1389-1393` 傳入 `extra_tools` 處）。不加入 extended thinking 的 proposer 清單（D6）。`document_edit` 在準備候選前，解析 `replacement_text` 中的 key：不在書目、且不在被替換的原範圍文字中出現的 key 視為新引入的未知 key → 回傳 `failed` 與缺少的 key 清單、建議先用 `/citation` 存檔，不產生候選、不發出 `document.proposed`。書目讀不到時，只拒絕引入新 key 的修改。更新文件回合提示文字（`service.py:2840-2853`）與 `app/skills/citation/SKILL.md`：有專案書目時在正文用 key，不自行打出作者年份或編號，不捏造 key | 測試：`bibliography_lookup` 在文件回合可被呼叫且不觸發 `approval.required`；引入未知 key → failed 且沒有候選；已知 key → 正常產生候選；原範圍本來就有的未知 key 保留不擋；沒有新 key 的修改不受書目錯誤影響；`bibliography_lookup` 不在 `FUSION_READ_ONLY_ALLOWLIST`；既有 `test_desktop_document_service.py`、`test_desktop_documents.py`、`test_inline_skills.py`、`test_citation_skill_activation.py` 全部通過 |

## 失敗與恢復

- 解析器與 Pandoc 的交叉比對不一致：以 Pandoc 的結果為準修正解析器；兩次修正後仍有差異，就把差異寫成已知限制（附例子），面板與檢查照常使用。
- Pandoc 尚不可用（C1 阻塞）：交叉比對記為待補，在 C4 開始前補做。

## 交付給後續階段

`find_citations` 與 `inspect` 的輸出格式（C6 的 RPC 直接序列化它們），以及 `bibliography_lookup` 的工具描述。
