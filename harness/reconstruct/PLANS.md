# Canonical Conversation JSON 與 Plan Mode 退場 — Execution Plan

## 2026-09-05 correction overlay（目前有效）

這個 overlay 取代下方 roadmap 中與固定 answer/document/wire/transcript byte 拒絕及 legacy importer/migration 有關的工作與完成條件；原始 phases、估時與驗證紀錄保留為歷史，不能再當作目前功能要求。這次修正的狀態與實測只由 `build-log.md` 新增段落記錄。

目前只執行三個直接工作流：

1. 移除完整合法 assistant answer、整份 canonical JSON、`session.turn` 成功 result、transcript text/page 上的任意固定容量拒絕，讓同一全文可保存、final-only 交付、切換與重啟恢復。不得把舊數字換成另一個新數字；1 MiB submit input 與 tool/event/failure/security bounds 保留。
2. 移除正常 create/list/select/restore/restart/continue 對 legacy Chroma／Plan logs importer 的呼叫與 importer-only code/tests/fixtures/current docs。舊來源保持原樣；canonical JSON 流程與 catalog-only unavailable 行為保留。
3. 讓 React 以 `(conversationId, turnId)` 合併 retry 結果，採 canonical `turnNumber`／count；failed/interrupted 明確 retry 成功、completed replay、duplicate delivery、A→B→A 與 restart 都不得多一筆或多計一次。

Focused acceptance 必須覆蓋 40,000-byte 與 Unicode 正式回答、超過舊 2 MiB 單筆與累積超過舊 8 MiB 文件、50 turns／多頁／latest-10 context、final-only 與寫入失敗、無 legacy source／catalog-only ID、retry/replay dedupe，以及 Python／TypeScript／Rust lockstep。這些測試大小只是證明舊門檻已退場，不定義新 ceiling。原生 Tauri journey 與自動測試分開；無法取得 native surface 時須記為未驗證，不可用 build 或 headless 證據代替。

Fusion、Extended Thinking restart/retry、thinking-mode persistence、Citation redesign、document RAG、provider/model 選擇及其他 backlog 不在本輪範圍。Normal 仍為 `final_only`／`chunkCount=0`，Python 仍是唯一 durable writer，prompt-first、response-before-success、no automatic replay、latest-ten context、Bash approval、SafeContent 與 single-active-turn 仍是必要 gates。

本 correction 不新增 dependency，不修改 lockfile／environment definition，不操作真實使用者資料，不呼叫 live/paid provider，也不授權 commit、push、branch/worktree 或其他破壞性 Git 操作。

## 快速執行卡

**下一步（約 2 分鐘）：** 準備開始實作時，複製 `PROMPTS.md` 的「Start or Resume End-to-End Execution」完整 block，作為一則新訊息送出；在那之前不要把本 bundle 當成 implementation authorization。

**目前狀態：** 只有計畫；7 個 phases 全部 `Not started`，application/tests、真實 store、Git branch與dependencies都尚未變更。

以下是單一熟悉 Python/React/Rust agent、使用既有 offline tests、沒有 dependency或真實資料阻塞時的粗估；它是排程提示，不是完成承諾：

| 可見里程碑 | 涵蓋 | 粗估專注時間 | 完成時看得到的成果 |
|---|---|---:|---|
| Contract + importer | Phases 01–02 | 1–2 個工程日 | JSON round-trip、bounds與non-destructive legacy fixture import皆有綠燈 |
| Atomic vertical cutover | Phase 03 | 1–2 個工程日 | 第一個prompt先落盤，CLI/Desktop可restart/select/continue，無write/read split-brain |
| Host hardening + removals | Phases 04–06 | 2–3 個工程日 | Retry/catalog/paging完成，Plan Mode與conversation Chroma runtime消失 |
| Faults + docs + final checks | Phase 07 | 1–2 個工程日 | 六個crash points、full Desktop journey、一次broad validation與文件一致性完成 |

**總粗估：5–9 個工程日。** 任一phase遇到外部protocol consumer、legacy ambiguity、schema決策、dependency需求或>10分鐘的未授權額外broad rerun，就依stop condition暫停，不能用這個估時跨過gate。

## Plan 概況

- **Plan root:** `harness/reconstruct`
- **目的:** 以 [GOALS.md](GOALS.md) 的 lifecycle 與 invariants 為穩定契約，先建立 executable JSON domain，再切換 session/hosts，最後退役 Plan Mode 與 conversation Chroma。
- **Execution mode:** 使用者送出 `PROMPTS.md` 的完整 launch block 後，在授權範圍內 autonomous；本次 authoring 不授權實作。
- **Repository shape:** application；一個 Poetry Python distribution 加一個 React/Tauri desktop source-checkout app。
- **Change risk:** high；原因是 durable data format、crash semantics、legacy migration、三語言 protocol 與跨層移除 public surface，但資料只在單人本機範圍。
- **Phase directory:** `phases/`；根 `.gitignore` 會忽略任何 `build/`，現有 durable harness 也使用 `phases/`。

## Source-of-truth map

- Stable purpose、成功條件、範圍、non-goals、invariants 與 authoritative constraints：`GOALS.md`
- Phase order、dependencies、execution authorization、stop conditions 與 overall completion：`PLANS.md`
- 可複製的 launch/resume/review prompts：`PROMPTS.md`
- 每一 phase 的 bounded work 與 planned verification：`phases/phase-*.md`
- Runtime status 與實際執行/驗證證據：`build-log.md`
- Phase 開始後才出現的 material discoveries：`context/`
- 真正 review 發生後才出現的 findings：`code_review/`
- 最強事實：live repository、current diff、實際 tests/behavior；它們可推翻未執行的 plan，但不可靜默改寫 stable goal。

## 已確認 repository baseline

- Root `/home/minervamuses/research-agent-workspace`；唯一適用 instructions 是根 `AGENTS.md`；branch `GUI`、HEAD `b145b040f014560157ef9444544f4102b81e485e`，authoring preflight 的 worktree 為 clean。
- Linux/WSL login shell 可用 Conda `app`、Python 3.13.14、Poetry 2.4.1、Node 24.18.0/npm 11.16.0 與 Rust/Cargo。每次 execution 仍須重新驗證，不可依賴這份日期化快照。
- `ChatSession.turn_outcome()` 現在先執行 graph/tool，再由 `finalize_and_record()` 建立 completed record；`TurnStore` 只在 overflow/switch/shutdown 寫 Chroma。
- `DesktopService` 現在由 catalog IDs 列舉，restore 合併 Chroma + Plan logs + current memory；第一個 completed normal answer 後才 register catalog；switch/shutdown 綁 `flush_recent_turns()`。
- Desktop protocol v1 由 `app/desktop/protocol/v1/contract.json` 與 fixtures 定義，再由 Python、TypeScript、Rust 手動 implementation/test 對齊。`session.turn` 沒有 durable retry ID；Plan 與 Thinking 是兩個不同 control。
- Document RAG 使用 `knowledge` Chroma、`raw.json`、`folder_meta.json`；conversation history 使用獨立 `<persist_dir>/chat_history` collection。`app/rag/` 目前沒有 import `agent`。
- Catalog 的 tempfile + file fsync + `os.replace` + directory fsync 與 RAG JSONStore 的 external-fingerprint tests 是可參照行為，不是可直接搬入 `rag` 的 conversation domain abstraction。
- Authoring 只做 read-only discovery；沒有執行 pytest/npm/Cargo/Tauri build，也沒有使用 provider、Ollama、credentials 或真實 generated store。

## Execution authorization

### 本次 authoring 的 authority

只允許建立 `harness/reconstruct/` 內已凍結的 Markdown planning artifacts。這不授權修改 application/tests、變更 persistent data、執行 migration、改 protocol、加 dependency、commit 或其他 Git mutation。

### 完整 launch block 送出後的 routine authority

- 在每個 phase 列出的 causal scope 內修改 `app/agent/`、`app/desktop/`、`app/tests/` 與直接受影響的現有 docs；可新增最小 `app/agent/conversations/` domain package 與對應 tests。
- 明確實作 GOALS 已固定的一-conversation-一-JSON schema、prompt-first/finalized-response durability、legacy read-only migration、三語言 protocol-v1 lockstep changes，以及完整移除 Product Plan Mode 與 `recall_history`。
- 這項 launch authorization明確涵蓋超過三個直接相關 production files、persistent JSON schema 與既有 public desktop protocol method/field removal；不得藉此擴到其他 schema/API 或一般重構。
- 使用 isolated `tmp_path`/fixture roots 與 fake providers/runners，執行 phase-specific local checks；在 Phase 07 最多執行一次full Python suite、一次npm test、一次Cargo test與一次Tauri no-bundle build；後者依live config觸發唯一一次npm production build。
- 每個通過focused verification的logical change使用簡短Conventional Commit提交；push、merge、rebase、branch/worktree切換與publish仍不在授權內。
- 更新本 bundle 的 `build-log.md`、material `context/`、真正 review 的 `code_review/`，並在 evidence 推翻 future plan 時修訂尚未開始的 phase files。

### 必須停止並取得 fresh authority

- 需要新增/更新 dependency、environment definition、manifest 或 lockfile；現有 Chroma/Ollama dependencies 預期保留。
- 要改變 GOALS 的 lifecycle、context=10、single-writer、Python-only writer、legacy retention、Plan/recall removal 或 preserved safety behavior。
- 要對使用者真實 `persist_dir` 執行 migration、刪除/移動 legacy data、處理不可逆資料、讀 credentials、呼叫 live/paid providers，或寫入外部 system。
- 要建立 service/database/queue/background worker/new concurrency model、protocol compatibility framework、conversation semantic index，或支援多 writer。
- 要 push、merge、rebase、switch branch/worktree、deploy、release、publish，或執行第二次昂貴 broad pass。

如果受支援的外部 protocol-v1 consumer、既有 JSON collision、無法安全判定的 legacy source，或 required evidence 不可取得，將該 phase 設為 `Blocked`；不要用猜測、雙寫或資料刪除跨過阻塞。

### Repository instructions

每次 phase 的 live `AGENTS.md` 仍高於本 plan。Plan 不得修改 `AGENTS.md`，也不得把 launch authority 解讀成對無關 dirty changes 的所有權。

## Phase roadmap

| Phase | Observable outcome | Depends on | Build file |
|---|---|---|---|
| 01 — Canonical conversation contract | Versioned JSON model、state/identity/context semantics 與 fail-closed atomic repository 由 executable unit tests 固定 | None | `phases/phase-01-canonical-conversation-contract.md` |
| 02 — Legacy import bridge | 現有嚴格 Chroma/Plan readers 可在不改 source 的前提下，all-or-nothing 產生並驗證 canonical JSON | Phase 01 | `phases/phase-02-legacy-import-bridge.md` |
| 03 — Atomic write/read vertical cutover | Session、CLI、Python Desktop 與最小三語 protocol/client slice 同步切到 JSON；selected legacy session 先 import，prompt/final write ordering、latest-10 與 basic restart 保持可用，沒有「寫 JSON、仍從舊 store restore」的完成 checkpoint | Phases 01–02 | `phases/phase-03-write-through-turn-lifecycle.md` |
| 04 — Host/catalog/retry hardening | Catalog corruption/orphan/missing reconcile、完整 bounded transcript、display-only command、before-ack retry 與 UI failure semantics 都完成跨語言 edge journeys | Phase 03 | `phases/phase-04-host-catalog-and-retry-cutover.md` |
| 05 — Remove Product Plan Mode | CLI、session、protocol、Rust/TS/React、writer、tests 與現行 docs surfaces 不再有 Plan Mode；Extended Thinking 完整保留 | Phase 04 | `phases/phase-05-remove-plan-mode.md` |
| 06 — Retire chat-history Chroma | 一般 runtime 不初始化/讀寫 conversation Chroma，`recall_history` 從 tool policy 移除；document RAG Chroma 保留 | Phase 05 | `phases/phase-06-retire-chat-history-chroma.md` |
| 07 — Migration, faults, docs | Explicit fixture-only batch migration、crash/corruption/idempotency journeys、三語整合、原生視窗人工驗收與文件/invariants 完成，legacy source 保留為 archive | Phase 06 | `phases/phase-07-migration-faults-and-documentation.md` |

所有 phases 為依序 dependency chain；不得因下一階段看似容易而跳過 failing gate。Phase 03 的實作過程可有短暫、未宣告完成的 integration window，但該 phase 只有在 write、read、selected-session import 與最小 client protocol 已形成可工作的 vertical slice 後才能完成；同一 turn 永遠不得雙寫 JSON 與 legacy store。Phase 03–05 是 app-offline、不可對真實 user store 使用的非發布中間狀態；若執行在 Phase 06 前停止，app 保持不啟動。暫存的 Product Plan control 若仍存在，也只能把新 turn 寫入同一 JSON，不得再建立 Plan log。Phase 05/06 結束後普通 runtime 只能走 JSON，legacy code 只由 Phase 02 建立的 explicit migration boundary 觸及。

## Cross-phase technical decisions

### Canonical path 與 identity

- Root 為 `Path(config.persist_dir) / "conversations"`；檔名為 canonical UUIDv4 hex + `.json`，payload conversation ID 必須一致。
- Transport `requestId` 繼續只做 request/event/result correlation。Desktop React client 在首次 send 前產生一個 logical turn ID，保留到收到確定的 accepted/completed 結果，TypeScript/Rust 只逐字轉送；CLI host 在呼叫 session 前產生同型 ID。Python 驗證 logical ID、以它做 idempotency key，並只在 prompt commit 時配置/驗證 conversation-local 單調 turn number。
- 同 logical ID + 同 prompt 的 retry 是 idempotent；completed 時直接回 durable response，不重跑 provider/tool；同 ID + 不同內容是 conflict。
- UI timeout 或 completed commit 後 response delivery 中斷時，React 以首次 send 前保留的同一 logical ID retry；完整 app restart 則先從 JSON transcript 恢復該 ID/state，再決定顯示既有 completed result 或提供 interrupted retry，不能猜測新 ID。
- Exact attempt metadata 保持最少，只服務 lifecycle/retry/error display；不得建立 event-sourcing framework 或保存 provider internals。

### Protocol strategy

- 目前 app 是同一 source checkout 內 lockstep Python/TS/Rust，沒有 version negotiation 或受支援的外部 client；預設原地更新 v1 contract 與 fixtures，三語同一 phase 一起通過。
- `session.turn` 必須傳遞 durable logical identity 並回報 prompt 是否已 accepted/persisted；transcript DTO 能呈現 pending/failed/interrupted/display-only，而不是假設完整 pair。
- `session.set_thinking` 與 `thinkingMode` 保留；Phase 05 刪除 `session.set_mode`、`planMode`、`planLogPath`。
- `ShutdownReport.flushed` 與 `CONVERSATION_FLUSH_FAILED`/`SHUTDOWN_FLUSH_FAILED` 不得成為永遠成功的 no-op。Phase 04 將它們移除或改為真實 graceful/durability acknowledgement；Rust 仍需以 Python terminal shutdown result + child exit 判定 graceful。

### Legacy boundary

- Import 的等價範圍只涵蓋現有 bounded strict readers 可恢復的資料；已在過去 crash 中遺失的 recent memory、normal tool traces、不可恢復 fusion Plan turn 都不能捏造。
- 成功採 per-conversation temp write、re-read validation、atomic replace；失敗不留下 canonical file、不改 Chroma/Plan logs，並讓該 conversation degraded/migration-failed。
- 已驗證的 bounded legacy tool activity最多保留為 display metadata，永遠不是 context authority；raw/ambiguous/oversized activity 被隔離或使 import 失敗，依 Phase 01 contract。
- JSON 檔本身是 migration success marker；不新增 migration database。真實使用者資料 migration 仍需 fresh authority。

## Verification cadence

- Phase 先跑最小 failing/characterization check，再做 minimal Green；material refactor 後重跑 focused check。Required check 失敗時該 phase 保持 `In progress`/`Blocked`。
- Python commands 從 repository root 以 `cd app && conda run -n app poetry run pytest ... -q` 執行；TypeScript/Rust 從 `app/desktop` 以 Conda `app` toolchain 執行。
- Live OpenRouter/Ollama/MCP/citation provider 不屬於 verification；conversation tests 使用 fake provider，RAG preservation 使用現有 deterministic/offline tests。
- Phase 07 才各跑一次最終 broad Python、npm test、Cargo test與Tauri no-bundle build；Tauri目前以`beforeBuildCommand`執行唯一一次`npm run build`，因此不另跑standalone production build。若任何一項超過約十分鐘仍可讓第一次完成，但第二次 broad rerun 必須 fresh authority。
- `git diff --check`、residue searches、`git status --short --untracked-files=all` 與 validator 是結尾 checks；它們不替代 user-visible lifecycle/integration evidence。即使每個logical change都會commit，commit前與final residue search仍必須用`git grep --untracked`（或等價、明確包含untracked source的工具），而且相對phase-start baseline由本計畫新增的task-owned untracked檔要另做content/whitespace review；既有無關user-owned untracked檔只盤點、保留、不納入本任務所有權。Plain `git grep`/`git diff`不能當完整working-tree證據。

## Expected write surfaces

Phase files列出較精確的 expected components。整體外框如下；不是每一檔都一定會改，也不是無關 cleanup 的授權：

- New domain/tests：`app/agent/conversations/`、`app/tests/test_conversation_repository.py`、`app/tests/test_conversation_migration.py`。
- Session/turn/hosts：`app/agent/session.py`、`app/agent/turns/`、`app/agent/cli/`、`app/agent/desktop/` 與直接 tests/fixtures。
- Desktop contract/client：`app/desktop/protocol/v1/`、`app/desktop/src/protocol.ts`、`conversations.ts`、`backend.ts`、`App.tsx`、Rust protocol/backend 與 desktop tests。
- Tool retirement/RAG guard：`app/agent/history_rag/`、`app/agent/tools/`、`app/agent/graph.py`、thinking wiring與 tests；`app/rag/` production code不在本計畫變更範圍，若 live evidence 顯示非改不可，應停止並取得新授權。
- Docs：`README.md`、component READMEs、`app/SKILLS_GUIDE.md`、`for_agents/`、`issue/07-gui-first-turn-durability-deferred.md`；歷史 harness/note/issue records不做機械清理。

## Plan maintenance

- `build-log.md` 是唯一 mutable phase status/evidence owner；不要在 roadmap、prompt 或檔名放 current-phase pointer。
- Required focused/acceptance check 失敗會阻止 dependent phase。先診斷一個 causal hypothesis；同一原因兩次 focused implementation attempt 失敗後停止並記錄，不堆疊 speculative edits。
- Live evidence 推翻 future work 時，先在 `build-log.md` 保留觀察，再更新 `PLANS.md` 與受影響且尚未開始的 phase files；之後重跑 fresh-agent walkthrough。
- Stable purpose、scope、success conditions 或 invariants 的改變需要 explicit user decision 才能更新 `GOALS.md`。
- `context/` 只記 omission 會改變未來 implementation/verification 的 material discovery；`code_review/` 只在真 review 發生時建立。不要預建空檔。

## Overall completion criteria

- [ ] 七個 phase 在 `build-log.md` 都是 `Complete`，且每項 acceptance criterion 有實際 evidence mapping。
- [ ] GOALS 的 prompt-first、final-response durability、exactly-once、latest-10、restart/A→B→A、catalog reconcile、malformed isolation 與 display/context split 都由 deterministic journeys 證明。
- [ ] Product Plan Mode 與 conversation Chroma/`recall_history` 不再出現在普通 runtime/public UI/CLI/protocol；legacy references只留在 migration/archive/history docs 的明確邊界。
- [ ] Python/TypeScript/Rust protocol fixtures一致；SafeContent、approval、single-turn、Citation、Skills 與 Extended Thinking preserved checks通過。
- [ ] Conversation operation不需 Ollama/chat-history Chroma，document RAG deterministic suite仍通過，且 Chroma/Ollama dependencies沒有被錯刪。
- [ ] Legacy fixture migration成功/失敗都符合 non-destructive rules；沒有操作或刪除真實 user store。
- [ ] 一次 final Python/npm/Cargo/Tauri check set、`git diff --check`、path/residue/generated-data review與fresh-agent final review都有實際結果；任何 unavailable evidence/limitations 清楚記錄。
- [ ] 使用隔離fixture root的原生Tauri視窗人工journey有逐項觀察紀錄；headless/browser/layered automation不得替代未觀察的native、keyboard、focus、scroll或layout行為。
