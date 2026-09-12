# Phase 02 — Thinking Effort button 與整合驗收

## 來源與目標

依 [GOALS](../GOALS.md)、[PLANS](../PLANS.md) 及 Phase 01 實際 evidence，
讓使用者在真實 Linux Desktop 選取核准段位、辨識有效設定、
完成下一回合及 A/B/restart 流程，保留現有交談控制。

來源：App.tsx:updateThinkingMode／session controls、protocol.ts、conversations.ts，
既有 Node protocol/conversations/backend tests、Python desktop service/conversation/
fixture tests、fixture_session.py、README 與 main.py。

## 範圍與非目標

範圍：原 Thinking control 的 button／選項、snapshot 回寫、錯誤／busy／focus、
真實操作、必要 integration assertions、最小既有用法說明與最後一次 broader checks。
非目標：一般 GUI 改版、App 重構、新設定中心／persistence／測試框架、
IME 安裝、live provider、model 品質評比、installer／發布。

## 依賴與前置條件

- Phase 01 在 build-log Complete，required evidence 可核對；不得跳過前階段驗證。
- 段位、workflow 關係、保存與 protocol 已定案，本階段不自行改產品答案。
- 待解：WSLg/Linux Desktop 可操作性、build cache、既有 FixtureSession 是否支援
  新契約；先唯讀檢查。必要時局部更新既有 fixture_session.py／test_desktop_fixture.py，
  必須在凍結 scope 內，不建新 fixture framework。
- 無 GUI 操作能力時先完成可獨立的離線檢查，必要 native evidence 保持 Blocked，
  請使用者提供操作結果或環境。Node source assertion／合成事件不能冒充真實 UI。
  不用真實 provider/store 繞過 fixture 限制。

## 預期受影響元件

app/desktop/src/App.tsx 為主；只有必要時調整現有控制區樣式
（先確認 live style path）、protocol/conversations 使用處及既有 tests。
FixtureSession 和對應 tests 僅補契約適配；README 僅更新 Thinking 用法／保存說明。
若需修 Phase 01 契約，先回 owning phase 處理，不在 UI 補假資料掩蓋。
候選路徑均受 PLANS 的最小 scope／授權門檻約束。

## 實作與驗證計劃

### Preflight、Red、Green

對照 live response／diff，確認 generation、session ID、workspace busy、
active turn 與 pending approval 的控制順序。重用既有 backend/conversation tests，
只有行為缺口才加最小 assertion，不以 source 字串當互動證據。

在原位置實作有名稱和有效值的 Thinking Effort button／選項，用既有 React/CSS。
選項遵循核准契約，不在 UI 發明第二份 mapping。後端成功才顯示生效值；
失敗保留舊值和既有 actionable error，stale generation／不同 session response
不能污染畫面。操作後可回 composer，草稿保留，不送出聊天。

Red 由目前尚無核准多段 button 的人工基準與最小 state/ack regression 建立；
不為測試另造通用 module。無獨立 refactor 工作。

### 代表性整合 journey

1. 隔離 fixture 啟動 Linux Desktop，建立 A，核對 button 初值／選項與
   authoritative snapshot 和定案 default。
2. 滑鼠、鍵盤可開啟、移動、選取、Escape 關閉；焦點／選中狀態可辨認。
   改設定不送 turn、不覆蓋草稿。
3. 選兩個不同核准值，分別送出同一 fixture 問題，確認 UI、ack 與觀察設定一致。
   真正 model mapping 的證據取 Phase 01 真實 ChatSession／fake transport；
   FixtureSession 模擬不能替代 runtime 證據。
4. A→B→A、新對話、restart 後選 A，逐項核對 GOALS 保存契約。
   同 session ID 的舊 generation reply 不改新畫面，歷史 transcript 保留可讀。
5. Active turn／pending approval／workspace operation 遵守禁用規則；
   非法／不支援／更新失敗顯示核准結果，舊有效值保留，可重試而不重複送聊天。
6. 用既有離線 tests 核對 CLI 相容、citation normal-only、installer restore、
   Bash ask/bypass、cancel/retry、final-only 與 canonical 保存，不做真實副作用操作。
7. 修改 Node protocol.test.ts 的舊 select 字串斷言時，
   保留 Product Plan Mode 退休的檢查。

所有核准段位都要檢查控制及 mapping，不對每個 model/role/platform 做交叉矩陣。
Native fixture journey 證明畫面／操作／bridge，真實 provider 另依契約與授權。

### Planned verification commands

全部使用 Linux Conda app，先跑新增／修改的最小 test nodes，再於 app/：

~~~bash
poetry run pytest tests/test_desktop_fixture.py tests/test_desktop_conversations.py tests/test_desktop_service.py -q
~~~

Phase 01 已通過且未再變更的 modules 不無故重跑。
局部和 journey 完成後，最後只跑一次：

~~~bash
poetry run pytest
~~~

於 app/desktop：

~~~bash
npm test
cargo test --offline --manifest-path src-tauri/Cargo.toml
npm run tauri -- build --no-bundle
~~~

Tauri source build 包含 npm run build，不另重跑相同 frontend build。
Preflight 核對 cache／近期 evidence；預估逾十分鐘、要下載或第二次 full suite
依 PLANS 取得授權。無關既有失敗分開報告，不擴張修復。

隔離 GUI 啟動，在 repo root、已啟用 Conda app：

~~~bash
THINKING_FIXTURE_ROOT=$(mktemp -d /tmp/research-agent-desktop-phase02-thinking-XXXXXX)
RESEARCH_AGENT_DESKTOP_FIXTURE=phase02 RESEARCH_AGENT_DESKTOP_FIXTURE_ROOT="$THINKING_FIXTURE_ROOT" python main.py
~~~

沿用現有 phase02 opt-in fixture，先確認 UI 是 deterministic fixture conversations；
A/B/restart 重用同一 owned tmp root。結束本次程序後，僅清理已核對絕對路徑、
ownership 的自有 temporary resources，不碰 user store。
最後於 repo root 執行 git diff --check，查看 status／diff。

## Reliability、失敗與恢復

前端跟隨後端有效值，錯誤／取消／stale response 不能誤標成功。
本階段不新增 storage/migration；保存問題按 Phase 01 已核准契約修復。
Required failure／缺少 native evidence 阻擋 Complete，不擴張為一般環境修復。

## 驗收

- [ ] 所有核准選項可用鍵盤／滑鼠操作；值、焦點、草稿、送出次數符合 journey。
- [ ] 選擇→下一回合由 UI/bridge 與真實 runtime 離線證據共同支持，
      不只靠 label、snapshot、source text 或 fixture 模擬。
- [ ] A/B、新對話／restart、舊資料、busy／approval、失敗／stale reply 符合契約。
- [ ] GOALS 保留行為通過，最小用法說明準確反映實際段位及保存方式。
- [ ] 最後一次 full pytest、Node／Rust suite、Linux source build 通過，
      或必要限制已由使用者明確接受；skipped／unavailable 不當作 pass。
- [ ] diff 僅含核准 scope，git diff --check 通過，原有工作保留。

## 證據與交接

在 ../build-log.md 記錄 exact commands、Linux UI 操作／結果、
criteria→evidence 及限制；重大發現才建 context，真 review 才建對應 review。
全部 GOALS 與 PLANS 完成標準達成才標 Complete，報告實際 files/checks/限制並停止，
不要繼續 polishing 或自行 Git 發布。
