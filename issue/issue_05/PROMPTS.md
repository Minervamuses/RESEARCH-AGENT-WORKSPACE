# Issue 05 — Citation 保存結果回報：續作指令

## Start / Resume — 啟動與續作

以下指令可直接複製使用；送出後才授權執行。

> 執行 `issue/issue_05` 的計劃。先閱讀所有 applicable `AGENTS.md`、
> `issue/issue_05/GOALS.md`、`issue/issue_05/PLANS.md`、
> `issue/issue_05/build-log.md`，以及相關的既有 context／code_review。
> 根據 log 的實際狀態與 PLANS 的依賴順序，選擇第一個未 Complete 且
> prerequisites 均已滿足的 phase，讀取其 phases/ 檔案及相關 live code/tests。
> 依 PLANS 核對 issue 04 的外部依賴；沒有 eligible phase 時記錄 blocker，
> 回報所缺 evidence／決定，不自行實作其他 issue。
>
> 每個 eligible phase 都先完成 read-only preflight：確認 root、Linux runtime、
> Conda 工具、Git diff、既有工作與證據；重述 scope、non-goals、planned checks
> 和 stop conditions。先核對被修改中的檔案，不覆寫其他工作。
> 只實作該 phase；適用時做最小 red／green，若 characterization 已通過則
> 不製造 production change。執行該 phase 所有 required checks；
> 必要檢查失敗或未驗證時不得完成或進入後續工作，先依因果證據修正，
> 並遵守 PLANS 的失敗次數上限。
>
> 將 exact command、結果、失敗／skipped／unavailable 及 acceptance 對應記入
> `issue/issue_05/build-log.md`，它是唯一 runtime status 來源。
> 只有重大發現才建立／更新 `issue/issue_05/context/`；
> 真實 review 才建立 `issue/issue_05/code_review/`。
> 新證據推翻未開始工作時，先修訂 PLANS 與受影響的 phase 檔，
> 保留已完成與失敗的證據，不把過時計劃當成比 live behavior 更強的事實。
>
> 依 PLANS 的 autonomous authorization envelope 繼續至整體完成或記錄的
> stop condition；不得因一次 focused test 通過就省略 acceptance。
> 不修改 AGENTS.md，不做未授權的 Git mutation、依賴變更、
> 外部／paid／destructive 操作。完成後報告實際檔案、checks 與限制，停止。

## Execute One Phase — 執行單一階段

> 只執行 `issue/issue_05/phases/phase-01-save-result-reporting.md`。
> 先依本檔 Start/Resume 讀取同一組 durable sources，確認
> `issue/issue_05/PLANS.md` 的 dependencies 已有 evidence，
> 再做 read-only preflight。限定本 phase 的授權工作，執行必要驗證，
> 寫入 `issue/issue_05/build-log.md` 與必要重大 context，完成或遇 stop
> condition 即停，不擴張到其他 issue。

## Verify / Review — 驗證或審查

> 審查 `issue/issue_05`：依 GOALS、PLANS、phase acceptance、build-log、
> live diff 及存在的 context，核對 outcome → ToolMessage content →
> model invocation → answer／CLI／history 的證據。
> 特別檢查是否只讀 artifact、fake 是否預寫答案、retry 是否混淆作品與
> request_index、transport success 是否誤當保存成功，以及是否重建全文覆寫層。
> 審查授權只可唯讀，不修改 application code/tests。
> 如需跑 checks，遵守 PLANS 的環境、成本與既有執行次數限制，
> 不為審查無條件重跑完整 suite。將實際 findings 與證據寫入
> `issue/issue_05/code_review/phase-01-save-result-reporting-review.md`，
> 不將作者敘述或 fake-model 結果當成真實 LLM 可靠性保證。

## Repair Plan — 證據矛盾時修訂計劃

> 僅修訂 `issue/issue_05` 計劃：讀 GOALS、PLANS、build-log、phase、
> 重大 context 和 live repository，指出哪項原理解被新證據推翻。
> 保留穩定目標及已完成歷史，只改受影響的 roadmap／未開始 phase，
> active phase 只可在原授權目標內澄清；重大更正在 log 追加記錄。
> 如需變更成果或授權範圍，先取得使用者決定。本次不實作應用程式。

## Final Integration Review — 最終核對

> 依 `issue/issue_05/GOALS.md` 每個成功條件及 PLANS 的整體完成條件，
> 核對 phase 的 exact evidence 是否足夠；必要時執行尚未執行且已授權的
> 檢查，不超出完整 suite 的次數與成本限制。
> 檢查 CLI、history 與真實 fixture bundle 是否對得上該次結果，
> 外部 prerequisites 是否滿足，未驗證限制是否清楚。
> 必要 evidence 缺少時不得標 Complete；不自行加入新 UI 或其他 issue。
