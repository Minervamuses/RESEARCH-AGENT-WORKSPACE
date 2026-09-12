# Retry fixture 的快取邊界

2026-09-12（Asia/Taipei），首次新增 e2e 檢查為 34 passed / 1 failed：
retry 的兩批都是 verification_failed，沒有保存成功。其他三種代表流程通過。

`app/skills/citation/providers/doi_org.py:fetch_bibtex` 在 service 驗證 DOI
之前把 HTTP 200 原始文字存入 24 小時 TTL cache。因此「第一次錯 DOI、
下一次 fetcher 回正確 fixture」不會直接成立：第二次仍取快取。
這是 fixture 假設錯誤，不是 ToolMessage 傳輸失敗。

Active phase 只調整 retry 的失敗安排：第一次 HTTP 503，provider 不快取
HTTP error，service 回 verification_failed / bibtex_lookup_failed；第二次真
service save 再取得既有正確 fixture。Mixed / all-failure 保留錯 DOI。
不清空或停用快取，不修改 production，GOALS 與 acceptance 不變。

離線 fake-model 證據只證明訊息傳遞與整合，並不保證錯 DOI 可立即重試成功，
亦不證明真實 LLM 永不誤報。Exact command / 結果由 build-log 唯一維護。
