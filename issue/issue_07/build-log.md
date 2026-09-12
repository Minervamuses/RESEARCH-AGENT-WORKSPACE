# Issue 07 — Build Log

本檔是 runtime phase status 與 observed implementation evidence 的唯一來源。
計劃描述未來工作；此處只記錄實際發生的實作與驗證。

## 階段狀態

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Cross-process apply lock | Not started | — | — | — | 尚未啟動；實作授權條件見 PLANS.md |

狀態只用 `Not started`、`In progress`、`Blocked`、`Complete`。
只有 phase acceptance 與 required checks 都有實際 evidence 才能標為 Complete。
授權未授予是未啟動狀態，不能寫成已開始實作或已驗證。

## 證據規則

- 記錄精確命令／步驟、runtime、簡短結果與 pass／fail／skipped／unavailable。
- 對每個 acceptance 指向具體結果；不能以「新增測試」當成功證據。
- 區分此 authoring 的唯讀觀察、歷史紀錄和未來實作結果。
- Multiprocess 結果記錄每個 child 的 outcome、revision、exit code、
  registry／installed assertions 與清理結果，不只記錄 aggregate pass。
- 記錄重要失敗及其原因；追加 correction，不刪除影響後續判斷的歷史。
- 不貼 secrets、完整 stdout、完整 diff 或例行工作流水帳。
- 只有重大新發現才建立 context，實際 review 才建立 code_review。

## 活動紀錄

尚無 implementation activity；本次僅撰寫計劃。
未執行 application tests，未重現或修正 race；不得將文件 validator 結果當成實作通過。

實作開始後，每筆重要紀錄包含時間與時區、phase/status 變化、授權範圍、
必要修改、精確驗證與觀察、限制／blocker、下個 eligible action，以及需要的 evidence link。
