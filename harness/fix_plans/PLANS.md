# Research Agent Desktop GUI 修復 — Execution Plan

## Plan Profile

- Plan root: `harness/fix_plans`
- Repository shape: local application；一個 Python/Poetry distribution，加上一個 Tauri 2 + React desktop application。
- Runtime: WSL/Linux；Conda environment `app` 提供執行環境，Poetry、npm、Cargo 使用現有 dependency graph。
- Execution mode: 使用者送出 [`PROMPTS.md`](PROMPTS.md) 的 Start/Resume prompt 後，在明確 authorization envelope 內 autonomous 執行。
- Change risk: medium；修復跨 Python/TypeScript/Rust internal protocol 與一個 versioned persistent format，但限於 local single-user application、fake/temp 驗證且不新增 dependency。
- Phase directory: `phases/`；repository `.gitignore` 忽略 `build/`，因此不可用 `build/` 存 durable plan。
- Authoring date: 2026-08-31 Asia/Taipei。

## Source-of-Truth Map

- 穩定產品目標、成功條件、範圍與 invariants：[`GOALS.md`](GOALS.md)
- 使用者原話、已固定產品決策與 deferred boundary：[`user-decisions.md`](user-decisions.md)
- Phase graph、執行演算法、authorization、變更控制與整體完成定義：本檔
- 可直接貼回 coding agent 的開始／恢復／狀態 prompt：[`PROMPTS.md`](PROMPTS.md)
- 各 phase 的 causal scope、acceptance、focused verification 與 handoff：[`phases/`](phases/)
- 唯一 mutable execution status、checkpoint、attempt、blocker、actual command/result 與 commit：[`build-log.md`](build-log.md)
- Material implementation discovery（只有實際需要時才建立）：`context/`
- Actual code-review finding（只有真的執行 review 時才建立）：`code_review/`
- 最強事實來源：執行當下的 live code、tests、manifests、Git state 與實際觀察。

不得在其他文件複製 mutable phase status。計劃中的 command 與 checkbox 不是 evidence。

## Confirmed Authoring Baseline

- Repository root 是 `/home/minervamuses/research-agent-workspace`，supported runtime 是 WSL/Linux。
- Authoring preflight 觀察到 Linux Git `/usr/bin/git` 2.43.0、Conda environment `app` 的 Python 3.13.14，以及 Linux Poetry 2.3.4；executor 必須重新檢查，不能把版本當成永久保證。
- Branch `GUI` 追蹤 `origin/GUI`。Authoring 開始時 HEAD 是 `fa24b086e8dcf5bdae1a8db228b4337e9798df65`。
- 既有 `harness/plans/2026-08-24-desktop-gui-completion/` 是完成的歷史 bundle。它保留當時 evidence；本計劃不回寫其 phase/status。
- CLI source 已預設載入 MCP；GUI `App.tsx` 建立 session 時明確送 `loadMcp: false`，Python desktop service 對缺省值則採 `true`。
- Rust backend 把一般 request timeout 固定為 600 秒，timeout 後形成 fatal/kill；尚無真實 600 秒 incident replay，因此只有 source-confirmed risk。
- 一般 Skill 目前是 session-persistent `/skill <name> [mode]` control，Task mode 穿越 manifest/runtime/state/CLI/Desktop/protocol/UI；Desktop composer 不接受 dynamic Skill command。
- Desktop answer event 目前在 `ChatSession.turn_outcome()` 已完成 finalization、Desktop pre-record wire validation 與 turn persistence後，才把 authoritative answer切成最多16 KiB的`post_finalized answer.chunk`；React再維護 provisional/reconciliation state。Phase 05 attempt 1 已證明真正live token無安全pre-token acceptance seam，USER DECISION 014因此把目標改為移除整條answer-event模擬串流鏈並只回傳`final_only` terminal result。
- Plan log reader 遇到 tool markers 會 degraded/refuse；transcript DTO 只有 `userText`／`assistantText`，React 只呈現 You/Assistant。
- Authoring 本身不執行 application test、build、provider、MCP、Ollama 或 data mutation；後續 actual evidence 只能由 `build-log.md` 記錄。

## Supersession Rules

下列舊 bundle assumptions 已被使用者新決策取代，executor 不得因舊 phase 已 Complete 而恢復它們：

- GUI `loadMcp:false` 不是保留行為；CLI/GUI 都須 default on。
- USER DECISION 014 supersede USER DECISION 006；Normal answer 不再要求live token streaming，也不得保留`post_finalized` answer slicing。唯一正式delivery是完成validation/persistence後的`final_only` terminal result。
- Active Skill dropdown、persistent `/skill` activation 與 Task mode 不再是產品要求。
- 「不得修改 Plan log format」不適用於完成 tool-aware restore 所需的最小 versioned 延伸。
- Fusion 與 Extended Thinking 仍排除；舊 bundle 的 live Extended trials 或 acceptance 不會被本計劃重跑。

## Phase Roadmap / 階段路線圖

| Phase | File | Dependencies | Initial status | Required outcome |
| --- | --- | --- | --- | --- |
| 01 | [`phase-01-mcp-defaults.md`](phases/phase-01-mcp-defaults.md) | none | Not started | CLI regression-protected、GUI MCP default on |
| 02 | [`phase-02-long-request-liveness.md`](phases/phase-02-long-request-liveness.md) | none | Not started | 移除一般 request absolute deadline，保留真 terminal failures |
| 03 | [`phase-03-one-shot-skill-runtime.md`](phases/phase-03-one-shot-skill-runtime.md) | none | Not started | Python-owned dynamic command + one-shot runtime；移除 Task mode core |
| 04 | [`phase-04-desktop-skill-command.md`](phases/phase-04-desktop-skill-command.md) | Phase 03 | Not started | Desktop command route；移除 GUI control/RPC/protocol residue |
| 05 | [`phase-05-normal-live-streaming.md`](phases/phase-05-normal-live-streaming.md) | Phase 04 | Not started | Normal authoritative final-only answer delivery；移除 answer chunk/reconciliation chain |
| 06 | [`phase-06-tool-aware-conversation-restore.md`](phases/phase-06-tool-aware-conversation-restore.md) | Phase 05 | Not started | Versioned tool-aware Plan persistence/transcript/continuation |
| 07 | [`phase-07-integration-acceptance.md`](phases/phase-07-integration-acceptance.md) | Phases 01–06 | Not started | Isolated cross-feature journey、broader checks、delivery audit |

Phases 01、02、03 可依 numeric order 獨立開始。04 必須建立在 03 的 Python contract；05 先等待 04 穩定 Desktop command/protocol/UI surface；06 再改同一 transcript/protocol surface，避免同時移動 streaming 與 persistence contract；07 只在所有前置 phase Complete 後執行。

## Autonomous Execution Algorithm

每次收到 Start/Resume prompt，main agent 執行以下 loop；phase boundary 是 checkpoint，不是自動向使用者詢問的 gate：

1. 完整重讀適用的 `AGENTS.md`、`PROMPTS.md`、`GOALS.md`、`PLANS.md`、`user-decisions.md`、`build-log.md`、候選 phase 與相關 live source/tests。
2. 第一次 write 前完成 project/runtime gate，確認所有 command 都透過 WSL/Linux 與 Conda `app`；記錄 Git HEAD、branch/upstream、dirty-tree ownership。不得把使用者現有 change reset、checkout 或混入不相干 phase。
3. 從 `build-log.md` 與 dependency graph 選第一個 status 為 `Not started` 或 `In progress`、且所有 dependencies 為 `Complete` 的 phase。若一個 phase `Blocked`，在有其他獨立 eligible phase 時跳過，不重複撞同一 blocker。
4. 在 `build-log.md` 記錄 phase start、current hypothesis、attempt number、實際 initial write set、已知 overlap 與最便宜的 rejecting check。
5. 先寫 focused red/characterisation test 或取得等價可重現 evidence，再做最小 production change。一次只改一個主要 causal variable；不得順手修理鄰近問題。
6. 每個 coherent checkpoint 先跑該 phase 的 focused checks、`git diff --check`、scope/diff audit，再把 exact observed result 寫入 `build-log.md`。
7. 只有 Start/Resume prompt 明確授權 local phase commits 時，才建立只含該 checkpoint 與明確指定既有變更的 local commit，記錄 hash；不得 push，除非使用者另有當下明確指示。
8. Acceptance 全部有 evidence 才把 phase 標為 `Complete` 並立刻選下一 eligible phase。Skipped、unavailable、planned 或 inferred 不算 pass。
9. 同一 causal hypothesis 兩次 focused implementation attempt 失敗，或唯一下一步需要 envelope 外 authority 時，記錄 evidence 並把該 path 標 `Blocked`；先繼續其他 eligible work，所有剩餘路徑都 blocked 才一次向使用者提出最小決策。
10. Live evidence 若推翻本計劃，先修復最小 durable plan section、說明原因並重新載入；不得把錯誤假設留在後續 phase。

## Authorization Envelope

`PROMPTS.md` 的推薦 Start/Resume prompt 被使用者實際送出後，才授權以下 future implementation actions；本文件本身不授權寫 application code：

### Routine in-scope actions

- Read repository instructions、source、tests、manifests、logs、Git state；在 WSL/Linux 執行 read-only discovery。
- 修改 phase 明列且有 causal need 的 Python、TypeScript/React、Rust、protocol contract、manifest、system prompt、fixture 與 focused test files。
- 為 USER DECISION 011 做最小 versioned Plan log format/DTO addition，並同步 writer、reader、prompt reconstruction、protocol fixture、Rust/TypeScript type 與 UI；不建立第二套 persistence。
- 為 USER DECISION 012 移除 Task mode 與一般 Skill persistent control chain；允許跨超過三個直接相關 production files，因為該契約目前本來就橫跨 schema/runtime/session/CLI/Desktop。
- 為 USER DECISION 014 移除 Normal `post_finalized answer.chunk` producer、internal protocol event/schema/fixture、React provisional/reconciliation consumer與直接tests；同步保留`session.turn`的`final_only` terminal DTO，不改protocol major version。
- 用既有 fixture seam、fake provider/tool/MCP 與 caller-owned direct `/tmp` child 做 deterministic test；只能操作該次 test 建立且已驗證的 temporary root。
- 執行 phase 列出的 focused tests；Near final 只執行一次 Phase 07 列出的 broader suites/build。
- 在 prompt 明確授權時建立 phase-scoped local commit；保留其他 dirty change unstaged。

### Still requires fresh authority

- 新增 production dependency、改 package manager/environment definition/lockfile。
- Public API、protocol major version、unrelated persistent format、second store/service/queue/worker/cache、generic framework 或 broad graph rewrite。
- Live/paid provider、真實 MCP endpoint、Ollama、full dataset、GPU/model sweep、真實 user store/root 或 credential value access。
- Fusion、Extended Thinking、Citation redesign、first-turn abnormal-loss durability、多 GUI process、issue 02 或其他 non-goal。
- Command 預估超過約十分鐘、重跑 full suite、第二次 full build，除非新 evidence 說明為何必要。
- Branch/worktree change、rebase、merge、remote push、release/deployment；local commit 也只有在 launch prompt 明確授權時才可做。

### Hard prohibitions

- 不修改 `AGENTS.md`。
- 不用 system Python、direct `pip install`、project `.venv`、Windows-native runtime 或 cross-environment file mutation。
- 不刪除/重置使用者變更，不執行 destructive broad path command。
- 不讀、輸出、複製或編輯 secret/credential value。
- 不把planned result、任何`answer.chunk`、post-finalized event、legacy tool text或unchecked disk boolean描述成符合acceptance。

## Expected Write Surfaces

這些是 authoring 時依 live source 推定的初始 surface。每個 phase 開始時必須用 source/tests 重新縮小；新增 file 只有在 phase causal outcome 無法用既有 file 清楚完成時才可，且要先記錄到 `build-log.md`。

### Phase 01

- Production: `app/desktop/src/App.tsx`；如 backend default 本身需 guard，才觸及 `app/agent/desktop/service.py`。
- Tests: `app/tests/test_chat_cli.py`、`app/tests/test_desktop_service.py`、`app/desktop/tests/conversations.test.ts` 或直接覆蓋 session-create payload 的既有 test。

### Phase 02

- Production: `app/desktop/src-tauri/src/backend.rs`。
- Tests: 同檔 Rust unit/integration test 或既有 `app/desktop/src-tauri/src/` backend test surface；不得新增通用 scheduler。

### Phase 03

- Core: `app/agent/skills/manifest_schema.py`、`app/agent/skills/runtime.py`、`app/agent/state.py`、`app/agent/session.py`、`app/agent/thinking/orchestrator.py`。
- CLI: `app/agent/cli/slash_commands.py`、`app/agent/cli/chat.py`、`app/agent/cli/prompting.py`。
- Built-in metadata/docs directly carrying Task mode: `app/skills/_prompt-master/manifest.yaml`、`app/skills/academic-paper-writing/manifest.yaml`、`app/SKILLS_GUIDE.md` 與現行 session system-prompt owner。
- Tests: `app/tests/test_slash_commands.py`、`test_chat_cli.py`、`test_skills.py`、`test_skill_runtime.py`、`test_state.py`、Citation focused regressions。

### Phase 04

- Python Desktop: `app/agent/desktop/service.py`、`fixture_session.py`、`protocol.py`，及直接相關 desktop tests。
- Shared Desktop contract: `app/desktop/protocol/v1/contract.json`、fixtures、`app/desktop/src/protocol.ts`、`app/desktop/src/App.tsx`、相關 CSS/tests、`app/desktop/src-tauri/src/protocol.rs`。
- 移除 `session.list_skills`、`session.activate_skill`、`session.deactivate_skill` 與 active/task restore snapshot；`loadedSkills` 只可保留為 bounded diagnostic catalog，不是 control state。

### Phase 05

- Python delivery owner: `app/agent/desktop/service.py`與`app/tests/test_desktop_answer_stream.py`、`test_desktop_service.py`、`test_turn_finalizer.py`。`app/agent/session.py`/turn finalizer先作read-only ordering oracle；只有rejecting evidence證明既有validation/persistence chokepoint不足時才可最小修改。Graph/execution不再需要streaming seam。
- Desktop contract/rendering: `app/desktop/protocol/v1/contract.json`、fixtures、`app/desktop/src/protocol.ts`、`app/desktop/src/conversations.ts`、`App.tsx`、`app/desktop/tests/answer_stream.test.ts`、`protocol.test.ts`與Rust protocol validator/tests。移除`answer.chunk` inventory/DTO/reconciliation，同步保留`session.turn`的`final_only`/zero-chunk result。
- 不得觸及 Fusion/Extended/Citation implementation files；focused audit只證明它們未因Normal final-only cleanup改變。

### Phase 06

- Persistence/core: `app/agent/turns/plan_log.py`、turn result/record owner、`app/agent/desktop/service.py`、catalog only if selection metadata requires it。
- Contract/UI: transcript DTO contract/fixtures、TypeScript/Rust protocol types、`App.tsx` 與 direct tests。
- Tests: `app/tests/test_plan_mode.py`、`test_desktop_conversations.py`、`test_desktop_service.py`、`test_desktop_protocol_contract.py` 與 existing isolated fixture。

### Phase 07

- Prefer tests/fixture/build-log only。Production change 只允許修復由 integration evidence 直接顯示、且屬 Phases 01–06 acceptance 的 regression；先回到 owning phase 記錄 attempt，不另開 cleanup workstream。

## Verification Strategy

### Cadence

- Phase development：只跑 phase file 明列的最小 selector；先測最小 representative case。
- 跨 Python/TS/Rust contract change：每次 schema checkpoint 同步跑 Python contract test、TypeScript protocol test、Rust protocol test，避免一側漂移。
- Phase transition：focused checks + `git diff --check` + scope/status audit。
- Final：Phase 07 只做一次 broader pass。若失敗，先跑 focused selector；不得無新 hypothesis 重複 full suite/build。

### Common command environment

從 repository root，以 Conda `app` 明確執行 Python：

```bash
conda run -n app bash -lc 'cd /home/minervamuses/research-agent-workspace/app && poetry run pytest ...'
```

Desktop commands 從 `app/desktop/` 執行，仍使用 Linux Node/Cargo toolchain。不得從 Windows PowerShell 直接啟動 package/runtime behavior。

### Planned final broader commands

這些命令目前只是計劃；只有 Phase 07 的 actual log 能宣稱結果：

```bash
cd /home/minervamuses/research-agent-workspace/app
poetry run pytest --ignore=tests/rag/test_component_flow.py --ignore=tests/rag/test_root_identity.py

cd /home/minervamuses/research-agent-workspace/app/desktop
npm test
cargo test --manifest-path src-tauri/Cargo.toml
npm run tauri -- build --no-bundle
```

最後另跑 `git diff --check`。`npm run tauri -- build --no-bundle` 已包含 frontend build，不再額外重跑 `npm run build`；若 live package scripts 已變更，executor 先重新檢查並在 log 說明最小等價命令。

## Persistent and Protocol Change Contract

Phase 06 的預設最小設計如下；實作前若 live code 顯示名稱需調整，可以改名，但不可削弱語意或擴張 framework：

- Plan log 新 writer 記錄 `format_version: 2`；沒有版本欄位的既有 Markdown 視為 legacy v1。
- 一個 turn 保存原始 user text、finalized assistant text，以及 bounded tool activities。每個新 activity 至少含 `call_id`、`name`、`arguments`、`result`、`status`。
- Parser 只在 call identity、name、arguments/result shape、pairing、bounds 全部驗證後，才把 v2 activity 標為 prompt eligible；磁碟不保存或不信任能自行授權 prompt injection 的 `promptEligible=true`。
- Transcript DTO 保留相容欄位 `userText`／`assistantText`，新增 `toolActivities`。一個 bounded activity 的 presentation fields 為 `callId`（可 null）、`name`、`arguments`、`result`、`status`、`promptEligible`；`status` 必須是 contract-defined bounded enum，不接受任意磁碟字串。
- Arguments/result 使用可安全 round-trip 的 bounded canonical representation；內容即使含 Markdown marker、turn heading 或三反引號也不得逃逸成 parser control。Transcript page/wire byte accounting 必須包含所有 activities。
- 完整 generic pair 的 prompt order 是 assistant tool-call → matching tool result → final assistant；missing/duplicate/ambiguous identity 僅 display-only。Fusion candidate 與 Citation-scope activity不得套用 generic reconstruction。
- Legacy v1 tool block 轉成 `callId:null`、`promptEligible:false` 的 display-only activity；無可靠 pair 時不猜測、不拒絕整個 conversation、不注入 prompt。
- Merge/dedup/pagination equality 必須包含 tool activities，否則 restore 可能靜默丟失或重複 tool history。
- 不 bulk migrate 舊檔、不建立 sidecar、不重跑工具、不把 tool text塞進 user role。

## Plan Maintenance / 維護、修訂與停止條件

- 一個 phase 的 source evidence 若顯示預期 write surface 錯誤，先在 `build-log.md` 記錄原因與新 exact file，再編輯；不可事後合理化 broad diff。
- 需要 dependency、另一個 persistence system、protocol major version、extra model call 或 unsafe draft display 才能前進時，停止該 path 並要求 fresh authority。
- Phase 05 必須保留attempt 1的live-token blocker evidence，但新attempt只在證明terminal result前沒有answer text、result在validation/persistence後一次交付、error/cancel/validation failure沒有partial，且`post_finalized answer.chunk`全鏈已移除後才能Complete。
- Phase 06 若 legacy tool identity 不足，只能 display-only；不得猜 call id 或讓 restore 觸發 execution。
- Unrelated test failure 只記錄，不修；若它阻擋 required verification，說明最小選項。
- 每個 phase 最多對同一因果假設做兩次 focused implementation attempt。一次 expensive attempt 無實質改善即停止，不自動開始第二次。

## Overall Completion Definition

只有以下全部成立，整個 plan 才能標 `Complete`：

1. Phases 01–07 都在 `build-log.md` 有 `Complete` status、exact evidence 與 scoped diff/commit disposition。
2. [`GOALS.md`](GOALS.md) 所有 required success conditions 都能映射到 observed test或 isolated journey，不以 inference/plan 取代。
3. MCP default、long-turn liveness、dynamic one-shot Skill、authoritative final-only answer delivery、tool-aware restore/continue 在同一 current codebase 無相互回歸。
4. Citation deferred boundary、Fusion/Extended exclusion、first-turn durability deferral 與 single-GUI assumption 都沒有被偷偷擴張或誤稱已解決。
5. Final broader commands、Tauri no-bundle build、`git diff --check` 與 final scope audit 有實際結果；failure/skip/unavailable 都已說明且不被勾為 pass。
6. 沒有 dependency/lockfile、real data、credential、provider/MCP/Ollama、remote push 或 non-goal change。
7. 使用者取得 concise completion report，列出實際 changed files、checks、known deferrals 與 commit state；remote push 只有另行明確授權後才做。
