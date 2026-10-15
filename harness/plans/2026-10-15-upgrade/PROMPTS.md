# upgrade｜啟動與交接提示

計畫包位於 `harness/plans/2026-10-15-upgrade/`。以下是可複製的未來請求，本檔本身不啟動任何實作。現況只讀 [build-log.md](build-log.md)，不在這裡維護當前階段。

## 啟動／續作

> 執行 `harness/plans/2026-10-15-upgrade/` 的 upgrade 計劃。先讀適用 AGENTS.md、該目錄的 GOALS.md、PLANS.md、build-log.md，再讀下一個依賴已滿足的 build/phase-*.md。重新完成 Linux／Conda app 的 runtime gate，查看 GUI 分支、HEAD 與未提交變更，核對已有批准、檢查結果及已發生的副作用。首次啟動的第一步是 build/phase-00-preflight.md 的唯讀狀態核對；續作時先對照 build-log.md 與真實檔案，完成或修正最後一個未驗收步驟。遵守 PLANS.md 的執行／批准／成本及失敗處理契約，繼續依賴已滿足且已授權的工作，每個有意義步驟更新 build-log.md。不要重新討論 D1～D8，不要把此提示當成依賴、schema、Git 或付費操作的無限批准。直到必要驗收完成，或遇到具體未解前提才停止受影響工作；不需要原對話或撰寫技能才能接手。

連結閱讀順序：[GOALS.md](GOALS.md) → [PLANS.md](PLANS.md) → [build-log.md](build-log.md) → [P0 首次入口](build/phase-00-preflight.md) 或 PLANS.md 第 4 節列出的下一個可執行階段。適用專案規範必須先讀。

## 修訂

> 僅修訂 `harness/plans/2026-10-15-upgrade/` 計劃，變更內容以我這次提供的說明為準。先讀 GOALS.md、PLANS.md、build-log.md 與受影響階段；保留既定需求、未受影響範圍及歷史證據。同步更新需求、共同設計、階段依賴、驗收、PROMPTS.md 和 plan-index.json 的受影響部分；狀態及實際批准只在 build-log.md 維護。完成結構與語意檢查後交付，不開始實作。

## 審查

> 唯讀審查 `harness/plans/2026-10-15-upgrade/` 計劃。以 GOALS.md 的來源、D1～D8、G1～G7 及實際 repository 狀態核對 PLANS.md、build/ 各階段、PROMPTS.md、build-log.md 與 plan-index.json。指出具體需求遺漏、無證據宣稱、錯誤依賴、批准或成本越界、無法接手之處；區分計劃驗證與產品實作證據。不修改檔案或執行產品工作。
