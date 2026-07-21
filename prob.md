# 目前問題紀錄

本文件只保留 citation workflow 與 skill runtime 尚未消除的風險。已修復事故與設計演進見 `RETROSPECTIVE.md`。（最近一次更新：2026-07-21。）

## 1. 上游 metadata 無法保證版本關係完整

- Crossref/DataCite 的 relation 是 depositor 提供；存在的關係可當強證據，缺少關係不能證明兩個 DOI 無關。
- OpenAlex 可能把 preprint、accepted manuscript、published version 與後來轉載合併成同一 Work；top-level DOI、year、primary location 都不一定是使用者要引用的 manifestation。
- 現行 resolver 會保留 OpenAlex 的多個 DOI locations，遇到不同或不明版本時 abstain／要求澄清，不會把 top-level DOI 直接升格為答案；代價是 metadata 不完整時可能多問一次或回報 ambiguous。
- publisher version 本來就可能沒有 DOI。系統不得為了產生 BibTeX 而拿相似 preprint DOI 代替；只有 allowlisted authority metadata 可走 trusted non-DOI 保存。

## 2. Provider drift 與查詢成本需要持續監控

- Crossref、DataCite、OpenAlex 的 searchable fields、回傳 shape、rate limit 與排序都可能改變。local contract tests 可鎖住我們的 parser/query builder，但無法取代定期 live probe。
- OpenAlex 搜尋會消耗 credits；identity lookup 採 strict → conditional fallback，最多三次 search。年份漂移或 metadata 缺漏會提高 fallback 次數。
- provider score 不是 identity confidence，也不能跨 provider 比較。現行程式只用它保留來源內排序，最終仍由 title/author/year/version checks 與 doi.org refetch 決定。
- 大型 failure corpus 的 recall、wrong-DOI、wrong-version、abstention 與 latency 門檻仍需持續累積；目前 regression corpus集中保護已知的 AIAYN 多版本、VAE 錯作、DOI alias、特殊字元、空結果與 partial-provider failure。

## 3. DOI alias 與 authoritative lookup 仍依賴上游可用性

- 明確 DOI 直接走 doi.org content negotiation；若回傳 canonical DOI 不同，系統保留原 DOI 為 alias，再用回傳 metadata 驗證作品身分。
- doi.org timeout/rate-limit/invalid response 會 fail closed，不會退回模糊搜尋換一個 DOI。這提高 precision，但上游暫時故障時無法保存。
- 明確 arXiv ID 同樣只走 export.arxiv.org authority；authority record 的 title/author/year 仍須通過本地 identity checks。

## 核心設計結論

- `search` 是探索；`save(WorkIntent)` 才是 verified identity resolution。Web/RAG 可讀內容或提供線索，但不能直接授權 citation identity。
- 模型只需分欄提供 title、authors、year、venue、type 與 identifiers；Crossref、DataCite、OpenAlex 的語法、escaping 與 fallback 由各自 adapter 負責。
- 找不到或版本不明時，可靠輸出是 `not_found`／`ambiguous`，不是猜一個看似合理的 DOI。
- 身分驗證不等於正典性保證；只要 manifestation 仍有多種合理解讀，就必須保留歧義並讓使用者選擇。
