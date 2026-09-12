# Issue 05 — Citation 保存結果回報：執行紀錄

本檔是唯一 runtime phase status 與實際 implementation／verification evidence
來源。未來步驟在 phase 檔；本檔只記錄已發生的事。

## Phase Summary

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Save result reporting | Not started | — | — | — | 啟動時依 PLANS 核對 issue 04 完成證據 |

使用 `Not started`、`In progress`、`Blocked`、`Complete`。
必要 acceptance 與 verification 均有實際證據才可標 Complete。

## Evidence Rules

- 記錄 exact command／procedure、runtime／working directory、結果及 acceptance
  對應；分清 observed、historical、planned，不用 skipped 代替 pass。
- 記錄實際變更、重要失敗與未執行原因；新測試直接通過時如實記錄
  characterization，不虛構 red／修正。
- 模型輸入證據必須指出讀取 ToolMessage content 的位置及其先後順序；
  CLI evidence 指向本次實際擷取輸出，不只記 metrics。
- 大型輸出用連結，避免完整 payload、secrets 或 routine narration。
- 重大發現才寫 context，真實 review 才寫 review。矛盾 evidence 都保留，
  釐清前不得 Complete；錯誤紀錄以 append-only correction 修正。

## Activity Log

尚未開始實作，沒有 application tests、live provider 或保存流程的執行證據。
本次只撰寫計劃；authoring validator 結果不代表應用程式已驗收。

日後事件記錄：時間／時區、phase 狀態變化、授權 scope 連結、
實際變更、exact checks／結果、驗收對應、重大發現、未執行限制與 blocker。
