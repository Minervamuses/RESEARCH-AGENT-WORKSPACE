# Issue 09 — Desktop Thinking Effort：執行計劃

## 計劃概況

- Plan root：issue/issue_09；穩定目標與產品決策見 [GOALS.md](GOALS.md)。
- Execution mode：Autonomous within authorization envelope。
  僅在產品定案、具體跨層 scope 獲核准且使用者要求實作後生效。
- Repository shape / risk：Application / medium；主要風險是 workflow／effort
  混淆、跨語言契約、cached model 和 preference／歷史資料邊界。
  若需資料遷移或較大改動，定案時重新評估範圍與授權。
- 沿用 issue/issue_XX/phases/；根 .gitignore 忽略 build/。
  兩個階段交付後端契約和完整使用者流程，不加純規劃階段。

## 資訊唯一來源

| 資訊 | Owner |
|---|---|
| 穩定目標、限制、產品答案 | GOALS.md |
| 階段順序、授權、停止、修訂、完成標準 | PLANS.md |
| 可複製的入口 | PROMPTS.md |
| 各階段範圍、planned checks、acceptance | phases/phase-*.md |
| 唯一 runtime status／observed evidence | build-log.md |
| 執行後重大發現／實際 review | context/、code_review/ |

不預建 context／review，不維護第二份 current-phase 指標。

## 已確認 repository baseline

2026-09-12 唯讀觀察如下；不是測試通過證據。

- Root /home/minervamuses/research-agent-workspace；唯一 repository AGENTS 在根。
  WSL Ubuntu-24.04；bash /usr/bin/bash、Git /usr/bin/git；
  Python 3.13.14、Poetry 2.4.1、Node、Cargo 均來自 Linux Conda app。
  PowerShell 只作 launcher；rg 不存在，使用 grep／find，不安裝工具。
- 初始 branch GUI、HEAD 2870bcd75eb809120f9e4bb7a2ab1668330946d6。
  原有 72 個未提交檔案項目：issue_03／issue_10 tracked deletions，
  issue_01、02、03(fin)、04、05、06、07、08、10(fin) 的 untracked 文件。
  原先沒有 issue_09。issue_08 在本次規劃期間由另一個任務完成修訂；
  本任務保留其最終內容。使用者已要求本次全部 commit/push。
  未來啟動必須重新讀 status，不能把此歷史快照當成當時狀態。
- session.py:118 預設 normal；set_thinking_mode():782 僅 normal／extended；
  _run_turn():1100 分流。slash_commands.py:359/:429 定義並處理相同 mode。
- desktop/service.py:_session_set_thinking():1992 經 idle guard 回 authoritative
  snapshot；_ConversationControlSnapshot:183、capture/apply:1166/1172、
  select:763 與 shutdown:2091/2103 實作同程序保存／重啟清空。
- conversations/models.py:27/43/405 限制 turn mode，
  repository.py:160/257 讀寫 thinkingMode 並採 exact-object validation；
  歷史 turn 並非 preference store。
- llm/openrouter.py:get_openrouter_chat_model():33 沒有傳 effort。
  graph.py:119/149/158 cache normal models；
  thinking/orchestrator.py:103–122/196 cache role／aggregator／proposer models。
  只改 config 或 DTO 不足以證明下一回合生效。
- session.py:787/789 限制 installer pending／citation active 的 Extended，
  :822 citation 強制 normal，:845 installer cleanup 恢復先前選擇。
- protocol/v1/contract.json:127/212/403、src/protocol.ts:248/362/548/667、
  src-tauri/src/protocol.rs:523/1048 各有限定值。
  Python desktop/protocol.py 直接載入 JSON；shared samples 是 fixtures.json。
- App.tsx:updateThinkingMode():1091 等待 ack 才回寫，使用 workspace operation、
  generation 與 session ID guards；:1262 是二段 select。
  conversations.ts:589 在 active turn 禁用 control。
- test_desktop_conversations.py:1421 覆蓋 A→B→A；
  test_desktop_fixture.py:632 覆蓋 restart normal 與歷史 mode 保留。
  test_openrouter_model.py:76 提供 pinned SDK 離線建構 seam。
  Node protocol.test.ts:175 同時保護 Product Plan Mode 退休及 Extended 存在，
  更新 select 斷言不可一併移除前者。
- desktop/package.json、README:157 提供 Node／Rust／source-build commands；
  server.py:397 選擇 opt-in phase02 無 provider FixtureSession；
  main.py 啟動現有 Tauri dev。

## 執行授權與停止條件

### 本次 authoring／Git

只新增本 bundle 六個 Markdown。使用者明確授權 commit 所有變更、
push 及確認同步，故本次可提交既有文件與新計劃，推送目前 GUI；
不改其他文件內容、不實作功能、不改 AGENTS。
此一次性 Git 授權不延伸至未來功能實作的 Git 操作。

### 實作啟動門檻

1. 取得 GOALS 三項決策，形成精確段位映射、預設、保存與相容結果。
2. 依決策收斂 phase 的候選路徑為最小 scope，凍結 method／DTO／持久格式
   差異與離線驗收。移除沒有直接因果需要的路徑，不能把候選清單當全改授權。
3. 呈現具體 scope、跨層必要性、預期時間／usage／maintenance cost，
   取得使用者明確實作啟動授權。尤其 public protocol／schema／持久結構及
   超過三個 production files 須符合 Personal Engineering Defaults。
4. 如本 session 已明確批准同一 scope，保存來源後直接執行，不重複索權。
   否則只處理計劃／決策；文件、「繼續規劃」或本次 Git 授權皆不算批准實作。

### 核准後例行範圍

可修改核准且直接必要的既有元件和最少 tests，跑階段內短時間離線檢查、
使用自有 temporary fixture，更新 log、重大 context、真實 review 及未開始 plans。
在授權內自主完成兩階段；不用逐步詢問，不新增抽象層或測試框架。

### Fresh authority／停止

- 產品決策缺漏、須改目標／相容性／必要驗證或超出凍結 scope。
- 未核准 public API／protocol／schema／格式／持久結構、dependency／lockfile、
  package manager／environment、storage／concurrency model。
- 額外 production paths、局部可解卻新增 persistent module、
  generic framework／registry／adapter 或廣泛重構。
- 新 benchmark／evaluation／fixture／regression framework、full-dataset replay、
  live paid-provider、model／GPU sweep、外部寫入或使用者資料操作。
- 預估超約十分鐘的命令、安裝／下載、第二次 full suite 或昂貴重跑。
- 未來實作的 commit/push/merge/rebase/切 branch/worktree/deploy，
  除非當時已有另外明確授權。
- 必要證據 unavailable 且最小離線替代不能回答驗收：保持 Blocked，
  說明缺少的證據與決策，不以 skipped 冒充 pass。

兩次 focused implementation attempts 失敗即停止並報告最小下一步；
一次 expensive attempt 無效不自行重跑。無關失敗不擴張修復。
根 AGENTS 與 Personal Engineering Defaults 持續有效。

## 階段路線與依賴

| Phase | 可觀察結果 | Depends on | Phase file |
|---|---|---|---|
| 01 — Thinking contract and runtime | 核准段位確實影響後端，lifecycle 與三語言契約一致 | 無前置 phase；產品決策及啟動門檻 | [phase-01-thinking-contract-and-runtime.md](phases/phase-01-thinking-contract-and-runtime.md) |
| 02 — Desktop control and acceptance | button 完成選擇、下一回合與 A/B/restart journey | Phase 01 Complete 且 required evidence 齊全 | [phase-02-desktop-control-and-acceptance.md](phases/phase-02-desktop-control-and-acceptance.md) |

Phase 01 同步 wire consumers 和 focused checks，不能把破碎契約留到 GUI 階段；
Phase 02 才加入新互動和一次 broader verification。不做中途發布。

## 計劃維護

- build-log 唯一保存狀態；開始前對照 live repository，依依賴選首個未完成 phase。
- Required failure／unverified acceptance 阻擋 dependent phase；先修當前 causal scope。
- 新證據否定路線時，先修訂本 roadmap 與受影響未開始 phase；
  active phase 只能在原授權內澄清，不藉修訂擴張權限。
- 穩定目標依使用者決策更新 GOALS；重大失敗／完成紀錄以 append correction 更正。
- 重大發現才建 context/phase-01-thinking-contract-and-runtime-context.md 或
  context/phase-02-desktop-control-and-acceptance-context.md；
  真 review 才建對應 code_review/phase-*-review.md。
- 修訂後重新從 PROMPTS 走讀，確保不需對話記憶或隱藏假設。

## 整體完成標準

- [ ] 所有 phases 在 build-log Complete，各 acceptance 連到 observed evidence。
- [ ] GOALS 每項成功條件均有支持，保存、失敗與相容結果已驗證。
- [ ] Focused checks 先通過，最後一次 full pytest、Node／Rust suite 與 Linux source
      build 按計劃完成；必要證據豁免只能由使用者明確接受。
- [ ] GUI fixture、真實 runtime 離線及 provider 的證據界線清楚，不互相冒充。
- [ ] diff 只含核准 scope，git diff --check 通過，原有工作保留；
      最小用法說明及未驗證限制已記錄，完成即停止。

## Authoring write set

只新增 GOALS.md、PLANS.md、PROMPTS.md、build-log.md 與 roadmap 兩個 phase files。
初始全部 Not started，不建立 context／review，不回填 implementation evidence。
