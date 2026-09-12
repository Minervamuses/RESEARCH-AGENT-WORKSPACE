# Issue 05 — Citation 保存結果回報：執行紀錄

本檔是唯一 runtime phase status 與實際 implementation／verification evidence
來源。未來步驟在 phase 檔；本檔只記錄已發生的事。

## Phase Summary

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Save result reporting | In progress | 2026-09-12 | — | Preflight / baseline below | None |

使用 `Not started`、`In progress`、`Blocked`、`Complete`。
必要 acceptance 與 verification 均有實際證據才可標 Complete。

## Evidence Rules

- 記錄 exact command／procedure、runtime／working directory、結果及 acceptance
  對應；分清 observed、historical、planned，不用 skipped 代替 pass。
- 記錄實際變更、重要失敗與未執行原因；新測試直接通過時如實記錄
  characterization，不虛構 red／修正。
- 模型輸入證據必須指出讀取 ToolMessage content 的位置及其先後順序；
  CLI evidence 指向本次實際擷取輸出，不只記 metrics。
- 大型輸出用連結，避免完整 payload、secrets 或 routine narration。
- 重大發現才寫 context，真實 review 才寫 review。矛盾 evidence 都保留，
  釐清前不得 Complete；錯誤紀錄以 append-only correction 修正。

## Activity Log

尚未開始實作，沒有 application tests、live provider 或保存流程的執行證據。
本次只撰寫計劃；authoring validator 結果不代表應用程式已驗收。

日後事件記錄：時間／時區、phase 狀態變化、授權 scope 連結、
實際變更、exact checks／結果、驗收對應、重大發現、未執行限制與 blocker。

### 2026-09-12（Asia/Taipei）— Preflight / baseline

- 使用者要求執行 issue_05 且每一步 commit；授權本計劃與逐步 commit。
  Not started → In progress。唯一 applicable AGENTS 在 repository root；
  已讀 GOALS、PLANS、PROMPTS、phase、log 與相關 live code/tests。
  issue 04 / 05 均無既有 context/code_review。
- Root `/home/minervamuses/research-agent-workspace`，project `app/`，Linux，
  bash `/usr/bin/bash`、Git `/usr/bin/git`，branch `GUI`，起始 HEAD `6b6d8a5`。
  `git status --short`、`git diff --stat` 均空。
- 初始 PATH 優先找到 Linux pipx Poetry 2.3.4；未用它跑 application checks。
  以下共同前置確認 Python 3.13.14、Poetry 2.4.1 與
  `poetry run python -c 'import sys; print(sys.executable)'` 均來自 Conda app：

  ```bash
  source /home/minervamuses/miniconda3/etc/profile.d/conda.sh
  conda activate app
  export PATH="$CONDA_PREFIX/bin:$PATH"
  cd /home/minervamuses/research-agent-workspace/app
  ```

- 外部 prerequisite：issue_04/build-log 的 Complete 與 commits
  `359669b`、`6b6d8a5` 對得上 live resolution 的 earliest 年份歧義、
  service authority guard 及三個相關測試檔。其 72 focused / 1061 full-suite
  passes 是歷史證據，本次不冒充重跑；未發現矛盾。
- Live tool 使用一次 outcome.to_artifact 產生 content/artifact；PolicyToolNode
  保留 ToolMessage，graph tools → agent，session 使用 artifact 做 metrics，
  finalization 寫入答案，CLI 印出 session.turn response。既有 e2e fake 仍讀
  artifact；本次補 content 觀察。維持 schema、production 與其他 issue 範圍。
- Baseline exact command（上述 runtime/cwd）：

  ```bash
  poetry run pytest tests/test_citation_workflow_tool.py tests/test_citation_e2e.py -q
  ```

  **21 passed, 1 warning in 0.41s**。Warning 為既有 LangChain
  allowed_objects pending deprecation；無 failed/skipped/unavailable。
- 下一步僅補兩個既有測試檔：11 狀態序列化、四種真 graph 流程、mixed CLI、
  history / registry / bundle 對照。通過即記 characterization，不製造 red。
  Required checks 依 phase 包含 focused、preserved regressions、最後一次
  timeout 600s full suite 與 diff check。既有 fetcher/模型/embedding fixtures
  可離線使用，issue 04 full suite 歷史約 27 秒，未發現成本門檻變更。
  必要檢查缺證據、範圍外 production 修正或兩次 focused attempt 失敗即停止。
