# Issue 01 — 可重用指令

## 啟動與續作（Start / Resume）

以下區塊可直接作為之後的實作要求；此次撰寫計劃不等於已送出此要求。

> 請執行 `issue/issue_01` 計劃。先讀適用的 AGENTS.md，
> `issue/issue_01/GOALS.md`、`issue/issue_01/PLANS.md`、
> `issue/issue_01/build-log.md`，再按 PLANS 的依賴順序選取
> 第一個尚未 Complete 且前置 phase 全部 Complete 的階段。
> 讀該 `issue/issue_01/phases/` 文件、相關既有 context／code_review
> 及目前程式和測試，不依賴之前的對話記憶。
>
> 在修改前做 read-only preflight：確認 workspace、Linux／Conda app 工具鏈、
> branch、worktree、已存在的部分實作與證據；簡短說明該階段範圍、
> 驗證方式及停止條件。保留使用者修改，對 log 與實況矛盾追加更正。
>
> 我授權 PLANS「啟動後的日常授權」範圍內的工作，依序完成所有符合依賴的
> phases；PLANS「額外授權與阻塞」的操作仍須另行明確批准。
> 先完成可審閱的方案與成本資訊再提出安裝或持久設定的批准請求，
> 不把缺少前置條件視為已獲安裝授權。
>
> 每次只實作所選 phase，以最小觀察驗證因果，適用時才做最小 regression test。
> 執行該階段所有必需且可用的檢查；失敗先修正，不推進依賴它的階段。
> 原生 IME 操作無法自動完成時，明確安排人工驗收，不能用 paste 或
> synthetic events 替代，也不得把未驗證判成通過。
>
> 將 exact commands、實際結果、限制及 criterion→evidence 對應寫到
> `issue/issue_01/build-log.md`，只有重大發現才新增
> `issue/issue_01/context/` 文件，真正 review 才寫
> `issue/issue_01/code_review/`。若證據推翻後續計劃，
> 先修改 PLANS 及受影響的未開始 phase，再繼續。
>
> 符合日常授權且本階段驗收通過後自主進入下一個符合依賴的 phase。
> 遇停止條件／必要證據缺失就記錄 Blocked 與最小下一步並停止；
> 否則持續至整體完成。不得自行變更 GOALS、commit、push、切分支或擴大範圍。

## 執行單一階段

> 只執行我指定的 `issue/issue_01/phases/` 階段。
> 依本文件 Start/Resume 的讀取順序完成 preflight，確認前置階段已有 Complete
> 證據，遵守 `issue/issue_01/PLANS.md` 授權；完成該階段檢查、log
> 與必要 context 後停止，不進入後续階段。未指定階段時先確認目標。

## 階段驗證與最終審查

> 審查 `issue/issue_01`：讀 GOALS、PLANS、build-log、相關 phase、
> 目前 diff、context 與真正 review 紀錄。將每項成功條件對照實際證據，
> 特別檢查原生 IME 與 paste 的區別、單次送出、保存／重啟、
> 模型呼叫與資料隔離、必要設定是否真的測過。僅執行已授權、
> 與未解疑慮直接相關的檢查，不無故重跑昂貴 suite。
> 缺失明列為 finding；審查確實完成後才寫 code_review，
> 未取得必要證據不得標記 Complete。

## 新證據推翻計劃時修訂

> 只修訂 `issue/issue_01` 計劃：先讀 GOALS、PLANS、build-log、
> 被推翻的 phase、material context 與 live code。標明矛盾證據及
> 影響的未開始 phases；只更新必要 roadmap、phase 與交叉引用，
> 保留已完成與失敗證據，以追加紀錄更正。未經我改變目標，不修改
> GOALS 的成功條件；本次修訂不授權應用實作或環境設定。
