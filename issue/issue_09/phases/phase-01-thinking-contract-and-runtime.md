# Phase 01 — Thinking 契約、runtime 與生命週期

## 來源與目標

依 [GOALS](../GOALS.md)、[PLANS](../PLANS.md) 和原 issue 09，
讓核准段位透過真實後端影響下一回合，並在指定生命週期、
Python／JSON／TypeScript／Rust 契約及舊資料相容方面保持一致。
相關來源為 PLANS baseline 的 session、CLI、service、model／graph、
orchestrator、conversations 和 protocol 檔案。

## 範圍與非目標

範圍是所選契約必要的 validation、CLI 相容、model request／workflow、
control snapshot、wire validation 及另獲核准的持久格式。
非目標是新 GUI 互動、任意段位、通用 provider adapter、模型評比或新 storage。
不能只改 enum／DTO，把實際生效或資料相容留給 Phase 02。

## 依賴與前置條件

- 無前置 phase；GOALS 三項產品決策及 PLANS 實作啟動門檻必須滿足。
  未定案則保持未啟動，不用暫用值先寫 code/tests。
- 定案後將 GOALS 轉成明確 mapping／lifecycle 預期，再凍結最小實作 scope。
  產品答案只存 GOALS，此 phase 引用它。
- 技術待解：若選 provider effort，檢查已 pin langchain-openrouter 實作與當時
  官方文件，確認參數／模型／角色及可用離線 request seam。
  kwargs 建構不證明遠端生效；必要 live check 須另外授權。
- 若獨立 effort，明示與 workflow mode 關係；若擴充 mode，先審查 durable turn
  exact schema 與核准相容處理。不能同時實作兩套候選方案。
- 新格式、migration、無可用 seam 均先形成具體最小方案及必要授權，
  不因技術困難擅自增加 persistent layer。

## 預期受影響元件

以下是條件式候選，啟動前依決策刪除不必要路徑：

- app/agent/session.py、cli/slash_commands.py、desktop/service.py：
  控制入口、回合生效、snapshot、Skill 邊界及核准 CLI 相容。
- app/desktop/protocol/v1/contract.json、fixtures.json、src/protocol.ts、
  src-tauri/src/protocol.rs：合法 requests／results 及 shared samples。
  Python desktop/protocol.py 已 generic 讀 contract，無缺口不改。
- app/agent/llm/openrouter.py、llm/thinking.py、graph.py、
  thinking/orchestrator.py、config.py：僅所選 mapping 影響的元件；
  局部更新實際用到的 model cache，不建通用 invalidation 框架。
- app/agent/conversations/models.py／repository.py：只有已核准的新 metadata
  或 preference 確實需改格式才動，不能順便遷移。
- 相應既有 Python／Node／Rust tests；保留 retired Product Plan Mode 斷言。

## 實作與驗證計劃

### Preflight 與 Red

核對 runtime、diff、核准契約與舊行為；重用 fake session、fake ChatOpenRouter、
monkeypatch、tmp_path 和現有 repository fixtures。

1. 真實 ChatSession 在同程序依次選兩個核准值再切回，逐次送同一代表性問題，
   觀察實際 routing／factory／transport 設定。最小 Red 須顯示未支援新契約
   或 cached model 還在用舊值；不能只斷言 config 字串不同。
2. 設定→snapshot→下一回合，以及 new／A→B→A／restart，取 GOALS 的確切預期。
   只補既有 tests 缺少的差異，不建立完整 model/role 交叉矩陣。
3. 非法值、不支援設定、busy／pending approval 確認沒有部分更新／錯誤 ack。
4. 若改格式，使用 tmp repository 的舊 normal／extended／display-only 資料，
   驗證讀取、寫回及核准 migration；不接觸真實對話。

### Green 與 Refactor

沿現有入口實作最小 mapping／validation，使下一回合真正生效。
依核准角色範圍更新 model／cache，保留工具權限與 history，不重載無關工具。
成功回 authoritative state；失敗維持原有效選擇並可重試。
同步跨語言 validator／fixture；遵守核准 CLI 相容與資料政策。
新段位不可繞過 citation／installer workflow 限制。

不安排獨立重構；必要檔內整理只在行為通過後、既有授權內進行，
之後重跑受影響 focused checks。

### Planned verification commands

以下只在未來實作執行，使用 Linux Conda app：

~~~bash
source /home/minervamuses/miniconda3/etc/profile.d/conda.sh
conda activate app
cd /home/minervamuses/research-agent-workspace/app
poetry run pytest tests/test_slash_commands.py tests/test_thinking_session.py tests/test_thinking_models.py tests/test_openrouter_model.py -q
poetry run pytest tests/test_desktop_protocol_contract.py tests/test_desktop_service.py tests/test_desktop_conversations.py tests/test_citation_skill_activation.py tests/test_skill_adherence.py -q
~~~

開發時先跑受影響 test node/module，上述是階段回歸邊界。
若動 orchestrator，再跑 poetry run pytest tests/test_thinking.py -q。
若動 durable format，再跑
poetry run pytest tests/test_conversation_repository.py tests/test_conversation_archive_access.py -q。

在 app/desktop 進行跨語言 focused checks：

~~~bash
node --test --experimental-strip-types tests/protocol.test.ts
cargo test --offline --manifest-path src-tauri/Cargo.toml protocol::tests
npm run build
~~~

Rust 沿用既有 suite，限 protocol test module；offline cache 不足先停止，不下載。
這些不是 GUI 操作證據。本階段不跑 full pytest；最後一次由 Phase 02 負責。
預估超十分鐘或不可用驗證依 PLANS 處理。

## Reliability、相容與恢復

保留 idle／approval 邊界。設定失敗不得更改有效值、歷史回合或部分 preference。
若核准持久化，需具體驗證寫入失敗、舊資料讀取、恢復結果；
不能假設 migration／回退天然安全。本機修補失敗保持 phase 未完成，
只修 scope 內 diff，不重設使用者原有工作。

## 驗收

- [ ] 每個核准值有可觀察映射；同 session 連續切換對下一回合生效，
      已建 model 亦有效，未指定的角色／workflow 不受影響。
- [ ] CLI／backend 接受、拒絕、snapshot 符合契約，Python/JSON/TS/Rust 無漏同步。
- [ ] preference 與 turn metadata 不混用；new／A→B→A／restart 及舊資料符合定案策略。
- [ ] 非法／不支援／busy／失敗無部分成功，citation／installer 保護通過。
- [ ] 必要 focused tests／frontend build 通過；缺少必要 evidence 不標 Complete。
      若契約要求真實 provider 證據，須另取得授權且驗證後才能完成。

## 證據與交接

將 exact commands、routing/request 觀察、lifecycle 值、資料結果及
acceptance→evidence 寫 ../build-log.md；重大發現才建 phase-01 context。
所有 required evidence 齊全才標 Complete；任何必要失敗均阻擋 Phase 02。
若新證據改變 GUI／保存理解，先修訂未開始 Phase 02，再依 PLANS 續作。
