# C10 — 文件、完整驗證與交付

- **完成後的狀態**：
  - 使用者文件與程式現況一致。
  - 四套檢查在最終狀態上通過。
  - 最終彙報已寫好並提交。
- **涵蓋**：G9
- **相依**：C2–C9。若有階段是 Blocked，C10 照樣執行，並在彙報中列出未完成的部分。
- **輸入**：
  - build-log 的所有事件；
  - `evidence/C1-S3/metrics-before.md`；
  - `evidence/C8-S1/app-behaviors.md`；
  - 各階段加入 GUI 清單的項目。

## 範圍

- **改**：
  - 根目錄 `README.md`；
  - `app/README.md`；
  - `app/agent/**/README.md`；
  - `app/skills/**/README.md`。`SKILL.md` 已在 C5-S5 處理；C10 只修 grep 出來仍與現況不符的 README。
  - `app/rag/README.md` 與 `app/rag/docs/`；
  - 協定測試 docstring 中的約定說明（C3-S4）。
- **不改**：
  - `for_agents/`：由 `$infrastructure` 維護，且有使用者未提交的修改；
  - `AGENTS.md`；
  - `note/` 的既有內容；
  - 其他 `harness/plans/` 計劃。
- **不做**：README 的整體改寫（S133）。只修正與行為不符的句子與表格列。

## 步驟

| 步驟 | 工作 | 必要檢查 |
|---|---|---|
| C10-S1 | **文件。** 在上述範圍內 grep 已移除或已改名的名稱與行為，逐一更新：<br>• `cite/`、`bundle`、`reference.bib`、`CITATION_OUTPUT_DIR`、`citation_output_dir`、`Citation output`<br>• `knowledge.`、`retry_registration`、`desktop-projects.json`、`catalog`、`cataloged`、`transient`<br>• `bashPermissionMode`、`set_bash_permission`<br>• `streamKind`、`Ollama`、`browser preview`<br>• `schemaVersion`（v1、v2）、`fixture`<br>• Retry Stop 的承諾：C7 之後已成立，確認文字與 P4 的行為一致。<br>根目錄 `README.md` 已知要改的地方：「引用與參考文獻」一節（約 125 行）與資料位置表的「已儲存的文獻」列（約 162 行）。依[決策紀錄](../../../../note/20261119/citation_storage_unification_decision.md) §4 改寫，CLI 不存檔的說明要寫清楚。 | • grep 結果寫入 `evidence/C10-S1/doc-grep.md`：修改前與修改後的命中清單；修改後只剩歷史紀錄性質的命中，並逐一註明。<br>• 文件中的 Markdown 連結都指向存在的檔案。 |
| C10-S2 | **完整驗證。** 在最終程式狀態上執行：<br>• 完整 pytest（沙箱外）<br>• `npm test`<br>• `npm run build`<br>• `cargo test --locked`（沙箱外）<br>• `git diff --check <本計劃第一個 C 步驟 commit 的父 commit>..HEAD`<br>• 依 C1-S3 的方式重量所有指標，寫入 `evidence/C10-S2/metrics-after.md`。<br>• residual grep：重跑 C3–C9 各自的 grep 檢查，結果彙整成一份。 | • 四套都通過，數字與耗時寫入 evidence。<br>• 若有失敗：屬於本計劃造成的就修正；屬於 C1 的既有失敗就註明。<br>• `git diff --check` 無輸出。 |
| C10-S3 | **最終彙報**：`evidence/C10-S3/final-report.md`，以使用者的語言（繁體中文）撰寫，內容依序為：<br>1. **總結**：完成、阻塞與未納入各有多少項。<br>2. **S-ID 結果表**：S001–S134 每項一列，狀態是 APPLIED、Blocked（附理由）、未納入（附 GOALS 的理由）或 KEEP，並附對應的 commit 步驟 ID。<br>3. **量測前後對照**：取自 C1-S3 與 C10-S2。<br>4. **使用者可見的行為改變**：U2–U8、P1–P10、決策紀錄 §6。<br>5. **citation 評估的分界 commit**：取自 C5-S7。<br>6. **過時的 `for_agents/` 條目**，建議以 `$infrastructure` 重新整理。至少包括：<br>　• INV-006、INV-010、INV-011、INV-016、INV-023、INV-027、INV-029、INV-032<br>　• FAIL-022（已修正）<br>　• BACKLOG-011、BACKLOG-022<br>　• ASM-016<br>　• `data-flow.md`、`module-responsibilities.md`、`testing-strategy.md`、`architecture-map.md` 中提到的被改動模組<br>7. **`AGENTS.md` 過時的句子**（不修改，只列出）：`issue/` 不存在；`cite/` 已不會產生新內容。<br>8. **GUI 手動檢查清單**：依 C8-S1 的行為盤點，加上各階段加入的項目；C8 與 C9 標為高風險的項目放在最前面。<br>9. **未處理、需要使用者決定的事**：GOALS 的「不納入」表與執行中新發現的項目。<br>10. **殘留資料**：使用者可以自行處理的檔案，包括 `cite/` 的 bundle 與 `.locks/`，以及各歷史目錄中的 `desktop-projects.json`。 | • 彙報中的每個數字與狀態都能在 build-log 或 evidence 找到出處。<br>• 沒有宣稱 GUI 已驗證。 |

## 驗收

- 符合 [PLANS.md](../PLANS.md#整體完成條件) 的整體完成條件。
- build-log 的 C10 列為 Complete，下一步寫「使用者：GUI 清單、`$infrastructure` 重新整理、未處理的決策」。
