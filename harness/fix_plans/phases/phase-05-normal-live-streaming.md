# Phase 05 — True Normal OpenRouter Streaming

## Initial Status

Not started.

## Dependencies

Phase 04 Complete.

## Objective

把 Normal、非 Fusion、非 Extended Thinking 的 OpenRouter answer path從「final後切塊」改為模型仍生成時的live text delta，同時由Python證明delta只屬於最後可公開的accepted answer stage，terminal result仍是authoritative truth。

## Non-negotiable Product Boundary

- OpenRouter與LangGraph支援live streaming；不得再用provider不支援當理由保留`post_finalized`。
- 第一個answer delta必須在authoritative terminal result之前抵達Desktop/React。
- Tool-call JSON、tool result、reasoning、provider metadata、initial draft、empty retry、repair前/force-final前草稿，以及finalizer會丟棄或重寫的內容，永遠不得出現在user-visible answer chunk。
- 不增加第二次live/paid model call只為重述已完成答案；不呼叫真provider驗證。
- Fusion與Extended Thinking完全排除，維持既有path與tests，不因共用seam被意外改成normal streaming。

## Mandatory Characterisation Checkpoint

實作前先用fake streaming model與live graph source回答：

1. Initial answer、tool continuation、empty retry、repair、force-final/final validation各自由什麼node/stage/model call產生？
2. LangGraph `messages` metadata能否單獨識別可公開stage？只以現行node name=`agent`篩選是否會混入其他draft？
3. Normal finalizer是否可能改變內容；什麼precondition能在token送出前保證該stage是accepted-answer producer？
4. Existing cancellation/error如何終止async stream並形成terminal result？

預期現況是多個stage共用同一node，因此只按node filter不符合acceptance。Required implementation是建立最小、Python-owned、可測試的stage attribution seam；可用distinct node/tag/callback/context，但不能讓React猜stage。

若source evidence顯示無法在不增加第二次model call、不顯示unchecked draft、且不做broad graph rewrite的條件下安全完成，Phase 05必須在`build-log.md`記錄characterisation並標`Blocked`，要求fresh authority。不得退回post-final slicing後宣稱完成。

## Causal Scope

### Python stream owner

- `app/agent/turns/execution.py`
- `app/agent/graph.py`
- `app/agent/session.py`
- `app/agent/desktop/service.py`
- Existing directly related result/finalizer seam only if source證明necessary
- `app/tests/test_desktop_answer_stream.py`
- `app/tests/test_desktop_service.py`
- Minimal graph/session/finalizer tests needed to distinguish accepted stage

### Desktop contract/rendering

- `app/desktop/protocol/v1/contract.json` and fixtures
- `app/desktop/src/protocol.ts`
- `app/desktop/src/App.tsx`
- `app/desktop/tests/answer_stream.test.ts`
- Rust protocol/backend only if event enum/validation needs同步；transport本身若已轉送ordered events則read-only。

不得修改provider credentials/models、Fusion candidate algorithm、Extended orchestrator或dependency/lockfile。

## Non-goals / 非目標

- 不串流 Fusion、Extended Thinking、Citation 專用 finalization、reasoning 或 tool payload。
- 不新增第二次模型呼叫、live provider trial、provider-specific parallel pipeline 或 generic streaming framework。
- 不把 complete answer buffering/slicing 重新命名成 live streaming。
- 不做 unrelated graph refactor、UI animation/polish 或 performance benchmark。

## Required Dataflow

1. Normal turn execution啟用LangGraph/model live message stream，並攜帶Python-owned publishable-stage attribution。
2. Desktop service只把該stage的non-empty assistant text delta轉成ordered bounded `answer.chunk` event，使用canonical `streamKind=live_delta`（若live contract已有等價名稱，以其為準並全鏈一致）。
3. Event保留request/session correlation與strict sequence；chunk size仍有byte bound，但bound是transport safety，不是final answer slicing。
4. Python finalizer/history/persistence等待完整authoritative result；stream event不能自行commit transcript。
5. React維護一個transient preview，收到terminal success後用authoritative answer對帳成單一assistant message，不重複prefix、不留下兩份答案。
6. Terminal error/cancel/child failure不把partial preview存成final；UI可明確標示interrupted或清除，但retry不得把舊partial與新stream串接。

## Required Tests

### Event order and timing

- Fake model用barrier控制：送第一/第二delta後阻擋final；test在release barrier前已觀察`answer.chunk`，之後才收到terminal result。
- Sequence/correlation與bounded chunk test不依wall-clock race，使用event/barrier而非長sleep。

### Attribution exclusions

- Fake graph產生tool-first content、tool result、empty retry text、repair前draft、repair後accepted answer、finalizer-blocked draft與reasoning metadata；只有accepted answer delta進event sink。
- Source stage即使與`agent`同node，也要靠新Python seam區分；test不得只mock service直接餵安全chunk而跳過graph attribution。
- Normal finalizer outcome與streamed concatenation相同；若finalizer有合法normalization，設計必須保證不會先顯示後被拒絕的內容。

### Reconciliation and failure

- Terminal success只形成一份assistant answer；duplicate/out-of-order/wrong-request chunk fail closed。
- Error/cancel/retry不persist partial、不duplicate。
- Short answer仍至少以provider實際delta呈現，不在terminal後人為切一塊。
- Fusion與Extended focused regression證明未進`live_delta` normal path。

## Acceptance Criteria

- Actual fake event trace顯示至少一個answer chunk時間/順序早於terminal result。
- Concatenated chunks等於authoritative final answer，且exclusion fixture中的tool/reasoning/retry/repair draft字串從未出現。
- Normal success source不再建立`post_finalized` chunk；repository search只可在migration/negative test或舊historical plan出現。
- React reconciliation、cancel/error/retry與Rust/Python contract tests通過。
- No live provider、extra model call、dependency、Fusion/Extended behavior change或broad graph rewrite。

## Focused Verification

```bash
cd /home/minervamuses/research-agent-workspace/app
poetry run pytest tests/test_desktop_answer_stream.py tests/test_desktop_service.py tests/test_turn_finalizer.py -q

cd /home/minervamuses/research-agent-workspace/app/desktop
node --test --experimental-strip-types tests/answer_stream.test.ts tests/protocol.test.ts
./node_modules/.bin/tsc --noEmit
```

若Rust contract有diff：

```bash
cargo test --manifest-path src-tauri/Cargo.toml protocol::tests backend::tests
```

最後執行`git diff --check`。不執行live provider或full build。

## Handoff Evidence

在`build-log.md`記錄：

- Graph/model stage map與為何新seam能識別publishable final answer。
- Fake trace的exact event order：delta sequence、barrier、terminal result。
- Excluded sentinel strings與event sink observation。
- Stream concatenation對authoritative final result的comparison。
- Error/cancel/retry、Fusion/Extended regressions、focused commands、diff與commit disposition。
