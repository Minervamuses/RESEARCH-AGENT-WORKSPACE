# Issue 07 — Extension apply 跨程序一致性：執行計劃

## 計劃概況

- **Plan root：** `issue/issue_07`；穩定目標見 [GOALS.md](GOALS.md)。
- **Execution mode：** Autonomous within authorization envelope。
  使用者明確核准下述鎖方案並要求執行後才生效；目前僅 authoring。
- **Repository shape / risk：** Application / medium。改動小，但錯誤鎖範圍可能
  覆蓋已成功更新；需真 process 交錯及釋鎖證據。
- 沿用現有 `issue/issue_XX/phases/` 慣例；根 `.gitignore:8` 忽略 `build/`。
  一個 phase 完成同一 critical section 的重現、修正與驗證，不另設探索／驗收專案。

## 資訊唯一來源

| 資訊 | Owner |
|---|---|
| 目的、成功條件、範圍、保留行為與限制 | GOALS.md |
| 路線、依賴、授權、停止、修訂與整體完成 | PLANS.md |
| 可複製的啟動／續作入口 | PROMPTS.md |
| 詳細步驟、planned checks、acceptance | phases/phase-01-cross-process-apply-lock.md |
| Runtime status 與 observed implementation evidence | build-log.md |
| 執行後重大發現／實際 review | context/、code_review/ |

不預建 context／review，不在多個文件維護 current-phase 狀態。

## 已確認 repository baseline

以下是 2026-09-12 authoring 的唯讀觀察，不能視為測試通過：

- Root `/home/minervamuses/research-agent-workspace`，根 AGENTS 是唯一 applicable
  repository instructions。WSL Ubuntu-24.04，Linux bash `/usr/bin/bash`、
  Git `/usr/bin/git`；Conda app 的 Python 3.13.14／Poetry 2.4.1
  位於 `/home/minervamuses/miniconda3/envs/app/bin/`。
  PowerShell 僅作 WSL launcher；需先 source Conda，非 system Python。
- Branch `GUI`；HEAD `2870bcd75eb809120f9e4bb7a2ab1668330946d6`。
  初始 tracked deletions 在 `issue/issue_03/` 與 `issue/issue_10/`；
  既有 untracked bundles 為 `issue_01/`、`issue_02/`、`issue_03(fin)/`、
  `issue_04/`、`issue_05/`、`issue_10(fin)/`，皆在 `issue/` 下。
  保留這些狀態，不還原、不 stage。authoring 前 `issue/issue_07/` 不存在。
- `manager.py:65,456–477` 的 module threading lock 非阻塞且只包同 process；
  `_apply_locked:485` 才讀 latest revision，`:639` 呼叫 writer。
  ApplyReport 在 writer 回傳後建立，preview 與 LLM planning 在鎖外。
- `registry.py:40–78` 以 UUID temporary file、file fsync、os.replace、
  chmod、fsync_directory 寫 registry；`install_scanned_extension` 另寫
  staging／installed，故只包 `write_registry` 太晚。
  此次 production writer 搜尋僅發現 manager 呼叫；測試可直接 seed registry。
- `paths.py:resolve_extension_paths` 已 resolve state root 並禁止與 dropin 重疊，
  不需新增路徑 abstraction。`models.py` 定義 revision／extensions 現有 schema。
- `test_extension_manager.py` 的 `_PlanModel`、`_write_skill`、
  `_write_private`、`_config` 可重用；selected-skill tests 可構造同 revision
  的兩個互不相同變更。既有 stale-preview test 只序列更動 registry，非 process race。
- CLI `extension_management.py:169` 轉譯 ManagementError；
  Desktop `service.py:453–464` 用訊息子字串
  `another extension apply is already running` 對應既有
  `BUSY_EXTENSION_OPERATION`。保留該訊息即可沿用既有錯誤契約。
  Desktop apply 消耗 preview ID，重試需重新 preview；不改 durable-turn 語意。
- `test_extension_registry.py:test_install_copy_and_registry_round_trip` 檢查
  JSON round trip、installed file 與 0600，沒有涵蓋整個 fsync 持鎖邊界。
  `test_extension_user_journey.py:test_user_dropin_apply_restart_use_update_delete`
  已覆蓋 dry-run、apply、restart、Skill／MCP、update／delete。
- `app/pyproject.toml` 為 pytest 9；無 formatter／linter 設定。
  `/usr/bin/timeout` 已確認存在。歷史
  `issue/issue_10(fin)/build-log.md:322` 記錄 full suite 27.57 秒，
  只支持安排一次有時間上限的離線檢查，不代表本次或未來 suite 已通過。
  Linux 無 rg，使用 grep／find，不安裝新工具。

## 擬採方案

在既有 `manager.py` 局部加入 Linux stdlib `fcntl.flock`，
對 `preview.paths.state_root / ".apply.lock"` 使用固定、非截斷的檔案描述符與
`LOCK_EX | LOCK_NB`。維持外層 threading lock，以相同順序取得 process lock，
再進入整個 `_apply_locked`，writer 回傳或任何 exception 後確保釋放。

取得鎖失敗立即沿用既有 busy 訊息；其他 I/O／lock 錯誤沿用 ManagementError
失敗通道。沒有自動 retry 或 timeout 設定，等待政策為零等待。
不使用 registry.json 本身當鎖媒介，因為它會被 replace。

依據 [Python 3.13 fcntl 文件](https://docs.python.org/3.13/library/fcntl.html)
與 [Linux flock(2)](https://man7.org/linux/man-pages/man2/flock.2.html)，
flock 可作非阻塞排他鎖；lock 與 open file description 關聯，所有對應 fd
關閉後釋放，fork／dup 可共享該 description。
因此本方案每次 apply 獨立開啟固定檔案，避免 fd 流入 child，
不刪除 lock file、不靠其內容或存在與否判斷鎖。
這是文件支持的設計推論，實際 manager cleanup／crash 行為仍須測試。
Advisory lock 只協調採用相同方案的 writers。

## 執行授權

### 啟動前

目前只能 authoring，不得開始 production／test edits。
Personal Engineering Defaults 要求新增 concurrency model 先獲明確核准。
使用者須核准「固定 `.apply.lock`、Linux 非阻塞 flock、立即衝突報錯」
並啟動本計劃；PROMPTS 提供含此具體核准內容的範例。
文件自身、排程或另一個 agent 讀到文件，均不等同使用者已核准。

### 明確啟動後的例行範圍

- 預期 production 只改 `app/agent/extensions/manager.py` 的鎖生命週期，
  不新增 persistent module；可用檔內 private helper，避免大幅重排既有方法。
- 在 `app/tests/test_extension_manager.py` 加最少的局部 multiprocessing helper
  與回歸案例；在 `app/tests/test_extension_registry.py` 只有需要時補 writer
  durability 斷言。必要的 CLI error assertion 優先放既有 manager 測試，
  Desktop error regression 可局部放 `app/tests/test_desktop_service.py`。
- 可執行 phase 明列的本機離線 focused checks 與最後一次 full suite，
  使用 tmp_path／既有 fake model／sandbox MCP，執行受時間上限約束。
- 可更新本 bundle 的實際 log、重大 context、真實 review、被新證據推翻的未開始計劃。
  不修改原 issue、AGENTS、README、其他 bundle 或任何真實 state。
- 在授權內自主完成，不逐小步詢問；完成或觸發下列停止條件時交回使用者。

### 停止條件與 fresh authority

- 未取得上述跨程序鎖的明確實作授權。
- 目標、preserved behavior、必要驗證須改變，或需要阻塞等待／自動重試等不同語意。
- 已確認 manager 局部方案不足，需修改其他 production 檔案；先提出直接因果證據、
  具體最小 diff。超過三個 production files、可局部解決卻新增 persistent module，
  或 generic framework／adapter／parallel pipeline／broad refactor 仍須新授權。
- 除精確核准的 flock 外，新增 service、database、queue、worker、cache、
  storage layer 或其他 concurrency model；改 public API、schema、file format、
  persistent data structure、依賴、lockfile、套件管理器或 runtime environment。
- 新 benchmark／evaluation／regression／fixture／test framework；
  full-dataset replay、exhaustive sweep、live／paid provider、model／GPU、
  credentials、外部寫入、真實使用者資料操作。
- 命令預期超過約十分鐘、第二次完整 suite 或昂貴重跑。必要證據 unavailable 時
  不以 skipped 冒充 pass；先評估最小離線替代，不足才請使用者決定。
- Commit、push、merge、rebase、切 branch、修改 worktree、deploy、不可逆操作。
  清理僅限測試自己建立的 temporary resources／children，不碰原有工作。

兩次 focused implementation attempt 失敗後停止並報告證據、最可能原因及最小下一步；
一次 expensive attempt 無效後不得自行重跑。詢問授權需說明具體需要、
更小替代為何不足、預期時間／usage／complexity／maintenance cost。
Applicable AGENTS 及使用者 Personal Engineering Defaults 持續優先，不能修改 AGENTS。

## 階段路線與依賴

| Phase | 可觀察結果 | Depends on | Phase file |
|---|---|---|---|
| 01 — Cross-process apply lock | 同 revision 競爭不遺失成功更新，衝突／crash 可恢復，既有流程不退化 | 無前置 phase；上述明確啟動授權與 Linux runtime gate | [phase-01-cross-process-apply-lock.md](phases/phase-01-cross-process-apply-lock.md) |

所有必要驗證都屬於這個同一鎖定邊界；不用第二個 phase 延後證明第一個是否安全。

## 計劃維護與失敗處理

- 先核對 live root／runtime／git status，再由 log 與依賴選擇首個 eligible phase。
- Required check 失敗或未驗證，phase 不得 Complete，任何 dependent work 不得開始。
- 新證據否定方案時，移除被否定的 speculative work，先修訂本 roadmap 及受影響
  未開始 phase；active phase 只能在原授權目標內澄清，不能藉修訂擴張權限。
- GOALS 的穩定目標只能依使用者決策改變；log 以 append-only correction 保留
  重要失敗與完成證據，不倒寫歷史。
- 重大發現才建立 `context/phase-01-cross-process-apply-lock-context.md`。
  真 review 才建立 `code_review/phase-01-cross-process-apply-lock-review.md`；
  不建立永久 reviewer／orchestrator 流程。

## 整體完成標準

- [ ] Roadmap 每個 phase 在 build-log 為 Complete，逐項 acceptance 有 observed evidence。
- [ ] GOALS 的成功條件由真正 process 結果、registry／installed bytes 與入口回歸支持。
- [ ] 必要 focused checks、代表 journey 與最後一次完整 suite 完成且通過；
      不相關失敗單獨報告，必要檢查的豁免只由使用者明確接受。
- [ ] Diff 僅含必要實作、測試與執行紀錄；git diff --check 通過，原有工作保留。
- [ ] 如實列出 fake model、本機 filesystem、crash-before-commit 的驗證界線；
      不宣稱 power-loss transaction rollback 或任意 writer 安全。

## Authoring write set

僅新增本目錄 `GOALS.md`、`PLANS.md`、`PROMPTS.md`、`build-log.md`
及 roadmap 唯一 phase file。不得覆寫其他 bundle；初始 context／code_review 不建立。
