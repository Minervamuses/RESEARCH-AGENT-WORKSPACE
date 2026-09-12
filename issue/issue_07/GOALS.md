# Issue 07 — Extension apply 跨程序一致性：目標

## 目的與背景

兩個獨立 CLI／Desktop backend process 共享同一 extension state root 時，
目前各自的 `threading.Lock` 無法互斥。兩者可能從相同 registry revision N
通過 recheck，各自提交 N+1，後一次 replace 覆蓋前一次已回報成功的更新。

原始需求見 [07-extension-apply-cross-process-race.md](../07-extension-apply-cross-process-race.md)。
本計劃處理這個本機併發問題；issue 06 的 session 完整性問題獨立，不是前置條件。
原 issue 的排序表示優先度，不代表技術依賴。

## 預期成果與成功條件

- [ ] 兩個獨立 process 對相同 state root、相同 revision N 的 preview
      套用不同有效變更時，最多一個成功提交 N+1；沒有其他故障的代表案例恰有一個成功。
- [ ] 失敗方收到可理解的「另一個 apply 執行中」或「registry 已變更，請重新 preview」，
      不產生成功 ApplyReport／成功 applied revision，也不先安裝失敗方的 bundle。
- [ ] 最終 registry 為有效 JSON，成功方的 entry、source hash 與 installed bytes 保留。
      敗方在成功方完成後重新 preview／核准，再 apply，能提交 N+2 且保留兩者。
- [ ] 鎖競爭立即失敗，不無限等待；持鎖 process 在提交前被終止後，其他 process
      能再次 apply，不需刪除 lock file 或人工解除永久死鎖。
- [ ] 單 process apply、selected-skill scope、source／private Skill 驗證、MCP 核准、
      dry-run 不寫 state、restart 載入與既有 CLI／Desktop 結果契約維持。
- [ ] Registry 的 temporary file、file fsync、atomic replace、directory fsync
      寫入順序不變，跨程序互斥涵蓋最後 revision read 至 writer 完成。

「最多一個提交」限定相同 revision 的競爭變更；重新 preview 後依序成功是正常行為。
無變更 apply 可以回傳相同 revision，不等同一次新提交。

## 範圍

- 共用 state root 的 `ExtensionManager.apply()` 整段 critical section。
- 衝突、錯誤與 process 終止的鎖生命週期，以及直接防止 lost update 的回歸測試。
- 現有本機離線 user journey／CLI／Desktop backend checks，重用既有測試資源。

## 非目標

- issue 06、citation、GUI 功能、SkillInstaller staging 競態或其他 extension 改造。
- 新 CAS storage、database、transaction log、queue、worker、通用鎖框架或套件依賴。
- Native Windows 支援、分散式／網路檔案系統保證、跨主機協調。
- 對不遵循本鎖的舊版 process、手動 registry writer 或外部編輯提供互斥保證。
- 自動重試、背景等待、可設定 timeout、清理既有 installed 孤兒副本。
- 模擬所有斷電點、提供整個安裝流程的 transaction rollback。
  Process crash 釋鎖不代表回滾已寫入的資料。

## 保留行為與 invariants

- 使用者核准的 preview 才能 apply；不因 lock conflict 自動重新計劃或套用新 preview。
- Revision recheck、private Skill hash、source／diff signature 與 MCP binding 檢查保留。
- `ApplyReport`、registry JSON schema、public method signatures 與 Desktop protocol 不變。
- 未成功取得 process lock，不執行 revision transaction、安裝、刪除或 registry 寫入。
  Apply 為了取得鎖可以建立 state root／固定 lock file；preview／dry-run 仍不可因此寫入。
- 同 process 的既有非阻塞鎖行為保留，不藉本題改善不同 state root 的 thread 並行能力。
- 固定 lock file 是互斥媒介，其存在不等同持鎖；不得藉刪除、replace 或 PID 判斷搶鎖。

## 限制與權威來源

- **Runtime：** 根 [AGENTS.md](../../AGENTS.md) 指定 Linux；Conda `app` 管 runtime，
  Poetry 管 Python dependencies。可從 Windows 經 WSL tooling 操作，檔案保持 UTF-8／LF。
- **規模：** 使用者 Personal Engineering Defaults 指定最小可驗證改動、保留既有工作、
  無額外架構與昂貴驗證。只用 pytest、stdlib multiprocessing 與現有 fake model。
- **授權：** 2026-09-12 使用者只要求閱讀 AGENTS 並撰寫 issue 07 計劃。
  新增跨程序同步機制的實作仍須明確核准；具體啟動方式由 PLANS／PROMPTS 擁有。
- **驗證界線：** 所有測試使用 Linux 本機 temporary state root，不碰實際使用者 state、
  secrets、live model／paid provider 或真實外部 MCP。真 GUI 兩個視窗不是本題必要 oracle；
  兩個獨立 process 呼叫同一正式 manager，加上既有入口測試，驗證共用故障邊界。
- **作業限制：** 不新增 dependency、manifest、環境、public format 或其他持久資料模型；
  唯一擬新增 runtime 檔案是 state root 下固定 lock file，不儲存業務資料。

## 已知未知與使用者決策

目前沒有阻擋「撰寫計劃」的未決使用者資訊。採立即回報 lock conflict 的規劃選擇
依據既有 `_APPLY_LOCK.acquire(blocking=False)`，不是額外等待策略。

- **待實作驗證：** 真正跨 process 的交錯、exception cleanup、crash 釋鎖及 writer
  directory fsync 期間是否仍持鎖，均由唯一 phase 的有界測試確認；目前沒有執行證據。
- **啟動所需決策：** 是否核准 PLANS 明列的固定檔案鎖及局部實作。
  這不是 authoring 的前置條件，也不能由計劃文件自行代替使用者授權。
- 若日後發現 state root 位於不具所需 locking semantics 的 filesystem，
  停止並說明缺少的證據；不可靜默退回單 process 鎖或擴張平台支援。

## 來源

- 原始 issue、根 AGENTS 與本次使用者的 Personal Engineering Defaults。
- `app/agent/extensions/manager.py`：`apply`／`_apply_locked`。
- `app/agent/extensions/registry.py`：`load_registry`／`write_registry`／安裝副本。
- `app/agent/extensions/paths.py`、`models.py`：state root 與既有資料契約。
- `app/tests/test_extension_manager.py`、`test_extension_registry.py`、
  `test_extension_user_journey.py`：既有代表流程。
