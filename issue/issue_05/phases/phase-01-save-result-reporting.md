# Phase 01 — Citation 保存結果的完整回報與代表流程

## Source Inputs

- [GOALS](../GOALS.md)、[PLANS](../PLANS.md) 與原
  `issue/05-citation-save-result-reporting.md`。
- `app/tests/test_citation_workflow_tool.py`、
  `app/tests/test_citation_e2e.py`、`app/tests/citation_fixtures.py`。
- `app/tests/test_citation_save_outcomes.py`、
  `app/tests/test_turn_finalizer.py`、`app/tests/test_chat_cli.py`。
- PLANS baseline 列出的 tool／service／graph／session／CLI 原始碼。
  下列 repository paths 皆相對於 repository root，非本 phases/ 目錄。

## Objective

在既有正式執行路徑上，從 tool content 讀取的保存事實先於最終答案生成，
四類代表結果都有可核對回覆；其中 mixed case 實際抵達 CLI 並與 history 一致。

## In Scope

- 全部現有 SaveItemStatus 的 ToolMessage content 完整性。
- 真 graph 配 deterministic model、真 CitationService 配離線 provider fetcher；
  只補最小代表案例，不重測每種 status 的 resolver 成因。
- 同一 turn retry 的工具呼叫／batch 與作品對應，以及實際成功／失敗的 bundle。
- 有直接失敗證據時才做 PLANS 已列明的局部 production 修正。

## Non-Goals

GOALS 的所有非目標持續適用。本 phase 不新增 status UI、provider 驗證、
schema、finalizer、共用 fake module 或新的測試框架。

## Dependencies and Prerequisites

- 本計劃已被使用者明確要求執行。
- 按原 issue 順序，先讀 `issue/issue_04/build-log.md` 的完成 evidence，
  並對照 live resolver/service 與其相關測試；有矛盾不能僅信 Complete 標記。
  缺少證據時記錄 Blocked／回報，不代為做 issue 04。
- Linux／Conda `app`／Poetry 環境及必要已安裝依賴可用。
- **Unresolved：** 四種代表流程是否揭露 production 缺口。
  先以現有 fixture 建立下列有界觀察；若通過，保留 production 原狀。
- **Unresolved：** 完整 suite 實作時是否仍可離線且在成本範圍內；
  preflight 查現有 fixtures、近期 log 與 test configuration，不呼叫 paid provider
  來確認環境。

## Expected Components Affected

- 預期修改：`app/tests/test_citation_workflow_tool.py`、
  `app/tests/test_citation_e2e.py`。局部 helper 留在既有檔案中。
- 只有因果證據支持才修改：`app/skills/citation/tool.py`、
  `app/skills/citation/SKILL.md`，且不得改既有 content/artifact 格式。
- 唯讀與既有回歸：types、service、resolver、graph、policy_node、session、
  session_policy、CLI、test_turn_finalizer、test_chat_cli。
  原 issue 文件不需為測試而修改。

## Authorization and Stop Conditions

遵守 PLANS 的完整 envelope；其他 production 檔案若出現已證實問題，
先報告具體因果與最小修正範圍，不擴寫本 phase。
即使測試資料含 DOI 也只能送入 injected fetcher；不得連真實 provider。
缺 issue 04 evidence 或 required check 未通過時，本 phase 不得完成。

## Implementation and Verification Plan

### Preflight

1. 核對 applicable instructions、root/runtime、branch／diff、log、
   issue 04 prerequisite。保留所有既有變更。
2. 重讀 `tool.py` 的 save 分支、`SaveBatchOutcome`、
   `PolicyToolNode.ainvoke`、`graph.py` 的 tool → agent 邊、
   `session.finalize_and_record` 與 CLI 的 response 輸出。
3. 閱讀既有 focused tests，確認可注入 fake model、provider fetcher 與
   `tmp_path`；必要外部邊界都已替換後，跑下面 focused command 作 baseline。

### Characterization / Red

優先補現有測試，不建立新 framework。純補驗證允許新增測試直接 green；
只有觀察到錯誤才要求能區分該 bug 的 red，不故意破壞正確程式。

1. 在 workflow tool test 擴充真正 tool-call envelope 的測試。
   用既有 outcome types 構造逐狀態結果，參數化覆蓋 11 種狀態，
   分成符合 `works` 1–10 限制的呼叫，**不要把 11 項塞進同一批**。
   驗證 `Actual citation save result:\n` 後的 JSON 等於 artifact
   與 service 提供的 outcome，並保留原 index／label／reason／receipt／
   alternatives／order。工具正常返回的 failure item 仍是 failure。
   該測試只證明序列化通道，不聲稱跑過每種 provider failure。
2. 在 e2e 既有 fake-model 結構內，從 `ToolMessage.content` 的 JSON
   解讀 outcome。artifact 只能在測試斷言作對照，不用來決定模型回覆。
   既有成功 journey 也改為經 content 讀取。
3. 新 fake 在 `invoke(messages)` 保存實際收到的訊息快照；
   呼叫工具之前不得有本次保存結果，回覆時必須存在 matching tool_call_id
   的 ToolMessage。回覆逐項由 decoded content 產生，不預寫完整答案、
   不依測試預期列表或共享 service 物件假裝模型已取得事實。
   測試 oracle 可獨立對照期望狀態與實際 files／registry。
   不以 `make_astream_graph` 重播預製 events 代替真 graph。

### Green — 最小完整代表案例

重用 `_make_session`、`_seed_fixture_service`、`_workflow_call`、
`_workflow_results` 與 `RoutingFetcher`。每個案例使用隔離 `tmp_path`，
provider hub 用 `env={}` 並注入 fetcher。未知 URL 立即拒絕，不 fallback 到網路。
小型 fetcher 包裝置於本測試檔；不改現有 shared fixture 的全部行為。

| 情境 | 工具／儲存安排 | 必須觀察的答案與副作用 |
|---|---|---|
| 全成功含 reused | 先在同一 service 以 fixture 保存 A 作準備，再以 A、B 執行受測批次，得到 A reused、B saved | 回覆分清重用／新保存；兩項 receipt 對應既有／新 bundle；A 的內容不改寫，唯一 bundles 為 2 |
| 全失敗 | 真 save 呼叫至少一項；以穩定錯誤 DOI 的 BibTeX 觸發 verification_failed，或既有有界 failed intent | 模型收到正常 ToolMessage 的失敗 item／原因；答案不宣稱成功；registry／bundle 不增加 |
| 混合成功／失敗 | 同批 A 正常，B 的 BibTeX 回錯誤 DOI，得到 saved＋verification_failed | 逐項回覆 A 已保存、B 失敗原因；只生成 A 的 bundle；以真 CLI 輸出驗收 |
| 同 turn retry 成功 | B 第一次 BibTeX 回錯 DOI，下一次同作品 save 回正確 fixture；由收到失敗的 fake 發出第二次 call | 第二次 call 發生在第一次結果之後；保留兩個不同 call_id／batch_id，答案說明先前失敗、後續成功；唯一 bundle 為 1 |

DOI_B 既有 BibTeX 僅缺 DOI，production 會 `inject_doi`，
因此不能直接當成失敗樣本。用錯誤 DOI 可讓失敗跨過 provider retry
並清楚落在 `verification_failed`，避免引入等待或 live network。

同 turn retry 案例內明確使用同一作品的相同 DOI／intent；
不可只靠跨 batch 的 request_index 或文字 label 相同來識別。
這是測試模型的回覆依據，不是在 host 新增持久 retry reconciliation 系統。
Metrics 仍可記錄失敗及成功兩次嘗試；不修改現有計數規則。

Mixed case 走 `agent.cli.chat._run`：
以 monkeypatch 的 async `ChatSession.create` 回傳建好的真 session，
注入 reader 依次送 `/citation 保存 A 與 B 並逐項回報` 與 `q`，
使用現有 args `no_mcp=True`、`max_graph_steps=None`。
這只是測試的輸入安排；production `session.turn`、graph、tool、service、
finalization 與 CLI print 必須實際執行。
用 `capsys` 擷取真 CLI response，與 fake 收到 content 後生成的回覆、
`session.recent_turns[-1].assistant_output` 比對，忽略 banner 等非答案文字。
其餘案例至少檢查 `session.turn` 回覆與 persisted answer 一致。

若以上全部通過，production code／Skill 不需改動。
只有具體失敗支持時才在 PLANS 允許的局部位置修正，重跑相關 focused case。
不要求一定加入人類可讀摘要，也不改現有 JSON prefix／schema。

### Refactor

沒有預定重構。只有新增測試內重複妨礙理解時可做局部整理，
不得改 shared fixture API；整理後跑受影響 focused checks。

### Verification

所有 application commands 於 Linux 執行，先設定：

```bash
source /home/minervamuses/miniconda3/etc/profile.d/conda.sh
conda activate app
cd /home/minervamuses/research-agent-workspace/app
```

**Focused baseline／完成後檢查：**

```bash
poetry run pytest tests/test_citation_workflow_tool.py tests/test_citation_e2e.py -q
```

**保留行為回歸：**

```bash
poetry run pytest tests/test_citation_save_outcomes.py tests/test_turn_finalizer.py tests/test_chat_cli.py tests/test_citation_skill_activation.py -q
```

**Broader：** focused 通過後，確認離線與時間條件仍成立，再於接近完成時
執行完整既有 suite 一次：

```bash
timeout 600s poetry run pytest -q
git -C /home/minervamuses/research-agent-workspace diff --check
```

不要為 baseline 先跑完整 suite，也不要在 final review 無條件重跑。
若 timeout 或失敗，記錄未取得的證據；需要重跑／擴大處理先遵守 PLANS 門檻。
與本 issue 無關的失敗單獨報告，不順手修理。

**代表 acceptance：** 四個表列 scenario 必須各留下最小實際結果摘要，
mixed case 要有 CLI 擷取文字。不可用只有 finalizer metrics 的測試代替。

**Manual／external：** 不要求真 provider 或真 LLM；本 issue 明確允許
deterministic fake-model。若使用者後續要求 live 試跑，先核對 credentials、
paid usage、範圍與成本並另取授權，未執行不能記為 pass。

**Failure behavior：** 必要 focused、回歸、CLI acceptance 或 broader check
失敗／缺證據時留 In progress／Blocked，不 Complete。若觀察推翻計劃，
先改未開始計劃與必要說明，不能堆疊 speculative patches。

## Reliability and Recovery

所有受測 bundle／conversation store 均在 `tmp_path`；
不讀寫 repository 的真 `cite/`、`app/store/` 或使用者的保存資料。
當前修改可局部撤回或修補，但不得以 reset／clean 覆蓋別人的工作。
不需 migration／backup／新 retry engine；既有 storage 原子性不是本次重做範圍。

## Acceptance Criteria

- [ ] GOALS 中 11 種狀態逐項完整進入 ToolMessage content，
      與 artifact 相等；工具層「成功返回」不掩蓋 item failure。
- [ ] 四個 scenario 均經真 graph／PolicyToolNode／tool／service，
      fake 只依 content 決定回覆；matching tool result 先於 final model answer。
- [ ] 回覆中的逐項結果、reason 與實際 bundle／registry 相符；
      reused 不重寫，失敗不誤保存，同作品 retry 最新結果可追溯且無重複 bundle。
- [ ] Mixed case 的真 CLI response 與 session 最終答案、persisted history
      一致；沒有新增第二個保存結果事實來源。
- [ ] 既有 save-artifact 不覆寫 prose 的 finalizer 測試、
      citation gate/render／inactive skill 行為保持。
- [ ] 所有 required commands 通過，或使用者明確批准必要驗證範圍調整；
      未跑 live LLM 的限制不能被描述為已證實真模型永不誤報。
- [ ] Diff 只有直接必要檔案，AGENTS／schema／dependencies／其他 issue 未變動。

## Evidence to Record

在 `../build-log.md` 記錄：

- issue 04 prerequisite 的來源與 live 核對結果。
- exact commands、cwd/runtime、baseline 與完成後結果、是否有 red、
  actual production diff 是否為零。
- 每項 acceptance 的 content／model-call／CLI／history／filesystem 證據摘要。
  結果是 planned、observed、skipped 或 unavailable 必須清楚。
- 重大發現才寫 `../context/phase-01-save-result-reporting-context.md`；
  真實審查才寫 `../code_review/phase-01-save-result-reporting-review.md`。

## Handoff

只有 acceptance 及 PLANS 的整體完成條件都有 evidence 才標 Complete。
沒有後續 phase；完成後報告實際檔案、checks 與限制並停止。
未滿足外部 prerequisite 或觸及授權門檻時，回報最小待決事項，
不自動轉去其他 issue。
