# Issue 08 — Citation 流程：執行計劃

## Plan Overview

- **Plan root:** issue/issue_08。
- **Purpose:** 見 [GOALS.md](GOALS.md)。先讓 CLI 與 turn lifecycle 成為一致的
  單次工作，再完成 Desktop dispatch／catalog 接入和跨介面恢復驗收。
- **Execution mode:** Autonomous within authorization envelope。
  只在使用者日後明確啟動、確認 GOALS 待決契約並核准下列具體範圍後生效；
  本次僅 authoring，不授權實作。
- **Repository shape / risk:** Application / medium。跨 CLI、session、
  Desktop 與可信引用邊界，但使用既有機制和離線小型驗證，不遷移資料。
- **Layout:** 沿用 issue/issue_XX/phases/；根 .gitignore 忽略任意 build/。
  本 bundle 為新建，沒有覆寫原 issue 或既有計劃。

## Source-of-Truth Map

| 資訊 | 唯一 owner |
|---|---|
| 目的、成果、契約、invariants、限制與使用者待決 | GOALS.md |
| 路線、依賴、授權、停止與計劃維護 | PLANS.md |
| 可複製啟動／續作入口 | PROMPTS.md |
| 各階段範圍、planned checks 與 acceptance | phases/phase-*.md |
| Runtime status、真正執行過的結果與 blockers | build-log.md |
| 執行後重大發現／真實 review | context/、code_review/ |

Context／review 有真實內容時才建立；不重複維護 current-phase pointer。

## Confirmed Repository Baseline

2026-09-12 authoring 的唯讀來源如下；不是 application checks 通過證據。

- Root /home/minervamuses/research-agent-workspace；唯一 repository AGENTS.md
  位於根目錄。PowerShell 只作 WSL launcher；Bash／Git 為
  /usr/bin/bash、/usr/bin/git。Conda app Python 3.13.14、
  Poetry 2.4.1、Node v24.18.0、npm 11.16.0 位於
  /home/minervamuses/miniconda3/envs/app/bin。Linux 無 rg，使用 find／grep。
- Branch GUI，HEAD 2870bcd75eb809120f9e4bb7a2ab1668330946d6。
  初始 tracked deletions 是 issue/issue_03 與 issue/issue_10 各八個計劃／review 檔；
  初始 untracked 為 issue_01、issue_02、issue_03(fin)、issue_04、issue_05、
  issue_06、issue_10(fin) 目錄。Authoring 對 364 個 tracked/untracked paths
  留存 hash／missing snapshot 作最後比對；執行時重取當下 baseline，不還原這些變更。
- issue/issue_02/build-log.md 三階段均記 Not started。Live App.tsx composer
  仍是 textarea，service.py 未有可確認的 command catalog projection；
  不能聲稱 issue 02 已完成，也不能在本計劃順便實作它。
- slash_commands.py:485 的 _handle_citation 先 persistent activation；
  :200 保留 built-in，:259 排除 dynamic Citation。chat.py:222–232
  已將 followup_input／skill_name 送進 session.turn，保留 display_input。
  但 chat.py:96–105 的 _command_feeds_agent 只看第一個參數是否 off token，
  與 handler 的單一 token 判斷不同；/citation off topic 會被誤分為 local command，
  並在 :110 的 _display_only_result_text 拒絕 followup。此為同語意契約的直接缺口。
- session.py:956 的 _run_one_shot_skill_turn 明確拒絕 citation；
  :1194 turn_outcome 已有 lock、durable duplicate／retry／exception／cancel；
  duplicate 在實際執行前返回。可以重用，不必加新 turn runner。
- session.py:739–780 的 finalizer 使用 registry 做 gate/render，再保存正式答案。
  Validation error 仍可能是 completed + validation_errors，不得誤判為沒有 cleanup 的
  非 terminal 狀態。:822 activation 強制 normal；:800 teardown 只 reset policy。
- CitationSessionPolicy.service 延遲建立 service；reset 丟 in-memory reference。
  skills/citation/service.py:234–247 先以 asyncio.to_thread 寫 bundle，再 register
  receipt。取消不能保證阻止已開始的磁碟寫入。
- skills/citation/SKILL.md:41 允許 earlier-turn 選擇／授權，:62 sources/source
  描述 session registry；需對齊單次 scope，不能刪掉 visible history 授權能力。
- desktop/service.py:1722 _session_turn 有自己的 busy guard；dynamic Skill
  會傳 result.skill_name，built-in local command 分支拒絕 followup_input。
  只在 allowlist 加 citation 不足以支援真正 agent turn。
- App.tsx:1268 顯示 Citation CLI-only；:300 RestoredTurn 顯示既有
  toolActivities／assistantText。Desktop final-only answer 已有 reducer tests。
- test_citation_e2e.py:268–282 的 fixture 以 env={} 和 RoutingFetcher 跑
  真 graph／citation tool／service；test_turn_finalizer.py:509、:551
  保護 receipt 不漏進 transcript、舊答案不因後續回合改寫。
- test_desktop_conversations.py 已有 canonical restore、tool summary、
  completed duplicate no-replay；test_session_persistence.py 已有失敗／重啟案例。
  它們尚不是 Citation 單次流程完成的證據。
- app/pyproject.toml 使用 pytest，無 formatter/linter 設定；
  desktop/package.json 有 npm test、npm run build，不需要新 test framework。

## Execution Authorization

### 實作啟動前須有的具體授權

僅要求「寫計劃」沒有授權以下修改。日後開始實作前，使用者需確認 GOALS
建議契約及本段範圍；若授權已在後續對話清楚給出，記錄決定，不重問。

預估 production write set 共六個檔案：

1. app/agent/cli/slash_commands.py：Citation 指令改回傳單次工作意圖，保留專用名稱。
2. app/agent/cli/chat.py：分類完整 off token 指令，避免把 off topic 等需求當成 local command。
3. app/agent/session.py：支援 Citation turn scope、normal 記錄／恢復、cleanup。
4. app/skills/citation/SKILL.md：只校正來源 lifetime／後續重啟語意。
5. app/agent/desktop/service.py：重用共同 command 結果，讓 Citation 進入真正 turn。
6. app/desktop/src/App.tsx：將 CLI-only 改為單次工作／normal 的可見說明。

這是同一個跨介面行為變更，不能把 phase 分拆當成規避「focused fix 超過三個
production files」門檻。需要六檔的理由是只改 CLI／session 無法讓 Desktop
dispatch／使用者提示正確，只改 GUI 又無法釋放可信來源；CLI classifier 的
第一個參數判斷也會阻擋合法的自然語言需求，須一起校正。預估數個局部修改與
離線 checks，各命令目標低於十分鐘；沒有 paid-provider／GPU 使用，沒有依賴、
新的 module 或持久狀態維護成本。不承諾尚未量測的工時。

具體 API 變更為 /citation 的 persistent command 改單次語意，以及既有
turn／turn_outcome 的 skill_name 路徑接受 citation。預計不新增 RPC／DTO 欄位，
不改 v1 contract、conversation schema 或 bundle 格式；若 issue 02 整合後
證實需要，先提出確切 shape／caller 影響並取得額外核准。

### Routine actions authorized after launch

- 在已核准六檔與 phase 明列既有 test files 做直接必要的局部修改，
  重用現有 pytest fixtures、fake provider 與 tmp_path；不先寫新的共用 module。
- 執行各 phase 的離線 focused checks、Desktop tests／build，最後一次完整
  Python suite。應以 timeout 保持單次低於十分鐘，不先 install 或 update。
- 更新本 bundle 的實際 build-log、重大 context、真實 review、被證據否定的
  未開始計劃；不新增額外報告、不改 AGENTS.md 或無關 issue。
- 授權 envelope 內完成一個 phase 且證據充分後，自動接下一個 eligible phase。

### Stop and obtain fresh authority

- GOALS 待決尚未確認、上述具體範圍尚未核准，或 issue 02 缺完成證據。
  保留待辦，不自行執行另一個 issue。
- 需改目標、成功條件、保留行為，或接受必要驗證缺失。
- 需超出六個預估 production files；尤其 policy、protocol／DTO、
  reducer、storage 若有缺口先提交直接因果證據與最小 proposed diff。
- 需 dependency／package manager／environment／lockfile 變更、替換 major
  library、改 API／file format／schema／persistent data 超出上述批准範圍。
- 需新增 service、database、worker、queue、cache、storage layer、concurrency
  model、框架／adapter／parallel pipeline、broad refactor 或 persistent module。
- 需新 benchmark／evaluation／fixture／test framework、live provider、model／GPU、
  credentials、外部寫入、真實使用者資料、full-dataset replay 或 sweep。
- 命令預期超過約十分鐘、第二次完整 suite／昂貴重跑，或 necessary UI evidence
  unavailable 且沒有已核准替代。
- 需 commit、push、merge、rebase、切 branch、修改 worktree、deploy 或破壞性操作。

以上來自使用者的 Personal Engineering Defaults，計劃不豁免。
兩次 focused implementation attempts 失敗後停止；一次昂貴嘗試無效後不自行再跑。
需要新授權時說明具體需要、較小替代不足之處、預期時間／使用量／複雜度／維護成本。

## Phase Roadmap

| Phase | 可觀察結果 | Depends on | Phase file |
|---|---|---|---|
| 01 — Citation turn lifecycle | CLI 完成單次可信 Citation；terminal 後釋放來源並恢復 thinking | issue 02 完成且可核對；GOALS 契約與實作範圍已批准 | [phase-01-citation-turn-lifecycle.md](phases/phase-01-citation-turn-lifecycle.md) |
| 02 — Desktop integration | 同一 command 可由 GUI 發現與執行；switch／restore／restart 不重播 | Phase 01 完成及其驗證；issue 02 的 live catalog／menu 可用 | [phase-02-desktop-integration.md](phases/phase-02-desktop-integration.md) |

沿用 issue 08 指定的 issue 02 前置順序。此次 authoring 可先完成全路線提案，
不表示 implementation prerequisites 已滿足。Phase 01 自己驗證 cleanup／gate；
Phase 02 加上跨介面代表驗收與最後回歸，不延後 Phase 01 的必要檢查。

## 共用驗證環境

每個命令均在 WSL Ubuntu Linux，先執行：

```bash
cd /home/minervamuses/research-agent-workspace
source /home/minervamuses/miniconda3/etc/profile.d/conda.sh
conda activate app
cd app
command -v python poetry node npm git
```

確認 language/package tools 均屬 Conda app、Git 為 Linux；不符合則停止，
不能改用 Windows 或 system tools。Phase 標明的路徑／命令以此 cwd 為準。
只用 temporary test outputs；GUI 操作也不得接真 credentials 或 user store。

## Plan Maintenance

- 每次恢復先重新核對 root、runtime、AGENTS、worktree 與外部依賴；依 log 和 roadmap
  找第一個未完成且 dependencies 完成的 phase，不依 conversation memory。
- Required check 失敗或缺證據，不得 Complete，也不得開始 dependent phase。
  未執行不等於通過；無關 failure 分開回報，不順手修。
- 若新 evidence 推翻 single-turn 實作路徑或 issue 02 catalog 假設，先修 roadmap
  和受影響的未開始 phase；移除被否定的 speculative fix，不堆疊防禦工程。
- GOALS 的穩定契約只依使用者新決定修訂；完成／失敗歷史以追加 correction 保存。
- 重大發現才建立 context/phase-01-citation-turn-lifecycle-context.md 或
  context/phase-02-desktop-integration-context.md；真實 review 才建立相應
  code_review/phase-NN-review.md。不用新 workflow engine。

## Overall Completion Criteria

- [ ] 全部 required phase 在 build-log 為 Complete，有逐條 acceptance 對應 evidence。
- [ ] GOALS 成功條件與正式核准的命令／terminal／thinking 契約有直接觀察支持。
- [ ] 必要 focused checks、代表 GUI 操作、Desktop tests／build 與最後一次完整
      Python suite 有結果；必要缺失已補齊或由使用者明確接受。
- [ ] git diff --check 通過，diff 只有授權必要檔案；既有 worktree 變更保留。
- [ ] 恢復、重送與取消限制如實記錄，沒有把 fake model 說成真實模型品質證明。
      完成即停止，不繼續實作其他 issue。

## Authoring Write Set

僅新增 GOALS.md、PLANS.md、PROMPTS.md、build-log.md 與 roadmap 兩個 phase files。
不寫 application、tests、manifests、原 issue、AGENTS.md、context 或 review evidence。
