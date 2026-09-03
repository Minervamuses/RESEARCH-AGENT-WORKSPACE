# Canonical Conversation JSON 與 Plan Mode 退場 — Goals

## 目的與背景

本計畫以 `GUI` 分支 `b145b040f014560157ef9444544f4102b81e485e`（2026-09-03）為基準，把目前分散於 Python 記憶體 `recent_turns`、conversation `chat_history` Chroma、Plan Mode Markdown log 與 desktop catalog 的對話狀態，收斂成單一、可立即持久化、可獨立恢復的本機紀錄。

目前 normal turn 只在回答完成後進入記憶體；它要等 window eviction、conversation switch 或正常 shutdown 才寫入 Chroma。若持續寫入失敗，`app/agent/turns/store.py` 的 hard cap 甚至會丟棄最舊 turn。Desktop 在第一個 finalized answer 後即可把 session ID 寫進 `desktop-projects.json`，因此 catalog membership 可能比 transcript durability 更早成立。恢復時又要合併 Chroma、Plan log 與目前 process memory，形成三個競爭來源。

Plan Mode 並不是 LangGraph 的另一條 reasoning graph。它主要改變 persistence target、加入 mode hint，並在 CLI、desktop protocol、React 與 session 中維護額外控制狀態。真正的 reasoning 選擇是 `thinking = normal | extended`；Extended Thinking、Skills、Citation、tool policy 與 approval 邊界都必須保留。

這個 bundle 是逐階段施工契約，不是實作證據。計畫建立時沒有修改應用程式或測試，也沒有宣稱任何未執行的檢查已通過。

## 期望成果

- 每個 conversation ID 在 `<persist_dir>/conversations/<conversation-id>.json` 至多有一份具 schema version 的 UTF-8 canonical transcript；檔名與 payload identity 一致。
- accepted prompt 在 provider 或 tool 執行前 durable；finalized assistant response 在 terminal success 前 durable；檔案能表達尚未完成的 turn。
- Desktop sidebar、完整 transcript、turn numbering、恢復與最近十回合模型 context 都由 canonical JSON 衍生；catalog 只保留可重建索引與 project/sidebar 順序。
- Product Plan Mode 從 UI、CLI、protocol、session、persistence、restore、測試與現行文件退場；一般對話中撰寫計畫、planning Skills 與 Extended Thinking 保留。
- Conversation Chroma 與 `recall_history` 退場；研究文件 RAG 仍使用既有 Chroma/Ollama 路徑，精確文字搜尋改為使用者可見且維持 Bash approval 的 grep/read-file 流程。

## 成功條件

### Durable lifecycle 與 exactly-once

| 情境 | 必須觀察到的結果 |
|---|---|
| 第一個 prompt | JSON durable commit 成功後才開始 model/tool；conversation 此時已可恢復，catalog 落後不會使內容消失。 |
| Prompt write 失敗 | 不呼叫 provider、不執行 tool；UI/CLI 保留可重送文字，沒有假的 accepted turn。 |
| Prompt write 後立即終止 | 重啟後看得到同一個 pending/interrupted prompt；不自動 replay。 |
| Provider/tool 失敗 | Prompt 保留並標示未完成；明確 retry 沿用同一 logical turn，不追加第二份 user message。 |
| Response write 失敗 | 不回 terminal success；檔案不宣稱 completed，未持久化 answer 不只留在 React state。 |
| Response write 後、UI result 前終止 | 重啟或同-ID retry 取得恰好一份已保存 response，不重跑 provider/tool。 |
| Tool 可能已有副作用後終止 | 重啟不自動執行；使用者明確選擇 retry、discard 或另開新 turn。 |

### Restore、context 與 catalog

| 情境 | 必須觀察到的結果 |
|---|---|
| 完整 backend restart | 只靠 JSON 即可 list、select、read、continue；不依賴舊 process memory。 |
| 50 個 completed turns | UI 可分頁查看 50 個；模型只收到最近十個 completed 且 context-eligible 的回合，順序由舊到新。 |
| 本次 prompt | 在 assembled model input 中恰好出現一次，且位於歷史之後。 |
| A→B→A | A/B 不交叉污染、不需要 history flush，回到 A 時 turn number 連續。 |
| JSON 存在但 catalog 缺項 | 啟動或 refresh 可重新發現並 reconcile，不重跑模型。 |
| Catalog 有 ID 但 JSON 缺失 | 顯示 unavailable，不建立假的空 transcript。 |
| 單一 malformed/oversized/version-mismatch JSON | 只有該 conversation degraded；其他 conversation 與 backend 可用。 |
| Slash/Skill 輸入 | UI/grep 看得到原始輸入；模型 context 使用實際送入 agent 的 semantic text，one-shot Skill 不會因 restore 重新啟用。 |
| 可見本機 command | 回覆可在 restart 後顯示為 display-only，但不占最近十回合、不進模型 context。 |

### 退場與保留界線

| 情境 | 必須觀察到的結果 |
|---|---|
| Product Plan Mode | `session.set_mode`、`planMode`、`planLogPath`、`/mode normal|plan`、plan hints、writer 與新 log 產生路徑皆不存在。 |
| Extended Thinking | normal/extended 切換、proposer/reviewer/reviser/fusion、citation 相容性限制與共同 finalizer 仍通過。 |
| 新 turn 完成 | 不產生 Plan log，也不建立 conversation-history embedding。 |
| Ollama/chat-history 不可用 | Conversation create/send/save/restart/select/continue 仍運作。 |
| Document RAG | `rag_explore`、`rag_search`、`rag_get_context`、ingest、`raw.json`、`folder_meta.json` 與 `knowledge` Chroma 行為不因本改造退化。 |
| Legacy migration 成功 | JSON 重新讀取後與現有嚴格 reader 可恢復的 turn identity、順序、文字與 timestamp 等價。 |
| Legacy migration 失敗 | 原 Chroma/Plan logs 不被修改或刪除；不留下看似成功但不完整的 canonical JSON。 |
| 歷史精確搜尋 | 固定 conversation root 可被既有 approval-gated shell grep；找不到 paraphrase 是明確接受的取捨。 |

## 範圍

- `app/agent/` 的 conversation domain、session/turn lifecycle、CLI、tool inventory、desktop catalog/service/fixture 與最小必要 adapters。
- `app/desktop/` 的 protocol-v1 contract/fixtures、Python/TypeScript/Rust validators、React conversation state/UI 與 shutdown semantics。
- Legacy Chroma role-pair與 Plan log 的 bounded read-only importer、catalog reconciliation、fixture-only migration rehearsal、failure injection 與 recovery behavior。
- 直接受影響的 Python/TypeScript/Rust tests，以及 root/component/`for_agents`/issue 文件中已過時的現行架構敘述。
- 保護 document RAG、Citation、Skills、Extended Thinking、SafeContent、Bash approval 與 single-active-turn 的回歸驗證。

## 非目標

- 不建立 conversation embedding、RAG ingest、SQLite/FTS、倒排索引、自動摘要、background compaction 或 long-term-memory extraction。
- 不支援多使用者、雲端同步、多個 desktop process 共寫、distributed transaction、worker、queue、service 或 database。
- 不新增 CLI 的 conversation browser/selector，也不要求 thinking mode 在完整 backend restart 後保持選取；只要求已完成的 normal/extended turns 可恢復。
- 不保存 chain of thought、內部 reasoning、raw provider payload、完整 response metadata、secret、authorization header、raw stderr、未過濾 tool arguments/results、React dump 或 LangGraph object serialization。
- 不自動刪除 legacy Chroma、Plan logs 或 archive；不修改歷史 `harness/`、`note/`、無關 `issue/`，也不處理鄰近 RAG/extension/citation backlog。

## Canonical lifecycle 契約

### Context 定義

「最近十則 prompt/response」固定指最近十個 `completed` 且 `context-eligible` 的 conversation turns，也就是最多十個 user prompt 加十個 finalized assistant responses。組裝順序固定為：

```text
system prompt
→ 當前 Skill / tool availability / citation 等 ephemeral system context
→ 最近十個 completed、context-eligible turns（舊到新）
→ 本次 prompt，恰好一次
```

Pending、failed/interrupted、display-only、UI activity、raw tool trace、被拒絕或失敗的 retry attempt 不占這十個 turns。UI transcript 範圍與模型 context 範圍分離。

### Turn 語意

| 狀態／種類 | Durable meaning | Assistant text | Model context |
|---|---|---|---|
| pending/submitted | Prompt 已接受並持久化，執行尚未完成。 | 無 | 排除 |
| completed | Prompt 與 finalized response 都已持久化。 | 必須存在 | 依 `context-eligible` |
| failed/interrupted | 執行或 persistence 沒有完成 response；prompt 仍保留。 | 不得冒充成功 | 排除 |
| display-only | 本機 command 等可見交換。 | 可存在 | 永遠排除 |

每個 turn 必須區分原始 display text 與實際送入模型的 semantic/context text。Transport `requestId` 只做 wire correlation；durable logical turn identity 與單調 `turnNumber` 必須在 provider/tool 前配置。Retry 重用 logical turn identity；同 ID、不同 prompt 必須 conflict fail-closed。Schema 的實際欄位名與 validation code 由 Phase 01 固定，但不得改變這些語意。

Lifecycle 與呈現種類必須能正交表達：本機 command 在執行前也可能是 `pending`，完成後才成為可見的 display-only exchange，但它從頭到尾都不具 context eligibility。Sidebar title固定取最低turnNumber的第一個有效、已接受、非display-only conversational prompt；以nonblank semantic text判定有效，以bounded original display text產生可見title。後續prompt、catalog cache或command text不得改寫title。

### Write ordering

```text
validate bounded input and stable identity
→ durable prompt write
→ best-effort catalog registration/reconciliation
→ normal or extended model/tool execution
→ tool-protocol safety
→ citation gate/render
→ desktop final-text boundary
→ durable finalized-response write
→ terminal success
```

Catalog failure可以留下可重試的索引狀態，但不得讓已 durable 的 conversation 消失，也不得要求 replay model。Response write failure不得繞過 finalizer或回報成功。

## 必須保留的既有行為與 invariants

| 邊界 | 必須保留 |
|---|---|
| Domain ownership | Python 是 conversation JSON、catalog、RAG、citation 與 extension state 的唯一 writer；React 只表達 intent，Rust/Tauri 只管理 native window、child lifecycle 與 protocol correlation。 |
| Turn serialization | 每個 session 同時最多一個 turn；active turn 期間不得切換 conversation；approval/tool/turn identity 不跨 conversation。 |
| Finalization | `ChatSession.finalize_and_record()` 的 safety/citation/final-text chokepoint 必須先於 assistant response persistence 與 user-visible success。 |
| Tool security | Prompt 中未列出的 forged tool call 仍由 execution policy 拒絕；Bash 每次 approval、extension/prune one-shot confirmation、restart/switch/timeout 清 approval 的行為不弱化。 |
| Desktop safety | Protocol schema/bounds/forbidden secret-like keys、bounded DTO、SafeContent、URL revalidation 與不傳 raw stderr/provider/tool internals 的邊界保留。 |
| Package boundary | `app/rag/` 仍 framework-neutral 且不得 import `agent`; conversation repository 位於 `agent` domain。 |
| Skills/Citation/Thinking | One-shot Skill 為當前 turn ephemeral；citation bundle/registry 不由 transcript 取代；Citation 先 gate/render 再保存；Extended Thinking 完成分支使用同一 finalizer 與 transcript contract。 |

## 新增且不可破壞的 JSON invariants

| ID | 規則 |
|---|---|
| JSON-INV-001 | 每個 conversation ID 至多一份 canonical JSON；restart、sidebar、context 與 turn numbering 都從它衍生。 |
| JSON-INV-002 | Prompt durable write 成功後才算 accepted，才允許 provider/tool execution。 |
| JSON-INV-003 | Finalized response durable write 成功後才可回 terminal success。 |
| JSON-INV-004 | 同一 logical prompt/response 不因 retry、restart、UI timeout 或 rematerialization 重複插入。 |
| JSON-INV-005 | Turn identity 單調且順序穩定；restore 不重新編號，也不把舊 turn 當新 turn 保存。 |
| JSON-INV-006 | Model context 永遠取最近十個 completed、context-eligible turns；本次 prompt 恰好附加一次。 |
| JSON-INV-007 | Pending/interrupted turn 在 restart 後不自動 replay；需使用者明確決定。 |
| JSON-INV-008 | Catalog 可遺失或落後並由 JSON 重建；catalog 不得比 transcript 更權威。 |
| JSON-INV-009 | Malformed、oversized 或 schema-mismatch conversation 只使該檔 degraded。 |
| JSON-INV-010 | Cutover 後一般 runtime 不讀寫 chat-history Chroma 或 Plan logs；legacy reader 只存在於明確 migration boundary。 |

## 限制與權威

| 限制 | 權威 | 對計畫的影響 |
|---|---|---|
| Linux/WSL + Conda `app`; Poetry 管 Python packages | 根 `AGENTS.md` 與 live toolchain | 所有命令在 `/home/minervamuses/research-agent-workspace` 執行；不得用 system Python、pip 或 `.venv`。 |
| 小型單人本機專案，優先簡單與可除錯 | 根 `AGENTS.md`、使用者架構 brief | 使用一 conversation 一 JSON；不引入新 service、database、concurrency model 或 compatibility framework。 |
| Conversation root 固定為 `<persist_dir>/conversations/` | 使用者架構與現有 `persist_dir` boundary | 可 grep、可 scan/reconcile；不污染 `app/rag/`。 |
| 單 writer；外部 rewrite fail-closed | 使用者架構 brief | Repository 在 replace 前驗證 fingerprint；不靜默覆寫外部修改。 |
| Protocol 為 lockstep source-checkout app | Live repository evidence | 預設原地更新 protocol v1 contract、fixtures 與三語言 implementation，不建立 v1/v2 negotiation 或長期雙路徑；若發現受支援的外部 consumer，須停下取得新決定。 |
| Legacy data 不可自動刪除 | 使用者架構 brief | Import 後保留 source/archive；清除是未來獨立且明確授權的操作。 |
| Dependency、schema/API、廣泛多檔、昂貴或 Git 操作需明確授權 | 根 `AGENTS.md` | 本次只寫 plan；未來須由 `PROMPTS.md` 的完整 launch block 明確啟動，dependency、真實資料 migration、remote/destructive/Git actions 仍另行 gated。 |

## 已知未知與使用者決策

沒有尚待使用者回答、會阻止本 plan 完成的產品決策。下列技術細節不得在 authoring 時假裝已知，已分配給 Phase 01/02 的 executable contract 與 bounded preflight：

- JSON 欄位的最終拼字、storage/DTO size alignment、failure reason 的最小安全集合。
- Durable logical turn、wire request、單調 turn number 與 retry attempt 的精確型別關係。
- 現有 bounded Plan v2 tool activity 可保留多少 display metadata；它永遠不成為 model context 或 raw trace authority。
- Legacy fusion Plan turns 等現行嚴格 reader 不可恢復的資料，應明確 migration-failed/degraded，不能捏造等價內容。
- Startup migration/reconciliation 的最小 batching 與回報形式；JSON 存在即為成功邊界，不新增第二份 migration status database。

Thinking mode 本身不要求跨完整 backend restart 持久化；驗收 `normal → extended → restart` 指兩種已完成 turn 都依同一 transcript contract 恢復，restart 後控制值可依現有安全預設回到 normal。CLI 必須共用 repository 與 lifecycle，但新增跨 session browser/selector 不在範圍。

## 來源

- 使用者於 2026-09-03 提供的「以每會話 JSON 取代對話 Chroma，並移除 Plan Mode」上位架構 brief。
- 根 `AGENTS.md`。
- `issue/07-gui-first-turn-durability-deferred.md` 與 `for_agents/future-work-backlog.md` 的 `BACKLOG-012`。
- `app/agent/session.py`、`app/agent/turns/`、`app/agent/history_rag/`、`app/agent/desktop/`、`app/desktop/` 與相關 tests。
- `for_agents/architecture-map.md`、`data-flow.md`、`invariants.md`、`dangerous-assumptions.md`、`module-responsibilities.md`、`testing-strategy.md`、`known-failure-modes.md`。
