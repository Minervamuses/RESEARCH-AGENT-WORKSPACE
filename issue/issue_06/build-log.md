# Issue 06 — Applied Skill 啟動後完整性：Build Log

此檔是 runtime phase status 與實際 implementation/verification evidence 的唯一來源。
計劃說明未來工作；這裡只記錄已觀察事實。

## Phase Summary

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Activation integrity | Not started | — | — | — | 啟動時依 PLANS 核對具體 API 變更授權 |

可用狀態：Not started、In progress、Blocked、Complete。
只有 acceptance 與 required verification 均有 evidence 才可 Complete。

## Evidence Rules

- 每次記錄 exact command/procedure、runtime/target、簡短結果與 evidence reference。
- 分清 observed、historical、planned；skipped/unavailable 說明原因與殘留限制。
- Acceptance criterion 必須對應到實際檢查，不能以 code shape、phase status、
  fake model 固定文字或 authoring validator 代替。
- 大輸出用路徑引用；不保存 secrets、YAML 敏感內容或整份 transcript。
- 有矛盾證據時保留雙方觀察，先解決再 Complete；更正以 append-only 追加。
- Failed attempt、必要 scope/API 核准、實際 review 與未驗證項均如實記錄。

## Activity Log

尚無實作活動。此 bundle 已撰寫，但沒有執行 application tests、
Skill activation 或實際 recovery；planned checks 都不是通過證據。

未來事件格式：日期與時區、Phase、Status 變動、授權 scope 連結、最小 changes、
exact verification/result、review findings、limitations/blockers、next action、
必要 context/review references。重大更正追加，不抹掉原紀錄。
