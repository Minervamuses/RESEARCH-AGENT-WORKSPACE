# Issue 04 — Citation earliest 歧義：執行計劃

## Plan Overview

- **Plan root:** `issue/issue_04`。
- **Purpose:** 見 [GOALS.md](GOALS.md)。在一個 phase 內完成年份歧義判斷、
  保存邊界保護與必要驗證；三者共享同一個「不能誤選並保存」驗收結果，
  不另拆探索、重構或驗證專案。
- **Execution mode:** Autonomous within authorization envelope。
  使用者日後明確要求執行此計劃後才生效；目前只有 authoring 授權。
- **Repository shape / risk:** Application / low。局部 Python 決策修正，
  可用現有離線測試觀察，無資料遷移。
- **Phase directory:** `phases/`，沿用 `issue/issue_03`、
  `issue/issue_10` 慣例；根 `.gitignore` 會忽略任意深度的 `build/`。

## Source-of-Truth Map

| 資訊 | 唯一 owner |
|---|---|
| 穩定目的、範圍、限制、成功條件 | `GOALS.md` |
| 路線、依賴、授權、停止及修訂規則 | `PLANS.md` |
| 可複製啟動與續作指令 | `PROMPTS.md` |
| 本階段詳細步驟與預定驗證 | `phases/phase-01-earliest-ambiguity.md` |
| 唯一 runtime status 與實際驗證證據 | `build-log.md` |
| 開始實作後才存在的重大發現 | `context/` |
| 實際審查後才存在的 findings | `code_review/` |

不預先建立 context 或 review 文件；live repository 與實際觀察優先於過時計劃。

## Confirmed Repository Baseline

以下是 2026-09-12 authoring 的唯讀觀察，不是修正通過的證據。

- Root：`/home/minervamuses/research-agent-workspace`；唯一 applicable
  repository `AGENTS.md` 在根目錄。
- Linux Git：`/usr/bin/git`；shell `/usr/bin/bash`；Conda `app` 的
  Python 3.13.14、Poetry 2.4.1 均位於
  `/home/minervamuses/miniconda3/envs/app/bin/`。
  Windows PowerShell 僅用來呼叫 WSL；base shell 沒有自動啟用 Conda。
- Branch `GUI`，HEAD `2870bcd75eb809120f9e4bb7a2ab1668330946d6`。
  初始沒有 tracked diff，已有未追蹤 `issue/issue_01/`；
  唯讀檢查期間 `issue/issue_02/` 也出現。兩者是本任務以外工作，必須保留。
  續作時重新核對，不把這份 snapshot 當作現在工作樹狀態。
- `resolution.py:339–365` 先篩 eligible，再依 canonical DOI、normalized
  arXiv 或 provider/id 去重。同 identity 依 score 保留代表 record。
  `:367–382` 的 earliest 分支仍用 year、score、rank、provider 選第一筆。
- `providers/base.py` 的 `ProviderRecord` 只有 year 作直接時間欄位，
  但已有 relations、relation_edges、manifestations 等欄位；本計劃不用它們。
- `WorkResolver.resolve()` 在 `resolution.py:548–550` 已直接傳回非
  eligible decision，無須為新歧義另建 provider pipeline。
  `:488–508` 的 exact DOI/arXiv 路徑先於描述搜尋。
- `CitationService.save()` 在 `service.py:95–154` 對部分非 eligible
  結果嘗試 authority fallback；`authority.py:55–66` 可用 title/year/venue
  找到 NeurIPS allowlisted record。這是局部 guard 的待驗證因果依據。
  `service.py:154–170` 已將 alternatives 轉為 `SaveAlternative`。
- `types.py` 已有 ambiguous status 與完整 alternatives 欄位；
  `tool.py` 的 save 已回傳實際 outcome 的 JSON content 和 artifact。
  不需要為本問題改 schema 或重做 issue 05。
- `test_citation_resolution.py` 有 `manifestation()` 和 2020 對 2022
  案例；`test_citation_work_resolver.py` 有記錄 calls 的 fake providers；
  `test_citation_authority.py` 有 service／authority injection 與
  `tmp_path` 範例；`test_citation_workflow_tool.py` 有 ToolMessage 用法。
- 根 AGENTS.md 與 `app/pyproject.toml` 指定 pytest；沒有 formatter/linter
  設定。歷史 `issue/issue_10/build-log.md` 記錄過約 28 秒的完整 suite，
  僅支持先規劃一次有時間上限的本機檢查，不能當作目前測試結果。

## Execution Authorization

### Routine actions authorized after launch

使用者送出 `PROMPTS.md` 的 Start/Resume 指令或等價明確實作要求後：

- 可修改 `app/skills/citation/resolution.py` 的 earliest 選擇；
  若 phase 的反例證實新歧義會被 authority 覆寫，可局部修改
  `app/skills/citation/service.py`。預期一至兩個 production files，
  不新增 persistent module。
- 可在 phase 明列的既有 pytest 檔案新增直接回歸案例，重用 fake、monkeypatch、
  `tmp_path`；可使用既有 reason_code 字串欄位表達本次兩種歧義，
  不變更公開資料結構或格式。
- 可執行 phase 明列的離線 focused checks 與最後一次、預期不超過十分鐘的
  完整 suite；可維護本計劃的 log、重大 context、實際 review 和被證據推翻的
  未開始計劃。無必要不改原 issue、README 或其他文件。
- 不需逐步或逐 phase 再問；完成或遇到下列停止條件才交回使用者。

### Stop and obtain fresh authority

以下保留使用者 Personal Engineering Defaults 的門檻；本計劃不是例外授權：

- 需改變 GOALS 的成果、範圍、既有行為或將必要驗證降為非必要。
- 需新增 production dependency，修改套件管理器、環境定義、lockfile，
  或替換 major library/framework。
- 需改公開 API、schema、protocol、file format 或 persistent data structure。
- 需新增 service/database/queue/worker/cache/儲存層、concurrency model，
  generic framework／adapter／平行 pipeline 或 broad refactor。
- Focused fix 需超過三個 production files，或在可局部修改時新增 persistent
  module；任何超出上述預期 production 範圍的檔案，先用因果證據修訂計劃，
  不以鄰近缺陷作為擴張理由。
- 需建立新的 benchmark/evaluation/regression/fixture/test framework；
  需要 live/paid provider、credentials、model/GPU sweep、full-dataset replay、
  exhaustive search、外部寫入或真實使用者資料操作。
- 命令預期超過約十分鐘、需第二次完整 suite／昂貴重跑，或重要 evidence
  無法取得。不得以 skipped 冒充成功。
- 需 commit、push、merge、rebase、branch/worktree change、deploy 或
  destructive 操作。

兩次 focused implementation attempt 失敗後停止，回報證據、最可能未解原因
和最小下一步；一次 expensive attempt 無效後不得自行再跑。
要求新授權時，說明具體需要、為何較小替代不足及預期時間／使用量／維護成本。
其他 applicable AGENTS.md 持續優先，不修改任何 AGENTS.md。

## Phase Roadmap

| Phase | 可觀察結果 | Depends on | Phase file |
|---|---|---|---|
| 01 — Earliest ambiguity | 同年及全缺年份不誤選；歧義與候選抵達 tool，沒有誤保存；既有可決定案例維持 | None | [phase-01-earliest-ambiguity.md](phases/phase-01-earliest-ambiguity.md) |

同一 phase 依序做最小 red、局部 green、focused／代表流程驗證與最後回歸。
沒有另設 discovery phase：所需 execution path 已於 authoring 閱讀；
fallback 的小型反例屬本次 regression 驗證。

## Plan Maintenance

- 每次開始先核對 root、runtime、worktree、log 與 live code。只從
  `build-log.md` 和本 roadmap 找第一個未完成且 dependencies 已完成的 phase。
- Required check 失敗或缺證據時，phase 不得完成或流入後續工作。
  先處理當前因果假說；遵守上面的失敗次數上限。
- 新證據推翻路徑時，移除已被否定的工作，先改本 roadmap 與受影響未開始
  phase；active phase 只可在既有目標內澄清，不可趁機擴張。
- 穩定目標的改變須使用者決定並先更新 GOALS。已完成 evidence 與重要失敗
  記錄保留，用 append-only correction 修正，不重寫歷史。
- 只在省略會影響後續決策時才建立
  `context/phase-01-earliest-ambiguity-context.md`。
  實際 review 後才可建立
  `code_review/phase-01-earliest-ambiguity-review.md`；本低風險修正
  不要求額外獨立審查流程或新的驗證框架。

## Overall Completion Criteria

- [ ] Roadmap 的每個 phase 在 log 為 Complete，且有逐項 acceptance evidence。
- [ ] GOALS 的代表案例及 preserved behavior 均可對應到實際 test／tool output。
- [ ] Required focused checks 與最後一次完整 suite 通過；若 unavailable 或
      不相關失敗阻塞，先報告並取得使用者對驗證範圍的決定，不自稱已通過。
- [ ] Diff 只含直接必要修正、最小測試及計劃執行紀錄；
      `git diff --check` 通過，其他工作保持不動。
- [ ] 未驗證與明確不處理的限制如實記錄；完成即停止，不順便實作 issue 05。

## Authoring Write Set

本次只建立 GOALS.md、PLANS.md、PROMPTS.md、build-log.md 及 roadmap 的
唯一 phase file，全部位於 `issue/issue_04/`。不覆寫其他 bundle。
