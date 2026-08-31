# Phase 05 — Final-only Normal Answer Delivery

## Initial Status

Not started.

## Dependencies

Phase 04 Complete.

## Objective

讓Normal answer只在Python完成generation、repair、finalization、validation與persistence後，以一個authoritative `final_only` terminal result完整交付Desktop；移除完成後`answer.chunk`模擬串流與React provisional reconciliation。

## Source Inputs and Supersession

- [`../user-decisions.md`](../user-decisions.md) USER DECISION 014明確supersede USER DECISION 006；舊決策與官方串流蒐證保留為歷史。
- [`../build-log.md`](../build-log.md) Phase 05 attempt 1已用fake live graph證明rejected draft會先於accepted repair出現，且pre-token attribution不能保證authoritative acceptance。該evidence保留，不重跑、不改寫。
- Live `ChatSession.finalize_and_record()`目前在回傳`TurnOutcome`前執行final response safety、Citation policy（若適用）、Desktop final-text/wire validator與`_record_turn()`；Desktop service之後才發送`post_finalized answer.chunk`並回傳terminal result。

## Non-negotiable Product Boundary

- Desktop在Python generation、repair、finalization、validation與persistence全部成功前不得顯示answer text。
- GUI一次顯示authoritative final answer完整內容，不顯示provisional answer preview。
- Normal success不發送`answer.chunk`；terminal `session.turn` result必須是`streamKind=final_only`、`chunkCount=0`。
- 不得以post-finalized slicing、replay event或另一種完成後chunk模擬串流。
- Error、cancel、provider/child failure、oversize或validation failure不得顯示任何partial answer；原始user draft與不含answer text的bounded progress/tool activity可依既有行為保留。
- Fusion、Extended Thinking與Citation redesign仍排除；本phase不改它們的execution/finalization語意。

## Confirmed Cause and Minimal Route

- `DesktopService._session_turn()`已等待`session.turn_outcome()`完成，並在terminal result前做bounded success-envelope與catalog registration處理；但它隨後呼叫`_emit_answer_chunks()`把完成答案切塊。
- Shared protocol、fixtures、Rust/TypeScript validators仍宣告`answer.chunk`與`post_finalized`；React reducer累積`provisionalText`並在terminal result做`final`/`reconciled`/`final_only`分支。
- 目前沒有其他production producer使用`answer.chunk`。最小一致修復是刪除這條internal producer/contract/consumer chain，收斂`session.turn` result schema為`final_only`與zero chunks；不改graph/model stream。

## Causal Scope

### Python delivery owner and focused tests

- `app/agent/desktop/service.py`
- `app/tests/test_desktop_answer_stream.py`
- `app/tests/test_desktop_service.py`
- `app/tests/test_desktop_fixture.py`
- `app/tests/test_desktop_protocol_contract.py`
- `app/tests/test_turn_finalizer.py`
- `app/tests/test_session_eviction.py::test_final_text_validator_runs_before_the_turn_is_recorded`（read-only ordering oracle unless a regression is exposed）
- `app/agent/session.py`／turn finalizer先作read-only ordering oracle；只有rejecting evidence證明現有chokepoint不足才可最小修改。

### Desktop contract and rendering

- `app/desktop/protocol/v1/contract.json` and `fixtures.json`
- `app/desktop/src/protocol.ts`
- `app/desktop/src-tauri/src/protocol.rs`
- `app/desktop/src/conversations.ts`
- `app/desktop/src/App.tsx`
- `app/desktop/tests/answer_stream.test.ts`
- `app/desktop/tests/protocol.test.ts`

不得修改provider/model config、graph/execution stream、Fusion candidate algorithm、Extended orchestrator、Citation flow或dependency/lockfile。

## Non-goals / 非目標

- 不做live token streaming、provisional draft display或post-final event delivery。
- 不新增model call、live provider trial、provider-specific pipeline或generic delivery framework。
- 不重設Fusion、Extended Thinking或Citation的產品流程。
- 不做unrelated graph refactor、UI animation/polish、performance benchmark或first-turn durability修復。

## Required Dataflow

1. Normal turn照現行Python-owned path完成model/tool工作、repair、finalization與validation。
2. Final-text/wire validation在turn record寫入前通過；`_record_turn()`完成後，`turn_outcome()`才把authoritative `TurnOutcome`交回Desktop service。
3. Desktop完成success-envelope budget與既有catalog registration disposition後，直接回傳一個含完整text、`streamKind=final_only`、`chunkCount=0`的terminal result；期間不發送answer-text event。
4. React active turn只保存correlation、bounded activity與waiting state。Terminal success到達時才新增一份完整assistant message；沒有chunk assembly、prefix reconciliation或late answer event。
5. Terminal error/cancel/child failure清除active turn、保留既有可重試user draft，且從未建立partial assistant message。

## Implementation and Verification Plan

### Preflight

- Reconfirm Phase 04 Complete、clean/owned dirty tree、Conda/Poetry/Node/Cargo Linux paths與broader counters仍為0。
- Re-read live service/finalizer ordering、contract inventories、React reducer與current focused tests；確認`answer.chunk`沒有其他production owner。

### Red

- 先把最小Python regression改成：blocked fake turn在release前沒有answer event，release後仍完全沒有`answer.chunk`，terminal result一次帶完整text、`final_only`與zero chunks。現行service應因發送`post_finalized` event而拒絕。
- Contract/React deletion tests可在同一attempt內接續，但第一個causal red只跑上述單一selector。

### Green

- 移除Python chunk constants/emitter與normal success呼叫；wire candidate和terminal result固定使用`final_only`/0。
- 同步刪除shared `answer.chunk` inventory/schema/fixtures、Rust/TypeScript event validator/DTO與React chunk action/state/rendering；將terminal result validator收斂到`final_only`與zero chunks。
- 保留stage/tool/progress事件，因它們不攜帶answer text。

### Refactor

- 只移除因answer chunk deletion而失效的types/constants/helpers/labels/tests。不得清理其他conversation state或transport code。

### Failure behavior

- Required focused check失敗時Phase 05保持`In progress`；先用最小selector定位owning boundary，不開始Phase 06。
- 若live source出現另一個必要的answer-event consumer或需要改protocol major/dependency/Fusion/Extended/Citation才能移除，記錄evidence並停止該path要求fresh authority。

## Required Tests and Acceptance

- Success ordering：release barrier前沒有answer text/event；turn完成後只有完整authoritative terminal result，`streamKind=final_only`、`chunkCount=0`。
- Finalization/persistence ordering：validator failure不寫turn；successful persistence完成後才返回outcome/result。使用既有finalizer oracle或最小spy，不以planned order當proof。
- Negative paths：provider error、cancel、oversize、wire validation failure與broken/unavailable event sink都沒有partial answer；user draft/retry state維持既有bounded behavior。
- Protocol：`answer.chunk`與`post_finalized`從current production contract、fixtures、Rust/TypeScript validators/DTO消失；`session.turn`只接受`final_only`/zero chunks。
- React：pending turn只顯示working/activity；terminal success一次新增完整answer；failure/cancel不留下assistant preview，late/duplicate result仍fail closed。
- Scope：Fusion、Extended Thinking、Citation、dependencies/locks與graph/model stream無diff。

## Focused Verification

```bash
cd /home/minervamuses/research-agent-workspace/app
poetry run pytest tests/test_desktop_answer_stream.py tests/test_desktop_service.py tests/test_desktop_fixture.py tests/test_desktop_protocol_contract.py tests/test_turn_finalizer.py tests/test_session_eviction.py::test_final_text_validator_runs_before_the_turn_is_recorded -q

cd /home/minervamuses/research-agent-workspace/app/desktop
node --test --experimental-strip-types tests/answer_stream.test.ts tests/protocol.test.ts
./node_modules/.bin/tsc --noEmit
cargo test --manifest-path src-tauri/Cargo.toml protocol::tests
```

最後執行`git diff --check`與exact name/scope audit。不執行live provider、full suite或build。

## Acceptance Criteria

- Normal success trace在terminal result前沒有answer text或`answer.chunk`；terminal result一次交付完整authoritative text。
- Generation/repair/finalization/validation/persistence ordering有observed test evidence，failure/cancel/validation failure沒有partial answer。
- Current protocol/UI不再接受或呈現`post_finalized`/`answer.chunk`，且`final_only`/zero-chunk contract全鏈一致。
- Focused Python、Node、TypeScript、Rust checks與`git diff --check`通過。
- No dependency、live provider、graph rewrite、Fusion/Extended/Citation behavior change或non-goal expansion。

## Handoff Evidence

在`build-log.md`記錄：

- 舊characterisation blocker如何由USER DECISION 014解除，且歷史trace仍保留。
- Exact first red、success/failure/cancel event/result order與persistence oracle。
- Removed producer/contract/consumer inventory及repository residue search。
- Focused commands/results、diff/scope audit、temporary boundary與commit disposition。
- Phase 05 Complete後Phase 06成為下一個eligible phase。
