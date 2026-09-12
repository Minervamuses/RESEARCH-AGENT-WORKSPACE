# Issue 05 — Citation 保存結果回報：目標

## Purpose and Background

依 [原 issue](../05-citation-save-result-reporting.md)，驗證 citation 保存事實
能經正式工具訊息抵達模型，並成為使用者收到的答案依據。
`SaveBatchOutcome` 已有逐項結果，缺口是完整代表流程的證據，
並非已證實缺少傳輸機制。這次 authoring 只建立計劃，不代表已執行修正。

## Desired Outcomes

- Agent 在生成保存回覆前收到每一項真實結果，可區別新保存、重用和失敗。
- 同一批部分成功不會被測試模型概括成全部成功；重試後的回報保留先前失敗
  與後續結果的對應，不把嘗試次數誤當保存作品數。
- CLI 顯示與 session 保存的答案一致，既有工具與 finalization 邊界保持不變。

## Success Conditions

- [ ] 真實 StructuredTool 呼叫產生的 ToolMessage，其 content JSON 與同一
      outcome 的 artifact 一致；index、label、status、reason_code、receipt、
      alternatives 不遺漏，順序保留。
- [ ] 覆蓋 `saved`、`reused` 及全部九種現有 failure status：
      `insufficient_intent`、`ambiguous`、`not_found`、
      `identity_conflict`、`unsupported_identifier`、`unsupported_no_doi`、
      `provider_failed`、`verification_failed`、`storage_failed`。
- [ ] 在真 graph／PolicyToolNode／tool／service 的離線流程中，fake model
      先從 ToolMessage **content** 取得結果才產生最終答案；
      全成功、全失敗、混合結果、同一 turn 失敗後重試成功均有觀察證據。
- [ ] 全成功包含 `reused`；混合結果同時包含成功與失敗原因。
      回覆逐項對應 requested work；成功有實際 bundle／registry 支持，
      失敗不誤增 bundle，重用不重寫既有 bundle。
- [ ] 至少混合結果流程抵達真 CLI 的輸出函式；擷取輸出與該次
      `session.turn` 最終回覆、history 的 `assistant_output` 一致。
- [ ] 既有不依保存 artifact 覆寫模型全文、citation marker gate／render、
      telemetry 與 history persistence 的測試保持成立。

## In Scope

- Tool content／artifact 的完整性，以及工具結果到最終答案的順序與對應。
- 重用現有 pytest、fake model、provider fetcher 和 `tmp_path`，
  補齊目前測試缺口；只有明確失敗證據支持時才做直接必要的局部修正。
- 保留 citation Skill 已有「依實際 tool result 回報」指令；
  若代表案例證實指令缺少必要區分，才局部補充。
- 與 issue 04 的先後順序，以及本計劃執行時的證據與續作文件。

## Non-Goals

- 不在本計劃實作 issue 04 的 resolver／authority 修正或 issue 08。
- 不重新驗證 provider metadata、改 bundle／artifact schema、改 public API。
- 不加入 stdout／CLI log parser、第二條模型資料通道、
  host-side receipt renderer 或依保存結果覆寫模型全文的 finalizer。
- 不新增 CLI status block；原 issue 將其列為可選 observability。
  如日後使用者明確要求，應另定 UI 範圍與驗證，不能用它替代模型訊息測試。
- 不重構 session／graph、改 telemetry 的 attempt 計數語意、新增測試框架、
  引入 dependencies 或執行 live provider／paid model 評測。

## Preserved Behavior and Invariants

- `SaveBatchOutcome` 是保存事實的單一來源，ToolMessage content 是模型的
  正式輸入；artifact 留給程式端保存／觀察，不假設模型能直接讀它。
- `ToolMessage.status == "success"` 只代表工具正常返回；item 仍可能全部
  失敗。不得把 transport status 當成保存成功。
- 保存結果 schema、receipt 信任邊界、registry、atomic bundle write、
  stable identity／reused 行為維持原狀。
- 不移除既有一般 final-response safety 或 citation marker gate/render；
  禁止的是重新加入 citation-save 專用的全文覆寫層。
- 每次保存的 batch_id、tool_call_id 與 request_index 有各自範圍；
  重試跨批對應用明確同一作品的 intent／identifier 與該次訊息，
  不能只因 request_index 相同就合併不同作品。
- Deterministic fake model 證明訊息可見性、時序與程式整合，
  不證明任意真實 LLM 永遠遵守保存結果；這不是本 issue 的保證。

## Constraints

- **Runtime：** Linux，Conda `app` 管 Python／Poetry 執行環境，
  Poetry 管依賴；Windows 僅透過 WSL 操作。來源：根 `AGENTS.md`、
  `app/env/env-app.yml`、`app/poetry.toml`。文字使用 UTF-8／LF。
- **Scope／成本：** 使用者 Personal Engineering Defaults 要求最小可驗證修改。
  預期以兩個既有測試檔完成，無 production change 也可達成目標。
  不為得到紅燈而故意破壞程式或建立通用測試系統。
- **順序：** 原 issue 建議先完成 issue 04。本計劃預設遵循，
  啟動條件與證據核對由 PLANS／phase 管理；不授權代為實作 issue 04。
- **Authority：** 2026-09-12 使用者只要求寫計劃。未來執行授權與例外門檻
  見 PLANS；任何 `AGENTS.md` 均不得修改。

## Known Unknowns and User Decisions

目前沒有阻止撰寫計劃的待決使用者選項；issue 已允許 deterministic fake-model
驗證，CLI status block 是可選項，本計劃採最小範圍。

技術待確認項交由 phase 的有界 preflight／驗證處理：

- issue 04 是否已有與 live code 一致的完成證據。
- 所有狀態的 content 是否確實完整，以及 mixed／retry 是否有實際傳遞缺陷。
  若新增測試直接通過，記為既有行為的 characterization，不能宣稱修好了未知 bug。
- 完整 suite 在實作時是否仍能離線、便宜地完成；歷史時長不等於當前結果。

## Source Inputs

- 根 `AGENTS.md`；本次對話中的 Personal Engineering Defaults。
- `issue/05-citation-save-result-reporting.md`、
  `issue/04-citation-earliest-version-ambiguity.md`、
  `issue/issue_04/PLANS.md`、`issue/issue_04/build-log.md`。
- `app/skills/citation/{tool.py,types.py,service.py,SKILL.md}`。
- `app/agent/{graph.py,state.py,session.py}`、
  `app/agent/tools/policy_node.py`、
  `app/agent/skills/citation/session_policy.py`、`app/agent/cli/chat.py`。
- `app/tests/test_citation_workflow_tool.py`、
  `app/tests/test_citation_save_outcomes.py`、
  `app/tests/test_citation_e2e.py`、`app/tests/test_turn_finalizer.py`、
  `app/tests/test_chat_cli.py`、`app/tests/citation_fixtures.py`。
