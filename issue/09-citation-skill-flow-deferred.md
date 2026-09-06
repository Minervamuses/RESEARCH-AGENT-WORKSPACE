# Citation Skill 一次性啟動與 GUI 流程延後處理

## Issue 定位

- 類型：Skill invocation／session lifecycle／GUI access 契約尚未統一。
- 優先度：Deferred。
- 狀態：Open；使用者於 2026-08-31 明確延後 Citation Skill 的跨介面 lifecycle 決策。非 Citation Skill 的一次性 slash-command 修復已完成。
- 本次處理：只記錄現況、已知落差、未決產品選擇與後續驗收，不修改 Citation 實作。
- 執行順序：先完成 [`13-desktop-slash-command-menu.md`](13-desktop-slash-command-menu.md) 的通用 GUI command catalog／鍵盤清單；Citation command 是否能列出與執行，仍須等本 issue 的 lifecycle 決策完成。

## 使用者決定

> 「本次不處理citation這個skill。然後去issue裡面追加一份文件，寫清楚citation skill的流程需要處理」

一般 Skill 現已使用 `/<skill-name> <自然語言 prompt>` 的一次性工作，但 Citation 沒有被強行套入同一流程。決策來源見 [`harness/fix_plans/user-decisions.md`](../harness/fix_plans/user-decisions.md)。

## 現行 CLI 流程（Source 已確認）

`/citation` 目前不是一般 Skill 的薄 alias，而是一個有獨立 lifecycle 的內建 handler：

1. `/citation` 會啟用 `citation` Skill，沒有自然語言 prompt 時仍保持啟用。
2. `/citation <自然語言 prompt>` 先啟用 Citation，再把 command 後方的原始文字送進普通 agent turn。
3. 啟用狀態會持續影響後續回合，直到 `/citation off`、`/citation none`、`/citation deactivate`、切換到其他 Skill，或 process/session 結束。
4. Citation 啟用會取代先前 Active Skill；關閉 Citation 後不會恢復舊 Skill。
5. 啟用 Citation 會強制 thinking mode 回到 `normal`；Citation active 時要求 `extended` 會被拒絕。

主要來源：

- `app/agent/cli/slash_commands.py`
- `app/agent/cli/chat.py`
- `app/agent/session.py`
- `app/tests/test_citation_slash_command.py`
- `app/tests/test_citation_skill_activation.py`

## Citation 為何不能直接視為一般一次性 Skill

Citation Skill 擁有一般 Skill 沒有的 session-scoped state：

- `CitationSessionPolicy` 延遲建立 `CitationService` 與 source registry。
- `citation_workflow` tool 會把可信 save receipt 與 registry 內容連結起來。
- prompt hint 只在 Citation active 且 registry 有可引用來源時注入。
- finalization 會驗證 citation marker、拒絕無效引用，並把可信來源渲染成正式答案。
- deactivation 或切換到其他 Skill 會丟棄 in-memory service 與 registry；已寫出的 citation bundle 不會刪除。

若只在一次 turn 的 `finally` 中直接關閉 Citation，可能同時改變 source registry 可用期間、跨回合研究流程、thinking 限制與 finalization 時點。這些都是產品與 correctness 決策，不能由一般 Skill 修復順便猜定。

主要來源：

- `app/agent/skills/citation/session_policy.py`
- `app/skills/citation/`
- `app/agent/session.py`
- `app/tests/test_citation_e2e.py`
- `app/tests/test_turn_finalizer.py`

## 現行 GUI 落差

Desktop composer 的 Python allowlist 目前不接受 `/citation`。舊的通用 Active Skill dropdown 與 `session.activate_skill`／`session.deactivate_skill` RPC 已被移除；一般非 Citation Skill 改由 Python-owned one-shot slash command 執行。React 現在明確顯示 Citation mode 為 CLI-only，沒有替代的 GUI Citation 入口。

因此現況是：

- CLI 的既有 `/citation` 流程暫時保留。
- `/citation` 保留為 built-in slash-command 名稱，動態 Skill command 不得覆寫它。
- GUI 沒有 Citation 啟動入口；這是已知 deferred gap，不得被描述為已解決或不再需要。
- Backend restart 後 Citation 是否應恢復、重新開始或要求新 command，仍待後續產品決定。

主要來源：

- `app/agent/desktop/service.py`
- `app/desktop/src/App.tsx`
- `app/desktop/src/protocol.ts`
- `app/desktop/protocol/v1/contract.json`
- `app/tests/test_desktop_service.py`

## 後續必須固定的產品決策

重新處理本 issue 時，至少要一次決定：

1. Citation 是嚴格單一 turn、由一條 command 完成的工作，還是允許一個明確有始有終的多回合 citation workflow。
2. 若允許多回合，開始、繼續、完成、取消與失敗各自用什麼 command／terminal state 表示；不得靠隱藏 dropdown state。
3. `/citation` 是否繼續是保留的專用命令，以及 CLI 與 GUI 是否採完全相同的語法與錯誤行為。
4. Source registry 在成功、失敗、取消、conversation switch、backend restart 與普通下一回合後應保留或清除到哪個界線。
5. Citation 與 normal／extended thinking 的相容契約；不得把目前強制 normal 當成永遠不需再確認的產品答案。
6. Citation tool activity、final assistant 與已儲存 citation bundle 在 conversation restore 時如何顯示與重建，且不得重跑舊 tool call。
7. GUI 暫時沒有 Citation 入口的缺口何時結束，以及需要什麼可見提示。

## 後續最小驗收方向

- CLI 與 GUI 使用同一個 Python-owned Citation command contract；React 不解析 Skill policy。
- 一次代表性 Citation 工作能取得來源、執行 `citation_workflow`、通過 citation gate 並產生 final answer。
- Success、provider/tool failure、validation failure、取消與 conversation switch 都有明確、可觀察的 registry cleanup／retention 行為。
- 下一個普通輸入不會在未經產品契約允許時偷偷沿用 Citation。
- Backend restart 不會重播 Citation command、舊 tool call 或未完成工作。
- 若產品選擇多回合 workflow，UI 必須明確顯示 active scope 與結束方式；若選擇單一 turn，terminal state 後必須完全清除 transient Citation state。
- Extended Thinking 相容性依正式決策驗收，不得藉一般 Skill 測試冒充。
- 測試使用 fake provider、fake citation tool 與 temporary registry/output root，不讀取 credential 值、不呼叫付費 provider、不修改真實使用者資料。

## 本輪明確非目標

- 不修改 `_handle_citation`、Citation Skill bundle、`CitationSessionPolicy`、citation gate／renderer 或 registry lifetime。
- 不把 `/citation` 自動轉成一般 `/<skill-name> <prompt>` handler。
- 不新增 GUI Citation button、dropdown、hidden state 或臨時 alias。
- 不以移除共用 `task_mode` 欄位宣稱 Citation lifecycle 已修復。
- 不處理 Citation 的 Extended Thinking、Fusion、跨重啟恢復或 persistence redesign。

## 主要參考檔案

- `harness/fix_plans/user-decisions.md`
- `app/agent/cli/slash_commands.py`
- `app/agent/cli/chat.py`
- `app/agent/session.py`
- `app/agent/skills/citation/session_policy.py`
- `app/skills/citation/`
- `app/agent/desktop/service.py`
- `app/desktop/src/App.tsx`
- `app/desktop/src/protocol.ts`
- `app/desktop/protocol/v1/contract.json`
- `app/tests/test_citation_slash_command.py`
- `app/tests/test_citation_skill_activation.py`
- `app/tests/test_citation_e2e.py`
- `app/tests/test_turn_finalizer.py`
