# Issue 04 — Citation earliest 歧義：執行紀錄

本檔是唯一 runtime phase status 與實際 implementation／verification evidence
來源。計劃描述預定工作，本檔只記錄已發生的事情。

## Phase Summary

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Earliest ambiguity | Not started | — | — | — | None |

狀態只用 `Not started`、`In progress`、`Blocked`、`Complete`。
只有 phase 的必要驗收與驗證都有實際證據，才可標 Complete。

## Evidence Rules

- 記錄 exact command/procedure、working directory、runtime、結果、驗收對應。
- 清楚區別觀察、歷史、計劃和推測；skipped/unavailable 不等於 pass。
- 保留重要失敗、修改與更正歷史；不要只留下最後成功結果。
- 只有重大 discovery 才連到 context；只有真實審查才連到 review。
- 不寫 credentials、完整 provider payload、完整 diff 或例行敘事。
- Evidence 衝突時保留兩者，未釐清前不得標 Complete。
- 不在其他文件複製本表的 mutable status。

## Activity Log

尚未開始實作，沒有 application tests、provider calls 或保存流程驗證證據。
本次僅撰寫計劃；authoring validator 的結果不代表應用程式修正已通過。

日後每筆重要紀錄包含：時間與時區、phase、狀態變化、實際改動、exact checks
與結果、未執行項及理由、驗收條件對應、重大 context/review 連結、剩餘 blocker。
