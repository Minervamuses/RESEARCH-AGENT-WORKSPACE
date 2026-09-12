# Issue 10 — 對話式本機 ZIP Skill 安裝：可重用指令

以下 prompt 只有在使用者實際送出時才啟動實作。文件本身不構成授權。

## Start or Resume End-to-End Execution

複製以下完整區塊：

> 在 WSL/Linux repository `/home/minervamuses/research-agent-workspace`
> 執行 `issue/issue_10` 的計畫。我明確授權 `PLANS.md` 的 execution envelope：
> 包含超過三份直接必要 production files、既有 manager 的相容性 selected-skill
> 參數與 preview scope、skill-scoped host action、公開 installer skill 與有限
> in-memory 續接，以及該範圍的最小測試／文件更新。可依 phase 指定程序進行
> 隔離的無害本機 shell／檔案驗證、讀取公開固定版本 ZIP、執行一次預期十分鐘內
> 的完整 pytest 與 Poetry build。不要安裝依賴、改持久化格式／Desktop protocol、
> 使用 live/paid model、執行下載的腳本或修改真實使用者安裝資料。
>
> 先讀全部 applicable `AGENTS.md`、`issue/issue_10/GOALS.md`、
> `issue/issue_10/PLANS.md`、`issue/issue_10/build-log.md`，再從 roadmap
> 與 log 選出第一個 dependencies 已 Complete、自身未 Complete 的 phase，
> 讀其 phase file、存在時相關 context/code_review，以及 live code 和 tests。
> 核對 root、Linux 工具、Conda app、Git 與工作目錄，保留既有使用者修改。
>
> 對每個 eligible phase 做 read-only preflight，確認 scope、non-goals、
> planned checks 與 stop conditions；只做該 phase，使用最小 red 或
> characterization、green、必要 cleanup 及 verification。Required checks
> 失敗或缺證據時不得開始 dependent phase；先診斷並按 PLANS.md 決定修復或停止。
> 將 exact commands、pass/fail/skipped、限制與狀態寫入 build-log；只有重大
> 發現才建立 context，只有實際 review 才建立 code_review。若新證據使後續
> 計畫不成立，先修正 roadmap 與受影響的未開始 phase，不改寫已完成證據。
>
> 在授權範圍內自主接續下一個 eligible phase，直到整體完成或遇到 PLANS.md
> 的停止條件，不需逐 phase 再問。此 launch 不授權 commit/push、變更分支、
> 部署或發布；不得修改 AGENTS.md。不得把歷史、planned 或 fake-model
> integration 結果宣稱為本次實測或真實模型自主性證明。

## Execute One Phase

使用者指定 phase 後，讀取與 Start/Resume 相同的 durable sources，確認依賴已
Complete 且目前對話有該 phase 的實作授權。只完成其 preflight、實作、驗證與
evidence recording，然後停止，不延伸到下一個 phase。

## Verify a Phase

以 named phase、GOALS、實際 diff、build-log 與 context 對照 acceptance。
直接檢查 selected-only 是否涵蓋重新掃描、批准是否由 host 綁定、檔案是否保留、
對話是否實際走工具迴圈。只記錄觀察所得，不把 builder 自述當作證據；有真實
review 才建立該 phase 的 code_review 文件。

## Repair the Plan After Contradictory Evidence

讀 GOALS、PLANS、build-log、受影響 phase、相關 context/review 與 live code。
明列矛盾證據及下游影響，只調整 roadmap 和受影響的未開始 phase，對 log 追加
必要 correction。使用者未改目標時不得改 GOALS。這項 repair 本身只改計畫，
不實作功能；完成後跑 plan validator 與 fresh-agent walkthrough。

## Final Integration Review

逐項把 GOALS 成功條件與 PLANS 整體完成標準對到實際證據。優先檢查 Phase 03
的真實 ZIP、兩種對話入口、跨 session 啟用、原 bundle hash、未選項目隔離、
拒絕／取消及 packaging；已通過檢查只有在新增改動或疑慮需要時重跑。
Required evidence 缺失時保持未完成，清楚區分已證明行為與未執行的外部驗證。
