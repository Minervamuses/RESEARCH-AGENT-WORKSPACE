# Phase 02 — Long-request Liveness

## Initial Status

Not started.

## Dependencies

None.

## Objective

移除 Desktop 對已啟動一般 request 套用的固定 600 秒 absolute deadline，讓仍正常執行研究、工具工作或回報 event 的長回合不會只因總經過時間被 kill；同時保留真正 child/transport failure 與 bounded startup/shutdown semantics。

## Confirmed Cause and Evidence Boundary

- `app/desktop/src-tauri/src/backend.rs` 定義 `REQUEST_TIMEOUT = 600s`，放入 `SupervisorTimeouts.request`，並在等待 response 時以 timeout 產生 fatal error/kill。
- Issue 08 與 source 證明存在 absolute limit；尚未等待真實 600 秒重現使用者回合。因此本 phase 用 deterministic shortened test 證明 causal behavior，不浪費十分鐘或呼叫 provider。

## Causal Scope

### Expected production write

- `app/desktop/src-tauri/src/backend.rs`

### Expected tests

- 優先擴充同檔既有 Rust backend tests 與 fake child/protocol fixture。
- 只有既有 topology 無法表達 request lifecycle 時，才新增一個直接相鄰的 backend test module；不得建立 generic scheduler、heartbeat service 或第二個 supervisor。

Startup timeout、graceful shutdown timeout 與 process-exit handling 是 read/verify scope，只有修復被 request timeout 共用型別牽連時才做最小調整。

## Non-goals / 非目標

- 不新增 heartbeat/inactivity service、queue、worker、scheduler 或任意替代 absolute timeout。
- 不修改 Python agent/model/tool semantics，不呼叫真 provider，不等待真實 600 秒。
- 不處理 user-initiated cancellation redesign、Fusion/Extended 或多 GUI process。

## Required Design

- 已成功寫入 child、正在等待 terminal response 的一般 request 不再有 fixed total-duration deadline。
- 不把 600 秒換成 1 小時、24 小時或其他 arbitrary total timeout。
- Transport 仍以 child exit、stdout/pipe close、reader failure、malformed/mismatched protocol、explicit application shutdown/cancel 作 terminal signal。
- Startup/readiness 與 graceful shutdown 可以維持各自 bounded deadline，因為它們不是一般 agent turn 的總執行時間。
- Inactivity/heartbeat policy 不在預設方案。只有 source/test 證明移除 total deadline 後無法偵測既有 failure signal，才可提出最小 evidence-backed設計並先要求需要的新 authority；不可順手發明 watchdog。

## Implementation Steps

1. Characterize `SupervisorTimeouts` 所有 caller，分清 startup、request、shutdown，避免刪錯 safety boundary。
2. 寫 deterministic red test：用毫秒級「舊 deadline」與 fake child，request 在該界線前後送合法 event/progress，跨過界線後才送 terminal result；現行 code 應 timeout，新 code 必須成功。
3. 把 request wait 改成沒有 general absolute deadline 的 receive path，保留 correlation/sequence/result validation。
4. 加/維持 terminal failure cases：
   - child 在 result 前 exit；
   - stdout/response channel close；
   - malformed 或 wrong-id terminal message；
   - application shutdown 在 pending request 時可結束並回報非成功；
   - startup ready deadline 與 shutdown grace deadline 仍生效。
5. 檢查 fatal UI/error code。不得讓已移除的 `BACKEND_REQUEST_TIMEOUT` 仍從 normal request path 出現；也不得把真 exit 誤報成 success。

## Acceptance Criteria

- Fake request 跨過縮短舊 deadline後收到 terminal success，child 未被 kill，event order/correlation 保持正確。
- 同一 test 若 child exit/pipe close 則 bounded fail，不永久 hang。
- Source 不再含 normal request 600 秒或替代 arbitrary total deadline。
- Startup/shutdown safety tests 維持通過。
- 不加入 dependency、thread pool、queue、heartbeat service、provider call 或 sleep 到真實十分鐘的 test。

## Focused Verification

```bash
cd /home/minervamuses/research-agent-workspace/app/desktop
cargo test --manifest-path src-tauri/Cargo.toml backend::tests
```

如新 test 位於不同 module，記錄並執行最小等價 Rust selector。所有 test delay 要是短 deterministic duration，整個 focused command 應在普通 local feedback loop 內完成。

```bash
git diff --check
```

## Handoff Evidence

在 `build-log.md` 記錄：

- 舊 absolute deadline 的 exact test substitute 與新 event/result order。
- Request wait 的新 terminal conditions。
- Child-exit/pipe-close/startup/shutdown cases 的 actual outcomes。
- 是否完全移除 `request` timeout field，或保留型別但不套在 general turn；若後者，說明不會成為 hidden deadline 的 source evidence。
- Diff、focused test、local commit disposition。
