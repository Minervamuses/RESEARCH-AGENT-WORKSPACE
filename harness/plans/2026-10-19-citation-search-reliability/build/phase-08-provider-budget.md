# P8 — Citation provider 等待與不完整結果

目標 G8；前提 P1、P4 完成，並有能辨識 Citation/provider 執行的資料；執行者自主完成診斷與必要修正。共通 [政策](../PLANS.md)／[目標](../GOALS.md)。

## 問題與既有行為

`skills/citation/service.py:55–113` gather 等全部 provider；`providers/net.py:324–420` 每次請求有分類重試，成功快取不消除新 query 對故障來源的等待。現有工具已會顯示 provider states／search incomplete；不是從零新增失敗語義。10/19 那筆未呼叫 Citation，不用本機制解釋它。

## 步驟

P8-S1：由已選定的正常 Citation trace 分辨各 provider 的 limiter queue、HTTP attempt、backoff、成功 cache hit、總經過時間與跨 query 重複失敗。若 P4 只能看到工具總時間，最小地在現有 service/net 邊界補細分；不預建全域監控。

P8-S2：依代表資料自行選定並在 log 記錄「整次 search 時間預算」「同回合同故障 provider 剩餘重試預算」「部分結果何時可交付」的具體政策。分清全 provider 失敗、部分失敗、成功零命中；不把 deadline 到期視為零命中。規劃時不虛構數值；執行者選保守有限值，記錄依據後離線驗證，不等待使用者逐項決策。若需回合內狀態，指定既有 turn/session owner 及重置點；不得擴成跨回合 circuit-breaker／持久 cache。

P8-S3（政策已記錄後）：只處理已證明的等待路徑。先評估沿用 gather 加有界單來源等待是否足夠；確有必要改成 wait／as_completed 時，記錄較小做法不足的證據與取消清理方案，依本階段已列明的局部等待安排實作，不另建 worker／queue／通用並行框架。取消／到期要真的清理 task，無洩漏；保留成功來源、來源狀態與摘要 provenance。不要更改 save／DOI resolution 的重試政策來修 search。

## 驗收

使用既有 fake provider、假 clock／sleep，快成功來源＋慢／故障來源：依接受的政策返回快來源候選，明示缺哪個來源及原因。新 query 在同一 turn 不重開超出核定預算的同故障來源等待；下一 turn 按接受政策恢復。全成功零命中、全失敗、成功 cache hit、外部取消皆仍能辨識，無 dangling task。

重用 `tests/test_citation_hub.py`（含 surviving one-provider failure）、`tests/test_citation_net.py`、`tests/test_citation_workflow_tool.py`，在 app/ 跑選定 module 的 `poetry run pytest ... -q`。不跑真 Retry-After 等待。

交付為可檢查的 provider 分段與接受政策；選定實作後還需部分結果／清理反例和同案例等待改善。有充分資料顯示現有等待可接受且不需改動時，明記判定；資料不足或必需驗收未通過則記 Blocked／待驗並繼續獨立工作，不能以 defer 冒充完成或宣稱搜尋已完整。
