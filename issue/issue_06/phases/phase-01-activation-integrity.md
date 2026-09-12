# Phase 01 — Applied Skill activation integrity

## Source Inputs

- [GOALS.md](../GOALS.md)、[PLANS.md](../PLANS.md)、
  [原 issue](../../06-extension-skill-post-startup-integrity.md)。
- app/agent/extensions/{startup,discovery,registry}.py、
  app/agent/skills/{metadata,runtime}.py、app/agent/session.py。
- app/tests/test_extension_skill_startup.py、test_citation_skill_activation.py、
  test_skill_runtime.py、test_extension_user_journey.py。

## Objective

當 applied Skill 在 session 啟動後、下一次 activation 前被修改，
runtime 以啟動時核准 hash 拒絕載入；錯誤可理解且不洩漏內容，
正常 activation 與 apply/restart 的版本邊界保持。

## In Scope

啟動 hash 的 optional metadata 傳遞、共用 runtime 的一次 precheck、
兩個 session activation 入口及錯誤顯示的最小驗收。
GOALS 擁有穩定的保護範圍與限制，本檔只定義實作與 verification。

## Non-Goals

不採 startup snapshot 或 pre/post 雙掃描，不改 registry 或 Session 架構，
不修 issue 07，不把安全回歸擴大成全組合 fuzz/benchmark。
其他 non-goals 見 GOALS。

## Dependencies and Prerequisites

- 無其他 phase/issue 的技術依賴；須明確啟動並滿足 PLANS Launch prerequisite。
- 使用 Linux、Conda app、現有 Poetry/pytest；沒有新套件、真實 model 或 provider。
- **Unresolved technical preflight：** 確認當時 package import 順序與測試 fixture。
  已知 agent.skills.__init__ 匯入 runtime、discovery 匯入 skills.manifest_schema；
  優先在 applied 檢查分支內 import inspect_bundle，避免 circular import。
  如此局部接法不足，先報根因，不搬移整個 package。
- 模型/graph 在離線 fixture 可替換，startup/metadata/hash/runtime/session gate
  必須是真實路徑，不可 mock 掉驗收核心。

## Expected Components Affected

| 類別 | 預計檔案／作用 |
|---|---|
| Production 1 | app/agent/skills/metadata.py：optional applied_source_hash，預設 None |
| Production 2 | app/agent/extensions/startup.py：_load_skill 傳遞已核准 registry hash |
| Production 3 | app/agent/skills/runtime.py：只對 applied metadata 啟用前檢查 |
| Tests | app/tests/test_extension_skill_startup.py：真 apply/startup/load 與異動案例 |
| Tests | app/tests/test_citation_skill_activation.py：session 兩入口、狀態保留與可見錯誤 |
| 有證據才改 Tests | app/tests/test_extension_user_journey.py：既有版本旅程缺少的斷言 |

Discovery、registry、session、CLI/desktop 只讀作行為依據，預期不改。
不需要新的 persistent module 或測試框架。

## Authorization and Stop Conditions

沿用 PLANS 的 launch、routine 與 fresh-authority gates。
若需額外 production 檔或要求普通 file/shell 工具也讀 immutable bytes，
先停止，提供 causal evidence 與最小提案。
兩次 focused attempt 失敗的上限同樣適用；不堆疊 speculative fixes。

## Implementation and Verification Plan

### Preflight

1. 唯讀確認 root、所有 AGENTS、branch/status 與既有變更；核對 metadata public
   type 的具體授權。不能還原既有 issue 文件搬移。
2. 確認上述 source/test paths 與 fixture；以 startup helper 建立 tmp_path
   的 installed A，保存 startup catalog/revision、instructions/tool access 基準。
3. 從 app 以既有單元測試取得 cheap baseline（命令見下），
   將已存在 failure 與新 failure 分開。保持 production code 未改。

### Red — 最小可辨別檢查

在 test_extension_skill_startup.py 重用 _write_skill/_apply_skill，為 bundle 加一個
pinned reference；以同一 fixture 的三個小案例，先 startup，再改 installed：
SKILL.md instructions、manifest 的 tools/resources、pinned bytes。
下一次 load_skill_runtime 應拒絕，舊 code 預計失敗；必須記錄實際失敗原因，
不可把 import/fixture failure 當作 bug 重現。

另加必要 failure representatives：移除 required 檔案、invalid YAML 含敏感 marker、
bundle-root 或內部檔案換成 symlink（全部在 tmp_path）。
重用現有 fingerprint limits 測試，只有新 gate 接法缺證據時加一個小 limit 案例；
不建廣泛矩陣。來源檔案已變更但 basename/hash-dir 名稱未改，不能以目錄名當驗證。

### Green — 最小修正

1. 對已核准的 optional SkillMetadata 欄位保留 None 預設及舊建構呼叫。
   Built-in/custom discovery 不填；startup 成功驗證後填 entry.source_hash，
   不從 path basename 推導，也不另造 parallel registry。
2. Runtime 找到 metadata 後、讀取 manifest/instructions/pinned 與解算工具前，
   applied branch 對 metadata.path.parent 原始路徑呼叫 inspect_bundle。
   先檢查再做 .resolve()，讓 bundle-root symlink 不被 normalization 隱去。
   用 metadata.name 的正式身分與原 startup hash，禁止改查最新 registry。
3. 掃描 invalid、hash mismatch 或必要 I/O 失敗，用固定 ValueError：
   applied bundle changed; restart or re-apply required。
   可帶可信 Skill ID，不串接 scanned.errors、parser text 或異動檔案內容；
   避免 exception chaining 將原始敏感內容送到使用者可見 traceback/log。
4. Gate 通過後沿用既有 lazy runtime 載入、manifest validation、tool broker、
   pinned limits、total context limits 與 active state 順序。未帶 hash 的 metadata
   維持舊路徑，不增加全 catalog 預載。
5. 不額外加 postcheck 或 bytes snapshot。這一步的保證與剩餘 TOCTOU
   邊界以 GOALS 為準；若所需安全目標已變，先修訂範圍取得授權。

### Refactor

無獨立 refactor 工作。只整理這三個檔內因本次修改產生的重複或無用內容；
行為綠燈後才做，若有實質變化重跑 focused check。

### Verification — 命令與代表旅程

以下是 planned commands，authoring 未執行。每次從 Linux 環境開始：

```bash
source /home/minervamuses/miniconda3/etc/profile.d/conda.sh
conda activate app
cd /home/minervamuses/research-agent-workspace/app
```

**Focused baseline 與修改後 gate：**

```bash
poetry run pytest tests/test_extension_skill_startup.py tests/test_skill_runtime.py tests/test_citation_skill_activation.py -q
```

**Session 代表驗收（補在上述既有 tests，隨 focused command 執行）：**

- 真 startup catalog 注入真 ChatSession，使用既有 fake graph 僅攔住模型。
  Session 存活後修改 installed A；one-shot session.turn(skill_name=...) 必須
  在 graph 執行前失敗，記錄 graph call count=0。先前 Citation active 時，
  runtime、service marker、thinking 不應因失敗被清理或取代。
- 引用三種變更的 runtime gate 證據，session 入口各用一個代表變更即可，
  不把每個變更乘上所有入口。Applied Citation fixture 以獨立 tmp config／
  catalog 明確排除 built-in，經真 apply/startup 產生可驗證的 citation entry，
  再用 activate_citation_skill() 觸發拒絕。
  這是共用入口的受控 fixture；不是正式允許覆蓋內建 Citation。
- 在同一測試模組用既有 parse_slash_command／execute_slash_command。
  Generic Skill 先取得 SlashCommandResult，再把 followup_input 與 skill_name
  傳入真 session.turn，驗證安全的 ValueError；generic slash handler 本身尚未
  activation，不能要求它立即丟 SlashCommandError。/citation 則在 handler
  直接 activation，應捕捉 SlashCommandError。兩條路徑的 message 均有固定
  指引且沒有敏感 marker，沿用 CLI 既有錯誤格式，不改 CLI exception contract。
  一般內建 Citation 的 existing tests 仍必須通過。

**Broader extension/restart 與入口回歸：**

```bash
poetry run pytest tests/test_extension_user_journey.py tests/test_citation_slash_command.py tests/test_skills.py tests/test_skill_adherence.py -q
```

使用 existing journey 或在 startup test 補最小斷言，直接觀察：
clean A 正常 → drop-in B 尚未 apply 時，舊 catalog 與新 startup 仍用 A →
normal apply B（新的 hash）後舊 catalog 仍用 A → restart catalog 使用 B。
驗證 instructions、pinned content、tool_access、revision/root；不只看 status 字串。
既有 tmp MCP subprocess 是本機 fixture，不連外；不設 ISSUE10_ACCEPTANCE_ZIP
指向使用者真檔，不執行任意外部腳本。

**最後一次完整 suite：**

```bash
timeout 600s poetry run pytest -q
```

只在 focused/代表旅程通過且無已知昂貴外部測試時執行一次。
與本案無關 failure 分開報告；不能為得到全綠修別的 issue。
若必要範圍 unavailable 或 timeout，不記 pass，也不自行反覆重跑。

**Diff 檢查（repository root）：**

```bash
git diff --check
git diff --stat
git status --short
```

**獨立 review：** 以 fresh agent/context 唯讀檢查三檔 diff、acceptance 與 log，
特別檢視基準來源、gate 順序、builtin 分支、import cycle、敏感錯誤與保證範圍。
不必另建工具或重跑全 suite。實際 findings 才寫 review file，必要修正後重跑
受影響的 focused checks。Required finding 未解，不可 Complete。

**Manual/external：** 無必要 live provider／LLM／GUI 操作；離線測試驗證的是
真 host/session 邊界，不是模型生成品質或所有 Desktop rendering 行為。
若 production 入口證據出現差異，最小重現後依 PLANS 決定是否需擴大修正。

**Failure behavior：** 必要測試或 acceptance 不通過，保持 In progress/Blocked，
不得 Complete。先判別是現有問題、新 patch 還是被反證的計劃，再做有界修正。

## Reliability, Security, and Recovery

測試只改 tmp_path 的 installed copy；真實 registry/drop-in 不受影響。
拒絕不自動刪除或修復任何內容，也不自動切到新 revision。
以「保留損毀時 restart 仍拒絕」觀察安全失敗；驗證正常新版本 B 的 apply/restart
恢復有效功能，不宣稱 unchanged re-apply 能修好損毀 A。
若 patch 失敗，保留未完成狀態並局部修正；要回復本次 diff 時逐段處理，
不使用 reset/checkout 清掉使用者工作。

## Acceptance Criteria

- [ ] GOALS 三種 activation 前異動各有真 hash/runtime 拒絕證據。
- [ ] 缺檔、invalid YAML 敏感 marker、symlink 與既有 limits 不會因 gate 接法漏過；
      error/message 無敏感內容。
- [ ] 真 one-shot 與受控 applied Citation activation 均在 active state 改變前失敗；
      one-shot 未進入 graph；正常 builtin Citation 不退化。
- [ ] A/drop-in B/apply B/restart B 的內容與 revision 觀察符合 GOALS；
      runtime 不採最新 registry 取代該 session 基準。
- [ ] 舊 metadata 建構、built-in/custom skills_dir、manifest/tools/pinned limits
      的 focused tests 保持；focused、broader、一次完整 suite 有 evidence。
- [ ] 獨立 diff review 必要 findings 解決；diff 只含核准範圍，LF/diff check 通過，
      未實測或 out-of-scope 的完整性不宣稱已保證。

## Evidence to Record

在 ../build-log.md 記授權、baseline/red/green 的實際命令與結果、每項 acceptance
對應的 test node／觀察、suite 時間與結果、review findings 和限制。
重大新事實才建 ../context/phase-01-activation-integrity-context.md；
真 review 才建 ../code_review/phase-01-activation-integrity-review.md。
不把本文件的 planned command 或 authoring lint 寫成 runtime pass。

## Handoff

所有 required acceptance 有觀察才在 build-log 標 Complete；
依 PLANS overall completion 確認結果後停止。
若缺授權或證據，記明阻礙與最小下一步交回；不開始 issue 07 或其他改進。
