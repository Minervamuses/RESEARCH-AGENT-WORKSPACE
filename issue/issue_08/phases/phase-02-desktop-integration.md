# Phase 02 — Desktop Citation 整合與恢復驗收

## 目標

Desktop 使用 Phase 01 同一個 Python Citation command；
使用者可從已完成的通用 menu 選取、送出、看到工具活動和正式答案。
切換／重啟後顯示既有答案與工具摘要，且不重播工作或恢復 registry。

## 來源

- ../GOALS.md、../PLANS.md、../build-log.md、Phase 01 evidence/context。
- issue/issue_02/PLANS.md、其 build-log 與完成後 live catalog/menu。
- app/agent/desktop/service.py、app/desktop/src/App.tsx、
  app/desktop/src/conversations.ts、app/desktop/src/protocol.ts。
- app/desktop/protocol/v1/contract.json、app/desktop/package.json。
- test_desktop_service.py、test_desktop_conversations.py、
  test_desktop_protocol_contract.py、desktop/tests/。

## 範圍與預期元件

Production 預期只改 service.py 與 App.tsx：
讓 reserved Citation command 的 followup／skill_name 走 session.turn_outcome，
並更新入口提示。重用 issue 02 的 Python eligibility／catalog、通用選取 UI、
現有 final-only result、tool activity、transcript 以及 output path 呈現。

測試以 test_desktop_service.py、test_desktop_conversations.py 為主，
按必要性補 desktop/tests/answer_stream.test.ts／conversations.test.ts；
protocol tests 和其契約為不變式驗證，預期不改 schema。

## 非目標

不補做 issue 02、不新增 registry store／RPC／Cancel button／workflow toolbar、
bundle browser、auto-resume、parallel command parser 或 React Skill policy。
本 phase 不重寫通用 recovery、catalog 或 transcript reducer。

## 依賴與前置

- Phase 01 在 build-log Complete，required evidence 足夠，正式產品契約沒有待決。
- issue 02 的可執行 Python catalog 與 menu 已存在；讀取其實際 helper／DTO／tests。
  2026-09-12 live helper 為 `_session_slash_registry`、`_desktop_command_eligible`、
  snapshot `slashCommands` 與 React `SlashComposer`。使用者已批准越過 issue 02
  尚缺原生 GUI 驗收的前置門檻；本 phase 自身驗收要求仍保留。
- 先確認現有 node_modules 可用，npm／node 是 Conda app 的 Linux 工具。
  不自動 npm install／npm ci，也不動 package-lock。
- **Unresolved：** 原生 Linux Desktop 接 fake provider／temporary store 的
  可操作入口和啟動命令。先檢查 live Desktop backend／Tauri 啟動程式與
  test_desktop_service.py 的 factory 接縫。若只有直接接使用者設定的入口，
  不啟動它；提出最小既有接縫替代，缺必要 UI evidence 則保持 Blocked。
  不以未確認的啟動命令、SSR 字串或 npm build 推論 UI 已通過。

## 實作與驗證計劃

### Preflight／最小修改

1. 以 Phase 01 command contract 對照 service 的 dynamic Skill／built-in local
   command 分支；讓 Python 同一 registry 結果決定 dispatch 和 catalog eligibility。
   只加 allowlist 會遇到 local handler 不接受 followup_input，不能作為完整修正。
2. Python tests 比較 CLI parser 與 Desktop 對有效需求、空 command、舊 off tokens、
   unavailable Citation／name collision 的語意和錯誤訊息；wrapper 維持原協定。
   Menu 只在 backend 可 load／dispatch Citation 時列出。
3. Desktop 的有效 Citation 直接走既有 session.turn_outcome，保留原 command
   display_input、turnId／retry／busy guards，收到 authoritative final-only answer。
   不由 React 啟用 Skill，不新增 hidden active mode。
4. App 更新 CLI-only 說明為實際可用的單次 Citation／暫用 normal 契約；
   同一次工作可看見 existing busy、citation_workflow activity 和 final answer。
   若原選 extended，工作後 selector 與 backend 真正 mode 一致。
5. 用現有 fake factory 但真 ChatSession／tool／temporary store 跑 Desktop
   dispatch 代表流程；不能只用回傳固定成功值的 FakeSession 證明 registry cleanup。
6. 在現有 conversation tests 補 Citation 專屬 A→B→A、backend recreation、
   completed duplicate／retry 與 interrupted restore。比對保存的 assistant text、
   bounded tool activities、provider/model/tool counts、output bundle 以及空 registry。
   既有 raw payload display-only 邊界不變，restore 不重跑舊 call。
7. Active turn 的 switch／shutdown 保持 BUSY_TURN；以取消 task 的既有接縫
   驗證 service busy flag 釋放、session cleanup 及可重新操作。不得把 off
   指令或 UI 暫存文字當成已取消後端工作。

### Planned verification

依 PLANS 共用環境從 app/ 執行；以下均未作為 implementation evidence 跑過。

```bash
timeout 300s poetry run pytest tests/test_desktop_service.py tests/test_desktop_conversations.py tests/test_desktop_protocol_contract.py -q
cd desktop
timeout 300s npm test
timeout 300s npm run build
cd ..
```

如 issue 02 把直接測試移至新檔，preflight 依實際檔案修訂 focused command
並記原因；不能默默跳過 catalog coverage。只有 production 進一步改動、
failure 或新證據時才重跑相關 checks。

**GUI 代表驗收：** 在確認安全的 Linux Desktop fake／temporary session：

- 按 /，選取 Citation，補上 fixture 文獻保存需求；選取不直接送出。
- 送出後看到單次工作／normal 說明、工具活動，再看到一份經 gate 的正式答案。
- 工作完成後送一般問題，核對沒有 Citation 狀態延續，thinking 選項正確。
- A→B→A 以及 backend restart，看到同一份保存答案／工具摘要；
  model/tool counter 不增加，沒有 Citation active／registry 重建。
- 用可控 fake failure／取消例驗證提示、恢復可操作性，以及 interrupted
  conversation 不自動續跑。正常 terminal 後 output 檔仍存在。

此 native UI 步驟和 backend／Node checks 是不同證據。
若目前工具無法操作 Linux Desktop，記 unavailable 並交由有該環境的使用者
完成指定操作，或先取得等價替代驗證的明確接受；不得標 Complete。

**最後一次完整 suite 與 diff（從 app/）：**

```bash
timeout 540s poetry run pytest
git -C .. diff --check
```

這是全計劃唯一預定完整 Python suite；若逾時／無關失敗，記實際結果，
不自動第二次全跑、不擴大修無關 subsystem，按 PLANS 的門檻處理。

## 驗收條件

- [ ] GUI command catalog 與 actual dispatch 同源；Citation 可見且真正可執行，
      invalid／unavailable commands 的處理與 CLI 核准契約一致。
- [ ] 真 ChatSession、fake provider、真 tool/service/gate 的 Desktop journey
      產生一份可見正式答案、工具活動與 temp bundle，terminal cleanup 正確。
- [ ] 原生代表操作有直接觀察；CLI-only 文案不再誤導，thinking／busy UI 與
      實際 session 一致，沒有新增 React policy／hidden mode。
- [ ] 普通下一回合、switch、restore、restart、duplicate 和明確 retry
      符合 GOALS 的 retention／no-replay 契約；已有 bundle 不被 cleanup 刪除。
- [ ] Required Python focused tests、Node tests／build、一次完整 suite 和
      diff check 有記錄；必要缺失補齊或獲使用者明確接受。
- [ ] 全部 GOALS 成功條件可映射 observed evidence，未改 persistent schema、
      trust authority，未重播舊工具，既有工作變更保留。

## 復原、停止與證據交接

維持原有 error、failed／interrupted、busy guards，不發明新的 terminal enum。
需要 protocol／reducer／新的 UI state module 或超出預估六檔時，先提出
具體失敗原因與最小 write set 取得授權；不要為完成畫面而先改 schema。
遇必要 check failure／unavailable 保持 In progress 或 Blocked，不能宣稱 issue 關閉。

在 ../build-log.md 記錄 exact commands、GUI 環境／操作／看到的結果、counter、
bundle 存留、未測限制及逐項 success evidence。重大發現才寫
../context/phase-02-desktop-integration-context.md；
真實 review 才建立 ../code_review/phase-02-review.md。

依 ../PLANS.md 的 Overall Completion Criteria 做最後核對。
全部達成才標 Complete，向使用者交付實際結果並停止，不修改原 issue 狀態、
不建立額外報告、不接著實作其他 issue。
