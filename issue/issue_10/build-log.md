# Issue 10 — 對話式本機 ZIP Skill 安裝：Build Log

本檔是 phase runtime status 與 observed implementation／verification evidence
的唯一來源；目標與未來作法分別由 GOALS、PLANS 及 phase files 擁有。

## Phase Summary

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Scoped installation | Complete | 2026-09-11 | 2026-09-11 | Red and green evidence below | None |
| 02 — Conversational installer | In progress | 2026-09-12 | — | Preflight and red below | None |
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


### 2026-09-11 — Phase 01 green and completion

- Red/test commit: `67f8046`. Production changes are limited to
  `app/agent/extensions/manager.py` and `discovery.py`: optional non-empty set of
  selected skill keys, frozen in preview, scoped authoritative planning and
  rescanning/signature verification, plan revalidation at apply; regular skill ZIP
  files are skipped while malformed files/directories/symlinks retain diagnostics.
  Registry entries still merge from existing state; no persistent format change.
- PASS `poetry run pytest tests/test_extension_manager.py
  tests/test_extension_baseline.py -q`: **27 passed**, 1 warning, 0.38s.
- PASS `poetry run pytest tests/test_extension_registry.py tests/test_extension_mcp.py
  tests/test_extension_skill_startup.py -q`: **24 passed**, 1 warning, 0.30s.
  Same Linux/Conda/cwd procedure as above. Existing MCP exact-binding approval and
  full manager semantics pass. Selected source/revision stale rejection, unchanged
  unselected entries/bytes, source retention and scanner acceptance all observed.
- PASS `git diff --check`. No independent refactor was required. All Phase 01
  acceptance criteria have offline evidence; Phase 01 Complete, Phase 02 eligible.
  Limits: no live-model autonomy claim, no real user installation state touched.


### 2026-09-12 — Phase 02 preflight and initial red

- Phase 01 complete (`adf1917`); live session/graph/tool policy, skill metadata,
  runtime, CLI and Desktop entry/lifecycle code inspected before implementation.
  Common session accepts both entries. Existing skill tool injection avoids any
  Desktop RPC reentry. The only new file-operation helper stays in the public
  installer skill; no new service, dependency, persistent format or protocol.
- In-memory host state belongs to the existing manager module and current
  ChatSession. Exact source, user candidate/update replies and preview token bind
  the action; model-supplied approval is not an input. Source preparation uses
  ordinary bash + the first-party stdlib helper, never downloaded scripts.
- Planned checks remain both Phase 02 command groups. Stop on missing required
  evidence or the plan's authority boundaries; Phase 03 remains Not started.
- RED `poetry run pytest tests/test_skill_adherence.py -q -k 'installer or
  root_document'`: **3 failed, 2 passed, 5 deselected**, 1 warning, 0.32s:
  natural request lacks installer activation, slash skill absent, root missing.
  Added an explicit failing extended-workflow stub to this new test afterwards
  so verification cannot leave the fake normal-graph seam.
- RED (helper subagent) `poetry run pytest tests/test_skill_runtime.py -q -k
  installer_zip`: **17 failed, 17 deselected**, 1 warning, 0.45s; helper absent.
  Tests cover original bundle bytes, selected-only size limits, ZIP path/type
  rejection and prepared-content verification.
- RED (Desktop subagent) `poetry run pytest tests/test_desktop_service.py -q -k
  'conversation_replacement_clears_installer_before_saving_controls or
  session_shutdown_clears_active_session'`: **2 failed, 57 deselected**, 1 warning,
  0.36s; pending state not cleared before replacement/shutdown.
- Commands use the same root/app, Linux Conda activation recorded above. Desktop
  subagent equivalent dispatch was `wsl.exe -d Ubuntu-24.04 --cd
  /home/minervamuses/research-agent-workspace/app
  /home/minervamuses/miniconda3/bin/conda run -n app poetry run pytest ...`.
  Isolated temp filesystem, fake models; red is expected, not phase completion.
