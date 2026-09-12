# Issue 09 — 可重用提示

## 啟動／續作（Start / Resume）

~~~text
處理 issue/issue_09 的 Thinking Effort 計劃。先讀全部適用 AGENTS.md，再讀
issue/issue_09/GOALS.md、issue/issue_09/PLANS.md、issue/issue_09/build-log.md。
檢查 GOALS 產品決策及 PLANS 啟動門檻是否已由使用者明確滿足。
未滿足時只指出缺少的決策／具體授權並停止實作；本提示不授權代選設定。

門檻滿足後，以 build-log 的狀態與 PLANS 依賴選出第一個尚未 Complete
且前置 phases 都 Complete 的階段。讀相應 phases/ 檔、已存在且相關的
context/、code_review/、live code/tests。不依賴對話記憶或另一份 current-phase 指標。

先唯讀 preflight：核對 Linux、Conda app、Git worktree、前階段證據、
本階段 scope／non-goals／checks／stop conditions；保留先前使用者工作。
前置證據不足則於 build-log 標 Blocked 並記錄原因。

依 PLANS 自主模式，只實作當前階段；需要時先以最小 failing check 確認差異，
完成最小修正並執行必要 focused／broader checks 與 acceptance。
Required failure 或 unverified evidence 必須先處理，不開始 dependent phase。
兩次 focused attempt 失敗或一次 expensive attempt 無效依 PLANS 停止。

將 exact commands、觀察結果、失敗／限制及 acceptance→evidence 寫入
issue/issue_09/build-log.md。重大發現才建 context，真 review 才建 code_review。
新證據否定後續路線時，先修訂 PLANS 與受影響未開始 phase，保留完成／失敗歷史，
不得藉修訂擴權。繼續下一個 eligible phase，直到整體完成或觸發停止條件。
本次 authoring 的 commit/push 不構成後續實作的 Git／外部／付費操作授權。
~~~

## 執行單一階段（Execute One Phase）

~~~text
只執行 issue/issue_09 中我指定的一個階段。先遵循本檔 Start / Resume 的讀取、
產品決策與授權檢查；若未指定，依 PLANS 和 build-log 選首個 eligible phase。
確認 prerequisites Complete，唯讀 preflight 後僅改核准 scope，完成必要驗證、
實際證據及重大 context。遇 blocker 如實記錄。結束後不開始下一階段。
~~~

## 驗證／審查（Verify / Review）

~~~text
唯讀審查 issue/issue_09 中我指定的階段，未指定則檢查 bundle 現有進度。
讀 AGENTS、GOALS、PLANS、build-log、相關 phases/context 及實際 diff。
逐項把 acceptance 對到 observed evidence，核對下一回合生效、model cache、
workflow/effort 區別、保存邊界、CLI/GUI 與 Python/TS/Rust 一致性。
不把 source 字串、fixture 模擬、SDK 建構或過往敘述當真實 GUI/provider 證據。
依授權跑最小必要離線檢查，回報 actionable findings、限制與解除門檻。
若此次明確要求保存 review 才寫 code_review，不自行改實作。
~~~

## 定案或矛盾證據後修訂計劃

~~~text
僅修訂 issue/issue_09。讀 AGENTS、GOALS、PLANS、build-log、相關 phases 與 live code。
把使用者明確產品答案寫入 GOALS，沒有答案的繼續未決。
依新決策／證據凍結最小 scope、精確契約與可驗收結果，修訂 PLANS 和受影響未開始
phases；保留已完成／失敗歷史。需要 public protocol/schema 等批准時呈現具體
差異、必要性及成本，不把規劃要求當作實作授權。本次不實作。
~~~

## 最終整合核對

~~~text
對照 issue/issue_09/GOALS.md、PLANS.md、兩個 phase files 與 build-log.md，
逐項確認成功條件。重用仍有效的 observed checks，只針對新變更／未解問題
補最小驗證，不無故重跑完整 suite 或 live provider。
檢查 actual diff、Linux Desktop journey、離線 request/workflow 結果與資料相容。
列出 changed files、commands、成功／失敗／限制；必要證據缺少不得宣告完成。
完成即停止，不自行 commit/push/deploy。
~~~
