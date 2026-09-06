# GUI 修復計劃 — 使用者決策紀錄

## 紀錄性質

本檔只記錄目前修復計劃必須遵守的產品決策與範圍界線。

以下各項均以專案擁有者／使用者本人於 2026-08-30、2026-08-31 或 2026-09-01 明確提出的要求為準。引文是使用者原話；「現況蒐證」只說明程式在決策當時怎麼做，不把 coding agent 的推論冒充為使用者決定。實作狀態與證據只由 [`build-log.md`](build-log.md) 記錄，本檔不把決策本身冒充為完成證據。

## USER DECISION 001 — CLI 與 GUI 預設開啟 MCP

> 「預設關閉 MCP 是錯的，無論 CLI 或 GUI，我都要它預設開啟。」

修復計劃必須把下列內容視為已決定的產品要求：

- CLI 預設開啟 MCP。
- GUI 預設開啟 MCP。
- 不得再把「GUI 是否預設載入 MCP」列為待決產品問題。
- 現行 GUI 預設關閉 MCP 的行為屬於需要修正的缺口。

## USER SCOPE DECISION 002 — 此次不修復 Fusion 與 Extended Thinking

> 「與 Fusion、Extended Thinking 相關的部分，此次計劃不修復，我日後再處理。」

本次修復計劃的範圍界線如下：

- 不安排 Fusion 相關修復。
- 不安排 Extended Thinking 相關修復。
- 若其他修復與它們有相依性，只記錄影響與後續風險，不藉此擴張本次修復範圍。
- Fusion 與 Extended Thinking 的處理時間、驗收標準及修復方式，留待使用者日後另行決定。

## USER SCOPE DECISION 003 — 第一回合內容尚未耐久保存的問題延後處理

> 「在 fix_plans 裡面紀錄這件事我決定保留，本次不修正，之後再處理。」

本次修復計劃接受下列範圍界線：

- 不更動第一個 normal answer 完成後的 catalog registration 與 recent-turn persistence 順序。
- 這表示「sidebar 已列出對話，但第一批問題與回答仍只在 backend 記憶體」的風險仍然存在；此決定是延後修正，不代表現況已安全。
- 尚未執行真實 backend abnormal-loss boundary test，因此紀錄必須區分「寫入順序已由 source 證實」與「SIGKILL 後的具體失敗尚未重現」。
- 後續處理的歷史追蹤檔為 `issue/07-gui-first-turn-durability-deferred.md`；問題解決後已移除。

## USER DECISION 004 — 取消 Desktop 的固定十分鐘總時限

> 「在 fix_plans 裡面紀錄，取消十分鐘設置。」

修復計劃必須把下列內容視為已決定的產品要求：

- 移除 Desktop 對一般 request 套用的固定 600 秒總執行期限。
- 一個仍在正常研究、使用工具或回報進度的回合，不得只因總經過時間超過十分鐘就被終止。
- 不把 600 秒直接換成另一個任意的較大總時限；backend 啟動、關閉與真正失去回應的偵測可以有各自界線，但不能再混成同一個長回合 absolute deadline。
- 本決定不授權修改 Fusion 或 Extended Thinking 路徑。
- 問題與後續驗收的歷史追蹤檔為 `issue/08-desktop-absolute-request-timeout.md`；問題解決後已移除。

## USER DECISION 005 — 移除 Task mode 與 GUI Skill 控制，改由 slash command 啟動 Skill

> 「我的看法是本來就不該有這種東西，skill 裡面如果不能寫好功能路由，那個 skill 就是失敗的。另外，我不想要再繼續有個 skill button，我要跟 Claude Code 一樣，用 slash command 來啟動 skill，理論上我 CLI 介面就是這樣做的，GUI 多弄了 button，現在我要把它拆掉。」

修復計劃必須遵守：

- Task mode 不再是使用者要選擇的產品概念；一個 Skill 必須在自己的指令與邏輯內完成工作路由。
- 移除 GUI 的 Active skill dropdown／button，以及 task-mode 顯示或選擇介面。
- Skill 只能由使用者輸入 slash command 啟動，不得由 GUI 的獨立控制狀態暗中啟用。
- 不能只刪除 React 控制。現行 Task mode 同時存在於 CLI handler、Skill runtime、manifest schema 與內建 Skill manifest；修復計劃必須追蹤並移除整條已廢棄契約，避免留下 GUI 看不到但 runtime 仍依賴的半套狀態。

### 現況蒐證與必要校正

- CLI 現在使用 `/skill <name> [mode]` 與 `/skill none`，不是 `/<skill-name>`。
- CLI 現在的 Skill 啟用狀態會持續影響後續回合，直到 `/skill none`、改選 Skill 或 process restart；它不是天然的單次 slash-command 執行。
- Desktop composer 的 slash-command allowlist 目前不包含 `/skill`，所以直接移除 GUI 控制後，使用者反而無法在 GUI 啟動 Skill。
- 使用者已決定「以 slash command 啟動」；最終語法已由 USER DECISION 012 固定為 `/<skill-name> <自然語言 prompt>`。作用期間由後續 USER DECISION 009 決定為一次性，不得再沿用現行 persistent activation。Citation Skill 依 USER SCOPE DECISION 013 暫不套用這次語法遷移。

## USER DECISION 006 — Normal OpenRouter 路徑改成真正的生成中串流

> 「假設是因為 OpenRouter 那邊不支援，就取消逐字顯示機制，直接整坨出來；假設 OpenRouter 那邊其實支援，就要改掉現況。你研究清楚後，直接去紀錄到 fix_plans 裡面。」

### 官方蒐證結論

OpenRouter 支援真正的生成中串流，不是只能在答案完成後一次回傳全文：

- OpenRouter Chat API 接受 `stream: true`，以 Server-Sent Events 回傳生成中的增量內容。
- OpenRouter 官方 quickstart 示範逐一迭代 chunk，讀取每個 chunk 的 `delta` 新文字。
- LangGraph 的 `stream_mode="messages"` 能從 graph 內的 LLM call 送出 token／message chunk，並附帶 node metadata 供應用程式篩選來源。

官方資料：

- [OpenRouter — Create a chat completion](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion)
- [OpenRouter — Quickstart](https://openrouter.ai/docs/cookbook/get-started/quickstart)
- [LangGraph — Streaming](https://docs.langchain.com/oss/python/langgraph/streaming)

### 對修復計劃的決定

- Normal、非 Fusion、非 Extended Thinking 的 OpenRouter 回合改用真正的 live text-delta streaming。
- 移除目前「先等待完整答案，再把全文切成最多 16 KiB 的 `answer.chunk`」這條 post-finalized chunk delivery；它不是逐字生成，而且短答案通常只會送一塊。
- OpenRouter 已支援 live streaming，因此 normal path 不得再以 provider 不支援為由保留 post-finalized fallback。
- Fusion 與 Extended Thinking 仍依 USER SCOPE DECISION 002 排除於本次修復。

### 已知工程邊界（不是新增的使用者產品決定）

LangGraph 的 message stream 可能同時包含工具呼叫、empty retry、repair 前草稿與最後被 finalizer 修改的內容。實作者仍需用 source 與測試證明 GUI 只呈現正確的 answer stream；這是完成真串流所必須解決的 correctness 問題，不是授權退回目前的完成後切塊機制。

## USER DECISION 007 — Skill 不做跨重啟控制狀態恢復

> 「這是個偽議題；如前所述，該次對話沒有 slash command，skill 就不該是開啟的。」

本次修復計劃採用以下產品契約：

- Active Skill 必須來自使用者的 slash-command 操作，不從 React control snapshot 或 backend restart 前的暫存狀態自行恢復。
- Backend restart 後，舊 conversation 中曾經發生的 slash command 不會被自動重播；在使用者再次輸入 Skill slash command 前，Active Skill 為未啟用。
- 不新增 active Skill 的 durable persistence，也不把 backend restart 後 Skill 回到未啟用狀態列為缺陷。
- 同一個 backend lifecycle 內也不得持續沿用 Active Skill；Skill slash command 只作用於它所啟動的一次工作，後續普通輸入不得自動繼承。CLI 與 GUI 都依 USER DECISION 009 修改。
- 這項決定只處理 Skill；不以 slash-command 理由推論 Plan mode 的 persistence 語意。Extended Thinking 依 USER SCOPE DECISION 002 另行處理。

## USER SCOPE DECISION 008 — 不支援同時執行兩個 GUI process

> 「本來就不該同時開兩個，不予處理。」

本次修復計劃的範圍界線如下：

- 支援情境是一個 local state root 同時只有一個 GUI process。
- 不修復兩個 GUI process 同時寫入 `desktop-projects.json` 時的 catalog lost update。
- 不加入跨 process lock、compare-and-swap storage 或其他多 GUI 併發架構。
- 這是明確不支援的操作方式；若使用者仍同時開啟兩個 GUI，catalog entry 互相覆蓋的風險不在本次保證內。

## USER DECISION 009 — CLI 與 GUI 的 Skill activation 都改成一次性

針對現況「CLI 啟用 Skill 後會持續作用於後續回合，並不是一次性執行」，使用者明確指示：

> 「這件事情在 CLI、GUI 兩邊都必須改掉，寫入 fix_plans。」

修復計劃必須遵守：

- CLI 與 GUI 採用同一個一次性 Skill invocation 契約。
- 一次 Skill slash command 只把指定 Skill 套用到該 command 所啟動的一次 agent 工作。
- 該次工作到達成功、失敗或取消等 terminal state 後，不得留下會影響後續普通輸入的 Active Skill。
- 下一個沒有 Skill slash command 的普通輸入必須在未啟用 Skill 的狀態執行。
- 現行 CLI「先 `/skill <name>`，再讓後續回合持續沿用，直到 `/skill none`」的兩步式 persistent activation 不符合新契約，CLI 與 GUI 都必須改。
- 最終 slash 語法已由 USER DECISION 012 固定為 `/<skill-name> <自然語言 prompt>`；除 Citation Skill 的延後例外外，不得以 session-persistent control 實作。

## USER DECISION 010 — GUI composer 必須允許 Skill slash command

針對現況「GUI composer 禁止 `/skill`」，使用者明確指示：

> 「必須改掉，記錄下來。」

修復計劃必須遵守：

- Desktop composer 不得繼續全面拒絕 canonical Skill slash command。
- GUI 移除 Skill button／dropdown 後，使用者必須能直接在 composer 輸入最終選定的 Skill slash 語法並啟動一次性工作。
- Python backend 仍負責辨識、驗證與執行 slash command；React 不自行推測 Skill 名稱、權限或作用期間。
- 未知、格式錯誤或未授權的 slash command 仍須在進入模型前明確拒絕；本決定只打開正式支援的 Skill slash command，不是允許所有任意 command。

## USER DECISION 011 — Sidebar 對話必須像 ChatGPT 一樣可查看並接續

使用者再次明確說明產品目的：

> 「我在說一次目的，是為了創造像 ChatGPT 的體驗，左邊那排對話點進去時不只可以看見先前的對話，還能接續繼續對話。」

針對舊工具是否需要重跑，以及 Tool／Result 被錯放進 user 欄位的問題，使用者另明確指示：

> 「本來就不該再次執行不是嗎？這只是為了看過去的紀錄而已，為什麼要再次執行？」
>
> 「那就改一下新增欄位。」
>
> 「改掉恢復程式的欄位，讓他分的清楚就好。」

### 產品驗收契約

- Sidebar 選取一個既有 conversation 後，GUI 必須顯示先前的完整對話，並允許使用者從同一 conversation 繼續送出新回合。
- Conversation selection／transcript restore 是載入既有紀錄，不得重新執行任何舊 tool call，不得因載入而呼叫模型，也不得把歷史 Tool／Result 當成待執行工作。
- 只有使用者在恢復後新送出的回合，才可以依正常 agent 流程產生新的模型或工具執行。
- 使用過工具的 Plan conversation 不得只因含有 `Tool`／`Result` 紀錄就被整份標成 degraded 或禁止選取。

### 恢復資料必須分開角色

恢復程式與對應 DTO／資料結構必須至少能分清三類語意資料；實際欄位名稱由正式修復計劃固定：

1. 使用者原始輸入。
2. 該回合的工具活動紀錄，例如 tool name、arguments、result、status，以及能可靠保存時的 tool-call identity。
3. 助理經 finalization 後的正式答案。

必須遵守：

- Tool／Result 不得串接進 user 欄位，也不得在 GUI 標成「You」。
- GUI 應把工具活動顯示為獨立且明確標示的 tool activity／result，而不是使用者或助理的一部分。
- 使用者原始輸入恢復為 user role；正式最終答案恢復為 assistant role。
- 工具活動只有在具備完整、可驗證的 tool-call／result 配對時，才可用正確的 tool role 加入後續模型上下文。
- 舊資料若缺少可靠配對，工具活動仍可作為獨立的唯讀歷史顯示，但不得偽造成 user message、不得重新執行，也不得以猜測出的 tool role 注入模型；conversation 仍以原始 user／final assistant 對話接續。

### Persistent format 與舊資料邊界

- 本決定明確授權在完成上述需求所必要的最小範圍內，修改 Plan persistence／restore 欄位與相關 protocol DTO；先前 Phase 02「不得修改既有 Plan log format」的限制，不得再用來阻止 tool-bearing conversation 的正確恢復。
- 不得把「新增可辨識欄位」擴張成與本需求無關的新 persistence framework；優先採用最小、versioned、可驗證且能明確區分角色的資料表示。
- 對新的紀錄，writer 必須保存足以無歧義重建 user、tool activity 與 final assistant 的結構資訊。
- 對既有 legacy Markdown，工具標記本身不是拒絕載入的理由；恢復程式應在可可靠辨識的範圍內轉換。無法可靠配對的舊工具 trace 依上節作為 display-only 資料，不得污染後續 prompt。

### 最小 lifecycle 驗收

修復計劃至少必須覆蓋：

1. Plan 回合執行 fake tool，保存後關閉 backend。
2. 重啟 GUI，從 sidebar 選取該 conversation。
3. Transcript 依序顯示原始 user、獨立 tool activity／result、final assistant；任何 tool 都沒有再次執行。
4. 使用者送出新的普通問題，系統沿用正確的舊 user／assistant context，不把歷史工具內容冒充成 user input。
5. 新回合只在自身需要時產生新的 tool call，且不重播舊回合的 call。

## USER DECISION 012 — 非 Citation Skill 採專屬的一次性 slash command

針對先前尚未固定的 canonical Skill slash 語法，使用者明確選擇：

> 「我選這個，假設有個skill叫做writting,他的啟用就會是 /writting <自然語言prompt>」

本次修復計劃必須遵守：

- 一般 Skill 的 canonical 語法是 `/<skill-name> <自然語言 prompt>`；例如 Skill 名稱為 `writting` 時，使用者輸入 `/writting 請改寫這段文字`。
- 同一個 slash command 同時選定 Skill 並提供該次工作的完整自然語言輸入；不得先把 Skill 設成 session state，再等下一個普通回合沿用。
- 缺少自然語言 prompt 時，系統只能回傳清楚的用法錯誤或可用 Skill 提示，不得留下等待下一回合的 Active Skill。
- 現行通用 `/skill <name> [mode]`、`/skill none` 與 task-mode 選擇不再是一般 Skill 的產品契約。
- Python backend 依目前 session 實際載入的 Skill catalog 驗證名稱、命令衝突與權限，並執行一次性工作；CLI completion 可呈現可用命令，但 React 不自行解析或推測 Skill 名稱。
- 內建 slash command 與其 alias 保留名稱優先權。Skill 名稱若不能安全表示為單一 slash token，或與保留命令衝突，必須明確拒絕或標示不可用，不得靜默覆寫既有 handler。
- Citation Skill 是 USER SCOPE DECISION 013 的明確例外；本輪不把 `/citation` 改造成這個一般 Skill 流程。

## USER SCOPE DECISION 013 — Citation Skill 流程延後處理

使用者明確指示：

> 「本次不處理citation這個skill。然後去issue裡面追加一份文件，寫清楚citation skill的流程需要處理」

本次修復計劃的範圍界線如下：

- 不把現行 `/citation` handler、`/citation off`、Citation source registry、citation finalization 或 thinking-mode 相容性改造成一般 `/<skill-name> <prompt>` 流程。
- `/citation` 保留為內建保留命令，不由動態 Skill slash command 覆寫；本輪不宣稱它已符合一般 Skill 的一次性 invocation 契約。
- 移除 GUI 的通用 Active skill control 後，本輪不新增替代的 GUI Citation 啟動流程。這是已知延後缺口，不代表 Citation 已不需要 GUI 路徑。
- 移除共用 Task mode 欄位時，只能做維持共用 runtime/schema 一致性所需的機械調整；不得藉此重設 Citation 的 registry 生命週期、thinking 限制、持續期間或恢復語意。
- 目前 CLI Citation 的既有行為應以 focused regression 保護，避免一般 Skill 修復意外破壞；產品流程的正式改造另案處理。
- 後續問題、未決產品選擇與驗收方向見 [`issue/08-citation-skill-flow-deferred.md`](../../issue/08-citation-skill-flow-deferred.md)。

## USER DECISION 014 — Normal answer 改為 authoritative final-only delivery

使用者在 Phase 05 的 accepted-answer／live-token characterisation blocker 已被完整記錄後，做出新的正式產品決定：

> 「取消 USER DECISION 006 的真正生成中串流要求。Normal answer 不再進行 live token streaming，也不要在答案完成後用 post_finalized chunk 模擬串流。」

本決定明確 **supersede USER DECISION 006**。USER DECISION 006 與其官方蒐證、工程邊界仍保留為歷史，不刪除、不改寫成未曾存在；從本決定起，Phase 05 與最終驗收必須遵守以下契約：

- Python agent 必須先完成 generation、repair、finalization、validation 與 persistence，Desktop 才能顯示 answer。
- GUI 一次顯示 authoritative final answer 的完整內容，不顯示 provisional answer preview。
- Normal success path 不發送 `answer.chunk`；terminal `session.turn` result 使用 `streamKind=final_only`，並以 `chunkCount=0` 表示沒有 answer event。
- 不得把完成後的全文切成 `post_finalized` chunks，或用任何 post-finalized event 模擬串流。
- Error、cancel、provider/child failure 或 validation failure 不顯示任何 partial answer；可保留原始 user draft 與既有 bounded activity/progress，但它們不能包含 answer text。
- Fusion、Extended Thinking 與 Citation redesign 仍維持 USER SCOPE DECISION 002／013 的排除範圍；本決定不授權改寫它們。

### 對既有 blocker 的處置

- `build-log.md` 中 Phase 05 的 fake live-graph characterisation、rejected draft trace 與 blocker conclusion 都是有效歷史證據，必須保留。
- 該 blocker 不再需要 provisional-draft authority，因為產品目標已改成 final-only；Phase 05 可在本決策授權下恢復執行。
- 最小實作方向是移除現行 Normal `post_finalized answer.chunk` producer／consumer chain，保留 Python 已有的 authoritative finalization、validation 與 persistence chokepoint，並以 deterministic fake 驗證 terminal result 前沒有 answer text。
