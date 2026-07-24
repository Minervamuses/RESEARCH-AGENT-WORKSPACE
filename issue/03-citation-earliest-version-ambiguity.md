# Citation `version_kind="earliest"` 的同年與缺日期歧義

## Issue 定位

- 類型：引用版本選擇正確性。
- 優先度：後。
- 是否阻擋 `repair` branch 整併：否；使用者已決定整併後再處理。

## 專案背景

Citation Skill 使用 `WorkIntent` 描述 agent 從對話中選定的作品。`WorkIntent.version_kind` 可指定：

- `published`
- `preprint`
- `repository`
- `repost`
- `earliest`

前四種要求某一類 manifestation；`earliest` 則要求系統在同一作品的多個 manifestation 中找出時間最早者。

相關流程：

1. `app/skills/citation/tool.py` 將 model input 轉成 `WorkIntent`。
2. `app/skills/citation/resolution.py` 向 Crossref、DataCite、OpenAlex 等 provider 取得 `ProviderRecord`。
3. `evaluate_record()` 排除明顯不符合的候選。
4. `decide_resolution()` 對 eligible candidates 排序並選出一筆。
5. `CitationService` 再做權威資料與 BibTeX 驗證後保存。

多數 `ProviderRecord` 目前只保留 `year`，沒有完整發表日期。Provider rank 表示搜尋結果順序或相關性，不代表出版時間。

## 原 annotation

> 這個優先度較後，先合併 branch 後我再來弄。

## 現行問題

當 `version_kind="earliest"` 時，`decide_resolution()` 目前主要按照：

1. 是否缺 year。
2. year 由小到大。
3. score、provider rank 與 provider 名稱；若這些鍵仍相同，則沿用輸入順序。

若候選年份不同，例如 2020 與 2022，可以合理選 2020。

若 preprint 與 published version 都只有 `year=2020`，程式無法從現有資料判斷哪個月份或日期更早，卻仍會用 score/rank 打破平手並回傳 eligible。這等於把「搜尋排序較前」誤當成「時間較早」。

相同問題也會出現在：

- 多個候選都沒有 year。
- online-first 與正式出版落在同一年。
- Repository deposit date、preprint version date 與 publication date 的語意不同。

## 具體重現案例

建立兩個同標題且都能通過 identity comparison 的 records：

- Record A：published，DOI A，year 2020，rank 0。
- Record B：preprint，DOI B，year 2020，rank 1。

以 `WorkIntent(title=<same title>, version_kind="earliest")` 呼叫 `decide_resolution()`。

現況預期：Record A 因 rank 較前被選為 eligible，即使沒有證據證明它較早。

## 期望語意

- `earliest` 是時間主張，必須由時間或明確版本關係證據支持。
- 最早候選無法唯一判定時應回傳 `ambiguous`，並提供 alternatives 讓 agent 詢問使用者或補查。
- Provider rank、搜尋 relevance 或預設 primary location 不得單獨作為 earliest 證據。

## 後續設計問題

接手 Agent 需先決定哪些日期可互相比較：

- Crossref published-online／published-print。
- DataCite created／published／registered。
- arXiv submitted date 與版本日期。
- OpenAlex location／version metadata。
- 關係欄位，例如 `is-preprint-of`、`is-version-of`。

如果資料模型暫時不擴充完整日期，最安全的第一步是：同一最小 year 有兩個以上不同 canonical identities 時 fail closed 為 ambiguity。

## 驗收條件

- 不同年份候選仍選較小年份。
- 同年、不同 DOI 且沒有更細時間證據時回傳 ambiguity。
- 所有候選都缺年份時不得靜默選擇。
- 有可靠完整日期時能選出較早者。
- 有明確 manifestation relation 時，選擇遵守 relation 與日期證據。
- Alternatives 保留足夠 title、year、version kind 與 identifier 供 agent 說明。

## 主要參考檔案

- `app/skills/citation/resolution.py`
- `app/skills/citation/providers/base.py`
- `app/skills/citation/types.py`
- `app/skills/citation/service.py`
- `app/tests/test_citation_resolution.py`
- `app/tests/test_citation_work_resolver.py`
