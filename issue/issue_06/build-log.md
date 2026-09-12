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

### 2026-09-12（Asia/Taipei）— Red

- 新增 `test_runtime_rejects_applied_bundle_changed_after_startup`，使用既有
  `_write_skill` / `_apply_skill`，真實 install → startup 後再修改 installed
  SKILL.md、manifest tools/resources、pinned reference；未改 production。
- 在 `app/` 執行
  `conda run -n app /home/minervamuses/miniconda3/envs/app/bin/poetry run pytest tests/test_extension_skill_startup.py -k changed_after_startup -q`：
  **3 failed, 6 deselected, 1 warning in 0.27s**，三者均為
  `DID NOT RAISE ValueError`；不是 import、fixture 或 parser 錯誤。
- 同一 Conda/Poetry 命令的 `env info --executable` 已在 `app/` 證實使用
  `/home/minervamuses/miniconda3/envs/app/bin/python`。
- 這是預期 bug 重現，不是失敗的 implementation attempt。下一步只改計劃三檔。

### 2026-09-12（Asia/Taipei）— Green / 三檔修正

- `metadata.py` 新增預設 None 的欄位；`startup.py` 以 dataclasses.replace
  保存該 registry entry 的已驗證 hash；`runtime.py` 在 resolve/load/工具解析前
  重用 inspect_bundle，拒絕 invalid/hash mismatch/I/O failure，只回固定 ValueError。
  不回傳 parser errors，也不 chain 原始 I/O exception。
- 在 `app/` 執行
  `conda run -n app /home/minervamuses/miniconda3/envs/app/bin/poetry run pytest tests/test_extension_skill_startup.py tests/test_skill_runtime.py tests/test_citation_skill_activation.py -q`：
  **53 passed, 2 warnings in 0.35s**。第一次 focused implementation attempt 成功；
  原三個 Red 案例轉綠，既有 50 案例保持。
- 下一步補齊計劃指定的失敗代表、session/slash 入口與 A/B 版本驗收，
  再做 broader、獨立 review 及唯一一次完整 suite。沒有新增 refactor。

### 2026-09-12（Asia/Taipei）— 代表驗收 / broader

- 僅補兩個核准 test 檔，未改第四個 production 檔，也未改既有 user journey。
  新增 17 個 pytest cases（含先前 3 個 Red），重用 tmp_path、真 install/startup、
  真 ChatSession 與現有 fake graph／deterministic manager model。
- 首次新增驗收 focused run：**1 failed, 66 passed, 2 warnings in 0.63s**。
  唯一失敗為測試誤假設 `ConversationDocument` 有 `model_dump_json()`；
  gate、graph count、狀態、traceback/log 斷言此前已通過。改成
  `conversation_repository.path_for(session_id).read_text()` 驗證實際保存檔，
  沒有改 production 或降低 acceptance。
- 完成後，在 `app/` 執行
  `conda run -n app /home/minervamuses/miniconda3/envs/app/bin/poetry run pytest tests/test_extension_skill_startup.py tests/test_skill_runtime.py tests/test_citation_skill_activation.py -q`：
  **67 passed, 2 warnings in 0.52s**，無 skipped/unavailable。
- Broader exact command（同 cwd/runtime）：
  `conda run -n app /home/minervamuses/miniconda3/envs/app/bin/poetry run pytest tests/test_extension_user_journey.py tests/test_citation_slash_command.py tests/test_skills.py tests/test_skill_adherence.py -q`：
  **42 passed, 1 warning in 2.13s**。包含現有 tmp MCP subprocess 與 CLI/desktop
  本機 ZIP 旅程；`ISSUE10_ACCEPTANCE_ZIP` 未設定，無使用者 archive/live provider。

| Acceptance | 實際 evidence |
|---|---|
| 三種 activation 前異動 | `test_runtime_rejects_applied_bundle_changed_after_startup` 的 SKILL.md、manifest.yaml（tools 與 resources 一起改）、reference.md；全部固定 ValueError；仍損毀時 restart catalog 排除該 Skill |
| 缺檔／invalid YAML／symlink／fingerprint | `test_applied_activation_failure_is_safe` 九例：缺 SKILL/manifest/reference、含 marker 的 invalid YAML、同 bytes 的 root/file symlink、1 KiB file limit、executable bit、Linux chmod 0 讀取失敗；錯誤與 traceback/caplog 無 marker，registry/drop-in bytes 保持 |
| 真 one-shot + generic slash | `test_tampered_one_shot_slash_preserves_citation_before_graph`：handler 先回 followup，再進真 session.turn；graph.states 為空，原 Citation runtime/service/thinking/tools 不變，active context 與實際保存檔無 marker |
| Applied Citation 兩入口 | `test_tampered_applied_citation_activation_preserves_state[direct/slash]`：排除 builtin 的真 applied catalog；direct 保留先前 runtime/service；slash 在 inactive/extended 狀態拋安全 SlashCommandError，不切 normal、不改工具權限 |
| 正常啟用與 A/B 邊界 | `test_applied_revision_stays_pinned_until_restart`：runtime 的 instructions/pinned/tool_access/root、startup hash/revision 直接比對；drop-in B 未 apply 時新舊 startup 都用 A，真 manager.apply 後舊 catalog 仍可 load A，新 startup 使用 B；損毀舊 A 時不偷換最新 registry B |
| 相容性 | `test_legacy_metadata_constructor_has_no_applied_identity` 保持三參數建構；原 built-in/custom/manifest/tools/pinned/total limits tests 及 Citation activation/deactivation/normal thinking tests 全數通過 |

- 更正計劃的測試盤點：live tree 沒有獨立的 extension fingerprint limits test；
  因此按 phase 所允許新增單一 1 KiB limit 案例，未展開 limits matrix。
  runtime 直接重用原 fingerprint，所以沒有改其檔案数/總大小/hash 規則。
- `git diff --check` 通過。下一步為計劃要求的獨立 diff review 與一次 full suite。
