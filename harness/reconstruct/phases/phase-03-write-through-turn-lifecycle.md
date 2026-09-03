# Phase 03 — 原子切換 write-through vertical slice

Status: Not started

## Objective

把 Agent、CLI 與最小 Desktop vertical slice 原子切換到 canonical repository，使 user prompt 在任何 provider/tool 工作前先持久化為 pending，final answer 則只在既有 safety/citation/final-text chokepoint 完成後轉成 completed，且必須在 terminal success 對 caller 可見前完成持久化。

Phase completion 時不得存在「Session 已寫 JSON，但 CLI/Desktop 還從 Chroma/Plan restore」的 split-brain checkpoint。為此，本階段同時更新最低必要的 Python host、protocol、TypeScript/Rust pass-through 與 React logical-ID dispatch；Phase 04 再完成 catalog corruption、完整 paging、display-only 與 failure UX edge cases。Plan controls 暫時可見時，新 Plan turn 也只能寫 canonical JSON，不再建立新 Plan log；控制面於 Phase 05 移除。

## In Scope

1. 在 `Session`/turn execution boundary 注入 canonical repository。
2. Desktop React 在首次 send 前產生 logical turn ID、TS/Rust 原樣轉送、Python 驗證；CLI host 產生同型 ID。Python 在既有 per-session lock 內，於 provider/tool 前配置 monotonic turnNumber並寫入 pending prompt。
3. 將正常與 extended-thinking 的 completed output 都在 `finalize_and_record` 所代表的既有安全/引用/桌面 final validator 之後寫入。
4. 將已知 provider/tool/finalization/persistence 錯誤轉成明確 failed 或 interrupted terminal state；process crash 留下 pending，由下一次載入辨識為 interrupted，不自動 replay。
5. prompt history 改由 canonical latest-10 completed/context-eligible pairs 建立，目前 prompt 只加入一次。
6. 將 `TurnMemory`/journal/store 的 runtime authority 降為必要的 in-memory view 或移除其 durable responsibility，避免 silent eviction/drop。
7. Restored/canonical turns 不再攜帶 `persist_target` 或其他「稍後再決定寫 Chroma/Plan」的 durable routing 語意。
8. CLI 與 Python Desktop create/materialize/read/restore/switch/shutdown 同步改用 JSON；選取尚無 JSON 的 legacy session 時，先以 Phase 02 importer 做單會話 all-or-nothing import，失敗則 degraded/unavailable，不建立空 transcript。
9. 更新 `session.turn` 的最低必要 lockstep protocol/request/result fields，使 logical ID、accepted/persisted 與 lifecycle state 可跨 React→TS→Rust→Python；basic restart 能從 JSON恢復。
10. 暫時仍存在的 Product Plan control 只能選擇 prompt/hint behavior；normal、extended 或 Plan 新 turn都走同一 repository，停止新 Plan-log writes。
11. CLI/Desktop caller同時傳入original display input與實際semantic input；one-shot Skill restore後只保存歷史文字，不重新啟用skill runtime。
12. 第一個durable prompt足以讓基本catalog discovery找到conversation；若catalog registration落後，restart可由JSON補回最小索引，不重跑model。
13. Switch/shutdown不再呼叫legacy conversation flush；`ShutdownReport.flushed`與相關flush error若屬protocol contract，要在同一lockstep slice移除或改成真實durability/graceful acknowledgement，不能留下永遠成功的no-op。

## Non-goals

- 不完成 catalog 全檔損壞、catalog-only missing、50-turn paging、display-only command 與完整 React failure presentation；Phase 04 專責 hardening，但本階段必須保持 basic create/send/restore/continue 可用。
- 不移除 Plan Mode UI/protocol/control；但其新 turn 不再擁有 Plan-only persistence target，也不得寫 legacy store。
- 不移除 legacy importer 或 read-only legacy source。
- 不改 citation、SafeContent、tool approval、Bash allowlist 或 model-thinking semantics。
- 不增加 automatic replay、background recovery 或 multi-process writer。

## Dependencies and prerequisites

- Phase 01 repository 與 tests 綠燈；Phase 02 importer 可獨立運作但不在 turn path 呼叫。
- 先完整追蹤 `app/agent/session.py` 中 lock、`turn_outcome`, `_prompt_history`, `finalize_and_record`, `_record_turn`, normal/extended route 的實際呼叫順序。
- 先追蹤 `turns/memory.py`, `journal.py`, `store.py` 與 citation/final validation tests，確認唯一 final-text chokepoint。
- 若執行時發現正常與 extended 路徑沒有共用可安全插入的 commit boundary，先記錄證據並採最小兩處明確呼叫；不要先做廣泛架構重構。
- 在改任何 caller 前畫出 Session、CLI、Desktop service、protocol fixture、TS/Rust bridge與 React dispatch 的 vertical sequence；Phase 不可在只有 write cutover、沒有 read/restore cutover時標 Complete。

## Expected components

主要預期變更：

- `app/agent/session.py`
- `app/agent/turns/memory.py`、`journal.py`、`store.py` 中僅與 authority/cap/drop 直接相關的部分
- `app/agent/desktop/service.py`, `protocol.py`, `server.py` 與 CLI session construction 的最低必要 cutover
- `app/desktop/protocol/v1/contract.json`, `fixtures.json`、React/TypeScript request state與 Rust protocol pass-through 的最低必要變更
- Phase 01 conversation models/repository 的小幅 caller-facing extension（不得改已固定 persistent schema）
- `app/tests/test_session_eviction.py` 重新聚焦 lifecycle/durability/failure；或新增一個更精確的相鄰測試檔並刪除不再成立的 eviction assertions
- 相鄰的 `test_state.py`, finalizer, thinking, citation tests 中最小調整

## Authorization and stop conditions

本 bundle 的完整 launch block明確授權此聚焦的多檔與 lockstep protocol-v1 cutover；但沒有授權新 dependency、外部 compatibility layer、live provider 或已固定 schema 語意變更。下列情況停止：

- 無法證明 prompt persist 在 provider/tool invocation 之前。
- final answer 有任何 bypass 既有 safety/citation/final validator 的新路徑。
- 為支援 Plan Mode 暫存而必須對同一 normal/extended turn 永久雙寫 Chroma/Plan/JSON。
- 目前 prompt 的去重需要猜測 message semantics，且代表性測試無法區分一次與兩次。
- 無法在同一 phase內讓最低必要 write/read/restore/client path一起工作；不得留下 Desktop新寫 JSON卻只讀 legacy 的完成狀態。

## Implementation and verification plan

### Preflight

1. 以 sequence table 記錄現況：lock → prompt construction → graph/provider/tools → finalization → persistence → return。
2. 固定目標 sequence：lock → allocate identity → persist pending → construct latest-10 + current once → execute → finalize → persist terminal state → return。
3. 識別 process-crash 無法 catch 的邊界，以及下次 load 時 pending→interrupted 的唯一位置。
4. 保存 normal、extended、one-shot Skill、citation-gated final answer 的既有代表測試。
5. 固定 selected legacy session 的 pre-turn rule：target JSON 不存在就先 import；有效 JSON存在就只讀 JSON；migration失敗就阻止該 session 執行，不混合來源。

### Red

加入會失敗的 ordering/fault tests：

- pending save 失敗時 provider/tool spy 完全未被呼叫。
- provider/tool 前 repository 已能讀到原始 prompt、semantic input、stable ID 與 turnNumber。
- provider 或 tool 已知錯誤後沒有 completed/fake assistant answer，且 state/錯誤可辨識。
- final output persistence 失敗時不得回 terminal success。
- crash-like leftover pending 在重新載入時成為 interrupted，不自動執行 provider。
- 12 個歷史 turns 只注入最後 10 個 completed eligible pairs，目前 prompt 恰好一次。
- normal、extended、one-shot Skill 與 citation route 都遵守相同 commit ordering。
- JSON restart後的one-shot Skill不會重新啟用；未列入當前tool policy的forged call仍由execution layer拒絕。
- CLI/Desktop 建立第一個 turn、restart/select/continue 都走 JSON；legacy-only selected session 在 turn前先完成一次 import。
- React 預先產生 logical ID，TS/Rust 不改值，Python duplicate completed request 回 durable result。
- 暫存 Plan control 的新 turn 不建立 Plan log，而是依同一 prompt/final lifecycle寫 JSON。
- Basic A→B→A與shutdown不呼叫legacy flush，protocol不回報假的`flushed=true`。

### Green

1. 在 session lock 內以 repository 原子建立 pending turn；此動作失敗立即回傳 persistence failure。
2. 由 repository query 建構歷史；semantic/context input 供模型，original display input 保留供 UI。
3. 保持既有 graph/tool/citation/final validator 邏輯，只把 completed commit 插在 final text 已確定且 return 之前。
4. 對可捕捉錯誤做明確 terminal transition；對上次未結束 pending 在 load/recovery boundary 標為 interrupted。
5. 拆除 normal/extended path 的 legacy durable write，避免兩個 authority；若 UI cache 仍需 memory，讓它可由 JSON 重建。
6. 同步切換 CLI/Desktop最低必要 materialization與 restore；legacy-only selected session只經 importer產生 JSON後才繼續，runtime不做 Chroma/Plan/current-memory merge。
7. 更新最小 protocol vertical slice：React首次 dispatch前建立 logical ID，TS/Rust只轉送，Python以它做 idempotency；accepted/completed state在 response/error中可辨識。
8. 關閉新 Plan-log writes；Phase 05移除之前，Plan control若仍存在只能走相同 JSON lifecycle。
9. 保持tool policy與ephemeral state在repository之外；restore只重建transcript，不重建active Skill、approval或tool availability。
10. 移除host的active legacy flush gate，並同步更新Python/TS/Rust shutdown DTO/error mapping，使回報描述真正的JSON durability與child shutdown結果。

### Refactor

- 將 lifecycle ordering 集中在最少的 session methods；不建立 event bus 或 generic transaction coordinator。
- 刪除因本次 cutover 才成為 dead 的 cap/drop/flush code，但只限已無 caller 且 phase acceptance 可證明者。
- 不整理無關 prompts、tools、graph nodes 或 citation code。

### Verification

從 `app/` 執行精確的相關集合：

```bash
conda run -n app poetry run pytest tests/test_session_eviction.py tests/test_memory.py tests/test_state.py tests/test_turn_finalizer.py tests/test_thinking.py tests/test_thinking_session.py tests/test_skill_runtime.py tests/test_citation_gate.py -q
```

若 preflight 證明上述某檔與 changed path 無關，可在 build log 寫明 causal reason 後略過；若新增或搬移測試，記錄 replacement selector。以 repository fakes 驗證 ordering，不呼叫 live provider 或 Ollama。

再執行最低必要 host/protocol slice：

```bash
conda run -n app poetry run pytest tests/test_desktop_conversations.py tests/test_desktop_service.py tests/test_desktop_protocol_contract.py tests/test_desktop_fixture.py tests/test_chat_cli.py tests/test_slash_commands.py tests/test_plan_mode.py -q
conda run -n app poetry run pytest tests/test_policy_tool_node.py tests/test_tool_access.py tests/test_extension_user_journey.py tests/test_bash_tool.py -q
```

再從 `app/desktop/` 執行：

```bash
conda run -n app node --test --experimental-strip-types tests/protocol.test.ts tests/backend.test.ts tests/conversations.test.ts
conda run -n app ./node_modules/.bin/tsc --noEmit
conda run -n app cargo test --manifest-path src-tauri/Cargo.toml protocol::tests
```

本機`node_modules/.bin/tsc --noEmit`是本phase改動React/TS contract的必要typecheck，不是Vite production build；若binary不存在，依dependency gate停止，禁止用`npx`或install隱式下載。不要在此phase跑完整npm suite、`npm run build`或完整Cargo suite。

## Reliability, security, and recovery

- Prompt-first 是硬 gate：如果 durable write 失敗，禁止 provider/tool side effect。
- Completed 是硬 gate：如果 final commit 失敗，caller 只能收到非成功結果。
- Pending recovery 不 replay，避免重複外部工具或 provider side effect。
- Repository error 不得把 prompt/answer 全文放進 exception/log。
- Lock 保持涵蓋 identity allocation、persist 與 execution，避免同一 session turnNumber collision。

## Acceptance Criteria

- [ ] 測試直接證明 provider/tool 前 prompt 已 durable，失敗時完全不執行它們。
- [ ] safety/citation/final-text 後才 commit completed，且 commit 在 terminal success 前。
- [ ] 所有正常與 extended routes 使用同一 canonical authority，無永久 legacy dual-write。
- [ ] latest-10 completed eligible context 正確，目前 prompt 恰好一次。
- [ ] failed、interrupted 與 completed 語義可由重啟後 JSON 重建，不會自動 replay。
- [ ] Restored turns 不再被當成新 turn 重寫或重新編號，也沒有 `persist_target` 類別。
- [ ] 既有 citation、SafeContent、tool approval 與 thinking 行為的相關測試仍通過。
- [ ] CLI/Desktop最低必要 create/send/restart/select/continue讀寫同一 JSON；selected legacy session先成功 import或明確 unavailable。
- [ ] React→TS→Rust→Python logical ID與 accepted/completed state完成最小 lockstep contract，basic duplicate不重跑 provider/tool。
- [ ] 暫存 Plan control的新 turn也只寫JSON且不產生新Plan log；Phase完成時沒有 write-JSON/read-legacy split-brain。
- [ ] Original/semantic input由真實CLI/Desktop caller傳入；one-shot Skill不因JSON restore重啟，forged unavailable tool仍被拒絕。
- [ ] 第一個prompt已durable但catalog寫入落後時，basic restart仍可從JSON發現conversation。
- [ ] Basic switch/shutdown不呼叫legacy flush，三語protocol沒有失真的no-op `flushed`成功旗標或flush-only errors。

## Evidence to record

在 build log 寫下 before/after sequence、每個 fault injection point 的 observable 結果、變更檔案、測試命令與 exit code。若某錯誤只能留下 pending，明確記錄其在 reload 時如何轉為 interrupted。

## Handoff

Phase 04 應以本階段已貫通的 logical ID與 JSON host path完成 edge hardening，而不是另建身份或第二 cutover。若任何 host仍可能新寫 JSON卻從 legacy restore、或 success可能先於 final commit，禁止進入 Phase 04。
