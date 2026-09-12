# Issue 05 — Citation 保存結果回報：執行計劃

## Plan Overview

- **Plan root:** `issue/issue_05`。
- **Purpose:** 見 [GOALS.md](GOALS.md)。用一個有界 phase 完成結果完整性、
  模型接收時序、四種代表回覆與 CLI 顯示驗證；不拆獨立探索或重構階段。
- **Execution mode:** Autonomous within authorization envelope。
  使用者日後明確要求執行此計劃後才生效，目前只授權 authoring。
- **Repository shape / risk:** Application / low。主要為離線 pytest 補測，
  無資料遷移；測試證據的能力限制見 GOALS。
- **Phase directory:** 沿用其他 `issue/issue_XX/phases/` 慣例；
  根 `.gitignore` 忽略任意深度 `build/`，因此不用該目錄名稱。

## Source-of-Truth Map

| 資訊 | 唯一 owner |
|---|---|
| 目的、成果、scope、invariants、限制 | GOALS.md |
| 路線、依賴、授權、停止與修訂規則 | PLANS.md |
| 啟動／續作入口 | PROMPTS.md |
| 階段步驟、planned checks、acceptance | phases/phase-01-save-result-reporting.md |
| Runtime status 與實際 implementation evidence | build-log.md |
| 執行後才產生的重大發現／實際 review | context/、code_review/ |

不預先建立 context 或 review 文件，不在其他文件維護「目前 phase」指標。

## Confirmed Repository Baseline

以下為 2026-09-12 authoring 的唯讀觀察，不是 application test 通過證據：

- Root `/home/minervamuses/research-agent-workspace`；唯一 applicable
  repository `AGENTS.md` 在根目錄。Shell `/usr/bin/bash`、
  Git `/usr/bin/git`，Conda `app` Python 3.13.14／Poetry 2.4.1
  均位於 `/home/minervamuses/miniconda3/envs/app/bin/`。
  PowerShell 只作 WSL launcher；base shell 未自動啟用 Conda。
  Linux 未安裝 `rg`，已使用 `grep`／`find`，不需安裝工具。
- Branch `GUI`，HEAD `2870bcd75eb809120f9e4bb7a2ab1668330946d6`；
  初始無 tracked diff；已有 untracked `issue/issue_01/`、
  `issue/issue_02/`、`issue/issue_04/`，均屬既有工作，必須保留。
  執行時重新核對，不將 snapshot 視為最新狀態。
- `tool.py:create_citation_workflow_tool` 的 save 分支先 await
  `service.save`，由一次 `outcome.to_artifact()` 產生 JSON content
  與 artifact，StructuredTool 設為 `content_and_artifact`。
- `graph.py:166–176` 從 state messages 呼叫 model；
  `:323–335` 設定 tools → agent。
  `PolicyToolNode.ainvoke` 保留工具訊息；目前唯讀路徑未發現缺少回傳通道。
  實際訊息與時序仍須以 planned tests 觀察。
- `session.py:647–658,679–780` 將 save artifact 用於 metrics，
  final text 經既有 citation policy 後寫入 conversation／journal。
  真 CLI `chat.py:227–247` await `session.turn` 後印出 response，
  未見額外 citation-save status block。
- `test_citation_workflow_tool.py` 的
  `test_real_tool_call_returns_content_json_identical_to_message_artifact`
  只測單項 `not_found`；`test_citation_save_outcomes.py` 已測
  saved／not_found 的 ordered round trip。
- `test_citation_e2e.py` 已提供 `_make_session`、
  `_seed_fixture_service`、`_workflow_call`、`_workflow_results`，
  可跑真 graph／tool／service。`_SearchSaveModel` 目前直接讀 artifact，
  成功 journey 只有單項；empty search 不是 save all-failure。
- `test_turn_finalizer.py` 已測 mixed／reused／all-failure／多批 metrics
  及不覆寫模型 prose，但只呼叫 finalizer，不能作模型生成順序的證據。
- `tests/citation_fixtures.py:RoutingFetcher` 可離線走正式 providers。
  DOI_B 的 BibTeX 缺 DOI 會被 `service.py:195–196` 補入，
  不能用這點當 failure；需明確錯誤 DOI 等可辨識的 fixture 回應。
  執行時另確認 HTTP 200 的錯誤 DOI BibTeX 會先被 doi.org client 快取，
  同 turn 直接 retry 不會 refetch。Retry 代表案例改用首次 HTTP 503、
  再回正確 fixture；mixed/all-failure 仍用錯 DOI。保留 production 快取語意，
  實際失敗與修訂證據見 build-log / context。
- `app/pyproject.toml` 使用 pytest，無 formatter/linter 設定。
  `issue/issue_10/build-log.md` 曾記錄完整 suite 約 28 秒；
  僅用於估計一次有時間上限的檢查可行，不代表當前 suite 已通過。

## Execution Authorization

### Routine actions authorized after launch

使用者明確啟動本計劃後，且 phase prerequisites 已滿足：

- 可在 `app/tests/test_citation_workflow_tool.py` 與
  `app/tests/test_citation_e2e.py` 補上 phase 明列案例、局部 fake 和斷言，
  重用現有 pytest／fetcher／tmp_path，不新增共用模組或框架。
- 預期 production files 不需改動。若失敗證據證實 `tool.py` 的結果
  呈現有直接缺口，可局部修正；若代表案例支持 Skill 指令缺少必要說明，
  可在 `app/skills/citation/SKILL.md` 局部補充。
  保留 content/artifact 既有格式，不為可讀性另創 serialization protocol。
- 可執行 phase 明列的離線 focused checks，以及最後一次預期不到十分鐘的
  完整 suite；可維護本 bundle 的實際 log、重大 context、review 與被證據
  推翻的未開始計劃。無必要不改原 issue、README 或其他文件。
- 不需逐步再問；完成或出現下列停止條件時交回使用者。

### Stop and obtain fresh authority

保留 Personal Engineering Defaults 的門檻，此計劃不構成例外：

- 需改變 GOALS 的範圍、成果、invariants，或降低必要驗證。
- issue 04 缺少完成證據；記錄外部 prerequisite，不能自行執行其修正。
  如使用者想先做 issue 05，先決定調整順序與剩餘驗證範圍。
- 需新增／替換 production dependency、改套件管理器、環境、lockfile，
  major library/framework、public API、file format、schema 或 persistent data。
- 需新增 service、database、queue、worker、cache、storage layer、
  concurrency model、generic framework／adapter／parallel pipeline，
  或 broad refactor。
- 需要上述預期範圍外的 production 修正，例如 graph／session／policy node；
  先提出直接因果證據與最小 diff 範圍。不得順便改 resolver／authority。
  Focused fix 超過三個 production files，或有局部替代卻新增 persistent
  module，均須新授權。
- 需要新的 benchmark／evaluation／regression／fixture／test framework，
  live／paid provider、真實 model／GPU inference、credentials、外部寫入、
  full-dataset replay、exhaustive sweep 或真實使用者資料操作。
- 命令預期超過約十分鐘、第二次完整 suite／昂貴重跑，或必要證據 unavailable。
  小型離線替代不足時說明缺口，不以 skipped 冒充 pass。
- 需 commit、push、merge、rebase、切 branch、修改 worktree、deploy，
  或 destructive 操作。

兩次 focused implementation attempt 失敗後停止並交付證據、最可能原因、
最小下一步；一次 expensive attempt 無效後不得自行再跑。
詢問新授權時說明具體需要、較小方案不足之處及預期時間／使用量／維護成本。
所有 applicable AGENTS.md 持續優先，且不得修改。

## Phase Roadmap

| Phase | 可觀察結果 | Depends on | Phase file |
|---|---|---|---|
| 01 — Save result reporting | 全狀態抵達 content；四類真 graph 流程及 mixed CLI 回覆與保存事實一致 | issue 04 完成且有可核對 evidence；本 bundle 無其他前置 phase | [phase-01-save-result-reporting.md](phases/phase-01-save-result-reporting.md) |

一個 phase 已覆蓋同一個結果回報邊界。完整性測試、代表流程及回歸驗證都由它
負責，不把本 phase 的驗證延後交給另一個「驗收專案」。

## Plan Maintenance

- 依 live root/runtime/worktree 與 log 做 read-only preflight。
  從 log 及本表找第一個未完成且 prerequisites 滿足的 phase。
- Required check 失敗或缺 evidence 不得 Complete，也不得推進 dependent work。
  如果新增測試直接通過，保留既有 production behavior，記為補齊證據。
- 新證據推翻路徑時先修訂本 roadmap 及受影響的未開始 phase，移除被否定的
  speculative fix；active phase 只在授權目標內澄清。
- GOALS 只有使用者決定改變穩定目標時才修訂。重要失敗與已完成 evidence
  保留，以 append-only correction 修正。
- 重大發現才建立 `context/phase-01-save-result-reporting-context.md`；
  真實 review 才建立 `code_review/phase-01-save-result-reporting-review.md`。
  此低風險工作不需要另建永久 reviewer／orchestrator 流程。

## Overall Completion Criteria

- [ ] Roadmap 全部 phase 在 build-log 為 Complete 並有逐項 acceptance evidence。
- [ ] GOALS 成功條件對應至實際 content、模型呼叫、回覆、CLI、history 與
      filesystem 觀察，不能只用 metrics 或 scripted final text 代替。
- [ ] Required focused checks 與最後一次完整 suite 通過。
      不相關失敗／unavailable 應單獨報告；必要範圍調整須使用者明確接受。
- [ ] Diff 只含必要測試／有因果證據的修正／執行紀錄，
      `git diff --check` 通過；其他工作不變。
- [ ] 如實記錄 fake-model 證據邊界與未執行項；完成即停止。

## Authoring Write Set

本次僅建立本目錄的 GOALS.md、PLANS.md、PROMPTS.md、build-log.md，
以及 roadmap 的唯一 phase file。不覆寫既有 bundle 或原 issue。
