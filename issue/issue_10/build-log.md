# Issue 10 — 對話式本機 ZIP Skill 安裝：Build Log

本檔是 phase runtime status 與 observed implementation／verification evidence
的唯一來源；目標與未來作法分別由 GOALS、PLANS 及 phase files 擁有。

## Phase Summary

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Scoped installation | In progress | 2026-09-11 | — | Preflight and red below | None |
| 02 — Conversational installer | Not started | — | — | — | None |
| 03 — Acceptance and documentation | Not started | — | — | — | None |

只使用 `Not started`、`In progress`、`Blocked`、`Complete`。
Required acceptance 與 checks 有觀察證據後才能標 Complete。

## Evidence Rules

- 每次實作記錄時間、phase、實際修改、exact command/procedure、環境、結果、
  限制與下一步；可連結大型輸出，不貼 secrets、全 diff 或無關逐步流水帳。
- 區分 observed、historical、planned、skipped、unavailable；fake model
  可證明 host integration，不能證明真實模型可自主選對工具。
- 中斷後先對照 live code/worktree 與既有 evidence，不盲目重做套用或刪除。
- 新證據與舊記錄矛盾時保留兩者，追加 correction，必要時標 Blocked；不能
  擦掉失敗歷史以配合原計畫。

## Activity Log

目前沒有 implementation activity。此 bundle 僅完成 authoring；各 phase 的
planned application checks 尚未執行，不將計畫驗證或先前研究測試算作實作證據。


### 2026-09-11 — Phase 01 preflight and red

- Observed runtime: root `/home/minervamuses/research-agent-workspace`, Linux
  WSL Ubuntu-24.04, `/usr/bin/git`, branch `GUI`, HEAD `66b0e5e`, clean worktree.
  PowerShell dispatches Linux bash only. Conda prefix
  `/home/minervamuses/miniconda3/envs/app`; Python 3.13.14, Poetry 2.4.1.
  Read root/applicable AGENTS and all required plan inputs; no nested AGENTS,
  context or code_review files exist. `rg` unavailable; used `find`/`grep`/`sed`.
  First discovery commands had shell quoting/final CR errors and did not mutate
  files; rerun with literal stdin scripts and a final comment passed the gate.
- Scope confirmed: selected skill in-memory preview/apply scope, ZIP coexistence,
  minimum existing-test regressions. No ZIP orchestration, protocol/schema,
  dependency or MCP-approval changes. Stop conditions remain as in PLANS.
- Existing characterization PASS: `poetry run pytest
  tests/test_extension_manager.py tests/test_extension_baseline.py -q`:
  **11 passed**, 1 upstream deprecation warning, 0.26s.
- New tests cover selected add/update alongside unselected skill/MCP add/update/
  delete, entries/source/managed bytes, frozen scope, invalid/deleted selections,
  stale source/revision, extra model operations, collision checks, ZIP coexistence.
- RED command: `poetry run pytest tests/test_extension_manager.py
  tests/test_extension_baseline.py -q -k 'selected_skill or
  ignores_only_regular_zip_sources'`: **16 failed, 11 deselected**, 1 warning,
  0.34s. Fifteen failures are missing `selected_skill_keys` API; scanner failure
  exposes `skill:pending.ZIP`. An earlier invocation of this same command failed
  collection due to a missing bracket in a new test; corrected before valid red.
  These are observed offline subagent runs, not historical/model autonomy claims.
- All pytest commands here run after `cd /home/minervamuses/research-agent-workspace/app;
  source /home/minervamuses/miniconda3/etc/profile.d/conda.sh; conda activate app`.
  Test filesystem writes use pytest temporary directories only; no live providers.
- Current conversation explicitly requests a commit for each change step. Commit
  this red/test step separately; no push, branch change, or AGENTS edit authorized.
  Phase 02 remains Not started until Phase 01 required checks pass.
