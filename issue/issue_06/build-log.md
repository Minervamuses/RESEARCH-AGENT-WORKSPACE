# Issue 06 — Applied Skill 啟動後完整性：Build Log

此檔是 runtime phase status 與實際 implementation/verification evidence 的唯一來源。
計劃說明未來工作；這裡只記錄已觀察事實。

## Phase Summary

| Phase | Status | Started | Completed | Evidence | Blockers |
|---|---|---|---|---|---|
| 01 — Activation integrity | In progress | 2026-09-12 | — | 下列 preflight 與 baseline | 無 |

可用狀態：Not started、In progress、Blocked、Complete。
只有 acceptance 與 required verification 均有 evidence 才可 Complete。

## Evidence Rules

- 每次記錄 exact command/procedure、runtime/target、簡短結果與 evidence reference。
- 分清 observed、historical、planned；skipped/unavailable 說明原因與殘留限制。
- Acceptance criterion 必須對應到實際檢查，不能以 code shape、phase status、
  fake model 固定文字或 authoring validator 代替。
- 大輸出用路徑引用；不保存 secrets、YAML 敏感內容或整份 transcript。
- 有矛盾證據時保留雙方觀察，先解決再 Complete；更正以 append-only 追加。
- Failed attempt、必要 scope/API 核准、實際 review 與未驗證項均如實記錄。

## Activity Log

尚無實作活動。此 bundle 已撰寫，但沒有執行 application tests、
Skill activation 或實際 recovery；planned checks 都不是通過證據。

未來事件格式：日期與時區、Phase、Status 變動、授權 scope 連結、最小 changes、
exact verification/result、review findings、limitations/blockers、next action、
必要 context/review references。重大更正追加，不抹掉原紀錄。

### 2026-09-12（Asia/Taipei）— Preflight / baseline

- 本次使用者指示「先閱讀AGENTS.md，然後執行issue/issue_06，入口在PROMPTS.md。
  每一步皆需 commit」啟動本計劃，涵蓋所列三 production 檔及 optional
  `SkillMetadata.applied_source_hash: str | None = None` 的相容性變更；每步 commit
  亦已授權。未擴大 public API、persistent schema、依賴或其他 issue。
- 已依 PROMPTS 順序讀取 root AGENTS、GOALS、PLANS、本 log、唯一 phase，
  以及 live startup/discovery/metadata/runtime/session 與既有 tests。
  尚無 context/code_review。只有 root AGENTS 適用。
- Live baseline 更新（取代計劃中的歷史環境理解）：Linux Bash `/usr/bin/bash`、
  Git `/usr/bin/git`，branch `GUI`，HEAD `931684f`，初始 `git status --short`
  為空。`rg` 可用。Python 為 Conda app 的 3.13.14。
- PATH 預設 Poetry 是 Linux pipx 的 2.3.4；Conda app 另有 Poetry 2.4.1。
  後续命令明確用 `/home/minervamuses/miniconda3/envs/app/bin/poetry`，
  以 `conda run -n app` 保持應用程式在 Conda app 執行。
- 未改 production 時，在 `app/` 執行：
  `source /home/minervamuses/miniconda3/etc/profile.d/conda.sh`、`conda activate app`、
  `poetry run pytest tests/test_extension_skill_startup.py tests/test_skill_runtime.py tests/test_citation_skill_activation.py -q`。
  實際 runner 為 PATH 的 Poetry 2.3.4，pytest/packages 位於 Conda app；
  **50 passed, 2 warnings in 0.37s**。警告為 LangChain pending deprecation 與
  現有 ZIP duplicate-name fixture，沒有 application failure。
- 一次 `poetry env info --executable` 誤在 repository root 呼叫，因沒有
  pyproject.toml 失敗；不屬 application test 或 implementation attempt。
- Live code 證實 metadata 丟失 startup hash；兩種 activation 先完成共用 load
  才換 active runtime。採 applied branch 內 import discovery，維持三檔 scope。
  下一步：以真 install/startup 加最小三案例，先觀察 activation 接受異動的 Red。
