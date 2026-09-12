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
