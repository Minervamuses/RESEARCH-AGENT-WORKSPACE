# Phase 06 — Tool-aware Conversation Restore and Continue

## Initial Status

Complete.

## Dependencies

Phase 05 Complete.

## Objective

讓含工具活動的Plan conversation能從sidebar安全載入、正確分角色顯示並繼續；restore永遠不重跑舊工具。以既有Plan log做最小versioned延伸，不建立第二套persistence。

## Confirmed Cause

- Current Plan log把tool tracesrender成Markdown blocks，但restore parser只接受direct user/final assistant；只要看到Tool/Result/Fusion marker就拒絕整份conversation。
- `TurnRecord`只保存user/final assistant，沒有structured tool activity或safe prompt reconstruction。
- Desktop transcript DTO只有`userText`、`assistantText`，React只顯示You/Assistant；Desktop service因此把tool-bearing Plan selection標degraded/refuse。

## Required Format Contract

### Versioning

- New writer產生Plan log format v2，header含`format_version: 2`；沒有版本欄位的現有檔視為legacy v1。
- 維持同一Plan log directory、filename/session ownership、atomic/append owner與size/file-count limits；不bulk migrate、不sidecar、不新database/store。
- `resume_log_file`與new writer都明確驗證version；unknown future version fail closed且不覆寫。

### Structured turn data

- `TurnRecord`或最小相鄰型別新增ordered tool activities。
- 每個v2 activity至少有bounded `call_id`、`name`、`arguments`、`result`、`status`；multiple calls/results保留原順序。
- On-disk representation必須用結構化、無歧義encoding。Round-trip tests必須涵蓋arguments/result內含換行、Unicode、JSON quotes、``````, `### Tool:`、`**Result:**`、`---`與看似turn heading的文字，不能讓payload逃逸成parser control marker。
- File/total/turn/field byte或char budget必須把tool activities算進去；oversized/duplicate/malformed activity在最小可隔離範圍fail closed，不能繞過既有2 MiB transport或Plan restore bounds。

### Prompt eligibility

- `promptEligible`是parser從可信v2結構推導的presentation field，不是on-disk caller可以設true的authority。
- 只有完整、唯一、ordered、bounds-valid且name/args/result shape合法的call/result pair能重建為model context：HumanMessage → AIMessage(tool_calls) →matching ToolMessage(s) → finalized AIMessage。
- Duplicate/missing call id、orphan result、incomplete pair或malformed activity降為activity-level display-only；不得猜id、不得執行、不得因可分離tool marker把整個其餘健康conversation降級。
- Legacy v1 activity永遠`callId:null`、`promptEligible:false`、display-only；後續prompt只取可靠user/final assistant。

## Fusion and Citation Boundaries

- Fusion/Extended candidate blocks依USER SCOPE 002保持現行non-restore/fail-closed boundary，不把candidate tool calls、candidate answer excerpt或reviser trace誤分類成generic restorable activity。Writer共用函式若需機械相容可以調整，但不得藉此新增Fusion restore semantics。
- v2 turn若產生於Citation active scope，所有Citation tool activities最多作bounded獨立顯示，必須`promptEligible=false`；不得重建source registry、active Citation或citation finalization context。
- 特別保護`citation_workflow`與其result不會因generic完整pair規則被注入restart後的normal prompt。若需記錄最小provenance來辨識Citation scope，只能為此safe exclusion使用，不得改Citation lifecycle。

## Transcript Contract

保留既有相容fields並新增每turn的`toolActivities`：

- `userText`
- `assistantText`
- `toolActivities[]`
  - `callId: string | null`
  - `name: string`
  - `arguments: string`（bounded presentation）
  - `result: string`（bounded presentation）
  - `status: string`（contract-defined bounded enum；不得接受任意 on-disk 值）
  - `promptEligible: boolean`

實作可用更強internal typed arguments，但protocol/presentation必須有bounded deterministic form。Transcript page/response byte accounting要包含activities；pagination、merge/dedup equality也要包含activities，避免靜默遺失/重複。

React將每個activity顯示為明確Tool activity/result區塊，不標成You/Assistant，不render raw HTML，不讓arguments/result取得desktop capability。`promptEligible`可用於diagnostic，不作UI執行按鈕。

## Causal Scope

### Persistence/core

- `app/agent/turns/plan_log.py`
- `app/agent/turns/memory.py`或live `TurnRecord` owner
- Direct turn-result/writer seam needed to capturetool identity/status
- `app/agent/desktop/service.py`
- `app/agent/desktop/catalog.py` only if live selection/merge metadata requires it

### Contract/UI

- `app/desktop/protocol/v1/contract.json` and fixtures
- `app/desktop/src/protocol.ts`
- `app/desktop/src/App.tsx` and directly related CSS
- `app/desktop/src-tauri/src/protocol.rs`
- Existing conversation/protocol tests

### Python tests/fixture

- `app/tests/test_plan_mode.py`
- `app/tests/test_desktop_conversations.py`
- `app/tests/test_desktop_service.py`
- `app/tests/test_desktop_protocol_contract.py`
- `app/tests/test_desktop_fixture.py`
- Direct memory/turn tests only ifneeded formessage reconstruction

No new persistence framework、dependency、Fusion/Citation redesign或real user log migration。

## Non-goals / 非目標

- 不 bulk migrate/rewrite legacy logs，不新增 sidecar/database/store 或第二個 writer。
- 不重跑歷史 tool/model/slash command，不為缺失 identity 猜 call id。
- 不恢復 Fusion candidates、Extended state、Citation registry/active state/finalizer context。
- 不新增 tool execution/retry 按鈕、raw HTML/capability rendering、dependency 或 real user-data trial。

## Required Lifecycle Tests

### New v2

1. Isolated fake Plan turn呼叫fake tool exactly once，writer保存user、call identity/name/args/result/status與final answer。
2. Shutdown backend，建立fresh service/session process view，從sidebar選同conversation。
3. Transcript按user → independent tool activity/result → final assistant顯示；fake tool invocation count仍是1。
4. 送一個新普通問題；captured model context包含經驗證的AI tool-call/ToolMessage pair與final AI，但不把tool text當HumanMessage，也不重跑old call。
5. 新turn只有自身policy需要時才可產生new tool call。

### Legacy v1

- Tool/Result blocks可讀取為display-only；missing id不使整個conversation unselectable。
- New normal turn只取得legacy user/final assistant；tool sentinel不在model prompt，invocation count不增加。
- Malformed/incomplete tool block若user/final boundary仍可靠，隔離成display-only diagnostic；若連turn boundary都不可靠才degrade該file/conversation，且不覆寫原檔。

### Safety/special scopes

- Adversarial Markdown payload round-trip。
- Duplicate/orphan/oversized activity、unknown version、wrong session id、bad UTF-8、file/total limits fail closed。
- Citation activity display-only、不重建registry/active skill。
- Fusion candidate log不被generic parser誤分類；現行excluded behavior有focused regression。
- Selection/pagination/merge不重跑model/tool，healthy sibling conversation仍可選。

## Acceptance Criteria

- New v2 lifecycle完整通過，restore前後old fake tool invocation count不變。
- GUI role separation正確；Tool/Result從未進`userText`或You bubble。
- Valid generic v2 pairs才能prompt reconstruction；legacy/Citation/incomplete pairs永遠display-only。
- Marker/fence payload安全round-trip，bounds含toolActivities。
- Fusion/Citation/non-goal boundaries維持，沒有migration/sidecar/dependency/real data。

## Focused Verification

```bash
cd /home/minervamuses/research-agent-workspace/app
poetry run pytest tests/test_plan_mode.py tests/test_desktop_conversations.py tests/test_desktop_service.py tests/test_desktop_protocol_contract.py tests/test_desktop_fixture.py -q

cd /home/minervamuses/research-agent-workspace/app/desktop
node --test --experimental-strip-types tests/conversations.test.ts tests/protocol.test.ts
./node_modules/.bin/tsc --noEmit
cargo test --manifest-path src-tauri/Cargo.toml protocol::tests
```

最後執行`git diff --check`。不得在real `app/plan_logs/`做trial；只能用caller-owned temporary root。

## Handoff Evidence

在`build-log.md`記錄：

- v2 exact schema/encoding、bounds與v1/v2/unknown-version dispositions。
- Fake tool invocation count：initial、persist、restart/select、new turn後。
- Captured model message roles/order與legacy/Citation exclusion。
- Adversarial marker round-trip、oversize/malformed/fusion regressions。
- Transcript DTO/render observation、focused commands、temporary cleanup、diff與commit disposition。
