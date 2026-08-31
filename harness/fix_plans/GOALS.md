# Research Agent Desktop GUI 修復 — Goals

## Purpose

以目前已完成的 Desktop GUI 為基礎，修正五個已由使用者確認的產品缺口：MCP 預設值、長回合固定總時限、一般 Skill 的啟動契約、Normal answer 的 authoritative final-only delivery，以及含工具紀錄的 sidebar conversation 恢復與接續。

本計劃是既有 `harness/plans/2026-08-24-desktop-gui-completion/` 完成後的 corrective plan。舊 bundle 保留為歷史證據，不回寫舊 phase；若舊 bundle 的假設與本計劃的使用者決策衝突，以 [`user-decisions.md`](user-decisions.md) 與本 bundle 為準。

本 bundle 同時保存跨 session 的執行計劃與實際 evidence；application code、test、manifest 或 internal protocol 只有在 [`PLANS.md`](PLANS.md) authorization envelope 與 eligible phase causal scope 內才可修改。Dependency/lockfile 與 `AGENTS.md` 不在授權內。

## Required Outcomes

- CLI 與 GUI 建立 session 時都預設載入 MCP；CLI 的既有正確預設要有 regression protection，GUI 不得再硬送 `loadMcp: false`。
- Desktop 一般 request 不再因固定 600 秒 absolute deadline 被終止；仍保留有因果依據的啟動、關閉、child exit 與 transport failure 邊界。
- 非 Citation Skill 由 CLI 與 GUI 共用的 Python-owned `/<skill-name> <自然語言 prompt>` 契約啟動，且只作用於該命令所建立的一次工作；成功、失敗、取消或關閉後都不得殘留 Active Skill 或 Task mode。
- Normal answer 只有在 Python 完成 generation、repair、finalization、validation 與 persistence 後才交付；Desktop 一次顯示完整 authoritative final answer，不發送 `answer.chunk`，也不以完成後切塊模擬串流。
- Sidebar 能載入並接續含工具活動的 Plan conversation：歷史 user、tool activity/result、final assistant 分開顯示，舊 tool call 永不因 restore 而重跑，可靠的新格式資料才能以 tool role 加入後續 prompt。
- Citation 的專用流程本次不重設；它保留為 built-in `/citation` 例外，已知 GUI 入口缺口另由 [`issue/09-citation-skill-flow-deferred.md`](../../issue/09-citation-skill-flow-deferred.md) 追蹤。

## Success Conditions

### MCP defaults

- [ ] CLI 在沒有 `--no-mcp` 時仍以 `load_mcp=True` 建立 session；明確傳入 `--no-mcp` 時仍關閉。
- [ ] GUI 的一般 session creation 讓 Python backend 的 `loadMcp=true` default 生效，或明確送 `true`；沒有另一條正常 GUI 建立路徑仍預設關閉 MCP。
- [ ] 驗證以 fake MCP loader／protocol fixture 完成，不連接真實外部 MCP server。

### Long-request liveness

- [ ] Rust supervisor 不再對已成功啟動的一般 `session.turn` 套用固定 600 秒總時限，也不以另一個任意較大 absolute deadline 取代。
- [ ] 一個 deterministic fake request 跨過測試中縮短的舊 deadline、期間送出合法 progress/event、最後回傳 terminal result，必須成功且 child 不被 kill。
- [ ] Child exit、stdout/pipe close、malformed protocol、startup failure 與 bounded graceful shutdown 仍會形成明確 terminal error；移除總時限不得把真正失敗變成永久等待。

### One-shot dynamic Skill invocation

- [ ] CLI 與 Desktop 對同一個 session Skill catalog 接受 `/<skill-name> <自然語言 prompt>`，並保留 command 後方原始自然語言文字。
- [ ] 空 prompt、未知 Skill、非法名稱、duplicate name、與 built-in command／alias 衝突，都在模型執行前 fail closed；起始沒有 Citation 時不留下任何 transient Skill，起始已有 Citation 時則保持其既有 state/registry。
- [ ] 一般 Skill 的 runtime scope 被 session turn lock 包住；success、graph/provider/finalizer/persistence error、cancellation 與 backend shutdown 都以 `finally` 等價邊界清除非 Citation transient state。若命令前 Citation 已 active，parse/empty/load failure 不得先 teardown Citation；只有另一 Skill 成功切換才沿用現行 teardown/no-restore 語意。
- [ ] 一般 Skill 成功執行後，緊接著的普通輸入以無 Active Skill 狀態執行；process restart 不恢復舊的一般 Active Skill。
- [ ] 一般 `/skill <name> [mode]`、`/skill none`、Task mode schema/runtime/manifest/UI/protocol control 與 Desktop Skill dropdown/RPC 都被完整移除，不留下第二套 hidden activation path。
- [ ] `/citation` 保留 built-in 優先權；focused Citation regression 證明一般 Skill 改動沒有順便重寫既有 CLI Citation lifecycle。本計劃不要求 GUI 可啟動 Citation。

### Normal authoritative final-only delivery

- [ ] Deterministic fake normal turn 證明 terminal `session.turn` result 是唯一 answer-text delivery，`streamKind=final_only`、`chunkCount=0`，且整個 success path 沒有 `answer.chunk`。
- [ ] Python generation、repair、finalization、final-text/wire validation 與 turn persistence 全部完成後，Desktop 才收到一次完整 authoritative answer；React 在此之前只顯示 bounded progress/activity 與 waiting state，不顯示 provisional answer text。
- [ ] Normal production、protocol 與 UI 不再保留 `post_finalized` 全文 slicing／reconciliation path；不得用另一種完成後 event 模擬串流。
- [ ] Error、cancel、provider/child failure、oversize 或 validation failure 不顯示、reconcile 或 persist partial answer；user draft 的既有 retry 行為可保留。
- [ ] Phase 05 的既有 rejected-draft characterisation evidence 保留為產品決策依據；Fusion、Extended Thinking 與 Citation redesign 不因 final-only 修復改變。

### Tool-aware conversation restore

- [ ] Plan persistence 使用一個最小、versioned 的既有格式延伸，能無歧義保存 user input、tool call/result activity 與 finalized assistant answer；不建立第二個 store 或 sidecar persistence framework。
- [ ] Transcript DTO 與 React rendering 將 tool activity 顯示成獨立角色，不串進 `userText`、不標成 `You`、不暴露未設限 raw payload。
- [ ] 新格式中只有完整且驗證通過的 call/result pair 可以重建為後續模型 tool context；prompt eligibility 由 parser 驗證推導，不能信任磁碟中的布林宣告。
- [ ] Legacy Plan log 即使含 `Tool`／`Result` marker 也可以選取與閱讀；無可靠 identity 的 legacy activity 僅 display-only，後續 prompt 只取可確認的 user/final assistant 內容。
- [ ] Citation scope／`citation_workflow` activity 本輪最多作 bounded display-only history；不設 prompt eligible、不重建 registry、不自動啟用 Citation。
- [ ] 代表性 lifecycle 以 fake tool 完成 `turn → persist → backend shutdown → restart → sidebar select → user/tool/final display → new normal turn`，觀察到舊 tool invocation count 沒有增加，且新回合沒有重播或冒充歷史工具文字。
- [ ] Catalog selection、pagination、merge/dedup 與 malformed/oversized input 邊界仍 fail closed，健康 conversation 不受單一壞檔污染。

### Final integration

- [ ] 各 phase 的 focused checks 通過，最後只執行一次適當的 Python broader suite、完整 npm tests、完整 Cargo tests 與 Tauri no-bundle build；實際命令與結果記入 `build-log.md`。
- [ ] 一次 isolated fake Desktop journey 證明 MCP default、長回合存活、dynamic Skill command、final-only answer delivery、tool-aware restore/continue 之間沒有互相回歸。
- [ ] `git diff --check` 通過，實際 diff 僅包含 phase 宣告且有因果必要性的檔案；沒有 dependency、lockfile、真實 user store、credential 或付費 provider 變更。

## In Scope

- `app/agent/cli/`、`app/agent/session.py`、`app/agent/state.py`、`app/agent/skills/`、`app/agent/turns/`、`app/agent/desktop/` 與直接受影響的 built-in Skill manifests/system prompt。
- `app/desktop/src/`、`app/desktop/tests/`、`app/desktop/protocol/v1/` 與 `app/desktop/src-tauri/src/` 的最小 protocol、supervisor、React/CSS 修復。
- `app/tests/` 中與 MCP default、slash command、Skill runtime、Citation regression、streaming、conversation persistence/restore 直接相關的 focused tests 與既有 isolated Desktop fixture。
- Plan log 的最小 versioned schema 延伸，以及同一 writer/parser/DTO/rendering chain 的相容讀取。
- 只使用 fake provider、fake tool、fake MCP、temporary state root 的 deterministic verification。

## Non-goals

- Fusion 或 Extended Thinking 的串流、Skill 相容性、模型選擇或其他修復。
- Citation handler、Citation source registry、citation gate/renderer、thinking 限制、持續期間、重啟語意或 GUI 替代入口的產品重設。
- 第一個 normal answer 完成後、catalog registration 前的 abnormal-loss durability；另見 [`issue/07-gui-first-turn-durability-deferred.md`](../../issue/07-gui-first-turn-durability-deferred.md)。
- 同一 local state root 同時執行兩個 GUI process。
- Extension Skill integrity、Fusion、其他 `issue/` 或 `note/` 中未被本計劃列入的問題。
- 任意 inactivity framework、heartbeat service、queue、worker、database、第二套 persistence、generic command router 或 broad architecture rewrite。
- Windows-native/macOS support、installer、release、deployment、CI、telemetry、多使用者或 remote service。
- 新 dependency、package-manager/lockfile 更新、live/paid provider call、Ollama/full dataset、真實 MCP endpoint 或真實使用者資料 mutation。
- 回寫或重開已完成的舊 GUI plan phases。

## Preserved Invariants

- 支援 runtime 是 WSL/Linux；Conda environment `app` 提供 Python/toolchain context，Poetry、npm 與 Cargo 只使用 repository 現有依賴圖。
- React 只呈現 bounded state 與收集 intent；Rust 只負責 desktop transport/process lifecycle；Python 擁有 slash parsing、Skill catalog/policy、agent/session state 與 persistence semantics。
- Composer 原始文字由 React 傳給 Python；React 不自行推測 dynamic Skill 名稱、command collision、permission 或 lifecycle。
- Static built-in commands與 alias 先取得 command namespace；`/citation` 是保留 built-in。Dynamic Skill 只能來自該 `ChatSession` 已載入且驗證成功的 catalog。
- Restore 是唯讀載入歷史，不呼叫模型、不執行工具、不重播 slash command。只有恢復後的新 user turn 能產生新的模型或工具工作。
- Authoritative final result 由 Python/finalizer 擁有；answer text 只經 terminal `final_only` result 交付。Progress/tool activity 不得攜帶 answer preview、繞過 finalization 或污染 durable history。
- 所有 transport/persistent strings、arrays 與 file reads 延續現有 bounded/fail-closed policy；不顯示 secret、credential、unbounded stderr、traceback、provider payload 或任意 raw tool data。
- Verification 預設用 injected fake 與 direct `/tmp` child；不讀 credential value、不改 real store、不呼叫 provider/MCP/Ollama。
- 執行者保留使用者既有 dirty-tree work，不 reset、checkout、格式化或順手修理無關檔案。
- Planned command、checkbox 與 phase 描述都不是 pass evidence；只有後續在 `build-log.md` 記錄的實際 observation 才算證據。

## Decision and Deferral Map

- MCP default：[`user-decisions.md`](user-decisions.md) USER DECISION 001。
- Fusion/Extended Thinking 排除：USER SCOPE DECISION 002。
- First-turn durability 延後：USER SCOPE DECISION 003 與 issue 07。
- 取消 600 秒總時限：USER DECISION 004 與 issue 08。
- 移除 Task mode／GUI Skill control：USER DECISION 005。
- Normal OpenRouter live streaming 的歷史要求：USER DECISION 006；已由 USER DECISION 014 明確 supersede。
- Normal authoritative final-only delivery：USER DECISION 014。
- Active Skill 不持久化：USER DECISION 007、009。
- 不支援多 GUI process：USER SCOPE DECISION 008。
- GUI 接受 Skill command：USER DECISION 010。
- Sidebar tool-aware restore/continue：USER DECISION 011。
- Dynamic Skill canonical syntax：USER DECISION 012。
- Citation 延後：USER SCOPE DECISION 013 與 issue 09。

## Known Engineering Unknowns / 工程未知

None currently identified for the Phase 05 product boundary. Phase 05 attempt 1 已用 fake live graph 證明 pre-token accepted-answer attribution 不安全；USER DECISION 014 以 final-only 契約解除該 blocker。實作者仍須用 focused tests 證明既有 finalization／validation／persistence ordering 與全鏈 `answer.chunk` removal，而不能把 source inference 當成 pass。

## Source Inputs

- [`user-decisions.md`](user-decisions.md) 中截至 2026-09-01 的使用者決策、USER DECISION 006 歷史蒐證與 superseding USER DECISION 014。
- Repository root `AGENTS.md` 與 live Git/runtime/toolchain evidence。
- 既有完成 bundle：`harness/plans/2026-08-24-desktop-gui-completion/`。
- [`issue/07-gui-first-turn-durability-deferred.md`](../../issue/07-gui-first-turn-durability-deferred.md)、[`issue/08-desktop-absolute-request-timeout.md`](../../issue/08-desktop-absolute-request-timeout.md)、[`issue/09-citation-skill-flow-deferred.md`](../../issue/09-citation-skill-flow-deferred.md)。
- Live Python、React/TypeScript、Rust、protocol contract、fixture 與 tests；執行 phase 時必須重新讀取，不能只信本計劃中的 dated paths。
