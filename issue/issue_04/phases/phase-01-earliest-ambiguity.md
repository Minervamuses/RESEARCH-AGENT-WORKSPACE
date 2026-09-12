# Phase 01 — Earliest ambiguity

## Source Inputs

- [GOALS.md](../GOALS.md)、[PLANS.md](../PLANS.md)、
  [build-log.md](../build-log.md)。
- `issue/04-citation-earliest-version-ambiguity.md`。
- `app/skills/citation/resolution.py`、`service.py`、`authority.py`、
  `providers/base.py`、`types.py`、`tool.py`。
- 下列 Expected Components 中的既有 tests。
  所有 application 路徑相對 repository root。

## Objective

最小年份無法唯一選定或所有候選無年份時，描述式 earliest 請求透過真實
resolver/service/tool 回傳可說明的歧義而不誤保存；可決定與非 earliest
路徑保持原有行為。

## In Scope

局部年份歧義判斷、alternatives、直接必要的 service fallback 保護、
最小 regression tests 與本 phase 完整驗證。

## Non-Goals

以 GOALS 的 Non-Goals 為準；不新增日期、關係推論、identity abstraction，
不改 provider 搜尋、exact lane、schema 或 issue 05 回報流程。
不做其他 cleanup，也不新增獨立測試模組或 fixtures framework。

## Dependencies and Prerequisites

- Depends on：None。正式 implementation 要有使用者 launch 授權。
- Runtime、worktree 與成本條件見 PLANS；使用現有 pytest fake providers。
- **待觀察：** 新 earliest ambiguity 在現有 NeurIPS authority fallback
  是否被覆寫（包含改成 saved、其他 status 或丟失原始 alternatives）。
  用下方 service 反例確認；若原始歧義與候選均完整保留，移除 service patch
  工作，只保留能直接證明保存邊界正確的測試，不保留猜測性 guard。
- 不需要 live API、模型或 GPU。Full suite 的現況時間和 unrelated failures
  未被本次 authoring 驗證；先做 targeted checks，最後限時跑一次。

## Expected Components Affected

| 類別 | 檔案 | 必要理由 |
|---|---|---|
| Production | `app/skills/citation/resolution.py` | 在既有去重之後辨識年份歧義 |
| Conditional production | `app/skills/citation/service.py` | 只在反例證实後，阻止新歧義被 authority fallback 覆寫 |
| Tests | `app/tests/test_citation_resolution.py` | 使用 manifestation helper 驗證選擇與去重 |
| Tests | `app/tests/test_citation_work_resolver.py` | 用既有 fake providers 驗證 ambiguity 不進 refetch |
| Tests | `app/tests/test_citation_authority.py` | service fallback 保護及真實 tool 回傳的離線小型案例 |

`tool.py`、`types.py`、`authority.py`、provider modules 是讀取與驗證邊界，
沒有證據要求改動。若現場顯示另有直接必要變更，先依 PLANS 修訂 scope；
不可順便改造其他流程。

## Authorization and Stop Conditions

遵守 PLANS 的完整授權與停止條件。本 phase 只用現有 in-memory fakes 與
pytest `tmp_path`，不碰真實 citation bundles。沒有 implementation authority
或 runtime 不符時，只能唯讀檢查。

## Implementation and Verification Plan

### Preflight

在 Linux Bash 中使用：

```bash
source /home/minervamuses/miniconda3/etc/profile.d/conda.sh
conda activate app
cd /home/minervamuses/research-agent-workspace
git status --short
git diff --stat
command -v git
command -v python
command -v poetry
python --version
poetry --version
cd app
```

重新閱讀上述 execution path、所用 tests 和初始 diff，保留其他人的改動。
本文件各 pytest 命令均從 `app/`、Conda `app` 執行。先跑一次現有 focused
命令建立 baseline；記錄失敗，不把 baseline 當作修正驗收。

### Red — 最小可區分錯誤的案例

1. 在 `test_citation_resolution.py` 重用 `manifestation()`：
   - Issue 的 2020 published/preprint、不同 DOI 案例應 ambiguous、
     `record is None`，alternatives 含兩個身份。用少量參數變更
     順序、rank／provider 或可通過 identity checks 的 score 差異，
     防止非時間因素消除歧義；不用全排列矩陣。
   - 年份全為 None，涵蓋一個和兩個 distinct identity，都應 ambiguous。
   - 補最小去重保護：同一 canonical DOI 的跨 provider 重複結果、
     同一最小年與較晚年份候選，不能造成假歧義。沿用 canonicalize_doi，
     不新增跨身份合併規則。
   - 補一個較晚年份平手與一個已知/未知年份混合案例；依 GOALS 保留行為。
     既有 2020/2022、指定版本、未指定版本測試直接重用。
2. 在 `test_citation_work_resolver.py` 用既有 SearchProvider/DoiProvider，
   透過真實 `WorkResolver.resolve()` 驗證同年與全缺年份 ambiguity；
   不 mock `decide_resolution()`，並斷言 DOI calls 空、provider states 保留。
3. 在 `test_citation_authority.py` 依既有 service injection 用法：
   - 先讓 resolver 回傳新 earliest ambiguity，附兩個候選；
     intent 使用 `Attention Is All You Need`、2017、earliest，
     venue 使用 `Advances in Neural Information Processing Systems 30`，
     不含 exact identifier；使用真實 AuthorityRegistry 的 allowlisted
     metadata。此測試可 mock resolver，目的限於觀察 fallback 邊界。
   - 預期結果仍 ambiguous，receipt 空、registry 無新增、
     `tmp_path` 下沒有 citation bundle。記錄是否會被現行 fallback
     改寫為 saved 或其他非原始歧義結果，再決定 service guard。
   - 全部 fetcher 都使用現有 injection seam，未預期 URL 直接 raise；
     不可把假的回傳或沒有發出網路當作真實 provider 驗證。

Red 應因目標問題失敗；若因 fixture 不符 identity 而失敗，先修正 fixture，
不要因此降低 production identity 閾值。

### Green — 最小修正

- 保留 `evaluate_record()`、原本空候選處理和 canonical dedup。
  只在去重後的 earliest 分支分析非空 eligible 集合：
  - 無已知 year：`ResolutionDecision("ambiguous", "earliest_year_missing",
    record=None, alternatives=...)`。
  - 最小已知 year 對應兩個以上 distinct dedup keys：
    `ambiguous`、`earliest_year_tie`、`record=None`。
  - 否則回傳最小已知年份的唯一既有 decision，保留其 evidence。
- 缺年份情境的 alternatives 取 eligible 候選；同年平手取最小年候選。
  每個 identity 一筆，沿用最多五筆的回傳慣例，不含被 identity 篩除的
  records。可用穩定鍵決定顯示順序，但不可把顯示順序當成 earliest 證據。
- 兩個 reason codes 使用既有自由字串欄位，不新增 enum、schema version、
  public class 或協議。不要為跨兩處使用建立新 constant module。
- 若 fallback 反例確認：在既有 `CitationService.save()` 判斷內，
  只針對本次 earliest ambiguity 阻止 authority 替代，讓既有 status /
  alternatives 轉換路徑處理。不要一律禁止所有非 eligible 的 authority
  fallback；exact arXiv 與正常 NeurIPS fallback 必須維持。
- 不更動 `WorkResolver` 的 refetch 流程，因它已拒絕非 eligible winner。
  不要求 service/tool 新增 payload 欄位。

### Refactor

無獨立 refactor 工作。只移除本次臨時 diagnostics、重複或不用的新增內容，
保留附近風格；若實質改動 green 後結構，重跑 affected focused checks。

### Verification

**Focused（baseline、red、green 使用同一組既有測試入口；可先以 -k earliest 縮小）：**

```bash
poetry run pytest tests/test_citation_resolution.py tests/test_citation_work_resolver.py tests/test_citation_authority.py tests/test_citation_workflow_tool.py -q
```

**代表性接受情境（新增於上列現有 authority test 檔，納入 focused command）：**

重用現有 fake provider/fetcher 方法，讓真實 WorkResolver 收到兩筆同年、
不同 DOI 且 identity 相符的 records。把真實 CitationService 接到
`create_citation_workflow_tool(service_getter=...)`，用既有 ToolMessage
呼叫方式送出 `action="save"`、`version_kind="earliest"`。
此案例不替換 `service.save`、`resolver.resolve` 或 `decide_resolution`。

直接解析 tool 的 content 與 artifact，確認兩者反映相同 ambiguous 項目，
無 receipt，alternatives 保留 title/year/實際 version kind/identifiers，
fetcher calls 沒有 winner DOI 的 CSL/BibTeX 請求，registry 及 output_dir
沒有新增引用。以最少參數覆蓋同年與全缺年份，勿重建 graph/model harness。
這是 issue 真實 execution path 的離線重現，不宣稱 live end-to-end 或
模型已能正確追問。

**Broader（focused 和代表情境 green 後，最後一次）：**

```bash
timeout 600s poetry run pytest -q
```

這涵蓋既有 save artifact、authority、provider routing、citation e2e、
storage 及其他 application regression。超時 exit 124／required failure
不能視為通過；不要自行第二次 full run，不修不相關失敗。

**Diff：從 repository root 執行：**

```bash
git diff --check
git diff --stat
git status --short
```

不需要 wheel build、linter、live service、model inference 或 GPU，因本修正
不涉及 packaging、介面/依賴或模型行為。未執行的外部驗證明列為範圍限制。

**Failure behavior：** 必要 check 未通過或未取得證據時，維持 In progress
或 Blocked，不開始其他 issue。依 PLANS 的失敗/成本界線停止，不堆疊修補。

## Reliability, Security, and Recovery

唯一直接風險是把尚未選定的 citation 保存：以無 receipt、無 registry
新增、無 citation bundle 和禁止 fallback 覆寫的斷言觀察，不只看 status。
所有檔案副作用在 pytest 暫存目錄內，無資料遷移或線上 rollback 需求。

若 patch 使原有保存路徑失敗，停止、檢查本次局部 diff，修復或只撤回本次
改動後重跑 affected focused checks；不得用 reset/clean 丟棄其他工作，
不得刪除使用者既有 bundles。所有 Git state 操作遵守 PLANS 授權。

## Acceptance Criteria

- [ ] GOALS 的每項條件能對應到本 phase 的 unit／resolver／tool/service
      證據；同年及全缺年份都 ambiguous，沒有單一 winner。
- [ ] 替代候選包含不同身份與足夠描述；重複 provider hits 不誤觸歧義，
      最小年份唯一及非 earliest／exact 路徑維持。
- [ ] 新歧義不 refetch、不被 authority 覆寫、不產生 receipt 或保存副作用；
      若未需要 service patch，保留直接證據說明何以無需修改。
- [ ] Focused、代表接受情境、最後一次 broader suite 與 diff checks
      有實際結果，失敗或缺證據依 PLANS 處理。
- [ ] 實際修改通過 causal scope test；沒有日期/relation、schema、
      dependency 或 issue 05 擴張。

## Evidence to Record and Handoff

- 將 exact commands、工作目錄/runtime、red 與 green 原因、pass/fail、
  tool outcome 關鍵欄位、未執行項及每項驗收對應寫到 `../build-log.md`。
- Authority fallback 的實際反例結果與必要 guard 決策若影響續作，
  記入 `../context/phase-01-earliest-ambiguity-context.md`；不存 routine output。
- 真實 review 才寫 `../code_review/phase-01-earliest-ambiguity-review.md`；
  不必為本局部修正另建 mandatory reviewer 流程。
- 所有必要條件成立才標 Complete，依 PLANS 的 overall completion 交接並停止。
  本計劃沒有 dependent phase；issue 05 是另一次任務，不自動接續。
