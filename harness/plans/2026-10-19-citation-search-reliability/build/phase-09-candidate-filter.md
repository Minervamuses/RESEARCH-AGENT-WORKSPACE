# P9 — 先資格過濾，再截斷候選

目標 G9；無其他階段硬依賴；正常安排在第一批後，若其他項受阻可先用現有 offline fixtures 完成已知正確性修正。無須等待真實延遲排名或使用者選定。共通 [政策](../PLANS.md)／[目標](../GOALS.md)。

## 已證明的資料順序

`skills/citation/service.py:89–113` 合併去重、保留同 DOI 真摘要、排序、ordered[:rows]；`tool.py:331–343` 在 service 返回後才按 year_from/year_to 過濾。`types.py:PublishedDateFilter.admits_year` 已可重用，無需新篩選 framework。

P9-S1：用現有 ProviderRecord fixtures 形成大於 rows 的已取得候選池，讓排序前段含不合年份／未知年份、後段含合格候選；先觀察修復前不足筆數，再驗證正確輸出。這是候選正確性反例，不是 benchmark。

P9-S2：優先只在現有 service 的最終 slice 前套用資格條件，保持先前 DOI 去重／摘要合併與 rank 順序；tool 的本地過濾可留作相同語義防線，避免無關重構。年份條件仍向 provider 傳遞，不因此增加 provider calls 或提高每來源上限。不新增候選 registry／persistent pool。

P9-S3：檢查實際 tool 格式化後候選清單而非只測 service list 長度。若合格數不少於 rows，回 rows 個合格且不重複候選；不足則誠實不足；無年份限制保留原行為；有年份限制時未知年份依現有規則不通過；上下界 inclusive、一邊有界都正確。同 DOI 的真摘要／source URL 不能因移動過濾而丟掉。

排序調整是另一決策：有摘要只代表可評估，不等同相關性；本次預設不變 provider rank 比較、不增加 reranker、不以取得摘要強行升權。若去重勝者的年份 metadata 衝突造成新缺口，記錄一個具體反例再決定，不能順手改整個候選融合。

重用 `tests/test_citation_workflow_tool.py` 年份／摘要／partial failure cases 及 `tests/test_citation_hub.py`，以 fake providers 走真 service＋tool；在 app/ 執行 `poetry run pytest tests/test_citation_workflow_tool.py tests/test_citation_hub.py -q`。不得用只有 FakeService 且完全跳過真合併邏輯的測試當完整證據。

交付為合格候選補位的實際結果及原摘要／來源狀態保留驗證；不據此報告研究時間縮短。
