# Final Check — 可複製的執行入口

## 啟動／續作 — Start/Resume

```text
執行 issue/final_check 的補救與驗收計畫。
先讀根及適用 AGENTS.md、issue/final_check/GOALS.md、issue/final_check/PLANS.md、
issue/final_check/build-log.md，
再按 PLANS 依賴順序找第一個未 Complete、且所有前置 Complete 的 phase，讀取其 phases/ 檔案、
已有相關 context/ 和 code_review/，以及該階段 live code/tests。不要依賴本對話或硬編碼 current phase。

在修改前完成 read-only runtime/worktree preflight：使用既定 Linux Conda app 工具，確認既有 diff、
授權、產品決策、驗證入口與環境。遵守 PLANS 的 execution authorization；本啟動不代答 GOALS
中未定的產品決策，不授權未凍結 API/schema、依賴、昂貴命令或 Git 操作。

逐階段：簡述 scope、最小驗收與停止條件；只修改該階段直接必要的內容。
修 bug 先用既有接縫留下最小 red，再做 green；純驗收觀察實際輸出，不安排形式重構。
執行該 phase required focused/acceptance checks，失敗先查因果並遵守嘗試上限；不能進 dependent phase。
將 exact commands/操作、runtime、pass/fail/unavailable、限制和 acceptance→evidence 寫 build-log.md。
重大發現才寫 context，實際 review 才寫 code_review；不把 planned/historical evidence 改成今日 passed。

證據改變路線時先修 PLANS 與受影響未開始 phases；穩定目標變更先取得使用者決定。
在授權內自主接續 eligible phase，不逐步詢問。遇無變化的外部 Blocked，僅可轉做另一個
前置完整且不受同一 blocker 影響的 phase；沒有可執行工作就報告具體缺項並停止。
完整 suites/build 依 Phase 06 統一安排一次；不重做 Issue 01 已核准略過的矩陣。
完成所有 required outcomes 或到達真正停止條件才停，不自行 push、切 branch/worktree、
安裝依賴、重啟 WSL／系統服務或呼叫付費 provider。
```

## 執行單一階段

```text
只執行 issue/final_check 中我指定的單一 phase。
依本文件 Start/Resume 的相同讀取與 preflight 次序，從 build-log／PLANS 核對前置完成，
讀該 phases/ 檔案及 live code；若沒指定 phase，依 roadmap 選第一個 eligible phase。
遵守授權、驗證及 evidence 規則。完成該階段或遇停止條件即停，不接續後面的 phase。
```

## 只驗證／審查

```text
只審查 issue/final_check 的指定 phase；未指定時以當前已完成階段為範圍。
讀 GOALS、PLANS、build-log、該 phase、實際 diff 與相關 context。
對照 acceptance 檢查原始 evidence，執行當下已授權且最小必要的只讀／離線驗證；
遵守 PLANS 的完整套件次數與外部／原生操作授權，不自行擴張。不能把 builder 的描述當作證明。
本次有真實 review 才寫對應 code_review，列具體反例、缺少證據或 no findings 及其範圍；
不修 application code，除非另外明確要求修正。
```

## 新證據下修訂計畫

```text
只修訂 issue/final_check 的計畫。
讀 GOALS、PLANS、build-log、受影響 phases、實際 code/evidence，指出哪個假設被推翻。
保留完成與失敗歷史；只更新必要 roadmap／未開始 phase，重大更正追加到 log。
若涉及使用者已批准的穩定目標、限縮或產品決策，先取得明確改變。
核對 links、唯一狀態 owner、authoring write set，依 skill 執行 harness validation 與 diff check。
本次不啟動修訂後的實作、不改 AGENTS 或其他未選定 bundle。
```

## 最終整合驗證

```text
執行 issue/final_check/phases/phase-06-regression-and-closure.md。
先按 Start/Resume 讀 durable sources；其依賴尚未 Complete 就不得宣稱完成。
按當前實際 diff 和已跑 evidence 去重 required checks；完整 suite 次數遵守 PLANS。
在 build-log 建立逐 Issue 接受／限縮／延期／阻塞與證據對照，區分新的觀察與歷史結果。
沒有 evidence 的 required 行為保持未完成；不要修改舊 Issue logs 來製造整批結案。
```
