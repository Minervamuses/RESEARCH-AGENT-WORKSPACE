# Issue 08 — Build Log

本檔是唯一 runtime phase status 與 observed implementation evidence owner。
計劃描述未來工作；本檔只記錄真正發生的執行結果。

## 階段狀態

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Citation turn lifecycle | Not started | — | — | — | 啟動前需核對 GOALS 待決、PLANS 授權與 issue 02 |
| 02 — Desktop integration | Not started | — | — | — | 依 PLANS 前置順序 |

只使用 Not started、In progress、Blocked、Complete。
必要 acceptance 有 observed evidence 才可 Complete。

## 證據規則

- 記錄時間、phase、狀態變化、changed files、exact command／操作、
  cwd／runtime、pass／fail／skipped／unavailable、簡短觀察與 artifact 路徑。
- 分開實際觀察、歷史資訊與 planned checks；不複製整份輸出或 credentials。
- 以 command 輸入／正式答案／registry 狀態／provider counter／bundle 檔案
  對應 acceptance；fake model、reducer 或 helper checks 不代表原生 UI 已驗收。
- 未通過或不可執行的必要檢查保持未完成，記具體原因與下一個最小行動。
- 重大矛盾以 append-only correction 保留原紀錄；依證據更新狀態表。
- 重大發現與真實 review 依 PLANS.md 路徑寫入，沒有內容不先建立空文件。

## 活動紀錄

尚無 implementation activity。本次只 authoring，application tests、Desktop
build／UI 操作與各 phase planned verification 均未作為本計劃實作證據執行。
