# Issue 04 — Citation earliest 歧義：執行紀錄

本檔是唯一 runtime phase status 與實際 implementation／verification evidence
來源。計劃描述預定工作，本檔只記錄已發生的事情。

## Phase Summary

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Earliest ambiguity | In progress | 2026-09-12 | — | Preflight/baseline below | None |

狀態只用 `Not started`、`In progress`、`Blocked`、`Complete`。
只有 phase 的必要驗收與驗證都有實際證據，才可標 Complete。

## Evidence Rules

- 記錄 exact command/procedure、working directory、runtime、結果、驗收對應。
- 清楚區別觀察、歷史、計劃和推測；skipped/unavailable 不等於 pass。
- 保留重要失敗、修改與更正歷史；不要只留下最後成功結果。
- 只有重大 discovery 才連到 context；只有真實審查才連到 review。
- 不寫 credentials、完整 provider payload、完整 diff 或例行敘事。
- Evidence 衝突時保留兩者，未釐清前不得標 Complete。
- 不在其他文件複製本表的 mutable status。

## Activity Log

尚未開始實作，沒有 application tests、provider calls 或保存流程驗證證據。
本次僅撰寫計劃；authoring validator 的結果不代表應用程式修正已通過。

日後每筆重要紀錄包含：時間與時區、phase、狀態變化、實際改動、exact checks
與結果、未執行項及理由、驗收條件對應、重大 context/review 連結、剩餘 blocker。

### 2026-09-12（Asia/Taipei）— Phase 01 preflight / baseline

- 使用者明確要求執行 issue_04 且每一步 commit；啟動 routine implementation
  與本任務 commit 授權。唯一 phase 無 dependencies，Not started → In progress。
- 已依序讀取根 AGENTS、GOALS、PLANS、既有 log、phase、live code/tests；
  無其他 applicable AGENTS 或既有 context/review。維持年份限定、exact lane、
  identity/dedup 規則及最多五個 alternatives，不擴張 issue 05。
- Root `/home/minervamuses/research-agent-workspace`，branch `GUI`，起始 HEAD
  `92e602b`。`git status --short`、`git diff --stat` 均空；`uname -s` 為 Linux。
- Shell `/usr/bin/bash`，Git `/usr/bin/git`。初始 PATH 優先指向 Linux pipx
  Poetry 2.3.4；未用它執行測試。指定既有 Conda app bin 優先後，確認 Python
  3.13.14、Poetry 2.4.1 皆位於 `/home/minervamuses/miniconda3/envs/app/bin/`，
  `poetry run python -c 'import sys; print(sys.executable)'` 也為該環境 Python。
- 以下為本次所有 pytest 命令的共同前置（working directory 為 root/app）：

  ```bash
  source /home/minervamuses/miniconda3/etc/profile.d/conda.sh
  conda activate app
  export PATH="$CONDA_PREFIX/bin:$PATH"
  ```

- Baseline exact command：

  ```bash
  poetry run pytest tests/test_citation_resolution.py tests/test_citation_work_resolver.py tests/test_citation_authority.py tests/test_citation_workflow_tool.py -q
  ```

  結果 **54 passed, 1 warning in 0.44s**。Warning 為既有 LangChain
  `allowed_objects` pending deprecation；這是 baseline，不是修正驗收。
- 現場仍有 earliest 非時間排序與 authority fallback 覆寫風險；下一步加入
  最小 red/characterization。所有 provider 使用離線 injection，寫入限 tmp_path。
