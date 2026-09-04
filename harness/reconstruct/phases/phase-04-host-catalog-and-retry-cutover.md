# Phase 04 — 強化 host、catalog 與 retry edge cases

Status: In progress

## Objective

在 Phase 03 已完成的可工作 vertical slice 上，補齊 catalog rebuild、bounded完整 transcript、display-only local commands、before-ack retry 與 React failure UX。Phase完成後，catalog只是一個可由 JSON重建的索引，所有跨語言 edge cases都使用同一 stable logical identity，切換 conversation也不再依賴 legacy flush。

## In Scope

1. 強化 CLI/Desktop JSON create/list/restore/switch/shutdown edge behavior；不得重新引入 legacy fallback或第二 authority。
2. Catalog scan/reconcile：JSON orphan 可重新加入；catalog-only missing entry 必須保留為明確 unavailable，不得靜默移除或生成空 transcript；catalog 本身損壞時可由健康 JSON 重建；單一 malformed file 不阻斷其他 conversations。
3. Transcript/page model 可表達 pending、completed、failed、interrupted、display-only，而非假設每筆皆為完整 pair。
4. Local slash commands的原始輸入與顯示結果走display-only lifecycle且不進模型context；在執行read-only或side-effectful command前先durably保存command prompt，完成後再保存bounded visible result。
5. 區分 wire request ID、service request correlation、durable logical turn ID；Desktop React 在首次 send 前產生並保留 logical ID，CLI host 產生同型 ID，TypeScript/Rust 只轉送，Python 驗證並作 idempotency key；retry 同一已接受 turn必須沿用該 ID。
6. React failure UX 依「prompt 未接受」與「已接受但未完成」決定是否保留 draft、顯示 interrupted/failed，及允許明確 retry。
7. 更新 shared protocol fixture、Python/TS/Rust tests；Plan-specific protocol field 先保留到 Phase 05，但不得再承擔 durability。

## Non-goals

- 不在本階段移除所有 Plan Mode UI/protocol/code；Phase 05 專責清除。
- 不在本階段刪除 conversation-history Chroma implementation；Phase 06 專責清除。
- 不自動 retry 或 replay provider/tool；retry 必須是使用者明確動作。
- 不讓 Rust transport request ID 變成 durable turn identity。
- 不保證 thinking mode 選擇跨完整 backend restart 持久化；只保證 normal→extended→restart 後已完成對話仍存在。

## Dependencies and prerequisites

- Phase 03 vertical-slice tests 通過；CLI/Desktop已基本讀寫 JSON，stable logical turn ID與 terminal state已跨最小 protocol固定。
- 先讀 Desktop `service.py`, `server.py`, catalog、protocol fixture、TS backend/reducer 與 Rust command/shutdown tests。
- 確認此 repository 是 app lockstep source checkout；預設直接更新 protocol v1。若發現受支援的外部 protocol consumer，停止並取得版本化策略授權，不自行加相容層。
- CLI 只需共享 repository 與 lifecycle；沒有授權新增 session browser UI。

## Expected components

預期變更集中在：

- `app/agent/desktop/service.py`, catalog/protocol/server 的相鄰模組
- CLI session construction 的相鄰模組
- `app/desktop/src/` 的 backend/types/reducer/App 中與 conversation lifecycle 直接相關部分
- `app/desktop/src-tauri/` 中 transport/shutdown contract 的最小改動
- `app/tests/test_desktop_conversations.py`, `test_desktop_service.py`, `test_desktop_server.py`, shared protocol fixture tests
- 對應 TypeScript 與 Rust tests

## Authorization and stop conditions

本階段授權 lockstep protocol 更新，但不授權通用 compatibility layer、schema 變更、背景 watcher 或 multiwriter。以下情況停止：

- 發現外部支援中的 client 依賴目前 protocol v1 shape。
- retry 無法沿用 durable logical ID，或需要把 transport request ID 持久化才可工作。
- catalog reconciliation 會覆寫 conversation JSON 或自動刪除未知檔案。
- UI 無法可靠區分「prompt durable 前失敗」與「prompt 已接受後中斷」。

## Implementation and verification plan

### Preflight

1. 從 Phase 03 build-log evidence重核三種舊 ID的退場/保留結果，確認只有 wire requestId做 correlation、logical turn ID做 domain idempotency、turnNumber做 conversation order。
2. 記錄 protocol v1 request/response/error shape 與 shared fixture consumer。
3. 記錄 catalog 的 atomic replace/validation 慣例及 A→B→A、shutdown 現況。
4. 固定 UI state table：not accepted、pending、completed、failed、interrupted、display-only。

### Red

先建立跨層失敗測試：

- create 第一個 prompt 在任何 provider 工作前即有 JSON，catalog 可在 crash 後由掃描補回。
- JSON orphan、catalog-only missing、單一 malformed JSON 各自 reconciliation，健康 session 仍可開啟。
- Catalog file 整體損壞時可由健康 conversation JSON 重建索引；原 conversation files 不被修改。
- A→B→A 保留 completed/pending/display-only transcript，且不呼叫 legacy flush。
- backend restart 後 completed turns 恢復；normal→extended→restart 不遺失內容。
- 50-turn transcript 經 bounded DTO 分頁完整顯示，sidebar title、turn count、created/updated time 均從 JSON summary 推導；模型仍只取最後 10 個 eligible turns。
- transport duplicate delivery 或已 completed turn 的同-ID retry 使用既有 durable result，不建立第二個 turn，也不重跑 provider/tool；failed/interrupted turn 的使用者明確 retry 沿用原 logical turn ID，但可再次執行 provider/tool，不承諾通用外部 side-effect dedupe。
- Completed commit 後、result delivery 前中斷或 UI timeout 時，React 仍持有首次 send 前的 logical ID，重送後 Python 回既有 durable result；完整 app restart 則由 transcript 恢復相同 ID/state。
- prompt durable 前失敗時 React 保留 draft；已 durable 後中斷時顯示已接受 record，retry 不建立新 logical turn。
- `/help` 等本地命令保留原始顯示內容但不進 context。
- Extension/prune等有副作用的本機command也先保存display-only pending prompt；在已獲既有one-shot confirmation後才執行，完成結果後寫，crash/restart不auto replay。
- Active turn期間conversation switch仍被拒絕；restart、switch、timeout會清除pending approval，Bash每次執行及extension/prune仍維持one-shot confirmation。

### Green

1. 補齊 Desktop/CLI construction與 materialization的 edge paths，持續只用同一 repository與 conversation ID，不得用 Chroma/Plan merge還原。
2. Catalog 僅保存可重建的 summary/index；startup/list 時掃描 canonical directory 並逐檔 reconcile。
3. Protocol request/response/error 明確傳遞 logical turn ID、accepted/persisted 與 terminal state；transport ID 只負責 correlation。
4. React 在 dispatch 前產生並保存 logical ID；TS/Rust bridge 逐欄保真轉送且不自行產生 durable identity；Python 驗證並以 repository 狀態處理 duplicate；React reducer 依 state table 更新 draft/transcript。
5. 驗證並強化Phase 03已切換的switch/shutdown：不得呼叫legacy flush，三語DTO/error mapping不得殘留或重新引入失真的flush-only contract。
6. Transcript paging/serialization 允許非 pair states，並保持 turnNumber 順序。
7. 保留 transient empty-session UX；第一個 prompt durable 後才要求 JSON/catalog 可恢復，不建立假的空 transcript 填補 catalog-only entry。
8. 重跑並保留active-turn/switch與approval lifecycle guards；conversation persistence不得序列化或恢復approval tokens。
9. 將local command handler包在同一logical-ID/prompt-first display-only lifecycle內；command result需經既有bounded/SafeContent boundary後commit。Read-only與side-effectful command都不進context，失敗/中斷不假裝completed且不自動重播。

### Refactor

- 移除因 cutover 而 dead 的 catalog registration-on-first-completed 與 restore merge code。
- 保留現有 per-session locks、approval lifecycle、SafeContent 邊界。
- 不順手重寫 React architecture、Tauri transport 或 CLI command framework。

### Verification

Python（從 `app/`）：

```bash
conda run -n app poetry run pytest tests/test_desktop_conversations.py tests/test_desktop_service.py tests/test_desktop_server.py tests/test_desktop_protocol_contract.py tests/test_desktop_fixture.py -q
conda run -n app poetry run pytest tests/test_bash_tool.py tests/test_extension_user_journey.py tests/test_slash_commands.py tests/test_policy_tool_node.py tests/test_tool_access.py -q
```

Desktop（從 `app/desktop/`）：

```bash
conda run -n app node --test --experimental-strip-types tests/protocol.test.ts tests/backend.test.ts tests/conversations.test.ts
conda run -n app ./node_modules/.bin/tsc --noEmit
conda run -n app cargo test --manifest-path src-tauri/Cargo.toml protocol::tests
conda run -n app cargo test --manifest-path src-tauri/Cargo.toml backend::tests::child_crash_fails_pending_and_restart_is_user_driven
```

若新增的 domain-retry Rust test使用不同名稱，build log記錄精確 replacement filter。本機`node_modules/.bin/tsc --noEmit`是必要typecheck；binary不存在時停止，不得隱式下載。此階段不執行完整npm test、`npm run build`、完整Cargo suite或Tauri bundle，它們保留到Phase 07。

## Reliability, security, and recovery

- Catalog 不是 authority；刪 catalog 不得刪 conversation，重建不得改 JSON。
- Completed-result replay 與 duplicate delivery 必須 idempotent 且不得重跑 provider/tool；failed/interrupted retry 只保證沿用 logical turn ID、不新增 turn。Restart 永不自動重播 provider/tool，且不宣稱能對外部 side effect 提供通用 dedupe。
- Malformed conversation 的錯誤可見但局部隔離；不要把其內容放入 UI error/log。
- 原始 display input 與 semantic input 分離，避免 slash-command text 或 UI-only output 污染 prompt。
- Cross-language deserialization 對未知 state/version fail closed，不自行降級成 completed。

## Acceptance Criteria

- [ ] CLI 與 Desktop 都從 canonical JSON create/restore conversation。
- [ ] Catalog 可由 JSON 重建，orphan/missing/malformed 案例各有測試且不破壞健康 sessions。
- [ ] Catalog 全檔損壞可重建；catalog-only missing entry 明確顯示 unavailable，沒有靜默刪除或假 transcript。
- [ ] 跨 Python/TS/Rust/React 的 logical turn ID 與 state 一致，transport ID 未被持久化為 domain identity。
- [ ] Completed-result replay 與 duplicate delivery 不新增 turn 且不重跑 provider/tool；failed/interrupted retry 沿用原 logical turn ID，但允許重新執行且不宣稱通用外部 side-effect dedupe；restart 不自動 replay。
- [ ] Completed-before-ack/UI-timeout 與 full-app-restart cases 都證明首次 send 前的 logical ID 可被保留或由 JSON 恢復。
- [ ] UI 正確區分未接受與已接受的失敗，draft/transcript 行為符合 state table。
- [ ] A→B→A、backend restart、normal→extended→restart 的代表 journey 通過。
- [ ] Sidebar title/turn count/updatedAt 由 JSON 推導；50-turn transcript 透過 bounded pages 完整可見且不越過 protocol size/SafeContent 邊界。
- [ ] Sidebar title始終來自第一個有效accepted conversational prompt；display-only、blank或later prompt不能設定/改寫它，catalog cache也不能成為title authority。
- [ ] Local slash commands 是 display-only 且不進 context。
- [ ] Read-only與side-effectful local commands都prompt-first；extension/prune的既有one-shot approval保留，crash後只顯示interrupted且不auto replay。
- [ ] Active turn阻擋switch；restart/switch/timeout清approval；Bash、extension、prune的一次性確認語意有直接tests且approval不進JSON。

## Evidence to record

在 build log 記錄 identity mapping、protocol diff、catalog reconciliation matrix、各語言測試命令/exit code、代表 UI state assertions。若任何active `flushed` no-op、flush-only error或legacy restore caller仍存在，本phase維持Blocked；migration-only reference則列出精確allowlist理由。

## Handoff

Phase 05 可在 host 已不依賴 Plan durability 後移除 Plan Mode。若 protocol 仍用 plan fields 決定 turn completion，或 Desktop restore 仍 merge legacy stores，不得開始清除。
