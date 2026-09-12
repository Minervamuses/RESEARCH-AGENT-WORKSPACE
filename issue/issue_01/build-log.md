# Issue 01 — 執行紀錄

本檔是唯一 runtime phase 狀態與實際執行證據來源。
計劃內的命令是預定驗證，不是通過紀錄。

## 階段狀態

| Phase | 狀態 | 開始 | 完成 | 證據 | 阻塞 |
|---|---|---|---|---|---|
| 01 — 重現與分流 | Not started | — | — | — | — |
| 02 — 最小修正 | Not started | — | — | — | — |
| 03 — 完整驗收 | Not started | — | — | — | — |

只使用 Not started、In progress、Blocked、Complete。
只有該階段所有必要驗收均有觀察證據才標 Complete。
尚待決定的前置條件由 GOALS／phase 保存，不在此複製計劃內容。

## 證據規則

- 每筆記錄包含日期與時區、phase、狀態變更、直接相關檔案、
  exact command／人工程序、pass／fail／skipped／unavailable、觀察與限制。
- 區分親自觀察、使用者回報、歷史資料與預定行為。
- 實際 IME journey 記錄引擎／輸入方式、控制程式與 backend、
  測試文字、候選確認前後的 turn 數、canonical input 與重載結果。
- 記錄額外授權的確切範圍與來源；不含 secrets、整份環境 dump、
  私人對話或無關終端輸出。
- 每個完成條件連結到對應證據；必要證據缺失或矛盾就保持未完成。
- 重大更正追加到活動紀錄，不刪除影響後續判斷的失敗歷史。
  material discovery 放 context，真正 review finding 放 code_review。

## 活動紀錄

尚無 implementation 活動。此次只撰寫計劃與做 authoring 檢查，
未啟動 Desktop、安裝 IME、修改應用、執行應用測試或完成中文輸入驗收。
