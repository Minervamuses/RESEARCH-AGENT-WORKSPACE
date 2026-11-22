# C6-S5 階段收尾與 C6 驗收

- **日期**：2026-11-22，程式狀態 `87c8844`（最後一次程式變更在 `f6126ce`，C6-S4 只加了 evidence）。

## 檢查

| 檢查 | 指令 | 結果 |
|---|---|---|
| 完整 pytest（沙箱外） | `cd app && /home/minervamuses/miniconda3/envs/app/bin/python -m pytest -q -p no:cacheprovider` | 1755 passed（C5-S6 為 1762；C6 刪除 11 個 catalog／registration 測試並新增 7 個測試函式、共 13 個參數化案例，其餘為改寫） |
| `npm test` | `cd app/desktop && npm test` | 224 pass、0 fail |
| `npm run build` | `cd app/desktop && npm run build` | 通過 |
| `cargo test --locked`（沙箱外，Conda env `app`） | `cd app/desktop/src-tauri && cargo test --locked` | 35 passed |
| contract 已無 C6 負責移除的項目 | `grep -cE "project\.list|session\.retry_registration|registrationStatus|registrationIssue" app/desktop/protocol/v1/contract.json` | 0；方法數 25 |

## C6 驗收對照（phase-06「完成後的狀態」）

| 狀態 | 證據 |
|---|---|
| 沒有程式讀寫 `desktop-projects.json` | C6-S2 grep：只剩 `LEGACY_CATALOG_FILENAME` 與 `initialize_project` 的「容許殘留」檢查；(e) 的兩個測試比對 bytes 與 mtime |
| 清單來自 `ConversationRepository.scan()` | `project_conversations`；C6-S2 (a)(b)(c) 與 S027 測試 |
| `project.list`、`session.retry_registration`、registration 狀態與 UI 分支已移除 | contract grep 0；TS grep 0（C6-S3） |
| 前端只有單一專案路徑；重啟後原本選取的對話恢復 | C6-S3：`sessionList` 單一清單、`conversationToRestore` 的 (a)(b)(c) 測試；GUI 清單第 4 項 |
| 擁有權與歷史健康檢查照舊 fail closed | C6-S2 (d)(f)(g) |
| 掃描成本已量測，是否加快取交給使用者 | `evidence/C6-S4/scan-cost.md` |

本階段只驗收自己負責移除的項目；完整方法清單與錯誤碼的跨階段複查在 C10-S0。
