# Issue 02 — Build Log

本檔是唯一 runtime phase status 與 observed implementation evidence owner。
計劃描述將做什麼；此處只記錄真正發生的事情。

## 階段狀態

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Command catalog | Not started | — | — | — | — |
| 02 — Composer menu | Not started | — | — | — | — |
| 03 — Integration acceptance | Not started | — | — | — | — |

只使用 `Not started`、`In progress`、`Blocked`、`Complete`。
必要驗收有實際證據才可 Complete；前置授權或 checks 缺失時不得繼續 dependent phase。

## 證據規則

- 記錄時間、phase、狀態變化、實際 changed files、exact command／操作、
  cwd／runtime、pass/fail/skipped/unavailable、簡短結果與相關 artifact。
- 分開實際觀察、歷史參考與 planned checks；預定命令不等於已執行。
- 不寫入 credentials、使用者資料、整份輸出或日常操作流水帳。
- 原生 keyboard、mouse、IME／screen reader 檢查記錄具體環境與看到的行為；
  不以 helper test 或 SSR markup 推論全部通過。
- 矛盾或錯誤以追加 correction 保留歷史，並更新本表。
- material discovery 才新增 `context/phase-NN-context.md`，
  真實 review 才新增 `code_review/phase-NN-review.md`。

## 活動紀錄

尚無 implementation activity。本次僅 authoring；application tests、build、
GUI 操作與各 phase planned verification 都尚未作為本計劃實作證據執行。
