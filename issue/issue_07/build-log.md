# Issue 07 — Build Log

本檔是 runtime phase status 與 observed implementation evidence 的唯一來源。
計劃描述未來工作；此處只記錄實際發生的實作與驗證。

## 階段狀態

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Cross-process apply lock | In progress | 2026-09-12 | — | 下列 preflight / baseline | 無 |

狀態只用 `Not started`、`In progress`、`Blocked`、`Complete`。
只有 phase acceptance 與 required checks 都有實際 evidence 才能標為 Complete。
授權未授予是未啟動狀態，不能寫成已開始實作或已驗證。

## 證據規則

- 記錄精確命令／步驟、runtime、簡短結果與 pass／fail／skipped／unavailable。
- 對每個 acceptance 指向具體結果；不能以「新增測試」當成功證據。
- 區分此 authoring 的唯讀觀察、歷史紀錄和未來實作結果。
- Multiprocess 結果記錄每個 child 的 outcome、revision、exit code、
  registry／installed assertions 與清理結果，不只記錄 aggregate pass。
- 記錄重要失敗及其原因；追加 correction，不刪除影響後續判斷的歷史。
- 不貼 secrets、完整 stdout、完整 diff 或例行工作流水帳。
- 只有重大新發現才建立 context，實際 review 才建立 code_review。

## 活動紀錄

尚無 implementation activity；本次僅撰寫計劃。
未執行 application tests，未重現或修正 race；不得將文件 validator 結果當成實作通過。

實作開始後，每筆重要紀錄包含時間與時區、phase/status 變化、授權範圍、
必要修改、精確驗證與觀察、限制／blocker、下個 eligible action，以及需要的 evidence link。

### 2026-09-12（Asia/Taipei）— 啟動 / preflight / baseline

- 使用者要求「執行 issue/issue_07，入口在 PROMPTS.md。每一步皆需 commit」，
  本次按指定 Start / Resume 執行固定 `.apply.lock`、Linux 非阻塞 flock 方案；
  同時明確授權各步 commit。舊 authoring-only 記錄是歷史，不是本次 runtime status。
- 已依序閱讀根 AGENTS、GOALS、PLANS、log、唯一 phase、原 issue 與 live code/tests；
  無其他 applicable AGENTS，無既有 context/review。初始 HEAD `4d7d8a5`、branch `GUI`，
  `git status --short` 為空；不依 authoring 的舊 HEAD/dirty 狀態推斷現況。
- Root `/home/minervamuses/research-agent-workspace`，project `app/`；Linux bash
  `/usr/bin/bash`、Git `/usr/bin/git`，Conda app Python 3.13.14、Poetry 2.4.1。
  PATH 原先選到 pipx Poetry 2.3.4，後續明確指定 Conda 內 Poetry；無環境檔變更。
  在 workspace root 執行 `poetry env info` 因無 pyproject 失敗，切至 app/ 後確認
  Python 與 virtualenv 均為 `/home/minervamuses/miniconda3/envs/app`、Valid True。
  `stat -f -c '%T' /tmp /home/minervamuses/research-agent-workspace` 均為 ext2/ext3。
- Live apply 仍只有 threading lock；revision read、installation、write_registry
  均在 `_apply_locked`，writer 的 fsync/replace/directory fsync 順序與計劃相符。
  CLI/desktop 原 busy message mapping 可沿用，尚缺 apply-lock 的入口 regression。
- Baseline（app cwd）：
  `conda run -n app timeout 120s /home/minervamuses/miniconda3/envs/app/bin/poetry run pytest tests/test_extension_manager.py tests/test_extension_registry.py -q`
  → **51 passed, 1 warning in 0.49s**，exit 0，既有 LangChain pending deprecation。
- 範圍：僅 manager.py production、既有 test 檔與本 bundle 紀錄；不改 registry writer、
  schema、依賴、其他 issue。下一步依序 Red、Green、必要 lifecycle/入口驗證、一次 full suite，
  各步 commit。必要 checks 失敗先診斷；超出 envelope 或兩次修正失敗按 PLANS 停止。

### 2026-09-12（Asia/Taipei）— Red：雙成功與 lost update

- 僅在既有 `test_extension_manager.py` 加 spawn child、bounded Pipe helper 與一個 regression。
  A/B 均先 preview revision 0；A 在真 writer 前暫停，B 完成後才放行 A，無 sleep/barrier。
- app cwd：`conda run -n app timeout 120s /home/minervamuses/miniconda3/envs/app/bin/poetry run pytest tests/test_extension_manager.py -q -k cross_process`
  → **1 failed, 42 deselected, 1 warning in 1.25s**，exit 1（預期 Red）。
- 實際 child outcomes：beta success 1、alpha success 1；最終 registry revision 1
  僅 `skill:alpha`。斷言「恰好一成功」因 2 != 1 失敗，直接證明 beta 更新遺失。
  無 child import/通信 timeout/cleanup failure；finally terminate/join 並關閉自身 handles。
  Red 的 exception 路徑沒有輸出 child exit 數值，不將其稱為正常 exit 0。
- Production 尚未修改。下一步只在 manager 的既有 threading lock 內加固定檔案鎖。

### 2026-09-12（Asia/Taipei）— Green：完整 apply critical section

- 唯一 production 改動為 manager.py：外層保留非阻塞 threading lock，開啟固定
  `.apply.lock`（非截斷、0600、O_CLOEXEC），取得 `LOCK_EX | LOCK_NB` 後才呼叫
  `_apply_locked`；finally close fd，再 release thread lock。Busy 沿用原訊息；
  其他 OSError 走原 ManagementError，沒有無鎖 fallback 或 retry。
- app cwd：`conda run -n app timeout 120s /home/minervamuses/miniconda3/envs/app/bin/poetry run pytest tests/test_extension_manager.py -q -s -k cross_process`
  → **1 passed, 42 deselected, 1 warning in 1.37s**，exit 0。
- A/B 均 ready revision 0；A 暫停 writer 時 B 回報 busy error（無 applied revision），
  A 成功 revision 1；最終 JSON 只有 alpha，hash 與 installed SKILL bytes 相符，
  beta installed 目錄不存在。A/B 正常 exit 0，handles 全部 close。
- 第一個 focused implementation attempt 通過原 Red。尚未宣告 phase Complete；
  下一步補舊 preview/重新核准、fsync 邊界、exception/open-error、crash、root 隔離與入口。

### 2026-09-12（Asia/Taipei）— Lifecycle 與入口驗收

- 補充僅修改既有 manager/desktop service test files。共新增 10 個 pytest cases
  （manager 9，含原 Red；Desktop 1），沿用 fake planner、tmp_path 與 spawn/Pipe。
  每個 poll/join 上限 10 秒，無 sleep，正常 child exit 必須 0；僅 crash A 預期 -15。
- 以下在 app cwd、Linux/Conda app 執行，無 skipped/unavailable：

  ```bash
  conda run -n app --no-capture-output timeout 180s /home/minervamuses/miniconda3/envs/app/bin/poetry run pytest tests/test_extension_manager.py tests/test_extension_registry.py -q -s
  conda run -n app --no-capture-output timeout 180s /home/minervamuses/miniconda3/envs/app/bin/poetry run pytest tests/test_extension_user_journey.py tests/test_extension_mcp.py tests/test_extension_skill_startup.py -q
  conda run -n app --no-capture-output timeout 180s /home/minervamuses/miniconda3/envs/app/bin/poetry run pytest tests/test_desktop_service.py tests/test_desktop_protocol_contract.py -q -k extension
  ```

- Manager/registry：**60 passed, 1 warning in 7.60s**。
- Journey/MCP/startup：**32 passed, 1 warning in 1.45s**。已讀 live fake model 與
  temporary stdio MCP server，沒有 live provider；重用既有 dry-run/apply/restart/update/delete。
- Desktop 第一次：**1 failed, 15 passed, 165 deselected in 0.41s**。
  新 test 錯誤假設會原樣傳出 busy 文字；code 與 retryable 已通過。
  核對 service.py 原有 mapping，實際刻意回傳通用文字
  `The extension operation could not be completed.`。只更正 test 的原契約斷言，
  無 production 變更；同命令再跑 **16 passed, 165 deselected, 1 warning in 0.33s**。
  這是驗收測試假設修正，不是修改既有 Desktop message。

| 必要案例 | Observed evidence |
|---|---|
| 同 revision 競爭與恢復 | `test_cross_process_apply_preserves_successful_update`：alpha/beta ready 0；beta busy，alpha success 1；beta 舊 preview registry-changed，重新 preview ready 1 後 success 2。Registry 1 只有 alpha，beta 無 installed 副本；registry 2 有兩者，各 source hash 與 SKILL bytes 相符；A/B exit 0 |
| Directory fsync 邊界 | `test_cross_process_lock_covers_directory_fsync`：alpha paused directory_fsync 時 JSON 已 revision 1，但獨立 beta fd probe 為 locked；alpha success 1 後 probe available。固定 lock inode 不變、空 bytes、0600；A/B exit 0 |
| Crash 釋鎖 | `test_cross_process_crash_releases_lock_before_revision_read`：alpha 在首個 apply revision read 前持真鎖暫停，beta probe locked；無 registry/installed。終止 alpha 並 join → exit -15，beta 原 revision 0 preview success 1、exit 0，JSON/installed bytes 正確；未 unlink，inode 保持 |
| Root 隔離 | `test_cross_process_apply_uses_separate_state_root_locks`：A 持 X 等待 writer，B 對 Y success 1，才放行 A success 1；各 registry 僅自身 skill；A/B exit 0 |
| Read/writer exceptions | `test_cross_process_apply_exception_releases_locks[read/write]`：注入 OSError/RegistryError，兩例均 ManagementError，原 revision 7 JSON bytes 不變；同 process 重新 apply success 8，beta 重新 preview ready 8、success 9、exit 0，兩 entry 保留。Writer failure 不宣稱回滾 installed 副本 |
| Open/non-busy flock I/O | `test_apply_lock_io_failure_does_not_enter_transaction[open/flock]`：EIO 走 ManagementError，未進 `_apply_locked`、無 registry/installed；去掉 patch 後同 manager success 1 |
| CLI busy | `test_apply_lock_busy_is_slash_command_error`：真固定 fd 持鎖，slash command 回 SlashCommandError/busy，無 registry/installed；release 後 success 1 |
| Desktop busy | `test_extension_apply_maps_manager_lock_conflict_to_busy`：正式 dispatch 將 fake manager 的真 ManagementError 映射為 BUSY_EXTENSION_OPERATION/retryable=True、既有通用文字，無 applied_preview；成功/durable-result/protocol 既有 tests 亦通過 |

- 所有自身 children 均有界 join、關閉 Pipe/Process handles；無殘留 child assertion failure。
  `git diff 4d7d8a5 --check` 與 `git diff --check` 通過。
- 下一步為唯一一次 full suite 與 actual diff review。近期 issue 06 的同 runtime
  full suite 為 1092 tests / 23.64 秒，本次新增 focused 7.60 秒且僅本機離線資料，
  仍適合計劃的 540 秒上限；不啟動 provider/GPU/外部資料工作。
