# P7 — 以引擎與瀏覽器證據選定搜尋改善

目標 G7；前提 P1–P4 完成、新資料與後續範圍核准。共通 [政策](../PLANS.md)／[目標](../GOALS.md)，外部交付沿用 [P2](phase-02-search-results.md)。

## 已知與待回答

外部 search-engine.ts:35–53 依 Bing→Brave→DDG，單 approach timeout 不是整次 deadline；120 起／216 起有各次 attempt 的 browser launch／close。1025–1032 的 keyword 處理會移除中文；1072 附近有未做 word boundary 的詞彙懲罰。這些是機制，不是本機五分鐘耗時占比。

P7-S1：對 P4 指出的代表 query，記錄引擎開始／結束、browser launch／close、attempt／fallback 原因、返回候選數與現有品質分數。若進程／瀏覽器時間不可分，先補最小局部診斷，不同時優化。新量測必須維持 P2 的結果保留契約。

## 出口與互斥的單變數步驟

- 若 browser 開關有實質可減成本，先提**一個**最小共用生命週期方案，決定 owner／關閉與失敗恢復，再核准是否值得；不直接建 pool。
- 若多引擎加內部 retry 使整次等待超出可接受範圍，提出整次搜尋預算，由使用者確認延遲與完整性取捨；到期保留已取得 best、標明有限搜尋範圍，取消未完工作且關閉資源。timeout wrapper 只提早 return 卻讓 browser 繼續跑不算完成。
- 若不合理分數引發 fallback，先保留一個中文 query、一個被懲罰字串誤傷的合理學術 query 及其既得結果，確認預期；再改最小 token／詞界判定。不能只降低 threshold，也不能用「有摘要」代替相關性。

P7-S2：在上述選中一條有證據路線後，更新具體寫入檔案與驗收；第二條改善需新的證據與當次授權，不把三者全實作。public tool 輸出若需新增 incomplete 欄位，先列出 schema／consumer 影響並核准，不偷改 MCP protocol。

P7-S3：保留 P2 四情境、全無結果、例外／取消等直接回歸；若改 heuristic，檢查中文／學術例與明顯不相關例，排除改善召回卻大量誤收；若改 lifecycle/deadline，驗證 pending work 真正被收尾。採既有 Node/assert，不跑未核實的 live tests。

交付需包含同案例前後分段時間與結果品質。若只有離線控制流程改善，明記未證實真實速度；不把 P6 echo 差額套入本階段。
