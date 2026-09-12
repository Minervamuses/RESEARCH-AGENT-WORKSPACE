# Issue 06 — Applied Skill 啟動後完整性：執行計劃

## Plan Overview

- **Plan root:** issue/issue_06。
- **Purpose:** 見 [GOALS.md](GOALS.md)。採方案 A，一次 activation 前 rehash；
  用一個 phase 完成基準傳遞、拒絕行為與代表驗收，不拆出空泛探索或驗收專案。
- **Execution mode:** Autonomous within authorization envelope。
  日後使用者明確啟動且核准下述具體 API 變更後生效，本次只做規劃。
- **Repository shape / risk:** Application / medium。涉及 activation 的完整性與
  工具授權邊界，但可在 tmp_path 離線驗證，不改持久資料、不引入隔離框架。
- **Layout:** 沿用 issue/issue_XX/phases/；根 .gitignore 忽略 build/。

## Source-of-Truth Map

| 資訊 | Owner |
|---|---|
| 目的、成果、scope、invariants、限制與待決 | GOALS.md |
| Phase 順序、依賴、授權、停止與修訂規則 | PLANS.md |
| 可複製的開始／續作指令 | PROMPTS.md |
| 實作步驟、planned verification、acceptance | phases/phase-01-activation-integrity.md |
| Runtime phase status 與 observed evidence | build-log.md |
| 實作後的重大發現／實際 review | context/、code_review/ |

只有 build-log.md 維護 phase 狀態。Context 與 review 有真實內容時才建立。

## Confirmed Repository Baseline

以下為 2026-09-12 唯讀觀察，不是 implementation verification：

- Root /home/minervamuses/research-agent-workspace；唯一 applicable repository
  AGENTS.md 在根目錄。PowerShell 只作 WSL launcher，Linux Bash/Git 為
  /usr/bin/bash、/usr/bin/git。Conda app 的 Python 3.13.14、Poetry 2.4.1
  均在 /home/minervamuses/miniconda3/envs/app/bin。Linux 無 rg，使用 find/grep，
  不安裝工具。app/poetry.toml 禁止 Poetry 建立 venv。
- Branch GUI，HEAD 2870bcd75eb809120f9e4bb7a2ab1668330946d6。
  初始 tracked deletions 為 issue/issue_03 的 8 個計劃／review 檔，
  issue/issue_10 的 8 個計劃／review 檔；已有 untracked
  issue/issue_01/、issue/issue_02/、issue/issue_03(fin)/、issue/issue_04/、
  issue/issue_05/、issue/issue_10(fin)/。不得還原、搬移或納入本次修改。
  Authoring 前對 354 個 tracked/untracked 路徑留存 hash／missing snapshot，
  用於結束比對；執行時仍須重新取得當下 baseline。
- startup.py:_load_skill 核對 inspect_bundle 與 registry source_hash 後，
  read_skill_metadata 只回傳 name、description、path。metadata.py:SkillMetadata
  是 frozen dataclass，且被 agent.skills.__init__ 匯出。
- runtime.py:load_skill_runtime 重新讀 manifest、SKILL.md、pinned resources。
  Session 的 _load_skill_runtime 傳入 loaded_skills；one-shot 與 Citation
  均共用此入口，且 load 成功前不變更 active state。因此不預計修改 session。
- discovery.py:inspect_bundle 重用既有 fingerprint，並驗證 manifest/resources；
  scanned.errors 可能帶 YAML 內容，不適合直接回傳使用者。
- agent.skills.__init__ 會 import runtime，discovery import skills.manifest_schema；
  將 discovery 直接加成 runtime 的 top-level import 有 circular-import 風險。
  優先 applied branch 的函式內 import；不為此搬移 package 或造新共用模組。
- test_extension_skill_startup.py 已有 _write_skill、_apply_skill、
  startup 前 tamper、drop-in 變動、builtin collision 的測試。
  test_citation_skill_activation.py 已有 fake graph 與失敗 activation 保留狀態案例。
  test_extension_user_journey.py 的既有旅程涵蓋 apply/update/delete/restart，
  用 deterministic manager model 和暫存本機 MCP，無需 live provider。
- app/pyproject.toml 有 pytest，沒有 formatter/linter。歷史紀錄
  issue/issue_10(fin)/build-log.md 記完整 suite 1031 passed / 27.57s，
  只支持估計一次 timeout 600s 的檢查合理，不代表目前已通過。

## Execution Authorization

### Launch prerequisite

使用者目前只授權新增本 bundle。日後執行時，先確認是否已明確核准：
在匯出的 SkillMetadata 加入 optional applied_source_hash: str | None = None，
原有三參數建構繼續可用，startup 填入已核准 hash，runtime 消費該欄位。
若啟動指令未核准此具體 public API 變更，先完成可供檢視的唯讀 preflight，
說明三檔 diff 預期與既有呼叫相容性，再依 Personal Engineering Defaults
的 public API gate 取得一次授權；不得以本文件自己授權自己。

### Routine actions authorized after launch

前項已核准後，可在同一目標內連續完成：

- 只修改三個 production 檔：app/agent/skills/metadata.py、
  app/agent/extensions/startup.py、app/agent/skills/runtime.py。
  Optional metadata 欄位只存在 session 記憶體，不改 registry serialization。
- 在 app/tests/test_extension_skill_startup.py、
  app/tests/test_citation_skill_activation.py 補最小 regression；
  只有必要時才在既有 test_extension_user_journey.py 加代表旅程斷言。
  重用 pytest、tmp_path、monkeypatch 和既有 fake graph，無新測試框架。
- 執行 phase 的便宜離線 focused checks、代表旅程與最後一次完整 suite。
  測試只在 tmp_path 改 bundle，不碰使用者真實 installed state 或 credentials。
- 維護本計劃的 actual build-log、重大 context、實際 review，以及被證據推翻
  的 roadmap/未開始 phase。完成後停止，不順手修改其他 issue 或文件。

### Stop and obtain fresh authority

- 需改 GOALS、降低必要證據，或將威脅模型擴大為載入中原子／同權限 writer 隔離。
- 新增或替換 production dependency、package manager、環境、lockfile、
  major framework/library，或超出前述核准欄位的 public API、file format、
  schema、persistent data 變更。
- 新增 service/database/queue/worker/cache/storage/concurrency model，
  broad refactor、generic framework、adapter 或並行實作。
- 超過上述三個 production 檔，或有局部替代卻新增 persistent module。
  若真 session/CLI 的代表案例證明需額外修正，先給直接證據與最小第四檔提案。
- 新 benchmark/evaluation/fixture/test framework、full dataset replay、
  exhaustive sweep、live/paid provider、model/GPU workload、外部寫入、
  使用 secrets，或命令預期超過約十分鐘。完整 suite 只跑一次；
  再跑需有新原因且依既有授權門檻處理。
- Commit、push、merge、rebase、切 branch、修改 worktree、deploy、
  破壞性操作或操作使用者真實資料。
- 必要檢查 unavailable 或失敗未解；兩次 focused implementation attempt
  失敗即停止，報原因、證據與最小下一步；一次昂貴嘗試無效不自行重跑。

詢問授權時說明需要、較小方案不足、預期時間／使用量／維護成本。
適用 AGENTS.md 與使用者指示持續優先，AGENTS.md 不得改動。

## Phase Roadmap

| Phase | 可觀察結果 | Depends on | Phase file |
|---|---|---|---|
| 01 — Activation integrity | 啟用前已異動的 applied bundle 被拒絕；正常啟用與 revision 行為保持 | 無其他 phase／issue 技術依賴；須滿足 Launch prerequisite | [phase-01-activation-integrity.md](phases/phase-01-activation-integrity.md) |

Hash 傳遞與 activation gate 是同一條 execution path，只有合在一起才有可驗收
行為。該 phase 自己完成 focused 與跨入口驗證，不把失敗往後推。

## Plan Maintenance

- 從 build-log 與 roadmap 選第一個未完成且依賴完成的 phase，先核對 live
  root/runtime/worktree；不要依對話記憶或多份 current-phase 指標。
- Required check 不通過或未取得證據，不得標 Complete，不得開始 dependent work。
  新測試若原本已通過，先查原因；被反證的 speculative fix 移出計劃。
- 新證據推翻路線時，先修訂 roadmap 與受影響的未開始 phase；active phase
  只在同一核准目標內澄清。穩定 GOALS 改變仍由使用者決定。
- 重要失敗／完成 evidence 不抹除；以 append-only correction 修正 log。
- 重大發現才建 context/phase-01-activation-integrity-context.md；
  真實審查才建 code_review/phase-01-activation-integrity-review.md。
  不設永久 reviewer 或工作流程引擎。

## Overall Completion Criteria

- [ ] Roadmap 所列 phase 在 build-log 為 Complete，且逐項 acceptance 有 evidence。
- [ ] GOALS 的三種內容異動、兩種 session activation 入口、revision/drop-in
      行為、錯誤內容與 preserved behavior 均有直接觀察。
- [ ] Focused、代表旅程、一次完整 suite 通過；無關 failures 分開列，
      必要證據不可用 skipped 代替。降低驗收須使用者明確接受。
- [ ] 安全邊界的獨立 diff review 已解決實際 findings；
      不把 reviewer 敘述或結構 lint 當執行成功證據。
- [ ] git diff --check 通過，diff 限必要檔案，既有使用者變更保留，
      TOCTOU、普通 resource 讀取及 re-apply 的限制如實記錄。完成即停。

## Authoring Write Set

只新增 GOALS.md、PLANS.md、PROMPTS.md、build-log.md、
phases/phase-01-activation-integrity.md；不改原 issue、不實作 application、
不預建 context/review。Authoring validator 不屬 implementation evidence。
