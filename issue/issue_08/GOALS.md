# Issue 08 — Citation 單次工作與 Desktop 流程：目標

## 目的與背景

來源為 [08-citation-skill-flow-deferred.md](../08-citation-skill-flow-deferred.md)。
Citation 目前是持續啟用的 CLI command，與一般一次性 Skill 不同；
Desktop 拒絕 /citation，也沒有替代入口。本計劃處理這個跨介面流程缺口，
保留可信 save receipt、citation gate、renderer 與既有 bundle。

**本文件是建議版，不是已核准的產品決策。** 2026-09-12 使用者要求讀取
AGENTS.md 後為 issue 08 撰寫計劃；已詢問工作週期與 thinking 選擇，
authoring 時尚未收到回答。以下採最小單次方案供審閱；實作前須確認
「待決事項」，不能因文件存在就視為允許改變 CLI／API 行為。

## 預期成果

- CLI 與 GUI 均以 Python-owned /citation <自然語言需求> 啟動一次工作。
  一次工作可以包含多個 model/tool round trips，並非只能呼叫一次工具。
- Citation 不再由 slash command 留下隱藏的跨回合 active state；
  下一個普通輸入使用一般聊天規則。
- 成功答案先完成可信引用驗證、渲染與既有保存流程，再釋放本次來源。
- GUI 能找到並執行 Citation，看到工具活動、正式答案與明確錯誤；
  恢復 conversation 只顯示已有記錄，不重播工具。

## 建議產品契約（待使用者確認）

### 指令與工作範圍

| 輸入 | 建議可觀察行為 |
|---|---|
| /citation <非空需求> | 一次 Citation 工作；原始 command 保留作顯示，原始自然語言部分傳入 model |
| /citation 或只有空白參數 | Python 回傳用法提示；不啟用 Skill、不呼叫 provider |
| /citation off、none、deactivate | Python 回傳「已改為單次工作，請使用 /citation <需求>」提示；不宣稱完成取消、不開始模型工作 |
| 一般下一回合 | 無 Citation active runtime、workflow tool 權限或 citable-source hint |
| 下一次 /citation <需求> | 新 service／registry；可依可見歷史選擇文獻，重新 save/reuse 取得本次可信 receipt |

/citation 繼續是保留 built-in，dynamic Skill 不得覆寫。同一組自然語言、
大小寫、空參數與舊 off token 的語意與錯誤文字由 Python 決定；
CLI 印字與 Desktop PROTOCOL_INVALID 封裝可依原介面不同，不另造錯誤協定。
舊 off tokens 不當成自然語言工作，也不成為 GUI Cancel API。

本提案不移除內部 persistent activation API；沒有 caller／compatibility 證據
不得順便刪除。CLI／GUI command 路徑必須改用受 turn lock 管理的 scope，
不能先在 parser handler 啟用後才進入 turn。

### Thinking

建議本次 Citation 僅在 normal 執行；接受原 session 選為 extended，
以可見提示說明這次暫用 normal，terminal cleanup 後恢復原設定。
不啟動 Fusion／extended Citation，也不永久改變使用者的 thinking 選項。
Durable turn 應記錄實際執行的 normal；GUI 原選項不因暫時 scope 變成陳舊值。
若使用者選擇納入 Extended Thinking，先修訂此契約與受影響 phase，不能
把「保留 normal」當成已被使用者核准。

### Registry、terminal state 與恢復

| 情境 | 暫存 Citation 狀態 | 已有答案／bundle |
|---|---|---|
| 成功 | gate、render、durable completion 完成後清除 | 保留正式答案與已寫 bundle |
| 工具回傳失敗／找不到來源 | 若 agent 能結束，按既有 finalization 結束後清除 | 如實呈現工具結果，不捏造保存成功 |
| Gate validation error | 保留既有安全回覆與 validation_errors，再清除 | 不將未驗證 marker 顯示成可信引用；不擅改 terminal schema |
| Provider exception／durable write failure | 既有失敗處理仍執行；本次暫存狀態必須釋放 | 不捏造 completed 或已保存答案；已落盤 bundle 保留 |
| Task cancellation | 既有 interrupted 路徑；finally 釋放、恢復 thinking | 不回滾已落盤或已開始的磁碟寫入 |
| Turn 中要求 conversation switch／shutdown | 保留既有 BUSY_TURN 拒絕，不偷偷切換或清除正在使用的 registry | 原工作依既有機制繼續／取消 |
| Terminal 後 conversation switch | 不攜帶 registry 至其他 conversation；切回也不恢復 active scope | 既有 final answer／bounded tool activity 可顯示 |
| Backend restart／unclean restart | 新 runtime 空 registry；未完成記錄走既有恢復規則，不自動續跑 | 從 canonical transcript 顯示 completed／failed／interrupted |
| Completed turnId 重送 | 不啟動新的 Citation scope、model 或 save | 回傳既有 durable answer |
| 明確 retry 失敗／中斷工作 | 依既有 retry 規則啟動新 scope；不得帶入舊 registry | 可使用既有安全 bundle reuse，不承諾零磁碟痕跡 |

取消清除的是 session 對 service／registry 的引用，並撤銷本次工具 scope；
不是抹掉已保存檔案。CitationService.save 使用 asyncio.to_thread 寫 bundle，
被取消後該磁碟操作可能完成。本方案保留這項既有行為，驗收晚到結果不污染
下一次工作，不新增背景工作管理器或取消交易框架。

Conversation restore 使用 canonical assistant text、bounded tool activities
與現有 Citation output 位置提示。它不重新驗證／重新渲染舊答案，不掃描 bundle
以補造 registry，不把歷史 receipt 或 source id 當本次可信來源。
已有記錄若未包含 bundle 路徑，UI 不捏造；本次不新增 bundle browser 或 restore schema。

## 成功條件

- [ ] 代表需求「/citation 找出並保存指定文獻，提供正式引用」從 fake provider、
      真 graph／tool／service 與 temporary output 走到真 gate/render 和保存答案。
- [ ] 上表各 terminal／switch／restart 情境有直接狀態與使用者輸出證據；
      下個普通輸入不繼承 Citation，thinking 設定符合正式決策。
- [ ] CLI 與 GUI 對同一 command 使用同一 Python 規則；GUI menu 只列可執行的 Citation。
- [ ] GUI 的 active 工作、工具活動、完成答案、錯誤與恢復內容可見；
      舊 CLI-only 文案在入口真正可用後更新。
- [ ] Restore、completed duplicate 與 backend restart 的 provider／tool counter
      證明沒有重播，既有 bundle 不被 cleanup 刪除。
- [ ] 原一般 one-shot Skill、citation trust gate、durable retry 與 Desktop
      final-only 回覆規則沒有被破壞；required checks 有實際結果。

## 範圍

只涵蓋 Citation command、turn-owned lifecycle、Desktop eligibility／catalog
接入、可見提示及上述代表驗收；預期沿用現有 session、policy、protocol、
transcript、pytest 與 Node test runner。

## 非目標

- 不執行 issue 02 的通用 menu 工作；它是外部前置條件。
- 不實作多回合 Citation workflow、Extended Thinking／Fusion Citation、
  registry persistence、恢復未完成工作或新的 protocol／storage schema。
- 不修 issue 04 resolver ambiguity、issue 05 save-result wording，
  不改 citation authority／identity／gate 演算法。
- 不新增服務、依賴、框架、模組層或 GUI 隱藏 dropdown state。
- 不改 AGENTS.md，不刪 legacy API，不整理無關程式碼；不操作真實使用者資料。

## 必須保留的行為與限制

- Citation 可信性只來自本次 service 接受的 save receipt；歷史文字與 tool payload
  不自動取得信任。保存授權仍可來自可見先前對話，不強迫重複問相同授權。
- 原子 bundle 寫入、existing bundle reuse、final-only answer 與既有 durable
  turnId／retry 行為保持；不為 lifecycle 換 schema 或重跑舊工具。
- **權威來源：** 根 AGENTS.md 與使用者提供的 Personal Engineering Defaults。
  Linux 為 supported runtime，Conda app 管 runtime，Poetry 管 Python 依賴；
  不用 Windows Python／Git、system Python、pip 或新 venv，文字使用 LF。
- **驗證限制：** 使用現有 fake model、RoutingFetcher、env={}、tmp_path；
  不讀 credentials、不呼叫 live／paid provider、不碰真實 output root。
  離線 scripted model 能驗證 wiring、trust、cleanup 與輸出，不證明真模型的回答品質。

## 待決事項與技術未知

- **使用者待決：** 是否採本建議單次契約（包括空 command、舊 off tokens、
  retention／restore 表），或保留明確多回合 workflow。
- **使用者待決：** 是否採工作內 normal、結束恢復原 mode；或本次加入 extended。
  已詢問但未答覆；未選不等於同意。正式選擇寫回本檔後才可實作。
- **啟動授權：** CLI 指令語意與 turn_outcome 對 Citation 的支援會改變 API 行為，
  且預估共六個 production files；具體實作範圍與授權門檻由 PLANS.md 管理。
- **技術未知：** issue 02 完成後的 catalog helper／型別名稱尚不存在；
  在 Desktop phase preflight 核對，不另建平行 catalog。
- **技術未知：** 原生 Linux Desktop fake backend 的可操作入口尚未確認；
  在 Desktop phase 先找現有啟動／測試接縫，無法安全提供就記 unavailable，
  不以 reducer test 冒充原生 UI 驗收。

## 來源

- 根 AGENTS.md、使用者於 2026-09-12 提供的 engineering defaults。
- issue/08-citation-skill-flow-deferred.md、issue/02-desktop-slash-command-menu.md。
- app/agent/cli/slash_commands.py、app/agent/cli/chat.py、app/agent/session.py。
- app/agent/skills/citation/session_policy.py、app/skills/citation/SKILL.md、
  app/skills/citation/service.py。
- app/agent/desktop/service.py、app/desktop/src/App.tsx、
  app/desktop/src/conversations.ts、app/desktop/src/protocol.ts。
- 對應測試與 live baseline／位置見 PLANS.md、各 phase。
